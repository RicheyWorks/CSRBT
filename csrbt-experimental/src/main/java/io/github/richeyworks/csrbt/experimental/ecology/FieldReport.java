package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.List;
import java.util.Map;

/**
 * Plain-English readings of the ecology instruments — the interpretation layer for a
 * reader who thinks in biology, not in index values. Every method here takes a number
 * one of the instruments produced and returns the sentence a field-course TA would say
 * about it, using fixed documented thresholds so the wording is as deterministic as the
 * numbers (same input, same sentence — testable at every boundary).
 *
 * <p>The thresholds are conventions, not fitted values, and are declared as public
 * constants so a report always says which line it graded against. The full-report
 * builders at the bottom assemble a narrated section per instrument.</p>
 */
public final class FieldReport {

    private FieldReport() {}

    // ── Thresholds (documented conventions) ───────────────────────────────────

    /** J&#x2032; at or above this reads "very even". */
    public static final double EVEN_VERY = 0.85;
    /** J&#x2032; at or above this reads "moderately even". */
    public static final double EVEN_MODERATE = 0.55;
    /** J&#x2032; at or above this reads "uneven"; below it, "strongly dominated". */
    public static final double EVEN_UNEVEN = 0.30;

    /** Dispersion index below this reads "regular"; above {@link #DISP_CLUMPED}, "clumped". */
    public static final double DISP_REGULAR = 0.7;
    /** Dispersion index above this reads "clumped"; between, "random". */
    public static final double DISP_CLUMPED = 1.5;

    /** Pianka overlap at or above this reads "high overlap". */
    public static final double OVERLAP_HIGH = 0.8;
    /** Pianka overlap at or above this reads "partial overlap"; below, "little overlap". */
    public static final double OVERLAP_PARTIAL = 0.4;

    /** Bray–Curtis at or below this reads "nearly identical". */
    public static final double TURNOVER_LOW = 0.2;
    /** Bray–Curtis at or below this reads "moderate turnover"; above, "major turnover". */
    public static final double TURNOVER_MODERATE = 0.6;

    /** Saturation at or above this reads "full house". */
    public static final double SATURATION_FULL = 0.999;
    /** Saturation at or above this reads "crowded"; below, "room to spare". */
    public static final double SATURATION_CROWDED = 0.7;

    /** |p* &#x2212; occupancy| at or below this reads "model matches observation". */
    public static final double LEVINS_AGREEMENT = 0.15;

    /** Page fill at or above this reads "tightly packed". */
    public static final double FILL_TIGHT = 0.85;
    /** Page fill at or above this reads "healthy"; below, "sparse". */
    public static final double FILL_HEALTHY = 0.6;

    // ── Single-number readings ────────────────────────────────────────────────

    /** How even is the community? (Pielou J&#x2032;.) */
    public static String evennessReading(double j) {
        if (j >= EVEN_VERY)     return "very even — no key dominates the community";
        if (j >= EVEN_MODERATE) return "moderately even — some keys are busier than others";
        if (j >= EVEN_UNEVEN)   return "uneven — a few hot keys carry most of the traffic";
        return "strongly dominated — a handful of keys get nearly all the attention";
    }

    /** Effective species count (any Hill number), said plainly. */
    public static String effectiveSpeciesReading(double hill, int richness) {
        return String.format(
                "of %d keys present, the community behaves like about %.1f equally-common ones",
                richness, hill);
    }

    /** Spatial pattern from a dispersion index (variance-to-mean or Morisita). */
    public static String dispersionReading(double index) {
        if (index < DISP_REGULAR)  return "regular — individuals spaced out more evenly than chance";
        if (index <= DISP_CLUMPED) return "random — no detectable spatial pattern (Poisson-like)";
        return "clumped — individuals bunched into patches";
    }

    /** Niche overlap between two communities (Pianka O). */
    public static String overlapReading(double o) {
        if (o >= OVERLAP_HIGH)    return "high overlap — the two draw on nearly the same resources";
        if (o >= OVERLAP_PARTIAL) return "partial overlap — shared ground, but distinct preferences";
        return "little overlap — effectively separate niches";
    }

    /** Composition change between two communities (Bray–Curtis dissimilarity). */
    public static String turnoverReading(double bc) {
        if (bc <= TURNOVER_LOW)      return "nearly identical — the community barely changed";
        if (bc <= TURNOVER_MODERATE) return "moderate turnover — a noticeable shift in who is common";
        return "major turnover — this is substantially a different community";
    }

