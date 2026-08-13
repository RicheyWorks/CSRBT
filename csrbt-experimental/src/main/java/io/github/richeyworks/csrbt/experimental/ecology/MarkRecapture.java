package io.github.richeyworks.csrbt.experimental.ecology;

/**
 * Mark–recapture population estimation (ADR-020) — the classic first field experiment
 * (the "bean lab"): mark M individuals, release them, later catch C and count how many
 * R carry marks. Two standard estimators:
 *
 * <ul>
 *   <li><b>Lincoln–Petersen:</b> N&#770; = MC/R — the intuitive proportion argument
 *       (marked fraction in the second sample estimates the marked fraction in the
 *       whole population). Undefined when R = 0 and biased for small samples.</li>
 *   <li><b>Chapman:</b> N&#770; = (M+1)(C+1)/(R+1) − 1 — the small-sample correction,
 *       defined even at R = 0, with the standard variance
 *       (M+1)(C+1)(M−R)(C−R) / ((R+1)²(R+2)) giving an approximate 95% interval.</li>
 * </ul>
 *
 * <p>Assumptions (state them in your report — graders look for this): the population
 * is closed between samples, marks are not lost, and marked individuals mix and are
 * caught with the same probability as unmarked ones.</p>
 */
public final class MarkRecapture {

    private MarkRecapture() {}

    /** Both estimates plus Chapman's approximate 95% confidence interval. */
    public record Estimate(long marked, long caught, long recaptured,
                           double lincolnPetersen, double chapman,
                           double low95, double high95) {}

    /**
     * Estimate population size from one mark–recapture pair.
     *
     * @param marked     M — individuals marked and released in the first sample
     * @param caught     C — individuals caught in the second sample
     * @param recaptured R — of those, how many carried marks (0 &le; R &le; min(M, C))
     */
    public static Estimate estimate(long marked, long caught, long recaptured) {
        if (marked <= 0 || caught <= 0) {
            throw new IllegalArgumentException("marked and caught must be positive");
        }
        if (recaptured < 0 || recaptured > Math.min(marked, caught)) {
            throw new IllegalArgumentException(
                    "recaptured must be in [0, min(marked, caught)]");
        }
        double lp = recaptured == 0 ? Double.POSITIVE_INFINITY
                : (double) marked * caught / recaptured;
        double chapman = (double) (marked + 1) * (caught + 1) / (recaptured + 1) - 1;
        double variance = (double) (marked + 1) * (caught + 1)
                * (marked - recaptured) * (caught - recaptured)
                / ((double) (recaptured + 1) * (recaptured + 1) * (recaptured + 2));
        double half = 1.96 * Math.sqrt(variance);
        return new Estimate(marked, caught, recaptured, lp, chapman,
                Math.max(0, chapman - half), chapman + half);
    }
}
