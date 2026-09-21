# 2026-09-21 — ADR-234: a goal's figures are bound to the claims that hold them

## Added

- **`figures` on a task**: `[{says, step, claim}]`. `load_task` refuses a task
  whose goal phrase does not state, as a whole token, the value a required
  step's claim holds. `figures_of(task)` lists them and `goal_of` counts them.
  18 are bound on the three tasks whose prose a blind trial caught: the tree
  proofs (10), the tree visualizer (4) and the ecology lab (4).
- **`tools/mutate_proofs.py`** (on the board), 8/8 killed.

## Fixed

- **Tree proofs**: the worst-case note said "ascending" over a loop that
  counts down. The order and the depth are now read off the tree: "63 keys
  inserted in descending order (63 first) … key 1 sits 62 edges down". The
  task holds the exact sentence.
- **Tree visualizer goal**: "24 nodes after 15 draws" becomes 11 draws and 11
  nodes, from *inserted 60* to *inserted 24*.
- **Tree proofs goal**: key 1 costs "5 rotations + 1 = 6" (it said 6 + 1); key
  63's 7 is stated as what it costs after key 1 is the root.
- **`mutate_brief`**: two anchors that no longer landed (one stale since ADR-196).

## Checked

verify_brief 31 → 46, verify_proofs 143 → 149 (independent splay port plus an
ascending counterfactual), verify_tv 115 → 118 (mulberry32 port);
mutate_brief 14 → 24 and mutate_proofs 8, all killed.
