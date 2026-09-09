# ADR-168 — The soil bench, recorded whole

**Status:** accepted · **Date:** 2026-09-09 · **The composting bench logged its readings on defaults nobody set: the temperature unit, the squeeze-test moisture and the turn chip were never driven. Now 10 of 10, each driven as a pending input so the demo verdict holds.**

## Three controls that fed a reading, and were never touched

`soil-bench.html` is the composting-and-media bench across five panes: a windrow
temperature log measured against the 40 CFR 503 / NOP time-and-temperature
rules, a C:N recipe blender, a media mix, and a texture-by-feel key. Its task
drove the log, the recipe, the mix and the key — but **three controls in the
composting pane were never touched**, and all three are *inputs to a reading*
rather than results: the **Celsius temperature-unit chip**, the **squeeze-test
moisture dial**, and the **turn chip** that records whether the pile was turned
that day.

The task logged its readings on the defaults — Celsius, moisture "Right", not
turned — and never drove the controls that set them, so the bench held no
evidence it could record a turning or a moisture class at all.

## Driven as what they are — pending inputs

The three controls feed the log only through the *Add reading* button:
pressing it snapshots the current temperature, moisture and turn state into a
reading. So the demo windrow log is kept verbatim — 14 of 15 days at or above
55 °C, 5 of 5 turnings while hot, peak 64, not yet certified — and the three
controls are driven **without adding a reading**: the unit chip reselected to
Celsius, the moisture set to "bone dry", and the turn chip toggled. Nothing is
logged, the demo verdict is unchanged, and it is read once more to confirm it.

## What moved

    soil-bench    7 → 10 of 10 fields entered      (the composting pane's three
                                                    pending inputs, now driven)
    soil-bench   66 → 72 confirmed expectations       0 refuted
    the kit     515 → 518 of 521 fields              (99%), 25 of 27 whole

## Held

The three controls feed the log only through the "Add reading" button, so
setting them and not pressing it drives every one while the certified-days
count, the turning tally and the 64 peak all stay where the demo put them. The
unit chip's reselection rebuilds the entry controls and recomputes the verdict
from the same readings, which is why it is driven first. No page was edited: a
task-only slice, the eighteenth page driven end to end.
