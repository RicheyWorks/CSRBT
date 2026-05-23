package test.core;

import core.BinarySearchTree1;
import core.TreeNode1;
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import java.util.*;

@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
public class BinarySearchTreeTester {
    private static final Logger logger = LogManager.getLogger(BinarySearchTreeTester.class);
    private BinarySearchTree1 bst;

    @BeforeAll
    static void setupSuite() {
        logger.info("=== RED-BLACK TREE TEST SUITE: READY TO EXPLODE ===");
        System.out.println("🔥 BinarySearchTreeTester: 100+ NODE CHAOS UNLEASHED 🔥");
    }

    @BeforeEach
    void reset() {
        logger.info("=== RESETTING RED-BLACK TREE ===");
        bst = new BinarySearchTree1();
    }

    // Helper methods for Red-Black validation
    private int blackHeight(TreeNode1 node) {
        if (node == TreeNode1.NIL) return 0; // Updated NIL reference
        int leftHeight = blackHeight(node.getLeft());
        int rightHeight = blackHeight(node.getRight());
        assertEquals(leftHeight, rightHeight, "Black height mismatch at " + node.getData());
        return leftHeight + (node.isRed() ? 0 : 1);
    }

    private void checkRedBlackProperties(TreeNode1 root) {
        // Property 2: Root is black
        if (root == TreeNode1.NIL) return; // Updated NIL reference
        assertFalse(root.isRed(), "Root must be black!");
        // Property 4: No two reds in a row
        checkNoRedRed(root);
        // Property 5: Black height consistency (checked within blackHeight)
        blackHeight(root);
    }

