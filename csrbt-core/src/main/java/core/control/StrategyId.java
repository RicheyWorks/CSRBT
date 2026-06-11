package core.control;

import core.strategy.AVLStrategy;
import core.strategy.HybridStrategy;
import core.strategy.RedBlackStrategy;
import core.strategy.SplayStrategy;
import core.strategy.TreeStrategy;

/**
 * The lean set of balancing strategies the control plane can actually choose between
 * (ADR-002 step 6, Phase B). This is deliberately decoupled from
 * {@code TreeGenome.StructureType} — which names seven types, three of them with no
 * engine — so the control plane carries no dependency on the legacy genome. Each id
 * maps directly to a fresh, key-agnostic {@link TreeStrategy} via {@link #newStrategy()}.
 *
 * <p>The {@code StrategyId ↔ StructureType} bridge that the strangler period needs to
 * drive the legacy {@code GenomeDrivenTreeController} is intentionally <em>not</em> here;
 * it lands in Phase D where the wiring actually uses it, keeping {@code core.control}
 * free of any {@code core.evolution} dependency for now.</p>
 */
public enum StrategyId {

    RED_BLACK("Red-Black"),
    AVL("AVL"),
    SPLAY("Splay"),
    HYBRID("Hybrid");

    private final String displayName;

    StrategyId(String displayName) { this.displayName = displayName; }

    /** Human-readable label for log lines and rationales. */
    public String displayName() { return displayName; }

    /**
     * Build a fresh strategy instance for this id, generic over the caller's key type
     * {@code K}. This is the control plane's single mapping from a decision back to an
     * executable {@link TreeStrategy}; the {@code MorphController} (Phase D) hands the
     * result to {@code OrderedSet.setStrategy}, which builds-aside, health-checks, and
     * atomically swaps it in.
     */
    public <K> TreeStrategy<K> newStrategy() {
        switch (this) {
            case RED_BLACK: return new RedBlackStrategy<K>();
            case AVL:       return new AVLStrategy<K>();
            case SPLAY:     return new SplayStrategy<K>();
            case HYBRID:    return new HybridStrategy<K>();
            default:        throw new AssertionError("unhandled StrategyId: " + this);
        }
    }
}
