# -*- coding: utf-8 -*-
"""Which pages the mutation sweep has covered, and which are left.

WHY THIS EXISTS

For seven slices the answer to "how far has the sweep got" was a sentence at the
bottom of an ADR -- **Swept: 19 pages. 20 to go.** -- typed by hand, carried
forward from the previous ADR, and derived from nothing. ADR-041 says a number a
tool can compute should never be pinned as a constant. This one was pinned in
prose, which is worse, because prose has no test.

It was also wrong. `greenhouse.html` was swept in ADR-063 and swept again in
ADR-064; both ADRs added it to the running total, so from ADR-064 onward every
tally was one too high. The true figure at ADR-068 was 18 pages, not 19, and 21
to go, not 20. Nobody could have noticed, because there was nothing to notice it
against.

WHAT THIS IS

`sweep_ledger.json` records one row PER RUN -- page, the ADR that reported it,
and whether the row was written by the tool or backfilled by hand from the
prose. Re-sweeps get their own row on purpose: a ledger that silently collapsed
`greenhouse` twice into `greenhouse` once would hide exactly the event that
caused the drift. The COUNTS are computed here, from the rows and from the
docs/ glob, and never stored.

That last part matters more than it looks. "39 pages" was itself hand-typed. Add
a page to the kit tomorrow and the old sentence still says 39; this says 40 the
moment the file lands, and the page shows up under "not yet swept" without
anyone remembering to add it.

    python3 tools/sweep_ledger.py            # the status block
    python3 tools/mutate.py --status         # the same block
    python3 tools/mutate.py --page X --record ADR-070    # appends a row
"""
import glob, io, json, os, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")
LEDGER = os.path.join(ROOT, "tools", "sweep_ledger.json")


def load():
    with io.open(LEDGER, encoding="utf-8") as f:
        return json.load(f)


def records():
    return load().get("records", [])


def swept_pages():
    """The DISTINCT pages with at least one recorded run. Derived, never stored."""
    return sorted({r["page"] for r in records()})


def all_pages():
    """Every page in docs/. Computed from the tree, so a new page counts itself."""
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(DOCS, "*.html")))


def remaining():
    done = set(swept_pages())
    return [p for p in all_pages() if p not in done]


def append(page, adr, killed=None, survived=None, fresh=None):
    """Record one run. Called by mutate.py --record; never edits an existing row."""
    d = load()
    row = {"page": page, "adr": adr, "source": "tool"}
    for k, v in (("killed", killed), ("survived", survived), ("fresh", fresh)):
        if v is not None:
            row[k] = v
    d["records"].append(row)
    with io.open(LEDGER, "w", encoding="utf-8") as f:
        f.write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    return row


def classify(page):
    """Why a page is not swept yet -- measured with the sweep's own machinery.

    The first cut of this returned "ready" for all twenty-one remaining pages,
    including the glossary and the essay, which was obviously wrong and worth
    keeping the reason for: EVERY page carries the shared webfont loader, the
    loader contains `if(!l) return`, and `neg-guard` mutates it. So no page has
    zero mutants and "has mutable code" separates nothing. A classifier whose
    every row reads the same is not measuring anything (ADR-039).

    What actually separates them is whether a page has mutable code OF ITS OWN.
    Nine of the twenty-one are prose whose only script is that loader -- the same
    one line, twenty-one times, and one run of it settles the lot.

    The loader's bytes come from _kit.LOADER, the same pattern the offline suite
    uses, so "this is the shared loader" cannot mean two different things in two
    files.

    Returns "own-code" | "loader-only" | "no-suite" | "prose".
    """
    import mutate as _m
    sys.path.insert(0, os.path.join(ROOT, "tools", "verify"))
    import _kit
    path = os.path.join(DOCS, page)
    src = io.open(path, encoding="utf-8").read()
    _src, muts = _m.mutants_for(path, 999)
    if not muts:
        return "prose"
    spans = [(m.start(), m.end()) for m in _kit.LOADER.finditer(src)]
    own = [mu for mu in muts
           if not any(a <= mu["at"] < b for a, b in spans)]
    if not own:
        return "loader-only"
    if _m.CROSS is None:
        _m.CROSS = _m.cross_cutting()
    suites, _skipped = _m.suites_for(page)
    return "own-code" if suites else "no-suite"


