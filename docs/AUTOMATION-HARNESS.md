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

Every listed tool carries `_meta` — `pluginId`, `action`, `risk`, the contract's
own names (ADR-121): a tool name is a provider-safe slug, and a client that
scopes argument pools by action must not guess `set-text` back out of
`csrbt_page__set_text`. A call's body carries `ms`, `snapshotMs` and the
`requestId` the gateway recorded. MCP returns no snapshot with a call; a client
that observes after every act reads the resource, and that second round trip is
the price of this transport (about a millisecond, on the record in the walk
ledger's `@mcp` entries).

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

**Every response prices its snapshot (ADR-120, protocol 1.2).** An execute
response carries `ms` (the action) and `snapshotMs` (what the target charged to
be asked about itself), timed separately. The organism's and the lab's snapshots
are free; a page's costs more than its actions (91 ms median on collection-sheet
against 69 ms), because reading a page's state means evaluating the control map
over the DOM. The robot reads the price from the responses and keeps it in the
walk ledger per target; the suites bound the median at 250 ms.

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

A pool may be **scoped to an action** — `"set-text.selector"` is the text
controls, `"attach-file.selector"` the file inputs — and a client should prefer
the scoped pool every time: the target said "these". The page plugin publishes
one per action (controls behind a closed tab included, since every action opens
the pane first), plus `pane`, `page` and `choose-option.value`. The organism
publishes one per **bound pair** — `range.lo`/`range.hi`, `count-range`,
`overlap` — in which every low value is below every high one, because "lo below
hi" is a domain no schema can state and a client forming each side from its own
bounds is refused half the time (ADR-123). Where no per-argument pool can say
what goes together — which option value belongs to which select — a pool keyed
by the **action name alone** is a list of whole argument sets, valid right now
(protocol 1.3, ADR-124): the page plugin publishes `choose-option:
[{selector, value}, …]`, and a client takes one set whole and forms the rest.

`tools/harness_walk.py` is the proof (ADR-114, ADR-117, ADR-121): a client that
imports nothing from this kit, speaks the four operations over either transport
(`--transport stdio | mcp`), and forms every call from the schema and the pools
alone. `--target organism | lab | page | all`
walks every plugin the manifest names, keeps the accounting identity
`commands == driven + refused + declined + chaos + failed` per target, reports a
tool whose published pools were empty throughout as `unreachable` (a fact about
the target — a page with no select cannot have `choose-option` driven), and fails
if any other published tool cannot be driven from its schema or any cross-check
between reads breaks. `--target page --page all` walks every routed page (ADR-124)
and keeps each as `csrbt-page/<page>`; its first pass found the robot following
links off the page — to another kit page, and once to the internet — so
`activate` on a link that leaves the document is refused now: leaving is
`open`'s job. Its ledger is `tools/walk_ledger.json`, merged per target
and per transport (`<plugin>@mcp` for MCP walks). The same walk from the same
seed lands every action in the same bucket the same number of times through
either transport — "a transport decides nothing", measured.

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
| `pick` | `selector`, `value` | `DRAFT` |
| `read-control` | `selector` | `SENSITIVE_READ` |
| `read-report` | none | `SENSITIVE_READ` |
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

`pick` (ADR-128) drives a FEK picker the way a finger does: the value goes into
the filter and the option whose label matches exactly, else by prefix, else the
only one left, is clicked; two left is refused as ambiguous. `read-report`
returns the page's report as it stands — every `.l`/`.v` figure flat and by its
box, every box the kit names (`an*`, `*Out`, `*Box`, `*Stats`, `*Note`, `*List`,
`*Table`, `toast` …) whether or not its pane is open, with the visible ones
named in `shown`, every table's cells and every `.row2` list's count. It is
what a task checks a page's arithmetic against.

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
| Sizzle | `restart` | `chaos` (none\|once:N\|every:N\|prob:SEED:P), `latency-ms`, `replica-lag-ms` (0–200), `how` (clean\|cold) | `NAVIGATE` |
| SuperBeefSort | `recovery` | — | `READ` |
| the process | `jvm` | — | `READ` |

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

`restart` also takes `replica-lag-ms` (ADR-120): every replicated event is held
back that long — `Sizzle.slow` on the replication feed seam that SmokeHouse's
`ReplicationServer` and PitBoss pass through — so the fleet's replica is
genuinely behind the primary until a `quiesce` lands the feed. Late, never
wrong: frames arrive in order and none are dropped. `fleet` then reports a lag
that is a reading — measured by PitBoss from the primary it conducts, because a
replica whose feed is held back has not yet received the frame that would tell
it how far behind it is (the first pull of this seam found the fleet reporting
0 for a replica twenty frames behind).

