package core;

import core.evolution.TreeGenome.StructureType;
import core.interfaces.TreeEngine;
import core.strategy.AVLStrategy;
import core.strategy.HybridStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;
import core.strategy.TreeStrategy;

import java.util.EnumMap;
import java.util.EnumSet;
import java.util.Map;
import java.util.function.Supplier;

/**
 * Single source of truth for which {@link StructureType}s are actually
 * buildable, and how.
 *
 * <p>Previously the genome could recommend a {@code FIBONACCI_HEAP} or
 * {@code VAN_EMDE_BOAS} that no code could instantiate, and the controller's
 * {@code buildStrategy} quietly returned {@code null} (a silent no-op morph).
 * This registry makes the enum honest: every value maps to exactly one of
 * three states, with no silent gaps.</p>
 *
 * <ul>
 *   <li>{@link Support#STRATEGY} — a member of the pointer-based-BST family,
 *       built as a {@link RedBlackTree} driven by a {@link TreeStrategy}.</li>
 *   <li>{@link Support#ENGINE} — a standalone {@link TreeEngine} that is not a
 *       red-black strategy (e.g. the persistent tree).</li>
 *   <li>{@link Support#UNSUPPORTED} — declared in the enum but deliberately not
 *       built here, with a reason. These are not ordered-map structures and
 *       therefore do not fit the {@code TreeEngine} contract.</li>
 * </ul>
 *
 * <p>ADR-002 step 2: the registry builds {@code Integer}-keyed engines
 * ({@code TreeEngine<Integer>}), matching the current int behaviour. A
 * key-type-parameterised registry can come with the {@code OrderedSet<K>} facade
 * (step 4) if needed.</p>
 */
public final class TreeEngineRegistry {

    private TreeEngineRegistry() { }

    public enum Support { STRATEGY, ENGINE, UNSUPPORTED }

    /** Describes how (or whether) a {@link StructureType} can be built. */
    public static final class Capability {
        public final Support support;
        public final String  note;
        private final Supplier<TreeEngine<Integer>> engineFactory;   // null iff UNSUPPORTED

        private Capability(Support support, String note, Supplier<TreeEngine<Integer>> f) {
            this.support       = support;
            this.note          = note;
            this.engineFactory = f;
        }

        public boolean isBuildable() { return engineFactory != null; }
    }

    private static final Map<StructureType, Capability> MAP =
            new EnumMap<>(StructureType.class);

    static {
        MAP.put(StructureType.RED_BLACK,
                strategy("Red-black tree — default balanced BST.", RedBlackStrategy::new));
        MAP.put(StructureType.AVL,
                strategy("AVL tree — strict height balance, search-heavy workloads.", AVLStrategy::new));
        MAP.put(StructureType.SPLAY,
                strategy("Splay tree — self-adjusting, favours access locality.", SplayStrategy::new));
        MAP.put(StructureType.HYBRID,
                strategy("Hybrid — AVL balance pass + RB recolor pass.", HybridStrategy::new));

        MAP.put(StructureType.PERSISTENT_TREE,
                engine("Persistent ordered set — immutable, weight-balanced, path-copying; "
                     + "O(1) snapshots, wait-free reads (ADR-005).",
                       PersistentTreeEngine::withNaturalOrder));

        MAP.put(StructureType.FIBONACCI_HEAP, unsupported(
                "Priority-queue contract (insert / extract-min / decrease-key). "
              + "Not an ordered map, so it does not fit the OrderedCollection/TreeEngine API."));
        MAP.put(StructureType.VAN_EMDE_BOAS, unsupported(
                "Bounded-universe integer structure requiring a fixed key universe u. "
              + "This API exposes an unbounded int key space, so vEB is out of scope."));
    }

    private static Capability strategy(String note, Supplier<TreeStrategy<Integer>> s) {
        return new Capability(Support.STRATEGY, note, () -> RedBlackTree.withNaturalOrder(s.get()));
    }

    private static Capability engine(String note, Supplier<TreeEngine<Integer>> f) {
        return new Capability(Support.ENGINE, note, f);
    }

    private static Capability unsupported(String note) {
        return new Capability(Support.UNSUPPORTED, note, null);
    }

    // ── Public API ─────────────────────────────────────────────────────────────

    /** @return the capability descriptor for a type (never null for a valid enum value). */
    public static Capability capability(StructureType type) {
        return MAP.get(type);
    }

    /** @return {@code true} if an engine can actually be built for this type. */
    public static boolean isSupported(StructureType type) {
        return MAP.get(type).isBuildable();
    }

    /**
     * Build a live {@link TreeEngine} for the given type.
     *
     * @throws UnsupportedOperationException with a clear reason for any type
     *         that is declared in the enum but intentionally not buildable.
     */
    public static TreeEngine<Integer> create(StructureType type) {
        Capability c = MAP.get(type);
        if (!c.isBuildable()) {
            throw new UnsupportedOperationException(type + ": " + c.note);
        }
        return c.engineFactory.get();
    }

    /** @return every type that can actually be built. */
    public static EnumSet<StructureType> supportedTypes() {
        EnumSet<StructureType> out = EnumSet.noneOf(StructureType.class);
        for (Map.Entry<StructureType, Capability> e : MAP.entrySet()) {
            if (e.getValue().isBuildable()) out.add(e.getKey());
        }
        return out;
    }

    /** @return a one-line capability report across all declared types. */
    public static String describe() {
        StringBuilder sb = new StringBuilder("TreeEngineRegistry capabilities:\n");
        for (StructureType t : StructureType.values()) {
            Capability c = MAP.get(t);
            sb.append(String.format("  %-15s [%-11s] %s%n", t, c.support, c.note));
        }
        return sb.toString();
    }
}
