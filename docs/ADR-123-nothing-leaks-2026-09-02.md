# ADR-123 — Nothing leaks: the process, restarted forty times

**Status:** accepted · **Date:** 2026-09-02 · **Gives the harness a leak detector, and the robot a cross-check that a target's process ends a round where it began**

## 1. A verdict with no clock

Every harness suite so far has asked whether a target does the right thing
*once*. The organism's committed walk restarts it twenty-one times and
checks every read against the mirror after each; nothing checks whether
the process that answered the twenty-first was still the process that
answered the first. A tail thread that survives `close()`, a socket that
outlives its server, a channel nobody closes — none of these change a read.
They change a count, and nobody was reading it.

"Verify that everything works" includes "keeps working". The ninth pass
found the organism leaking on the *error* path (W-1: a partial build left
every earlier resource open). The clean path had never been measured.

## 2. The decision

Both JVM consoles gain a `jvm` verb and a `jvm` field in every snapshot:
live threads (by name, on the organism), open file descriptors where the
platform's MXBean has a count (−1 elsewhere), heap in use. The organism and
lab plugins publish it as a 35th and a 9th action, `READ`.

**The robot** (`harness_walk.py`) cross-checks it every round for both
targets: round one is the baseline; a thread not there in round one is a
broken invariant, *by name*; descriptors may rise by the segments the store
rolled since round one (a cached reader channel each) plus a little slack,
and no more. `verify_walk` section **H** pins the checker on synthetic
counts; `mutate_walk` breaks it three ways (a new thread never reported,
descriptors unbounded, the baseline retaken every round) — **24 killed, 0
survived, 2 equivalent**.

**`verify_organism` section Y** is the drill: forty restarts — clean, cold,
cold under a replica lag, clean under a chaos plan, cycling — with a write
between each and a read into every fifth segment, then a final clean
restart and a quiesce. The live threads must be the same set by name;
descriptors up by at most the segments those restarts rolled; a `compact`
must give them back; every record equals the mirror (301 → **315**).
`HarnessConsoleTest` and `LabConsoleTest` carry the same shape in-process
(ten restarts; twenty controller runs): WholeHog 21, csrbt-experimental
**257**.

## 3. What the first probe read

Forty alternating restarts, a put between each:

    baseline: threads 16, fds 41
    after 10: threads 16, fds 51
    after 20: threads 16, fds 61
    after 40: threads 16, fds 81

Threads flat, by name. Descriptors **+1 per restart** — and it was not a
leak. `/proc/<pid>/fd` showed one open `seg-NNNNNNNN.log` per cold restart:
every cold open rolls a new active segment (the abandoned one is never
appended to again), the put after it lands in that segment, and the read of
that record earns the segment a cached reader channel in `SegmentLog`.
Clean restarts roll a segment too, but an empty one is never read and never
earns a reader. A `compact` merged the closed segments and the count fell
from 49 to 41 in the same session.

So the bound the checks enforce is the fact the probe found: descriptors
rise with segments and fall with compaction, and on a `STATIC` tier — which
never auto-compacts — a long-running organism under repeated crashes holds
one descriptor per segment until somebody compacts. The description of the
`jvm` action says so. A count that rose *without* a segment to explain it
would be the leak; none did.

## 4. A tool missed by seed-luck

Adding a 35th tool changed the shuffle of the suite's short 2×2 organism
walk, and `overlap` was refused all four times it was tried — `lo` and
`hi` are formed from their own bounds independently, so half of all pairs
have `lo > hi`, and four coin tosses come up tails one time in sixteen. The
manifest could not say "lo below hi"; a schema cannot. The snapshot can:
the organism now publishes a scoped pool per bound pair (`range`,
`count-range`, `overlap`) in which every low value is below every high
one, and the robot, which reads scoped pools first, forms a valid pair
every time. `verify_organism` pins the pools and that their narrowest pair
is accepted (315 → **317**); `mutate_organism` breaks them (31 killed).
Refusals remain where the target's own rules make them.

## 5. Held

- Heap is reported, not bounded: a JVM's used heap between collections is
  noise, and a bound on it would be a check that fails on Tuesdays. A
  leak that shows only in heap needs a forced collection and a floor, which
  is a different instrument.
- The page target has no process of its own to read; Playwright's browser
  is the harness's, and its leaks are the harness's problem, not the page's.
- Sockets in flight (the wire client per `via: wire` call, the replication
  pair per restart) are the slack. A slack of eight is generous for a
  loopback; it is on the record, and the walk's own numbers will tighten it
  if they can.
