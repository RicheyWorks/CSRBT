# ADR-087 — the figure two documents agreed on by accident

*2026-08-28. Status: accepted. Extends the binding in
[ADR-052](ADR-052-binding-the-docs-to-the-engine-2026-08-26.md); another instance of the scope problem
in [ADR-072](ADR-072-ninety-eight-checks-that-were-never-allowed-to-speak-2026-08-27.md).*

## 1. Off the publish ladder, onto the claims worklist

Five slices of publish-state work left the pile clean and every entry provenanced. The other standing
worklist is `audit_claims` — thirty numeric claims across nineteen pages that the finder cannot source.
Working it started with the one claim that is about **this engine** rather than about biology:

> "80% of keys survive a generation, but only 57% of the physical nodes — the gap is the price of path
> copying."

`verify_engine_sessions` already binds three links for that sentence:
`engine → ecology-lab-session.json → the page's inlined copy → the rendered prose`, and its link C
**bans** a hand-written literal inside `ecology-lab.html`, so the figures can only be interpolated.

## 2. The ban had a scope of one file

Two other documents write the same sentence with the numbers typed in by hand:

| file | figures | bound by |
|---|---|---|
| `ecology-lab.html` | interpolated | link C |
| `ECOLOGY-FIELD-GUIDE.md` | typed | **nothing** |
| `ecology-field-guide.html` | typed | **nothing** |

The third of those is a published page a reader opens. This is ADR-072's shape again — *the fix that
names one caller does not cover the next one somebody writes* — and it is worth naming that the failure
recurred inside the very suite built to prevent it, one file over.

The extension is a **binding, not a ban**: prose is allowed to quote a figure, so link D requires that
wherever the pair appears the digits are the digits the page renders. Dated records — ADRs, changelogs,
audits — are exempt by an explicit prefix list, because a record reports what was true on its date and
must not be rewritten when the engine moves. Seeding the drift in the real tree makes it fail and name
the file:

```
FAIL  every quote of the pair matches what the page renders (80% / 57.5%)
      got: [('ECOLOGY-FIELD-GUIDE.md', '80', '57')]
```

## 3. And the number they agreed on was a coin flip

Measuring the agreement is what turned up the real defect. The session's own literal is
`"meanStructural": 0.575000`. In decimal that is **exactly 57.500** — a rounding tie at the zero
decimal places the page displayed. The page showed 57, and so did every document quoting it, and they
agreed **only because the nearest double to 0.575 is 57.49999999999999**:

```
0.575 * 100          -> 57.49999999999999      (the double)
Decimal("0.575")*100 -> 57.500                  (the number)
toLocaleString(57.49999999999999, 0 dp) -> "57"
toLocaleString(57.5,               0 dp) -> "58"
```

Had the value been one a double can hold exactly, the page would have rendered **58** and both guides
would still have said **57** — and nothing in a green kit would have disagreed. A number displayed at a
precision where it is a tie is not a reported figure; it is a coin flip between two implementations,
and this one happened to come up the way the prose was written.

The fix is not a tolerance and not a chosen rounding mode. It is to stop displaying the figure at a
precision where it is a tie: the seven heredity renderings on the lab page now use one decimal place,
which `toLocaleString` drops when it is not needed. **80% stays "80%"; 57% becomes "57.5%"** — the
value the engine actually produced, and no tie to break. Both guides now say 57.5% too, and link D
holds all three together.

Two checks state it, one of which fails if the tie ever returns:

```
PASS  the structural figure is NOT displayed at a precision where it is a tie
PASS  ...and it WOULD have been at the 0 dp this page used to render -- the
      agreement across the kit was a float-representation accident
```

The tie test reads the JSON's **decimal literal**, not the double, because reading the double is how
the tie hid in the first place. And `displayed()` writes out JavaScript's half-away-from-zero rounding
rather than borrowing Python's `round()`, which is half-to-even and would disagree on exactly the case
under test — a check using different arithmetic from the page would be a second source of truth
(ADR-068).

`verify_engine_sessions` 18 → **26 checks**. `ecology-lab` and `ecology-field-guide` republished and
stamped; 39 current, 0 behind.

## 4. What this says about the other twenty-nine

The claim that started this was on the worklist as *unsourced-looking*. It was sourced — bound through
three links to a Java run — and it was still wrong in a way no source could have fixed, because the
defect was in how the sourced number was displayed. **A finder that asks "is this cited?" cannot ask
"is this the number?"**

**The next prediction, and its falsifier.** Any other figure the kit displays at zero decimals whose
exact decimal value ends in .5 is the same coin flip. **This one was found, not swept for**, and I have
not looked at the other session artifacts or the other pages — so the honest statement is that I expect
few, on no evidence beyond one instance. **Falsifier: a sweep turning up more of them**, which would
make this a class rather than an instance, and would argue for the rule living in the formatter rather
than at seven call sites. That sweep is the next slice, and it should be run before the expectation is
repeated anywhere.
