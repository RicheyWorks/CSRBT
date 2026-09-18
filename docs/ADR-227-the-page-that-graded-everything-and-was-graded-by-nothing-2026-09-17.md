# ADR-227 — The page that graded everything and was graded by nothing

**`harness_board.py` renders the one page whose job is to say what the harness
can vouch for, and it was the one subject in the kit with no mutant runner.
`verify_board` held the committed page byte-for-byte to a fresh render and the
summary's arithmetic to the committed ledgers — and the committed ledgers are
green. Every suite `n == of`, no mutant survived, no engine failed, every task
held. A renderer that summed `of` where it should sum `n`, counted every mutant
as killed, or rendered every engine's pill good renders those ledgers to the
same page, and passes every check.**

Measured before anything was changed, on a copy: `"survived": 0` in place of
the sum, re-rendered, verify_board 121/121. `kind = "good"` for every engine,
re-rendered, 121/121. The suite could not fail on a board with nothing wrong
in it, and the board had nothing wrong in it.

## Why the obvious runner would have lied

A runner that copies `tools/`, breaks the renderer and runs `verify_board`
kills every mutant that moves a byte of output — at the byte-for-byte check,
because the committed page no longer matches. Forty mutants, forty kills, and
every one of them proves the output changed and nothing about any rule
(ADR-140's lesson, "killed by the wrong check", one level up). The mutants
that survive the byte check are exactly the ones a renderer can hide behind:
those whose difference is invisible on green ledgers.

## Decision

- **`verify_board` section 9: a fixture ledger set with every gate broken at
  known numbers.** Four suites (one with a hole, one green-but-whole, one
  whole-but-not-green), four walks (one with a failed command, one whose
  identity moved), three tasks (a pass, a canary that must FAIL, a fail) with a
  sighted trace, a blind trace on the same task and a failed blind trace on
  another, a duplicate route, two runners (a survivor; an inconclusive with no
  survivor), three engines (a failure, errors with no failures, no reading),
  contention, entry, readable and delivery rows. `summary()` is held to 39
  exact numbers and `render()` to the bytes each row should produce: every
  gate NOT MET and named, every tile's figure and note, the pill of each
  kind, the order of the engines, the blind trace winning the calls column,
  the dash where there is no stamp. 121 → 204.
- **`tools/mutate_board.py`, 43 mutants, every one RE-RENDERING ITS OWN BOARD
  before the suite runs**, so the byte-for-byte check is satisfied and only a
  rule can kill it. A prose-only mutant (`typed.` → `typed!`) SURVIVES this
  runner, which is the proof that the re-render works and the 43 kills are
  rule kills. 43/43 on the first honest run; each is aimed at the fixture
  check that names its clause.

## What the fixture found in the renderer

Nothing wrong — 43 clauses, 43 held. What it found was in the suite: 80 checks
that could not have failed before this slice existed, on the page that reports
whether anything else can.

## Held

The fixture is one ledger set. A second, with every gate MET but a reading
below its ceiling (a hole and no failure, say), would hold the other half of
each `and`; trigger: the first mutant this runner misses.
