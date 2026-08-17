package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.evolution.PolicyBandit;
import io.github.richeyworks.csrbt.evolution.PolicyEvolutionController;
import io.github.richeyworks.csrbt.evolution.PolicyGenome;
import io.github.richeyworks.csrbt.evolution.PolicySearchController;
import io.github.richeyworks.csrbt.evolution.PolicySearchController.TrialResult;
import io.github.richeyworks.csrbt.evolution.StrategyBattleRunner;
import io.github.richeyworks.csrbt.evolution.StrategyBattleRunner.BattleResult;
import io.github.richeyworks.csrbt.evolution.StrategyBattleRunner.WorkloadType;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Seventh-pass closure (2026-08-17) — the regression pins for audit items A, C, D, E, G and H.
 *
 * <p>One nested class per item; each behavioural pin was verified red by reverting its fix in
 * isolation. Nothing is mocked: the snapshot probes go through the real
 * {@code FilePersistenceAdapter} and the real filesystem, and the pricing probes run real
 * ensembles through a real fan-out.</p>
 */
@DisplayName("Seventh-pass closure 2026-08-17")
class SeventhPassClosureTest {

    private static final Path DIR = Paths.get("snapshots");
    private final List<Path> litter = new ArrayList<>();

    @AfterEach
    void cleanUp() throws IOException {
        for (Path p : litter) Files.deleteIfExists(p);
        litter.clear();
    }

    private String snap(String base) {
        String name = "p7c_" + base + "_" + System.nanoTime();
        litter.add(DIR.resolve(name + ".rbt"));
        return name;
    }

    private static EnsembleOrderedSet.Builder<Integer> ensemble() {
        return EnsembleOrderedSet.builder(Comparator.<Integer>naturalOrder());
    }

    // ── Item A ──────────────────────────────────────────────────────────────────────────

    /**
     * {@code loadSnapshot} adopted the deserialized context's {@code OrderedSet} wholesale, and
     * that set was built fresh by the adapter with {@code maxSize == 0} — so a load did not merely
     * fail to enforce the live sliding-window bound, it <em>destroyed</em> it. Third instance of
     * the family sixth-pass fixes S6-19 (clone) and S6-20 (checkpoint restore) closed.
     */
    @Nested
    @DisplayName("item A — a snapshot load respects the live sliding-window bound")
    class SnapshotLoadRespectsTheWindow {

        @Test
        @DisplayName("the audit's reproduction: the bound survives the load and keeps the newest keys")
        void theBoundSurvivesTheLoad() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            ctx.getOrderedSet().setMaxSize(3);
            for (int i = 1; i <= 10; i++) ctx.add(i);
            assertEquals(List.of(8, 9, 10), ctx.inOrder());

            String name = snap("windowA");
            ctx.saveSnapshot(name);
            for (int i = 20; i <= 25; i++) ctx.add(i);
            assertEquals(List.of(23, 24, 25), ctx.inOrder());

            ctx.loadSnapshot(name);
            assertEquals(3, ctx.getOrderedSet().getMaxSize(),
                    "the load must not wipe the bound — it was 0 before this fix, permanently");
            assertEquals(List.of(8, 9, 10), ctx.inOrder());
            assertEquals(3, ctx.size());

            // ...and the window is still live afterwards: 11 more adds cannot grow the set.
            for (int i = 100; i <= 110; i++) ctx.add(i);
            assertEquals(3, ctx.size(), "a destroyed bound let this reach 14");
            assertEquals(List.of(108, 109, 110), ctx.inOrder());
        }

        @Test
        @DisplayName("an over-bound snapshot is evicted down to the bound, exactly as a restore is")
        void anOverBoundSnapshotIsEvictedOnLoad() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            for (int i = 1; i <= 10; i++) ctx.add(i);         // saved unbounded
            String name = snap("windowB");
            ctx.saveSnapshot(name);

            ctx.getOrderedSet().setMaxSize(3);                // bound applied after the save
            assertEquals(List.of(8, 9, 10), ctx.inOrder());
            ctx.loadSnapshot(name);

