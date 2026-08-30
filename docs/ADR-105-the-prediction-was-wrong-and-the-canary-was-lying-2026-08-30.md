# ADR-105: the prediction was wrong, and the canary had been lying for a while

**Status:** Accepted (2026-08-30)
**Date:** 2026-08-30
**Deciders:** Richmond
**Builds on:** ADR-104 (a hole is not a failure), whose machinery this slice's
first new client uses, and ADR-099 (the prediction was wrong, and the reverse of
it was true) — which this repeats almost exactly.

---

## 1. The prediction, and how it failed

ADR-104 closed with a falsifiable claim: run the suite on the Windows host and
expect **64 of 64 jobs green**, with `verify_audit_frontend` at 19/19 — and if
it came back anything else, its 6/19 in the Linux VM was a real defect rather
than an environment artifact.

Measured on the host: **13 of 64 jobs green**, and `verify_audit_frontend` at
**6/19 — identical to the VM.**

The prediction did not fail at its edges. It failed at its premise. Fifty-one
jobs died on `ModuleNotFoundError: No module named 'playwright'` **on the host
too**: the Windows machine has no playwright either. The claim "the browser
suites run on the host" was carried forward from context and never checked, and
every number built on it — including the confident 64/64 — was decoration on an
unmeasured assumption. That is precisely the "two true facts joined by
plausibility" this kit wrote ADR-102 and ADR-103 about, committed one ADR after
naming it.

The falsifier was worth having. It fired, and it was right.

## 2. What that exposes about the kit's headline numbers

ADR-103 reported *"63 of 64 jobs green, 4461 of 4462 checks"*. Those numbers
cannot have come from either machine in this loop: the host runs 13 jobs and the
VM runs 14. They came from the autonomous polish container, which has playwright
installed.

So the kit's verification numbers have a provenance problem of exactly the kind
`publish_state.py` was written to fix for published pages: **nothing recorded
which environment a green run came from**, and three environments produce three
different meanings for "green". This ADR does not fix that; it names it, and the
counts ledger now at least stamps every entry with when it was measured
(ADR-104).

The practical unlock is small and worth doing: `pip install playwright` and
`python -m playwright install chromium` on the host turns 51 FAIL rows into real
results. Until then, a local run says nothing about the browser-tested behaviour
of this kit.

## 3. The canary that accused working code

`verify_audit_frontend` seeds a fault into a page, runs `audit_frontend` over it
as a subprocess, and asserts the finding comes back. It scraped the subprocess's
stdout for finding rows and **never looked at its return code**.

So when `audit_frontend` died on its import line, it emitted no rows, and:

- the twelve checks asking *"is this seeded fault caught?"* saw `[]` and reported
  **FAIL … got: []** — twelve accusations against a finder that never started;
- the seven checks asking *"is a clean page left alone?"* saw `[]` and reported
  **PASS** — false green, from the same emptiness.

6/19 was not a defect in the finder. It was nineteen checks about nothing, and
it has been printing on both machines for as long as neither has had playwright.
It read as a real defect precisely *because* it reproduced in two environments.

Fixed: the runner latches a reason when the audit exits non-zero with no rows,
and every check then reports `NOT VERIFIED` with that reason. The suite now says
**0/19** with nineteen declared holes — worse-looking and enormously more honest
than 6/19. `run_all` marks it `ok--` and names it in the holes section, which is
ADR-104's machinery meeting its first new client the day after it landed.

## 4. A stamp that meant different things on different machines

`verify_publish_drift` was 50/50 in the Linux VM and 49/50 on the host, failing
one check: *"the sha it wrote is the sha of the bytes publish.py would emit
now."*

The cause: `tools/publish.py` wrote its build output with
`open(..., "w", encoding="utf-8")` and no `newline=""`. On Windows Python
translates `\n` to `\r\n` on write; `publish_state.sha()` reads those files in
binary. So the same page, built on Linux and on Windows, hashes to two different
values — and the drift check, which hashes the bytes in memory (`\n`), agrees
with one platform and not the other.

This was not merely a failing test. **The seven pages republished in ADR-104
were stamped from the Linux VM**, so every one of those stamps is an LF hash;
regenerating the build on Windows would have produced CRLF hashes and reported
all seven as BEHIND — a false drift alarm, on pages that are in fact current,
caused by who last ran the tool. The ledger silently meant a different thing
depending on the machine.

Fixed at the cause: `publish.py` now writes with `newline=""`, so build output is
byte-identical on every platform and a stamp is portable. Verified in the VM —
the on-disk sha and the in-memory sha of `food-web.html` are now equal, and the
build carries zero `\r` bytes. The ADR-104 stamps are correct as recorded; no
re-stamping is needed.

## 5. Still open

- **51 jobs cannot run on either of Richmond's machines.** One `pip install`
  away. Until then "green" locally covers 13 of 64 jobs, and this slice's numbers
  say so rather than rounding up.
- **`counts.json` is again restored to HEAD and not committed from this VM**, for
  the same reason as ADR-104: a ledger written where 50 suites cannot run
  describes the machine, not the kit. It is now correct on the host — the run
  there wrote it and it was pushed — and this slice deliberately leaves it alone.
- The provenance gap in §2: nothing records which environment produced a green
  run. Worth a slice; not this one.
- ADR-103's worklist is still untouched and still the best queue.
