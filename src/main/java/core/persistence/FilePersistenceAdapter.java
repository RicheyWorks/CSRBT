package core.persistence;

import core.OrderedSet;
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
 * <p>ADR-002 step 5: the two key-touching points (emit/parse) route through a pluggable
 * {@link KeySerializer}. The {@code TreeContext} entry points below stay {@code int},
 * delegating through {@link KeySerializer#INTEGER} so the on-disk format is byte-identical to
 * the legacy int files; {@link #saveSnapshot(String, OrderedSet, KeySerializer)} and
 * {@link #loadOrderedSet(String, KeySerializer, java.util.Comparator)} persist any key type
 * {@code K} (the interval augmentor stays {@code Integer}, so the generic path records
 * {@code AUGMENTOR=DEFAULT} while per-node tags still round-trip).</p>
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

            // Pre-order serialization (int keys via the built-in Integer serializer)
            StringBuilder sb = new StringBuilder();
            serializePreOrder(snapshot.getTree().getRoot(), snapshot.getTree().getNIL(), sb,
                    KeySerializer.INTEGER);
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
    private <K> void serializePreOrder(TreeNode1<K> node, TreeNode1<K> nil, StringBuilder sb,
                                       KeySerializer<K> ks) {
        Deque<TreeNode1<K>> stack = new ArrayDeque<>();
        stack.push(node);
        while (!stack.isEmpty()) {
            TreeNode1<K> cur = stack.pop();
            if (cur == nil) {
                sb.append("#;");
                continue;
            }
            sb.append(ks.serialize(cur.getData()))
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
            TreeNode1<Integer> root  = deserializePreOrder(tokens, context.getTree().getNIL(),
                    KeySerializer.INTEGER);

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
    private <K> TreeNode1<K> deserializePreOrder(String[] tokens, TreeNode1<K> nil, KeySerializer<K> ks) {
        int[] index = {0};
        TreeNode1<K> root = parseToken(tokens, index, nil, ks);
        if (root == nil) return nil;

        Deque<Frame<K>> stack = new ArrayDeque<>();
        stack.push(new Frame<>(root));

        while (!stack.isEmpty() && index[0] < tokens.length) {
            Frame<K> f = stack.peek();
            TreeNode1<K> child = parseToken(tokens, index, nil, ks);

            if (f.childrenDone == 0) {
                f.childrenDone = 1;
                if (child != nil) {
                    f.node.setLeft(child);
                    child.setParent(f.node);
                    stack.push(new Frame<>(child));
                }
            } else {
                stack.pop();   // this node's children are now both consumed
                if (child != nil) {
                    f.node.setRight(child);
                    child.setParent(f.node);
                    stack.push(new Frame<>(child));
                }
            }
        }
        return root;
    }

    /** Parse one token, advancing {@code index}, returning {@code nil} for "#". */
    private <K> TreeNode1<K> parseToken(String[] tokens, int[] index, TreeNode1<K> nil, KeySerializer<K> ks) {
        if (index[0] >= tokens.length) return nil;
        String token = tokens[index[0]++];
        if (token.equals("#") || token.isEmpty()) return nil;

        // Limit 3 so a tag containing commas is preserved as a single field.
        String[] parts = token.split(",", 3);
        K data = ks.deserialize(parts[0]);
        TreeNode1.Color color = TreeNode1.Color.valueOf(parts[1]);
        TreeNode1<K> node = TreeNode1.createNode(data, nil);
        node.setColor(color);
        // Optional third field: per-node tag. Absent in legacy two-field records.
        if (parts.length >= 3 && !parts[2].isEmpty()) {
            node.setTag(parts[2]);
        }
        return node;
    }

    /** Reconstruction frame: a node plus how many children have been attached. */
    private static final class Frame<K> {
        final TreeNode1<K> node;
        int childrenDone;   // 0 → left pending, 1 → right pending
        Frame(TreeNode1<K> node) { this.node = node; }
    }

    // ── Generic snapshot I/O over any key type K (ADR-002 step 5) ──────────────

    /**
     * Save an {@link OrderedSet} of arbitrary {@code K} keys, rendering each key through
     * {@code keySerializer}. Header and tag handling are identical to the int path; the
     * interval augmentor is {@code Integer}-bound, so the augmentor token is recorded as
     * {@code DEFAULT}. Per-node tags still round-trip — re-apply a custom {@code Augmentor<K>}
     * after load to recompute augmented values from them.
     */
    public <K> void saveSnapshot(String name, OrderedSet<K> set, KeySerializer<K> keySerializer) {
        if (set == null)            throw new IllegalArgumentException("set must not be null");
        if (keySerializer == null)  throw new IllegalArgumentException("keySerializer must not be null");
        Path path = snapshotPath(name);
        RedBlackTree<K> engine = set.getEngine();
        try (BufferedWriter writer = Files.newBufferedWriter(path)) {

            writer.write(String.join("|",
                    VERSION,
                    Instant.now().toString(),
                    engine.getStrategy().getClass().getSimpleName(),
                    String.valueOf(set.size()),
                    "DEFAULT"
            ));
            writer.newLine();

            StringBuilder sb = new StringBuilder();
            serializePreOrder(engine.getRoot(), engine.getNIL(), sb, keySerializer);
            writer.write(sb.toString());
            writer.newLine();

            logger.info("Snapshot '{}' saved (generic, strategy={}) → {}",
                    name, engine.getStrategy().getClass().getSimpleName(), path);

        } catch (IOException e) {
            logger.error("Failed to save snapshot '{}'", name, e);
        }
    }

    /**
     * Load a snapshot into an {@link OrderedSet} of {@code K}, parsing keys with
     * {@code keySerializer} and ordering them by {@code keyOrder}. The comparator is supplied
     * by the caller (comparators are not serialized) and must match the one used when saving.
     * The engine is rebuilt wholesale and the set's size/window are resynced via
     * {@link OrderedSet#resyncFromEngine()}. Returns {@code null} if the file is missing or
     * malformed.
     */
    public <K> OrderedSet<K> loadOrderedSet(String name, KeySeriali