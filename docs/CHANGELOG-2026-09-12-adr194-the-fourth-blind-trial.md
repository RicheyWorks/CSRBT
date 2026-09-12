# 2026-09-12 — ADR-194: the fourth blind trial

**The last of the seven slices of `docs/PLAN-operator-api-2026-09-11.md`, and
the only one that measures the other six. Same four pages, same goals, same
grader, same floors — through the door ADR-188 to ADR-193 built.**

## What it measured

|  | third trial | fourth trial |
|---|---|---|
| outcomes reached | 53 / 112 | **82 / 112** |
| claims confirmed | 169 / 260 | **213 / 260** |
| calls, whole trial | 996 | **398** |
| attempts | 21 | **4** — one each |

Nothing about the grader, the tasks or the pages changed between them. Not one
goal sentence was rewritten.

## Added

- `tools/traces/blind4/` — four traces, gzipped as the server wrote them, with
  `PROVENANCE.md`: the conditions, what each operator was handed, the
  comparison table, and what the trial found.
- `verify_tasks` section F4 (308 → 331): the four traces against the third
  trial's floors and the fourth's own; every page reached more outcomes and
  confirmed more claims in fewer calls; graded as a route all four are still
  FAIL.
- `verify_mcp` 89 → 93: a session opened with the fourth rung named lists what
  the supervised three do not; a rung off the ladder is refused by name; the
  default is unchanged.
- `mutate_contract` 56 → 60 / 60.

## Changed

- `tools/blind_console.py`: `--rungs A,B,C`, defaulting to
  `SENSITIVE_READ,DRAFT,MUTATE`. **The trial found this defect in itself**: two
  of the four briefs declare `DESTRUCTIVE` (ADR-142) and print it (ADR-193),
  and the console hard-coded the supervised three — so two operators were
  stopped at the goal's last step by the trial harness rather than by the door.
  Both diagnosed it precisely. The two affected scores are lower bounds.

## Filed, not fixed

Six page defects, two of them found for the second time (the breeding bench's
linear "after 10 generations" under a *compounding* caption; the collection
sheet's entity-truncated reagent labels). New: `popOut`'s citation label in the
mating-system slot, roguing coupled to the Selection card's population, a stale
voucher label, silent no-op exports with nothing to export, an `.eco` header
naming an unscored trait, and plant-button addresses that move with their
labels.

And the gap two operators reported independently: **the diff is
control-shaped**. A `read-report`'s figures and boxes have no `since`, so an
operator watching a computed figure must re-read the whole report.
