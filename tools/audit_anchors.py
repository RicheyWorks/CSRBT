# -*- coding: utf-8 -*-
"""Whether the mutant ledger is still about the code (ADR-235).

A mutant runner breaks its subject by replacing one exact string -- the
ANCHOR -- and records what its suite said to `tools/mutant_ledger.json`. The
board reads that ledger and counts the kills. Nothing re-reads the anchors
between runs, so a kill stays on the board after its anchor has stopped
matching anything. ADR-234 found two of `mutate_brief`'s fourteen anchors in
that state, one of them for nine slices (ADR-196 split it with a comment). The
ledger still said 14 of 14 killed, and it was true of the code that existed
when the runner last ran.

Two measurements, both static. No runner is run, so this costs a second:

  STALE    a mutant whose anchor is found nowhere in the code it could break --
           the kit's tools, pages, tasks, CI definition, and the sibling engine
           the organism and lab consoles live in -- leaving out the runners
           themselves, since every anchor is written in its own runner. A
           stale mutant cannot apply. The next run reads it as BAD MUTANT, and
           until then it counts as killed.
  DRIFTED  a runner whose catalogue (the mutant names) is not the one its
           ledger entry recorded. A mutant added, removed or renamed since the
           last run means the ledger's count is about a different catalogue.

"Found nowhere" is the honest bound of a static check: an anchor that lands in
the wrong file, or twice, is the runner's own business at run time (it refuses
a mutant whose anchor does not match exactly once). What this catches is the
anchor that CANNOT land, and the ledger that is about another list.

    python3 tools/audit_anchors.py           # the table; exit 1 on any stale or drifted
    python3 tools/audit_anchors.py --json
"""
import argparse, glob, importlib.util, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# What a runner can break, by where it lives. Text only; the runners are left
# out below, because every anchor is written in its own runner and would find
# itself there.
CORPUS_GLOBS = ("tools/**/*.py", "tools/**/*.js", "tools/**/*.json", "tools/**/*.html",
                "docs/**/*.html", "docs/**/*.js", ".github/**/*.yml", ".github/**/*.yaml",
                "*.gradle", "*.gradle.kts", "*/*.gradle.kts", "*/src/**/*.java")
SKIP_PARTS = ("__pycache__", os.sep + "build" + os.sep, os.sep + ".git" + os.sep,
              "node_modules", "_evidence")
FILE_EXT = (".py", ".html", ".json", ".java", ".yml", ".yaml", ".js")


def engine_dir(root):
    """The sibling engine the organism and lab consoles are compiled from --
    found the way the organism plugin finds it."""
    return os.environ.get("CSRBT_WHOLEHOG") or os.path.join(root, "..", "WholeHog")


def engine_present(root=ROOT):
    return os.path.isdir(engine_dir(root))


def is_runner(path):
    b = os.path.basename(path)
    return b.startswith("mutate_") and b.endswith(".py")


def corpus(root):
    """{path: text} of everything a runner could break, runners excluded."""
    out = {}
    for pat in CORPUS_GLOBS:
        for p in glob.glob(os.path.join(root, pat), recursive=True):
            if os.path.isdir(p) or is_runner(p) or any(s in p for s in SKIP_PARTS):
                continue
            try:
                out[p] = io.open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                pass
    eng = engine_dir(root)
    if os.path.isdir(eng):
        for p in glob.glob(os.path.join(eng, "**", "*.java"), recursive=True):
            if any(s in p for s in SKIP_PARTS):
                continue
            try:
                out[p] = io.open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                pass
    return out


def shape(m):
    """(name, anchor) of one catalogue entry, or None when the entry has no shape
    this audit knows -- which is reported, never guessed past.

    The kit's runners use three shapes, all tuples of strings:
      (name, find, repl, expect)                        -- most runners
      (target, name, find, repl, expect)                -- a one-word target first
                                                           (mutate_lab, mutate_organism)
      (name, file, find, repl, expect)                  -- the file second
                                                           (mutate_audit_states)
      (name, find, repl, expect, where)                 -- a where last
                                                           (mutate_ci, mutate_outbox, mutate_keep)
    """
    if not isinstance(m, (tuple, list)) or not all(isinstance(x, str) for x in m):
        return None
    if len(m) == 4:
        return m[0], m[1]
    if len(m) == 5:
        if " " not in m[0].strip() and " " in m[1].strip():
            return m[1], m[2]
        if m[1].endswith(FILE_EXT) and " " not in m[1]:
            return m[0], m[2]
        return m[0], m[1]
    return None


