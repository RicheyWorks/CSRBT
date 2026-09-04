# ADR-139 — The engines, ratcheted forward: a floor per test class, and a record of having run the engine

**Status:** accepted · **Date:** 2026-09-04 · **The ecosystem ledger's floor was per engine, so a suite could delete a test class and grow another by the same count and the ratchet would see nothing. It now holds every one of 299 test classes, with `--forget` as the only way down. And the engine-session link, which has reported `NOT VERIFIED` on most runs since it was written, is closed on machines with no JDK by an attestation that expires the instant the engine's sources move**

## 1. What ADR-118 built and what it could not see

`ecosystem.py --read` walks fifteen engines' JUnit XML into a ledger with a
**floor** per engine: a suite may grow and may not shrink, and `--lower` with a
reason is the only way down. `verify_ecosystem` fails on a count below its
floor.

That is a real ratchet and it has a hole the size of the thing it is guarding.
The floor is a **total**. Delete one test class, grow another by the same
number of tests, and the total is unchanged — the ratchet is satisfied by a
suite that lost a subject. Nothing in the kit could have said so.

## 2. The ratchet goes down to the class

`read_results` now returns `suites` — the JUnit `<testsuite name>` and its test
count, which is the test class — and the ledger keeps a `classFloor` per engine.
**299 test classes** across the fifteen engines, each at the highest count it
has ever been read at. A read raises a class's floor and never lowers it; a
class that has ever been seen stays on the record.

`verify_ecosystem` then says two things it could not say before, per engine,
naming what moved:

- a class on the ratchet that is **not in the results any more** — a suite that
  lost a subject;
- a class that is **smaller** than its floor, with both numbers.

The only way down is `--forget ENGINE CLASS --reason "..."`, the same shape as
`--lower` one level in: the class comes off the ratchet, and the fact that it
was deliberately removed, with the size it had and why, goes into the ledger.
A shrink you meant is still a shrink, and it stays on the record.

### The rule, tested as a rule

Checks that read the ledger as it stands cannot hold a ratchet, because as it
stands nothing has shrunk — a `read_all` that *lowered* every floor would
satisfy all of them. So `verify_ecosystem` now drives `read_all` against a
fixture ledger whose floors are inflated (99999 tests, a class at 500, a class
that will not appear at all) and requires: the floor stays, the class floor
stays, the absent class keeps its floor **because that is what makes its
absence visible**, a new class joins at what it read, and a forgotten class does
not rejoin on the next read. Both escape hatches are driven too — refused
without a reason, and with one, recording where the floor came from and what
size the class had.

## 3. The hole that had never been closed

`verify_engine_sessions` link A — *is `docs/ecology-lab-session.json` really
`EcologyFieldDay.run().json()`?* — answers by **running the engine**. That is
the only check worth having, and it needs a JDK, built classes, and log4j on the
classpath. On the desktop Linux VM the classes are there over the mount and the
log4j jars are not, because they live in the Windows host's `~/.gradle`. On a
fresh clone nothing is there. The link has therefore reported `NOT VERIFIED` on
most runs since it was written, and a hole nobody can close is a hole that stays
open.

### An attestation, not a fixture

A cached copy of the engine's output standing in for the engine would pass on a
machine where the engine has been broken for a month. That is worse than the
hole. `tools/engine_attest.py` records something narrower and dated, the same
shape ADR-078 gave a published page:

> on **2026-09-04**, on **openjdk 21.0.10**, the engine emitted exactly these
> bytes, and the engine's sources digested to **ef76eca82be7** at that moment.

The digest is over **93 source files** — both modules' main sources, whole, by
**path and bytes**, so a file renamed with its content unchanged is a different
engine. Deliberately over-broad: a change that could not possibly affect the
session invalidates the attestation and costs one re-run on a machine with a
JDK, while a narrow digest that missed a real dependency would go on saying
"still applies" about an engine that had moved.

The suite's link A now reads:

- the engine runs here → the **live** check, unchanged, and the attestation on
  record is checked to agree with what the run just produced;
- the engine does not run here, and the attestation **applies** → a PASS whose
  own name says it is attested and not run, and when;
- the engine does not run here and the shipped bytes are **not** what was
  attested → a **failure**, on a machine with no Java at all;