`restart` with `how: cold` (ADR-122) makes the organism **die** instead of
closing — every organ released, the store abandoned without its checkpoint — so
the reopen is SmokeHouse's own recovery: the log scanned, SuperBeefSort sorting
it, the index born from what it measured. `recovery` is engine 2's report of
the last open: entries, whether the checkpoint was used, whether it sorted and
by which strategy at what cost, the feed's sortedness and inversions, the born
tree. A clean restart's report says "nothing sorted"; until this action existed,
that was every restart the harness had ever made, and the recovery engine had
never run under it.

`jvm` (ADR-123) is the process itself — live threads by name, open file
descriptors where the platform counts them, heap in use — and every snapshot
carries its headline. The robot holds it every round: the threads of round one
and no others, descriptors up by no more than the segments the store rolled (a
cached reader each; a `compact` gives them back). `verify_organism` restarts the
organism forty ways and requires the same. The lab's `jvm` is the same
instrument on the science engine.

## Tasks: what an operator is for

A walk proves a target is operable; a **task** asks whether a goal was done
(ADR-125). `tools/tasks/*.json` — a target, a goal in words, steps with
arguments, references to earlier responses (`"$gen.output.generation"`), and
expectations graded `CONFIRMED` / `REFUTED` (`==`, `!=`, `>`, `>=`, `<`, `<=`,
`in`, `not-in`, `contains`, `excludes`, `exists`). `excludes` is how a task says a
box has stopped saying something — a refusal that must also stop computing — and
it is deliberately not satisfied by a missing path, or a typo would read as proof
of absence. A trailing `#n` on the path (no space) labels a second claim about
the same box; a ` #2` with a space is a real path segment, the way `read-report`
writes a duplicate label. An op the grader does not know is the task's DEFECT. A refusal, a decline or a failure is a result a
task can expect; a failure nobody expected is the target's and ends the task;
a reference that does not resolve is the task's own DEFECT, never a finding.
`tools/harness_tasks.py` runs each task on a fresh target through either
transport and keeps `tools/task_ledger.json`; a task that declares `must: FAIL`
is the canary that proves the grader can say no. Eight tasks ship — the
preserve-and-cold-scan road, the crash road, the replica held behind, a cold
recovery, the shipped protocol, a page entered and read back, the fixture's
buckets, the canary — and every one is held. A model handed the goal and the
manifest, and not the steps, is what this grader is for — and has been graded
once (ADR-126): `harness_mcp.py --trace FILE` records every call and observation
a host makes, and `harness_tasks.py --grade-trace FILE` holds that trace to a
task — required steps in order, probes anywhere after, one call per step, the
operator's own detours allowed and counted. Six traces under `tools/traces/`,
planned from the goals alone, every one held; their provenance is stated there.

**A session that can change (ADR-137).** `--attachable` on either door serves
`csrbt-session` -- `targets`, `attach`, `detach` -- and a host may then pick up a
target the session did not start with. Attaching registers the target's plugins
in the live registry; the registry announces, the gateway drops the retired
plugin's replayable responses (a target detached and attached again is a new
target that has done nothing), and the MCP server drops its own tool-name map
and sends `notifications/tools/list_changed` and
`notifications/resources/list_changed`, written BEFORE the response that caused
them. `listChanged` is declared true exactly when `csrbt-session` is served, so
ADR-115's `false` is still the right answer for a session nothing can change.
The stdio door needs no notice: every op re-reads. The consumer is the robot --
`harness_walk --attach <target>` walks the starting target, attaches a second,
re-reads and walks it, then detaches and finds the list exactly what it was.

