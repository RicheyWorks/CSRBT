# ADR-154 — The ethogram, recorded whole

**Status:** accepted · **Date:** 2026-09-07 · **The one page in the kit whose product is a measurement of *time*, and no task had ever run a session on it: 5 of 16 fields, 3 exports unread, 2 that had never produced anything. Driven against a clock the harness steps, every duration is exact — and the exact numbers found two things wrong. 16 of 16 fields, 5 of 5 outputs held, and the page now reports 06:20 where it used to report 06:00.**

## The page that had never been run

`ethogram.html` is behaviour sampling: the four sampling rules, the three
recording rules, a stopwatch, a time budget, event rates, a transition matrix
and Cohen's κ. Its only task drove the κ calculator and two of the design chips
— 5 of 16 fields, the worst ratio in the kit. **Nothing had ever started a
session.** Its "Copy log CSV" and "Copy budget CSV" were two of ADR-153's
nineteen silent buttons, and they were silent for the honest reason: they say
*"Nothing recorded"*, and nothing ever had been.

## Time, entered

A time budget is a measurement of wall-clock time, and a task cannot assert a
wall-clock number. The page reads `Date.now()` at every press, so the harness's
own clock control answers it: **freeze the clock, then step it.**

    set-clock 09:00:00 · Start
    set-clock 09:00:20 · forage      set-clock 09:03:50 · rest
    set-clock 09:01:35 · vigilant    set-clock 09:05:20 · vigilant
    set-clock 09:02:20 · aggress     set-clock 09:05:50 · alarm
    set-clock 09:02:35 · forage      set-clock 09:06:20 · Stop
    set-clock 09:03:20 · alarm
    set-clock 09:03:50 · out of sight

Every duration is then exact and the whole budget is an oracle:

    forage        02:30   45.5% of observed   2 bouts   mean 01:15
    vigilant      02:00   36.4%               2 bouts   mean 01:00
    rest          01:00   18.2%               1 bout    mean 01:00
    out of sight  00:30   excluded from the denominator
    alarm   2  0.364 / observed min  21.8 / h
    aggress 1  0.182 / observed min  10.9 / h   (over 5.5 observed min)

`set-clock` was in the manifest for freezing a date stamp. Used as a *stepper*
it turns a stopwatch into an instrument a task can hold, which is a use nothing
in this kit had made of it.

## The two things the exact numbers found

**The elapsed tile was not elapsed.** It showed `observed + out of sight` — the
time that is *in a state*, not the time the session ran. They differ by however
long the clock runs before the first state is tapped and after the last is
closed, which on a real session is the time it takes to find the animal. The
stepped clock made the gap exact: **the session ran 06:20 and the tile said
06:00.** It now shows the elapsed time, and names the difference:

> **00:20 of the session is in no state.** The clock was running before the
> first state was tapped, or after the last one was closed. It is neither
> observed time nor out-of-sight time, and nothing below is computed on it.

**A transition is adjacency, not order.** Out-of-sight segments are dropped
before the pairs are taken — rightly; "out of sight" is not a behaviour — and
dropping them *closed the gap*, so the state before a disappearance and the
state after it were counted as one following the other. **This session reported
four transitions where three were observed**, and the invented one — forage →
rest across 30 s of nothing — was exactly the kind of row a transition matrix is
read for. Pairs that are not adjacent in time are no longer counted, and the
page says how many it dropped and why.

Both are the page's own subject matter. It is a page about the difference
between what you measured and what you can claim.

## What the session closed

    ethogram.html   5 -> 16 of 16 fields entered   (100%)
                    3 unread + 2 silent -> 5 of 5 outputs held
    the kit         405 -> 416 of 520 fields (78% -> 80%)
                    42 -> 39 unread outputs, 21 -> 26 held, 19 -> 17 silent
                    63 -> 65 outputs that hand something over

Three worklists, one page. The two silent exports are silent no longer because
the session gives them something to hand over — which is the mechanism ADR-153
predicted: *"closing that gap will turn some of them into findings here."* Both
now emit and both are held, along with the session sheet, the ethogram pack
export and the AI prompt.

The task also folds in the reliability check the session is designed to be
judged by: two observers' ten scans, Cohen's κ **0.722** from 80% raw agreement
against 28% expected by chance, and the confusion matrix. **68 confirmed
expectations, 0 refuted.**

## Two elements the audit found because the session ran

`audit_readable` measures the elements a page WRITES that `read-report` cannot
see, and it had never seen this page's `clock` or `nowState` change, because
nothing had ever started the stopwatch. Running a session made both of them
written elements, and the audit said so the same day. Both are declared
furniture, with reasons: the clock is the recorder's own display of a number the
budget now reports properly, and `nowState` is which state is open and for how
long — the control surface telling the observer what the recorder thinks is
happening, not the record. What it becomes is a segment, and segments are in the
budget, the transitions and the log CSV, all of which the task now holds.

That is the ratchet doing exactly what it is for: a page that grows a figure the
harness cannot read fails the day it does, including when what grew it was
finally driving the page.

## Held

- **The stepped clock is not a real session.** It reproduces exact durations and
  nothing about an observer's reaction time, a mis-tap, or the scan timer firing
  — which under a frozen clock never fires at all, so instantaneous and one-zero
  recording are still driven only by their design chips and not by a run.
  Continuous focal sampling is what this session is.
- The transition fix counts a pair only when `t1 === t0`. Two segments separated
  by a gap the recorder did not create — there is no such path today — would
  also be dropped, which is the right answer for the same reason.
- The budget's "in no state" line is a report, not a correction: the page does
  not guess what the animal was doing before the first tap, and says so.
- 39 outputs on 15 pages are still unread and 17 buttons still silent. The
  silent ones are on the pages `entry_reach` still names.
