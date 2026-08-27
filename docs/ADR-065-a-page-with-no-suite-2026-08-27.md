# ADR-065 — A published page with no suite

**Date:** 2026-08-27
**Status:** accepted
**Extends:** ADR-063/064 (the sweeps)

## 0%

`docs/tree-visualizer.html` reimplements four balancing strategies — Red-Black,
AVL, Splay and BB[3,2] weight-balanced — and shows their heights side by side.
Its own prose states the thesis: *"the teal card has the lowest height … no
single tree wins every workload, which is why CSRBT morphs between them."*

The sweep scored it **0 of 4**. The reason is in the header line:

```
tree-visualizer.html -- 4 mutant(s), suites: verify_focus_slice, verify_print_slice
```

Focus rings and print CSS. **Nothing had ever asserted that the trees are
trees.** Two of the four mutants were serious:

```js
n.h = 1 + Math.max(n.left.h, n.right.h)   ->  Math.min
e.key >= "1" && e.key <= "4"              ->  e.key > "1"
```

The first is the *same height recurrence* ADR-063 found broken-and-unnoticed on
tree-proofs, on a second page, with even less around it. The second leaves the
first strategy unreachable from the keyboard while 2–4 still work.

## The page already had the checkers

Under a comment reading `// ---------- invariant checkers (for tests) ----------`
sit `checkBST`, `checkSize`, `checkRB`, `checkAVL` and `checkWB`. Nothing in the
repo has ever called one. They are good checkers, shipped as dead code.

`verify_tv.py` calls them, rather than writing a second set that could disagree
with the page's own (ADR-039). What it adds is the part they cannot supply:

- **the floor**, `h ≥ log2(n+1)`. Every bound a reader would think to assert is
  an upper bound, and a height computed too *small* satisfies all of them —
  which is exactly how `min` survived here and on tree-proofs.
- the page's headline claim, asserted: ascending 1‥20 really does collapse Splay
  to a spine (h = n = 20), AVL and WB stay short, Red-Black stays within 2×
  optimal, and Splay ends up the tallest of them.
- order statistics — select, rank, median — against an independent Python sort.
- the keyboard shortcuts the page advertises.

## The half my own suite missed

At 51 checks the suite was green and the sweep still scored 50%. The survivor:

```js
while (x !== T.root && !x.red)     ->  ||        // red-black delete fixup
```

Every check I had written **inserted**. None deleted. An insert-only suite for a
structure whose hardest code is deletion measures the easy half — and the sweep
said so immediately, which is the whole argument for running it against a suite
you just wrote and believe in.

Deletions now run on all four strategies — a leaf, an internal node and the root
— re-checking order, sizes and the strategy invariant after each. 51 → 115
checks, and the mutant dies.

Adding them broke the duplicate-rejection check, because the deletes remove 50
and a "duplicate" test on an absent key tests nothing. The suite failed and said
so; it rebuilds first now.

## The one left

`checkBST`'s `if (a[i] <= a[i-1])` → `<`. Equivalent: `bstInsert` returns null
for a key already present, so no two adjacent in-order keys are ever equal and
the two spellings cannot differ. Recorded — and the measurement that settles it
is a check in this same suite, asserting that inserting 50 twice leaves the
count unchanged.

## Also swept

`plant-characters` 100%. `field-notebook` and `cp-characters` each left one
fresh survivor, carried forward rather than waved through: a dispersion band
(`I <= 1.4`), a prose figure (`0.2 to 5 mm` for bladderwort bladders), and the
shared webfont loader's `if(!l) return` — that last one appears on every page in
the kit and nothing tests it, which is worth its own look.

## Cost

`tools/verify/verify_tv.py`, 115 checks, new — the kit's 52nd suite.
`mutate.py` +1 recorded equivalent. No page changed. 52/52 jobs green,
3748 checks.

**Swept: 16 pages. 23 to go.**
