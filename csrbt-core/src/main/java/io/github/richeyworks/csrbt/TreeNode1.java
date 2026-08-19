package io.github.richeyworks.csrbt;

import java.util.Comparator;

public class TreeNode1<K> implements Comparable<TreeNode1<K>>, Cloneable {
    public enum Color { RED, BLACK }
    enum Rotation { NONE, LEFT, RIGHT }

    @FunctionalInterface
    public interface Augmentor<K> {
        void apply(TreeNode1<K> node);
    }

    /**
     * The default augmentor writes an {@code int} (a subtree count) into
     * {@link #augmentedValue} and never touches the key {@code K}, so a single
     * shared instance is type-safe for every {@code K}. It is handed out cast via
     * {@link #defaultAugmentor()} so that identity comparisons
     * ({@code augmentor != TreeNode1.defaultAugmentor()}) still work — every call
     * returns the same object. (A factory that built a fresh lambda each call would
     * silently break those identity checks.)
     */
    private static final Augmentor<Object> DEFAULT_AUGMENTOR = node -> {
        int leftSize = (node.left != null && !node.left.isNil()) ? node.left.augmentedValue : 0;
        int rightSize = (node.right != null && !node.right.isNil()) ? node.right.augmentedValue : 0;
        node.augmentedValue = 1 + leftSize + rightSize;
    };

    /**
     * The shared default augmentor, viewed as {@code Augmentor<E>}. Returns the
     * same singleton on every call (see {@link #DEFAULT_AUGMENTOR}), so it is safe
     * to compare against by identity.
     */
    @SuppressWarnings("unchecked")
    public static <E> Augmentor<E> defaultAugmentor() {
        return (Augmentor<E>) DEFAULT_AUGMENTOR;
    }

    private final K data;
    private TreeNode1<K> left;
    private TreeNode1<K> right;
    private TreeNode1<K> parent;
    private Color color;
    private final TreeNode1<K> nilSentinel;
    /**
     * ADR-002 step 2 — the per-tree key-ordering authority (was the static
     * {@code KEY_ORDER}). A generic class cannot hold a {@code static
     * Comparator<K>}, so ordering moves to an instance field. The per-tree NIL
     * sentinel is the source of truth (set once via {@link #createNil(Comparator)});
     * every real node copies the reference from the {@code nil} it is built against,
     * so {@link #createNode(Object, TreeNode1)} stays two-arg and no comparison
     * call-site changes. {@link #compareTo} / {@link #compareKeyTo} consult this.
     */
    private final Comparator<? super K> keyOrder;
    private Rotation lastRotation = Rotation.NONE;
    private int augmentedValue = 0;   // pluggable augmentor payload (e.g. interval max-hi) — NOT subtree size; see `size` (ADR-002)
    /**
     * The additive GENERIC augment slot (outer-ring ADR, Phase 7): a reference-typed
     * payload for augmentors whose subtree summary cannot fit the int
     * {@link #augmentedValue} — e.g. {@code GenericIntervalAugmentor}'s typed
     * {@code {hi, maxHi}}. Contract: the referenced payload is treated as
     * <b>immutable</b> — augmentors replace it, never mutate it — because
     * {@link #deepCopy} copies the reference, so a clone shares payload objects with
     * its source until either side replaces them. {@code null} on any node no
     * ref-slot augmentor has touched; the default augmentor and every int-slot
     * augmentor (order statistics, the int {@code IntervalAugmentor}) ignore it.
     */
    private Object augmentedRef;
    private int blackHeight = 1;
    private int height = 1;
    /**
     * Intrinsic subtree node count (this node + both subtrees), maintained on
     * every structural link exactly like {@link #height} and {@link #blackHeight}
     * and independent of the pluggable {@link #augmentor}. This is the source of
     * truth for dynamic order statistics (CLRS 14.1).
     *
     * Giving subtree size its own field — rather than borrowing
     * {@code augmentedValue} — is what lets order statistics coexist with a custom
     * augmentor (e.g. {@code IntervalAugmentor}'s max-hi) on a single tree, instead
     * of the two fighting over one overloaded slot. See ADR-002.
     */
    private int size = 1;
    private String tag = "";
    private boolean pathCompressed = false;
    private Augmentor<K> augmentor;

