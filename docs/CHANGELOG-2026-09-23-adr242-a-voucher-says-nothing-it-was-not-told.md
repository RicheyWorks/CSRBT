# 2026-09-23 — ADR-242: a voucher says nothing it was not told

## Fixed (relevé, filed by the seventh blind trial)

- **Voucher material and phenophase start unset.** They defaulted to *in
  flower* and *flowering*, and a voucher recorded without touching them
  carried `[in flower, flowering]` onto its label.
- **A voucher is refused until its material is said**; the number is kept.
- **A voucher with no phenophase records none**: its record, label, list
  row, export line and confirmation all say *phenophase not recorded*.
- **`vouNote`** under the dials says what the next voucher will be recorded
  as, so a value carried from the last specimen is seen before it is written.

## Checked

Task 183 → 187 confirmed (refuted on the old page). verify_rv 81 → 94,
against the record KEEP holds. New runner `tools/mutate_rv.py`, 12 mutants, all killed.
