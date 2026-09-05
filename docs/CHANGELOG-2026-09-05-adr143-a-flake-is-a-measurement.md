# Changelog — 2026-09-05 — ADR-143: a flake is a measurement nobody took

Three of the six full runs it took to close ADR-141 failed on checks that
passed every time they were run alone. Both were re-rolled. This slice measures
them instead.

## New — `tools/contend.py`

Runs a suite N times while **other real suites of this kit** run beside it
(restarted for as long as the target runs), plus optional busy-loop burners, and
records the rate with its conditions.

```
python3 tools/contend.py --suite verify_organism --beside verify_tie_render --runs 10
python3 tools/contend.py --sweep        # the standing set
python3 tools/contend.py --report       # the ledger, no runs
```

- The ledger key is the target **and** its conditions — `verify_organism beside
  verify_tie_render +1cpu`. The first draft keyed by target alone and reset the
  count when conditions changed, throwing away a real measurement every time a
  second load was tried.
- A failing run's **own output** is kept (last 40 lines) and printed by
  `--report`: a failure that takes twenty minutes to reproduce must not be
  reproduced twice because nobody kept the output.
- Zero failures is reported as an **upper bound**, with the run count beside it.
- Exits non-zero when a run failed: the kit's own runs are under load.

**First readings** (`tools/contention_ledger.json`):

```
audit_contrast  beside verify_tasks            3 run(s), 0 failed
audit_targets   beside verify_tasks            3 run(s), 0 failed
verify_contract beside verify_tie_render       4 run(s), 0 failed
verify_organism beside verify_tasks            6 run(s), 0 failed
verify_organism beside verify_tie_render      16 run(s), 1 failed
    x1  two consecutive physicals are identical through the gateway
verify_organism beside verify_tie_render +1cpu 16 run(s), 0 failed
verify_report   beside verify_tie_render       4 run(s), 0 failed
```

The organism's physicals **reproduced deliberately for the first time**, on the
third run of the first reading — beside the browser suite, not beside the one
that starts a second JVM. The cause is still unidentified; the instrument is
what closes that gap, since the next occurrence carries the differing meter
lines into the ledger.

## `tools/audit_states.py` — the look repeats

ADR-140 gave `coverage()` one extra look after the walk. `audit_targets` still
lost one control in one of six runs: the extra look is itself a probe, and a
probe can be early. The look now repeats up to three times and **stops as soon
as a look finds nothing new**, and `lateLooks` records how many controls each
look was the first to see. `audit_targets` prints `LATE (found on look 2)` when
a later look caught something — a page whose measurement depended on what else
the machine was doing says so on its own row.

## ...and the family is narrowed, not closed

This slice's own closing `run_all -j 2` produced a **third** instance:
`audit_contrast`, one control never exposed, clean standing alone and clean in
three runs under load afterwards. So two more changes make the next occurrence
readable rather than claim there will not be one:

- `audit_contrast` and `audit_focus` print `LATE  n control(s) only a later look
  saw` on the page's own row.
- `audit_contrast` prints the never-exposed control's **name in the summary**.
  `run_all` shows a failing job's tail, so three times now the kit's report of
  this fault has been `never exposed, unmeasured: 1` with the name cut off two
  hundred lines above.
- `audit_contrast` joins the standing set.

## The board — `tools/harness_board.py`

- New tile: **clean under load**, `5 / 6` readings, with the run count and the
  failures beside it.
- `mutate_contend` joins the runner table.

## Verification

- `verify_contend` **35**, new. Both score formats; a crash counted as a failure
  even with no `FAIL` line; the check text kept; a co-tenant restarted when it
  exits and one nobody has dropped rather than "started"; `stop()` leaving
  nothing behind; the ledger's add-don't-replace; a second load landing under
  its own key with the first reading intact; the last failure's output kept and
  not erased by a later pass; `--no-ledger` writing nothing; a failure under
  load exiting non-zero.
- `mutate_contend` **18**, 18 killed, 0 survived.
- `verify_audit_states` **62** (+4): a control revealed *between two looks of one
  `coverage()` call* is counted, the run says a later look found it, a settled
  page stops after the second look, and `looks=1` is exactly the old behaviour.
  The fixture triggers the reveal from the measurement itself rather than a
  timer.
- `mutate_audit_states` **42** (+3), 42 killed, 0 survived, 2 equivalent.

## Docs

`docs/ADR-143-a-flake-is-a-measurement-2026-09-05.md`; `docs/AI_HARNESS.md`.
