# ADR-027: Reading a protocol back in — `.eco` import in the Workbench — 2026-08-17

## Status

Accepted, implemented. Trigger: **ADR-020's own Held** — *"a Workbench `import .eco` reverse
path (the forward path — Workbench → protocol — is the one classrooms need first)"* — which
ADR-026 re-examined the same week, kept held for want of a classroom asking, and named as the
best remaining follow-on: *"that one remains a reasonable follow-on; it is self-contained in
`docs/ecology-lab.html` plus its `.eco` parser mirror."* It is now built, at the mirror standard
the seventh pass set for `parseCounts`.

Scope: `docs/ecology-lab.html` only. **No Java changed.** Build green throughout: 1063 tests, 0
failures, 0 skipped, 0 javadoc warnings.

## Context

### The loop only ran one way

ADR-019 gave students a plain-text `.eco` protocol and an engine that runs and grades it.
ADR-020 gave the lab page a **transfer box**: everything typed into the Workbench, rewritten as
`.eco` lines. Between them the page can *write* the format and cannot *read* it.

That asymmetry has a specific victim. The whole point of the Workbench is that it needs no JDK —
"No build at all? The lab page's Workbench section runs in any browser" (`ECOLOGY-FIELD-GUIDE`
§Design your own experiment). A student on a school Chromebook can type counts, build a
protocol, and save it. They cannot then **check** that protocol, or a protocol a lab partner
mailed them, or the one on the handout, without the very JDK the page exists to avoid. The
engine's answer to a bad line — reported, never guessed — was unreachable to exactly the person
the format was designed for.

