# -*- coding: utf-8 -*-
"""Measurement, made the default: what the reader is actually being served.

`publish_state.py` records two different kinds of evidence about a published
page and refuses to let them read as one (ADR-078):

    via "publish"   these are the bytes I handed the publisher. Says nothing
                    about whether the publisher kept them.
    via "read"      the URL was serving these bytes at that moment.

The second is the one that answers "does a green audit of docs/ describe what a
reader gets?", and it was the EXCEPTION: 22 of 41 pages carried the weaker
stamp, because measuring a page meant a human remembering to fetch it and hand
the copy to `--verify` one page at a time. A stronger form of evidence that
costs more to obtain is a form of evidence you do not have.

This file makes the measurement mechanical.

    python3 tools/publish_reach.py                    # the reach: who is measured, who is not
    python3 tools/publish_reach.py --plan             # the work list, one artifact per line
    python3 tools/publish_reach.py --sweep DIR        # verify every saved copy in DIR
    python3 tools/publish_reach.py --check            # exit non-zero unless every artifact is MEASURED

WHY THIS DOES NOT FETCH

An artifact lives behind claude.ai and is read through the host's own Artifact
tool, not over plain HTTP from this container. A script here cannot fetch one,
and a script that pretended to -- by scraping a mirror, or by trusting a cached
copy it did not date -- would be manufacturing exactly the evidence this file
exists to insist on. So the boundary is stated rather than hidden: `--plan`
emits precisely which artifacts to read and where each copy must land, the
operator (or an agent with the Artifact tool) does the reading, and `--sweep`
attributes and verifies whatever comes back, page by page, through
`publish_state.py`'s existing rules -- the same containment test, the same
dating from the version marker in the bytes, the same refusal to let a copy of
one page be recorded as evidence about another.

THE BOARD IS AN ARTIFACT TOO

ADR-127 published the Harness Board and then held that it is republished by
hand -- so the one page in this kit that reports on everything else was the one
page nothing reported on. It is mapped here like any other, under the build
name `_harness-board.html`, and `publish.py` writes it into `build/publish`
beside the docs pages. It is measured or it is a hole, the same as the rest.
"""
import argparse, glob, io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import publish_state as PS

COPY_OF = re.compile(r"artifact-([0-9a-f]{6,})-")


def artifacts():
    """Every artifact this kit publishes: build name -> (artifact id, build path).

    The map's `pages` are the kit's own pages, built into build/publish by
    publish.py. Anything under `others` is an artifact that is not a docs page
    -- the Harness Board -- and publish.py builds those into the same place
    under the name the map gives them, so everything downstream (classify,
    --stamp, --verify) needs to know nothing about the difference."""
    m = PS.load(PS.MAP, {"pages": {}})
    out = {}
    for name, aid in sorted(m.get("pages", {}).items()):
        out[name] = (aid, os.path.join(PS.BUILD, name))
    for name, spec in sorted((m.get("others") or {}).items()):
        out[name] = (spec["artifact"], os.path.join(PS.BUILD, name))
    return out


def base_url():
    return PS.load(PS.MAP, {"pages": {}}).get("_base", "https://claude.ai/code/artifact/")


def reach(state=None):
    """Per artifact: ("measured"|"stamped"|"behind"|"unknown"|"not-built", entry).

    MEASURED is the only state that is evidence about a URL. `stamped` means the
    repo's bytes were handed to a publisher and nobody has looked since; it is
    the honest name for what 22 of these were, and it is not a pass."""
    state = state if state is not None else PS.load(PS.STATE, PS.BLANK)
    out = {}
    for name, (_aid, bp) in artifacts().items():
        if not os.path.exists(bp):
            out[name] = ("not-built", None)
            continue
        kind, entry = PS.classify(name, PS.sha(bp), state)
        if kind == "current":
            out[name] = ("measured" if PS.entry_via(entry) == "read" else "stamped"), entry
        elif kind in ("behind", "measured-behind"):
            out[name] = ("behind", entry)
        else:
            out[name] = ("unknown", None)
    return out


def plan(state=None):
    """The artifacts still owed a measurement, in the order they should be read."""
    r = reach(state)
    art = artifacts()
    return [(n, art[n][0], art[n][1]) for n in sorted(r)
            if r[n][0] != "measured"]


