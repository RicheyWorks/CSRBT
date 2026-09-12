# ADR-191 — The session: a stamp, and what changed since it

**Status:** accepted · **Date:** 2026-09-11 · **The fourth of the seven slices of `docs/PLAN-operator-api-2026-09-11.md`, and the one that turns a door into an API. Every snapshot now carries a `stamp`; `observe(since=<stamp>)` answers with what CHANGED rather than with the snapshot; every act — over either transport — answers with the same change, against the snapshot the client planned the act from. On the collection sheet that is about two kilobytes where a re-read is a hundred. The plugin says what identity means on its own snapshot and the gateway does the diffing, so the page, the organism, the lab, the fixture and the session target all diff alike. And `blind_console` keeps one door open between invocations, so an attempt is a conversation rather than a replay. `verify_contract` 115 → 143, `verify_mcp` 73 → 89, `verify_report` 160 → 179, `mutate_contract` 36 → 56, `mutate_report` 104 → 110. Protocol 1.7.**

## 1. What the third blind trial was actually reporting

Four operators, four science pages, 200–290 calls to land 73–89 points. The
post-mortem counted the calls and found two shapes, over and over:

    read the snapshot -> act -> read the snapshot -> act -> read the snapshot

and

    run the whole plan again from a fresh page, because the last one is gone

The first is a door with no memory of what it just showed you. The second is
a console with no memory at all. Both are the same missing thing: **a
session** — a conversation in which the second sentence may refer to the
first.

ADR-188 gave the page stable names. ADR-189 made the page hold still before
the first act. ADR-190 made the page say what it offers. All three made a
single call better. None of them made the *second* call cheaper than the
first, and the trial's arithmetic is almost entirely second calls.

## 2. A stamp is a version of the observation

The page already had a version: ADR-188's `version`, a digest of every
selector and id in document order, which moves exactly when an index could
mean a different control. That is the numbering's version, and it is what a
stamped selector is held to.

It is not what a client wants to know after an act. A `set-text` that enters
a name moves no selector at all. So a second stamp, and it is a version of
the *observation*:

    stamp   sec167f74e0a8   moves when any value a reader could notice moves

Both ride every page snapshot, because they answer different questions and a
page that published one of them would leave the other unaskable.

The stamp is computed by the gateway over the snapshot **as served**, after
the ADR-141 pool filtering — so two sessions at different rungs get different
stamps for the same page, and nobody is told `unchanged` about a snapshot
they were never shown.

Two things are deliberately outside it:

- **Noise.** The organism's `jvm` thread and descriptor counts and its
  `replicaLagMs` move on their own. A stamp that moved with them would say
  "changed" on every call to a store nobody had touched, and `unchanged`
  would never be true of anything. The plugin names those paths; the diff
  names them back, so a reader can see what was not compared rather than
  conclude it did not move.
- **Order.** A keyed list is stamped as a set. These pages rebuild their
  controls on nearly every act, in whatever order the rebuild produced, and a
  stamp that moved with the order would contradict the empty diff the same
  two snapshots produce.

## 3. The plugin says what identity means; the gateway does the diffing

    def identity(self, snapshot=None):
        return {"keys": {"controls": ["address", "selector"], "tabs": ["pane"]},
                "noise": ["jvm", "replicaLagMs"]}

That split is the whole design. The gateway cannot know that a page control
is its ADR-188 address rather than its index — and the page cannot know
anything about diffing, and should not have to. So the plugin supplies the
one fact only it has, and one algorithm serves all five targets, held by one
suite.

`keys` names the lists that have identity, by path from the snapshot's root,
each with the fields that identify an entry — first one present wins — or
`"self"` for a list of scalars. A list **not** named there is compared by
length and never entry by entry, because a list with no declared identity
cannot be diffed without inventing an identity for its entries, and inventing
one is how a reordered list reads as everything changing.

The paths are joined with `/` and not `.`, because the page's own pool names
contain dots (`choose-option.value`, `set-text.selector`) and a dotted path
could not say which it meant.

## 4. What an act answers with

    pick  { selector: "pick_search:0", value: "Agaricus" }

    diff  fields    version      v13mnrvv -> vnfmnpn
          altered   controls     "@Agaricus"       selected  false -> true
                                 "@Abies concolor" selector  pick_opt:71 -> pick_opt:6
                                 ... 12 more
                    pickers      pick_search:0     of        66 -> 6
          vanished  controls     40 addresses, and `capped` says there were 65
          counts    pickChoices  79 -> 14
                    argumentPools/address  307 -> 242

    2 021 bytes.  The snapshot it replaces: 76 975.

