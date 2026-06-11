package core.util;

import core.TreeContext;
import core.TreeNode1;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.time.Instant;
import java.util.*;

/**
 * Undo/redo with named checkpoints and an audit trail.
 *
 * <h2>Model — inverse commands (not per-op snapshots)</h2>
 * <p>Each ordinary mutation records only what is needed to invert it:
 * an {@code ADD(v)} is undone by {@code REMOVE(v)} and vice-versa. This makes
 * recording O(1) in time and memory per operation, replacing the previous
 * design that deep-copied the entire tree on every add/remove (O(n) per op,
 * O(n²) to build a tree, and unbounded memory in the audit log). See
 * {@code docs/code-review-2026-05-29.md} item #3.</p>
 *
 * <p><b>Semantics note:</b> undo restores the tree's <em>contents</em>
 * (the ordered set of keys), not necessarily the exact prior node layout —
 * re-inserting a key may yield a different but equally valid balanced shape.
 * For an ordered-set abstraction this is the meaningful contract.</p>
 *
 * <p>Named checkpoints still hold a real snapshot (they are explicit, rare save
 * points). Restoring a checkpoint pushes a lightweight {@code RESTORE} entry
 * carrying the before/after key lists, so the restore is itself undoable
 * without retaining a full tree copy on the undo stack.</p>
 *
 * <p>This class is not thread-safe and assumes single-threaded use alongside a
 * given {@link TreeContext} (whose mutators are individually synchronized).</p>
 */
public class TreeHistory {

    private static final Logger logger = LogManager.getLogger(TreeHistory.class);
    private static final int    MAX_HISTORY = 200;

    private final TreeContext               context;
    private final Deque<Command>            undoStack   = new ArrayDeque<>();
    private final Deque<Command>            redoStack   = new ArrayDeque<>();
    private final Map<String, TreeContext>  checkpoints = new LinkedHashMap<>();
    private final List<Command>             auditLog    = new ArrayList<>();

    public TreeHistory(TreeContext context) {
        this.context = context;
    }

    // ── Command record ────────────────────────────────────────────────────────

    /**
     * A recorded, invertible operation.
     *
     * <ul>
     *   <li>{@code ADD}/{@code REMOVE} — carry only {@link #value}.</li>
     *   <li>{@code RESTORE} — carries {@link #beforeContents} (undo target) and
     *       {@link #afterContents} (redo target) as key lists.</li>
     * </ul>
     */
    public static class Command {

        public enum Action { ADD, REMOVE, RESTORE }

        public final Action        action;
        public final int           value;            // ADD / REMOVE
        public final List<Integer> beforeContents;   // RESTORE: state to set on undo
        public final List<Integer> afterContents;    // RESTORE: state to set on redo
        public final int           sizeAtRecord;
        public final Instant       timestamp;
        public final String        strategyName;

        private Command(Action action, int value,
                        List<Integer> beforeContents, List<Integer> afterContents,
                        int sizeAtRecord, String strategyName) {
            this.action         = action;
            this.value          = value;
            this.beforeContents = beforeContents;
            this.afterContents  = afterContents;
            this.sizeAtRecord   = sizeAtRecord;
            this.timestamp      = Instant.now();
            this.strategyName   = strategyName;
        }

        static Command op(Action action, int value, int sizeAtRecord, String strategyName) {
            return new Command(action, value, null, null, sizeAtRecord, strategyName);
        }

        static Command restore(List<Integer> before, List<Integer> after, String strategyName) {
            return new Command(Action.RESTORE, -1, before, after, after.size(), strategyName);
        }

        @Override
        public String toString() {
            if (action == Action.RESTORE) {
                return String.format("[%s] RESTORE | strategy=%s | size=%d",
                        timestamp, strategyName, sizeAtRecord);
            }
            return String.format("[%s] %s(%d) | strategy=%s | size=%d",
                    timestamp, action, value, strategyName, sizeAtRecord);
        }
    }

    // ── Record ────────────────────────────────────────────────────────────────

    /** Record an insertion (called by {@link TreeContext#add}). */
    public void recordAdd(int value) {
        pushUndo(Command.op(Command.Action.ADD, value, context.getSize(), strategyName()));
    }

    /** Record a removal (called by {@link TreeContext#remove}). */
    public void recordRemove(int value) {
        pushUndo(Command.op(Command.Action.REMOVE, value, context.getSize(), strategyName()));
    }

    private void pushUndo(Command cmd) {
        // Trim oldest (tail) when over the cap — push() adds at the head.
        if (undoStack.size() >= MAX_HISTORY) {
            undoStack.removeLast();
            logger.debug("History limit reached — oldest command evicted.");
        }
        undoStack.push(cmd);
        redoStack.clear();   // any new action invalidates the redo future
        auditLog.add(cmd);
        // Cap the audit trail too: an uncapped log leaks memory in long-running
        // processes (the undo stack is already bounded by MAX_HISTORY). Keep the
        // most recent MAX_HISTORY entries.
        if (auditLog.size() > MAX_HISTORY) {
            auditLog.remove(0);
        }
        logger.debug("History recorded: {}", cmd);
    }

    // ── Undo / Redo ─────────────────────────────────────────────────────────────

    /** Reverts the most recent recorded operation. */
    public boolean undo() {
        if (undoStack.isEmpty()) {
            logger.warn("Nothing to undo.");
            return false;
        }
        Command cmd = undoStack.pop();
        applyInverse(cmd);
        redoStack.push(cmd);
        logger.info("UNDO: {}", cmd);
        return true;
    }

