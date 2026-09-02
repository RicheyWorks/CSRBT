# ADR-118 — The engines' own suites, ratcheted

**Status:** accepted · **Date:** 2026-09-02 · **Extends ADR-108's ledger rule to the Java side of the ecosystem**

## 1. The numbers that lived in prose

Underneath the harness, fourteen engines each carry a JUnit suite — the
engine's own claim about itself. Their sizes have been quoted for a month:
*SmokeHouse 75, Carver 9, WholeHog 12*, in ADRs, in the Atlas's engine ledger,
in the session notes. Every one of those was typed by hand from a Gradle
run somebody remembered, and carried forward. The kit's rule since ADR-041
is that a number a tool can compute is never pinned as a constant, and since
ADR-108 that a coverage claim has a ledger with a consumer that can refuse
it. The engines' suites had neither, and the numbers had drifted: SmokeHouse
is 79, SmokeSignal is 14, DryAge is 10, WholeHog is 21.

"The harness verifies that everything works" had, one layer down, fifteen
suites nobody's tool was reading.

## 2. The decision

`tools/ecosystem.py` names every engine repo as a sibling of this one — the
way the composite builds find them — with the module directories that hold
its JUnit XML. `--read` walks the XML Gradle writes and records tests,
failures, errors, skipped and when, per engine, into
`tools/ecosystem_ledger.json`; `--run` executes `./gradlew test` in each repo
first. The ledger is **merged**, not replaced: a machine that has not built
Carver keeps Carver's reading with its own `at`, and an engine with no
results here is `NOT VERIFIED` in the suite, never green.

Each engine carries a **floor**: the smallest count the ledger will accept.
A read raises a floor to the count it read and never lowers one. Lowering
is `--lower ENGINE N --reason "..."`, and the reason goes into the ledger.

`tools/verify/verify_ecosystem.py` is the consumer, **52 checks**:

1. every repo the organism's composite build reaches is an engine the
   ledger lists — **derived from the settings files** (WholeHog includes
   every engine; each includes what it depends on, down to CSRBT), not from
   what sits beside this repo — and the ledger lists nothing the composite
   does not reach. A new engine fails until listed, the way a new page fails
   `verify_routes`;
2. every listed repo exists;
3. for every engine with results on this machine that are **newer than its
   sources**: no failures, no errors, tests ≥ floor, and the ledger's
   reading not older than the XML on disk;
4. an engine without results, or with results older than its sources, is
   `NOT VERIFIED` by name — stale evidence is not a shrunken suite;
5. floors only rise on a read, and every lowering carries a reason;
6. the total is the sum of the rows.

Both refusals were canaried before the suite was believed: a floor raised
above the live count fails naming the shortfall; a reading older than the
XML fails naming the rerun. Lowering without a reason is refused by the
tool.

The first run on the author's machine then failed **ten checks, all
wrongly**, and both were the same defect this kit keeps finding — right
about what it matched, wrong about what the match meant. It listed
`BlackJackPro` as an unlisted engine, because the first draft took *every
sibling with a Gradle build* for an engine and the projects folder holds a
card game. And it called nine suites shrunken — `WholeHog: 5 tests on disk
is below the floor of 21` — because the XML on that disk was from builds a
month old, and a count from stale evidence is not a count of the suite. The
engine list is now the composite closure, computed from the build files;
results older than their sources are `NOT VERIFIED` with the date, never a
failure. On that machine the suite now reports what is true: the engines it
has fresh results for, and the rest as holes with a reason.

## 3. The first reading

All fifteen suites, run in one place, on one JDK 21:

| engine | tests |
|---|---|
| csrbt-core | 877 |
| csrbt-experimental | 256 |
| SuperBeefSort | 318 |
| SmokeHouse | 79 |
| Carver | 9 |
| Renderer | 6 |
| Brine | 5 |
| PitBoss | 3 |
| DryAge | 10 |
| Twine | 8 |
| SmokeSignal | 14 |
| Jerky | 5 |
| Rub | 6 |
| Sizzle | 7 |
| WholeHog | 21 |

**1624 tests, 0 failures, 0 errors.** Two things this reading corrects:

- **SuperBeefSort's suite runs.** The session notes said it needed a Rust
  toolchain and a JDK 22 and could not run in the sandbox. That is true of
  its native-kernel *module*, which its own build file skips on an older
  JVM; the main suite is 318 tests and runs on 17+. The ledger's note says
  which.
- **The Atlas's engine ledger is stale by a month** on nine of fourteen
  rows. It is a published artifact and a separate slice to republish; this
  ledger is now the source it should be regenerated from.

`run_all` picks the suite up by its glob, so one command now reports the
Java side of the ecosystem beside the Python side, with holes named.

## 4. Held

- **`--run` is sequential and slow** (~8 minutes for all fifteen here). It
  is the honest way — each repo's own `gradlew`, its own composite — and it
  is not what `run_all` does: `run_all` reads; running is the operator's.
- **The Atlas is not regenerated from this ledger yet.** It should be, and
  the drift above is the reason.
- **Skipped tests are recorded, not judged.** SuperBeefSort skips one; the
  ledger says so and the suite does not fail it. A skip that hides a
  failure is a different finding, and not one a count can make.
