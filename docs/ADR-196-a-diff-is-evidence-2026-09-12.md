# ADR-196 — A diff is evidence: the fifth blind trial, and the grader that could not read one

**Status:** accepted · **Date:** 2026-09-12 · **The fifth blind trial, run to measure ADR-195, and the defect it found in this kit's own instrument. Four fresh operators, the same four science pages, the same goals, the same grader. They read the report **75 times against the fourth trial's 71 and were served 332,828 bytes against 1,214,815** — more reads for a quarter of the bytes, which is ADR-195's claim measured on work nobody scripted. And scored the way the fourth trial was scored, they came out **nineteen outcomes worse**, because `grade_outcomes` holds a claim against what a call answered with, and what those calls answered with was a diff. Nothing was re-run: `apply_diff` and `fold_diffs` were built and the same traces re-read, at **80 of 112 outcomes and 208 of 260 claims** against the fourth's 82 and 213.**

## 1. The measurement ADR-195 was for

|  | fourth trial | fifth trial |
|---|---|---|
| `read-report` calls | 71 | **75** |
| of those, the whole report | 71 | **8** |
| report bytes served | 1,214,815 | **332,828** |
| outcomes reached | 82 / 112 | **80 / 112** |
| claims confirmed | 213 / 260 | **208 / 260** |
| calls | 398 | **408** |

Outcomes and claims are level; what moved is the bytes. That is the honest
shape of this result and it is worth saying plainly: **ADR-195 did not make
operators reach further, it made them pay a quarter as much to reach the same
place.** The breeding bench went from 622,981 bytes over 32 reads to 92,794
over 30. Both goals that declare `DESTRUCTIVE` reached a destructive act this
time, which is the two lower bounds ADR-194 recorded now measured.

## 2. What the trial found, which was in here

Graded as the fourth trial was graded, the fifth scores **63 outcomes and 172
claims**. Nobody operated worse. The fall is proportional, page by page, to
how much each operator used the feature the trial was built to test:

| task | whole-report reads | scored naively | scored by folding |
|---|---|---|---|
| breeding bench | 32 → **2** | 19 → **11** | **19** |
| stand sheet | 28 → **2** | 42 → **32** | **40** |
| pheno tracker | 9 → **2** | 9 → **8** | **9** |
| collection sheet | 2 → **2** | 12 → **12** | **12** |

The collection sheet, which barely used it, did not move at all. That is not a
coincidence; it is the control.

A diff is not a smaller answer. It is the same answer stated differently, and
**everything that reads the document has to be able to read it.** We built
half of that in ADR-191 and the other half was never noticed missing, because
until this trial nothing but a client had ever had to read one.

## 3. `apply_diff`, and the two ways it can fail you

The inverse lives beside the thing it inverts, and returns what it could not
do:

    approximate   the value is the TARGET'S OWN WORDS and fewer of them -- a
                  windowed box. Believe what is there; read nothing into what
                  is not. Supports "the page said X", never "the page did not".
    unrestored    the diff carried no value for this path at all -- a list it
                  only counted, a bucket it capped, a path it called noise, a
                  table left as {"list": 2}.

`fold_diffs` **deletes** the unrestored paths before grading and **keeps** the
approximate ones. That asymmetry is the whole of why this is safe: a truncated
box can cost a claim and cannot manufacture one, while a claim confirmed
against `{"list": 2}` would be a claim confirmed against the diff's own
bookkeeping. An instrument is allowed to be wrong in one direction.

Every trace recorded before today is a diff with no `trimmed` register. Those
are still readable, because the shortening was this module's own doing and its
shapes are exact — a stand-in object, or a string that opens with an ellipsis
or is precisely `BRIEF_CAP` characters and closes with one. Derived, not
guessed; and where the two cannot be told apart the path is called approximate,
which loses a claim rather than inventing one.

## 4. Two defects the trial found in ADR-195 itself

**A box could report a change it could not show.** The breeding-bench operator
was told `boxes/storOut` had moved and handed two *identical* strings, because
the sentence that changed sat past character two hundred; it fell back to
`read-page`, which is the re-read the diff exists to avoid. Both sides are now
windowed on the first character they differ about, with a quarter of the cap
before it for bearings — the same bytes, and the thing the reader asked for in
them.

**A key may contain the path separator, and the pages' do.** The breeding
bench publishes a figure called `pollen / seed parents`, so
`figures/pollen / seed parents` split naively into four segments and rebuilt
as an object nobody has. Joining is lossy; un-joining does not have to be,
because the document is right there — the longest key that matches wins, which
is exact wherever the key exists and falls back to the naive split only for a
path the document does not have yet. This was found by the one check that can
find it: a rebuilt document compared against the whole report the operator
read a moment later, on the two occasions in the trial where an operator did
both without touching the page in between.

## 5. What the operators found in the door

- **The two stamps cannot be told apart.** Three of four passed a snapshot
  stamp to `read-report` or the reverse. Both are `s` and twelve hex digits.
  The door failed toward more and said so, so it cost a re-read rather than a
  wrong answer — but it cost one every time. Filed.
- Two concluded report stamps are "single-use". They are not: the baseline is
  the last report served, which is the same fact from the other side. Neither
  was led to a wrong answer by it.

## 6. What they found in the pages

Three pages' worth, in `tools/traces/blind5/PROVENANCE.md`. Found for the
third time: the bench's linear "after 10 generations" under a *compounding*
caption, and the collection sheet's entity-truncated reagent labels. New: the
stand sheet's exported expansion factor does not reproduce its own per-hectare
column; `associatedTaxa` is emitted and never populated; the bench's sowing
rate reads 100.0 seeds per plant at 0% germination; `Clear trial` raises no
confirmation at all; the pheno tracker's exports name a weight set they did
not use and hardcode `Aa × Aa` against whatever the page concluded.

## What moved

    verify_contract    148 → 161      mutate_contract    65 → 74 / 74
    verify_tasks       329 → 358      mutate_tasks       73 → 80 / 80
    blind traces        16 →  20

    fifth trial   80 / 112 outcomes, 208 / 260 claims, 408 calls
    report bytes  1,214,815 → 332,828 for 75 reads against 71

## Held

- `fold_diffs` is not a thumb on the scale: re-graded through it, the fourth
  trial's numbers are unchanged, because a trace with no diff answers in it
  has nothing to fold. The suite holds that per page.
- `grade_outcomes(..., fold=False)` is kept, so the cost of not folding stays
  a number this suite prints rather than a story about an afternoon.
- The traces are as the server wrote them. The grader was fixed to read them;
  not one session was re-run.
- A claim whose value cannot be hashed is false rather than fatal: grading a
  table row against a mapping used to raise `TypeError` and stop the suite.
