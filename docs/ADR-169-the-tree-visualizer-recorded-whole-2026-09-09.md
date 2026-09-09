# ADR-169 — The tree visualizer, recorded whole

**Status:** accepted · **Date:** 2026-09-09 · **The order-statistic tree was never asked an order statistic: its select-k-th and rank-of boxes sat at defaults, read by nothing. Now 3 of 3, both queries held against the obvious answers on a known three-key tree.**

## A tree that reports select and rank, and is never asked either

`tree-visualizer.html` inserts keys into a red-black / AVL / splay /
weight-balanced tree and reports node counts, height, rotations and order
statistics against an independent Python port of all four strategies. Its task
drove the boot tree, the four morphs and a seeded random build — but **two of its
three value-carrying inputs were never driven**: the **select-k-th** and
**rank-of** boxes, the two order-statistic queries, left at their defaults (1
and 42) and read by nothing.

A tree that reports select and rank but is never asked either is a data
structure whose two most characteristic queries — the whole point of an
order-statistic tree — go unexercised.

## Asked, on a tree a reader can count

The existing scenario is kept verbatim — the 13-key boot tree at height 4, the
14th key, the ascending 20-key RB build, the four morphs, the seeded random
fill — so its assertions hold, and the two inputs are driven at the end on a
**rebuilt deterministic tree**: cleared, then {10, 20, 30} inserted. `select(2)`
is asked and reads **20**; `rank(30)` is asked and reads **#3** — the page's own
`selectK` and `rankOf` held against the obvious order statistics of three known
keys, so both sides of the claim are the same arithmetic and no hand-typed
figure can be wrong.

## What moved

    tree-visualizer   1 → 3 of 3 fields entered      (the two order-statistic
                                                      queries, now asked)
    tree-visualizer  80 → 91 confirmed expectations     0 refuted
    the kit         518 → 520 of 521 fields             (26 of 27 pages whole)

## Held

The order-statistic queries do not change the tree, so building a known
three-key tree and asking select and rank of it exercises both inputs against
answers a reader can check by counting; the rebuild happens after every earlier
assertion has been graded. No page was edited: a task-only slice, the nineteenth
page driven end to end, and only cp-characters is left short of whole.
