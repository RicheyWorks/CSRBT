package test.core;

import io.github.richeyworks.csrbt.BPlusTreeEngine;
import io.github.richeyworks.csrbt.TreeEngineRegistry;
import io.github.richeyworks.csrbt.evolution.TreeGenome;
import io.github.richeyworks.csrbt.evolution.TreeGenome.StructureType;
import io.github.richeyworks.csrbt.interfaces.TreeEngine;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-029 — fires ADR-008 D3 ahead of D2 (owner's call): {@code StructureType.B_PLUS_TREE}
 * gets its registry slot, capability note, and genome fitness model while the engine is
 * still in-memory. The registry builds it through {@link BPlusTreeEngine#asTreeEngine()}
 * (a live view — RankedSet's boolean add/remove collide with TreeEngine's void ones, so
 * one class cannot implement both seams directly).
 */
class BPlusRegistrySlotTest {

    @Test
    @DisplayName("registry builds a working B+ engine through the TreeEngine seam")
    void registryBuildsBPlus() {
        TreeEngine<Integer> e = TreeEngineRegistry.create(StructureType.B_PLUS_TREE);
        for (int i = 200; i >= 1; i--) e.add(i);
        e.remove(100);
        e.add(100);
        assertEquals(200, e.size());
        assertEquals(List.of(1, 2, 3), e.inOrder().subList(0, 3));
        assertTrue(e.contains(200));
        e.clear();
        assertTrue(e.isEmpty());

        // The capability note stays honest about what fired and what is still held.
        String note = TreeEngineRegistry.capability(StructureType.B_PLUS_TREE).note;
        assertTrue(note.contains("D2"), "note must say disk pages (D2) are still held");
        assertTrue(note.contains("in-memory"), "note must say the engine is in-memory today");
    }

    @Test
    @DisplayName("asTreeEngine is a live view, not a copy")
    void viewIsLive() {
        BPlusTreeEngine<Integer> engine = BPlusTreeEngine.withNaturalOrder(BPlusTreeEngine.MIN_FANOUT);
        TreeEngine<Integer> view = engine.asTreeEngine();
        view.add(7);
        assertTrue(engine.contains(7), "view add must land in the backing engine");
        engine.add(9);
        assertTrue(view.contains(9), "engine add must be visible through the view");
        view.remove(7);
        assertFalse(engine.contains(7));
        assertEquals(engine.inOrder(), view.inOrder());
    }

    @Test
    @DisplayName("genome scores B_PLUS_TREE like any declared structure")
    void genomeScoresBPlus() {
        for (TreeGenome g : List.of(new TreeGenome(), TreeGenome.redBlackGenome(),
                TreeGenome.splayGenome())) {
            double f = g.fitnessFor(StructureType.B_PLUS_TREE);
            assertTrue(f >= 0.0 && f <= 1.0, "fitness must clamp to [0,1], got " + f);
            assertEquals(f, g.scoreCard().scoreOf(StructureType.B_PLUS_TREE), 1e-9,
                    "scoreCard must carry the same B+ fitness");
            assertTrue(g.scoreCard().toString().contains("B_PLUS_TREE"),
                    "the scorecard narration must include the new structure");
        }
    }
}
