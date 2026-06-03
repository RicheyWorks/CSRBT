package core.persistence;

import core.RedBlackTree;
import core.TreeContext;
import core.TreeNode1;
import core.augment.IntervalAugmentor;
import core.interfaces.TreePersistenceAdapter;
import core.strategy.AVLStrategy;
import core.strategy.HybridStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;
import core.strategy.TreeStrategy;
import core.util.TreeDiagnostics;
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
 *   Line 1: VERSION|TIMESTAMP|STRATEGY|SIZE|AUGMENTOR
 *           (AUGMENTOR is optional/absent in legacy files: DEFAULT | INTERVAL)
 *   Line 2: pre-order node list as: DATA,COLOR[,TAG];DATA,COLOR[,TAG];...
 *            NIL nodes encoded as "#"
 *
 * ADR-002 step 2: the text format is {@code int}-keyed (keys parsed via
 * {@link Integer#parseInt}); this adapter is pinned to {@code TreeNode1<Integer>}.
 * A pluggable key (de)serializer for arbitrary {@code K} is step 5.
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

            // Header: VERSION|TIMESTAMP|STRATEGY|SIZE|AUGMENTOR
            writer.write(String.join("|",
                    VERSION,
                    Instant.now().toString(),
                    snapshot.getTree().getStrategy().getClass().getSimpleName(),
                    String.valueOf(snapshot.getSize()),
                    augmentorToken(snapshot)
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

    /**
     * Iterative pre-order serialization. Explicit stack rather than recursion so
     * a deep/degenerate tree (e.g. a skewed splay tree) cannot overflow the call
     * stack. Right child is pushed before left so left is emitted first, matching
     * the recursive pre-order order the reader expects.
     */
    private void serializePreOrder(TreeNode1<Integer> node, TreeNode1<Integer> nil, StringBuilder sb) {
        Deque<TreeNode1<Integer>> stack = new ArrayDeque<>();
        stack.push(node);
        while (!stack.isEmpty()) {
            TreeNode1<Integer> cur = stack.pop();
            if (cur == nil) {
                sb.append("#;");
                continue;
            }
            sb.append(cur.getData())
              .append(",")
              .append(cur.getColor().name());
            // Optional third field: per-node tag (e.g. interval high endpoint).
            // Commas inside a tag are fine (the reader splits with limit 3); a
            // tag containing the ';' node separator can't be encoded in this flat
            // format, so it is dropped with a warning rather than corrupting the
            // stream. Empty tags are omitted entirely (backward compatible: old
            // two-field records still parse).
            String tag = cur.getTag();
            if (tag != null && !tag.isEmpty()) {
                if (tag.indexOf(';') >= 0) {
                    logger.warn("Tag on node {} contains ';' and cannot be persisted — dropping it.",
                            cur.getData());
                } else {
                    sb.append(",").append(tag);
                }
            }
            sb.append(";");
            stack.push(cur.getRight());
            stack.push(cur.getLeft());
        }
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
            // ── Header line: VERSION|TIMESTAMP|STRATEGY|SIZE ──────────────────
            String headerLine = reader.readLine();
            if (headerLine == null) {
                logger.warn("Snapshot '{}' is empty — no header line.", name);
                return null;
            }
            String[] header = headerLine.split("\\|");
            if (header.length < 4) {
                logger.warn("Snapshot '{}' has a malformed header ({} fields, need 4): {}",
                        name, header.length, headerLine);
                return null;
            }
            String version      = header[0];
            String strategyName = header[2];
            if (!VERSION.equals(version)) {
                logger.warn("Snapshot '{}' version mismatch (file='{}', expected='{}') — attempting load anyway.",
                        name, version, VERSION);
            }
            int declaredSize;
            try {
                declaredSize = Integer.parseInt(header[3].trim());
            } catch (NumberFormatException e) {
                logger.warn("Snapshot '{}' has a non-numeric size field: '{}'", name, header[3]);
                return null;
            }

            TreeStrategy<Integer> strategy = resolveStrategy(strategyName);
            TreeContext  context  = new TreeContext(strategy);

            // ── Data line: pre-order node list ───────────────────────────────
            String dataLine = reader.readLine();
            if (dataLine == null) {
                logger.warn("Snapshot '{}' has a header but no node data line.", name);
                return null;
            }
            String[] tokens = dataLine.split(";");
            TreeNode1<Integer> root  = deserializePreOrder(tokens, context.getTree().getNIL());

            context.getTree().setRoot(root);
            if (root != context.getTree().getNIL()) root.setParent(context.getTree().getNIL());

            // Restore the facade's size (previously left at 0 — a latent bug) and
            // verify it against the header, which is advisory only.
            int actualSize = new TreeDiagnostics(context).inOrderTraversal().size();
            if (actualSize != declaredSize) {
                logger.warn("Snapshot '{}' size mismatch: header={}, parsed={} — using parsed.",
                        name, declaredSize, actualSize);
            }
            context.forceSizeInternal(actualSize);

            // Restore the augmentor identity (5th header field, absent in legacy
            // files). Re-applying it recomputes augmented values from the restored
            // tags, so an interval tree round-trips without a manual setAugmentor.
            if (header.length >= 5 && "INTERVAL".equals(header[4].trim())) {
                context.setAugmentor(IntervalAugmentor.INSTANCE);
            }

            logger.info("Snapshot '{}' loaded. strategy={} size={}", name, strategyName, actualSize);
            return context;

        } catch (Exception e) {
            logger.error("Failed to load snapshot '{}'", name, e);
            return null;
        }
    }

    /**
     * Iterative pre-order reconstruction (explicit stack, no recursion) so a
     * deep/degenerate snapshot cannot overflow the call stack. Each stack frame
     * tracks how many of its node's two children have been attached; the next
     * token fills the left child first, then the right.
     */
    private TreeNode1<Integer> deserializePreOrder(String[] tokens, TreeNode1<Integer> nil) {
        int[] index = {0};
        TreeNode1<Integer> root = parseToken(tokens, index, nil);
        if (root == nil) return nil;

        Deque<Frame> stack = new ArrayDeque<>();
        stack.push(new Frame(root));

        while (!stack.isEmpty() && index[0] < tokens.length) {
            Frame f = stack.peek();
            TreeNode1<Integer> child = parseToken(tokens, index, nil);

            if (f.childrenDone == 0) {
                f.childrenDone = 1;
                if (child != nil) {
                    f.node.setLeft(child);
                    child.setParent(f.node);
                    stack.push(new Frame(child));
                }
            } else {
                stack.pop();   // this node's children are now both consumed
                if (child != nil) {
                    f.node.setRight(child);
                    child.setParent(f.node);
                    stack.push(new Frame(child));
                }
            }
        }
        return root;
    }

    /** Parse one token, advancing {@code index}, returning {@code nil} for "#". */
    private TreeNode1<Integer> parseToken(String[] tokens, int[] index, TreeNode1<Integer> nil) {
        if (index[0] >= tokens.length) return nil;
        String token = tokens[index[0]++];
        if (token.equals("#") || token.isEmpty()) return nil;

        // Limit 3 so a tag containing commas is preserved as a single field.
        String[] parts = token.split(",", 3);
        int data = Integer.parseInt(parts[0]);
        TreeNode1.Color color = TreeNode1.Color.valueOf(parts[1]);
        TreeNode1<Integer> node = TreeNode1.createNode(data, nil);
        node.setColor(color);
        // Optional third field: per-node tag. Absent in legacy two-field records.
        if (parts.length >= 3 && !parts[2].isEmpty()) {
            node.setTag(parts[2]);
        }
        return node;
    }

    /** Reconstruction frame: a node plus how many children have been attached. */
    private static final class Frame {
        final TreeNode1<Integer> node;
        int childrenDone;   // 0 → left pending, 1 → right pending
        Frame(TreeNode1<Integer> node) { this.node = node; }
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
        if (name == null || name.isEmpty()) {
            throw new IllegalArgumentException("Snapshot name must be non-empty");
        }
        // Prevent path traversal: the resolved file must stay directly inside DIR.
        // Reject separators and parent references outright, then verify the
        // normalized path's parent is exactly the snapshots directory.
        if (name.contains("/") || name.contains("\\") || name.contains("..")) {
            throw new IllegalArgumentException("Illegal snapshot name: " + name);
        }
        Path base     = Paths.get(DIR).toAbsolutePath().normalize();
        Path resolved = base.resolve(name + EXT).normalize();
        if (!resolved.getParent().equals(base)) {
            throw new IllegalArgumentException("Snapshot name escapes snapshot directory: " + name);
        }
        return resolved;
    }

    /**
     * Persistable token for the context's augmentor. Only the two built-in
     * augmentors are recognized; any custom lambda is recorded as DEFAULT (its
     * augmented values are still rebuilt from structure on load).
     */
    private String augmentorToken(TreeContext ctx) {
        return ctx.getAugmentor() == IntervalAugmentor.INSTANCE ? "INTERVAL" : "DEFAULT";
    }

    private TreeStrategy<Integer> resolveStrategy(String name) {
        switch (name) {
            case "AVLStrategy":    return new AVLStrategy<>();
            case "SplayStrategy":  return new SplayStrategy<>();
            case "HybridStrategy": return new HybridStrategy<>();
            default:               return new RedBlackStrategy<>();
        }
    }
}
