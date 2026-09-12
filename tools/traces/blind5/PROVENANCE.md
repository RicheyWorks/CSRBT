# The fifth blind trial — provenance (ADR-196)

Four operators, the same four science pages as the third and fourth trials,
the same grader, the same floors. What changed between the fourth and this one
is ADR-195: `read-report` carries a stamp and takes a `since`, and
`blind_console` can grant the fourth rung that two of the briefs declare.

Run **2026-09-12**. The traces are gzipped because every response carries a
page snapshot; `gunzip -c <file>` is the trace exactly as the server wrote it.

## The conditions

Four general-purpose subagents, fresh context each, working in
`/tmp/blind5/CSRBT` — a copy of the repository with `tools/tasks/`,
`tools/traces/`, `tools/delivery/`, `tools/push/`, every ledger, the board and
its renderer, every `mutate_*.py`, the whole of `tools/verify/` except
`_kit.py` (which the door imports), and every `*.md` **removed from the
filesystem**. As in ADR-136, "the operator did not see the task" is a fact
about the disk rather than a promise about anyone's attention.

Each was handed its blind brief (ADR-193), an `OPERATOR.md` that names the
door and both `since` mechanisms, and `blind_console.py --session op` — the
two DESTRUCTIVE tasks with `--rungs SENSITIVE_READ,DRAFT,MUTATE,DESTRUCTIVE`,
which is the thing ADR-194 could not do.

## What it measured

| task | reached (4th → 5th) | of | claims (4th → 5th) | of | calls 4th | calls 5th |
|---|---|---|---|---|---|---|
| page-stand-sheet-science | 42 → **40** | 57 | 107 → **101** | 125 | 123 | **120** |
| page-collection-sheet-science | 12 → **12** | 21 | 34 → **34** | 45 | 100 | **113** |
| page-pheno-tracker-science | 9 → **9** | 12 | 25 → **25** | 32 | 87 | **87** |
| page-breeding-bench-science | 19 → **19** | 22 | 47 → **48** | 58 | 88 | **88** |
| **total** | **82 → 80** | 112 | **213 → 208** | 260 | **398** | **408** |

**Outcomes and claims are level; what moved is the bytes.**

| | 4th | 5th |
|---|---|---|
| `read-report` calls | 71 | **75** |
| report bytes served | **1,214,815** | **332,828** |
| of those calls, full reports | 71 | **8** |

More reads, a quarter of the bytes. The breeding bench went from 622,981
bytes over 32 reads to 92,794 over 30; the stand sheet from 475,623 over 28 to
147,906 over 25. Both DESTRUCTIVE goals were reached: the stand sheet's undo
and the bench's `Clear trial` both went through, which is the two lower bounds
ADR-194 recorded now measured.

## What it found: the grader could not read a diff

Graded as the fourth trial was graded, this trial scores **63 outcomes and 172
claims** — a fall of nineteen outcomes with no operator doing anything worse.
The drop is proportional, page by page, to how much each used ADR-195:

| task | full report reads | naive score | folded score |
|---|---|---|---|
| breeding bench | 32 → **2** | 19 → **11** | **19** |
| stand sheet | 28 → **2** | 42 → **32** | **40** |
| pheno tracker | 9 → **2** | 9 → **8** | **9** |
| collection sheet | 2 → **2** | 12 → **12** | **12** |

`grade_outcomes` holds a claim against **what a call answered with**, and a
`since` answer is a diff. An operator who used the feature exactly as designed
read as one that never looked at the page.

That is a defect in the **instrument**, and the numbers in the table above are
the folded ones: `harness_tasks.fold_diffs` now rebuilds the document each
call stood for, through the contract's own `apply_diff`. Nothing was re-run —
the traces are as the server wrote them and the grader was fixed to read them.
Re-grading the **fourth** trial through the same folding grader returns
82 / 213 unchanged, because a trace with no diffs in it has nothing to fold.

## What the operators found in the door

- **The two stamps cannot be told apart.** Three of the four passed a snapshot
  stamp to `read-report` (or the reverse) at least once; both are `s` and
  twelve hex digits. The door failed toward more and said so, which is why it
  cost a re-read rather than a wrong answer — but it cost one every time.
- **A trimmed box could report a change it could not show.** The bench
  operator was told `boxes/storOut` had moved and handed two **identical**
  strings, because the sentence that changed sat past character two hundred;
  it fell back to `read-page` to find out what the page now said. Fixed here:
  both sides are windowed on the first character they differ about.
- Two operators concluded report stamps are "single-use" or "rotate per
  serve". They are not — the baseline is the last report served, which is the
  same thing seen from the other side, and neither operator was misled into a
  wrong answer by it.

## What they found in the pages

Filed, not fixed. Found again, for the third time: the breeding bench's
"after 10 generations" is still `10 × ΔF` under a caption that says
*compounding*; the collection sheet's field-sheet export still truncates
entity-encoded reagent labels (`KOH 3&ndas`, `&alpha;-Nano`, `Syringalda`) and
the voucher label still leaks `&ndash;` and is still stale.

New this time:

- **stand sheet** — the exported expansion factor does not reproduce the
  exported per-hectare numbers. π·11.28² is 399.72 m², so EF is 25.0175, but
  the page prints `400 m²` and `EF 25.0` while the stem CSV's per-hectare
  column uses the unrounded factor (0.07069 → 1.7683, where 0.07069 × 25.0 is
  1.7672). The page makes exactly this point elsewhere — it insists r = 5.64 m
  is "EF 100.1, not 100.0".
- **stand sheet** — `associatedTaxa` is emitted as a Darwin Core column and
  never populated, though an interaction names a tallied species.
- **stand sheet** — `top height` is reported as a stand figure from a single
  measured stem, with no sample-size qualifier.
- **breeding bench** — the crop-class token is substituted wrongly for cited
  crops: bean and tomato read "this crop is inbreeder", sweet corn reads
  "this crop is **cited for this crop**" (ADR-194 found the same slot; this
  names which crops are affected and why).
- **breeding bench** — at 0% germination the sowing rate reads "about 100.0
  seeds per plant wanted": 1/p floored at p = 1% where no seed count suffices.
- **breeding bench** — `Clear trial` raised no confirmation dialog at all;
  `read_dialogs` returned none after the clear.
- **pheno tracker** — both exports print the weight set including a trait that
  scored nothing, while the scores are the mean over the traits that were
  scored; the `.eco` export hardcodes `cross: Aa x Aa … vs 3:1` even when the
  page itself concluded 9:7; the CSV column named `weighted total` holds a
  weighted **mean**.
- **collection sheet** — the guild spectrum bar reads percentages by fruit
  body beside a table of taxa counts, with no unit on the percentage.
