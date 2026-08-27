# ADR-072: ninety-eight checks that were never allowed to speak

**Status:** Accepted and implemented — `tools/mutate.py` (`scratch_root` completeness, and an exclusion
message that points at the right thing), `tools/verify/verify_mutate.py` (19 → 24),
`tools/verify/verify_rv.py` (76 → 81), `tools/verify/verify_sweep_ledger.py` (22 → 23).
**Date:** 2026-08-27
**Deciders:** Richmond
**Follows:** ADR-066, ADR-069, ADR-070, ADR-071

---

## Context

ADR-070 taught the sweep to refuse a suite that cannot testify. The first thing it refused was not a
bad suite. It was a good suite being run in a broken room, and the sweep blamed the suite.

## 1. `verify_eco` has never once testified in a sweep

Sweeping the twelve loader-only pages, five of them printed:

```
EXCLUDED, already failing on clean code -- a red suite kills every mutant: eco
no green suite names this page -- nothing to measure against
```

`verify_eco` passes **98/98** in the real tree. It fails in the sweep's scratch copy, and the reason is
one line:

```
FAIL: no broken links across the kit  << [('tree-proofs.html', '../README.md', 'missing file')]
```

`scratch_root()` copies `docs/` and `tools/`. `tree-proofs.html` links to `../README.md`, which is
neither. So in every scratch copy ever built, that link was broken, so `verify_eco` was red, so the
guard excluded it — **from every page it names, for as long as the guard has existed, and from every
sweep before that in the form of a suite that could never report a kill.** Ninety-eight checks with no
vote.

The pages it names are `ecology`, `ecology-essay`, `ecology-field-card`, `ecology-field-guide`,
`ecology-glossary`, `ecology-lab`, `ecology-lab-manual`, `ecology-teachers-guide`,
`eco-protocol-library`, `eco-protocol-reference`, `fungal-characters` and `plant-characters`. Two of
those were recorded at 100% already, so nothing was overstated — the error ran the safe way, toward
pessimism — but a score is not a score if a witness was gagged.

`scratch_root()` now copies the top-level **files** as well. Directories are still left out on purpose:
`build/` and the Java tree are large and nothing in `docs/` links into them.

### The message was the second defect

*"already failing on clean code"* is a claim about the suite, and it was false. The suite is healthy;
the copy was incomplete. The line sent the reader to look in the wrong place, and it took a sweep
printing it about a suite I knew to be green before anybody looked at the copy instead.

```
EXCLUDED, red on the UNMUTATED scratch copy -- a red suite kills every mutant.
If it passes in the real tree, the scratch copy is missing something it reads: eco
```

`verify_mutate` asserts the wording now, along with the completeness of the copy and, specifically,
that a page's links out of `docs/` still resolve inside it. Canaried by removing the copy: two checks
fail, naming the eight files and the `../README.md` link.

This is the third time in four ADRs that a guard was right and its **reason** was wrong. A guard that
reports the wrong cause costs more than one that stays silent, because it is confidently pointing.

## 2. The twelve loader-only pages, swept for real

They were tempting to wave through: ADR-066 proved the boot loader is byte-identical across the kit
and ADR-071 found that `verify_offline_slice` kills its mutant, so one page's result is arguably every
page's. Sweeping them anyway cost about twenty minutes of background CPU and produced evidence instead
of an argument. **Twelve pages, 100% each, every kill attributed to `offline_slice`.**

It also produced the finding above, which the argument would have skipped past.

**34 of 39 pages swept. Five to go, all with code of their own.**

## 3. Relevé: 67% → 100%

**`PI <= 3.0` → `PI < 3.0`.** The prevalence index threshold for hydrophytic vegetation. This is a
regulatory criterion, the boundary is inclusive, and at exactly 3.00 the mutant flips a wetland
determination from *"at or below 3.0, the Corps threshold"* to *"above 3.0, so the vegetation does not
by itself indicate a wetland"*. The suite checked that an index appeared and never what it was
compared against.

3.00 exactly is trivially reachable and realistic: score every taxon **FAC**, indicator value 3, and
the cover-weighted mean is 3 whatever the covers are. That independence is the point — a fixture whose
index depended on the cover classes would be testing the arithmetic, and the mutation was in the
comparison.

**`Math.max(..., 100)` → `Math.min` in the stratum bars.** The `100` is a floor: a stratum covering 40%
draws a bar 40% of the way across, because cover is read against a 100% scale. With a min, the largest
stratum sets the scale and every bar fills. Measured: 90.5% cover drew a 90.5% bar, and 100% with the
mutant. The check asserts the meaning of the floor — while the total is under 100%, the bar width **is**
the total — rather than any particular number.

Nothing in this kit had asserted a bar width before, in the same way nothing had asserted a plotted
point's position before yesterday.

## Cost

`verify_rv` 76 → 81, `verify_mutate` 19 → 24, `verify_sweep_ledger` 22 → 23. No page changed.
17 pages swept this slice. **55/55 jobs green, 3895 checks.**

One more check fired on correct work and had to be rewritten. `verify_sweep_ledger` asserted the
classifier "returns more than one value across the remaining pages", and the moment the twelve
loader-only pages were swept the backlog became homogeneous and the check failed. It now asks the
classifier to tell two NAMED pages apart, which is what non-vacuous means for a classifier and stays
true when the backlog empties.

**Swept: 34 pages, 5 to go — collection-sheet, cp-bench, eco-protocol-library, ecology-lab, soil-bench.**