It is also the difference between an authoring tool and an exporter. A `.eco` file is the
storage format the field guide tells students to keep ("the Workbench is where data is born, the
`.eco` file is where it lives"). A store you cannot load from is a drawer with no handle.

### The page was contradicting itself in the artefact it tells students to save

`buildEco` was not brought along with the seventh pass's hardening of `runTheory`. It read every
parameter box with `+el.value`, which is `0` for a blank box and — in Chromium — `0` for an
unparseable one, because `.value` reads back as `""`. Consequences, all reachable by ordinary
use:

| entries | line written | what the engine does with it |
|---|---|---|
| K blank or 0 | `model: logistic 0.15 0 5 60` | `⚠ spec: carrying capacity K must be > 0` |
| genotype boxes cleared | `model: hardyweinberg 0 0 0` | `⚠ spec: no individuals in the sample` |
| one observed count typed | `cross: Rr x Rr observed 5474` | `⚠ spec: observed needs >= 2 counts` |
| R > min(M, C) | `model: markrecapture 120 90 200` | `⚠ spec: recaptured must be in [0, …]` |

The first of those is the one the seventh pass had *just* fixed on the chart directly above the
button: the Theory Bench refuses to draw K = 0 and says why, and then the button underneath it
writes that same K = 0 into the file. Same page, same numbers, two answers.

### The precedent this slice is held to

Part 3 item B of `CHANGELOG-2026-08-17-seventh-pass.md`: the last time this page mirrored a Java
parser, the comment claiming the mirror was accurate and the code was not — "the RFC-4180
splitters themselves were an exact mirror; the surrounding bare-token logic was not, over 398
count-divergences in a 1,865-line corpus", two whole families wrong, closed only by a 25,066-record
differential test. A comment cannot hold a mirror in place. This ADR does not assume it can.

## Options considered

- **A viewer, not an importer** — parse and display, populate nothing. Cheap, honest, and
  useless for the case that motivates it: a student wants the numbers *in the bench* so the
  charts, the χ², the cladogram and the β-diversity readings answer for them. Rejected.
- **Populate everything by inventing the missing controls** — a phases editor, a notes pad, a
  hypotheses grid, protocol-header boxes. That is a second application, most of it unreachable
  (a `phase:` needs a live CSRBT to generate traffic against, and there is no tree in a
  browser), and every new control would be a dead end the transfer box could not write back.
  Rejected; the boundary is drawn at "what a Workbench control already holds".
- **Re-implement the `.eco` grammar loosely and forgivingly**, since it is only a browser. This
  is the option that produces the ADR-020 failure a second time: two parsers that agree on the
  easy cases, diverge on the hard ones, and tell a student two different things about the same
  file. Rejected explicitly.
- **A strict transliteration of `ExperimentSpec`, differential-tested against the compiled
  oracle (chosen).** Same discipline, same evidence standard, and the same shape of test as
  `FieldDataJsMirrorTest`.

## Decision

### 1. The importer parses with the oracle's semantics, not an approximation of them

`docs/ecology-lab.html` gained `parseEco(lines)`, a line-for-line transliteration of
`ExperimentSpec.parse` — every directive, every bound, every domain probe it runs before
accepting a model, and every problem message **verbatim**, including the messages that come from
`TheoreticalModels`, `PopulationGenetics`, `MarkRecapture`, `MendelianGenetics` and `PhyloTree`
underneath it. A trajectory model is probed over its **real step count**, as the oracle does,
because whether a run leaves the range of a double is a property of how long it runs.

Mirroring the *messages* forced mirroring five pieces of Java that JavaScript spells differently,
each of which was a live divergence before it was written:

- **`Double.parseDouble`.** `Number("0x10")` is 16; Java refuses it (a hex literal needs a binary
  exponent). `Number("1f")` is `NaN`; Java reads 1.0 (the float suffix is grammar). `Number("")`
  is 0; Java throws `empty String`. Every `.eco` number except `keys:`/`seed:`/`window:` goes
  through it.
- **`Double.toString`.** Java writes `1.0E7` where JS writes `10000000`, always keeps a digit on
  both sides of the point, and — the clause that matters — when the shortest round-tripping
  decimal has a *single* digit, Java's spec (JDK 19+) also considers the two-digit renderings
  and takes whichever is closest to the value. That is why `Double.MIN_VALUE` prints `4.9E-324`
  in Java and `5e-324` in JS. Measured: 10 divergences in a 67,000-value probe of the two
  formatters, every one a subnormal below 1e-322; all ten closed.
- **`String.split(regex)`** drops trailing empty fields — *unless the separator never matched, in
  which case Java hands back the input.* Getting only the first half right made
  `expect: richness() > 1` report the wrong problem (`richness takes 1 community name(s)` instead
  of `expect has a blank phase/dataset name`) and made `model: eulerlotka 1.0:` parse instead of
  refuse. Found by the differential test, not by reading.
- **`Character.isWhitespace`** — a third whitespace set, different from both `String.trim`'s and
  JS's `\s`: it takes U+001C–U+001F and excludes the non-breaking spaces U+00A0/U+2007/U+202F
  that JS's `\s` takes.
- **`(long)` and `(int)` casts**, which saturate and turn `NaN` into 0 rather than doing whatever
  JS does; `Long.parseLong`'s Unicode-digit acceptance was already mirrored and is reused.

### 2. `jsNewick` became the mirror it said it was

The page's Newick parser carried the comment "mirrors the Java parser (`PhyloTree.parseNode`)
exactly". It did not. It said `trailing characters:` where the oracle says `trailing characters
after tree:`; `missing name at index N` where the oracle says `empty node (missing name) at index
N`; it quoted an **untrimmed** branch length back at the student; it folded the oracle's separate
non-finite refusal into its bad-number one; and it used JS's whitespace set and JS's `Number()`.
Rather than add a second Newick parser for the importer, `jsNewick` was rewritten as the
transliteration and both callers use it. The Workbench's tree box now reports what
`./gradlew ecologyExperiment` reports about the same string.

### 3. What the importer loads, what it shows, what it declares unsupported

The rule: **load into a control the Workbench already has; otherwise say so, in the report, with
the reason.** Nothing is dropped and nothing is invented.

| directive | disposition |
|---|---|
| `data:` | **loaded** — into the field box / site A / site B. A dataset whose label is `myfield`, `siteA` or `siteB` claims that box (those are the labels the transfer button writes, so a protocol this page produced round-trips into the boxes it came from); the rest fill what is left in file order. A fourth dataset is listed with its kinds and total, never merged into a third. |
| `model: hardyweinberg` | **loaded** — the genotype boxes |
| `model: markrecapture` | **loaded** — the bean-lab boxes |
| `model: logistic\|exponential\|levins\|island\|competition\|predation` | **loaded** — the Theory Bench, model and parameters |
| `factor:` | **loaded** — all four habitat knobs, every time, including the ones the file omits (an absent factor *is* the neutral value; leaving a knob where the last import put it would quietly change the model the file describes) |
| `cross:` | **loaded** — parents, dominance, observed counts |
| `tree:` | **loaded** — the Newick box |
| `name:`, `keys:`, `seed:`, `window:` | **shown** — no Workbench control holds a protocol name, and the other three set up a simulated tree |
| `phase:` | **shown** — a phase is traffic against a live CSRBT; there is no tree in a browser |
| `note:` | **shown** — the field notebook travels with the file and the run |
| `expect:` | **shown**, and *parsed and validated*, so a malformed hypothesis is reported here. Grading one needs the run it was registered against. |
| `model: eulerlotka` | **shown** — the bench has no Euler–Lotka station; the engine runs it |
| a second trajectory model / cross / tree | **shown** — each of those controls holds one at a time, and it holds the first one in the file |

Every entry appears in exactly one of three lists — **Loaded into the Workbench**, **Read, and
shown here only**, **Problems** — under a counted summary (`Read 33 line(s): 9 loaded, 20 shown
only, 0 problems`). Entries that stayed for the same reason print that reason once with all of
them named under it, because repeating one sentence per phase buried the list it was explaining.

Datasets are written back as RFC-4180 `name,count` lines, quoted when needed. `name count` would
have been prettier and wrong: a species name may already contain a comma (`data: p oak,white=12`
is one species) and the space form would split it.

### 4. `buildEco` writes only lines the engine would accept, and says what it left out

The call, and the reason.

**Every candidate line is handed to `parseEco` before it is written.** If the engine would report
it, the line is not written; the refusal is recorded. This makes the two directions consistent by
construction: *what the page emits, the page — and the oracle — accepts.* The browser suite
asserts exactly that round trip.

Clamping was rejected on the house rule: setting K to 1 because the box was blank answers a
question the student did not ask, in a file they will keep. Emitting the line anyway is what was
wrong. Silently omitting it is the third bad option, and it is the one this decision most
deliberately avoids —

**the refusal travels with the protocol, as a `#` comment.** A comment is legal `.eco`, survives
the copy-and-paste into a file, arrives at the lab partner along with the data, and is the only
part of a protocol that can explain an absence:

```
# left out on purpose — the engine would refuse these, and a protocol
# that said nothing about them would be a quieter kind of wrong:
#   model: hardyweinberg 0 0 0  (no individuals in the sample)
#   model: logistic 0.15 0 5 60  (carrying capacity K must be > 0)
#   cross: Rr x Rr observed 5474  (observed needs >= 2 counts)
```

The same list is rendered under the button, where the fix is. Parameter boxes are read with the
`numField` discipline `runTheory` already uses, so a blank box is *reported*, not read as zero.

### 5. Dropping a file

The page's drop handler already took a session JSON. It now routes a `.eco` file to the importer,
by **extension** — a protocol and a session are never confusable by content, and guessing between
them is exactly the habit this page does not have. A protocol dropped under some other name still
fails as JSON, and the error card now says which door it wants instead of only printing
`Unexpected token 'n'`. A dropped protocol lands in the import box first, so what was imported is
on screen, readable and editable, next to the report about it.

### 6. Two defects of one kind, found on the way

JavaScript objects inherit names; Java's `LinkedHashMap` and `switch` do not. Both places this
page used an object as a lookup table keyed by a token out of the student's file were wrong for
the same reason.

- **`parseCounts`'s count table was a plain `{}`.** `"constructor" in {}` is `true`, so a species
  named `constructor` — or `toString`, or `valueOf` — was never entered into the insertion order,
  and `counts[name] || 0` added a count to a *function*. Now `Object.create(null)`.
- **The importer's own arity and band tables** would have found `Object.prototype.constructor`
  where an arity belongs, and reported `model: constructor 1 2 3` as *"model constructor needs
  function Object() { [native code] }1 parameters"* instead of *"unknown model 'constructor'"*.
  All four tables now go through an `own()` helper, and the differential corpus feeds those names
  to every directive.

The token half of `FieldData` was also lifted into a shared `countsBag()` used by both entry faces
(`parseLines`, and the `parseTokens` the `data:` directive needs), so the two cannot drift apart
the way the page and the oracle did.

## Evidence

**Differential test against the compiled oracle.** `ExperimentSpec` compiled standalone
(`./gradlew --offline :csrbt-experimental:compileJava`, then a driver on the class output) and run
against the page's `parseEco`, which is **lifted out of the shipped HTML by source range** — never
a copy kept beside it. Both sides render the whole parse: name, keys, seed (exact, via `BigInt`),
window, environment, phases, models, crosses, expectations, datasets, notes, trees and problems,
with every `double` compared as its **raw 64-bit pattern** so no formatting question can hide a
value difference, and every problem string compared verbatim.

Corpus: `docs/sample-experiment.eco` whole and line by line; 289 hand-built lines covering every
directive, every model kind valid and refused, every `expect` metric numeric and qualitative,
every phase kind, every factor, and the cross-line checks (duplicate phase names, dataset/phase
collision, unknown note targets); 25,000 randomised records assembled from directive keys, glue
and hostile tokens; and every one of 24 well-shaped directives crossed with 87 hostile numeric
tokens (hex floats, float suffixes, `Long` boundaries, Unicode and astral digits, `1e400`,
subnormals, `9007199254740993`), and every directive fed the names JavaScript
inherits from `Object.prototype` (`constructor`, `toString`, `__proto__`, …).

```
records      27,585
lines        52,641
directives   11,279   (models 623, datasets 1,151, expects 185, trees 560)
problems     40,469
divergences  0
```

Plus a targeted probe of the two number formatters — 67,000 values including the whole subnormal
floor and 60,000 random bit patterns — **0 divergences**.

Non-vacuity: the oracle output contains 128 distinct problem-message families, including every
one that can only be reached through a domain probe (`no intrinsic rate r fits this schedule`,
`Lotka–Volterra competition … leaves the range of a double at step N`, `no individuals in the
sample`, `at most 3 loci`, `recaptured must be in [0, min(marked, caught)]`).

Two divergence families were found and fixed this way and would not have been found by
reading: the `String.split` no-match case (§Decision 1) and the `Double.toString` single-digit
clause. The prototype-inheritance pair in §Decision 6 was found by review and then pinned by
extending the corpus, which is the order this project prefers but not the one that happened here.

**Browser verification** (headless Chromium, `docs/ecology-lab.html` over `file://`): **88 checks,
0 failures, 0 console errors, 0 page errors.**

- *Round trip, driven in the browser*: a chosen bench state (six species including a quoted
  comma-bearing name and a repeated tally, two sites, a genotype census, the bean lab, the island
  model with its five parameters, four non-neutral habitat factors, a dihybrid cross with observed
  counts, a phylogeny) → `buildEco` → every box scrambled to something else → import → **all 16
  scalar controls, the model parameter vector, and all seven rendered readings restored
  identically**, and `buildEco` run again is **byte-identical** to the first output. The importer
  is a fixpoint of the exporter.
- The shipped `docs/sample-experiment.eco`, pasted and dropped as a file: 9 loaded, 20 shown, **0
  problems**, with pondA/pondB/coop in the three count boxes, the census, the bean lab, the first
  trajectory model, the habitat, the first cross and the tree all in place.
- 17 malformed and degenerate inputs — empty, whitespace, comments only, a 20,000-character line,
  CRLF, tabs, astral digits, `<script>` in a note, a 400-deep unbalanced Newick, four datasets, a
  protocol of nothing but refusals — each produced a report, none injected markup, and the
  21-refusal case listed **every** refusal in the engine's own words with none collapsed.
- `buildEco` with K = 0, an empty census and a one-count observed cross: none of the three lines
  is written, all three are named in the protocol's `# left out` comment with the engine's own
  reason, and what *was* written imports with 0 problems. A blank K is reported as empty, not read
  as zero.

**The shipped payloads render identically.** Serialised DOM of `#main`, `#terrarium` and
`#workbench` before and after, with only animation state stripped (`grow-line`/`grow-bar`
classes, the `--len` custom property, `animation-delay`, and the `stroke-dasharray` the draw-on
removes when it finishes — inline `style` is otherwise *kept* and compared), for the embedded
session and all three ecology session JSONs:

| payload | `#main` | `#terrarium` | `#workbench` |
|---|---|---|---|
| embedded | identical (93,333 B) | identical (16,736 B) | identical for all 20,044 B, +1,086 B appended |
| `ecology-lab-session.json` | identical (93,333 B) | identical | same |
| `ecology-experiment-session.json` | identical (78,973 B) | identical | same |
| `ecology-trace-session.json` | identical (29,364 B) | identical | same |

`#main` and `#terrarium` are byte-identical everywhere. `#workbench` is byte-identical for its
entire existing content; the 1,086 appended bytes are exactly the new import panel (`#wb-eco-left`,
the heading, the explanation, the textarea, the button, `#wb-eco-in-out`), placed as a **suffix**
specifically so the diff could be stated this precisely rather than approximately. The claim is
"nothing that rendered before renders differently", and it is the strongest form of that claim
available once a panel is added at all.

**Full build:** `./gradlew --offline build -x :csrbt-benchmarks:jmh --rerun-tasks` →
**1063 tests, 0 failures, 0 skipped, 0 javadoc warnings.** `FieldDataJsMirrorTest` ran (not
skipped) against the rewritten page and still reports 0 divergences, so the `countsBag` refactor
and the `Object.create(null)` change did not move `parseCounts`.

Screenshots: `screenshots/before-{embedded,lab,experiment,trace}.png` and
`screenshots/after-{embedded,lab,experiment,trace}.png`, plus
`after-import-report.png`, `after-sample-import.png`, `after-roundtrip-import.png`,
`after-malformed-import.png`, `after-buildeco-refusal.png`.

## Consequences

- **The loop closes.** A student with a browser and no JDK can now write a protocol, save it,
  reopen it, check it, and see every line the engine would refuse — with the engine's own
  sentence, not a paraphrase of it. That is the ADR-020 promise ("run, reuse, store, export")
  with the reading half finally present.
- **The page can no longer contradict itself about the format.** `buildEco` validates its output
  with the same parser the import box uses, and the browser suite pins the round trip. The class
  of defect the seventh pass fixed on the chart and left on the button is closed at the seam
  rather than case by case.
- **A third mirror now exists and is measured.** `parseCounts` ↔ `FieldData.parseLines`,
  `jsNewick` ↔ `PhyloTree.parse`, `parseEco` ↔ `ExperimentSpec.parse`. The Java-semantics helpers
  (`jParseDouble`, `jDoubleToString`, `jSplit`, `jIsWhitespace`, the casts) are shared by all
  three, so the next mirror starts from a stocked shelf.
- **Two `jTrim`s live in this file, deliberately.** `FieldDataJsMirrorTest` lifts the `FieldData`
  mirror out of the shipped HTML by *source range* (`function splitCsvLine` → `const ecoName =`),
  so that parser's helpers must stay inside that range; the global `jTrimJ` serves the two mirrors
  outside it. Removing the duplication means editing a Java test, which this slice does not own.
  Recorded here so the next reader knows it is a constraint and not an oversight.
- **A protocol that round-trips is not a byte-identical protocol.** The importer restores the
  *entries*; `buildEco` then writes them in its own canonical form (its own dataset labels, its
  own header, `name=count` normalised by `ecoName`). What is pinned, and what a student can rely
  on, is that `buildEco → import → buildEco` is a fixpoint.
- **Stated residuals**, in the tradition of ADR-025's missing `fsync`:
  - Counts above 2^53 agree to double precision, not exactly — JavaScript has no 64-bit integer.
    Inherited unchanged from the seventh pass; the accept/reject decision is exact. `seed:` is
    *not* subject to this: it is carried as a `BigInt`.
  - A hexadecimal float literal with more than thirteen significant hex digits is rounded once
    here and once in Java and can differ in the last bit. No other numeric shape can.
  - `Math.exp` is permitted 1 ulp of error in both languages and they need not agree on which.
    A trajectory whose finiteness turns on that last bit could in principle be accepted by one
    side and refused by the other. Not observed in 27,585 records; named so the mirror is not
    read as stronger than it is.
  - Single-character case folding (`Character.toLowerCase` for a genotype letter, `Locale.ROOT`
    lowercasing for a directive key) is mirrored with JS's, which differs for a handful of
    characters that expand on folding. Directive keys and genotype letters are ASCII in every
    documented use.

## Held

- **No new Workbench controls for `phase:`, `note:`, `expect:` or the protocol header.** They are
  read, validated and shown, and nothing writes them back. Adding boxes for them would create
  controls the transfer button cannot round-trip, and `phase:` in particular is unreachable in a
  browser: it needs a live `TreeContext` to generate traffic against. **Trigger:** a Workbench
  that can run a real phase — a JS CSRBT, or a notes/hypotheses pad the transfer box also emits.
  Either one makes this a symmetric importer instead of a partial one.
- **Only the first trajectory model, cross and tree are loaded; only three datasets fit.** Each of
  those controls holds one thing, and the report names every extra with its reason. Cycling
  through them (a "next model" affordance) is a UI, not a parser, and it belongs to whoever adds
  the controls above. **Trigger:** a protocol in classroom use whose *second* model is the one the
  student wants to see, often enough to be worth a control.
- **`jsCross` keeps its own wording.** The Punnett box says *"genotype must be 1–3 letter pairs
  (Aa, AaBb)"* where `MendelianGenetics` says *"genotype must be letter pairs, e.g. Aa or AaBb"*,
  and the importer uses the oracle's. Two sentences for one defect is a smell, and the resolution
  is not obvious: the Punnett box is a text field on a web page, not a `.eco` line, and its
  message is arguably the better one for someone typing into it. Unifying them means either
  changing a message the engine prints (Java, not this slice) or making the page's own box speak
  the engine's register for no reason a student would notice. **Trigger:** a report from a student
  who saw both messages for the same genotype and could not tell they were the same complaint.
- **The importer does not grade anything.** `expect:` lines are parsed and their *shape* is
  checked; `CONFIRMED`/`REFUTED` needs a run against a live tree. A hypothesis over two entered
  datasets could in principle be graded here — the page already computes Jaccard, Sørensen and
  Bray–Curtis in the compare-two-sites facet — but grading *some* hypotheses and not others, in a
  layer whose whole discipline is `UNGRADEABLE` rather than a plausible guess, would be the wrong
  kind of half-answer. **Trigger:** the phase-capable Workbench above, at which point everything
  is gradeable and the split disappears.
- **No `.eco` file is written out.** The transfer box still produces text to copy; there is no
  download button, because a download needs either a `Blob` URL the page's own house rules have
  not previously used or a data URI that mangles on some platforms, and copy-paste has worked
  since ADR-020. **Trigger:** a protocol long enough that selecting it is a chore.
- **`buildEco`'s refusal comment is not machine-readable.** It is prose behind `#`, so a
  re-import reads it as a comment and ignores it — which is correct — but nothing downstream can
  count what was left out. **Trigger:** a tool that wants to reconcile a Workbench state against
  the protocol it produced.
