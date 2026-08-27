# ADR-069: a red suite scores 100%, and four other things that reported success

**Status:** Accepted and implemented — `tools/sweep_ledger.py` and `tools/sweep_ledger.json` (new),
`tools/emit_common.py` (new), `tools/verify/verify_sweep_ledger.py` (new, the kit's 53rd suite), `tools/mutate.py` (+baseline guard, +emitter kill, `--status`, `--record`),
`tools/verify/verify_label_escaping.py` (18 → 27), `tools/verify/verify_emitters.py` (88 → 94),
`tools/verify/verify_sel.py` (77 → 83), `tools/keep_emit.py`, `tools/fek_emit.py`, `tools/dwc_emit.py`,
`tools/gh_emit.py`, `tools/verify/_kit.py`, `docs/selection-log.html`, `docs/survey-design.html`,
`docs/stand-sheet.html`.
**Date:** 2026-08-27
**Deciders:** Richmond
**Follows:** ADR-039 (a fixture that cannot tell two things apart), ADR-041 (recompute, never pin),
ADR-046 (a suite that exits 0 on failure), ADR-056 (an entry gained a timestamp), ADR-066 (one loader,
thirty-eight pages)

---

## Context

This slice began as the next page in the mutation sweep. It ended up being about five separate things
that were reporting success while measuring nothing, and the first one was my own progress number.

## 1. The tally had no source, and was wrong

Seven ADRs ended with a sentence like **Swept: 19 pages. 20 to go.** It was typed by hand, carried
forward from the previous ADR, and derived from nothing. ADR-041 says a number a tool can compute
must not be pinned as a constant; this one was pinned in prose, which is worse, because prose has no
test.

Reconstructing it took twenty minutes of grepping and produced a different answer. `greenhouse.html`
was swept in ADR-063 **and again** in ADR-064, and both ADRs added it to the running total. From
ADR-064 onward every figure was one too high. The truth at ADR-068 was **18 pages, not 19** — and
**21 to go, not 20**.

`tools/sweep_ledger.json` records one row per RUN, with the ADR that reported it and whether the row
was written by the tool or backfilled from the prose. Re-sweeps get their own row deliberately: a
ledger that collapsed `greenhouse` twice into `greenhouse` once would hide exactly the event that
caused the drift. Everything derived — swept, remaining, total — is computed by `sweep_ledger.py`
from those rows and the `docs/` glob, and stored nowhere. `mutate.py --status` prints it;
`mutate.py --page X --record ADR-070` appends a row so future entries are a byproduct of running the
tool rather than a thing to remember.

### The classifier that classified nothing

The first `classify()` called all twenty-one remaining pages **ready**, which is obviously wrong for a
glossary — and the reason is worth keeping. Every page in the kit carries the shared webfont loader,
the loader contains `if(!l) return`, and `neg-guard` mutates it. So no page has zero mutants, and "has
mutable code" separates nothing at all (ADR-039, one hour before this file was written).

What separates them is code of a page's **own**. The loader's bytes now come from `_kit.LOADER`, the
same pattern `verify_offline_slice` reads, so "this is the shared loader" cannot mean two different
things in two files. The honest backlog:

| bucket | n | what it means |
|---|---|---|
| own code, with a suite | **9** | actual sweep work |
| loader-only | **12** | one shared line, twenty-one times over |
| no suite | 0 | — |

So **21 to go** is really nine pages and one line.

## 2. A red suite kills every mutant

This is the serious one, and it was found by accident.

Extending `verify_label_escaping` (below) put `selection-log.html` on its list. The suite then went red
for an unrelated reason — a page it now covers was not published current. The very next sweep of
selection-log reported **six mutants killed in three seconds and a mutation score of 100%**. An hour
earlier the same six had scored 33%, and two of them were known blind spots.

A suite that already fails on clean code returns non-zero for every mutant, and the sweep reads
non-zero as a kill. ADR-046 fixed the mirror image — `verify_fek` printed FAIL and exited 0, so every
failure read as a pass and FEK scored 7% when it should have scored 95%. Both directions produce a
number with nothing behind it.

`mutate.py` now runs each named suite against the **unmutated** scratch copy first and drops any that
fails, printing why:

```
selection-log.html  -- 6 mutant(s) against verify_label_escaping, verify_sel, verify_suites
              EXCLUDED, already failing on clean code -- a red suite kills every mutant: label_escaping
```

Audits and the cross-cutting suites are baselined **lazily** — they run only when a mutant is otherwise
about to survive, which is rare, so paying for them up front on every page would collect almost
nothing. The page is put back for the length of one run, the answer is cached per checker, and the
mutant is restored.

### Green was not enough either

With the guard in, the same sweep ran again and reported **six killed, 100%, all six by
`verify_label_escaping`** — including a `Math.max` → `Math.min` inside the Field Entry Kit that that
suite has no opinion about whatsoever. It had passed its baseline. It was still not testing anything.

Its section 5 recomputes each page's publish bytes and compares them against the stamp in
`published.json`. **Any** edit to a covered page makes it fail — and a mutation sweep edits the page by
construction. Every mutant was killed by the fact of having been made.

So the second half of the guard is a **null mutation**: a comment appended to the page, which changes
its bytes and cannot change its behaviour. A suite that fails on that is not testifying about any
mutant, it is testifying about the edit, and it is dropped with the reason printed:

```
              EXCLUDED, fails on a comment appended to the page -- it is
              measuring bytes, not behaviour: label_escaping
```

Three ways this tool has now been fooled into reporting a kill: a suite that exits 0 on failure
(ADR-046), a suite that was already red, and a suite that measures the file rather than what it does.
All three produced a mutation score with nothing behind it, and two of the three were found this
afternoon.

## 3. The commonest survivor in the kit was never a blind spot

Every page inlines the Field Entry Kit; some inline Keep, the greenhouse engine, Darwin Core or
Ordination too. `verify_fek` builds its own harness from `tools/fek.py` and never opens `docs/` —
correctly, because that is what makes it a test of the module rather than of one consumer. The
consequence was that a mutation inside a page's **inlined** FEK was invisible to every suite the sweep
ran for that page, and came back a survivor. It came back on every page swept so far.

It is not a blind spot. `fek_emit.py --check` compares each page's block against the module byte for
byte. Measured, not assumed: seeding `Math.max(min,x)` → `Math.min(min,x)` into selection-log's
`clamp()` makes `--check` report one consumer would be rewritten. So the coverage is real in two
links — the emitter proves the page's copy IS the module, the module's suite proves the module
behaves — and the sweep now runs the owning module's `--check` before giving up on a module-block
mutant. The output attributes the kill to `fek_emit` by name, because it means something narrower
than a suite kill: **not that anything tests that line on that page, but that the line is not that
page's to change.**

## 4. The escape that put entities on the screen

`selection-log`'s trait chips read `girth (&quot;)` while the trait list two inches below read
`girth"`. The same unit, two spellings, one page.

FEK escapes an option label itself — deliberately, "rather than at each call site, because a component
whose safety depends on every caller remembering is a component that will bite somebody", its own
comment. Two call sites escaped anyway, so the entity survived to the screen. It is a leftover from
FEK v1.1.1, when the escaping WAS the caller's job; when v1.2.0 moved it into the component the
cleanup took `esc(i.label)` out of `indOptions()` and left `esc(t.unit)` in `traitOptions()`.

The mutation sweep found it, and this is the first survivor in the kit where **the mutant was the fix**:
dropping the `esc()` makes the page correct.

Nobody saw it for months because both spellings are "escaped" and the eye reads `&quot;` as a quote.
The check that would have caught it is in section 3b of `verify_label_escaping`: an option literal —
a line carrying `value:` alongside a `label:`/`sub:` — must not call an escaper. Narrow enough that
pheno-tracker's `dial` label, which is authored markup by design and escapes only the data inside it,
does not match. `stand-sheet` had the same shape over a page constant; equivalent today, fixed anyway,
because an exception that happens to be harmless is how the next one gets written.

`verify_sel` gained the behavioural half: a trait name and unit are typed in, and the chip must read
back **exactly what was typed**. The expected string is built from the input rather than written out —
a check pinning `girth (")` passes for a page that ignores the typed value entirely.

## 5. "Every option list is built from a page constant" was false on five pages

`verify_label_escaping` said so in its own docstring. It required `.map(` at the `options:` site and
treated any ALL-CAPS name as a constant. Both assumptions are wrong on real pages here:

| page | what actually reaches an option label |
|---|---|
| selection-log | `TRAITS` is ALL-CAPS **and the "add trait" button pushes a typed name and unit into it** |
| collection-sheet | `PACK` starts as `GENERA.slice()` and is **replaced wholesale from a file the user loads** |
| survey-design | event names, typed, into `sub` |
| pheno-tracker | plants and crosses (labels are derived ids; the list behind them is runtime) |
| cp-bench | already known |

The tracer follows one hop through a helper (`var opts = traitOptions()` → `function traitOptions(){
return TRAITS.map(...) }`) and asks whether an ALL-CAPS table is **written to** rather than trusting
its shape. Deliberately one hop and one shape: a general answer needs the JavaScript parsed, and the
last attempt at that here had to be withdrawn (ADR-062). Everything that does not match is treated as
runtime data, so the failure direction is a page named that need not have been, never a page missed.

Two of my own fixes to it were wrong first:

- `(?!\s*\()` on the assignment pattern broke `var opts = PACK.slice()`, which is a constant reached
  through a method call.
- Preferring the call binding only when strictly nearer made `var opts = famOptions()` resolve as a
  variable named `famOptions`, and reported **farm-scout** — built entirely from a constant table — as
  runtime data. `>=`, not `>`: both patterns match at the same offset.

Section 5 also read `published.json` entries raw. ADR-056 gave an entry a timestamp, eight of nineteen
entries are the new shape, and comparing a dict to a digest is never equal — so this check would have
called a freshly stamped page "behind" the moment anyone re-stamped one of these five. It reads
through `publish_state.entry_sha` now, and asserts that it handles both shapes.

Its requirement then bit, correctly: **selection-log's live copy was serving Field Entry Kit v1.1.1** —
the pre-ADR-031 dial and picker that interpolate `op.label` raw — on a page that pushes typed text
into option labels. That is the exact defect the suite exists for, live, on a URL people have. All
four flagged pages are now republished and stamped.

## 6. Four copies of a stylesheet, and `--check` said the tree was clean

Reading survey-design's published copy line by line for the publish gate turned up something no tool
had: it carries the **Keep stylesheet four times**. `keep_emit.py --check` reported "0 consumers would
change", because the rewrite finds the first banner, replaces it, and stops looking.

Four identical copies render identically, which is why a contrast audit, a print audit and an offline
audit all walked past it. They stop being identical the first time `keep.CSS` changes: copy one is
updated, copies two to four are not, and **the last rule wins in CSS**. The page would render the stale
stylesheet with every regenerator reporting success — the failure this whole layer exists to prevent,
arriving through the layer itself.

`tools/emit_common.py` holds the collapse, and `fek_emit`, `dwc_emit`, `keep_emit` and `gh_emit` all
call it. A new canary in `verify_emitters` duplicates a block and requires the emitter to notice:
**three of the four failed it** before the fix.

Two of my own checks were wrong on the way, both in the direction of firing on working code:

- The canary first copied "banner to `</style>`", which on fek and dwc pages swallows the stylesheets
  that follow. The emitters removed their own duplicates correctly and the byte comparison still
  failed. It now asks the **emitter's own** `css_span` where the block ends.
- The dead-helper detector counts call syntax, and `gh_emit`'s `css_span` is handed to `dedupe` as a
  value. A live helper was reported as dead.

The removal is exactly reversible — one newline, not `lstrip` — because a canary that cannot restore
the original byte for byte proves nothing about the emitter.

Also found by reading: survey-design carried an **orphaned CSS declaration block** with no selector, the
tail of a `.cv` rule whose head had been deleted. The parser scans forward for a `{` and swallows the
next rule; measured, that rule is `.tiles`, which survey-design does not use. Cosmetically harmless,
removed, and worth recording as the second thing in one file that no audit could see.

## Cost

`verify_sel` 77 → 83, `verify_label_escaping` 18 → 27, `verify_emitters` 88 → 94,
`verify_sweep_ledger` new at 42 — one of its checks is per remaining page, so that total falls by one each time a page is swept, which is the right behaviour for a suite about the backlog. Four pages republished and stamped; three pages edited. Six canaries run,
all six caught. 53/53 jobs green, 3873 checks.

`selection-log` swept, and its honest score is **100%** — six of six, of which two are
`fek_emit` kills on the inlined module and four are checks that mean something, two of them written
this slice. The 33% it read before the guards, and the 100% it read twice for the wrong reasons in
between, were both measurements of the runner rather than of the page.

**Swept: 19 pages, 20 to go — of which 8 have code of their own and 12 are the shared loader.**
And for the first time that sentence is computed rather than typed:

    python3 tools/mutate.py --status
