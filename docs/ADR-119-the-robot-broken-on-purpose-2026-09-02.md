# ADR-119 — The robot, broken on purpose

**Status:** accepted · **Date:** 2026-09-02 · **Applies the kit's mutation rule to the instrument every "operable from the manifest" claim rests on**

## 1. An instrument nobody had broken

`tools/harness_walk.py` is the robot: since ADR-114 it is what shows that a
target can be operated from its manifest alone, and since ADR-117 it walks
every target — 33 organism actions, 8 lab actions, 15 page actions, the
accounting identity `commands == driven + refused + declined + chaos +
failed`, the coverage floor, the cross-checks. Every one of those claims is
a claim the robot makes about a target.

The kit's rule since ADR-041 is that a suite is believed only after the
thing it guards has been broken on purpose and the suite required to
notice. Five harness suites had mutant runners; the robot's had none. Its
suite (`verify_walk`) watched it walk targets that mostly succeed, and a
walker that filed every refusal as driven, or never raised when the target
went away, or read the argument pools once and never again, would have
passed every one of those walks. The instrument was unmeasured.

Breaking it against the organism is the wrong way to measure it: a JVM per
walk, and which bucket a call lands in depends on what arguments a seed
happened to form. A mutant that misfiles one bucket would show up as a
count that is *sometimes* wrong.

## 2. The decision: a target built to be walked

`tools/harness_plugin_fixture.py` is `csrbt-fixture`, the fourth plugin,
served only by `--target fixture` and listed by no production manifest. It
holds no data and touches no disk. Every one of its eleven actions lands in
a **known bucket, every time**:

| action | risk | it always … | bucket |
|---|---|---|---|
| `ok` | READ | succeeds | driven |
| `refuse` | READ | raises `invalid_argument` | refused |
| `decline` | NAVIGATE | answers `ok:false` with no code | declined |
| `crash` | MUTATE | raises naming a `Crash` while the snapshot says a plan is armed | chaos |
| `boom` | MUTATE | raises with no `Crash` in the message | failed |
| `pooled` | DRAFT | accepts only the slot the *latest* snapshot publishes in `pooled.slot`, and rotates it on every call | driven — only by a walker that re-reads every response's pools |
| `empty-pool` | DRAFT | publishes its scoped pool empty and refuses whatever it is handed | unreachable |
| `reached` | DRAFT | publishes its scoped pool empty too, but accepts the schema's example | driven — and must **not** be called unreachable |
| `unformable` | READ | takes a string with no enum and no examples | unschemable |
| `array` | DRAFT | records the lengths of the arrays it is handed | driven |
| `broken` | MUTATE | flips the snapshot's `consistent` flag | driven; the cross-check reports the flag |
| `die` | DESTRUCTIVE (only with `CSRBT_FIXTURE_DIE=1`) | goes away: every later execute is `unavailable` | an alarm, not a bucket |

A walk of it — 2 rounds × 2 per round — takes a quarter of a second and
every count is pinned exactly: `refuse` is 4 refused and nothing else,
`boom` is 4 failed and nothing else, `pooled` is 4 driven, the totals are
`{driven 20, refused 8, declined 4, chaos 4, failed 4}`, the fixture's own
call counters equal the walk's 40, the cross-check ran both rounds and
reported "not consistent" both times and nothing else, `arrayLengths` starts
with 1, and with the fixture armed to die the walk raises "went away".

`verify_walk` gained section **F** with those checks (49 → 74 in all, with
the price checks of ADR-120), and `CSRBT_WALK_QUICK=1` runs it without the
engine and page walks — sections A, B, D, E and F — in under a second.

## 3. `tools/mutate_walk.py`: 17 mutants, all killed

Each mutant of `harness_walk.py` names the check that must kill it, and the
suite runs in quick mode against a copy of `tools/`:

a refusal filed as driven · a decline filed as failed · chaos never
recognised · any raise under an armed plan taken for chaos · failures not
noted · a scoped pool not preferred · pools not refreshed from each
response · arrays never one item first · an unschemable tool skipped
without being named · a target that went away walked on · the cross-checks
never run · unreachable never reported · unreachable ignoring whether
anything was driven · relevant pools looked up plain, never scoped ·
undriven counting the unreachable and the unschemable · the verdict
ignoring failures · the verdict ignoring unschemable tools.

**Final: 17 killed, 0 survived, 2 recorded equivalent** — "accounted set to
commands instead of summed" (every execute adds one to exactly one row, so
the identity is a tripwire for a bucket added without a row, not a runtime
measurement) and "the plain-pool 70% made 100%" (the fixture publishes only
scoped pools).

## 4. What the fixture found in the robot

Two things the 49 checks over three real targets had not:

- **"One first" was true in the unit check and false in every walk.** The
  generator's array branch draws `1 + tick % 3` items, and the suite pinned
  that with ticks 0, 1, 2. The walk's tick was `round × 100 + i`, so the
  first call to every tool in every walk drew *two* items — a single-file
  input got two files before it got one, and was refused first. The tick is
  now the tool's own call number from zero.
- **A tool whose pool was empty but whose example got through was
  "unreachable".** ADR-117's rule was "pools empty throughout"; the fixture's
  `empty-pool` was driven from its schema example and reported unreachable
  in the same breath. Unreachable now also requires `driven == 0`, and
  `reached` exists to keep it that way.

Neither changed a real target's verdict. Both changed what the verdict
meant.

## 5. Held

- The fixture is not a page: nothing here breaks `page_checks` or the
  Playwright half of the page plugin. `verify_walk` section C still walks
  two real pages for that.
- Mutants of the *plugins* are the other runners' job; this one breaks the
  robot only.