def load_runner(path):
    name = "_anchors_" + os.path.basename(path)[:-3]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    d = os.path.dirname(path)
    added = d not in sys.path
    if added:
        sys.path.insert(0, d)
    try:
        spec.loader.exec_module(mod)
    finally:
        if added:
            sys.path.remove(d)
    return mod


def audit(root=ROOT, ledger=None):
    """One row per runner: read, mutants, anchors, stale, drifted."""
    if ledger is None:
        lp = os.path.join(root, "tools", "mutant_ledger.json")
        ledger = json.load(io.open(lp, encoding="utf-8")) if os.path.isfile(lp) else {"runners": {}}
    runs = ledger.get("runners") or {}
    texts = list(corpus(root).values())
    rows = []
    for path in sorted(glob.glob(os.path.join(root, "tools", "mutate_*.py"))):
        rid = os.path.basename(path)[:-3]
        row = {"runner": rid, "read": False, "why": "", "mutants": 0, "anchors": 0,
               "stale": [], "unshaped": 0, "drifted": [], "recorded": rid in runs}
        try:
            mod = load_runner(path)
        except Exception as e:
            row["why"] = "does not import: %s: %s" % (type(e).__name__, str(e)[:80])
            rows.append(row)
            continue
        cat = getattr(mod, "MUTANTS", None)
        if not isinstance(cat, (list, tuple)) or not cat:
            row["why"] = "has no MUTANTS catalogue"
            rows.append(row)
            continue
        row["read"] = True
        row["mutants"] = len(cat)
        names = []
        for m in cat:
            s = shape(m)
            if s is None:
                row["unshaped"] += 1
                continue
            name, anchor = s
            names.append(name)
            row["anchors"] += 1
            if not anchor or not any(anchor in t for t in texts):
                row["stale"].append(name)
        if row["unshaped"]:
            row["why"] = "%d catalogue entr%s of a shape this audit does not know" % (
                row["unshaped"], "y" if row["unshaped"] == 1 else "ies")
        e = runs.get(rid)
        if e is not None:
            was = sorted(r.get("name") for r in (e.get("rows") or []))
            if was != sorted(names) or e.get("mutants") != len(cat):
                row["drifted"] = sorted(set(was) ^ set(names)) or ["%d recorded, %d now"
                                                                  % (e.get("mutants"), len(cat))]
        rows.append(row)
    return rows


def problems(rows):
    return [r for r in rows if not r["read"] or r["unshaped"] or r["stale"] or r["drifted"]]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rows = audit()
    if a.json:
        print(json.dumps(rows, indent=1))
        return 1 if problems(rows) else 0
    print("%-22s %8s %8s %6s %8s  %s" % ("RUNNER", "MUTANTS", "ANCHORS", "STALE", "DRIFTED", ""))
    print("-" * 78)
    for r in rows:
        note = r["why"] or ("; ".join(r["stale"][:2]) if r["stale"] else
                            ("catalogue changed since its last run: " + "; ".join(r["drifted"][:2])
                             if r["drifted"] else ("" if r["recorded"] else "never recorded")))
        print("%-22s %8d %8d %6d %8s  %s" % (r["runner"], r["mutants"], r["anchors"], len(r["stale"]),
                                            "yes" if r["drifted"] else "-", note[:60]))
    print("-" * 78)
    bad = problems(rows)
    print("%d runner(s), %d mutant(s), %d stale, %d runner(s) drifted, %d unread"
          % (len(rows), sum(r["mutants"] for r in rows), sum(len(r["stale"]) for r in rows),
             sum(1 for r in rows if r["drifted"]), sum(1 for r in rows if not r["read"])))
    if bad:
        print("A stale mutant cannot apply, and still counts as killed until its runner runs again. "
              "A drifted runner's ledger is about another catalogue. Fix the anchor, or run the runner.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