    public TreeNode1(K data, TreeNode1<K> nil) {
        this(data, nil, Color.RED, defaultAugmentor());
    }

    public TreeNode1(K data, TreeNode1<K> nil, Augmentor<K> augmentor) {
        this(data, nil, Color.RED, augmentor);
    }

    private TreeNode1(K data, TreeNode1<K> nil, Color color, Augmentor<K> augmentor) {
        if (nil == null) throw new IllegalArgumentException("nilSentinel cannot be null");
        this.data = data;
        this.nilSentinel = nil;
        this.keyOrder = nil.keyOrder;   // inherit the tree's ordering authority from its sentinel
        this.left = this.right = nil;
        this.parent = null;
        this.color = color;
        this.augmentor = augmentor != null ? augmentor : defaultAugmentor(); // Null-safe
        this.augmentor.apply(this);
    }

    private TreeNode1(K data, Color color, Comparator<? super K> keyOrder) {
        this.data = data;
        this.keyOrder = keyOrder;
        this.nilSentinel = this;
        this.left = this.right = this;
        this.parent = null;
        this.color = color;
        this.augmentedValue = 0;
        this.size = 0;            // the sentinel is empty: a NIL subtree has 0 nodes
        this.blackHeight = 1;
        this.height = 0;
        this.augmentor = defaultAugmentor();
        this.augmentor.apply(this);
    }

    public static <K> TreeNode1<K> createNode(K data, TreeNode1<K> nil) {
        return new TreeNode1<>(data, nil);
    }

    /**
     * Create a node and stamp {@code augment} into its {@link #augmentedValue} slot.
     *
     * @deprecated The value does not last. This factory uses the two-argument constructor, which
     *     installs the {@linkplain #defaultAugmentor() default augmentor} and has already run it
     *     ({@code augmentedValue = 1}) before the assignment here overwrites it — so the caller's
     *     value survives only until the next re-augment, which is the very next structural link
     *     the node takes part in. Measured: {@code createNodeWithAugment(42, nil, 999)} reads back
     *     999, and after one {@code setLeft} it reads 2. Nothing in this repository has ever called
     *     it, so nothing has ever depended on that (wiring audit 2026-08-17, seventh pass, "needs
     *     routing"); it predates the intrinsic {@link #size} field that freed the augment slot for
     *     custom augmentors, and it would be a trap for the first caller.
     *
     *     <p>It is not removed because it is {@code public} on a published 0.2.0 module and
     *     deleting it would force 0.3.0. The way to put a durable payload in the slot is to supply
     *     the augmentor that <em>computes</em> it — {@link #TreeNode1(Object, TreeNode1, Augmentor)}
     *     for one node, or {@link io.github.richeyworks.csrbt.OrderedSet#setAugmentor} /
     *     {@link io.github.richeyworks.csrbt.interfaces.AugmentedTree#setAugmentor} for a whole
     *     tree — because an augmentor is re-applied on every link and a stamped constant is not.
     */
    @Deprecated
    public static <K> TreeNode1<K> createNodeWithAugment(K data, TreeNode1<K> nil, int augment) {
        TreeNode1<K> node = new TreeNode1<>(data, nil);
        node.augmentedValue = augment;
        return node;
    }

    /**
     * Create a FRESH, independent NIL sentinel carrying this tree's key-ordering
     * authority. Each engine instance owns its own sentinel; every node built
     * against it inherits {@code keyOrder}. (ADR-002 step 2 replaced the former
     * argument-less {@code createNil()} — and the shared static {@code NIL} — with
     * this comparator-carrying factory.)
     */
    public static <K> TreeNode1<K> createNil(Comparator<? super K> keyOrder) {
        return new TreeNode1<>(null, Color.BLACK, keyOrder);
    }

    public static <K> boolean isSharedNil(TreeNode1<K> node, TreeNode1<K> nil) {
        return node == nil;
    }

    public K getData() {
        return data;
    }

    public TreeNode1<K> getLeft() {
        return left;
    }

    public TreeNode1<K> getRight() {
        return right;
    }

    public TreeNode1<K> getParent() {
        return parent;
    }

    public TreeNode1<K> getGrandparent() {
        return (parent != null) ? parent.parent : nilSentinel;
    }

