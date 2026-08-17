package io.github.richeyworks.csrbt.evolution;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.TreeEngineRegistry;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.strategy.*;
import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.control.WorkloadMonitor;
import io.github.richeyworks.csrbt.control.CostModelStrategyScorer;
import io.github.richeyworks.csrbt.control.MorphController;
import io.github.richeyworks.csrbt.control.StrategyId;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

/**
 * GenomeDrivenTreeController v2
 *
 * The tree that listens to its genome, remembers what worked, and evolves.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * FIXES FROM v1
 *
 *   1. REAL MORPH   — context.setStrategy() already rebuilds via inOrder
 *                     traversal + re-insert; this is now explicit, documented,
 *                     and verified rather than a side-effect we relied on silently.
 *
 *   2. REAL HYBRID  — HybridStrategy is a first-class TreeStrategy with AVL
 *                     rebalancing + RB recolor pass.  Not "RB pretending".
 *
 *   3. PERFORMANCE  — {@code Map<StructureType, PerformanceRecord>} tracks avg depth,
 *                     rotation rate, and op timing per strategy.  The genome's
 *                     fitness recommendation is biased by historical data.
 *
 *   4. ACCESS TRACK — recordAccess(value) feeds entropy so search locality
 *                     (the primary signal for Splay preference) is visible.
 * ─────────────────────────────────────────────────────────────────────────────
 */
public class GenomeDrivenTreeController {

    private static final Logger logger = LogManager.getLogger(GenomeDrivenTreeController.class);

    private static final int EVAL_INTERVAL    = 10;
    private static final int WINDOW_SIZE      = 50;
    private static final int STAGNATION_LIMIT = 5;

    // ── Performance memory ────────────────────────────────────────────────────

    /**
     * Running performance record for one StructureType.
     * Updated every eval cycle while that strategy is active.
     */
    public static class PerformanceRecord {
        private final TreeGenome.StructureType type;
        private double totalAvgDepth    = 0.0;
        private double totalRotRate     = 0.0;
        private int    samples          = 0;

        public PerformanceRecord(TreeGenome.StructureType type) { this.type = type; }

        void record(double avgDepth, double rotRate) {
            totalAvgDepth += avgDepth;
            totalRotRate  += rotRate;
            samples++;
        }

        /** Lower = better: normalized sum of avg depth + rotation pressure. */
        public double score() {
            if (samples == 0) return Double.MAX_VALUE; // unknown — try it
            return (totalAvgDepth / samples) + (totalRotRate / samples);
        }

        public int getSamples()  { return samples; }
        public TreeGenome.StructureType getType() { return type; }

        @Override
        public String toString() {
            return type + "[samples=" + samples +
                   ", avgDepthMean=" + String.format("%.3f", samples == 0 ? 0 : totalAvgDepth / samples) +
                   ", rotRateMean="  + String.format("%.3f", samples == 0 ? 0 : totalRotRate  / samples) +
                   ", score="        + String.format("%.3f", score()) + "]";
        }
    }

    // ── State ─────────────────────────────────────────────────────────────────

    private TreeContext context;
    private TreeGenome  genome;

    private final int[]  recentValues = new int[WINDOW_SIZE];
    private int          windowHead   = 0;
    private int          windowFill   = 0;

    private int    rotationsAtLastWindow  = 0;
    private int    opCount                = 0;
    private int    morphCount             = 0;
    private int    stagnationCounter      = 0;

    private double lastStress        = 0.0;
    private double lastEntropy       = 0.0;
    private double lastFragmentation = 0.0;
    private double lastMorphPressure = 0.0;

    // ── Morph policy state (anti-thrash gating, DESIGN §3.3) ──────────────────
    private int                       lastMorphOpCount = 0;
    private TreeGenome.StructureType  lastCandidate    = null;
    private int                       candidateStreak  = 0;
    private MorphPolicy               morphPolicy      = MorphPolicy.defaults();

