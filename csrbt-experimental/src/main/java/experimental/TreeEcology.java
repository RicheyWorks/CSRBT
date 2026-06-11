package experimental;

import core.TreeContext;
import core.TreeNode1;
import core.util.TreeDiagnostics;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

/**
 * Ecological analysis of tree structure.
 *
 * Maps classical CS tree properties onto biological frameworks:
 *
 *   Shannon (1948)           → diversity of key distribution
 *   MacArthur & Wilson (1967)→ species-area relationship on subtrees
 *   Pianka (1973)            → niche overlap between left/right subtrees
 *   MacArthur (1958)         → broken-stick model for subtree size distribution
 *   MacArthur & Wilson (1967)→ r/K selection → strategy classification
 *   Margulis (1967)          → endosymbiosis → tree merging
 *   Mitochondrial Eve        → deepest common ancestor of all leaves
 *
 * None of this is metaphor for metaphor's sake — each mapping is
 * structurally faithful to the original biological model.
 */
public class TreeEcology {

    private static final Logger logger = LogManager.getLogger(TreeEcology.class);

    private final TreeContext    context;
    private final TreeDiagnostics diagnostics;

    // MacArthur-Wilson island biogeography constants
    // z = 0.30 is the canonical z-value for true islands (Preston 1962)
    private static final double MAW_Z = 0.30;
    private static final double MAW_C = 1.5;

    public TreeEcology(TreeContext context) {
        this.context     = context;
        this.diagnostics = new TreeDiagnostics(context);
    }

    // ── Shannon Diversity ─────────────────────────────────────────────────────

    /**
     * Shannon diversity index  H' = −Σ pᵢ · ln(pᵢ)
     *
     * Applied to the frequency distribution of key values.
     * H' = 0      → one value dominates (monoculture tree)
     * H' = ln(S)  → perfectly even distribution across S distinct values
     *
     * In CLRS terms: the frequencyMap in TreeContext IS the species
     * abundance distribution.  High diversity ↔ uniform key space coverage.
     */
    public double shannonDiversity() {
        List<Integer> values = diagnostics.inOrderTraversal();
        if (values.isEmpty()) return 0.0;

        Map<Integer, Integer> freq = new HashMap<>();
        for (int v : values) freq.merge(v, 1, Integer::sum);

        double n = values.size();
        double H = 0.0;
        for (int count : freq.values()) {
            double p = count / n;
            if (p > 0) H -= p * Math.log(p);
        }
        return H;
    }

    /**
     * Shannon evenness J' = H' / ln(S)
     * J' = 1.0 → perfectly even; J' → 0 → one species dominates.
     * Normalizes diversity by the theoretical maximum.
     */
    public double shannonEvenness() {
        int S = speciesRichness();
        if (S <= 1) return 1.0;
        return shannonDiversity() / Math.log(S);
    }

    /**
     * Species richness S = count of distinct values.
     * The most basic diversity metric (Margalef 1958).
     */
    public int speciesRichness() {
        return new HashSet<>(diagnostics.inOrderTraversal()).size();
    }

    // ── MacArthur-Wilson Species-Area Relationship ────────────────────────────

    /**
     * S = c · A^z   (MacArthur & Wilson 1967, p.8)
     *
     * Predicts how many distinct values to expect in a subtree of size A.
     * Deviation from this prediction reveals how "island-like" vs
     * "mainland-like" a given subtree is.
     *
     * @param subtreeSize  area A (number of nodes)
     * @return             predicted species count S
     */
    public double speciesAreaPrediction(int subtreeSize) {
        if (subtreeSize <= 0) return 0;
        return MAW_C * Math.pow(subtreeSize, MAW_Z);
    }

