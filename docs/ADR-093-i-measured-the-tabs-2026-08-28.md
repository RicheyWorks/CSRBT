# ADR-093 — I measured the tabs

*2026-08-28. Status: accepted. Corrects the measurement in
[ADR-092](ADR-092-a-channel-nobody-had-rendered-2026-08-28.md), shipped an hour earlier.*

## 1. The number was wrong by two orders of magnitude

ADR-092 reported that seventeen of thirty-nine pages put text on paper that no screen shows —
**1682 lines, 328 carrying digits** — and called it the largest unexamined surface the kit had left.

The mechanism, read afterwards, is one line of CSS:

```css
@media print { .pane { display:block !important; } }
```

These pages are tab UIs. Printing opens **every tab at once**. So most of what I called "print-only"
was simply the tabs a reader had not clicked — content the page suites already check, a click away on
screen. My sweep compared print against the tab that happens to open.

Measured again with every tab visited first:

| | print vs the default tab | print vs every tab |
|---|---|---|
| pages | 17 | **1** |
| lines | 1682 | **11** |
| carrying digits | 328 | **2** |

`stand-sheet` 238 → 11; `releve` 164 → 0; `greenhouse` 161 → 0; `cp-bench` 133 → 0.

**A difference is only a channel if the other side cannot be reached.** I had measured a difference and
called it a channel.

## 2. What the eleven lines actually are

They are `#htCard` — the two-angle clinometer method — and the page forces it open in print on purpose,
with a comment saying why:

> The two-angle height method is toggled shut on screen to keep the sheet short, but its content is
> exactly what you need on paper, standing under the tree with no signal.

Both digit-carrying lines were checked by hand, since there are two of them and the kit's rule is that
arithmetic is checkable (ADR-041):

```
√(1 + 0.20²) = 1.0198  →  "1.02 times the horizontal", "overestimates by about 2%"   ✓
```

So the honest finding of ADR-092 and this record together is: **the print channel is one deliberate
card, and it is correct.** Not a surface with 328 unchecked figures.

## 3. What survives from ADR-092

The tool and the suite survive; the headline does not. Both now compare against every tab, and the
suite's method check is the gap between the two measurements:

```
PASS  visiting every tab is load-bearing -- it removes most of the difference
PASS  ...and it WOULD have looked like a channel against one tab only
```

That second line runs on three control pages. It asserts the *old* number — that comparing against one
tab makes each of them look like a channel — so the mistake is kept as a fixture rather than deleted.
A future version that stops clicking tabs passes every other check in the file and fails those two.
**11 checks**, up from 5.

`ecology-lab.html` stays in the controls with no such assertion, because it has no tabs and never
looked like a channel either way — its presence is about the tie work, which reads only its screen view.

## 4. The pattern, now five for five

Every slice in this arc has had one of these, and the shape is identical each time: something cheap to
check, assumed instead.

| | assumed | one command away |
|---|---|---|
| ADR-089 | which nudge direction can flip a tie | try both |
| ADR-090 | which page reads a fixture | drop the file in |
| ADR-091 | that the charts were canvas | count the canvases |
| ADR-092 | that a filename was free | `ls tools/audit_*.py` |
| here | that a hidden pane means a hidden channel | click the tab |

The measurements that were *hard* — 103 saved copies, 4149 checks, 258 tooltips — have all held up. The
ones that failed were the ones I did not think needed making. That is worth more than any of the
individual findings, and it is the reason this record exists rather than a quiet edit to ADR-092:
**a wrong number that has been published is a different object from a wrong number that has not.**

**The next prediction, and its falsifier.** ADR-092's real claim — that nothing had ever rendered these
pages' non-default tabs in a *print* context — is now settled and small. The open work is what it was
before the detour: the `audit_claims` worklist, twenty-nine science claims still to triage.
**Falsifier: none available for this record**, which is itself the point — it reports a measurement I
can repeat, not a prediction I can test.