    /** Historical performance per strategy type. */
    private final Map<TreeGenome.StructureType, PerformanceRecord> performanceMemory =
            new EnumMap<>(TreeGenome.StructureType.class);

    /** Morph history log: [{from, to, pressure, opCount}] */
    private final List<MorphEvent> morphLog = new ArrayList<>();

    private TreeGenome.StructureType activeStrategyType;

    // Control-plane workload monitor (ADR-002 step 6 Phase D / D3): observation-only.
    // Every op feeds an O(1) rolling summary; nothing in the genome decision path reads
    // it yet (the re-point to the control plane is D4).
    private final WorkloadMonitor workloadMonitor = new RollingWorkloadMonitor();

    // Control-plane re-point (ADR-002 step 6 Phase D). Flag-gated; default ON since D5 — the
    // WorkloadMonitor -> StrategyScorer -> MorphPolicy pipeline now drives adaptation. Set false
    // to fall back to the (deprecated) genome decision body, which is retained for one-switch rollback.
    private boolean useControlPlane = true;
    private int     lastControlEvalOpCount = 0;
    private final MorphController<Integer> morphController;

    // ── Constructor ───────────────────────────────────────────────────────────

    public GenomeDrivenTreeController(TreeContext context, TreeGenome genome) {
        this(context, genome, io.github.richeyworks.csrbt.control.MorphPolicy.defaults());
    }

    /**
     * Test/convergence seam (ADR-002 step 6 Phase D — plan §4.6 and the D5 note that a
     * convergence harness may use "an eager {@code MorphPolicy(small cooldown, …)} to keep
     * runtime bounded"). Builds the control-plane {@link MorphController} with an explicit
     * {@code controlPolicy} over this controller's own monitor, so a test can inject an eager
     * policy and exercise a morph without driving the full 4000-op default cooldown.
     * Production uses the two-arg constructor, which passes {@link io.github.richeyworks.csrbt.control.MorphPolicy#defaults()}.
     */
    public GenomeDrivenTreeController(TreeContext context, TreeGenome genome,
                                      io.github.richeyworks.csrbt.control.MorphPolicy controlPolicy) {
        if (context == null)       throw new IllegalArgumentException("context cannot be null");
        if (genome  == null)       throw new IllegalArgumentException("genome cannot be null");
        if (controlPolicy == null) throw new IllegalArgumentException("controlPolicy cannot be null");
        this.context            = context;
        this.genome             = genome;
        // The incumbent is what the TREE runs, not what the genome wishes (bug audit
        // 2026-08-12, G-B): initializing from the genome's preference meant a
        // genome/context mismatch (reachable via breedWith) reported the preferred
        // strategy as "active", every evaluation saw best == current, and the tree was
        // never morphed to the strategy the controller believed was running.
        this.activeStrategyType = inferStructureType(context);
        this.morphController = new MorphController<>(
                context, workloadMonitor, new CostModelStrategyScorer(), controlPolicy);

        // Pre-populate performance records for all known types
        for (TreeGenome.StructureType t : TreeGenome.StructureType.values()) {
            performanceMemory.put(t, new PerformanceRecord(t));
        }

        logger.info("GenomeDrivenTreeController v2 initialized — genome={}, structure={}",
                genome.getGenomeId(), genome.getPreferredStructure());
    }

    public static GenomeDrivenTreeController fromContext(TreeContext context) {
        return new GenomeDrivenTreeController(context, inferGenomeFromContext(context));
    }

    // ── Tree operations ───────────────────────────────────────────────────────

    public void add(int value) {
        boolean inserted = context.add(Integer.valueOf(value));
        if (inserted) workloadMonitor.recordAdd(Integer.hashCode(value), 0);
        recordAccess(value);   // inserts count as accesses
        afterOperation();
    }

    public void remove(int value) {
        boolean removed = context.remove(Integer.valueOf(value));
        if (removed) workloadMonitor.recordRemove(Integer.hashCode(value), 0);
        afterOperation();
    }

