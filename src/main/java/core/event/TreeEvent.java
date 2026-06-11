package core.event;

/**
 * Structured adaptation events (ADR-009 P3) — the machine-readable counterpart of the
 * {@code event=...} log lines. The set's behavior is identical with or without a listener;
 * events are records allocated <em>only</em> when a listener is registered, so the
 * unobserved hot path stays allocation-free (asserted by a benchmark row in
 * {@code TreeEventExportTest}).
 *
 * <p>All subtypes live in this file, so the interface is sealed without a {@code permits}
 * clause. JSON logging, Micrometer counters, or a visualizer feed are one switch statement
 * over this hierarchy away — that layering is deliberately the caller's, not the library's.</p>
 *
 * <p>Rotation events are deliberately absent: the engine keeps no rotation counter, and
 * instrumenting {@code MutableTree.rotateLeft/rotateRight} is hot-path surgery to be done
 * only when a consumer demands per-rotation granularity (ADR-009 §3).</p>
 */
public sealed interface TreeEvent<K> {

    // ── OrderedSet (the single-set facade) ────────────────────────────────────────

    /** An effective insert (duplicates emit nothing). */
    record Insert<K>(K key) implements TreeEvent<K> { }

    /** An effective remove (absent keys emit nothing). */
    record Remove<K>(K key) implements TreeEvent<K> { }

    /** A sliding-window eviction of the oldest-inserted key ({@code setMaxSize}). */
    record Evict<K>(K key) implements TreeEvent<K> { }

    /**
     * A health-gated strategy morph attempt. {@code committed} is false when the candidate
     * failed the health gate and the incumbent was kept — the no-data-loss path, made visible.
     * Same-strategy no-op requests emit nothing (no attempt was made).
     */
    record Morph<K>(String fromStrategy, String toStrategy, boolean committed) implements TreeEvent<K> { }

    /** A {@code selfRepair()} rebuild; {@code healthy} is the post-rebuild validation verdict. */
    record Repair<K>(boolean healthy) implements TreeEvent<K> { }

    // ── EnsembleOrderedSet (member lifecycle) ─────────────────────────────────────

    /** A member quarantined — by the health pass, a vote dissent, or a mid-write failure. */
    record Quarantine<K>(String member) implements TreeEvent<K> { }

    /** A quarantined member rebuilt from the primary; {@code healed} is the outcome. */
    record Heal<K>(String member, boolean healed) implements TreeEvent<K> { }

    /** A member permanently retired (heal failed or operator decision). */
    record Retire<K>(String member) implements TreeEvent<K> { }

    /**
     * The serving primary changed. {@code failover} distinguishes an unplanned swap (write
     * failure, structural fault, vote dissent) from a deliberate {@code promote(...)}.
     */
    record Promote<K>(String fromMember, String toMember, boolean failover) implements TreeEvent<K> { }

    /** An Option C cadence rebuild refreshed {@code rebuilt} shadows to n keys. */
    record ShadowRebuild<K>(int rebuilt, int n) implements TreeEvent<K> { }

    /** The soft memory ceiling latched ({@code breached=true}) or recovered. */
    record MemoryCeiling<K>(boolean breached, long estimateBytes, long ceilingBytes) implements TreeEvent<K> { }

    // ── PolicySearchController (ADR-011 V3: the evolution machine's search loop) ────

    /**
     * One step of a policy-search trial: an arm was {@code TRIED} (morphed onto the trial
     * shadow through the health gate), {@code SCORED} (fitness recorded; {@code cost} is the
     * evaluation, {@code pulls} the arm's pull count), {@code DISQUALIFIED} (failed the gate
     * or its own invariant — dead permanently), or {@code SELECTED} (promoted to primary
     * through the MorphPolicy gates). {@code cost} is {@code NaN} where no score exists
     * (TRIED, and DISQUALIFIED before scoring).
     */
    record Trial<K>(String arm, String phase, double cost, int pulls) implements TreeEvent<K> { }

    /**
     * A birth in the population search (ADR-011 V4): {@code child} was bred in
     * {@code generation} from {@code parentA} (and {@code parentB} for a blend;
     * {@code null} for a mutation or founder) by {@code op} ∈ founder / mutation / blend.
     * Deaths are {@code Trial} events (DISQUALIFIED for gate/invariant kills, CULLED for
     * selection), so a recorded session carries complete lineages.
     */
    record Lineage<K>(int generation, String child, String parentA, String parentB, String op)
            implements TreeEvent<K> { }

    /**
     * The population's diversity at the close of {@code generation} (ADR-012 E2) — emitted
     * once per {@code endGeneration}, after selection, over the <em>surviving parents</em>:
     * {@code survivors} (= μ when the pool allows), {@code lineages} (distinct founder
     * roots among survivors — ancestry follows parentA; a blend inherits its first parent's
     * root; a rediscovered genome value keeps its first-recorded root),
     * {@code meanPairwiseDistance} (mean L1 distance in parameter space over survivor
     * pairs of the same parameterized family; {@code NaN} when no such pair exists —
     * serialized as null), and the generation's deaths: {@code disqualified} (gate /
     * own-invariant kills) and {@code culled} (selection). Diversity is an output, not a
     * mechanism: nothing reads it back into selection (that would be E4).
     */
    record Diversity<K>(int generation, int survivors, int lineages,
                        double meanPairwiseDistance, int disqualified, int culled)
            implements TreeEvent<K> { }
}
