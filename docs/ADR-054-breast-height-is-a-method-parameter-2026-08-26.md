# ADR-054 — Breast height is a method parameter

**Status:** accepted · 2026-08-26

## The defect

`stand-sheet` said, in four places:

> Measured at **1.37 m**, uphill side.

Stated as a constant. It is not one. **1.37 m (4 ft 6 in) is the North American
convention; most of the world measures at 1.30 m**, and Australia, New Zealand,
India, Malaysia and South Africa historically used 1.40 m.

Seven centimetres of stem is not a rounding difference on a tapering trunk, and
DBH does not stay put once measured: it is **squared** into basal area and QMD,
and **raised to 1.605** in Reineke's SDI. Two stand sheets recorded on different
continents are not comparable, and the export said nothing about which height
either used.

The page already refuses to export an expansion factor without a minimum tallied
diameter — *"expansion factors are meaningless without it"* — for exactly this
reason. It applied that rule to one method parameter and silently fixed another.

## What changed

Breast height is now a control: **1.30 m** (most of the world), **1.37 m**
(N. America), **1.40 m** (historic AU/NZ/IN/MY/ZA), defaulting to 1.37, mounted
beside the minimum tallied diameter and **written into the export line**. The
prose points at the control instead of asserting a number, and the slope rule is
stated as the kit's choice — the uphill side is the highest point of ground
touching the trunk; some protocols average the high and low sides, which is a
different number on a steep slope.

## Three testing defects this turned up

**A frozen constant broke on a legitimate change.** `verify_ss` asserted
`#geoEntry .fek-row == 3`. Adding a control failed it — an assertion that a
legitimate change breaks is not a test, it is a future ignored failure
(ADR-041). It now names the parameters the block must carry (design, breast
height, minimum DBH) rather than counting rows, and a companion check asserts
the rectangle swap brings in length and width and takes the radius away.

**A control nothing records is decoration.** The first version of the check
asserted only that the dial existed. Two canaries — deleting the export line,
and hardcoding `"1.37 m"` in place of reading the field — both survived. The
check now reads the **export**, flips the dial to 1.30 m, and requires the export
to follow.

**A check that raises has told you nothing, and hides the ones after it.** The
canary that removed the control crashed the suite: an unguarded `.click()` on a
control that is not there throws, aborting the run before the two checks that
name it could fail. Guarded, the same canary now produces three clean failures.

**And a claim-arithmetic check was pinned to prose I moved.** `verify_claims_math`
grepped `Measured at ([\d.]+) m on the uphill side` to verify 1.37 m ≈ 4.5 ft.
That check was right and its anchor was gone. It now reads the dial option that
states an imperial equivalent — the one place on the page where two units claim
to be the same length — and recomputes rather than pins: every option's label
must agree with its own value, and 1.30 m must be among them.

## Still open

- 32 claims remain on the `audit_claims` worklist. The 30–300 plate-count window
  and soil-bench's 65–66 °C thermophile ceiling are the next two that look
  citable rather than unsourced.
- `collection-sheet` and `stand-sheet` still publish figures the repo
  contradicts (ADR-050) — and stand-sheet's published copy now also predates
  this change.
- `fungal-characters` remains blocked on the publish gate's duplicate branch.

## The rule this adds

> A number that changes what the measurement means is a method parameter, not a
> constant. Offer it, record it in the export, and let the prose point at the
> control instead of repeating a number it cannot keep true.

## Sources

- *Diameter at breast height* — regional conventions (US 4½ ft / 1.37 m; ~1.3 m
  in many countries; historic 1.4 m in AU, NZ, Burma, India, Malaysia, South
  Africa; slope and swelling conventions).
  https://en.wikipedia.org/wiki/Diameter_at_breast_height
