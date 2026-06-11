package test.core;

import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.event.TreeEvent;

import io.github.richeyworks.csrbt.experimental.cache.CacheEvolutionLoop;
import io.github.richeyworks.csrbt.experimental.cache.CacheGenome;
import io.github.richeyworks.csrbt.experimental.cache.SegmentedLruCache;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-012 E6 — <b>does the evolve-under-viability machinery transfer to a second policy
 * space?</b> The ADR's thesis, verbatim: "the machinery (genome → strategy, health gate,
 * shadow eval, selection, recorder) transfers with only a new genome + fitness +
 * viability oracle, <em>no change to the loop</em>. If it transfers, the contribution is
 * the pattern, not the tree."
 *
 * <p><b>Registered before the run:</b> the thesis is scored in two parts, because reading
 * the code already split it. (1) <em>Code transfer</em> — could
 * {@code PolicyEvolutionController} run this space unchanged? <b>No</b>, by inspection:
 * its signature and operators name {@code PolicyGenome} and ensemble member types; the
 * protocol had to be re-typed ({@code CacheEvolutionLoop}). (2) <em>Pattern + seam
 * transfer</em> — measured here, falsifiably: the re-typed loop must run the full
 * protocol in the new space (founders, lethal-genome gate kill with zero unsafe
 * promotions, lineage/trial/diversity events through the <em>unchanged</em>
 * {@link TreeEvent} vocabulary, {@link MorphPolicy} consumed verbatim as the promotion
 * gate, (μ+λ) convergence to a viable genome) and the evolved primary must finish within
 * 5% of the best fixed founder's hit rate on the same stream — evolution may not
 * <em>cost</em> viability. Verdict printed either way as one
 * {@code event=adr012_e6_verdict} line.</p>
 *
 * <p>The workload drifts (a hot working set that shifts every 5k ops) so the segmented
 * policy genes matter; everything is seeded and deterministic — no clock, no threads.</p>
 */
@DisplayName("ADR-012 E6 — the transfer experiment (cache eviction policy space)")
public class CacheTransferExperimentTest {

    private static final int CAPACITY = 256;
    private static final int TOTAL_OPS = 30_000;
    private static final int GEN_OPS = 1_500;
    private static final int HOT_SPAN = 200;
    private static final int DRIFT_EVERY = 5_000;
    private static final int DRIFT_STEP = 150;
    private static final int COLD_SPAN = 50_000;
    private static final long[] SEEDS = { 11L, 2026L, 42L };

    private static final CacheGenome LRU = CacheGenome.of(0, 1);
    private static final CacheGenome MID = CacheGenome.of(5, 4);
    private static final CacheGenome SLRU_TEXTBOOK = CacheGenome.of(8, 2);
    private static final CacheGenome LETHAL = CacheGenome.of(10, 1);   // in-box, no probation

    /** The drifting reference stream: 85% hot (sliding window), 15% cold uniform. */
    private static int nextKey(Random r, int op) {
        int base = (op / DRIFT_EVERY) * DRIFT_STEP;
        return r.nextInt(100) < 85 ? base + r.nextInt(HOT_SPAN) : r.nextInt(COLD_SPAN);
    }

    private static double runFixed(CacheGenome g, long seed) {
        SegmentedLruCache c = new SegmentedLruCache(CAPACITY, g);
        Random r = new Random(seed);
        for (int op = 0; op < TOTAL_OPS; op++) {
            int k = nextKey(r, op);
            if (!c.get(k)) c.admit(k);
        }
        assertTrue(c.validateInvariant().isEmpty(), "fixed " + g + " must stay viable");
        return c.hitRate();
    }

    // ── Unit pins for the body (the oracle must be trustworthy before it judges) ──

    @Test
    @DisplayName("SLRU body: probation hits earn promotion; a cold scan cannot flush the protected segment")
    void bodySemantics() {
        SegmentedLruCache c = new SegmentedLruCache(10, CacheGenome.of(5, 2)); // 5 protected, 5 probation
        c.admit(1);
        assertTrue(c.get(1));            // 1st probation hit
        assertTrue(c.get(1));            // 2nd → promoted
        for (int k = 100; k < 120; k++) { c.get(k); c.admit(k); }  // cold scan through probation
        assertTrue(c.peek(1), "a promoted key must survive a probation-only scan");
        assertTrue(c.validateInvariant().isEmpty());
        assertTrue(c.size() <= 10, "capacity bound holds: " + c.size());
    }

    @Test
    @DisplayName("the viability oracle kills the in-box lethal genome (protectedTenths=10): admission liveness")
    void oracleCatchesLethalGenome() {
        SegmentedLruCache c = new SegmentedLruCache(CAPACITY, LETHAL);
        List<String> failures = c.validateInvariant();
        assertFalse(failures.isEmpty(), "no-probation genome must violate admission liveness");
        c.admit(7);
        assertFalse(c.peek(7), "the lethal behavior: an admitted key is not retrievable");
    }