def attribute(copy_path, art=None):
    """Which page is this saved copy a copy of? -> name, or None.

    By the artifact id in the filename, which is what the Artifact tool writes
    and the only attributor that does not need the page's own bytes.
    `publish_state.copy_is_of` still gets the last word at verify time -- this
    only decides which page to OFFER it to, and offering it to the wrong one
    would be refused there rather than believed here."""
    art = art if art is not None else artifacts()
    m = COPY_OF.search(os.path.basename(copy_path))
    if not m:
        return None
    got = m.group(1)
    hits = [n for n, (aid, _bp) in art.items() if aid.startswith(got)]
    return hits[0] if len(hits) == 1 else None


def pick(copies, art=None):
    """Choose one copy per page: the NEWEST. -> ({name: (path, at)}, [orphans])

    "Newest" is the version the copy CARRIES, not its mtime -- the same rule
    publish_state dates by, and for the same reason: mtime moves forward when
    anything rewrites the local file, so across 103 saved copies every mtime was
    later than the version it held. Sweeping a directory that has both an old
    and a new copy of a page and taking the older would record, with the
    strongest provenance this kit has, that a URL is serving what it served
    two publishes ago."""
    art = art if art is not None else artifacts()
    done, orphans = {}, []
    for c in copies:
        name = attribute(c, art)
        if name is None:
            orphans.append(c)
            continue
        at, _how = PS.copy_taken_at(c, io.open(c, encoding="utf-8", errors="replace").read())
        if name not in done or (at or 0) > done[name][1]:
            done[name] = (c, at or 0)
    return done, orphans


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true",
                    help="print the artifacts still owed a measurement, one per line")
    ap.add_argument("--sweep", metavar="DIR",
                    help="verify every saved artifact copy in DIR against the page it names")
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero unless every mapped artifact is MEASURED")
    a = ap.parse_args(argv)
    art = artifacts()
    PS.build_current([])

    if a.sweep:
        copies = sorted(glob.glob(os.path.join(a.sweep, "*.html")))
        if not copies:
            print("no saved copies in %s" % a.sweep)
            return 2
        done, orphans = pick(copies, art)
        for c in orphans:
            print("%-30s UNATTRIBUTED  %s" % ("", os.path.basename(c)))
        rc = 0
        for name in sorted(done):
            code = PS.main(["--verify", name, done[name][0]])
            rc = rc or (0 if code == 0 else code)
        left = [n for n, _a, _b in plan()]
        print("-" * 68)
        print("%d copy/copies swept; %d artifact(s) still unmeasured" % (len(done), len(left)))
        return rc

    r = reach()
    if a.plan:
        b = base_url()
        rows = plan()
        for name, aid, bp in rows:
            print("%s\t%s%s\t%s" % (name, b, aid, os.path.relpath(bp, ROOT)))
        if not rows:
            print("# nothing owed: every mapped artifact is measured")
        return 0

    order = {"behind": 0, "unknown": 1, "not-built": 2, "stamped": 3, "measured": 4}
    print("publish reach  --  %d mapped artifact(s)" % len(art))
    print("-" * 68)
    for name in sorted(r, key=lambda n: (order[r[n][0]], n)):
        kind, entry = r[name]
        note = {"measured": "the URL was serving this build when it was read",
                "stamped": "these bytes were handed to a publisher; nobody has looked since",
                "behind": "the repo has moved since this URL was last known",
                "unknown": "never stamped; published state cannot be asserted",
                "not-built": "no build output -- run tools/publish.py"}[kind]
        print("%-30s %-9s %s" % (name, kind.upper(), note))
    print("-" * 68)
    counts = {}
    for kind, _e in r.values():
        counts[kind] = counts.get(kind, 0) + 1
    print(", ".join("%d %s" % (counts[k], k) for k in sorted(counts, key=lambda k: order[k])))
    unmeasured = [n for n, _a, _b in plan()]
    if unmeasured:
        print("\n%d artifact(s) are NOT measured. For those, every audit and suite in this"
              % len(unmeasured))
        print("kit is green about the REPO, and says nothing about what a reader is served.")
        print("Read each and sweep the copies:")
        print("    python3 tools/publish_reach.py --plan")
        print("    python3 tools/publish_reach.py --sweep <dir of saved copies>")
    return 1 if (a.check and unmeasured) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
