package test.core;

import core.OrderedSet;
import core.control.MorphController;
import core.control.MorphController.MorphResult;
import core.control.MorphPolicy;
import core.control.StrategyId;
import core.control.StrategyMorphTarget;
import core.control.StrategyScorer;
import core.control.WorkloadFeatures;
import core.control.WorkloadMonitor;
import core.strategy.RedBlackStrategy;
import core.strategy.TreeStrategy;

import org.apache.logging.log4j.Level;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Property;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * core.control.MorphController (ADR-002 step 6, Phase D / D1): orchestration of one
 * evaluation, the MorphResult contract, health-fail-keeps-incumbent (G6), and exactly one
 * event=morph_eval line per evaluation (G9). Monitor/scorer/policy are hand-fed; the real
 * OrderedSet executor is exercised through the StrategyMorphTarget seam.
 */
@DisplayName("core.control.MorphController (Phase D / D1)")
public class MorphControllerTest {

    private static WorkloadMonitor fixedMonitor(WorkloadFeatures f) {
        return new WorkloadMonitor() {
            @Override public void recordAdd(int keyHash, int rotations) { }
            @Override public void recordRemove(int keyHash, int rotations) { }
            @Override public void recordSearch(int keyHash, int depthTouched) { }
            @Override public WorkloadFeatures snapshot() { return f; }
        };
    }

    private static StrategyScorer fixedScorer(StrategyScorer.Score... ranked) {
        final List<StrategyScorer.Score> list = Arrays.asList(ranked);
        return features -> list;
    }

    private static StrategyScorer.Score sc(StrategyId id, double cost) {
        return new StrategyScorer.Score(id, cost, id + " @" + cost);
    }

    private static WorkloadFeatures anyFeatures() {
        return new WorkloadFeatures(0.94, 0.06, 0.71, 14.2, 0.3, 9_120L, 12.0);
    }

    /** An eager policy (no cooldown, 10% margin, one win) to keep the streak warm-up short. */
    private static MorphPolicy eager() { return new MorphPolicy(0, 0.10, 1); }

    /** A target that always rejects the swap — stands in for a health-gate failure. */
    private static final class FailingTarget implements StrategyMorphTarget<Integer> {
        private final TreeStrategy<Integer> incumbent;
        int attempts = 0;
        FailingTarget(TreeStrategy<Integer> incumbent) { this.incumbent = incumbent; }
        @Override public boolean setStrategy(TreeStrategy<Integer> s) { attempts++; return false; }
        @Override public TreeStrategy<Integer> getStrategy() { return incumbent; }
    }

    @Test
    @DisplayName("HOLD when the incumbent is already cheapest: no swap, clock advances")
    void holdsWhenIncumbentCheapest() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        set.add(1); set.add(2); set.add(3);
        MorphController<Integer> mc = new MorphController<>(
                set, fixedMonitor(anyFeatures()),
                fixedScorer(sc(StrategyId.RED_BLACK, 0.30), sc(StrategyId.AVL, 0.50)),
                eager());

        MorphResult r = mc.evaluateAndMaybeMorph(StrategyId.RED_BLACK, 10);