    private void checkNoRedRed(TreeNode1 node) {
        if (node == TreeNode1.NIL) return; // Updated NIL reference
        if (node.isRed()) {
            assertFalse(node.getLeft().isRed(), "Red node " + node.getData() + " has red left child!");
            assertFalse(node.getRight().isRed(), "Red node " + node.getData() + " has red right child!");
        }
        checkNoRedRed(node.getLeft());
        checkNoRedRed(node.getRight());
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
        assertTrue(bst.isFull(), "Empty tree should be full!");

        bst.add(10);
        assertTrue(bst.isFull(), "Single-node tree should be full!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.add(5);
        bst.add(15);
        assertTrue(bst.isFull(), "Balanced tree [10,5,15] should be full!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.add(20);
        assertTrue(bst.isFull(), "Tree [10,5,15,20] should still be full in Red-Black!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(3)
    public void testEquals() {
        logger.info("=== TEST: EQUALS ===");
        assertTrue(bst.equals(new BinarySearchTree1()), "Empty trees should be equal!");

        bst.add(10);
        BinarySearchTree1 bst2 = new BinarySearchTree1();
        bst2.add(10);
        assertTrue(bst.equals(bst2), "Single-node trees should be equal!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.add(5);
        bst.add(15);
        bst2.add(15);
        bst2.add(5);
        logger.debug("BST1: {}, BST2: {}", bst.toString(), bst2.toString());
        assertFalse(bst.equals(bst2), "Different insertion order should fail equals!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(4)
    public void testRemoveLeaves() {
        logger.info("=== TEST: REMOVE LEAVES ===");
        bst.add(10);
        bst.add(5);
        bst.add(15);
        bst.add(2);
        bst.add(7);

        assertFalse(bst.isEmpty(), "Tree shouldn’t be empty yet!");
        bst.removeLeaves();
        assertFalse(bst.contains(2), "Leaf 2 should be gone!");
        assertFalse(bst.contains(7), "Leaf 7 should be gone!");
        assertTrue(bst.contains(10), "Root should stick around!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.removeLeaves();
        assertTrue(bst.contains(10), "Root should still be here!");
        assertFalse(bst.contains(5), "5 should be gone!");
        assertFalse(bst.contains(15), "15 should be gone!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst = new BinarySearchTree1();
        bst.add(42);
        bst.removeLeaves();
        assertTrue(bst.isEmpty(), "Single-node tree should empty out!");

        bst = new BinarySearchTree1();
        bst.add(10);
        bst.add(20);
        bst.add(30);
        bst.add(40);
        bst.add(50);
        bst.removeLeaves();
        assertFalse(bst.contains(50), "Deep leaf 50 should be toast!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(5)
    public void testTrim() {
        logger.info("=== TEST: TRIM ===");
        assertTrue(bst.isEmpty(), "Empty tree should stay empty after trim!");

        bst.add(10);
        bst.trim(20, 30);
        assertTrue(bst.isEmpty(), "10 < 20 should trim to empty!");

        bst.add(5);
        bst.add(15);
        bst.trim(20, 30);
        assertTrue(bst.isEmpty(), "All < 20 should trim to empty!");

        bst.add(25);
        bst.trim(20, 30);
        assertFalse(bst.isEmpty(), "25 in [20, 30] should stay!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst = new BinarySearchTree1();
        bst.add(10);
        bst.add(5);
        bst.add(15);
        bst.trim(16, 19);
        assertTrue(bst.isEmpty(), "All out of [16, 19] should trim to empty!");
    }

    @Test
    @Order(6)
    public void testSize() {
        logger.info("=== TEST: SIZE ===");
        assertEquals(0, bst.size(), "Empty tree size should be 0!");

        bst.add(10);
        bst.add(5);
        bst.add(15);
        bst.add(2);
        bst.add(7);
        assertEquals(5, bst.size(), "Size should be 5!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.add(10);
        bst.add(5);
        assertEquals(5, bst.size(), "Duplicates shouldn’t bump size!");

        bst.remove(5);
        assertEquals(4, bst.size(), "Size should drop to 4!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.remove(100);
        assertEquals(4, bst.size(), "Non-existent remove shouldn’t change size!");

        bst.clear();
        assertEquals(0, bst.size(), "Cleared tree should be 0!");
    }

    @Test
    @Order(7)
    public void testHeight() {
        logger.info("=== TEST: HEIGHT ===");
        assertEquals(-1, bst.height(), "Empty tree height should be -1!");

        bst.add(10);
        assertEquals(1, bst.height(), "Single-node height should be 1!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.add(5);
        bst.add(15);
        bst.add(2);
        bst.add(7);
        assertTrue(bst.height() <= 3, "Red-Black height should be <= 3 for 5 nodes!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst = new BinarySearchTree1();
        for (int i = 1; i <= 10; i++) bst.add(i);
        assertTrue(bst.height() <= (int)(1.44 * Math.log(10 + 2) / Math.log(2)) - 1,
                   "Red-Black height should be <= 1.44*log₂(12)-1 for 10 nodes!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(8)
    public void testMaxValue() {
        logger.info("=== TEST: MAX VALUE ===");
        assertThrows(NoSuchElementException.class, () -> bst.maxValue(), "Empty tree should throw!");

        bst.add(42);
        assertEquals(42, bst.maxValue(), "Single-node max should be 42!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst = new BinarySearchTree1();
        bst.add(10);
        bst.add(5);
        bst.add(2);
        assertEquals(10, bst.maxValue(), "Left-heavy max should be 10!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst = new BinarySearchTree1();
        bst.add(10);
        bst.add(15);
        bst.add(20);
        assertEquals(20, bst.maxValue(), "Right-heavy max should be 20!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(9)
    public void testCountLeaves() {
        logger.info("=== TEST: COUNT LEAVES ===");
        assertEquals(0, bst.countLeaves(), "Empty tree should have 0 leaves!");

        bst.add(10);
        assertEquals(1, bst.countLeaves(), "Single-node should have 1 leaf!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.add(5);
        bst.add(15);
        assertEquals(2, bst.countLeaves(), "Tree [10,5,15] should have 2 leaves!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(10)
    public void testSum() {
        logger.info("=== TEST: SUM ===");
        assertEquals(0, bst.sum(), "Empty tree sum should be 0!");

        bst.add(10);
        assertEquals(10, bst.sum(), "Single-node sum should be 10!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.add(5);
        bst.add(15);
        bst.add(2);
        bst.add(7);
        assertEquals(39, bst.sum(), "Sum should be 39!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(11)
    public void testAverage() {
        logger.info("=== TEST: AVERAGE ===");
        assertEquals(0, bst.average(), "Empty tree average should be 0!");

        bst.add(10);
        assertEquals(10.0, bst.average(), 0.01, "Single-node average should be 10!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.add(20);
        bst.add(30);
        assertEquals(20.0, bst.average(), 0.01, "Average should be 20!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(12)
    public void testContainsIter() {
        logger.info("=== TEST: CONTAINS ITER ===");
        assertFalse(bst.containsIter(10), "Empty tree shouldn’t contain 10!");

        bst.add(10);
        assertTrue(bst.containsIter(10), "Should contain 10!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.add(5);
        bst.add(15);
        assertTrue(bst.containsIter(5), "Should contain 5!");
        assertTrue(bst.containsIter(15), "Should contain 15!");
        assertFalse(bst.containsIter(7), "Shouldn’t contain 7!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(13)
    public void testRemove() {
        logger.info("=== TEST: REMOVE ===");
        bst.add(10);
        bst.add(5);
        bst.add(15);
        bst.add(2);
        bst.add(7);

        bst.remove(2);
        assertFalse(bst.contains(2), "2 should be gone!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.remove(5);
        assertFalse(bst.contains(5), "5 should be gone!");
        assertTrue(bst.contains(7), "7 should stay!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.remove(10);
        assertFalse(bst.contains(10), "10 should be gone!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(14)
    public void testSizeRecursive() {
        logger.info("=== TEST: SIZE RECURSIVE ===");
        assertEquals(0, bst.sizeRecursive(), "Empty tree size should be 0!");

        bst.add(10);
        bst.add(5);
        bst.add(15);
        assertEquals(3, bst.sizeRecursive(), "Size should be 3!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(15)
    public void testMinValue() {
        logger.info("=== TEST: MIN VALUE ===");
        assertThrows(NoSuchElementException.class, () -> bst.minValue(), "Empty tree should throw!");

        bst.add(42);
        assertEquals(42, bst.minValue(), "Single-node min should be 42!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst = new BinarySearchTree1();
        bst.add(10);
        bst.add(5);
        bst.add(2);
        assertEquals(2, bst.minValue(), "Left-heavy min should be 2!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(16)
    public void testPostOrderTraversal() {
        logger.info("=== TEST: POST-ORDER TRAVERSAL ===");
        assertTrue(bst.postOrderTraversal().isEmpty(), "Empty tree traversal should be empty!");

        bst.add(10);
        assertEquals(List.of(10), bst.postOrderTraversal(), "Single-node post-order should be [10]!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.add(5);
        bst.add(15);
        assertEquals(List.of(5, 15, 10), bst.postOrderTraversal(), "Post-order should be [5, 15, 10]!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(17)
    public void testInOrderTraversal() {
        logger.info("=== TEST: IN-ORDER TRAVERSAL ===");
        assertTrue(bst.inOrderTraversal().isEmpty(), "Empty tree traversal should be empty!");

        bst.add(10);
        bst.add(5);
        bst.add(15);
        assertEquals(List.of(5, 10, 15), bst.inOrderTraversal(), "In-order should be sorted!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(18)
    public void testPreOrderTraversal() {
        logger.info("=== TEST: PRE-ORDER TRAVERSAL ===");
        assertTrue(bst.preOrderTraversal().isEmpty(), "Empty tree traversal should be empty!");

        bst.add(10);
        bst.add(5);
        bst.add(15);
        assertEquals(List.of(10, 5, 15), bst.preOrderTraversal(), "Pre-order should be [10, 5, 15]!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(19)
    public void testToString() {
        logger.info("=== TEST: TO STRING ===");
        assertEquals("[]", bst.toString(), "Empty tree should be '[]'!");

        bst.add(10);
        assertEquals("[10]", bst.toString(), "Single-node should be '[10]'!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.add(5);
        bst.add(15);
        assertEquals("[5, 10, 15]", bst.toString(), "Should be sorted [5, 10, 15]!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
    }

    @Test
    @Order(20)
    public void testClear() {
        logger.info("=== TEST: CLEAR ===");
        bst.add(10);
        bst.add(5);
        bst.add(15);
        bst.clear();
        assertTrue(bst.isEmpty(), "Tree should be empty after clear!");
        assertEquals(0, bst.size(), "Size should be 0!");
    }

    @Test
    @Order(21)
    public void testIsEmpty() {
        logger.info("=== TEST: IS EMPTY ===");
        assertTrue(bst.isEmpty(), "New tree should be empty!");

        bst.add(10);
        assertFalse(bst.isEmpty(), "Tree with 10 shouldn’t be empty!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()

        bst.remove(10);
        assertTrue(bst.isEmpty(), "Tree should be empty after remove!");
    }

    @Test
    @Order(22)
    public void testStressInsertAndRemove_100Plus() {
        logger.info("=== TEST: STRESS INSERT & REMOVE 100+ ===");
        Random rand = new Random();
        Set<Integer> keys = new TreeSet<>();
        while (keys.size() < 100) {
            keys.add(rand.nextInt(2000));
        }

        long startTime = System.currentTimeMillis();
        for (int key : keys) {
            bst.add(key);
        }
        assertEquals(100, bst.size(), "Size should be 100 after inserts!");
        
        List<Integer> keyList = new ArrayList<>(keys);
        Collections.shuffle(keyList);
        for (int i = 0; i < 50; i++) {
            bst.remove(keyList.get(i));
        }
        long endTime = System.currentTimeMillis();

        assertEquals(50, bst.size(), "Size should be 50 after removing half!");
        assertTrue(bst.height() <= (int)(1.44 * Math.log(50 + 2) / Math.log(2)) - 1,
                   "Height should stay Red-Black balanced!");
        assertTrue(endTime - startTime < 3000, "Took too long: " + (endTime - startTime) + "ms—under 3s!");
        checkRedBlackProperties(bst.getRoot()); // Updated to getRoot()
        logger.info("Stress test: 100 inserts, 50 removes, height: {}", bst.height());
    }
}
