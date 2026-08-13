package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.EcologyFieldDay;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentExport;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentLab;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentSpec;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-019 — the classroom engine end to end: spec parsing (contract + honest problem
 * reporting), deterministic runs, hypothesis grading in all three verdicts, the export
 * bundle, and CSV round-tripping.
 */
@DisplayName("ExperimentLab — the classroom experiment engine")
class ExperimentLabTest {

    private static final List<String> SPEC = List.of(
            "name: unit test experiment",
            "keys: 60",
            "seed: 9",
            "window: 100",
            "factor: area 0.5",
            "factor: wind 1.2",
            "phase: calm uniform 600",
            "phase: storm hot 600 4 85",
            "phase: churny churn 400 60",
            "model: logistic 0.2 100 5 30",
            "model: hardyweinberg 25 50 25",
            "model: eulerlotka 1.0:0 1.0:2",
            "model: markrecapture 100 60 15",
            "cross: Rr x Rr observed 5474 1850",
            "cross: Bb x Bb incomplete",
            "data: siteA oak=3 fern=2 moss",
            "data: siteB oak=1 pine=4",
            "note: a general note",
            "note(calm): looked even all morning",
            "tree: mini (A,(B,C));",
            "expect: evenness(calm) > 0.9",
            "expect: evenness(storm) > 0.9",          // will be refuted
            "expect: richness(nowhere) > 1",          // ungradeable: unknown community
            "expect: jaccard(siteA, siteB) <= 0.5",   // entered data: 1 shared / 4 union
            "expect: evenness(calm) is very-even",    // qualitative band
            "expect: braycurtis(calm, siteA) > 0.1"); // ungradeable: phase vs dataset

    @Test
    @DisplayName("spec parsing: everything lands, factors build the environment")
    void specParses() {
        ExperimentSpec spec = ExperimentSpec.parse(SPEC);
        assertEquals("unit test experiment", spec.name());
        assertEquals(3, spec.phases().size());
        assertEquals(4, spec.models().size());
        assertEquals(2, spec.crosses().size());
        assertEquals(6, spec.expectations().size());
        assertEquals(2, spec.datasets().size());
        assertEquals(2, spec.notes().size());
        assertEquals(1, spec.trees().size());
        assertEquals(0, spec.problems().size());
        assertEquals(0.5, spec.environment().area(), 1e-9);
        assertEquals(1.2, spec.environment().wind(), 1e-9);
        // The data bus: tally form parsed into ordered counts.
        assertEquals(3L, spec.datasets().get(0).counts().get("oak"));
        assertEquals(1L, spec.datasets().get(0).counts().get("moss"));
        // The note target survived; the general note has none.
        assertEquals("calm", spec.notes().get(1).about());
        assertEquals(List.of("A", "B", "C"), spec.trees().get(0).tree().leaves());
        // Qualitative expectation carries its word, numeric ones carry null.
        assertEquals("very-even", spec.expectations().get(4).word());
        assertEquals("is", spec.expectations().get(4).op());
        assertEquals(null, spec.expectations().get(0).word());
    }

    @Test
    @DisplayName("bad spec lines become reported problems, never guesses or crashes")
    void badLinesReported() {
        ExperimentSpec spec = ExperimentSpec.parse(List.of(
                "phase: a uniform 100",
                "phase: a uniform 100",               // duplicate name
                "phase: b wobbly 100",                // unknown kind
                "factor: gravity 2",                  // unknown factor
                "model: nonsense 1 2 3",              // unknown model
                "cross: Aa y Aa",                     // bad separator
                "expect: magic(a) > 1",               // unknown metric
                "expect: evenness(a) is sparkly",     // not a band word
                "data: onlylabel",                    // no counts
                "data: a oak=1",                      // collides with phase name
                "note(ghost): hello",                 // unknown target
                "tree: broken (A,(B);",               // unbalanced parens
                "just some prose"));                  // no directive
        assertEquals(2, spec.phases().size());   // both "a" phases parse; the dup is flagged
        assertEquals(12, spec.problems().size());
        // ... and the spec still runs.
        EcologyFieldDay.Session s = ExperimentLab.run(spec);
        assertTrue(s.report().contains("⚠ spec:"));
    }

    @Test
    @DisplayName("byte-determinism: same spec, same report, same JSON")
    void determinism() {
        EcologyFieldDay.Session a = ExperimentLab.run(ExperimentSpec.parse(SPEC));
        EcologyFieldDay.Session b = ExperimentLab.run(ExperimentSpec.parse(SPEC));
        assertEquals(a.report(), b.report());
        assertEquals(a.json(), b.json());
    }

