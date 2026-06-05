package core.control;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * Transparent, weight-based {@link StrategyScorer} (ADR-002 step 6, Phase B). It rebases
 * the genome's per-structure weighted "fitness" idea (DESIGN §3.2) onto the live
 * {@link WorkloadFeatures} and emits an <em>estimated per-op cost</em> (lower = better)
 * instead of a self-interpreting fitness — so each decision is explainable from named
 * constants and one log line, with no opaque internal state.
 *
 * <h2>The model (cost in [0,1], lower wins)</h2>
 * Driven by the op mix ({@code readFraction r}, {@code writeFraction w}) and hot-key
 * {@code accessSkew s} — the three signals DESIGN §3.2 names as decisive:
 * <ul>
 *   <li><b>AVL</b> — strict balance ⇒ shallowest tree ⇒ reads cheap, writes pay more
 *       rotations: {@code BASE − READ·r + WRITE·w}. Ignores skew (no locality use).</li>
 *   <li><b>Red-Black</b> — fewest rotations per insert, solid worst case: cost falls with
 *       writes (and a little with reads): {@code BASE − WRITE·w − READ·r}. The safe
 *       all-rounder, so it wins balanced/write-heavy mixes.</li>
 *   <li><b>Splay</b> — self-adjusting: hot keys migrate to the root, so cost falls sharply
 *       with skew (most when reads dominate) but rises when the workload is uniform and the
 *       rotation overhead goes unrewarded:
 *       {@code BASE − SKEW·s − SKEW_READ·s·r + UNIFORM·(1−s)}.</li>
 *   <li><b>Hybrid</b> — the AVL+RB compromise, modelled as the mean of the three plus a
 *       small tie penalty, so it is scored but <em>never wins a tie</em> (anti-churn,
 *       DESIGN §3.3 spirit).</li>
 * </ul>
 *
 * <p>{@code meanSearchDepth} and {@code rotationsPerWrite} are present in the feature
 * vector but intentionally not weighted here: they describe the <em>incumbent's realized</em>
 * shape, which Phase D feeds back as an optional post-morph term, not the candidate cost
 * model. The scorer stays a pure function of workload shape.</p>
 */
public final class CostModelStrategyScorer implements StrategyScorer {

    // ── AVL: read-cheap, write-expensive (strict balance) ───────────────────────
    static final double BASE_AVL   = 0.55;
    static final double K_AVL_READ = 0.22;
    static final double K_AVL_WRITE= 0.30;

    // ── Red-Black: write-cheap baseline, mild read benefit ──────────────────────
    static final double BASE_RB    = 0.58;
    static final double K_RB_WRITE = 0.34;
    static final double K_RB_READ  = 0.06;

    // ── Splay: skew-driven, penalised when uniform ──────────────────────────────
    static final double BASE_SPLAY      = 0.55;
    static final double K_SPLAY_SKEW    = 0.16;
    static final double K_SPLAY_SKEWREAD= 0.25;
    static final double K_SPLAY_UNIFORM = 0.10;

    // ── Hybrid: mean of the three, biased to lose ties ──────────────────────────
    static final double HYBRID_TIE_PENALTY = 0.02;

    @Override
    public List<Score> score(WorkloadFeatures f) {
        double r = f.readFraction();
        double w = f.writeFraction();
        double s = f.accessSkew();

        double avl   = clamp01(BASE_AVL   - K_AVL_READ * r + K_AVL_WRITE * w);
        double rb    = clamp01(BASE_RB    - K_RB_WRITE * w - K_RB_READ * r);
        double splay = clamp01(BASE_SPLAY - K_SPLAY_SKEW * s - K_SPLAY_SKEWREAD * (s * r)
                                          + K_SPLAY_UNIFORM * (1.0 - s));
        double hybrid = clamp01((avl + rb + splay) / 3.0 + HYBRID_TIE_PENALTY);

        List<Score> scores = new ArrayList<>(4);
        scores.add(new Score(StrategyId.SPLAY, splay, String.format(
                "skew=%.2f read=%.2f: self-adjusts hot keys toward the root", s, r)));
        scores.add(new Score(StrategyId.AVL, avl, String.format(
                "read=%.2f write=%.2f: strict balance → shallowest tree, skew unused", r, w)));
        scores.add(new Score(StrategyId.RED_BLACK, rb, String.format(
                "write=%.2f: fewest rotations/insert, solid worst case", w)));
        scores.add(new Score(StrategyId.HYBRID, hybrid,
                "AVL+RB compromise; biased to lose ties to avoid churn"));

        // Ascending cost; deterministic tie-break by enum ordinal (Hybrid is last anyway).
        scores.sort(Comparator.comparingDouble(Score::estimatedCost)
                              .thenComparingInt(sc -> sc.strategy().ordinal()));
        return scores;
    }

    private static double clamp01(double x) {
        return x < 0.0 ? 0.0 : (x > 1.0 ? 1.0 : x);
    }
}
