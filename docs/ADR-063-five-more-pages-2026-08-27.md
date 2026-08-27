# ADR-063 — Five more pages, and two bugs the upper bounds could not see

**Date:** 2026-08-27
**Status:** accepted
**Extends:** ADR-062 (the recorded triage)

## The sweep

Five pages, four mutants each. The recorded triage from ADR-062 absorbed the
recurring Field Entry Kit noise on every one of them, which is what it was for.

| page | before | after | fresh survivors |
|---|---|---|---|
| fungal-characters | 100% | 100% | — |
| farm-scout | 75% | 75% | none unexamined |
| greenhouse | 25% | 25% | 1 |
| field-season | 25% | 25% | none unexamined |
| tree-proofs | 50% | **75%** | none unexamined |
| food-web | 50% | **100%** | — |

Six fresh questions came out of it. Two were real, two were equivalent, one is
cosmetic, one is still open.

## Real: a tree height that no upper bound could catch

`tree-proofs` computes `n.h = 1 + Math.max(n.left.h, n.right.h)`. The sweep made
it `Math.min` and the whole section stayed green — because **every bound the
page asserts is an upper bound**:

```
h <= 1.4404 * log2(n+2) - 0.3277        (AVL)
h <= 2 * log2(n+1)                      (red-black)
```

A height computed too *small* satisfies all of them. On a page whose entire
purpose is demonstrating height bounds, the heights could have collapsed toward
1 and 137 checks would have passed.

The missing half is the information-theoretic floor: **no tree of n nodes fits
in a height below log2(n+1)**. Added to both the AVL and red-black loops,
recomputed from n rather than pinned (ADR-041). The mutant dies.

## Real: the first link was unremovable

`food-web`'s instructions say *"Tap the same pair again to erase the arrow."*
The erase branch is `if (i >= 0)` on a `findIndex` result. The sweep made it
`i > 0`, which leaves **the link at index 0 permanently unremovable** while every
other link still erases — and nothing noticed, because no check had ever erased
the *first* link.

`verify_fw` now loads the pond preset, taps the pair for `links()[0]`, asserts
the count drops and that it was *that* link, then taps again and asserts it comes
back.

## Real: a verdict boundary nothing sat on

The connectance reading hinges on `C <= 0.3`. The sweep made it `C < 0.3` and
everything passed, because **no web in the suite sat on the boundary** — the only
place the two spellings differ. `S = 10, L = 30` is exactly 0.300.

Building that web took three tries, and the failures are the interesting part:

1. Python dicts and dict-shaped links — `FW.load` takes **arrays of pairs**, and
   a dict reaches JS as an object with no `.forEach`.
2. Every consumer eating every other species, which is mutual predation. The
   verdict block is guarded by `!orphans.length && !L.loop`, so the page printed
   *Loop detected* and never printed a connectance reading at all. The check was
   failing for a reason that had nothing to do with the boundary.

The web is now a DAG with one seeded incoming link per consumer, so there are
neither loops nor orphans, and a companion check at 31 links asserts the verdict
*flips* — otherwise the first check would pass on a page that says "in the range"
whatever the number.

## Examined and left

- **`lam <= 0` → `lam < 0`** in field-season's Poisson draw. Equivalent: with
  λ=0, `L = exp(0) = 1` and the do/while exits on the first draw, because the
  PRNG returns `t/2³²` which is always below 1. `k-1 = 0` either way.
- **`t <= 4` → `t < 4`** in tree-proofs' chart: five gridlines at 0/25/50/75/100%
  become four. Chart furniture; no claim depends on it.

Both recorded in `KNOWN_EQUIVALENT` with the reasoning, so no one triages them
again.

## Still open

`greenhouse`, `drop-esc` on `esc(lastErr)` — the autosave-failure banner. The
value is a browser-generated error message, not typed input, so
`audit_escaping`'s probe cannot reach it. It is testable — force
`localStorage.setItem` to throw with markup in the message — and it is not
tested. Left on the worklist rather than waved through.

## Cost

`verify_proofs` 137 → 139, `verify_fw` 57 → 61, `mutate.py` +2 recorded
equivalents. No page changed: every fix this slice was a missing check, not a
wrong page. 51/51 jobs green, 3628 checks.

**Swept: 8 pages. 31 to go.**
