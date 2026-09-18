# ADR-219 — origin/main was red for ten slices, and the audit built to see that called it "in flight"

**A fresh clone of `origin/main` at ADR-217 fails `verify_keep`: 270 of 271. The
ledger in that same commit says `verify_keep` 316 of 316, green. Both are true.
The 316 was counted on a disk that had a change to `tools/keep_emit.py` which
ADR-207 made and no push script ever staged; the 270 is what everybody else
gets. `tools/audit_delivery.py` exists to find exactly that file (ADR-147), ran
in every full run since, and reported `0 UNDELIVERED` each time.**

## 1. What the audit excused, and why

    UNDELIVERED = tracked files whose sha is not the delivered one
                  - the paths the manifests of unshipped slices claim

That is the docstring, and the second line is not what the code did. `claimed()`
returned every path **any** manifest names — all seventy-one of them, shipped or
not, forever. A claim is a statement about work that has not been committed yet;
here it never ended.

ADR-206's manifest names `tools/keep_emit.py`. ADR-206 shipped. ADR-207 then
added five pages to the emitter's `CONSUMERS` list, named five paths in its own
manifest, and `keep_emit.py` was not one of them. The audit looked the file up,
found ADR-206's two-slice-old claim, and filed the change under *in flight —
the push script will stage them*. No script was ever going to.

By ADR-217 that bucket held **221 files**: `harness_contract.py`, every
ledger, the board, `AI_HARNESS.md`, every hot file in the kit. A change to any
of them, left out of any manifest, would have been excused the same way. The
audit could still see a brand-new file nobody had ever named, and nothing else.

## 2. The ratchet under it had stopped too

Claims were supposed to end when `deliver.py --record` moved the ledger forward
and the bytes matched again. The last slice recorded is **ADR-190**. Twenty-seven
slices shipped after it and none was recorded — `--record` was a step in every
close and a check in none, which is ADR-216's shape: a ratchet that was a
sentence.

## 3. What changed

- **A claim expires when its slice ships.** `claimed()` reads only UNSHIPPED
  manifests. A manifest whose slice is over claims nothing; a later change to
  one of its paths is somebody else's work, and if nobody names it, it is the
  file this audit is for.
- **Where there is git, git is asked.** ADR-147 wrote *"there is no git here
  (the agent's copy is a mount, not a clone)"*. That stopped being true and the
  audit went on reading a ledger of hashes. `git_view()` asks two things — which
  bytes are not HEAD's (`status --porcelain -z --untracked-files=all`), and
  which manifests are in HEAD's tree (`ls-tree`, the same fact a push script's
  own guard reads since ADR-184). No git, no repository, no commit yet, or a git
  that failed is **no evidence**, never "clean": the audit falls back to the
  ledger and says which evidence it read.
- **Without git, a slice is over when the ledger says so by name.** `--record`
  appends the id to `recorded`. Not inferred from which slice a path was last
  delivered `by` — the first version did that, and an adoption writes `by` too;
  the suite's own fixture caught it (five failures on the first run).
- **`--catch-up`** brings a stalled ledger up to what git vouches for: every path
  whose bytes are HEAD's, credited to the last shipped slice that names it (or to
  `HEAD`), every shipped slice marked over, each line tagged `evidence: git`. It
  will not record a modified file and refuses outright with no git — a catch-up
  without evidence is an adoption, and there is already a flag for that. Run
  here: 217 paths, 71 slices.
- **`--check` holds the step nothing held**: a slice git says is committed and
  the ledger never recorded is a problem. It named 27.
- **`tools/keep_emit.py` is delivered**, ten slices late.

## 4. What it found on its first honest run

    before   654 delivered   222 in flight   0 UNDELIVERED   (71 slices "open")
    after    870 delivered     0 in flight   1 UNDELIVERED   tools/keep_emit.py

Git and the caught-up ledger agree file for file.

**And one more, which this audit cannot see and is recorded here instead.**
`docs/AI_HARNESS.md` in `origin/main` carries a paragraph headed **ADR-218** —
thirty declarations, `tools/exempt.py`, `tools/audit_declared.py`,
`verify_declared`. None of those files exists in origin, on the operator's disk,
or in any tarball there. Four SHARED paths carry it and nothing else does:
`AI_HARNESS.md` has its paragraph, `harness_board.py` lists its runner,
`mutant_ledger.json` records that runner's 53 mutants, all killed — and
`tools/verify/run_all.py` runs `audit_declared` as its last audit, a file that is
not there, **so a full run on origin/main has had a red row since ADR-217 for a
second reason**. ADR-217's commit staged those paths while the next slice's
edits were already in them, and the slice itself never left the session that
wrote it. It is ADR-184's incident
again with the roles swapped: there, shared paths were committed under the wrong
message; here a description was committed and its subject was not. From ADR-147
on, every slice has four records — an ADR, a changelog, a manifest and a
paragraph — and 218 is the only number with one of four.

This slice is numbered 219 so that 218 stays what it is.

## 5. Numbers

`verify_delivery` 50 → 66 (section E; thirteen of the sixteen build a real
repository and print NOT VERIFIED where there is no git). `mutate_delivery`
38 → 53, all killed.

## 6. Held

- **ADR-218 is rebuilt** — its paragraph and the names of its 53 mutants are a
  specification — **or its four traces are withdrawn**, and `--check` then holds
  the four records of a slice to each other. Until then `audit_declared` is a
  red row that says exactly what is wrong: the file is not there. Trigger: the
  end of the door work that follows this slice (ADR-220 to ADR-222). Not before, because a check that fails
  on arrival for a reason the slice cannot fix is a red nobody reads.
- **Committed is not pushed.** `ls-tree HEAD` is the local branch. What the
  remote holds is visible only to the push script, which has checked it since
  ADR-217.
- **`git commit` in a push script commits the whole index**, not only the paths
  it just added; anything staged by hand beforehand rides along. Price: one
  `--only`-style pathspec per script and all seventy scripts regenerated.
  Trigger: the first stray staged file.
