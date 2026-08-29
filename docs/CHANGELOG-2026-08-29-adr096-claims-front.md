# 2026-08-29 — the claims worklist, and what reading the published copies found (ADR-096)

Working ADR-094's twelve BARE claims meant republishing nine pages, which meant reading each live
copy first. **Eight of the nine were serving prose the repository never had** — most of it
provenance the repo was missing. That is the finding; the worklist is the occasion.

## The published copies, back-merged into `docs/`

| page | brought back into the repo |
|---|---|
| `breeding-bench` | the 20/100 floor as "the seed-savers' rule of thumb, not a measured threshold"; sweet corn cited to *The Seed Garden* (Colley & Zystro, 2015); the intensities cited to Falconer & Mackay, 1996 |
| `cell-bench` | the chamber-factor derivation inline; "conventional 24 h"; the *improved* Neubauer ruling named |
| `deployment-log` | the `.src` sentence for the three AudioMoth figures; the speed-of-sound approximation written out; the duty legend printing "60 s of 600 s = 10.0% duty" |
| `cp-characters` | *Utricularia* bladders as 0.2 mm to 1.2 cm (Taylor, 1989) |
| `fungal-characters` | "Read at the **conventional** 30 s"; the 35 °C floor as a practitioners' rule of thumb |
| `micro-bench` | "The **conventional** volumes are 0.1 mL spread, 1.0 mL pour" |
| `cp-bench` | the top-up arithmetic, (10 × 50 = 500) |
| `eco-protocol-library` | "an **arbitrary** skew, chosen to make the collapse unmistakable" |

`ecology.html` was the only one that matched.

## What this slice added on top

* `ecology.html` — the water card **declares** its source: `<span class="src">California
  Carnivores</span>`. This is the half of ADR-094 §2 that the finder never accepted, and it is why
  that ADR's "14 BARE → 12" was wrong.
* `breeding-bench` — the 20/100 floor now states the spread it simplifies (Seed Savers Exchange's
  crop chart: 10–20 self-pollinators, 80 brassicas, 200 corn/carrots/onions) and calls the single
  floor a **deliberate simplification rather than an oversight**; the selection intensities are
  written out with p substituted — `i = φ(1.2816) / 0.10 ≈ 1.755` — so a reader can check them.
* `cp-characters` — the bladder range gains the usual 1–5 mm band beside the genus range.
* `micro-bench` — the spread volume names the standard that fixes it (FDA BAM Ch. 23 states 0.1 mL
  outright), which corrects ADR-094's use of this claim as its worked example of a number no standard
  in the card covers.
* `eco-protocol-library` — the 5-and-90 point at the `hot 2000 5 90` line printed below them.

## The finder — `tools/audit_claims.py`

* **One vocabulary, two probes.** `PROV`/`STD`/`CITED` were written out twice and had drifted: the
  section-level list named FDA BAM, AOAC, USP, APHA and Standard Methods, the block-level list did
  not, so the strict test was weaker than the loose one on five tokens. Written once now.
  **Clears no claim on today's forty pages** — measured.
* **A floor under `.cite`/`.src`/`.ref`.** An empty provenance element exempted the block it sat in.
  It must now carry three characters of text, or a link. No page had done it; closed anyway.
* **`.echo` built and withdrawn.** An exemption for "a legend that restates the reader's own entry"
  was written with a suite that drove each named control to prove the text moved — then the live
  `deployment-log` turned out to print its own duty arithmetic, so the existing derivation exemption
  covers it and `.echo` had zero members. Withdrawn, with the reason left in the file.

## The suites

* **`_kit.tool(name)`** imports a module out of `tools/`. `verify_claims_slice`,
  `verify_claims_triage` and `verify_print_slice` no longer split a tool's source on a literal
  sequence — the coupling ADR-094 named as not-done, and one that had to go now because §3's fix
  builds the probe from parts.
* **`verify_claims_slice` 31 → 51 checks.** Retires the extraction-marker uniqueness check for
  *no suite may split a tool's source*, across every `verify_*.py`. New seeded canaries: an empty
  `.src` is reported, a named one is not, a named organisation in bare prose still is. Plus the
  back-merged wording on six pages.
* **`verify_claims_math` 43 → 49 checks.** The intensity sentence now prints its substitution, so the
  suite checks the *argument* too — `x = Φ⁻¹(1−p)` and the denominator, not just `i`. Recomputed from
  the method, as before.

## The numbers

```
                                   claims   BARE
before                               29      13
finder changes only, pages untouched 29      13
page changes only, finder untouched  15       1
both                                 15       1
```

The one remaining BARE claim is `ecology-lab`'s heredity reading, adjudicated in ADR-094 §3.

## Verified

* `run_all.py -j 4` — **59 of 60 jobs green, 4277/4278 checks**, against a baseline of 59/60 and
  4247/4248 on the same tree. The one long-standing gap (`verify_engine_sessions` 24/25, needs
  `./gradlew classes`) is unchanged.
* `audit_targets`, `audit_focus`, `audit_contrast`, `audit_print`, `audit_escaping` — zero findings.
* `audit_ties`, `audit_print_channel` — unchanged.
* **`publish_state`: 40 current, 0 behind, 0 unknown** — 18 measured from the live page (up from 14),
  22 stamped at publish. **Five** pages republished (ecology, eco-protocol-library, cp-characters,
  breeding-bench, micro-bench); **four** verified against their live copy without republishing
  (cell-bench, cp-bench, fungal-characters, deployment-log), because after the back-merge the repo
  and the live page agreed byte for byte and `--verify` could stamp them from the read.

## Next

Thirty-one published pages have still not been read against the repo. Eight of the nine that were
read had drifted.
