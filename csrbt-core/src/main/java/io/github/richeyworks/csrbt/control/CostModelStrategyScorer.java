package io.github.richeyworks.csrbt.control;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * Transparent, weight-based {@link StrategyScorer} (ADR-002 step 6, Phase B; recalibrated
 * 2026-06-10). It turns the live {@link WorkloadFeatures} into an <em>estimated per-op
 * cost</em> (lower = better), so each decision is explainable from named constants and one
 * log line, with no opaque internal state.
 *
 * <h2>What the model predicts — and the calibration decision</h2>
 * <p>The constants are calibrated against <b>realized comparisons per op</b> — the
 * deterministic meter ADR-011 V5 made the house standard — using the measured tables in
 * the V5 verdict, the ADR-012 E3 per-block series, and the E3b fixed-strategy probe.
 * The original Phase-B constants encoded a rotation-priced (wall-clock-flavored) story:
 * "RB wins write-heavy and balanced mixes." On the comparisons meter that story is
 * <b>measurably false</b> — AVL beat RB on every diet probed (uniform 12.6 vs 15.4,
 * churn 14.0 vs 16.2, sequential 20.3 vs 33.9 cmp/op) — and the miscalibration had a
 * pinned consequence: in the E3b pre-registered experiment the selector sat on RB
 * through a 36% opportunity and never morphed. Where the two meters disagree, the
 * deterministic one decides (the V5 rule); rotation pricing remains a held item
 * (ADR-009 §3) until the composite metric has a consumer.</p>
 *
 * <h2>The model (cost in [0,1], lower wins)</h2>
 * Driven by the op mix ({@code readFraction r}, {@code writeFraction w}) and hot-key
 * {@code accessSkew s}:
 * <ul>
 *   <li><b>AVL</b> — strict balance ⇒ shallowest tree ⇒ fewest comparisons on nearly
 *       every diet; mild write surcharge: {@code BASE − READ·r + WRITE·w}. The
 *       calibrated all-diet baseline.</li>
 *   <li><b>Red-Black</b> — looser balance ⇒ deeper paths ⇒ consistently more
 *       comparisons than AVL (measured +16% churn, +22% uniform, +67% sequential); rotation thrift is real
 *       but unpriced by this meter: {@code BASE − WRITE·w − READ·r}, BASE set so RB
 *       trails AVL everywhere, more under read pressure.</li>
 *   <li><b>Splay</b> — self-adjusting: hot keys migrate to the root, so cost falls
 *       sharply with skew (most when reads dominate) and rises when uniform traffic
 *       leaves the rotation overhead unrewarded:
 *       {@code BASE − SKEW·s − SKEW_READ·s·r + UNIFORM·(1−s)}. Calibrated to overtake
 *       AVL near s·r ≳ 0.4 (the measured sequential/hot-read crossover).</li>
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

    // ── AVL: the comparisons baseline — shallowest paths, mild write surcharge ──
    static final double BASE_AVL   = 0.46;
    static final double K_AVL_READ = 0.12;
    static final double K_AVL_WRITE= 0.04;

    // ── Red-Black: deeper paths than AVL on every measured diet ─────────────────
    static final double BASE_RB    = 0.62;
    static final double K_RB_WRITE = 0.05;
    static final double K_RB_READ  = 0.04;

    // ── Splay: skew-driven, penalised when uniform ──────────────────────────────
    static final double BASE_SPLAY      = 0.50;
    static final double K_SPLAY_SKEW    = 0.10;
    static final double K_SPLAY_SKEWREAD= 0.30;
    static final double K_SPLAY_UNIFORM = 0.12;

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
                "read=%.2f write=%.2f: strict balance → fewest comparisons (calibrated baseline)", r, w)));
        scores.add(new Score(StrategyId.RED_BLACK, rb, String.format(
                "write=%.2f: rotation-thrifty but deeper paths — trails AVL on comparisons", w)));
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
