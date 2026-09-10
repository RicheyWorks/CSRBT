# 2026-09-10 — ADR-184: a push script pushes once

**`push-adr182.ps1`, run a second time after ADR-183 had landed on disk,
committed ADR-183's changes to the paths the two slices share under ADR-182's
message and left ADR-183's own files behind: origin held a `verify_eco` that
imported a module origin did not have. A manifest that says `"once": true`
now generates a script that knows it has run.**

## Changed — `tools/deliver.py`

- `script_text`: with `"once": true`, a guard before the chain and before any
  `git add` — `git ls-tree HEAD -- tools/delivery/<id>.json`; if the slice's
  own manifest is in HEAD, push if `rev-list --count "@{u}..HEAD"` is above
  zero, otherwise say "already pushed — nothing to do (modified paths belong
  to a later slice; run its script)" and exit 0. Manifests without the key
  generate exactly what they did; every earlier script still passes `--check`.

## Changed — suite, runner, manifest

- `verify_delivery` 36 → 43: no guard without the key; the guard names the
  slice's own manifest, asks with `ls-tree`, sits before the chain and the
  add, pushes an undelivered commit, exits 0 otherwise, stages nothing inside
  itself, and is deterministic.
- `mutate_delivery` 30 → 34 / 34: guard for every manifest; guard on a shared
  path; the undelivered push dropped; the fall-through after "nothing to do".
- `tools/delivery/adr184.json` is the first manifest with `"once": true`; its
  chain probe is `tools/verify/_lab_charts.py`, so `push-adr184.ps1` runs
  `push-adr183.ps1` first and lands ADR-183's five uncommitted files.

## Numbers

    verify_delivery 36 → 43    mutate_delivery 30 → 34 / 34

No page was edited.