    /** Re-applies the most recently undone operation. */
    public boolean redo() {
        if (redoStack.isEmpty()) {
            logger.warn("Nothing to redo.");
            return false;
        }
        Command cmd = redoStack.pop();
        applyForward(cmd);
        undoStack.push(cmd);
        logger.info("REDO: {}", cmd);
        return true;
    }

    /** Step back up to {@code steps} commands. */
    public int rewind(int steps) {
        int rewound = 0;
        for (int i = 0; i < steps && !undoStack.isEmpty(); i++) {
            if (undo()) rewound++;
        }
        logger.info("Rewound {} step(s).", rewound);
        return rewound;
    }

    private void applyInverse(Command cmd) {
        context.setHistoryRecording(false);
        try {
            switch (cmd.action) {
                case ADD:     context.remove(cmd.value);          break;
                case REMOVE:  context.add(cmd.value);             break;
                case RESTORE: setContents(cmd.beforeContents);    break;
            }
        } finally {
            context.setHistoryRecording(true);
        }
    }

    private void applyForward(Command cmd) {
        context.setHistoryRecording(false);
        try {
            switch (cmd.action) {
                case ADD:     context.add(cmd.value);             break;
                case REMOVE:  context.remove(cmd.value);          break;
                case RESTORE: setContents(cmd.afterContents);     break;
            }
        } finally {
            context.setHistoryRecording(true);
        }
    }

    /** Replace the tree's contents with exactly {@code contents}. Caller has
     *  already suppressed history recording. */
    private void setContents(List<Integer> contents) {
        context.clear();
        for (int v : contents) context.add(v);
    }

    // ── Named checkpoints ───────────────────────────────────────────────────────

    /** Save the current state under a name (full snapshot — explicit save point). */
    public void saveCheckpoint(String name) {
        TreeContext snap = new TreeCloner(context).snapshot();
        checkpoints.put(name, snap);
        logger.info("Checkpoint '{}' saved. size={} strategy={}",
                name, snap.getSize(), strategyName());
    }

    /** Restore a named checkpoint. The restore is undoable via a lightweight
     *  RESTORE entry (before/after key lists), not a full tree copy. */
    public boolean restoreCheckpoint(String name) {
        TreeContext snap = checkpoints.get(name);
        if (snap == null) {
            logger.warn("Checkpoint '{}' not found. Available: {}", name, checkpoints.keySet());
            return false;
        }
        List<Integer> before = new TreeDiagnostics(context).inOrderTraversal();
        restoreFrom(snap);
        List<Integer> after  = new TreeDiagnostics(context).inOrderTraversal();

        pushUndo(Command.restore(before, after, strategyName()));
        logger.info("Restored checkpoint '{}'. size={}", name, after.size());
        return true;
    }

    public Set<String> listCheckpoints() {
        return Collections.unmodifiableSet(checkpoints.keySet());
    }

    public boolean deleteCheckpoint(String name) {
        return checkpoints.remove(name) != null;
    }

    // ── Audit log ─────────────────────────────────────────────────────────────

    /** Full immutable audit trail of every recorded operation. */
    public List<Command> getAuditLog() {
        return Collections.unmodifiableList(auditLog);
    }

    public void printAuditLog() {
        logger.info("=== AUDIT LOG ({} entries) ===", auditLog.size());
        for (int i = 0; i < auditLog.size(); i++) {
            logger.info("  #{}: {}", i + 1, auditLog.get(i));
        }
    }

    /** Diff of which keys were added/removed between two contexts. */
    public Map<String, List<Integer>> diff(TreeContext before, TreeContext after) {
        Set<Integer> beforeSet = new HashSet<>(new TreeDiagnostics(before).inOrderTraversal());
        Set<Integer> afterSet  = new HashSet<>(new TreeDiagnostics(after).inOrderTraversal());

        List<Integer> added   = new ArrayList<>(afterSet);  added.removeAll(beforeSet);
        List<Integer> removed = new ArrayList<>(beforeSet);  removed.removeAll(afterSet);

        Map<String, List<Integer>> result = new LinkedHashMap<>();
        result.put("added",   added);
        result.put("removed", removed);
        return result;
    }

    // ── Stats ─────────────────────────────────────────────────────────────────

    public int undoDepth()  { return undoStack.size(); }
    public int redoDepth()  { return redoStack.size(); }
    public int auditSize()  { return auditLog.size(); }

    // ── Internal ─────────────────────────────────────────────────────────────

    private String strategyName() {
        return context.getTree().getStrategy().getClass().getSimpleName();
    }

    /** Structural restore from a snapshot — bypasses add/remove so it does not
     *  re-record history. */
    private void restoreFrom(TreeContext snap) {
        TreeContext fresh = new TreeCloner(snap).snapshot();
        context.getTree().setRoot(
            fresh.getTree().getRoot() != null
                ? fresh.getTree().getRoot().deepCopy(context.getTree().getNIL())
                : context.getTree().getNIL()
        );
        context.forceSizeInternal(fresh.getSize());
        // deepCopy rebuilds nodes with the default (size) augmentor; re-apply the
        // checkpoint's augmentor so non-size augmentation (e.g. interval max-hi) is
        // restored from the copied tags rather than reverting to subtree size.
        if (fresh.getAugmentor() != TreeNode1.<Integer>defaultAugmentor()) {
            context.setAugmentor(fresh.getAugmentor());
        }
    }
}
