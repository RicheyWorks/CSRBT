package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics;
import io.github.richeyworks.csrbt.experimental.ecology.DarwinCore;
import io.github.richeyworks.csrbt.experimental.ecology.DarwinCore.Archive;
import io.github.richeyworks.csrbt.experimental.ecology.DarwinCore.Quantity;

import io.github.richeyworks.csrbt.experimental.ecology.EcologyFieldDay;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentLab;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentSpec;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-107 — the Darwin Core reader: the seam between the kit's field pages and its analysis engine.
 * The rule under test throughout is that {@code organismQuantityType} is load-bearing: cover and
 * individuals are different quantities and the richness estimators may only see one of them.
 */
@DisplayName("DarwinCore — reading the standard the field pages already emit")
class DarwinCoreTest {

    /** A GBIF-shaped download: tab-separated, individual counts. */
    private static final List<String> GBIF = List.of(
            "occurrenceID\tscientificName\tindividualCount\teventDate\trecordedBy\t"
            + "decimalLatitude\tdecimalLongitude\tcoordinateUncertaintyInMeters\tbasisOfRecord",
            "obs:1\tPinus jeffreyi\t12\t2026-06-21\tM Linton\t39.0968\t-120.1122\t30\tHumanObservation",
            "obs:2\tAbies concolor\t7\t2026-06-21\tM Linton\t39.0968\t-120.1122\t30\tHumanObservation",
            "obs:3\tPinus jeffreyi\t3\t2026-06-21\tM Linton\t39.0968\t-120.1122\t30\tHumanObservation");

    /** A relevé-shaped export from the kit's own page: comma-separated, percent cover. */
    private static final List<String> RELEVE = List.of(
            "scientificName,organismQuantity,organismQuantityType,eventDate,recordedBy,"
            + "decimalLatitude,decimalLongitude,coordinateUncertaintyInMeters,"
            + "minimumElevationInMeters,identificationQualifier,associatedMedia,locality",
            "Abies concolor,45,% cover,2026-06-21,M Linton,39.0968,-120.1122,30,2073,cf.,"
            + "tahoe-westshore-a42a4047.png,Lake Tahoe west shore",
            "Pinus jeffreyi,30,% cover,2026-06-21,M Linton,39.0968,-120.1122,30,2073,cf.,"
            + "tahoe-westshore-a42a4047.png,Lake Tahoe west shore",
            "Calocedrus decurrens,8,% cover,2026-06-21,M Linton,39.0968,-120.1122,30,2073,aff.,"
            + "tahoe-westshore-a42a4047.png,Lake Tahoe west shore");

    @Test
    @DisplayName("a GBIF download reads as individuals, and repeated taxa sum")
    void gbifCounts() {
        Archive a = DarwinCore.read(GBIF);
        assertEquals(0, a.problems().size(), a.problems().toString());
        assertEquals(Quantity.INDIVIDUALS, a.quantityKind());
        assertEquals(3, a.records().size());
        assertEquals(15L, a.abundance().get("Pinus jeffreyi"));   // 12 + 3
        assertEquals(7L, a.abundance().get("Abies concolor"));
        assertEquals(2, a.abundance().size());
    }

    @Test
    @DisplayName("the site travels with the records: coordinates, uncertainty, date, observer")
    void siteIsCarried() {
        DarwinCore.Site s = DarwinCore.read(GBIF).site();
        assertEquals(39.0968, s.latitude(), 1e-9);
        assertEquals(-120.1122, s.longitude(), 1e-9);
        assertEquals(30.0, s.coordinateUncertaintyM(), 1e-9);
        assertEquals("2026-06-21", s.eventDate());
        assertEquals("M Linton", s.recordedBy());
    }

    @Test
    @DisplayName("a relevé export reads as COVER, not as a headcount")
    void releveIsCover() {
        Archive a = DarwinCore.read(RELEVE);
        assertEquals(0, a.problems().size(), a.problems().toString());
        assertEquals(Quantity.COVER, a.quantityKind());
        assertEquals(45.0, a.cover().get("Abies concolor"), 1e-9);
        assertEquals(2073.0, a.site().elevationM(), 1e-9);
        assertEquals("Lake Tahoe west shore", a.site().locality());
    }

