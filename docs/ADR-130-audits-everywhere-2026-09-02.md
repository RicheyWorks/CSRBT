# ADR-130 — Audits, everywhere: every state of every page measured, and the unmeasured counted

**Status:** accepted · **Date:** 2026-09-02 · **The 44 px, contrast and focus audits now measure each page in every state a reader can put it in — each tab, every `<details>`, the season started, the comparison opened — and count a control no state reached as a fault; and `audit_frontend` now reconciles every rule a page's stylesheet declares against the rules the browser kept. 35 defects behind closed tabs and three pages of dead CSS are fixed**

## 1. What ADR-129 left

The audits measured each page **as loaded**. An element with no bounding
box was skipped, and half of every instrument's surface has no box until
a tab is pressed: the collection sheet's analysis, the season's recap,
the guide's designer, the visualizer's comparison. So the 44 px rule, the
AA rule and the focus rule had been applied to the front pane of each
page and to nothing behind it, and a clean audit said "the part I could
see is fine" in the voice of "the page is fine". The experiment guide's
import card spilling 30 px sideways on a phone (found by the robot in
ADR-128, not by any audit) was the proof: the guide's tabs name their
pane by `aria-controls`, and no audit had ever opened one.

## 2. The decision

### One walker, three audits (`tools/audit_states.py`)

A page has **states**, and an audit measures every one:

- **`rest`** — the page as loaded, with every `<details>` opened.
- **`pane:<id>`** — each `.tab[data-pane]`, then each `[aria-controls]`
  button, pressed in document order.
- **`state:<sel>`** — a page-specific reveal no tab reaches: the season
  started, marked, recapped, filed and graded; the visualizer's
  comparison; the stand sheet's height card and pack; the relevé's pack;
  a phenology plant selected; and a `<select>` set to the value that grows
  a dependent field (the guide's hot and churn phases, the survivorship
  metric), its owning tab pressed first or the field has no box. A
  revealed surface's own tabs are pressed after it
  (`state:<sel>/pane:<id>`).

The clicks are **programmatic** (`el.click()`), not pointer clicks: after
a real click the browser hides focus rings on programmatic focus, and the
focus audit run after pointer clicks reported 1,461 "no visible focus"
faults that were the mouse's, not the pages'.

### The accounting

Every control (`button`, `input` bar hidden and file, `select`,
`textarea`, `[role=button]`, `.tab`) is stamped once, in document order,
and the walker remembers which stamps had a box in at least one state.
After the walk, `coverage()` reports how many controls exist, how many
were exposed, and the **names of those no state reached** — and each
audit counts those as faults. "I never measured it" must not print as "it
is fine".

### What the audits found, now that they looked

Ten controls under 44 px and twenty-five field borders below 3:1 — all of
them behind a tab or a toggle, none of them ever measured:

- **Under 44 px (10):** cell-bench's buffer-grid buttons (`.bgrid .bb`,
  five), farm-scout's bed cells (`.bed .x`, two), pheno-tracker's `.kbtn`
  keys (two), deployment-log's `time` input (one) — each behind a tab or
  a selected plant.
- **Field borders at 1.35:1 against the card, below the 3:1 floor (25):**
  experiment-guide's designer and tracker inputs and textareas (22),
  cp-bench's inline inputs on its later tabs (2), pheno-tracker's note
  textarea (1). All now `#8E8160`, the border the rest of the kit's
  fields already had.

The three audits are clean across the kit, and for the first time that
sentence is about the whole kit: every control on every page was exposed
in some state and measured there.

### The rule the browser never kept

Every audit in this kit measures what the browser **painted**. A rule the
browser threw away is therefore invisible to all of them — by
construction, not by oversight. Three pages had an orphaned declaration
block: a rule whose selector line had been deleted along with the widget
it styled (the cover-scale `.cv`, gone from these three pages), leaving

    padding:8px 6px; font:800 15px var(--body); ... }

standing alone in the sheet. A browser recovering from that reads on to
the next `{`, so the block *after* the orphan is eaten too: on
**deployment-log**, **ordination** and **relevé** the `.tiles` row lost
its flex layout, and nothing in the kit said so.

`audit_frontend` now reconciles the two: every rule a page's `<style>`
declares must come back from the CSSOM, and anything that does not is
reported **by its selector** as dead CSS. The only rules exempt are the
ones Chromium drops on purpose — `::-moz-`, `::-ms-`, written for other
engines. The reconciliation normalizes the CSSOM's own spelling (it
quotes attribute values, and renames a keyframe's `from`/`to` to
`0%`/`100%`) and nothing else; 41 pages, 0 findings after the fix.
`verify_audit_frontend` seeds the real defect — an orphaned block — plus
a malformed selector, and requires both to fire while a `::-moz-` rule,
an `@media` block, a keyframe and a quoted attribute stay quiet: **23**
checks (+3).

### Verification

`tools/verify/verify_audit_states.py` (**33** checks) holds the walker to
the states on a fixture page whose reveals are declared (tabs by
`data-pane` and by `aria-controls`, a closed `<details>`, a `<select>`
that grows a field only in a pane another tab has since closed, a reveal
that replaces the tab bar with its own), the accounting to exact counts
(the one control no state reaches is named; a stamp is assigned once and
survives; a hidden input is not a control), the click to the focus audit's
own probe (a ring on every control after the walk), and then runs
**the three audits themselves** on a fixture directory whose faults are
known — a 20 px button behind the second tab, faint text behind the
third, a control no state reaches — and requires each to exit non-zero,
name the fault, and count the unreached control as one. On real pages:
the season starts for the audits, the guide's hot phase is reached
through its tab, and coverage on both is complete.

`tools/mutate_audit_states.py` breaks the walker and the three audits
**20** ways — tabs not pressed, `aria-controls` not a tab, `<details>`
left closed, reveals skipped, the owning tab not pressed before a
`<select>`, exposure not accumulated, stamps reassigned, coverage naming
nothing, a pointer click, the reveal table emptied, and each audit
measuring the page as loaded or not counting what it never measured —
and requires the suite to notice each. 20 killed, 0 survived.

The audits accept `CSRBT_DOCS_DIR` (a fixture directory) and the walker
`CSRBT_AUDIT_STATES` (a fixture's reveals, as JSON); nothing but the suite
sets them.

## 3. Held

- **Audits after entry.** The states are the page's own reveals, before
  any data is entered. A report that appears only once a row exists (the
  greenhouse's runOut, the sheet's analysis with figures in it) is
  measured empty. Next: the task runner's entered state as an audit
  state — run a page's science task, then audit.
- `audit_print`, `audit_offline`, `audit_escaping` measure the page as
  loaded; they are about the document, not its controls, and are
  unchanged. `audit_frontend` gained the stylesheet reconciliation above
  but still sweeps at rest.
- The lab's session station cards still have no ids; `#bRand`,
  `#bRand10`, `#spRand` are not driven.

## 4. First reading

    audit_targets   0 under 44 px or never measured   (every page, every state)
    audit_contrast  0 faults                           (every page, every state)
    audit_focus     0 faults                           (every page, every state)
    audit_frontend  369 / 369 checks clear, 0 dead rules (41 pages)
    verify_audit_states 33 / 33 · mutate_audit_states 20 killed, 0 survived
    verify_audit_frontend 23 / 23
    kit  69 / 69 suite jobs, 5,106 / 5,106 checks; 8 audits green
    board 156 / 156 mutants, 50 / 50 tasks, 7,481 commands walked
