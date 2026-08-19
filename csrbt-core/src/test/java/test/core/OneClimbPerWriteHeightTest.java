package test.core;

import io.github.richeyworks.csrbt.MutableTree;
import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
import io.github.richeyworks.csrbt.strategy.WeightBalancedStrategy;
import io.github.richeyworks.csrbt.util.TreeCloner;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-028 — height is maintained ONCE per write, and is still exact everywhere.
 *
 * <p><b>What changed.</b> The BST-descent links on the five engine strategies moved from the
 * propagating {@code setLeft}/{@code setRight} to {@code linkLeft}/{@code linkRight}, which carry
 * size, augment and black-height to the root but no height at all; {@code RedBlackStrategy} and
 * {@code WeightBalancedStrategy} moved from the height-carrying {@code rotateLeft}/
 * {@code rotateRight} to the {@code *Local} primitives; and each write ends with a single
 * {@link TreeNode1#repairHeightUpward(TreeNode1)} from its anchor. ADR-023's guarantee —
 * {@code getHeight()} exact for every node on every strategy — has to survive that, and the
 * ways it can fail are all "the one climb stopped too early":</p>
 *
 * <ul>
 *   <li>a rotation is a SECOND origin of height change, invisible below itself, so the climb is
 *       unconditional through the adopter of the write's highest rotation;</li>
 *   <li>a delete that splices the in-order successor into the removed node's place is a THIRD
 *       origin, at the successor, which gets its own repair;</li>
 *   <li>arriving at a write with heights already stale would poison everything, which is why the
 *       reconstruction paths keep the fully propagating setters (AUDIT-2026-08-14 F-1).</li>
 * </ul>
 *
 * <p>Each of the three was observed red while this change was being built (weight-balanced
 * ascending went wrong at n = 38 with a pure fixed-point climb; Red-Black mixed add/remove went
 * wrong at op 122 before the successor repair), so every assertion below is a live tripwire and
 * not a formality. {@link RotationHeightPropagationTest} pins ADR-023's own sweep; this one adds
 * the shapes and the reconstruction-then-write interaction that ADR-028 put at risk.</p>
 */
@DisplayName("ADR-028 — one height climb per write, still exact on every node")
class OneClimbPerWriteHeightTest {

    /** The measured truth: real height by full recursion, ignoring every cache. */
    private static int realHeight(TreeNode1<Integer> n) {
        if (n == null || n.isNil()) return 0;
        return 1 + Math.max(realHeight(n.getLeft()), realHeight(n.getRight()));
    }

    /** Deepest cached-vs-real height mismatch in the subtree, or null when all agree. */
    private static String firstStaleHeight(TreeNode1<Integer> n) {
        if (n == null || n.isNil()) return null;
        int real = realHeight(n);
        if (n.getHeight() != real) {
            return "node " + n.getData() + " caches height " + n.getHeight() + " but really is " + real;
        }
        String left = firstStaleHeight(n.getLeft());
        return left != null ? left : firstStaleHeight(n.getRight());
    }

    private static int countNodes(TreeNode1<Integer> n) {
        return (n == null || n.isNil()) ? 0 : 1 + countNodes(n.getLeft()) + countNodes(n.getRight());
    }

    private static List<Supplier<TreeStrategy<Integer>>> strategies() {
        return List.of(RedBlackStrategy::new, AVLStrategy::new, SplayStrategy::new,
                HybridStrategy::new, WeightBalancedStrategy::new);
    }

    private static String name(TreeStrategy<Integer> s) {
        return s.getClass().getSimpleName();
    }

    /**
     * One operation of the named shape. Returns the key stream position's effect so the caller
     * can keep its own bookkeeping of live keys.
     */
    private static void step(OrderedSet<Integer> set, List<Integer> live, Random rng,
                             String shape, int i, int ops) {
        switch (shape) {
            case "ascending" -> set.add(i + 1);
            case "descending" -> set.add(ops - i);
            case "random" -> set.add(1 + rng.nextInt(ops * 4));
            case "sawtooth" -> set.add((i % 32) * 1000 + i / 32);        // many short monotone runs
            case "duplicates" -> set.add(1 + rng.nextInt(Math.max(2, ops / 8)));
            case "zipf" -> set.add(1 + (int) (Math.pow(rng.nextDouble(), 3) * ops));
            case "delete-heavy" -> {
                if (!live.isEmpty() && rng.nextInt(100) < 70) {
                    set.remove(live.remove(rng.nextInt(live.size())));
                } else {
                    int key = 1 + rng.nextInt(ops * 4);
                    if (set.add(key)) live.add(key);
                }
            }
            default -> {
                if (!live.isEmpty() && rng.nextInt(100) < 35) {
                    set.remove(live.remove(rng.nextInt(live.size())));
                } else {
                    int key = 1 + rng.nextInt(ops * 4);
                    if (set.add(key)) live.add(key);
                }
            }
        }
    }

    // ── The sweep: every strategy × every shape × three seeds, checked after every op ────────

    @Test
    @DisplayName("every strategy × shape × seed leaves every node's cached height exact, per op")
    void everyStrategyShapeAndSeedStaysExactAfterEveryOperation() {
        List<String> shapes = List.of("ascending", "descending", "random", "sawtooth",
                "duplicates", "zipf", "mixed", "delete-heavy");
        int checkedCells = 0;
        for (Supplier<TreeStrategy<Integer>> make : strategies()) {
            for (String shape : shapes) {
                for (long seed : new long[] {1L, 7L, 31L}) {
                    TreeStrategy<Integer> strategy = make.get();
                    OrderedSet<Integer> set = OrderedSet.withNaturalOrder(strategy);
                    Random rng = new Random(seed);
                    List<Integer> live = new ArrayList<>();
                    int ops = 220;
                    for (int i = 0; i < ops; i++) {
                        step(set, live, rng, shape, i, ops);
                        String stale = firstStaleHeight(set.getEngine().getRoot());
                        assertNull(stale, name(strategy) + "/" + shape + "/seed " + seed
                                + " after op #" + (i + 1) + ": " + stale);
                    }
                    assertEquals(set.size(), countNodes(set.getEngine().getRoot()),
                            name(strategy) + "/" + shape + ": tree walk disagrees with reported size");
                    checkedCells++;
                }
            }
        }
        assertEquals(5 * 8 * 3, checkedCells, "the sweep must cover every cell");
    }

    // ── Depth: the shapes above are small; this one runs long enough to get deep ─────────────

    @Test
    @DisplayName("a 6000-operation run stays exact on every strategy (checked every 50 ops)")
    void longRunsStayExact() {
        for (Supplier<TreeStrategy<Integer>> make : strategies()) {
            for (String shape : List.of("ascending", "random", "mixed")) {
                TreeStrategy<Integer> strategy = make.get();
                if (shape.equals("ascending") && strategy instanceof SplayStrategy) {
                    continue;   // splay degenerates to an O(n) chain: quadratic, and says nothing
                }
                OrderedSet<Integer> set = OrderedSet.withNaturalOrder(strategy);
                Random rng = new Random(99);
                List<Integer> live = new ArrayList<>();
                int ops = 6000;
                for (int i = 0; i < ops; i++) {
                    step(set, live, rng, shape, i, ops);
                    if (i % 50 == 0 || i == ops - 1) {
                        String stale = firstStaleHeight(set.getEngine().getRoot());
                        assertNull(stale, name(strategy) + "/" + shape + " after op #" + (i + 1)
                                + ": " + stale);
                    }
                }
                assertTrue(set.size() > 100, name(strategy) + "/" + shape + ": tree too small to matter");
            }
        }
    }

    // ── The reconstruction interaction ADR-028 puts at risk ──────────────────────────────────

    /**
     * A write that links with {@code linkLeft}/{@code linkRight} and repairs once assumes the tree
     * it arrived at was already consistent. That is exactly what the arbitrary-order
     * reconstruction paths guarantee by keeping the fully propagating setters (AUDIT-2026-08-14
     * F-1). This checks the seam directly on the two strategies that maintain no height of their
     * own — the ones that would silently accumulate error if reconstruction ever stopped
     * propagating: load a snapshot / take a deep-copy clone, then keep writing.
     */
    @Test
    @DisplayName("snapshot load and clone, then keep writing: heights stay exact on RB and WB")
    void reconstructionThenWritesStayExact() {
        FilePersistenceAdapter io = new FilePersistenceAdapter();
        for (Supplier<TreeStrategy<Integer>> make :
                List.<Supplier<TreeStrategy<Integer>>>of(RedBlackStrategy::new, WeightBalancedStrategy::new)) {
            TreeStrategy<Integer> strategy = make.get();
            String label = name(strategy);
            TreeContext ctx = new TreeContext(castRaw(strategy));
            Random rng = new Random(5);
            while (ctx.getSize() < 200) ctx.add(rng.nextInt(10_000));

            String snapshot = "adr028-" + label;
            try {
                io.saveSnapshot(snapshot, ctx);
                TreeContext loaded = io.loadSnapshot(snapshot);
                assertEquals(ctx.inOrder(), loaded.inOrder(), label + ": snapshot round-trip");
                assertHeightsExact(loaded.getTree(), label + " after load");
                for (int i = 0; i < 400; i++) {
                    loaded.add(rng.nextInt(20_000));
                    assertHeightsExact(loaded.getTree(), label + " after load + insert #" + (i + 1));
                }
            } finally {
                io.deleteSnapshot(snapshot);
            }

            TreeContext clone = new TreeCloner(ctx).deployCloneArmy(1).get(0);
            assertHeightsExact(clone.getTree(), label + " clone");
            for (int i = 0; i < 400; i++) {
                if (i % 3 == 2) clone.remove(rng.nextInt(10_000));
                else clone.add(rng.nextInt(20_000));
                assertHeightsExact(clone.getTree(), label + " clone + op #" + (i + 1));
            }
        }
    }

    /**
     * {@link TreeContext} is the {@code int} facade, so its strategy argument is the raw
     * {@code TreeStrategy<Integer>} the suppliers above already produce.
     */
    private static TreeStrategy<Integer> castRaw(TreeStrategy<Integer> strategy) {
        return strategy;
    }

    private static void assertHeightsExact(MutableTree<Integer> tree, String where) {
        String stale = firstStaleHeight(tree.getRoot());
        assertNull(stale, where + ": " + stale);
    }

    // ── The out-of-band rotation seam has to keep working on its own ─────────────────────────

    /**
     * {@code MutableTree.rotateLeft}/{@code rotateRight} remain the height-CARRYING seam: a
     * rotation fired from outside a write — a third-party strategy, a repair tool — still has to
     * leave every ancestor exact by itself, because there is no per-write repair to catch it.
     * ADR-028 moved the in-repo strategies off that pair; this is what stops the pair rotting.
     */
    @Test
    @DisplayName("an out-of-band rotation through the engine seam still leaves ancestors exact")
    void outOfBandRotationStillCarriesHeight() {
        OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
        for (int i = 1; i <= 400; i++) set.add(i);
        MutableTree<Integer> tree = set.getEngine();

        int rotated = 0;
        TreeNode1<Integer> cur = tree.getRoot();
        while (!cur.isNil()) {
            TreeNode1<Integer> next = cur.getRight();
            if (!cur.getRight().isNil()) {
                tree.rotateLeft(cur);
                rotated++;
                String stale = firstStaleHeight(tree.getRoot());
                assertNull(stale, "after out-of-band rotation #" + rotated + ": " + stale);
            }
            cur = next;
        }
        assertTrue(rotated > 5, "the walk must actually rotate something (rotated " + rotated + ")");
    }
}
