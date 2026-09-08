# 2026-09-08 — ADR-160: the farm scout, recorded whole

**The kit's most-neglected data-entry page (5/15 fields, both exports unread).
Now 15/15, both exports held. The kit crosses 90%.**

## Changed — `tools/tasks/page-farm-scout-science.json`

58 → 89 steps, 68 → 117 confirmed expectations. The existing scenario is kept
verbatim (ten-stop scout averaging 3.6 pests/plant, var/mean 2.54; germination
83% → 65% → 45%; one rotation conflict), so its assertions hold, and the ten
never-entered fields are driven around it: the pest name, the field/observer/date
stamp, the action threshold, five pollinator tallies (four defaults + one added
by hand → 11 visits, effective types 4.3, evenness 0.91), and the four remaining
rotation season-pickers. Both exports are then read and held against an oracle —
the field-day report and the CSV — with the diversity, dispersion, germination
percentage and every export line computed the page's own way (Shannon/evenness,
`Math.round`, `famLabel`).

## Numbers

    farm-scout.html   5 -> 15 of 15 fields entered   (100%)
                      68 -> 117 confirmed, 0 refuted
                      0 -> 2 exports read and held
    the kit         461 -> 471 of 521 fields          (90%), 17/27 whole

## Held

- The rotation family selectors count one field each (a picker per season), so
  completing bed two added a rotation line to both exports — folded into the
  oracle, not worked around.
- Pollinator tallies are reached by host index (`@control:poGrid#0`) because a
  tally button's label carries its live count.
- No page was edited — a task-only slice, the tenth page entered whole.
