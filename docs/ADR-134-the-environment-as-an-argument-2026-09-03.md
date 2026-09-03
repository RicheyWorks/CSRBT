# ADR-134 — The environment as an argument: the clocks, the dice and the dialogs

**Status:** accepted · **Date:** 2026-09-03 · **Protocol 1.3 → 1.4. A target may now publish actions that set the world a run happens in: `set-clock` freezes what "now" answers, `set-seed` makes `Math.random` the kit's own mulberry32, and `set-dialog` decides what a page's `confirm()` gets told. Five paths that no expectation could hold and no audit could measure are now driven and held.**

## 1. What ADR-128 held on purpose

> Wall clocks and dialogs. The ethogram's time budget, the ordination's
> `Date.now()`-seeded NMDS starts, the greenhouse's demo log read with a real
> clock, `confirm()` on Clear buttons: not driven, on purpose.

And ADR-129 added `#bRand`, `#bRand10`, `#spRand` to the list. The reason was
always the same: a harness cannot hold a number it cannot reproduce. These
paths do not answer to what you enter — they answer to the clock and the dice —
so no task could assert about them and no audit could see them, and they were
driven by nobody.

That is a hole in the standing goal, not a footnote to it: *"make sure it can
enter all the data and the reports are correct"* includes the report a page
produces from chance.

## 2. The decision

### A shim that does nothing until it is asked

`harness.DETERMINISM` is installed as an init script beside `harness.STUBS`, in
every session, on every target that has a browser. It replaces `Date`,
`performance.now` and `Math.random` with versions that consult `window.__D` —
and while `window.__D` says nothing, they **are** the real ones. A page under
this shim behaves exactly as it did until a task says otherwise, which is the
only way a shim earns its place in every session. The suite pins that: with
nothing set, the clock still moves, and the dice are the real dice and not the
seeded generator running from an unset state.

### Three actions and a read

| action | risk | what it decides |
|---|---|---|
| `set-clock` | NAVIGATE | `Date.now()` and `new Date()` answer one instant. Every **other** `Date` form is untouched: a date the page names itself is not "now". |
| `set-seed` | NAVIGATE | `Math.random` becomes mulberry32, the generator the kit's own pages seed themselves with. |
| `set-dialog` | NAVIGATE | What `confirm()` and `prompt()` are answered with — so the branch a reader takes when they say **no** can be driven. |
| `read-dialogs` | SENSITIVE_READ | Every dialog the page raised, in order, by kind and text. |

NAVIGATE, not MUTATE: they change the world the page is in, not the data the
page holds. Each is reversible by calling it with no argument.

Two details the pages forced. A page that reads the clock **once, at load** —
the ethogram stamps its date field that way — has already read the real one by
the time an action can run, so `set-clock` answers with `reloadForLoadTime:
true` and a task reloads. And the environment is re-installed as an init script
after every set, because an environment that survived one navigation and not
the next would be worse than none at all.

The snapshot publishes `environment` — clock, seed, draws so far, the dialog
answer, the dialog count — on every observation. A figure that came out of a
seeded draw is only reproducible if the reader can see what the seed was.

### The generator is a module, and it is a port

`tools/mulberry32.py` is mulberry32 in Python, masking back to 32 bits at every
step because Python's integers are unbounded and JavaScript's are not. It is a
**port**, not a wrapper: a wrapper around the page's own JavaScript would agree
with it by construction and prove nothing. It lived in a scratch file through
ADR-129, which is how one port becomes two ports that drift.

The two agree bit for bit — the suite asserts the first five draws of seed 42
against the page's.

### What is now held

- **tree-visualizer** — clear the tree, seed 42, press *+ Random* and
  *+10 Random*: mulberry32 with the page's own skip-a-key-already-present rule
  draws 60 first and 24 eleventh, the tree is 11 nodes, and the page took
  exactly 11 draws.
- **tree-proofs** — seed 7, rebuild balanced, *20 random*: keys 1, 4, 62, 45,
  33, 26, 30, 16, 35, 46, 17, 10, 49, 33, 13, 24, 19, 34, 19, 62, and an
  independent splay port totals **131 actual against 152.0 amortized** — the
  figures the page prints.
- **ethogram** — freeze at 2026-03-01T09:00:00Z, reload, and the sheet stamps
  itself `2026-03-01`.
- **greenhouse** — answer `confirm()` **no**: the page asks *"Clear every saved
  run?"*, the five runs survive; answer yes, and they do not. A branch nothing
  could reach before.

### And the robot found one more

Walking all 41 pages with the four new tools, the robot typed a long site id
into the survey designer's hierarchy and pushed the row's two buttons 2 px past
the edge of a phone: `.tree .n` did not wrap and `.id`/`.ty` did not shrink.
Fixed, and re-walked clean. That is the fourth kit defect the robot has found
by driving something nobody thought to drive.

## 3. Verification

`verify_report` **49** (+16, section E) holds the shim end to end: untouched it
is the real world; the freeze reaches `Date.now()` and `new Date()` and nothing
else; the seeded stream agrees with the Python port; a dialog is answered by
policy and recorded by text; the whole environment survives a reload; each
action reverses; a clock that is not an instant and a `set-dialog` with nothing
to set are refused.

`mutate_report` **35** (+11), across both files the subject now spans — the
clock never frozen, the freeze swallowing every `Date`, the shim seizing
`Math.random` before anyone asks, the generator's constants changed, the draws
uncounted, a dialog always answered yes, dialogs counted but not recorded, the
environment not surviving a reload, the snapshot hiding it, and both refusals
removed.

`verify_contract` **89** at protocol 1.4; `verify_walk` at 21 page tools, all
driven; the MCP server's `serverInfo.version` is now the gateway's protocol
version rather than a second number that could drift.

## 4. First reading

    verify_report 49 / 49 · mutate_report 35 killed, 0 survived
    verify_contract 89 / 89 at protocol 1.4 · verify_walk 121 / 121, 21 page tools
    41 / 41 pages re-walked, 0 broken · 53 tasks, 53 held
    kit  77 / 77 jobs, 5,579 / 5,579 checks

## 5. Held

- `performance.now()` answers 0 under a frozen clock rather than a monotonic
  count from it. Nothing in the kit measures with it; a page that did would
  need a tick, not a freeze.
- The ordination's NMDS seed comes from `Date.now()` and is now reproducible,
  but its figures on the task's five-site dataset do not move when the seed
  does — the solution is degenerate, so there is nothing there to hold that
  freezing the clock did not already give.
- The splay port that priced the twenty accesses is ADR-129's, still outside
  `tools/`. `mulberry32.py` is in; the tree port should follow.
- `audit_focus` reported one fault under the kit's parallel run that it did not
  report alone: a transition that had not finished under load. `_settle` now
  waits two seconds rather than one. An audit whose answer depends on what else
  is running is not an audit, and this is the second time that has bitten.
