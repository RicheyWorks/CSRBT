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
 * deterministic meter ADR-011 V5 made the house standard. <b>Recalibrated 2026-07-14</b>
 * after the single-descent write fix (census finding A): the 2026-06-10 tables were
 * measured through a write path that descended twice per successful mutation and compared
 * twice per insert step (RB/Splay/Hybrid), so "AVL beats RB on every diet" was largely
 * that artifact. The post-fix evidence (phase-shift censuses + re-run E3/E3b probes):
 * <b>reads are a family-wide near-tie</b> (RB = TreeMap bit-exactly; AVL/Hybrid within
 * ~1.5%); on <b>any diet with writes, Hybrid is best-fixed on every seed</b> (E3
 * 11.56–11.61 vs AVL 11.84–11.90 vs RB 14.09–14.19; E3b the same shape); RB's remaining
 * deficit is concentrated in sequential/windowed write blocks, which the r/w/s feature
 * space cannot see, so it is blended into the write term. Rotation pricing remains a held
 * item (ADR-009 §3) — noted because Hybrid's per-write instrumentation (recordAccess) is
 * likewise unpriced by this meter.</p>
 *
 * <h2>The model (cost in [0,1], lower wins)</h2>
 * Driven by the op mix ({@code readFraction r}, {@code writeFraction w}) and hot-key
 * {@code accessSkew s}:
 * <ul>
 *   <li><b>AVL</b> — the read-side baseline: {@code BASE − READ·r + WRITE·w}. First on
 *       read-dominant diets (by a whisker over Hybrid — measured tie, ordered for
 *       anti-churn continuity with the 2026-06-10 pins).</li>
 *   <li><b>Hybrid</b> — the measured all-rounder post-fix (AVL balance + RB delete
 *       machinery, single-compare insert): its own calibrated line,
 *       {@code BASE − READ·r + WRITE·w} with the smallest write surcharge. Crosses under
 *       AVL at {@code w ≳ 0.08}: writes fund it, pure reads don't.</li>
 *   <li><b>Red-Black</b> — read parity with AVL (modelled +6% at r=1: inside the
 *       production 20% margin ⇒ a read diet HOLDS an RB incumbent, which is what the
 *       post-fix meter says such a morph is worth), but the sequential/windowed write
 *       deficit lands in its write term: {@code BASE − READ·r + WRITE·w} crossing the
 *       morph margin vs Hybrid near {@code w ≈ 0.8}.</li>
 *   <li><b>Splay</b> — unchanged: self-adjusting, cost falls with skew (most when reads
 *       dominate), rises when uniform traffic leaves the rotation overhead unrewarded:
 *       {@code BASE − SKEW·s − SKEW_READ·s·r + UNIFORM·(1−s)}; overtakes the balanced
 *       family near s·r ≳ 0.4. (Note: post-ADR-004 reads never splay — its wins live in
 *       write-containing recency-local diets, which is where the probes still crown it.)</li>
 * </ul>
 *
 * <p>{@code meanSearchDepth} and {@code rotationsPerWrite} are present in the feature
 * vector but intentionally not weighted here: they describe the <em>incumbent's realized</em>
 * shape, which Phase D feeds back as an optional post-morph term, not the candidate cost
 * model. The scorer stays a pure function of workload shape.</p>
 */
public final class CostModelStrategyScorer implements StrategyScorer {

    // ── AVL: the read-side baseline; modest write surcharge ─────────────────────
    static final double BASE_AVL   = 0.46;
    static final double K_AVL_READ = 0.12;
    static final double K_AVL_WRITE= 0.04;

    // ── Hybrid: the post-fix all-rounder — crosses under AVL once w ≳ 0.08 ──────
    static final double BASE_HYBRID   = 0.462;
    static final double K_HYBRID_READ = 0.12;
    static final double K_HYBRID_WRITE= 0.015;

    // ── Red-Black: read parity (holds inside the morph margin); the measured
    //    sequential/windowed write deficit lands in the write term ────────────────
    static final double BASE_RB    = 0.56;
    static final double K_RB_READ  = 0.20;
    static final double K_RB_WRITE = 0.06;

    // ── Splay: skew-driven, penalised when uniform (unchanged from 2026-06-10) ──
    static final double BASE_SPLAY      = 0.50;
    static final double K_SPLAY_SKEW    = 0.10;
    static final double K_SPLAY_SKEWREAD= 0.30;
    static final double K_SPLAY_UNIFORM = 0.12;

    @Override
    public List<Score> score(WorkloadFeatures f) {
        double r = f.readFraction();
        double w = f.writeFraction();
        double s = f.accessSkew();

        double avl    = clamp01(BASE_AVL    - K_AVL_READ * r    + K_AVL_WRITE * w);
        double hybrid = clamp01(BASE_HYBRID - K_HYBRID_READ * r + K_HYBRID_WRITE * w);
        double rb     = clamp01(BASE_RB     - K_RB_READ * r     + K_RB_WRITE * w);
        double splay  = clamp01(BASE_SPLAY  - K_SPLAY_SKEW * s  - K_SPLAY_SKEWREAD * (s * r)
                                            + K_SPLAY_UNIFORM * (1.0 - s));

        List<Score> scores = new ArrayList<>(4);
        scores.add(new Score(StrategyId.SPLAY, splay, String.format(
                "skew=%.2f read=%.2f: self-adjusts hot keys toward the root (write-path only post-ADR-004)", s, r)));
        scores.add(new Score(StrategyId.AVL, avl, String.format(
                "read=%.2f write=%.2f: the read-side baseline (family near-tie on reads)", r, w)));
        scores.add(new Score(StrategyId.HYBRID, hybrid, String.format(
                "write=%.2f: measured post-fix all-rounder — writes fund it, pure reads don't", w)));
        scores.add(new Score(StrategyId.RED_BLACK, rb, String.format(
                "write=%.2f: read parity, rotation-thrifty; sequential/windowed write deficit priced here", w)));

        // Ascending cost; deterministic tie-break by enum ordinal (Hybrid is last anyway).
        scores.sort(Comparator.comparingDouble(Score::estimatedCost)
                              .thenComparingInt(sc -> sc.strategy().ordinal()));
        return scores;
    }

    private static double clamp01(double x) {
        return x < 0.0 ? 0.0 : (x > 1.0 ? 1.0 : x);
    }
}
