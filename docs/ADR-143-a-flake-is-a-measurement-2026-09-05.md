# ADR-143 — A flake is a measurement nobody took

**Status:** accepted · **Date:** 2026-09-05 · **It took six full runs to close ADR-141, and three of them failed on checks that passed every time they were run alone. Both were called flakes and re-rolled. `tools/contend.py` runs a suite N times while other named suites of this kit run beside it and records the rate WITH its conditions, so "flaky" becomes a number and the failing run's own words are kept. First readings: `verify_organism` fails 1 in 16 beside `verify_tie_render` and 0 in 22 beside anything else; `audit_targets` is 0 in 3 after a second fix to `coverage()`**

## 1. Every number here was taken on an idle machine

5,847 checks, 334 mutants, 42 measured artifacts — every one of them produced
by a suite that was, at the moment it answered, the only thing this container
was seriously doing. That is not the condition the kit runs in. `run_all -j 2`
puts two jobs on two cores, one usually driving a browser and one sometimes a
JVM, and under it:

| | |
|---|---|
| `verify_organism` — *"two consecutive physicals are identical through the gateway"* | failed in 2 of ADR-141's 6 closing runs |
| `audit_targets` — one control *"never measured"* | failed in 1 of 6 |

Both passed every solo run. Both were re-rolled. A re-rolled flake is a
measurement nobody took: it might be a race in the instrument, a race in the
subject, or a claim that is simply false when the machine is busy — three
different bugs with one symptom, and re-running until it is green picks none of
them.

ADR-134 already said the principle for the walk's settle time: *an instrument
whose answer depends on what else is running is not an instrument.* This ADR
measures that dependence instead of asserting it away.

## 2. `tools/contend.py`

    python3 tools/contend.py --suite verify_organism --beside verify_tie_render --runs 10
    python3 tools/contend.py --sweep      # the standing set
    python3 tools/contend.py --report     # the ledger, no runs

The load is **other real suites of this kit**, restarted for as long as the
target runs, plus optional busy-loop burners. Not synthetic sleep and not a
fixed CPU percentage: the condition being reproduced is `run_all -j 2`, whose
co-tenant is always another suite of this kit, and the closest thing to that
condition is that suite.

Three decisions worth naming.

**The ledger key is the target AND its conditions** — `verify_organism beside
verify_tie_render +1cpu`. The first draft keyed by target alone and *reset* the
count when the conditions changed, which threw away a real measurement every
time the sweep tried a second load. Two loads are two questions; both answers
are kept, and both say what they were taken under (the ADR-078 rule, applied to
a third ledger).

**A failing run's own words are kept**, bounded to the last 40 lines. The first
draft recorded "1 of 6 failed", which is a rate and not a finding — and a
failure that takes twenty minutes to reproduce must not be reproduced twice
because nobody kept the output. `verify_organism` prints the two physicals'
differing lines when they differ (ADR-142); now that print survives the run
that produced it.

**Zero failures is an upper bound, not a promise.** The report says so, and
prints the run count beside every reading, because "0 failed" over three runs
and "0 failed" over sixty are not the same claim.

## 3. What the first readings say

    audit_contrast  beside verify_tasks           3 run(s), 0 failed
    audit_targets   beside verify_tasks           3 run(s), 0 failed
    verify_contract beside verify_tie_render      4 run(s), 0 failed
    verify_organism beside verify_tasks           6 run(s), 0 failed
    verify_organism beside verify_tie_render     16 run(s), 1 failed
        x1  two consecutive physicals are identical through the gateway
    verify_organism beside verify_tie_render +1cpu   16 run(s), 0 failed
    verify_report   beside verify_tie_render      4 run(s), 0 failed

The organism's physicals **reproduced on the third run of the first reading**,
which is the first time that failure has been produced deliberately. And the
co-tenant that reproduces it is the browser suite, not the one that starts a
second JVM — so whatever moves between two consecutive `report` calls is
sensitive to *this machine being busy*, not to another engine running.

What it is remains unidentified. The physical carries the store's, the wire's,
the journal's and the cache's meters — including `champion=SLRU(2/10,p1)`, an
adaptive choice — and none of a wall-clock delay of 30 s, a batch still
applying, 200 wire writes, 1,200 cache-driving gets, four busy loops, or six
concurrent suites reproduced it in a targeted probe. The instrument is what
closes that gap: the next occurrence carries the differing lines into the
ledger, and this reading says how many runs it takes to expect one (about 16).

