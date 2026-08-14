package io.github.richeyworks.csrbt.ensemble;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;

/**
 * ParallelMemberExecutor — ADR-003 E5's parallel write fan-out. Members share no mutable state, so
 * one logical write can be applied to all K members concurrently; the caller (the ensemble facade)
 * still holds the single writer lock for the whole fan-out, so the logical set stays linearizable —
 * parallelism is <em>within</em> a write, never <em>between</em> writes.
 *
 * <p>The first member runs on the calling thread (no handoff for the common K=2 case's primary);
 * the rest are submitted to a fixed daemon pool. {@code Future.get} establishes the happens-before
 * edge back to the caller, and the writer lock's acquire/release orders one write's mutations
 * before the next — so a member mutated by pool thread A this write is safely mutated by pool
 * thread B the next, with no member-level locking.</p>
 *
 * <p>A member's throwable is captured in its {@link MemberExecutor.Outcome}; it never aborts the
 * other members' writes. Threads are daemons, so {@link #shutdown()} is best practice, not a
 * leak-prevention requirement.</p>
 */
public final class ParallelMemberExecutor implements MemberExecutor {

    private static final AtomicInteger POOL_SEQ = new AtomicInteger();

    private final ExecutorService pool;
    private final int threads;

    /** A pool of {@code threads} daemon workers (callers typically size this min(K-1, cores)). */
    public ParallelMemberExecutor(int threads) {
        if (threads < 1) throw new IllegalArgumentException("threads must be >= 1: " + threads);
        this.threads = threads;
        final int poolId = POOL_SEQ.incrementAndGet();
        final AtomicInteger seq = new AtomicInteger();
        ThreadFactory daemons = r -> {
            Thread t = new Thread(r, "ensemble-fanout-" + poolId + "-" + seq.incrementAndGet());
            t.setDaemon(true);
            return t;
        };
        this.pool = Executors.newFixedThreadPool(threads, daemons);
    }

    @Override
    public <K> List<Outcome> apply(List<EnsembleMember<K>> members, Function<EnsembleMember<K>, Boolean> op) {
        int n = members.size();
        if (n == 1) {
            List<Outcome> one = new ArrayList<>(1);
            one.add(applyOne(members.get(0), op));
            return one;
        }

        // Submit members 1..n-1 to the pool, run member 0 here, then collect.
        List<Future<Outcome>> futures = new ArrayList<>(n - 1);
        for (int i = 1; i < n; i++) {
            final EnsembleMember<K> m = members.get(i);
            futures.add(pool.submit(() -> applyOne(m, op)));
        }
        Outcome first = applyOne(members.get(0), op);

        List<Outcome> outcomes = new ArrayList<>(n);
        outcomes.add(first);
        boolean interrupted = false;
        for (Future<Outcome> f : futures) {
            while (true) {
                try {
                    outcomes.add(f.get());
                    break;
                } catch (InterruptedException e) {
                    // A submitted task keeps running and mutating its member whether we
                    // wait or not — throwing here abandoned the remaining futures, so the
                    // write was reported failed while an unknown subset of members had
                    // applied it, all still ACTIVE (the silent-divergence class E-D closed
                    // for throwing members). Finish collecting uninterruptibly so the
                    // caller's quarantine bookkeeping sees every outcome, then restore
                    // the interrupt flag for the caller.
                    interrupted = true;
                } catch (java.util.concurrent.ExecutionException e) {
                    // applyOne never throws, so this is an executor-level failure; surface it as the member's.
                    outcomes.add(Outcome.failed(e.getCause() != null ? e.getCause() : e));
                    break;
                }
            }
        }
        if (interrupted) Thread.currentThread().interrupt();
        return outcomes;
    }

    private static <K> Outcome applyOne(EnsembleMember<K> m, Function<EnsembleMember<K>, Boolean> op) {
        try {
            return Outcome.ok(op.apply(m));
        } catch (Throwable t) {
            return Outcome.failed(t);
        }
    }

    @Override
    public void shutdown() { pool.shutdownNow(); }

    @Override
    public String toString() { return "ParallelMemberExecutor[threads=" + threads + "]"; }
}
