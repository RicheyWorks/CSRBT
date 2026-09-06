# ADR-147 — One list, not two

**Status:** accepted · **Date:** 2026-09-06 · **Every slice produced two hand-written lists of the same file set — the tarball's, and the push script's `git add` — and nothing compared them. When they disagreed, the file reached the disk and never reached a commit, and every audit in the kit stayed green. Four files sat that way for three days. There is one list now, and the push script moves into the repository**

## 1. The blind spot, stated

Every audit in this kit measures the **working tree**. That is the right thing
to measure, and it has one blind spot, which is total:

> A file that was written, shipped to the operator's disk and never named by a
> push script is **present in every measurement the kit takes** and **absent
> from the repository.**

Every suite is green about it. Every audit reads it. `entry_reach` counts the
fields it enters, `audit_readable` reads the figures it publishes,
`verify_suites` finds it registered. And it exists nowhere but one machine.

## 2. It happened

ADR-143 and ADR-144 delivered four files in their tarballs:

```
tools/audit_targets.py     tools/audit_focus.py
tools/audit_contrast.py    tools/verify/verify_organism.py
```

The three state audits printing the **name** of a never-exposed control in
their summaries — ADR-143's own rule, which ADR-144's changelog says it
finished — and `verify_organism` printing the lines that differ when two
consecutive physicals disagree, which is the whole of what ADR-143 learned about
that flake.

Neither slice's push script named them. They sat modified and uncommitted for
three days, through six full green runs, and were found only because a push
script was run twice and the second run had nothing to stage.

Nothing in the kit could have found them. There is no audit of the delivery.

## 3. One list

A slice writes **one** file, `tools/delivery/<id>.json`:

```json
{"id": "adr147", "chain": "adr146b", "chain_probe": "tools/audit_targets.py",
 "subject": "...", "body": "...", "paths": [...], "clean": [...]}
```

and `tools/deliver.py` generates both artefacts from it:

```
python3 tools/deliver.py --script adr147   # tools/push/push-adr147.ps1
python3 tools/deliver.py --bundle adr147   # the tarball, containing exactly those paths
python3 tools/deliver.py --record adr147   # move the delivery ledger forward
python3 tools/deliver.py --check           # every manifest, every script
```

Neither list is hand-written again, and `--check` holds that: every path a
manifest names **exists**; every generated script is **byte-identical** to the
one on disk, so a hand edit is a failure rather than a silent divergence; a
manifest's id is its filename; and its chain names a manifest or a script that
is really there.

The escaping is the fiddly part and it is checked: a subject carrying a quote, a
**backtick** and a `$` comes out right, and the backtick is escaped **first** —
it is PowerShell's escape character, so doing it last escapes every other escape.

## 4. The push script moves into the repository

It was the one artefact of every slice that lived outside it — outside every
audit, outside every suite, outside the commit it describes.

ADR-096 to ADR-103 kept theirs in `CSRBT/`. From ADR-104 they were written to
the parent directory instead, and **the scripts for ADR-104 to ADR-111 no longer
exist anywhere**, so what those eight slices staged cannot now be read. Nothing
noticed either the drift or the loss, because nothing was looking.

They live in `tools/push/` now, and a generated script finds the repository from
its own location rather than from the directory it is run in.

## 5. The measurement — `tools/audit_delivery.py`

There is no git in the agent's copy — it is a mount, not a clone — so the
evidence is **content**:

    UNDELIVERED = tracked files whose sha256 is not the one last delivered
                  - the paths some manifest claims
                  - the paths declared outside delivery, with a reason

The subtraction is what makes it runnable **during** a slice: work in flight is
declared by the slice's own manifest, which is the same list the script and the
tarball come from. **Name it in the manifest, or the audit names it here** —
that is the whole mechanism in one sentence.

It fails by default with no flag, because `run_all` runs an audit with no
arguments, and `audit_delivery` is registered there now.

**Seeded by adoption.** The ledger starts from a tree known to be committed, and
says so in its own `_adopted` block: an adoption is not evidence that those bytes
were pushed, it is the baseline the ratchet starts from. It does **not** adopt
what a manifest already claims — adopting a slice's own work in flight would
record as delivered exactly the files that have not been.

## 6. What is asserted

`verify_delivery` **36**, new, on a fixture repository: the script stages every
path in the manifest's order; the subject's quote, backtick and `$` are escaped
and the body is one line; generating twice gives the same bytes; a hand-edited
script, a manifest naming a file that is not there, an id that is not its
filename and a chain to nothing each fail while a good manifest does not; the
tarball holds exactly the manifest's paths plus the script that commits them;
an unrecorded file is undelivered and **named**, one a manifest claims is in
flight, recording moves it to delivered and changing its bytes moves it back;
ignoring needs a reason; and a file delivered once and since deleted is reported
as *gone* and is not a failure.

`mutate_delivery` **30**, 30 killed, 0 survived.

## 7. Held

- **This is not proof that a delivered file was pushed.** That happens on a
  machine this process cannot see, and the ledger records what was handed over,
  not what git did with it. It is the other half: *a file nothing has ever
  handed over cannot have been pushed*, and that is the failure this exists for.
- **A regenerated ledger is not evidence about itself.** The delivery ledger
  cannot record its own bytes — writing the record changes the file — so it is
  declared outside the accounting with that reason. Every other ledger the suite
  rewrites is named by the slice's manifest, which is the honest discipline: if
  you ran the suite, you are shipping the ledgers.
- **Evidence directories, traces and binaries are outside the accounting**,
  because a screenshot rewritten by every run is not an undelivered change.
- **An audit's last line is what `run_all` puts in its row, and `run_all` scores
  anything shaped like `N / M`.** Written that way, this audit's summary made the
  kit's headline check count grow by 621 in one commit — 621 *files* read as 621
  checks. The line is deliberately not that shape now, and `verify_delivery`
  holds it: a row that reads is worth having; a score that is not a score is not.
- **The scripts for ADR-104 to ADR-111 are gone and this does not recover them.**
  What those slices staged is unreadable now and stays unreadable.
- This slice's own delivery is made by the new tool, which is the only way to
  find out whether it works.