- the sources have moved since, or nothing was ever attested → `NOT VERIFIED`,
  naming which.

Measured: with `build/` removed and no classpath, the suite goes from one
`NOT VERIFIED` to **25/25 clean**. Add one byte to one `csrbt-core` source and
it goes straight back to `NOT VERIFIED`, saying the engine has moved since the
record was taken. Nobody has to remember.

Only `--attest` writes the record, and it can only run where the engine runs.
There is no path by which the weaker evidence can be created without the
stronger one having happened.

## 4. Verification

`verify_ecosystem` **99** (+10): the class ratchet on the real ledger, the
ratchet's rule on a fixture, both escape hatches refused without a reason and
recorded with one, and an engine spread over two modules keeping both modules'
classes.

`verify_engine_sessions` **37** (+11, and it no longer needs a JDK to reach 25
of them): the committed attestation names what produced it; the digest covers
both modules by path and bytes; a rename is a different engine and an edit
different again; the decay rule three ways (applies / stale / differs) plus
absent; and what `--attest` writes, with the engine's output faked and the
record it produces not.

`tools/mutate_engines.py` is new: **13** mutants over `ecosystem.py` and
`engine_attest.py`, each put to whichever of the two suites owns it. The floor
falling, a floor lowered with no reason, the class ratchet not kept, a class
floor falling, one module's classes lost, every class read under one name, a
class forgotten with no reason; an attestation that applies whatever the engine
has done, one with nothing in it reading as attested, the shipped bytes never
compared, a digest of bytes alone, a digest of one module, and a record written
with no digest at all. **13 killed, 0 survived.**

The runner mirrors the real layout in its temp tree — `<tmp>/eco/CSRBT/tools`
with `docs/` and every sibling engine repo linked in beside it — because
`ecosystem.py` resolves each engine at `<repo>/..`, and a copied `tools/` in a
bare temp dir finds no engine at all: every ledger check is skipped and every
mutant "survives" a suite that never looked.

## 4a. Two things the run turned up

**A suite that reaches for a temp dir must say what for.** `verify_mutate`
holds every suite in the kit to `MUTATE_ROLE` (ADR-077), and both suites this
slice touched started using one — for a fixture *ledger* and two fixture
*.java* files, neither of them fixture pages. Both now declare `subject`, which
is what they are.

**The board is behind the moment it is rendered.** It is a report on the run,
rendered from the run's own ledgers, so a slice that changes any count leaves
the published board stale by construction. Now that it is a mapped artifact
(ADR-138) that is a FAILING check rather than a shrug, which is right, and it
makes the ritual explicit: the last full run of a slice is followed by a board
render, a republish and a measurement, and the run after that is clean because
the render is byte-deterministic given the ledgers. Measured here: two runs to
converge, and the second was 77/77.

## 5. Held

- **The class ratchet cannot see a renamed test class.** Rename
  `FooTest` to `FooBarTest` and it reads as one class gone and one arrived;
  the gone one fails until it is `--forget`-ten. That is the safe direction and
  it is friction, and a rename map is not cut.
- **Nothing here runs the engines.** `ecosystem.py --run` exists and this slice
  did not use it; the ledger still reads whatever JUnit XML is on disk, and
  results older than the sources are `NOT VERIFIED` as before.
- **One artifact is attested.** `docs/ecology-lab-session.json`. The lab's
  shipped experiment session (ADR-135's `FIXTURES["session"]`) is engine-derived
  too and is not on the list.
- **An attestation says nothing about the engine's correctness**, only that the
  shipped bytes are the ones it emitted. The engine's own 1,629 tests are the
  other half, and they are ratcheted separately.

## 6. First reading

    ecosystem ledger  15 engines, 1,629 tests, 299 test classes on the ratchet
    engine attest     docs/ecology-lab-session.json, digest ef76eca82be7 / 93 files
    verify_ecosystem  99 / 99  ·  verify_engine_sessions 37 / 37 (25 without a JDK)
    mutate_engines    13 killed, 0 survived  ·  verify_board 51 / 51
    kit  77 / 77 jobs, 5,731 / 5,731 checks
    board 5,321 checks, 256 / 256 mutants  ·  publish reach 42 / 42 measured