    public TreeNode1<K> getUncle() {
        TreeNode1<K> gp = getGrandparent();
        if (gp == nilSentinel) return nilSentinel;
        return (parent == gp.left) ? gp.right : gp.left;
    }

    public TreeNode1<K> getSibling() {
        if (parent == null) return nilSentinel;
        return (this == parent.left) ? parent.right : parent.left;
    }

    public boolean isRed() {
        return color == Color.RED;
    }

    public boolean isBlack() {
        return color == Color.BLACK;
    }

    public boolean isNil() {
        return this == nilSentinel;
    }

    public boolean isLeaf() {
        return left.isNil() && right.isNil();
    }

    public int blackHeight() {
        if (isNil()) return 1;
        int leftBH = left.blackHeight();
        int rightBH = right.blackHeight();
        // Explicit check (not `assert`, which is disabled by default at runtime)
        // so this genuinely validates the invariant whenever it is called.
        if (leftBH != rightBH) {
            throw new IllegalStateException("Black-height violation at node " + data
                    + " (left=" + leftBH + ", right=" + rightBH + ")");
        }
        return (isBlack() ? 1 : 0) + leftBH;
    }

    /**
     * The CACHED black-height, which — unlike {@link #getHeight()} — is <b>not</b> guaranteed
     * current for every node, and is deliberately left that way (ADR-023).
     *
     * <p><b>What it is.</b> Informational bookkeeping on every strategy: {@code updateBlackHeight}
     * records {@code (isBlack() ? 1 : 0) + max(left, right)} without enforcing the red-black
     * invariant, because AVL/Splay/Hybrid colour every node black and legitimately have unequal
     * subtree black-heights. The exact, invariant-checking answer is {@link #blackHeight()} (no
     * {@code get}) — an O(subtree) recursive walk that throws {@link IllegalStateException} on a
     * genuine violation. Red-black validity itself is checked by {@code TreeDiagnostics}, never by
     * this accessor.</p>
     *
     * <p><b>Where it goes stale.</b> The link setters and the {@code *Local} ones both refresh it
     * for the nodes they touch, and the propagating {@link #setLeft}/{@link #setRight} — and the
     * write path's {@link #linkLeft}/{@link #linkRight}, which drop only the height leg — carry it
     * to the root; but {@link #setColor} and {@link #flipColor} update the recoloured node alone,
     * and neither the ADR-023 rotation climb nor the ADR-028 per-write repair carries anything but
     * height. Recolouring, not rotation, is the dominant
     * source: the RB insert and delete fixups recolour O(log n) nodes per write, so making this
     * exact would mean a propagation walk per recolour on the hottest path in the engine, for a
     * quantity with no consumer that needs it. Measured residue after ADR-023: 0% of nodes on
     * RedBlack under insert-only streams, 2.7% under mixed add/remove, and 0.2&ndash;8.5% on
     * AVL/Hybrid/WeightBalanced, essentially always off by exactly 1.</p>
     *
     * <p><b>If you need an exact value</b>, call {@link #blackHeight()}, or recompute the subtree
     * bottom-up yourself. Do not infer red-black validity from this field.</p>
     */
    public int getBlackHeight() {
        return blackHeight;
    }

    private void updateBlackHeight() {
        if (isNil()) {
            blackHeight = 1;
            return;
        }
        // Informational bookkeeping only. This is called from setLeft/setRight for
        // EVERY strategy, but only Red-Black trees maintain equal subtree
        // black-heights — AVL/Splay/Hybrid colour all nodes black and legitimately
        // have unequal black-heights. So we record a value without enforcing the
        // RB invariant here; RB validity is checked separately by TreeDiagnostics.
        int leftBH  = left.getBlackHeight();
        int rightBH = right.getBlackHeight();
        blackHeight = (isBlack() ? 1 : 0) + Math.max(leftBH, rightBH);
    }

