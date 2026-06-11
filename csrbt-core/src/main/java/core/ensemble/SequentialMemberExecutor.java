package core.ensemble;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;

/**
 * The E1 fan-out preserved behind the E5 seam: apply the write to each member in the caller's
 * thread, in member order. A throwing member is captured as a failed {@link MemberExecutor.Outcome}
 * and the loop continues — the ADR-003 consistency rule (the write still commits to the rest) is
 * enforced here, not just in the parallel path.
 */
final class SequentialMemberExecutor implements MemberExecutor {

    @Override
    public <K> List<Outcome> apply(List<EnsembleMember<K>> members, Function<EnsembleMember<K>, Boolean> op) {
        List<Outcome> outcomes = new ArrayList<>(members.size());
        for (EnsembleMember<K> m : members) {
            try {
                outcomes.add(Outcome.ok(op.apply(m)));
            } catch (Throwable t) {
                outcomes.add(Outcome.failed(t));
            }
        }
        return outcomes;
    }

    @Override
    public String toString() { return "SequentialMemberExecutor"; }
}
