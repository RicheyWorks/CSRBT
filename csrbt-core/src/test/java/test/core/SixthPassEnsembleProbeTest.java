package test.core;

import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.control.StrategyId;
import io.github.richeyworks.csrbt.control.StrategyScorer;
import io.github.richeyworks.csrbt.control.WorkloadFeatures;
import io.github.richeyworks.csrbt.ensemble.EnsembleController;
import io.github.richeyworks.csrbt.ensemble.EnsembleController.PromotionResult;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.ensemble.MemberExecutor;
import io.github.richeyworks.csrbt.ensemble.ParallelMemberExecutor;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Function;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Sixth-pass audit (2026-08-17) — the ensemble half: findings 9 (a dead promotion target crashed
 * the control loop), 18 (strategy identity was frozen at construction), 10 (a shutdown racing a
 * fan-out parked the writer forever, under the write lock) and 39 (an unsafely published
 * per-instance vote pin).
 *
 * <p>The concurrency probes run their blocking half on a daemon thread and {@code join} with a
 * timeout, so a regression <em>fails</em> the suite instead of hanging it (and cannot keep the
 * test JVM alive).</p>
 */
@DisplayName("Sixth-pass audit — ensemble control loop and fan-out lifecycle")
class SixthPassEnsembleProbeTest {

