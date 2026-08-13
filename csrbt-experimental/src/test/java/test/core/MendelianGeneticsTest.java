package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.MendelianGenetics;
import io.github.richeyworks.csrbt.experimental.ecology.MendelianGenetics.Cross;
import io.github.richeyworks.csrbt.experimental.ecology.MendelianGenetics.Dominance;
import io.github.richeyworks.csrbt.experimental.ecology.MendelianGenetics.RatioFit;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-019 Punnett squares — the famous crosses as oracles: Mendel's monohybrid and
 * dihybrid ratios, his actual 1866 seed-shape counts, the blue Andalusian chicken
 * (incomplete dominance), and the four chicken comb types.
 */
@DisplayName("MendelianGenetics — Punnett squares and the famous ratios")
class MendelianGeneticsTest {

    @Test
    @DisplayName("monohybrid Aa × Aa: genotypes 1:2:1, phenotypes 3:1")
    void monohybrid() {
        Cross c = MendelianGenetics.cross("Aa", "Aa", Dominance.COMPLETE);
        assertEquals(Map.of("AA", 1, "Aa", 2, "aa", 1), c.genotypeCounts());
        assertEquals(2, c.phenotypeCounts().size());
        assertEquals(3, c.phenotypeCounts().get("A_"));
        assertEquals(1, c.phenotypeCounts().get("aa"));
        assertEquals(2, c.gametes1().size());
        assertEquals("Aa", c.square()[1][0]);   // a × A normalizes dominant-first
    }

    @Test
    @DisplayName("test cross Aa × aa: the 1:1 that reveals the hidden genotype")
    void testCross() {
        Cross c = MendelianGenetics.cross("Aa", "aa", Dominance.COMPLETE);
        assertEquals(Map.of("Aa", 2, "aa", 2), c.genotypeCounts());
        assertEquals(2, c.phenotypeCounts().get("A_"));
        assertEquals(2, c.phenotypeCounts().get("aa"));
    }

    @Test
    @DisplayName("dihybrid RrPp × RrPp — the chicken combs: walnut 9, rose 3, pea 3, single 1")
    void chickenCombs() {
        Cross c = MendelianGenetics.cross("RrPp", "RrPp", Dominance.COMPLETE);
        assertEquals(16, 4 * c.gametes2().size());
        assertEquals(9, c.phenotypeCounts().get("R_P_"));   // walnut
        assertEquals(3, c.phenotypeCounts().get("R_pp"));   // rose
        assertEquals(3, c.phenotypeCounts().get("rrP_"));   // pea
        assertEquals(1, c.phenotypeCounts().get("rrpp"));   // single
        assertEquals(9, c.genotypeCounts().size());         // 3^2 distinct genotypes
    }

    @Test
    @DisplayName("blue Andalusian Bb × Bb (incomplete): phenotypes 1:2:1 — not 3:1")
    void blueAndalusian() {
        Cross c = MendelianGenetics.cross("Bb", "Bb", Dominance.INCOMPLETE);
        assertEquals(Map.of("BB", 1, "Bb", 2, "bb", 1), c.phenotypeCounts());
        // The classroom trap: crossing two blue chickens never gives an all-blue flock.
        assertEquals(2, c.phenotypeCounts().get("Bb"));
    }

    @Test
    @DisplayName("Mendel's actual 1866 seed-shape counts pass the χ² gate at the historic value")
    void mendelsRealData() {
        Cross c = MendelianGenetics.cross("Rr", "Rr", Dominance.COMPLETE);
        RatioFit fit = MendelianGenetics.ratioFit(new long[]{ 5474, 1850 }, c);
        assertEquals(0.263, fit.chiSquare(), 0.005);        // the number in the textbooks
        assertEquals(1, fit.df());
        assertTrue(fit.consistent());
    }

    @Test
    @DisplayName("a clearly non-Mendelian count is flagged: 1:1 observed against a 3:1 expectation")
    void nonMendelianFlagged() {
        Cross c = MendelianGenetics.cross("Rr", "Rr", Dominance.COMPLETE);
        RatioFit fit = MendelianGenetics.ratioFit(new long[]{ 500, 500 }, c);
        assertTrue(fit.chiSquare() > 100);
        assertFalse(fit.consistent());
    }

    @Test
    @DisplayName("9:3:3:1 grading: a textbook F2 sample passes with df 3")
    void dihybridGrading() {
        Cross c = MendelianGenetics.cross("RrYy", "RrYy", Dominance.COMPLETE);
        // Mendel's actual dihybrid F2: 315 round-yellow, 108 round-green,
        // 101 wrinkled-yellow, 32 wrinkled-green — order must match phenotype order.
        RatioFit fit = MendelianGenetics.ratioFit(new long[]{ 315, 108, 101, 32 }, c);
        assertEquals(3, fit.df());
        assertTrue(fit.consistent());
        assertEquals(0.47, fit.chiSquare(), 0.01);          // the historic χ² ≈ 0.47
    }

    @Test
    @DisplayName("trihybrid stays drawable: 8×8 square, 27 genotypes, 8 phenotypes")
    void trihybrid() {
        Cross c = MendelianGenetics.cross("AaBbCc", "AaBbCc", Dominance.COMPLETE);
        assertEquals(8, c.gametes1().size());
        assertEquals(27, c.genotypeCounts().size());
        assertEquals(8, c.phenotypeCounts().size());
        assertEquals(27, (int) c.phenotypeCounts().get("A_B_C_"));
    }

    @Test
    @DisplayName("contracts: mismatched loci, malformed genotypes, too many loci, bad ratios")
    void contracts() {
        assertThrows(IllegalArgumentException.class,
                () -> MendelianGenetics.cross("Aa", "AaBb", Dominance.COMPLETE));
        assertThrows(IllegalArgumentException.class,
                () -> MendelianGenetics.cross("Ab", "Ab", Dominance.COMPLETE)); // letters differ
        assertThrows(IllegalArgumentException.class,
                () -> MendelianGenetics.cross("Aa", "Bb", Dominance.COMPLETE)); // locus mismatch
        assertThrows(IllegalArgumentException.class,
                () -> MendelianGenetics.cross("AaBbCcDd", "AaBbCcDd", Dominance.COMPLETE));
        assertThrows(IllegalArgumentException.class,
                () -> MendelianGenetics.ratioFit(new long[]{ 1 }, new double[]{ 1 }));
        assertThrows(IllegalArgumentException.class,
                () -> MendelianGenetics.ratioFit(new long[]{ 0, 0 }, new double[]{ 3, 1 }));
    }
}
