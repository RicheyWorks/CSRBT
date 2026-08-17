package io.github.richeyworks.csrbt.experimental;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.util.TreeDiagnostics;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

/**
 * Ecological analysis of tree structure.
 *
 * Maps classical CS tree properties onto biological frameworks:
 *
 * <pre>
 *   Shannon (1948)            → diversity of key distribution
 *   MacArthur &amp; Wilson (1967) → species-area relationship on subtrees
 *   Pianka (1973)             → niche overlap between left/right subtrees
 *   MacArthur (1958)          → broken-stick model for subtree size distribution
 *   MacArthur &amp; Wilson (1967) → r/K selection → strategy classification
 *   Margulis (1967)           → endosymbiosis → tree merging
 *   Mitochondrial Eve         → deepest common ancestor of all leaves
 * </pre>
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
     * <p><b>Read this before quoting the number.</b> The sample is the tree's stored keys,
     * and the tree is a <i>set</i>: every key is present exactly once, so every "species"
     * has abundance 1 and this returns ln n for every tree of size n — the top of its own
     * scale, always. That is the arithmetically correct H' of a perfectly even sample; it
     * is not a measurement of the workload. Ecologically the stored key set is a
     * <i>species list</i> (incidence data), and abundance-based indices are not defined on
     * incidence data (Magurran 2004, ch. 2). To get diversity that varies, count key
     * <i>touches</i> rather than keys — {@code EcologyRecorder} feeds
     * {@link io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics#shannon(Map)}
     * with exactly that abundance distribution (ADR-015, which exists because of this
     * defect: audit 2026-08-09 EC-1).</p>
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
     * Pielou's evenness J' = H' / ln(S) (Pielou 1966) over the tree's stored keys —
     * <b>identically 1.0, and therefore not a measurement.</b>
     *
     * <p>The formula is right; the sample is wrong. J' is defined on a species-abundance
     * vector — individuals counted per species. A duplicate-free BST is not that: it is a
     * <i>species list</i> (incidence data), every key present exactly once, so S = n,
     * H' = ln n, and J' = 1 for every tree that has ever existed. Ecology draws the same
     * line: incidence data supports richness and the incidence-based similarity indices
     * (Jaccard, Sørensen, Chao2), but abundance-based diversity and evenness are simply
     * undefined on it (Magurran, <i>Measuring Biological Diversity</i>, 2004, ch. 2). An
     * index that cannot vary carries no information — its own H' is zero.</p>
     *
     * <p>This was found by the 2026-08-09 ecology audit (EC-1/EC-3), confirmed by the
     * 2026-08-12 deep sweep (E-1), and is settled here by making the API say so rather
     * than by re-pointing a named index at some other partition. Redefining J' over depth
     * strata was measured and rejected: it does vary, but it runs backwards — a 15-node
     * spine, the worst shape a BST can take, reads J' = 1.000 (one node per stratum, a
     * perfectly even canopy) while a perfect 15-node tree reads 0.820 and a perfect
     * 1023-node tree 0.599, so "most even" would name the most pathological tree, and the
     * usable range would be a size-dependent 0.6–1.0. Calling that "Shannon evenness"
     * would repeat exactly the fault the sixth pass diagnosed in {@code rKScore} — a named
     * index quietly meaning something other than its name.</p>
     *
     * <p>Two honest instruments replace it, and neither is a rename of this one:</p>
     * <ul>
     *   <li><b>Community evenness</b> — count key <i>touches</i>, not keys:
     *       {@code EcologyRecorder} accumulates a real abundance distribution and
     *       {@link io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics#pielouEvenness(Map)}
     *       computes the same Pielou J' on it, where it varies as ecology intends
     *       (uniform scans → J' near 1, hot-key workloads → J' near 0.5). That layer
     *       (ADR-015) exists because of this defect.</li>
     *   <li><b>Structural evenness</b> — {@link #subtreeEvenness()}, the abundance-weighted
     *       mean evenness of the two-daughter splits, in the spirit of MacArthur's broken
     *       stick (1957). That is what {@code rKScore()} uses, and what
     *       {@code ecologyReport()} prints.</li>
     * </ul>
     *
     * <p>The return value is unchanged (1.0 for any non-empty tree, and for the empty one)
     * so that no existing caller's arithmetic moves; what changes is that the API, and the
     * report, stop presenting it as something the tree was measured for.</p>
     *
     * @deprecated structurally constant at 1.0 on a duplicate-free BST, so it measures
     *             nothing. For community evenness use
     *             {@link io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics#pielouEvenness(Map)}
     *             over access abundances; for structural evenness use
     *             {@link #subtreeEvenness()}.
     * @return 1.0, always
     */
    @Deprecated
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
     * S = c · A^z   (MacArthur &amp; Wilson 1967, p.8)
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
     * <p><b>Read this before quoting the number: it is 1.0, always.</b> The species-area
     * relationship needs two "islands" whose species count S is genuinely smaller than their
     * area A. A BST is a <i>set</i>, so every subtree's distinct-value count equals its node
     * count: S1 = A1 and S2 = A2 by construction, and
     * {@code log(S2/S1)/log(A2/A1) = log(A2/A1)/log(A2/A1) = 1} for every tree that has ever
     * existed — measured over 40 random Red-Black and Splay trees of 3–300 keys plus every
     * shipped fixture, the only two values this method can return are {@code 1.0} and
     * {@code NaN} (an empty subtree, or A1 == A2, where the ratio is undefined). Against the
     * bands the formula is usually read with — z ≈ 0.30 islands, z &gt; 0.35 fragmented — that
     * constant reads "extreme fragmentation" for a perfectly balanced tree just as loudly as
     * for a spine.</p>
     *
     * <p>This is the same defect as {@link #shannonEvenness()} and for the same reason, and
     * {@code EcologyRecorder}'s own class javadoc has named it since ADR-015 ("empirical z ≡ 1").
     * The cure is the same too: the varying quantity is <i>access</i>, not membership. Rarefaction
     * — richness as a function of sampling effort — is the species-area curve's honest analogue
     * over an abundance distribution; see
     * {@link io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics#rarefiedRichness(Map, long)}
     * and {@link io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics#chao1(Map)}
     * fed by {@code EcologyRecorder}, where the number moves with the workload.</p>
     *
     * <p>The return value is unchanged so that no existing caller's arithmetic moves; what
     * changes is that the API, and the report, stop presenting it as a measurement.</p>
     *
     * @deprecated structurally constant on a duplicate-free BST (1.0 whenever it is defined at
     *             all), so it measures nothing about the tree. For a sampling-effort view of
     *             richness use
     *             {@link io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics#rarefiedRichness(Map, long)}
     *             over access abundances.
     * @return 1.0 whenever both subtrees are non-empty and of different sizes; {@code NaN} otherwise
     */
    @Deprecated
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
     *
     * <p><b>Read this before quoting the number: it is 0.0, always.</b> Pianka's index is a
     * sum over shared resource axes, and the two subtrees of a BST share none: every key in the
     * left subtree sorts below the root and every key in the right subtree above it, so the two
     * utilization vectors have <i>disjoint support by the search-tree invariant</i>. Every term
     * of the numerator is {@code pL·pR} with one factor zero, so O ≡ 0 for every tree that has
     * ever existed — measured over 40 random Red-Black and Splay trees of 3–300 keys and every
     * shipped fixture, the set of values this method returns has exactly one element. Read
     * against the bands above, a perfectly balanced tree and a spine both report "complete
     * partitioning", and MacArthur's 0.3–0.5 is unreachable by construction rather than
     * informative.</p>
     *
     * <p>Same defect and same cure as {@link #shannonEvenness()} and {@link #empiricalZValue()};
     * {@code EcologyRecorder}'s class javadoc has named this one since ADR-015 ("Pianka overlap
     * between disjoint-by-construction subtrees ≡ 0"). Overlap becomes a real measurement when
     * the two communities are <i>access</i> distributions that can genuinely share keys — two
     * workload phases, two recorder windows, two entered datasets — which is what
     * {@link io.github.richeyworks.csrbt.experimental.ecology.BetaDiversity#pianka(Map, Map)}
     * computes, and what {@code ExperimentLab} prints per consecutive phase pair.</p>
     *
     * <p>The return value is unchanged so that no existing caller's arithmetic moves; what
     * changes is that the API, and the report, stop presenting it as a measurement.</p>
     *
     * @deprecated structurally constant at 0.0 — the subtrees of a BST are disjoint by the
     *             search-tree invariant, so there is no niche to overlap. Use
     *             {@link io.github.richeyworks.csrbt.experimental.ecology.BetaDiversity#pianka(Map, Map)}
     *             over two access-abundance distributions.
     * @return 0.0, always
     */
    @Deprecated
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
     * (MacArthur &amp; Wilson 1967; Pianka 1970)
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
     * Three measured terms, each in [0, 1]: balance efficiency (40%), density (35%),
     * and the evenness of the subtree-size splits (25%).
     *
     * The third term used to be shannonEvenness(), commented "evenness of subtree sizes"
     * — which it never was. It reads the KEY frequency distribution, and on a
     * duplicate-free BST every key has abundance 1, so H' = ln n with S = n and the term
     * is identically 1.0 (audit 2026-08-09 EC-3, deep-sweep E-1). A constant +0.25 on
     * every tree put a hard floor at −0.5, so rKLabel()'s "strongly r-selected" branch
     * was dead code: a maximally right-skewed 15-node tree — the worst shape a BST can
     * take — scored −0.4997 and read "weakly r-selected" (audit 2026-08-17, finding 27).
     * {@link #subtreeEvenness()} measures what the comment always claimed, so the whole
     * documented range is reachable and the weights and bands keep their calibration:
     * a spine now scores −1.0, while an ordinary Red-Black tree stays in the middle
     * bands its labels name (dropping the term instead and reweighting the survivors
     * would push a healthy sorted-insert RB tree to −0.96, "splay-like" — trading one
     * wrong label for another).
     *
     * Returns score in [−1.0, +1.0], both ends reachable:
     *   −1.0 = strongly r-selected (a degenerate spine: no balance, no density, no split)
     *   +1.0 = strongly K-selected (a perfect tree: minimal height, every slot filled)
     */
    public double rKScore() {
        TreeNode1<Integer> root = context.getTree().getRoot();
        if (root.isNil() || context.getSize() == 0) return 0.0;

        int    n    = context.getSize();
        // Measured height, not the cached one (bug audit 2026-08-12, E-1): only
        // AVL/Hybrid maintain node height caches up the path, so under Red-Black/
        // Splay/WB the cache is stale — a perfect 7-node RB tree reported h=2
        // (true 3), driving efficiency and density above 1 and rKScore to 2.5+
        // against its documented [-1, +1] range.
        int    h    = measuredHeight(root);
        double logN = Math.log(n + 1) / Math.log(2);

        // hMin = ceil(log2(n+1)): the true minimum height for ANY n (floor is only
        // right when n = 2^k − 1 and charged optimally-balanced trees imbalance).
        double hMin = Math.ceil(logN);
        // hAVL ≈ 1.44·log2(n) — theoretical AVL worst case
        double hAVL = 1.44 * logN;

        // Balance efficiency: 1.0 = perfect, 0.0 = maximally unbalanced (clamped).
        double efficiency = 1.0
                - Math.min(1.0, Math.max(0.0, h - hMin) / Math.max(1, hAVL - hMin));

        // Density: actual nodes / theoretical maximum for this height (clamped).
        double maxNodes = Math.pow(2, h) - 1;
        double density  = Math.min(1.0, n / maxNodes);

        // Evenness of the subtree-size splits — the structural reading the third term
        // always claimed and never made (finding 27).
        double evenness = subtreeEvenness();

        // Weighted K-score
        double raw = (0.4 * efficiency) + (0.35 * density) + (0.25 * evenness);
        return (raw * 2.0) - 1.0; // rescale to [−1, +1]
    }

    /**
     * Evenness of the subtree-size splits — Shannon evenness asked of tree STRUCTURE
     * instead of key frequency.
     *
     * At every branching node the two daughter subtrees are the "abundances" of a
     * two-species community: J' = H'/ln 2 is 1.0 when they are the same size and 0.0
     * when one side is empty. Each split is weighted by how many nodes it divides, so
     * the root's split counts for more than a leaf's parent — the same logic as
     * MacArthur's broken stick, where the big pieces carry the signal.
     *
     * 1.0 → every split halves the population (a perfect tree)
     * 0.0 → every split strands one side (a degenerate spine)
     *
     * Unlike {@link #shannonEvenness()}, which is identically 1.0 on a duplicate-free
     * BST, this varies with the thing r/K selection is actually about. An empty or
     * single-node tree has nothing to split, and reads 1.0.
     */
    public double subtreeEvenness() {
        TreeNode1<Integer> root = context.getTree().getRoot();
        if (root == null || root.isNil()) return 1.0;

        // Preorder (parents before children), so a single reverse pass sizes every
        // subtree by traversal. Node caches are not trusted here for the same reason
        // measuredHeight() exists (E-1).
        List<TreeNode1<Integer>> order = new ArrayList<>();
        Deque<TreeNode1<Integer>> stack = new ArrayDeque<>();
        stack.push(root);
        while (!stack.isEmpty()) {
            TreeNode1<Integer> n = stack.pop();
            order.add(n);
            if (!n.getLeft().isNil())  stack.push(n.getLeft());
            if (!n.getRight().isNil()) stack.push(n.getRight());
        }

        Map<TreeNode1<Integer>, Integer> sizes = new IdentityHashMap<>();
        double weighted = 0, weight = 0;
        for (int i = order.size() - 1; i >= 0; i--) {
            TreeNode1<Integer> n = order.get(i);
            int left  = sizes.getOrDefault(n.getLeft(), 0);
            int right = sizes.getOrDefault(n.getRight(), 0);
            sizes.put(n, 1 + left + right);
            int split = left + right;
            if (split == 0) continue;                  // a leaf divides nothing
            weighted += split * splitEvenness(left, right);
            weight   += split;
        }
        return weight == 0 ? 1.0 : weighted / weight;
    }

    /** J' = H'/ln 2 for one two-daughter split: 1.0 even, 0.0 with a side left empty. */
    private static double splitEvenness(int left, int right) {
        double total = left + right;
        double h = 0;
        if (left  > 0) { double p = left  / total; h -= p * Math.log(p); }
        if (right > 0) { double p = right / total; h -= p * Math.log(p); }
        return h / Math.log(2);
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
     *   P = species pool, supplied by the caller
     *
     * Returns predicted equilibrium tree size.
     *
     * <p><b>Read this before quoting the number: it is not deterministic.</b> I and E are
     * reciprocals of <i>wall-clock</i> mean latencies, so the same op stream replayed on the
     * same tree returns a different equilibrium on a busy machine than on an idle one — and
     * this repo's house rule since audit EC-2 is that deterministic meters decide. It is also
     * a category error: the ratio of two <i>latencies</i> is not a ratio of immigration and
     * extinction <i>rates</i>, and nothing in the tree limits occupancy to P, so the value
     * simply tracks whichever of add/remove happened to run faster.</p>
     *
     * <p>{@link io.github.richeyworks.csrbt.experimental.ecology.LogisticGrowth} is the
     * deterministic replacement named at EC-2: it fits r and the carrying capacity K to the
     * op-indexed population series {@code EcologyRecorder} records, so time is the op index
     * and nothing reads a clock. For an immigration/extinction equilibrium proper, use
     * {@link io.github.richeyworks.csrbt.experimental.ecology.TheoreticalModels#islandEquilibrium(double, double, double)}
     * with rates you actually measured.</p>
     *
     * @deprecated derives its rates from wall-clock latencies, so it is nondeterministic and
     *             not comparable across runs (audit EC-2). Use
     *             {@link io.github.richeyworks.csrbt.experimental.ecology.LogisticGrowth#fit(java.util.List)}
     *             over {@code EcologyRecorder.populationSeries()}, or
     *             {@link io.github.richeyworks.csrbt.experimental.ecology.TheoreticalModels#islandEquilibrium(double, double, double)}.
     */
    @Deprecated
    public double colonizationEquilibrium(int speciesPool) {
        double insertRate = context.avgInsertTimeMs() == 0 ? 1.0 : 1.0 / context.avgInsertTimeMs();
        double deleteRate = context.avgDeleteTimeMs() == 0 ? 0.1 : 1.0 / context.avgDeleteTimeMs();
        if (insertRate + deleteRate == 0) return speciesPool;
        return (insertRate / (insertRate + deleteRate)) * speciesPool;
    }

    // ── Full Report ───────────────────────────────────────────────────────────

    /**
     * The full plain-English report, as printed for classroom use.
     *
     * <p>The Shannon block reports H' and richness but <b>no species evenness</b>: on a
     * duplicate-free BST J' is identically 1.0 (see {@link #shannonEvenness()}), and a
     * constant printed next to real numbers reads as a measurement. The block says so in
     * words instead, and the evenness that <i>is</i> measured — {@link #subtreeEvenness()},
     * the structural split evenness that {@link #rKScore()} weighs — is reported in the
     * r/K block where it is actually used, labelled for what it is (audit 2026-08-09 EC-3).</p>
     *
     * <p>The MacArthur-Wilson and Pianka blocks now say the same kind of thing for the same
     * kind of reason (audit 2026-08-17 seventh pass, finding 3). {@link #empiricalZValue()} is
     * 1.0 on every tree and {@link #nicheOverlap()} is 0.0 on every tree — both constants of the
     * search-tree invariant, not measurements — and they were still being printed to four
     * decimal places, each with an interpretation band beside it, in a report written for a
     * classroom. They are replaced by the reason, exactly as evenness was; the one number in
     * that block that <i>is</i> a function of the tree, the species-area <em>prediction</em>
     * {@code S = c·n^z}, is kept and labelled as a prediction.</p>
     */
    public String ecologyReport() {
        int    n       = context.getSize();
        double shannon = shannonDiversity();
        double maxH    = n > 1 ? Math.log(n) : 1.0;
        int    rich    = speciesRichness();
        double rk      = rKScore();
        double splitJ  = subtreeEvenness();
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
            "║  Richness  = %d distinct values                    %n" +
            "║  Evenness  — not reported here, and not because it was%n" +
            "║    forgotten. The tree is a SET: every key is stored once,%n" +
            "║    so every species has abundance 1. That is a species%n" +
            "║    list, not an abundance sample — richness S = n and%n" +
            "║    H' = ln n follow by construction, and Pielou's J' is%n" +
            "║    1.0 for every tree that has ever existed. Evenness needs%n" +
            "║    counts of key TOUCHES: run the workload instruments%n" +
            "║    (EcologyRecorder → CommunityMetrics.pielouEvenness).%n" +
            "╠══ MacArthur-Wilson (1967) ═════════════════════════════╣%n" +
            "║  Predicted S (n=%d, z=0.30) = %.2f              %n" +
            "║    (a prediction from n alone, not a measurement of%n" +
            "║    this tree — the canonical island z, applied to n)  %n" +
            "║  Empirical z — not reported here. Same reason as evenness:%n" +
            "║    the tree is a SET, so each subtree's species count S%n" +
            "║    equals its area A, and log(S2/S1)/log(A2/A1) is 1.0 for%n" +
            "║    every tree that has ever existed. Species-area needs a%n" +
            "║    sample where S grows slower than A: run the workload%n" +
            "║    instruments (EcologyRecorder → CommunityMetrics%n" +
            "║    .rarefiedRichness), where richness answers to effort.%n" +
            "╠══ Pianka Niche Overlap (1973) ═════════════════════════╣%n" +
            "║  O_LR      — not reported here. The left subtree holds only%n" +
            "║    keys below the root and the right only keys above it, so%n" +
            "║    the two utilization vectors share no resource axis and%n" +
            "║    Pianka's O is 0.0 for every tree that has ever existed —%n" +
            "║    a fact about binary search trees, not about this one.%n" +
            "║    Overlap measures something when both communities are%n" +
            "║    TOUCH counts that can share keys: two workload phases,%n" +
            "║    two recorder windows (BetaDiversity.pianka).        %n" +
            "╠══ r/K Selection (MacArthur & Pianka 1970) ════════════╣%n" +
            "║  Score     = %+.4f                               %n" +
            "║  Class     → %s%n" +
            "║  Split J'  = %.4f  (structural evenness of the subtree%n" +
            "║    splits — 1 = every split halves the population, 0 = every%n" +
            "║    split strands one side; 25%% of the score above)     %n" +
            "╠══ Mitochondrial Eve (bottleneck) ══════════════════════╣%n" +
            "║  Eve node  = %-6d  depth = %d                    %n" +
            "║    (depth=0→diverse pop, depth>0→bottleneck)          %n" +
            "╠══ Broken-Stick Deviation (MacArthur 1957) ════════════╣%n" +
            "%s" +
            "╚══════════════════════════════════════════════════════╝%n",
            n,
            shannon, n, maxH,
            rich,
            n, speciesAreaPrediction(n),
            rk, rKLabel(), splitJ,
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

    /**
     * Actual tree height by an iterative walk (nodes on the longest root-to-leaf path;
     * single node = 1). Cached node heights are maintained only by the AVL/Hybrid
     * strategies, so metrics must never trust them across strategies (E-1).
     */
    private static int measuredHeight(TreeNode1<Integer> root) {
        if (root == null || root.isNil()) return 0;
        Deque<TreeNode1<Integer>> nodes = new ArrayDeque<>();
        Deque<Integer> depths = new ArrayDeque<>();
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
}
