package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Punnett squares and Mendelian ratios for the classroom seam (ADR-019) — the tools
 * for replaying the famous crosses: Mendel's peas, the blue Andalusian chicken
 * (incomplete dominance), the four chicken comb types (the classic 9:3:3:1 dihybrid),
 * and any cross a student writes as parent genotypes.
 *
 * <p>Genotypes are letter pairs per locus: {@code "Aa"} is one locus, {@code "AaBb"}
 * two, up to {@value #MAX_LOCI} (the square grows as 4&#x207F; cells — beyond three loci a
 * drawn square stops teaching anything). Both alleles of a locus must be the same
 * letter (case carries dominance: {@code A} dominant, {@code a} recessive). Under
 * complete dominance a phenotype shows the dominant trait when any dominant allele is
 * present; under incomplete dominance every genotype is its own phenotype (the blue
 * Andalusian: BB black, Bb blue, bb splash-white — the 1:2:1 that surprises
 * students who expect 3:1).</p>
 *
 * <p>Observed offspring counts can be graded against the expected ratio with the
 * standard &#x3C7;&#xB2; goodness-of-fit (df = classes &#x2212; 1) — Mendel's own seed-shape data
 * (5474 round : 1850 wrinkled) passes at &#x3C7;&#xB2; &#x2248; 0.26, and the oracle test pins that
 * historic number.</p>
 */
public final class MendelianGenetics {

    private MendelianGenetics() {}

    /** Loci cap — a 64-cell square is the largest that still reads as a picture. */
    public static final int MAX_LOCI = 3;

    /** &#x3C7;&#xB2; critical values at &#x3B1; = 0.05 for df 1..8 (index df−1). */
    public static final double[] CHI_SQUARE_CRITICAL = {
            3.841, 5.991, 7.815, 9.488, 11.070, 12.592, 14.067, 15.507 };

    public enum Dominance { COMPLETE, INCOMPLETE }

    /**
     * A completed cross: the gametes along each axis, the Punnett square itself
     * (cells are normalized offspring genotypes), and the genotype and phenotype
     * ratio maps (insertion-ordered by first appearance in the square).
     */
    public record Cross(String parent1, String parent2, Dominance dominance,
                        List<String> gametes1, List<String> gametes2,
                        String[][] square,
                        Map<String, Integer> genotypeCounts,
                        Map<String, Integer> phenotypeCounts) {}

    /** The &#x3C7;&#xB2; grade of observed offspring counts against an expected ratio. */
    public record RatioFit(double chiSquare, int df, double critical, boolean consistent) {}

    // ── The cross ─────────────────────────────────────────────────────────────

    public static Cross cross(String parent1, String parent2, Dominance dominance) {
        String[] loci1 = splitLoci(parent1);
        String[] loci2 = splitLoci(parent2);
        if (loci1.length != loci2.length) {
            throw new IllegalArgumentException("parents must have the same loci count");
        }
        for (int i = 0; i < loci1.length; i++) {
            if (Character.toLowerCase(loci1[i].charAt(0)) != Character.toLowerCase(loci2[i].charAt(0))) {
                throw new IllegalArgumentException("locus " + (i + 1) + " letters differ between parents");
            }
        }
        List<String> g1 = gametes(loci1);
        List<String> g2 = gametes(loci2);
        String[][] square = new String[g1.size()][g2.size()];
        Map<String, Integer> genotypes = new LinkedHashMap<>();
        Map<String, Integer> phenotypes = new LinkedHashMap<>();
        for (int r = 0; r < g1.size(); r++) {
            for (int c = 0; c < g2.size(); c++) {
                String genotype = combine(g1.get(r), g2.get(c));
                square[r][c] = genotype;
                genotypes.merge(genotype, 1, Integer::sum);
                phenotypes.merge(phenotype(genotype, dominance), 1, Integer::sum);
            }
        }
        return new Cross(parent1, parent2, dominance, g1, g2, square, genotypes, phenotypes);
    }

    /**
     * Phenotype of a normalized genotype: under COMPLETE dominance, each locus shows
     * its dominant letter if present ({@code "A_"}) else the recessive pair
     * ({@code "aa"}); under INCOMPLETE dominance the genotype is the phenotype.
     */
    public static String phenotype(String genotype, Dominance dominance) {
        if (dominance == Dominance.INCOMPLETE) return genotype;
        StringBuilder out = new StringBuilder();
        for (String locus : splitLoci(genotype)) {
            boolean hasDominant = Character.isUpperCase(locus.charAt(0))
                    || Character.isUpperCase(locus.charAt(1));
            char letter = Character.toLowerCase(locus.charAt(0));
            out.append(hasDominant ? Character.toUpperCase(letter) + "_" : "" + letter + letter);
        }
        return out.toString();
    }

