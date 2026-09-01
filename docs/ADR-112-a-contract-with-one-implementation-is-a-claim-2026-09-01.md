# ADR-112 — A contract with one implementation is a claim

**Status:** accepted · **Date:** 2026-09-01 · **Supersedes nothing; measures ADR-102's "or another target"**

## 1. The sentence that had never been tested

`docs/AUTOMATION-HARNESS.md` has said since ADR-102:

> HarnessPlugin implementations → *A CSRBT page in a browser, or another target*

and

> A client can connect an OpenAI-compatible tool, a local model, an MCP server,
> or an ordinary script without changing the plugin, because a transport maps
> exactly four operations and decides nothing.

For eleven ADRs there was exactly one plugin. The gateway, the risk ladder, the
replay cache, the redaction rule and the stdio transport had all been built,
tested (70 checks in `verify_contract`) and used (the swarm drives forty pages
through nothing else) — against one target, shaped like a page. Nothing had
shown that any of it was target-neutral rather than page-shaped. A contract
with one implementation is a claim about the second implementation, and the
kit's rule since ADR-041 is that a claim nobody has measured is a number nobody
should quote.

The ask that started this was plainer than the ADR: *the harness needs to
verify that everything works, and later robots and AI get plugged into it.*
"Everything" in this ecosystem is not forty-one HTML pages. It is fourteen
engines composed over one store, and the harness had never touched one of them.

## 2. The decision

Put the organism behind the contract. **WholeHog** — the integration organism
that composes every engine (CSRBT's adaptive index inside SmokeHouse's store,
Carver, Renderer, Brine, PitBoss and its replica, DryAge, Twine, SmokeSignal,
Jerky, Rub, the Sizzle seam) — becomes the second `Plugin`, `csrbt-organism`,
served by the same gateway, the same policy, the same replay cache and the same
stdio transport as `csrbt-page`, **with no change to any of them**.

Where a change would have been needed, that would have been the finding. None
was. The transport gained an argument parser option and nothing below it; the
suite pins that `serve()` names no target.

Three pieces:

| piece | where | what |
|---|---|---|
| `HarnessConsole` | `WholeHog/src/main/java/…/HarnessConsole.java` | one `Organism` driven over stdin/stdout by a line protocol of numbers; hand-emitted JSON replies; no policy, no token — it is a seam, not the contract |
| `harnessClasspath` | `WholeHog/build.gradle.kts` | writes the runtime classpath to `build/harness/classpath.txt`; absent file == not built, and the plugin says so rather than guessing at jars |
| `OrganismPlugin` | `CSRBT/tools/harness_plugin_organism.py` | the `Plugin` — descriptor with declared risks, value-redacted `observe`, `execute` over the console, bounded waits |

## 3. The risk mapping, and why it is not symmetric with the page's

| risk | organism actions | reasoning |
|---|---|---|
| `READ` | `report`, `pulse` (+ `observe`) | meters only: sizes, sequences, counters, vitals. Never a key, never a value |
| `NAVIGATE` | `tick`, `quiesce` | they move an instrument or wait; no record changes |
| `SENSITIVE_READ` | `get`, `contains`, `range`, `count-range`, `query`, `cold-scan`, the snapshot's record sample | anything that returns a key, a value, or an aggregate over *named* keys. "Does key 5 exist" is data about the data |
| `MUTATE` | `put`, `delete`, `batch`, `preserve` | every one changes what is on disk: store, journal, vault, archive |
| `DESTRUCTIVE` | **none** | there is no generic "press this" on an organism. Every action names exactly what it does, so the rung the page plugin needs for "a selector that might be *Clear trial*" has no member. Left empty rather than filled for symmetry |

A write's **route is an argument, not an action**: `put`/`delete` take
`via = direct | wire`, and `batch` always goes through Twine's journal. The
organism's whole claim is that every route lands in every index; a client that
can name the route can test the claim — and the suite does.

## 4. What the second plugin proved about the first contract

`tools/verify/verify_organism.py`, **234 checks** in ten sections, every one a
command through the gateway with a request id against a policy it names:

- **B** the default policy refuses `put` (direct and over the wire), `get` and
  `batch`, and *none of it reached the organism* — the store, the wire and the
  journal all still read zero. The manifest an adapter bootstraps from marks
  every write and every record read `allowed: false`.
- **C** a plain snapshot carries no `sample`, `records`, `key` or `value` field;
  a sensitive one carries the sample, capped at 20, with the mirror's median.
