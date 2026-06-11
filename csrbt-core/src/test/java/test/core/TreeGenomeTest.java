package test.core;

import io.github.richeyworks.csrbt.evolution.TreeGenome;
import io.github.richeyworks.csrbt.evolution.TreeGenome.AdaptationMode;
import io.github.richeyworks.csrbt.evolution.TreeGenome.BalanceTraits;
import io.github.richeyworks.csrbt.evolution.TreeGenome.CapabilityProfile;
import io.github.richeyworks.csrbt.evolution.TreeGenome.EcologyTraits;
import io.github.richeyworks.csrbt.evolution.TreeGenome.GenomeOrigin;
import io.github.richeyworks.csrbt.evolution.TreeGenome.MorphTraits;
import io.github.richeyworks.csrbt.evolution.TreeGenome.ScoreCard;
import io.github.richeyworks.csrbt.evolution.TreeGenome.StructureType;
import io.github.richeyworks.csrbt.evolution.TreeGenome.WorkloadTraits;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.RepeatedTest;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for {@link TreeGenome} — ADR-001 action item 11.
 *
 * <p>The genome splits cleanly into two halves for testing:</p>
 * <ul>
 *   <li><b>Scoring / recommendation</b> — pure functions of the trait blocks,
 *       fully deterministic, so we assert exact values and tight invariants.</li>
 *   <li><b>Mutation / crossover</b> — driven by a static, unseeded {@code Random},
 *       so we assert only the invariants that hold for <em>every</em> RNG outcome
 *       (clamping, provenance bookkeeping, source immutability, generation
 *       monotonicity), repeated enough times to exercise the random branches.</li>
 * </ul>
 */
@DisplayName("TreeGenome scoring & mutation")
class TreeGenomeTest {

    private static final double EPS = 1e-9;

    // ── Scoring / recommendation (deterministic) ────────────────────────────

    @Nested
    @DisplayName("Scoring")
    class Scoring {

        @ParameterizedTest
        @EnumSource(StructureType.class)
        @DisplayName("fitnessFor is bounded to [0,1] for every structure")
        void fitnessBounded(StructureType type) {
            double f = new TreeGenome().fitnessFor(type);
            assertTrue(f >= 0.0 && f <= 1.0, type + " fitness out of range: " + f);
        }

        @Test
        @DisplayName("scoreCard.scoreOf matches fitnessFor for every structure")
        void scoreCardConsistentWithFitness() {
            TreeGenome g = TreeGenome.hybridGenome();
            ScoreCard card = g.scoreCard();
            for (StructureType t : StructureType.values()) {
                // scoreCard does NOT apply the preferred-structure bonus, so it
                // equals fitnessFor only for non-preferred types; assert it for
                // the structures that are not the preferred one.
                if (t != g.getPreferredStructure()) {
                    assertEquals(g.fitnessFor(t), card.scoreOf(t), EPS,
                            "scoreOf disagrees with fitnessFor for " + t);
                }
            }
        }

        @Test
        @DisplayName("recommendedStructure equals the scoreCard's best structure")
        void recommendedMatchesBest() {
            TreeGenome g = TreeGenome.avlGenome();
            assertEquals(g.scoreCard().bestStructure(), g.recommendedStructure());
        }

        @Test
        @DisplayName("bestStructure has the maximal scoreOf in the card")
        void bestStructureIsMaximal() {
            ScoreCard card = TreeGenome.splayGenome().scoreCard();
            StructureType best = card.bestStructure();
            double bestScore = card.scoreOf(best);
            for (StructureType t : StructureType.values()) {
                assertTrue(card.scoreOf(t) <= bestScore + EPS,
                        t + " scores higher than the declared best " + best);
            }
        }

