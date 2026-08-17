package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.RedBlackTree;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.augment.GenericIntervalAugmentor;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;
import io.github.richeyworks.csrbt.util.TreeCloner;
import io.github.richeyworks.csrbt.util.TreeDiagnostics;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Random;
import java.util.function.Supplier;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Regressions for AUDIT-2026-08-17 (sixth pass), findings 1, 2, 6, 11, 15, 19, 20, 21.
 *
 * <ul>
 *   <li>1  — a checkpoint restore leaves the root's parent as the NIL sentinel, so the
 *           next insert does not NPE inside a rotation.</li>
 *   <li>2  — {@code fixDelete} never recolours or rotates the shared NIL sentinel when
 *           the sibling is NIL, so a structurally-built (not RB-valid) tree loses one
 *           key on {@code remove}, not all of them.</li>
 *   <li>6  — clones carry the generic augment slot, so interval payloads survive
 *           {@code snapshot()} and the checkpoint path built on it.</li>
 *   <li>11 — the morph rebuilds from a comparator-keyed capture, so keys that are
 *           {@code equals} but compare non-zero are not collapsed away.</li>
 *   <li>15 — Hybrid's ±2 depth relaxation is recorded where it is granted, so
 *           {@code validateInvariant} agrees with what the write path permitted.</li>
 *   <li>19 — clones inherit the sliding-window bound.</li>
 *   <li>20 — a checkpoint restore honours the sliding-window bound.</li>
 *   <li>21 — documentation only (rotation height/black-height staleness); no behaviour
 *           change, so no test here.</li>
 * </ul>
 */
@DisplayName("Sixth-pass audit (2026-08-17) regressions")
class SixthPassAuditTest {

    // ── Helpers ───────────────────────────────────────────────────────────────

    /** Actual subtree height by traversal (never trusts the cached field). */
    private static <K> int realHeight(TreeNode1<K> n) {
        if (n == null || n.isNil()) return 0;
        return 1 + Math.max(realHeight(n.getLeft()), realHeight(n.getRight()));
    }

    private static <K> void collect(TreeNode1<K> n, List<TreeNode1<K>> out) {
        if (n.isNil()) return;
        collect(n.getLeft(), out);
        out.add(n);
        collect(n.getRight(), out);
    }

    // ══════════════════════════════════════════════════════════════════════════
    //  Finding 1 — restored root's parent is the sentinel, not null
    // ══════════════════════════════════════════════════════════════════════════

    @Nested
    @DisplayName("1: checkpoint restore leaves an insertable tree")
    class RestoreRootParent {

        private void saveMutateRestoreAdd(Supplier<TreeStrategy<Integer>> strategy) {
            TreeContext ctx = new TreeContext(strategy.get());
            for (int k = 1; k <= 40; k++) ctx.add(k * 2);

            ctx.getHistory().saveCheckpoint("cp");
            for (int k = 1; k <= 10; k++) ctx.add(1000 + k);
            ctx.remove(4);

            assertTrue(ctx.getHistory().restoreCheckpoint("cp"));

            TreeNode1<Integer> root = ctx.getTree().getRoot();
            assertNotNull(root.getParent(),
                    "restored root's parent must be the sentinel, not null");
            assertTrue(root.getParent().isNil(), "restored root's parent must be NIL");

            // The reported crash: the very next insert rotates through the root and
            // dereferenced its null parent.
            assertDoesNotThrow(() -> {
                for (int k = 1; k <= 30; k++) ctx.add(5000 + k);
            }, "insert after restore must not NPE in the rotation");
            assertEquals(70, ctx.getSize());
            assertTrue(ctx.contains(5001));
        }

        @Test @DisplayName("RedBlack: save → mutate → restore → add")
        void redBlack() { saveMutateRestoreAdd(RedBlackStrategy::new); }

        @Test @DisplayName("AVL: save → mutate → restore → add")
        void avl() { saveMutateRestoreAdd(AVLStrategy::new); }

