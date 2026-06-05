package core.evolution;

import core.control.StrategyId;

/**
 * The single source of truth for the {@link StrategyId} &lt;-&gt; {@code StructureType}
 * mapping (ADR-002 step 6, Phase D / D2). {@code core.control} stays free of any
 * {@code core.evolution} dependency (see {@link StrategyId}'s own note), so the
 * strangler-period bridge that lets the legacy {@link GenomeDrivenTreeController} read its
 * incumbent and write a morph back lives here, in the legacy package that already knows
 * about both sides.
 *
 * <p>{@link StrategyId} names only the four implemented strategies; {@link TreeGenome.StructureType}
 * additionally names three types with no ordered-set engine (Fibonacci heap, van Emde Boas,
 * persistent tree). Asking for the {@code StrategyId} of one of those fails loudly rather than
 * inventing a strategy — the same "no silent no-op" stance as
 * {@code GenomeDrivenTreeController.buildStrategy}.</p>
 */
public final class StrategyIdBridge {

    private StrategyIdBridge() { }   // static utility; not instantiable

    /**
     * The control-plane {@link StrategyId} for an implemented {@link TreeGenome.StructureType}.
     *
     * @throws IllegalArgumentException for {@code null} or for the three non-strategy types
     *         (FIBONACCI_HEAP, VAN_EMDE_BOAS, PERSISTENT_TREE), which have no strategy.
     */
    public static StrategyId toStrategyId(TreeGenome.StructureType type) {
        if (type == null) throw new IllegalArgumentException("type cannot be null");
        switch (type) {
            case RED_BLACK: return StrategyId.RED_BLACK;
            case AVL:       return StrategyId.AVL;
            case SPLAY:     return StrategyId.SPLAY;
            case HYBRID:    return StrategyId.HYBRID;
            default:
                throw new IllegalArgumentException(
                        type + " has no control-plane StrategyId (not an ordered-set strategy)");
        }
    }

    /**
     * The {@link TreeGenome.StructureType} for a {@link StrategyId}. Total: every id maps.
     *
     * @throws IllegalArgumentException for {@code null}.
     */
    public static TreeGenome.StructureType toStructureType(StrategyId id) {
        if (id == null) throw new IllegalArgumentException("id cannot be null");
        switch (id) {
            case RED_BLACK: return TreeGenome.StructureType.RED_BLACK;
            case AVL:       return TreeGenome.StructureType.AVL;
            case SPLAY:     return TreeGenome.StructureType.SPLAY;
            case HYBRID:    return TreeGenome.StructureType.HYBRID;
            default:
                throw new AssertionError("unhandled StrategyId: " + id);
        }
    }
}
