package core.util;

import core.TreeContext;
import core.TreeNode1;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

/**
 * Deep-clones TreeContext instances.
 *
 * The original iterative copy had a critical bug: it tried to wire
 * parent→child links while the memo was still being populated, so
 * getOrDefault() returned NIL for unvisited children and produced
 * a completely disconnected tree.
 *
 * Fix: two-pass BFS.
 *   Pass 1 — visit every node, create its clone, populate memo.
 *   Pass 2 — revisit every original node, wire its clone's left/right/parent
 *             from the now-complete memo. Every node is guaranteed to be
 *             present before any link is set.
 *
 * Features:
 *   snapshot()           — deep copy of context, isolated from original
 *   deployCloneArmy()    — N independent parallel clones
 *   strategyParallelClones() — one clone per strategy variant for benchmarking
 *   divergenceScore()    — structural distance [0.0 identical → 1.0 disjoint]
 *   mutantClone()        — clone with depth-variant augmentor mutation applied
 *   shallowClone()       — clone limited to maxDepth levels (useful for visualization)
 */
public class TreeCloner {

    private static final Logger logger = LogManager.getLogger(TreeCloner.class);

    private final TreeContext context;

    public TreeCloner(TreeContext context) {
        this.context = context;
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /**
     * Returns a fully independent deep copy of the current context.
     * No references are shared with the original.
     */
    public TreeContext snapshot() {
        TreeContext clone    = new TreeContext(context.getTree().getStrategy());
        TreeNode1<Integer> origNil = context.getTree().getNIL();
        TreeNode1<Integer> cloneNil = clone.getTree().getNIL();

        TreeNode1<Integer> origRoot = context.getTree().getRoot();

        if (origRoot == origNil) {
            clone.getTree().setRoot(cloneNil);
        } else {
            TreeNode1<Integer> clonedRoot = deepCopyTwoPass(origRoot, origNil, cloneNil);
            clone.getTree().setRoot(clonedRoot);
            clonedRoot.setParent(cloneNil);
        }

        clone.forceSizeInternal(context.getSize());

        // Preserve a non-default augmentor (e.g. interval max-hi): clone nodes are
        // created with the default size augmentor, and the structural wiring above
        // recomputes augmentedValue from it — overwriting any copied non-size
        // augment. Re-applying the source augmentor to the rebuilt clone recomputes
        // the correct values from the copied tags and sets the clone's field.
        if (context.getAugmentor() != TreeNode1.<Integer>defaultAugmentor()) {
            clone.setAugmentor(context.getAugmentor());
        }

        logger.debug("Snapshot created. size={}", clone.getSize());
        return clone;
    }

    /**
     * Spawns count fully isolated clones of the current context.
     */
    public List<TreeContext> deployCloneArmy(int count) {
        logger.warn("Deploying {} clones into parallel memory...", count);
        List<TreeContext> army = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            army.add(snapshot());
        }
        logger.info("Clone army of {} trees deployed.", army.size());
        return army;
    }

    /**
     * Creates one clone per strategy type — each clone holds the same data
     * but is ready to be morphed. Useful for A/B benchmarking.
     *
     * Note: the clones are copies of the current tree structure. If you want
     * the tree actually re-built under each strategy, call
     * clone.setStrategy(new XStrategy()) on each entry.
     */
    public Map<String, TreeContext> strategyParallelClones() {
        String[] labels = { "RedBlackStrategy", "AVLStrategy", "SplayStrategy" };
        Map<String, TreeContext> variants = new LinkedHashMap<>();
        for (String label : labels) {
            variants.put(label, snapshot());
        }
        logger.info("Strategy-parallel clones created: {}", variants.keySet());
        return variants;
    }

    /**
     * Structural divergence between this context and another.
     *   0.0 = identical node sets
     *   1.0 = completely disjoint
     */
    public double divergenceScore(TreeContext other) {
        TreeDiagnostics diagA = new TreeDiagnostics(context);
        TreeDiagnostics diagB = new TreeDiagnostics(other);

        Set<Integer> setA = new HashSet<>(diagA.inOrderTraversal());
        Set<Integer> setB = new HashSet<>(diagB.inOrderTraversal());

        Set<Integer> union        = new HashSet<>(setA); union.addAll(setB);
        Set<Integer> intersection = new HashSet<>(setA); intersection.retainAll(setB);

        if (union.isEmpty()) return 0.0;
        double score = 1.0 - ((double) intersection.size() / union.size());
        logger.debug("Divergence score vs other: {}", score);
        return score;
    }

    /**
     * Clone with the augmentor mutated based on depth tier.
     * See {@link #mutateAugmentorByDepth} for the per-depth logic.
     */
    public TreeContext mutantClone() {
        TreeContext clone = snapshot();
        TreeNode1<Integer> root = clone.getTree().getRoot();
        if (!root.isNil()) {
            mutateAugmentorByDepth(root, 0);
        }
        logger.info("Mutant clone created with depth-variant augmentors.");
        return clone;
    }

    /**
     * Clone that only contains nodes up to maxDepth levels from the root.
     * Good for visualizing the top of a large tree without copying everything.
     */
    public TreeContext shallowClone(int maxDepth) {
        TreeContext clone    = new TreeContext(context.getTree().getStrategy());
        TreeNode1<Integer> origNil  = context.getTree().getNIL();
        TreeNode1<Integer> cloneNil = clone.getTree().getNIL();

        TreeNode1<Integer> root = cloneDepthLimited(
                context.getTree().getRoot(), origNil, cloneNil, 0, maxDepth);

        clone.getTree().setRoot(root);
        if (!root.isNil()) root.setParent(cloneNil);

        int size = new TreeDiagnostics(clone).inOrderTraversal().size();
        clone.forceSizeInternal(size);

        // Preserve a non-default augmentor over the (truncated) copy — see snapshot().
        if (context.getAugmentor() != TreeNode1.<Integer>defaultAugmentor()) {
            clone.setAugmentor(context.getAugmentor());
        }

        logger.info("Shallow clone (maxDepth={}) created. size={}", maxDepth, size);
        return clone;
    }

