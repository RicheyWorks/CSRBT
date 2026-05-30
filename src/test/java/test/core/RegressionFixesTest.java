package test.core;

import core.RedBlackTree;
import core.TreeContext;
import core.TreeNode1;
import core.persistence.FilePersistenceAdapter;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.util.TreeDiagnostics;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
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
    private static int height(TreeNode1 node) {
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
            TreeContext ctx = new TreeContext(new RedBlackStrategy());
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
            TreeContext ctx = new TreeContext(new RedBlackStrategy());
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
            TreeContext ctx = new TreeContext(new AVLStrategy());
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
            TreeContext ctx = new TreeContext(new AVLStrategy());
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

    // ── #5  Path traversal ──────────────────────────────────────────────────────

    @Nested
    @DisplayName("#5 Snapshot path traversal rejected")
    class PathTraversal {

        @Test
        @DisplayName("Malicious names are rejected on save and delete")
        void rejectsTraversalNames() {
            FilePersistenceAdapter fpa = new FilePersistenceAdapter();
            TreeContext ctx = new TreeContext(new RedBlackStrategy());
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
        @DisplayName("A normal name still round-trips")
        void normalNameWorks() {
            FilePersistenceAdapter fpa = new FilePersistenceAdapter();
            TreeContext ctx = new TreeContext(new RedBlackStrategy());
            for (int v = 1; v <= 5; v++) ctx.add(v);

            assertDoesNotThrow(() -> fpa.saveSnapshot("regression_ok", ctx));
            TreeContext loaded = fpa.loadSnapshot("regression_ok");
            assertTrue(loaded != null, "snapshot should load back");
            fpa.deleteSnapshot("regression_ok");
        }
    }
}
