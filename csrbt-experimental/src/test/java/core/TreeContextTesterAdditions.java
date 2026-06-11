// ═══════════════════════════════════════════════════════════════════════════
//  ADDITIONS TO TreeContextTester.java  (or your own driver / JUnit class)
//  Drop these methods into your existing tester, or run them standalone.
// ═══════════════════════════════════════════════════════════════════════════

package core;

import core.augment.IntervalAugmentor;
import core.strategy.AVLStrategy;
import core.strategy.RedBlackStrategy;
import core.util.OrderStatisticsOps;
import experimental.TreeEcology;

import java.util.List;

public class TreeContextTesterAdditions {

    // ── 1. ORDER-STATISTICS DEMO ─────────────────────────────────────────────
    static void demoOrderStatistics() {
        System.out.println("\n═══ CLRS Ch.14.1 — Order-Statistics ═══");

        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        // Insert unsorted to prove OS-SELECT isn't just array indexing
        for (int v : new int[]{ 41, 38, 31, 12, 19, 8 }) ctx.add(v);

        OrderStatisticsOps<Integer> os = new OrderStatisticsOps<>(ctx.getTree());

        System.out.printf("Tree size = %d%n", ctx.getSize());
        System.out.printf("Minimum   = %s  (rank=1)%n",       os.minimum());
        System.out.printf("Maximum   = %s  (rank=%d)%n",       os.maximum(), ctx.getSize());
        System.out.printf("Median    = %s%n",                  os.median());
        System.out.printf("25th pct  = %s%n",                  os.percentile(25));
        System.out.printf("75th pct  = %s%n",                  os.percentile(75));

        // Rank lookup — CLRS p.342 example
        System.out.printf("rank(38)  = %d  (expected: 5)%n",  os.rank(38));
        System.out.printf("rank(12)  = %d  (expected: 2)%n",  os.rank(12));
        System.out.printf("select(3) = %s  (expected: 19)%n", os.select(3));

        // Range queries
        System.out.printf("count [12,38] = %d%n",             os.countInRange(12, 38));
        System.out.printf("range [12,38] = %s%n",             os.rangeQuery(12, 38));
        System.out.printf("successor(19) = %s%n",             os.successor(19));
        System.out.printf("predecessor(31)= %s%n",            os.predecessor(31));
    }

    // ── 2. INTERVAL TREE DEMO ────────────────────────────────────────────────
    static void demoIntervalTree() {
        System.out.println("\n═══ CLRS Ch.14.3 — Interval Trees ═══");

        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        ctx.setAugmentor(IntervalAugmentor.INSTANCE);

        // CLRS Figure 14.4 intervals
        int[][] intervals = { {16,21},{8,9},{25,30},{5,8},{15,23},{17,19},{26,26},{0,3},{6,10},{19,20} };
        for (int[] iv : intervals) IntervalAugmentor.insertInterval(ctx, iv[0], iv[1]);

        System.out.println(IntervalAugmentor.dump(ctx));

        // CLRS p.352 example: search for overlap with [22, 25]
        TreeNode1<Integer> hit = IntervalAugmentor.intervalSearch(ctx, 22, 25);
        System.out.printf("INTERVAL-SEARCH([22,25]) → [%d,%d]%n",
                hit.getData(), IntervalAugmentor.parseHi(hit));

        // All overlaps with [14, 18]
        List<int[]> all = IntervalAugmentor.intervalSearchAll(ctx, 14, 18);
        System.out.print("All overlapping [14,18]: ");
        all.forEach(iv -> System.out.printf("[%d,%d] ", iv[0], iv[1]));
        System.out.println();

        // Stabbing query: which intervals contain point 17?
        List<int[]> stab = IntervalAugmentor.stabQuery(ctx, 17);
        System.out.print("Intervals containing 17: ");
        stab.forEach(iv -> System.out.printf("[%d,%d] ", iv[0], iv[1]));
        System.out.println();
    }

    // ── 3. ECOLOGY DEMO ──────────────────────────────────────────────────────
    static void demoEcology() {
        System.out.println("\n═══ Ecological Analysis ═══");

        // Build a tree with a non-uniform distribution to make the metrics interesting
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        int[] values = { 10, 20, 30, 25, 15, 12, 8, 5, 40, 35, 22, 18, 28, 33, 7 };
        for (int v : values) ctx.add(v);

        TreeEcology eco = new TreeEcology(ctx);
        System.out.println(eco.ecologyReport());

        // Compare r/K score between RB and AVL on same data
        TreeContext avlCtx = new TreeContext(new AVLStrategy<>());
        for (int v : values) avlCtx.add(v);
        TreeEcology ecoAVL = new TreeEcology(avlCtx);

        System.out.printf("r/K (RedBlack) = %+.4f → %s%n",
                eco.rKScore(), eco.rKLabel());
        System.out.printf("r/K (AVL)      = %+.4f → %s%n",
                ecoAVL.rKScore(), ecoAVL.rKLabel());

        // Endosymbiosis: merge a guest tree into host
        TreeContext guest = new TreeContext(new RedBlackStrategy<>());
        for (int v : new int[]{ 100, 200, 25, 30 }) guest.add(v); // 25,30 are duplicates
        int transferred = eco.endosymbiosis(guest);
        System.out.printf("%nEndosymbiosis: %d values absorbed (duplicates silently lost)%n",
                transferred);
        System.out.printf("Host tree size after merge: %d%n", ctx.getSize());

        // Mitochondrial Eve
        TreeNode1<Integer> eve = eco.mitoEve();
        System.out.printf("Mitochondrial Eve: node=%d depth=%d%n",
                eve.getData(), eve.depth());
    }

    // ── 4. ADAPTIVE MORPHING DEMO ────────────────────────────────────────────
    static void demoAdaptiveMorph() {
        System.out.println("\n═══ Adaptive Morph (r → K selection pressure) ═══");

        // Insert in adversarial sorted order — maximally stresses RB
        TreeContext ctx = new TreeContext(new RedBlackStrategy<>());
        for (int i = 1; i <= 20; i++) {
            ctx.add(i);
            if (i % 5 == 0) {
                TreeEcology eco = new TreeEcology(ctx);
                System.out.printf("n=%2d  r/K=%+.3f  strategy=%s  h=%d%n",
                        ctx.getSize(),
                        eco.rKScore(),
                        ctx.getTree().getStrategy().getClass().getSimpleName(),
                        ctx.getTree().getRoot().getHeight());
            }
        }
    }

    public static void main(String[] args) {
        demoOrderStatistics();
        demoIntervalTree();
        demoEcology();
        demoAdaptiveMorph();
    }
}