    @Test
    @DisplayName("determinism: same seed and stream, same lineages and survivors")
    void deterministicRuns() {
        List<CacheGenome> founders = List.of(LRU, MID, SLRU_TEXTBOOK, LETHAL);
        CacheEvolutionLoop a = new CacheEvolutionLoop(CAPACITY, founders, 2, 4, MorphPolicy.defaults(), 7L);
        CacheEvolutionLoop b = new CacheEvolutionLoop(CAPACITY, founders, 2, 4, MorphPolicy.defaults(), 7L);
        Random ra = new Random(99L);
        Random rb = new Random(99L);
        for (int gen = 0; gen < 6; gen++) {
            a.beginGeneration();
            b.beginGeneration();
            for (int i = 0; i < GEN_OPS; i++) {
                a.lookup(nextKey(ra, gen * GEN_OPS + i));
                b.lookup(nextKey(rb, gen * GEN_OPS + i));
            }
            a.endGeneration(GEN_OPS);
            b.endGeneration(GEN_OPS);
        }
        assertEquals(a.parents(), b.parents(), "same seed must reproduce the same survivors");
        assertEquals(a.primaryGenome(), b.primaryGenome(), "and the same throne");
        assertEquals(a.graveyard(), b.graveyard(), "and the same graveyard");
    }

    // ── The experiment ─────────────────────────────────────────────────────────────

    @Test
    @DisplayName("the protocol runs in the second space: gate kill, lineages, selection, verdict")
    void theExperiment() {
        System.out.println("=== ADR-012 E6: the transfer experiment (cache eviction) ===");
        System.out.println("loop reused verbatim: NO (PolicyEvolutionController is genome-typed; protocol re-typed as CacheEvolutionLoop)");
        System.out.println("seams reused verbatim: MorphPolicy (promotion gates), TreeEvent.Lineage/Trial/Diversity, TreeEventListener");

        boolean allSeedsWithinBound = true;
        for (long seed : SEEDS) {
            Map<String, Double> fixedRates = new LinkedHashMap<>();
            for (CacheGenome g : List.of(LRU, MID, SLRU_TEXTBOOK)) {
                fixedRates.put(g.toString(), runFixed(g, seed));
            }
            double bestFixed = fixedRates.values().stream().mapToDouble(Double::doubleValue).max().orElseThrow();

            List<TreeEvent<Integer>> events = new ArrayList<>();
            CacheEvolutionLoop loop = new CacheEvolutionLoop(
                    CAPACITY, List.of(LRU, MID, SLRU_TEXTBOOK, LETHAL), 2, 4,
                    MorphPolicy.defaults(), seed);
            loop.setEventListener(events::add);

            Random r = new Random(seed);
            int op = 0;
            while (op < TOTAL_OPS) {
                loop.beginGeneration();
                for (int i = 0; i < GEN_OPS && op < TOTAL_OPS; i++, op++) {
                    loop.lookup(nextKey(r, op));
                }
                loop.endGeneration(GEN_OPS);
            }

            // The protocol's receipts, hard-asserted.
            assertTrue(loop.graveyard().contains(LETHAL),
                    "the gate must kill the in-box lethal founder");
            boolean lethalDisqualified = false;
            boolean lethalEverSelected = false;
            int births = 0;
            int diversityLines = 0;
            for (TreeEvent<Integer> e : events) {
                if (e instanceof TreeEvent.Trial<Integer> t) {
                    if (t.arm().equals(LETHAL.toString())) {
                        if (t.phase().equals("DISQUALIFIED")) lethalDisqualified = true;
                        if (t.phase().equals("SELECTED")) lethalEverSelected = true;
                    }
                }
                if (e instanceof TreeEvent.Lineage<Integer>) births++;
                if (e instanceof TreeEvent.Diversity<Integer>) diversityLines++;
            }
            assertTrue(lethalDisqualified, "the death must be on the record (Trial DISQUALIFIED)");
            assertFalse(lethalEverSelected, "zero unsafe promotions — the gate is load-bearing");
            assertTrue(births >= 1, "breeding must be on the record (Lineage)");
            assertEquals(TOTAL_OPS / GEN_OPS, diversityLines, "one Diversity line per generation");
            for (CacheGenome p : loop.parents()) {
                assertFalse(loop.graveyard().contains(p), "no survivor may be a corpse");
                assertTrue(new SegmentedLruCache(CAPACITY, p).validateInvariant().isEmpty(),
                        "every survivor must be viable: " + p);
            }

            double evolved = loop.primaryHitRate();
            boolean withinBound = evolved >= bestFixed - 0.05;
            allSeedsWithinBound &= withinBound;

            StringBuilder row = new StringBuilder();
            fixedRates.forEach((name, rate) ->
                    row.append(String.format(Locale.ROOT, " %s=%.3f", name, rate)));
            System.out.println(String.format(Locale.ROOT,
                    "seed %d: fixed:%s | evolved primary=%s rate=%.3f (best fixed %.3f, Δ%+.3f) "
                    + "graveyard=%d births=%d",
                    seed, row, loop.primaryGenome(), evolved, bestFixed, evolved - bestFixed,
                    loop.graveyard().size(), births));
        }

        System.out.println(String.format(Locale.ROOT,
                "event=adr012_e6_verdict patternTransferred=%s loopReusedVerbatim=false "
                + "seamsReusedVerbatim=MorphPolicy,TreeEvent,TreeEventListener "
                + "(pattern criterion: full protocol + gate kill + zero unsafe promotions + "
                + "evolved within 5%% of best fixed, all seeds)",
                allSeedsWithinBound));
        // Printed, never hard-asserted on the performance bound (V5 discipline): either
        // answer publishes. The protocol receipts above ARE hard — a machine that lost
        // its gate or its record would be a failed transfer regardless of hit rate.
    }
}