        assertFalse(r.morphed());
        assertEquals(StrategyId.RED_BLACK, r.from());
        assertEquals(StrategyId.RED_BLACK, r.to());
        assertEquals("RedBlackStrategy", set.getStrategy().getClass().getSimpleName());
        assertEquals(10, mc.history().opsSinceLastMorph(), "a hold advances the cooldown clock");
    }

    @Test
    @DisplayName("MORPH against the real OrderedSet executor swaps strategy and resets cooldown")
    void morphsAgainstRealExecutor() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int v : new int[]{50, 20, 80, 10, 30, 60, 90}) set.add(v);
        List<Integer> before = set.inOrder();

        MorphController<Integer> mc = new MorphController<>(
                set, fixedMonitor(anyFeatures()),
                fixedScorer(sc(StrategyId.SPLAY, 0.40), sc(StrategyId.RED_BLACK, 0.78)),
                eager());

        // stabilityWins=1 needs one prior observation; the first eval only credits the streak.
        MorphResult warm = mc.evaluateAndMaybeMorph(StrategyId.RED_BLACK, 10);
        assertFalse(warm.morphed(), "first eval just credits the win streak");
        assertEquals("RedBlackStrategy", set.getStrategy().getClass().getSimpleName());

        MorphResult r = mc.evaluateAndMaybeMorph(StrategyId.RED_BLACK, 10);

        assertTrue(r.morphed(), "all gates clear on the second eval");
        assertTrue(r.healthPassed(), "the real health gate passes for Splay");
        assertEquals(StrategyId.RED_BLACK, r.from());
        assertEquals(StrategyId.SPLAY, r.to());
        assertEquals("SplayStrategy", set.getStrategy().getClass().getSimpleName(),
                "the live executor actually swapped");
        assertEquals(before, set.inOrder(), "contents preserved across the morph");
        assertEquals(0, mc.history().opsSinceLastMorph(), "a committed morph resets the cooldown clock");
        assertTrue(r.buildNanos() >= 0L);
    }

    @Test
    @DisplayName("a health-rejected candidate keeps the incumbent and counts as a hold")
    void healthRejectedKeepsIncumbent() {
        FailingTarget target = new FailingTarget(new RedBlackStrategy<Integer>());
        MorphController<Integer> mc = new MorphController<>(
                target, fixedMonitor(anyFeatures()),
                fixedScorer(sc(StrategyId.AVL, 0.30), sc(StrategyId.RED_BLACK, 0.78)),
                eager());

        mc.evaluateAndMaybeMorph(StrategyId.RED_BLACK, 10);            // warm-up HOLD (streak=1)
        MorphResult r = mc.evaluateAndMaybeMorph(StrategyId.RED_BLACK, 10);

        assertEquals(1, target.attempts, "the controller attempted exactly one swap");
        assertFalse(r.morphed(), "a rejected swap is not a morph");
        assertFalse(r.healthPassed(), "the gate verdict is reported");
        assertEquals(StrategyId.RED_BLACK, r.to(), "incumbent retained on rejection");
        assertEquals(20, mc.history().opsSinceLastMorph(),
                "a rejected morph advances the clock like a hold (no reset)");
    }

    @Test
    @DisplayName("exactly one event=morph_eval line is emitted per evaluation (G9)")
    void emitsOneLinePerEval() {
        Logger coreLogger = (Logger) LogManager.getLogger(MorphController.class);
        coreLogger.setLevel(Level.INFO);                 // root is WARN; the line logs at INFO
        CapturingAppender cap = new CapturingAppender("morphCtrlCap");
        cap.start();
        coreLogger.addAppender(cap);
        try {
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            set.add(1); set.add(2);
            MorphController<Integer> mc = new MorphController<>(
                    set, fixedMonitor(anyFeatures()),
                    fixedScorer(sc(StrategyId.RED_BLACK, 0.30), sc(StrategyId.AVL, 0.50)),
                    eager());
            mc.evaluateAndMaybeMorph(StrategyId.RED_BLACK, 10);
        } finally {
            coreLogger.removeAppender(cap);
            cap.stop();
        }
        int n = 0;
        for (String m : cap.messages) if (m.contains("event=morph_eval")) n++;
        assertEquals(1, n, "exactly one morph_eval line per evaluation");
    }

    /** Minimal programmatic Log4j2 appender that records formatted messages. */
    private static final class CapturingAppender extends AbstractAppender {
        final List<String> messages = Collections.synchronizedList(new ArrayList<>());
        CapturingAppender(String name) {
            super(name, null, null, true, Property.EMPTY_ARRAY);
        }
        @Override public void append(LogEvent event) {
            messages.add(event.getMessage().getFormattedMessage());
        }
    }
}