    @Test
    @DisplayName("THE RULE: cover data is refused by abundance(), because Chao1 does not model it")
    void coverRefusesAbundance() {
        Archive cover = DarwinCore.read(RELEVE);
        IllegalStateException e = assertThrows(IllegalStateException.class, cover::abundance);
        assertTrue(e.getMessage().contains("Chao1"), e.getMessage());
        // ...and the reverse is refused too, so neither can be reached by accident.
        assertThrows(IllegalStateException.class, () -> DarwinCore.read(GBIF).cover());
    }

    @Test
    @DisplayName("proportional indices still work on cover, through the narrow door")
    void proportionalWorksOnCover() {
        Archive a = DarwinCore.read(RELEVE);
        var w = a.proportionalWeights();
        assertEquals(10_000L, w.values().stream().mapToLong(Long::longValue).sum());
        // 45 : 30 : 8 of 83 total -> the same proportions, scaled.
        assertEquals(Math.round(45.0 / 83.0 * 10_000), w.get("Abies concolor"));
        // Shannon on cover proportions is legitimate and agrees with a hand computation.
        double n = 83.0;
        double hand = 0;
        for (double c : new double[]{ 45, 30, 8 }) hand -= (c / n) * Math.log(c / n);
        assertEquals(hand, CommunityMetrics.shannon(w), 1e-3);
    }

    @Test
    @DisplayName("an absent coordinate stays absent — it never becomes zero at Null Island")
    void emptyCoordinateStaysEmpty() {
        Archive a = DarwinCore.read(List.of(
                "scientificName,individualCount,decimalLatitude,decimalLongitude",
                "Pinus jeffreyi,4,,"));
        assertEquals(0, a.problems().size(), a.problems().toString());
        assertNull(a.records().get(0).latitude());
        assertNull(a.site().latitude());
    }

    @Test
    @DisplayName("identificationQualifier surfaces the hedged identifications")
    void uncertainty() {
        Archive a = DarwinCore.read(RELEVE);
        assertEquals(List.of("Abies concolor", "Pinus jeffreyi", "Calocedrus decurrens"),
                a.uncertainTaxa());
        assertTrue(a.records().get(0).uncertain());
    }

    @Test
    @DisplayName("cover vocabularies are recognised: percent, Braun-Blanquet, Domin, Daubenmire")
    void coverVocabularies() {
        for (String t : new String[]{ "% cover", "percentageOfCover", "braunBlanquetScale",
                "Domin scale", "Daubenmire cover class" }) {
            assertEquals(Quantity.COVER, DarwinCore.classify(t), t);
        }
        for (String t : new String[]{ "individuals", "individualCount", "stems", "specimens" }) {
            assertEquals(Quantity.INDIVIDUALS, DarwinCore.classify(t), t);
        }
        assertEquals(Quantity.UNKNOWN, DarwinCore.classify("biomass in grams"));
    }

    @Test
    @DisplayName("mixing cover and counts in one file is refused, not pooled")
    void mixedQuantitiesRefused() {
        Archive a = DarwinCore.read(List.of(
                "scientificName,organismQuantity,organismQuantityType",
                "Abies concolor,45,% cover",
                "Pinus jeffreyi,12,individuals"));
        assertEquals(Quantity.COVER, a.quantityKind());
        assertEquals(1, a.records().size());
        assertTrue(a.problems().get(0).contains("cannot be pooled"), a.problems().toString());
    }

    @Test
    @DisplayName("bad rows are reported and skipped; the rest of the file still reads")
    void badRowsReported() {
        Archive a = DarwinCore.read(List.of(
                "scientificName,individualCount,decimalLatitude",
                ",5,39.1",                      // no name
                "Abies concolor,many,39.1",     // quantity not a number
                "Pinus jeffreyi,-2,39.1",       // negative
                "Pinus jeffreyi,4,not-a-number",// bad coordinate, row still counts
                "Abies concolor,6,39.1"));
        assertEquals(2, a.records().size());
        assertEquals(4, a.problems().size(), a.problems().toString());
        assertNull(a.records().get(0).latitude());
        assertEquals(6L, a.abundance().get("Abies concolor"));
    }

