# Changelog — 2026-09-06 — ADR-147: one list, not two

Every audit in this kit measures the working tree. A file that was written,
shipped to the operator's disk and never named by a push script is **present in
every measurement the kit takes and absent from the repository** — and every
suite stays green about it.

## It happened

ADR-143 and ADR-144 shipped four files and neither push script named them:

```
tools/audit_targets.py     tools/audit_focus.py
tools/audit_contrast.py    tools/verify/verify_organism.py
```

The three state audits printing the **name** of a never-exposed control in their
summaries, and `verify_organism` printing the lines that differ when two
consecutive physicals disagree. Modified and uncommitted for three days, through
six full green runs, found only because a push script was run twice and the
second run had nothing to stage.

## New — `tools/deliver.py`

One list. A slice writes `tools/delivery/<id>.json` and the tool generates both
artefacts from it.

```
python3 tools/deliver.py --script adr147   # tools/push/push-adr147.ps1
python3 tools/deliver.py --bundle adr147   # the tarball — exactly those paths
python3 tools/deliver.py --record adr147   # move the delivery ledger forward
python3 tools/deliver.py --check           # every manifest, every script
```

`--check` holds: every path a manifest names exists; every generated script is
**byte-identical** to the one on disk (a hand edit is a failure, not a silent
divergence); a manifest's id is its filename; its chain names something that is
really there. The PowerShell escaping is checked too — quote, backtick and `$`,
with the backtick **first**, since doing it last escapes every other escape.

## The push script moves into the repository

It was the one artefact of every slice that lived outside it — outside every
audit, outside every suite, outside the commit it describes. ADR-096 to ADR-103
kept theirs in `CSRBT/`; from ADR-104 they went to the parent directory, and
**the scripts for ADR-104 to ADR-111 no longer exist anywhere.** What those
eight slices staged cannot now be read. Nothing noticed the drift or the loss.

They live in `tools/push/` now, and find the repository from their own location.

```
.\CSRBT\tools\push\push-adr147.ps1
```

## New — `tools/audit_delivery.py`

There is no git in the agent's copy, so the evidence is **content**:

```
UNDELIVERED = tracked files whose sha256 is not the one last delivered
              - the paths some manifest claims
              - the paths declared outside delivery, with a reason
```

The subtraction is what makes it runnable during a slice. **Name it in the
manifest, or the audit names it here.** Fails by default with no flag;
registered in `run_all`.

Seeded by adoption from a tree known to be committed, and the ledger says so —
an adoption is a baseline, not evidence. It does not adopt what a manifest
already claims.

## The board — `tools/harness_board.py`

New tile: **files delivered**, and the slice count behind it. `mutate_delivery`
joins the runner table.

## Verification

- `verify_delivery` **36**, new, on a fixture repository.
- `mutate_delivery` **30**, 30 killed, 0 survived.

## Docs

`docs/ADR-147-one-list-not-two-2026-09-06.md`; `docs/AI_HARNESS.md`.
