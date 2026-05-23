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
        Queue<TreeNode1> q = new LinkedList<>();
        TreeNode1 root = context.getTree().getRoot();
        if (!root.isNil()) q.add(root);
        while (!q.isEmpty()) {
            TreeNode1 node = q.poll();
            logger.info("🔹 Node {}: Color={}, Augment={}, Tag='{}'",
                    node.getData(), node.isRed() ? "Red" : "Black",
                    node.getAugmentedValue(), node.getTag());
            if (!node.getLeft().isNil()) q.add(node.getLeft());
            if (!node.getRight().isNil()) q.add(node.getRight());
        }
    }

    public boolean isValidRedBlack() {
        TreeNode1 root = context.getTree().getRoot();
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
        TreeNode1 root = context.getTree().getRoot();
        if (root.isNil()) return true;
        Stack<TreeNode1> stack = new Stack<>();
        stack.push(root);
        while (!stack.isEmpty()) {
            TreeNode1 current = stack.pop();
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

    private int blackHeight(TreeNode1 node) {
        if (node == TreeNode1.NIL) return 0;
        int leftHeight = blackHeight(node.getLeft());
        int rightHeight = blackHeight(node.getRight());
        if (leftHeight != rightHeight) {
            throw new IllegalStateException("Black height mismatch at " + node.getData());
        }
        return leftHeight + (node.isRed() ? 0 : 1);
    }

    public List<Integer> inOrderTraversal() {
        List<Integer> result = new ArrayList<>();
        Stack<TreeNode1> stack = new Stack<>();
        TreeNode1 current = context.getTree().getRoot();
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
