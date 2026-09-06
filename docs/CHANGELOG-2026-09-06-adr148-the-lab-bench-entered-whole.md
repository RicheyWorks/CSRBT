# Changelog — 2026-09-06 — ADR-148: the lab bench, entered whole

The third page taken whole, and the first one whose entry layer had a second
path nothing had ever pressed.

## The task — `tools/tasks/page-ecology-lab-science.json`

22 steps → **129**. The terrarium, diversity, β diversity, mark–recapture,
quadrat dispersion, Hardy–Weinberg, the Punnett builder and its χ² fit, a
dichotomous key, Newick trees, a seeded flashcard drill, the theory bench and
the `.eco` round trip.

```
ecology-lab.html    7 → 40 of 40 fields   (74 → 202 confirmed expectations)
the kit           279 → 312 of 518 fields  (54% → 60%)
figures readable  230 → 233 of 256          (26 → 23 blind, on 8 pages)
```

## The two entry paths agree

Every count box has a **chip adder** over it — name, count, Add, and ± chips per
species — because that is the entry a gloved thumb on a tablet can hit. It
writes through to the textarea underneath, and the textarea writes back.

Nothing had ever pressed it. Now one claim holds both halves: adding **heron 5**
through the chips writes `heron 5` into the textarea *and* moves the figures to
six species, H′ 1.33, J′ 0.75, Chao1 6 — and typing the old list back into the
textarea returns them. Site A gains *lily* through its chips, site B gains
*moss* through its own, site A is retyped as text.

## Three things this found

**The oracle's formatter was wrong on ties.** The page prints through
`toLocaleString`, which rounds **half away from zero** on the **shortest
round-trip decimal** of the double. Python's `round()` is half-to-even on the
binary value: Hardy–Weinberg's p read 0.542 against a page showing **0.543**, and
2.675 is 2.68 on the page and 2.67 in Python. The port is `Decimal(repr(x))` with
`ROUND_HALF_UP`.

**An occurrence index is not an address.** This page prints *evenness J′* three
times, and `read-report` distinguishes them with `#2`. Writing
`output.figures.evenness J′ #2` makes a task depend on how many tiles sit above
it — ADR-145's lesson one layer up. Figures are addressed by the box that owns
them: `output.by.wb-field-out.evenness J′`.

**Seed 0 is a seed.** The page's own comment records that `+value || 42` once
sent seed 0 back to the default order. The fix was never held. The drill at seed
7 deals *detritivore* first and at seed 0 *decomposer*, both recomputed by the
`mulberry32` port running the same Fisher–Yates.

## Two things the entry broke, and both were the instrument

**`tools/audit_focus.py` — a control the entry left focused.** The chip adder
returns focus to its count box after Add, so the entered lab ended with
`site B count` focused, and the probe reported *no visible focus* on a page whose
ring is fine: the "unfocused" reading it compared against was taken while the
control was focused. The probe now blurs each control before reading its resting
state, switches transitions off for its own duration (a ring mid-transition
answers with a value from a hundred milliseconds ago), and puts focus back where
the page had it — the audits share a tab, and a probe that leaves focus moved
changes what the next one measures. `verify_audit_states` **70** (+3).

**`tools/verify/verify_tasks.py` — a check asserting something other than what
it said.** It compared the tasks that entered with no destructive rung against
*the tasks that declare a policy at all*, which was the same set only while every
policy in the kit went all the way to DESTRUCTIVE. This task is the first to
declare one that stops short, and the arithmetic counted it on both sides. Now
compared against the tasks that declare **DESTRUCTIVE**. `verify_tasks` **285**.

## Refusals, held in the page's own words

Nine, each entered on purpose: `R ≤ min(M, C)`; two quadrats minimum; a key line
without its two pipes; a key that points at itself (*this key loops*); an
unbalanced Newick string; a drill with no cards; `K` = 0; `K₁` = 0; a negative
distance; negative steps.

## `docs/ecology-lab.html`

The terrarium's three slider readouts were figures no task could read (ADR-146).
Renamed to the convention and held:

| was | now |
|---|---|
| `o-hot` | `o-hotOut` |
| `o-set` | `o-setOut` |
| `o-cap` | `o-capOut` |

`verify_eco` **138**, unchanged in count. ecology-lab is the second page in the
kit with **zero** blind figures.

## Docs

`docs/ADR-148-the-lab-bench-entered-whole-2026-09-06.md`; `docs/AI_HARNESS.md`.
