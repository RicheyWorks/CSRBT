# -*- coding: utf-8 -*-
"""What the kit's evidence is ABOUT, and what it may not fall below (ADR-241).

Ported from the FlowersForever harness's `verify_harness.py`, which binds a
passing verification to a SHA-256 over every build input and refuses, on
`--check`, evidence taken on any other tree; and which holds every test class
to a committed floor so a growing class cannot hide a deleted one.

This kit's `counts.json` bound each suite's count to the SHA of the SUITE
SOURCE (ADR-052). That says the count is about this suite. It says nothing
about what the suite was pointed at: edit a page, a task, a tool, and every
count that measured them still reads green, still renders green on the board,
and the board is published with a number about a tree that no longer exists.
The ADR-238 close found it the hard way -- verify_board read 218/219 until the
board was re-rendered, and the fix was to hand-edit a counts entry. A count
that can be hand-edited into green is a count nothing binds.

Two measurements, both cheap:

  THE TREE    a digest over the subject files -- pages, prose, tools, tasks,
              suites, CI -- and NOT over the evidence those produce (ledgers,
              counts, the rendered board, the published-state file, delivery
              manifests, push scripts). run_all records the tree it measured;
              the board's verdict has a gate "the counts are about this tree",
              which names the files that have changed since.
  THE FLOOR   a committed count per suite (tools/verify/floors.json). A run
              whose green suite counts fewer checks than its floor is red for
              that suite, and says so. Floors rise only by `--raise-floors`;
              a suite never seen before is floored at what it counted.

    python3 tools/evidence.py                # the tree now, and whether counts.json is about it
    python3 tools/evidence.py --check        # exit 1 when it is not, naming the files
    python3 tools/evidence.py --raise-floors # today's counts become the floors where higher
"""
import argparse, glob, hashlib, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COUNTS = os.path.join(HERE, "verify", "counts.json")
FLOORS = os.path.join(HERE, "verify", "floors.json")

# The subject: what the suites and audits READ. Text, by extension, under the
# kit's own directories.
SUBJECT_GLOBS = ("docs/**/*.html", "docs/**/*.md", "docs/**/*.js", "docs/**/*.json", "docs/**/*.css",
                 "tools/**/*.py", "tools/**/*.js", "tools/**/*.json", "tools/**/*.html", "tools/**/*.md",
                 ".github/**/*.yml", ".github/**/*.yaml",
                 "*.gradle", "*.gradle.kts", "*/*.gradle.kts", "*/src/**/*.java", "gradle/**/*.toml")
# The evidence: what a run WRITES. A digest over its own outputs would change
# with every run and bind nothing.
EVIDENCE_PARTS = ("_ledger.json", os.sep + "counts.json", os.sep + "floors.json", os.sep + "published.json",
                  os.sep + "harness_board.html", os.sep + "delivery" + os.sep, os.sep + "push" + os.sep,
                  os.sep + "routes.json")
SKIP_PARTS = ("__pycache__", os.sep + "build" + os.sep, os.sep + ".git" + os.sep, "node_modules",
              "_evidence", os.sep + ".gradle" + os.sep)


def is_evidence(rel):
    r = os.sep + rel.replace("/", os.sep)
    return any(p in r for p in EVIDENCE_PARTS)


def subject_files(root=ROOT):
    """Sorted repo-relative paths of everything the evidence is about."""
    out = set()
    for pat in SUBJECT_GLOBS:
        for p in glob.glob(os.path.join(root, pat), recursive=True):
            if os.path.isdir(p) or any(s in p for s in SKIP_PARTS):
                continue
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            if is_evidence(rel):
                continue
            out.add(rel)
    return sorted(out)


def digest(root=ROOT):
    """{"digest": hex64, "files": {rel: sha12}} -- the tree as it stands."""
    files = {}
    h = hashlib.sha256()
    for rel in subject_files(root):
        try:
            b = io.open(os.path.join(root, rel), "rb").read()
        except OSError:
            continue
        s = hashlib.sha256(b).hexdigest()
        files[rel] = s[:12]
        h.update(rel.encode("utf-8") + b"\0" + s.encode("ascii") + b"\0")
    return {"digest": h.hexdigest(), "files": files}


