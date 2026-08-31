# Changelog — 2026-08-31 — ADR-111: one visibility oracle

Closes the open question ADR-110 left: four `ecology-lab` textarea fills that
timed out under the walk while working perfectly by hand. **The harness was
wrong, not the page.** Four accepted "defects" struck from the baseline.

## Fixed — `tools/harness.py`

- **One visibility oracle.** Discovery asked a hand-rolled test (non-empty box,
  `display`, `visibility`); the driver asked Playwright, which asks
  `checkVisibility()`. A textarea inside a **collapsed `<details>`** passes the
  first and fails the second — Chromium skips rendering the subtree without
  touching either property, so the box is still 300×120 and the styles still say
  visible. Discovery drove it, the fill timed out, and the record was filed under
  `failed`, which in this harness means *the page misbehaved*. Discovery now asks
  the same question the driver obeys.
- **Collapsed disclosures are named.** The probe counts `<details>` ancestors
  that are shut, so an unreached control reads *"inside a collapsed disclosure
  the walk did not open"* instead of *"not visible with its own pane open"*. Both
  land in `hidden`; only one of them tells the truth about which.

## Considered, measured, and rejected

Opening the disclosures — built two ways, both reverted, both kept as a comment
block with their numbers:

| approach | `ecology-lab` driven |
|---|---|
| before | 83 |
| one oracle, no opening | **85** |
| open ancestors before each press | 55 |
| expand every `<details>` once, before discovery | 55 |

Four controls bought, thirty lost. The `edit as text` box rebuilds the whole
Workbench widget from its own contents, destroying the row editor above it, and
affordance ids are positional — so every id above the break pointed at nothing.
Driving the raw box and driving the row buttons are mutually exclusive in one
walk: `sequenced` at widget scale, not a defect on either side.

Recorded separately because it corrects an impression: **the accounting identity
held perfectly through both experiments** while coverage fell 85 → 55. It says
nothing was lost track of, not that nothing was lost.

## New — `tools/verify/verify_harness_matrix.py` section K (62 → **71 checks**)

K1 a collapsed-disclosure control is `hidden`, never `failed` · K2 the reason
names the disclosure · K3 an **open** disclosure is driven normally (so K1 can't
be satisfied by not testing disclosures at all) · K4 `display:none` stays hidden
and is not mislabelled · K5 rendered-but-zero-box stays hidden · K6/K7 (×2
fixtures) nothing reaches `failed` carrying an actionability timeout, and the
identity holds.

## New — `tools/mutate_harness.py` (13 → **15 mutants, 15 killed, 0 survived**)

- restore discovery's private visibility test → killed by **K1**
- stop counting collapsed disclosures → killed by **K2**

`I2` (every mutant's anchor still matches exactly once) **failed** during this
work — editing `drive_all` moved the `B3` anchor. Without that check `B3` would
have silently stopped testing anything while still printing *killed*.

## Changed — `tools/harness_baseline.json` (17/67/4 → **13/63/3**)

The four `ecology-lab | failed | <textarea sample>` entries are **struck**.
`verify_findings.py` refused the run until they were written off — the "debt paid
and not written off also fails" half of the ratchet, doing exactly the job
ADR-109 built it for. The file records why they went.

## Kit totals

3,699 discovered · 2,367 driven · 1 dead · 10 sequenced · 255 hidden ·
**0 failed** · 1,066 excluded · 61 invariant breaks (was 62).

Four records moved from `failed` to `hidden` with **no coverage lost**.

## Docs

- `docs/ADR-111-two-oracles-in-one-instrument-2026-08-31.md`
- `docs/AI_HARNESS.md` §7a, §7b, §7bb (new), §8
- `docs/ADR-110-…` §7 — the open item is closed, and the "one genuinely dead
  control" line is annotated rather than quietly corrected: it read 2 kit-wide on
  the run ADR-110 was written from, and is 1 from this ADR onward.
