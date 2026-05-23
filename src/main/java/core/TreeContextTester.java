package test.core;

import core.RedBlackStrategy;
import core.SplayStrategy;
import core.TreeContext;
import core.TreeNode1;
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import java.util.*;

@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
public class TreeContextTester {
    private static final Logger logger = LogManager.getLogger(TreeContextTester.class);
    private TreeContext tree;

    @BeforeAll
    static void setupSuite() {
        logger.info("=== TREE TEST SUITE: READY TO EXPLODE ===");
        System.out.println("🔥 TreeContextTester: 100+ NODE CHAOS UNLEASHED 🔥");
    }

    @BeforeEach
    void reset() {
        logger.info("=== RESETTING TREE ===");
        tree = new TreeContext(new RedBlackStrategy());
    }

    private int blackHeight(TreeNode1 node) {
        if (node == TreeNode1.NIL) return 0;
        int leftHeight = blackHeight(node.getLeft());
        int rightHeight = blackHeight(node.getRight());
        assertEquals(leftHeight, rightHeight, "Black height mismatch at " + node.getData());
        return leftHeight + (node.isRed() ? 0 : 1);
    }

    private void checkRedBlackProperties(TreeNode1 root) {
        if (root == TreeNode1.NIL) return;
        assertFalse(root.isRed(), "Root must be black!");
        checkNoRedBlack(root);
        blackHeight(root);
    }

    private void checkNoRedBlack(TreeNode1 node) {
        if (node == TreeNode1.NIL) return;
        if (node.isRed()) {
            assertFalse(node.getLeft().isRed(), "Red node " + node.getData() + " has red left child!");
            assertFalse(node.getRight().isRed(), "Red node " + node.getData() + " has red right child!");
        }
        checkNoRedBlack(node.getLeft());
        checkNoRedBlack(node.getRight());
    }

    @Test
    @Order(1)
    public void testExample() {
        logger.debug("Running example test—buck wild flex!");
        assertTrue(true, "Test suite’s alive—let’s roll!");
    }

    @Test
    @Order(2)
    public void testIsFull() {
        logger.info("=== TEST: IS FULL ===");
        assertTrue(tree.getTree().isFull(), "Empty tree should be full!");

        tree.add(10);
        assertTrue(tree.getTree().isFull(), "Single-node tree should be full!");
        checkRedBlackProperties(tree.getTree().getRoot());

        tree.add(5);
        tree.add(15);
        assertTrue(tree.getTree().isFull(), "Balanced tree [10,5,15] should be full!");
        checkRedBlackProperties(tree.getTree().getRoot());

        tree.add(20);
        assertTrue(tree.getTree().isFull(), "Tree [10,5,15,20] should still be full!");
        checkRedBlackProperties(tree.getTree().getRoot());
    }

    @Test
    @Order(3)
    public void testSplayMode() {
        logger.info("=== TEST: SPLAY MODE ===");
        tree.setStrategy(new SplayStrategy());
        tree.add(10);
        tree.add(5);
        tree.add(15);
        assertTrue(tree.contains(5), "Splay tree should contain 5!");
        assertTrue(tree.contains(15), "Splay tree should contain 15!");
        // Splay brings last accessed node to root
        tree.contains(5);
        assertEquals(5, tree.getTree().getRoot().getData(), "Root should be 5 after splay!");
    }

    @Test
    @Order(4)
    public void testAlienSeed() {
        logger.info("=== TEST: ALIEN SEED ===");
        tree.alienSeed(100, 3, 10);
        assertTrue(tree.getSize() > 1, "Alien seed should create multiple nodes!");
        checkRedBlackProperties(tree.getTree().getRoot());
    }

    // Update remaining tests (similar to BinarySearchTreeTester, replacing BinarySearchTree1 with TreeContext)
}