- **D** the differential oracle: 160 seeded operations by every route (direct,
  wire, Twine batch) mirrored in a dict; then `size`, every `get`, `contains`
  on every absent key, a full `range`, a capped `range`, twelve random
  `count-range` windows and eight random Carver `query` windows compared against
  it — and the wire and journal meters equal to exactly the traffic sent their
  way, and Rub on the primary and Rub on the replica both counting the mirror.
- **E** a replayed `put` is served with `replayed: true` and writes nothing —
  size and tail sequence unchanged; the same id with a different body is a
  `conflict`; a cached `get` stops flowing when `SENSITIVE_READ` closes.
- **F** `preserve` returns a generation, `cold-scan` streams exactly the moment,
  twenty more puts and a delete later it *still* streams the moment, and a
  generation never preserved is `not_found`.
- **G** nine refusals — boundary (`via: teleport`, a string key, an undeclared
  argument, a cap past the plugin's 200) and target (`attr: 1000`, `lo > hi`, a
  zero cap, an empty batch, a malformed op) — with the right code each, and
  **no trace on any meter** afterwards.
- **H** two consecutive physicals identical through the gateway.
- **I** the console killed under the plugin: `unavailable` in under a second,
  not a hang and **not `failed`** — `failed` in this harness accuses the target
  (ADR-111), and a transport death is not a finding about the organism.
- **J** `harness_stdio.py --target organism`: wrong token `unauthorized`,
  manifest names the organism alone, a wire put lands and the snapshot says so,
  `get` `forbidden` on a session that opened only `MUTATE`.

The contract held on all of it unchanged. That is the measurement §1 asked
for. The gateway is target-neutral; it was not merely page-shaped.

## 5. The tester, tested

`tools/mutate_organism.py` breaks the plugin and the console on purpose —
plugin mutants against a copy of `tools/`, console mutants compiled with
`javac` into a scratch classpath put first via `CSRBT_ORGANISM_CLASSPATH`, so
nothing real is written to.

First sweep, same afternoon: **twelve mutants, eight killed, four survived.**
Three of the four were real:

| survivor | what nobody asserted | now killed by |
|---|---|---|
| a put naming no route goes over the wire | the *documented default* route — every check named `via` explicitly | "a put that names no route goes direct, and the wire's meter agrees" |
| the plugin stops bounding the cap | the plugin's own 200 — the console's 1000 refused everything the suite tried | "a cap past the published 200 is refused by the PLUGIN" |
| the pump dies without telling the reader | the death sentinel — `send()` checks liveness first, so a console dying *between* requests never exercised `_recv` | "the reader learns of the death from the pump's sentinel in 0.00s, not from its timeout" |

The fourth — the plugin's batch-op regex accepting anything — survived because
the console refuses the same input with the same code, and "keep domain
validation inside the target as well as at the boundary" is the contract's own
rule. It is recorded in `KNOWN_EQUIVALENT` with the measurement so the next
reader does not re-run it and call the survival a finding.

Final: **11 killed, 0 survived, 1 equivalent.** `verify_organism` 231 → 234.

## 6. What is held, and why

- **Chaos.** `Sizzle` is a constructor seam — a `ChaosPlan` is fixed at standup,
  not injected at runtime — so there is no `chaos` action. Publishing one would
  need an upstream cut, and *a harness that presses buttons nobody can reach*
  is ADR-103's finding, not a thing to repeat. Every snapshot already carries
  `chaosCrashes`, so the day the seam is cut the meter is wired.
- **The wire's read side.** `get`/`range`/`count-range` read the primary
  directly; the wire is exercised as a *write* route. Reading over the wire
  would add a `via` to the reads and an oracle that the wire's answer equals
  the primary's — a real slice, unbuilt, named.
- **Snapshot-per-response cost.** The gateway takes a snapshot after every
  command; on the organism that is one `observe` round trip (~1 ms). Fine at
  this size; the page plugin's re-stamp is the heavier one and it has never
  been priced either.
- **The suite on a machine without the build** prints nine `NOT VERIFIED`
  lines and scores 17/26 — the discipline `verify_engine_sessions` set. A
  fresh clone needs `./gradlew harnessClasspath` in WholeHog before sections
  B–J are evidence of anything.

## 7. What "robots and AI get plugged in" now means

The same four operations, the same token, the same policy, the same manifest
with one JSON Schema per action — now over **two** targets in one registry
(`--target both`). An adapter written against `csrbt-page` needs to learn
nothing to drive the organism; the tool names differ (`csrbt_organism__put`)
and the risks are declared, so an operator opening `MUTATE` for a supervised
session knows exactly which four actions that unlocks and which six record
reads it does not. Nothing in the ecosystem is reachable by a model except through this
boundary, and the boundary has now been shown to hold for something that is
not a page.
