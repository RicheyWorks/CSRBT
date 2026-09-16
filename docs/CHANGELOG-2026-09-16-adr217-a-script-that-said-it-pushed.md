# 2026-09-16 — ADR-217: a quoted phrase with a space in it cost a commit, and the script said it had pushed

**ADR-215's subject quoted `"everything is green"`. PowerShell re-quotes native
arguments and the quotes do not survive; git re-split on the spaces inside them
and read the pieces as pathspecs. Nothing was committed. The script printed
`ADR215 pushed.`**

## Fixed

- **`ps_quote` escapes a straight quote** as it always did, and turns a
  **typographic** one into a single quote — that one delimits a PowerShell string
  as surely and cannot be escaped at all. The first fix curled the straight quote
  and failed in the same place; that wrong answer is in the record.
- **`deliver.py --check` refuses** a manifest whose subject or body quotes a
  phrase **containing a space**. The rule is the mechanism: six older manifests
  carry straight quotes and pushed cleanly because none of their quoted strings
  had a space in it.
- **Every script reads `$LASTEXITCODE`** after `commit` and after `push`, and
  checks the **post-condition** — this slice's own manifest in `HEAD` — before
  pushing. `$ErrorActionPreference = "Stop"` governs cmdlets and says nothing
  about `git.exe` returning 1.
- **All 69 push scripts regenerated.** The script is generated and never edited
  (ADR-184), so a generator change means all of them.

## Checked

`verify_delivery` 43 → 50. The pre-ADR-184 "no guard unless asked" check now asks
about the once-guard rather than the words `ls-tree HEAD`, since every script asks
git that question now for a different reason.