        @Test
        @DisplayName("preferred structure adds a +0.04 fitness bonus")
        void preferredStructureBonus() {
            TreeGenome g = TreeGenome.builder()
                    .preferredStructure(StructureType.RED_BLACK)
                    .build();
            // SPLAY base score for the default profile sits well below 1.0, so
            // the bonus cannot be clipped by clamping.
            double base = g.fitnessFor(StructureType.SPLAY);
            g.setPreferredStructure(StructureType.SPLAY);
            double boosted = g.fitnessFor(StructureType.SPLAY);
            assertEquals(base + 0.04, boosted, EPS);
        }

        @Test
        @DisplayName("scoreCard average and range stay within [0,1]")
        void cardAggregatesBounded() {
            ScoreCard card = new TreeGenome().scoreCard();
            assertTrue(card.average() >= 0.0 && card.average() <= 1.0);
            assertTrue(card.range() >= 0.0 && card.range() <= 1.0);
        }
    }

    // ── Bias families (deterministic) ───────────────────────────────────────

    @Nested
    @DisplayName("Bias")
    class Bias {

        @Test
        @DisplayName("all four bias scores are bounded to [0,1]")
        void biasBounded() {
            TreeGenome g = new TreeGenome();
            for (double s : new double[]{
                    g.searchBiasScore(), g.priorityBiasScore(),
                    g.persistenceBiasScore(), g.intervalBiasScore()}) {
                assertTrue(s >= 0.0 && s <= 1.0, "bias out of range: " + s);
            }
        }

        @Test
        @DisplayName("dominantBiasLabel reports one of the four known families")
        void dominantLabelKnown() {
            String label = TreeGenome.fibonacciGenome().dominantBiasLabel();
            assertTrue(java.util.Set.of(
                    "SEARCH_DOMINANT", "PRIORITY_DOMINANT",
                    "PERSISTENCE_DOMINANT", "INTERVAL_DOMINANT").contains(label),
                    "unexpected bias label: " + label);
        }

        @Test
        @DisplayName("fibonacci genome is priority-dominant")
        void fibonacciIsPriorityDominant() {
            // The Fibonacci preset loads meld/decrease-key/extract-min and a high
            // priority-queue preference; its priority bias should top the others.
            TreeGenome fib = TreeGenome.fibonacciGenome();
            assertTrue(fib.priorityBiasScore() > fib.searchBiasScore(),
                    "expected priority bias to exceed search bias for Fibonacci genome");
            assertEquals("PRIORITY_DOMINANT", fib.dominantBiasLabel());
        }

        @Test
        @DisplayName("red-black genome is search-dominant")
        void redBlackIsSearchDominant() {
            assertEquals("SEARCH_DOMINANT", TreeGenome.redBlackGenome().dominantBiasLabel());
        }
    }

    // ── Morph pressure (deterministic) ──────────────────────────────────────

    @Nested
    @DisplayName("Morph pressure")
    class MorphPressure {

        @Test
        @DisplayName("morph pressure is bounded to [0,1]")
        void pressureBounded() {
            TreeGenome g = new TreeGenome();
            assertTrue(g.computeMorphPressure(2.0, -1.0, 5.0) <= 1.0);  // inputs clamped first
            assertTrue(g.computeMorphPressure(0.0, 0.0, 0.0) >= 0.0);
        }

        @Test
        @DisplayName("higher stress never decreases morph pressure")
        void pressureMonotonicInStress() {
            TreeGenome g = new TreeGenome();
            double low = g.computeMorphPressure(0.10, 0.50, 0.20);
            double high = g.computeMorphPressure(0.95, 0.50, 0.20);
            assertTrue(high >= low, "pressure should be non-decreasing in stress");
        }

        @Test
        @DisplayName("shouldMorph agrees with the threshold comparison")
        void shouldMorphMatchesThreshold() {
            TreeGenome g = new TreeGenome();
            double pressure = g.computeMorphPressure(0.95, 0.0, 0.95);
            double threshold = g.getMorphTraits().getMorphThreshold();
            assertEquals(pressure >= threshold, g.shouldMorph(0.95, 0.0, 0.95));
        }
    }