    public boolean contains(int value) {
        boolean found = context.contains(value);
        recordAccess(value);   // search locality feeds entropy
        workloadMonitor.recordSearch(Integer.hashCode(value), 0);
        if (useControlPlane) afterOperation();   // reads drive the eval cadence on the new path (plan B2)
        return found;
    }

    // ── Evaluation loop ───────────────────────────────────────────────────────

    private void afterOperation() {
        opCount++;
        if (opCount % EVAL_INTERVAL == 0) evaluate();
    }

    public void evaluate() {
        if (useControlPlane) evaluateViaControlPlane();
        else evaluateViaGenome();
    }

    /**
     * Control-plane evaluation (ADR-002 step 6 Phase D / D4): WorkloadMonitor -> StrategyScorer
     * -> MorphPolicy via the MorphController, driving the health-gated setStrategy. The
     * MorphController emits the single event=morph_eval line for the evaluation.
     */
    private void evaluateViaControlPlane() {
        StrategyId current;
        try {
            current = StrategyIdBridge.toStrategyId(activeStrategyType);
        } catch (IllegalArgumentException e) {
            current = null;   // incumbent has no StrategyId (non-strategy type) -> treat as unknown
        }
        int opsElapsed = opCount - lastControlEvalOpCount;
        lastControlEvalOpCount = opCount;
        MorphController.MorphResult r = morphController.evaluateAndMaybeMorph(current, opsElapsed);
        if (r.morphed()) {
            activeStrategyType = StrategyIdBridge.toStructureType(r.to());
            morphCount++;
            lastMorphOpCount = opCount;
        }
    }

    /** Legacy genome-driven evaluation (retained behind the flag; demoted in D5). */
    private void evaluateViaGenome() {
        // Record performance for the currently active strategy
        recordCurrentPerformance();

        // Compute live metrics
        lastStress        = computeStress();
        lastEntropy       = computeEntropy();
        lastFragmentation = computeFragmentation();
        lastMorphPressure = genome.computeMorphPressure(lastStress, lastEntropy, lastFragmentation);

        // Decision tracked for the structured observability line (DESIGN §12).
        String                   decision = "HOLD";
        TreeGenome.StructureType from     = activeStrategyType;
        TreeGenome.StructureType to       = activeStrategyType;

        if (genome.shouldMorph(lastStress, lastEntropy, lastFragmentation)) {
            TreeGenome.StructureType chosen = chooseStrategyWithMemory();

            // Stability gate: count consecutive evaluations the same candidate
            // wins. Adapting to a flickering winner is worse than holding.
            if (chosen == lastCandidate) candidateStreak++;
            else { lastCandidate = chosen; candidateStreak = 1; }

            if (chosen != activeStrategyType) {
                double currentScore   = combinedScore(activeStrategyType);
                double candidateScore = combinedScore(chosen);
                int    opsSinceMorph  = opCount - lastMorphOpCount;
                if (morphPolicy.shouldMorph(currentScore, candidateScore, opsSinceMorph, candidateStreak)) {
                    applyStructure(chosen);          // sets lastMorphOpCount
                    candidateStreak = 0;
                    lastCandidate   = null;
                    decision = "MORPH";
                    to       = chosen;
                }
            }
        } else {
            stagnationCounter++;
            if (stagnationCounter >= STAGNATION_LIMIT) {
                logger.info("Stagnation: micro-mutating genome.");
                genome.mutate();
                stagnationCounter = 0;
            }
        }

        emitMorphEval(decision, from, to);
        rotationsAtLastWindow = context.getRotationCount();
    }

    /**
     * One structured line per evaluation (DESIGN §12) so adaptation is auditable:
     * features, per-strategy scores, and the decision. Any morph is reconstructable
     * from this single line.
     */
    private void emitMorphEval(String decision, TreeGenome.StructureType from,
                               TreeGenome.StructureType to) {
        StringBuilder scores = new StringBuilder("[");
        boolean first = true;
        for (TreeGenome.StructureType t : implementedTypes()) {
            if (!first) scores.append(", ");
            scores.append(t).append(':').append(fmt(combinedScore(t)));
            first = false;
        }
        scores.append(']');
        logger.info("event=morph_eval n={} stress={} entropy={} frag={} pressure={} scores={} decision={} from={} to={}",
                context.getSize(), fmt(lastStress), fmt(lastEntropy), fmt(lastFragmentation),
                fmt(lastMorphPressure), scores, decision, from, to);
    }