    /**
     * The subtree height: 1 for a leaf, 0 for NIL. <b>Exact for every node</b>, like
     * {@link #getSize()} — the cache is maintained on every structural change, including
     * rotations, on every strategy (ADR-023).
     *
     * <p><b>How it is maintained: once per write.</b> The engine's five strategies link with
     * {@link #linkLeft}/{@link #linkRight}, which carry size, augment and black-height to the
     * root but no height at all, and rotate with the {@code TreeStrategy} {@code *Local}
     * primitives, which recompute the touched nodes only. Every write then ends with exactly one
     * height pass: {@code RedBlackStrategy} and {@code WeightBalancedStrategy} call
     * {@link #repairHeightUpward(TreeNode1)} from the write's anchor, while {@code AVLStrategy},
     * {@code HybridStrategy} and {@code SplayStrategy} need no call at all — their own passes
     * (the AVL rebalance walk; splaying to the root) already recompute every node from the
     * modification point to the root, because they steer by those very heights (ADR-028).</p>
     *
     * <p>Off the write path the propagating {@link #setLeft}/{@link #setRight} remain fully
     * height-maintaining, walking to the root like they always did — which is what keeps trees
     * wired top-down or in arbitrary order (snapshot deserialization, two-pass deep copy) exact
     * without any repair call of their own (AUDIT-2026-08-14 F-1). Those setters, not the
     * {@code link*} pair, are the safe default; see the rotation and linking notes on
     * {@link io.github.richeyworks.csrbt.strategy.TreeStrategy} for the rule a new strategy has to
     * follow.</p>
     *
     * <p><b>History.</b> Until ADR-023 this accessor could read high for any ANCESTOR of a
     * rotation under {@code RedBlackStrategy} and {@code WeightBalancedStrategy} — the two that do
     * not rebalance by height (AUDIT-2026-08-17 finding 21; AUDIT-2026-08-14 F-1 deferred the fix
     * on cost grounds). It was not a rare corner: the root alone was wrong after 98.7% of ascending
     * and 59.7% of random Red-Black inserts, and after 74.3% of ascending WeightBalanced inserts
     * with errors up to 8. Code written against that caveat — recomputing before reading — is still
     * correct, just no longer necessary.</p>
     *
     * <p><b>Cost, so that nobody re-litigates it by guess.</b> Exactness is now free on every
     * measured strategy &times; workload cell. The expensive case used to be Red-Black under a
     * MONOTONE insert stream, where ADR-023 maintained height twice per write in opposite
     * directions — 27.7 levels up at link time, 22.7 back down at rotation time — and paid about
     * +22% of write time for it. ADR-028 collapsed that to one pass: 6.0 levels per operation on
     * the same workload, and wall clock back at the pre-ADR-023 figure (+0.5%, inside a &plusmn;6%
     * noise floor). Uniform and mixed add/remove streams sit at 3.6 levels. For bulk-loading
     * known-sorted data {@code OrderedSet.buildFromSorted} is still the right answer — it is O(n)
     * and rotation-free. ADR-023 and ADR-028 have the tables.</p>
     */
    public int getHeight() {
        return height;
    }

    /**
     * Recompute this node's cached height from its children's cached heights.
     * Local and non-throwing — intended to be called while walking UP a path
     * (bottom-up) so that each ancestor's height is current before a parent's
     * balance factor is read. Unlike {@link #setLeft}/{@link #setRight}, this
     * does not propagate or re-augment; callers control the traversal.
     */
    public void refreshHeight() {
        if (isNil()) { height = 0; return; }
        int leftHeight  = (left  == null) ? 0 : left.getHeight();
        int rightHeight = (right == null) ? 0 : right.getHeight();
        height = 1 + Math.max(leftHeight, rightHeight);
    }

    private void updateHeight() {
        if (isNil()) {
            height = 0;
            return;
        }
        int leftHeight = left.getHeight();
        int rightHeight = right.getHeight();
        height = 1 + Math.max(leftHeight, rightHeight);
    }

