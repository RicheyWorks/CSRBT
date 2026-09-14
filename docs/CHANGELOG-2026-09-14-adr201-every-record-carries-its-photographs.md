# 2026-09-14 — ADR-201: every record carries its photographs

**One page in this kit took a photograph and twenty did not, on a kit that emits
Darwin Core with `associatedMedia` missing from the column list entirely — so
every deposit it has ever produced left its media unnamed. Closed on nine pages
through one shared component. Driving that component then found a second defect
in the harness: two of its eight action pools named kinds the snapshot never
published.**

## Added

- **`FEK.photos`** in the shared entry layer, with `FEK.crc32`. A record is
  `filename · bytes · captured · crc32` — the reference, never the image: a CSV
  cell cannot hold a JPEG, base64 turns a 40 kB export into a 4 MB one, and
  Darwin Core asks the term for an identifier *of* the media. CRC-32 rather than
  SHA-256 because `crypto.subtle` does not exist on a `file://` page and this
  kit runs off a card in the field as well as over https — a digest available in
  one of those two is worse than a weaker one that agrees in both. It is an
  integrity check, not a cryptographic one. The component carries its own live
  region, so a file that is not an image is refused **out loud, naming it**.
- **Photographs on nine pages**: collection sheet, relevé, deployment log, field
  notebook, pheno tracker, farm scout, selection log, ethogram, survey design.
  Each export carries the filename and the checksum.
- **`associatedMedia` in the Darwin Core term list** — it was absent. The
  collection sheet, relevé, survey design and stand sheet now populate it.
- **`mutate_fek`** — the one file nineteen pages inline had no mutant runner at
  all. Thirteen mutants, all killed.
- `verify_fek` 101 → 122, `verify_harness` 28 → 33, `verify_dwc` 150 → 154,
  `verify_report` 242 → 246, `mutate_harness` 18 → 22, `mutate_report` 145 → 148.

## Fixed

- **`drop_zone` and `checkbox` were kinds the door pooled and the snapshot never
  published.** `drop-files` takes a `drop_zone`, and the refusal a bad address
  earns advertised `@kind=drop_zone`, while the kind list carried no such thing —
  it lived in `swarm.py`, which only the swarm reads. ADR-141's rule backwards.
  Both published; the check is written over the **pools**, which is how the
  second one was found.
- **A `verify_report` check that passed or failed on machine load.** Three
  checks failed on the committed ADR-200 tree when run outside `run_all`: the
  page autosaves on a debounce and the widget it renders arrived after the
  baseline snapshot. The suite now settles — two observations agreeing on the
  stamp — before taking its baseline.
- **Three exports that said "nothing logged" whatever else the session held.** A
  reader who photographed four stations before typing any settings copied a
  sheet claiming their morning had not happened.
- **A `typeof x === "function"` guard hiding a wrong function name** on the
  survey design, where the export writer is `outOut()` and the wiring named
  `ecoOut()`. The photographs never reached the export and nothing complained.

## Changed

- The swarm's kind list no longer re-adds `drop_zone` and `checkbox`: a kind
  listed twice is discovered twice, the selectors renumber, and a diff reports
  controls appearing that nobody added. Asserted in both lists now.
- `mutate_harness` runs **both** harness suites. A mutant only `verify_harness`
  could see was, until now, a mutant nothing could see.
- The stand sheet's own photo pane takes the shared checksum so its
  `associatedMedia` matches the rest of the kit. It is **not** migrated onto the
  component — it carries a *Link species* button the component knows nothing
  about, and that is a second change wearing one hat. Filed.