    public void forceMorph() {
        TreeGenome.StructureType chosen = chooseStrategyWithMemory();
        applyStructure(chosen);
    }

    // ── Morph with real rebuild ───────────────────────────────────────────────

    /**
     * Applies a new structure type.
     *
     * context.setStrategy() already performs a full rebuild:
     *   1. inOrder traversal → element list
     *   2. tree.setRoot(NIL), size = 0
     *   3. re-insert all elements under the new strategy
     *
     * This is explicit here so it is never accidentally bypassed.
     */
    private void applyStructure(TreeGenome.StructureType type) {
        TreeStrategy<Integer> newStrategy = buildStrategy(type);
        if (newStrategy == null) {
            logger.warn("No strategy for {} — morph skipped.", type);
            return;
        }

        TreeGenome.StructureType from = activeStrategyType;
        logger.info("🧬 MORPH: {} → {} (pressure={}, gen={})",
                from, type, fmt(lastMorphPressure), genome.getGeneration());

        // ── REAL REBUILD ──────────────────────────────────────────────────────
        // setStrategy does: inOrderTraversal → clear → re-insert all values.
        // No data is lost; every node is rebalanced under the new rules.
        // setStrategy can REFUSE (health-gate failure, same-policy no-op) — commit
        // controller/genome state only on a real morph, or the incumbent lies, the
        // cooldown clock starts for a morph that never happened, and morphLog records
        // a phantom (the read-side desync class G-B fixed, now closed on the write
        // side too; MorphController already checked this verdict correctly).
        boolean applied = context.setStrategy(newStrategy);
        // ─────────────────────────────────────────────────────────────────────
        if (!applied) {
            logger.warn("Morph {} → {} refused by the engine (health gate or same policy) — "
                    + "controller state unchanged.", from, type);
            return;
        }

        activeStrategyType = type;
        genome.setPreferredStructure(type);
        genome.mutate();
        morphCount++;
        stagnationCounter = 0;
        lastMorphOpCount  = opCount;   // start the cooldown window

        morphLog.add(new MorphEvent(from, type, lastMorphPressure, opCount));
        logger.info("Morph complete. treeSize={}, morphCount={}", context.getSize(), morphCount);
    }

    // ── Memory-biased strategy selection ─────────────────────────────────────

    /**
     * Blends genome fitness score with historical performance memory.
     *
     * Combined score = (genome fitness × 0.6) + (memory score × 0.4)
     *
     * Memory score is inverted (lower = better → higher combined score).
     * Unknown strategies (0 samples) are given a bonus to encourage exploration.
     */
    private TreeGenome.StructureType chooseStrategyWithMemory() {
        TreeGenome.StructureType best     = null;
        double                   bestScore = Double.NEGATIVE_INFINITY;

        for (TreeGenome.StructureType type : implementedTypes()) {
            double combined = combinedScore(type);
            if (combined > bestScore) {
                bestScore = combined;
                best      = type;
            }
        }

        logger.debug("Memory-biased selection: {} (score={})", best, fmt(bestScore));
        return best != null ? best : genome.recommendedStructure();
    }

    /**
     * Combined desirability of a structure: genome fitness (0.6) blended with
     * historical performance memory (0.4). Higher is better. Untried strategies
     * get a neutral 0.5 memory term so they remain eligible for exploration.
     */
    private double combinedScore(TreeGenome.StructureType type) {
        double genomeFitness = genome.fitnessFor(type);   // 0-1, higher = better
        PerformanceRecord rec = performanceMemory.get(type);
        double memoryScore;
        if (rec.getSamples() == 0) {
            memoryScore = 0.5;                              // exploration bonus
        } else {
            memoryScore = Math.max(0.0, 1.0 - (rec.score() / 10.0));
        }
        return (genomeFitness * 0.6) + (memoryScore * 0.4);
    }