    // ── Compatibility (deterministic) ───────────────────────────────────────

    @Nested
    @DisplayName("Compatibility")
    class Compatibility {

        @Test
        @DisplayName("a genome is maximally compatible with itself")
        void selfCompatibilityIsHigh() {
            TreeGenome g = TreeGenome.avlGenome();
            assertEquals(1.0, g.compatibilityScore(g), EPS);
        }

        @Test
        @DisplayName("compatibility is symmetric and bounded")
        void symmetricAndBounded() {
            TreeGenome a = TreeGenome.redBlackGenome();
            TreeGenome b = TreeGenome.fibonacciGenome();
            double ab = a.compatibilityScore(b);
            double ba = b.compatibilityScore(a);
            assertEquals(ab, ba, EPS, "compatibility should be symmetric");
            assertTrue(ab >= 0.0 && ab <= 1.0);
        }

        @Test
        @DisplayName("similar genomes are more compatible than dissimilar ones")
        void similarBeatsDissimilar() {
            TreeGenome rb = TreeGenome.redBlackGenome();
            TreeGenome avl = TreeGenome.avlGenome();          // close cousin
            TreeGenome fib = TreeGenome.fibonacciGenome();    // far apart
            assertTrue(rb.compatibilityScore(avl) > rb.compatibilityScore(fib));
        }

        @Test
        @DisplayName("compatibilityScore rejects null")
        void rejectsNull() {
            assertThrows(NullPointerException.class,
                    () -> new TreeGenome().compatibilityScore(null));
        }
    }

    // ── Conflict detection (deterministic) ──────────────────────────────────

    @Nested
    @DisplayName("Conflicts")
    class Conflicts {

        @Test
        @DisplayName("a default genome reports no major conflicts")
        void defaultHasNoConflicts() {
            TreeGenome g = new TreeGenome();
            assertFalse(g.hasMajorConflicts());
            assertEquals("No major internal conflicts detected.", g.conflictReport());
        }

        @Test
        @DisplayName("strict balance + heavy priority queue is flagged as a conflict")
        void balanceVsPriorityConflict() {
            TreeGenome g = TreeGenome.builder()
                    .balanceTraits(new BalanceTraits(0.95, 0.50, 0.50))
                    .workloadTraits(new WorkloadTraits(0.40, 0.70, 0.95))
                    .build();
            assertTrue(g.hasMajorConflicts());
            assertTrue(g.conflictReport().contains("Conflict"));
        }

        @Test
        @DisplayName("high persistence weight without memory focus is flagged")
        void persistenceWithoutMemoryFocus() {
            TreeGenome g = TreeGenome.builder()
                    .adaptationMode(AdaptationMode.SPEED_FOCUSED)
                    .capabilityProfile(new CapabilityProfile(
                            0.50, 0.50, 0.50, 0.50, 0.05, 0.05, 0.10, 0.95, 0.30))
                    .build();
            assertTrue(g.hasMajorConflicts());
        }
    }

    // ── Mutation (RNG-driven — invariants only) ─────────────────────────────

    @Nested
    @DisplayName("Mutation")
    class Mutation {

        @RepeatedTest(50)
        @DisplayName("mutatedCopy records provenance and leaves the source untouched")
        void mutatedCopyProvenance() {
            TreeGenome parent = TreeGenome.redBlackGenome();
            UUID parentId = parent.getGenomeId();
            int parentGen = parent.getGeneration();
            TreeGenome before = parent.clone();

            TreeGenome child = parent.mutatedCopy();

            assertNotEquals(parentId, child.getGenomeId(), "child must get a fresh id");
            assertEquals(parentId, child.getParentAId(), "child must point back to its parent");
            assertNull(child.getParentBId(), "mutation is asexual — no second parent");
            assertEquals(parentGen + 1, child.getGeneration());
            assertEquals(GenomeOrigin.MUTATED, child.getOrigin());
            // Source genome is unchanged by mutatedCopy.
            assertEquals(before, parent, "mutatedCopy must not mutate its source");
        }

