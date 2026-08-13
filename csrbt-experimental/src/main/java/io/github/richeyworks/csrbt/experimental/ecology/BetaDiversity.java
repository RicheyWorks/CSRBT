package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Between-community comparison — the layer the 2026-08-09 audit showed cannot live on
 * tree <em>structure</em>: left/right subtrees are disjoint by the BST invariant
 * (presence overlap &#x2261; 0) and ensemble replicas hold identical key sets (presence
 * overlap &#x2261; 1). The communities with real signal are <b>time windows of the access
 * distribution</b> ({@link EcologyRecorder#closedWindows()}): window-to-window turnover
 * is workload drift made measurable.
 *
 * <p>Standard first-course measures, presence-based and abundance-based, each cited at
 * the method. All pure static functions, oracle-testable with hand vectors.</p>
 */
public final class BetaDiversity {

    private BetaDiversity() {}

    // ── Presence-based similarity ─────────────────────────────────────────────

    /**
     * Jaccard similarity |A &#x2229; B| / |A &#x222A; B| (Jaccard 1912), in [0, 1].
     * Two empty communities are defined as identical (1.0).
     */
    public static <T> double jaccard(Set<T> a, Set<T> b) {
        if (a.isEmpty() && b.isEmpty()) return 1.0;
        Set<T> union = new HashSet<>(a);
        union.addAll(b);
        int inter = 0;
        for (T x : a) if (b.contains(x)) inter++;
        return (double) inter / union.size();
    }

    /**
     * S&#xF8;rensen–Dice similarity 2|A &#x2229; B| / (|A| + |B|) (S&#xF8;rensen 1948), in [0, 1].
     * Two empty communities are defined as identical (1.0).
     */
    public static <T> double sorensen(Set<T> a, Set<T> b) {
        if (a.isEmpty() && b.isEmpty()) return 1.0;
        int inter = 0;
        for (T x : a) if (b.contains(x)) inter++;
        return 2.0 * inter / (a.size() + b.size());
    }

    // ── Abundance-based dissimilarity / overlap ───────────────────────────────

    /**
     * Bray–Curtis dissimilarity 1 &#x2212; 2&#x3A3;min(a&#x1D62;, b&#x1D62;) / (&#x3A3;a + &#x3A3;b) (Bray &amp; Curtis
     * 1957), in [0, 1]: 0 = identical composition and abundance, 1 = nothing shared.
     * Two empty communities are defined as identical (0.0).
     */
    public static <T> double brayCurtis(Map<T, Long> a, Map<T, Long> b) {
        long totalA = 0, totalB = 0, sharedMin = 0;
        for (long c : a.values()) if (c > 0) totalA += c;
        for (long c : b.values()) if (c > 0) totalB += c;
        if (totalA + totalB == 0) return 0.0;
        for (Map.Entry<T, Long> e : a.entrySet()) {
            long ca = e.getValue();
            if (ca <= 0) continue;
            Long cb = b.get(e.getKey());
            if (cb != null && cb > 0) sharedMin += Math.min(ca, cb);
        }
        return 1.0 - (2.0 * sharedMin) / (totalA + totalB);
    }

    /**
     * Renkonen similarity (percentage similarity, Renkonen 1938): &#x3A3; min(p&#x1D62;, q&#x1D62;)
     * over <em>relative</em> abundances, in [0, 1] — 1 = identical composition. This is
     * the size-fair companion to {@link #brayCurtis}: raw Bray–Curtis between
     * communities of very different totals is inflated by the size gap alone (two
     * identically-composed communities of sizes N and 5N measure BC &#x2248; 0.67), so any
     * comparison across unequal sampling effort — a single window against a merged
     * baseline, a small survey against a large one — belongs here. Both empty &#x2192; 1.0;
     * exactly one empty &#x2192; 0.0.
     */
    public static <T> double renkonen(Map<T, Long> a, Map<T, Long> b) {
        long totalA = 0, totalB = 0;
        for (long c : a.values()) if (c > 0) totalA += c;
        for (long c : b.values()) if (c > 0) totalB += c;
        if (totalA == 0 && totalB == 0) return 1.0;
        if (totalA == 0 || totalB == 0) return 0.0;
        double sim = 0.0;
        for (Map.Entry<T, Long> e : a.entrySet()) {
            long ca = e.getValue();
            if (ca <= 0) continue;
            Long cb = b.get(e.getKey());
            if (cb != null && cb > 0) {
                sim += Math.min((double) ca / totalA, (double) cb / totalB);
            }
        }
        return sim;
    }

    /**
     * Pianka's symmetric niche-overlap index O = &#x3A3;p&#x1D62;q&#x1D62; / &#x221A;(&#x3A3;p&#x1D62;&#xB2; &#xB7; &#x3A3;q&#x1D62;&#xB2;)
     * (Pianka 1973), in [0, 1] — here between two <em>access</em> distributions
     * (e.g. two time windows: temporal niche overlap), where the resource axis is the
     * key space and utilization is touch frequency. This is the re-founding of
     * {@code TreeEcology.nicheOverlap()}, whose structural form is identically 0 (EC-1).
     * Either community empty &#x2192; 0.
     */
    public static <T> double pianka(Map<T, Long> a, Map<T, Long> b) {
        long totalA = 0, totalB = 0;
        for (long c : a.values()) if (c > 0) totalA += c;
        for (long c : b.values()) if (c > 0) totalB += c;
        if (totalA == 0 || totalB == 0) return 0.0;

        double num = 0.0, sqA = 0.0, sqB = 0.0;
        for (Map.Entry<T, Long> e : a.entrySet()) {
            long ca = e.getValue();
            if (ca <= 0) continue;
            double pa = (double) ca / totalA;
            sqA += pa * pa;
            Long cb = b.get(e.getKey());
            if (cb != null && cb > 0) num += pa * ((double) cb / totalB);
        }
        for (long cb : b.values()) {
            if (cb <= 0) continue;
            double pb = (double) cb / totalB;
            sqB += pb * pb;
        }
        double denom = Math.sqrt(sqA * sqB);
        return denom == 0.0 ? 0.0 : num / denom;
    }

    // ── Multi-community turnover ──────────────────────────────────────────────

    /**
     * Whittaker's beta diversity &#x3B2;w = &#x3B3;/&#x3B1;&#x304; &#x2212; 1 (Whittaker 1960): gamma richness over
     * mean alpha richness, minus one. 0 = every community holds the same species;
     * grows as composition turns over. Input is a window sequence, e.g.
     * {@link EcologyRecorder#closedWindows()}. Empty input or all-empty windows &#x2192; 0.
     */
    public static <T> double whittakerTurnover(List<Map<T, Long>> communities) {
        if (communities.isEmpty()) return 0.0;
        Set<T> gamma = new HashSet<>();
        double alphaSum = 0.0;
        for (Map<T, Long> c : communities) {
            int s = 0;
            for (Map.Entry<T, Long> e : c.entrySet()) {
                if (e.getValue() > 0) {
                    gamma.add(e.getKey());
                    s++;
                }
            }
            alphaSum += s;
        }
        double alphaBar = alphaSum / communities.size();
        if (alphaBar == 0.0) return 0.0;
        return gamma.size() / alphaBar - 1.0;
    }

    /** Presence set of a community — keys with abundance &gt; 0. */
    public static <T> Set<T> presence(Map<T, Long> abundance) {
        Set<T> out = new HashSet<>();
        for (Map.Entry<T, Long> e : abundance.entrySet()) {
            if (e.getValue() > 0) out.add(e.getKey());
        }
        return out;
    }
}
