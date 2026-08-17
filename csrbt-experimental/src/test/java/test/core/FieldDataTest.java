package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.FieldData;
import io.github.richeyworks.csrbt.experimental.ecology.MarkRecapture;
import io.github.richeyworks.csrbt.experimental.ecology.PhyloTree;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-020 — the data bus (both entry forms, honest problems, round-trips),
 * mark–recapture against the hand oracle, and Newick phylogenies.
 */
@DisplayName("FieldData, MarkRecapture, PhyloTree — the student data seam")
class FieldDataTest {

    // ── FieldData ─────────────────────────────────────────────────────────────

    @Test
    @DisplayName("token form: name=count plus bare-name tally marks, in first-seen order")
    void tokens() {
        FieldData.Parsed p = FieldData.parseTokens("oak=12 maple=5 peck peck birch peck");
        assertEquals(Map.of("oak", 12L, "maple", 5L, "peck", 3L, "birch", 1L), p.counts());
        assertEquals(List.of("oak", "maple", "peck", "birch"),
                List.copyOf(p.counts().keySet()));
        assertEquals(0, p.problems().size());
    }

    @Test
    @DisplayName("bad tokens are reported, never guessed — and the rest still counts")
    void tokenProblems() {
        FieldData.Parsed p = FieldData.parseTokens("oak=12 fern=zero moss=0 =7 elm");
        assertEquals(Map.of("oak", 12L, "elm", 1L), p.counts());
        assertEquals(3, p.problems().size());
    }

    @Test
    @DisplayName("table form: CSV, TSV, 'name count', and bare lines all land in one table")
    void tableForm() {
        FieldData.Parsed p = FieldData.parseLines(List.of(
                "robin,34", "wren\t5", "sparrow 12", "great blue heron",
                "# a comment", "", "robin,6"));
        assertEquals(34L + 6L, p.counts().get("robin"));
        assertEquals(5L, p.counts().get("wren"));
        assertEquals(12L, p.counts().get("sparrow"));
        assertEquals(1L, p.counts().get("great-blue-heron"));
        assertEquals(0, p.problems().size());
    }

    @Test
    @DisplayName("table problems: zero counts and empty names are flagged")
    void tableProblems() {
        FieldData.Parsed p = FieldData.parseLines(List.of("robin,0", ",5"));
        assertEquals(0, p.counts().size());
        assertEquals(2, p.problems().size());
    }

    @Test
    @DisplayName("toEcoLine round-trips through parseTokens byte-for-byte")
    void ecoLineRoundTrip() {
        FieldData.Parsed p = FieldData.parseTokens("cattail=18 duckweed=44 frogbit");
        String line = FieldData.toEcoLine("pondA", p.counts());
        assertEquals("data: pondA cattail=18 duckweed=44 frogbit", line);
        FieldData.Parsed again = FieldData.parseTokens(line.substring("data: pondA ".length()));
        assertEquals(p.counts(), again.counts());
    }

    @Test
    @DisplayName("toCsv quotes names that need it")
    void csvExport() {
        String csv = FieldData.toCsv("site", Map.of("a,b", 3L));
        assertEquals("site,\"a,b\",3\n", csv);
    }

    @Test
    @DisplayName("toCsv round-trips through parseLines — quoted names and the dataset column")
    void csvRoundTrip() {
        LinkedHashMap<String, Long> counts = new LinkedHashMap<>();
        counts.put("oak, white", 12L);
        counts.put("maple", 5L);
        counts.put("say \"ash\"", 2L);
        String csv = FieldData.toCsv("plotA", counts);

        FieldData.Parsed back = FieldData.parseLines(List.of(csv.split("\n")));
        assertEquals(List.of(), back.problems(),
                "the tool must be able to read its own export (audit 2026-08-17, item 4)");
        assertEquals(counts, back.counts());
        assertEquals(List.copyOf(counts.keySet()), List.copyOf(back.counts().keySet()),
                "first-seen order survives the round trip");
    }

    @Test
    @DisplayName("a quoted comma inside a name is one field, not a malformed line")
    void quotedNamesParse() {
        FieldData.Parsed p = FieldData.parseLines(List.of(
                "\"oak, white\",12", "\"a \"\"quoted\"\" name\",4", "plain,7"));
        assertEquals(0, p.problems().size());
        assertEquals(12L, p.counts().get("oak, white"));
        assertEquals(4L, p.counts().get("a \"quoted\" name"));
        assertEquals(7L, p.counts().get("plain"));
    }

    @Test
    @DisplayName("the dataset column is optional: name,count and dataset,name,count both land")
    void datasetColumnIsOptional() {
        FieldData.Parsed p = FieldData.parseLines(List.of(
                "robin,34", "plotA,robin,6", "plotA,wren,5"));
        assertEquals(0, p.problems().size());
        assertEquals(40L, p.counts().get("robin"), "the label is dropped; the counts merge");
        assertEquals(5L, p.counts().get("wren"));
        // A two-field row is ALWAYS name,count — never re-read as dataset,name — so the
        // format stays unambiguous with the export shape supported.
        assertEquals(2, p.counts().size());
    }