    /**
     * Computes the z-value empirically from the actual left/right subtree data.
     * log(S2/S1) / log(A2/A1) = z  (rearranged from S = cA^z)
     *
     * A z near 0.30 means the tree's structure follows typical island dynamics.
     * z >> 0.30 suggests extreme fragmentation (very uneven subtrees).
     * z << 0.30 suggests mainland-like (subtrees very similar in composition).
     */
    public double empiricalZValue() {
        TreeNode1<Integer> root = context.getTree().getRoot();
        if (root.isNil()) return 0.0;

        List<Integer> leftVals  = subtreeValues(root.getLeft());
        List<Integer> rightVals = subtreeValues(root.getRight());
        if (leftVals.isEmpty() || rightVals.isEmpty()) return Double.NaN;

        int A1 = leftVals.size(),  S1 = (int) new HashSet<>(leftVals).size();
        int A2 = rightVals.size(), S2 = (int) new HashSet<>(rightVals).size();
        if (S1 <= 0 || S2 <= 0 || A1 == A2) return Double.NaN;

        return Math.log((double) S2 / S1) / Math.log((double) A2 / A1);
    }

    // ── Pianka Niche Overlap ──────────────────────────────────────────────────

    /**
     * Pianka's symmetric niche overlap index (Pianka 1973):
     *
     *   O_jk = Σ(pᵢⱼ · pᵢₖ) / √(Σpᵢⱼ² · Σpᵢₖ²)
     *
     * Applied between left and right subtrees, treating each value as a
     * "resource axis" and its relative frequency as "utilization".
     *
     * O = 1.0 → complete overlap (left and right draw from same key range)
     * O = 0.0 → complete separation (perfectly partitioned niches)
     *
     * MacArthur's warblers maintained O ≈ 0.3–0.5 — enough overlap to share
     * the same tree, enough separation to avoid competitive exclusion.
     */
    public double nicheOverlap() {
        TreeNode1<Integer> root = context.getTree().getRoot();
        if (root.isNil()) return 0.0;

        List<Integer> left  = subtreeValues(root.getLeft());
        List<Integer> right = subtreeValues(root.getRight());
        if (left.isEmpty() || right.isEmpty()) return 0.0;

        Set<Integer> universe = new HashSet<>(left);
        universe.addAll(right);

        Map<Integer, Double> pL = proportions(left,  universe);
        Map<Integer, Double> pR = proportions(right, universe);

        double num = 0, sqL = 0, sqR = 0;
        for (int v : universe) {
            double pl = pL.getOrDefault(v, 0.0);
            double pr = pR.getOrDefault(v, 0.0);
            num += pl * pr;
            sqL += pl * pl;
            sqR += pr * pr;
        }
        double denom = Math.sqrt(sqL * sqR);
        return denom == 0 ? 0.0 : num / denom;
    }

    // ── MacArthur Broken-Stick Model ──────────────────────────────────────────

    /**
     * MacArthur's broken-stick model (MacArthur 1957).
     *
     * Originally predicted species abundance in a community with S species
     * by randomly breaking a stick of length N into S pieces.
     *
     * Applied here: treats each depth level as a "community", the nodes at
     * that depth as "species", and their subtree sizes as "abundances".
     *
     * Expected size at depth d in a perfectly balanced tree = n / 2^d.
     * Deviation reveals where the tree's balance breaks down.
     *
     * @return  Map: depth → int[]{ expected_avg_size, actual_avg_size }
     */
    public Map<Integer, int[]> brokenStickDeviation() {
        Map<Integer, int[]> result = new LinkedHashMap<>();
        TreeNode1<Integer> root = context.getTree().getRoot();
        if (root.isNil()) return result;

        int n = context.getSize();
        Queue<TreeNode1<Integer>> queue  = new LinkedList<>();
        Queue<Integer>   depths = new LinkedList<>();
        queue.add(root);
        depths.add(0);

        Map<Integer, List<Integer>> sizesByDepth = new TreeMap<>();
        while (!queue.isEmpty()) {
            TreeNode1<Integer> node = queue.poll();
            int depth      = depths.poll();
            sizesByDepth.computeIfAbsent(depth, k -> new ArrayList<>())
                        .add(node.getAugmentedValue());
            if (!node.getLeft().isNil())  { queue.add(node.getLeft());  depths.add(depth + 1); }
            if (!node.getRight().isNil()) { queue.add(node.getRight()); depths.add(depth + 1); }
        }

        for (Map.Entry<Integer, List<Integer>> e : sizesByDepth.entrySet()) {
            int depth     = e.getKey();
            int expected  = (int) (n / Math.pow(2, depth));
            int actual    = (int) e.getValue().stream().mapToInt(x -> x).average().orElse(0);
            result.put(depth, new int[]{ expected, actual });
        }
        return result;
    }