    // ── Core copy logic ───────────────────────────────────────────────────────

    /**
     * Two-pass BFS deep copy.
     *
     * Pass 1 (BFS): create a clone node for every original node, store in memo.
     *               No links are set yet — we just need every node to exist.
     *
     * Pass 2 (memo iteration): for each original node, look up its clone in
     *               the memo and wire left, right, parent using memo lookups.
     *               Because pass 1 is complete, every lookup is guaranteed to
     *               hit — no NIL fallback from an unvisited child.
     */
    private TreeNode1<Integer> deepCopyTwoPass(TreeNode1<Integer> origRoot,
                                       TreeNode1<Integer> origNil,
                                       TreeNode1<Integer> cloneNil) {

        // ── Pass 1: BFS — create all clone nodes ──────────────────────────────
        Map<TreeNode1<Integer>, TreeNode1<Integer>> memo = new IdentityHashMap<>();
        Queue<TreeNode1<Integer>> queue = new ArrayDeque<>();
        queue.add(origRoot);

        while (!queue.isEmpty()) {
            TreeNode1<Integer> orig = queue.poll();
            if (orig == origNil || memo.containsKey(orig)) continue;

            TreeNode1<Integer> copy = TreeNode1.createNode(orig.getData(), cloneNil);
            copyNodeFields(orig, copy);
            memo.put(orig, copy);

            if (orig.getLeft()  != origNil) queue.add(orig.getLeft());
            if (orig.getRight() != origNil) queue.add(orig.getRight());
        }

        // ── Pass 2: wire left / right / parent ────────────────────────────────
        for (Map.Entry<TreeNode1<Integer>, TreeNode1<Integer>> entry : memo.entrySet()) {
            TreeNode1<Integer> orig = entry.getKey();
            TreeNode1<Integer> copy = entry.getValue();

            TreeNode1<Integer> cloneLeft  = memo.getOrDefault(orig.getLeft(),  cloneNil);
            TreeNode1<Integer> cloneRight = memo.getOrDefault(orig.getRight(), cloneNil);
            TreeNode1<Integer> cloneParent = (orig.getParent() == null || orig.getParent() == origNil)
                    ? cloneNil
                    : memo.getOrDefault(orig.getParent(), cloneNil);

            if (cloneLeft  != cloneNil) copy.setLeft(cloneLeft);
            if (cloneRight != cloneNil) copy.setRight(cloneRight);
            copy.setParent(cloneParent);
        }

        return memo.get(origRoot);
    }

    /**
     * Copies all non-structural fields from orig → copy.
     * Structural fields (left, right, parent) are handled separately in pass 2.
     */
    private void copyNodeFields(TreeNode1<Integer> orig, TreeNode1<Integer> copy) {
        copy.setColor(orig.getColor());
        copy.setLastRotation(orig.getLastRotation());
        copy.setAugmentedValue(orig.getAugmentedValue());
        copy.setTag(orig.getTag());
        copy.setPathCompressed(orig.isPathCompressed());
    }

    // ── Depth-limited copy (for shallowClone) ─────────────────────────────────

    private TreeNode1<Integer> cloneDepthLimited(TreeNode1<Integer> node,
                                         TreeNode1<Integer> origNil,
                                         TreeNode1<Integer> cloneNil,
                                         int depth, int max) {
        if (node == origNil || depth > max) return cloneNil;

        TreeNode1<Integer> copy  = TreeNode1.createNode(node.getData(), cloneNil);
        copyNodeFields(node, copy);

        TreeNode1<Integer> left  = cloneDepthLimited(node.getLeft(),  origNil, cloneNil, depth + 1, max);
        TreeNode1<Integer> right = cloneDepthLimited(node.getRight(), origNil, cloneNil, depth + 1, max);

        if (left  != cloneNil) { copy.setLeft(left);   left.setParent(copy);  }
        if (right != cloneNil) { copy.setRight(right); right.setParent(copy); }

        return copy;
    }

    // ── Depth-tiered augmentor mutation (relocated from TreeNode1) ─────────────

    /**
     * Installs a depth-tiered augmentor on each node, doing simple key arithmetic
     * (key, key·2, key²). ADR-002 step 2 moved this off the generic
     * {@code TreeNode1<K>} — which carries no key arithmetic — into this
     * {@code Integer}-specialised helper, the only place that needs it
     * ({@link #mutantClone()}). Keys unbox to {@code int} for the arithmetic.
     */
    private static void mutateAugmentorByDepth(TreeNode1<Integer> node, int depth) {
        if (node.isNil()) return;

        if (depth <= 1) {
            node.setAugmentor(n -> n.setAugmentedValue(n.getData()));
        } else if (depth <= 3) {
            node.setAugmentor(n -> n.setAugmentedValue(n.getData() * 2));
        } else {
            node.setAugmentor(n -> n.setAugmentedValue(n.getData() * n.getData()));
        }

        mutateAugmentorByDepth(node.getLeft(), depth + 1);
        mutateAugmentorByDepth(node.getRight(), depth + 1);
    }
}
