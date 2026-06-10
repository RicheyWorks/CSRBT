package core.util;

import core.TreeContext;
import core.TreeNode1;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

public class TreeDiagnostics {
    private static final Logger logger = LogManager.getLogger(TreeDiagnostics.class);
    private final TreeContext context;

    public TreeDiagnostics(TreeContext context) {
        this.context = context;
    }

    public void emitRelicBeacon() {
        logger.info("📡 Emitting relic beacon from all active nodes");
        Queue<TreeNode1<Integer>> q = new LinkedList<>();
        TreeNode1<Integer> root = context.getTree().getRoot();
        if (!root.isNil()) q.add(root);
        while (!q.isEmpty()) {
            TreeNode1<Integer> node = q.poll();
            logger.info("🔹 Node {}: Color={}, Augment={}, Tag='{}'",
                    node.getData(), node.isRed() ? "Red" : "Black",
                    node.getAugmentedValue(), node.getTag());
            if (!node.getLeft().isNil()) q.add(node.getLeft());
            if (!node.getRight().isNil()) q.add(node.getRight());
        }
    }

    /**
     * Red-Black validity check — <b>RB-strategy introspection only</b> (ADR-010 X1): root
     * blackness, black-height equality, no red-red edges. A tree managed by AVL/Splay/Hybrid
     * legitimately fails these color rules, so this must never gate strategy-agnostic
     * decisions; {@code StrategyHealthCheck.validate} is the per-strategy gate.
     */
    public boolean isValidRedBlack() {
        TreeNode1<Integer> root = context.getTree().getRoot();
        if (root.isNil()) return true;
        if (root.isRed()) {
            logger.error("Root {} is red—violation!", root.getData());
            return false;
        }
        try {
            blackHeight(root);
        } catch (IllegalStateException e) {
            return false;
        }
        return hasNoRedRed();
    }

    public boolean hasNoRedRed() {
        TreeNode1<Integer> root = context.getTree().getRoot();
        if (root.isNil()) return true;
        Stack<TreeNode1<Integer>> stack = new Stack<>();
        stack.push(root);
        while (!stack.isEmpty()) {
            TreeNode1<Integer> current = stack.pop();
            if (current.isRed()) {
                if (!current.getLeft().isNil() && current.getLeft().isRed()) {
                    logger.error("Red-red violation between {} and left child {}",
                            current.getData(), current.getLeft().getData());
                    return false;
                }
                if (!current.getRight().isNil() && current.getRight().isRed()) {
                    logger.error("Red-red violation between {} and right child {}",
                            current.getData(), current.getRight().getData());
                    return false;
                }
            }
            if (!current.getRight().isNil()) stack.push(current.getRight());
            if (!current.getLeft().isNil()) stack.push(current.getLeft());
        }
        return true;
    }

    /**
     * O(log n) localized red-red check around a single key. An insertion can
     * only introduce a red-red violation at the inserted (RED) node relative to
     * its parent or its children, so this is sufficient to detect insert-induced
     * stress without the O(n) whole-tree {@link #hasNoRedRed()} scan.
     *
     * @return {@code true} if there is NO red-red violation at {@code value}'s node
     */
    public boolean hasNoRedRedAt(int value) {
        TreeNode1<Integer> node = findNode(value);
        if (node.isNil() || !node.isRed()) return true;   // absent or black → no local violation

        TreeNode1<Integer> parent = node.getParent();
        if (parent != null && !parent.isNil() && parent.isRed()) return false;
        if (!node.getLeft().isNil()  && node.getLeft().isRed())  return false;
        if (!node.getRight().isNil() && node.getRight().isRed()) return false;
        return true;
    }

    private TreeNode1<Integer> findNode(int value) {
        TreeNode1<Integer> x = context.getTree().getRoot();
        while (!x.isNil()) {
            if (x.compareKeyTo(value) == 0) return x;
            x = (x.compareKeyTo(value) > 0) ? x.getLeft() : x.getRight();
        }
        return context.getTree().getNIL();
    }

    private int blackHeight(TreeNode1<Integer> node) {
        if (node.isNil()) return 0;   // per-tree sentinel: compare via identity-aware isNil()
        int leftHeight = blackHeight(node.getLeft());
        int rightHeight = blackHeight(node.getRight());
        if (leftHeight != rightHeight) {
            throw new IllegalStateException("Black height mismatch at " + node.getData());
        }
        return leftHeight + (node.isRed() ? 0 : 1);
    }

    public List<Integer> inOrderTraversal() {
        List<Integer> result = new ArrayList<>();
        Stack<TreeNode1<Integer>> stack = new Stack<>();
        TreeNode1<Integer> current = context.getTree().getRoot();
        while (!stack.isEmpty() || !current.isNil()) {
            while (!current.isNil()) {
                stack.push(current);
                current = current.getLeft();
            }
            current = stack.pop();
            result.add(current.getData());
            current = current.getRight();
        }
        return result;
    }

    public String toJson() {
        // Simplified: Implement JSON serialization
        return "{}";
    }
}
