# The CSRBT automation harness

The kit exposes a provider-neutral automation contract for AI agents, test
runners, accessibility tools, and future transports. It embeds no model SDK and
gives no model unrestricted access to the page. A small typed gateway sits
between every client and each target:

```text
AI provider / MCP / script / test runner / accessibility tool
                 │
       stdio, REST, MCP, or another adapter
                 │
         HarnessGateway (token + policy + replay safety)
                 │
         HarnessRegistry (plugin discovery)
                 │
         HarnessPlugin implementations
                 │
         A CSRBT page in a browser, or the WholeHog organism
```

The gateway and the plugin interface are the contract. stdio is only the first
transport. A client can connect an OpenAI-compatible tool, a local model, an MCP
server, or an ordinary script without changing the plugin, because a transport
maps exactly four operations and decides nothing.

| file | what it is |
|---|---|
| `tools/harness_contract.py` | risk ladder, policy, argument specs, registry, gateway |
| `tools/harness_plugin_page.py` | the `csrbt-page` plugin: one page in a browser |
| `tools/harness_plugin_organism.py` | the `csrbt-organism` plugin: the fourteen-engine organism in a child process (ADR-112) |
| `tools/harness_plugin_lab.py` | the `csrbt-lab` plugin: the science engine — protocols graded, the arena, the controller, the field day (ADR-116) |
| `tools/harness_stdio.py` | the first transport, ~120 lines |
| `tools/harness_mcp.py` | the second transport: MCP (JSON-RPC 2.0 over stdio), no SDK (ADR-115) |
| `tools/harness_targets.py` | stands a target up for either transport — the only file that names one |
| `tools/swarm.py` | the contract's first client, and its heaviest user |

## Safety defaults

The harness is **off by default**. No transport serves anything unless
`CSRBT_HARNESS_ENABLED` is `true`, and every request needs a separate harness
token of at least 24 characters — required on every operation, including
discovery, and read from the environment rather than from a command line, where
it would sit in a process list and a shell history.

Actions carry a risk **declared by the plugin**, never claimed by the caller:

| Risk | Default | Meaning |
|---|---:|---|
| `READ` | allowed | Discover plugins and observe control metadata |
| `NAVIGATE` | allowed | Open a pane or a page without changing a record |
| `SENSITIVE_READ` | blocked | Read entered values, page text, or pixels |
| `DRAFT` | blocked | Enter a temporary field or option value |
| `MUTATE` | blocked | Change persistent data, including the autosave |
| `DESTRUCTIVE` | blocked | Generic activation whose effect cannot be known |

`DESTRUCTIVE` cannot be enabled unless `MUTATE` is also enabled. The page plugin
classifies generic button activation as `DESTRUCTIVE` deliberately, because a
selector on these pages may resolve to *Add row*, to *Clear trial*, or to *Copy
CSV*, and deciding which from the label is exactly the guess this contract
exists to refuse. This is stricter than reading the button's text, on purpose.

Observation is value-redacted: a snapshot publishes kind, selector, label, pane,
visible, enabled and commandable, and never what is in a field. Labels *are*
published, and on a page that renders entered records into a list a label can
contain what a user typed — the manifest says so rather than pretending
otherwise. Protect the token and treat observations as private field data.

## Enable the stdio transport

Use a per-session secret. This example allows observation, navigation and
drafting, and nothing else:

```bash
CSRBT_HARNESS_ENABLED=true \
CSRBT_HARNESS_TOKEN=replace-with-at-least-24-random-characters \
CSRBT_HARNESS_ALLOW_DRAFT=true \
python3 tools/harness_stdio.py --page collection-sheet.html
```

Every rung has its own switch: `CSRBT_HARNESS_ALLOW_NAVIGATE`,
`CSRBT_HARNESS_ALLOW_SENSITIVE_READ`, `CSRBT_HARNESS_ALLOW_DRAFT`,
`CSRBT_HARNESS_ALLOW_MUTATE`, `CSRBT_HARNESS_ALLOW_DESTRUCTIVE`. Enable only what
the supervised session needs, then unset them. Do not put the token in a URL, a
prompt, a source file, a screenshot, or a transcript.

## Enable the MCP transport — plug a model in

The same policy and token, in the environment of the server process. A host's
config is the whole of it:

```json
{"mcpServers": {"csrbt": {
  "command": "python3",
  "args": ["/path/to/CSRBT/tools/harness_mcp.py", "--target", "organism"],
  "env": {"CSRBT_HARNESS_ENABLED": "true",
          "CSRBT_HARNESS_TOKEN": "<at least 24 random characters>",
          "CSRBT_HARNESS_ALLOW_MUTATE": "true"}}}}
```

