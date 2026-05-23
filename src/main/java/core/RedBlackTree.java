package core;

import core.strategy.TreeStrategy;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

public class RedBlackTree {

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

    // ── Accessors ─────────────────────────────────────────────────────────────

    public TreeNode1 getRoot()            { return root; }
    public void      setRoot(TreeNode1 r) { this.root = r; }
    public TreeNode1 getNIL()             { return NIL; }    // strategies need this
    public TreeStrategy getStrategy()     { return strategy; }
}