    /**
     * Refresh the cached {@linkplain #getHeight() height} of every STRICT ancestor of this node,
     * stopping at the first ancestor whose recomputed height is unchanged (ADR-023).
     *
     * <p>This is the propagation that {@link #setLeftLocal}/{@link #setRightLocal} deliberately
     * skip and that rotations therefore have to make up for. It touches neither size nor the
     * augment payload — both are ancestor-invariant under a rotation — and it is a
     * <b>fixed-point climb</b>, not an unconditional walk to the root: a node's cached height is a
     * pure function of its two children's cached heights, so once a level recomputes to the value
     * it already held, no ancestor above it can change either. On uniform and mixed add/remove
     * workloads that exits after 1&ndash;3 levels; on a monotone (sorted) insert stream, where the
     * BST link has just pushed +1 up the whole spine and the rebalancing rotation takes it back
     * off, it runs the full height. ADR-023 has the measured distribution.</p>
     *
     * <p>Correct only if this node's own height is already current (the {@code *Local} setters
     * leave it so), every ancestor's was current before the change, and the change ORIGINATED
     * here — a second, higher origin (a rotation) is invisible from below and would let the climb
     * stop short. That is the precondition {@code TreeStrategy.rotateLeft}/{@code rotateRight}
     * satisfy by construction, since they climb from the rotation itself; a whole write has more
     * than one origin and uses {@link #repairHeightUpward(TreeNode1)} instead. Callers should
     * invoke it only when this node's height actually moved; otherwise the first comparison exits
     * on the value the caller just wrote and the climb is skipped.</p>
     *
     * <p>Black-height is deliberately NOT carried on this walk — see {@link #getBlackHeight()}.</p>
     */
    public void refreshHeightUpward() {
        TreeNode1<K> current = parent;
        while (current != null && current != nilSentinel) {
            int cached = current.height;
            current.updateHeight();
            if (current.height == cached) return;
            current = current.parent;
        }
    }

    /**
     * The single per-write height repair (ADR-028): recompute THIS node's cached height, then
     * climb its strict ancestors recomputing each, stopping at the first ancestor <em>above the
     * write's last rotation</em> whose height comes out unchanged.
     *
     * <p>Called once, at the end of a write, from the write's <b>anchor</b> — the deepest node
     * the write structurally touched (the newly linked node for an insert; the parent of the
     * spliced-out position for a delete). The engine's write paths link through
     * {@link #linkLeft}/{@link #linkRight} and rotate through the {@code TreeStrategy}
     * {@code *Local} primitives, so between the link and this call the only nodes whose cached
     * height can disagree with their children are strict ancestors of that anchor: a rotation is
     * always fired either at an ancestor of the anchor or at a child of one, and both shapes
     * recompute their touched triple bottom-up from children that are themselves anchor-free and
     * therefore exact.</p>
     *
     * <p><b>Why the stop needs {@code unconditionalThrough}.</b> A pure fixed-point climb is
     * correct only for a change that ORIGINATES at the anchor — the link's — because the climb
     * then sees it at every level until it dies out. A rotation introduces a second origin
     * higher up: it changes the height of the subtree it rearranges without that change being
     * visible at any node below it, so a climb that has already reached its fixed point lower
     * down would stop short and leave everything above the rotation stale (measured: a
     * weight-balanced ascending build goes wrong at n = 38). Passing the ancestor that ADOPTED
     * the write's last — that is, highest — rotated subtree makes the climb unconditional up to
     * and including that node, which is the last node the write wrote a height into; from its
     * parent upward the fixed-point stop is exact again. Pass {@code null} when the write
     * rotated nothing, and the climb is a pure fixed point from the anchor.</p>
     *
     * <p>On a monotone Red-Black insert stream that is a handful of levels: the BST link no
     * longer pushed the change up the spine and the rebalancing rotation sits two levels above
     * the new leaf, where it has already put the subtree height back. Before ADR-028 the same
     * write paid a 27.7-level link walk and a 22.7-level rotation climb. Safe on the sentinel
     * (NIL's height is 0 and it has no parent), so a delete that empties the tree can call it
     * unconditionally.</p>
     *
     * @param unconditionalThrough the ancestor that adopted this write's highest rotated
     *                             subtree, or {@code null} when the write rotated nothing
     */
    public void repairHeightUpward(TreeNode1<K> unconditionalThrough) {
        refreshHeight();
        boolean armed = unconditionalThrough == null;
        TreeNode1<K> current = parent;
        while (current != null && current != nilSentinel) {
            int cached = current.height;
            current.updateHeight();
            if (armed && current.height == cached) return;
            if (current == unconditionalThrough) armed = true;
            current = current.parent;
        }
    }

    public int depth() {
        int depth = 0;
        TreeNode1<K> current = this;
        // "No parent" is either null (freshly created) or the sentinel (a root
        // under the unified convention); stop at both so a root has depth 0.
        while (current.getParent() != null && !current.getParent().isNil()) {
            depth++;
            current = current.getParent();
        }
        return depth;
    }

