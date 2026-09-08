# ADR-155 — The instrument in the measurement

**Status:** accepted · **Date:** 2026-09-07

## 0. How this one was found, including the part that reflects badly on me

I set out to close the oldest item on the open list — the twelve accepted layout
spills on `selection-log` and `survey-design`, carried since ADR-103 — and could
not reproduce a single one. Four attempts: load the page and measure; press
every button; fill every field the way the harness does and press again; walk
the ancestor chain of anything overflowing. Nothing overflowed at 390 px in any
state I could put the page in. The harness had reported thirty-eight of them on
the same page minutes earlier.

I then did the work against **a clone forty-two ADRs stale**, and was one call
away from republishing `selection-log` and `survey-design` on top of ADR-128 and
everything after it. The stale clone was caught only because the live artifact
came back carrying CSS my tree had never seen. That is the second time in one
session I inherited "my working copy is current" without checking it — the same
defect ADR-105 is about, committed by the person who wrote ADR-105 down.

It is recorded here because the finding below is the same shape, and a document
that names that shape in a tool while hiding it in its author is worth less.

## 1. Twelve findings, and a fix nobody could see land

`verify_findings.py` was **red on this tree** before this slice:

```
FAIL  no baseline entry has been fixed without being written off
      selection-log.html | spill15px | +   (accepted 12, now gone)
      selection-log.html | spill15px | 0   (accepted 5,  now gone)
      ... twelve entries
```

Five of those were a real layout defect, and **ADR-128 fixed it on 2026-09-02** —
`.rowlist` given `minmax(0,1fr)` instead of the implicit `auto` track, `.row2`
allowed to wrap. Correct, and diagnosed correctly. It has been in the tree for
five days and twenty-six ADRs, and the baseline never noticed, because the
number it was meant to move had stopped being a property of the page.

## 2. The counter was the page's third author

`tools/harness.py` keeps a counter so every fill is a different value; a field
filled with what it already holds changes nothing, and the walk was once
reporting live fields as wired to nothing for exactly that reason. The counter
was a **module global**, shared by every page in the run.

So `survey-design` driven **alone** is filled with `harness-3`. Driven as page
35 of 41 it is filled with `harness-378`. Three characters wider — and a row
that fitted in 390 px stops fitting.

The receipt is in this repo's own files. The same two pages, unchanged, at three
different answers:

| | `selection-log` | `survey-design` |
|---|---|---|
| committed `harness_ledger.json` (pre-ADR-128) | 38 | 0 |
| the working-copy ledger of 08-31 | 38 | 23 |
| a run on this tree today | 0 | 0 |

Nobody edited those pages between the second row and the third.

Two consequences, and the second is the worse one:

- **A finding you cannot reproduce by opening the page it names never gets
  fixed.** It gets accepted, and an accepted finding is one nobody reads again.
  Twelve of them outlived the defect by twenty-six ADRs.
- **Whether the kit was green depended on the order the pages happened to be
  walked in.** With `-j2` that order is thread scheduling, so it was not merely
  order-dependent — it was flaky.

### The fix

`threading.local()`, reset at the top of each page. Thread-local rather than
merely reset per page: the run drives two pages at a time, so a plain global
assignment would have left the two walks clobbering each other — the same leak,
harder to see, and only under `-j2`. **A fix that is correct when nothing else
is running is not a fix for a tool whose whole job is forty-one pages at once.**

## 3. Why the report sent three ADRs to the wrong place

The other half of why this took so long. The spill report read:

```
spills 15px sideways [step_val:0 1]: div.row2 w=372, div.row2 w=372
```

A 372 px box inside a 390 px page. That is not too wide for anything. The number
is true and it points nowhere. Two faults, both easy to repeat:

- **Document order is not blame order.** Every ancestor of an overflowing child
  also overflows, so the first two matches in document order are the outermost
  containers — innocent by construction, and exactly what got printed. The
  candidates are the elements whose *parent still fits*.
- **A width alone cannot be judged.** `w=372` looks fine until you know the box
  starts at `x=33`.

It now names the outermost element whose parent fits, with its span and overrun:

```
spills 37px sideways [action_btn:0 Add individual]:
  div.row2 x=33..427 (+37 past 390) "harness-2harness-3 · un"
```

One reading of that sentence gives the diagnosis ADR-102, ADR-103 and ADR-128
spent three passes converging on: the row starts 33 px in, its `.rowlist` track
is a correct 324 px, and the row is 48 px wider than the track it lives in — so
nothing was squeezing it. A finding that has to be reproduced before it can be
understood is a finding that will be accepted instead.

## 4. Section L, and why section F did not catch this

`verify_harness_matrix.py` gains a twelfth section, **six checks** (71 → 77):

