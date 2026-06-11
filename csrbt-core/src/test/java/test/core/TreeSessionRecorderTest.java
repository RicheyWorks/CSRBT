package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.export.TreeSessionRecorder;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-010 X2a — the session recorder. Contracts: per-key events are counted between
 * decision points (never stored individually); each decision entry carries the running op
 * count, the counts since the previous decision, and a post-decision snapshot; no-op morph
 * requests record nothing; the v1 envelope is well-formed.
 */
@DisplayName("TreeSessionRecorder — replayable sessions over the event seam (ADR-010 X2a)")
public class TreeSessionRecorderTest {

    @Test
    @DisplayName("counts accumulate between decisions and reset at each; snapshots ride along")
    void countsAndDecisions() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        TreeSessionRecorder<Integer> rec = TreeSessionRecorder.attach(set);

        for (int i = 0; i < 100; i++) set.add(i);
        for (int i = 0; i < 30; i++) set.add(i);          // duplicates: not effective, not counted
        for (int i = 0; i < 20; i++) set.remove(i);
        for (int i = 500; i < 505; i++) set.remove(i);    // absent: not counted
        assertEquals(120, rec.opCount());

        assertTrue(set.setStrategy(new AVLStrategy<>()));
        assertEquals(1, rec.decisionCount());

        set.setMaxSize(80);                               // size is exactly 80: no eviction yet
        for (int i = 1_000; i < 1_005; i++) set.add(i);   // each add evicts the oldest survivor
        assertTrue(set.setStrategy(new SplayStrategy<>()));
        assertEquals(2, rec.decisionCount());
        assertEquals(130, rec.opCount(), "5 inserts + 5 evictions since the first decision");

        String json = rec.toJson();
        assertTrue(json.contains("\"version\": 1"), json.substring(0, 60));
        assertTrue(json.contains("\"op\": 120, \"type\": \"Morph\", \"from\": \"RedBlackStrategy\", "
                + "\"to\": \"AVLStrategy\", \"committed\": true"), "first decision header");
        assertTrue(json.contains("\"counts\": { \"inserts\": 100, \"removes\": 20, \"evicts\": 0 }"),
                "counts before the first decision");
        assertTrue(json.contains("\"counts\": { \"inserts\": 5, \"removes\": 0, \"evicts\": 5 }"),
                "counts reset and re-accumulate between decisions");
        assertTrue(json.contains("\"strategy\": \"AVLStrategy\""), "post-decision snapshot");
        assertTrue(json.lastIndexOf("\"strategy\": \"SplayStrategy\"")
                        > json.indexOf("\"final\":"), "the final state reflects the live set");
        assertEquals(count(json, '{'), count(json, '}'), "balanced braces");
    }

    @Test
    @DisplayName("no-op morphs record nothing; repairs record their verdict")
    void noOpsAndRepairs() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        TreeSessionRecorder<Integer> rec = TreeSessionRecorder.attach(set);
        for (int i = 0; i < 50; i++) set.add(i);

        assertFalse(set.setStrategy(new RedBlackStrategy<>()), "same-strategy no-op");
        assertEquals(0, rec.decisionCount(), "no attempt, no decision entry");

        assertTrue(set.selfRepair());                     // OrderedSet.selfRepair always rebuilds
        assertEquals(1, rec.decisionCount());
        assertTrue(rec.toJson().contains("\"type\": \"Repair\", \"healthy\": true"));
    }

    private static int count(String s, char c) {
        int n = 0;
        for (int i = 0; i < s.length(); i++) if (s.charAt(i) == c) n++;
        return n;
    }
}
