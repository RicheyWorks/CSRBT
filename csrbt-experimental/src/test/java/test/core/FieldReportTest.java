package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.CommunityMetrics;
import io.github.richeyworks.csrbt.experimental.ecology.FieldReport;
import io.github.richeyworks.csrbt.experimental.ecology.LifeTable;
import io.github.richeyworks.csrbt.experimental.ecology.LogisticGrowth;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The interpretation layer — every reading pinned at its documented threshold
 * boundaries (inclusive side checked explicitly), plus section assembly and
 * determinism. Wording is part of the contract: same number, same sentence.
 */
@DisplayName("FieldReport — plain-English readings with fixed thresholds")
class FieldReportTest {

    @Test
    @DisplayName("evenness reading: all four bands, boundaries on the documented side")
    void evennessBands() {
        assertTrue(FieldReport.evennessReading(1.0).startsWith("very even"));
        assertTrue(FieldReport.evennessReading(FieldReport.EVEN_VERY).startsWith("very even"));
        assertTrue(FieldReport.evennessReading(0.70).startsWith("moderately even"));
        assertTrue(FieldReport.evennessReading(FieldReport.EVEN_MODERATE).startsWith("moderately even"));
        assertTrue(FieldReport.evennessReading(0.40).startsWith("uneven"));
        assertTrue(FieldReport.evennessReading(FieldReport.EVEN_UNEVEN).startsWith("uneven"));
        assertTrue(FieldReport.evennessReading(0.10).startsWith("strongly dominated"));
    }

    @Test
    @DisplayName("dispersion reading: regular / random / clumped at the documented cuts")
    void dispersionBands() {
        assertTrue(FieldReport.dispersionReading(0.3).startsWith("regular"));
        assertTrue(FieldReport.dispersionReading(FieldReport.DISP_REGULAR).startsWith("random"));
        assertTrue(FieldReport.dispersionReading(1.0).startsWith("random"));
        assertTrue(FieldReport.dispersionReading(FieldReport.DISP_CLUMPED).startsWith("random"));
        assertTrue(FieldReport.dispersionReading(3.0).startsWith("clumped"));
    }

    @Test
    @DisplayName("overlap and turnover readings: bands at the documented cuts")
    void overlapAndTurnoverBands() {
        assertTrue(FieldReport.overlapReading(0.9).startsWith("high overlap"));
        assertTrue(FieldReport.overlapReading(FieldReport.OVERLAP_HIGH).startsWith("high overlap"));
        assertTrue(FieldReport.overlapReading(0.5).startsWith("partial overlap"));
        assertTrue(FieldReport.overlapReading(0.1).startsWith("little overlap"));

        assertTrue(FieldReport.turnoverReading(0.1).startsWith("nearly identical"));
        assertTrue(FieldReport.turnoverReading(FieldReport.TURNOVER_LOW).startsWith("nearly identical"));
        assertTrue(FieldReport.turnoverReading(0.4).startsWith("moderate turnover"));
        assertTrue(FieldReport.turnoverReading(0.9).startsWith("major turnover"));
    }

    @Test
    @DisplayName("survivorship readings name the type and a biological example")
    void survivorshipWording() {
        assertTrue(FieldReport.survivorshipReading(LifeTable.SurvivorshipType.TYPE_I)
                .contains("old age"));
        assertTrue(FieldReport.survivorshipReading(LifeTable.SurvivorshipType.TYPE_II)
                .contains("age-independent"));
        assertTrue(FieldReport.survivorshipReading(LifeTable.SurvivorshipType.TYPE_III)
                .contains("early mortality"));
    }

    @Test
    @DisplayName("page-occupancy reading: tight / healthy / sparse at the documented cuts")
    void pageOccupancyBands() {
        assertTrue(FieldReport.pageOccupancyReading(0.95).startsWith("tightly packed"));
        assertTrue(FieldReport.pageOccupancyReading(FieldReport.FILL_TIGHT).startsWith("tightly packed"));
        assertTrue(FieldReport.pageOccupancyReading(0.7).startsWith("healthy fill"));
        assertTrue(FieldReport.pageOccupancyReading(FieldReport.FILL_HEALTHY).startsWith("healthy fill"));
        assertTrue(FieldReport.pageOccupancyReading(0.5).startsWith("sparse pages"));
    }

    @Test
    @DisplayName("Levins reading states both numbers and the agreement verdict")
    void levinsWording() {
        String agree = FieldReport.levinsReading(0.70, 0.66);
        assertTrue(agree.contains("70%") && agree.contains("66%"));
        assertTrue(agree.contains("matches"));
        String disagree = FieldReport.levinsReading(0.0, 1.0);
        assertTrue(disagree.contains("disagrees"));
    }

    @Test
    @DisplayName("growth reading covers growing, declining, and flat")
    void growthWording() {
        assertTrue(FieldReport.growthReading(new LogisticGrowth.Fit(0.01, 500, 5, 0.99))
                .contains("growing"));
        assertTrue(FieldReport.growthReading(new LogisticGrowth.Fit(-0.01, 500, 400, 0.99))
                .contains("declining"));
        assertTrue(FieldReport.growthReading(new LogisticGrowth.Fit(0.0, 500, 400, 1.0))
                .contains("flat"));
    }

    @Test
    @DisplayName("community section narrates a skewed community as dominated")
    void communitySectionNarration() {
        Map<Integer, Long> skewed = Map.of(1, 900L, 2, 40L, 3, 30L, 4, 20L, 5, 10L);
        String section = FieldReport.communitySection("TEST PLOT", skewed);
        assertTrue(section.contains("TEST PLOT"));
        assertTrue(section.contains("5 distinct keys"));
        assertTrue(section.contains("1000 touches"));
        assertTrue(section.contains("dominated") || section.contains("uneven"),
                "a 90%-one-key community must not read as even: " + section);
    }

    @Test
    @DisplayName("spatial section flags a clumped grid")
    void spatialSectionNarration() {
        String section = FieldReport.spatialSection("GRID", new long[]{ 50, 0, 0, 0, 1 });
        assertTrue(section.contains("clumped"));
        assertTrue(section.contains("51 individuals"));
    }

    @Test
    @DisplayName("demography section reports cohort, ages, and the type sentence")
    void demographySectionNarration() {
        LifeTable t = LifeTable.fromLifespans(List.of(
                new LifeTable.Lifespan(1, 0, 30), new LifeTable.Lifespan(2, 0, 30),
                new LifeTable.Lifespan(3, 0, 29), new LifeTable.Lifespan(4, 0, 1)), 3);
        String section = FieldReport.demographySection("COHORT", t);
        assertTrue(section.contains("Cohort of 4"));
        assertTrue(section.contains("Type I")); // 3 of 4 die old together
    }

    @Test
    @DisplayName("readings are deterministic: same input, same sentence")
    void determinism() {
        assertEquals(FieldReport.evennessReading(0.42), FieldReport.evennessReading(0.42));
        Map<Integer, Long> m = Map.of(1, 3L, 2, 9L);
        assertEquals(FieldReport.communitySection("X", m), FieldReport.communitySection("X", m));
        assertEquals(
                FieldReport.abundanceModelReading(CommunityMetrics.bestFit(m)),
                FieldReport.abundanceModelReading(CommunityMetrics.bestFit(m)));
    }
}
