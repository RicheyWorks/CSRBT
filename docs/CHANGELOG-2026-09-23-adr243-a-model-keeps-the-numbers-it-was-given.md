# 2026-09-23 — ADR-243: a model keeps the numbers it was given

## Fixed (ecology lab, filed by the tenth blind trial)

- **The theory bench keeps what each model was given.** Choosing another
  model and coming back rebuilt the boxes from the defaults, and the `.eco`
  line built next was a protocol of numbers nobody typed. Each model's boxes
  are kept and put back; `wb-params-note` under them says whether the model
  is drawn from *the numbers you gave it* or *its starting numbers*.
- **The two-site verdict says which figure it is reading.** At Bray–Curtis
  0.17 sharing 3 of 7 kinds it no longer says *nearly identical communities*;
  it says the abundant kinds are nearly the same, that 4 of 7 kinds are at
  one site only, and that the turnover is among the scarce kinds. Identical
  sites are called *identical*.

## Checked

Task 345 → 359 confirmed (refuted on the old page). verify_eco 200 → 227,
against ports of the model and of the verdict's word. New runner
`tools/mutate_ecolab.py`, 12 mutants, all killed. Found closed already: the
pheno tracker's `.eco` header (ADR-197) and the stand sheet's empty copy.
