package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.EcologyRecorder;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentLab;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentSpec;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probe (bug audit 2026-08-17, finding 28): {@code drift.csv} labelled its transitions
 * {@code (i+1)->(i+2)} over the recorder's RETAINED window list. The recorder caps
 * retention at 64 and evicts the oldest, so on any run that closes more than 64 windows
 * the labels were off by the eviction count — row "1->2" on a 101-window run actually
 * described windows 38→39, and a student charting the export read end-of-run drift as
 * opening drift. The Bray–Curtis values themselves were always right; only the label
 * column lied, which is worse, because nothing looked wrong.
 */
@DisplayName("Drift export — transition labels are absolute window numbers")
class ExperimentDriftLabelProbeTest {

    /** 60 seeded keys + 5000 ops at 50 ops/window = 101 closed windows, 64 retained. */
    private static final List<String> SPEC = List.of(
            "name: drift label probe",
            "keys: 60",
            "seed: 3",
            "window: 50",
            "phase: long uniform 5000");

    @Test
    @DisplayName("the recorder reports how many windows eviction dropped")
    void recorderCountsEvictedWindows() {
        EcologyRecorder rec = new EcologyRecorder(50, 64);
        for (int op = 0; op < 5060; op++) rec.recordSearch(op % 60, 1);

        assertEquals(101, rec.closedWindowCount(), "101 windows close in 5060 ops of 50");
        assertEquals(64, rec.closedWindows().size(), "only 64 are retained");
        assertEquals(37, rec.evictedWindowCount(), "the other 37 were evicted");
    }

    @Test
    @DisplayName("with 37 windows evicted, drift.csv starts at window 38, not window 1")
    void driftLabelsSurviveEviction() {
        Map<String, String> files = ExperimentLab.runWithExports(ExperimentSpec.parse(SPEC));
        String[] rows = files.get("drift.csv").strip().split("\n");

        assertEquals("transition,brayCurtis", rows[0]);
        assertEquals(64, rows.length, "header + 63 transitions between 64 retained windows");
        assertTrue(rows[1].startsWith("38->39,"),
                "the first retained transition is windows 38→39, got: " + rows[1]);
        assertTrue(rows[rows.length - 1].startsWith("100->101,"),
                "the last transition is windows 100→101, got: " + rows[rows.length - 1]);
        // No label may repeat or reappear from the truncated head of the run.
        assertTrue(files.get("drift.csv").indexOf("\n1->2,") < 0,
                "window 1 was dropped; nothing may be labelled 1->2");
    }

    @Test
    @DisplayName("the report says plainly that earlier windows were dropped")
    void reportStatesTheTruncation() {
        String report = ExperimentLab.runWithExports(ExperimentSpec.parse(SPEC)).get("report.txt");
        assertTrue(report.contains("windows 1–37 were dropped, so this series starts at window 38"),
                "a truncated series must say so:\n" + report);
    }

    @Test
    @DisplayName("a run short enough to keep every window still labels from 1")
    void shortRunUnchanged() {
        Map<String, String> files = ExperimentLab.runWithExports(ExperimentSpec.parse(List.of(
                "name: short run",
                "keys: 60",
                "seed: 3",
                "window: 100",
                "phase: brief uniform 600")));
        String[] rows = files.get("drift.csv").strip().split("\n");
        assertTrue(rows[1].startsWith("1->2,"), "nothing was evicted; got: " + rows[1]);
        assertTrue(!files.get("report.txt").contains("were dropped"),
                "no eviction, so no truncation note");
    }
}