**The blind trial (ADR-136).** Those six were produced by the session that had
written the tasks. Six more, under `tools/traces/blind/`, were not: a fresh
subagent each, given the task's goal sentence verbatim and
`tools/blind_console.py` — a JSON-RPC console that offers `tools/list`,
`resources/list`, a call and a read, and nothing else — in a checkout with
`tools/tasks/`, `tools/traces/`, the ledger and every ADR deleted. First
grading, 24 of 40 required steps; after four fixes to the instrument, 30 of 30.
The fixes: an `observe` step is met by the snapshot riding ANY response (the
licence is observe's alone); four steps that described the author's route
became probes; a read-back reads `$type.output.value` rather than the literal
the task types; a count claims `>= 3` rather than the author's batch size. And
`load_task` now refuses a required step that reads a probe — a claim may not
rest on a step an operator may skip. The blind traces are a committed check:
`verify_tasks` section F2 requires each to grade PASS and held, which is what
stops a task from quietly re-acquiring its author's route.

**The science (ADR-128).** Twenty-one tasks, one per data-entry page of the
kit, enter data through the gateway and hold the page's report to an oracle
computed by hand: the collection sheet's Chao1 6.5 and H′ 1.359, the stand
sheet's QMD 29.7 and SDI 132, Cohen's κ 0.722, the breeding bench's Nₑ 36.0
and LSD 0.82 kg, the field season's whole seeded meadow from an independent
port of its generator. A task names its controls the page's way —
`"@control:cName"`, `"@control:area searched"`, `"@control:rCov/4"`,
`"@control:iList/died#2"` — resolved to the moment's selector from the latest
snapshot, and never writes a selector down. A page canary claims a wrong figure
and is refuted. `verify_tasks` section G pins that every data-entry page has
one, that each holds a figure and not prose alone, and that the ledger holds
every one with at least twenty confirmed expectations. ADR-129 extended the
sweep to every routed page: the keys, the visualizer, the proofs and the lab
are held to independent ports of their arithmetic, and each reference page
to its outline (`read-report` now carries `headings`); every routed page has
exactly one task, and `verify_tasks` pins it.

## The fourth target: the fixture

`--target fixture` serves `csrbt-fixture` (ADR-119): a plugin built to be
walked, whose every action lands in a known bucket every time — always ok,
always refuses, always declines, raises a Crash under an armed plan, raises
without one, accepts only the slot the latest snapshot publishes, publishes an
empty pool, takes a string nothing can form, records array lengths, flips its
own consistency flag, and (with `CSRBT_FIXTURE_DIE=1`) goes away. It is what
`tools/mutate_walk.py` breaks the robot against, and it is never part of
`--target all`.

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

## The board

`tools/harness_board.py` renders the Harness Board — one page saying what the
harness can vouch for right now — from its ledgers and nothing else: the suites'
counts, the robot's walks of every target and every page, the tasks and traces,
the mutant runners (which record their runs in `tools/mutant_ledger.json` since
ADR-127), the engines' own suites. `verify_board` fails when the committed page
and the ledgers disagree. It is published as an artifact beside the Atlas.

## Verification

`tools/verify/verify_contract.py` covers authentication on every operation, the
minimum token length, policy refusal at each rung, that a refused command never
reaches the plugin, that a caller cannot re-label its own risk, required/unknown/
type-invalid/enum-invalid arguments, unknown action and unknown plugin, replay
and id-collision behaviour, re-authorisation of a replay after a gate closes,
cache bounding, manifest completeness including typed array items, redaction with
and without `SENSITIVE_READ`, provider-safe naming, duplicate-plugin failure, and
that every action the swarm drives with is one the plugin publishes.

`tools/verify/verify_organism.py` (317 checks) is the evidence that the contract
is target-neutral and that the organism does what it says when driven through
it: default refusals leaving every meter at zero, redaction both ways, a 160-op
differential oracle over direct, wire and batch routes against a mirror, replay
writing nothing, cold-scan equal to the preserved moment, nine refusals with the
right code and no trace, a killed console `unavailable` in under a second, the
stdio transport end to end — and (ADR-113) one oracle per engine: wire == direct,
order statistics against the sorted mirror, Carver spans against brute force,
the Renderer fold against the histogram, Brine's hit after its miss, the fleet
through a rebootstrap, `as-of` reading the frozen moment, Jerky verifying,
segments summing to the garbage, and the recovery road under an armed crash —
and (ADR-120) `compact` reclaiming exactly the closed segments' garbage, the
replica held behind the primary and reporting it, and the snapshot priced —
and (ADR-122) a cold restart recovering from the log alone with engine 2's
report naming the sort, its cost and the feed's disorder — and (ADR-123) forty
restarts leaving the process's threads and descriptors where they were.
`tools/mutate_organism.py` breaks the plugin and the console thirty-one ways and
requires that suite to notice each (31 killed, 0 survived, 4 recorded
equivalents).

`tools/verify/verify_walk.py` (120 checks) holds the robot to its claim on every
target: an outsider, a generator that respects every kind of bound and reports
the unformable rather than guessing, live walks of the organism, the lab and two
pages with full coverage and nothing failed, the committed ledger at the same
bar for all three with the snapshot's price on it, and (ADR-119) a walk of the
fixture with every bucket's count pinned exactly. `tools/mutate_walk.py` breaks
the robot twenty-six ways against that suite (the MCP wire, the leak checks and
the argument-set pools included): 26 killed, 0 survived, 2 recorded equivalents.
Section I holds the committed walk of every routed page to the same bar.

`tools/verify/verify_lab.py` (35 checks) holds the third target to the
canonical oracle the repository already keeps — the shipped protocol run through
the gateway must produce the shipped session — and to determinism, grading,
refusal and export. `tools/mutate_lab.py`: 9 killed, 0 survived, 1 equivalent.

`tools/verify/verify_mcp.py` (70 checks) holds the second transport to "decides
nothing": the adapter names no target, both transports share one builder, the
full protocol surface in-process over a fixture, the server as a child over
the organism spoken to in JSON-RPC, and — since ADR-137 — `listChanged` with a
consumer: the declaration honest in both directions, attach and detach and every
refusal by its own code, the server's and the robot's caches dropped on the
notice, the gateway forgetting a retired plugin's replayable responses, the
notices written before the response that caused them, and a real browser page
attached over a real child. `tools/mutate_mcp.py`: 20 killed, 0 survived, 1
recorded equivalent — the runner mutates `harness_contract.py`,
`harness_plugin_session.py` and `harness_walk.py` too, because the notice is the
server's, the change is the registry's, the forgetting is the gateway's, the
attach is the plugin's and the consumer is the robot's.

`tools/verify/verify_tasks.py` (234 checks) holds the task runner to its grammar,
its files and its grader — the canary refuted and held, a bad reference a
defect, a dead target a defect, MCP the same verdicts — runs every task through
the gateway, and holds the trace grader (order, one call per step, probes after
required steps) and the twelve committed traces, six of them blind (ADR-136).
`tools/mutate_tasks.py`: 55 killed, 0 survived — and to carry four of them the
runner mutates TASK FILES as well as the harness, putting the author's
constants back; only the blind operators refuse them.

`tools/verify/verify_audit_states.py` (33 checks) holds the kit's audits to
"everywhere" (ADR-130): `tools/audit_states.py` walks a page through its
states — rest with every `<details>` open, each tab (`data-pane` or
`aria-controls`), each page-specific reveal, a revealed surface's own tabs —
by programmatic click, and keeps the accounting of which controls had a box in
some state; the 44 px, contrast and focus audits measure every state and count
a control no state reached as a fault. The suite pins the states and the
counts on a fixture, the focus audit's own probe after the walk, and runs the
three audits on a fixture directory whose faults are known. `tools/mutate_audit_states.py`:
20 killed, 0 survived.

ADR-131 adds the ENTERED state: `audit_states.enter()` replays the page's own
science task in process on the audit's browser (the task file is the single
source of what entering means for that page — the science task, never a
reference task, a canary, or another page's), then `entered` and each tab from
there are measured like any other state. An entry that could not run, or drove
nothing, is counted as a fault; a refusal on a step written to be refused is
not. The suite pins all four selection rules with fixture tasks that isolate
each, and the focus audit presses and releases a key before every probe so the
browser is in a keyboard user's mood whatever the entry did with the pointer.

ADR-135: a task may name a control by what it IS — `@control:kind=drop_zone` —
for a control the page never named. A `drop` listener on the window stamps the
page's `<body>` as its drop zone, and `FIXTURES["session"]` is the kit's own
shipped experiment session, so a task can hand the interactive lab the session
the engine just wrote and hold every station's figures to it.

ADR-134 (protocol 1.4): a target may publish actions that set the environment a
run happens in. The page plugin publishes `set-clock`, `set-seed` and
`set-dialog` (NAVIGATE) and `read-dialogs` (SENSITIVE_READ); the shim behind
them is installed on every browser target and is the real clock and the real
dice until a caller says otherwise. Each set is re-installed as an init script,
so it survives a reload — which a page that reads the clock at load needs, and
`set-clock` says so in its answer. Every snapshot publishes `environment`: the
clock, the seed, the draws so far, and the dialog answer.

ADR-133: a task's steps may each name a `target`. The runner opens every target
the task names once, keeps them for its life, and closes them in the reverse of
the order they were opened; a reference resolves across targets, so a page's
figure can be held to an engine's. `~=` (with a required tolerance) is how two
instruments that print the same number differently are held to each other. A
step naming a target that does not exist is the task's DEFECT.

`tools/verify/verify_swarm.py` is the evidence that the verdicts mean something:
ten fixture pages, nine of them wired and wrong in a different way, one of them
entirely in order.

The heaviest evidence is ordinary use. `tools/swarm.py` drives all forty pages
through this gateway and nothing else — every observation and every action a
command, with a request id, against a policy it names in its own output.
