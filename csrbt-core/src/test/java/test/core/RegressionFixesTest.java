package test.core;

import io.github.richeyworks.csrbt.RedBlackTree;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.TreeNode1;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.util.OrderStatisticsOps;
import io.github.richeyworks.csrbt.util.TreeDiagnostics;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Deque;
import java.util.List;
import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Regression tests for the code-review fixes (docs/code-review-2026-05-29.md):
 *
 *   #1  RedBlackStrategy deletion no longer NPEs when the replacement node is
 *       the shared NIL sentinel (black-leaf / one-child black deletions), and
 *       RB invariants are preserved after heavy mixed insert/delete.
 *   #2  AVLStrategy keeps cached heights correct along the rebalance path, so
 *       the tree stays height-balanced after random insert/delete churn.
 *   #5  FilePersistenceAdapter rejects snapshot names that would escape the
 *       snapshots directory (path traversal).
 *
 * These are intentionally independent of the legacy TreeContextTester suite
 * (which targets a different package layout) so they compile and run against
 * the current core packages.
 */
@DisplayName("Code-review fix regressions")
public class RegressionFixesTest {

    // ── Helpers ────────────────────────────────────────────────────────────

    /** Actual height by traversal (does not trust the cached field). */
    private static int height(TreeNode1<Integer> node) {
        if (node == null || node.isNil()) return 0;
        return 1 + Math.max(height(node.getLeft()), height(node.getRight()));
    }

    private static boolean isSorted(List<Integer> xs) {
        for (int i = 1; i < xs.size(); i++) if (xs.get(i - 1) >= xs.get(i)) return false;
        return true;
    }

    // ── #1  RB deletion ──────────────────────────────────────────────────────

    @Nested
    @DisplayName("#1 Red-Black deletion (NIL-parent fix)")
    class RbDeletion {

        @Test
        @DisplayName("Deleting a black leaf does not throw and keeps RB validity")
        void deleteBlackLeafNoThrow() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            // 1..7 builds a tree whose lower level contains black leaves.
            for (int v = 1; v <= 7; v++) ctx.add(v);

            TreeDiagnostics diag = new TreeDiagnostics(ctx);
            assertTrue(diag.isValidRedBlack(), "tree should be a valid RB tree before delete");

            // Remove every element; under the old bug at least one of these
            // (a black node with a NIL replacement) threw NullPointerException.
            assertDoesNotThrow(() -> {
                for (int v = 1; v <= 7; v++) {
                    ctx.remove(v);
                    assertTrue(new TreeDiagnostics(ctx).isValidRedBlack(),
                            "RB invariants must hold after removing " + v);
                }
            });
            assertEquals(0, ctx.size());
        }

        @Test
        @DisplayName("Heavy randomized insert/delete preserves RB invariants, order, size")
        void randomizedChurnStaysValid() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            Random rng = new Random(42);

            List<Integer> values = new ArrayList<>();
            for (int i = 0; i < 600; i++) values.add(i);
            Collections.shuffle(values, rng);

            java.util.Set<Integer> present = new java.util.TreeSet<>();
            for (int v : values) { ctx.add(v); present.add(v); }

            List<Integer> toDelete = new ArrayList<>(values);
            Collections.shuffle(toDelete, rng);
            for (int i = 0; i < 400; i++) {
                int v = toDelete.get(i);
                ctx.remove(v);
                present.remove(v);
            }

            TreeDiagnostics diag = new TreeDiagnostics(ctx);
            assertTrue(diag.isValidRedBlack(), "RB invariants must hold after churn");
            assertEquals(present.size(), ctx.size(), "size must match logical contents");

