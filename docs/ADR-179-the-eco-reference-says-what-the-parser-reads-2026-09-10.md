# ADR-179 — The `.eco` Reference says what the parser reads: the grammar page held to the parser's source, and its own examples run

**Status:** accepted · **Date:** 2026-09-10 · **The page a reader writes a protocol from named a metric the engine does not have, an operator it refuses, band words it never uses, six of nine models, and a header example the parser rejects. Nothing held the page to the grammar. Now `verify_epr` reads `ExperimentSpec.java` and holds the page to it — metrics, operators, bands, models and their arities, phase shapes, factors, directives — and assembles the page's own examples into one protocol the engine grades. The page is corrected and republished.**

## What a reader was told, against what the parser does

`eco-protocol-reference.html` is the grammar. ADR-178, rewriting two library
protocols to the report's bands, found the reference calling those bands
`even / uneven`. Reading the page against `ExperimentSpec.parse` turned up
the rest:

- **A metric that does not exist.** `dispersion` was listed among the
  quantitative metrics; `expect: dispersion(graze) > 1` is `unknown metric`.
  `chao1` and `pianka`, which the parser accepts, were not listed.
- **An operator the parser refuses.** The form row offered `> < >= <= =`;
  the parser's rule is *operator must be < > <= >=*.
- **Bands the report never narrates with.** `even / uneven` and `random /
  regular / clumped` were offered as the qualitative words. The parser's
  qualitative metrics are `evenness` (very-even / moderate / uneven /
  dominated), `turnover` (low / moderate / major), `overlap` (high / partial
  / little), `fit` (geometric / brokenstick / uniform) and `survivorship`
  (type1 / type2 / type3); there is no dispersion band at all. Three of the
  five metrics were unmentioned.
- **Six of nine models.** `exponential`, `levins` and `predation` were
  absent from the model table, and `competition`'s arguments read *(two-species
  Lotka–Volterra)* where the parser wants nine numbers in a fixed order.
- **The page's own header example is refused.** `keys: 100   seed: 42
  window: 250` on one line is one directive with the value
  `100   seed: 42   window: 250` — *keys must be a whole number*. The first
  example on the grammar page was a spec problem.

Every one of these is a reader copying the reference and getting a `⚠ spec:`
line back — from the page whose job is to prevent exactly that.

## What changed

**The page.** The header example is one directive per line. The model table
carries all nine models with the parser's argument order (`exponential r N0
steps`, `levins c e p0 steps`, `competition r1 K1 r2 K2 a12 a21 N1 N2 steps`,
`predation r a b m N0 P0 steps`). The expect section lists the five one-scope
metrics and four pairwise ones, the four operators with `=` named as absent
and why, and the five qualitative metrics with their exact band words and
arities — `survivorship` with no scope and the note that it needs a `churn`
phase to have a census. The example gains `expect: turnover(graze, bloom) is
major`. Republished (`c54e14b5…`), read back, stamped, swept: 42 of 42
measured from the live page.

**`verify_epr` (new, 46 checks).** The grammar is read from
`ExperimentSpec.java` — the `switch` that gives each metric its arity, the
`op.equals` chain, `wordsFor`'s lists, `parseModel`'s parameter counts,
`parsePhase`'s shapes, the factor names, the directive keys — so no build is
needed to hold the page, and a grammar change moves the suite before it moves
the page. Then the page: the metrics it names are exactly the parser's, the
operators exactly, each qualitative metric's bands word for word and in the
parser's order with the parser's arity in the form, the model table's names
exactly the parser's with each argument column counting what the parser
wants, the phase and factor tables exactly the parser's, a section for every
directive. Then the examples, where the engine is built: each keyword
section's example accepted on its own, and all nine assembled in page order
run as one protocol — no problem line, nothing ungradeable, every `expect:`
graded in order, the *deliberately wrong* line the one refuted, the
survivorship claim graded type3 because the page's `churn` phase gives it a
census, three datasets, three notes, one tree and three crosses reaching the
bench. Then the lab's importer reads the assembled protocol with zero
problems.

## What moved

    eco-protocol-reference: claims the parser refuses   5 kinds → 0
    verify_epr                                          new, 46
    artifacts measured from the live page               42 of 42

One page edited and republished; one new suite; the ledger. The reference
task is unchanged: the page's outline did not move.

## Held

- The grammar is read from the parser's source, not restated: a metric,
  band, model or operator added to `ExperimentSpec` fails this suite until
  the page names it, and one removed fails it until the page stops.
- The page's mention that `=` is absent is not counted as an offer: the
  operator list is read up to the sentence that names the absence.
- `turnover(graze, bloom) is major` is confirmed at 0.85 — the same
  Bray–Curtis the `> 0.5` line reads, said in the band the report narrates.
- Not done here: the Interactive Lab's importer carries its own copy of the
  band words (`evenness: ["very-even", …]`); `verify_epr` proves it reads the
  page's examples, not that its lists equal the parser's. The `dwc:`
  directive is parsed but undocumented on the reference — a section with a
  republish. `rankBoard` and the unasserted charts stand.