    public int compareTo(TreeNode1<K> other) {
        return keyOrder.compare(this.data, other.data);
    }

    /**
     * Order this node's key against a raw key, through the same {@link #keyOrder}
     * authority as {@link #compareTo}. Sign matches {@code (this.key - otherKey)}:
     * negative if this node's key sorts before {@code otherKey}, 0 if equal,
     * positive if after. Used by search / range / interval navigation, which
     * compare a node against a query key rather than against another node.
     */
    public int compareKeyTo(K otherKey) {
        return keyOrder.compare(this.data, otherKey);
    }

    /**
     * Identity equality. Nodes are mutable (color, children, augment change on
     * rotation/insert), so a structural {@code equals}/{@code hashCode} would be
     * O(n), would mutate its hash over a node's lifetime — violating the hash
     * contract — and would conflate distinct-but-similar nodes. Collections that
     * track nodes (e.g. ancestor sets for LCA, clone memos) want identity, so
     * that is what we provide. Use {@code inOrder()} / a structural comparator
     * when value-based tree comparison is actually needed.
     */
    @Override
    public boolean equals(Object obj) {
        return this == obj;
    }

    @Override
    public int hashCode() {
        return System.identityHashCode(this);
    }

    @Override
    public TreeNode1<K> clone() throws CloneNotSupportedException {
        return deepCopy(nilSentinel);
    }

    public Color getColor() {
        return color;
    }

    public void setColor(Color color) {
        this.color = color;
        updateBlackHeight();
    }

    public void flipColor() {
        if (color == Color.RED) color = Color.BLACK;
        else color = Color.RED;
        updateBlackHeight();
    }

    public void setParent(TreeNode1<K> p) {
        if (this != nilSentinel) { // Prevent NIL from getting a parent
            this.parent = p;
        }
    }

    public void setLeft(TreeNode1<K> child) {
        left = child;
        if (child != null && !child.isNil()) {
            child.parent = this;
        }
        recomputeAugmentAndPropagate();   // refreshes size, augment, black-height AND height to root
    }

    public void setRight(TreeNode1<K> child) {
        right = child;
        if (child != null && !child.isNil()) {
            child.parent = this;
        }
        recomputeAugmentAndPropagate();   // refreshes size, augment, black-height AND height to root
    }

    /**
     * Link {@code child} as the left child and recompute THIS node's augment,
     * black-height and height locally — without walking the augment up to the
     * root. Intended for rotations, which rearrange a local pair but never
     * change any ancestor's subtree size, so the O(height) propagation that
     * {@link #setLeft} performs is pure waste there (it made each rotation
     * O(height) and inserts O(height²)). Insert/delete BST links must still use
     * the propagating {@link #setLeft}/{@link #setRight}.
     */
    public void setLeftLocal(TreeNode1<K> child) {
        left = child;
        if (child != null && !child.isNil()) {
            child.parent = this;
        }
        recomputeAugment();
        updateBlackHeight();
        updateHeight();
    }

    /** Right-side counterpart of {@link #setLeftLocal}. */
    public void setRightLocal(TreeNode1<K> child) {
        right = child;
        if (child != null && !child.isNil()) {
            child.parent = this;
        }
        recomputeAugment();
        updateBlackHeight();
        updateHeight();
    }

    /**
     * Link {@code child} as the left child on a WRITE PATH — the BST-descent link an
     * insert or a delete makes (ADR-028).
     *
     * <p>Recomputes size, augment and black-height for this node and for every ancestor,
     * exactly like {@link #setLeft}, and deliberately touches the cached
     * {@linkplain #getHeight() height} <b>nowhere</b>: not here and not above. Height is
     * restored <em>once per write</em>, by a single fixed-point
     * {@link #repairHeightUpward(TreeNode1)} from the write's anchor after the rebalancing pass has
     * finished — which is what stops the engine from pushing a height change up the whole
     * spine at link time and then taking it straight back off at rotation time (ADR-023
     * measured 26.7 levels up and 22.7 levels back down per Red-Black monotone insert).</p>
     *
     * <p><b>Use {@link #setLeft} unless you are inside such a write.</b> A caller that links
     * with this and never runs the repair leaves every ancestor's cached height stale — the
     * exact defect AUDIT-2026-08-14 F-1 recorded for arbitrary-order reconstruction (snapshot
     * deserialization, two-pass deep copy), which is why those paths keep using the
     * propagating {@link #setLeft}/{@link #setRight} and are unaffected by this pair. The
     * suffix-free setters remain the safe default, exactly as with
     * {@link #setLeft} vs {@link #setLeftLocal}.</p>
     */
    public void linkLeft(TreeNode1<K> child) {
        left = child;
        if (child != null && !child.isNil()) {
            child.parent = this;
        }
        recomputeAugmentAndPropagateWithoutHeight();
    }

