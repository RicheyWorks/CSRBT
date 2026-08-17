package io.github.richeyworks.csrbt.ensemble;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CancellationException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.RejectedExecutionException;
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
 *
 * <p><b>Shutdown can never park a fan-out</b> (sixth-pass audit finding 10). A {@code shutdown()}
 * racing an in-flight fan-out used to leave the queued {@code FutureTask}s NEW forever — drained
 * out of the queue by {@code shutdownNow()}, never run, never cancelled — so the collecting
 * {@code Future.get} blocked permanently <em>while the ensemble held its write lock</em>. Both
 * halves of that race now end in a failed {@link MemberExecutor.Outcome} instead: a drained task is
 * cancelled (its {@code get} throws immediately), and a submission that arrives after the shutdown
 * is rejected and reported for the members it never reached. Either way the caller sees one outcome
 * per member and quarantines the ones that missed the write, so a shutdown mid-write degrades into
 * the ordinary write-failure path rather than a hang or a silently divergent member.</p>
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
        RejectedExecutionException rejected = null;
        for (int i = 1; i < n && rejected == null; i++) {
            final EnsembleMember<K> m = members.get(i);
            try {
                futures.add(pool.submit(() -> applyOne(m, op)));
            } catch (RejectedExecutionException e) {
                // shutdown() beat this fan-out to the pool: this member and every member after
                // it never receive the write. Reported as failures below so the caller
                // quarantines them (E-D) instead of leaving them ACTIVE and silently behind.
                rejected = e;
            }
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
                } catch (CancellationException e) {
                    // shutdown() drained this task out of the queue before any worker ran it
                    // (finding 10). Without the cancel in shutdown() the task would sit NEW
                    // forever and this get() would never return — the deadlock. The member did
                    // not receive the write, so it is a failure like any other.
                    outcomes.add(Outcome.failed(e));
                    break;
                } catch (java.util.concurrent.ExecutionException e) {
                    // applyOne never throws, so this is an executor-level failure; surface it as the member's.
                    outcomes.add(Outcome.failed(e.getCause() != null ? e.getCause() : e));
                    break;
                }
            }
        }
        // One outcome per member, in input order: the tail this fan-out could not submit.
        while (outcomes.size() < n) outcomes.add(Outcome.failed(rejected));
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

    /**
     * Stop the pool and <b>cancel</b> whatever {@code shutdownNow()} drains out of the queue.
     * The drained {@code Runnable}s are the very {@code FutureTask}s a concurrent {@link #apply}
     * is waiting on; they will never run, so cancelling them is what turns that wait into an
     * immediate {@link CancellationException} instead of a permanent park (finding 10). Idempotent.
     */
    @Override
    public void shutdown() {
        for (Runnable pending : pool.shutdownNow()) {
            if (pending instanceof Future<?> f) f.cancel(false);
        }
    }

    @Override
    public String toString() { return "ParallelMemberExecutor[threads=" + threads + "]"; }
}
