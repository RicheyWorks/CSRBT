# ADR-167 — The collection sheet, recorded whole

**Status:** accepted · **Date:** 2026-09-09 · **The kit's largest data-entry page (262 controls) drove 59 of its 63 fields, but four chemical spot-test inputs were never filled — and on this sheet a blank reagent means "not tested". Now 63 of 63, every reagent recorded.**

## The four tests that read as never run

`collection-sheet.html` is the mycological field-and-herbarium sheet: a
search-effort header, five collections each with genus, host, count and
characters, spore-print and voucher panes, and a Darwin Core / Humboldt export.
At 262 controls it is the largest data-entry page in the kit, and its task
already drove **59 of 63 fields** — the site, the weather, five full
collections, a spore print, a voucher label and every export.

The four it missed are all in one place: the **chemical spot-test panel**. It
offers eight reagents — KOH, ammonia, iron salts, Melzer's, guaiac, phenol,
α-naphthol and syringaldazine — and the task recorded four of them (KOH,
ammonia, iron, guaiac) and left **Melzer's, phenol, α-naphthol and
syringaldazine** blank. On this sheet a blank reagent field means *not tested*,
not *no reaction*, so four real bench tests read as never having been run.

## Recorded, and the sheet held still

The existing scenario is kept verbatim — the five collections, the diversity
statistics (S_obs 5, Chao1 6.5, the Shannon figure), the spore-print verdict,
the voucher label and every export (CSV, Darwin Core, ECO, material sheet) are
all asserted **before** the new steps run, so they hold — and the four missing
reagents are recorded on collection RCW-2026-041 alongside the four already
noted: Melzer's inamyloid, phenol slowly wine-brown, α-naphthol no reaction,
syringaldazine negative. Because the reagent inputs write to the current
collection's record and feed the export, they are driven *after* every export
assertion has been graded, and the note the sheet already carried is read once
more to confirm nothing moved.

## What moved

    collection-sheet   59 → 63 of 63 fields entered      (the kit's largest
                                                         data-entry page, closed)
    collection-sheet   83 → 90 confirmed expectations      0 refuted
    the kit           511 → 515 of 521 fields              (99%), 24 of 27 whole

## Held

The reagent inputs write to the current collection and feed the export, so they
are driven after every export assertion has been graded — the note the sheet
already carried is re-read at the end and still contains "notes Cap viscid when
wet", so adding four reagent lines changed nothing the sheet is trusted for. No
page was edited: a task-only slice, the seventeenth page driven end to end.
