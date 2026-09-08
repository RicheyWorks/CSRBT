# Changelog — 2026-09-07 — ADR-155: the instrument in the measurement

`verify_findings` was **red on this tree**: twelve accepted baseline entries no
longer occurred. Five were a real layout defect **ADR-128 already fixed on
09-02** — nobody could tell, because the number it was meant to move had stopped
being a property of the page. Seven were never defects at all.

**Accepted debt 13 → 1. Invariant breaks: 0/38/61 depending on the run → 0 on
every run. No page edited.**

## Fixed — `tools/harness.py`

- **The fill counter is per page and thread-local.** It was a module global
  shared by every page in the run, so `survey-design` driven *alone* was typed
  `harness-3` and driven as page 35 of 41 was typed `harness-378` — three
  characters wider, and a row that fitted a 390 px phone stopped fitting. The
  same two pages are on record in this repo at three different answers:

  | | `selection-log` | `survey-design` |
  |---|---|---|
  | committed ledger (pre-ADR-128) | 38 | 0 |
  | working-copy ledger, 08-31 | 38 | 23 |
  | a run on this tree today | 0 | 0 |

  Thread-local rather than merely reset per page: the run drives two pages at a
  time, so a plain global assignment would leave the two walks clobbering each
  other — only under `-j2`.

- **The spill report names something you can act on.** It took the first two
  matches in document order and printed a tag and a width — `div.row2 w=372` for
  a 15 px spill, a 372 px box in a 390 px page, too wide for nothing. Document
  order is not blame order (every ancestor of an overflowing child also
  overflows), and a width alone cannot be judged (372 looks fine until you know
  the box starts at x=33). It now names the outermost element **whose parent
  still fits**, with its span and overrun:
  `div.row2 x=33..427 (+37 past 390) "harness-2harness-3 · un"`.

## New — `verify_harness_matrix.py` section L (71 → **77 checks**)

L1 a page measured after another page measures the same · L2 and the fixture
really was driven both times · L3 the counter restarts at one per page · L4 two
walks at once don't share it · L5 the accounting holds · **L6 no module-level
state in the harness is written to during a run.**

L6 is the rule rather than the instance — an AST walk rejecting `global`,
container mutation and subscript assignment on any module-level name, so the
*next* cross-page counter is caught before it invents a defect. `_FILLS` is a
`threading.local()` and exempt by construction. Canaried by reintroducing a
module-level list.

**Section F has claimed determinism since ADR-109 and passed throughout** — it
compares bucket counts on a fixture with no text input, so the counter never
advanced and nothing compared what the harness types. *A promise checked only
where it cannot be broken is not checked.*

## New — `tools/mutate_harness.py` (15 → **18 mutants, 18 killed, 0 survived**)

Remove the per-page reset → **L1** · make the reset a no-op → **L1** · make the
counter a plain global again → **L4**.

**Two of the three survived the first version of these checks**, both silently:

- **L1 was a comparison**, and both of its runs inherited the pollution from
  sections A–K, so deleting the per-page reset made both spill and the two still
  agreed. It now asserts an absolute fact — a page's first fill is `harness-1`,
  read out of the harness's own spill report — instead of comparing two runs.
- **L4's two threads never overlapped.** Started back to back, the first finished
  reset-and-tick before the second began, so both read 1 while sharing one
  counter. It now uses a `threading.Barrier`; canaried both ways (thread-local
  `[1,1]`, plain object `[1,2]`).

## Changed — `tools/harness_baseline.json` (13/63/3 → **1/1/1**)

All twelve spill entries struck, with the reason in the file. The kit's entire
defect register is now `stand-sheet | dead | 📷 Add photos` — one control in
3,699 affordances.

## Also audited

Three module-level containers remain in `harness.py` (`VIEWPORT`, `KINDS`,
`EXCLUDED`); none is written to at runtime and no `global` statement remains.
L6 keeps it that way.

## Docs

- `docs/ADR-155-the-instrument-in-the-measurement-2026-09-07.md`
- `docs/AI_HARNESS.md` §7a, §7b, §7z (new), §8