`tools/list` shows **only the tools the policy allows** (the risk is the first
word of each description, and an MCP annotation: `readOnlyHint` for READ,
NAVIGATE and SENSITIVE_READ, `destructiveHint` for MUTATE and DESTRUCTIVE).
`tools/call` is `execute` with **the JSON-RPC id as the request id**, so a host
that retries with the same id gets the replay, not a second write. Each target's
snapshot is a resource, `harness://<plugin>/snapshot`, redacted under the
session's policy. A badly formed call is `-32602` with the gateway's code in the
message; a policy refusal is `-32001`; a target that ran and said no is a normal
result with `isError: true`. The token never crosses the protocol.

## The four operations

```json
{"op":"manifest","token":"..."}
{"op":"discover","token":"..."}
{"op":"observe","token":"...","plugin":"csrbt-page"}
{"op":"execute","token":"...","plugin":"csrbt-page",
 "command":{"request_id":"01H...","action":"show-pane",
            "arguments":{"pane":"log"}}}
```

An adapter bootstraps itself from `manifest` alone. It carries the protocol
version, the replay-cache limits, strict-argument behaviour, the minimum token
length, the effective policy for every risk, the plugin descriptors, and one
JSON Schema per action. Tool names are `plugin_id__action`, contain only
provider-safe letters, numbers, hyphens and underscores, and stay within 64
characters. Array arguments publish an `items.type` as well as their outer
`array` type, so a provider can tell a list of row indexes from a list of
labels.

`allowed: false` on a tool is an instruction to omit or disable it for the
current session, not a hint. The gateway enforces the same policy independently
if a client submits the command anyway.

**The schema is enough to form a call (ADR-114, protocol 1.1).** Integer and
number arguments publish `minimum`/`maximum` (inclusive); string arguments and
arrays of strings publish a `pattern` (full-match; on the items for arrays) —
and a pattern always comes with `examples` that satisfy it, because a pattern
with no example is a lock with no key. Unbounded integers such as keys carry
`examples` as a pool to draw from. The gateway enforces all of it before a
plugin runs: outside a bound or a pattern is `invalid_argument`. A value that is
a fact of the moment rather than of the schema — which generations exist right
now — is published in the snapshot as `argumentPools`, a map from argument name
to currently valid values; observe, then act on what you observed.

`tools/organism_walk.py` is the proof: a client that imports nothing from this
kit, speaks the four operations over stdio, and forms every call from the
schema alone. It drives all thirty-three organism actions, keeps the accounting
identity `commands == driven + refused + declined + chaos + failed`, and fails
if any published tool cannot be driven from its schema or any cross-check
between reads breaks. Its ledger is `tools/organism_ledger.json`.

## Replay safety

Every command carries a caller-generated `request_id`. Replaying the same id
with the same body returns the cached response with `replayed: true` and does not
operate the page twice. Reusing that id with different contents is a `conflict`.
The cache is bounded to 256 completed commands or 8 MiB of output, whichever
comes first; durable orchestration should keep its own audit and retry state.

A replay is **authorised again before it is served**. A response captured while
`SENSITIVE_READ` was open must not keep flowing after an operator closes it, so
tightening the policy takes effect on the next call rather than the next
restart.

## What the page plugin publishes

| Action | Required arguments | Risk |
|---|---|---|
| `open` | `page` | `NAVIGATE` |
| `show-pane` | `pane` | `NAVIGATE` |
| `set-text` | `selector`, `value` | `DRAFT` |
| `choose-option` | `selector`, `value` | `DRAFT` |
| `set-slider` | `selector`, `value` | `MUTATE` |
| `press-step` | `selector`, `direction` | `MUTATE` |
| `activate` | `selector` | `DESTRUCTIVE` |
| `read-control` | `selector` | `SENSITIVE_READ` |
| `read-page` | none | `SENSITIVE_READ` |
| `collect-output` | none | `SENSITIVE_READ` |
| `capture-screen` | none | `SENSITIVE_READ` |

Selectors are the `kind:index` names a snapshot publishes — `dial_btn:2`,
`text_in:7`. They are positional within a kind and **the widgets rebuild**, so a
client observes, then acts on what it observed. Every snapshot re-stamps; a stale
selector gets `not_found` rather than the wrong element. A client that holds a
selector across a rebuild and judges the result by the label it remembers will
apply one control's expectation to another — which is a mistake the swarm made
before it was corrected, and the reason this paragraph exists.

Sensitive perception is bounded on every axis: `read-control` covers one visible
non-password control, caps text at 8,000 characters, caps option and picker
lists, and reports `truncated` rather than clipping silently. `capture-screen`
returns a base64 PNG and refuses over 4 MiB. Password controls are refused even
when the gate is open.

No file-chooser action is published. Choosing a file needs OS focus and an
approval policy the gateway does not own, so it stays an explicit transport or
plugin extension — and the swarm excludes file inputs with that reason rather
than reaching around the contract to drive one.

## The second target: the organism