def compare(recorded, current):
    """What differs between a recorded tree and the current one: changed, added, removed."""
    rf = (recorded or {}).get("files") or {}
    cf = (current or {}).get("files") or {}
    return {"changed": sorted(k for k in rf if k in cf and rf[k] != cf[k]),
            "added": sorted(k for k in cf if k not in rf),
            "removed": sorted(k for k in rf if k not in cf)}


def short(d):
    return (d or "")[:12]


def load_counts(path=COUNTS):
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {"suites": {}}


def load_floors(path=FLOORS):
    try:
        f = json.load(io.open(path, encoding="utf-8"))
        return dict((k, v) for k, v in (f.get("floors") or {}).items()
                    if isinstance(v, int) and not isinstance(v, bool) and v >= 1)
    except (OSError, ValueError):
        return {}


def save_floors(floors, path=FLOORS):
    io.open(path, "w", encoding="utf-8").write(json.dumps(
        {"_comment": "Written by tools/evidence.py (ADR-241). The fewest checks each suite may count "
                     "and still be green. Raised only by --raise-floors; a suite never seen before is "
                     "floored at what it first counted. A suite that shrinks below its floor is red "
                     "for that run, whatever it printed.",
         "floors": dict(sorted(floors.items()))}, indent=1, sort_keys=True) + "\n")


def apply_floors(rec, floors):
    """Hold this run's scored entries to the floors. Mutates `rec`: a green entry
    that counted fewer than its floor goes red and says so; a suite with no
    floor yet gets one at what it counted. Returns (below, new_floors)."""
    below, new = [], dict(floors)
    for name, e in rec.items():
        n = e.get("n")
        if n is None:
            continue
        f = new.get(name)
        if f is None:
            new[name] = n
            continue
        # a red suite is red for its own reason; the floor is about a suite that
        # PASSES with fewer checks than it used to have
        if n < f and e.get("green"):
            below.append((name, n, f))
            e["green"] = False
            e["below_floor"] = f
    return below, new


def raise_floors(rec, floors):
    new = dict(floors)
    for name, e in rec.items():
        n = e.get("n")
        if n is not None and e.get("green") and n >= new.get(name, 0):
            new[name] = n
    return new


def status(counts=None, root=ROOT):
    """The tree the counts were measured on, the tree now, and the difference."""
    counts = counts if counts is not None else load_counts()
    now = digest(root)
    rec = counts.get("tree") or {}
    entries = counts.get("suites") or {}
    stamped = dict((k, v.get("tree")) for k, v in entries.items() if v.get("tree"))
    unstamped = sorted(k for k in entries if not entries[k].get("tree"))
    off = sorted(k for k, t in stamped.items() if t != short(now["digest"]))
    diff = compare(rec, now) if rec else {"changed": [], "added": [], "removed": []}
    return {"now": short(now["digest"]), "recorded": short(rec.get("digest")),
            "files": len(now["files"]), "same": bool(rec) and rec.get("digest") == now["digest"],
            "diff": diff, "off": off, "unstamped": unstamped,
            "moved": counts.get("tree_moved") or []}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 unless counts.json is about this tree")
    ap.add_argument("--raise-floors", action="store_true", help="today's green counts become the floors where higher")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.raise_floors:
        c = load_counts()
        f = raise_floors(c.get("suites") or {}, load_floors())
        save_floors(f)
        print("floors: %d suite(s) recorded in %s" % (len(f), os.path.relpath(FLOORS, ROOT)))
        return 0
    s = status()
    if a.json:
        print(json.dumps(s, indent=1, sort_keys=True))
        return 0 if s["same"] and not s["off"] else 1
    print("tree now       %s  (%d subject files)" % (s["now"], s["files"]))
    print("counts.json    %s" % (s["recorded"] or "no tree recorded -- rerun run_all"))
    d = s["diff"]
    for k in ("changed", "added", "removed"):
        for f in d[k]:
            print("  %-8s %s" % (k, f))
    if s["moved"]:
        print("  the tree MOVED during the run: %s" % ", ".join(s["moved"][:6]))
    if s["off"]:
        print("  %d suite count(s) are about another tree: %s" % (len(s["off"]), ", ".join(s["off"][:6])))
    if s["unstamped"]:
        print("  %d suite count(s) carry no tree at all: %s" % (len(s["unstamped"]), ", ".join(s["unstamped"][:6])))
    ok = s["same"] and not s["off"] and not s["moved"]
    print("counts.json is %s this tree" % ("ABOUT" if ok else "NOT ABOUT"))
    return 0 if ok or not a.check else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
