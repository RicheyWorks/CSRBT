package test.core;

import io.github.richeyworks.csrbt.experimental.ViabilityMap;
import io.github.richeyworks.csrbt.experimental.ViabilityMap.Cell;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-012 E1 — the viability map. Pure instrument: the health gate's lethality oracle
 * (the strategy's own {@code validateInvariant}, probed by {@link ViabilityMap} under
 * the V1 discovering-churn recipe on identical seeded streams) swept over the (Δ, Γ)
 * plane, in-box and unboxed.
 *
 * <p>House discipline: correctness is hard (oracle-exact contents on every probe —
 * {@code probe} throws on data loss, so the sweep itself is the assertion — plus the
 * pinned landmarks below); the <em>shape</em> of the map is the finding and is printed,
 * one {@code event=adr012_e1_viability} line, never hard-asserted beyond the landmarks.</p>
 *
 * <p><b>The finding (first run, 2026-06-10):</b> of 46 probed cells, exactly two are
 * viable at 8k ops × 3 seeds — (3,2), the literature point, and (4,2). Everything else
 * dies, most within 300–500 ops: all of Γ=1 (too eager to single-rotate), everything at
 * Γ ≥ 3 in-box, and every unboxed sample. The viable region is not "most of the box with
 * (5,3) as a fluke" — it is a sliver, which is the literature's narrowness result
 * (integer-parameter weight-balance has essentially one safe pair) reproduced by the
 * gate that was built to catch it.</p>
 */
@DisplayName("ADR-012 E1 — viability map over the (Δ, Γ) plane")
class ViabilityMapTest {

    @Test
    @DisplayName("landmarks pin: (3,2)/(4,2) viable; (5,3) and (2,1) die by their own invariant")
    void landmarks() {
        for (long seed : ViabilityMap.SEEDS) {
            assertEquals(-1, ViabilityMap.probe(3, 2, seed, null),
                    "(3,2) is the literature point — it must map clean (seed " + seed + ")");
            assertEquals(-1, ViabilityMap.probe(4, 2, seed, null),
                    "(4,2) is the suite's other empirically sound arm (seed " + seed + ")");
        }
        boolean dead53 = false, dead21 = false;
        for (long seed : ViabilityMap.SEEDS) {
            dead53 |= ViabilityMap.probe(5, 3, seed, null) >= 0;
            dead21 |= ViabilityMap.probe(2, 1, seed, null) >= 0;
        }
        assertTrue(dead53, "(5,3) is ADR-011 V1's in-bounds-but-unsound finding — if this "
                + "ever maps clean, the repair changed and the whole map needs re-running");
        assertTrue(dead21, "(2,1) died on the record in docs/arena-search-session.json — "
                + "same contract as (5,3)");
    }

    @Test
    @DisplayName("the sweep: oracle-exact everywhere, the map printed, the boundary nontrivial")
    void sweepAndPrint() {
        List<Cell> cells = ViabilityMap.sweep();          // throws on any data loss — hard
        assertFalse(cells.isEmpty());

        Map<String, Cell> byKey = cells.stream()
                .collect(Collectors.toMap(c -> c.delta() + "," + c.ratio(), c -> c));
        int viable = 0, unsound = 0, inBoxViable = 0;
        for (Cell c : cells) {
            if (c.unsound()) unsound++; else viable++;
            if (!c.unsound() && c.inBox()) inBoxViable++;
        }

        // The map, as rows (cols = Δ ascending; '.' = not a cell; OK = clean; n = first death op).
        int maxRatio = cells.stream().mapToInt(Cell::ratio).max().orElse(1);
        List<Integer> deltas = cells.stream().map(Cell::delta).distinct().sorted().toList();
        StringBuilder header = new StringBuilder("      ");
        for (int d : deltas) header.append(String.format("%5d", d));
        System.out.println("viability map (ops=" + ViabilityMap.OPS + ", seeds="
                + ViabilityMap.SEEDS.length + ", V1 churn recipe):");
        System.out.println(header);
        for (int g = maxRatio; g >= 1; g--) {
            StringBuilder row = new StringBuilder(String.format("Γ=%-3d ", g));
            for (int d : deltas) {
                Cell c = byKey.get(d + "," + g);
                row.append(c == null ? "    ." : (c.unsound()
                        ? String.format("%5d", c.earliest()) : "   OK"));
            }
            System.out.println(row);
        }
        System.out.println("event=adr012_e1_viability cells=" + cells.size()
                + " viable=" + viable + " unsound=" + unsound
                + " inBoxViable=" + inBoxViable);

        // The thesis ("the viable region has nontrivial structure") needs both kinds of
        // cell to exist; anything sharper is the printed map's job, not an assertion's.
        assertTrue(viable >= 1, "at least (3,2) must be viable");
        assertTrue(unsound >= 1, "at least (5,3) must be unsound");

        // The artifact holds the whole sweep, well-formed enough for the visualizer.
        String json = ViabilityMap.toJson(cells);
        assertTrue(json.startsWith("{\"type\":\"ViabilityMap\""));
        long cellCount = json.split("\\{\"delta\":", -1).length - 1;
        assertEquals(cells.size(), cellCount, "every probed cell is in the artifact");
    }
}
