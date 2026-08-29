# 2026-08-29 — ADR-097: thirty-one published pages read back into the repository

Companion to `docs/ADR-097-the-worklist-was-being-worked-in-the-wrong-copy-2026-08-29.md`.
This slice executed ADR-096 §9 verbatim: read every remaining artifact, diff, back-merge, `--verify`.

## Back-merged (live → repo)

Eleven of the thirty-one pages read had drifted. In every case the **published** copy was the newer
one; the direction of travel was live → repo throughout, and nothing was published.

| page | − | + | what came back |
|---|---|---|---|
| `breeding-suite.html` | 1 | 1 | 20/100 floor named "the seed-savers' rule of thumb" |
| `collection-sheet.html` | 6 | 8 | **factual correction** — 40–45 °C *straddles* the lower edge of 43–50 °C rather than sitting inside it; plus two provenance clauses |
| `cp-suite.html` | 1 | 1 | top-up arithmetic inline, (10 × 50 = 500) |
| `ecology-field-card.html` | 3 | 3 | "a rule of thumb"; "the conventional 80%"; "the conventional >80% confluence" |
| `ecology-glossary.html` | 2 | 2 | cover over 100% "correct by definition" |
| `ecology-lab-manual.html` | 2 | 2 | "Altmann's (Altmann, 1974)"; quadrat size named a convention |
| `ecology-lab.html` | 2 | 3 | a `.src` span naming where the two heredity figures come from |
| `ethogram.html` | 1 | 1 | "conventional starting points" |
| `field-season.html` | 1 | 1 | "a random (Poisson) pattern has ratio 1 by definition" |
| `releve.html` | 1 | 1 | cover over 100% "correct by definition" |
| `stand-sheet.html` | 1 | 1 | breast height as "the regional convention" |

Twenty of the thirty-one were byte-identical to their published copy and needed nothing.

## Re-measured

`tools/published.json` — every one of the forty entries re-stamped `via "read"` from a live copy
taken this session.

```
before   40 current, 0 behind, 0 unknown, 0 unmapped
         of the current: 22 stamped at publish time, 18 measured from the live page
after    40 current, 0 behind, 0 unknown, 0 unmapped
         of the current: 0 stamped at publish time, 40 measured from the live page
```

The five pages ADR-096 republished and stamped `via "publish"` — `breeding-bench`, `cp-characters`,
`eco-protocol-library`, `ecology`, `micro-bench` — were re-read from the live URL and all five
diffed to zero. ADR-096's republishes landed.

## Tools

**None changed.** `tools/audit_claims.py` is byte-identical to the version ADR-096 left
(`sha256 3c7a1fa0…`), as are `publish_state.py` and `verify/_kit.py`. Every number below moved
because the content moved.

## The numbers

```
pages read from the live URL                 36   (31 sweep + 5 ADR-096 republishes re-read)
of the 31 sweep pages: drifted               11
of the 31 sweep pages: identical             20
lines back-merged                            22 replaced by 24

audit_claims.py  before   11 pages, 15 claims, 1 BARE, 14 near
audit_claims.py  after     2 pages,  3 claims, 0 BARE,  3 near
```

The eleven pages `audit_claims.py` flagged before this slice are **the same eleven pages** that had
drifted — the finder's worklist and the drift set were one set. Each of the twelve cleared flags was
read against the edit that cleared it; ten were cleared by a phrase in the flagged claim's own
sentence, one by a `.src` span, one by inline arithmetic. None by a section-level blanket
(ADR-094). `collection-sheet` was edited three times and still carries both of its flags.

## Verification

* `python3 tools/audit_claims.py` — 2 pages, 3 claims, 0 BARE, 3 near.
* `python3 tools/publish_state.py` — 40 current, 40 measured from the live page.
* `python3 tools/verify/run_all.py` — **60 of 60 jobs green, 4279 of 4279 checks passing.**
  (4279, not ADR-096's 4278: `verify_engine_sessions` had been reporting 24/25 with its one
  engine round-trip UNVERIFIED because `log4j-core` was absent from the build cache. Resolving
  the test classpath supplied it; the job now runs the engine and reports 26/26. Nothing in the
  suite changed — a check that had been abstaining is now voting.)
* Every back-merged page re-published to `build/publish/` and re-diffed against its live copy to
  **0 drift lines** before being stamped.

## Next

* Three `near` claims remain: `collection-sheet` ×2, `micro-bench` ×1. Two want a source, not a label.
* ADR-097's falsifier: any of the forty drifting again before it is deliberately republished. The
  cheap check is `publish_state.py --verify` on a handful of pages, run *before* the next slice edits
  anything.
