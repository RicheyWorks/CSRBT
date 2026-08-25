# -*- coding: utf-8 -*-
"""What is actually published, versus what is in the repo.

Thirty-seven pages of this kit are published as Artifacts, and those URLs are
the ones people are given. Nothing recorded which version of a page each URL was
serving, so after any slice the honest answer to "is the published Relevé the
Relevé in this repo?" was: nobody knows. A stale artifact is not a missing
feature, it is a wrong page in front of a reader who has no way to tell.

This records a hash of the exact bytes handed to the publisher, and reports
drift against it.

    python3 tools/publish_state.py                  # report
    python3 tools/publish_state.py --stamp a.html   # record what was just published
    python3 tools/publish_state.py --check          # exit non-zero if anything is behind

A page that has never been stamped reports as **unknown**, not as current.
Unknown is the truthful state for the pages published before this file existed,
and collapsing it into "up to date" would be the single most useful lie this
tool could tell.
"""
import glob, hashlib, io, json, os, subprocess, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")
BUILD = os.path.join(ROOT, "build", "publish")
STATE = os.path.join(ROOT, "tools", "published.json")
MAP = os.path.join(ROOT, "tools", "artifact_map.json")

BLANK = {
    "_comment": "sha256 of the bytes last handed to the publisher, per page. "
                "A page absent from this map has never been stamped and its "
                "published state is UNKNOWN -- which is not the same as current.",
    "pages": {},
}


def load(path, blank):
    if not os.path.exists(path):
        return json.loads(json.dumps(blank))
    return json.load(io.open(path, encoding="utf-8"))


def save(state):
    io.open(STATE, "w", encoding="utf-8").write(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()


def build_current(names):
    """Regenerate the publish bytes so the comparison is against what WOULD be
    published now, not against a stale build directory."""
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "publish.py")] + list(names),
                   cwd=os.path.join(ROOT, "tools"), capture_output=True, text=True)


def main(argv):
    state = load(STATE, BLANK)
    mapped = load(MAP, {"pages": {}})["pages"]

    if "--stamp" in argv:
        names = [a for a in argv if a.endswith(".html")]
        if not names:
            print("--stamp needs at least one page name"); return 2
        build_current(names)
        for n in names:
            p = os.path.join(BUILD, n)
            if not os.path.exists(p):
                print("%-30s NOT BUILT -- nothing stamped" % n); return 2
            state["pages"][n] = sha(p)
            print("%-30s stamped %s" % (n, state["pages"][n][:12]))
        save(state)
        return 0

    build_current([])
    pages = sorted(os.path.basename(p) for p in glob.glob(os.path.join(DOCS, "*.html")))
    behind, unknown, current, unmapped = [], [], [], []
    for n in pages:
        if n not in mapped:
            unmapped.append(n); continue
        p = os.path.join(BUILD, n)
        if not os.path.exists(p):
            unknown.append(n); continue
        h = sha(p)
        if n not in state["pages"]:
            unknown.append(n)
        elif state["pages"][n] != h:
            behind.append(n)
        else:
            current.append(n)

    print("published state  --  %d pages mapped to an artifact" % len(mapped))
    print("-" * 68)
    for n in behind:
        print("%-30s BEHIND    the repo has moved since it was published" % n)
    for n in unknown:
        print("%-30s unknown   never stamped; published state cannot be asserted" % n)
    for n in unmapped:
        print("%-30s unmapped  no artifact URL" % n)
    print("-" * 68)
    print("%d current, %d behind, %d unknown, %d unmapped"
          % (len(current), len(behind), len(unknown), len(unmapped)))
    if behind:
        print("\nRepublish those, then:  python3 tools/publish_state.py --stamp " + " ".join(behind))
    if unknown and not behind:
        print("\nUnknown is honest, not clean: those pages were published before this")
        print("file existed and nothing recorded what they were serving.")
    return 1 if ("--check" in argv and (behind or unknown)) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