def mutants_available():
    """How many mutants the kit HAS, page by page. Computed, like everything else.

    This is the denominator the headline number has been missing. "39 of 39
    pages swept" is true and, on its own, reads as coverage -- and a page is
    swept at a SAMPLE, four to eight mutants chosen to spread across operators,
    not at all of them. Without this figure beside it the sentence claims about
    twenty times what it has earned.
    """
    import mutate as _m
    total = {}
    for name in all_pages():
        _src, muts = _m.mutants_for(os.path.join(DOCS, name))
        total[name] = len(muts)
    return total


def mutants_run():
    """Mutants actually run, from the rows that recorded a count.

    A LOWER BOUND: the rows backfilled from the ADRs carry no counts, because
    the tool was not writing them yet. Reporting it as exact would be the same
    class of mistake as the tally this ledger replaced.
    """
    n, counted = 0, 0
    for r in records():
        if "killed" in r and "survived" in r:
            n += r["killed"] + r["survived"]
            counted += 1
    return n, counted


def status_lines():
    recs, done, left, total = records(), swept_pages(), remaining(), all_pages()
    hand = sum(1 for r in recs if r.get("source") != "tool")
    out = []
    out.append("mutation sweep coverage -- counts computed, not stored")
    out.append("-" * 78)
    out.append("%d of %d page(s) swept, %d to go" % (len(done), len(total), len(left)))
    out.append("%d recorded run(s) over those %d page(s) -- %d re-sweep(s)"
               % (len(recs), len(done), len(recs) - len(done)))
    out.append("%d row(s) backfilled by hand from the ADRs, %d written by the tool"
               % (hand, len(recs) - hand))
    _avail = sum(mutants_available().values())
    _run, _counted = mutants_run()
    out.append("")
    out.append("SAMPLE, not census: a swept page was swept at four to eight mutants,")
    out.append("spread across the operators, and not at every mutant it has.")
    out.append("   at least %d mutant(s) run, from %d row(s) that recorded a count"
               % (_run, _counted))
    out.append("   %d mutant(s) exist across the %d page(s) -- so this is a %.0f%% sample"
               % (_avail, len(total), 100.0 * _run / _avail if _avail else 0))
    out.append("")
    buckets = {"own-code": [], "no-suite": [], "loader-only": [], "prose": []}
    for p in left:
        buckets[classify(p)].append(p)
    out.append("NOT YET SWEPT -- %d with code of their own, %d with no suite, "
               "%d loader-only, %d prose"
               % (len(buckets["own-code"]), len(buckets["no-suite"]),
                  len(buckets["loader-only"]), len(buckets["prose"])))
    for label, why in (("own-code", "code of its own and a suite that names it -- "
                                    "the sweep can score these"),
                       ("no-suite", "code of its own that NOTHING tests -- every mutant "
                                    "survives by default, which is not a score"),
                       ("loader-only", "its only mutable line is the shared webfont "
                                       "loader, the same line on every page"),
                       ("prose", "no script the operators can reach")):
        if not buckets[label]:
            continue
        out.append("   %s -- %s" % (label, why))
        for p in buckets[label]:
            out.append("      %s" % p)
    # A row naming a page that is gone is not a coverage claim, it is a typo.
    missing = [r["page"] for r in recs if r["page"] not in set(total)]
    if missing:
        out.append("")
        out.append("LEDGER ROWS NAMING A PAGE THAT IS NOT IN docs/:")
        for p in sorted(set(missing)):
            out.append("   %s" % p)
    return out


def main():
    print("\n".join(status_lines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
