# ADR-083 — the kit was wrong about itself

*2026-08-28. Status: accepted. Applies [ADR-041](ADR-041-arithmetic-is-checkable-2026-08-26.md) and
[ADR-052](ADR-052-binding-the-docs-to-the-engine-2026-08-26.md) to prose; corrects the prediction in
[ADR-082](ADR-082-three-numbers-in-one-file-2026-08-28.md).*

## 1. Five of six

Four hub pages advertise a suite's size in prose. Nobody was comparing those numbers to anything, and
five of the six distinct claims were wrong:

| card | page said | the suite counts |
|---|---|---|
| Soil Bench | 64/64 | `verify_soil` **70** |
| Stand Sheet | 76/76 | `verify_ss` **84** |
| Relevé | 66/66 | `verify_rv` **81** |
| CP Bench | 78/78 | `verify_cp` **87** |
| Breeding Bench | 85/85 | `verify_br` **90** |
| CP Characters | 116/116 | `verify_cpc` **116** ✓ |

Every one understated, which is the direction that makes the error invisible — nobody reads a rigour
claim and thinks *that seems low*. The one true claim is true by standing still, not by upkeep.

This is [ADR-052](ADR-052-binding-the-docs-to-the-engine-2026-08-26.md) in prose rather than in code: a
value generated in one place and inlined in another with nothing binding the two. It is also
[ADR-041](ADR-041-arithmetic-is-checkable-2026-08-26.md) — don't pin a constant you did not recompute —
applied to a sentence instead of to a fixture. The kit has caught this shape twice before in test code
and never once looked at its own marketing copy.

The five are corrected in `docs/` and republished.

## 2. Not by re-running the suites

The obvious check runs the six suites and compares. That is a minute of browser time per kit run,
spent re-deriving numbers the run has just derived and thrown away. So `run_all.py` now writes
`tools/verify/counts.json`, and a new suite reads it.

That trades one staleness problem for another unless the recorded number knows what it was recorded
**from** — otherwise `counts.json` is simply the frozen constant moved one level down, which is the
failure this exists to end. So each entry carries the sha1 of the suite source it was measured from,
and a count whose sha no longer matches the file on disk **does not speak**:

```
FAIL  soil-suite.html: the recorded count for verify_soil applies
      << the recorded count was taken from a different version of verify_soil
         (631ceebaa44f, now 6c3432fbab25) -- rerun run_all
```

That is [ADR-078](ADR-078-the-published-copy-can-be-read-2026-08-27.md)'s rule — an observation is only
about the thing it was taken against — pointed at a check count instead of at a published page.
Deliberately not mtime: a fresh clone stamps every file with the checkout time, so an mtime comparison
would be vacuously true on any machine but this one.

Four canaries cover the record layer, with `recorded()` made injectable so the three ways a record can
fail to speak are provoked without editing a suite on disk:

```
PASS  a record whose sha matches the suite on disk speaks (canary control)
PASS  a record taken from a DIFFERENT version of the suite does not speak
PASS  a record from a run where the suite was not green does not speak
PASS  a suite with no record at all does not speak
```

The control is not decoration. Without it, a `recorded()` that returned `None` for everything would
pass the other three.

## 3. Two things it refuses to guess, and one it nearly got wrong

**Which suite owns a page is declared, not inferred.** The obvious derivation — which suites mention
this page — returns **seven** suites for one bench page, because every cross-cutting suite mentions it.
That is a fact about mentions, not about ownership: the same mistake the mutate role markers were
introduced to stop making. Six suites now carry `PAGE_SUITE_FOR`.

**And then I nearly broke the rule while explaining it.** The comment I wrote above that declaration
said, in all six files, *"returns seven suites for `soil-bench.html`, because every cross-cutting suite
mentions it"* — which put that filename inside five suites that have nothing to do with the page, and
`mutate.py` reads mentions as coverage. [ADR-077](ADR-077-a-rule-a-sentence-about-the-rule-can-break-2026-08-27.md)
is exactly this: a rule that a sentence about the rule can break. Caught by grepping the six files for
docs page names before moving on, and the comment now makes the point without naming a page. The new
suite's canaries use a fixture page name for the same reason, and the file names no real page at all.

**A claim outside a tool card is reported, not exempted.** Two live in the ADR-031 page, in a dated
build log — *"five tabs, first consumer of FEK v1. 64/64 verified"* is a record of what was true that
day, and correcting it would be falsifying a history. The distinction is structural — a live claim sits
inside an `<a class="card">` pointing at the tool — so it needs no list of exceptions, but the count is
printed on every run so a claim that drifts out of a card cannot go quiet
([ADR-061](ADR-061-the-survivor-that-was-already-dead-2026-08-27.md)):

```
2 claim(s) outside a tool card -- narrative, not checked:
    adr-031.html             64/64 verified
    adr-031.html             64/64 verified
6 advertised count(s) checked against a recorded suite count.
```

`verify_advertised`: **29 checks**, new. Kit: 56 jobs.

## 4. ADR-082's prediction is dead, and the reason is worth more than the prediction

ADR-082 predicted all seven remaining unknowns would come back blocking, with the falsifier: *any one
of the seven coming back CURRENT*. Three did come back blocking — `breeding-suite`, `soil-suite`,
`cp-suite` — and then `tree-visualizer` came back **CURRENT, measured**, with no webfont at all.

The mistake underneath is mine and it is a clean one. **Unknown is not a synonym for behind.** Twelve
consecutive reads had returned BEHIND, and I let that streak turn a bookkeeping category — *nothing was
ever recorded about this page* — into a prediction about the page's contents. They are unrelated
properties: `unknown` is a fact about `published.json`, `behind` is a fact about the artifact. A run of
twelve is exactly long enough to make the conflation feel earned and not long enough to make it true.

The publish-date account survives unchanged and is now the only one: a copy is behind iff it was last
published before the change it lacks. `tree-visualizer` has a later publish than the rest, which is why
it is current, and it never carried a webfont, which is why ADR-031's rule was vacuously satisfied — the
tool says so in as many words rather than scoring it a pass:

> the published copy has no webfont promoter; if it also has no font link that is fine, and worth a look if not

## 5. Where the pile stands

```
34 current, 5 behind (0 measured at the URL), 0 unknown, 0 unmapped
of the current: 14 stamped before provenance was recorded, 15 at publish time, 5 measured from the live page
```

**Zero unknown, for the first time.** Every page in `docs/` now has a recorded published state. Seven
moved out of the pile in this record — `breeding-suite`, `soil-suite`, `cp-suite`, `plant-characters`,
`cp-characters`, `eco-protocol-library` republished; `tree-visualizer` measured current without needing
one — and six of the seven were serving a blank screen to a reader on bad signal.

The five BEHIND are what is left, and they are now top of the list rather than correctly ranked below
something worse: `cell-bench`, `deployment-log`, `ordination`, `soil-recipes` (missing nav-rail links)
and `stand-sheet` (the latent double-escape from ADR-080). None is a blank page; all five are known,
measured and named.

**The next prediction, and its falsifier.** Fourteen pages are CURRENT only on a stamp written before
provenance was recorded — the weakest evidence in the file, and the tool says so on every run. On the
publish-date account those were stamped at publish, so they should all verify CURRENT when read.
**Falsifier: any of the fourteen coming back BEHIND at its URL.** That would mean a page can drift after
a stamp without anything touching it, which nothing in the model currently allows — and would be worth
more than another confirmation.
