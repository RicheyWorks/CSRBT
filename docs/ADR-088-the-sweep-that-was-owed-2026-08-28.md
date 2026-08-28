# ADR-088 — the sweep that was owed, and what it found

*2026-08-28. Status: accepted. Tests the prediction in
[ADR-087](ADR-087-a-number-that-was-a-coin-flip-2026-08-28.md); another instance of
[ADR-061](ADR-061-the-survivor-that-was-already-dead-2026-08-27.md), committed in the tool written to
find the first one.*

## 1. The prediction, and how badly it lost

ADR-087 said: *"I expect few, on no evidence beyond one instance. Falsifier: a sweep turning up more of
them. That sweep is the next slice, and it should be run before the expectation is repeated anywhere."*

The sweep finds **28 (figure, precision) pairs** on an exact rounding tie, in four of the five
recorded sessions. "Few" was wrong, and it was wrong in the way a guess from one instance usually is.

Two things separate the 28 from the one ADR-087 fixed, and both matter more than the count:

- **26 of the 28 are exactly representable.** ADR-087's figure was decided by IEEE — the nearest double
  to 0.575 is 57.49999999999999, so the tie was hidden. These are not hidden. They are ties in the
  number itself, where the displayed digit is decided purely by which rounding rule runs.
- **None of the 28 is claimed to be displayed.** Binding a fixture value to a call site means resolving
  `f.meanStructural` or `a.observed` through page JavaScript, and the naive version — match on key name
  — reports `p`, `q` and `observed` against every page that happens to use those names. That is a fact
  about names, not about data flow (ADR-077). So `audit_ties.py` reports the question, like
  `audit_claims` does, and says so in its own output.

## 2. The tool did it too, before it shipped

The first draft pinned the precisions to sweep at: `[(100,0), (100,1), (1,1), (1,2)]` — the set I
happened to have in mind. Reading the pages instead:

```
fmt      0,1,2,3,4    toFixed  0,1,2,3,4,5,6
```

Four precisions the kit formats at were not being swept, and the pinned list reported **12** pairs
where the derived one reports **28**. A sweep that quietly skips a precision is exactly ADR-061 — *a
silent exclusion is worse than a wrong one, because nothing in the output disagrees with it* — and it
was a pinned constant standing in for a value computable from the inputs, which is ADR-041. Both
committed inside the tool written to check other people's numbers, and caught only by asking the tool
where its own list came from.

The list is now derived, the sweep prints the set it used, and `verify_ties` reads the pages
**independently** to check the sweep covers them — a second opinion rather than the tool agreeing with
itself (ADR-068). Pinning the old list back makes it fail and name the gap:

```
FAIL  the sweep covers every precision the pages actually format at   got: [3, 4, 5, 6]
```

## 3. The live one: a trap for the next check somebody writes

`ecology-lab.html` renders carrying capacity as `fmt(g.K, 0)`, and the shipped session has
`"K": 138.500000`.

```
the page shows              139        (toLocaleString, half away from zero)
Python's round(138.5) gives 138        (half to even)
```

Nothing asserts K today, so nothing is wrong today. What exists is a **trap**: the next check written
in Python against that tile would compute 138, disagree with the page, and both numbers would look
plausible. The kit has hit the neighbouring version of this twice —
[ADR-068](ADR-068-a-check-that-compared-a-number-with-itself-2026-08-27.md), a check comparing a number
with itself, and ADR-087, where I nearly wrote the tie test using Python's rounding on the very case
under test.

So the rule is written down once, in `_kit.as_page_shows`, with the measured disagreements in its
docstring, and the three readers borrow it instead of each choosing. `verify_engine_sessions` no longer
carries its own copy: two implementations of a rounding rule is the frozen-constant problem with a
function in place of a number — they agree until one is edited.

`verify_ties.py` is new, **19 checks**, each rule with a control: a rule that always rounded up passes
four of the five rounding checks, so one case that must *not* move is checked beside them; the tie test
is checked against a value that is not a tie; and the claim that Python disagrees is checked *both
ways*, since a Python that disagreed everywhere would mean something different.

## 4. What the two records together actually say

ADR-087 fixed a figure by moving it from zero decimals to one. That was right for that figure and is
**not a rule** — three of the 28 are ties at one decimal place. A tie is a property of the pair
*(value, precision)*, not of a precision, and "add a digit" only ever moves the boundary.

The general form is the one the kit already believes: a number displayed at a precision where it is a
tie is not a reported figure, it is a rounding rule's output. Either display it where it is not a tie,
or make sure every reader of it rounds the same way. This slice does the second, once, for the whole
kit.

## 5. A traceback nobody raised

The kit run that added `verify_ties` also printed something new:

```
1 job(s) exited 0 while printing a traceback -- green is not the whole
story for these. An exception nobody raised is still an exception.
  verify_offline_slice   asyncio.exceptions.CancelledError
```

`verify_offline_slice` case (b) simulates a font request that **hangs** — the one-bar-of-signal case
ADR-031 exists for — with a route handler that returns without fulfilling, aborting or continuing. That
is correct: the hang is the point. What was wrong is that the page was then closed with the handler
still in flight, so playwright's dispatcher cancelled it and asyncio printed the trace. The suite scored
207/207 and exited 0 throughout; it has presumably been doing this for a while, and only the runner's
own guard, built in an earlier slice, made it visible.

Located by probe rather than by reading: resolving those two routes took the traceback from 1 to 0,
three runs each way, which is what identified case (b) out of the four. The fix keeps the hang and
settles the routes deliberately at teardown.

One thing I nearly wrote up as a second finding and did not: under the probe the case still scored
207/207 with the requests *aborted* instead of hanging, which looks like a fixture that cannot tell two
implementations apart (ADR-039). It is not. Abort and hang differ only against a page whose stylesheet
blocks paint; on correct code both pass, and discriminating power against the fault is what the canary
tests. The case is sound — but it now also checks that a request was intercepted at all, because if the
route never fires the page paints for the wrong reason and nothing says so. **208/208.**

**The next prediction, and its falsifier.** The 28 are unbound — nothing yet says which are displayed.
Binding them needs the page rather than a key name, which is a real piece of work and probably a
rendering pass with the browser the suites already drive. I expect **the displayed subset to be small,
and I am explicitly not repeating the mistake of putting a number on that** after the last guess lost
9-to-1. **Falsifier: a rendering pass finding a displayed tie other than the one already fixed.**
