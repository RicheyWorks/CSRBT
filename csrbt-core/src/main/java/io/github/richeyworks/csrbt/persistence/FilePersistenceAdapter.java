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
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.DeleteResult;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.LoadResult;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.LoadStatus;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.SaveResult;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.SaveStatus;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
import io.github.richeyworks.csrbt.strategy.WeightBalancedStrategy;
import io.github.richeyworks.csrbt.util.StrategyHealthCheck;
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
 *
 * <p><b>ADR-025:</b> every {@code saveSnapshot} shape has a {@code trySaveSnapshot} twin that
 * returns a {@link SaveResult} instead of only logging. The {@code void} shapes are unchanged and
 * now delegate to the reporting ones, discarding the answer — so a full disk, a revoked
 * permission, an I/O error mid-write, and a commit rename that cannot publish are all detectable
 * without changing a single existing call site.</p>
 *
 * <p><b>ADR-026:</b> the read side has the same twins. Every load shape returns a
 * {@link LoadResult} that separates the nine reasons a load used to answer {@code null} into the
 * four a caller acts on — {@link LoadStatus#ABSENT} (start fresh), {@link LoadStatus#MALFORMED}
 * (the file is there and unusable; do not start fresh and do not overwrite it),
 * {@link LoadStatus#FAILED} (an {@code IOException}; retry or fail over), and
 * {@link LoadStatus#LOADED}. The published {@code null} / {@code false} / empty-list returns are
 * unchanged and now delegate to the reporting twins.</p>
 *
 * <p><b>ADR-026 amendment (2026-08-18):</b> {@link #tryDeleteSnapshot} finishes the set.
 * {@link #deleteSnapshot} answered {@code false} both for "there was nothing to delete" and for
 * "the delete failed and the file is still there"; the twin separates them, and
 * {@link DeleteResult#gone()} is the one-liner for the caller — a retention sweep, a
 * delete-before-re-save — that only wants to know the name is free.</p>
 *
 * <p>The same amendment closes ADR-025's held {@code fsync} item as an <em>option</em>:
 * {@link #FilePersistenceAdapter(boolean)} forces each committed snapshot and its directory entry
 * to stable storage, so a caller who needs {@link SaveStatus#SAVED} to mean "survives a power cut"
 * rather than "the filesystem has it" can pay the measured ~0.4–0.6 ms per save for it. The
 * default is unchanged and free.</p>
 */
public class FilePersistenceAdapter implements TreePersistenceAdapter {

    private static final Logger logger   = LogManager.getLogger(FilePersistenceAdapter.class);
    private static final String DIR      = "snapshots";
    private static final String EXT      = ".rbt";
    private static final String VERSION  = "CSRBT-1.0";

    /**
     * Whether a committed save is forced to stable storage before it reports {@link SaveResult}.
     * Off by default: see {@link #FilePersistenceAdapter(boolean)} for what it costs and buys.
     */
    private final boolean fsyncOnCommit;

    /**
     * Prepare the snapshot directory. A failure here is logged and the adapter is still
     * constructed — deliberately, so that a snapshot directory which becomes writable later (a
     * mount that has not come up yet) does not make the adapter unusable for the life of the
     * process. It does mean every save until then fails; since ADR-025 the caller can see that,
     * as a {@code FAILED} {@link SaveResult} carrying the {@code NoSuchFileException}, instead of
     * having to read the log.
     *
     * <p>Equivalent to {@code new FilePersistenceAdapter(false)}: saves are published with an
     * atomic rename and <em>not</em> forced to stable storage, which is what every save has done
     * since 0.1.0.</p>
     */
    public FilePersistenceAdapter() {
        this(false);
    }

    /**
     * As {@link #FilePersistenceAdapter()}, choosing what {@link SaveStatus#SAVED} is allowed to
     * mean (ADR-026 amendment, 2026-08-18 — ADR-025's held {@code fsync} item).
     *
     * <p><b>{@code false} (the default, and the pre-0.2.1 behavior).</b> A save stages to a
     * sibling file and publishes it with an atomic rename. That is enough to survive a process
     * crash, a thrown exception, a killed JVM: the target is always either the complete new
     * snapshot or the complete previous one. It is <em>not</em> enough to survive a power cut or a
     * kernel panic, because neither the staging file's contents nor the renamed directory entry
     * has been forced out of the page cache. {@code SAVED} here means <b>the filesystem has
     * it</b>.</p>
     *
     * <p><b>{@code true}.</b> The staged file is forced with {@code FileChannel.force} before the
     * commit rename, and the snapshot directory is forced after it, so the publish itself is
     * durable and not just the bytes. {@code SAVED} here means <b>it survives a power cut</b>.</p>
     *
     * <p><b>What it costs</b>, measured on this repo's own save path (ext4 on a virtio disk, 200
     * saves per configuration after warm-up): a 100-key snapshot goes from 0.16–0.27 ms to
     * 0.53–0.59 ms per save, and a 10,000-key snapshot from 0.30–0.32 ms to 0.83–0.98 ms — about
     * +0.4 ms and +0.6 ms, a 2–3× multiple on the whole save. The surcharge is roughly constant in
     * the payload, because it is two device flushes rather than proportional work; on rotating or
     * networked storage a flush is milliseconds, so the multiple grows rather than shrinks. That
     * is why this is a choice and not a default: making every existing caller pay it silently is
     * the kind of uncompiled behavior change ADR-025 refused when it declined to throw from
     * {@code saveSnapshot}.</p>
     *
     * <p><b>One honest limit.</b> If the directory force itself fails — a platform that will not
     * open a directory for reading, notably Windows — the save still reports {@link
     * SaveStatus#SAVED} and the failure is logged at DEBUG. The file's own contents are on stable
     * storage and the rename has been published by then; reporting {@code FAILED} would claim
     * "nothing was written", which is the one thing that is certainly untrue. On such a platform
     * {@code SAVED} is back to meaning what it means with the flag off.</p>
     *
     * @param fsyncOnCommit force each committed snapshot, and the directory entry publishing it,
     *                      to stable storage before reporting success
     */
    public FilePersistenceAdapter(boolean fsyncOnCommit) {
        this.fsyncOnCommit = fsyncOnCommit;
        try {
            Files.createDirectories(Paths.get(DIR));
            logger.debug("Snapshot directory ready: {} (fsyncOnCommit={})", DIR, fsyncOnCommit);
        } catch (IOException e) {
            logger.error("Failed to create snapshot directory", e);
        }
    }

    /**
     * Whether this adapter forces committed snapshots to stable storage — i.e. whether
     * {@link SaveStatus#SAVED} means "it survives a power cut" or "the filesystem has it".
     */
    public boolean isFsyncOnCommit() { return fsyncOnCommit; }

    // ── Save ─────────────────────────────────────────────────────────────────

    /** Distinguishes this JVM's staging files from any other process writing the same directory. */
    private static final long PID = ProcessHandle.current().pid();

    /** Distinguishes concurrent saves inside this JVM (see {@link #tempPathFor}). */
    private static final java.util.concurrent.atomic.AtomicLong TMP_SEQ =
            new java.util.concurrent.atomic.AtomicLong();

    /**
     * D-3 (consolidation 2026-08-12): every save writes a sibling {@code .tmp} file and
     * commits with an atomic rename, so a failed save (I/O error, unencodable key) can
     * never truncate or half-write the target — the previous snapshot, if any, survives
     * intact. Before this, {@code Files.newBufferedWriter(path)} truncated the target at
     * OPEN, so a save that later failed had already destroyed the prior good file.
     *
     * <p>The staging name is unique <em>per save call</em>: {@code <name>.rbt.<pid>.<seq>.tmp}
     * (audit 2026-08-17, finding 5). It used to be derived from the target name alone, so two
     * saves of the same snapshot name — two threads, or two JVMs sharing the directory —
     * opened, truncated and wrote the <em>same</em> staging file, and one {@code commitAtomically}
     * renamed a file the other was still writing: 4 of 25 measured rounds committed a target
     * that {@code loadOrderedSet} then refused, destroying the previously-good snapshot. A
     * per-name lock would only have covered one JVM; a unique name covers both cases.</p>
     *
     * <p>What this now guarantees: each save's bytes are written to a file only that call
     * touches, and the rename publishes them in one step. Concurrent saves of one name still
     * race to <em>commit</em> — the target ends up as one of the snapshots, whichever renamed
     * last — but it is always exactly one complete, loadable snapshot, never a blend.</p>
     */
    private static Path tempPathFor(Path target) {
        return target.resolveSibling(target.getFileName()
                + "." + PID + "." + TMP_SEQ.incrementAndGet() + ".tmp");
    }

    /**
     * Force the directory entry the commit rename just created (ADR-026 amendment). Without this
     * the file's contents are durable but the name pointing at them may not be, which after a
     * power cut can leave the previous snapshot — or nothing — under the name that reported
     * {@link SaveStatus#SAVED}.
     *
     * <p>A failure here is logged at DEBUG and swallowed <em>on purpose</em>. By the time it is
     * called the rename has already published the snapshot, so the two things a
     * {@link SaveResult#failed} promises — nothing was published, the previous snapshot is intact
     * — are both false. Platforms that will not open a directory for reading (Windows) therefore
     * get the non-fsync guarantee for the publish step and say so in the log, rather than a save
     * that reports a failure it did not have.</p>
     */
    private static void forceDirectoryOf(Path target) {
        Path dir = target.getParent();
        if (dir == null) return;
        try (java.nio.channels.FileChannel channel =
                     java.nio.channels.FileChannel.open(dir, StandardOpenOption.READ)) {
            channel.force(true);
        } catch (IOException e) {
            logger.debug("Could not force snapshot directory {} — the snapshot's contents are on "
                    + "stable storage, its directory entry may not be", dir, e);
        }
    }

    private static void commitAtomically(Path tmp, Path target) throws IOException {
        try {
            Files.move(tmp, target, StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING);
        } catch (AtomicMoveNotSupportedException e) {
            Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    /** The body of one snapshot file: everything written between open and the commit rename. */
    @FunctionalInterface
    private interface SnapshotBody {
        void writeTo(BufferedWriter writer) throws IOException;
    }

    /**
     * The one staging-and-commit routine every save path runs (ADR-025): open the per-call
     * staging file, write {@code body}, close it, publish it with the atomic rename, and report
     * what happened.
     *
     * <p>This is where {@code void saveSnapshot}'s log-and-swallow used to live, four times over.
     * The behavior is unchanged — the same ERROR line, the same "previous file left intact"
     * guarantee, the same staging-file cleanup — but the outcome is now a value the caller may
     * have, instead of something only the log knows. A caller that ignores the value sees exactly
     * the pre-ADR-025 behavior, which is what keeps {@code saveSnapshot} honest as a delegate.</p>
     *
     * <p>Only {@link IOException} becomes a {@link SaveResult}. An unencodable key
     * ({@code ';'} in a serialized token) is an {@link IllegalArgumentException} and still
     * propagates: it is deterministic, retrying will not fix it, and the caller must change the
     * serializer, not the disk. The staging file is cleaned up on that path too.</p>
     */
    private SaveResult stageAndCommit(String name, Path path, SnapshotBody body, String detail) {
        Path tmp = tempPathFor(path);
        boolean committed = false;
        try {
            try (BufferedWriter writer = Files.newBufferedWriter(tmp)) {
                body.writeTo(writer);
            }
            // Force the staged bytes before publishing them, so the rename can never make a
            // snapshot visible whose contents the disk has not got yet. Done by reopening the
            // closed staging file rather than by syncing the writer's own descriptor, which
            // leaves the encode-and-write path above byte-for-byte and character-for-character
            // what it has always been — including Files.newBufferedWriter's strict UTF-8
            // encoder, which refuses (rather than substitutes) an unencodable tag. Measured at
            // roughly the same price as syncing the descriptor: two flushes either way.
            if (fsyncOnCommit) {
                try (java.nio.channels.FileChannel staged =
                             java.nio.channels.FileChannel.open(tmp, StandardOpenOption.WRITE)) {
                    staged.force(true);
                }
            }
            commitAtomically(tmp, path);   // writer closed above; rename is the commit
            committed = true;
            if (fsyncOnCommit) forceDirectoryOf(path);
            logger.info("Snapshot '{}' saved{} → {}", name, detail, path);
            return SaveResult.saved(name);
        } catch (IOException e) {
            logger.error("Failed to save snapshot '{}' — previous file (if any) left intact",
                    name, e);
            return SaveResult.failed(name, e);
        } finally {
            if (!committed) {
                try { Files.deleteIfExists(tmp); } catch (IOException ignored) { }
            }
        }
    }

    @Override
    public void saveSnapshot(String name, TreeContext snapshot) {
        trySaveSnapshot(name, snapshot);   // ADR-025: same work; the outcome is simply discarded
    }

    /**
     * {@link #saveSnapshot(String, TreeContext)} with the outcome reported (ADR-025).
     *
     * @return {@link SaveResult#saved} once the snapshot is committed, or
     *         {@link SaveResult#failed} carrying the {@code IOException} — in which case nothing
     *         was published and the previous snapshot of this name, if any, is untouched
     */
    @Override
    public SaveResult trySaveSnapshot(String name, TreeContext snapshot) {
        Path path = snapshotPath(name);
        return stageAndCommit(name, path, writer -> {
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
        }, "");
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
            sb.append(requireEncodableKey(ks.serialize(cur.getData()), cur.getData()))
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
                // ';' would split the record; a control char (\n, \r) would split the
                // LINE — same failure as unescaped string keys (P-1). Both are dropped
                // with a warning rather than corrupting the stream.
                if (tag.indexOf(';') >= 0 || tag.chars().anyMatch(c -> c < 0x20)) {
                    logger.warn("Tag on node {} contains ';' or a control character and "
                            + "cannot be persisted — dropping it.", cur.getData());
                } else {
                    sb.append(",").append(tag);
                }
            }
            sb.append(";");
            stack.push(cur.getRight());
            stack.push(cur.getLeft());
        }
    }

    /**
     * Enforce {@link KeySerializer}'s token contract on the pre-order path, at save time
     * (edge-case pass 2026-08-17).
     *
     * <p>The flat persistent path already refuses a token containing {@code ';'} with the reasoning
     * "silently dropping a KEY (unlike a tag) would corrupt the set on reload" — but the pre-order
     * path, which reserves {@code ','} as well (the record is {@code DATA,COLOR[,TAG]}), checked
     * nothing. A serializer emitting either character wrote a file that looked fine and only
     * surfaced on load, as an {@code ArrayIndexOutOfBoundsException} reported as MALFORMED: the
     * caller learned its snapshot was unreadable, in a different process, with no hint that its own
     * serializer was the cause. This is the same deterministic caller defect the flat path names,
     * so it is named the same way and at the same moment.</p>
     *
     * @throws IllegalArgumentException if the token cannot survive a round trip through the format
     */
    private static <K> String requireEncodableKey(String token, K key) {
        String why = null;
        if (token == null || token.isEmpty())              why = "is empty (an empty token means NIL)";
        else if (token.equals("#"))                        why = "is \"#\" (the NIL marker)";
        else if (token.indexOf(';') >= 0)                  why = "contains ';' (the node separator)";
        else if (token.indexOf(',') >= 0)                  why = "contains ',' (the field separator)";
        else if (token.chars().anyMatch(c -> c < 0x20))    why = "contains a control character";
        if (why != null) {
            throw new IllegalArgumentException("key " + key + " serializes to a token that " + why
                    + " and cannot be persisted: '" + token + "'");
        }
        return token;
    }

    // ── Load ─────────────────────────────────────────────────────────────────

    /**
     * The terminal catch every load path shares (ADR-026). The line between the two reportable
     * failures is the line the code already caught on: an {@link IOException} is the
     * <em>environment</em> — retryable, and the snapshot itself may be fine — while anything else
     * escaping the decoder is the <em>file</em>, which will decode exactly the same way next time.
     *
     * <p>The ERROR line is the pre-ADR-026 one, unchanged.</p>
     */
    private <T> LoadResult<T> loadFailure(String name, Exception e) {
        logger.error("Failed to load snapshot '{}'", name, e);
        return e instanceof IOException io
                ? LoadResult.failed(name, io)
                : LoadResult.malformed(name, "unreadable content: " + e);
    }

    /**
     * The same non-{@code LOADED} outcome, retyped for a caller that was building something else —
     * a persistent engine out of a key list, an ensemble out of an {@code OrderedSet}. Never called
     * with a {@code LOADED} result, whose value is of the wrong type by construction.
     */
    private static <T, U> LoadResult<U> propagate(LoadResult<T> outcome) {
        return new LoadResult<>(outcome.name(), outcome.status(), null,
                outcome.detail(), outcome.cause());
    }

    @Override
    public TreeContext loadSnapshot(String name) {
        // ADR-026: same work, same log lines; the outcome is simply discarded.
        return tryLoadSnapshot(name).value();
    }

    /**
     * {@link #loadSnapshot(String)} with the outcome reported (ADR-026).
     *
     * @return {@link LoadResult#loaded} carrying the restored context;
     *         {@link LoadResult#absent} when there is no such snapshot;
     *         {@link LoadResult#malformed} naming the gate that rejected the file, which is left on
     *         disk untouched; or {@link LoadResult#failed} carrying the {@code IOException}
     */
    @Override
    public LoadResult<TreeContext> tryLoadSnapshot(String name) {
        Path path = snapshotPath(name);
        if (!Files.exists(path)) {
            logger.warn("Snapshot '{}' not found at {}", name, path);
            return LoadResult.absent(name);
        }

        try (BufferedReader reader = Files.newBufferedReader(path)) {
            // ── Header line: VERSION|TIMESTAMP|STRATEGY|SIZE ──────────────────
            String headerLine = reader.readLine();
            if (headerLine == null) {
                logger.warn("Snapshot '{}' is empty — no header line.", name);
                return LoadResult.malformed(name, "empty file — no header line");
            }
            String[] header = headerLine.split("\\|");
            if (header.length < 4) {
                logger.warn("Snapshot '{}' has a malformed header ({} fields, need 4): {}",
                        name, header.length, headerLine);
                return LoadResult.malformed(name,
                        "malformed header (" + header.length + " fields, need 4)");
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
                return LoadResult.malformed(name, "non-numeric size field: '" + header[3] + "'");
            }

            TreeStrategy<Integer> strategy = resolveStrategy(strategyName);
            TreeContext  context  = new TreeContext(strategy);

            // ── Data line: pre-order node list ───────────────────────────────
            String dataLine = reader.readLine();
            if (dataLine == null) {
                logger.warn("Snapshot '{}' has a header but no node data line.", name);
                return LoadResult.malformed(name, "header present, no node data line");
            }
            String[] tokens = dataLine.split(";");
            TreeNode1<Integer> root  = deserializePreOrder(tokens, context.getTree().getNIL(),
                    KeySerializer.INTEGER);

            context.getTree().setRoot(root);
            if (root != context.getTree().getNIL()) root.setParent(context.getTree().getNIL());

            // Restore the facade's size and verify it against the header. A mismatch is a
            // REFUSAL, not a warning (bug audit 2026-08-12, P-2): the pre-order decoder
            // reads token exhaustion as NIL children, so a truncated/partially-written
            // file parses cleanly into a smaller tree that would sail through the
            // structural gate below — the header size field exists precisely to catch it.
            List<Integer> restored = new TreeDiagnostics(context).inOrderTraversal();
            int actualSize = restored.size();
            if (actualSize != declaredSize) {
                logger.error("Snapshot '{}' size mismatch: header={}, parsed={} — refusing "
                        + "(truncated or tampered file).", name, declaredSize, actualSize);
                return LoadResult.malformed(name, sizeMismatchDetail(declaredSize, actualSize));
            }
            context.forceSizeInternal(actualSize);

            // Hardening M-2: a snapshot is INPUT, not truth. Refuse a file whose restored tree
            // violates ordering or the strategy's own structural invariant — the same gate every
            // morph passes — rather than silently serving a corrupt (or tampered) structure.
            List<String> failures = validateRestored(context.getTree(), strategy, restored,
                    Comparator.<Integer>naturalOrder());
            if (!failures.isEmpty()) {
                logger.error("Snapshot '{}' failed structural validation, refusing to load: {}",
                        name, failures);
                return LoadResult.malformed(name, structuralDetail(failures));
            }

            // Restore the augmentor identity (5th header field, absent in legacy
            // files). Re-applying it recomputes augmented values from the restored
            // tags, so an interval tree round-trips without a manual setAugmentor.
            if (header.length >= 5 && "INTERVAL".equals(header[4].trim())) {
                context.setAugmentor(IntervalAugmentor.INSTANCE);
            }

            logger.info("Snapshot '{}' loaded. strategy={} size={}", name, strategyName, actualSize);
            return LoadResult.loaded(name, context);

        } catch (Exception e) {
            return loadFailure(name, e);
        }
    }

    /** The MALFORMED detail for the P-2 declared-size tripwire, worded identically on all paths. */
    private static String sizeMismatchDetail(int declared, int parsed) {
        return "size mismatch: header=" + declared + ", parsed=" + parsed
                + " (truncated or tampered file)";
    }

    /** The MALFORMED detail for the M-2 structural gate, worded identically on all paths. */
    private static String structuralDetail(Object failures) {
        return "failed structural validation: " + failures;
    }

    /**
     * Post-load structural gate (hardening M-2): the restored keys must be strictly ascending under
     * {@code order} (a corrupt file can encode an out-of-order tree that parses cleanly), and the
     * tree must pass {@link StrategyHealthCheck} — contents, size, the strategy's own structural
     * invariant, and order-statistics spot checks: the same gate every morph passes, applied to
     * file input. Returns the failure list; empty means healthy.
     */
    private static <K> List<String> validateRestored(RedBlackTree<K> engine, TreeStrategy<K> strategy,
                                                     List<K> restoredInOrder,
                                                     Comparator<? super K> order) {
        for (int i = 1; i < restoredInOrder.size(); i++) {
            if (order.compare(restoredInOrder.get(i - 1), restoredInOrder.get(i)) >= 0) {
                return List.of("restored keys not strictly ascending at index " + i);
            }
        }
        return StrategyHealthCheck.validate(engine, strategy, restoredInOrder);
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
        trySaveSnapshot(name, set, keySerializer);   // ADR-025
    }

    /** {@link #saveSnapshot(String, OrderedSet, KeySerializer)} with the outcome reported (ADR-025). */
    public <K> SaveResult trySaveSnapshot(String name, OrderedSet<K> set, KeySerializer<K> keySerializer) {
        if (set == null)            throw new IllegalArgumentException("set must not be null");
        if (keySerializer == null)  throw new IllegalArgumentException("keySerializer must not be null");
        Path path = snapshotPath(name);
        RedBlackTree<K> engine = set.getEngine();
        String strategy = engine.getStrategy().getClass().getSimpleName();
        return stageAndCommit(name, path, writer -> {
            writer.write(String.join("|",
                    VERSION,
                    Instant.now().toString(),
                    strategy,
                    String.valueOf(set.size()),
                    "DEFAULT"
            ));
            writer.newLine();

            StringBuilder sb = new StringBuilder();
            serializePreOrder(engine.getRoot(), engine.getNIL(), sb, keySerializer);
            writer.write(sb.toString());
            writer.newLine();
        }, " (generic, strategy=" + strategy + ")");
    }

    /**
     * Load a snapshot into an {@link OrderedSet} of {@code K}, parsing keys with
     * {@code keySerializer} and ordering them by {@code keyOrder}. The comparator is supplied
     * by the caller (comparators are not serialized) and must match the one used when saving.
     * The engine is rebuilt wholesale and the set's size/window are resynced via
     * {@link OrderedSet#resyncFromEngine()}. Returns {@code null} if the file is missing or
     * malformed — see {@link #tryLoadOrderedSet} for the version that says which.
     */
    public <K> OrderedSet<K> loadOrderedSet(String name, KeySerializer<K> keySerializer,
                                            Comparator<? super K> keyOrder) {
        // ADR-026: same work, same log lines; the outcome is simply discarded.
        return tryLoadOrderedSet(name, keySerializer, keyOrder).value();
    }

    /**
     * {@link #loadOrderedSet(String, KeySerializer, Comparator)} with the outcome reported
     * (ADR-026).
     *
     * @return {@link LoadResult#loaded} carrying the restored set; {@link LoadResult#absent};
     *         {@link LoadResult#malformed} naming the gate that rejected the file; or
     *         {@link LoadResult#failed} carrying the {@code IOException}
     */
    public <K> LoadResult<OrderedSet<K>> tryLoadOrderedSet(String name, KeySerializer<K> keySerializer,
                                                           Comparator<? super K> keyOrder) {
        if (keySerializer == null) throw new IllegalArgumentException("keySerializer must not be null");
        if (keyOrder == null)      throw new IllegalArgumentException("keyOrder must not be null");
        Path path = snapshotPath(name);
        if (!Files.exists(path)) {
            logger.warn("Snapshot '{}' not found at {}", name, path);
            return LoadResult.absent(name);
        }

        try (BufferedReader reader = Files.newBufferedReader(path)) {
            String headerLine = reader.readLine();
            if (headerLine == null) {
                logger.warn("Snapshot '{}' is empty — no header line.", name);
                return LoadResult.malformed(name, "empty file — no header line");
            }
            String[] header = headerLine.split("\\|");
            if (header.length < 4) {
                logger.warn("Snapshot '{}' has a malformed header ({} fields, need 4): {}",
                        name, header.length, headerLine);
                return LoadResult.malformed(name,
                        "malformed header (" + header.length + " fields, need 4)");
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
                return LoadResult.malformed(name, "non-numeric size field: '" + header[3] + "'");
            }

            TreeStrategy<K> strategy = resolveStrategy(strategyName);
            OrderedSet<K>   set      = new OrderedSet<>(strategy, keyOrder);
            RedBlackTree<K> engine   = set.getEngine();

            String dataLine = reader.readLine();
            if (dataLine == null) {
                logger.warn("Snapshot '{}' has a header but no node data line.", name);
                return LoadResult.malformed(name, "header present, no node data line");
            }
            String[] tokens = dataLine.split(";");
            TreeNode1<K> root = deserializePreOrder(tokens, engine.getNIL(), keySerializer);

            engine.setRoot(root);
            if (root != engine.getNIL()) root.setParent(engine.getNIL());
            set.resyncFromEngine();   // recompute size + FIFO window from the rebuilt engine

            int actualSize = set.size();
            if (actualSize != declaredSize) {
                // Refusal, not warning — see the int path (P-2): a pre-order prefix from a
                // truncated file parses cleanly, and the header size is the tripwire.
                logger.error("Snapshot '{}' size mismatch: header={}, parsed={} — refusing "
                        + "(truncated or tampered file).", name, declaredSize, actualSize);
                return LoadResult.malformed(name, sizeMismatchDetail(declaredSize, actualSize));
            }

            // Hardening M-2: refuse a restored tree that violates ordering or the strategy's own
            // structural invariant (the morph gate, applied to file input).
            List<String> failures = validateRestored(engine, strategy, engine.inOrder(), keyOrder);
            if (!failures.isEmpty()) {
                logger.error("Snapshot '{}' failed structural validation, refusing to load: {}",
                        name, failures);
                return LoadResult.malformed(name, structuralDetail(failures));
            }

            logger.info("Snapshot '{}' loaded (generic). strategy={} size={}", name, strategyName, actualSize);
            return LoadResult.loaded(name, set);

        } catch (Exception e) {
            return loadFailure(name, e);
        }
    }

    /** Natural-order convenience overload for {@link Comparable} keys. */
    public <K extends Comparable<? super K>> OrderedSet<K> loadOrderedSet(String name,
                                                                          KeySerializer<K> keySerializer) {
        return loadOrderedSet(name, keySerializer, Comparator.<K>naturalOrder());
    }

    /** Natural-order convenience overload of {@link #tryLoadOrderedSet} for {@link Comparable} keys. */
    public <K extends Comparable<? super K>> LoadResult<OrderedSet<K>> tryLoadOrderedSet(
            String name, KeySerializer<K> keySerializer) {
        return tryLoadOrderedSet(name, keySerializer, Comparator.<K>naturalOrder());
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
        trySaveSnapshot(name, snapshot, keySerializer);   // ADR-025
    }

    /**
     * {@link #saveSnapshot(String, PersistentTreeEngine.Snapshot, KeySerializer)} with the outcome
     * reported (ADR-025). The {@code ';'}-key {@link IllegalArgumentException} still propagates —
     * see {@link #stageAndCommit} for why a contract violation is not a {@link SaveResult}.
     */
    public <K> SaveResult trySaveSnapshot(String name, PersistentTreeEngine.Snapshot<K> snapshot,
                                          KeySerializer<K> keySerializer) {
        if (snapshot == null)      throw new IllegalArgumentException("snapshot must not be null");
        if (keySerializer == null) throw new IllegalArgumentException("keySerializer must not be null");
        Path path = snapshotPath(name);
        return stageAndCommit(name, path, writer -> {
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
        }, " (persistent, n=" + snapshot.size() + ")");
    }

    /**
     * Load a {@value #PERSISTENT_LABEL} snapshot into a fresh weight-balanced
     * {@link PersistentTreeEngine}, replaying the stored ascending keys (O(n log n), balanced by
     * construction). The comparator is supplied by the caller — comparators are not serialized —
     * and must match the one used when saving. Returns {@code null} if the file is missing,
     * malformed, or not a persistent snapshot — including a file whose key count disagrees with
     * its header (P-2's tripwire, see {@link #readFlatKeys}) or whose keys are not strictly
     * ascending (the M-2 gate the other two paths apply via {@code validateRestored}). See
     * {@link #tryLoadPersistent} for the version that says which of those it was.
     */
    public <K> PersistentTreeEngine<K> loadPersistent(String name, KeySerializer<K> keySerializer,
                                                      Comparator<? super K> keyOrder) {
        // ADR-026: same work, same log lines; the outcome is simply discarded.
        return tryLoadPersistent(name, keySerializer, keyOrder).value();
    }

    /**
     * {@link #loadPersistent(String, KeySerializer, Comparator)} with the outcome reported
     * (ADR-026).
     *
     * <p>"Not a persistent snapshot" is reported {@link LoadStatus#MALFORMED} rather than
     * {@link LoadStatus#ABSENT}: the file is there, it is simply the wrong format for this reader,
     * and telling the caller it is absent would invite exactly the overwrite that destroys it.</p>
     *
     * @return {@link LoadResult#loaded} carrying the replayed engine; {@link LoadResult#absent};
     *         {@link LoadResult#malformed} naming the gate that rejected the file; or
     *         {@link LoadResult#failed} carrying the {@code IOException}
     */
    public <K> LoadResult<PersistentTreeEngine<K>> tryLoadPersistent(
            String name, KeySerializer<K> keySerializer, Comparator<? super K> keyOrder) {
        if (keySerializer == null) throw new IllegalArgumentException("keySerializer must not be null");
        if (keyOrder == null)      throw new IllegalArgumentException("keyOrder must not be null");
        LoadResult<List<K>> read = readFlatKeys(name, keySerializer);
        if (!read.loaded()) return propagate(read);
        List<K> keys = read.value();
        String orderFailure = flatOrderFailure(keys, keyOrder);
        if (orderFailure != null) {
            logger.error("Snapshot '{}' failed structural validation, refusing to load: {}",
                    name, orderFailure);
            return LoadResult.malformed(name, structuralDetail(orderFailure));
        }
        PersistentTreeEngine<K> engine = new PersistentTreeEngine<>(keyOrder);
        for (K k : keys) engine.add(k);
        logger.info("Snapshot '{}' loaded (persistent). size={}", name, engine.size());
        return LoadResult.loaded(name, engine);
    }

    /** Natural-order convenience overload for {@link Comparable} keys. */
    public <K extends Comparable<? super K>> PersistentTreeEngine<K> loadPersistent(
            String name, KeySerializer<K> keySerializer) {
        return loadPersistent(name, keySerializer, Comparator.<K>naturalOrder());
    }

    /** Natural-order convenience overload of {@link #tryLoadPersistent} for {@link Comparable} keys. */
    public <K extends Comparable<? super K>> LoadResult<PersistentTreeEngine<K>> tryLoadPersistent(
            String name, KeySerializer<K> keySerializer) {
        return tryLoadPersistent(name, keySerializer, Comparator.<K>naturalOrder());
    }

    /**
     * Strictly-ascending gate for the flat format — the counterpart of {@code validateRestored}'s
     * ordering clause on the two structured paths. The file records a <em>set</em> in ascending
     * order, so a duplicate or an inversion means the file is malformed; replaying it would
     * silently produce fewer keys than the header declares.
     *
     * @return a failure message, or {@code null} when the keys are strictly ascending.
     */
    private static <K> String flatOrderFailure(List<K> keys, Comparator<? super K> order) {
        for (int i = 1; i < keys.size(); i++) {
            if (order.compare(keys.get(i - 1), keys.get(i)) >= 0) {
                return "restored keys not strictly ascending at index " + i;
            }
        }
        return null;
    }

    /**
     * Parse a flat persistent snapshot's keys, reporting why not when it cannot (ADR-026): the file
     * is missing, is not a persistent snapshot, or is malformed — which includes a key count that
     * disagrees with the header's declared size (the P-2 tripwire; see the refusal below).
     */
    private <K> LoadResult<List<K>> readFlatKeys(String name, KeySerializer<K> ks) {
        Path path = snapshotPath(name);
        if (!Files.exists(path)) {
            logger.warn("Snapshot '{}' not found at {}", name, path);
            return LoadResult.absent(name);
        }
        try (BufferedReader reader = Files.newBufferedReader(path)) {
            String headerLine = reader.readLine();
            if (headerLine == null) {
                logger.warn("Snapshot '{}' is empty — no header line.", name);
                return LoadResult.malformed(name, "empty file — no header line");
            }
            String[] header = headerLine.split("\\|");
            if (header.length < 4 || !PERSISTENT_LABEL.equals(header[2])) {
                logger.warn("Snapshot '{}' is not a persistent snapshot (strategy='{}').",
                        name, header.length >= 3 ? header[2] : "?");
                return LoadResult.malformed(name, "not a persistent snapshot (strategy='"
                        + (header.length >= 3 ? header[2] : "?") + "')");
            }
            if (!VERSION.equals(header[0])) {
                logger.warn("Snapshot '{}' version mismatch (file='{}', expected='{}') — attempting load anyway.",
                        name, header[0], VERSION);
            }
            int declaredSize;
            try {
                declaredSize = Integer.parseInt(header[3].trim());
            } catch (NumberFormatException e) {
                logger.warn("Snapshot '{}' has a non-numeric size field: '{}'", name, header[3]);
                return LoadResult.malformed(name, "non-numeric size field: '" + header[3] + "'");
            }
            String dataLine = reader.readLine();
            if (dataLine == null) {
                logger.warn("Snapshot '{}' has a header but no key data line.", name);
                return LoadResult.malformed(name, "header present, no key data line");
            }
            List<K> keys = new ArrayList<>();
            for (String token : dataLine.split(";")) {
                if (!token.isEmpty()) keys.add(ks.deserialize(token));
            }
            // Same refusal the int and generic paths make (P-2), which this third path was
            // missing (audit 2026-08-17, finding 3): a truncated data line parses cleanly into
            // a shorter key list — and its trailing partial token deserializes into a
            // valid-but-wrong key ("12" out of "123") — so the header size field is the only
            // tripwire. It is not advisory here either.
            if (keys.size() != declaredSize) {
                logger.error("Snapshot '{}' size mismatch: header={}, parsed={} — refusing "
                        + "(truncated or tampered file).", name, declaredSize, keys.size());
                return LoadResult.malformed(name, sizeMismatchDetail(declaredSize, keys.size()));
            }
            return LoadResult.loaded(name, keys);
        } catch (Exception e) {
            return loadFailure(name, e);
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
        trySaveSnapshot(name, ensemble, keySerializer);   // ADR-025
    }

    /**
     * {@link #saveSnapshot(String, EnsembleOrderedSet, KeySerializer)} with the outcome reported
     * (ADR-025).
     *
     * <p><b>There is no save fan-out to be partially failed.</b> An ensemble snapshot is the
     * <em>primary's</em> snapshot — one file, one staging write, one atomic commit — because every
     * ACTIVE mirror is an exact copy of it and persisting K member trees would store the same keys
     * K times. So this method's outcome is exactly the single underlying save's outcome; there is
     * no state in which some members were persisted and others were not, and none of the members
     * is mutated by a save at all. The read side ({@link #loadEnsemble}) is where an ensemble-wide
     * partial <em>could</em> exist, and it already refuses before touching the target
     * (validate-then-mutate, audit 2026-08-17 finding 4) and reports with a {@code boolean}.</p>
     */
    public <K> SaveResult trySaveSnapshot(String name, EnsembleOrderedSet<K> ensemble,
                                          KeySerializer<K> keySerializer) {
        if (ensemble == null) throw new IllegalArgumentException("ensemble must not be null");
        RankedSet<K> primarySet = ensemble.primary().set();
        if (primarySet instanceof OrderedSet<K> os) {
            return trySaveSnapshot(name, os, keySerializer);
        } else if (primarySet instanceof PersistentRankedSet<K> prs) {
            return trySaveSnapshot(name, prs.engine().snapshot(), keySerializer);
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
     * <p>Validate-then-mutate (audit 2026-08-17, finding 4): every check — file present, header
     * well-formed, declared size matched, keys strictly ascending — happens on the parsed key
     * list <em>before</em> {@code target.clear()}, so the contract below holds literally. Until
     * this was fixed, the flat branch cleared the target and replayed a truncated key list,
     * returning {@code true}: a 300-key snapshot wiped the destination and refilled it with 118.
     * The structured branch parses into a throwaway {@code OrderedSet} that is itself fully
     * validated (size tripwire + M-2 structural gate) before any key reaches the target.</p>
     *
     * @return {@code true} if the snapshot was found and replayed; {@code false} if missing or
     *         malformed (the target is left untouched in that case) — see {@link #tryLoadEnsemble}
     *         for the version that says which
     * @throws IllegalArgumentException if {@code target} or {@code keySerializer} is {@code null},
     *         or the name escapes the snapshot directory — caller defects, thrown before any I/O
     */
    public <K> boolean loadEnsemble(String name, KeySerializer<K> keySerializer, EnsembleOrderedSet<K> target) {
        // ADR-026: same work, same log lines; the outcome is simply narrowed to a boolean.
        return tryLoadEnsemble(name, keySerializer, target).loaded();
    }

    /**
     * {@link #loadEnsemble} with the outcome reported (ADR-026).
     *
     * <p>The "target left untouched" guarantee is unchanged and is what makes the distinction
     * worth having: on {@link LoadStatus#MALFORMED} or {@link LoadStatus#FAILED} the ensemble still
     * holds whatever it held before the call, so a caller that branches on the status can keep
     * serving from memory instead of concluding the snapshot was simply absent.</p>
     *
     * <p>Argument validation happens <b>before any I/O</b> and on <b>both</b> branches
     * (audit 2026-08-17 seventh pass, finding 1). The {@code keySerializer} used to be checked
     * only inside {@link #tryLoadOrderedSet}, i.e. only on the structured branch: a {@code null}
     * serializer against a {@value #PERSISTENT_LABEL} snapshot reached {@code readFlatKeys},
     * NPE'd on the first key token, and came back {@link LoadStatus#MALFORMED} — the adapter
     * blaming a perfectly good file for the caller's defect, which is exactly the kind of wrong
     * answer ADR-026 exists to remove. A caller defect is deterministic and is fixed by changing
     * code, not by changing the disk, so it throws.</p>
     *
     * @return {@link LoadResult#loaded} carrying {@code target} itself once replayed;
     *         {@link LoadResult#absent}; {@link LoadResult#malformed}; or {@link LoadResult#failed}
     * @throws IllegalArgumentException if {@code target} or {@code keySerializer} is {@code null}
     */
    public <K> LoadResult<EnsembleOrderedSet<K>> tryLoadEnsemble(
            String name, KeySerializer<K> keySerializer, EnsembleOrderedSet<K> target) {
        if (target == null)        throw new IllegalArgumentException("target must not be null");
        if (keySerializer == null) throw new IllegalArgumentException("keySerializer must not be null");
        LoadResult<List<K>> read;
        if (PERSISTENT_LABEL.equals(snapshotStrategy(name))) {
            read = readFlatKeys(name, keySerializer);              // ADR-005 P3 flat format
            if (read.loaded()) {
                // The flat format carries no structure to validate, so the ordering gate is the
                // one the other path gets from validateRestored: duplicate or inverted keys mean
                // the replay would land fewer keys than the file claims.
                String orderFailure = flatOrderFailure(read.value(), target.comparator());
                if (orderFailure != null) {
                    logger.error("Snapshot '{}' failed structural validation, refusing to load "
                            + "(ensemble left untouched): {}", name, orderFailure);
                    return LoadResult.malformed(name, structuralDetail(orderFailure));
                }
            }
        } else {
            LoadResult<OrderedSet<K>> loaded = tryLoadOrderedSet(name, keySerializer, target.comparator());
            read = loaded.loaded() ? LoadResult.loaded(name, loaded.value().inOrder())
                                   : propagate(loaded);
        }
        if (!read.loaded()) return propagate(read);                // nothing has touched target yet
        target.clear();
        for (K k : read.value()) target.add(k);
        logger.info("Snapshot '{}' replayed into ensemble ({} members, n={}).",
                name, target.members().size(), target.size());
        return LoadResult.loaded(name, target);
    }

    // ── List / Delete ─────────────────────────────────────────────────────────

    @Override
    public List<String> listSnapshots() {
        // ADR-026: same work, same log line; an unreadable directory still reads as empty here.
        return tryListSnapshots().orElse(Collections.emptyList());
    }

    /**
     * {@link #listSnapshots()} with the outcome reported (ADR-026).
     *
     * @return {@link LoadResult#loaded} carrying the names — possibly an empty list, which then
     *         genuinely means "no snapshots" — or {@link LoadResult#failed} carrying the
     *         {@code IOException} the directory read threw (a missing or unreadable snapshot
     *         directory arrives here as a {@code NoSuchFileException}, which is a fact about the
     *         filesystem and not a claim that there are no snapshots)
     */
    @Override
    public LoadResult<List<String>> tryListSnapshots() {
        // try-with-resources: Files.list holds an open directory handle (hygiene,
        // bug audit 2026-08-12).
        try (java.util.stream.Stream<java.nio.file.Path> paths = Files.list(Paths.get(DIR))) {
            List<String> names = new ArrayList<>();
            paths.filter(p -> p.toString().endsWith(EXT))
                 .forEach(p -> {
                     String filename = p.getFileName().toString();
                     names.add(filename.substring(0, filename.length() - EXT.length()));
                 });
            return LoadResult.loaded(ALL_SNAPSHOTS, names);
        } catch (IOException e) {
            logger.error("Failed to list snapshots", e);
            return LoadResult.failed(ALL_SNAPSHOTS, e);
        }
    }

    @Override
    public boolean deleteSnapshot(String name) {
        // ADR-026 amendment: same work, same log line; the outcome is simply narrowed back to
        // "did this call remove one", which is exactly what the published boolean meant.
        return tryDeleteSnapshot(name).deleted();
    }

    /**
     * {@link #deleteSnapshot(String)} with the outcome reported (ADR-026 amendment, 2026-08-18).
     *
     * <p>{@link Files#deleteIfExists} already draws the line this needs: {@code true} removed a
     * file, {@code false} found none, and an {@code IOException} means the entry is still there.
     * The published {@code boolean} folded the last two together.</p>
     *
     * @return {@link DeleteResult#deleted} when this call removed the snapshot;
     *         {@link DeleteResult#absent} when there was none of that name — in which case the
     *         name is free, which is what a retention sweep is really asking; or
     *         {@link DeleteResult#failed} carrying the {@code IOException}, in which case the
     *         snapshot is still on disk
     * @throws IllegalArgumentException if {@code name} is empty or escapes the snapshot directory
     */
    @Override
    public DeleteResult tryDeleteSnapshot(String name) {
        Path path = snapshotPath(name);          // caller defects still throw, before any I/O
        try {
            return Files.deleteIfExists(path) ? DeleteResult.deleted(name)
                                              : DeleteResult.absent(name);
        } catch (IOException e) {
            logger.error("Failed to delete snapshot '{}'", name, e);
            return DeleteResult.failed(name, e);
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
            case "AVLStrategy":            return new AVLStrategy<>();
            case "SplayStrategy":          return new SplayStrategy<>();
            case "HybridStrategy":         return new HybridStrategy<>();
            // P-3 (bug audit 2026-08-12): WB colors every node BLACK; the old RB fallback
            // applied red-black validation to that shape and refused every WB snapshot.
            case "WeightBalancedStrategy": return new WeightBalancedStrategy<>();
            default:                       return new RedBlackStrategy<>();
        }
    }
}