    // ── Performance tracking ──────────────────────────────────────────────────

    private void recordCurrentPerformance() {
        int n = context.getSize();
        if (n == 0) return;

        int actualHeight = measuredHeight();   // G-D: never trust the cached height
        double avgDepth  = actualHeight == 0 ? 0.0 : (double) actualHeight / Math.max(1, log2ceil(n));

        int rotDelta = Math.max(0, context.getRotationCount() - rotationsAtLastWindow);
        double rotRate = (double) rotDelta / Math.max(1, EVAL_INTERVAL);

        performanceMemory.get(activeStrategyType).record(avgDepth, rotRate);
    }

    // ── Metric computation ────────────────────────────────────────────────────

    private double computeStress() {
        if (windowFill == 0) return 0.0;
        int rotationsDelta = Math.max(0, context.getRotationCount() - rotationsAtLastWindow);
        return Math.min(1.0, (double) rotationsDelta / Math.max(1, windowFill));
    }

    /**
     * Shannon entropy of the access window bucketed into 8 ranges.
     * Covers BOTH inserts and searches — Splay's locality signal comes from
     * repeated searches on the same values, not just insertions.
     */
    private double computeEntropy() {
        if (windowFill < 2) return 0.5;

        // Bucket by the window's OBSERVED key range, not the absolute int range (bug
        // audit 2026-08-12, G-A): with 2^32/8 ≈ 5.4e8-wide absolute buckets, every
        // realistic workload — uniform-random in [0, 1e6) and a single hot key alike —
        // landed in bucket 0 and read entropy 0.0, blinding the Splay locality signal
        // this metric is documented as ("the primary signal for Splay preference").
        final int BUCKETS = 8;
        long min = Long.MAX_VALUE, max = Long.MIN_VALUE;
        for (int i = 0; i < windowFill; i++) {
            min = Math.min(min, recentValues[i]);
            max = Math.max(max, recentValues[i]);
        }
        long span = max - min + 1;
        if (span <= 1) return 0.0;   // one distinct key: genuinely zero entropy

        int[] counts = new int[BUCKETS];
        for (int i = 0; i < windowFill; i++) {
            long shifted = (long) recentValues[i] - min;
            int  bucket  = (int) Math.min(BUCKETS - 1, (shifted * BUCKETS) / span);
            counts[bucket]++;
        }

        double entropy    = 0.0;
        double maxEntropy = Math.log(BUCKETS) / Math.log(2);
        for (int c : counts) {
            if (c > 0) {
                double p = (double) c / windowFill;
                entropy -= p * (Math.log(p) / Math.log(2));
            }
        }
        return Math.min(1.0, entropy / maxEntropy);
    }

    private double computeFragmentation() {
        int n = context.getSize();
        if (n < 2) return 0.0;
        int actualHeight = measuredHeight();   // G-D: never trust the cached height
        if (actualHeight == 0) return 0.0;
        double idealHeight = log2ceil(n);
        return Math.max(0.0, Math.min(1.0, 1.0 - (idealHeight / actualHeight)));
    }

    // ── Access window ─────────────────────────────────────────────────────────

    /** Records an access (insert or search) into the rolling window. Deletes do NOT
     *  feed the window — the entropy signal reads insert/search locality only (doc
     *  drift noted in the 2026-08-12 fourth-pass audit; behavior unchanged). */
    private void recordAccess(int value) {
        recentValues[windowHead] = value;
        windowHead = (windowHead + 1) % WINDOW_SIZE;
        if (windowFill < WINDOW_SIZE) windowFill++;
    }

    // ── Evolution API ─────────────────────────────────────────────────────────

