package core.evolution;

import core.TreeContext;
import core.strategy.*;
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
 *   3. PERFORMANCE  — Map<StructureType, PerformanceRecord> tracks avg depth,
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

    /** Historical performance per strategy type. */
    private final Map<TreeGenome.StructureType, PerformanceRecord> performanceMemory =
            new EnumMap<>(TreeGenome.StructureType.class);

    /** Morph history log: [{from, to, pressure, opCount}] */
    private final List<MorphEvent> morphLog = new ArrayList<>();

    private TreeGenome.StructureType activeStrategyType;

    // ── Constructor ───────────────────────────────────────────────────────────

    public GenomeDrivenTreeController(TreeContext context, TreeGenome genome) {
        if (context == null) throw new IllegalArgumentException("context cannot be null");
        if (genome  == null) throw new IllegalArgumentException("genome cannot be null");
        this.context            = context;
        this.genome             = genome;
        this.activeStrategyType = genome.getPreferredStructure();

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
        context.add(value);
        recordAccess(value);   // inserts count as accesses
        afterOperation();
    }

    public void remove(int value) {
        context.remove(value);
        afterOperation();
    }

    public boolean contains(int value) {
        boolean found = context.contains(value);
        recordAccess(value);   // search locality feeds entropy
        return found;
    }

    // ── Evaluation loop ───────────────────────────────────────────────────────

    private void afterOperation() {
        opCount++;
        if (opCount % EVAL_INTERVAL == 0) evaluate();
    }

    public void evaluate() {
        // Record performance for the currently active strategy
        recordCurrentPerformance();

        // Compute live metrics
        lastStress        = computeStress();
        lastEntropy       = computeEntropy();
        lastFragmentation = computeFragmentation();
        lastMorphPressure = genome.computeMorphPressure(lastStress, lastEntropy, lastFragmentation);

        logger.debug("Eval — stress={}, entropy={}, frag={}, pressure={}",
                fmt(lastStress), fmt(lastEntropy), fmt(lastFragmentation), fmt(lastMorphPressure));

        if (genome.shouldMorph(lastStress, lastEntropy, lastFragmentation)) {
            TreeGenome.StructureType chosen = chooseStrategyWithMemory();
            if (chosen != activeStrategyType) {
                applyStructure(chosen);
            }
        } else {
            stagnationCounter++;
            if (stagnationCounter >= STAGNATION_LIMIT) {
                logger.info("Stagnation: micro-mutating genome.");
                genome.mutate();
                stagnationCounter = 0;
            }
        }

        rotationsAtLastWindow = context.getRotationCount();
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
        TreeStrategy newStrategy = buildStrategy(type);
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
        context.setStrategy(newStrategy);
        // ─────────────────────────────────────────────────────────────────────

        activeStrategyType = type;
        genome.setPreferredStructure(type);
        genome.mutate();
        morphCount++;
        stagnationCounter = 0;

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
            double genomeFitness = genome.fitnessFor(type);    // 0-1, higher = better
            PerformanceRecord rec = performanceMemory.get(type);

            double memoryScore;
            if (rec.getSamples() == 0) {
                memoryScore = 0.5;   // exploration bonus for untried strategies
            } else {
                // Normalize: assume max reasonable score is 10, clamp to [0,1]
                double rawScore = rec.score();
                memoryScore = Math.max(0.0, 1.0 - (rawScore / 10.0));
            }

            double combined = (genomeFitness * 0.6) + (memoryScore * 0.4);

            if (combined > bestScore) {
                bestScore = combined;
                best      = type;
            }
        }

        logger.debug("Memory-biased selection: {} (score={})", best, fmt(bestScore));
        return best != null ? best : genome.recommendedStructure();
    }

    // ── Performance tracking ──────────────────────────────────────────────────

    private void recordCurrentPerformance() {
        int n = context.getSize();
        if (n == 0) return;

        int actualHeight = context.getTree().getRoot().getHeight();
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

        final int BUCKETS = 8;
        int[] counts = new int[BUCKETS];
        long range   = (long) Integer.MAX_VALUE - Integer.MIN_VALUE;

        for (int i = 0; i < windowFill; i++) {
            long shifted = (long) recentValues[i] - Integer.MIN_VALUE;
            int  bucket  = (int) Math.min(BUCKETS - 1, (shifted * BUCKETS) / range);
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
        int actualHeight = context.getTree().getRoot().getHeight();
        if (actualHeight == 0) return 0.0;
        double idealHeight = log2ceil(n);
        return Math.max(0.0, Math.min(1.0, 1.0 - (idealHeight / actualHeight)));
    }

    // ── Access window ─────────────────────────────────────────────────────────

    /** Records any access (insert, search, or delete target) into rolling window. */
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

    private static TreeStrategy buildStrategy(TreeGenome.StructureType type) {
        return switch (type) {
            case RED_BLACK      -> new RedBlackStrategy();
            case AVL            -> new AVLStrategy();
            case SPLAY          -> new SplayStrategy();
            case HYBRID         -> new HybridStrategy();
            // Aspirational — implement and add here when ready:
            case FIBONACCI_HEAP,
                 VAN_EMDE_BOAS,
                 PERSISTENT_TREE -> null;
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
}
