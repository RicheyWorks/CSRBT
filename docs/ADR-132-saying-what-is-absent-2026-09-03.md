# ADR-132 — Saying what is absent: `excludes`, `not-in`, and two claims about one box

**Status:** accepted · **Date:** 2026-09-03 · **The task grammar can now assert that something is *not* there. Six expectations that had been guessing at a replacement are now the claim they were reaching for, an unknown op is the task's defect rather than a finding about the kit, and one box can carry two claims.**

## 1. What ADR-128 left

The grammar had `== != > >= < <= in contains exists` and no way to say *does
not contain*. ADR-128 held it deliberately: "a task that wants to say a
sentence is absent says what replaced it. Added when a task needs it, with its
mutant." Several tasks need it now, and all of them are the same shape — a
**refusal**. A page that refuses an entry has two obligations: say why, and
stop answering. The grammar could hold the first and not the second, so every
refusal in the kit was held by its words alone.

Saying what replaced it is not the same claim. It happens to be true, which is
not the same as being what you meant.

## 2. The decision

### `excludes` and `not-in`

`excludes` is `value not in got` over a string, a list or a dict.
`not-in` is its mirror — `got` is not one of a set.

The important half is what `excludes` does **not** do: it is not satisfied by a
missing path. A path the response does not carry is REFUTED, the same as every
other op — because otherwise a typo in a path would read as proof of absence,
which is the exact failure the op was added to stop. A task must name a box
that exists and say the string is not in it.

### An unknown op is the task's defect

The grader used to fall through to `ok = False` on an op it did not recognise:
a typo in a task file printed as a REFUTED expectation, which is a finding
about the kit. That is ADR-125's rule — *a bad reference is the task's DEFECT,
never a finding* — broken by the grader itself. An unrecognised op now raises
`TaskDefect` and the message names the ops that exist.

Writing that check found a second one: there were **two** op tables, the
loader's and the grader's, and a task file could be accepted at load and
rejected at grade. There is now one.

### Two claims about one box

Expectations are keyed by path, so a box could carry exactly one claim — and
the interesting pair is *"it says the refusal"* **and** *"it no longer says the
answer"*, which are two claims about the same box. A trailing `#n` with no
space before it is a label, stripped before the path is followed:
`output.boxes.selOut` and `output.boxes.selOut#2` are the same box, graded and
reported separately.

The space matters, and the suite pins it: `read-report`'s own duplicate labels
are written `doubling time #2`, *with* a space, and are real path segments.

### The six claims

Each was written from what the tool said, not from what the page looked like it
would say — and the runner refuted the first draft of one of them, which is the
whole argument for the rule.

| task | box | the claim underneath |
|---|---|---|
| plant key, no match | `kres` | excludes `3/3 characters` — **no** family is a complete match, which is what "nothing matches" means |
| fungal key, Russula | `fkout` | excludes `Lactarius` — the genus a reader confuses it with is not on the list |
| cp key, pitchers | `kRes` | excludes `Nepenthes` — the Old World pitcher did not survive the filter |
| experiment guide, refused import | `eco-out` | excludes `IMG_0431` — nothing of a refused file reaches the protocol |
| breeding bench, too many kept | `selOut` | excludes `intensity i` — the refusal *stops computing*, rather than leaving the previous answer standing |
| breeding bench, one replicate | `triOut` | excludes `MSE` and `CV` — same claim, other box |

The first draft of the last one asserted the box excluded `LSD`, and the runner
refuted it: the refusal *explains* that there is no LSD, so the word is in the
box. The claim underneath was about the figures, not the word. A guess that
looks right is what the oracle rule exists to catch, and it caught one here.

## 3. Verification

`verify_tasks` **185** (+9): `excludes` confirms when the value is absent from a
string or a list, is refuted when it is there, and is refuted on a path the
response does not carry; `not-in` reads the other way; a typo'd op is a
`TaskDefect` whose message names the known ops; the op table is one table; a
trailing `#n` labels a second claim about one path, and a ` #2` with a space is
a real path segment.

`mutate_tasks` **31** (+7): `excludes` satisfied by a missing path, reading the
wrong way round, always true; `not-in` inverted; the two op tables restored; a
`#n` label treated as part of the path; and a real ` #2` segment stripped as if
it were a label.

Ledger: **43 page tasks, 43 held** (the canary refuted, as written).

    verify_tasks 185 / 185 · mutate_tasks 31 killed, 0 survived
    kit  77 / 77 jobs, 5,544 / 5,544 checks

## 4. Held

- `excludes` over a *number* is not a thing: it is a containment op, and a task
  that wants "not 5" says `{"op": "!=", "value": 5}`.
- Timing is still not an expectation (ADR-125).
- A task is still single-target and sequential (ADR-125) — next slice.