ADR-112 put **WholeHog** — the integration organism composing every engine of the
ecosystem over one store — behind the same gateway. `harness_stdio.py --target
organism` serves it; `--target both` serves it and a page from one registry, with
distinct tool names (`csrbt_organism__put`, `csrbt_page__set_text`). Nothing
below the transport's argument parser changed, and `verify_organism` pins that.

It needs the engine built once, as a sibling of this repo (or wherever
`CSRBT_WHOLEHOG` points):

```bash
cd ../WholeHog && ./gradlew harnessClasspath     # writes build/harness/classpath.txt
```

| Engine | Action | Arguments | Risk |
|---|---|---|---|
| Rub | `report`, `pulse`, `history` | none | `READ` |
| Rub | `tick` | none | `NAVIGATE` |
| — | `quiesce` | `ms` (0–30000) | `NAVIGATE` |
| SmokeHouse | `get`, `contains` | `key`, `via` | `SENSITIVE_READ` |
| SmokeHouse | `range` | `lo`, `hi`, `cap` (1–200), `via` | `SENSITIVE_READ` |
| SmokeHouse | `count-range` | `lo`, `hi`, `via` | `SENSITIVE_READ` |
| SmokeHouse | `segments` | none | `READ` |
| SmokeHouse | `compact` | none | `MUTATE` |
| CSRBT | `order` | `kind` (rank\|nth\|median\|percentile\|first\|last\|size), `arg`, `via` | `SENSITIVE_READ` |
| CSRBT | `depth` | `key` | `SENSITIVE_READ` |
| Carver | `query` | `lo`, `hi`, `attr-lo`, `attr-hi`, `cap` | `SENSITIVE_READ` |
| Carver | `overlap` | `lo`, `hi`, `cap` | `SENSITIVE_READ` |
| Carver | `stab` | `point`, `cap` | `SENSITIVE_READ` |
| Renderer | `groups` | `top` (1–1000) | `SENSITIVE_READ` |
| Brine | `cache-get` | `key` | `SENSITIVE_READ` |
| PitBoss | `fleet` | none | `READ` |
| PitBoss | `replica-get` | `key` | `SENSITIVE_READ` |
| PitBoss | `rebootstrap` | none | `MUTATE` |
| Twine | `batch` | `ops` (`"p K A S E"` / `"d K"`) | `MUTATE` |
| Twine | `recover` | none | `MUTATE` |
| SmokeSignal | `put` | `key`, `attr`, `start`, `end`, `via` (`direct`\|`wire`) | `MUTATE` |
| SmokeSignal | `delete` | `key`, `via` | `MUTATE` |
| DryAge | `preserve` | none | `MUTATE` |
| DryAge | `generations` | none | `READ` |
| DryAge | `as-of` | `generation`, `key` | `SENSITIVE_READ` |
| DryAge | `retain-newest` | `count` | `MUTATE` |
| Jerky | `verify-archive`, `archive-names` | `generation` | `READ` |
| Jerky | `cold-scan` | `generation` | `SENSITIVE_READ` |
| Sizzle | `restart` | `chaos` (none\|once:N\|every:N\|prob:SEED:P), `latency-ms` | `NAVIGATE` |

Thirty-three actions (ADR-113): every engine of the organism is reachable by
its own surface. `via` is on every read the wire can answer as well as on the
writes, so a client can test that the wire reads what the store reads.

No action is `DESTRUCTIVE`: an organism has no generic "press this", so the rung
the page needs has no member here and is left empty rather than filled for
symmetry. A write's **route is an argument**, because the organism's claim is
that every route lands in every index, and a client that can name the route can
test the claim. Snapshots carry meters only — sizes, sequences, wire and journal
counters, Rub's vitals on the primary and the replica; a record sample appears
only under `SENSITIVE_READ`.

A dead or silent console is reported `unavailable`, never `failed`: `failed`
accuses the target, and a transport death is not a finding about the organism.

Chaos goes through the front door. Sizzle is a constructor seam on the
organism, so `restart` closes it and reopens it at the same root under a plan —
which is also the crash-recovery road, because construction replays Twine's
journal into every index. Arm `once:2`, commit a batch (`failed`: `Sizzle.Crash`
at op 2, `chaosCrashes: 1`), `restart` clean (`journalReplays: 1`), and read the
batch back whole. `restart` is `NAVIGATE`: it changes no record, and a plan only
makes later writes fail. After `rebootstrap`, snapshots say
`replicaObserverDetached: true` until the next restart — the replica vitals line
is then about a store nobody reads, and the snapshot says so.

## The third target: the science engine

`--target lab` serves `csrbt-lab` (ADR-116): csrbt-experimental's classroom
runner, arena, adaptive controller and field day. Build it once:

```bash
./gradlew :csrbt-experimental:harnessClasspath
```