    /**
     * Grade observed class counts against an expected ratio (same length, same order).
     * &#x3C7;&#xB2; = &#x3A3;(O&#x2212;E)&#xB2;/E with E = ratio&#x1D62;/&#x3A3;ratio &#xB7; N; df = classes &#x2212; 1 (&#x2264; 8 supported).
     */
    public static RatioFit ratioFit(long[] observed, double[] expectedRatio) {
        if (observed.length != expectedRatio.length || observed.length < 2) {
            throw new IllegalArgumentException("observed and ratio need equal length >= 2");
        }
        if (observed.length - 1 > CHI_SQUARE_CRITICAL.length) {
            throw new IllegalArgumentException("df > " + CHI_SQUARE_CRITICAL.length + " not supported");
        }
        long n = 0;
        double ratioSum = 0;
        for (int i = 0; i < observed.length; i++) {
            if (observed[i] < 0 || expectedRatio[i] <= 0) {
                throw new IllegalArgumentException("counts must be >= 0, ratio parts > 0");
            }
            n += observed[i];
            ratioSum += expectedRatio[i];
        }
        if (n == 0) throw new IllegalArgumentException("no offspring observed");
        double chi = 0;
        for (int i = 0; i < observed.length; i++) {
            double e = expectedRatio[i] / ratioSum * n;
            double d = observed[i] - e;
            chi += d * d / e;
        }
        int df = observed.length - 1;
        double critical = CHI_SQUARE_CRITICAL[df - 1];
        return new RatioFit(chi, df, critical, chi <= critical);
    }

    /** Convenience: grade observed counts against a cross's phenotype ratio, in its order. */
    public static RatioFit ratioFit(long[] observed, Cross cross) {
        double[] ratio = cross.phenotypeCounts().values().stream()
                .mapToDouble(Integer::doubleValue).toArray();
        return ratioFit(observed, ratio);
    }

    // ── Internals ─────────────────────────────────────────────────────────────

    private static String[] splitLoci(String genotype) {
        if (genotype == null || genotype.length() < 2 || genotype.length() % 2 != 0) {
            throw new IllegalArgumentException("genotype must be letter pairs, e.g. Aa or AaBb");
        }
        int loci = genotype.length() / 2;
        if (loci > MAX_LOCI) throw new IllegalArgumentException("at most " + MAX_LOCI + " loci");
        String[] out = new String[loci];
        for (int i = 0; i < loci; i++) {
            String pair = genotype.substring(i * 2, i * 2 + 2);
            char a = pair.charAt(0), b = pair.charAt(1);
            if (!Character.isLetter(a) || !Character.isLetter(b)
                    || Character.toLowerCase(a) != Character.toLowerCase(b)) {
                throw new IllegalArgumentException("locus '" + pair + "' must be two of the same letter");
            }
            out[i] = pair;
        }
        return out;
    }

    /** All gamete combinations, one allele per locus, in deterministic order. */
    private static List<String> gametes(String[] loci) {
        List<String> out = new ArrayList<>();
        int n = loci.length;
        for (int mask = 0; mask < (1 << n); mask++) {
            StringBuilder g = new StringBuilder();
            for (int i = 0; i < n; i++) {
                g.append(loci[i].charAt((mask >> (n - 1 - i)) & 1));
            }
            out.add(g.toString());
        }
        return out;
    }

    /** Combine two gametes into a normalized genotype (dominant allele written first). */
    private static String combine(String gamete1, String gamete2) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < gamete1.length(); i++) {
            char a = gamete1.charAt(i), b = gamete2.charAt(i);
            // Uppercase (dominant) first; ties keep order.
            if (Character.isLowerCase(a) && Character.isUpperCase(b)) {
                out.append(b).append(a);
            } else {
                out.append(a).append(b);
            }
        }
        return out.toString();
    }

    /** Human label helper for the famous presets, used by reports and the lab page. */
    public static String describe(Cross cross) {
        return String.format(Locale.ROOT, "%s × %s (%s dominance): %d×%d square",
                cross.parent1(), cross.parent2(),
                cross.dominance().name().toLowerCase(Locale.ROOT),
                cross.gametes1().size(), cross.gametes2().size());
    }
}
