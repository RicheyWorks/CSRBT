package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.LifeTable;
import io.github.richeyworks.csrbt.experimental.ecology.LifeTable.Lifespan;
import io.github.richeyworks.csrbt.experimental.ecology.LifeTable.SurvivorshipType;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Cohort life tables over op-aged lifespans — a hand-computed table oracle, the l&#x2093;
 * monotonicity invariant, and the three Deevey classifications each pinned on a
 * synthetic cohort built to be that type.
 */
@DisplayName("LifeTable — cohort demography in op time")
class LifeTableTest {

    private static final double EPS = 1e-9;

    private static List<Lifespan> cohortWithAges(long... ages) {
        List<Lifespan> out = new ArrayList<>();
        int key = 0;
        for (long age : ages) {
            out.add(new Lifespan(key++, 100, 100 + age)); // birth op arbitrary
        }
        return out;
    }

    // ── Table construction ────────────────────────────────────────────────────

    @Test
    @DisplayName("hand-computed 3-class table: d_x, n_x, l_x, q_x all exact")
    void handComputedTable() {
        // ages: 3 in class 0, 2 in class 1, 5 in class 2 (maxAge 22 → width 8)
        LifeTable t = LifeTable.fromLifespans(
                cohortWithAges(2, 2, 2, 12, 12, 22, 22, 22, 22, 22), 3);

        assertEquals(10, t.cohortSize());
        assertEquals(8, t.classWidth()); // 22/3 + 1
        assertEquals(3, t.deathsAt(0));
        assertEquals(2, t.deathsAt(1));
        assertEquals(5, t.deathsAt(2));
        assertEquals(10, t.enteringAt(0));
        assertEquals(7,  t.enteringAt(1));
        assertEquals(5,  t.enteringAt(2));
        assertEquals(1.0, t.survivorshipAt(0), EPS);
        assertEquals(0.7, t.survivorshipAt(1), EPS);
        assertEquals(0.5, t.survivorshipAt(2), EPS);
        assertEquals(0.3,       t.mortalityAt(0), EPS);
        assertEquals(2.0 / 7.0, t.mortalityAt(1), EPS);
        assertEquals(1.0,       t.mortalityAt(2), EPS);
        assertEquals(14.0, t.lifeExpectancy(), EPS); // (3·2 + 2·12 + 5·22)/10
    }

    @Test
    @DisplayName("survivorship l_x is monotone non-increasing and l_0 = 1")
    void survivorshipMonotone() {
        LifeTable t = LifeTable.fromLifespans(
                cohortWithAges(1, 4, 9, 16, 25, 36, 49, 64, 81, 100), 5);
        assertEquals(1.0, t.survivorshipAt(0), EPS);
        for (int x = 1; x < t.ageClasses(); x++) {
            assertTrue(t.survivorshipAt(x) <= t.survivorshipAt(x - 1),
                    "l_x rose at class " + x);
        }
    }

    @Test
    @DisplayName("lifespan validation: deathOp < birthOp throws; age is op-measured")
    void lifespanContract() {
        assertThrows(IllegalArgumentException.class, () -> new Lifespan(1, 50, 40));
        assertEquals(25, new Lifespan(1, 50, 75).age());
        assertThrows(IllegalArgumentException.class,
                () -> LifeTable.fromLifespans(List.of(), 0));
    }

    // ── Deevey classification ─────────────────────────────────────────────────

    @Test
    @DisplayName("Type I — deaths concentrated late (ρ = mean/median < 1.2)")
    void typeOne() {
        // 100 die young (age 1), 900 die old (age 30): median 30, mean 27.1 → ρ ≈ 0.90
        long[] ages = new long[1000];
        for (int i = 0; i < 100; i++)    ages[i] = 1;
        for (int i = 100; i < 1000; i++) ages[i] = 30;
        LifeTable t = LifeTable.fromLifespans(cohortWithAges(ages), 6);
        assertEquals(SurvivorshipType.TYPE_I, t.survivorshipType());
        assertTrue(t.concentrationRatio() < LifeTable.TYPE_I_MAX_RATIO);
    }

    @Test
    @DisplayName("Type II — constant per-capita mortality (geometric ages, ρ ≈ 1.4)")
    void typeTwo() {
        // Half the survivors die each age class: 500@5, 250@15, 125@25, 125@35.
        // median = 10, mean = 13.75 → ρ = 1.375, inside (1.2, 1.8).
        long[] ages = new long[1000];
        int i = 0;
        for (int k = 0; k < 500; k++) ages[i++] = 5;
        for (int k = 0; k < 250; k++) ages[i++] = 15;
        for (int k = 0; k < 125; k++) ages[i++] = 25;
        for (int k = 0; k < 125; k++) ages[i++] = 35;
        LifeTable t = LifeTable.fromLifespans(cohortWithAges(ages), 4);
        assertEquals(SurvivorshipType.TYPE_II, t.survivorshipType());
        assertEquals(1.375, t.concentrationRatio(), EPS);
    }

    @Test
    @DisplayName("Type III — deaths concentrated early (ρ = mean/median > 1.8)")
    void typeThree() {
        // 900 die at age 1, 100 survive to 30: median 1, mean 3.9 → ρ = 3.9
        long[] ages = new long[1000];
        for (int i = 0; i < 900; i++)    ages[i] = 1;
        for (int i = 900; i < 1000; i++) ages[i] = 30;
        LifeTable t = LifeTable.fromLifespans(cohortWithAges(ages), 6);
        assertEquals(SurvivorshipType.TYPE_III, t.survivorshipType());
        assertTrue(t.concentrationRatio() > LifeTable.TYPE_III_MIN_RATIO);
    }

    @Test
    @DisplayName("degenerate cohorts: empty and singleton default to Type II")
    void degenerateCohorts() {
        assertEquals(SurvivorshipType.TYPE_II,
                LifeTable.fromLifespans(List.of(), 3).survivorshipType());
        assertEquals(SurvivorshipType.TYPE_II,
                LifeTable.fromLifespans(cohortWithAges(10), 3).survivorshipType());
        assertEquals(0, LifeTable.fromLifespans(List.of(), 3).cohortSize());
    }

    @Test
    @DisplayName("determinism: same lifespans in any order give the identical table")
    void determinism() {
        List<Lifespan> forward = cohortWithAges(2, 12, 22, 7, 30);
        List<Lifespan> reversed = new ArrayList<>(forward);
        java.util.Collections.reverse(reversed);
        LifeTable a = LifeTable.fromLifespans(forward, 4);
        LifeTable b = LifeTable.fromLifespans(reversed, 4);
        for (int x = 0; x < 4; x++) {
            assertEquals(a.deathsAt(x), b.deathsAt(x));
            assertEquals(a.survivorshipAt(x), b.survivorshipAt(x));
        }
        assertEquals(a.lifeExpectancy(), b.lifeExpectancy());
        assertEquals(a.medianAge(), b.medianAge());
        assertEquals(a.survivorshipType(), b.survivorshipType());
    }
}