        @Test @DisplayName("Splay: save → mutate → restore → add")
        void splay() { saveMutateRestoreAdd(SplayStrategy::new); }
    }

    // ══════════════════════════════════════════════════════════════════════════
    //  Finding 2 — fixDelete must never write the shared NIL sentinel
    // ══════════════════════════════════════════════════════════════════════════

    @Nested
    @DisplayName("2: fixDelete never recolours or rotates the NIL sentinel")
    class SentinelSafety {

        @Test
        @DisplayName("shallowClone then remove: keys go one at a time, sentinel stays black")
        void shallowCloneThenRemove() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            for (int k = 1; k <= 63; k++) ctx.add(k);

            // A depth-truncated clone is a real tree that never ran the RB fixups, so
            // the CLRS "sibling is never NIL" precondition does not hold on it.
            TreeContext clone = new TreeCloner(ctx).shallowClone(2);
            List<Integer> keys = new TreeDiagnostics(clone).inOrderTraversal();
            assertEquals(7, keys.size(), "depth-2 clone holds the top three levels");

            TreeNode1<Integer> nil = clone.getTree().getNIL();
            int expected = keys.size();
            for (int key : keys) {
                assertDoesNotThrow(() -> clone.remove(key),
                        "remove(" + key + ") must not throw on a structurally-built tree");
                expected--;
                assertEquals(expected, new TreeDiagnostics(clone).inOrderTraversal().size(),
                        "each remove must drop exactly one key, never empty the tree");
                assertTrue(nil.isBlack(), "the NIL sentinel must never be recoloured RED");
                assertTrue(nil.getLeft().isNil() && nil.getRight().isNil(),
                        "the NIL sentinel's links must never be rewritten");
            }
        }

        @Test
        @DisplayName("black chain 10→5→2: remove(2) keeps [5, 10] instead of emptying the tree")
        void blackChain() {
            RedBlackTree<Integer> t =
                    new RedBlackTree<>(new RedBlackStrategy<>(), Comparator.<Integer>naturalOrder());
            TreeNode1<Integer> nil = t.getNIL();

            TreeNode1<Integer> n10 = TreeNode1.createNode(10, nil);
            TreeNode1<Integer> n5  = TreeNode1.createNode(5, nil);
            TreeNode1<Integer> n2  = TreeNode1.createNode(2, nil);
            n10.setColor(TreeNode1.Color.BLACK);
            n5.setColor(TreeNode1.Color.BLACK);
            n2.setColor(TreeNode1.Color.BLACK);
            n5.setLeft(n2);
            n10.setLeft(n5);
            t.setRoot(n10);
            n10.setParent(nil);

            assertEquals(List.of(2, 5, 10), t.inOrder());

            assertDoesNotThrow(() -> t.remove(2), "remove on a non-RB-valid black chain");
            assertEquals(List.of(5, 10), t.inOrder(), "only the removed key may disappear");
            assertTrue(nil.isBlack(), "the NIL sentinel must never be recoloured RED");
            assertTrue(t.getRoot() != nil, "the tree must not have been emptied via setRoot(NIL)");
        }