            List<Integer> inOrder = diag.inOrderTraversal();
            assertTrue(isSorted(inOrder), "in-order traversal must be ascending");
            assertEquals(new ArrayList<>(present), inOrder, "contents must match expected set");
        }
    }

    // ── #2  AVL balance ────────────────────────────────────────────────────────

    @Nested
    @DisplayName("#2 AVL height correctness")
    class AvlBalance {

        @Test
        @DisplayName("Sequential insert stays balanced (height ~ log n, not linear)")
        void sequentialInsertBalanced() {
            TreeContext ctx = new TreeContext(new AVLStrategy<>());
            int n = 500;
            for (int v = 0; v < n; v++) ctx.add(v);   // worst case for a naive BST

            int h = height(ctx.getTree().getRoot());
            // AVL bound is < 1.4404 * log2(n+2) - 0.328; allow generous slack.
            int bound = (int) Math.ceil(2.0 * (Math.log(n) / Math.log(2)) + 2);
            assertTrue(h <= bound,
                    "AVL height " + h + " should be <= " + bound + " for n=" + n);
            assertEquals(n, ctx.size());
            assertTrue(isSorted(new TreeDiagnostics(ctx).inOrderTraversal()));
        }

        @Test
        @DisplayName("Random insert/delete stays balanced and ordered")
        void randomChurnBalanced() {
            TreeContext ctx = new TreeContext(new AVLStrategy<>());
            Random rng = new Random(7);
            java.util.Set<Integer> present = new java.util.TreeSet<>();

            for (int i = 0; i < 400; i++) {
                int v = rng.nextInt(1000);
                ctx.add(v);
                present.add(v);
            }
            List<Integer> snapshot = new ArrayList<>(present);
            Collections.shuffle(snapshot, rng);
            for (int i = 0; i < snapshot.size() / 2; i++) {
                int v = snapshot.get(i);
                ctx.remove(v);
                present.remove(v);
            }

            int h = height(ctx.getTree().getRoot());
            int n = present.size();
            int bound = (int) Math.ceil(2.0 * (Math.log(Math.max(2, n)) / Math.log(2)) + 2);
            assertTrue(h <= bound, "AVL height " + h + " should be <= " + bound + " for n=" + n);
            assertEquals(new ArrayList<>(present),
                    new TreeDiagnostics(ctx).inOrderTraversal());
        }
    }

    // ── #3  Inverse-command undo/redo ───────────────────────────────────────────

    @Nested
    @DisplayName("#3 Inverse-command undo/redo")
    class UndoRedo {

        @Test
        @DisplayName("Undo reverses adds and removes; redo re-applies them")
        void undoRedoRoundTrip() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            ctx.add(10);
            ctx.add(20);
            ctx.add(30);
            assertEquals(List.of(10, 20, 30),
                    new TreeDiagnostics(ctx).inOrderTraversal());

            // Undo last add → {10,20}
            assertTrue(ctx.getHistory().undo());
            assertEquals(List.of(10, 20), new TreeDiagnostics(ctx).inOrderTraversal());
            assertEquals(2, ctx.size());

            // Redo → {10,20,30}
            assertTrue(ctx.getHistory().redo());
            assertEquals(List.of(10, 20, 30), new TreeDiagnostics(ctx).inOrderTraversal());
            assertEquals(3, ctx.size());

            // Undo a remove → value comes back
            ctx.remove(20);
            assertEquals(List.of(10, 30), new TreeDiagnostics(ctx).inOrderTraversal());
            assertTrue(ctx.getHistory().undo());
            assertEquals(List.of(10, 20, 30), new TreeDiagnostics(ctx).inOrderTraversal());
        }

        @Test
        @DisplayName("Rewinding all operations returns to empty")
        void rewindToEmpty() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            for (int v = 1; v <= 50; v++) ctx.add(v);
            assertEquals(50, ctx.size());

            int rewound = ctx.getHistory().rewind(50);
            assertEquals(50, rewound);
            assertEquals(0, ctx.size());
            assertTrue(new TreeDiagnostics(ctx).inOrderTraversal().isEmpty());
        }

        @Test
        @DisplayName("Replayed undo/redo does not itself create new history entries")
        void replayDoesNotRecord() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            ctx.add(1);
            ctx.add(2);
            int depthBefore = ctx.getHistory().undoDepth();   // 2

            ctx.getHistory().undo();                           // undo add(2)
            assertEquals(depthBefore - 1, ctx.getHistory().undoDepth());
            ctx.getHistory().redo();                           // redo add(2)
            assertEquals(depthBefore, ctx.getHistory().undoDepth(),
                    "redo must not push an extra command onto the undo stack");
            assertEquals(List.of(1, 2), new TreeDiagnostics(ctx).inOrderTraversal());
        }

        @Test
        @DisplayName("Checkpoint restore is undoable")
        void checkpointRestoreUndoable() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            ctx.add(1); ctx.add(2); ctx.add(3);
            ctx.getHistory().saveCheckpoint("cp");

            ctx.add(4); ctx.add(5);
            assertEquals(List.of(1, 2, 3, 4, 5), new TreeDiagnostics(ctx).inOrderTraversal());

            assertTrue(ctx.getHistory().restoreCheckpoint("cp"));
            assertEquals(List.of(1, 2, 3), new TreeDiagnostics(ctx).inOrderTraversal());

            // Undo the restore → back to {1..5}
            assertTrue(ctx.getHistory().undo());
            assertEquals(List.of(1, 2, 3, 4, 5), new TreeDiagnostics(ctx).inOrderTraversal());
        }
    }

    // ── #9  Localized per-insert diagnostic ─────────────────────────────────────

    @Nested
    @DisplayName("#9 Localized red-red check preserves behavior")
    class LocalDiagnostic {

        @Test
        @DisplayName("Clean RB inserts never raise stress → no auto-morph, tree stays valid RB")
        void noSpuriousMorph() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            Random rng = new Random(99);
            for (int i = 0; i < 300; i++) ctx.add(rng.nextInt(5000));

            // A correct RB strategy never leaves a red-red violation, so the
            // stress signal must stay at zero and no morph to AVL should occur.
            assertEquals("RedBlackStrategy",
                    ctx.getTree().getStrategy().getClass().getSimpleName(),
                    "no spurious stress-morph should have fired");
            assertTrue(new TreeDiagnostics(ctx).isValidRedBlack());
        }
    }

    // ── #1  Augment correctness after local-only rotation recompute ─────────────

    @Nested
    @DisplayName("#1 Order statistics stay correct (augment maintained through rotations)")
    class AugmentIntegrity {

        @Test
        @DisplayName("select/rank are exact after rotation-heavy insert and delete")
        void orderStatisticsExact() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            int n = 400;
            List<Integer> vals = new ArrayList<>();
            for (int i = 1; i <= n; i++) vals.add(i);
            Collections.shuffle(vals, new Random(2024));
            for (int v : vals) ctx.add(v);   // many rotations → exercises augment upkeep

            OrderStatisticsOps<Integer> os = new OrderStatisticsOps<>(ctx.getTree());

            // Subtree size at root must equal element count (the augment invariant).
            assertEquals(n, ctx.getTree().getRoot().getAugmentedValue(),
                    "root augment must equal n after inserts");

            for (int r = 1; r <= n; r++) {
                assertEquals(r, os.select(r).getData(), "select(" + r + ")");
                assertEquals(r, os.rank(r),             "rank(" + r + ")");
            }
            assertEquals((n + 1) / 2, os.median().getData());

            // Delete a chunk, then re-verify against a reference sorted list.
            List<Integer> deleted = new ArrayList<>(vals.subList(0, 150));
            for (int v : deleted) ctx.remove(v);

            List<Integer> remaining = new ArrayList<>();
            for (int i = 1; i <= n; i++) if (!deleted.contains(i)) remaining.add(i);
            Collections.sort(remaining);

            assertEquals(remaining.size(), ctx.getTree().getRoot().getAugmentedValue(),
                    "root augment must equal remaining count after deletes");

            for (int r = 1; r <= remaining.size(); r++) {
                assertEquals(remaining.get(r - 1), os.select(r).getData(),
                        "post-delete select(" + r + ")");
            }
            assertEquals(remaining.size(), os.countInRange(1, n));
        }
    }

    // ── #4 + #7  Per-tree sentinel & parent convention ──────────────────────────

    @Nested
    @DisplayName("#4/#7 Per-tree NIL sentinel + uniform parent convention")
    class SentinelModel {

        @Test
        @DisplayName("Distinct trees own distinct sentinels and do not contaminate each other")
        void perTreeIsolation() {
            TreeContext a = new TreeContext(new RedBlackStrategy<>());
            TreeContext b = new TreeContext(new RedBlackStrategy<>());

            assertNotSame(a.getTree().getNIL(), b.getTree().getNIL(),
                    "each engine must own its own NIL sentinel");

            for (int i = 0; i < 100; i++) a.add(i);

            assertEquals(0, b.size(), "mutating tree A must not affect tree B");
            assertTrue(new TreeDiagnostics(b).inOrderTraversal().isEmpty());
            assertTrue(new TreeDiagnostics(a).isValidRedBlack());
            assertEquals(100, a.size());
        }

        @Test
        @DisplayName("Splay tree never leaves a null parent (root's parent is the sentinel)")
        void splayParentConvention() {
            TreeContext s = new TreeContext(new SplayStrategy<>());
            int[] vals = {5, 3, 8, 1, 4, 7, 9, 2, 6};
            for (int v : vals) s.add(v);
            s.remove(4);
            s.remove(8);

            // Walk the whole tree: no live node should have a null parent.
            TreeNode1<Integer> root = s.getTree().getRoot();
            Deque<TreeNode1<Integer>> stack = new ArrayDeque<>();
            if (!root.isNil()) stack.push(root);
            while (!stack.isEmpty()) {
                TreeNode1<Integer> n = stack.pop();
                assertNotNull(n.getParent(), "node " + n.getData() + " has a null parent");
                if (!n.getLeft().isNil())  stack.push(n.getLeft());
                if (!n.getRight().isNil()) stack.push(n.getRight());
            }
            assertEquals(List.of(1, 2, 3, 5, 6, 7, 9),
                    new TreeDiagnostics(s).inOrderTraversal());
        }
    }

    // ── #2  Node identity equality ──────────────────────────────────────────────

    @Nested
    @DisplayName("#2 TreeNode1 uses identity equality")
    class NodeIdentity {

        @Test
        @DisplayName("hashCode is stable across mutation and equals is identity-based")
        void identitySemantics() {
            java.util.Comparator<Integer> ord = java.util.Comparator.naturalOrder();
            TreeNode1<Integer> nil = TreeNode1.createNil(ord);   // per-tree sentinel (ADR-002 step 2: shared static NIL removed)
            TreeNode1<Integer> a = TreeNode1.createNode(5, nil);
            TreeNode1<Integer> b = TreeNode1.createNode(5, nil);

            // Distinct instances with identical data must NOT be equal.
            org.junit.jupiter.api.Assertions.assertNotEquals(a, b);
            assertTrue(a.equals(a));

            // hashCode must not change when the node's structure/color mutates
            // (the old recursive hashCode violated this).
            int h = a.hashCode();
            a.setColor(TreeNode1.Color.BLACK);
            a.setLeft(TreeNode1.createNode(3, nil));
            assertEquals(h, a.hashCode(), "hashCode must be stable across mutation");
        }
    }

    // ── #5  Path traversal ──────────────────────────────────────────────────────

    @Nested
    @DisplayName("#5 Snapshot path traversal rejected")
    class PathTraversal {

        @Test
        @DisplayName("Malicious names are rejected on save and delete")
        void rejectsTraversalNames() {
            FilePersistenceAdapter fpa = new FilePersistenceAdapter();
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            ctx.add(1);

            for (String bad : new String[]{"../escape", "..\\escape", "a/b", "a\\b", "", null}) {
                assertThrows(IllegalArgumentException.class,
                        () -> fpa.saveSnapshot(bad, ctx),
                        "saveSnapshot must reject name: " + bad);
                assertThrows(IllegalArgumentException.class,
                        () -> fpa.deleteSnapshot(bad),
                        "deleteSnapshot must reject name: " + bad);
            }
        }

        @Test
        @DisplayName("A normal name round-trips with contents AND size restored (#8)")
        void normalNameWorks() {
            FilePersistenceAdapter fpa = new FilePersistenceAdapter();
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            for (int v = 1; v <= 5; v++) ctx.add(v);

            assertDoesNotThrow(() -> fpa.saveSnapshot("regression_ok", ctx));
            TreeContext loaded = fpa.loadSnapshot("regression_ok");
            assertTrue(loaded != null, "snapshot should load back");
            assertEquals(5, loaded.getSize(), "loaded size must be restored (was a latent bug)");
            assertEquals(List.of(1, 2, 3, 4, 5),
                    new TreeDiagnostics(loaded).inOrderTraversal());
            fpa.deleteSnapshot("regression_ok");
        }

        @Test
        @DisplayName("Missing snapshot loads as null, not a crash")
        void missingLoadsNull() {
            FilePersistenceAdapter fpa = new FilePersistenceAdapter();
            assertEquals(null, fpa.loadSnapshot("definitely_does_not_exist_12345"));
        }
    }
}
