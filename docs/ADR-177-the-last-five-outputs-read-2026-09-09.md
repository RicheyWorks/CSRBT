# ADR-177 — The last five outputs, read: the outputs loop closes, and the protocol library's own predictions are graded

**Status:** accepted · **Date:** 2026-09-09 · **Five pages had one unread output each: three prints, the soil bench's mix recipe, and the protocol library's `Copy`. Every one is now pressed and held by its task — the recipe and the protocol byte for byte — and every page suite pins what its task holds. The protocol library gets a suite of its own that runs each copied protocol through the engine the page says to run it in, which is how two of the library's five ready-made experiments turned out to carry predictions the engine refutes. Unread outputs 5 → 0 of 66; every ceiling 0.**

## The loop

ADR-153 built `audit_outputs` to ask one question of every button whose name
says it hands something over: does the page's own task press it, and then ask
what came out? Twenty-three of sixty-six did not. ADR-172 to ADR-176 closed
the pages with three or more, then two, and left five pages with one each.
This slice reads them.

**Three prints.** The farm scout's `Print / save PDF` on its export pane, the
pheno tracker's on its segregation pane, the field season's `Print the season`
on the graded results card. Each task presses it where it stands — the scout
and the tracker after their exports, the season after the peer-review grade —
and holds exactly one payload, a print, nothing leaving with it; then reads
its figures again unchanged (avg 3.6/plant and spread 2.54; selection
differential +1.44; the meadow held 101 voles, richness 25/25). `verify_fs`,
`verify_pt` and `verify_two` each stub `window.print`, press the button, and
hold that it printed once and the export beside it is the same text after;
each pins its task's print step.

**The soil bench's recipe.** The task builds a 1:1:1 mix (sphagnum peat,
perlite, finished compost) and had read the mix's tiles since ADR-129; `Copy
recipe` was unread. It now holds the clipboard **byte for byte** — `Mix recipe
— 3 parts total`, then one line per component with its share, `1 part
sphagnum peat  (33%)` and the two after it — and reads the mix's nutrient load
`1.00 / 5` again. `verify_soil` gains a port of the recipe as the page's prose
states it (parts over the total, rounded to a whole percent, one line per
part in the order tapped), holds the page's clipboard and the task's literal
to it, and holds that an *empty* mix copies nothing — the page says `Empty
mix` and leaves the clipboard alone.

**The protocol library's `Copy`.** The page carries five ready-made `.eco`
experiments, "ready to copy, edit, and run"; its task (a reference task)
pressed the first `Copy` and read the toast, never the text. It now holds the
clipboard byte for byte — `meadow-disturbance.eco` whole, fourteen lines from
`name: meadow disturbance study` to `expect: evenness(bloom) is uneven` — as
one payload and nothing else.

## The library gets a suite, and the suite gets a finding

The library had no suite; `verify_eco` checks its nav. `verify_epl` (40
checks) holds the page to the two things that can judge a protocol:

- *The page.* Five protocol boxes, each named `*.eco`, each with one `Copy`
  that puts exactly that protocol's text on the clipboard; every line a
  directive, a comment or blank; the meadow's `hot 2000 5 90` line the prose
  points at, and exactly one expectation marked *deliberately wrong*.
- *The engine.* Each copied protocol is written to a file and run through
  `ExperimentLab` — the `./gradlew ecologyExperiment -Pspec=` the page tells
  the reader to run. Every one parses with no `⚠ spec:` line; the engine's
  summary counts the seed, phases, models and expectations the text carries;
  every `expect:` line is graded, in order; the notes, datasets and crosses
  reach the notebook and the bench (Mendel's bench: five crosses); and the
  line marked *deliberately wrong* is the one refuted. Skipped and said so
  where the engine is not built.

Running the protocols is what turned up the finding. The page's meadow
protocol says which of its five hypotheses is wrong on purpose, and the engine
agrees: four confirmed, that one refuted. But **two-ponds.eco** grades 1 of 3
— `evenness(pondA) is uneven`, commented `# duckweed dominates`, observes
0.763 and the band says *moderate*; `brayCurtis(pondA, pondB) > 0.4` observes
0.311 — and **activity-budget.eco** grades 0 of 2 — `evenness(morning) is
uneven` observes 0.894, *very-even*; `brayCurtis(morning, afternoon) > 0.3`,
commented `# the budget shifted`, observes 0.237. Four predictions the page
presents as the experiment's, refuted by the kit's own instruments, with
nothing in the prose saying so. The suite records those four lines as the
reading (`KNOWN_REFUTED`) and holds that no *other* protocol has a refuted
prediction the page did not call wrong — so a fix to the page moves the
numbers and the suite says so, and a new protocol with the same fault is
caught the day it is added. Fixing the protocols is a page edit with a
republish behind it, and a choice about what the examples should teach (a
wrong prediction is a lesson too — the meadow's is); noted here, not made
here.

## What moved

    the kit's unread outputs       5 → 0 of 66        every page's ceiling 0
    farm-scout / pheno-tracker / field-season / soil-bench / eco-protocol-library
                                   1 unread each → 0

    page-farm-scout-science         117 → 120     verify_fs     45 → 48
    page-pheno-tracker-science      102 → 105     verify_pt     60 → 63
    page-field-season-replay         35 →  41     verify_two    37 → 40
    page-soil-bench-science          72 →  78     verify_soil   70 → 75
    page-eco-protocol-library-reference  9 → 12   verify_epl    new, 40

One page was edited: the soil suite hub advertises `verify_soil`'s size in its
Soil Bench card (ADR-078's rule, held by `verify_advertised`), so growing the
suite moved its `70/70 verified` to `75/75 verified`; the hub was republished
and the copy swept. Otherwise five tasks, four page suites, one new suite, the
ledger.

## Held

- A print is held to one payload of kind `print` and `payloads.1` absent —
  the shape every print in the kit has carried since ADR-172.
- The protocol library's task is a reference task and stays one: it presses
  `Copy#0` and reads what came out; it does not run anything.
- `verify_epl` declares `MUTATE_ROLE = "subject"`: it uses a temp dir for the
  engine's session and export bundle, not for fixture pages.
- The audit's count of the library's buttons is three — one `Copy` and two
  nav links it cannot press. The five `Copy` buttons share a name and a host,
  so the audit keys them as one; the task holds the first, the suite holds all
  five.
- Not done here: the two protocols' refuted predictions (a page edit and a
  republish); `rankBoard` is still skipped by the readable audit as an entry
  host (ADR-146, ADR-171); ten-odd charts remain unasserted.
