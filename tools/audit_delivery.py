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

A CLAIM EXPIRES WHEN ITS SLICE SHIPS (ADR-218)

"In flight" used to mean "some manifest names it" -- ANY manifest, forever.
Seventy-one manifests later that was 221 files, every hot file in the kit among
them, and a change to any of them was excused by a slice that had been pushed
weeks before. ADR-207 changed tools/keep_emit.py and did not name it; ADR-206's
manifest did, so this audit called the change "in flight" for ten slices while
origin/main failed verify_keep and every run here was green. A claim is a
statement about work that has NOT been committed yet, so only an UNSHIPPED
manifest may make one.

And where there is git, git is asked. The paragraph above was true of a mount
with no git in it; a clone has one, and `git status` is exact where a ledger of
hashes is a memory. With git: committed means the bytes are HEAD's, shipped
means the manifest is in HEAD's tree. Without it: the ledger, as before, and a
manifest is shipped once `deliver.py --record` has said so.

WHAT THIS IS NOT

It is not proof that a delivered file was PUSHED -- that happens on a machine
this process cannot see, and the ledger records what was handed over, not what
git did with it. It is the other half of the ratchet: a file nothing has ever
handed over cannot have been pushed, and that is the failure this exists for.
"""
import argparse, io, json, os, subprocess, sys, time

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


def git_view(root=None):
    """What git says about this tree, or None when there is no git to ask.

    -> {"dirty": set of paths whose bytes are not HEAD's (modified, staged,
                 untracked), under the tracked directories,
        "shipped": set of manifest ids whose manifest is in HEAD's tree}

    None means NO EVIDENCE, never "clean": no git binary, not a repository, no
    commit yet, or a git that failed. The caller falls back to the ledger."""
    root = root or ROOT
    try:
        st = subprocess.run(["git", "-C", root, "status", "--porcelain", "-z",
                             "--untracked-files=all", "--"] + list(TRACKED_DIRS),
                            capture_output=True, timeout=120)
        ls = subprocess.run(["git", "-C", root, "ls-tree", "-r", "--name-only", "-z", "HEAD",
                             "--", "tools/delivery"], capture_output=True, timeout=120)
    except Exception:
        return None
    if st.returncode != 0 or ls.returncode != 0:
        return None
    dirty = set()
    parts = st.stdout.decode("utf-8", "replace").split("\0")
    i = 0
    while i < len(parts):
        e = parts[i]
        i += 1
        if len(e) < 4:
            continue
        dirty.add(e[3:])
        if e[0] in "RC":            # a rename or a copy: the next field is where it came from
            if i < len(parts) and parts[i]:
                dirty.add(parts[i])
            i += 1
    shipped = set()
    for n in ls.stdout.decode("utf-8", "replace").split("\0"):
        if n.startswith("tools/delivery/") and n.endswith(".json"):
            shipped.add(os.path.basename(n)[:-5])
    return {"dirty": dirty, "shipped": shipped}


def shipped(view=None):
    """The manifests whose slice is OVER. With git: the manifest is in HEAD's
    tree, which is the same fact the push script's own guard reads (ADR-184).
    Without: `deliver.py --record` said so, by name. Not inferred from which
    slice a path was last delivered `by` -- an adoption writes that too, and an
    adoption is a baseline, not a slice that shipped."""
    if view is not None:
        return set(view["shipped"])
    return set(D.load_ledger().get("recorded") or [])


def claimed(view=None):
    """Every path an UNSHIPPED manifest names: work a slice has DECLARED it is
    shipping and has not shipped yet. A manifest whose slice is over claims
    nothing -- a later change to one of its paths is somebody else's work, and
    if nobody names it, it is exactly the file this audit exists to find."""
    done = shipped(view)
    out = {}
    for mid in D.manifests():
        if mid in done:
            continue
        for p in D.load_manifest(mid).get("paths") or []:
            out.setdefault(p, mid)
    return out


def measure(view="ask"):
    if view == "ask":
        view = git_view()
    led = D.load_ledger().get("paths", {})
    cl = claimed(view)
    state = D.load_ledger()
    ignored = state.get("ignored") or {}
    rows = {"delivered": [], "claimed": [], "undelivered": [], "ignored": [], "gone": [],
            "evidence": "git" if view is not None else "ledger"}
    for rel in tracked():
        if rel in ignored:
            rows["ignored"].append(rel)
            continue
        if view is not None:
            # GIT IS ASKED. The bytes are HEAD's or they are not; what a ledger
            # remembers about them is beside the point where the repository
            # itself can be read.
            same = rel not in view["dirty"]
        else:
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
    rows["unshipped"] = sorted(set(cl.values()))
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
    print("delivery reach  --  %d tracked file(s), evidence: %s" % (n, r["evidence"]))
    print("-" * 78)
    print("  %5d delivered      %s" % (len(r["delivered"]),
                                       "their bytes are HEAD's" if r["evidence"] == "git"
                                       else "their bytes are in the ledger"))
    print("  %5d in flight      an UNSHIPPED manifest claims them (%s); its push script will "
          "stage them" % (len(r["claimed"]), ", ".join(r["unshipped"]) or "none"))
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
