package io.github.richeyworks.csrbt.experimental.ecology;

import io.github.richeyworks.csrbt.control.WorkloadFeatures;
import io.github.richeyworks.csrbt.control.WorkloadMonitor;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Deque;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The abundance seam (audit EC-1's fix): a deterministic, op-indexed recorder that turns
 * the per-key stream already flowing through the {@link WorkloadMonitor} interface into
 * the inputs every community-level index needs.
 *
 * <p>The 2026-08-09 ecology audit found that {@code TreeEcology}'s distribution indices
 * are constants on a duplicate-free BST: every stored key has abundance exactly 1, so
 * Shannon H&#x2032; &#x2261; ln(S), evenness &#x2261; 1, empirical z &#x2261; 1, and Pianka overlap between
 * disjoint-by-construction subtrees &#x2261; 0. The correct abundance distribution is not
 * <em>membership</em> but <em>access</em>: how often the workload touches each key. This
 * class retains exactly that — a per-key touch tally — plus the two byproducts the other
 * approved layers need: per-key lifespans (birth op &#x2192; death op) for the life-table layer,
 * and a population-size series for the growth layer.</p>
 *
 * <p>Three design rules, all house discipline:</p>
 * <ul>
 *   <li><b>Deterministic.</b> The clock is the op index — no wall time, no RNG. Two
 *       identical op streams produce identical state, field for field.</li>
 *   <li><b>Additive.</b> Implements {@link WorkloadMonitor}, so it can stand in the
 *       existing ADR-002 §9.2 seam (optionally chaining to a real monitor via
 *       {@code delegate}) with zero core changes.</li>
 *   <li><b>Bounded where it can be.</b> Closed windows are capped at {@code maxWindows}
 *       (oldest evicted); the cumulative tally and the alive-key birth register
 *       ({@code birthOps}) grow only with <em>distinct</em> keys, the same lifetime
 *       discipline as the E2 ancestry map. Two registers instead grow with <em>events</em>
 *       and are deliberately uncapped so the demography and growth layers see a complete
 *       run: {@link #lifespans()} grows with observed deaths (one entry per remove of a
 *       live key — a key repeatedly re-added and removed contributes one entry per cycle,
 *       so this is <em>not</em> bounded by distinct keys), and {@link #populationSeries()}
 *       grows with closed windows (one sample per boundary, retained even after the window
 *       it sampled is evicted). For a long-running deployment in the ADR-002 §9.2 seam over
 *       a remove-heavy stream, drain or periodically reconstruct the recorder rather than
 *       retaining one indefinitely.</li>
 * </ul>
 *
 * <p>Windowing: every {@code windowOps} recorded ops, the current per-key tally is closed
 * and a fresh one started. Closed windows are the "communities" the between-community
 * layer ({@link BetaDiversity}) compares — temporal turnover, window-to-window overlap.
 * The population size (alive-key count) is sampled at each window boundary for
 * {@link LogisticGrowth}.</p>
 */
public final class EcologyRecorder implements WorkloadMonitor {

    /** Default ops per window. */
    public static final int DEFAULT_WINDOW_OPS = 1024;
    /** Default cap on retained closed windows. */
    public static final int DEFAULT_MAX_WINDOWS = 32;

    private final int windowOps;
    private final int maxWindows;
    private final WorkloadMonitor delegate; // nullable — chain to a real monitor if given

    private long opIndex = 0;
    private long windowStartOp = 0;

    private final Map<Integer, Long> cumulative = new LinkedHashMap<>();
    private Map<Integer, Long> currentWindow = new LinkedHashMap<>();
    private final Deque<Map<Integer, Long>> closedWindows = new ArrayDeque<>();

    // Demography: birth op of currently-alive keys; completed lifespans of dead ones.
    private final Map<Integer, Long> birthOps = new HashMap<>();
    private final List<LifeTable.Lifespan> lifespans = new ArrayList<>();

    // Growth: (opIndex, aliveCount) sampled at every window boundary.
    private final List<long[]> populationSeries = new ArrayList<>();

    public EcologyRecorder() {
        this(DEFAULT_WINDOW_OPS, DEFAULT_MAX_WINDOWS, null);
    }

    public EcologyRecorder(int windowOps, int maxWindows) {
        this(windowOps, maxWindows, null);
    }

    /**
     * @param windowOps  ops per window; must be &#x2265; 1
     * @param maxWindows closed windows retained (oldest evicted); must be &#x2265; 1
     * @param delegate   optional real monitor to chain to; {@code null} for standalone use
     */
    public EcologyRecorder(int windowOps, int maxWindows, WorkloadMonitor delegate) {
        if (windowOps < 1)  throw new IllegalArgumentException("windowOps must be >= 1");
        if (maxWindows < 1) throw new IllegalArgumentException("maxWindows must be >= 1");
        this.windowOps  = windowOps;
        this.maxWindows = maxWindows;
        this.delegate   = delegate;
    }

    // ── WorkloadMonitor ───────────────────────────────────────────────────────

    /** An insert touches its key: tallied, and a birth if the key was not alive. */
    @Override
    public void recordAdd(int keyHash, int rotations) {
        tally(keyHash);
        birthOps.putIfAbsent(keyHash, opIndex);
        maybeRollWindow();
        if (delegate != null) delegate.recordAdd(keyHash, rotations);
    }

    /** A remove touches its key: tallied, and closes the key's lifespan if it was alive. */
    @Override
    public void recordRemove(int keyHash, int rotations) {
        tally(keyHash);
        Long birth = birthOps.remove(keyHash);
        if (birth != null) {
            lifespans.add(new LifeTable.Lifespan(keyHash, birth, opIndex));
        }
        maybeRollWindow();
        if (delegate != null) delegate.recordRemove(keyHash, rotations);
    }

    /** A lookup touches its key — the primary abundance signal. */
    @Override
    public void recordSearch(int keyHash, int depthTouched) {
        tally(keyHash);
        maybeRollWindow();
        if (delegate != null) delegate.recordSearch(keyHash, depthTouched);
    }

    /** Delegates when chained; {@link WorkloadFeatures#EMPTY} when standalone. */
    @Override
    public WorkloadFeatures snapshot() {
        return delegate != null ? delegate.snapshot() : WorkloadFeatures.EMPTY;
    }

    // ── Outputs ───────────────────────────────────────────────────────────────

    /** Total recorded ops (the deterministic clock). */
    public long opCount() {
        return opIndex;
    }

    /** Cumulative per-key touch counts over the whole run (unmodifiable view). */
    public Map<Integer, Long> cumulativeAbundance() {
        return Collections.unmodifiableMap(cumulative);
    }

    /** The still-open window's per-key touch counts (unmodifiable view). */
    public Map<Integer, Long> currentWindowAbundance() {
        return Collections.unmodifiableMap(currentWindow);
    }

    /** Closed windows, oldest &#x2192; newest, each an independent per-key tally. */
    public List<Map<Integer, Long>> closedWindows() {
        List<Map<Integer, Long>> out = new ArrayList<>(closedWindows.size());
        for (Map<Integer, Long> w : closedWindows) out.add(Collections.unmodifiableMap(w));
        return out;
    }

    /** Completed lifespans (keys removed after an observed insert), in death order. */
    public List<LifeTable.Lifespan> lifespans() {
        return Collections.unmodifiableList(lifespans);
    }

    /** Currently-alive keys with their birth ops — the right-censored cohort tail. */
    public Map<Integer, Long> aliveBirthOps() {
        return Collections.unmodifiableMap(birthOps);
    }

    /** Alive-key count as this recorder has observed it. */
    public int aliveCount() {
        return birthOps.size();
    }

    /**
     * Population-size samples, one {@code {opIndex, aliveCount}} pair per closed window
     * boundary — the input series for {@link LogisticGrowth#fit(List)}.
     */
    public List<long[]> populationSeries() {
        List<long[]> out = new ArrayList<>(populationSeries.size());
        for (long[] s : populationSeries) out.add(s.clone());
        return out;
    }

    // ── Internals ─────────────────────────────────────────────────────────────

    /** Advance the op clock and count the touch. Demography applies AFTER this and
     *  BEFORE {@link #maybeRollWindow()}, so a boundary op's birth/death is visible in
     *  the population sample taken at that boundary. */
    private void tally(int keyHash) {
        opIndex++;
        cumulative.merge(keyHash, 1L, Long::sum);
        currentWindow.merge(keyHash, 1L, Long::sum);
    }

    private void maybeRollWindow() {
        if (opIndex - windowStartOp < windowOps) return;
        closedWindows.addLast(currentWindow);
        if (closedWindows.size() > maxWindows) closedWindows.removeFirst();
        currentWindow = new LinkedHashMap<>();
        windowStartOp = opIndex;
        populationSeries.add(new long[]{ opIndex, birthOps.size() });
    }
}
