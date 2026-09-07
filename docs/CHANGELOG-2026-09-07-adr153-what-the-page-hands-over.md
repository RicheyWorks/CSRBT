# 2026-09-07 — ADR-153: what the page hands over

**63 outputs across 19 pages hand something over. 62 of them left with nothing
reading them. Three sheets now read their own exports; 62 → 42, and a ratchet
holds the rest.**

## New

- **`tools/audit_outputs.py`** — the other end of `entry_reach`. Walks each
  page's states, replays its own task, then presses every control whose *name*
  says it hands something over and asks `collect-output` what came out.
  Classifies each as emits / silent, and each emitting one as held (the task
  presses it *and* then reads it) or unread. Ratchets **downward** per page.
  Refuses to press anything `harness_plugin_page.destroys` calls destructive —
  "Forget this device's copy" matches `copy` — and measures nothing until the
  entry has run, because an export pressed on an empty page hands over the
  page's placeholder line and that is a payload.
- **`tools/verify/verify_outputs.py`** — 26 checks on a fixture carrying an
  export that always emits, one that refuses until there are rows, a download, a
  print, one behind a tab, one named for an export that never emits, a
  "Preprint checklist" (a verb inside a word), a text box labelled "Plants you
  plan to save", and a destroyer sitting first on the page so that pressing it
  would show up in everything after.
- **`tools/mutate_outputs.py`** — 24 mutants, 1 known equivalent.
- **`tools/outputs_ledger.json`** — per page: what each button hands over, which
  are held, and the ceiling.
- Registered in `run_all`'s audits and on the Harness Board.

## Changed — three sheets read their own exports

- **`tools/tasks/page-collection-sheet-science.json`** 104 → 117 steps
- **`tools/tasks/page-releve-science.json`** 109 → 125 steps
- **`tools/tasks/page-stand-sheet-science.json`** 149 → 165 steps

Each export is pressed and its payload held against a figure the task **already
asserts on screen** — the relevé's `Shannon H' 0.67`, `FQI 7.5`, prevalence
index `4.77`, its matrix row `WAS-12,62.5,0.5,3.0,15.0`; the stand sheet's plot
line `r=11.28 m = 400 m² (0.0400 ha), EF 25.0`; the collection sheet's
`# searched: 1000 m² in 90 min`. The generator refuses any figure the task does
not already hold, allowing only the export's own decimal padding.

## Numbers

    outputs that emit         63 across 19 pages
    unread                    62 -> 42
    held                       1 -> 21
    silent                    19  (pages whose tasks give them nothing to export)
    verify_outputs            26 new
    mutate_outputs            24 new

## Held

- It measures reach, not correctness: a task that reads a payload and asserts
  nothing about it counts as holding it, the same bargain `entry_reach` makes.
- 42 outputs on 16 pages are still unread. The ceiling holds them.
- The candidate rule is the page's own vocabulary — copy, download, export,
  print, save, as whole words. A file handed over under some other name is
  invisible, and the rule is in one place so it can be widened.
