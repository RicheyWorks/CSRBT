# ADR-079: Green about the repo

**Status:** Accepted and implemented — `docs/adr-031.html` and `docs/ecology-lab.html` republished and
confirmed at their URLs; `tools/publish_state.py` states the transfer rule in its report.
**Date:** 2026-08-27
**Deciders:** Richmond
**Follows:** ADR-031, ADR-055, ADR-078

---

## 1. Acting on the measurement

ADR-078 built the instrument and left the work: two pages measured **BEHIND**, both blocking first
paint on a font request. This slice republished them and confirmed the fix at the URL rather than at
the publisher.

What the diff turned up is the reason this is its own record. `ecology-lab.html` was not behind by one
defect. It was behind by **nine regions**, and two of them are the kit's own accessibility work:

| what the published flagship was serving | what the repo says |
|---|---|
| `--muted: #8B8B7B` — **2.98:1**, below WCAG AA | `#6B6B5E` |
| `--s1: #2E7D4F`, `--s2: #C0592B` — the 4.34–4.47 near-misses | `#2C784C`, `#A94F26` |
| a render-blocking webfont stylesheet | `media="print"` + promoter (ADR-031) |
| no WCAG 1.4.11 rule on form-control borders | scoped to inputs |
| no `data-print="chrome"` on the drop hint | declared for the print audit |

`adr-031.html` was behind by four, including a whole documented section and the same blocking font
link — **on the page that defines the constraint**.

## 2. The sentence this is about

`audit_contrast.py` found those 1,397 failures, and fixing four token values cleared every one. That
work is real, it is described at length in ADR-031, and the audit has been green ever since.

**It is green about `docs/`.** Nobody reads `docs/`.

Every audit and every suite in this kit measures the repo. For a page whose published copy carries the
same bytes, a green audit is also a claim about what a reader sees. For a page that is behind, it is a
claim about a file on a disk. Nothing had ever stated which pages were which — that is what ADR-078
made answerable — and nothing stated that the distinction was load-bearing for every other number the
kit reports.

So `publish_state.py` now says it, in the report, next to the count:

```
17 current, 6 behind (0 of them measured at the URL), 16 unknown, 0 unmapped
   22 page(s) are NOT known to carry the audited bytes -- for those, a green audit
   of docs/ says nothing about what a reader sees
```

Twenty-two of thirty-nine. That is the honest scope of every green audit in this kit today.

## 3. What was actually done

Both republishes went through the gate properly: `action: read`, then **every line** of the live
version read (636 and 3,356), then a computed diff to confirm nothing published was being dropped, then
publish. No forcing, and the standing authorisation was not used — the gate refused the first attempt
and re-reading in sequence satisfied it.

Then both were **read back from the URL** and re-measured, which is the only evidence that means
anything here:

```
adr-031.html        CURRENT, measured from the live copy taken at 1787873301
ecology-lab.html    CURRENT, measured from the live copy taken at 1787873397
```

Confirmed in the returned bytes: the deferred loader with its `noscript` fallback and promoter, and
`--muted: #6B6B5E` / `--s1: #2C784C` / `--s2: #A94F26`.

## 4. What I did not build, and why

The obvious next move is to run `audit_contrast.py` against the *published* bytes. I did not, because
the tool already answers it: **containment is the transfer.** `--verify` passes only when the published
copy carries the repo's bytes verbatim, and bytes that are identical paint identically. Running a
second contrast audit over a wrapped copy would add a browser, a skeleton to exclude, and a new class
of false finding — to re-derive something the hash already proves. The link needed stating, not
building.

## 5. Where the pile stands

| | before | after |
|---|---|---|
| published state | 15 current / 8 behind / 16 unknown | **17 current** / 6 behind / 16 unknown |
| pages known to carry the audited bytes | 15 | **17** |
| stamps earned by reading the live page | 1 | **3** |

The six remaining BEHIND pages are `cell-bench`, `deployment-log`, `food-web`, `ordination`,
`soil-recipes`, `stand-sheet` — each a `--stamp` away once republished. The sixteen unknowns are each
one read away from a verdict. Neither list is guessed at any more.
