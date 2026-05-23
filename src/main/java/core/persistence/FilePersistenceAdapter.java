package core.persistence;

import core.RedBlackTree;
import core.TreeContext;
import core.TreeNode1;
import core.interfaces.TreePersistenceAdapter;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;
import core.strategy.TreeStrategy;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.*;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

/**
 * Serializes TreeContext snapshots to disk as a simple pre-order text format.
 * No external dependencies — pure Java I/O.
 *
 * File format (each snapshot = one .rbt file):
 *   Line 1: VERSION|TIMESTAMP|STRATEGY|SIZE
 *   Line 2: pre-order node list as: DATA,COLOR;DATA,COLOR;...
 *            NIL nodes encoded as "#"
 */
public class FilePersistenceAdapter implements TreePersistenceAdapter {

    private static final Logger logger   = LogManager.getLogger(FilePersistenceAdapter.class);
    private static final String DIR      = "snapshots";
    private static final String EXT      = ".rbt";
    private static final String VERSION  = "CSRBT-1.0";

    public FilePersistenceAdapter() {
        try {
            Files.createDirectories(Paths.get(DIR));
            logger.debug("Snapshot directory ready: {}", DIR);
        } catch (IOException e) {
            logger.error("Failed to create snapshot directory", e);
        }
    }

    // ── Save ─────────────────────────────────────────────────────────────────

    @Override
    public void saveSnapshot(String name, TreeContext snapshot) {
        Path path = snapshotPath(name);
        try (BufferedWriter writer = Files.newBufferedWriter(path)) {

            // Header
            writer.write(String.join("|",
                    VERSION,
                    Instant.now().toString(),
                    snapshot.getTree().getStrategy().getClass().getSimpleName(),
                    String.valueOf(snapshot.getSize())
            ));
            writer.newLine();

            // Pre-order serialization
            StringBuilder sb = new StringBuilder();
            serializePreOrder(snapshot.getTree().getRoot(), snapshot.getTree().getNIL(), sb);
            writer.write(sb.toString());
            writer.newLine();

            logger.info("Snapshot '{}' saved → {}", name, path);

        } catch (IOException e) {
            logger.error("Failed to save snapshot '{}'", name, e);
        }
    }

    private void serializePreOrder(TreeNode1 node, TreeNode1 nil, StringBuilder sb) {
        if (node == nil) {
            sb.append("#;");
            return;
        }
        sb.append(node.getData())
          .append(",")
          .append(node.getColor().name())
          .append(";");
        serializePreOrder(node.getLeft(),  nil, sb);
        serializePreOrder(node.getRight(), nil, sb);
    }

    // ── Load ─────────────────────────────────────────────────────────────────

    @Override
    public TreeContext loadSnapshot(String name) {
        Path path = snapshotPath(name);
        if (!Files.exists(path)) {
            logger.warn("Snapshot '{}' not found at {}", name, path);
            return null;
        }

        try (BufferedReader reader = Files.newBufferedReader(path)) {
            // Parse header
            String[] header = reader.readLine().split("\\|");
            String strategyName = header[2];
            int size            = Integer.parseInt(header[3]);

            TreeStrategy strategy = resolveStrategy(strategyName);
            TreeContext context   = new TreeContext(strategy);

            // Parse pre-order node list
            String[] tokens = reader.readLine().split(";");
            int[] index     = {0};
            TreeNode1 root  = deserializePreOrder(tokens, index, context.getTree().getNIL());

            context.getTree().setRoot(root);
            if (root != context.getTree().getNIL()) root.setParent(context.getTree().getNIL());

            logger.info("Snapshot '{}' loaded. strategy={} size={}", name, strategyName, size);
            return context;

        } catch (Exception e) {
            logger.error("Failed to load snapshot '{}'", name, e);
            return null;
        }
    }

    private TreeNode1 deserializePreOrder(String[] tokens, int[] index, TreeNode1 nil) {
        if (index[0] >= tokens.length) return nil;

        String token = tokens[index[0]++];
        if (token.equals("#")) return nil;

        String[] parts = token.split(",");
        int      data  = Integer.parseInt(parts[0]);
        TreeNode1.Color color = TreeNode1.Color.valueOf(parts[1]);

        TreeNode1 node = TreeNode1.createNode(data, nil);
        node.setColor(color);

        TreeNode1 left  = deserializePreOrder(tokens, index, nil);
        TreeNode1 right = deserializePreOrder(tokens, index, nil);

        if (left  != nil) { node.setLeft(left);   left.setParent(node);  }
        if (right != nil) { node.setRight(right); right.setParent(node); }

        return node;
    }

    // ── List / Delete ─────────────────────────────────────────────────────────

    @Override
    public List<String> listSnapshots() {
        try {
            List<String> names = new ArrayList<>();
            Files.list(Paths.get(DIR))
                 .filter(p -> p.toString().endsWith(EXT))
                 .forEach(p -> {
                     String filename = p.getFileName().toString();
                     names.add(filename.substring(0, filename.length() - EXT.length()));
                 });
            return names;
        } catch (IOException e) {
            logger.error("Failed to list snapshots", e);
            return Collections.emptyList();
        }
    }

    @Override
    public boolean deleteSnapshot(String name) {
        try {
            return Files.deleteIfExists(snapshotPath(name));
        } catch (IOException e) {
            logger.error("Failed to delete snapshot '{}'", name, e);
            return false;
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private Path snapshotPath(String name) {
        return Paths.get(DIR, name + EXT);
    }

    private TreeStrategy resolveStrategy(String name) {
        switch (name) {
            case "AVLStrategy":   return new AVLStrategy();
            case "SplayStrategy": return new SplayStrategy();
            default:              return new RedBlackStrategy();
        }
    }
}