    public GenomeDrivenTreeController breedWith(GenomeDrivenTreeController other) {
        TreeGenome child = TreeGenome.crossover(this.genome, other.genome);
        logger.info("Crossover: {} × {} → gen-{}",
                this.genome.getGenomeId(), other.genome.getGenomeId(), child.getGeneration());
        return new GenomeDrivenTreeController(this.context, child);
    }

    public void nudgeGenome() {
        genome.mutate();
    }

    // ── Diagnostics ───────────────────────────────────────────────────────────

    public String diagnosticsReport() {
        StringBuilder sb = new StringBuilder();
        sb.append("═══════════════════════════════════════════════════════\n");
        sb.append(" GENOME-DRIVEN TREE DIAGNOSTICS v2\n");
        sb.append("═══════════════════════════════════════════════════════\n");
        sb.append(" Genome:        ").append(genome.getGenomeId()).append("\n");
        sb.append(" Generation:    ").append(genome.getGeneration()).append("\n");
        sb.append(" Lineage:       ").append(genome.getLineageTag()).append("\n");
        sb.append(" Active:        ").append(activeStrategyType).append("\n");
        sb.append("───────────────────────────────────────────────────────\n");
        sb.append(" Tree size:     ").append(context.getSize()).append("\n");
        sb.append(" Rotations:     ").append(context.getRotationCount()).append("\n");
        sb.append(" Morph count:   ").append(morphCount).append("\n");
        sb.append("───────────────────────────────────────────────────────\n");
        sb.append(" Live metrics:\n");
        sb.append("   stress        = ").append(fmt(lastStress)).append("\n");
        sb.append("   entropy       = ").append(fmt(lastEntropy)).append("\n");
        sb.append("   fragmentation = ").append(fmt(lastFragmentation)).append("\n");
        sb.append("   morph pressure= ").append(fmt(lastMorphPressure)).append("\n");
        sb.append("   threshold     = ").append(fmt(genome.getMorphTraits().getMorphThreshold())).append("\n");
        sb.append("───────────────────────────────────────────────────────\n");
        sb.append(" Performance memory:\n");
        for (TreeGenome.StructureType t : implementedTypes()) {
            sb.append("   ").append(performanceMemory.get(t)).append("\n");
        }
        sb.append("───────────────────────────────────────────────────────\n");
        sb.append(" Genome scorecard:\n   ").append(genome.scoreCard()).append("\n");
        sb.append(" Recommendation: ").append(genome.explainRecommendedStructure()).append("\n");
        sb.append(" Dominant bias:  ").append(genome.dominantBiasLabel()).append("\n");
        sb.append("───────────────────────────────────────────────────────\n");
        sb.append(" Conflict report: ").append(genome.conflictReport()).append("\n");
        sb.append("───────────────────────────────────────────────────────\n");
        sb.append(" Morph log (last 10):\n");
        int start = Math.max(0, morphLog.size() - 10);
        for (int i = start; i < morphLog.size(); i++) {
            sb.append("   ").append(morphLog.get(i)).append("\n");
        }
        sb.append("═══════════════════════════════════════════════════════\n");
        return sb.toString();
    }

    // ── Strategy factory ──────────────────────────────────────────────────────

    private static TreeStrategy<Integer> buildStrategy(TreeGenome.StructureType type) {
        return switch (type) {
            case RED_BLACK      -> new RedBlackStrategy<>();
            case AVL            -> new AVLStrategy<>();
            case SPLAY          -> new SplayStrategy<>();
            case HYBRID         -> new HybridStrategy<>();
            // These are NOT red-black strategies. PERSISTENT_TREE is a standalone
            // TreeEngine (build it via TreeEngineRegistry.create); FIBONACCI_HEAP
            // and VAN_EMDE_BOAS are intentionally unsupported (non-ordered-map
            // contracts). Failing loudly here beats the old silent null, which
            // setStrategy() swallowed as a no-op morph.
            case FIBONACCI_HEAP,
                 VAN_EMDE_BOAS,
                 PERSISTENT_TREE ->
                    throw new UnsupportedOperationException(
                        type + " is not a red-black strategy. "
                      + TreeEngineRegistry.capability(type).note);
        };
    }