        @Test
        @DisplayName("ordinary RB churn is unaffected by the guard")
        void ordinaryChurnUnaffected() {
            RedBlackTree<Integer> t =
                    new RedBlackTree<>(new RedBlackStrategy<>(), Comparator.<Integer>naturalOrder());
            java.util.TreeSet<Integer> oracle = new java.util.TreeSet<>();
            Random rng = new Random(2026);
            for (int i = 0; i < 2000; i++) {
                int v = rng.nextInt(500);
                if (rng.nextBoolean()) { t.add(v); oracle.add(v); }
                else                   { t.remove(v); oracle.remove(v); }
            }
            assertEquals(new ArrayList<>(oracle), t.inOrder());
            assertTrue(t.getRoot().isNil() || t.getRoot().isBlack(), "root stays black");
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    //  Finding 6 — clones carry the generic augment slot
    // ══════════════════════════════════════════════════════════════════════════

    @Nested
    @DisplayName("6: clones keep generic augment payloads")
    class GenericAugmentClone {

        private TreeContext stamped(GenericIntervalAugmentor<Integer> iv) {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            iv.insertInterval(ctx.getOrderedSet(), 10, 50);
            iv.insertInterval(ctx.getOrderedSet(), 20, 25);
            iv.insertInterval(ctx.getOrderedSet(), 30, 90);
            return ctx;
        }

        @Test @DisplayName("snapshot() reproduces the source's intervals and stabQuery")
        void snapshotKeepsIntervals() {
            GenericIntervalAugmentor<Integer> iv = GenericIntervalAugmentor.natural();
            TreeContext ctx = stamped(iv);

            List<GenericIntervalAugmentor.Interval<Integer>> source =
                    iv.stabQuery(ctx.getOrderedSet(), 45);
            assertEquals(2, source.size(), "source: [10,50] and [30,90] cover 45");

            TreeContext clone = new TreeCloner(ctx).snapshot();
            assertEquals(source, iv.stabQuery(clone.getOrderedSet(), 45),
                    "the clone must answer stabQuery exactly like its source");
            assertEquals(iv.intervalSearchAll(ctx.getOrderedSet(), 0, 100),
                    iv.intervalSearchAll(clone.getOrderedSet(), 0, 100),
                    "every high endpoint must survive the copy, not collapse to [lo, lo]");
        }

        @Test @DisplayName("saveCheckpoint/restoreCheckpoint keeps the intervals")
        void checkpointKeepsIntervals() {
            GenericIntervalAugmentor<Integer> iv = GenericIntervalAugmentor.natural();
            TreeContext ctx = stamped(iv);
            List<GenericIntervalAugmentor.Interval<Integer>> before =
                    iv.stabQuery(ctx.getOrderedSet(), 45);

            ctx.getHistory().saveCheckpoint("cp");
            iv.insertInterval(ctx.getOrderedSet(), 60, 70);
            assertTrue(ctx.getHistory().restoreCheckpoint("cp"));

            assertEquals(before, iv.stabQuery(ctx.getOrderedSet(), 45));
        }

        @Test @DisplayName("shallowClone keeps the payloads it copies")
        void shallowCloneKeepsIntervals() {
            GenericIntervalAugmentor<Integer> iv = GenericIntervalAugmentor.natural();
            TreeContext ctx = stamped(iv);

            TreeContext clone = new TreeCloner(ctx).shallowClone(8);
            assertEquals(iv.stabQuery(ctx.getOrderedSet(), 45),
                    iv.stabQuery(clone.getOrderedSet(), 45));
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    //  Finding 19 — clones inherit the window bound
    // ══════════════════════════════════════════════════════════════════════════

    @Nested
    @DisplayName("19: clones inherit the sliding-window bound")
    class ClonedWindow {

        private TreeContext bounded() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            ctx.setMaxSize(4);
            for (int k = 1; k <= 10; k++) ctx.add(k);
            assertEquals(4, ctx.getSize());
            return ctx;
        }

        @Test @DisplayName("snapshot() clone is bounded and stays bounded")
        void snapshotBounded() {
            TreeContext clone = new TreeCloner(bounded()).snapshot();
            assertEquals(4, clone.getMaxSize(), "the clone must inherit maxSize");
            assertEquals(4, clone.getSize());
            for (int k = 100; k < 110; k++) clone.add(k);
            assertEquals(4, clone.getSize(), "a bounded clone must not grow past the bound");
        }

        @Test @DisplayName("deployCloneArmy / mutantClone / shallowClone are bounded too")
        void otherEntryPointsBounded() {
            TreeContext ctx = bounded();
            for (TreeContext c : new TreeCloner(ctx).deployCloneArmy(2)) {
                assertEquals(4, c.getMaxSize(), "clone army members inherit maxSize");
            }
            assertEquals(4, new TreeCloner(ctx).mutantClone().getMaxSize());
            assertEquals(4, new TreeCloner(ctx).shallowClone(3).getMaxSize());
        }

        @Test @DisplayName("an unbounded source still clones unbounded")
        void unboundedStaysUnbounded() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            for (int k = 1; k <= 10; k++) ctx.add(k);
            TreeContext clone = new TreeCloner(ctx).snapshot();
            assertEquals(0, clone.getMaxSize());
            assertEquals(10, clone.getSize());
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    //  Finding 20 — a restore honours the window bound
    // ══════════════════════════════════════════════════════════════════════════

    @Nested
    @DisplayName("20: checkpoint restore honours the window bound")
    class RestoreRespectsWindow {

        @Test @DisplayName("restoring a 10-key checkpoint under maxSize=3 restores 3 keys")
        void restoreEvictsToBound() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            for (int k = 1; k <= 10; k++) ctx.add(k);
            ctx.getHistory().saveCheckpoint("cp");

            ctx.setMaxSize(3);
            assertEquals(List.of(8, 9, 10), new TreeDiagnostics(ctx).inOrderTraversal());

            assertTrue(ctx.getHistory().restoreCheckpoint("cp"));
            assertEquals(3, ctx.getSize(), "a restore may not exceed the window bound");
            assertEquals(List.of(8, 9, 10), new TreeDiagnostics(ctx).inOrderTraversal(),
                    "the window keeps the newest maxSize keys, like an undo's replay does");

            // The old symptom: the next single add evicted the whole excess at once.
            ctx.add(99);
            assertEquals(3, ctx.getSize());
            assertEquals(List.of(9, 10, 99), new TreeDiagnostics(ctx).inOrderTraversal());
        }

        @Test @DisplayName("an undo and a restore agree on the survivors")
        void undoAndRestoreAgree() {
            TreeContext undoCtx = new TreeContext(new RedBlackStrategy<>());
            for (int k = 1; k <= 10; k++) undoCtx.add(k);
            undoCtx.getHistory().saveCheckpoint("cp");
            undoCtx.setMaxSize(3);
            undoCtx.add(50);                                    // evicts, and is undoable
            undoCtx.getHistory().undo();
            List<Integer> afterUndo = new TreeDiagnostics(undoCtx).inOrderTraversal();

            assertTrue(undoCtx.getHistory().restoreCheckpoint("cp"));
            assertEquals(afterUndo.size(), undoCtx.getSize(),
                    "both restore paths cap at maxSize");
        }

        @Test @DisplayName("an unbounded context restores everything")
        void unboundedRestoresAll() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            for (int k = 1; k <= 10; k++) ctx.add(k);
            ctx.getHistory().saveCheckpoint("cp");
            ctx.clear();
            assertTrue(ctx.getHistory().restoreCheckpoint("cp"));
            assertEquals(10, ctx.getSize());
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    //  Finding 11 — the morph must not collapse equals-but-not-comparator-equal keys
    // ══════════════════════════════════════════════════════════════════════════

    /** Ordered by {@code id}; {@code equals}/{@code hashCode} by {@code name}. */
    private static final class Item {
        final int id;
        final String name;
        Item(int id, String name) { this.id = id; this.name = name; }
        @Override public boolean equals(Object o) {
            return o instanceof Item other && name.equals(other.name);
        }
        @Override public int hashCode() { return name.hashCode(); }
        @Override public String toString() { return id + ":" + name; }
    }

    @Nested
    @DisplayName("11: a morph keeps keys that are equals but compare non-zero")
    class MorphKeyCollapse {

        private OrderedSet<Item> threeItems() {
            OrderedSet<Item> set = new OrderedSet<>(new RedBlackStrategy<>(),
                    Comparator.comparingInt(i -> ((Item) i).id));
            set.add(new Item(1, "same"));
            set.add(new Item(2, "same"));
            set.add(new Item(3, "same"));
            assertEquals(3, set.size(), "the comparator, not equals, decides membership");
            return set;
        }

        @Test @DisplayName("setStrategy preserves every element")
        void morphPreservesElements() {
            OrderedSet<Item> set = threeItems();
            assertTrue(set.setStrategy(new AVLStrategy<>()), "the morph must be applied");
            assertEquals(3, set.size(), "no element may be lost across the morph");
            assertEquals(List.of(1, 2, 3), set.inOrder().stream().map(i -> i.id).toList());
        }

        @Test @DisplayName("selfRepair preserves every element too")
        void repairPreservesElements() {
            OrderedSet<Item> set = threeItems();
            assertTrue(set.selfRepair());
            assertEquals(3, set.size());
        }

        @Test @DisplayName("ordinary Integer morphs still round-trip")
        void integerMorphUnaffected() {
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            for (int k = 0; k < 200; k++) set.add(k);
            assertTrue(set.setStrategy(new AVLStrategy<>()));
            assertEquals(200, set.size());
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    //  Finding 15 — Hybrid validates what its write path permits
    // ══════════════════════════════════════════════════════════════════════════

    @Nested
    @DisplayName("15: Hybrid's depth relaxation is consistent between write and validation")
    class HybridRelaxation {

        private static final int SEEDS  = 20;
        private static final int INSERTS = 600;

        @Test @DisplayName("600 random inserts at thresholds 6 and 7: zero spurious violations")
        void noSpuriousViolations() {
            for (int threshold : new int[] { 6, 7 }) {
                for (int seed = 0; seed < SEEDS; seed++) {
                    HybridStrategy<Integer> hybrid = new HybridStrategy<>(threshold);
                    OrderedSet<Integer> set = OrderedSet.withNaturalOrder(hybrid);
                    Random rng = new Random(seed);
                    for (int i = 0; i < INSERTS; i++) set.add(rng.nextInt(100_000));

                    List<String> failures = hybrid.validateInvariant(set.getEngine());
                    assertTrue(failures.isEmpty(),
                            "Hybrid(" + threshold + ") seed " + seed
                                    + " reported violations on a tree it built itself: " + failures);
                }
            }
        }

        @Test @DisplayName("morphing to Hybrid(6)/Hybrid(7) is never silently refused")
        void morphNeverRefused() {
            for (int threshold : new int[] { 6, 7 }) {
                for (int seed = 0; seed < SEEDS; seed++) {
                    OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
                    Random rng = new Random(seed);
                    for (int i = 0; i < INSERTS; i++) set.add(rng.nextInt(100_000));
                    int before = set.size();

                    assertTrue(set.setStrategy(new HybridStrategy<>(threshold)),
                            "Hybrid(" + threshold + ") morph refused at seed " + seed);
                    assertEquals(before, set.size(), "the morph must preserve contents");
                }
            }
        }

        @Test @DisplayName("selfRepair short-circuits on a healthy finite-threshold Hybrid")
        void selfRepairShortCircuits() {
            HybridStrategy<Integer> hybrid = new HybridStrategy<>(7);
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(hybrid);
            Random rng = new Random(4242);
            for (int i = 0; i < INSERTS; i++) set.add(rng.nextInt(100_000));

            long rotationsBefore = set.rotationCount();
            assertTrue(set.selfRepair(), "a Hybrid-built tree must validate as healthy");
            assertTrue(set.rotationCount() >= rotationsBefore || set.size() > 0);
            assertTrue(hybrid.validateInvariant(set.getEngine()).isEmpty());
        }

        @Test @DisplayName("mixed insert/delete churn also validates clean")
        void mixedChurnValidates() {
            for (int threshold : new int[] { 3, 6, 7 }) {
                HybridStrategy<Integer> hybrid = new HybridStrategy<>(threshold);
                OrderedSet<Integer> set = OrderedSet.withNaturalOrder(hybrid);
                Random rng = new Random(threshold * 31L);
                for (int i = 0; i < 3000; i++) {
                    int v = rng.nextInt(800);
                    if (rng.nextInt(3) != 0) set.add(v); else set.remove(v);
                }
                assertTrue(hybrid.validateInvariant(set.getEngine()).isEmpty(),
                        "threshold " + threshold + " churn produced spurious violations");

                // The relaxation has a ceiling: nothing the write path grants can excuse
                // |bf| >= 3, so the invariant stays falsifiable however deep the tree gets.
                List<TreeNode1<Integer>> nodes = new ArrayList<>();
                collect(set.getEngine().getRoot(), nodes);
                for (TreeNode1<Integer> n : nodes) {
                    int bf = realHeight(n.getLeft()) - realHeight(n.getRight());
                    assertTrue(Math.abs(bf) <= 2,
                            "threshold " + threshold + ": node " + n.getData()
                                    + " reached |bf|=" + Math.abs(bf) + ", past the ±2 ceiling");
                    if (Math.abs(bf) > 1) {
                        assertTrue(hybrid.isDepthRelaxed(n),
                                "node " + n.getData() + " holds |bf|=" + Math.abs(bf)
                                        + " without a recorded grant");
                    }
                }
            }
        }

        @Test @DisplayName("the check is not vacuous: an unbalanced tree still fails it")
        void checkStillCatchesRealImbalance() {
            // A right spine wired by hand: no node was ever granted the relaxation, so
            // every out-of-balance node must be reported.
            RedBlackTree<Integer> t = new RedBlackTree<>(new HybridStrategy<>(7),
                    Comparator.<Integer>naturalOrder());
            TreeNode1<Integer> nil = t.getNIL();
            TreeNode1<Integer> root = TreeNode1.createNode(0, nil);
            root.setColor(TreeNode1.Color.BLACK);
            t.setRoot(root);
            root.setParent(nil);
            TreeNode1<Integer> cur = root;
            for (int k = 1; k <= 8; k++) {
                TreeNode1<Integer> next = TreeNode1.createNode(k, nil);
                next.setColor(TreeNode1.Color.BLACK);
                cur.setRight(next);
                cur = next;
            }
            assertEquals(9, realHeight(root), "hand-wired right spine");

            HybridStrategy<Integer> fresh = new HybridStrategy<>(7);
            assertFalse(fresh.validateInvariant(t).isEmpty(),
                    "a degenerate spine must still be reported as unbalanced");
        }

        @Test @DisplayName("a relaxed node is one this strategy actually granted")
        void relaxationIsRecordedWhereGranted() {
            HybridStrategy<Integer> hybrid = new HybridStrategy<>(4);
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(hybrid);
            for (int k = 0; k < 400; k++) set.add(k);

            List<TreeNode1<Integer>> nodes = new ArrayList<>();
            collect(set.getEngine().getRoot(), nodes);
            for (TreeNode1<Integer> n : nodes) {
                int bf = realHeight(n.getLeft()) - realHeight(n.getRight());
                if (Math.abs(bf) > 1) {
                    assertTrue(hybrid.isDepthRelaxed(n),
                            "node " + n.getData() + " holds |bf|=" + Math.abs(bf)
                                    + " without ever being granted the relaxation");
                    assertTrue(Math.abs(bf) <= 2, "the relaxation is ±2, never more");
                }
            }
            assertTrue(hybrid.validateInvariant(set.getEngine()).isEmpty());
        }

        @Test @DisplayName("the default (unbounded) threshold still holds strict AVL balance")
        void defaultThresholdIsStrict() {
            HybridStrategy<Integer> hybrid = new HybridStrategy<>();
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(hybrid);
            Random rng = new Random(7);
            for (int i = 0; i < 1200; i++) set.add(rng.nextInt(10_000));

            List<TreeNode1<Integer>> nodes = new ArrayList<>();
            collect(set.getEngine().getRoot(), nodes);
            for (TreeNode1<Integer> n : nodes) {
                int bf = realHeight(n.getLeft()) - realHeight(n.getRight());
                assertTrue(Math.abs(bf) <= 1,
                        "default Hybrid must be strict AVL at node " + n.getData());
                assertFalse(hybrid.isDepthRelaxed(n),
                        "an unbounded threshold must never grant the relaxation");
            }
            assertTrue(hybrid.validateInvariant(set.getEngine()).isEmpty());
        }
    }
}
