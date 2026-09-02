# ADR-129 — Every page, operated: the keys, the simulators, the proofs and the reference pages held through the gateway

**Status:** accepted · **Date:** 2026-09-02 · **Every one of the kit's 41 routed pages now has a task: 27 science tasks that enter data and hold the page's report to an independent oracle, 14 reference tasks that pin a page's outline; and the reader reaches what it could not**

## 1. What ADR-128 left

Twenty-one data-entry pages had a science task. Six interactive pages did
not — the three character keys, the tree visualizer, the tree proofs and
the interactive lab — and fourteen pages with no data entry (the hub, the
suites, the essays and guides, the protocol library and reference, the
explorer) had nothing at all. The walk (ADR-124) drove their buttons; no
task asked whether a key found the right family, whether a splay's
amortized cost came out negative on a path, whether the lab's seeded
terrarium read the evenness it should. And on the lab the robot could not
move the one experiment on the page: its three sliders are plain
`<input type=range>`, not FEK sliders, and the swarm's kind list only
named the FEK ones.

## 2. The decision

### The reader reaches everything (`read-report`)

- Box suffixes **`*Msg`, `*Check`, `*Read`, `*Desc`, `*Left`, `*Res`**:
  the keys' `#kres`/`#kRes`, the visualizer's `#msg` (`inserted 7`,
  `already present`, `morphed`), the proofs' `#spCheck` (the Access
  Lemma bound, `INVARIANT FAILED`), the lab's `#t-meadow-read`.
- A box holds **4,000** characters, not 1,500: a key with eight candidate
  cards needs more.
- **`headings`** — the page's `h1`–`h3` texts in order, capped at 80: a
  reference page has no figures and no boxes, and its outline is its
  report.
- A figure's label may be a bare **`.k`** beside the `.v` (the
  visualizer's `Nodes`, `Height`, `Rotations (total)`).
- The swarm discovers **every** `input[type=range]` as a slider, so
  `set-slider` reaches the lab's terrarium.

`verify_report` **33** (+3), `mutate_report` **24** (+2), all killed.

### Six more science tasks, with independent oracles

- **The three keys.** The scoring rule (`hit + 1.5·tells − 2·misses`,
  clean rows first, six shown) is ported to Python over the page's own
  data tables, and the tasks hold the **whole result box** verbatim:
  herbaceous + opposite + simple + square stem + aromatic → 7 of 20
  families, Lamiaceae first at 3/3 with 2 extra; gills + white print +
  chalk-snapping flesh → Russula alone, 4 of 4; a snap trap → Aldrovanda
  and Dionaea, then free-floating water leaves Aldrovanda with Dionaea
  disagreeing on where it grows; the no-match cases with the conflict
  named. (`verify_cpc` had hand-checked the cp key; the plant and fungal
  keys had never been asked.)
- **The tree visualizer.** An independent Python port of all four
  strategies — CLRS red-black, AVL, weight-balanced BB[3,2], bottom-up
  splay — with the page's rotation accounting: the boot tree (13 keys,
  height 4, 0 rotations, median 42, rank(42) #7), 7 inserted (height 5,
  `1.3×` — JS `toFixed` rounds 1.25 up; Python's `%.1f` does not, the
  oracle uses decimal half-up), 1..20 ascending into red-black (height 7,
  14 rotations), morphs rebuilt from sorted keys: AVL 5, **Splay 20 — a
  spine**, WB 6, RB 7. 70 expectations, first run.
- **The tree proofs.** The same port carries the splay potential
  Φ = Σ log₂ size: 79.3 balanced, access 1 costs 6 actual / 13.0
  amortized, the same key again 1 / 1.0, the descending path Φ 290.0 and
  the headline access **63 actual, −77.4 amortized** under the bound
  18.9; the minimal-AVL table to height 12 (F(h+2)−1 nodes under
  1.4404·log₂(n+2)−0.3277), select(9) in 5 steps and select(20) in 3,
  cell by cell from `tables`. 175 expectations.
- **The interactive lab.** The seeded terrarium reproduced from a
  mulberry32 port (meadow J′ 0.73 / 29.2 / 100; island 616 / 604 / 16 ops;
  95 % hot share uneven, a hot set of 20 very even, capacity 32 → 342 /
  310), every workbench figure recomputed (Shannon, Chao1, variance/mean,
  Morisita, Hardy–Weinberg, Jaccard/Sørensen/Bray–Curtis, Lincoln–Petersen
  and Chapman with its interval, χ² against the Mendelian ratios), and
  changed as entered — a sixth bird, AA = 400 (p 0.585), R = 20, the
  dihybrid preset; the `.eco` lines carry the entries. The plan's
  "critical 9.488" for df 3 was df 4's; the page prints 7.815 and the tool
  agreed.

### Fourteen reference tasks

A page with no data entry — the hub, the three suites, the four guides,
the glossary, the field card, the essay, ADR-031, the explorer, the
protocol library and reference — is held to its **outline**: the exact
list of headings in order, its table count (the explorer's twelve, the
field card's sixteen), the library's copy toast (one of two honest
strings, since a clipboard is the browser's to grant), and intact — no
leaked value, no script error, nothing pushed sideways.

### Verification

`verify_tasks` section G now pins that **every routed page has exactly
one kind of task** — science or reference — that every science task
reads its report after its last entry and holds a figure, a table cell, a
row count or a whole box, and that every reference task pins headings.
**125** in quick mode (+23), 176 in full. Ledger: 44 page tasks held (27 science, 14
reference, the read-back, the canary), 1,807 expectations confirmed on the page.

## 3. Held

- **Audits at rest.** `audit_targets`, `audit_contrast`, `audit_focus`
  measure each page as loaded: a control with no bounding box is skipped,
  so every control behind a closed tab — most of the kit's surface — has
  never been measured for 44 px, contrast or focus. The experiment
  guide's spill (ADR-128) is the proof. Next slice: every audit, in every
  pane and after entry.
- The lab's session station cards have no ids, so their tiles collide
  under `#main`; the task reads the workbench and the terrarium, not the
  stations.
- `#bRand`, `#bRand10`, `#spRand` (`Math.random`) are not driven.

## 4. First reading

    44 page tasks held (27 science, 14 reference, the read-back, the canary)
    1,807 expectations confirmed on the page
    kit 76 / 76 jobs, 5,435 / 5,435 checks
