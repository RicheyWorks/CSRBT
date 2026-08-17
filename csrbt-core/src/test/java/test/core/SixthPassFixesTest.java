package test.core;

import io.github.richeyworks.csrbt.BPlusTreeEngine;
import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.PersistentRankedSet;
import io.github.richeyworks.csrbt.PersistentTreeEngine;
import io.github.richeyworks.csrbt.adapter.NavigableOrderedSet;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.interfaces.RankedSet;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.persistence.KeySerializer;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.NavigableSet;
import java.util.Random;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Consumer;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Regression tests for the 2026-08-17 sixth-pass audit fixes
 * (docs/AUDIT-2026-08-17-sixth-pass.md), findings 3, 4, 5, 7, 13 and 14:
 *
 *   3   the flat persistent loader honours the header SIZE field (P-2's tripwire, third path).
 *   4   {@code loadEnsemble} validates before it mutates — a malformed file no longer wipes
 *       the destination ensemble and refills it with a partial key list.
 *   5   concurrent saves of one snapshot name no longer share a staging file, so a commit can
 *       never publish a half-written snapshot over a good one.
 *   13  {@code PersistentRankedSet.add/remove} report change exactly (the value VERIFIED votes
 *       on) and their meters are concurrency-safe.
 *   14  the B+tree engine's null-argument semantics match the other engines: NPE everywhere —
 *       and, per the follow-up item 1, at EVERY size: {@code OrderedSet}'s guards no longer
 *       depend on the descend reaching a comparison, so an empty set can no more answer
 *       {@code contains(null)} or store a null than a populated one can.
 *   7   the descending view is read-only along every path, including the iterators
 *       {@code retainAll}/{@code removeAll} reach through.
 */
@DisplayName("Sixth-pass audit fix regressions (2026-08-17)")
public class SixthPassFixesTest {

    // ── 3 + 4 + 5: persistence ────────────────────────────────────────────────

    @Nested
    @DisplayName("findings 3/4/5 — flat-format truncation, ensemble replay, concurrent saves")
    class Persistence {

        private final FilePersistenceAdapter adapter = new FilePersistenceAdapter();
        private final List<String> created = new ArrayList<>();

        private String snap(String base) {
            String name = "test-sixth-" + base + "-" + System.nanoTime();
            created.add(name);
            return name;
        }

        private Path fileOf(String name) { return Path.of("snapshots", name + ".rbt"); }

        @AfterEach
        void cleanup() {
            for (String name : created) adapter.deleteSnapshot(name);
        }

        /** Save a flat persistent snapshot of {@code 1..n} and return its name. */
        private String savePersistent(String base, int n) {
            PersistentRankedSet<Integer> set = PersistentRankedSet.withNaturalOrder();
            for (int i = 1; i <= n; i++) set.add(i);
            String name = snap(base);
            adapter.saveSnapshot(name, set.engine().snapshot(), KeySerializer.INTEGER);
            return name;
        }

        @Test
        @DisplayName("3: every truncation of a persistent snapshot is refused, never loaded short")
        void truncatedPersistentSnapshotRefused() throws IOException {
            String name = savePersistent("trunc", 200);
            Path file = fileOf(name);
            byte[] full = Files.readAllBytes(file);
            List<Integer> original = new ArrayList<>();
            for (int i = 1; i <= 200; i++) original.add(i);

            try {
                for (int cut = full.length - 1; cut > 0; cut--) {
                    Files.write(file, java.util.Arrays.copyOf(full, cut));
                    PersistentTreeEngine<Integer> loaded =
                            adapter.loadPersistent(name, KeySerializer.INTEGER);
                    if (loaded != null) {
                        assertEquals(original, loaded.inOrder(),
                                "truncation at byte " + cut + " loaded a WRONG set of "
                                + loaded.size() + " keys instead of being refused");
                    }
                }
            } finally {
                Files.write(file, full);
            }
        }

        @Test
        @DisplayName("3: a size-field/key-count disagreement is refused even when the line is intact")
        void tamperedSizeFieldRefused() throws IOException {
            String name = savePersistent("tamper", 40);
            Path file = fileOf(name);
            List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
            String[] header = lines.get(0).split("\\|");
            header[3] = "41";                                   // claims one more key than it has
            Files.write(file, List.of(String.join("|", header), lines.get(1)),
                    StandardCharsets.UTF_8);

            assertNull(adapter.loadPersistent(name, KeySerializer.INTEGER),
                    "the header size field is not advisory on the flat path either");
        }

        @Test
        @DisplayName("3: a non-ascending key list is refused (the flat path's structural gate)")
        void unorderedKeyListRefused() throws IOException {
            String name = savePersistent("unordered", 5);
            Path file = fileOf(name);
            List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
            Files.write(file, List.of(lines.get(0), "1;2;2;4;5;"), StandardCharsets.UTF_8);

            assertNull(adapter.loadPersistent(name, KeySerializer.INTEGER),
                    "a duplicate key would replay into a set smaller than the header declares");
        }

        @Test
        @DisplayName("4: a truncated persistent snapshot leaves the target ensemble untouched")
        void loadEnsembleRefusesWithoutWipingTarget() throws IOException {
            String name = savePersistent("ens-flat", 300);
            Path file = fileOf(name);
            byte[] full = Files.readAllBytes(file);
            Files.write(file, java.util.Arrays.copyOf(full, full.length / 2));   // mid-data-line

            EnsembleOrderedSet<Integer> target = mirrorEnsemble();
            for (int i = 900; i < 910; i++) target.add(i);
            List<Integer> before = target.inOrder();

            assertFalse(adapter.loadEnsemble(name, KeySerializer.INTEGER, target),
                    "a malformed snapshot must report false");
            assertEquals(before, target.inOrder(),
                    "the javadoc's 'the target is left untouched' must hold literally");
            assertEquals(before.size(), target.size());
        }

        @Test
        @DisplayName("4: a truncated pre-order snapshot leaves the target ensemble untouched too")
        void loadEnsembleRefusesTruncatedPreOrder() throws IOException {
            OrderedSet<Integer> src = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            for (int i = 0; i < 300; i++) src.add(i);
            String name = snap("ens-preorder");
            adapter.saveSnapshot(name, src, KeySerializer.INTEGER);
            Path file = fileOf(name);
            byte[] full = Files.readAllBytes(file);
            Files.write(file, java.util.Arrays.copyOf(full, full.length / 2));

            EnsembleOrderedSet<Integer> target = mirrorEnsemble();
            for (int i = 900; i < 910; i++) target.add(i);
            List<Integer> before = target.inOrder();

            assertFalse(adapter.loadEnsemble(name, KeySerializer.INTEGER, target));
            assertEquals(before, target.inOrder(), "target untouched on a malformed pre-order file");
        }

        @Test
        @DisplayName("4: a healthy flat snapshot still replays into every member")
        void loadEnsembleStillWorks() {
            String name = savePersistent("ens-ok", 250);
            EnsembleOrderedSet<Integer> target = mirrorEnsemble();
            target.add(-1);
            assertTrue(adapter.loadEnsemble(name, KeySerializer.INTEGER, target));
            assertEquals(250, target.size(), "the old contents are replaced, not merged");
            assertEquals(1, (int) target.minimum());
            assertEquals(250, (int) target.maximum());
        }

        @Test
        @DisplayName("5: concurrent saves of one name always commit one complete snapshot")
        void concurrentSavesNeverCorruptTheTarget() throws Exception {
            OrderedSet<Integer> even = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            OrderedSet<Integer> odd  = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            for (int i = 0; i < 2_000; i++) { even.add(2 * i); odd.add(2 * i + 1); }
            List<Integer> evenKeys = even.inOrder(), oddKeys = odd.inOrder();

            String name = snap("race");
            for (int round = 0; round < 25; round++) {
                CountDownLatch go = new CountDownLatch(1);
                Thread a = saver(go, name, even);
                Thread b = saver(go, name, odd);
                a.start(); b.start();
                go.countDown();
                a.join(); b.join();

                OrderedSet<Integer> loaded = adapter.loadOrderedSet(name, KeySerializer.INTEGER);
                assertNotNull(loaded, "round " + round + ": the committed file must be loadable — "
                        + "a shared staging file let one commit publish a half-written snapshot");
                List<Integer> got = loaded.inOrder();
                assertTrue(got.equals(evenKeys) || got.equals(oddKeys),
                        "round " + round + ": the committed file must be exactly one of the two "
                        + "snapshots, not a blend (n=" + got.size() + ")");
            }
        }

        private Thread saver(CountDownLatch go, String name, OrderedSet<Integer> set) {
            return new Thread(() -> {
                try {
                    go.await();
                    adapter.saveSnapshot(name, set, KeySerializer.INTEGER);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            });
        }

        private EnsembleOrderedSet<Integer> mirrorEnsemble() {
            return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(() -> new RedBlackStrategy<Integer>())
                    .member(() -> new AVLStrategy<Integer>())
                    .build();
        }
    }

    // ── 13: PersistentRankedSet change reporting + meters ─────────────────────

    @Nested
    @DisplayName("finding 13 — PersistentRankedSet reports change exactly under concurrent writers")
    class PersistentAdapterConcurrency {

        @Test
        @DisplayName("the number of true add() returns equals the final key count")
        void concurrentAddsReportChangeExactly() throws Exception {
            PersistentRankedSet<Integer> set = PersistentRankedSet.withNaturalOrder();
            int threads = 4, perThread = 20_000;
            AtomicInteger claimed = new AtomicInteger();
            AtomicReference<Throwable> fault = new AtomicReference<>();
            CountDownLatch go = new CountDownLatch(1);
            List<Thread> workers = new ArrayList<>();

            for (int t = 0; t < threads; t++) {
                final int seed = t;
                Thread w = new Thread(() -> {
                    try {
                        Random rng = new Random(seed);
                        go.await();
                        int mine = 0;
                        for (int i = 0; i < perThread; i++) {
                            if (set.add(rng.nextInt(25_000))) mine++;
                        }
                        claimed.addAndGet(mine);
                    } catch (Throwable e) {
                        fault.set(e);
                    }
                });
                workers.add(w);
                w.start();
            }
            go.countDown();
            for (Thread w : workers) w.join();

            assertNull(fault.get(), "no writer faulted");
            assertEquals(set.size(), claimed.get(),
                    "every key present was claimed by exactly one add() — a size-delta pair read "
                    + "outside the lock over-reports change, and that boolean is what VERIFIED votes on");
            assertTrue(set.avgInsertTimeMs() > 0, "the insert meter counted the inserts");
        }

        @Test
        @DisplayName("the number of true remove() returns equals the number of keys that left")
        void concurrentRemovesReportChangeExactly() throws Exception {
            PersistentRankedSet<Integer> set = PersistentRankedSet.withNaturalOrder();
            for (int i = 0; i < 20_000; i++) set.add(i);
            int before = set.size();

            int threads = 4;
            AtomicInteger claimed = new AtomicInteger();
            CountDownLatch go = new CountDownLatch(1);
            List<Thread> workers = new ArrayList<>();
            for (int t = 0; t < threads; t++) {
                final int seed = 100 + t;
                Thread w = new Thread(() -> {
                    try {
                        Random rng = new Random(seed);
                        go.await();
                        int mine = 0;
                        for (int i = 0; i < 20_000; i++) {
                            if (set.remove(rng.nextInt(20_000))) mine++;
                        }
                        claimed.addAndGet(mine);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                });
                workers.add(w);
                w.start();
            }
            go.countDown();
            for (Thread w : workers) w.join();

            assertEquals(before - set.size(), claimed.get(),
                    "every key removed was claimed by exactly one remove()");
            assertTrue(set.avgDeleteTimeMs() > 0, "the delete meter counted the deletes");
        }

        @Test
        @DisplayName("single-threaded change reporting is unchanged")
        void sequentialSemanticsUnchanged() {
            PersistentRankedSet<Integer> set = PersistentRankedSet.withNaturalOrder();
            assertTrue(set.add(5));
            assertFalse(set.add(5), "duplicate insert reports no change");
            assertTrue(set.remove(5));
            assertFalse(set.remove(5), "removing an absent key reports no change");
            assertEquals(0, set.size());
        }
    }

    // ── 14: B+tree null-argument parity ───────────────────────────────────────

    @Nested
    @DisplayName("finding 14 — null-argument parity across all three RankedSet implementations")
    class NullParity {

        /**
         * Every {@code RankedSet}/{@code OrderedCollection} method that takes a key, called with
         * {@code null}. The three implementations must throw the same class —
         * VERIFIED voting compares thrown-exception classes ({@code EnsembleOrderedSet.Thrown}),
         * so a divergence quarantines a structurally healthy member.
         *
         * <p>Asserted at size 0 as well as populated (audit 2026-08-17, item 1). The size-0 case
         * used to be excluded because {@code OrderedSet} genuinely diverged there: with no root
         * to compare against, the descend never reached the comparator that produced the NPE on a
         * populated set, so {@code contains(null)} answered {@code false}, {@code rank(null)} came
         * back as {@code NoSuchElementException}, and {@code add(null)} <em>linked null in as a
         * real element</em>. The entry points now null-check explicitly, so the thrown class no
         * longer depends on how many keys happen to be in the set.</p>
         */
        private Map<String, Consumer<RankedSet<Integer>>> nullOps() {
            Map<String, Consumer<RankedSet<Integer>>> ops = new LinkedHashMap<>();
            ops.put("add(null)",             s -> s.add(null));
            ops.put("remove(null)",          s -> s.remove(null));
            ops.put("contains(null)",        s -> s.contains(null));
            ops.put("rank(null)",            s -> s.rank(null));
            ops.put("successor(null)",       s -> s.successor(null));
            ops.put("predecessor(null)",     s -> s.predecessor(null));
            ops.put("countInRange(null, 5)", s -> s.countInRange(null, 5));
            ops.put("countInRange(5, null)", s -> s.countInRange(5, null));
            ops.put("rangeQuery(null, 5)",   s -> s.rangeQuery(null, 5));
            ops.put("rangeQuery(5, null)",   s -> s.rangeQuery(5, null));
            return ops;
        }

        private RankedSet<Integer> fill(RankedSet<Integer> s, int keys) {
            for (int i = 1; i <= keys; i++) s.add(i);
            return s;
        }

        @Test
        @DisplayName("all three implementations throw NullPointerException, method for method, at size 0 and populated")
        void nullArgumentsThrowIdentically() {
            for (int keys : new int[]{ 0, 1, 9 }) {
                for (Map.Entry<String, Consumer<RankedSet<Integer>>> op : nullOps().entrySet()) {
                    String where = op.getKey() + " at size " + keys;
                    Class<?> ordered    = thrownBy(op.getValue(),
                            fill(OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>()), keys));
                    Class<?> persistent = thrownBy(op.getValue(),
                            fill(PersistentRankedSet.withNaturalOrder(), keys));
                    Class<?> bplus      = thrownBy(op.getValue(),
                            fill(BPlusTreeEngine.withNaturalOrder(4), keys));

                    assertEquals(NullPointerException.class, ordered, where + " on OrderedSet");
                    assertEquals(ordered, persistent, where + " — PersistentRankedSet diverges");
                    assertEquals(ordered, bplus, where + " — BPlusTreeEngine diverges");
                }
            }
        }

        /**
         * The worst of the size-0 divergences on its own: a rejected {@code add} must leave the
         * set genuinely untouched. Before the fix the null was linked in as a real element, so
         * the set reported size 1 and every later read walked into it.
         */
        @Test
        @DisplayName("add(null) on an empty set inserts nothing — it does not become an element")
        void addNullNeverBecomesAnElement() {
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            assertThrows(NullPointerException.class, () -> set.add(null));
            assertEquals(0, set.size(), "the rejected add must not have grown the set");
            assertTrue(set.inOrder().isEmpty(), "no null key was linked into the tree");
            assertTrue(set.isEmpty());

            // and the set still works normally afterwards
            assertTrue(set.add(1));
            assertEquals(List.of(1), set.inOrder());
            assertThrows(NullPointerException.class, () -> set.add(null));
            assertEquals(List.of(1), set.inOrder());
        }

        /** Non-null arguments are unaffected at every size — the guards are not a lobotomy. */
        @Test
        @DisplayName("non-null keys behave exactly as before on an empty set")
        void nonNullArgumentsUnchangedOnEmptySets() {
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            assertFalse(set.contains(3), "absent on empty");
            assertFalse(set.remove(3), "removing from empty reports no change");
            assertEquals(0, set.countInRange(1, 9));
            assertTrue(set.rangeQuery(1, 9).isEmpty());
            assertNull(set.minimum());
            assertThrows(java.util.NoSuchElementException.class, () -> set.rank(3),
                    "an absent NON-null key is still NoSuchElementException, not NPE");
        }

        @Test
        @DisplayName("a VERIFIED ensemble survives contains(null): every member throws the same class")
        void ensembleContainsNullKeepsEveryMemberActive() {
            EnsembleOrderedSet<Integer> ens =
                    EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                            .member(() -> new RedBlackStrategy<Integer>())
                            .member(() -> new AVLStrategy<Integer>())
                            .engineMember(() -> BPlusTreeEngine.<Integer>withNaturalOrder(),
                                    "BPlusTreeEngine")
                            .mode(EnsembleMode.VERIFIED)
                            .build();
            for (int i = 1; i <= 200; i++) ens.add(i);

            assertThrows(NullPointerException.class, () -> ens.contains(null));

            assertEquals(3, ens.members().size());
            for (EnsembleMember<Integer> m : ens.members()) {
                assertEquals(EnsembleMember.State.ACTIVE, m.state(),
                        m.strategyName() + " must survive one bad caller argument");
            }
            assertTrue(ens.contains(7), "the ensemble still answers afterwards");
        }

        /** The exception class {@code op} throws on {@code set}, or {@code null} if it returns. */
        private Class<?> thrownBy(Consumer<RankedSet<Integer>> op, RankedSet<Integer> set) {
            try {
                op.accept(set);
                return null;
            } catch (Throwable t) {
                return t.getClass();
            }
        }
    }

    // ── 7: the descending view is read-only along every path ──────────────────

    @Nested
    @DisplayName("finding 7 — descendingSet() cannot mutate the base through its iterators")
    class DescendingViewIsReadOnly {

        private NavigableOrderedSet<Integer> base() {
            OrderedSet<Integer> s = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            for (int i = 1; i <= 5; i++) s.add(i);
            return new NavigableOrderedSet<>(s);
        }

        @Test
        @DisplayName("retainAll / removeAll on the descending view throw and leave the base intact")
        void bulkMutatorsThrowWithoutTouchingTheBase() {
            List<Integer> expected = List.of(1, 2, 3, 4, 5);

            NavigableOrderedSet<Integer> nav = base();
            NavigableSet<Integer> desc = nav.descendingSet();
            assertThrows(UnsupportedOperationException.class, () -> desc.retainAll(List.of(1)));
            assertEquals(expected, nav.base().inOrder(), "retainAll must not reach the base");

            // AbstractSet.removeAll picks its strategy by size: the smaller-argument shape goes
            // through remove(Object), the larger-argument shape through iterator().remove().
            NavigableOrderedSet<Integer> nav2 = base();
            assertThrows(UnsupportedOperationException.class,
                    () -> nav2.descendingSet().removeAll(List.of(1)));
            assertEquals(expected, nav2.base().inOrder(), "removeAll (small c) must not reach the base");

            NavigableOrderedSet<Integer> nav3 = base();
            assertThrows(UnsupportedOperationException.class,
                    () -> nav3.descendingSet().removeAll(List.of(1, 2, 3, 4, 5, 6, 7)));
            assertEquals(expected, nav3.base().inOrder(), "removeAll (large c) must not reach the base");
        }

        @Test
        @DisplayName("both descending-view iterators refuse remove(); the declared mutators still throw")
        void iteratorsAndDeclaredMutatorsRefuse() {
            NavigableOrderedSet<Integer> nav = base();
            NavigableSet<Integer> desc = nav.descendingSet();

            Iterator<Integer> it = desc.iterator();
            assertEquals(5, (int) it.next(), "descending order");
            assertThrows(UnsupportedOperationException.class, it::remove);

            Iterator<Integer> back = desc.descendingIterator();
            assertEquals(1, (int) back.next(), "ascending again");
            assertThrows(UnsupportedOperationException.class, back::remove);

            assertThrows(UnsupportedOperationException.class, () -> desc.add(9));
            assertThrows(UnsupportedOperationException.class, () -> desc.remove(3));
            assertThrows(UnsupportedOperationException.class, desc::clear);
            assertThrows(UnsupportedOperationException.class, desc::pollFirst);
            assertThrows(UnsupportedOperationException.class, desc::pollLast);

            assertEquals(List.of(1, 2, 3, 4, 5), nav.base().inOrder(), "the base is untouched");
        }

        @Test
        @DisplayName("a descending view of a range view is read-only too")
        void descendingRangeViewIsReadOnly() {
            NavigableOrderedSet<Integer> nav = base();
            NavigableSet<Integer> desc = nav.subSet(2, true, 5, false).descendingSet();
            assertEquals(List.of(4, 3, 2), new ArrayList<>(desc), "descending range contents");

            Iterator<Integer> it = desc.iterator();
            it.next();
            assertThrows(UnsupportedOperationException.class, it::remove);
            assertThrows(UnsupportedOperationException.class, () -> desc.retainAll(List.of(2)));
            assertEquals(List.of(1, 2, 3, 4, 5), nav.base().inOrder());
        }

        @Test
        @DisplayName("F-3 parity is preserved: the BASE descendingIterator() still removes")
        void baseDescendingIteratorStillRemoves() {
            NavigableOrderedSet<Integer> nav = base();
            Iterator<Integer> it = nav.descendingIterator();
            assertEquals(5, (int) it.next());
            it.remove();
            assertEquals(List.of(1, 2, 3, 4), nav.base().inOrder(),
                    "the base adapter's iterators are the mutation point (AUDIT-2026-08-14 F-3)");

            Iterator<Integer> asc = nav.iterator();
            asc.next();
            asc.remove();
            assertEquals(List.of(2, 3, 4), nav.base().inOrder());
        }

        @Test
        @DisplayName("descending views still read correctly (the fix is not a lobotomy)")
        void descendingViewStillReads() {
            NavigableOrderedSet<Integer> nav = base();
            NavigableSet<Integer> desc = nav.descendingSet();
            assertEquals(List.of(5, 4, 3, 2, 1), new ArrayList<>(desc));
            assertEquals(5, (int) desc.first());
            assertEquals(1, (int) desc.last());
            assertEquals(3, (int) desc.floor(3));
            assertTrue(desc.contains(4));

            Set<Integer> asSet = new HashSet<>(desc);
            assertEquals(5, asSet.size(), "copy constructors that iterate still work");
            assertTrue(desc.containsAll(List.of(1, 5)));
        }
    }
}
