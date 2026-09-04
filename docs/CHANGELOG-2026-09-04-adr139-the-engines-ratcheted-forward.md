# Changelog — 2026-09-04 — ADR-139: the engines, ratcheted forward

## Tools — `tools/`

- `ecosystem.py`: `read_results` also returns `suites` — the JUnit testsuite
  name (the test class) and its count — and the ledger keeps a **`classFloor`**
  per engine, 299 classes across fifteen engines. A read raises a class's floor
  and never lowers it. New `--forget ENGINE CLASS --reason "..."`: the only way
  a class comes off the ratchet, recording the size it had and why it went.
- `engine_attest.py` **(new)**: one implementation of "run the engine"
  (`classpath()`, `engine_output()`, moved out of the suite so the suite and the
  attestation cannot disagree), plus the attestation itself —
  `--attest` runs the engine and records what it emitted alongside a digest of
  `csrbt-core` + `csrbt-experimental` main sources, by **path and bytes**;
  `check()` returns `attested` / `differs` / `stale` / `absent`. Only a machine
  that ran the engine can write a record.
- `harness_board.py`: `mutate_engines` on the runners list.

## Verification

`verify_ecosystem` **99** (+10): a class on the ratchet that is not in the
results any more, or is smaller, is a failure naming it and both counts; the
ratchet's **rule** driven against a fixture ledger with inflated floors (a read
never lowers a floor, nor a class floor; an absent class keeps its floor,
because that is what makes its absence visible; a new class joins at what it
read; a forgotten class does not rejoin); both escape hatches refused without a
reason and recorded with one; an engine over two modules keeping both modules'
classes.

`verify_engine_sessions` **37** (+11): link A prefers the live run and falls
back to the attestation, which is a PASS whose own name says it is attested and
when — or a **failure** if the shipped bytes are not what was attested (on a
machine with no Java at all), or `NOT VERIFIED` if the engine has moved since.
Measured: with `build/` removed the suite goes from a hole to 25/25 clean, and
one byte added to one `csrbt-core` source puts the hole straight back.

`tools/mutate_engines.py` **(new)**: 13 mutants over `ecosystem.py` and
`engine_attest.py`, each put to whichever suite owns it. 13 killed, 0 survived.
The runner mirrors the real layout in its temp tree, because `ecosystem.py`
resolves each engine at `<repo>/..` and a bare temp dir finds none.

`verify_board` 51 (+3). `verify_mutate` 47 — `verify_ecosystem` and
`verify_engine_sessions` now declare `MUTATE_ROLE = "subject"`, since both
started using a temp dir this slice (a fixture ledger; two fixture `.java`
files) and neither holds fixture pages.

Kit **77 / 77 jobs, 5,731 / 5,731 checks**; board 5,321 checks / 256 mutants;
publish reach 42 / 42 measured.

## Docs

`docs/ADR-139-the-engines-ratcheted-forward-2026-09-04.md`;
`docs/AUTOMATION-HARNESS.md`, `docs/AI_HARNESS.md`.
