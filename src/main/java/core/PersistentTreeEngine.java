package core;

import core.interfaces.TreeEngine;

import java.util.ArrayList;
import java.util.List;

/**
 * Persistent (immutable, path-copying) ordered set of {@code int} keys.
 *
 * <p>This is a genuinely new {@link TreeEngine} — not a {@code TreeStrategy}
 * wrapped around {@link RedBlackTree}. Its nodes are immutable; every mutation
 * returns a new root that structurally shares all untouched subtrees with the
 * previous version (classic persistence, CLRS-style path copying). The cost is
 * O(log n) fresh nodes per update; the payoff is that every past version
 * remains intact and queryable.</p>
 *
 * <p>It satisfies the same representation-neutral contract as every other
 * engine, so it plugs into the {@link TreeEngineRegistry} alongside the
 * pointer-based BST family without that family knowing it exists.</p>
 *
 * <p>Set semantics: duplicate inserts are ignored. {@link #inOrder()} returns
 * ascending keys. Not thread-safe.</p>
 */
public final class PersistentTreeEngine implements TreeEngine {

    /** Immutable node. Once constructed, never mutated. */
    private static final class Node {
        final int  key;
        final Node left;
        final Node right;
        final int  count;   // subtree size, for O(log n)-free size()

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
    public void add(int value) {
        Node next = insert(root, value);
        if (next != root) {          // only a real structural change makes a version
            root = next;
            versions.add(root);
        }
    }

    private static Node insert(Node n, int key) {
        if (n == null)         return new Node(key, null, null);
        if (key == n.key)      return n;                       // set: no duplicates
        if (key < n.key) {
            Node l = insert(n.left, key);
            return l == n.left ? n : new Node(n.key, l, n.right);
        } else {
            Node r = insert(n.right, key);
            return r == n.right ? n : new Node(n.key, n.left, r);
        }
    }

    @Override
    public void remove(int value) {
        Node next = delete(root, value);
        if (next != root) {
            root = next;
            versions.add(root);
        }
    }

    private static Node delete(Node n, int key) {
        if (n == null) return null;
        if (key < n.key) {
            Node l = delete(n.left, key);
            return l == n.left ? n : new Node(n.key, l, n.right);
        }
        if (key > n.key) {
            Node r = delete(n.right, key);
            return r == n.right ? n : new Node(n.key, n.left, r);
        }
        // key == n.key : remove this node
        if (n.left  == null) return n.right;
        if (n.right == null) return n.left;
        int succ = min(n.right);                  // in-order successor
        Node r = delete(n.right, succ);
        return new Node(succ, n.left, r);
    }

    private static int min(Node n) {
        while (n.left != null) n = n.left;
        return n.key;
    }

    @Override
    public boolean contains(int value) {
        Node n = root;
        while (n != null) {
            if (value == n.key) return true;
            n = value < n.key ? n.left : n.right;
        }
        return false;
    }

    @Override
    public List<Integer> inOrder() {
        List<Integer> out = new ArrayList<>();
        walk(root, out);
        return out;
    }

    private static void walk(Node n, List<Integer> out) {
        if (n == null) return;
        walk(n.left, out);
        out.add(n.key);
        walk(n.right, out);
    }

    @Override
    public int size() { return sizeOf(root); }

    @Override
    public void clear() {
        root = null;
        versions.add(null);
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
        List<Integer> out = new ArrayList<>();
        walk(versions.get(version), out);
        return out;
    }
}
