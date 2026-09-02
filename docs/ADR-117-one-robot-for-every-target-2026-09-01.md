# ADR-117 — One robot for every target

**Status:** accepted · **Date:** 2026-09-01 · **Extends ADR-114; closes ADR-116's "the walker does not walk the lab"**

## 1. A robot for one target is a robot for one target

ADR-114's walker proved the organism operable from its manifest alone. It
was written for the organism: it asserted the plugin id, its cross-checks
were the organism's reads, and its ledger was the organism's. ADR-116 wired
the science lab and said, in its held list, *the walker does not walk the
lab*. And no robot had ever walked a page — the swarm drives pages, but the
swarm read the source.

The claim worth having is not "the organism is operable from the manifest"
but "**any** target behind this gateway is". That needs one robot, and the
same robot, for all of them.

## 2. The decision

`tools/organism_walk.py` becomes **`tools/harness_walk.py`**, target-neutral.
`--target organism | lab | page | both | all` stands the targets up through
the shared builder and the robot walks **every plugin the manifest names**,
one ledger entry each, merged (ADR-108's ledger rule) into
`tools/walk_ledger.json`. Forming calls, the five buckets, the accounting
identity and the coverage floor know nothing about any target. Three things
had to be said precisely for that to be true.

**Scoped pools.** A snapshot's `argumentPools` may carry
`"<action>.<argument>"` as well as `"<argument>"`. The robot prefers the
scoped pool *every time* — the target said "these are what this action can
act on", and mixing examples into that is noise — and falls back to the
plain pool, then the schema. The page plugin publishes `set-text.selector`,
`attach-file.selector`, `activate.selector` and so on from the same kind
map the swarm's `DRIVER` holds (the suite pins that they agree), plus `pane`,
`page` and `choose-option.value` (the page's own option values, which are
choices the page offers and not values a user typed). Controls **inside a
closed pane** are in the pools: every page action opens the control's pane
before acting, so a control behind a tab is reachable, and a pool that
omitted it would have hidden half the kit.

**Unreachable is a fact, not a hole.** A page with no `<select>` cannot have
`choose-option` driven, and calling that *undriven* would fail the coverage
floor on a fact about the page. When the pools a tool's required arguments
would draw from are published and **empty every time they were looked at**,
the tool is `unreachable`: reported, kept out of the floor, and not a
failure. `collection-sheet.html` reports exactly four — no select, no drop
zone, no checkbox, no slider — and `ecology-lab.html`, which has selects,
drives `choose-option` from the option-value pool.

**Cross-checks are keyed by plugin id.** The one place a target's meaning is
used — reads against reads, never against what was written — is
`INVARIANTS`: the organism's (unchanged), the lab's (its own counters must
equal what this walk drove: runs, lints, battles, adapts, field days), and
the page's (the invariants `read-page` already publishes: exactly one pane
open, no `NaN`/`[object Object]` rendered, no uncaught error, nothing
spilling sideways). A target with no entry gets the general oracle, which is
still a walk.

## 3. What the robot found on its first walk of the other two targets

Six things, in the lab, the page plugin, and — for the first time — the
core.

| where | finding | fix |
|---|---|---|
| **csrbt-core** | `adapt` with 20k+ keys and 50k ops killed the lab console with a `StackOverflowError` at ~1,000 frames of `StrategyHealthCheck.isBst` — the Splay candidate a morph builds aside from sorted keys is a chain as deep as the set, and the BST check recursed down it. A validator that dies on the trees it exists to validate | `isBst` is iterative, bounds travelling on an explicit stack. `HealthCheckDeepChainProbeTest` pins it with a 60k chain (confirmed to overflow the recursive form on a default stack) |
| both plugins | the console died *loudly* — a thousand frames on stderr — and the plugin reported `no answer within 120s` instead of `exited`. Nobody read stderr; the pipe filled; the JVM blocked on its own trace and never exited. **A detector with no alarm** | stderr is drained into a bounded tail by its own thread, and the tail is what the death message carries |
| both consoles | an `Error` escaped `answer()` and took the process with it | `Error` is caught like `Exception`: one verb failed, the console keeps serving |
| page plugin | `set-text` to a button → `TypeError: Illegal invocation` from the value setter, filed as the page failing | a wrong-kind selector is the caller's: `invalid_argument: not a text control`; likewise `set-slider` on a non-range, `set-checkbox` on a non-checkbox |
| page plugin | `attach-file` to a button raised out of Playwright; two files to a single-file input raised too | both `invalid_argument`, before Playwright is asked |
| page plugin | `drop-files` on *any* element "succeeded" — drag events dispatched at a button return `ok`. A driven that drove nothing | only an element carrying `data-h-drop` is a drop zone |

The `open` action needed a decision too. Its `page` pool was every kit page,
so the robot hopped pages mid-walk and the ledger was about whatever the pool
hit. The pool and the example are now the page the plugin is on; a walk
stays on its page, and every kit page is in `tools/routes.json` for a client
that wants another. The default page for a page walk is `collection-sheet`
— the old default, `ecology.html`, is the hub, which has fifty-four links
and nothing else.

## 4. Evidence

`tools/verify/verify_walk.py` (replaces `verify_organism_walk`), **49
checks**: the robot is an outsider; the generator respects every bound,
reaches every enum, uses pattern examples verbatim, prefers a scoped pool
every time and a plain pool most of the time, forms arrays one-first, and
reports the unformable; live walks of the organism (33/33), the lab (8/8,
protocols run and a bundle exported from the schema's example) and two
pages (collection-sheet: 11 driven and the four unreachable named;
ecology-lab: `choose-option` driven from the option pool) — identity holds,
nothing unschemable, nothing broken, nothing failed; the committed ledger
holds for all three targets; and the page plugin's pool kinds agree with the
swarm.

The committed ledger (`tools/walk_ledger.json`, 8 rounds × 3 per tool):
organism 900 commands: 805 driven, 91 refused, 0 declined, 4 chaos, 0 failed; lab 192 commands: 184 driven, 8 refused, 0 declined, 0 chaos, 0 failed; page (collection-sheet) 368 commands: 248 driven, 120 refused, 0 declined, 0 chaos, 0 failed.

`verify_contract` 85 → **87** (an enum on an array is per item, published on
the items). `verify_organism` and `verify_lab` unchanged and green.
csrbt-core: `HealthCheckDeepChainProbeTest`; core and experimental suites
green, javadoc clean. WholeHog 21 green.

## 5. Held

- **The page walk is a smoke walk, not the swarm.** Its oracle is the page's
  general invariants; it does not know that a `+` should add a row. The swarm
  still owns the per-control expectations. The robot's value on a page is
  that it got there from the manifest and the snapshot alone.
- **The lab's invariants are its counters.** That a `run` graded the right
  thing is `verify_lab`'s job, against the canonical session.
- **`unreachable` is decided by pools.** A target that publishes no pool for
  an argument can never be unreachable, only undriven — which is the right
  default: a target that says nothing about what it offers does not get to
  be excused for offering nothing.
