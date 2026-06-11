package test.core;

import core.evolution.PolicyGenome;
import core.strategy.RedBlackStrategy;
import core.strategy.TreeStrategy;
import core.strategy.WeightBalancedStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.HashSet;
import java.util.Random;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-011 V2 — the real genome. The properties that matter downstream: construction is
 * bounds-checked (no genome outside the box can exist), perturbation is a bounded step
 * that cannot leave the box (10k chained mutations as the proof), blend re-validates,
 * everything is pure and deterministic per seed (no static RNG — the {@code TreeGenome}
 * lesson), and equality is value identity, which is exactly V3's arm identity
 * (family + grid point).
 */
@DisplayName("PolicyGenome — bounds, perturbation, blend (ADR-011 V2)")
public class PolicyGenomeTest {

    @Nested
    @DisplayName("construction is the box")
    class Bounds {

        @Test
        @DisplayName("out-of-box grid points cannot be constructed")
        void boxEnforced() {
            assertThrows(IllegalArgumentException.class, () -> PolicyGenome.weightBalanced(1, 1));
            assertThrows(IllegalArgumentException.class,
                    () -> PolicyGenome.weightBalanced(PolicyGenome.DELTA_MAX + 1, 2));
            assertThrows(IllegalArgumentException.class, () -> PolicyGenome.weightBalanced(3, 0));
            assertThrows(IllegalArgumentException.class, () -> PolicyGenome.weightBalanced(3, 3));

            // The misuse seams fail loudly too: no parameterized of(), no genes on classics.
            assertThrows(IllegalArgumentException.class,
                    () -> PolicyGenome.of(PolicyGenome.Family.WEIGHT_BALANCED));
            assertThrows(IllegalStateException.class,
                    () -> PolicyGenome.of(PolicyGenome.Family.RED_BLACK).delta());
        }

        @Test
        @DisplayName("the verified default is WB(3,2), matching the strategy's constants")
        void verifiedDefault() {
            PolicyGenome g = PolicyGenome.verifiedDefault();
            assertEquals(WeightBalancedStrategy.DEFAULT_DELTA, g.delta());
            assertEquals(WeightBalancedStrategy.DEFAULT_RATIO, g.ratio());
            assertEquals("WB(Δ=3,Γ=2)", g.toString());
        }
    }

    @Nested
    @DisplayName("perturbation: bounded, box-closed, pure")
    class Perturbation {

        @Test
        @DisplayName("10k chained mutations never leave the box, and each is a ±1 step")
        void boxClosedUnderMutation() {
            PolicyGenome g = PolicyGenome.verifiedDefault();
            Random rng = new Random(11_2026);
            Set<PolicyGenome> visited = new HashSet<>();

            for (int i = 0; i < 10_000; i++) {
                PolicyGenome next = g.perturbed(rng);
                // Construction itself enforces the box; assert the step is bounded.
                assertTrue(Math.abs(next.delta() - g.delta()) <= 1, "Δ stepped by >1");
                assertTrue(Math.abs(next.ratio() - g.ratio()) <= 1, "Γ stepped by >1");
                visited.add(next);
                g = next;
            }
            // The walk actually explores: more than a handful of distinct grid points.
            assertTrue(visited.size() >= 5, "mutation walk stuck: visited " + visited);
        }

        @Test
        @DisplayName("same seed, same offspring — purity (the TreeGenome lesson)")
        void deterministicPerSeed() {
            PolicyGenome g = PolicyGenome.weightBalanced(5, 2);
            PolicyGenome a = g.perturbed(new Random(42));
            PolicyGenome b = g.perturbed(new Random(42));
            assertEquals(a, b);
            assertEquals(g, PolicyGenome.weightBalanced(5, 2), "parent unchanged (immutability)");
        }

        @Test
        @DisplayName("a classic family is a point: perturbation is identity")
        void classicsArePoints() {
            PolicyGenome rb = PolicyGenome.of(PolicyGenome.Family.RED_BLACK);
            assertSame(rb, rb.perturbed(new Random(7)));
        }
    }

    @Nested
    @DisplayName("blend: re-validated crossover")
    class Blend {

        @Test
        @DisplayName("WB × WB: genes land between the parents and inside the box")
        void blendWithinSpan() {
            PolicyGenome a = PolicyGenome.weightBalanced(3, 2);
            PolicyGenome b = PolicyGenome.weightBalanced(7, 4);
            for (int seed = 0; seed < 50; seed++) {
                PolicyGenome child = a.blended(b, new Random(seed));
                assertTrue(child.delta() >= 3 && child.delta() <= 7,
                        "Δ outside parents' span: " + child);
                assertTrue(child.ratio() >= 2 && child.ratio() < child.delta(),
                        "Γ invalid: " + child);
            }
        }

        @Test
        @DisplayName("WB × classic: the child is valid whichever family the coin picks")
        void blendAcrossFamilies() {
            PolicyGenome wb = PolicyGenome.weightBalanced(4, 2);
            PolicyGenome splay = PolicyGenome.of(PolicyGenome.Family.SPLAY);
            boolean sawWb = false;
            boolean sawSplay = false;
            Random rng = new Random(2026);   // one stream: fresh tiny seeds bias nextBoolean
            for (int i = 0; i < 50; i++) {
                PolicyGenome child = wb.blended(splay, rng);
                if (child.family().parameterized()) {
                    sawWb = true;
                    assertEquals(4, child.delta());   // genes come from the WB parent
                    assertEquals(2, child.ratio());
                } else {
                    sawSplay = true;
                    assertEquals(PolicyGenome.Family.SPLAY, child.family());
                }
            }
            assertTrue(sawWb && sawSplay, "coin never landed on one side across 50 seeds");
        }
    }

    @Nested
    @DisplayName("identity and execution")
    class IdentityAndExecution {

        @Test
        @DisplayName("value identity = V3 arm identity: same grid point equal, different not")
        void armIdentity() {
            assertEquals(PolicyGenome.weightBalanced(4, 2), PolicyGenome.weightBalanced(4, 2));
            assertEquals(PolicyGenome.weightBalanced(4, 2).hashCode(),
                         PolicyGenome.weightBalanced(4, 2).hashCode());
            assertNotEquals(PolicyGenome.weightBalanced(4, 2), PolicyGenome.weightBalanced(4, 3));
            assertNotEquals(PolicyGenome.of(PolicyGenome.Family.AVL),
                            PolicyGenome.of(PolicyGenome.Family.SPLAY));
        }

        @Test
        @DisplayName("genotype → phenotype: toStrategy builds the strategy the genes describe")
        void toStrategyCarriesGenes() {
            TreeStrategy<Integer> s = PolicyGenome.weightBalanced(5, 2).toStrategy();
            assertTrue(s instanceof WeightBalancedStrategy);
            assertEquals(5, ((WeightBalancedStrategy<Integer>) s).delta());
            assertEquals(2, ((WeightBalancedStrategy<Integer>) s).ratio());

            assertTrue(PolicyGenome.of(PolicyGenome.Family.RED_BLACK)
                    .<Integer>toStrategy() instanceof RedBlackStrategy);
        }
    }
}