    @Test
    @DisplayName("two sites in one file is a reported problem — they must not be pooled silently")
    void twoSitesFlagged() {
        Archive a = DarwinCore.read(List.of(
                "scientificName,individualCount,decimalLatitude,decimalLongitude",
                "Abies concolor,5,39.0968,-120.1122",
                "Abies concolor,5,39.5000,-120.9000"));
        assertTrue(a.problems().stream().anyMatch(p -> p.contains("more than one site")),
                a.problems().toString());
    }

    @Test
    @DisplayName("a table that is not Darwin Core is refused by name, not misread")
    void notDarwinCore() {
        Archive a = DarwinCore.read(List.of("name,count", "oak,3"));
        assertEquals(0, a.records().size());
        assertTrue(a.problems().get(0).contains("not a Darwin Core"), a.problems().toString());
        assertFalse(a.problems().isEmpty());
    }

    // ── The seam, end to end (ADR-107) ────────────────────────────────────────

    @Test
    @DisplayName("a dwc: line makes a Darwin Core file a dataset, and cover withholds Chao1")
    void dwcDirectiveEndToEnd(@TempDir Path dir) throws Exception {
        Path cover = dir.resolve("cover.csv");
        Files.write(cover, RELEVE);
        Path counts = dir.resolve("counts.tsv");
        Files.write(counts, GBIF);

        ExperimentSpec spec = ExperimentSpec.parse(List.of(
                "name: seam test",
                "dwc: veg " + cover.toString().replace("\\", "/"),
                "dwc: stems " + counts.toString().replace("\\", "/"),
                "expect: richness(veg) <= 3",
                "expect: turnover(veg, stems) is major"));
        assertEquals(0, spec.problems().size(), spec.problems().toString());
        assertEquals(2, spec.dwcSources().size());

        EcologyFieldDay.Session s = ExperimentLab.run(spec);
        // The cover archive is narrated as cover, and the richness estimator is withheld.
        assertTrue(s.report().contains("(3 kinds, cover)"), s.report());
        assertTrue(s.report().contains("Chao1 and rarefaction withheld"), s.report());
        // The counts archive keeps its Chao1 -- the distinction is real, not cosmetic.
        assertTrue(s.report().contains("(2 kinds, 22 records)"), s.report());  // 12 + 3 + 7
        // The hedged identifications are surfaced from identificationQualifier.
        assertTrue(s.report().contains("identification hedged for"), s.report());
        // A hypothesis may address a dwc label exactly like any other dataset.
        assertTrue(s.report().contains("richness(veg) <= 3"), s.report());
        assertTrue(s.report().contains("CONFIRMED"), s.report());
        // JSON marks which quantity each dataset holds, and nulls chao1 for cover.
        assertTrue(s.json().contains("\"quantity\": \"cover\""), s.json());
        assertTrue(s.json().contains("\"chao1\": null"), s.json());
    }

    @Test
    @DisplayName("an unreadable dwc: path is reported, and the rest of the run still happens")
    void missingDwcFileReported() {
        EcologyFieldDay.Session s = ExperimentLab.run(ExperimentSpec.parse(List.of(
                "name: missing file",
                "dwc: ghost /no/such/file/anywhere.csv",
                "data: real oak=3 fern=2")));
        assertTrue(s.report().contains("cannot read"), s.report());
        assertTrue(s.report().contains("ENTERED DATA · real"), s.report());
    }

    @Test
    @DisplayName("a record with no quantity at all counts as one occurrence")
    void bareOccurrence() {
        Archive a = DarwinCore.read(List.of("scientificName", "Ursus americanus"));
        assertEquals(Quantity.INDIVIDUALS, a.quantityKind());
        assertEquals(1L, a.abundance().get("Ursus americanus"));
    }
}
