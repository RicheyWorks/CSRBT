# ADR-226 — The script that was refused before its first line

**`push-adr225-siblings.ps1` never ran. Its twentieth line said
`Write-Host "!! $dir: git commit failed"`, and PowerShell reads `$dir:` as a
drive-qualified variable — the same syntax as `$env:PATH` and `$script:failed`
— so the file is a parse error and the whole of it is refused before the first
line executes. The main script had already printed `ADR225 pushed.`; the
sibling one printed `Variable reference is not valid` twice and pushed nothing.
WholeHog's workflow and SmokeHouse's fix stayed on the operator's disk.**

## Why nothing caught it

`deliver.py --check` compares every generated script to what its manifest
generates, byte for byte. The sibling script is hand-written — it commits two
repos that have no manifests — and a hand-written script is exactly the one
nothing else holds. Nothing in the kit had ever parsed a push script; the
generated ones are correct by construction, and the one that was not
constructed was not checked.

The fault is a fixed rule of the language, which is what makes it holdable: a
`$name` followed by a colon is a scope or drive qualifier, and the qualifiers
PowerShell knows are a short list.

## Decision

- **`deliver.ps_parse_faults(text)`** returns every `$name:` in a script whose
  name is not one of `env`, `script`, `global`, `local`, `private`, `using`,
  `variable`, `function`, `alias` — with its line number.
- **`--check` reads EVERY script under `tools/push/`**, generated or not, and
  refuses one with a fault, naming the file, the line, and the fix (`${dir}:`).
- The sibling script is fixed at both lines. Its `$script:failed` lines were
  already right; a scope qualifier is not a fault, in any case.

## Verified

`verify_delivery` 76 → 82 (section G: the exact line ADR-225 shipped; scopes in
every case pass; the braced form passes; line numbers are the file's; a
hand-written fixture script under `tools/push` is named by `--check` and the
check is quiet once it is removed). `mutate_delivery` 60 → 63: never a fault,
always a fault, only the generated scripts are read — all killed.

## And what the delivery of this slice found

`verify_board` was run on the operator's VM for the first time after a
delivery and failed its first check — *the committed board is byte-for-byte
what the ledgers render* — with every ledger identical to the container's.
The board stamped its readings in the renderer's LOCAL time, so the page was a
different page on every machine in a different zone: the container is UTC-7,
the VM is UTC, and the check was really "this machine stands where the page was
rendered". `when()` renders UTC now, the footer says so, and `verify_board`
renders the same ledgers under UTC, Tokyo and Los Angeles and holds the three
to the same bytes. 118 → 121.

## Held

`harness_board.py` has no mutant runner — `verify_board`'s 121 checks are the one suite in the
kit without one; its own slice. A real PowerShell parse (`[System.Management.Automation.Language.Parser]`)
would hold every syntax fault and not this one. Price: a `pwsh` on the machine
that runs `--check`; the container and the VM have none. Trigger: the second
class of parse fault a script ships with.
