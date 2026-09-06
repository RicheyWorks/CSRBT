# -*- coding: utf-8 -*-
"""Files that are on disk and in no commit (ADR-147).

Every audit in this kit measures the WORKING TREE. That is the right thing to
measure and it has one blind spot, which is total: a file that was written,
shipped to the operator's disk and never named by a push script is present in
every measurement the kit takes and absent from the repository. Every suite is
green about it. Every audit reads it. And it exists nowhere but one machine.

It has happened: ADR-143 and ADR-144 shipped four files -- the three state
audits printing the NAME of a never-exposed control in their summaries, and
verify_organism printing the lines that differ when two consecutive physicals
disagree -- and neither slice's push script named them in its `git add`. They
sat modified and uncommitted for three days, through six full green runs.

This measures it. There is no git here (the agent's copy is a mount, not a
clone), so the evidence is CONTENT: `tools/deliver.py --record` writes the
sha256 of every path a slice delivers into `tools/delivery_ledger.json`, and
anything on disk whose bytes are not in that ledger has not been delivered.

    UNDELIVERED = tracked files whose sha is not the delivered one
                  - the paths the manifests of unshipped slices claim

The subtraction is what makes it usable DURING a slice: work in flight is
declared by the slice's own manifest, which is the same list the push script and
the tarball come from. Name it in the manifest or the audit names it here --
which is the whole mechanism, stated as one sentence.

    python3 tools/audit_delivery.py                 # the table and the worklist
    python3 tools/audit_delivery.py --check         # symmetry; it fails either way
    python3 tools/audit_delivery.py --ignore PATH --reason "..."

WHAT THIS IS NOT

It is not proof that a delivered file was PUSHED -- that happens on a machine
this process cannot see, and the ledger records what was handed over, not what
git did with it. It is the other half of the ratchet: a file nothing has ever
handed over cannot have been pushed, and that is the failure this exists for.
"""
import argparse, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import deliver as D

# What a slice can deliver. The Java tree, the gradle wrapper and the build
# outputs are not the harness's to ship, and evidence directories are written by
# the suites themselves on every run -- a screenshot that changes whenever a
# suite runs is not an undelivered change, it is the suite running.
TRACKED_DIRS = ("tools", "docs")
SKIP_DIRS = ("__pycache__", "push")
SKIP_SUFFIX = (".pyc", ".png", ".webm", ".jsonl", ".gz")
SKIP_CONTAINS = ("_evidence/", "/traces/")


def tracked():
    out = []
    for base in TRACKED_DIRS:
        for dirpath, dirnames, files in os.walk(os.path.join(ROOT, base)):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in sorted(files):
                rel = os.path.relpath(os.path.join(dirpath, f), ROOT).replace(os.sep, "/")
                if rel.endswith(SKIP_SUFFIX) or any(c in rel for c in SKIP_CONTAINS):
                    continue
                out.append(rel)
    return sorted(out)


def claimed():
    """Every path some manifest names: work a slice has DECLARED it is shipping."""
    out = {}
    for mid in D.manifests():
        for p in D.load_manifest(mid).get("paths") or []:
            out.setdefault(p, mid)
    return out


def measure():
    led = D.load_ledger().get("paths", {})
    cl = claimed()
    state = D.load_ledger()
    ignored = state.get("ignored") or {}
    rows = {"delivered": [], "claimed": [], "undelivered": [], "ignored": [], "gone": []}
    for rel in tracked():
        if rel in ignored:
            rows["ignored"].append(rel)
            continue
        e = led.get(rel)
        same = bool(e) and e.get("sha") == D.sha(os.path.join(ROOT, rel))
        if same:
            rows["delivered"].append(rel)
        elif rel in cl:
            rows["claimed"].append(rel)
        else:
            rows["undelivered"].append(rel)
    have = set(tracked())
    rows["gone"] = sorted(p for p in led if p not in have and p not in ignored)
    return rows


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="accepted for symmetry with the kit's other ratchets; an undelivered "
                         "file fails with or without it")
    ap.add_argument("--ignore", metavar="PATH", help="declare one path outside delivery (needs --reason)")
    ap.add_argument("--reason", default="", help="why a path is outside delivery")
    ap.add_argument("--names", type=int, default=12, help="how many undelivered paths to name")
    a = ap.parse_args(argv)

    if a.ignore:
        if not a.reason.strip():
            print("ignoring a path needs --reason: it goes into the ledger, and a list of files\n"
                  "this audit is choosing not to care about is only useful if each line says why")
            return 2
        state = D.load_ledger()
        state.setdefault("ignored", {})[a.ignore] = a.reason.strip()
        D.save_ledger(state)
        print("%s: outside delivery" % a.ignore)
        return 0

    r = measure()
    n = sum(len(r[k]) for k in ("delivered", "claimed", "ignored", "undelivered"))
    print("delivery reach  --  %d tracked file(s)" % n)
    print("-" * 78)
    print("  %5d delivered      their bytes are in the ledger" % len(r["delivered"]))
    print("  %5d in flight      a manifest claims them; the push script will stage them"
          % len(r["claimed"]))
    print("  %5d ignored        outside delivery, with a reason" % len(r["ignored"]))
    print("  %5d UNDELIVERED    on disk, claimed by nothing, in no commit" % len(r["undelivered"]))
    if r["gone"]:
        print("  %5d gone           delivered once and no longer on disk" % len(r["gone"]))
    print("-" * 78)
    for p in r["undelivered"][:a.names]:
        print("    %s" % p)
    if len(r["undelivered"]) > a.names:
        print("    ...and %d more" % (len(r["undelivered"]) - a.names))
    if r["undelivered"]:
        print("\nA file that no slice has handed over cannot have been pushed. Name it in the\n"
              "current slice's manifest (tools/delivery/<id>.json) -- the same list the push\n"
              "script and the tarball are generated from -- or say why it is outside delivery.")
    # The last line is what run_all shows in this audit's row, and it is
    # DELIBERATELY NOT in the "N / M" shape run_all scores: written that way the
    # kit's headline "checks passing" grew by 621 in one commit, because 621
    # files were counted as 621 checks. A row that reads is worth having; a
    # score that is not a score is not.
    accounted = len(r["delivered"]) + len(r["claimed"])
    print("%d delivered or claimed, %d undelivered" % (accounted, len(r["undelivered"])))
    return 1 if r["undelivered"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
