# ADR-148 — The lab bench, entered whole — and the two entry paths agree

**Status:** accepted · **Date:** 2026-09-06 · **The third page taken whole: the interactive lab's workbench goes 7 → 40 of 40 fields, 74 → 202 confirmed expectations. It carries eleven instruments and a tablet-friendly chip adder over every count box, and nothing had ever pressed the chips. The kit reaches 312 of 518 fields (60%) and 23 blind figures**

## 1. Why this page

`ecology-lab.html` was ADR-144's third-largest gap at **7 of 40 fields**, and the
seven were the seeded terrarium and four defaults. The workbench underneath —
diversity, β diversity, mark–recapture, quadrat dispersion, Hardy–Weinberg, a
Punnett builder with a χ² fit, a dichotomous key, Newick trees, a seeded
flashcard drill, six theory models and an `.eco` round trip — was entered by
nothing, and every one of those is a published formula the page computes itself.

It also carried **three figures no task could read** (ADR-146): `o-hot`, `o-set`
and `o-cap`, the terrarium's three slider readouts. Renamed to the convention,
they are held now, and the page is the second to reach **zero blind figures**.

## 2. The two entry paths agree

Every count box on this page has a **chip adder** over it — a name field, a
count field, an Add button, and ± chips per species — because that is the entry
a gloved thumb on a tablet can actually hit. It writes through to the textarea
underneath, and the textarea writes back to the chips.

Nothing had ever pressed it.

The task now holds both halves as one claim: adding **heron 5** through the chip
adder writes `heron 5` into the textarea *and* moves the figures to six species,
H′ 1.33, J′ 0.75, Chao1 6; typing the old list straight back into the textarea
returns them to five, 1.16 and 5. Site A gains *lily* through its chips, site B
gains *moss* through its own, and site A is retyped as text — three of the six
remaining fields were exactly these two paths and the third box.

## 3. What is held, and what is recomputed

| instrument | held to |
|---|---|
| terrarium | J′ **0.73**, 29.2 effective species, Chao1 **100**; 0.43 at a 95% hot share; 0.88 at a hot set of 20; the island 616/604 at capacity 12 and **342/310** at 32 |
| diversity | 5 species → H′ 1.16, J′ 0.72, 3.2 effective, Chao1 5; six → 1.33, 0.75, 3.8, 6 |
| β diversity | Jaccard **0.5**, Sørensen 0.67, Bray–Curtis **0.31**, sharing 3 of 6 kinds; 0.67 / 0.8 / 0.25 with *lily*; **1 / 1 / 0** when the two sites are made identical |
| mark–recapture | M 120 C 90 R 30 → Lincoln–Petersen **360**, Chapman **354**, 95% CI **268–440**; R = 0 leaves L–P undefined and Chapman at **11,010**; R above min(M, C) is refused |
| quadrats | variance/mean **26.12**, Morisita **3.51**, *clumped*; eight equal quadrats **0** and **0.82**; twelve quadrats 33.72 and 3.4; one quadrat refused |
| Hardy–Weinberg | p **0.543**, q 0.458, χ² **0.22**, expected 294 / 496 / 209, consistent; 400/489/213 → 8.19 and out of equilibrium; 250/500/250 → exactly **0** |
| Punnett | 3 R_ : 1 rr and Mendel's 5474 / 1850 → χ² **0.263** against critical 3.841; incomplete dominance → 1 : 2 : 1; the dihybrid → 9 : 3 : 3 : 1 and 315/108/101/32 → **0.47** against 7.815; a test cross → 2 R_ : 2 rr |
| the key | three couplets walked yes → no → yes to *butterfly or moth*, with the trail `1: yes → 2: no → 3: yes` kept |
| trees | seven taxa at depth 6; `(A,(B,(C,D)))` four and four |
| the drill | seed 7 deals **detritivore** first, seed 0 deals **decomposer**, flipped it deals the answer side |
| theory | the habitat chip carries area 2.5 · temp 1.4 · wind 0.6 · distance 3 |
| `.eco` | the import **loads** — the field counts become the imported pond's three species |

Every number in that table is printed by a Python oracle that ports the page's
own arithmetic. Nothing is remembered.

## 4. Three things this found

