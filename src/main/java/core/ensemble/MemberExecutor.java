package core.ensemble;

import java.util.List;
import java.util.function.Function;

/**
 * MemberExecutor — the fan-out seam named in ADR-003: applies one write operation to every member
 * handed to it and reports a per-member {@link Outcome}. E1 ran this loop inline and sequentially;
 * E5 makes it a strategy so the same write path can fan out in parallel (members share no mutable
 * state, so the fan-out is embarrassingly parallel).
 *
 * <p><b>Contract.</b> {@code apply} must return one outcome per member, in the same order as the
 * input list, and must not let one member's throwable abort the others — a member that throws is
 * reported as {@link Outcome#failed()} so the caller (the ensemble facade) can quarantine it while
 * the write commits to the rest. The caller serializes invocations (the ensemble's writer lock), so
 * implementations need no internal synchronization across calls; they only need to ensure the
 * results they return are visible to the calling thread (e.g. via {@code Future.get}).</p>
 */
public interface MemberExecutor {

    /**
     * Apply {@code op} to each member, returning per-member outcomes in input order.
     * Implementations must capture a member's throwable in its outcome, never propagate it.
     */
    <K> List<Outcome> apply(List<EnsembleMember<K>> members, Function<EnsembleMember<K>, Boolean> op);

    /** Release any threads the executor owns. Idempotent; the sequential executor has none. */
    default void shutdown() {}

    /** The E1 behavior: apply in the caller's thread, member by member. */
    static MemberExecutor sequential() {
        return new SequentialMemberExecutor();
    }

    /** Result of applying a write to one member: either an effective-change flag or a failure. */
    final class Outcome {
        private final boolean changed;
        private final Throwable failure;

        private Outcome(boolean changed, Throwable failure) {
            this.changed = changed;
            this.failure = failure;
        }

        public static Outcome ok(boolean changed)     { return new Outcome(changed, null); }
        public static Outcome failed(Throwable cause) { return new Outcome(false, cause); }

        /** True if the member threw instead of completing the write. */
        public boolean failed()    { return failure != null; }
        /** The member's effective-change result; meaningless if {@link #failed()}. */
        public boolean changed()   { return changed; }
        /** The captured throwable, or {@code null} if the write completed. */
        public Throwable cause()   { return failure; }

        @Override
        public String toString() {
            return failure == null ? "Outcome[changed=" + changed + "]"
                                   : "Outcome[failed: " + failure + "]";
        }
    }
}