    @Test
    @DisplayName("real user error is still reported, never guessed — including inside export rows")
    void malformedRowsAreStillReported() {
        FieldData.Parsed p = FieldData.parseLines(List.of(
                "robin,0",            // non-positive count
                ",5",                 // empty name
                "wren,x",             // count is not an integer
                "oak,",               // empty count
                "plotA,wren,x",       // export row with a bad count
                "plotA,,5",           // export row with an empty name
                "a,b,c,d"));          // too many fields for any shape
        assertEquals(0, p.counts().size(), "nothing malformed was guessed into the table");
        assertEquals(7, p.problems().size());
        assertTrue(p.problems().get(6).contains("dataset,name,count"),
                "the too-many-fields message names every accepted shape: " + p.problems().get(6));
    }

    // ── MarkRecapture ─────────────────────────────────────────────────────────

    @Test
    @DisplayName("hand oracle: M=100 C=60 R=15 → LP=400 exactly, Chapman=384.0625 exactly")
    void markRecaptureOracle() {
        MarkRecapture.Estimate e = MarkRecapture.estimate(100, 60, 15);
        assertEquals(400.0, e.lincolnPetersen(), 1e-9);
        assertEquals(101.0 * 61 / 16 - 1, e.chapman(), 1e-9);
        assertTrue(e.low95() < e.chapman() && e.chapman() < e.high95());
        // Chapman variance by hand: 101·61·85·45 / (16²·17)
        double var = 101.0 * 61 * 85 * 45 / (256.0 * 17);
        assertEquals(e.chapman() - 1.96 * Math.sqrt(var), e.low95(), 1e-9);
    }

    @Test
    @DisplayName("R=0: Lincoln–Petersen undefined (infinite), Chapman still finite")
    void zeroRecaptures() {
        MarkRecapture.Estimate e = MarkRecapture.estimate(50, 40, 0);
        assertTrue(Double.isInfinite(e.lincolnPetersen()));
        assertEquals(51.0 * 41 - 1, e.chapman(), 1e-9);
    }

    @Test
    @DisplayName("mark–recapture contracts: bad counts throw")
    void markRecaptureContracts() {
        assertThrows(IllegalArgumentException.class, () -> MarkRecapture.estimate(0, 10, 0));
        assertThrows(IllegalArgumentException.class, () -> MarkRecapture.estimate(10, 10, 11));
        assertThrows(IllegalArgumentException.class, () -> MarkRecapture.estimate(10, 10, -1));
    }

    // ── PhyloTree ─────────────────────────────────────────────────────────────

    @Test
    @DisplayName("Newick: leaves in order, depth, internal labels, branch lengths")
    void newickParses() {
        PhyloTree t = PhyloTree.parse("(A:0.1,(B:0.2,C:0.3)BC:0.4)root;");
        assertEquals(List.of("A", "B", "C"), t.leaves());
        assertEquals(3, t.depth());
        assertEquals("root", t.root().name());
        assertEquals(0.4, t.root().children().get(1).length(), 1e-9);
        assertEquals("BC", t.root().children().get(1).name());
    }

    @Test
    @DisplayName("newick() round-trips: parse(newick()) gives the same tree text")
    void newickRoundTrip() {
        String in = "(Porifera,(Cnidaria,((Mollusca,Annelida),(Arthropoda,(Echinodermata,Chordata)))));";
        PhyloTree t = PhyloTree.parse(in);
        assertEquals(7, t.leaves().size());
        assertEquals(in, t.newick());
        assertEquals(t.newick(), PhyloTree.parse(t.newick()).newick());
    }

    @Test
    @DisplayName("ascii cladogram: one line per node, all taxa present")
    void asciiRender() {
        String art = PhyloTree.parse("(A,(B,C));").ascii();
        for (String taxon : new String[]{ "A", "B", "C" }) {
            assertTrue(art.contains("─ " + taxon), "missing " + taxon + " in:\n" + art);
        }
        assertEquals(5, art.strip().split("\n").length);   // root + A + inner + B + C
    }

    @Test
    @DisplayName("malformed Newick throws with a reason — never a guessed tree")
    void newickContracts() {
        assertThrows(IllegalArgumentException.class, () -> PhyloTree.parse("(A,(B,C);"));
        assertThrows(IllegalArgumentException.class, () -> PhyloTree.parse("(A,B))extra;"));
        assertThrows(IllegalArgumentException.class, () -> PhyloTree.parse("(A,);"));
        assertThrows(IllegalArgumentException.class, () -> PhyloTree.parse("(A:x,B);"));
        assertThrows(IllegalArgumentException.class, () -> PhyloTree.parse("  ;"));
    }
}
