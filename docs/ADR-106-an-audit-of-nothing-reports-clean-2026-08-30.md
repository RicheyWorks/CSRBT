# ADR-106: an audit of nothing reports clean

**Status:** Accepted (2026-08-30)
**Date:** 2026-08-30
**Deciders:** Richmond
**Builds on:** ADR-105 (the canary that read an empty result as a verdict) and
ADR-104 (a hole is not a failure). This is the third and worst instance of that
pattern in two days, and the first one that was reporting on the *product*.

---

## 1. What running the full suite locally revealed

Playwright was installed on the host and the suite ran properly there for the
first time: **61 of 64 jobs green, 4383 of 4385 checks**. Both fixes from
ADR-105 held — `verify_publish_drift` 49/50 → **50/50**, and
`verify_audit_frontend` 6/19 → **19/19**, which settles that ADR: the finder was
never broken, the canary had simply never checked whether it started.

Three jobs did not pass, and they are three different things.

## 2. Two suites hardcoded a Linux scratch path

`verify_claims_slice` and `verify_print_slice` both died on
`net::ERR_FILE_NOT_FOUND`. They wrote their canary fixture to `/tmp/_ccan/` and
`/tmp/_pcan/` and navigated to `file:///tmp/...`. On Windows `os.makedirs`
cheerfully creates that directory on the current drive while the browser
resolves the absolute file URL somewhere else, so the fixture is written and
then not found. The suites **crashed rather than reported**, which by ADR-104's
rule means everything after the crash point said nothing.

Both now use `tempfile.mkdtemp()` and `pathlib.Path.as_uri()`. A sweep for the
same mistake found one more, in `harness.py`'s file-import action, fixed the
same way.

## 3. And two audits were reading a directory that does not exist

This is the serious one. `tools/audit_targets.py` and `tools/fek_lint.py` began:

```python
DOCS = "/tmp/eco/CSRBT/docs/"
```

That is the path the **autonomous polish job clones into** — `cd /tmp && git
clone … eco` — which exists inside one container, during one job, and nowhere
else. On every other machine `glob.glob(DOCS + "*.html")` returns `[]`, the loop
over pages never executes, the counter stays at zero, and the tool prints:

```
total under 44px across the kit: 0
clean — no FEK misconfiguration found
```

**A clean bill of health from an audit that examined zero pages**, exiting 0,
counted as green in the kit's headline numbers, on every local run Richmond has
ever done. `audit_targets` completing in 0.9s against `audit_focus`'s 25.8s was
the tell, and nobody had a reason to look at it.

Measured after the fix: `fek_lint` scans **19 FEK consumers** and is genuinely
clean. The verdict it printed before was the same word for a different fact.

Both now derive `DOCS` from the script's own location, so they read the checkout
they were run from. **And finding no pages is now a loud failure, exit 2, not a
clean result** — that second half matters more than the path, because the next
hardcoded path will fail the same silent way and "I looked at nothing" must
never again render as "nothing is wrong". Canaried: with the root pointed at a
directory that does not exist, `fek_lint` exits 2 and says so.

## 4. The third failure is a real product defect, and it is not new

`verify_cs_science` scored 84/86, failing on `collection-sheet.html`:

```
FAIL: no h-overflow phone p-rec  << 401 > 390
FAIL: nothing offscreen p-rec  << ['DIV.row2 @401' x4]
```

The suite source is byte-identical to when it scored 86/86 (`sha 9608d4d8271a`
in three consecutive ledgers). So either the page changed or the measurement
did.

**The page change is exonerated, and cleanly.** ADR-103's entire diff to
`collection-sheet.html` is one rule: `overflow-wrap:anywhere` on
`.verdict, .verdict *, code, td, th`. `overflow-wrap` governs only where a line
may break, and `anywhere` additionally *reduces* an element's min-content
contribution. It cannot make anything wider. A rule that can only narrow content
did not produce a 401px row.

What changed is the machine. Every previous green came from the polish
container; this is the first measurement on Windows, where the fallback font
metrics differ — the suite aborts the Google Fonts routes, so the text is laid
out in whatever the platform substitutes. 401 against a 390 budget is 2.8%.

So the overflow **pre-existed and was never measured**, and it is precisely the
item ADR-103 named and deliberately left: *"the row2 span repair, which needs a
flex-chain change rather than the property that regressed three pages."* What is
new is the evidence that it bites on a real user platform rather than in theory.

**Not fixed here, deliberately.** ADR-103 already tried a plausible one-property
repair on this exact rule, watched it regress three pages, and took it back off
all fifteen. A blind second attempt from a machine that cannot run the browser
suites would be the same mistake with less evidence.

## 5. Consequences

- The kit's green has meant three different things in three environments. Two
  audits were vacuous everywhere except the polish container; two suites crashed
  everywhere except Linux. All four are fixed, and the local run is now the
  strictest of the three rather than the most forgiving.
- The pattern is now named three times in three ADRs: **an empty result is not a
  passing result.** ADR-105 fixed a canary that read `[]` as a verdict; this one
  fixes two audits that read "no files" as "no faults". Worth a lint of its own
  eventually: any tool that can produce a clean report from an empty input set.

## 6. Still open

- **`.row2` overflows a 390px phone on `collection-sheet` once a record is in the
  row** (401px, measured on Windows). ADR-103's flex-chain repair, now with a
  reproducing platform. The highest-value item in the worklist.
- The provenance gap from ADR-105 §2 — nothing records which environment produced
  a green run — is now demonstrated rather than argued, by four defects that were
  invisible in the environment the numbers came from.
- ADR-103's remaining worklist: `ecology-lab`'s NaN from `1e308`,
  `deployment-log`'s 41px spill, and the two shrinker repros that would not
  reproduce from a reload.
