package test.core;

import io.github.richeyworks.csrbt.experimental.cache.CacheGenome;
import io.github.richeyworks.csrbt.experimental.cache.SegmentedLruCache;
import io.github.richeyworks.csrbt.experimental.ecology.CacheIsland;
import io.github.richeyworks.csrbt.experimental.ecology.LifeTable;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-016 §E4 — island observables over the segmented-LRU cache: bounded habitat,
 * admissions as immigration, evictions as extinction, and the MacArthur–Wilson
 * equilibrium signature (flat richness, nonzero turnover) checked on the live cache.
 *
 * <p>Cache geometry used throughout: capacity 10, {@code CacheGenome.of(5, 2)} —
 * protected segment 5 (tenths of capacity), probation 5, promotion after 2 probation
 * hits. Probation overflow evicts its LRU; only promoted keys reach the protected
 * segment.</p>
 */
@DisplayName("CacheIsland — bounded-habitat observables over the cache")
class CacheIslandTest {

    private static CacheIsland island(SegmentedLruCache[] out) {
        SegmentedLruCache cache = new SegmentedLruCache(10, CacheGenome.of(5, 2));
        if (out != null) out[0] = cache;
        return new CacheIsland(cache, 10);
    }

    @Test
    @DisplayName("immigration fills the probation habitat; no evictions while under its cap")
    void fillsWithoutEviction() {
        CacheIsland isle = island(null);
        for (int k = 0; k < 5; k++) isle.admit(k); // probation cap is 5
        assertEquals(5, isle.immigrations());
        assertEquals(5, isle.richness());
        assertEquals(0.5, isle.saturation(), 1e-9);
        assertEquals(0, isle.sample());
        assertEquals(0, isle.extinctions());
    }

    @Test
    @DisplayName("probation overflow is extinction: dated at the sweep, lifespans recorded")
    void overflowIsExtinction() {
        CacheIsland isle = island(null);
        for (int k = 0; k < 5; k++) isle.admit(k);   // ops 1..5
        isle.sample();
        isle.admit(5);                                // op 6 → evicts LRU key 0
        isle.admit(6);                                // op 7 → evicts key 1
        assertEquals(2, isle.sample());

        assertEquals(2, isle.extinctions());
        assertEquals(5, isle.richness());            // habitat stays full
        assertEquals(2, isle.residencies().size());
        LifeTable.Lifespan first = isle.residencies().get(0);
        assertEquals(0, first.key());
        assertEquals(1, first.birthOp());
        assertEquals(7, first.deathOp());            // dated at the sweep's op clock
        // Turnover of the interval: (2 immigrations + 2 extinctions) / 2
        assertEquals(2.0, isle.lastIntervalTurnover(), 1e-9);
    }

    @Test
    @DisplayName("the equilibrium signature: richness flat at 5 while composition keeps turning over")
    void equilibriumSignature() {
        CacheIsland isle = island(null);
        for (int k = 0; k < 5; k++) isle.admit(k);
        isle.sample();

        long turnoverSamples = 0;
        for (int wave = 0; wave < 10; wave++) {
            for (int j = 0; j < 5; j++) isle.admit(100 + wave * 5 + j); // 5 fresh immigrants
            isle.sample();
            assertEquals(5, isle.richness(), "richness must hold flat at equilibrium");
            if (isle.lastIntervalTurnover() > 0) turnoverSamples++;
        }
        assertEquals(10, turnoverSamples, "every interval at equilibrium shows turnover");
        assertEquals(55, isle.immigrations());
        assertEquals(50, isle.extinctions());        // 5 residents remain of 55 ever admitted
    }

    @Test
    @DisplayName("the protected segment is a refuge: a promoted key survives a probation flood")
    void protectedSegmentIsRefuge() {
        SegmentedLruCache[] cache = new SegmentedLruCache[1];
        CacheIsland isle = island(cache);
        isle.admit(7);
        isle.get(7);
        isle.get(7);                                  // 2 probation hits → promoted
        for (int k = 100; k < 120; k++) isle.admit(k); // flood probation far past its cap
        isle.sample();

        assertTrue(cache[0].peek(7), "promoted key must survive the probation flood");
        // The flood carried off probation residents, never the protected key.
        for (LifeTable.Lifespan ls : isle.residencies()) {
            assertTrue(ls.key() != 7, "the refuge key must not appear in the eviction record");
        }
    }