    /** Right-side counterpart of {@link #linkLeft}; same contract. */
    public void linkRight(TreeNode1<K> child) {
        right = child;
        if (child != null && !child.isNil()) {
            child.parent = this;
        }
        recomputeAugmentAndPropagateWithoutHeight();
    }

    public void safeSetLeft(TreeNode1<K> child) {
        setLeft(child != null ? child : nilSentinel);
    }

    public void safeSetRight(TreeNode1<K> child) {
        setRight(child != null ? child : nilSentinel);
    }

    public void clear() {
        left = right = parent = nilSentinel;
        color = Color.RED;
        augmentedValue = 1;
        augmentedRef = null;
        size = 1;                 // a cleared node is a standalone leaf: one node
        lastRotation = Rotation.NONE;
        blackHeight = 1;
        height = 1;
    }

    public boolean isLessThan(TreeNode1<K> other) {
        return this.compareTo(other) < 0;
    }

    public boolean wasRotatedLeft() {
        return lastRotation == Rotation.LEFT;
    }

    public boolean wasRotatedRight() {
        return lastRotation == Rotation.RIGHT;
    }

    public Rotation getLastRotation() {
        return lastRotation;
    }

    public void setLastRotation(Rotation r) {
        this.lastRotation = r;
    }

    public boolean isPathCompressed() {
        return pathCompressed;
    }

    public void setPathCompressed(boolean pathCompressed) {
        this.pathCompressed = pathCompressed;
    }

    /**
     * Intrinsic subtree size (node count). Always maintained on structural links,
     * independent of the active {@link Augmentor}. This is what dynamic order
     * statistics reads — see {@link io.github.richeyworks.csrbt.util.OrderStatisticsOps}. NIL reports 0.
     */
    public int getSize() {
        return isNil() ? 0 : size;
    }

    public int getAugmentedValue() {
        return augmentedValue;
    }

    public void setAugmentedValue(int value) {
        this.augmentedValue = value;
    }

    /** The generic augment slot's payload, or {@code null}; see the field contract. */
    public Object getAugmentedRef() {
        return augmentedRef;
    }

    /**
     * Set the generic augment slot. Like {@link #setTag} this does NOT propagate:
     * callers that change augment-relevant state must follow with {@link #reaugment()}.
     */
    public void setAugmentedRef(Object ref) {
        this.augmentedRef = ref;
    }

    /**
     * Recompute this node's intrinsic subtree size from its children's sizes.
     * Always run (independent of the pluggable augmentor) so order statistics stay
     * correct no matter which augmentor is installed. NIL has size 0. Like the
     * augment recompute this is O(1) and rides the same bottom-up traversal, so
     * insert/delete/rotation stay O(log n).
     */
    private void recomputeSize() {
        if (isNil()) { size = 0; return; }
        int leftSize  = (left  == null || left.isNil())  ? 0 : left.size;
        int rightSize = (right == null || right.isNil()) ? 0 : right.size;
        size = 1 + leftSize + rightSize;
    }

    protected void recomputeAugment() {
        recomputeSize();                 // intrinsic structural metadata, always maintained
        if (this.augmentor != null) {
            this.augmentor.apply(this);
        }
    }

    /**
     * Recompute this node's augment and propagate it to the root. Public hook for
     * callers that mutate augment-relevant state outside the structural setters —
     * e.g. {@code setTag}-based interval high endpoints, which the augmentor reads
     * but {@link #setTag} does not itself trigger. Requires every node on the path
     * to root to carry the same augmentor for the propagated values to be correct.
     */
    public void reaugment() {
        recomputeAugmentAndPropagate();
    }

