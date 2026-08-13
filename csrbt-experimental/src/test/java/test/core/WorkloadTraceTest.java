package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.EcologyFieldDay;
import io.github.richeyworks.csrbt.experimental.ecology.WorkloadTrace;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Trace replay — parsing contract (aliases, honest skip counting), byte-determinism,
 * schema sanity, graceful station skipping, and the discriminating check: a trace with
 * a mid-stream regime shift must show its sharpest window-to-window turnover at the
 * shift, not elsewhere.
 */
@DisplayName("WorkloadTrace — your workload as an ecosystem")
class WorkloadTraceTest {

    /** Deterministic synthetic trace: 40 keys, hot set {1,2,3} then {30,31,32}. */
    private static List<String> shiftTrace() {
        List<String> lines = new ArrayList<>();
        for (int k = 0; k < 40; k++) lines.add("add," + k);
        int[] hotA = { 1, 2, 3 }, hotB = { 30, 31, 32 };
        for (int i = 0; i < 600; i++) {
            int[] hot = i < 300 ? hotA : hotB;
            int key = (i % 10) < 7 ? hot[i % 3] : (i * 7) % 40;
            lines.add("search," + key);
        }
        return lines;
    }

    @Test
    @DisplayName("parser: aliases accepted, junk counted as skipped — never guessed at")
    void parserContract() {
        WorkloadTrace.Parsed p = WorkloadTrace.parse(List.of(
                "put,5", "GET 5", "del 5", "  # comment", "", "add,7",
                "garbage", "frobnicate,5", "add,notanumber"));
        assertEquals(4, p.ops().size());
        assertEquals(3, p.skipped());
    }

    @Test
    @DisplayName("byte-determinism: same trace, same report and JSON")
    void determinism() {
        EcologyFieldDay.Session a = WorkloadTrace.run(shiftTrace(), "t.csv");
        EcologyFieldDay.Session b = WorkloadTrace.run(shiftTrace(), "t.csv");
        assertEquals(a.report(), b.report());
        assertEquals(a.json(), b.json());
    }

    @Test
    @DisplayName("the drift station finds the regime shift: peak turnover at the boundary")
    void driftFindsTheShift() {
        EcologyFieldDay.Session s = WorkloadTrace.run(shiftTrace(), "shift.csv");
        assertTrue(s.report().contains("THE DRIFT"));

        // 640 ops, window = max(32, 640/24) = 32 → shift at op ~340 → window ~10.
        // Extract the bray array from the JSON and locate its argmax.
        String json = s.json();
        String bray = json.substring(json.indexOf("\"bray\": [") + 9);
        bray = bray.substring(0, bray.indexOf(']'));
        String[] parts = bray.split(",");
        // Skip the arrival transition (windows 0-1 are the 40-adds warmup turning into
        // traffic — a real turnover, but not the one under test).
        int argmax = 2;
        for (int i = 3; i < parts.length; i++) {
            if (Double.parseDouble(parts[i]) > Double.parseDouble(parts[argmax])) argmax = i;
        }
        assertTrue(argmax >= 7 && argmax <= 12,
                "peak turnover should sit at the regime boundary, found index " + argmax);
    }

    @Test
    @DisplayName("hardening: an empty trace is a valid session, not a crash")
    void emptyTrace() {
        EcologyFieldDay.Session s = WorkloadTrace.run(
                List.of("# nothing here", "", "   "), "empty.csv");
        assertTrue(s.report().contains("0 ops replayed"));
        String json = s.json();
        assertTrue(json.contains("\"meadow\""));
        assertEquals(json.chars().filter(c -> c == '{').count(),
                json.chars().filter(c -> c == '}').count());
        assertEquals(json.chars().filter(c -> c == '[').count(),
                json.chars().filter(c -> c == ']').count());
    }

    @Test
    @DisplayName("hardening: hostile labels are JSON-escaped, never emitted raw")
    void labelEscaping() {
        String hostile = "we\"ird\\pa\tth\n.csv";
        EcologyFieldDay.Session s = WorkloadTrace.run(List.of("add,1"), hostile);
        String json = s.json();
        assertTrue(json.contains("we\\\"ird\\\\pa\\tth\\n.csv"), "label must arrive escaped");
        assertEquals(json.chars().filter(c -> c == '{').count(),
                json.chars().filter(c -> c == '}').count());
        assertEquals("x", WorkloadTrace.escapeJson("x"));
        assertEquals("\\u0001", WorkloadTrace.escapeJson(String.valueOf((char) 1)));
    }

    @Test
    @DisplayName("hardening: a 58k-op, 8k-key trace completes at instrument speed (the O(S·m) fix)")
    void stressScale() {
        List<String> lines = new ArrayList<>();
        for (int k = 0; k < 8000; k++) lines.add("add," + k);
        for (int i = 0; i < 50_000; i++) {
            lines.add("search," + ((i % 10) < 7 ? i % 40 : (i * 31) % 8000));
        }
        EcologyFieldDay.Session s = WorkloadTrace.run(lines, "big.csv");
        // Before the rarefaction fix this took ~half a minute of pure math; the suite
        // timeout is the enforcement — here we assert the result, not the clock.
        String json = s.json();
        assertTrue(json.contains("\"richness\": 8000"));
        assertTrue(json.contains("\"rarefaction\""));
        assertEquals(json.chars().filter(c -> c == '{').count(),
                json.chars().filter(c -> c == '}').count());
    }

    @Test
    @DisplayName("schema: meadow phase carries chao1 + rarefaction; JSON balanced; stations skip gracefully")
    void schemaAndGracefulSkips() {
        EcologyFieldDay.Session s = WorkloadTrace.run(shiftTrace(), "shift.csv");
        String json = s.json();
        for (String key : new String[]{ "\"meadow\"", "\"phases\"", "\"chao1\"",
                "\"rarefaction\"", "\"drift\"", "\"grid\"" }) {
            assertTrue(json.contains(key), "missing " + key);
        }
        assertEquals(json.chars().filter(c -> c == '{').count(),
                json.chars().filter(c -> c == '}').count());
        assertEquals(json.chars().filter(c -> c == '[').count(),
                json.chars().filter(c -> c == ']').count());

        // Adds-only micro-trace: demography and growth stations must simply be absent.
        List<String> tiny = new ArrayList<>();
        for (int k = 0; k < 10; k++) tiny.add("add," + k);
        EcologyFieldDay.Session t = WorkloadTrace.run(tiny, "tiny.csv");
        assertTrue(t.json().contains("\"meadow\""));
        assertTrue(!t.json().contains("\"demography\""));
        assertTrue(!t.json().contains("\"growth\""));
        assertEquals(t.json().chars().filter(c -> c == '{').count(),
                t.json().chars().filter(c -> c == '}').count());
    }
}
