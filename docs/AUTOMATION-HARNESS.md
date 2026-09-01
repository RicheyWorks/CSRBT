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
| `tools/harness_stdio.py` | the first transport, ~120 lines |
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

| Action | Required arguments | Risk |
|---|---|---|
| `report` | none | `READ` |
| `pulse` | none | `READ` |
| `tick` | none | `NAVIGATE` |
| `quiesce` | `ms` (0–30000) | `NAVIGATE` |
| `get` | `key` | `SENSITIVE_READ` |
| `contains` | `key` | `SENSITIVE_READ` |
| `range` | `lo`, `hi`, `cap` (1–200) | `SENSITIVE_READ` |
| `count-range` | `lo`, `hi` | `SENSITIVE_READ` |
| `query` | `lo`, `hi`, `attr-lo`, `attr-hi`, `cap` | `SENSITIVE_READ` |
| `cold-scan` | `generation` | `SENSITIVE_READ` |
| `put` | `key`, `attr`, `start`, `end`, `via` (`direct`\|`wire`) | `MUTATE` |
| `delete` | `key`, `via` | `MUTATE` |
| `batch` | `ops` (`"p K A S E"` / `"d K"` strings, through Twine) | `MUTATE` |
| `preserve` | none | `MUTATE` |

No action is `DESTRUCTIVE`: an organism has no generic "press this", so the rung
the page needs has no member here and is left empty rather than filled for
symmetry. A write's **route is an argument**, because the organism's claim is
that every route lands in every index, and a client that can name the route can
test the claim. Snapshots carry meters only — sizes, sequences, wire and journal
counters, Rub's vitals on the primary and the replica; a record sample appears
only under `SENSITIVE_READ`.

A dead or silent console is reported `unavailable`, never `failed`: `failed`
accuses the target, and a transport death is not a finding about the organism.
Chaos is a constructor seam on the organism, so there is no chaos action —
`chaosCrashes` is in every snapshot for the day the seam is cut.

## Add another target

Implement `Plugin` — `descriptor()`, `observe(sensitive)`, `execute(action,
arguments)` — and register it. The registry fails on a duplicate plugin id or a
duplicate action name. Ids and action names are lowercase slugs of 1–30
characters, which keeps the combined tool name stable and portable.

Keep domain validation inside the target as well as at the boundary. A risk flag
is a gateway permission, not a substitute for the target's own rules.

## Add another transport

Map four operations — `manifest`, `discover`, `observe`, `execute` — and nothing
else. Do not touch the page from the transport. Keeping adapter code outside the
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

`tools/verify/verify_organism.py` (234 checks) is the evidence that the contract
is target-neutral: the organism plugin driven through the gateway only — default
refusals leaving every meter at zero, redaction both ways, a 160-op differential
oracle over direct, wire and batch routes against a mirror, replay writing
nothing, cold-scan equal to the preserved moment, nine refusals with the right
code and no trace, a killed console `unavailable` in under a second, and the
stdio transport end to end. `tools/mutate_organism.py` breaks the plugin and the
console eleven ways and requires that suite to notice each (11 killed, 0
survived, 1 recorded equivalent).

`tools/verify/verify_swarm.py` is the evidence that the verdicts mean something:
ten fixture pages, nine of them wired and wrong in a different way, one of them
entirely in order.

The heaviest evidence is ordinary use. `tools/swarm.py` drives all forty pages
through this gateway and nothing else — every observation and every action a
command, with a request id, against a policy it names in its own output.
