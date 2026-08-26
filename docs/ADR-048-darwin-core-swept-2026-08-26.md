# ADR-048: The last module, and a 55-kilometre error nothing could see

**Status:** Accepted and implemented — `tools/verify/verify_dwc.py` (138 → 147 checks), three new coordinate fixtures, every comparison in the new block None-guarded.
**Date:** 2026-08-26
**Deciders:** Richmond
**Follows:** ADR-045, ADR-046, ADR-047

---

## Context

ADR-047 named DWC as the one shared module still unswept, rather than leaving it implied. This closes
it. Darwin Core is the export layer: what it gets wrong leaves the kit and lands in somebody else's
dataset.

**DWC scored 56%.** Four survivors, and the first one matters more than the number.

## `dp >= 0` → `dp > 0`

`dp` is the number of decimal places in the coordinate as the user typed it, and the precision term
is `0.5 × 10⁻ᵈᵖ` degrees converted to metres. A coordinate written **`45`** — no decimal point — is
precise to half a degree.

| coordinate | precision term | included under `dp > 0` |
|---|---|---|
| `45` | **55,270 m** | **no** |
| `45.1` | 5,527 m | yes |
| `45.12` | 553 m | yes |
| `45.1234` | 5.5 m | yes |

Change one character and a location good to **55 kilometres** is published with the uncertainty of the
GPS alone — often a tidy single-digit number. That is the worst shape an error can take in an
occurrence record: not a missing value, not an obvious absurdity, but **a plausible small number
standing where a huge one belongs**, in the exact field a downstream user consults to decide whether
the record is fit for their analysis.

`verify_dwc`'s 138 checks did not notice. The Python recomputation beside them is correct and
independent — it was never the problem. **Every one of its fixtures carried at least two decimal
places**, so `dp >= 0` and `dp > 0` agreed on all of them.

Three fixtures now cover it, including `45.1` / `-93` where `dp = min(1, 0) = 0` — because the coarser
of the pair is what governs, and a mixed-precision pair is how this arrives in real data.

The magnitudes are also asserted directly, not only through equality: a whole degree must exceed
50 km, two places must sit in the hundreds of metres, and the ratio between them must be large enough
that the check can tell the precision term is *present at all*.

## Two survivors closed by proof rather than by a test

**`window.crypto && window.crypto.getRandomValues` → `||`.** In any browser `window.crypto` exists, so
`||` short-circuits true and behaviour is identical. The `&&` guards an environment where crypto
exists *without* `getRandomValues`, which nothing this suite can run in reproduces. Equivalent.

**`m > 0.5` → `m > 0.55`.** This one is provable rather than merely untested. The precision term is
`0.5 × 10⁻ᵈᵖ × 110540`, so `m` takes only the discrete values 55270, 5527, 552.7, 55.27, 5.527,
0.5527, 0.05527 … **It cannot land between 0.5 and 0.55 for any integer `dp`, at any latitude** —
`degLat` is a constant and the `max()` always picks it over `degLon`.

That is a stronger statement than "no fixture hits it", and it is the difference between a survivor
that is closed and one that is merely parked. The suite now asserts the value set skips that window,
so if anyone changes the constant the claim fails rather than quietly stops being true.

## A crash is a kill, and a bad report

The first version of the whole-degree check crashed: when the precision term is dropped, `uncertainty`
returns `None`, and `u0 > 50000` raises a `TypeError` that takes the suite down.

The sweep counts that as a kill — correctly, a suite that dies has not passed. But it is a bad report
for a person: the output says `TypeError` and not *which check* failed. Every comparison in the new
block is None-guarded, and the same mutation now produces **six clean failures naming themselves**
instead of one traceback.

## The new fixtures made an old flake reappear

The suite passed alone and **timed out in `run_all`**. Three more coordinate cases is more page work,
and under three-way parallelism the very first wait — for `DWC` to finish parsing — ran past its
20-second budget.

That is the worst kind of flake: it looks like a real failure, and it lands on whichever job happens
to lose the race. **A wait for a script to finish parsing is not a performance assertion.** It was
raised to 60 s, and the page-level default to 45 s. If the module genuinely stops loading, the suite
still fails — just not because three browsers were sharing a machine.

## Consequences

DWC 138 → **147** checks. All five shared modules are now swept: FEK 95%, GH 100%, KEEP and ORD
covered, DWC closed.

**The rule this leaves behind:** the fixtures that matter are the ones at the edge of the input's
*range*, not the middle of its *distribution*. Every coordinate anyone would naturally type to test
this has two or more decimal places. The one that breaks it is the one nobody types — and it is
exactly what turns up in a real dataset, typed by somebody reading a coordinate off a map.