    // ── r/K Selection ─────────────────────────────────────────────────────────

    /**
     * r/K selection score for the current tree state.
     * (MacArthur & Wilson 1967; Pianka 1970)
     *
     *   r-selected traits  (fast, opportunistic, low equilibrium):
     *     − High imbalance relative to optimal height
     *     − Sparse density (many wasted slots)
     *     − High variance in subtree sizes
     *     → Maps to: Splay tree behavior under adversarial access patterns
     *
     *   K-selected traits  (slow, equilibrium, high competitive ability):
     *     − Near-optimal height (dense packing)
     *     − High density relative to theoretical minimum
     *     − Low variance (even subtree sizes)
     *     → Maps to: AVL tree behavior
     *
     * Returns score in [−1.0, +1.0]:
     *   −1.0 = strongly r-selected (fast, chaotic, imbalanced)
     *   +1.0 = strongly K-selected (stable, dense, balanced)
     */
    public double rKScore() {
        TreeNode1<Integer> root = context.getTree().getRoot();
        if (root.isNil() || context.getSize() == 0) return 0.0;

        int    n    = context.getSize();
        int    h    = root.getHeight();
        double logN = Math.log(n + 1) / Math.log(2);

        // hMin = floor(log2(n+1)) for a perfect tree
        double hMin = Math.floor(logN);
        // hAVL ≈ 1.44·log2(n) — theoretical AVL worst case
        double hAVL = 1.44 * logN;

        // Balance efficiency: 1.0 = perfect, 0.0 = maximally unbalanced
        double efficiency = 1.0 - Math.min(1.0, (h - hMin) / Math.max(1, hAVL - hMin));

        // Density: actual nodes / theoretical maximum for this height
        double maxNodes = Math.pow(2, h) - 1;
        double density  = n / maxNodes;

        // Evenness of subtree sizes (Shannon evenness repurposed)
        double evenness = shannonEvenness();

        // Weighted K-score
        double raw = (0.4 * efficiency) + (0.35 * density) + (0.25 * evenness);
        return (raw * 2.0) - 1.0; // rescale to [−1, +1]
    }

    public String rKLabel() {
        double score = rKScore();
        if      (score < -0.5) return "strongly r-selected (splay-like, opportunistic)";
        else if (score < -0.1) return "weakly r-selected (RB-like, fast growth)";
        else if (score <  0.1) return "transitional (r/K boundary — adaptive zone)";
        else if (score <  0.5) return "weakly K-selected (RB-optimized)";
        else                   return "strongly K-selected (AVL-like, equilibrium)";
    }

    // ── Mitochondrial Eve ─────────────────────────────────────────────────────

