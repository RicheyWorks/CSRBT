package test.core;

import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.experimental.ecology.EnsembleCommunity;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Comparator;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-016 §E1 — metapopulation observables over the ensemble: members as patches,
 * quarantine as local extinction, heal as recolonization, strategy names as species.
 * Hand-oracle throughout, driven through the ensemble's public lifecycle API.
 */
@DisplayName("EnsembleCommunity — patches, occupancy, Levins, strategy diversity")
class EnsembleCommunityTest {

    private static final double EPS = 1e-9;

    private static EnsembleOrderedSet<Integer> ensemble() {
        EnsembleOrderedSet<Integer> e = EnsembleOrderedSet.<Integer>builder(Comparator.naturalOrder())
                .member(RedBlackStrategy::new)
                .member(AVLStrategy::new)
                .member(SplayStrategy::new)
                .build();
        for (int i = 0; i < 50; i++) e.add(i);
        return e;
    }

    @Test
    @DisplayName("baseline: full occupancy, 3 species, H' = ln 3, redundancy 1")
    void baseline() {
        EnsembleCommunity<Integer> eco = new EnsembleCommunity<>(ensemble());
        assertEquals(1.0, eco.occupancy(), EPS);
        assertEquals(3, eco.strategyRichness());
        assertEquals(Math.log(3), eco.strategyDiversity(), EPS);
        assertEquals(1.0, eco.strategyEvenness(), EPS);
        assertEquals(1.0, eco.functionalRedundancy(), EPS);
        assertEquals(0, eco.extinctions());
        assertEquals(1.0, eco.levinsEquilibrium(), EPS); // no observed pressure
    }

    @Test
    @DisplayName("quarantine is a local extinction: occupancy drops, event counted, species lost")
    void quarantineIsExtinction() {
        EnsembleOrderedSet<Integer> e = ensemble();
        EnsembleCommunity<Integer> eco = new EnsembleCommunity<>(e);

        EnsembleMember<Integer> victim = null;
        for (EnsembleMember<Integer> m : e.members()) {
            if (m != e.primary()) { victim = m; break; }
        }
        e.quarantine(victim);
        assertEquals(1, eco.sample());

        assertEquals(1, eco.extinctions());
        assertEquals(0, eco.recolonizations());
        assertEquals(2.0 / 3.0, eco.occupancy(), EPS);
        assertEquals(2, eco.strategyRichness());
        assertEquals(0.0, eco.levinsEquilibrium(), EPS); // extinction, no recolonization
    }

    @Test
    @DisplayName("heal is recolonization: occupancy restored, both events on the record")
    void healIsRecolonization() {
        EnsembleOrderedSet<Integer> e = ensemble();
        EnsembleCommunity<Integer> eco = new EnsembleCommunity<>(e);

        EnsembleMember<Integer> victim = null;
        for (EnsembleMember<Integer> m : e.members()) {
            if (m != e.primary()) { victim = m; break; }
        }
        e.quarantine(victim);
        eco.sample();
        e.healFromPrimary(victim);
        eco.sample();

        assertEquals(1, eco.extinctions());
        assertEquals(1, eco.recolonizations());
        assertEquals(1.0, eco.occupancy(), EPS);
        assertEquals(3, eco.strategyRichness());
        // Levins with e/c = 1/1: p* = 1 − 1 = 0 — the model says this extinction
        // pressure exactly cancels this colonization rate; the direct measurement
        // (occupancy 1.0) is the comparison the instrument exists to expose.
        assertEquals(0.0, eco.levinsEquilibrium(), EPS);
    }

    @Test
    @DisplayName("Levins ratio from the instrument: balanced cycles pin p* at 0; excess extinction clamps")
    void levinsRatioFromInstrument() {
        EnsembleOrderedSet<Integer> e = ensemble();
        EnsembleCommunity<Integer> eco = new EnsembleCommunity<>(e);

        EnsembleMember<Integer> patch = null;
        for (EnsembleMember<Integer> m : e.members()) {
            if (m != e.primary()) { patch = m; break; }
        }
        // 4 extinction+recolonization cycles, sampled around each transition.
        for (int i = 0; i < 4; i++) {
            e.quarantine(patch);
            eco.sample();
            e.healFromPrimary(patch);
            eco.sample();
        }
        assertEquals(4, eco.extinctions());
        assertEquals(4, eco.recolonizations());
        assertEquals(0.0, eco.levinsEquilibrium(), EPS); // e/c = 1 → p* = 0 exactly

        // A fifth extinction with no recolonization: e/c = 5/4 → raw p* < 0, clamped.
        e.quarantine(patch);
        eco.sample();
        assertEquals(5, eco.extinctions());
        assertEquals(4, eco.recolonizations());
        assertEquals(0.0, eco.levinsEquilibrium(), EPS);
        assertEquals(2.0 / 3.0, eco.occupancy(), EPS); // and the direct measurement moved
    }

    @Test
    @DisplayName("a missed transition between samples is not double-counted; sampling is idempotent")
    void samplingIdempotent() {
        EnsembleOrderedSet<Integer> e = ensemble();
        EnsembleCommunity<Integer> eco = new EnsembleCommunity<>(e);
        assertEquals(0, eco.sample());
        assertEquals(0, eco.sample());
        assertEquals(2, eco.samples());
        assertEquals(0, eco.extinctions());

        // quarantine + heal entirely between samples: net state unchanged → no events
        EnsembleMember<Integer> m0 = null;
        for (EnsembleMember<Integer> m : e.members()) {
            if (m != e.primary()) { m0 = m; break; }
        }
        e.quarantine(m0);
        e.healFromPrimary(m0);
        assertEquals(0, eco.sample());
        assertEquals(0, eco.extinctions(), "state-diff sampling cannot see a cancelled cycle");
    }

    @Test
    @DisplayName("strategy abundance map is sorted and deterministic")
    void abundanceDeterministic() {
        EnsembleCommunity<Integer> eco = new EnsembleCommunity<>(ensemble());
        Map<String, Long> a = eco.strategyAbundance();
        Map<String, Long> b = eco.strategyAbundance();
        assertEquals(a, b);
        assertEquals(3, a.size());
        String prev = null;
        for (String name : a.keySet()) {
            if (prev != null) assertTrue(prev.compareTo(name) < 0, "keys must be sorted");
            prev = name;
        }
    }
}
