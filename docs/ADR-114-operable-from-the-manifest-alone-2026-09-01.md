# ADR-114 — Operable from the manifest alone

**Status:** accepted · **Date:** 2026-09-01 · **Extends ADR-112/113; protocol 1.0 → 1.1**

## 1. Described is not operable

ADR-112 proved the contract target-neutral. ADR-113 put every engine behind
it. Both were proved by `verify_organism` — a suite that **read the source**.
It knows a key is an integer near 100, that a batch op reads `p K A S E`,
that a chaos plan reads `once:2`, that a generation is a small number that
exists. None of that is in the manifest. A robot holding only the manifest
would have had to guess every one of them from a description, and *a robot
that guesses a domain from prose* is exactly the thing the contract was built
to make unnecessary.

The ask was that robots and AI get plugged in. The test of that is not a
suite written by the person who wrote the plugin. It is a client that has
read nothing but the manifest.

## 2. The decision

Two things, in order.

**The contract publishes enough to form a call.** `ArgumentSpec` gains
`minimum`, `maximum`, `pattern` and `examples`, published in each tool's JSON
Schema and **enforced by the gateway** (a call outside a bound or a pattern is
`invalid_argument` before the plugin runs). Two rules are refused at
construction, not at call time: a pattern without examples is a lock with no
key, and an example must satisfy its own pattern. Protocol `1.0` → `1.1`;
`verify_contract` 70 → 85.

Both plugins declare them. The organism plugin publishes every bound it was
already enforcing by hand, the two string grammars (batch ops, chaos plans)
as patterns with examples, and example pools for the unbounded integers
(keys, generations). The page plugin publishes the selector grammar
`^[a-z_]+:\d+$` with examples, and the page-name grammar.

**The first robot.** `tools/organism_walk.py` imports nothing from the kit.
It starts `harness_stdio.py --target organism` as a child, speaks the four
operations, reads the manifest, and forms every call from the schema — enum
values, bounds (both ends and the middle), patterns' examples, example pools —
and nothing else. If an argument cannot be formed from the schema the tool is
reported **UNSCHEMABLE** and left alone. Every response lands in one of five
buckets: `driven`, `refused` (`invalid_argument`, `not_found`, `conflict` — the
target defending itself by its own rules, counted rather than hidden),
`declined` (`ok: false` with no code — an answer of no), `chaos` (a `Crash`
while a plan is armed), `failed` (the finding). After every round a set of
cross-checks that need no knowledge of what was written: `order size` ==
snapshot size == `range` count == `count-range` over the pool, direct and over
the wire; generations and segments match the snapshot; the fleet is caught up;
two physicals agree; the fold counts no more than the store holds.

`commands == driven + refused + declined + chaos + failed`, `UNACCOUNTED`
otherwise; every allowed tool must be driven at least once — the coverage
floor. A tool published tomorrow fails the walk until its schema is good
enough to form a call to it.

## 3. What the robot found on its first walk

Four things, none of which `verify_organism`'s 287 source-informed checks had
caught, because a suite that knows the domain never sends what it knows to
be invalid.

| finding | what it was | fix |
|---|---|---|
| `batch` → `failed: IllegalStateException: a committed batch is still applying` | after a chaos crash mid-batch, Twine is wedged until `recover()` — its documented rule (tenth-pass T4) | the console maps `IllegalStateException` to **`conflict`**; the plugin raises `Conflict`. The organism's own rule is not the organism failing |
| `pulse` → `ok: false, "fewer than two ticks"` | a reading that does not exist yet reported as a failed action | `ok: true, pulse: null, why` — the read succeeded; the answer is "not yet" |
| `put … via wire` with `start > end` → `failed`; the same put direct → `invalid_argument` | the interval index refuses; direct that surfaced as `IllegalArgumentException`, over the wire as the server's refusal wrapped in an `IOException` | validated in the console **before any route**; `nth` past the size likewise. Same input, same code, whichever route |
| `as-of` never driven | its `generation` examples `[0, 1]` went stale the moment `retain-newest` released them and later preserves numbered upward — a static example cannot name a value that is a fact of the moment | the snapshot publishes **`argumentPools`** — `{"generation": [ids that exist now]}` — and the walker prefers a pool over a static example. *Observe, then act on what you observed* is the contract's own advice since ADR-102; this is it applied to arguments |

The fourth is the interesting one. It is not a bug in the organism. It is a
limit of static schemas, and the fix is a small, named convention rather than
a hack: a snapshot may carry `argumentPools`, a map from argument name to
values valid right now, for arguments whose validity is a fact of the moment.
It is READ-level here because generation numbers are not records.

After the fixes, two full walks at different seeds (8 rounds, ~900 commands
each) both end: identity holds, 33/33 driven, 0 unschemable, 0 invariants
broken, 0 failed. The committed ledger (`tools/organism_ledger.json`) reads
896 commands: 796 driven, 96 refused, 0 declined, 4 chaos, 0 failed.

## 4. Evidence

- `verify_contract` 70 → **85**: bounds published and inclusive, patterns full-match
  (not search), array patterns per item, the four construction-time refusals,
  and a refused call never reaching the plugin.
- `verify_organism` 287 → **291**: every bounded integer publishes its bound; the
  two grammars are patterns with examples; keys and generations carry example
  pools; `start > end` and a rank past the size are `invalid_argument` over
  the wire too; a batch on a wedged Twine is a `conflict`; the snapshot's
  generation pool equals `generations`.
- `verify_organism_walk` — **26 checks**: the walker is an outsider (no kit
  imports, four operations plus quit, token in the environment and never on a
  command line); the generator respects bounds and reaches both ends, reaches
  every enum value, uses pattern examples verbatim, prefers a published pool,
  and reports a string it cannot form as UNSCHEMABLE rather than guessing (the
  canary); a live walk with the identity, full coverage, nothing unschemable,
  no invariant broken, nothing failed; and the committed ledger held to the
  same bar.
- `mutate_organism` 19 → **22 killed, 0 survived, 4 equivalent**. New: a wedged
  Twine reported as failing; the span check removed; the generation pool
  withheld. The ADR-112 mutant *the plugin stops bounding the cap* became
  equivalent the moment the bound moved into the schema — the gateway now
  refuses first — and is recorded as such; its replacement strips the bound
  from the *manifest* and is killed by the check that reads the manifest.
- WholeHog `HarnessConsoleTest` grows the conflict and the span cases; 21 green.

## 5. What this changes about "plugging in"

Before this ADR an adapter could bootstrap tool *names* and *types* from the
manifest and had to learn *values* from somewhere else. Now a model, an MCP
server or a script holding the manifest and a snapshot can form a valid call
to all thirty-three actions, be refused with a code it can act on when it
forms an invalid one, and never be told the organism failed when the
organism merely declined. That is what operable means.

## 6. Held

- The walker's cross-checks are the organism's general oracle; there is no
  per-action expectation, on purpose. Whether a `put` *landed* is checked by
  `verify_organism`, not by the robot — a robot that asserts what its author
  remembered is ADR-100's finding.
- `argumentPools` is one entry deep. Keys are not published in a pool because
  keys are records (SENSITIVE_READ); a client that wants to read what it wrote
  remembers what it wrote.
- The page plugin publishes patterns now but the walker does not drive pages:
  selectors there are a fact of the moment *and* sensitive, and the swarm
  already drives every page through the gateway with a real oracle.
