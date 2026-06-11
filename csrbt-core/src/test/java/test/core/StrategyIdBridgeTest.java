package test.core;

import io.github.richeyworks.csrbt.control.StrategyId;
import io.github.richeyworks.csrbt.evolution.StrategyIdBridge;
import io.github.richeyworks.csrbt.evolution.TreeGenome.StructureType;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * StrategyId &lt;-&gt; StructureType bridge (ADR-002 step 6, Phase D / D2): the single mapping
 * the strangler uses to read the incumbent and to write a morph back. The four implemented
 * types round-trip both ways; the three non-strategy types have no StrategyId and must throw.
 */
@DisplayName("io.github.richeyworks.csrbt.evolution.StrategyIdBridge (Phase D / D2)")
public class StrategyIdBridgeTest {

    @Test
    @DisplayName("each implemented StructureType maps to its StrategyId and round-trips")
    void implementedTypesRoundTrip() {
        assertSame(StrategyId.RED_BLACK, StrategyIdBridge.toStrategyId(StructureType.RED_BLACK));
        assertSame(StrategyId.AVL,       StrategyIdBridge.toStrategyId(StructureType.AVL));
        assertSame(StrategyId.SPLAY,     StrategyIdBridge.toStrategyId(StructureType.SPLAY));
        assertSame(StrategyId.HYBRID,    StrategyIdBridge.toStrategyId(StructureType.HYBRID));

        for (StructureType st : new StructureType[]{
                StructureType.RED_BLACK, StructureType.AVL, StructureType.SPLAY, StructureType.HYBRID}) {
            assertSame(st, StrategyIdBridge.toStructureType(StrategyIdBridge.toStrategyId(st)),
                    st + " must round-trip");
        }
    }

    @Test
    @DisplayName("every StrategyId maps to a StructureType and round-trips")
    void strategyIdsRoundTrip() {
        for (StrategyId id : StrategyId.values()) {
            assertSame(id, StrategyIdBridge.toStrategyId(StrategyIdBridge.toStructureType(id)),
                    id + " must round-trip");
        }
    }

    @Test
    @DisplayName("the three non-strategy types have no StrategyId and throw")
    void nonStrategyTypesThrow() {
        assertThrows(IllegalArgumentException.class,
                () -> StrategyIdBridge.toStrategyId(StructureType.FIBONACCI_HEAP));
        assertThrows(IllegalArgumentException.class,
                () -> StrategyIdBridge.toStrategyId(StructureType.VAN_EMDE_BOAS));
        assertThrows(IllegalArgumentException.class,
                () -> StrategyIdBridge.toStrategyId(StructureType.PERSISTENT_TREE));
    }

    @Test
    @DisplayName("null arguments throw")
    void nullsThrow() {
        assertThrows(IllegalArgumentException.class, () -> StrategyIdBridge.toStrategyId(null));
        assertThrows(IllegalArgumentException.class, () -> StrategyIdBridge.toStructureType(null));
    }
}
