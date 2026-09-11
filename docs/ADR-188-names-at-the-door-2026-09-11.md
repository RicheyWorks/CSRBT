# ADR-188 — Names at the door: a control is addressed by what the page calls it, not by where it happens to be

**Status:** accepted · **Date:** 2026-09-11 · **Four blind operators converged on one complaint (ADR-187): `action_btn:N` indexes the whole page and renumbers silently on every structural change, the snapshot publishes a stable `id` for a third of the controls — and no tool accepted one. `@control:<name>` existed, but the task runner resolved it, on the far side of the door the operator was speaking through. Every `selector` argument now takes an ADDRESS: the index as before, the index stamped with the snapshot it came from, the page's own id (`#cName`), or the page's own name for the control (`@working name`, `@rCov/4`, `@iList/died#2`, `@kind=drop_zone`). Every control in a snapshot publishes the shortest address that resolves back to itself — on the four pages of the trial that is all of them, no index left — and the pools publish them beside the selectors. A stamped index whose numbering has moved is refused and told what sits there now, instead of pressing it. `verify_report` 120 → 140, `mutate_report` 75 → 89. No page and no task was edited.**

## 1. The complaint

> *"Stable ids exist (`tAdd`, `iAdd`, `ecoCopy`) but no tool accepts them."*
> — the stand-sheet operator, ADR-187

All four said a version of it. `action_btn:N` is a flat index over every
activatable control on the page, so filtering a species list from 34 matches
to 2, loading a character pack, tallying a stem or adding a trait chip shifts
every later index. Two operators pressed the wrong button on the way (ADR-141's
raise caught the destructive ones and said what had moved, which is the only
reason it was survivable). All four re-observed after every structural change
and computed offsets by hand: `iAdd = 51 + stems`, `ecoCopy = 17 once the list
is at 2 matches with 4 stems`. That is a human being doing the page's
bookkeeping because the door would not.

And the names were there the whole time. ADR-128 built the grammar —
`@control:rCov/4` — and `tools/harness_tasks.py` resolves it out of the last
snapshot a step carried, *before* the call goes through the gateway. A task
gets names. An operator gets indexes.

## 2. What an address is

    text_in:3            the moment's index, exactly as before
    text_in:3@v1x7k      the same index, stamped with the snapshot it came from
    #cName               the page's own id
    @working name        the page's own name: id, then label, then host,
    @rCov/4              then host/label, "#n" for the nth such, and
    @kind=drop_zone      "kind=" for a control the page never named

The `@` grammar is ADR-128's, unchanged, down to its two edge rules: a name
that matches *whole* is taken whole, so a label carrying a slash (`Print / save
PDF`) is reachable unscoped (ADR-174), and a trailing `#n` is an index into the
matches, so a label that ends in `#` is still a label. `@control:<name>` — the
runner's own spelling — is accepted verbatim, so an argument can be lifted out
of a task and pasted into a call.

**A plain positional selector is passed through untouched.** It is what every
client wrote before this slice, what the pools still publish first, and what
the walk drives; `_reach` already answers one the page has moved past with the
numbering it has now. Only the three new forms are resolved.

## 3. Every control publishes one

`observe` now carries a `version` — a digest over every selector and id in
document order, so it moves exactly when an index could start meaning a
different control — and every control carries an `address`: the shortest form
that **resolves back to that control through the resolver itself**. Each
candidate is tried, in order (`#id`, `@label`, `@host/label`, `@host/label#n`,
`@label#n`, `@host`), and the first that round-trips is published; a label that
happens to end in `#2`, or an id some other control answers to first, falls
through rather than being published as a name that does not work. If none
round-trips the address is the index, stamped. On the four pages of the trial,
none is: the collection sheet publishes 33 `#id` addresses and 274 `@name`
ones, and not a single fallback.

The kit's own pages name everything, which is exactly why the awkward cases
are *built* rather than found: the suite drives a four-button page where one
control's id is another's label (the id wins), a label repeats under one host
(the second is `@zzHost/dup#1`, and publishes that), and one button carries no
name at all (its address is its index, stamped). An address scheme is only as
good as what it does when the page will not help.

The pools gain one key, `address`, listing them for exactly the controls the
`selector` pool lists — published *beside* the selectors, the way ADR-141
published `activate.destructive` beside them, because a pool that named only
indexes is what taught four operators to count buttons.

## 4. The stamp, and the risk read

A stamped index is compared against the live version. Same: resolved. Different:
refused, naming the version it carried, the version the page is at, and what is
at that index *now* — its label and its stable address — so the caller can see
whether it is still the control they meant. Nothing is pressed.

The risk read had to learn addresses too, and this is the part that would have
been a silent regression. ADR-141 raises `activate` to DESTRUCTIVE when the
selector resolves to nothing, because such a selector is the moment's and the
trial watched a stale one delete a tallied stem while answering `ok: true`.
`risk_for` runs *before* `execute`, on the caller's own arguments — so without
resolving there, every stable address would have arrived as "resolves to
nothing" and been refused at the top rung: the door refusing the very thing it
had just learned to accept.

So `risk_for` resolves first. And an address that resolves to nothing is **not**
raised: the ADR-141 rule is about an index, which is the moment's; a name is
not the moment's, so a name that answers to nothing is a typo, and `execute`
says so as a not-found. An unresolvable *positional* selector is still held at
DESTRUCTIVE, unchanged. A control named for removing something is still raised
through its address exactly as through its index — the raise reads the control,
not the spelling.

## 5. Two implementations, held to each other

The runner keeps its own `find_control`. That is deliberate, and it is the
kit's standing rule rather than an exception: the runner resolves against the
snapshot a task already has, which is what makes a task reproducible; the door
must resolve against the live page, because an operator has no snapshot to
hand. Two implementations of one grammar is how a port becomes two ports that
drift — so they are held to each other, empirically, on three real pages:
every id, every label and every host/label the snapshot offers is put to both,
and the answers must be equal. That is 1,200-odd names on the collection sheet
alone, and it is the check that would fail first if either side were edited
alone. Retiring the runner's copy is ADR-191's business, once the session
exists.

## What moved

    verify_report                 120 → 140      mutate_report   75 → 89 / 89
    harness_plugin_page.py        the address grammar, the resolver, the version,
                                  an address per control, the `address` pool

One plugin, one suite, one runner. No page and no task was edited, and the
walk drives the same 25,392 commands it drove before.

## Held

- The address is the shortest form that round-trips *at the moment it is
  published*. It is not a promise about the next moment: a page that renames a
  button changes its address, and that is honest — the name changed.
- `#id` is an id and nothing else. `@` tries the id first, so `@cName` also
  works; the two are not synonyms, or an id would be whatever happened to be
  written on some other button.
- The version is a digest, not a counter: it survives a reload, and two
  snapshots of the same page agree without a session to remember them. It moves
  on any structural change, including ones that cannot affect the index a
  caller is holding — a false alarm refuses a call that would have worked, and
  that is the right side to be wrong on.
- A distinct `stale` refusal *code* is not here. The refusal says stale in its
  message and is carried as `not_found`; separating the vocabulary —
  `not_found` / `stale` / `withheld` — is ADR-189, with the rest of it.
- The four trial pages left no control unnamed. A page whose buttons carry
  neither id nor distinguishable label would still get stamped indexes, and
  the suite would say so by counting them.
