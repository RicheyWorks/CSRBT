package experimental;

import core.TreeContext;
import core.TreeNode1;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.Random;
import java.util.Stack;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class TreeAgent {
    private static final Logger logger = LogManager.getLogger(TreeAgent.class);
    private final TreeContext context;

    public TreeAgent(TreeContext context) {
        this.context = context;
    }

    public void alienSeed(int seedValue, int maxDepth, int variance) {
        logger.info("🚀 Initiating alien seed protocol: seed={}, depth={}, var={}", seedValue, maxDepth, variance);
        context.clear();
        Random rng = new Random();
        TreeNode1 nil = context.getTree().getNIL();
        TreeNode1 seed = TreeNode1.createNode(seedValue, nil);
        context.getTree().setRoot(seed);
        context.forceSizeInternal(1);
        alienSpawnIterative(seed, 1, maxDepth, variance, rng);
        context.forceSizeInternal(sizeIterative());
        autoTag();
    }

    private void alienSpawnIterative(TreeNode1 node, int startDepth, int maxDepth, int variance, Random rng) {
        if (startDepth >= maxDepth) return;
        Stack<TreeNode1> stack = new Stack<>();
        Stack<Integer> depthStack = new Stack<>();
        stack.push(node);
        depthStack.push(startDepth);
        while (!stack.isEmpty()) {
            TreeNode1 current = stack.pop();
            int depth = depthStack.pop();
            if (depth >= maxDepth) continue;
            int leftData = current.getData() - rng.nextInt(variance + 1);
            int rightData = current.getData() + rng.nextInt(variance + 1);
            TreeNode1 nil = context.getTree().getNIL();
            TreeNode1 leftChild = TreeNode1.createNode(leftData, nil);
            TreeNode1 rightChild = TreeNode1.createNode(rightData, nil);
            current.safeSetLeft(leftChild);
            current.safeSetRight(rightChild);
            leftChild.setParent(current);
            rightChild.setParent(current);
            leftChild.setColor(rng.nextBoolean() ? TreeNode1.Color.RED : TreeNode1.Color.BLACK);
            rightChild.setColor(rng.nextBoolean() ? TreeNode1.Color.RED : TreeNode1.Color.BLACK);
            stack.push(rightChild);
            stack.push(leftChild);
            depthStack.push(depth + 1);
            depthStack.push(depth + 1);
        }
    }

    public void runAgentSwarm() {
        ExecutorService pool = Executors.newFixedThreadPool(8);
        TreeNode1 root = context.getTree().getRoot();
        if (!root.isNil()) {
            Stack<TreeNode1> stack = new Stack<>();
            stack.push(root);
            while (!stack.isEmpty()) {
                TreeNode1 current = stack.pop();
                pool.submit(() -> {
                    String role = current.isLeaf() ? "Scout" : (current.getTag() != null ? current.getTag() : "Node");
                    logger.info("🤖 Agent [{}] reports from Node {} (Color: {}, Rot: {})",
                            role, current.getData(), current.isRed() ? "Red" : "Black", current.getLastRotation());
                });
                if (!current.getRight().isNil()) stack.push(current.getRight());
                if (!current.getLeft().isNil()) stack.push(current.getLeft());
            }
        }
        pool.shutdown();
    }

    public void autoTag() {
        TreeNode1 root = context.getTree().getRoot();
        if (!root.isNil()) {
            Stack<TreeNode1> stack = new Stack<>();
            stack.push(root);
            while (!stack.isEmpty()) {
                TreeNode1 current = stack.pop();
                if (current.isLeaf()) {
                    current.setTag("leaf");
                } else if (current.getLeft().isNil() && !current.getRight().isNil()) {
                    current.setTag("right-heavy");
                } else if (!current.getLeft().isNil() && current.getRight().isNil()) {
                    current.setTag("left-heavy");
                } else {
                    current.setTag("balanced");
                }
                if (!current.getRight().isNil()) stack.push(current.getRight());
                if (!current.getLeft().isNil()) stack.push(current.getLeft());
            }
        }
    }

    private int sizeIterative() {
        TreeNode1 root = context.getTree().getRoot();
        if (root.isNil()) return 0;
        int size = 0;
        Stack<TreeNode1> stack = new Stack<>();
        stack.push(root);
        while (!stack.isEmpty()) {
            TreeNode1 current = stack.pop();
            size++;
            if (!current.getRight().isNil()) stack.push(current.getRight());
            if (!current.getLeft().isNil()) stack.push(current.getLeft());
        }
        return size;
    }
}
