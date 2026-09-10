# ADR-184 — A push script pushes once: run again after its slice is in HEAD, it finishes an undelivered push or does nothing

**Status:** accepted · **Date:** 2026-09-10 · **`push-adr182.ps1` was run a second time, after ADR-183 had landed on disk. It did exactly what it was written to do — `git add` the paths its manifest names, which ADR-183 had just changed, and commit them under ADR-182's message — and origin was left holding a `verify_eco` that imported a module origin did not have. The script had no notion of having already run. A manifest that says `"once": true` now generates a script that knows: its own manifest in HEAD's tree is the fact that the slice was committed, and from then on the script pushes a commit the push never delivered or does nothing, and says which. Every earlier script still generates byte for byte.**

## What happened

ADR-147 made the push script a generated thing: one manifest, one list of
paths, a script that stages exactly those and commits them, and `--check` to
hold the script to the manifest. It works because every slice's paths are the
slice's own — and that is not true of the ledgers. `task_ledger.json`,
`delivery_ledger.json`, `counts.json`, `harness_board.html`, `AI_HARNESS.md`
are in every manifest, because every slice moves them.

So when ADR-183's seventeen files were on disk and `push-adr182.ps1` ran
again, twelve of its nineteen paths were modified — the shared ledgers, plus
the lab task and `verify_eco`, which both slices happened to touch — and it
committed the twelve as ADR-182 and pushed. The five that were ADR-183's
alone (its manifest, its ADR and changelog, its push script, and
`tools/verify/_lab_charts.py`) were on no list the script had, and stayed
where they were. Origin's `verify_eco` now began `import _lab_charts`, and
origin had no such file. The chain mechanism could not help: it looks
*backward*, at whether the previous slice is committed, and ADR-182 was.

## What changed

**The guard.** With `"once": true` in the manifest, `script_text` emits,
after the lock removal and before the chain and the `git add`:

    $mine = git -C $csrbt ls-tree HEAD -- tools/delivery/<id>.json
    if ($mine) {
      $ahead = git -C $csrbt rev-list --count "@{u}..HEAD"
      if ([int]$ahead -gt 0) { push; exit 0 }          # the one thing left to finish
      "already pushed -- nothing to do (modified paths belong to a later slice; run its script)"; exit 0
    }

Three choices. *The slice's own manifest* is the probe, not a ledger or a
suite, because it is the one path in the list that is this slice's and no
later one's. *`ls-tree`*, not `cat-file -e`, because it prints the entry or
nothing and writes no stderr for `$ErrorActionPreference = "Stop"` to trip
on. *Before the chain*, because a second run must not run the previous
script either. The commit-but-no-push case is kept: a push that failed at
the network leaves the manifest in HEAD and the branch ahead of upstream,
and that is the only work a second run may still own.

**Opt-in by key.** Manifests without `"once"` generate what they always did.
Thirty-seven scripts on disk pass `--check` unchanged; `adr184.json` is the
first with the key, and every manifest copied from it will carry it.

**Held by text.** `verify_delivery` cannot run PowerShell, so it holds the
guard by what it says: no guard without the key; the guard names the slice's
own manifest and asks with `ls-tree`; it sits before `& $prev` and before
`git add`; the ahead branch counts `@{u}..HEAD` and pushes; the other branch
says "already pushed" and exits 0; nothing inside the guard stages a path;
the guarded script is deterministic. `mutate_delivery` breaks each: the
guard for every manifest (every old script would fail `--check`), the guard
on a shared path, the undelivered push dropped, the fall-through after
"nothing to do".

**This slice's chain lands the last one.** `adr184.json` chains from
`adr183` with probe `tools/verify/_lab_charts.py`, which is still uncommitted
on the working disk; `push-adr184.ps1` therefore runs `push-adr183.ps1`
first, which stages ADR-183's five remaining files under ADR-183's message,
and then commits its own. The twelve files already on origin under ADR-182's
second commit stay where they are: history is not rewritten for a message.

## What moved

    verify_delivery      36 → 43        mutate_delivery   30 → 34 / 34
    deliver.py --check   37 manifests, 0 problems (every earlier script unchanged)

One generator, one suite, one runner, one manifest. No page was edited.

## Held

- The guard is held by its text, not by running it: there is no PowerShell
  in the container. The first real run of a guarded script is
  `push-adr184.ps1` itself; its second run is the first measurement.
- A script without the key is exactly as unsafe as before. The key is
  opt-in so that `--check` stays byte-strict on the thirty-seven scripts that
  exist; a generator that emitted the guard for all would have made every one
  of them "edited by hand".
- ADR-182's second commit on origin carries ADR-183's changes under
  ADR-182's subject. It is a blemish in the log, not in the tree, and the
  delivery ledger records the bytes by slice regardless.
