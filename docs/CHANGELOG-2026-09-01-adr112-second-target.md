# Changelog — 2026-09-01 — ADR-112: the organism behind the contract

The automation harness reaches the engines. `csrbt-organism` is the contract's
second plugin: WholeHog's fourteen-engine organism, served by the same gateway,
policy, replay cache and stdio transport as the pages, **with no change to any
of them** — which is the measurement the slice exists to make.

## New — `WholeHog`

- `HarnessConsole.java` — one `Organism` over stdin/stdout, line protocol of
  numbers in, hand-emitted JSON out. Verbs: `observe`, `sample`, `put`/`delete`
  (`direct` or `wire`), `batch` (Twine), `get`, `contains`, `range`, `count`,
  `query` (Carver), `report`, `tick`, `pulse`, `quiesce`, `preserve`,
  `coldscan`. No token, no policy: a seam, not the contract.
- `harnessClasspath` Gradle task → `build/harness/classpath.txt`. Absent file
  means not built, and the plugin says so.

## New — `tools/harness_plugin_organism.py`

The `Plugin`: 14 actions with declared risks (4 `MUTATE`, 6 `SENSITIVE_READ`,
2 `READ`, 2 `NAVIGATE`, **0 `DESTRUCTIVE`** — an organism has no generic press),
value-redacted `observe` (meters; the record sample only under
`SENSITIVE_READ`), a write's route as an enum argument, bounded waits, and a
dead console reported `unavailable` — never `failed`, which accuses the target.

## Changed — `tools/harness_stdio.py`

`--target page | organism | both` (default `page`, unchanged behaviour).
Nothing below the argument parser changed; the suite pins that `serve()` names
no target.

## New — `tools/verify/verify_organism.py` (**234 checks**)

A descriptor and a two-plugin manifest with distinct provider-safe tool names;
then, through the gateway only: default-policy refusals that leave every meter
at zero; redaction both ways; a 160-op differential oracle over direct, wire
and batch routes against a mirror (size, every `get`, absent keys, full and
capped `range`, 12 `count-range` windows, 8 Carver `query` windows, wire and
journal meters, Rub on primary and replica); replay writes nothing; `cold-scan`
equals the preserved moment and keeps equalling it; nine refusals with the
right code and no trace; the physical unchanged by being read; a killed console
`unavailable` in <1 s; the stdio transport end to end. Prints `NOT VERIFIED`
×9 where WholeHog is not built.

## New — `tools/mutate_organism.py` (**11 killed, 0 survived, 1 equivalent**)

Plugin mutants on a copy of `tools/`; console mutants compiled with `javac`
into a scratch classpath (`CSRBT_ORGANISM_CLASSPATH`) — the build is never
written to. First sweep: 12 applied, 8 killed. Three survivors were real holes
(the documented default route, the plugin's own cap, the reader's death
sentinel) and are now killed by checks written for them; one is equivalent
under the contract and recorded with its measurement.

## Docs

- `docs/ADR-112-a-contract-with-one-implementation-is-a-claim-2026-09-01.md`
- `docs/AUTOMATION-HARNESS.md` — the second target, its action table, `--target`
- `docs/AI_HARNESS.md` §11 — the engines
- `WholeHog/README.md`, `WholeHog/CLAUDE.md` — the console and the classpath task

## Held

Runtime chaos (a constructor seam — no button nobody can reach); reads over the
wire (`via` on the read side, unbuilt, named); the per-response snapshot cost
(unpriced on both plugins).