**The oracle's formatter was wrong, and quietly.** The page prints through
`Number(x).toLocaleString("en-US", {maximumFractionDigits: d})`, which rounds
**half away from zero** and does so on the **shortest round-trip decimal** of the
double, not on the double itself. Python's `round()` is half-to-even on the
binary value and disagreed on both counts: Hardy–Weinberg's p came out 0.542
against a page showing **0.543**, and 2.675 rounds to 2.68 on the page and 2.67
in Python. The port is `Decimal(repr(x))` with `ROUND_HALF_UP`. A formatter that
is wrong on ties is wrong on roughly one figure in a thousand, which is exactly
often enough to be dismissed as a rounding quibble and never fixed.

**An occurrence index is not an address.** `read-report` distinguishes repeated
figure labels with `#2`, and this page prints *evenness J′* three times. Writing
`output.figures.evenness J′ #2` made the task depend on how many tiles happen to
sit above it — ADR-145's lesson about unnamed controls, one layer up. The task
addresses figures by the box that owns them instead:
`output.by.wb-field-out.evenness J′`.

**Seed 0 is a seed.** The page's own comment records that `+value || 42` once
sent seed 0 silently back to the default order, "a perfectly ordinary thing for a
student to ask for". The fix was never held. It is now: the drill at seed 7 deals
*detritivore* first and at seed 0 deals *decomposer*, both recomputed by the
`mulberry32` port running the same Fisher–Yates.

## 5. Two things the entry broke, and both were the instrument

**A control the entry left focused could not be asked what focus looks like.**
The chip adder returns focus to its count box after Add, so the entered lab
ended with `site B count` focused — and `audit_focus` then reported *no visible
focus* on a page whose ring is fine, because the "unfocused" reading it compared
against was taken while the control was focused. Nothing on the page was wrong;
the instrument could not ask the question. The probe now blurs each control
before reading its resting state, switches transitions off for the length of the
probe (a ring mid-transition answers with a value from a hundred milliseconds
ago — ADR-131's lesson, one layer down), and **puts focus back where the page had
it**, because the audits run one after another on the same tab and a probe that
leaves focus moved changes what the next one measures. `verify_audit_states` **70** (+3); `mutate_audit_states` **47** (+2), 47 killed.

**A check was asserting something other than what it said.** `verify_tasks`
compared the tasks that entered with no destructive rung against *the tasks that
declare a policy at all* — the same set only for as long as every policy in the
kit went all the way to DESTRUCTIVE. This task is the first to declare one that
stops short: it opens SENSITIVE_READ, DRAFT and MUTATE and says why it needs no
more, and the arithmetic then counted it on both sides. The sentence the check
prints always said "the tasks that did NOT declare **it**"; the set it used did
not. `verify_tasks` **285**.

## 6. Refusals, in the page's own words

Nine, each entered on purpose and each held to the sentence the page prints:
`R ≤ min(M, C)`; two quadrats minimum; a key line without its two pipes; a key
that points at itself (*this key loops*); an unbalanced Newick string; a drill
with no cards; `K` = 0; `K₁` = 0; a negative distance; negative steps.

## 7. The numbers

    ecology-lab.html    7 → 40 of 40 fields   (74 → 202 confirmed expectations)
    the kit           279 → 312 of 518 fields  (54% → 60%)
    figures readable  230 → 233 of 256          (26 → 23 blind, on 8 pages)

## 8. Held

- **A Python port catches a change in the page, not a shared misunderstanding of
  the method.** ADR-133's binding — the shipped protocol run through the Java
  science engine and held against this page's own session — is the check that
  covers that, and it is unchanged.
- **`releve.html` 7 of 42 and `experiment-guide.html` 16 of 52 are the next two**,
  and are now the largest gaps left.
- **A page that is entered more deeply is measured in more states**, and both
  faults above appeared only because the entry got further than it used to. That
  is the coupling `entry_reach` and `audit_readable` already have, and it cuts
  the useful way: every page taken whole is an audit taken further.
- The chip adder is held to agreeing with the textarea for **counts**. Its ±
  buttons and its ✕ are pressed by no task yet; they are controls, not fields,
  so `entry_reach` reads 40 of 40 with them untouched.
