package test.core;

import core.TreeContext;
import core.strategy.RedBlackStrategy;
import core.util.OrderStatisticsOps;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Sliding-window / bounded-set semantics (DESIGN goal G2): a capacity-limited set
 * that evicts the oldest-inserted key first, keeping order statistics exact on the
 * survivors.
 */
@DisplayName("Sliding-window eviction")
public class WindowingTest {

    private static List<Integer> range(int loInclusive, int hiInclusive) {
        List<Integer> xs = new ArrayList<>();
        for (int i = loInclusive; i <= hiInclusive; i++) xs.add(i);
        return xs;
    }

    @Test
    @DisplayName("window keeps only the most-recent N keys")
    void keepsRecent() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy());
        ctx.setMaxSize(10);
        for (int i = 1; i <= 100; i++) ctx.add(i);

        assertEquals(10, ctx.getSize());
        assertEquals(range(91, 100), ctx.inOrder());
        assertTrue(ctx.contains(91) && ctx.contains(100));
        assertFalse(ctx.contains(90), "the 90th key should have been evicted");
    }

    @Test
    @DisplayName("order statistics stay exact on the surviving window")
    void orderStatsOnSurvivors() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy());
        ctx.setMaxSize(20);
        for (int i = 0; i < 500; i++) ctx.add(i);   // survivors: 480..499

        List<Integer> survivors = range(480, 499);
        assertEquals(survivors, ctx.inOrder());

        OrderStatisticsOps os = new OrderStatisticsOps(ctx.getTree());
        assertEquals(480, os.select(1).getData(), "min of the window");
        assertEquals(499, os.select(20).getData(), "max of the window");
        assertEquals(10, os.rank(489), "rank within the window");
        assertEquals(survivors.get(9), os.median().getData());
    }

    @Test
    @DisplayName("setMaxSize shrinks an existing set to the most-recent keys")
    void setMaxSizeShrinks() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy());
        for (int i = 1; i <= 20; i++) ctx.add(i);   // unbounded so far
        assertEquals(20, ctx.getSize());

        ctx.setMaxSize(5);
        assertEquals(5, ctx.getSize());
        assertEquals(range(16, 20), ctx.inOrder());
    }

    @Test
    @DisplayName("eviction respects FIFO order across interleaved removes")
    void fifoWithRemoves() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy());
        ctx.setMaxSize(3);
        ctx.add(1); ctx.add(2); ctx.add(3);   // {1,2,3}
        ctx.remove(2);                         // {1,3}, order [1,3]
        ctx.add(4);                            // {1,3,4} (at capacity, no evict)
        ctx.add(5);                            // over capacity → evict oldest (1)
        assertEquals(List.of(3, 4, 5), ctx.inOrder());
        assertFalse(ctx.contains(1));
    }

    @Test
    @DisplayName("default is unbounded (no eviction)")
    void unboundedByDefault() {
        TreeContext ctx = new TreeContext(new RedBlackStrategy());
        assertEquals(0, ctx.getMaxSize());
        for (int i = 0; i < 1000; i++) ctx.add(i);
        assertEquals(1000, ctx.getSize());
    }
}
