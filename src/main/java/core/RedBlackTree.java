package core;

import core.interfaces.TreeEngine;
import core.strategy.TreeStrategy;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;

public class RedBlackTree implements TreeEngine, MutableTree {

    private static final Logger logger = LogManager.getLogger(RedBlackTree.class);

    private TreeNode1 root;
    private final TreeNode1 NIL;      // sentinel alias — never reassigned
    private final TreeStrategy strategy;

    public RedBlackTree(TreeStrategy strategy) {
        this.strategy = strategy;
        this.NIL      = TreeNode1.NIL;
        this.root     = NIL;
    }

    // ── Core operations ───────────────────────────────────────────────────────

    public void add(int value) {
        logger.info("Inserting value={}", value);
        TreeNode1 newNode = TreeNode1.createNode(value, NIL);
        strategy.insert(this, newNode);   // strategy calls setRoot() internally if needed
        strategy.fixInsert(this, newNode); // fixInsert enforces root BLACK at the end
    }

    public void remove(int value) {
        logger.info("Removing value={}", value);
        TreeNode1 node = strategy.search(this, value);
        if (node.isNil()) {
            logger.warn("Remove failed — value={} not found", value);
            return;
        }
        strategy.delete(this, node);
    }

    public boolean contains(int value) {
        logger.debug("Search value={}", value);
        return !strategy.search(this, value).isNil();
    }

    // ── Structural operations (strategies call back through here) ─────────────
    // Keeping rotation on the tree lets the tree own its own structure,
    // while the strategy decides *when* to rotate.

    public void rotateLeft(TreeNode1 x)  { strategy.rotateLeft(this, x); }
    public void rotateRight(TreeNode1 y) { strategy.rotateRight(this, y); }

    // ── TreeEngine: representation-neutral views ──────────────────────────────
    // These expose behaviour only (ordered keys / size / clear) so callers can
    // treat any backing structure uniformly via the TreeEngine interface.

    /** {@inheritDoc} Keys in ascending order via iterative in-order walk. */
    @Override
    public List<Integer> inOrder() {
        List<Integer> out = new ArrayList<>();
        Deque<TreeNode1> stack = new ArrayDeque<>();
        TreeNode1 cur = root;
        while (!stack.isEmpty() || !cur.isNil()) {
            while (!cur.isNil()) {
                stack.push(cur);
                cur = cur.getLeft();
            }
            cur = stack.pop();
            out.add(cur.getData());
            cur = cur.getRight();
        }
        return out;
    }

    /** {@inheritDoc} */
    @Override
    public int size() {
        int n = 0;
        Deque<TreeNode1> stack = new ArrayDeque<>();
        TreeNode1 cur = root;
        while (!stack.isEmpty() || !cur.isNil()) {
            while (!cur.isNil()) {
                stack.push(cur);
                cur = cur.getLeft();
            }
            cur = stack.pop();
            n++;
            cur = cur.getRight();
        }
        return n;
    }

    /** {@inheritDoc} Detaches the whole tree by resetting the root to NIL. */
    @Override
    public void clear() {
        this.root = NIL;
    }

    // ── Accessors ─────────────────────────────────────────────────────────────

    public TreeNode1 getRoot()            { return root; }
    public void      setRoot(TreeNode1 r) { this.root = r; }
    public TreeNode1 getNIL()             { return NIL; }    // strategies need this
    public TreeStrategy getStrategy()     { return strategy; }
}
