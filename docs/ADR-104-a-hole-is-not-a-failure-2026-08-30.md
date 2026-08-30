# ADR-104: a hole is not a failure, and a wrong remedy is not an explanation

**Status:** Accepted (2026-08-30)
**Date:** 2026-08-30
**Deciders:** Richmond
**Builds on:** ADR-103 (which shipped the seven page changes this slice republished),
ADR-040 (a row right about what it matched and wrong about what the match meant),
and ADR-038/056/078 (publish_state's refusal to read "unknown" as "current").

---

## 1. What this slice found

`run_all` reported `verify_engine_sessions` as **FAILED WHILE EXITING ZERO** —
24/25 with rc=0. That rule exists for a good reason: a mutation sweep found
suites that print their FAIL lines and exit 0, and eleven suites have no exit
statement at all, so the printed score is treated as evidence regardless of what
the process claims on the way out. Belt and braces, with the braces doing the
work.

But `verify_engine_sessions` was not failing. Its twenty-fifth check is the
round trip through the real Java engine, and it needs the built classes **plus
log4j on the classpath**. Where it cannot reach them it counts the check and
prints `NOT VERIFIED` — passing it would be a lie and failing it would be a
different one. That is the same three-state discipline `publish_state.py` uses
when it refuses to collapse "unknown" into "current".

So the shortfall rule was right that the score fell short, and wrong about what
the shortfall meant. **This is the third recorded instance of that exact defect
in this kit** — after ADR-040, and after the `"FAIL" in out` rule that flagged
`audit_contrast` for printing a column header reading "AA FAILURES". It is worth
naming as a pattern: a check that matches a true fact and infers the wrong cause
from it.

## 2. The two fixes

**`run_all` learns the third state.** It now counts the `NOT VERIFIED:` lines a
suite prints and subtracts them from the shortfall test:

```python
unver = unverified(out)
short = (got is not None and tot is not None and got < tot - unver)
```

A declared hole is no longer a silent failure. It is also not green: such rows
are marked `ok--`, and the run ends with its own section — *"N job(s) COULD NOT
RUN every check … What ran, passed; the rest was not attempted and is not
evidence of anything."* Folding the hole into `ok` would have been the more
comfortable fix and the dishonest one.

**Loosened by exactly the declared amount, and no more.** A canary over five
seeded cases holds the boundary, and the case that matters is the fourth:

| seeded output | holes | shortfall | verdict |
|---|---|---|---|
| `3/5`, nothing declared | 0 | 2 | **FAIL** |
| `24/25`, one `NOT VERIFIED` | 1 | 1 | hole |
| `23/25`, two `NOT VERIFIED` | 2 | 2 | hole |
| `23/25`, **one** `NOT VERIFIED` | 1 | 2 | **FAIL** |
| `25/25` | 0 | 0 | clean |

One declared hole cannot hide one real failure behind it.

**The unverified message named the wrong cause.** It read
*"engine classes or log4j not found — run `./gradlew classes`"*. On the machine
where it actually fires — the desktop Linux VM — the classes **are** built (they
arrive over the mount from the Windows host) and it is the log4j jars that are
absent, because they live in the *host's* `~/.gradle` cache, which is not
mounted. Worse, the advice cannot be followed there: Gradle 9 needs JVM 17+ and
that VM has 11, so a reader doing as told got a second failure that explained
nothing about the first. `classpath()` now returns `(path, why_not)` and
distinguishes the two, so the honest result carries an honest remedy:

```
NOT VERIFIED: engine -> docs/ecology-lab-session.json (classes are built but
log4j-api-*.jar is not in this machine's ~/.gradle cache -- run this suite
where the engine was built)
```

An unverified result is honest. An unverified result with a wrong remedy just
moves the confusion one step downstream.

## 3. A third defect, found because it bit this slice

Running the suite here rewrote `tools/verify/counts.json` — the ledger of what
each suite last counted — and the rewrite was destructive. It is built from
scratch on every run, so a machine that cannot *run* a suite deletes what a
machine that could had measured. This VM has no Playwright, 52 of the 64 jobs
are Playwright, those produced no score, and their entries simply vanished.

The damage did not stop at the file. `verify_advertised` **reads** that ledger,
and on the next run it went from 29/29 to 22/29 — reporting a defect in the kit
that was really a defect in the machine that last wrote the file. A ledger with
a consumer does not corrupt quietly.

The `sha` guard cannot catch this, and it is worth being explicit about why: the
suite *source* was identical, only the environment differed. **A hash of the
thing being measured cannot detect a change in what is doing the measuring.**

**The ledger is not committed from this slice.** The fix makes a limited machine
stop *deleting* measurements; it does not make that machine's measurements
right. `verify_audit_frontend` scores 19/19 on the host and 6/19 here, and its
failures are seeded-fault canaries returning `got: []` — the audit under test
finding nothing rather than erroring. That is a second instance of the same
class as the ledger bug (a thing that degrades silently in a limited
environment) and it is **named, not diagnosed**: working out why from a VM that
cannot run the browser suites would be exactly the "two true facts joined by
plausibility" this kit keeps paying for. `counts.json` is restored to HEAD and
should be regenerated by a `run_all` on the Windows host, which the merge now
makes safe to do.

A run now updates only the suites it actually scored and leaves the rest alone,
reporting what it did: `wrote tools/verify/counts.json (14 suite counts updated,
42 kept from earlier runs)`. Every entry carries its own `at`, so a kept reading
can be told from a fresh one — the ADR-056 lesson, applied to the second ledger
in this kit that needed it. Entries also record `unverified` where a suite
declared a hole, so "not green" never appears without saying why.

## 4. Also in this slice, outside the repository

The seven pages ADR-103 changed were republished and stamped:
`publish_state` reads **40 current, 0 behind**, and `verify_publish_reach` is
back to 58/58. ADR-103 shipped deliberately red on that check; it is now green
for the reason it was meant to be — the pages a reader sees are the audited ones.

The autonomous polish schedule was cut from every two hours to every twelve, and
given a stop rule. The evidence for that: ADR-098 through ADR-102 changed **zero**
kit pages between them while touching 32 files under `tools/`, and ADR-103 had to
retract two of ADR-102's headline findings. Twelve slices a day against a mature
kit is a machine for inventing work, and what it invents is more instruments. The
brief now says: if the audits are clean and you would change no page, say so and
stop; instrument work needs a product finding you can name in one sentence.

## 5. Still open

- 52 of 64 jobs are Playwright suites and cannot run in the Linux VM (no
  playwright there). They run on the Windows host; the 13 that ran here are
  green. **This slice's numbers are the non-browser subset, and that is stated
  rather than rounded up** — the ledger now keeps the host's numbers for the
  rest instead of overwriting them, but keeping is not measuring, and a full
  green needs a run on the host.
- The twenty-fifth check stays unverified anywhere the engine's jars are not on
  that machine. The fix is not more code — it is running that suite where the
  engine was built, which the message now says.
- `verify_audit_frontend` at 6/19 in the Linux VM against 19/19 on the host,
  failing on seeded-fault canaries that return empty. Either the audit it tests
  needs the browser and returns `[]` when it cannot get one — in which case an
  audit that finds nothing because it could not look is a defect worth its own
  slice — or something else. Measured, not explained.
- The counts ledger needs one `run_all` on the Windows host to be current again.
- ADR-103's worklist is untouched and still the best queue: `ecology-lab`'s NaN
  from `1e308`, the `row2` flex-chain repair, `deployment-log`'s 41px spill, and
  the two shrinker repros that would not reproduce from a reload.
