package core.control;

/**
 * Immutable record of the adaptation loop's recent decisions, supplying the two
 * stateful inputs the {@link MorphPolicy} needs for its anti-thrash gates
 * (DESIGN-adaptive-engine.md §3.3): how long since the last morph (cooldown) and how
 * many consecutive evaluations the current front-runner has held the top spot
 * (stability). The {@code MorphController} (Phase D) threads one of these through each
 * evaluation, advancing it with {@link #observed} and resetting it with
 * {@link #afterMorph}.
 *
 * @param opsSinceLastMorph ops elapsed since the last committed morph (cooldown clock)
 * @param lastWinner        the strategy that won the most recent evaluation, or {@code null}
 * @param winStreak         consecutive evaluations {@code lastWinner} has been the cheapest
 */
public record MorphHistory(int opsSinceLastMorph, StrategyId lastWinner, int winStreak) {

    /** A fresh history: no morph yet, no winner, cooldown clock at zero. */
    public static MorphHistory initial() {
        return new MorphHistory(0, null, 0);
    }

    /**
     * Consecutive wins credited to {@code candidate} — the stability signal. Returns the
     * running streak only when {@code candidate} is the standing winner, else 0 (it has
     * not yet strung together repeat wins).
     */
    public int consecutiveWins(StrategyId candidate) {
        return candidate != null && candidate == lastWinner ? winStreak : 0;
    }

    /**
     * Fold one evaluation into the history: advance the cooldown clock by
     * {@code opsElapsed} and update the win streak — incremented if {@code topCandidate}
     * repeats the last winner, otherwise restarted at 1.
     */
    public MorphHistory observed(StrategyId topCandidate, int opsElapsed) {
        int streak = (topCandidate != null && topCandidate == lastWinner) ? winStreak + 1 : 1;
        return new MorphHistory(opsSinceLastMorph + Math.max(0, opsElapsed), topCandidate, streak);
    }

    /** Reset after a committed morph: cooldown clock to zero and the streak cleared. */
    public MorphHistory afterMorph() {
        return new MorphHistory(0, null, 0);
    }
}
