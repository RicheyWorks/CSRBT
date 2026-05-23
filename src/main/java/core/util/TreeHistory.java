package core.util;

import core.TreeContext;
import core.TreeNode1;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.time.Instant;
import java.util.*;

/**
 * Full undo/redo system with named checkpoints and branching timelines.
 *
 * Architecture:
 *   - undoStack / redoStack for linear undo-redo
 *   - checkpoints map for named save points (branch roots)
 *   - auditLog for a complete immutable record of every operation ever run
 *
 * "Time travel": restore to any named checkpoint, or step backward/forward
 * through the undo stack one command at a time.
 */
public class TreeHistory {

    private static final Logger logger = LogManager.getLogger(TreeHistory.class);
    private static final int    MAX_HISTORY = 200;

    private final TreeContext              context;
    private final Deque<Command>           undoStack    = new ArrayDeque<>();
    private final Deque<Command>           redoStack    = new ArrayDeque<>();
    private final Map<String, Command>     checkpoints  = new LinkedHashMap<>();
    private final List<Command>            auditLog     = new ArrayList<>();

    public TreeHistory(TreeContext context) {
        this.context = context;
    }

    // ── Command record ────────────────────────────────────────────────────────

    public static class Command {

        public enum Action { ADD, REMOVE, CLEAR, MORPH, REPAIR }

        public final Action      action;
        public final int         value;
        public final TreeContext snapshot;   // state BEFORE this command ran
        public final Instant     timestamp;
        public final String      strategyName;

        public Command(Action action, int value, TreeContext snapshot, String strategyName) {
            this.action       = action;
            this.value        = value;
            this.snapshot     = snapshot;
            this.timestamp    = Instant.now();
            this.strategyName = strategyName;
        }

        @Override
        public String toString() {
            return String.format("[%s] %s(%d) | strategy=%s | size=%d",
                    timestamp, action, value, strategyName, snapshot.getSize());
        }
    }

    // ── Record ────────────────────────────────────────────────────────────────

    public void addCommand(Command.Action action, int value, TreeContext snapshot) {
        String sname = context.getTree().getStrategy().getClass().getSimpleName();
        Command cmd  = new Command(action, value, snapshot, sname);

        // Trim if over limit
        if (undoStack.size() >= MAX_HISTORY) {
            undoStack.removeFirst();
            logger.debug("History limit reached — oldest command evicted.");
        }

        undoStack.push(cmd);
        redoStack.clear(); // branching: any new action clears the redo future
        auditLog.add(cmd);

        logger.debug("History recorded: {}", cmd);
    }

    // ── Undo / Redo ───────────────────────────────────────────────────────────

    /**
     * Restores the tree to the state it was in just before the last command.
     */
    public boolean undo() {
        if (undoStack.isEmpty()) {
            logger.warn("Nothing to undo.");
            return false;
        }

        Command cmd = undoStack.pop();
        redoStack.push(cmd);
        restoreFrom(cmd.snapshot);

        logger.info("UNDO: {} — tree restored to size={}", cmd, cmd.snapshot.getSize());
        return true;
    }

    /**
     * Re-applies a command that was undone.
     */
    public boolean redo() {
        if (redoStack.isEmpty()) {
            logger.warn("Nothing to redo.");
            return false;
        }

        Command cmd = redoStack.pop();

        // Re-apply the action on the current context
        switch (cmd.action) {
            case ADD:    context.add(cmd.value);    break;
            case REMOVE: context.remove(cmd.value); break;
            case CLEAR:  context.clear();           break;
            default:
                logger.warn("Redo not supported for action {}", cmd.action);
                return false;
        }

        undoStack.push(cmd);
        logger.info("REDO: {} — action re-applied.", cmd);
        return true;
    }

    /**
     * Step back N commands at once.
     */
    public int rewind(int steps) {
        int rewound = 0;
        for (int i = 0; i < steps && !undoStack.isEmpty(); i++) {
            if (undo()) rewound++;
        }
        logger.info("Rewound {} step(s).", rewound);
        return rewound;
    }

    // ── Named checkpoints (branches) ─────────────────────────────────────────

    /**
     * Save the current state under a name. Can be restored at any time,
     * even after many subsequent operations — this is your branch point.
     */
    public void saveCheckpoint(String name) {
        TreeCloner cloner = new TreeCloner(context);
        TreeContext snap  = cloner.snapshot();
        String sname      = context.getTree().getStrategy().getClass().getSimpleName();
        Command cmd       = new Command(Command.Action.ADD, -1, snap, sname);
        checkpoints.put(name, cmd);
        logger.info("Checkpoint '{}' saved. size={} strategy={}", name, snap.getSize(), sname);
    }

    /**
     * Restore the tree to a previously saved named checkpoint.
     */
    public boolean restoreCheckpoint(String name) {
        Command cmd = checkpoints.get(name);
        if (cmd == null) {
            logger.warn("Checkpoint '{}' not found. Available: {}", name, checkpoints.keySet());
            return false;
        }

        // Push current state onto undo so the checkpoint restore is itself undoable
        TreeCloner cloner = new TreeCloner(context);
        addCommand(Command.Action.ADD, -1, cloner.snapshot());

        restoreFrom(cmd.snapshot);
        logger.info("Restored checkpoint '{}'. size={}", name, cmd.snapshot.getSize());
        return true;
    }

    public Set<String> listCheckpoints() {
        return Collections.unmodifiableSet(checkpoints.keySet());
    }

    public boolean deleteCheckpoint(String name) {
        return checkpoints.remove(name) != null;
    }

    // ── Audit log ─────────────────────────────────────────────────────────────

    /**
     * Full immutable audit trail of every operation since this TreeHistory was created.
     */
    public List<Command> getAuditLog() {
        return Collections.unmodifiableList(auditLog);
    }

    /**
     * Print a formatted audit trail to the logger.
     */
    public void printAuditLog() {
        logger.info("=== AUDIT LOG ({} entries) ===", auditLog.size());
        for (int i = 0; i < auditLog.size(); i++) {
            logger.info("  #{}: {}", i + 1, auditLog.get(i));
        }
    }

    /**
     * Returns a diff: which values were added or removed between two snapshots.
     */
    public Map<String, List<Integer>> diff(TreeContext before, TreeContext after) {
        TreeDiagnostics diagBefore = new TreeDiagnostics(before);
        TreeDiagnostics diagAfter  = new TreeDiagnostics(after);

        List<Integer> beforeVals = diagBefore.inOrderTraversal();
        List<Integer> afterVals  = diagAfter.inOrderTraversal();

        Set<Integer> beforeSet = new HashSet<>(beforeVals);
        Set<Integer> afterSet  = new HashSet<>(afterVals);

        List<Integer> added   = new ArrayList<>(afterSet);  added.removeAll(beforeSet);
        List<Integer> removed = new ArrayList<>(beforeSet); removed.removeAll(afterSet);

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

    private void restoreFrom(TreeContext snap) {
        TreeCloner cloner = new TreeCloner(snap);
        TreeContext fresh = cloner.snapshot();

        // Structural restore — bypasses add/remove to avoid re-recording history
        context.getTree().setRoot(
            fresh.getTree().getRoot() != null
                ? fresh.getTree().getRoot().deepCopy(context.getTree().getNIL())
                : context.getTree().getNIL()
        );
        context.forceSizeInternal(fresh.getSize());
    }
}