    /**
     * "Mitochondrial Eve" of the tree — the most recent common ancestor
     * of ALL leaf nodes.
     *
     * In population genetics, Mitochondrial Eve is the matrilineal MRCA of
     * all living humans — not the only ancestor, but the deepest common one
     * through a specific lineage.
     *
     * Here: Eve is the LCA of all leaves. In a perfectly balanced tree,
     * Eve IS the root. In a pathological right-skewed tree, Eve is far down
     * the right spine — analogous to a population bottleneck.
     *
     * @return the LCA of all leaves, with its depth as a bottleneck metric
     */
    public TreeNode1<Integer> mitoEve() {
        TreeNode1<Integer> root = context.getTree().getRoot();
        if (root.isNil()) return root;

        List<TreeNode1<Integer>> leaves = new ArrayList<>();
        Stack<TreeNode1<Integer>> stack = new Stack<>();
        stack.push(root);
        while (!stack.isEmpty()) {
            TreeNode1<Integer> n = stack.pop();
            if (n.isLeaf()) leaves.add(n);
            if (!n.getRight().isNil()) stack.push(n.getRight());
            if (!n.getLeft().isNil())  stack.push(n.getLeft());
        }

        if (leaves.isEmpty()) return root;
        TreeNode1<Integer> eve = leaves.get(0);
        for (int i = 1; i < leaves.size(); i++) {
            eve = lca(eve, leaves.get(i));
        }

        logger.info("🧬 Mitochondrial Eve: node={} depth={} (0=root=diverse population)",
                eve.getData(), eve.depth());
        return eve;
    }

    // ── Endosymbiosis ─────────────────────────────────────────────────────────

    /**
     * Endosymbiotic merger (Margulis 1967).
     *
     * Absorbs all values from the 'guest' tree into this tree's context.
     * Duplicate values are silently discarded — analogous to redundant gene
     * copies lost after endosymbiotic transfer (Timmis et al. 2004).
     *
     * The host tree structure is preserved; the guest is dismantled.
     * This mirrors mitochondrial genome reduction: ~99% of mitochondrial
     * genes transferred to the nucleus were either lost or integrated,
     * not kept as separate copies.
     *
     * @param  guest      the "proto-endosymbiont" tree
     * @return            number of values successfully transferred (genes kept)
     */
    public int endosymbiosis(TreeContext guest) {
        TreeDiagnostics gDiag     = new TreeDiagnostics(guest);
        List<Integer>   gValues   = gDiag.inOrderTraversal();
        int             original  = gValues.size();
        int             transferred = 0;

        for (int v : gValues) {
            if (!context.contains(v)) {
                context.add(v);
                transferred++;
            }
        }

        int lost = original - transferred; // "gene loss" post-transfer
        logger.info("🦠 Endosymbiosis: {} values offered, {} transferred, {} lost (duplicates)",
                original, transferred, lost);
        return transferred;
    }

    // ── Colonization / Extinction ─────────────────────────────────────────────

    /**
     * MacArthur-Wilson immigration-extinction equilibrium.
     *
     * On an island, species equilibrium S* = I / (I + E) * P
     * where I = immigration rate, E = extinction rate, P = species pool size.
     *
     * Applied to tree insertions/deletions:
     *   I = insert rate  (avgInsertTimeMs inverse)
     *   E = delete rate  (avgDeleteTimeMs inverse)
     *   P = total values ever inserted  (auditLog size proxy)
     *
     * Returns predicted equilibrium tree size.
     */
    public double colonizationEquilibrium(int speciesPool) {
        double insertRate = context.avgInsertTimeMs() == 0 ? 1.0 : 1.0 / context.avgInsertTimeMs();
        double deleteRate = context.avgDeleteTimeMs() == 0 ? 0.1 : 1.0 / context.avgDeleteTimeMs();
        if (insertRate + deleteRate == 0) return speciesPool;
        return (insertRate / (insertRate + deleteRate)) * speciesPool;
    }

    // ── Full Report ───────────────────────────────────────────────────────────

