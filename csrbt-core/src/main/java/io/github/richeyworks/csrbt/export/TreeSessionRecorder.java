package io.github.richeyworks.csrbt.export;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.event.TreeEvent;
import io.github.richeyworks.csrbt.event.TreeEventListener;

import java.util.Objects;

/**
 * Session recorder (ADR-010 X2) — turns a live {@link OrderedSet}'s structured events into
 * a replayable session file for the visualizer's arena mode (`demo/visualizer.html`).
 *
 * <p>Volume discipline: per-key events (insert/remove/evict) are <em>counted between</em>
 * decision points, never stored individually — 50k inserts must not mean 50k array entries.
 * Decision events (morph, repair) are stored with the running op count, the counts since
 * the previous decision, and a full {@link TreeExport} snapshot of the tree <em>after</em>
 * the decision, so the replay animates exactly what the structure did.</p>
 *
 * <p>Session format v1 (a second public JSON contract, versioned from day one):</p>
 * <pre>{@code
 * { "version": 1,
 *   "events": [ { "op": 720, "type": "Morph", "from": "RedBlackStrategy",
 *                 "to": "SplayStrategy", "committed": true,
 *                 "counts": { "inserts": 64, "removes": 0, "evicts": 0 },
 *                 "state": { ...TreeExport schema... } }, ... ],
 *   "final": { ...TreeExport schema... } }
 * }</pre>
 *
 * <p>Snapshots are taken inside the event callback — i.e. on the mutating thread, under the
 * set's locks, immediately after the decision committed — so they are consistent by
 * construction. The recorder inherits the listener contract: keep the set's other work off
 * this thread while recording, and detach (re-register {@code null}) when done. v1 records
 * single-set sessions; ensemble lifecycle events are ignored. ADR-011 V3 adds
 * {@code Trial} decision points (additive): register the recorder on a
 * {@code PolicySearchController} <em>and</em> attach it to the trial member's set, and the
 * session replays the search — arms tried, scored, disqualified, selected — over snapshots
 * of the trial tree itself.</p>
 */
public final class TreeSessionRecorder<K> implements TreeEventListener<K> {

    private final OrderedSet<K> set;
    private final StringBuilder events = new StringBuilder();
    private long ops;                                  // cumulative effective ops
    private int inserts, removes, evicts;              // since the last decision point
    private int decisions;

    public TreeSessionRecorder(OrderedSet<K> set) {
        this.set = Objects.requireNonNull(set, "set cannot be null");
        // The session opens on the state at attach time, so a replay shows the tree
        // BEFORE its first decision. Not a decision: decisionCount() stays 0.
        events.append("    { \"op\": 0, \"type\": \"Start\",\n      \"counts\": "
                + "{ \"inserts\": 0, \"removes\": 0, \"evicts\": 0 },\n      \"state\": ")
              .append(TreeExport.toJson(set))
              .append(" }");
    }

    /** Construct and register on {@code set} in one step. */
    public static <K> TreeSessionRecorder<K> attach(OrderedSet<K> set) {
        TreeSessionRecorder<K> r = new TreeSessionRecorder<>(set);
        set.setEventListener(r);
        return r;
    }

    @Override
    public synchronized void onEvent(TreeEvent<K> e) {
        if (e instanceof TreeEvent.Insert) {
            ops++; inserts++;
        } else if (e instanceof TreeEvent.Remove) {
            ops++; removes++;
        } else if (e instanceof TreeEvent.Evict) {
            ops++; evicts++;
        } else if (e instanceof TreeEvent.Morph<K> m) {
            decision("Morph", "\"from\": \"" + m.fromStrategy() + "\", \"to\": \""
                    + m.toStrategy() + "\", \"committed\": " + m.committed());
        } else if (e instanceof TreeEvent.Repair<K> r) {
            decision("Repair", "\"healthy\": " + r.healthy());
        } else if (e instanceof TreeEvent.Trial<K> t) {
            // ADR-011 V3: search-trial decision points (additive to session format v1).
            // cost is NaN where no score exists — rendered as null, since JSON has no NaN.
            decision("Trial", "\"arm\": \"" + t.arm() + "\", \"phase\": \"" + t.phase()
                    + "\", \"cost\": " + (Double.isNaN(t.cost()) ? "null"
                            : String.format(java.util.Locale.ROOT, "%.4f", t.cost()))
                    + ", \"pulls\": " + t.pulls());
        } else if (e instanceof TreeEvent.Lineage<K> l) {
            // ADR-011 V4: births in the population search (deaths are Trial decisions).
            decision("Lineage", "\"generation\": " + l.generation()
                    + ", \"child\": \"" + l.child() + "\", \"parentA\": "
                    + (l.parentA() == null ? "null" : "\"" + l.parentA() + "\"")
                    + ", \"parentB\": " + (l.parentB() == null ? "null" : "\"" + l.parentB() + "\"")
                    + ", \"op\": \"" + l.op() + "\"");
        } else if (e instanceof TreeEvent.Diversity<K> d) {
            // ADR-012 E2: per-generation population diversity (spread NaN → null, as Trial cost).
            decision("Diversity", "\"generation\": " + d.generation()
                    + ", \"survivors\": " + d.survivors()
                    + ", \"lineages\": " + d.lineages()
                    + ", \"meanPairwiseDistance\": " + (Double.isNaN(d.meanPairwiseDistance())
                            ? "null" : String.format(java.util.Locale.ROOT, "%.2f", d.meanPairwiseDistance()))
                    + ", \"disqualified\": " + d.disqualified()
                    + ", \"culled\": " + d.culled());
        }
        // Other ensemble lifecycle events: out of scope for v1 single-set sessions.
    }

    private void decision(String type, String fields) {
        if (events.length() > 0) events.append(",\n");
        events.append("    { \"op\": ").append(ops)
              .append(", \"type\": \"").append(type).append("\", ").append(fields)
              .append(",\n      \"counts\": { \"inserts\": ").append(inserts)
              .append(", \"removes\": ").append(removes)
              .append(", \"evicts\": ").append(evicts)
              .append(" },\n      \"state\": ")
              .append(TreeExport.toJson(set))
              .append(" }");
        inserts = removes = evicts = 0;
        decisions++;
    }

    /** Decision points recorded so far (morphs + repairs). */
    public synchronized int decisionCount() { return decisions; }

    /** Effective per-key ops observed so far. */
    public synchronized long opCount() { return ops; }

    /** Render the session (v1 schema); callable repeatedly — the final state is live. */
    public synchronized String toJson() {
        return "{\n  \"version\": 1,\n  \"events\": [\n" + events
                + "\n  ],\n  \"final\": " + TreeExport.toJson(set) + "\n}";
    }
}
