# 2026-09-09 — ADR-167: the collection sheet, recorded whole

**The kit's largest data-entry page (262 controls, 59/63 fields): four chemical
spot-test inputs were never filled, and a blank reagent here means "not tested".
Now 63/63. The kit reaches 99%.**

## Changed — `tools/tasks/page-collection-sheet-science.json`

117 → 124 steps, 83 → 90 confirmed expectations. The existing scenario is kept
verbatim (five collections, the diversity statistics, the spore-print verdict,
the voucher label and every export), so its assertions hold, and the four
never-filled reagent inputs are recorded on RCW-2026-041 — Melzer's, phenol,
α-naphthol and syringaldazine — alongside the KOH, ammonia, iron and guaiac the
task already noted.

## Numbers

    collection-sheet.html   59 -> 63 of 63 fields entered    (100%)
                            83 -> 90 confirmed, 0 refuted
    the kit                511 -> 515 of 521 fields            (99%), 24/27 whole

## Held

- The reagent panel offers eight tests; the task recorded four and a blank field
  on this sheet means "not tested", so the four blanks were four untested tests.
- The reagent inputs write to the current collection and feed the export, so
  they are driven after every export assertion is graded; the collection's note
  is re-read at the end and still contains "notes Cap viscid when wet".
- No page was edited — a task-only slice, the seventeenth page entered whole.