## 4. `coverage()` looks again, and says so

ADR-140 gave `coverage()` one extra look after the walk, because a probe can
run before the browser has laid a state out. `audit_targets` still lost exactly
one control in one of six runs afterwards — the same shape one layer down: **the
extra look is itself a probe, and a probe can be early.**

So the look repeats, up to three times, and stops as soon as a look finds
nothing the previous ones had not. It is bounded (the second look usually ends
it), it cannot invent exposure — every id still has to have a box when it is
measured — and it makes the race visible instead of silent: `lateLooks` records
how many controls each look was the *first* to see, and `audit_targets` prints
`LATE (found on look 2)` when a later look caught something. A page whose
measurement depended on what else the machine was doing now says so on its own
row.

**And it did not close the family.** This ADR's own closing `run_all -j 2`
produced a third instance: `audit_contrast`, one control never exposed, clean
standing alone and clean in three runs under load afterwards. The repeat-look
narrows the window; it does not prove there is none. So the honest additions are
the ones that make the next occurrence readable rather than the ones that claim
it will not happen:

- `audit_contrast` and `audit_focus` print **`LATE  n control(s) only a later
  look saw`** on the page's own row, so a run that needed the second or third
  look says so.
- `audit_contrast` prints the never-exposed control's **name in the summary**,
  not only two hundred lines above it. `run_all` shows a failing job's *tail*,
  so three times now the kit's own report of this fault has been
  `never exposed, unmeasured: 1` with the name cut off — a count with no name
  costs a whole re-run to read.
- `audit_contrast` joins the standing set.

The fixture that asserts the repeat-look does not use a timer. A timer long enough to beat
`_settle` would make the suite slow, and a short one is exactly the race the
fixture must not depend on. The control's own `getBoundingClientRect` answers
"no box" the first time it is asked and reveals the element as it does so —
which is what a browser that has not laid the state out yet looks like from
where the probe stands.

## 5. What is now asserted

`verify_contend` **35**, new: the score parsers (both formats the kit uses), a
crash counted as a failure even with no `FAIL` line, the check text kept, a
co-tenant restarted when it exits, a co-tenant nobody has dropped rather than
"started", `stop()` leaving nothing behind, the ledger's add-don't-replace, a
second load landing under its own key with the first reading intact, the
burners as part of the conditions, the last failure's output kept and not erased
by a later pass, `--no-ledger` writing nothing, and a failure under load exiting
non-zero. `mutate_contend` **18**, 18 killed, 0 survived.

`verify_audit_states` **62** (+4) and `mutate_audit_states` **42** (+3), 42
killed, 0 survived, 2 recorded equivalent.

## 6. Held

- **A rate is not a cause.** This ADR ships the measurement and one fix. The
  organism's physicals are still unexplained; what changed is that they are now
  reproducible on demand at about 1 in 16, and the next reproduction keeps its
  own evidence.
- **`audit_targets` and `audit_contrast` at 0 of 3 are upper bounds.** Three
  runs of a four-minute audit is what the sweep can afford; it is recorded as
  three runs, not as fixed. `audit_contrast` failed once in this ADR's own
  closing run *after* the repeat-look was in, so this family is narrowed and
  not closed.
- **The load is one machine's load.** Two cores and 8 GB here; a different
  machine reproduces different races, which is why the ledger records the
  conditions rather than a verdict.
- **`contend.py` cannot score an audit.** `audit_targets` ends with a sentence,
  not `n/m`, so its rows show `-` for the score and pass/fail comes from the
  exit code. That is enough to count failures and not enough to see a shortfall.
- Nothing here runs in `run_all`: a sweep costs 20 minutes and would double the
  kit's run time. It is run deliberately, and its ledger is what the board reads.

## 7. First reading

    contend             7 readings, 6 clean; 52 runs recorded, 1 failed
    kit                 78 / 78 jobs, 5,889 / 5,889 checks; board 5,479 checks, 337 mutants
    verify_organism     1 in 16 beside verify_tie_render, 0 in 22 elsewhere
    coverage            looks up to 3 times, stops early, reports lateLooks
    verify_contend       35 / 35  ·  mutate_contend      18 killed, 0 survived
    verify_audit_states  62 / 62  ·  mutate_audit_states 42 killed, 0 survived, 2 equivalent
