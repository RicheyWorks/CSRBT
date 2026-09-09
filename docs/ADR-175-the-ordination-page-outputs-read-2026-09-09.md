# ADR-175 — The ordination page's outputs, read — the dissimilarity matrix byte for byte, the coordinates by their shape

**Status:** accepted · **Date:** 2026-09-09 · **The ordination page hands over its coordinates, its dissimilarity matrix and a print, and nothing read them. The task reads all three: the matrix byte for byte against `verify_ord`'s own Bray-Curtis port, the coordinates by their shape and the page's own warning — because NMDS axes are arbitrary and a pinned position would be a coincidence held as a fact. Unread outputs 12 → 9.**

## Two exports, two kinds of claim

`audit_outputs` listed ordination next: `Copy coordinates`, `Copy
dissimilarity matrix`, `Print / save PDF`, none read. The matrix is the one
file a reader would take to R: for the task's last run — the quoted four-site
data, square-rooted, Wisconsin-standardised, Bray-Curtis — it is a
deterministic function of the data and the settings, and `verify_ord` has
carried Python ports of `wisconsin()` and `bray()` held against scipy since
ADR-149. The coordinates are not that kind of number. The export says so in
its own last line: *NMDS axes are arbitrary: this configuration may be rotated
or mirrored relative to another run and fit equally well.* ADR-140 declined to
hold the plot's positions for the same reason, and the export gets the same
answer.

## What changed

**The task presses every export on its last run and holds what left:**

- `Copy dissimilarity matrix` → one payload, held **byte for byte**: the
  header `,X,Y,Z,W`, four rows, six decimals, zeros on the diagonal, symmetric
  — X–Y 0.189902, X–W 0.101337, Y–Z 0.480846.
- `Copy coordinates` → one payload, held by **shape and warning**:
  `site,NMDS1,NMDS2`, a row for each of X, Y, Z and W, the arbitrary-axes
  warning with `stress-1 = 0.0000` (the task already holds `Stress 0.000` on
  screen), and no `NaN`. No position is pinned.
- `Print / save PDF` → exactly one payload, a print.
- Then the parse and the verdict are read once more, unchanged.

**The literals are pinned by the page's suite.** `verify_ord` recomputes the
matrix from the same data through its own `wisconsin()` and `bray()` and holds
the task's literal to it — change one digit in the task and the suite fails
(skipped, and said so, where numpy is absent, like the rest of that suite's
numerical checks). It also holds that the coordinates step pins *no*
six-decimal number: a later hand that "tightens" the task by pasting the
positions in is caught. 111 → 114.

## What moved

    ordination outputs           0 → 3 of 3 held      ceiling 3 → 0
    the kit's unread outputs    12 → 9 of 66          (7 pages still hand something over unread)
    page-ordination-science      70 → 89 confirmed, 0 refuted
    verify_ord                  111 → 114

No page was edited: a task, its page's suite, and the ledger.

## Held

- The copy on this page arrives as a `copy` payload (the page's clipboard
  path falls through to `execCommand` under the harness), not a `clipboard`
  one; the task holds the kind it actually is.
- The matrix's sixth decimal is the page's `toFixed(6)`; the port formats the
  same way, so agreement is to the printed digit, not to a tolerance.
- Not done here: deployment-log (2), soil-recipes (2), farm-scout,
  pheno-tracker, field-season, soil-bench, eco-protocol-library.
