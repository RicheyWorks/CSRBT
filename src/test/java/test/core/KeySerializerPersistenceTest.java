package test.core;

import core.OrderedSet;
import core.TreeContext;
import core.persistence.FilePersistenceAdapter;
import core.persistence.KeySerializer;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Persistence tests for the pluggable key (de)serializer (ADR-002 step 5).
 *
 * <p>Where the {@code int} snapshot tests (in {@code RegressionFixesTest} /
 * {@code AuditFixesTest}) pin the legacy {@code Integer} format, this suite proves the snapshot
 * format is now genuinely key-type-agnostic: it round-trips {@link OrderedSet}s of
 * <em>non-{@code Integer}</em> keys through {@link FilePersistenceAdapter} and a
 * {@link KeySerializer}, including adversarial string keys that contain the format's own
 * delimiters. It also re-pins the {@code Integer} {@code TreeContext} path to guarantee step 5
 * is backward compatible (the int path simply delegates through {@link KeySerializer#INTEGER}).</p>
 *
 * <p>Each test writes to the shared {@code snapshots/} directory under uniquely-prefixed names
 * and deletes them in {@link #cleanup()}.</p>
 */
@DisplayName("KeySerializer<K> snapshot persistence (step 5)")
class KeySerializerPersistenceTest {

    private final FilePersistenceAdapter adapter = new FilePersistenceAdapter();
    private final List<String> created = new ArrayList<>();

    /** Register a uniquely-named snapshot for cleanup and return the name. */
    private String snap(String base) {
        String name = "test-ks-" + base + "-" + System.nanoTime();
        created.add(name);
        return name;
    }

    @AfterEach
    void cleanup() {
        for (String name : created) {
            adapter.deleteSnapshot(name);
        }
    }

    // ── KeySerializer contract (unit) ──────────────────────────────────────────

    @Nested
    @DisplayName("KeySerializer contract")
    class SerializerUnit {

        @Test
        @DisplayName("INTEGER round-trips every int, including the extremes and negatives")
        void integerRoundTrip() {
            KeySerializer<Integer> ks = KeySerializer.INTEGER;
            for (int v : new int[]{0, -1, 1, 42, -9999, Integer.MIN_VALUE, Integer.MAX_VALUE}) {
                assertEquals(Integer.valueOf(v), ks.deserialize(ks.serialize(v)),
                        "round-trip " + v);
            }
        }

        @Test
        @DisplayName("LONG round-trips every long, including the extremes")
        void longRoundTrip() {
            KeySerializer<Long> ks = KeySerializer.LONG;
            for (long v : new long[]{0L, -1L, 1_000_000_000_000L, Long.MIN_VALUE, Long.MAX_VALUE}) {
                assertEquals(Long.valueOf(v), ks.deserialize(ks.serialize(v)), "round-trip " + v);
            }
        }

        @Test
        @DisplayName("string() escapes the reserved chars so adversarial keys survive")
        void stringEscaping() {
            KeySerializer<String> ks = KeySerializer.string();
            // Every reserved structural character, plus the escape char itself and non-ASCII.
            for (String s : Arrays.asList(
                    "plain", "a,b", "x;y", "p#q", "100%", "a|b", "%2C", "#", "a,b;c#d|e%f", "café")) {
                assertEquals(s, ks.deserialize(ks.serialize(s)), "round-trip [" + s + "]");
            }
        }

        @Test
        @DisplayName("string() leaves no raw delimiter in an encoded token")
        void stringEncodingHasNoRawDelimiters() {
            String enc = KeySerializer.string().serialize("a,b;c#d|e%f");
            assertFalse(enc.contains(","), "comma escaped");
            assertFalse(enc.contains(";"), "semicolon escaped");
            assertFalse(enc.contains("#"), "hash escaped");
            assertFalse(enc.contains("|"), "pipe escaped");
            assertFalse(enc.equals("#"), "an encoded token is never the NIL marker");
            assertFalse(enc.isEmpty(), "an encoded non-empty key is never empty");
        }

        @Test
        @DisplayName("string() rejects the empty string (it is the NIL/empty token)")
        void stringRejectsEmpty() {
            assertThrows(IllegalArgumentException.class, () -> KeySerializer.string().serialize(""));
        }
    }

    // ── Generic OrderedSet<K> round-trips through the adapter ───────────────────

    @Nested
    @DisplayName("Generic OrderedSet<K> save/load")
    class GenericRoundTrip {

        /** Save, reload with the supplied comparator, and assert contents + order stats survive. */
        private void assertRoundTrips(OrderedSet<String> set,
                                      KeySerializer<String> ks,
                                      Comparator<String> cmp,
                                      String name) {
            List<String> before = set.inOrder();
            adapter.saveSnapshot(name, set, ks);

            OrderedSet<String> loaded = adapter.loadOrderedSet(name, ks, cmp);
            assertNotNull(loaded, "load returns a set");
            assertEquals(before, loaded.inOrder(), "contents survive in comparator order");
            assertEquals(set.size(), loaded.size(), "size survives");
            for (String k : before) assertTrue(loaded.contains(k), "contains " + k);
            if (!before.isEmpty()) {
                assertEquals(before.get(0), loaded.minimum(), "minimum survives");
                assertEquals(before.get(before.size() - 1), loaded.maximum(), "maximum survives");
                // order statistics are recomputed from the rebuilt, augmented tree
                assertEquals(before.size(), loaded.rank(before.get(before.size() - 1)), "rank(max)");
                assertEquals(before.get((before.size() - 1) / 2), loaded.median(), "median");
            }
        }

        @Test
        @DisplayName("String keys, natural order — including keys that contain delimiters")
        void stringNaturalOrder() {
            OrderedSet<String> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<String>());
            TreeSet<String> oracle = new TreeSet<>();
            for (String k : Arrays.asList(
                    "mango", "apple", "fig", "cherry", "a,b", "x;y", "p#q", "100%", "a|b")) {
                set.add(k); oracle.add(k);
            }
            String name = snap("str-natural");
            assertRoundTrips(set, KeySerializer.string(), Comparator.naturalOrder(), name);

            // explicit: the reloaded contents equal the oracle (delimiters and all)
            OrderedSet<String> loaded = adapter.loadOrderedSet(name, KeySerializer.string());
            assertNotNull(loaded);
            assertEquals(new ArrayList<>(oracle), loaded.inOrder());
        }

        @Test
        @DisplayName("String keys, reverse comparator — the same comparator is supplied to load")
        void stringReverseComparator() {
            Comparator<String> reverse = Comparator.reverseOrder();
            OrderedSet<String> set = new OrderedSet<>(new AVLStrategy<>(), reverse);
            for (String k : Arrays.asList("delta", "alpha", "echo", "bravo", "charlie")) set.add(k);
            assertRoundTrips(set, KeySerializer.string(), reverse, snap("str-reverse"));
        }

        @Test
        @DisplayName("the backing strategy is restored from the header (AVL stays AVL)")
        void strategyIsRestored() {
            OrderedSet<String> set = new OrderedSet<>(new AVLStrategy<String>(), Comparator.naturalOrder());
            for (int i = 0; i < 32; i++) set.add(String.format("k%02d", i));
            String name = snap("strategy");
            adapter.saveSnapshot(name, set, KeySerializer.string());

            OrderedSet<String> loaded = adapter.loadOrderedSet(name, KeySerializer.string());
            assertNotNull(loaded);
            assertTrue(loaded.getStrategy() instanceof AVLStrategy, "AVL strategy restored from header");
        }

        @Test
        @DisplayName("a larger set round-trips under a Splay strategy with stats intact")
        void splayLargerSet() {
            OrderedSet<String> set = new OrderedSet<>(new SplayStrategy<String>(), Comparator.naturalOrder());
            for (int i = 0; i < 200; i++) set.add(String.format("v%03d", i));
            assertRoundTrips(set, KeySerializer.string(), Comparator.naturalOrder(), snap("splay-200"));
        }

        @Test
        @DisplayName("Integer keys via the generic API + KeySerializer.INTEGER")
        void integerKeysGenericApi() {
            OrderedSet<Integer> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<Integer>());
            for (int v : new int[]{5, -3, 42, 0, 17, -100, 8}) set.add(v);
            List<Integer> before = set.inOrder();

            String name = snap("int-generic");
            adapter.saveSnapshot(name, set, KeySerializer.INTEGER);
            OrderedSet<Integer> loaded = adapter.loadOrderedSet(name, KeySerializer.INTEGER);

            assertNotNull(loaded);
            assertEquals(before, loaded.inOrder(), "int contents survive");
            assertEquals(set.size(), loaded.size());
            assertEquals(Integer.valueOf(-100), loaded.minimum());
            assertEquals(Integer.valueOf(42), loaded.maximum());
        }
    }

    // ── Integer TreeContext back-compat (the int path must be unchanged) ────────

    @Nested
    @DisplayName("Integer TreeContext back-compat")
    class IntegerBackCompat {

        @Test
        @DisplayName("TreeContext snapshot save/load still round-trips through the int path")
        void treeContextRoundTrip() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            for (int v : new int[]{50, 30, 70, 20, 40, 60, 80, 10}) ctx.add(v);
            List<Integer> before = ctx.inOrder();

            String name = snap("ctx-int");
            adapter.saveSnapshot(name, ctx);                 // interface (Integer) entry point
            TreeContext loaded = adapter.loadSnapshot(name);

            assertNotNull(loaded, "int load returns a context");
            assertEquals(before, loaded.inOrder(), "int contents survive");
            assertEquals(ctx.getSize(), loaded.getSize(), "size survives");
            assertTrue(loaded.contains(80));
            assertFalse(loaded.contains(999));
        }

        @Test
        @DisplayName("a TreeContext saved by the int path reloads identically via the generic path")
        void intPathFileReadableByGenericPath() {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
            for (int v : new int[]{3, 1, 4, 1, 5, 9, 2, 6}) ctx.add(v);   // note the duplicate 1
            String name = snap("cross-read");
            adapter.saveSnapshot(name, ctx);                 // written by the int path

            // ... and read back by the generic path with KeySerializer.INTEGER
            OrderedSet<Integer> loaded = adapter.loadOrderedSet(name, KeySerializer.INTEGER);
            assertNotNull(loaded);
            assertEquals(ctx.inOrder(), loaded.inOrder(),
                    "the same .rbt file parses identically on both paths");
        }
    }

    // ── Edge cases ─────────────────────────────────────────────────────────────

    @Nested
    @DisplayName("Edge cases")
    class EdgeCases {

        @Test
        @DisplayName("an empty set round-trips (root is the NIL marker)")
        void emptySet() {
            OrderedSet<String> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<String>());
            String name = snap("empty");
            adapter.saveSnapshot(name, set, KeySerializer.string());

            OrderedSet<String> loaded = adapter.loadOrderedSet(name, KeySerializer.string());
            assertNotNull(loaded, "empty set still loads");
            assertTrue(loaded.isEmpty());
            assertEquals(0, loaded.size());
            assertNull(loaded.minimum());
        }

        @Test
        @DisplayName("a single-key set round-trips")
        void singleKey() {
            OrderedSet<String> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<String>());
            set.add("solo");
            String name = snap("single");
            adapter.saveSnapshot(name, set, KeySerializer.string());

            OrderedSet<String> loaded = adapter.loadOrderedSet(name, KeySerializer.string());
            assertNotNull(loaded);
            assertEquals(Arrays.asList("solo"), loaded.inOrder());
        }

        @Test
        @DisplayName("loading a missing snapshot returns null, not an exception")
        void missingSnapshot() {
            OrderedSet<String> loaded =
                    adapter.loadOrderedSet("test-ks-does-not-exist", KeySerializer.string());
            assertNull(loaded);
        }

        @Test
        @DisplayName("null arguments are rejected up front")
        void nullArguments() {
            OrderedSet<String> set = OrderedSet.withNaturalOrder(new RedBlackStrategy<String>());
            KeySerializer<String> ks = KeySerializer.string();
            Comparator<String> nat = Comparator.naturalOrder();
            assertThrows(IllegalArgumentException.class,
                    () -> adapter.saveSnapshot(snap("null-ks"), set, null));   // K=String from set
            assertThrows(IllegalArgumentException.class,
                    () -> adapter.loadOrderedSet("whatever", null, nat));      // K=String from nat
            assertThrows(IllegalArgumentException.class,
                    () -> adapter.loadOrderedSet("whatever", ks, null));       // K=String from ks
        }
    }
}
