# Changelog — 2026-08-30 — ADR-104: a hole is not a failure

Two defects in the verify harness, the ADR-103 pages republished, and the
autonomous polish loop retuned.

## Changed — `tools/verify/run_all.py`

- New `unverified(out)`: counts the `NOT VERIFIED:` lines a suite prints — checks
  it included in its total and openly said it did not run.
- The shortfall rule is now `got < tot - unver`, so a declared hole is no longer
  reported as **FAILED WHILE EXITING ZERO**. Loosened by exactly the declared
  amount: one hole cannot mask one real failure (canary case 4).
- Such rows are marked `ok--`, not `ok`, and the run ends with its own section
  naming them: *"N job(s) COULD NOT RUN every check … the rest was not attempted
  and is not evidence of anything."* The hole stays visible; it is not folded
  into green.

## Changed — `tools/verify/verify_engine_sessions.py`

- `classpath()` returns `(path, why_not)` and distinguishes missing classes from
  missing log4j jars. The old single message named the wrong cause on the only
  machine where it fires and prescribed `./gradlew classes`, which cannot run
  there (Gradle 9 needs JVM 17+; that VM has 11). The unverified line now reads:
  *"classes are built but log4j-api-\*.jar is not in this machine's ~/.gradle
  cache — run this suite where the engine was built."*
- Behaviour is unchanged where the engine is reachable: still 25/25 there.

## Changed — the counts ledger (`tools/verify/counts.json`)

- `run_all` now **merges** into the ledger instead of rebuilding it. It was
  destructive: a machine that could not run a suite deleted the measurement of
  a machine that could. This VM has no Playwright, so 52 suites produced no
  score and their entries vanished — and `verify_advertised`, which reads the
  ledger, went 29/29 → 22/29 on the next run, reporting a kit defect that was
  really a defect in the machine that last wrote the file.
- Each entry now carries its own `at` (a kept reading is distinguishable from a
  fresh one) and an `unverified` count where a suite declared a hole.
- The run says what it did: `(14 suite counts updated, 42 kept from earlier runs)`.
- `counts.json` itself is **restored to HEAD and not committed from this slice** —
  the fix stops a limited machine deleting measurements, it does not make that
  machine's measurements right. Regenerate it with one `run_all` on the host.

## Found, not fixed

- `verify_audit_frontend`: 19/19 on the host, 6/19 in the Linux VM, failing on
  seeded-fault canaries that return `got: []` — the audit under test finding
  nothing rather than erroring. Named and left; diagnosing it from a machine
  that cannot run the browser suites would be guessing.

## Verified

- Canary over five seeded outputs, including one declared hole alongside one
  real failure — all five classify correctly.
- `verify_engine_sessions` 24/25, rc=0, now reported as `ok--` with its reason.
- Ledger merge: `verify_advertised` keeps its host-measured 29/29 across a run
  that could not execute it; `verify_engine_sessions` updates to 24/25 with
  `unverified: 1`.
- Non-browser subset of the suite: 13 of 13 runnable jobs green. The other 52
  need Playwright and run on the Windows host, not the Linux VM.

## Published (outside the repository)

- The seven pages ADR-103 changed — collection-sheet, deployment-log, ecology-lab,
  ordination, releve, stand-sheet, survey-design — republished to their existing
  artifact URLs and stamped. `publish_state`: **40 current, 0 behind**.
  `verify_publish_reach`: 58/58. ADR-103 shipped red on that check by design; it
  is now green for the right reason.

## Operations

- The autonomous polish schedule moved from every 2 hours to every 12, with a
  stop rule (a slice that would change no kit page stops instead of building
  another audit tool) and an accurate conflict check (commit age alone, since
  this repo's messages are ADR prose and the "looks machine-written" heuristic
  never matched them).