    private static List<TreeGenome.StructureType> implementedTypes() {
        return List.of(
                TreeGenome.StructureType.RED_BLACK,
                TreeGenome.StructureType.AVL,
                TreeGenome.StructureType.SPLAY,
                TreeGenome.StructureType.HYBRID
        );
    }

    // ── Genome inference ──────────────────────────────────────────────────────

    private static TreeGenome inferGenomeFromContext(TreeContext context) {
        return switch (context.getTree().getStrategy().getClass().getSimpleName()) {
            case "AVLStrategy"    -> TreeGenome.avlGenome();
            case "SplayStrategy"  -> TreeGenome.splayGenome();
            case "HybridStrategy" -> TreeGenome.hybridGenome();
            default               -> TreeGenome.redBlackGenome();
        };
    }

    /** The installed strategy's structure type — the honest incumbent (G-B). */
    private static TreeGenome.StructureType inferStructureType(TreeContext context) {
        return switch (context.getTree().getStrategy().getClass().getSimpleName()) {
            case "AVLStrategy"    -> TreeGenome.StructureType.AVL;
            case "SplayStrategy"  -> TreeGenome.StructureType.SPLAY;
            case "HybridStrategy" -> TreeGenome.StructureType.HYBRID;
            default               -> TreeGenome.StructureType.RED_BLACK;
        };
    }

