package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.EcologyRecorder;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Contract characterization (bug audit 2026-08-12): the recorder's {@code Bounded}
 * Javadoc used to claim the demography registers "grow with distinct keys." They do not.
 * This pins the true, now-documented behaviour so the contract stays honest: on a stream
 * that churns a SINGLE distinct key, the genuinely-bounded structures stay flat, while
 * {@code lifespans} grows with observed deaths and {@code populationSeries} grows with
 * closed windows — neither bounded by distinct keys. A caller in the long-running seam
 * must drain/reconstruct rather than assume these self-cap.
 */
@DisplayName("EcologyRecorder — what is bounded, and what deliberately is not")
class EcologyRecorderBoundingTest {

    @Test
    @DisplayName("one churned key: tally/birthOps/windows bounded; lifespans & series grow with events")
    void boundedVsUnbounded() {
        int windowOps = 1000, maxWindows = 4, cycles = 50_000;
        EcologyRecorder rec = new EcologyRecorder(windowOps, maxWindows);
        for (int i = 0; i < cycles; i++) {
            rec.recordAdd(1, 0);      // same key hash every time
            rec.recordRemove(1, 0);
        }
        long ops = 2L * cycles;

        // Genuinely bounded: one distinct key, no survivors, windows capped.
        assertEquals(1, rec.cumulativeAbundance().size(), "cumulative is bounded by distinct keys");
        assertEquals(0, rec.aliveBirthOps().size(), "no key is alive at the end");
        assertEquals(maxWindows, rec.closedWindows().size(), "closed windows are capped");

        // Deliberately unbounded (now documented): grow with events, not distinct keys.
        assertEquals(cycles, rec.lifespans().size(),
                "one lifespan per remove of a live key — grows with deaths, not distinct keys");
        assertEquals((int) (ops / windowOps), rec.populationSeries().size(),
                "one population sample per closed window — retained past window eviction");
        assertTrue(rec.lifespans().size() > rec.cumulativeAbundance().size(),
                "the demography register is not bounded by distinct keys");
    }
}