    @Test
    @DisplayName("all three verdicts appear: CONFIRMED, REFUTED, UNGRADEABLE")
    void verdicts() {
        EcologyFieldDay.Session s = ExperimentLab.run(ExperimentSpec.parse(SPEC));
        assertTrue(s.report().contains("✅ CONFIRMED"));
        assertTrue(s.report().contains("❌ REFUTED"));
        assertTrue(s.report().contains("⚠ UNGRADEABLE"));
        assertTrue(s.json().contains("\"verdict\": \"CONFIRMED\""));
        assertTrue(s.json().contains("\"verdict\": \"REFUTED\""));
        assertTrue(s.json().contains("\"verdict\": \"UNGRADEABLE\""));
        // The qualitative hypothesis grades against the band and shows its word.
        assertTrue(s.report().contains("→ \"very-even\")"));
        assertTrue(s.json().contains("\"observed\": \"very-even\""));
        // Entered-vs-entered grades; phase-vs-entered is honestly refused.
        assertTrue(s.report().contains("jaccard(siteA, siteB) <= 0.5"));
        assertTrue(s.report().contains("cannot compare a simulated phase to an entered dataset"));
    }

    @Test
    @DisplayName("survivorship hypothesis without a census is UNGRADEABLE, not guessed")
    void survivorshipNeedsCensus() {
        EcologyFieldDay.Session s = ExperimentLab.run(ExperimentSpec.parse(List.of(
                "phase: calm uniform 200",
                "expect: survivorship is type1")));
        assertTrue(s.report().contains("⚠ UNGRADEABLE"));
        assertTrue(s.report().contains("no census"));
    }

    @Test
    @DisplayName("entered data and notes and trees land in the report and the exports")
    void enteredDataInReport() {
        Map<String, String> files = ExperimentLab.runWithExports(ExperimentSpec.parse(SPEC));
        String report = files.get("report.txt");
        assertTrue(report.contains("ENTERED DATA · siteA"));
        assertTrue(report.contains("siteA ↔ siteB: Jaccard 0.25"));
        assertTrue(report.contains("FIELD NOTEBOOK"));
        assertTrue(report.contains("[calm] looked even all morning"));
        assertTrue(report.contains("TREE THINKING"));
        assertTrue(report.contains("└─ C"));
        assertTrue(files.get("data.csv").contains("siteA,oak,3"));
        assertTrue(files.get("notes.csv").contains("calm,looked even all morning"));
        assertTrue(files.get("trees.csv").contains("(A,(B,C));"));
        // Mark–recapture hand oracle rides through the theory bench.
        assertTrue(report.contains("Lincoln–Petersen N̂=400.0"));
    }

    @Test
    @DisplayName("session JSON: balanced, all classroom stations present")
    void jsonSchema() {
        String json = ExperimentLab.run(ExperimentSpec.parse(SPEC)).json();
        for (String key : new String[]{ "\"meadow\"", "\"phases\"", "\"models\"",
                "\"crosses\"", "\"hypotheses\"", "\"square\"", "\"stats\"",
                "\"entered\"", "\"notes\"", "\"trees\"", "\"labels\"", "\"root\"" }) {
            assertTrue(json.contains(key), "missing " + key);
        }
        assertEquals(json.chars().filter(c -> c == '{').count(),
                json.chars().filter(c -> c == '}').count());
        assertEquals(json.chars().filter(c -> c == '[').count(),
                json.chars().filter(c -> c == ']').count());
    }

    @Test
    @DisplayName("the export bundle: report, session, CSVs, and printable HTML — all present, all consistent")
    void exportBundle() {
        Map<String, String> files = ExperimentLab.runWithExports(ExperimentSpec.parse(SPEC));
        for (String name : new String[]{ "report.txt", "session.json", "phases.csv",
                "hypotheses.csv", "model-series.csv", "crosses.csv", "punnett.csv",
                "data.csv", "notes.csv", "trees.csv", "report.html" }) {
            assertTrue(files.containsKey(name), "missing export " + name);
        }
        // phases.csv: header + one row per phase.
        assertEquals(4, files.get("phases.csv").strip().split("\n").length);
        // hypotheses.csv carries the verdicts.
        assertTrue(files.get("hypotheses.csv").contains("CONFIRMED"));
        assertTrue(files.get("hypotheses.csv").contains("REFUTED"));
        // punnett.csv: 4 cells for each 2×2 cross.
        assertEquals(1 + 8, files.get("punnett.csv").strip().split("\n").length);
        // The HTML report is self-contained and carries the verdict styling.
        String html = files.get("report.html");
        assertTrue(html.startsWith("<!DOCTYPE html>"));
        assertTrue(html.contains("verdict-REFUTED"));
        assertTrue(html.contains("<table>"));
        // Deterministic bundle.
        assertEquals(files, ExperimentLab.runWithExports(ExperimentSpec.parse(SPEC)));
    }

    @Test
    @DisplayName("CSV quoting round-trips fields with commas and quotes")
    void csvRoundTrip() {
        String field = "brayCurtis(a, b) said \"hi\"";
        String encoded = ExperimentExport.csv(field);
        assertArrayEquals(new String[]{ field, "plain" },
                ExperimentExport.splitCsv(encoded + ",plain"));
    }
}