- **L1** a page measured after another page measures the same
- **L2** and the fixture really was driven both times — so L1 cannot be
  satisfied by a harness that has stopped filling anything at all
- **L3** the counter restarts at one for each page
- **L4** two walks running at once do not share it
- **L5** the accounting still holds
- **L6** no module-level state in the harness is written to during a run — so
  the *next* cross-page counter is caught before it can invent a defect

Section F has claimed determinism since ADR-109 and passed every run. It
compares bucket counts on a fixture **with no text input**, so the counter never
advanced, and nothing anywhere compared what the harness types.

> **A promise checked only where it cannot be broken is not checked.**

That sentence is the transferable part of this ADR. Section F was not wrong; it
was aimed at the safe half of its own claim, which is the most comfortable way
for a suite to be green.

Three mutants join the catalogue (15 → 18): remove the per-page reset → **L1**;
make the reset a no-op → **L1**; make the counter a plain global again → **L4**.

### Two of the three survived the first version of my own checks

Worth writing down, because both failures are the same shape as the bug the
section is about, and both were invisible: the checks passed.

**L1 was a comparison, and comparisons inherit the pollution.** The first
version ran the fixture, ran a filler page, ran the fixture again, and compared
the two. Delete the per-page reset and it still passed — because sections A–K
have already driven dozens of fixtures in the same thread, so *both* runs start
from a high counter, both spill, and the two agree. Right about what it
compared, wrong about what the comparison meant.

The repair is to stop comparing. What is true of a page whatever ran before it
is that its **first fill is `harness-1`**. The fixture now always overflows when
filled and the spill message carries the value typed, so L1 reads the harness's
own report and asserts an absolute fact rather than a relative one.

**L4's two threads never overlapped.** It had each thread reset, sleep, then
take a number, and asserted both got 1. Making the counter a plain shared global
still passed: two threads started back to back do not interleave — the first
finished reset-and-tick before the second had begun, so both read 1 while
sharing one counter. A concurrency check whose threads never overlap tests
nothing, in the way hardest to notice.

It now uses a `threading.Barrier`: both walks reset, and only then does either
take a number. Sharing one counter, the second gets 2. Canaried both ways —
thread-local gives `[1, 1]`, a plain object gives `[1, 2]`.

The mutation catalogue is the only reason either was found. A check nobody has
watched fail is a check nobody knows the shape of, and I had just written three.

## 5. Results

| | before | after |
|---|---|---|
| discovered | 3,699 | 3,699 |
| driven | 2,367 | 2,367 |
| dead | 1 | 1 |
| invariant breaks | 0 / 38 / 61 depending on the run | **0, on every run** |
| accepted debt | 13 distinct / 63 occ / 3 pages | **1 / 1 / 1** |
| matrix checks | 71 | **77** |
| mutants | 15 | **18** |
| `verify_findings` | **RED** | 12 / 12 |

No coverage moved. No page was edited: ADR-128 had already fixed the only real
defect among the twelve.

The kit's entire defect register is now one entry — `stand-sheet`'s
**"📷 Add photos"**, the one control in 3,699 affordances wired to nothing.

## 6. The pattern, and the sharper name for it

ADR-040, ADR-105, ADR-106, ADR-109, ADR-110, ADR-111 and ADR-128 were the same
shape: *a check right about what it matched and wrong about what the match
meant*. ADR-111 sharpened it to a tool contradicting itself.

This one deserves its own name. The instrument was not mistaken about the page.
**The instrument was in the measurement.** Its own accumulated state — how many
fields it had filled that run — changed what it found, and the difference was
reported as a property of the page. Every layer above behaved correctly: the
accounting balanced, the ratchet held, the baseline was faithfully maintained.
They were all faithfully maintaining a fact about the harness.

The defence is not a cleverer check. It is that **any state a tool carries
across the things it measures must be reset between them, and something has to
assert that it was.**

## 7. Still open

- `stand-sheet`: "📷 Add photos" — the one dead control in the kit.
That last one was the only one. `_TICK` was found by chasing a symptom, and "we
fixed the one we tripped over" is not an audit — so the rest were checked. An
AST walk of `harness.py` finds three module-level containers (`VIEWPORT`,
`KINDS`, `EXCLUDED`), **none written to at runtime**, and no `global` statement
anywhere. They are configuration, and configuration is not modified while the
walk runs.

**L6** makes that a standing rule rather than a one-off audit: no module-level
name in `harness.py` may be rebound with `global`, mutated through
`append`/`update`/… , or written by subscript. Anything that must change during
a run is per-page, which in a thread pool means thread-local — `_FILLS` is a
`threading.local()` and is exempt by construction, which is the entire point of
it being one. Canaried by reintroducing a module-level list and confirming L6
names it.
