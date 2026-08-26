# ADR-049 — Reachability is not staleness

**Status:** accepted · 2026-08-26
**Supersedes nothing. Corrects ADR-031's follow-through and my own conclusion in ADR-048's wake.**

## What happened

Thirty-seven pages of this kit are published as Artifacts. Eleven were
measurably behind the repo and twenty-six were of unknown vintage. Spot-checking
Breeding Bench found it serving Field Entry Kit **v1.1.1**, whose dial builds an
option as

    '<span>' + op.label + '</span>'

with no escaping — the exact defect ADR-031 fixed in v1.2.0, live on URLs that
people have been given.

Republishing all thirty-seven costs roughly four Read calls per page to satisfy
the publish gate. Before spending that, I asked whether the defect could fire.
I grepped every page for an option label containing an angle bracket, found
none, and concluded it could not.

**That conclusion was wrong, and the detector I then built to enforce it
contradicted it within a minute of existing.**

- `cp-bench.html` maps user-typed text straight into picker labels:
  `plants.push({name: nm.trim()})` → `options:plants.map(… label:p.name …)`, and
  `crosses` → `label:c.pod+" × "+c.pol`. Both parents are typed by the grower.
  On the published v1.1.1 copy that is a live self-XSS, not a display bug.
- `releve.html` carries `sub:">10 m"` and `sub:"<2 m"` as stratum heights —
  legitimate labels that a stale copy renders as markup.

The grep had looked for angle brackets in *constants*. It had not asked where
labels come *from*. A finder that answers a narrower question than the one you
asked will answer it confidently.

## What was decided

**1. Both pages republished.** cp-bench first, because its staleness was a
security matter and not a cosmetic one. Both stamped in `tools/published.json`.

**2. The check keeps the finding.** `tools/verify/verify_label_escaping.py`,
18 checks, canaried against eight seeded faults. It fails the moment a page
constant gains an angle-bracket label, or a page starts feeding typed text into
an option list — either change re-lights the fuse for every stale published
copy.

**3. Reachability and staleness are different properties and the check now says
so.** Its original last assertion read:

    ck("the republish priority is exactly the pages where staleness is not cosmetic",
       priority == ["cp-bench.html", "releve.html"], priority)

That sentence claims something about published copies. Everything feeding it was
source. When releve was fetched, its live artifact was **already** on FEK v1.3.0
with the escaping in place — the check had named a page whose published copy was
already correct, on evidence that could not have told either way. Reachability
is a property of the source; staleness is a property of the published copy;
nothing in the check had looked at a published copy.

The assertion now crosses the two: *every page where the injection is reachable
must be stamped current*, hashing the publish bytes against
`tools/published.json`. That is falsifiable, and both canaries — un-stamping a
page, and editing one without republishing — fail it.

## Three defects found in my own check while canarying it

Recorded because each is a general failure mode, not a typo.

**The exemption that was a name.** soil-bench maps `n.a`, which is the
texture-key answer array — safe. The first version exempted it by *name*, with a
hand-written detector alongside. A canary that made soil-bench genuinely take
typed input walked straight past that detector: it was a disjunction whose
loose arm kept it green. The exemption is now evidence — the mapped variable is
traced to its binding, and `var n=TEX[node]` roots in an ALL-CAPS constant table.
No page is named; the next page that does this is covered for free.

**The finder was the defect, again (cf. ADR-040).** That tracer searched the
whole file for `var n=` and found `var n=parseFloat(x)` inside the FEK module —
a different `n`, hundreds of lines away, in another scope — and concluded
soil-bench was runtime data. It now takes the **nearest preceding** binding,
which is what a reader does, and has four fixtures of its own including a
shadowing case in each direction. A tracer that resolves the wrong binding fails
*open*: it calls typed input a constant.

**A check named for something it did not measure.** I added
`"the in-memory publish path reproduces publish.py's own output byte for byte"`,
comparing against `build/publish/cp-bench.html`. It did not measure that. It
measured whether the build directory was fresh, and it fired on a canary that
only edited a page. Since the suite imports publish.py's own `strip()` and
`wire()`, there is no reimplementation that could drift — the real risk is
importing something else. It now checks the provenance of those functions
(caught by pointing the import at a stub) and that the transform is not a no-op.

That is the same error as the one in point 3 above, made two checks apart, in
the same file, while fixing the first one. The lesson is not "be careful": it is
that **the sentence in a check is a claim, and it has to be tested against what
the code actually reads.**

**And the suite must not mutate the tree it tests.** The first version shelled
out to `publish.py`, which writes into `build/publish/` — a test with a side
effect on the artifact directory, the same mistake `tools/mutate.py` made and
had to be rebuilt to avoid. It now computes the bytes in memory.

## What is still open, honestly

- **~24 published pages remain unknown or behind.** They are not reachable for
  this injection, so they are cosmetic drift, but "cosmetic" is a claim about
  the escaping defect only. `publish_state.py` names them and the gate cost is
  real: four Read calls per page.
- Page-level mutation scores remain 10–20% on the four pages sampled; 39 pages
  are unswept at page level.
- `audit_escaping` cannot exercise `ordination.html` — covered by `verify_ord`
  instead, tracked, not closed.

## The rule this adds

> A check that names a set of pages is asserting a property of those pages.
> Name the property the evidence actually supports. "Where the flaw can fire"
> and "where the published copy is wrong" are two different sets, and the
> second one requires looking at the published copy.