    public String ecologyReport() {
        int    n       = context.getSize();
        double shannon = shannonDiversity();
        double maxH    = n > 1 ? Math.log(n) : 1.0;
        double even    = shannonEvenness();
        int    rich    = speciesRichness();
        double overlap = nicheOverlap();
        double rk      = rKScore();
        double z       = empiricalZValue();
        TreeNode1<Integer> eve  = mitoEve();

        Map<Integer, int[]> stick = brokenStickDeviation();
        StringBuilder stickStr = new StringBuilder();
        for (Map.Entry<Integer, int[]> e : stick.entrySet()) {
            stickStr.append(String.format("    depth %2d → expected=%4d  actual=%4d  Δ=%+d%n",
                    e.getKey(), e.getValue()[0], e.getValue()[1],
                    e.getValue()[1] - e.getValue()[0]));
        }

        return String.format(
            "╔══════════════════════════════════════════════════════╗%n" +
            "║              ECOLOGICAL TREE ANALYSIS                ║%n" +
            "╠══════════════════════════════════════════════════════╣%n" +
            "║ n = %-5d                                            ║%n" +
            "╠══ Shannon Diversity (1948) ═══════════════════════════╣%n" +
            "║  H'        = %.4f  (max H' for n=%d = %.4f)     %n" +
            "║  Evenness  = %.4f  (J'=1 → perfectly even)       %n" +
            "║  Richness  = %d distinct values                    %n" +
            "╠══ MacArthur-Wilson (1967) ═════════════════════════════╣%n" +
            "║  Predicted S (n=%d, z=0.30) = %.2f              %n" +
            "║  Empirical z               = %.4f               %n" +
            "║    (z≈0.30=islands, z<0.25=mainland, z>0.35=fragmented)%n" +
            "╠══ Pianka Niche Overlap (1973) ═════════════════════════╣%n" +
            "║  O_LR      = %.4f  (left ↔ right subtree)       %n" +
            "║    (O=1→identical niches, O=0→complete partitioning)  %n" +
            "╠══ r/K Selection (MacArthur & Pianka 1970) ════════════╣%n" +
            "║  Score     = %+.4f                               %n" +
            "║  Class     → %s%n" +
            "╠══ Mitochondrial Eve (bottleneck) ══════════════════════╣%n" +
            "║  Eve node  = %-6d  depth = %d                    %n" +
            "║    (depth=0→diverse pop, depth>0→bottleneck)          %n" +
            "╠══ Broken-Stick Deviation (MacArthur 1957) ════════════╣%n" +
            "%s" +
            "╚══════════════════════════════════════════════════════╝%n",
            n,
            shannon, n, maxH,
            even,
            rich,
            n, speciesAreaPrediction(n),
            Double.isNaN(z) ? 0.0 : z,
            overlap,
            rk, rKLabel(),
            eve.isNil() ? -1 : eve.getData(), eve.isNil() ? -1 : eve.depth(),
            stickStr
        );
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private List<Integer> subtreeValues(TreeNode1<Integer> root) {
        List<Integer> vals = new ArrayList<>();
        if (root == null || root.isNil()) return vals;
        Stack<TreeNode1<Integer>> stack = new Stack<>();
        stack.push(root);
        while (!stack.isEmpty()) {
            TreeNode1<Integer> n = stack.pop();
            vals.add(n.getData());
            if (!n.getRight().isNil()) stack.push(n.getRight());
            if (!n.getLeft().isNil())  stack.push(n.getLeft());
        }
        return vals;
    }

    private Map<Integer, Double> proportions(List<Integer> values, Set<Integer> universe) {
        Map<Integer, Integer> counts = new HashMap<>();
        for (int v : values) counts.merge(v, 1, Integer::sum);
        Map<Integer, Double> props = new HashMap<>();
        double total = values.size();
        for (int v : universe) props.put(v, counts.getOrDefault(v, 0) / total);
        return props;
    }

    private TreeNode1<Integer> lca(TreeNode1<Integer> a, TreeNode1<Integer> b) {
        Set<TreeNode1<Integer>> ancestors = new HashSet<>();
        for (TreeNode1<Integer> x = a; x != null && !x.isNil(); x = x.getParent()) ancestors.add(x);
        for (TreeNode1<Integer> y = b; y != null && !y.isNil(); y = y.getParent()) {
            if (ancestors.contains(y)) return y;
        }
        return context.getTree().getRoot();
    }
}
