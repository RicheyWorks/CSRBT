# ADR-223 — the path filter written to save the Actions minutes sat in tools/ci for fifteen slices, and the workflow never changed

**ADR-202 found that every push rebuilt the Java tree on two JDKs, that the last
dozen slices contained no Java, and that the minutes had run out. It wrote a path
filter, a suite that holds the filter to what the build reads, and one sentence:
*"the workflow travels as tools/ci/ci.yml and is copied into place by the same
command that pushes the slice."* The command that pushed the slice contains no
such step. `.github/workflows/ci.yml` in origin is the 1,356-byte file it was
before ADR-202; the 2,887-byte filter is beside it in `tools/ci/`, and every push
since — fifteen slices — has rebuilt the tree.**

## 1. How it stayed green

`verify_ci` fails on a fresh clone, 9 of 14: no filter on push, none on
pull_request, the mirror not identical. The ledger in the same commit says 14 of
14. As with `verify_keep` (ADR-219), both are true: the count was taken in a
session that had copied the file into place by hand, in a container, where a
copy is not a delivery. The delivery bridge refuses to write `.github/workflows`
— ADR-202 says so, and says the refusal is right — so the one place the file
could not be landed by the usual route was also the one place nobody checked
that it had landed.

ADR-203's shape, ADR-212's, ADR-216's, ADR-217's: a sentence asserting what
nothing did. This one is in a commit message.

## 2. The mechanism

A manifest may carry

    "install": [{"from": "tools/ci/ci.yml", "to": ".github/workflows/ci.yml"}]

and `deliver.py` generates, before the `git add`:

    Copy-Item -Force (Join-Path $csrbt "tools\ci\ci.yml") (Join-Path $csrbt ".github\workflows\ci.yml")

and stages the copy. The `to` path is **not** in `paths` and cannot be: the
tarball is made from `paths`, and a tarball that writes there is what the bridge
refuses. `--check` holds the pair: `from` must be a path this slice delivers,
`to` must not be (if the bridge can write it, it needs no install), and `to` may
not be under `tools/` or `docs/`. The `once` guard runs first, so a second run
copies nothing. A manifest with no `install` generates the script it always did,
byte for byte — seventy-one older scripts still pass `--check` unregenerated.

The supply-chain reasoning stands. Nothing remote writes the workflow: the
operator's own command does, from a file that is in the diff they are pushing.

## 3. This slice is last in its chain on purpose

A push that changes `.github/workflows/` needs a credential with the `workflow`
scope. The operator's has pushed that file before (ADR-170) and Git Credential
Manager asks for it by default, but if it is refused, it is refused for the
whole push — so ADR-219 to ADR-222 are committed and pushed by their own
scripts first, and this one's failure, which the script reports since ADR-217,
costs this slice only.

## 4. Numbers

`verify_delivery` 66 → 76, `mutate_delivery` 53 → 60 all killed. `verify_ci`
14 of 14 once the script has run; 9 of 14 before.

## 5. Held

- **What else was counted green in a container and is red in a clone.** Two so
  far, both found by cloning. A full run on a fresh clone of origin after every
  push is the only instrument that answers it, and the Actions minutes that
  would pay for it are the ones this filter exists to save. Price: one scheduled
  run a week. Trigger: the quota resetting.
