# 2026-09-10 — ADR-179: the `.eco` Reference says what the parser reads

**The grammar page named a metric the engine lacks, an operator it refuses,
bands it never uses, six of nine models, and a header example the parser
rejects. Corrected and republished; a new suite reads `ExperimentSpec.java`
and holds the page to it, and runs the page's own examples as one protocol.**

## Changed — `docs/eco-protocol-reference.html` (republished, `c54e14b5…`)

- Header example: `keys` / `seed` / `window` one per line (was one line —
  a spec problem).
- Model table: all nine models with the parser's argument order —
  `exponential`, `levins`, `predation` added; `competition` spelled out.
- expect: quantitative metrics `richness shannon evenness hill1 chao1`;
  pairwise `brayCurtis jaccard sorensen pianka` (was `dispersion`, no
  `chao1`/`pianka`); operators `< > <= >=` with `=` named as absent; bands
  `evenness is very-even|moderate|uneven|dominated`, `turnover(a, b) is
  low|moderate|major`, `overlap(a, b) is high|partial|little`, `fit(scope) is
  geometric|brokenstick|uniform`, `survivorship is type1|type2|type3` (was
  `even / uneven`, `random / regular / clumped`); example gains
  `turnover(graze, bloom) is major`.

## New — `tools/verify/verify_epr.py` (46)

- The grammar read from the parser's source: metrics and arity, operators,
  qualitative metrics and band words, models and parameter counts, phase
  shapes, factors, directives.
- The page held to it both ways; the model table's argument columns counted;
  a section per directive.
- Engine (skipped if unbuilt): each section's example accepted alone; the
  nine assembled in page order run as one protocol — no problem line, seven
  hypotheses graded, the deliberate one refuted, survivorship type3
  confirmed.
- The lab's importer reads the assembled protocol with zero problems.
- `MUTATE_ROLE = "subject"`.

## Numbers

    verify_epr    new, 46        artifacts measured   42 / 42

## Noted, not done

The lab importer's own band lists; the undocumented `dwc:` directive.