            assertEquals(3, ctx.getOrderedSet().getMaxSize());
            assertEquals(3, ctx.size(), "the window caps what can exist; a load is not exempt");
            assertEquals(List.of(8, 9, 10), ctx.inOrder(),
                    "the survivors are the newest maxSize keys — the same ones the checkpoint "
                            + "restore path (S6-20) keeps, so the two agree");
            // The next single add evicts exactly one, not the whole excess at once.
            ctx.add(99);
            assertEquals(3, ctx.size());
            assertEquals(List.of(9, 10, 99), ctx.inOrder());
        }

        @Test
        @DisplayName("an unbounded context still loads everything — the fix is not a blanket cap")
        void anUnboundedContextIsUnaffected() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            for (int i = 1; i <= 10; i++) ctx.add(i);
            String name = snap("windowC");
            ctx.saveSnapshot(name);
            ctx.clear();
            ctx.loadSnapshot(name);

            assertEquals(0, ctx.getOrderedSet().getMaxSize());
            assertEquals(10, ctx.size());
        }

        @Test
        @DisplayName("a load does not RESTORE a saved bound — the bound is the container's, not the payload's")
        void aLoadDoesNotRestoreASavedBound() {
            TreeContext bounded = new TreeContext(new RedBlackStrategy<>());
            bounded.getOrderedSet().setMaxSize(2);
            for (int i = 1; i <= 5; i++) bounded.add(i);
            String name = snap("windowD");
            bounded.saveSnapshot(name);

            TreeContext unbounded = new TreeContext(new RedBlackStrategy<>());
            unbounded.loadSnapshot(name);
            assertEquals(0, unbounded.getOrderedSet().getMaxSize(),
                    "the snapshot format has never recorded a bound and a load must not be able "
                            + "to silently bound (or unbound) the context it lands in");
            assertEquals(List.of(4, 5), unbounded.inOrder());
        }
    }

    // ── Item C ──────────────────────────────────────────────────────────────────────────

    /**
     * ADR-024 clause 3 ("both sides per-member or neither") held within an evaluation window but
     * not across the pool each decision actually reads: V3 gates on {@code bandit.meanCost(arm)},
     * a mean over <em>every</em> window that arm has run, against an incumbent priced from the
     * current one; V4 ranks this generation's bodies against surviving parents scored in earlier
     * generations. A generation shorter than a sampled shadow's stride sits below
     * {@link EnsembleMember#MIN_METERED_WRITES} and is stream-priced, the next may be
     * per-member-priced, and the two were then compared.
     */
    @Nested
    @DisplayName("item C — the comparability rule holds over the pool, not just within a window")
    class PoolWideComparability {

        /** A window in which the sampled lab receives fewer than MIN_METERED_WRITES writes. */
        private void shortWindow(PolicySearchController<Integer> c, Random rnd) {
            for (int i = 0; i < 70; i++) {
                c.add(rnd.nextInt(4_000));
                if (i % 7 == 0) c.contains(rnd.nextInt(4_000));
            }
        }

        private void longWindow(PolicySearchController<Integer> c, Random rnd) {
            for (int i = 0; i < 3_000; i++) {
                c.add(rnd.nextInt(4_000));
                if (i % 7 == 0) c.contains(rnd.nextInt(4_000));
            }
        }

        @Test
        @DisplayName("V3: a bandit mean is never a blend of a stream-priced and a per-member-priced window")
        void v3BanditMeanIsSingleBasis() {
            EnsembleOrderedSet<Integer> ens = ensemble()
                    .member(SplayStrategy::new)        // incumbent: a rotation thrasher
                    .member(RedBlackStrategy::new)     // the laboratory
                    .mode(EnsembleMode.SAMPLED_SHADOW)
                    .shadowSampleRate(0.1)
                    .build();
            EnsembleMember<Integer> lab = ens.members().get(1);
            PolicyGenome arm = PolicyGenome.weightBalanced(3, 2);
            PolicyBandit bandit = new PolicyBandit(List.of(arm));
            PolicySearchController<Integer> c = new PolicySearchController<>(
                    ens, lab, new RollingWorkloadMonitor(512), bandit,
                    new MorphPolicy(0, 10.0, 1));       // an unreachable margin: measure, don't promote
            Random rnd = new Random(11);

            c.beginTrial();
            shortWindow(c, rnd);
            assertTrue(lab.meteredWrites() < EnsembleMember.MIN_METERED_WRITES,
                    "non-vacuity: window 1 must genuinely be short of own-churn evidence, saw "
                            + lab.meteredWrites() + " writes");
            TrialResult w1 = c.endTrial(70);
            assertTrue(w1.scored(), w1.reason());
            assertFalse(bandit.perMemberBasis(),
                    "one unmeterable window puts the whole scoreboard on the stream basis");

            c.beginTrial();
            longWindow(c, rnd);
            assertTrue(lab.meteredWrites() >= EnsembleMember.MIN_METERED_WRITES,
                    "non-vacuity: window 2 must clear the floor, so the regimes really differ");
            TrialResult w2 = c.endTrial(3_000);
            assertTrue(w2.scored(), w2.reason());

            assertFalse(bandit.perMemberBasis(),
                    "window 2 alone could be priced per-member, but the arm's mean already holds a "
                            + "stream-priced window — a mean over a mixture is not a mean of either");
            assertTrue(Double.isNaN(bandit.meanOwnChurnCost(arm)),
                    "and the own-churn mean says so rather than reporting a blend");

            // The number the gate reads is the arithmetic mean of the two windows it actually
            // averaged, on ONE basis, and the reported per-window cost is on that same basis.
            assertEquals((w1.armCost() + w2.armCost()) / 2.0, bandit.meanCost(arm), 1e-9);
            assertEquals(bandit.meanStreamCost(arm), bandit.meanCost(arm), 1e-9);
        }

        @Test
        @DisplayName("V3: the reproduced promotion — the incumbent is priced on the basis the arm's mean is on")
        void v3IncumbentFollowsTheArmsBasis() {
            EnsembleOrderedSet<Integer> ens = ensemble()
                    .member(SplayStrategy::new)
                    .member(RedBlackStrategy::new)
                    .mode(EnsembleMode.SAMPLED_SHADOW)
                    .shadowSampleRate(0.1)
                    .build();
            EnsembleMember<Integer> primary = ens.members().get(0);
            EnsembleMember<Integer> lab     = ens.members().get(1);
            RollingWorkloadMonitor monitor = new RollingWorkloadMonitor(512);
            PolicyGenome arm = PolicyGenome.weightBalanced(3, 2);
            PolicyBandit bandit = new PolicyBandit(List.of(arm));
            PolicySearchController<Integer> c = new PolicySearchController<>(
                    ens, lab, monitor, bandit, new MorphPolicy(0, 10.0, 1));
            Random rnd = new Random(11);

            c.beginTrial();
            shortWindow(c, rnd);
            c.endTrial(70);
            c.beginTrial();
            longWindow(c, rnd);
            TrialResult w2 = c.endTrial(3_000);

            // Both sides of window 2 DO have own-churn rates — that is exactly the trap: pricing
            // this window per-member would have made its cost incomparable with window 1's, which
            // the arm's mean still carries.
            assertFalse(Double.isNaN(lab.rotationsPerWrite()));
            assertFalse(Double.isNaN(primary.rotationsPerWrite()));
            assertNotEquals(lab.rotationsPerWrite(), primary.rotationsPerWrite(), 1e-9,
                    "non-vacuity: the two policies must actually churn differently");

            var f = monitor.snapshot();
            var primSet = primary.orderedSet();
            double incumbentStream = io.github.richeyworks.csrbt.evolution.Fitness.evaluate(
                    f, io.github.richeyworks.csrbt.evolution.Fitness.meanDepth(primSet.getEngine()),
                    primSet.size()).cost();
            double incumbentOwn = io.github.richeyworks.csrbt.evolution.Fitness.evaluate(
                    primary.pricedFeatures(f),
                    io.github.richeyworks.csrbt.evolution.Fitness.meanDepth(primSet.getEngine()),
                    primSet.size()).cost();
            assertNotEquals(incumbentStream, incumbentOwn, 1e-9, "non-vacuity");
            assertEquals(incumbentStream, w2.incumbentCost(), 1e-9,
                    "the incumbent must be priced on the basis the arm's MEAN is on — before this "
                            + "it was priced per-member (" + incumbentOwn + ") and compared against "
                            + "a mean that averaged a stream-priced window in");
        }

        @Test
        @DisplayName("V3: with every window meterable the refinement is still used — the fallback is not a blanket")
        void v3StaysPerMemberWhenEveryWindowQualifies() {
            EnsembleOrderedSet<Integer> ens = ensemble()
                    .member(RedBlackStrategy::new)
                    .member(AVLStrategy::new)
                    .build();                              // MIRROR: the lab receives every write
            EnsembleMember<Integer> lab = ens.members().get(1);
            PolicyGenome arm = PolicyGenome.weightBalanced(3, 2);
            PolicyBandit bandit = new PolicyBandit(List.of(arm));
            PolicySearchController<Integer> c = new PolicySearchController<>(
                    ens, lab, new RollingWorkloadMonitor(512), bandit,
                    new MorphPolicy(0, 10.0, 1));
            Random rnd = new Random(11);

            for (int w = 0; w < 2; w++) {
                c.beginTrial();
                longWindow(c, rnd);
                assertTrue(c.endTrial(3_000).scored());
            }
            assertTrue(bandit.perMemberBasis(),
                    "every window had own-churn evidence on both sides, so the whole scoreboard is "
                            + "comparable on the per-member basis");
            assertFalse(Double.isNaN(bandit.meanOwnChurnCost(arm)));
            assertEquals(bandit.meanOwnChurnCost(arm), bandit.meanCost(arm), 1e-9);
            assertNotEquals(bandit.meanStreamCost(arm), bandit.meanCost(arm), 1e-9,
                    "non-vacuity: the two bases are different numbers");
        }

        @Test
        @DisplayName("the published one-argument recordCost still means 'no own-churn price'")
        void legacyRecordCostIsHonestlyStreamBasis() {
            PolicyGenome a = PolicyGenome.weightBalanced(3, 2);
            PolicyGenome b = PolicyGenome.weightBalanced(4, 2);
            PolicyBandit bandit = new PolicyBandit(List.of(a, b));
            bandit.recordCost(a, 0.5);                       // the 0.2.0 form
            bandit.recordCost(b, 0.4, 0.9);                  // the ADR-024 form

            assertFalse(bandit.perMemberBasis(),
                    "an arm recorded without an own-churn price cannot be ranked against one that has it");
            assertEquals(0.5, bandit.meanCost(a), 1e-9);
            assertEquals(0.4, bandit.meanCost(b), 1e-9, "b falls back to its stream price");
            assertTrue(Double.isNaN(bandit.meanOwnChurnCost(a)));
            assertEquals(0.9, bandit.meanOwnChurnCost(b), 1e-9);
            assertEquals(b, bandit.bestArm(), "ranked on the basis both arms share");
            assertThrows(IllegalArgumentException.class, () -> bandit.recordCost(a, 0.1, -1.0));
        }

        @Test
        @DisplayName("V4: a parent's carried-over cost is never ranked against a differently-priced one")
        void v4PoolRanksOnOneBasis() {
            EnsembleOrderedSet<Integer> ens = ensemble()
                    .member(RedBlackStrategy::new)
                    .member(AVLStrategy::new)
                    .member(RedBlackStrategy::new)
                    .mode(EnsembleMode.SAMPLED_SHADOW)
                    .shadowSampleRate(0.1)
                    .build();
            List<EnsembleMember<Integer>> nursery =
                    List.of(ens.members().get(1), ens.members().get(2));
            RollingWorkloadMonitor monitor = new RollingWorkloadMonitor(512);
            PolicyEvolutionController<Integer> evo = new PolicyEvolutionController<>(
                    ens, nursery, monitor, new MorphPolicy(0, 10.0, 1),
                    List.of(PolicyGenome.weightBalanced(3, 2), PolicyGenome.weightBalanced(4, 2)),
                    2, false, 20_260_817L);
            Random rnd = new Random(5);

            // Generation 1: short, so at least one body is below the metering floor.
            evo.beginGeneration();
            for (int i = 0; i < 70; i++) {
                evo.add(rnd.nextInt(4_000));
                if (i % 7 == 0) evo.contains(rnd.nextInt(4_000));
            }
            for (EnsembleMember<Integer> body : nursery) {
                assertTrue(body.meteredWrites() < EnsembleMember.MIN_METERED_WRITES,
                        "non-vacuity: generation 1 must be short of own-churn evidence");
            }
            PolicyEvolutionController.GenerationResult g1 = evo.endGeneration(70);
            assertTrue(g1.evaluated() > 0, g1.reason());

            // Generation 2: long, so every body clears the floor and the generation ALONE would
            // qualify for per-member pricing — while the pool still holds generation 1's parents.
            evo.beginGeneration();
            for (int i = 0; i < 3_000; i++) {
                evo.add(rnd.nextInt(4_000));
                if (i % 7 == 0) evo.contains(rnd.nextInt(4_000));
            }
            for (EnsembleMember<Integer> body : nursery) {
                assertTrue(body.meteredWrites() >= EnsembleMember.MIN_METERED_WRITES,
                        "non-vacuity: generation 2 must clear the floor");
            }
            PolicyEvolutionController.GenerationResult g2 = evo.endGeneration(3_000);
            assertTrue(g2.evaluated() > 0, g2.reason());

            // The reported best and incumbent are on one basis. The stream basis is forced here
            // because generation 1's survivors have no own-churn price; the check that this is
            // the STREAM basis is the pin, since per-member would mean ranking against a number
            // generation 1 never produced.
            var f = monitor.snapshot();
            var primary = ens.primary();
            var primSet = primary.orderedSet();
            double incumbentStream = io.github.richeyworks.csrbt.evolution.Fitness.evaluate(
                    f, io.github.richeyworks.csrbt.evolution.Fitness.meanDepth(primSet.getEngine()),
                    primSet.size()).cost();
            double incumbentOwn = io.github.richeyworks.csrbt.evolution.Fitness.evaluate(
                    primary.pricedFeatures(f),
                    io.github.richeyworks.csrbt.evolution.Fitness.meanDepth(primSet.getEngine()),
                    primSet.size()).cost();
            assertFalse(Double.isNaN(primary.rotationsPerWrite()),
                    "non-vacuity: the throne itself DOES have a rate this generation");
            assertNotEquals(incumbentStream, incumbentOwn, 1e-9, "non-vacuity");
            assertEquals(incumbentStream, g2.incumbentCost(), 1e-9,
                    "the throne is priced on the POOL's basis; pricing it per-member would compare "
                            + "it against carried-over parent costs that have no per-member price");
        }

        @Test
        @DisplayName("V4: with every generation meterable the pool stays on the per-member basis")
        void v4StaysPerMemberWhenEveryGenerationQualifies() {
            EnsembleOrderedSet<Integer> ens = ensemble()
                    .member(RedBlackStrategy::new)
                    .member(AVLStrategy::new)
                    .build();                              // MIRROR
            RollingWorkloadMonitor monitor = new RollingWorkloadMonitor(512);
            EnsembleMember<Integer> body = ens.members().get(1);
            PolicyEvolutionController<Integer> evo = new PolicyEvolutionController<>(
                    ens, List.of(body), monitor, new MorphPolicy(0, 10.0, 1),
                    List.of(PolicyGenome.weightBalanced(3, 2)), 1, false, 20_260_817L);
            Random rnd = new Random(5);

            PolicyEvolutionController.GenerationResult last = null;
            for (int g = 0; g < 2; g++) {
                evo.beginGeneration();
                for (int i = 0; i < 3_000; i++) {
                    evo.add(rnd.nextInt(4_000));
                    if (i % 7 == 0) evo.contains(rnd.nextInt(4_000));
                }
                last = evo.endGeneration(3_000);
            }

            var f = monitor.snapshot();
            var primary = ens.primary();
            var primSet = primary.orderedSet();
            double incumbentOwn = io.github.richeyworks.csrbt.evolution.Fitness.evaluate(
                    primary.pricedFeatures(f),
                    io.github.richeyworks.csrbt.evolution.Fitness.meanDepth(primSet.getEngine()),
                    primSet.size()).cost();
            double incumbentStream = io.github.richeyworks.csrbt.evolution.Fitness.evaluate(
                    f, io.github.richeyworks.csrbt.evolution.Fitness.meanDepth(primSet.getEngine()),
                    primSet.size()).cost();
            assertNotEquals(incumbentStream, incumbentOwn, 1e-9, "non-vacuity");
            assertEquals(incumbentOwn, last.incumbentCost(), 1e-9,
                    "every generation had own-churn evidence for every body and the throne, so the "
                            + "pool is comparable per-member and the refinement is used");
        }
    }

    // ── Item D ──────────────────────────────────────────────────────────────────────────

    /**
     * The ADR-024 meters are written on the write path under {@code EnsembleOrderedSet}'s
     * {@code writeLock} and read, unsynchronized, from the controller thread. They were plain
     * {@code long}s while every other cross-thread field on the class is {@code volatile} or
     * atomic — and JLS 17.7 permits a non-volatile 64-bit write to be seen as two halves.
     */
    @Nested
    @DisplayName("item D — the rotation meter's memory model matches its access pattern")
    class MeterMemoryModel {

        @Test
        @DisplayName("every meter word is volatile, like the class's other cross-thread state")
        void meterFieldsAreVolatile() throws Exception {
            for (String name : List.of("rotationMark", "meteredRotations", "meteredWrites",
                                       "meterVersion")) {
                Field f = EnsembleMember.class.getDeclaredField(name);
                assertTrue(Modifier.isVolatile(f.getModifiers()),
                        name + " is read without a lock from the controller thread and written on "
                                + "the write path; a plain long may tear (JLS 17.7)");
            }
            // Non-vacuity for the "class's own convention" claim the fix rests on.
            assertTrue(Modifier.isVolatile(EnsembleMember.class.getDeclaredField("state").getModifiers()));
            assertTrue(Modifier.isVolatile(EnsembleMember.class.getDeclaredField("exact").getModifiers()));
        }

        @Test
        @DisplayName("a reader racing the write path never sees a torn or half-updated meter")
        void meterIsSafelyPublishedAcrossThreads() throws Exception {
            EnsembleOrderedSet<Integer> ens = ensemble()
                    .member(RedBlackStrategy::new)
                    .member(SplayStrategy::new)
                    .build();
            EnsembleMember<Integer> watched = ens.members().get(1);

            CountDownLatch go = new CountDownLatch(1);
            AtomicReference<String> fault = new AtomicReference<>();
            AtomicInteger observations = new AtomicInteger();

            Thread reader = new Thread(() -> {
                try {
                    go.await();
                    for (int i = 0; i < 200_000; i++) {
                        long rots = watched.meteredRotations();
                        long writes = watched.meteredWrites();
                        double rate = watched.rotationsPerWrite();
                        if (rots < 0 || writes < 0) {
                            fault.compareAndSet(null, "negative meter: " + rots + "/" + writes);
                            return;
                        }
                        if (!Double.isNaN(rate) && (rate < 0.0 || rate > 64.0)) {
                            fault.compareAndSet(null, "impossible rate " + rate
                                    + " (a torn pair, or a numerator paired with the wrong denominator)");
                            return;
                        }
                        observations.incrementAndGet();
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }, "meter-reader");
            reader.setDaemon(true);
            reader.start();
            go.countDown();

            Random rnd = new Random(3);
            for (int i = 0; i < 40_000; i++) {
                if (rnd.nextInt(100) < 80) ens.add(rnd.nextInt(6_000));
                else ens.remove(rnd.nextInt(6_000));
                if (i % 5_000 == 0) ens.resetRotationMeters();
            }
            reader.join(30_000);
            assertFalse(reader.isAlive(), "the reader must terminate");
            assertNull(fault.get(), () -> String.valueOf(fault.get()));
            assertTrue(observations.get() > 0, "non-vacuity: the reader must actually have read");

            // The meter is still exactly right sequentially — the fix costs no accuracy.
            ens.resetRotationMeters();
            long before = watched.orderedSet().rotationCount();
            for (int i = 0; i < 100; i++) ens.add(1_000_000 + i);
            assertEquals(100L, watched.meteredWrites());
            assertEquals(watched.orderedSet().rotationCount() - before, watched.meteredRotations());
        }
    }

    // ── Item E ──────────────────────────────────────────────────────────────────────────

    /**
     * {@code TreeContext} hard-wired {@code new FilePersistenceAdapter()} with no way to supply
     * another, so {@link TreePersistenceAdapter} — a published seam whose {@code default} methods
     * exist for third-party implementors (ADR-025/026) — could not be used with the facade that is
     * its main in-repo consumer. Both additions are purely additive: 0.2.1-safe.
     */
    @Nested
    @DisplayName("item E — the persistence adapter is injectable")
    class InjectablePersistenceAdapter {

        /** A third-party adapter: an in-memory store that records what it was asked to do. */
        private static final class RecordingAdapter implements TreePersistenceAdapter {
            final Map<String, TreeContext> store = new java.util.LinkedHashMap<>();
            final List<String> calls = new ArrayList<>();

            @Override public void saveSnapshot(String name, TreeContext snapshot) {
                calls.add("save:" + name);
                store.put(name, snapshot);
            }
            @Override public TreeContext loadSnapshot(String name) {
                calls.add("load:" + name);
                return store.get(name);
            }
            @Override public List<String> listSnapshots() { return List.copyOf(store.keySet()); }
            @Override public boolean deleteSnapshot(String name) {
                calls.add("delete:" + name);
                return store.remove(name) != null;
            }
        }

        @Test
        @DisplayName("the constructor overload consults the injected adapter and never touches the disk")
        void constructorInjectionIsConsulted() {
            RecordingAdapter mem = new RecordingAdapter();
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>(), mem);
            assertSame(mem, ctx.getPersistenceAdapter());

            for (int i = 1; i <= 6; i++) ctx.add(i);
            ctx.saveSnapshot("inmem");
            assertEquals(List.of("save:inmem"), mem.calls);
            assertFalse(Files.exists(DIR.resolve("inmem.rbt")),
                    "an injected adapter means no file adapter ran");

            ctx.clear();
            assertEquals(0, ctx.size());
            ctx.loadSnapshot("inmem");
            assertEquals(List.of("save:inmem", "load:inmem"), mem.calls);
            assertEquals(List.of(1, 2, 3, 4, 5, 6), ctx.inOrder(),
                    "the round trip really went through the injected adapter");
        }

        @Test
        @DisplayName("the setter reaches a context this caller did not construct")
        void setterInjectionIsConsulted() {
            RecordingAdapter mem = new RecordingAdapter();
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            assertTrue(ctx.getPersistenceAdapter() instanceof
                    io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter,
                    "the default is unchanged");
            ctx.setPersistenceAdapter(mem);

            for (int i = 1; i <= 3; i++) ctx.add(i);
            ctx.saveSnapshot("swapped");
            ctx.loadSnapshot("missing");                 // the adapter's null, honestly reported
            assertEquals(List.of("save:swapped", "load:missing"), mem.calls);
            assertEquals(List.of(1, 2, 3), ctx.inOrder(), "a failed load leaves the context alone");
            assertThrows(NullPointerException.class, () -> ctx.setPersistenceAdapter(null));
            assertThrows(NullPointerException.class,
                    () -> new TreeContext(new RedBlackStrategy<>(), null));
        }

        @Test
        @DisplayName("an injected adapter that only implements the 0.2.0 seam still works through the facade")
        void theAdditiveDefaultsCarryTheFacade() {
            RecordingAdapter mem = new RecordingAdapter();      // overrides neither try* method
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>(), mem);
            for (int i = 1; i <= 4; i++) ctx.add(i);
            ctx.saveSnapshot("legacyseam");                     // UNREPORTED, not a fabricated SAVED
            ctx.clear();
            ctx.loadSnapshot("legacyseam");
            assertEquals(List.of(1, 2, 3, 4), ctx.inOrder(),
                    "the ADR-025/026 defaults are what make a 0.2.0-era adapter usable here");
        }
    }

    // ── Item G ──────────────────────────────────────────────────────────────────────────

    @Nested
    @DisplayName("item G — createNodeWithAugment is documented as the trap it is")
    class CreateNodeWithAugmentIsDeprecated {

        @Test
        @DisplayName("the stamped value does not survive the first re-augment — the reason for the deprecation")
        void theStampedValueDoesNotSurvive() throws Exception {
            TreeNode1<Integer> nil = TreeNode1.createNil(Comparator.<Integer>naturalOrder());
            @SuppressWarnings("deprecation")
            TreeNode1<Integer> node = TreeNode1.createNodeWithAugment(42, nil, 999);
            assertEquals(999, node.getAugmentedValue(), "it survives construction...");

            node.setLeft(TreeNode1.createNode(7, nil));         // any structural link re-augments
            assertEquals(2, node.getAugmentedValue(),
                    "...and no longer: the default augmentor recomputes the slot as a subtree "
                            + "count, so the caller's value lasts until the very next link");

            assertTrue(TreeNode1.class
                            .getMethod("createNodeWithAugment", Object.class, TreeNode1.class, int.class)
                            .isAnnotationPresent(Deprecated.class),
                    "it is public on a published 0.2.0 module, so it is deprecated rather than "
                            + "deleted — removing it would force 0.3.0");
        }

        @Test
        @DisplayName("the documented replacement does survive: supply the augmentor, not a constant")
        void theAugmentorFormSurvives() {
            TreeNode1<Integer> nil = TreeNode1.createNil(Comparator.<Integer>naturalOrder());
            TreeNode1<Integer> node = new TreeNode1<>(42, nil, n -> n.setAugmentedValue(999));
            assertEquals(999, node.getAugmentedValue());
            node.setLeft(TreeNode1.createNode(7, nil));
            assertEquals(999, node.getAugmentedValue(),
                    "an augmentor is re-applied on every link; a stamped constant is not");
        }
    }

    // ── Item H ──────────────────────────────────────────────────────────────────────────

    /**
     * {@code tournament} / {@code formatTournament} are the ADR-022 battle surface's top level —
     * public, and the only part of it with no caller and no test ({@code run} and
     * {@code formatBattle}, which they wrap, are both covered). Timing is machine-dependent, so
     * these pin structure and bookkeeping, never a winner.
     */
    @Nested
    @DisplayName("item H — the ADR-022 tournament surface is covered")
    class BattleTournament {

        @Test
        @DisplayName("a tournament runs every workload, ranks every competitor, and is reproducible")
        void tournamentCoversEveryWorkload() {
            Map<WorkloadType, List<BattleResult>> t = StrategyBattleRunner.tournament(400, 21L);

            assertEquals(WorkloadType.values().length, t.size(), "one battle per workload type");
            assertEquals(List.of(WorkloadType.values()), List.copyOf(t.keySet()),
                    "in declaration order — the report reads top to bottom");

            for (Map.Entry<WorkloadType, List<BattleResult>> e : t.entrySet()) {
                List<BattleResult> results = e.getValue();
                assertEquals(4, results.size(), e.getKey() + ": all four competitors ran");
                for (int i = 0; i < results.size(); i++) {
                    BattleResult r = results.get(i);
                    assertEquals(e.getKey(), r.workload, "each result is tagged with its own battle");
                    assertEquals(i + 1, r.rank, e.getKey() + ": ranks are 1..4 in returned order");
                    assertTrue(r.totalOps > 0 && r.totalTimeNs > 0, e.getKey() + ": a battle really ran");
                    assertTrue(r.finalSize > 0, e.getKey() + ": every competitor holds a tree");
                }
                assertEquals(4, results.stream().map(r -> r.strategyName).distinct().count(),
                        e.getKey() + ": four distinct competitors");
            }

            // Same seed, same workload for every competitor: the sizes are the deterministic part.
            Map<WorkloadType, List<BattleResult>> again = StrategyBattleRunner.tournament(400, 21L);
            for (WorkloadType wl : WorkloadType.values()) {
                List<Integer> a = t.get(wl).stream().map(r -> r.finalSize).sorted().toList();
                List<Integer> b = again.get(wl).stream().map(r -> r.finalSize).sorted().toList();
                assertEquals(a, b, wl + ": the workload is seeded, so contents reproduce");
            }
        }

        @Test
        @DisplayName("formatTournament prints every battle plus a leaderboard whose wins total the battles")
        void formatTournamentPrintsEveryBattleAndTheLeaderboard() {
            Map<WorkloadType, List<BattleResult>> t = StrategyBattleRunner.tournament(400, 22L);
            String report = StrategyBattleRunner.formatTournament(t);

            for (WorkloadType wl : WorkloadType.values()) {
                assertTrue(report.contains("BATTLE: " + wl), "missing the " + wl + " table");
            }
            assertTrue(report.contains("TOURNAMENT LEADERBOARD"), report);
            for (String name : List.of("RedBlack", "AVL", "Splay", "Hybrid")) {
                assertTrue(report.contains(name), name + " must appear on the leaderboard");
            }

            // Every battle awards exactly one win, so the printed win counts must sum to the
            // number of battles — the one arithmetic claim the leaderboard makes.
            int total = 0;
            for (String line : report.split("\n")) {
                int at = line.indexOf("wins: ");
                if (at < 0) continue;
                String tail = line.substring(at + "wins: ".length()).trim();
                total += Integer.parseInt(tail.substring(0, tail.indexOf(' ')));
            }
            assertEquals(WorkloadType.values().length, total,
                    "one rank-1 win per battle, no more and no fewer:\n" + report);
        }

        @Test
        @DisplayName("formatTournament of an empty tournament is still a report, not a crash")
        void emptyTournamentFormats() {
            String report = StrategyBattleRunner.formatTournament(new EnumMap<>(WorkloadType.class));
            assertTrue(report.contains("TOURNAMENT LEADERBOARD"), report);
            for (String name : List.of("RedBlack", "AVL", "Splay", "Hybrid")) {
                assertTrue(report.contains(name + "  "), name + " is listed with zero wins:\n" + report);
            }
        }
    }
}