        @RepeatedTest(50)
        @DisplayName("mutated traits stay clamped to [0,1] and pass validation")
        void mutatedTraitsClamped() {
            TreeGenome child = TreeGenome.splayGenome().mutatedCopy();
            assertDoesNotThrow(child::validate);
            assertTraitsInRange(child);
        }

        @RepeatedTest(50)
        @DisplayName("in-place mutate advances generation and changes identity")
        void inPlaceMutate() {
            TreeGenome g = TreeGenome.avlGenome();
            UUID oldId = g.getGenomeId();
            int oldGen = g.getGeneration();
            g.mutate();
            assertNotEquals(oldId, g.getGenomeId());
            assertEquals(oldGen + 1, g.getGeneration());
            assertEquals(GenomeOrigin.MUTATED, g.getOrigin());
            assertTraitsInRange(g);
        }
    }

    // ── Crossover (RNG-driven — invariants only) ────────────────────────────

    @Nested
    @DisplayName("Crossover")
    class Crossover {

        @RepeatedTest(50)
        @DisplayName("child generation exceeds both parents and traits stay valid")
        void crossoverInvariants() {
            TreeGenome a = TreeGenome.redBlackGenome();
            TreeGenome b = TreeGenome.fibonacciGenome();
            int expectedMin = Math.max(a.getGeneration(), b.getGeneration()) + 1;

            TreeGenome child = TreeGenome.crossover(a, b);

            // A post-crossover mutation may bump the generation once more, so the
            // child's generation is at least max(parents)+1.
            assertTrue(child.getGeneration() >= expectedMin,
                    "child generation " + child.getGeneration() + " < " + expectedMin);
            assertDoesNotThrow(child::validate);
            assertTraitsInRange(child);
            // Preferred structure is inherited from one of the two parents unless a
            // mutation re-rolled it — either way it must be a valid enum value
            // (guaranteed by type) and the child must not be one of the parents.
            assertNotEquals(a.getGenomeId(), child.getGenomeId());
            assertNotEquals(b.getGenomeId(), child.getGenomeId());
        }

        @Test
        @DisplayName("crossover rejects null parents")
        void rejectsNullParents() {
            TreeGenome g = new TreeGenome();
            assertThrows(NullPointerException.class, () -> TreeGenome.crossover(null, g));
            assertThrows(NullPointerException.class, () -> TreeGenome.crossover(g, null));
        }
    }

    // ── shared helper ───────────────────────────────────────────────────────

    private static void assertTraitsInRange(TreeGenome g) {
        BalanceTraits b = g.getBalanceTraits();
        inRange(b.getBalancePreference());
        inRange(b.getDepthStressTolerance());
        inRange(b.getFragmentationTolerance());

        EcologyTraits e = g.getEcologyTraits();
        inRange(e.getEntropyPreference());
        inRange(e.getDuplicateTolerance());

        WorkloadTraits w = g.getWorkloadTraits();
        inRange(w.getLocalityPreference());
        inRange(w.getOrderStatisticPreference());
        inRange(w.getPriorityQueuePreference());

        MorphTraits m = g.getMorphTraits();
        inRange(m.getMutationRate());
        inRange(m.getMorphThreshold());

        CapabilityProfile c = g.getCapabilityProfile();
        inRange(c.getOrderedSearchWeight());
        inRange(c.getPredecessorSuccessorWeight());
        inRange(c.getRankSelectWeight());
        inRange(c.getIntervalQueryWeight());
        inRange(c.getMeldWeight());
        inRange(c.getDecreaseKeyWeight());
        inRange(c.getExtractMinWeight());
        inRange(c.getPersistenceWeight());
        inRange(c.getLocalityExploitationWeight());
    }

    private static void inRange(double v) {
        assertTrue(v >= 0.0 && v <= 1.0, "trait out of [0,1]: " + v);
    }
}
