# 2026-09-17 — ADR-223: the CI path filter sat in tools/ci for fifteen slices and the workflow never changed

**ADR-202 said its workflow "is copied into place by the same command that
pushes the slice". The generated command had no such step. Origin's workflow is
the pre-ADR-202 file; every push since has rebuilt the Java tree on two JDKs.**

## Fixed

- **`deliver.py`: a manifest may `install`** `{from, to}` pairs. The script
  copies `from` over `to` before the add and stages the copy; the tarball never
  carries `to`. `--check` holds the pair. Manifests without `install` generate
  byte-identical scripts.
- **This slice installs `tools/ci/ci.yml` → `.github/workflows/ci.yml`**, which is
  ADR-202 arriving.

## Checked

`verify_delivery` 66 → 76, `mutate_delivery` 53 → 60. `verify_ci` is 9 / 14 on a
fresh clone and 14 / 14 after the script runs.
