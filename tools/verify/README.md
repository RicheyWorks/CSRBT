# Verifying the kit

    python3 tools/verify/run_all.py

That runs every audit and every page suite — **27 jobs, 1,454 checks** — and exits
non-zero if anything fails. On a laptop it takes a few minutes; `-j 4` speeds it up
at the cost of four browsers at once.

    python3 tools/verify/run_all.py --audits    # the five kit-wide audits only
    python3 tools/verify/run_all.py --suites    # the per-page suites only
    python3 tools/verify/run_all.py -v          # full output from anything that failed

## What you need

    pip install playwright
    playwright install chromium

Nothing else. There is no test framework here on purpose: the kit's standing
constraint is that it has no build step, and adding one to run the tests would
defeat the constraint the tests exist to protect. Every suite is a plain script
that prints `n/m` on its last line and exits non-zero if `n < m`.

## What is being checked

**Audits** run across all 33 pages at once and are in `tools/`, not here, because
you will want to run them on their own while working:

| audit | asks |
|---|---|
| `audit_targets.py` | is anything interactive smaller than 44 px at phone width |
| `audit_focus.py` | can every control be reached by keyboard, does focus show, is it named |
| `audit_contrast.py` | does every painted colour pair clear WCAG AA |
| `audit_print.py` | does the printed page still contain the document, and what does it cost in ink |
| `audit_claims.py` | which numbers in prose carry no visible provenance |

`audit_claims.py` is a **finder, not a gate**. It always exits zero and prints a
worklist, so `run_all.py` names it but does not run it — a job that cannot fail
tells you nothing about whether the kit is green. Run it on its own.

**Suites** are one per page or per slice, and check behaviour: that a control
records what you entered, that a statistic comes out right on a known input, that
the page refuses to assert what it cannot source.

## Two conventions worth knowing before you add one

**Drive the widget, not the field.** The Field Entry Kit replaced bare inputs with
composed controls that write through to hidden fields. Setting the hidden field
works for a value the page merely reads — but anything whose side effect lives in
the widget's `onchange` (a tell, a badge, a warning) is skipped silently. `_kit.py`
has `pick()` and `setstep()`; use them. `push()` is there for the read-only case
and says in its docstring when it is the wrong tool.

**Assert the invariant, not the count.** `verify_eco` once asserted the hub had
exactly 14 cards in 3 groups and a nav of exactly 11 chips. The kit grew, and the
suite failed on twelve pages at once for no fault of any of them — so it was
ignored, and then it was dead. It now checks that no group is empty, that every
card links to a page that exists, that the nav is identical everywhere, and that
the count the hub *states* matches the cards it actually has. Those stay true as
the kit grows, and the last one catches a real bug the frozen count never could.

## If a suite goes stale anyway

`verify_cs_science.py` was called `verify_fun.py` and pointed at
`collection-sheet.html` the whole time, which is why nobody noticed when it stopped
running altogether. Name a suite after the page it tests.