    /** RB primary + AVL + Splay, the shape EnsembleControllerTest uses. */
    private static EnsembleOrderedSet<Integer> rbAvlSplay() {
        return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())   // initial primary
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new SplayStrategy<Integer>())
                .build();
    }

    /** A scorer that is a pure lookup table: the ranking the test wants, ascending cost. */
    private static StrategyScorer fixedScorer(StrategyId cheapest, StrategyId... rest) {
        List<StrategyScorer.Score> ranked = new ArrayList<>();
        ranked.add(new StrategyScorer.Score(cheapest, 0.10, "pinned cheapest by the probe"));
        double cost = 0.90;
        for (StrategyId id : rest) {
            ranked.add(new StrategyScorer.Score(id, cost, "pinned expensive by the probe"));
            cost += 0.01;
        }
        return features -> ranked;
    }

    // ── Finding 9: a dead promotion target is a hold, not an IllegalStateException ──

    @Test
    @DisplayName("finding 9: a retired member the scorer ranks best is skipped, not promoted into a crash")
    void retiredPromotionTargetIsAHoldNotACrash() {
        EnsembleOrderedSet<Integer> ens = rbAvlSplay();
        for (int i = 0; i < 64; i++) ens.add(i);

        EnsembleMember<Integer> rb    = ens.members().get(0);
        EnsembleMember<Integer> avl   = ens.members().get(1);
        EnsembleMember<Integer> splay = ens.members().get(2);
        assertTrue(ens.retire(avl), "the AVL member is retired — never served, fanned to, or promoted");
        ens.quarantine(splay);

        // The scorer insists the retired AVL member is the cheapest thing in the world; gates wide open.
        EnsembleController<Integer> c = new EnsembleController<>(
                ens, new RollingWorkloadMonitor(512),
                fixedScorer(StrategyId.AVL, StrategyId.RED_BLACK, StrategyId.SPLAY),
                new MorphPolicy(0, 0.05, 1));

        // Pre-fix this threw IllegalStateException("cannot promote a non-active member") — and on
        // EVERY subsequent evaluation, because the index was never pruned.
        PromotionResult first = assertDoesNotThrow(() -> c.evaluateAndMaybePromote(1_000));
        assertFalse(first.promoted(), "a retired member must never be promoted: " + first.reason());
        assertSame(rb, ens.primary(), "the healthy primary keeps serving");

        PromotionResult second = assertDoesNotThrow(() -> c.evaluateAndMaybePromote(1_000));
        assertFalse(second.promoted());
        assertEquals(StrategyId.RED_BLACK, c.currentPrimaryId());
        assertEquals(64, ens.size(), "the hold cost the logical set nothing");
    }

    @Test
    @DisplayName("finding 9: healing the member back to ACTIVE makes it promotable again")
    void healedMemberBecomesPromotableAgain() {
        EnsembleOrderedSet<Integer> ens = rbAvlSplay();
        for (int i = 0; i < 64; i++) ens.add(i);
        EnsembleMember<Integer> avl = ens.members().get(1);
        ens.quarantine(avl);

        EnsembleController<Integer> c = new EnsembleController<>(
                ens, new RollingWorkloadMonitor(512),
                fixedScorer(StrategyId.AVL, StrategyId.RED_BLACK, StrategyId.SPLAY),
                new MorphPolicy(0, 0.05, 1));

        // Two evaluations: MorphPolicy's stability gate needs one observed win before it will switch.
        assertFalse(c.evaluateAndMaybePromote(1_000).promoted(), "quarantined: not a candidate");
        assertFalse(c.evaluateAndMaybePromote(1_000).promoted(), "still quarantined: still not a candidate");
        assertTrue(ens.healFromPrimary(avl), "heal returns it to ACTIVE");

        PromotionResult after = null;
        for (int i = 0; i < 4 && (after == null || !after.promoted()); i++) {
            after = c.evaluateAndMaybePromote(1_000);
        }
        assertTrue(after.promoted(), "an ACTIVE member the scorer ranks first is promotable: " + after.reason());
        assertSame(avl, ens.primary());
    }

    // ── Finding 18: strategy identity is read live, never from a construction-time index ──

    @Test
    @DisplayName("finding 18: a member morphed behind the controller's back is reported by what it runs now")
    void controllerReportsLiveStrategyIdentity() {
        EnsembleOrderedSet<Integer> ens = rbAvlSplay();
        for (int i = 0; i < 128; i++) ens.add(i);
        EnsembleMember<Integer> body = ens.members().get(1);           // built as AVL
        assertEquals("AVLStrategy", body.strategyName());

        EnsembleController<Integer> c = new EnsembleController<>(
                ens, new RollingWorkloadMonitor(512),
                fixedScorer(StrategyId.HYBRID, StrategyId.RED_BLACK, StrategyId.SPLAY),
                new MorphPolicy(0, 0.05, 1));
        assertEquals(StrategyId.RED_BLACK, c.currentPrimaryId());

        // Exactly what PolicySearchController.beginTrial / PolicyEvolutionController.beginGeneration
        // do by design: setStrategy on a member the controller also indexes.
        assertTrue(body.orderedSet().setStrategy(new HybridStrategy<Integer>()));
        assertEquals("HybridStrategy", body.strategyName(),
                "the member's label must follow its live strategy, not the one it was built with");

        // The controller must now SEE a Hybrid candidate that did not exist at construction.
        // (Two passes minimum: MorphPolicy's stability gate wants one observed win first.)
        PromotionResult r = null;
        for (int i = 0; i < 4 && (r == null || !r.promoted()); i++) {
            r = c.evaluateAndMaybePromote(1_000);
        }
        assertTrue(r.promoted(), "the live Hybrid member must be promotable: " + r.reason());
        assertEquals(StrategyId.HYBRID, r.to(), "the promotion must name the strategy actually promoted");
        assertSame(body, ens.primary());

        // ...and currentPrimaryId must track a morph of the serving member itself.
        assertEquals(StrategyId.HYBRID, c.currentPrimaryId());
        assertTrue(ens.primary().orderedSet().setStrategy(new AVLStrategy<Integer>()));
        assertEquals(StrategyId.AVL, c.currentPrimaryId(),
                "currentPrimaryId must read the primary's live strategy");
    }

    // ── Finding 10: a shutdown racing a fan-out can never park the writer ──

    @Test
    @DisplayName("finding 10: shutdown() during an in-flight fan-out returns outcomes instead of parking forever")
    void shutdownDuringFanOutDoesNotPark() throws Exception {
        ParallelMemberExecutor exec = new ParallelMemberExecutor(1);   // one worker: member 2 must queue
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new SplayStrategy<Integer>())
                .executor(exec)
                .build();
        List<EnsembleMember<Integer>> ms = ens.members();

        CountDownLatch occupied = new CountDownLatch(1);
        CountDownLatch release  = new CountDownLatch(1);
        Function<EnsembleMember<Integer>, Boolean> op = m -> {
            if (m == ms.get(1)) {                 // the member holding the single worker
                occupied.countDown();
                try {
                    release.await(30, TimeUnit.SECONDS);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }
            return true;
        };

        AtomicReference<List<MemberExecutor.Outcome>> outcomes = new AtomicReference<>();
        AtomicReference<Throwable> escaped = new AtomicReference<>();
        Thread writer = new Thread(() -> {
            try {
                outcomes.set(exec.apply(ms, op));
            } catch (Throwable t) {
                escaped.set(t);
            }
        }, "sixth-pass-fanout-writer");
        writer.setDaemon(true);                    // a regression must not keep the test JVM alive
        writer.start();

        assertTrue(occupied.await(15, TimeUnit.SECONDS), "the fan-out never reached the pool");
        exec.shutdown();                           // drains member 2's task out of the queue
        writer.join(20_000);
        release.countDown();

        assertFalse(writer.isAlive(),
                "the fan-out parked forever on an orphaned FutureTask (finding 10)");
        assertNull(escaped.get(), "apply() must report failures, never propagate them: " + escaped.get());
        List<MemberExecutor.Outcome> got = outcomes.get();
        assertNotNull(got);
        assertEquals(3, got.size(), "one outcome per member, in input order");
        assertFalse(got.get(0).failed(), "member 0 ran on the caller's thread and committed");
        assertTrue(got.get(2).failed(),
                "the drained member never received the write and must be reported failed, not silently skipped");
    }

    @Test
    @DisplayName("finding 10: close() during an in-flight write terminates, and later writes fail deterministically")
    void closeDuringInFlightWriteTerminates() throws Exception {
        EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                .member(() -> new RedBlackStrategy<Integer>())
                .member(() -> new AVLStrategy<Integer>())
                .member(() -> new SplayStrategy<Integer>())
                .executor(new ParallelMemberExecutor(1))
                .build();

        CountDownLatch running = new CountDownLatch(1);
        AtomicReference<Throwable> escaped = new AtomicReference<>();
        Thread writer = new Thread(() -> {
            try {
                for (int i = 0; i < 200_000; i++) {
                    ens.add(i);
                    if (i == 200) running.countDown();
                }
            } catch (IllegalStateException closedAsExpected) {
                // the deterministic outcome: the ensemble refuses writes once closed
            } catch (Throwable t) {
                escaped.set(t);
            }
        }, "sixth-pass-close-writer");
        writer.setDaemon(true);
        writer.start();

        assertTrue(running.await(15, TimeUnit.SECONDS), "the writer never started");
        ens.close();                               // races a fan-out that is genuinely in flight
        writer.join(30_000);

        assertFalse(writer.isAlive(),
                "close() parked the writer inside the fan-out while it held the write lock (finding 10)");
        assertNull(escaped.get(), "close must not surface as a RejectedExecutionException: " + escaped.get());
        assertTrue(ens.isClosed());
        assertThrows(IllegalStateException.class, () -> ens.add(-1),
                "a write after close must be a deterministic exception, not a hang or a half-mutation");
        assertThrows(IllegalStateException.class, ens::clear);
        assertDoesNotThrow(ens::close, "close is idempotent");
        assertDoesNotThrow(ens::size, "a closed ensemble is a frozen snapshot, still readable");
    }

    // ── Finding 39: the per-instance vote pin is safely published ──

    @Test
    @DisplayName("finding 39: optimisticVotesOverride is safely published (final), and the pin still holds")
    void optimisticVotesPinIsSafelyPublished() throws Exception {
        Field f = EnsembleOrderedSet.class.getDeclaredField("optimisticVotesOverride");
        int mods = f.getModifiers();
        assertTrue(Modifier.isFinal(mods) || Modifier.isVolatile(mods),
                "an unsafely published pin lets a reader see null and fall back to the process-global "
                + "static the pin exists to escape (AUDIT_2026-07-21 F-P2)");

        boolean saved = EnsembleOrderedSet.OPTIMISTIC_VOTES;
        try {
            for (boolean pin : new boolean[] { true, false }) {
                EnsembleOrderedSet<Integer> ens =
                        EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                                .member(() -> new RedBlackStrategy<Integer>())
                                .member(() -> new AVLStrategy<Integer>())
                                .member(() -> new SplayStrategy<Integer>())
                                .mode(EnsembleMode.VERIFIED)
                                .optimisticVotes(pin)
                                .build();
                EnsembleOrderedSet.OPTIMISTIC_VOTES = !pin;     // the static says the opposite
                for (int i = 0; i < 64; i++) ens.add(i);
                for (int i = 0; i < 64; i++) assertTrue(ens.contains(i), "pin=" + pin);
                assertEquals(64, ens.size());
                for (EnsembleMember<Integer> m : ens.members()) {
                    assertTrue(m.isActive(), "healthy members must survive every vote path, pin=" + pin);
                }
            }
        } finally {
            EnsembleOrderedSet.OPTIMISTIC_VOTES = saved;
        }
    }
}