    /** Survivorship curve type, in words. */
    public static String survivorshipReading(LifeTable.SurvivorshipType type) {
        return switch (type) {
            case TYPE_I   -> "Type I — most individuals survive to old age, then die together "
                    + "(think large mammals)";
            case TYPE_II  -> "Type II — a steady, age-independent death rate (think songbirds)";
            case TYPE_III -> "Type III — heavy early mortality, but survivors persist "
                    + "(think oysters: many spawned, few make it)";
        };
    }

    /** Island fullness (richness / capacity). */
    public static String saturationReading(double saturation) {
        if (saturation >= SATURATION_FULL)    return "full house — every new arrival displaces a resident";
        if (saturation >= SATURATION_CROWDED) return "crowded — most of the habitat is occupied";
        return "room to spare — the island is below capacity";
    }

    /** Levins prediction vs the directly measured occupancy. */
    public static String levinsReading(double predicted, double observed) {
        String verdict = Math.abs(predicted - observed) <= LEVINS_AGREEMENT
                ? "the model matches what we actually see"
                : "the model disagrees with observation — the event record is sparse, or "
                        + "transitions are happening between samples";
        return String.format(
                "Levins predicts %.0f%% patch occupancy from the event record; we observe %.0f%% — %s",
                predicted * 100, observed * 100, verdict);
    }

    /** Logistic growth fit, in words. */
    public static String growthReading(LogisticGrowth.Fit fit) {
        String trend;
        if (Math.abs(fit.r()) < 1e-9)  trend = "flat — no net growth detected";
        else if (fit.r() > 0)          trend = String.format(
                "growing at r = %.4f per op toward a ceiling", fit.r());
        else                           trend = String.format(
                "declining at r = %.4f per op", fit.r());
        return String.format(
                "the population is %s; carrying capacity ≈ %.0f keys (fit R² = %.3f)",
                trend, fit.carryingCapacity(), fit.rSquared());
    }

    /** B+tree page fill factor, in words. */
    public static String pageOccupancyReading(double fill) {
        if (fill >= FILL_TIGHT)   return "tightly packed pages — bulk or sequential history, little slack";
        if (fill >= FILL_HEALTHY) return "healthy fill — near the ~69% (ln 2) steady state of random insertion";
        return "sparse pages — a split-heavy history left slack in the leaves";
    }

    /** Chao1 estimate vs observed richness, in words. */
    public static String richnessEstimateReading(int observed, double chao1) {
        double missing = chao1 - observed;
        if (missing < 0.5) {
            return String.format(
                    "the survey looks complete — Chao1 estimates ≈ %.0f keys and we saw all %d",
                    chao1, observed);
        }
        return String.format(
                "we saw %d keys, but Chao1 estimates ≈ %.0f — roughly %.0f rare keys likely went unseen",
                observed, chao1, missing);
    }

    /** Rank–abundance model verdict, in words. */
    public static String abundanceModelReading(CommunityMetrics.ModelFit fit) {
        return switch (fit.best()) {
            case GEOMETRIC -> "the rank–abundance curve follows a geometric series — classic "
                    + "niche preemption, where each species takes a fixed share of what is left";
            case BROKEN_STICK -> "the rank–abundance curve fits MacArthur's broken stick — "
                    + "resources divided about as evenly as random splitting allows";
            case UNIFORM -> "the rank–abundance curve is essentially flat — every species is "
                    + "about equally common";
        };
    }

    // ── Section builders (one narrated block per instrument) ──────────────────

    /** Community section: diversity of an abundance distribution, narrated. */
    public static <T> String communitySection(String title, Map<T, Long> abundance) {
        int s = CommunityMetrics.richness(abundance);
        long n = CommunityMetrics.total(abundance);
        double h = CommunityMetrics.shannon(abundance);
        double j = CommunityMetrics.pielouEvenness(abundance);
        double hill1 = CommunityMetrics.hillNumber(abundance, 1);
        CommunityMetrics.ModelFit fit = CommunityMetrics.bestFit(abundance);
        StringBuilder sb = new StringBuilder();
        sb.append("── ").append(title).append(" ──\n");
        sb.append(String.format("  %d distinct keys, %d touches recorded.%n", s, n));
        sb.append(String.format("  Diversity H' = %.3f, evenness J' = %.2f: %s.%n",
                h, j, evennessReading(j)));
        sb.append("  ").append(effectiveSpeciesReading(hill1, s)).append(".\n");
        sb.append("  ").append(abundanceModelReading(fit)).append(".\n");
        sb.append("  ").append(richnessEstimateReading(s, CommunityMetrics.chao1(abundance)))
          .append(".\n");
        return sb.toString();
    }

