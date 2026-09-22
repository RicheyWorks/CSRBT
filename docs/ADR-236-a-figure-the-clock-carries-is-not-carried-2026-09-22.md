# ADR-236 — a figure the clock carries is not carried

**Date:** 2026-09-22 · **Status:** accepted · **Chain:** ADR-235 → this ·
**Protocol:** 1.11 (unchanged)

## Why

`audit_carried` (ADR-211) asks, for every figure a page works out, whether
anything the page hands over carries it. It matches the figure as a number
against every number in every export. By design the match leans towards
*carried*: a bare `4` is carried by any `4`.

Exports carry the time they were made. ADR-234's full run went red on
`audit_declared` because the relevé's declaration for *taxa in pack* read
IDLE: the audit had found the pack's size, 49, carried. Run alone, the page
did not carry it, and a second full run did not either. The 49 had come from
an export's timestamp, in a minute or second that happened to be 49. Nothing
about the page had changed, and a gate went red on the minute the audit ran.

The same coincidence can hide a real loss: a figure no export carries reads
as carried whenever the clock happens to say its number. A single reading
cannot tell the two cases apart.

## Decision

**Each page is measured under two clocks, and a figure counts as carried
only if it is carried under both.** One reading uses the real clock. The
other uses a clock *shifted* by 405 days, 7 hours, 23 minutes, 31 seconds and
457 milliseconds, so every field of a timestamp differs between the two
readings: year, month, day, hour, minute, second and weekday. A number that
only an export's timestamp supplied cannot be found under both clocks.

The clock is shifted, not frozen, and that matters. Freezing the harness
clock also stops `performance.now()`, which would turn every elapsed duration
a page works out into 0, a figure any 0 in any export would carry. Durations
are differences of the same clock, so a shift leaves them alone. A task that
pins the clock itself with `set-clock` stays pinned, because the shift
applies only while the harness clock is unpinned. The shift is an init script
installed after the kit's stubs and before the page plugin's determinism
layer, which wraps it. Checked directly: `new Date()` moves by the offset,
`performance.now()` does not, a date the page names itself is untouched, and
a pinned clock stays pinned.

`combine()` merges the two readings. A figure is lost if either reading lost
it, the figures are every label either reading measured, a reading that
failed under either clock is the reading, and each measured page records
`clocks: 2` and `clock_only`, the figures carried under one clock and lost
under the other.

## Held by

- `verify_carried` 47 → **55**. A new fixture page publishes an *hour stamp*
  (100 + the UTC hour of the real clock, read through `performance`, which no
  shift touches), and its export writes 100 + the hour of `new Date()`. Under
  the real clock the two agree, and one reading called the figure carried.
  Under two clocks it is lost and named in `clock_only`. Every measured
  fixture must be read under both clocks, no other fixture may change with
  the clock, the rules of `combine()` are checked, and the shift must move
  the year, hour, minute and second.
- `mutate_carried` 29 → **36**. The seven new mutants read under the real
  clock only, never install the second clock, make the shift script shift
  nothing, move the date but not the hour or minute, count a figure lost only
  if both clocks lost it, keep only the first clock's labels, and drop a
  reading that failed under one clock. All are killed; see the ledger.

## What it found

**The kit under two clocks reads exactly what it read under one**: 317
figures on the exporting pages, 0 lost, every `raw`, `lost` and `seen` list
identical to the committed ledger, and 30 of 30 declarations covering. No
figure in the kit was being carried by the clock alone. The relevé's IDLE
reading was the clock carrying a figure that is declared to stay on the
screen, and it cannot recur now.

Cost: the audit takes twice as long, about eight minutes of a full run
instead of four.

## Numbers

| | before | after |
|---|---|---|
| verify_carried | 47 | **55** |
| mutate_carried | 29 | **36** |
| readings per exporting page | 1 | **2** |
| figures lost in the kit | 0 | **0**, read under both clocks |

## Held

- **The other audits that match numbers in payloads.** `audit_outputs` asks
  whether a task reads an export, not what number is in it, so it does not
  match numbers this way. Trigger: an IDLE or flipped reading on another
  number-matching audit.
- **Anchors that land exactly once in their own subject** (ADR-235).
- **The pages' filed defects**, one page per slice, oracle first.

## Lessons

- An audit that runs in a real browser also runs on the real clock, and
  anything it matches loosely can match the clock. To tell the page from
  the clock, measure the page under two clocks and trust only what the two
  readings agree on.
- A shifted clock tests a page against another moment of time. A frozen one
  changes the page's behaviour, because every timer and duration stops.
