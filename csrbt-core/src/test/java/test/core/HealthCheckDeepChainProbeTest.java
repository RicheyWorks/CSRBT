package test.core;

import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.util.StrategyHealthCheck;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probe (ADR-117, 2026-09-01): the first robot to drive the adaptive controller over
 * 20k+ keys killed the lab console with a {@code StackOverflowError} at ~1,000 frames of
 * {@code StrategyHealthCheck.isBst} -- the candidate a morph builds aside under Splay from
 * sorted keys is a chain as deep as the set is large, and the BST check recursed down it.
 * A validator that dies on the trees it exists to validate is the ADR-106 defect in the
 * health check. The walk is iterative now; this pins it with a chain a recursive walk
 * cannot survive on a default stack.
 */
@DisplayName("StrategyHealthCheck — a deep chain is validated, not overflowed")
class HealthCheckDeepChainProbeTest {

    @Test
    @DisplayName("60,000 sorted keys under Splay validate healthy")
    void deepSplayChainValidates() {
        TreeContext ctx = new TreeContext(new SplayStrategy<>());
        for (int k = 1; k <= 60_000; k++) ctx.add(k);      // a chain: every insert is the new max
        List<String> failures = StrategyHealthCheck.validate(
                ctx.getTree(), ctx.getTree().getStrategy(), ctx.getTree().inOrder());
        assertTrue(failures.isEmpty(), "a deep but valid chain must validate: " + failures);
    }
}