    /** Demography section: a life table, narrated. */
    public static String demographySection(String title, LifeTable table) {
        StringBuilder sb = new StringBuilder();
        sb.append("── ").append(title).append(" ──\n");
        sb.append(String.format("  Cohort of %d completed lives; mean age %.0f ops, median %.0f.%n",
                table.cohortSize(), table.lifeExpectancy(), table.medianAge()));
        sb.append("  Survivorship: ").append(survivorshipReading(table.survivorshipType()))
          .append(".\n");
        return sb.toString();
    }

    /** Spatial section: quadrat counts, narrated. */
    public static String spatialSection(String title, long[] quadratCounts) {
        double id = RangeQuadrats.indexOfDispersion(quadratCounts);
        double im = RangeQuadrats.morisita(quadratCounts);
        StringBuilder sb = new StringBuilder();
        sb.append("── ").append(title).append(" ──\n");
        sb.append(String.format(
                "  %d individuals across %d quadrats (%.0f%% occupied).%n",
                RangeQuadrats.total(quadratCounts), quadratCounts.length,
                RangeQuadrats.occupancy(quadratCounts) * 100));
        sb.append(String.format("  Variance/mean = %.2f, Morisita = %.2f: %s.%n",
                id, im, dispersionReading(id)));
        return sb.toString();
    }

    /** Metapopulation section: the ensemble community, narrated. */
    public static String metapopulationSection(String title, EnsembleCommunity<?> eco) {
        StringBuilder sb = new StringBuilder();
        sb.append("── ").append(title).append(" ──\n");
        sb.append(String.format(
                "  %d local extinctions and %d recolonizations across %d surveys.%n",
                eco.extinctions(), eco.recolonizations(), eco.samples()));
        sb.append("  ").append(levinsReading(eco.levinsEquilibrium(), eco.occupancy()))
          .append(".\n");
        sb.append(String.format(
                "  %d strategy species serving (H' = %.3f); redundancy %.1f copies per role.%n",
                eco.strategyRichness(), eco.strategyDiversity(), eco.functionalRedundancy()));
        return sb.toString();
    }

    /** Lineage section: the snapshot record, narrated. */
    public static String lineageSection(String title, SnapshotLineage<?> lineage) {
        StringBuilder sb = new StringBuilder();
        sb.append("── ").append(title).append(" ──\n");
        sb.append(String.format(
                "  %d generations on record (%d retained).%n",
                lineage.generations(), lineage.retained().size()));
        sb.append(String.format(
                "  Average turnover %.0f%% of the community per generation.%n",
                lineage.turnoverPerGeneration() * 100));
        sb.append(String.format(
                "  Inheritance: %.0f%% of keys survive a generation, but only %.0f%% of the"
                        + " physical nodes%n    — the gap is the price of path copying"
                        + " (every edit rewrites its ancestors).%n",
                lineage.meanContentInheritance() * 100,
                lineage.meanStructuralInheritance() * 100));
        return sb.toString();
    }

    /** Island section: the cache habitat, narrated. */
    public static String islandSection(String title, CacheIsland isle) {
        StringBuilder sb = new StringBuilder();
        sb.append("── ").append(title).append(" ──\n");
        sb.append(String.format(
                "  %d residents of capacity %d: %s.%n",
                isle.richness(), isle.capacity(), saturationReading(isle.saturation())));
        sb.append(String.format(
                "  Lifetime record: %d arrivals, %d departures; last interval turnover %.1f.%n",
                isle.immigrations(), isle.extinctions(), isle.lastIntervalTurnover()));
        if (isle.residencies().size() >= 2) {
            LifeTable t = isle.residenceLifeTable(Math.min(6,
                    Math.max(3, isle.residencies().size() / 3)));
            sb.append("  Residence pattern: ")
              .append(survivorshipReading(t.survivorshipType())).append(".\n");
        }
        return sb.toString();
    }
}
