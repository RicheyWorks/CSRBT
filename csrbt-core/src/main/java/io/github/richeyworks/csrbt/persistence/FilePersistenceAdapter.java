package io.github.richeyworks.csrbt.persistence;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.PersistentRankedSet;
import io.github.richeyworks.csrbt.PersistentTreeEngine;
import io.github.richeyworks.csrbt.RedBlackTree;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.augment.IntervalAugmentor;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.interfaces.RankedSet;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
import io.github.richeyworks.csrbt.util.TreeDiagnostics;
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
    public <K> OrderedSet<K> loadOrderedSet(String name, KeySerializer<K> keySerializer,
                                            Comparator<? super K> keyOrder) {
        if (keySerializer == null) throw new IllegalArgumentException("keySerializer must not be null");
        if (keyOrder == null)      throw new IllegalArgumentException("keyOrder must not be null");
        Path path = snapshotPath(name);
        if (!Files.exists(path)) {
            logger.warn("Snapshot '{}' not found at {}", name, path);
            return null;
        }

        try (BufferedReader reader = Files.newBufferedReader(path)) {
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

            TreeStrategy<K> strategy = resolveStrategy(strategyName);
            OrderedSet<K>   set      = new OrderedSet<>(strategy, keyOrder);
            RedBlackTree<K> engine   = set.getEngine();

            String dataLine = reader.readLine();
            if (dataLine == null) {
                logger.warn("Snapshot '{}' has a header but no node data line.", name);
                return null;
            }
            String[] tokens = dataLine.split(";");
            TreeNode1<K> root = deserializePreOrder(tokens, engine.getNIL(), keySerializer);

            engine.setRoot(root);
            if (root != engine.getNIL()) root.setParent(engine.getNIL());
            set.resyncFromEngine();   // recompute size + FIFO window from the rebuilt engine

            int actualSize = set.size();
            if (actualSize != declaredSize) {
                logger.warn("Snapshot '{}' size mismatch: header={}, parsed={} — using parsed.",
                        name, declaredSize, actualSize);
            }

            logger.info("Snapshot '{}' loaded (generic). strategy={} size={}", name, strategyName, actualSize);
            return set;

        } catch (Exception e) {
            logger.error("Failed to load snapshot '{}'", name, e);
            return null;
        }
    }

    /** Natural-order convenience overload for {@link Comparable} keys. */
    public <K extends Comparable<? super K>> OrderedSet<K> loadOrderedSet(String name,
                                                                          KeySerializer<K> keySerializer) {
        return loadOrderedSet(name, keySerializer, Comparator.<K>naturalOrder());
    }

    // ── Persistent-engine snapshot I/O (ADR-005 P3) ─────────────────────────────

    /** Header strategy token marking the flat ascending-key format below. */
    private static final String PERSISTENT_LABEL = "PersistentTreeEngine";

    /**
     * Save a {@link PersistentTreeEngine.Snapshot} — an O(1) frozen version of the set — as a
     * flat ascending key list (same header line as every other snapshot, strategy token
     * {@value #PERSISTENT_LABEL}; the data line is {@code k1;k2;...}). No colors or structure:
     * the engine is weight-balanced, so an ascending replay on load rebuilds an equivalent tree.
     * A key whose serialized form contains {@code ';'} cannot be encoded and fails loudly
     * (unlike tags, silently dropping a <em>key</em> would corrupt the set).
     */
    public <K> void saveSnapshot(String name, PersistentTreeEngine.Snapshot<K> snapshot,
                                 KeySerializer<K> keySerializer) {
        if (snapshot == null)      throw new IllegalArgumentException("snapshot must not be null");
        if (keySerializer == null) throw new IllegalArgumentException("keySerializer must not be null");
        Path path = snapshotPath(name);
        try (BufferedWriter writer = Files.newBufferedWriter(path)) {
            writer.write(String.join("|",
                    VERSION,
                    Instant.now().toString(),
                    PERSISTENT_LABEL,
                    String.valueOf(snapshot.size()),
                    "DEFAULT"
            ));
            writer.newLine();

            StringBuilder sb = new StringBuilder();
            for (K k : snapshot.inOrder()) {
                String token = keySerializer.serialize(k);
                if (token.indexOf(';') >= 0) {
                    throw new IllegalArgumentException(
                            "key serializes to a token containing ';' and cannot be persisted: " + token);
                }
                sb.append(token).append(';');
            }
            writer.write(sb.toString());
            writer.newLine();
            logger.info("Snapshot '{}' saved (persistent, n={}) → {}", name, snapshot.size(), path);
        } catch (IOException e) {
            logger.error("Failed to save snapshot '{}'", name, e);
        }
    }

    /**
     * Load a {@value #PERSISTENT_LABEL} snapshot into a fresh weight-balanced
     * {@link PersistentTreeEngine}, replaying the stored ascending keys (O(n log n), balanced by
     * construction). The comparator is supplied by the caller — comparators are not serialized —
     * and must match the one used when saving. Returns {@code null} if the file is missing,
     * malformed, or not a persistent snapshot.
     */
    public <K> PersistentTreeEngine<K> loadPersistent(String name, KeySerializer<K> keySerializer,
                                                      Comparator<? super K> keyOrder) {
        if (keySerializer == null) throw new IllegalArgumentException("keySerializer must not be null");
        if (keyOrder == null)      throw new IllegalArgumentException("keyOrder must not be null");
        List<K> keys = readFlatKeys(name, keySerializer);
        if (keys == null) return null;
        PersistentTreeEngine<K> engine = new PersistentTreeEngine<>(keyOrder);
        for (K k : keys) engine.add(k);
        logger.info("Snapshot '{}' loaded (persistent). size={}", name, engine.size());
        return engine;
    }

    /** Natural-order convenience overload for {@link Comparable} keys. */
    public <K extends Comparable<? super K>> PersistentTreeEngine<K> loadPersistent(
            String name, KeySerializer<K> keySerializer) {
        return loadPersistent(name, keySerializer, Comparator.<K>naturalOrder());
    }

    /** Parse a flat persistent snapshot's keys, or {@code null} if missing/malformed/wrong format. */
    private <K> List<K> readFlatKeys(String name, KeySerializer<K> ks) {
        Path path = snapshotPath(name);
        if (!Files.exists(path)) {
            logger.warn("Snapshot '{}' not found at {}", name, path);
            return null;
        }
        try (BufferedReader reader = Files.newBufferedReader(path)) {
            String headerLine = reader.readLine();
            if (headerLine == null) {
                logger.warn("Snapshot '{}' is empty — no header line.", name);
                return null;
            }
            String[] header = headerLine.split("\\|");
            if (header.length < 4 || !PERSISTENT_LABEL.equals(header[2])) {
                logger.warn("Snapshot '{}' is not a persistent snapshot (strategy='{}').",
                        name, header.length >= 3 ? header[2] : "?");
                return null;
            }
            if (!VERSION.equals(header[0])) {
                logger.warn("Snapshot '{}' version mismatch (file='{}', expected='{}') — attempting load anyway.",
                        name, header[0], VERSION);
            }
            String dataLine = reader.readLine();
            if (dataLine == null) {
                logger.warn("Snapshot '{}' has a header but no key data line.", name);
                return null;
            }
            List<K> keys = new ArrayList<>();
            for (String token : dataLine.split(";")) {
                if (!token.isEmpty()) keys.add(ks.deserialize(token));
            }
            return keys;
        } catch (Exception e) {
            logger.error("Failed to load snapshot '{}'", name, e);
            return null;
        }
    }

    /** The strategy token in a snapshot's header, or {@code null} if unreadable. */
    private String snapshotStrategy(String name) {
        Path path = snapshotPath(name);
        if (!Files.exists(path)) return null;
        try (BufferedReader reader = Files.newBufferedReader(path)) {
            String headerLine = reader.readLine();
            if (headerLine == null) return null;
            String[] header = headerLine.split("\\|");
            return header.length >= 3 ? header[2] : null;
        } catch (IOException e) {
            return null;
        }
    }

    // ── Ensemble snapshot I/O (ADR-003 E6) ──────────────────────────────────────

    /**
     * Save an {@link EnsembleOrderedSet} by snapshotting its <em>primary</em> — the primary is the
     * logical set (every ACTIVE mirror is an exact copy of it, and in SAMPLED_SHADOW it is the one
     * exact copy), so persisting K member trees would store the same keys K times. A strategy-backed
     * primary writes the {@link #saveSnapshot(String, OrderedSet, KeySerializer)} pre-order format;
     * a persistent-engine primary (ADR-005 P3) writes the flat ascending-key format. Either way the
     * recorded strategy token is informational on the ensemble path (member strategies are runtime
     * configuration, like the comparator), and {@link #loadEnsemble} reads both.
     */
    public <K> void saveSnapshot(String name, EnsembleOrderedSet<K> ensemble, KeySerializer<K> keySerializer) {
        if (ensemble == null) throw new IllegalArgumentException("ensemble must not be null");
        RankedSet<K> primarySet = ensemble.primary().set();
        if (primarySet instanceof OrderedSet<K> os) {
            saveSnapshot(name, os, keySerializer);
        } else if (primarySet instanceof PersistentRankedSet<K> prs) {
            saveSnapshot(name, prs.engine().snapshot(), keySerializer);
        } else {
            throw new IllegalArgumentException(
                    "no persistence path for primary backing " + primarySet.getClass().getSimpleName());
        }
    }

    /**
     * Load a snapshot into {@code target}, rebuilding every member (ADR-003 E6): the target is
     * cleared and the snapshot's keys are replayed through the ensemble facade, so the usual write
     * path applies — in MIRROR/VERIFIED every ACTIVE member becomes an exact copy; in
     * SAMPLED_SHADOW the primary takes every key and shadows sample their stride, exactly as if
     * the keys had arrived live. The caller supplies the built ensemble (member strategies, mode,
     * comparator, and executor are runtime configuration and are not serialized); its comparator
     * must match the one used when saving.
     *
     * @return {@code true} if the snapshot was found and replayed; {@code false} if missing or
     *         malformed (the target is left untouched in that case)
     */
    public <K> boolean loadEnsemble(String name, KeySerializer<K> keySerializer, EnsembleOrderedSet<K> target) {
        if (target == null) throw new IllegalArgumentException("target must not be null");
        List<K> keys;
        if (PERSISTENT_LABEL.equals(snapshotStrategy(name))) {
            keys = readFlatKeys(name, keySerializer);              // ADR-005 P3 flat format
        } else {
            OrderedSet<K> loaded = loadOrderedSet(name, keySerializer, target.comparator());
            keys = loaded == null ? null : loaded.inOrder();
        }
        if (keys == null) return false;
        target.clear();
        for (K k : keys) target.add(k);
        logger.info("Snapshot '{}' replayed into ensemble ({} members, n={}).",
                name, target.members().size(), target.size());
        return true;
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

    private <K> TreeStrategy<K> resolveStrategy(String name) {
        switch (name) {
            case "AVLStrategy":    return new AVLStrategy<>();
            case "SplayStrategy":  return new SplayStrategy<>();
            case "HybridStrategy": return new HybridStrategy<>();
            default:               return new RedBlackStrategy<>();
        }
    }
}
