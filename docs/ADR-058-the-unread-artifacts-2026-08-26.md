# ADR-058 — The four artifacts nobody was reading

**Date:** 2026-08-26
**Status:** accepted
**Extends:** ADR-052 (binding the docs to the engine)

## What was unbound, and why it looked like it did not matter

ADR-052 bound `docs/ecology-lab.html` to the engine through
`ecology-lab-session.json` and listed five session artifacts it had *not*
bound. Four of them are:

```
docs/arena-session.json      docs/arena-search-session.json
docs/viability-map.json      docs/visualizer-contract.json
```

The reason they stayed unbound was a search that came back empty: no page in
`docs/` references any of them. On that evidence they look like dead weight —
826 KB of recorded state shipped beside pages that never load it.

They are not dead. Their reader is **`demo/visualizer.html`**, which is outside
`docs/` and therefore outside every sweep the kit runs. Its footer names all
four, describes what each shows, and invites you to drop them in. That is the
same defect one level out: an artifact and the prose describing it, with nothing
in between.

## What the descriptions actually said

Three of the four held up when checked against the files:

- **arena-search-session** — "genomes born, gate-killed, culled, and one
  promoted": `Lineage` events carry founders and mutations, generation 1
  disqualifies one, generations 2–6 each cull one, and a `Morph` commits. ✓
- **viability-map** — "the ADR-012 E1 lethality heatmap over the (Δ, Γ) plane":
  every cell carries `delta` and `ratio`, and ADR-012 uses that notation. ✓
- The **three states embedded in the page itself** — "the same 15 keys … before
  and after real health-gated morphs (RedBlack → Splay → AVL)": same 15 keys in
  all three, Splay a 15-deep spine, AVL four deep. ✓

One had gone wrong:

> try `docs/arena-session.json`: the real controller morphing **RB → Splay → RB**

The recorded arc is **RedBlack → Hybrid → Splay → Hybrid**, and it never returns
to red-black. A reader who loaded the file to see the described thing would have
watched the page's own cards name two strategies the description omits, and
waited for a return that never comes.

## The rule

A page's arrow chain must be a **faithful abbreviation** of the recorded arc:
same length, and each token abbreviating the strategy in that slot (`RB` for
`RedBlack` is fine). A page may shorten a name. It may not drop a strategy the
reader's own screen will name, and it may not invent a return to one.

The arc is computed from the file — repeats collapsed — and compared to the
chain parsed from the page. One implementation, two callers, per ADR-039.

## Why this needs no compiled engine

ADR-052's link A reports UNVERIFIED where the engine cannot run. Everything here
is checkable from the shipped bytes, because a tree export carries its own
invariants: node size is `1 + size(left) + size(right)`; the root sits at depth
1 and every child one deeper; the state's height is its deepest node; the
in-order key walk increases. **All four hold across 52 recorded states and 5576
nodes.** The exports are real engine output, and now something says so on every
run rather than on the day someone last looked.

Unlike a byte hash, these name the state and the node, and they keep passing
when the engine legitimately produces a different tree — ADR-041.

## Two fixtures that were passing for the wrong reason

The canary found both, and neither was visible by reading:

1. **The depth fixture was being caught by the height rule.** Seeding a wrong
   depth also makes the deepest node disagree with the recorded height, so
   disabling the depth rule outright left every fixture green. Each seeded fault
   now asserts *which* invariant complained, not merely that something did.
2. **Every `faithful()` refusal fired for the wrong reason.** With the length
   test deleted, `zip` truncates — and in all four negative fixtures a
   mismatched pair happened to line up anyway, so all four still refused.
   The missing case is a claim that is a correct *prefix* of the arc and simply
   stops early. Added, both directions.

## Canary

Thirteen mutants, all caught: length test dropped; `faithful()` always true;
initialism match widened; arc repeats no longer collapsed; each of the four
invariants disabled in turn; state discovery returning nothing; the page
reverting to the wrong arc; one node's size off by one inside a 1264-node
export; and the viability map losing its violation column.

## Cost

`tools/verify/verify_visualizer_sessions.py`, 32 checks, new. One sentence
corrected in `demo/visualizer.html`. 50/50 jobs green, 3552 checks.

## Still unbound

`ecology-experiment-session.json` — the fifth from ADR-052's list, read by
`eco-protocol-reference.html`, which is a published page and a different job.