| Action | Arguments | Risk |
|---|---|---|
| `protocols` | none | `READ` |
| `lint` | `protocol` | `READ` |
| `run-protocol` | `name` (the shipped `.eco` files, an enum) | `NAVIGATE` |
| `run` | `protocol` (an `.eco` text, ≤ 64 KiB; the schema carries a runnable example) | `NAVIGATE` |
| `battle` | `workload` (enum), `ops` (100–50000), `seed` | `NAVIGATE` |
| `adapt` | `keys` (1–100000), `ops` (1–50000), `seed` | `NAVIGATE` |
| `field-day` | none | `NAVIGATE` |
| `export` | `protocol` | `MUTATE` |

A `run` returns the narrated report, the lab-page session, every hypothesis
with its observed value and verdict (`CONFIRMED` / `REFUTED` / `UNGRADEABLE`),
and the export names. Compute that persists nothing is `NAVIGATE`; `export`
writes the bundle (CSVs, HTML, `workbook.xlsx`, `report.pptx`) into scratch the
plugin owns and is `MUTATE`. A protocol's `dwc:` line is refused at the boundary
and at the console: through the harness it would be the harness reading the
operator's disk. `--target all` serves the organism, the lab and a page from one
registry.

## Add another target

Implement `Plugin` — `descriptor()`, `observe(sensitive)`, `execute(action,
arguments)` — and register it. The registry fails on a duplicate plugin id or a
duplicate action name. Ids and action names are lowercase slugs of 1–30
characters, which keeps the combined tool name stable and portable.

Keep domain validation inside the target as well as at the boundary. A risk flag
is a gateway permission, not a substitute for the target's own rules.

## Add another transport

Map four operations — `manifest`, `discover`, `observe`, `execute` — and nothing
else. There are two now (stdio and MCP), and neither knows what it fronts: stand
the targets up with `harness_targets.stand_up(target)` and hand the registry to a
`Gateway`. Do not touch the page from the transport. Keeping adapter code outside the
plugin preserves one policy, one action schema, one replay rule and one test
surface for every client. Authentication beyond the token, rate limits, prompt
approval and transcript retention belong to the adapter and its operator.

## Verification

`tools/verify/verify_contract.py` covers authentication on every operation, the
minimum token length, policy refusal at each rung, that a refused command never
reaches the plugin, that a caller cannot re-label its own risk, required/unknown/
type-invalid/enum-invalid arguments, unknown action and unknown plugin, replay
and id-collision behaviour, re-authorisation of a replay after a gate closes,
cache bounding, manifest completeness including typed array items, redaction with
and without `SENSITIVE_READ`, provider-safe naming, duplicate-plugin failure, and
that every action the swarm drives with is one the plugin publishes.

`tools/verify/verify_organism.py` (284 checks) is the evidence that the contract
is target-neutral and that the organism does what it says when driven through
it: default refusals leaving every meter at zero, redaction both ways, a 160-op
differential oracle over direct, wire and batch routes against a mirror, replay
writing nothing, cold-scan equal to the preserved moment, nine refusals with the
right code and no trace, a killed console `unavailable` in under a second, the
stdio transport end to end — and (ADR-113) one oracle per engine: wire == direct,
order statistics against the sorted mirror, Carver spans against brute force,
the Renderer fold against the histogram, Brine's hit after its miss, the fleet
through a rebootstrap, `as-of` reading the frozen moment, Jerky verifying,
segments summing to the garbage, and the recovery road under an armed crash.
`tools/mutate_organism.py` breaks the plugin and the console nineteen ways and
requires that suite to notice each (19 killed, 0 survived, 3 recorded
equivalents).

`tools/verify/verify_organism_walk.py` (26 checks) holds the first robot to its
claim: an outsider, a generator that respects every kind of bound and reports
the unformable rather than guessing, a live walk with full coverage and nothing
failed, and the committed ledger at the same bar.

`tools/verify/verify_lab.py` (35 checks) holds the third target to the
canonical oracle the repository already keeps — the shipped protocol run through
the gateway must produce the shipped session — and to determinism, grading,
refusal and export. `tools/mutate_lab.py`: 9 killed, 0 survived, 1 equivalent.

`tools/verify/verify_mcp.py` (31 checks) holds the second transport to "decides
nothing": the adapter names no target, both transports share one builder, the
full protocol surface in-process over a fixture, and the server as a child over
the organism spoken to in JSON-RPC. `tools/mutate_mcp.py`: 6 killed, 0 survived,
1 recorded equivalent.

`tools/verify/verify_swarm.py` is the evidence that the verdicts mean something:
ten fixture pages, nine of them wired and wrong in a different way, one of them
entirely in order.

The heaviest evidence is ordinary use. `tools/swarm.py` drives all forty pages
through this gateway and nothing else — every observation and every action a
command, with a request id, against a policy it names in its own output.