    /**
     * {@link #recomputeAugmentAndPropagate} minus the height leg — the walk
     * {@link #linkLeft}/{@link #linkRight} run on the write path (ADR-028). Size, augment and
     * black-height still ride it to the root; height is the business of the single per-write
     * {@link #repairHeightUpward(TreeNode1)}, so that a monotone insert stream maintains it once
     * instead of twice in opposite directions.
     */
    private void recomputeAugmentAndPropagateWithoutHeight() {
        recomputeAugment();
        updateBlackHeight();
        TreeNode1<K> current = this;
        while (current.parent != null) {
            current = current.parent;
            current.recomputeAugment();
            current.updateBlackHeight();
        }
    }

    private void recomputeAugmentAndPropagate() {
        // Heights and black-heights ride the same walk as sizes/augments. Before
        // 2026-08-14 this walk refreshed only size + augment, so any tree wired
        // top-down or in arbitrary order (snapshot deserialization, two-pass deep
        // copy) converged to correct sizes but STALE cached heights — and
        // AVL/Hybrid then computed balance factors from those stale values,
        // violating their own invariant on the next insert (AUDIT-2026-08-14 F-1).
        //
        // ADR-028 moved the ENGINE's write paths off this walk and onto
        // linkLeft/linkRight + one repairHeightUpward per write, but deliberately left
        // the height leg here: arbitrary-order wiring has no "end of write" to hang a
        // single repair on, and this unconditional walk is what makes it converge from
        // any order. Reconstruction keeps paying it; the hot path no longer does.
        recomputeAugment();
        updateBlackHeight();
        updateHeight();
        TreeNode1<K> current = this;
        while (current.parent != null) {
            current = current.parent;
            current.recomputeAugment();
            current.updateBlackHeight();
            current.updateHeight();
        }
    }

    public void setAugmentor(Augmentor<K> augmentor) {
        this.augmentor = augmentor != null ? augmentor : defaultAugmentor();
        recomputeAugmentAndPropagate();
    }

    public String getTag() {
        return tag;
    }

    public void setTag(String tag) {
        this.tag = tag;
    }

    public TreeNode1<K> deepCopy(TreeNode1<K> nil) {
        if (this.isNil()) return nil;
        TreeNode1<K> copy = new TreeNode1<>(this.data, nil);
        copy.setColor(this.color);
        copy.safeSetLeft(this.left.deepCopy(nil));
        copy.safeSetRight(this.right.deepCopy(nil));
        copy.lastRotation = this.lastRotation;
        copy.augmentedValue = this.augmentedValue;
        copy.augmentedRef = this.augmentedRef;   // reference copy — payloads are immutable by contract
        copy.size = this.size;
        copy.blackHeight = this.blackHeight;
        copy.height = this.height;
        copy.tag = this.tag;
        copy.pathCompressed = this.pathCompressed;
        return copy;
    }

    public String toIndentedString() {
        return toIndentedString(0);
    }

    private String toIndentedString(int level) {
        if (isNil()) return "";
        StringBuilder sb = new StringBuilder();
        sb.append("  ".repeat(level))
          .append(getData())
          .append(isRed() ? " [R]" : " [B]")
          .append("\n");
        sb.append(left.toIndentedString(level + 1));
        sb.append(right.toIndentedString(level + 1));
        return sb.toString();
    }

    public boolean isTripleRed() {
        if (!this.isRed()) return false;
        TreeNode1<K> p = this.getParent();
        TreeNode1<K> gp = (p != null) ? p.getParent() : null;
        return (p != null && p.isRed() && gp != null && gp.isRed());
    }

    @Override
    public String toString() {
        return (isNil() ? "NIL" : data + (isRed() ? "R" : "B"));
    }

    /**
     * Validate this node's local red-black invariants, throwing
     * {@link IllegalStateException} on violation. Uses explicit checks rather
     * than {@code assert} (which is disabled by default at runtime) so the
     * validation actually runs in production.
     */
    public void assertValid() {
        if (isNil() && !isBlack()) {
            throw new IllegalStateException("NIL nodes must be black");
        }
        if (isRed()) {
            if (!left.isBlack()) {
                throw new IllegalStateException("Red node " + data + " has a red left child");
            }
            if (!right.isBlack()) {
                throw new IllegalStateException("Red node " + data + " has a red right child");
            }
        }
    }
}
