package core;

import core.interfaces.TreeEngine;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;

/**
 * Persistent (immutable, path-copying) ordered set of {@code int} keys.
 *
 * <p>This is a genuinely new {@link TreeEngine} — not a {@code TreeStrategy}
 * wrapped around {@link RedBlackTree}. Its nodes are immutable; every mutation
 * returns a new root that structurally shares all untouched subtrees with the
 * previous version (classic persistence, CLRS-style path copying). The cost is
 * O(height) fresh nodes per update; the payoff is that every past version
 * remains intact and queryable.</p>
 *
 * <p>It satisfies the same representation-neutral contract as every other
 * engine, so it plugs into the {@link TreeEngineRegistry} alongside the
 * pointer-based BST family without that family knowing it exists.</p>
 *
 * <p><b>Balancing caveat:</b> this engine is an <em>unbalanced</em> persistent
 * BST. It does not self-balance, so adversarial or sorted input produces a tall
 * tree and O(n) worst-case operations (vs. O(log n) for the balanced engines).
 * All traversals here are <em>iterative</em>, so a tall tree degrades gracefully
 * to O(n) time rather than overflowing the call stack — but if you need
 * worst-case O(log n), use a balanced strategy. Making this a balanced
 * persistent structure (weight-balanced / path-copying red-black) is future work.</p>
 *
 * <p>Set semantics: duplicate inserts are ignored. {@link #inOrder()} returns
 * ascending keys. Not thread-safe.</p>
 */
public final class PersistentTreeEngine implements TreeEngine<Integer> {

    /** Immutable node. Once constructed, never mutated. */
    private static final class Node {
        final int  key;
        final Node left;
        final Node right;
        final int  count;   // subtree size, for O(1) size()

        Node(int key, Node left, Node right) {
            this.key   = key;
            this.left  = left;
            this.right = right;
            this.count = 1 + sizeOf(left) + sizeOf(right);
        }
    }

    private static int sizeOf(Node n) { return n == null ? 0 : n.count; }

    /** Current root. */
    private Node root;

    /** Version history — each entry is the root of a past (or current) version. */
    private final List<Node> versions = new ArrayList<>();

    public PersistentTreeEngine() {
        this.root = null;
        versions.add(null);          // version 0 = empty
    }

    // ── TreeEngine ─────────────────────────────────────────────────────────────

    @Override
    public void add(Integer value) {
        Node next = insert(root, value);
        if (next != root) {          // only a real structural change makes a version
            root = next;
            versions.add(root);
        }
    }

    /**
     * Iterative path-copying insert. Descends to the insertion point recording the
     * ancestor path, then rebuilds that path bottom-up with fresh nodes (every
     * untouched subtree is shared). Iterative so a degenerate (tall) tree cannot
     * overflow the stack. Returns the original root unchanged if the key exists.
     */
    private static Node insert(Node root, int key) {
        Deque<Node> path = new ArrayDeque<>();
        Node cur = root;
        while (cur != null) {
            if (key == cur.key) return root;       // set semantics: no duplicates
            path.push(cur);
            cur = key < cur.key ? cur.left : cur.right;
        }
        Node rebuilt = new Node(key, null, null);  // fresh leaf
        while (!path.isEmpty()) {
            Node p = path.pop();
            rebuilt = key < p.key ? new Node(p.key, rebuilt, p.right)
                                  : new Node(p.key, p.left, rebuilt);
        }
        return rebuilt;
    }

    @Override
    public void remove(Integer value) {
        Node next = delete(root, value);
        if (next != root) {
            root = next;
            versions.add(root);
        }
    }

    /**
     * Iterative path-copying delete. Finds the target (recording the ancestor
     * path), builds the replacement subtree (promoting a child, or splicing in the
     * in-order successor for a two-child node — that splice is itself path-copied),
     * then rebuilds the ancestor path bottom-up. Returns the original root if the
     * key is absent.
     */
    private static Node delete(Node root, int key) {
        Deque<Node> path = new ArrayDeque<>();
        Node cur = root;
        while (cur != null && cur.key != key) {
            path.push(cur);
            cur = key < cur.key ? cur.left : cur.right;
        }
        if (cur == null) return root;              // not found — no change

        Node replacement;
        if (cur.left == null) {
            replacement = cur.right;
        } else if (cur.right == null) {
            replacement = cur.left;
        } else {
            // Two children: splice out the in-order successor (min of right
            // subtree) with path copying, then put its key in cur's slot.
            Deque<Node> succPath = new ArrayDeque<>();
            Node s = cur.right;
            while (s.left != null) { succPath.push(s); s = s.left; }
            Node sub = s.right;                    // promote successor's right child
            while (!succPath.isEmpty()) {
                Node p = succPath.pop();           // we always descended left
                sub = new Node(p.key, sub, p.right);
            }
            replacement = new Node(s.key, cur.left, sub);
        }

        // Rebuild ancestors. The slot direction is how we descended to cur, i.e.
        // comparing the (target) key to each ancestor's key.
        Node rebuilt = replacement;
        while (!path.isEmpty()) {
            Node p = path.pop();
            rebuilt = key < p.key ? new Node(p.key, rebuilt, p.right)
                                  : new Node(p.key, p.left, rebuilt);
        }
        return rebuilt;
    }

    @Override
    public boolean contains(Integer value) {
        Node n = root;
        while (n != null) {
            if (value == n.key) return true;
            n = value < n.key ? n.left : n.right;
        }
        return false;
    }

    @Override
    public List<Integer> inOrder() {
        return inOrderOf(root);
    }

    /** Iterative in-order traversal (stack-safe on a degenerate tree). */
    private static List<Integer> inOrderOf(Node node) {
        List<Integer> out = new ArrayList<>();
        Deque<Node> stack = new ArrayDeque<>();
        Node cur = node;
        while (cur != null || !stack.isEmpty()) {
            while (cur != null) { stack.push(cur); cur = cur.left; }
            cur = stack.pop();
            out.add(cur.key);
            cur = cur.right;
        }
        return out;
    }

    @Override
    public int size() { return sizeOf(root); }

    @Override
    public void clear() {
        if (root != null) {           // don't record a redundant empty version
            root = null;
            versions.add(null);
        }
    }

    // ── Persistence extras (the reason to choose this engine) ──────────────────

    /** @return number of retained versions (1 = just the empty starting version). */
    public int versionCount() { return versions.size(); }

    /** @return ascending keys of a past version; version 0 is the empty start. */
    public List<Integer> inOrderOfVersion(int version) {
        if (version < 0 || version >= versions.size()) {
            throw new IndexOutOfBoundsException(
                "version " + version + " of " + versions.size());
        }
        return inOrderOf(versions.get(version));
    }
}
