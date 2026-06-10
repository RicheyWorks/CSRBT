# CHANGELOG 2026-06-10 — consolidation audit over the ADR-006…009 slices

Fresh-eyes pass over two days of rapid building before calling the roadmap closed. One real
bug found and fixed; the rest of the audit is recorded so the reasoning isn't lost.

## Fixed: `TreeExport` vs degenerate trees (the spine, again)

The export walks were recursive over tree **height** — and a Splay tree after sorted
inserts is an O(n)-deep spine, the very pathology this codebase already met once (the E5a
benchmark's stack overflow) and the very state a visualizer is *for*. Two distinct failure
modes, both fixed:

- **Stack:** `node()` and `depthOf()` are now iterative (explicit frame stack / depth
  stack). Nesting cost moved from stack to heap.
- **Output size:** pretty-printing was quadratic — at depth d every line carries O(d)
  indentation, so a 50k spine emitted ~5 GB of whitespace before anything overflowed.
  Indentation now caps at 64 levels; the JSON stays valid, and readability at depth 64 was
  never on the table.

Regression test: `TreeEventExportTest.Export.degenerateTreeExports` builds a **50,000-deep
Splay spine** and exports it (height and size asserted, braces balanced). Suite 474, green.

## Audited clean (recorded so it isn't re-derived)

- **Event emission under locks** — every `if (events != null) emit(...)` site sits inside
  the same critical section as the mutation it reports, so event order is the mutation
  order; the listener contract (fast, non-throwing, non-reentrant) is documented on the
  interface and both setters.
- **`PersistentRankedSet` meters are non-volatile** — correct: meters are written only on
  the write path, which the ensemble serializes; lock-free readers never touch them.
- **Engine members vs lock-free votes** — the ADR-007 optimistic pass reads members without
  locks; the three member kinds are each safe by a different mechanism (OrderedSet: R1
  stamps; persistent: immutability; B+tree: coarse synchronization). Recorded as a
  requirement on future `engineMember(...)` implementations in the handoff notes.
- **Benchmark assertions vs CI noise** — the five printed rows assert with wide margins
  (15×, 2.7×, 2× bounds, absolute 500 ms) or deterministic facts (stride counts, heights);
  judged CI-safe as written. If a GitHub runner ever flakes one, loosen the single
  offender, not the discipline.
- **Stale docs** — `SESSION-HANDOFF-2026-06-09.md` rewritten to the post-ADR-009 state
  (everything landed or trigger-held; "next" options are visibility, a fired trigger, or
  another audit).
