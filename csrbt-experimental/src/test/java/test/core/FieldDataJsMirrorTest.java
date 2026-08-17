package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.FieldData;

import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.TimeUnit;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * The lab page's {@code parseCounts} against {@link FieldData#parseLines}, differentially, over a
 * random corpus — the pin for the claim {@code docs/ecology-lab.html} makes about itself.
 *
 * <p>The seventh-pass audit (item B) found that claim was false where it mattered most: the
 * RFC-4180 splitters were an exact mirror, but the surrounding bare-token logic was not.
 * {@code oak=5} — the shape {@link FieldData#toEcoLine} and the page's own "build .eco lines"
 * button emit — parsed in the page as a species literally <em>named</em> {@code oak=5} with count
 * 1, so a student round-tripping their own data through the page lost every count silently; a bare
 * number was auto-named {@code sp1}/{@code sp2}/… in the page and read as a species name in Java;
 * and every problem message was worded differently on the two sides. A comment cannot hold a
 * mirror in place. This does.</p>
 *
 * <h2>What "agree" means</h2>
 * <p>Field splits, problem strings (verbatim, including their subject and their wording) and the
 * count table's key order must be <b>identical</b>. Count values must be equal <em>as doubles</em>:
 * Java counts are {@code long} and JavaScript has no integer type wider than 2^53, so a count above
 * that is exact in the oracle and IEEE-754-rounded in the page. That is a property of the runtime,
 * not a disagreement about parsing — and the accept/reject decision, which is the part that could
 * silently corrupt data, is compared exactly (a count outside the signed 64-bit range is reported
 * as "not an integer" on both sides).</p>
 *
 * <h2>Why it can skip</h2>
 * <p>It drives the real page through {@code node}, so it needs {@code node} on the PATH and the
 * checked-in {@code docs/ecology-lab.html}. Where either is missing the test is skipped rather
 * than failed — a build host without node has not proven the mirror wrong. The JS is extracted
 * from the shipped file, never from a copy, so the page cannot drift away from what is tested.</p>
 */
@DisplayName("docs/ecology-lab.html parseCounts mirrors FieldData.parseLines")
class FieldDataJsMirrorTest {

    /** Shapes the audit named, plus everything that has ever gone wrong at a field boundary. */
    private static final String[] AWKWARD = {
        // the six divergent families from the audit's table
        "oak=5", "12", "0", "-5", "=5", "oak=",
        // the ordinary shapes
        "oak,5", "oak\t5", "oak 5", "great blue heron", "plotA,robin,6", "plain,7",
        // RFC-4180
        "\"oak, white\",12", "\"a \"\"quoted\"\" name\",4", "\"unterminated,5", "\"", "\"\"",
        "\"\",5", "a\"b,3", "\"a,b\"", "\"a,b\",", "\"multi\nline\",3",
        // separators at the edges
        "oak,", "oak,,5", "oak,5,", ",", ",,", ",5", "5,", ",5,", "a,b,c,d",
        "one,two,three,four,five",
        // whitespace, comments, CR
        "  spaced   name   9  ", "oak,5 # trailing comment", "# whole line comment", "", "   ",
        "\t", "oak=5#c", "oak\r", "oak,5\r", " ", "name 1,5", "oak white,3",
        // '=' corners
        "oak=+5", "oak=005", "oak==5", "=", "oak=1=2", "oak=5 maple=3", "data: pond oak=5",
        // number corners, including the Long boundary and non-ASCII decimal digits
        "+7", "-0", "9223372036854775807", "9223372036854775808",
        "oak,9223372036854775807", "oak,9223372036854775808", "١٢", "oak,١٢",
        "12.5", "oak5", "sp1,4\n7",
    };

    @Test
    @DisplayName("0 divergences over a random corpus, awkward shapes included")
    void thePageAgreesWithTheOracle() throws Exception {
        Path page = repoRoot().resolve("docs/ecology-lab.html");
        Assumptions.assumeTrue(Files.isRegularFile(page), "docs/ecology-lab.html not reachable");
        Path node = onPath("node");
        Assumptions.assumeTrue(node != null, "node is not on the PATH");

        List<String> corpus = corpus();
        Path work = Files.createTempDirectory("fielddata-mirror");
        try {
            Files.writeString(work.resolve("parse.mjs"),
                    extractParser(Files.readString(page, StandardCharsets.UTF_8))
                            + "\nexport { parseCounts, splitCsvLine };\n", StandardCharsets.UTF_8);
            Files.writeString(work.resolve("run.mjs"), DRIVER, StandardCharsets.UTF_8);
            Path in = work.resolve("corpus.txt");
            Path out = work.resolve("js.txt");
            try (var w = Files.newBufferedWriter(in, StandardCharsets.UTF_8)) {
                for (String rec : corpus) { w.write(json(rec)); w.newLine(); }
            }

            Process p = new ProcessBuilder(node.toString(), "run.mjs", "corpus.txt", "js.txt")
                    .directory(work.toFile()).redirectErrorStream(true).start();
            String log = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            assertTrue(p.waitFor(120, TimeUnit.SECONDS), "node did not finish: " + log);
            assertEquals(0, p.exitValue(), "node failed:\n" + log);

            List<String> js = Files.readAllLines(out, StandardCharsets.UTF_8).stream()
                    .filter(s -> !s.isEmpty()).toList();
            assertEquals(corpus.size(), js.size(), "one JS answer per corpus record");

            List<String> divergences = new ArrayList<>();
            int lines = 0, counts = 0, problems = 0;
            for (int i = 0; i < corpus.size(); i++) {
                String rec = corpus.get(i);
                FieldData.Parsed oracle = FieldData.parseLines(List.of(rec.split("\n", -1)));
                lines += rec.split("\n", -1).length;
                counts += oracle.counts().size();
                problems += oracle.problems().size();
                String expected = render(rec, oracle);
                if (!expected.equals(js.get(i))) {
                    divergences.add("input=" + json(rec) + "\n  java=" + expected + "\n  js  =" + js.get(i));
                }
            }
            assertTrue(divergences.isEmpty(),
                    () -> divergences.size() + " divergence(s) over " + corpus.size() + " records:\n"
                            + String.join("\n", divergences.subList(0, Math.min(8, divergences.size()))));
            // Non-vacuity: an all-blank corpus would also produce zero divergences.
            assertTrue(lines > 8_000 && counts > 1_000 && problems > 1_000,
                    "the corpus must actually exercise both sides: lines=" + lines
                            + " counts=" + counts + " problems=" + problems);
        } finally {
            try (Stream<Path> walk = Files.walk(work)) {
                for (Path q : walk.sorted(Comparator.reverseOrder()).toList()) Files.deleteIfExists(q);
            }
        }
    }

    // ── The corpus ──────────────────────────────────────────────────────────────────────

    /** Deterministic: the awkward shapes, then random multi-line records built from atoms. */
    private static List<String> corpus() {
        List<String> records = new ArrayList<>(Arrays.asList(AWKWARD));
        String[] atoms = {
            "oak", "maple", "12", "0", "-5", "=5", "oak=", "oak=5", "birch=0", ",", "\"",
            "\"oak, white\"", "a\"b", "5", "x", "sp1", "great blue heron", "#c", "",
            " ", "\t", "\r", "9223372036854775808", "١", " ", "oak white", "12.5",
        };
        String[] seps = { ",", "\t", " ", "", ",,", " , ", "\"" };
        Random rnd = new Random(20_260_817L);
        for (int i = 0; i < 4_000; i++) {
            StringBuilder rec = new StringBuilder();
            int lines = 1 + rnd.nextInt(4);
            for (int l = 0; l < lines; l++) {
                if (l > 0) rec.append('\n');
                int fields = 1 + rnd.nextInt(4);
                for (int f = 0; f < fields; f++) {
                    if (f > 0) rec.append(seps[rnd.nextInt(seps.length)]);
                    rec.append(atoms[rnd.nextInt(atoms.length)]);
                }
            }
            records.add(rec.toString());
        }
        return records;
    }

    // ── Rendering both sides into one comparable form ────────────────────────────────────

    /**
     * The oracle's answer as the JS driver writes its own: counts in first-seen order with each
     * value rendered as the {@code double} JavaScript would hold, the problems verbatim, and the
     * per-line field split. Rendering the count through {@code double} is the whole of the
     * "equal as doubles" allowance, and it is applied to the <em>Java</em> side, so a JS value
     * that is not the correctly-rounded double still fails.
     */
    private static String render(String record, FieldData.Parsed p) {
        StringBuilder sb = new StringBuilder("{\"counts\":[");
        boolean first = true;
        for (Map.Entry<String, Long> e : p.counts().entrySet()) {
            if (!first) sb.append(',');
            first = false;
            sb.append('[').append(json(e.getKey())).append(',').append(json(jsNumber(e.getValue()))).append(']');
        }
        sb.append("],\"problems\":[");
        for (int i = 0; i < p.problems().size(); i++) {
            if (i > 0) sb.append(',');
            sb.append(json(p.problems().get(i)));
        }
        sb.append("],\"fields\":[");
        String[] ls = record.split("\n", -1);
        for (int i = 0; i < ls.length; i++) {
            if (i > 0) sb.append(',');
            sb.append('[');
            String[] fs = splitFieldsLikeThePage(ls[i]);
            for (int k = 0; k < fs.length; k++) {
                if (k > 0) sb.append(',');
                sb.append(json(fs[k]));
            }
            sb.append(']');
        }
        return sb.append("]}").toString();
    }

    /**
     * The count as the JavaScript engine actually holds it, in decimal: the {@code long} widened
     * to {@code double} and printed exactly, which is what {@code Number.prototype.toFixed(0)}
     * prints on the other side. Below 2^53 that is the count itself; above it, the two sides
     * agree on the same rounded value rather than pretending JavaScript has 64-bit integers.
     */
    private static String jsNumber(long v) {
        return new java.math.BigDecimal((double) v).toBigInteger().toString();
    }

    /**
     * {@code FieldData.splitFields} is package-private, so the field column is re-derived here with
     * the identical algorithm. That is not a weaker check: any drift between this and the real
     * splitter changes the counts and problems columns, which come from the real one.
     */
    private static String[] splitFieldsLikeThePage(String line) {
        List<String> out = new ArrayList<>();
        StringBuilder cur = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (quoted) {
                if (c == '"' && i + 1 < line.length() && line.charAt(i + 1) == '"') { cur.append('"'); i++; }
                else if (c == '"') quoted = false;
                else cur.append(c);
            } else if (c == '"') quoted = true;
            else if (c == ',' || c == '\t') { out.add(cur.toString()); cur.setLength(0); }
            else cur.append(c);
        }
        out.add(cur.toString());
        return out.toArray(new String[0]);
    }

    // ── Plumbing ────────────────────────────────────────────────────────────────────────

    /** The page's parser, lifted out of the shipped HTML — never a copy kept beside it. */
    private static String extractParser(String html) {
        int start = html.indexOf("  function splitCsvLine(line) {");
        int end = html.indexOf("  const ecoName =");
        if (start < 0 || end < 0 || end <= start) {
            fail("could not find parseCounts in docs/ecology-lab.html — if the page was "
                    + "restructured, re-anchor this extraction rather than deleting the test");
        }
        return html.substring(start, end);
    }

    private static Path repoRoot() {
        Path here = Path.of("").toAbsolutePath();
        for (Path p = here; p != null; p = p.getParent()) {
            if (Files.isDirectory(p.resolve("docs")) && Files.isRegularFile(p.resolve("settings.gradle.kts"))) {
                return p;
            }
        }
        return here;
    }

    private static Path onPath(String exe) {
        String path = System.getenv("PATH");
        if (path == null) return null;
        for (String dir : path.split(java.io.File.pathSeparator)) {
            Path c = Path.of(dir).resolve(exe);
            if (Files.isExecutable(c)) return c;
        }
        return null;
    }

    /** {@code JSON.stringify}'s escaping, exactly, so the two renderings compare as text. */
    private static String json(String s) {
        StringBuilder sb = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            switch (ch) {
                case '"'      -> sb.append("\\\"");
                case '\\'     -> sb.append("\\\\");
                case '\b'     -> sb.append("\\b");
                case '\f'     -> sb.append("\\f");
                case '\n'     -> sb.append("\\n");
                case '\r'     -> sb.append("\\r");
                case '\t'     -> sb.append("\\t");
                default       -> {
                    if (ch < 0x20) sb.append(String.format("\\u%04x", (int) ch));
                    else sb.append(ch);
                }
            }
        }
        return sb.append('"').toString();
    }

    /** One record per line, JSON-encoded so a record may itself contain newlines. */
    private static final String DRIVER = """
            import { parseCounts, splitCsvLine } from "./parse.mjs";
            import { readFileSync, writeFileSync } from "node:fs";
            const text = readFileSync(process.argv[2], "utf8");
            const out = [];
            for (const rec of text.split("\\n")) {
              if (rec === "") continue;
              const input = JSON.parse(rec);
              const r = parseCounts(input);
              out.push(JSON.stringify({
                counts: r.order.map(k => [k, r.counts[k].toFixed(0)]),
                problems: r.problems,
                fields: input.split("\\n").map(l => splitCsvLine(l))
              }));
            }
            writeFileSync(process.argv[3], out.join("\\n") + "\\n");
            """;
}