    @Test
    @DisplayName("re-immigration after extinction is a new residency, not a resurrection")
    void reImmigration() {
        CacheIsland isle = island(null);
        for (int k = 0; k < 5; k++) isle.admit(k);
        isle.admit(5);                                // evicts key 0
        isle.sample();
        assertEquals(1, isle.extinctions());

        isle.admit(0);                                // key 0 immigrates again
        assertEquals(7, isle.immigrations());
        isle.sample();
        assertEquals(2, isle.extinctions());          // (key 1 fell to the re-admission)
        assertEquals(1, isle.residencies().stream().filter(ls -> ls.key() == 0).count(),
                "only the first residency of key 0 is closed so far");
    }

    @Test
    @DisplayName("residence life table plugs the eviction record into the demography layer")
    void residenceLifeTable() {
        CacheIsland isle = island(null);
        for (int k = 0; k < 5; k++) isle.admit(k);
        for (int k = 5; k < 15; k++) isle.admit(k);   // steady eviction pressure
        isle.sample();
        assertEquals(10, isle.residencies().size());

        LifeTable table = isle.residenceLifeTable(3);
        assertEquals(10, table.cohortSize());
        assertEquals(1.0, table.survivorshipAt(0), 1e-9);
        assertTrue(table.lifeExpectancy() > 0);
    }

    @Test
    @DisplayName("eviction + re-admission between samples: first residency closed at the admit, books stay balanced")
    void rebirthBetweenSamples() {
        CacheIsland isle = island(null);
        for (int k = 0; k < 5; k++) isle.admit(k);   // ops 1..5, probation full
        isle.admit(5);                                // op 6 → evicts key 0 (unsampled)
        isle.admit(0);                                // op 7 → key 0 back BEFORE any sample

        // The admit itself must notice the tracked key was gone: the first residency
        // closes (dated at the admit — sampling-resolution convention) and the books
        // stay balanced instead of silently dropping a lifespan.
        assertEquals(7, isle.immigrations());
        assertEquals(1, isle.extinctions());
        assertEquals(1, isle.residencies().size());
        LifeTable.Lifespan first = isle.residencies().get(0);
        assertEquals(0, first.key());
        assertEquals(1, first.birthOp());
        assertEquals(7, first.deathOp());

        isle.sample();                                // finds key 1 (evicted by op 7's overflow)
        assertEquals(2, isle.extinctions());
        // Accounting invariant: immigrations − extinctions == current residents.
        assertEquals(isle.richness(), isle.immigrations() - isle.extinctions());
    }

    @Test
    @DisplayName("a lookup miss on a tracked key also closes its residency, dated at the miss")
    void missClosesResidency() {
        CacheIsland isle = island(null);
        for (int k = 0; k < 5; k++) isle.admit(k);   // ops 1..5
        isle.admit(5);                                // op 6 → evicts key 0
        assertEquals(false, isle.get(0));             // op 7: miss proves the eviction
        assertEquals(1, isle.extinctions());
        assertEquals(1, isle.residencies().size());
        assertEquals(7, isle.residencies().get(0).deathOp());
        assertEquals(isle.richness(), isle.immigrations() - isle.extinctions());
    }

    @Test
    @DisplayName("determinism and constructor contract")
    void determinismAndContract() {
        long[] results = new long[2];
        for (int run = 0; run < 2; run++) {
            CacheIsland isle = island(null);
            for (int k = 0; k < 30; k++) {
                isle.admit(k % 12);
                if (k % 4 == 0) isle.get(k % 12);
                if (k % 5 == 0) isle.sample();
            }
            isle.sample();
            results[run] = isle.extinctions() * 1_000_000L + isle.immigrations() * 1_000L
                    + isle.opCount();
        }
        assertEquals(results[0], results[1]);
        assertThrows(IllegalArgumentException.class,
                () -> new CacheIsland(new SegmentedLruCache(4, CacheGenome.of(5, 2)), 0));
    }
}