Every claim in that block is one an operator spent a call finding out, four
times each, in ADR-187. The one that matters most is the second `altered`
line: a control whose **only** change is that it renumbered is reported as
that one field moving. Keyed positionally it would have read as a control
vanishing and a different one appearing — which is the mistake the whole
address grammar exists to stop, and which a diff written before ADR-188 would
have had to make. That is why these two slices are in this order.

The baseline is the last snapshot **this session was served** — the one the
client planned the call from — so the diff answers the question the client
actually has. A session that has never observed is told it has no baseline
rather than handed a diff against nothing. A stamp the session holds no
baseline for — from another door, or from before a plugin was detached — gets
the whole snapshot and the reason. It fails toward more information, never
less.

## 5. The diff rides the tool result; the snapshot never did

MCP's `tools/call` result has never carried the snapshot, and for a good
reason: it is read by a model with a context window and these snapshots are
seventy to a hundred kilobytes. That is exactly why every blind operator
followed every act with a full `resources/read`.

The diff is the affordable version of that re-read, so it rides every call.
And `resources/read` takes the stamp where MCP allows a parameter at all —
in the URI:

    harness://csrbt-page/snapshot?since=sec167f74e0a8

The same URI without the query is the resource it always was, so a host that
has never heard of stamps reads exactly what it read before.

## 6. A console that remembers

    python3 tools/blind_console.py --session s1 --target page \
            --page collection-sheet.html --moves first.json
    python3 tools/blind_console.py --session s1 --moves next.json
    python3 tools/blind_console.py --session s1 --end

The first call starts a server holding the door behind a unix socket; the
rest hand it moves. The page is where the last call left it, the store holds
what was put in it, and a stamp issued in one invocation is still the door's
baseline in the next.

This is the half of ADR-187's arithmetic that no length of moves file could
buy. An operator reads an answer, thinks, and writes the next move — and
until now "writes the next move" meant "throws the page away and starts
again".

## 7. What SENSITIVE_READ has promised since ADR-108

    "entered values omitted; use read-control with SENSITIVE_READ enabled"

The snapshot said that and then, under SENSITIVE_READ, omitted them anyway —
so a client holding the rung spent one call per control to collect what the
snapshot could have said in the call it was already making. It also made the
observation's stamp a lie by omission: a `set-text` that entered a name moved
nothing the snapshot could see, so the diff of the act that **enters data** —
which is what these pages are for — answered `nothing changed`.

A commandable control now carries its `value` under SENSITIVE_READ and under
nothing else, as the field holds it, capped at 200 characters. `commandable`
is what excludes a password field, so a value published past that test would
publish one; the suite holds that a control this session may not command
hands over nothing.

## What moved

    verify_contract    115 → 143      mutate_contract   36 → 56 / 56
    verify_mcp          73 →  89      mutate_report    104 → 110 / 110
    verify_report      160 → 179
    protocol           1.6 → 1.7

    the cost of learning what your own call did, on the collection sheet:
        76 975 bytes  ->  2 021

## Held

- One baseline per target per session, and it is the last snapshot served.
  A client that reads every response never falls behind; one that ignores
  intermediate responses does, and is handed the whole snapshot with the
  reason rather than a diff against a moment it does not remember.
- `counts` is a length, not a summary of contents. A pool whose entries
  churned without its length changing reports nothing in the diff — and the
  stamp still moves, so it is never reported as unchanged.
- The page's argument pools are counted rather than keyed, with one
  exception. Every one of them is derived from `controls`, so a keyed pool
  would say a second time, in selectors, what the controls list has already
  said in addresses. The exception is `activate.destructive`: short, and a
  button that removes work arriving in the set the door holds at DESTRUCTIVE
  is worth a line of its own.
- A diff is capped at forty entries per bucket, and where it stopped naming
  it says so with how many there were. A diff is a saving over the snapshot
  or it is nothing.
- The console's session is serial: one connection at a time, one operator.
  Two clients on one page at once would be a different experiment than the
  one this console is for.
- No page and no task was edited. The 44 science tasks read `boxes`,
  `figures` and `by`, none of which moved.
