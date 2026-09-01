package io.github.richeyworks.csrbt.experimental;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The lab console's own contract, in-process (ADR-116): one JSON line per verb, refusals with
 * a code, the one refused directive, and a run that grades. The heavier evidence -- the shipped
 * protocol reproducing the shipped session through the gateway, the arena and the controller
 * against determinism, exports on disk -- is {@code CSRBT/tools/verify/verify_lab.py}; this is
 * the floor under it.
 */
final class LabConsoleTest {

    private static final String SPEC = "name: floor\nkeys: 40\nseed: 3\nwindow: 50\n"
            + "phase: a uniform 200\nphase: b hot 200 4 90\n"
            + "expect: evenness(a) > 0.9\nexpect: hill1(nowhere) < 3\nbogus\n";

    private static String b64(String s) {
        return Base64.getEncoder().encodeToString(s.getBytes(StandardCharsets.UTF_8));
    }

    private static LabConsole console() {
        return new LabConsole(new PrintStream(new ByteArrayOutputStream(), true, StandardCharsets.UTF_8));
    }

    @Test
    void lintCountsAndNamesProblems() {
        String r = console().answer("lint " + b64(SPEC));
        assertTrue(r.contains("\"phases\":2,") && r.contains("\"expectations\":2,"), r);
        assertTrue(r.contains("\"problems\":[\"bogus  (no directive)\"]"), r);
    }

    @Test
    void runGradesAndReportsTheSession() {
        String r = console().answer("run " + b64(SPEC));
        assertTrue(r.startsWith("{\"ok\":true,\"name\":\"floor\""), r);
        assertTrue(r.contains("CONFIRMED") && r.contains("UNGRADEABLE"), "graded, and the untestable one named");
        assertTrue(r.contains("\"session\":\"{") && r.contains("\"files\":[{\"name\":\"report.txt\""), r);
    }

    @Test
    void theOneRefusedDirective() {
        String r = console().answer("run " + b64("name: x\nDWC: plot /etc/passwd\n"));
        assertTrue(r.startsWith("{\"ok\":false,\"code\":\"invalid_argument\",\"why\":\"dwc: lines are refused"), r);
        assertTrue(console().answer("run notbase64!").contains("\"invalid_argument\""));
        assertTrue(console().answer("battle NOPE 1000 1").contains("workload must be one of"));
        assertTrue(console().answer("battle MIXED 5 1").contains("\"invalid_argument\""), "ops below the floor");
        assertEquals("{\"ok\":false,\"code\":\"not_found\",\"why\":\"unknown verb zap\"}", console().answer("zap"));
    }

    @Test
    void arenaAndControllerAreDeterministicPerSeed() {
        LabConsole c = console();
        String a = c.answer("adapt 300 1500 42");
        assertEquals(a, c.answer("adapt 300 1500 42"));
        assertTrue(a.contains("\"from\":\"RED_BLACK\""), a);
        String b1 = c.answer("battle SEQUENTIAL 300 9"), b2 = c.answer("battle SEQUENTIAL 300 9");
        assertEquals(pinned(b1), pinned(b2), "everything but wall-clock time, and the rank it decides, is pinned");
        assertTrue(c.answer("observe").contains("\"battles\":2,\"adapts\":2,"));
    }

    /** The per-strategy facts, without time and without the rank time decides, in a fixed order. */
    private static String pinned(String battle) {
        String body = battle.substring(battle.indexOf("[{") + 2, battle.lastIndexOf("}]"));
        String[] rows = body.replaceAll("\"timeMs\":[0-9.]+,", "").replaceAll("\"rank\":[0-9]+,", "")
                .split("\\},\\{");
        java.util.Arrays.sort(rows);
        return String.join("|", rows);
    }

    @Test
    void exportWritesTheBundle(@TempDir Path dir) throws Exception {
        String r = console().answer("export " + b64(SPEC) + " " + dir.resolve("out"));
        assertTrue(r.contains("\"name\":\"workbook.xlsx\"") && r.contains("\"name\":\"report.pptx\""), r);
        assertTrue(Files.exists(dir.resolve("out").resolve("session.json")));
        assertTrue(Files.size(dir.resolve("out").resolve("report.html")) > 0);
    }
}