    /**
     * Actual tree height by an iterative walk (single node = 1). Cached node heights
     * are maintained only by AVL/Hybrid — under Red-Black/Splay/WB they go stale, the
     * bug class already confirmed in {@code TreeEcology.rKScore} (bug audit 2026-08-12,
     * G-D): a 500-key sequential RB tree cached height 9 against a real 15, reading
     * fragmentation 0.0 and biasing performance memory toward RB.
     */
    private int measuredHeight() {
        TreeNode1<Integer> root = context.getTree().getRoot();
        if (root == null || root.isNil()) return 0;
        java.util.ArrayDeque<TreeNode1<Integer>> nodes = new java.util.ArrayDeque<>();
        java.util.ArrayDeque<Integer> depths = new java.util.ArrayDeque<>();
        nodes.push(root);
        depths.push(1);
        int max = 0;
        while (!nodes.isEmpty()) {
            TreeNode1<Integer> n = nodes.pop();
            int d = depths.pop();
            if (d > max) max = d;
            if (!n.getLeft().isNil())  { nodes.push(n.getLeft());  depths.push(d + 1); }
            if (!n.getRight().isNil()) { nodes.push(n.getRight()); depths.push(d + 1); }
        }
        return max;
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static double log2ceil(int n) {
        return Math.ceil(Math.log(n) / Math.log(2));
    }

    private static String fmt(double v) {
        return String.format("%.4f", v);
    }

    // ── Morph event record ────────────────────────────────────────────────────

    public static class MorphEvent {
        public final TreeGenome.StructureType from;
        public final TreeGenome.StructureType to;
        public final double morphPressure;
        public final int    opCountAtMorph;

        public MorphEvent(TreeGenome.StructureType from, TreeGenome.StructureType to,
                          double morphPressure, int opCountAtMorph) {
            this.from           = from;
            this.to             = to;
            this.morphPressure  = morphPressure;
            this.opCountAtMorph = opCountAtMorph;
        }

        @Override
        public String toString() {
            return "[op=" + opCountAtMorph + "] " + from + " → " + to +
                   " (pressure=" + String.format("%.4f", morphPressure) + ")";
        }
    }

    // ── Morph policy ────────────────────────────────────────────────────────────

    /**
     * Anti-thrash gating for morphs (DESIGN §3.3). A pure decision function:
     * given the incumbent vs candidate desirability scores (higher = better),
     * how many ops have elapsed since the last morph, and how many consecutive
     * evaluations the candidate has won, decide whether to morph now. All three
     * gates must pass:
     *
     * <ul>
     *   <li><b>cooldown</b> — at least {@code cooldownOps} ops since the last morph;</li>
     *   <li><b>stability</b> — the candidate has won at least {@code stabilityWins}
     *       consecutive evaluations;</li>
     *   <li><b>minimum improvement</b> — the candidate beats the incumbent by at
     *       least {@code minImprovement} (fractional), not merely marginally.</li>
     * </ul>
     *
     * @deprecated ADR-002 step 6 Phase D / D5: promoted to {@code core.control.MorphPolicy}, which
     *     the control plane uses. This nested copy is retained only for the legacy (flag-off)
     *     decision body and its unit test; prefer {@code core.control.MorphPolicy}.
     */
    @Deprecated
    public static final class MorphPolicy {
        private final int    cooldownOps;
        private final double minImprovement;   // fractional, e.g. 0.20 = 20%
        private final int    stabilityWins;

        public MorphPolicy(int cooldownOps, double minImprovement, int stabilityWins) {
            this.cooldownOps    = Math.max(0, cooldownOps);
            this.minImprovement = Math.max(0.0, minImprovement);
            this.stabilityWins  = Math.max(1, stabilityWins);
        }

        /** Defaults from DESIGN §3.3: 4000-op cooldown, 20% margin, 3 wins. */
        public static MorphPolicy defaults() { return new MorphPolicy(4000, 0.20, 3); }

        public boolean shouldMorph(double currentScore, double candidateScore,
                                   int opsSinceLastMorph, int consecutiveWins) {
            if (opsSinceLastMorph < cooldownOps)  return false;   // cooldown
            if (consecutiveWins   < stabilityWins) return false;  // stability
            if (candidateScore   <= currentScore)  return false;  // must be better
            double improvement =
                    (candidateScore - currentScore) / Math.max(1e-9, Math.abs(currentScore));
            return improvement >= minImprovement;                 // by a margin
        }

        public int    cooldownOps()    { return cooldownOps; }
        public double minImprovement() { return minImprovement; }
        public int    stabilityWins()  { return stabilityWins; }
    }

    /** @deprecated legacy (flag-off) gate; the control plane uses {@code core.control.MorphPolicy}. */
    @Deprecated
    public MorphPolicy getMorphPolicy()              { return morphPolicy; }
    /** @deprecated legacy (flag-off) gate; the control plane uses {@code core.control.MorphPolicy}. */
    @Deprecated
    public void        setMorphPolicy(MorphPolicy p) { this.morphPolicy = (p != null) ? p : MorphPolicy.defaults(); }

    // ── Getters ───────────────────────────────────────────────────────────────

    public TreeGenome    getGenome()                    { return genome; }
    public TreeContext   getContext()                   { return context; }
    public int           getMorphCount()                { return morphCount; }
    public double        getLastStress()                { return lastStress; }
    public double        getLastEntropy()               { return lastEntropy; }
    public double        getLastFragmentation()         { return lastFragmentation; }
    public double        getLastMorphPressure()         { return lastMorphPressure; }
    public List<MorphEvent> getMorphLog()               { return Collections.unmodifiableList(morphLog); }
    public Map<TreeGenome.StructureType, PerformanceRecord> getPerformanceMemory() {
        return Collections.unmodifiableMap(performanceMemory);
    }
    public TreeGenome.StructureType getActiveStrategyType() { return activeStrategyType; }
    /** The control-plane workload monitor fed by every op (observation-only in D3). */
    public WorkloadMonitor getWorkloadMonitor() { return workloadMonitor; }

    /** Toggle the control-plane re-point (ADR-002 step 6 Phase D). Default ON —
     *  the field and its pinning test agree; this doc used to say OFF (drift noted
     *  in the 2026-08-12 fourth-pass audit). Turn OFF to use the legacy
     *  genome-metrics path (stress/entropy/fragmentation). */
    public void    setUseControlPlane(boolean on) { this.useControlPlane = on; }
    public boolean isUseControlPlane()            { return useControlPlane; }
}
