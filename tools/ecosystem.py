# -*- coding: utf-8 -*-
"""The ecosystem's own suites, in one ledger, ratcheted (ADR-118).

WHY

The harness verifies that everything works -- through the gateway, from the
manifest, over two transports. Underneath it, fourteen engines each carry a
JUnit suite that is the engine's own claim about itself: SmokeHouse 75,
csrbt-core 877, WholeHog 21, and so on. Those numbers lived in ADRs, in the
Atlas, and in memory -- typed by hand, carried forward, never computed. The
kit's rule since ADR-041 is that a number a tool can compute is never pinned
as a constant, and since ADR-108 that a coverage claim has a ledger with a
consumer. The engines' suites had neither.

WHAT THIS IS

    python3 tools/ecosystem.py --read           # read every engine's test results
    python3 tools/ecosystem.py --run            # run every engine's suite, then read
    python3 tools/ecosystem.py --run SmokeHouse Twine
    python3 tools/ecosystem.py --lower Rub 4 --reason "..."   # lower a floor, on the record

ENGINES names every repo of the organism, as a sibling of this one (the way
the composite builds find them), with its test modules. --read walks each
module's build/test-results/test/*.xml -- the JUnit XML Gradle writes -- and
records tests, failures, errors, skipped, and when. --run executes
`./gradlew test` in each repo first (SuperBeefSort's native module needs a
JDK 22 and a Rust toolchain; the main suite runs on 17+ and the module is
skipped by its own build file, which the ledger records as its reason).

THE RATCHET

Each engine carries a FLOOR: the smallest test count the ledger will accept.
--read raises a floor to the count it read (a suite only grows), and never
lowers one; lowering is --lower, with a reason, written into the ledger. A
count below the floor is a failure in verify_ecosystem: a suite that lost
tests without anybody saying why is the CONTROL_FLOOR defect (ADR-108) one
layer down.

MERGE, DO NOT REPLACE

--read updates only the engines it could read and keeps the rest, each with
its own `at`; a machine that has not built Carver does not delete Carver's
reading (ADR-104's counts ledger, ADR-108's harness ledger). An engine with
no results on this machine is NOT VERIFIED in the suite, never green.
"""
import argparse, glob, io, json, os, re, subprocess, sys, time
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SIBLINGS = os.path.normpath(os.path.join(ROOT, ".."))
LEDGER = os.path.join(HERE, "ecosystem_ledger.json")

# (engine, repo dir, [module dirs holding build/test-results], note)
ENGINES = [
    ("csrbt-core",         "CSRBT",        ["csrbt-core"],          "the adaptive index (engine 1)"),
    ("csrbt-experimental", "CSRBT",        ["csrbt-experimental"],  "arena, ecology, cache-evo; the lab console"),
    ("SuperBeefSort",      "SuperBeefSort", ["."],                  "sort engine; native kernels need JDK 22 + Rust and are skipped by its build on older JVMs"),
    ("SmokeHouse",         "SmokeHouse",   ["."],                   "the store"),
    ("Carver",             "Carver",       ["."],                   "cost-based read planner"),
    ("Renderer",           "Renderer",     ["."],                   "materialized views"),
    ("Brine",              "Brine",        ["."],                   "evolving cache"),
    ("PitBoss",            "PitBoss",      ["."],                   "replication fleet"),
    ("DryAge",             "DryAge",       ["."],                   "the vault"),
    ("Twine",              "Twine",        ["."],                   "crash-atomic batches"),
    ("SmokeSignal",        "SmokeSignal",  ["."],                   "the wire"),
    ("Jerky",              "Jerky",        ["."],                   "cold archives"),
    ("Rub",                "Rub",          ["."],                   "observability"),
    ("Sizzle",             "Sizzle",       ["."],                   "chaos"),
    ("WholeHog",           "WholeHog",     ["."],                   "the organism; the harness console"),
]


def repo_dir(repo):
    return os.path.join(SIBLINGS, repo)


INCLUDE = re.compile(r'includeBuild\("\.\./([A-Za-z0-9_-]+)"\)')


def composite_closure(start="WholeHog"):
    """The repos the organism's composite build reaches: WholeHog's
    settings.gradle.kts includes every engine, and each engine includes what
    it depends on, down to CSRBT. Derived from the build files, not typed --
    so the ledger is held to the ecosystem the builds define, and a sibling
    repo that is merely a neighbour on disk (a game, a scratch project) is
    not mistaken for an engine. The first run of verify_ecosystem on the
    author's machine did exactly that with BlackJackPro."""
    seen, todo = [], [start]
    while todo:
        r = todo.pop()
        if r in seen:
            continue
        seen.append(r)
        f = os.path.join(repo_dir(r), "settings.gradle.kts")
        if os.path.isfile(f):
            for inc in INCLUDE.findall(io.open(f, encoding="utf-8").read()):
                if inc not in seen:
                    todo.append(inc)
    return sorted(seen)


def newest_source(repo, module):
    """The newest mtime under the module's src/, or 0. Results older than
    the sources they claim to test are stale evidence, not a shrunken suite."""
    newest = 0
    base = os.path.normpath(os.path.join(repo_dir(repo), module, "src"))
    for dp, dn, fn in os.walk(base):
        for f in fn:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(dp, f)))
            except OSError:
                pass
    return newest


def results_dir(repo, module):
    return os.path.normpath(os.path.join(repo_dir(repo), module, "build", "test-results", "test"))


def read_results(repo, module):
    """(tests, failures, errors, skipped, newest mtime) from the JUnit XML, or None."""
    d = results_dir(repo, module)
    files = glob.glob(os.path.join(d, "TEST-*.xml"))
    if not files:
        return None
    t = f = e = s = 0
    newest = 0
    suites = {}
    for x in files:
        try:
            root = ET.parse(x).getroot()
        except ET.ParseError:
            continue
        t += int(root.get("tests", 0)); f += int(root.get("failures", 0))
        e += int(root.get("errors", 0)); s += int(root.get("skipped", 0))
        # ADR-139: PER TEST CLASS, not only per engine. A total that has not
        # fallen is not a suite that has not shrunk -- a class deleted and
        # another grown by the same count leaves the total flat, and the
        # engine-level ratchet cannot see it. The class name is what the
        # JUnit XML calls the testsuite.
        nm = root.get("name") or os.path.basename(x)[len("TEST-"):-len(".xml")]
        suites[nm] = suites.get(nm, 0) + int(root.get("tests", 0))
        newest = max(newest, os.path.getmtime(x))
    return {"tests": t, "failures": f, "errors": e, "skipped": s, "classes": len(files),
            "suites": suites, "results_at": int(newest)}


def load_ledger(path=LEDGER):
    if os.path.isfile(path):
        try:
            return json.load(io.open(path, encoding="utf-8"))
        except ValueError:
            pass
    return {"_comment": "Written by tools/ecosystem.py. One entry per engine; a read updates only "
                        "the engines it could read and keeps the rest, each with its own at. floor "
                        "only rises on a read; lowering it is --lower with a reason, on the record.",
            "engines": {}}


def save_ledger(led, path=LEDGER):
    io.open(path, "w", encoding="utf-8").write(json.dumps(led, indent=1, sort_keys=True) + "\n")


def gradlew(repo):
    d = repo_dir(repo)
    w = os.path.join(d, "gradlew.bat" if os.name == "nt" else "gradlew")
    return [w] if os.path.isfile(w) else ["gradle"]


def run_suite(repo, timeout=1800):
    d = repo_dir(repo)
    if not os.path.isdir(d):
        return None, "no repo at %s" % d
    t0 = time.time()
    try:
        p = subprocess.run(gradlew(repo) + ["--no-daemon", "-q", "test"], cwd=d,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timed out after %ds" % timeout
    tail = "\n".join(l for l in (p.stdout + p.stderr).split("\n")
                     if l.strip() and "JAVA_TOOL_OPTIONS" not in l)[-400:]
    return p.returncode, "%.0fs rc=%d %s" % (time.time() - t0, p.returncode, tail.strip()[-200:])


def read_all(led, only=None):
    """Read every engine's results into the ledger. Returns (read, missing)."""
    read, missing = [], []
    for name, repo, modules, note in ENGINES:
        if only and name not in only and repo not in only:
            continue
        agg = None
        for m in modules:
            r = read_results(repo, m)
            if r is None:
                continue
            if agg is None:
                agg = dict(r)
            else:
                for k in ("tests", "failures", "errors", "skipped", "classes"):
                    agg[k] += r[k]
                merged = dict(agg["suites"])
                for k, v in r["suites"].items():
                    merged[k] = merged.get(k, 0) + v
                agg["suites"] = merged
                agg["results_at"] = max(agg["results_at"], r["results_at"])
        e = led["engines"].setdefault(name, {"floor": 0, "repo": repo, "note": note})
        e["repo"], e["note"] = repo, note
        if agg is None:
            missing.append(name)
            continue
        e.update(agg)
        e["at"] = int(time.time())
        e["green"] = agg["failures"] == 0 and agg["errors"] == 0
        if agg["tests"] > e.get("floor", 0):
            e["floor"] = agg["tests"]
        # the class ratchet: each class's floor rises to what was read, and a
        # class that has ever been seen stays on the record until it is
        # --forget-ten with a reason. Nothing here ever lowers or removes one.
        cf = e.setdefault("classFloor", {})
        forgotten = set(f["class"] for f in e.get("forgotten", []))
        for nm, n in agg["suites"].items():
            if nm in forgotten:
                continue
            if n > cf.get(nm, 0):
                cf[nm] = n
        read.append(name)
    return read, missing


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--read", action="store_true", help="read every engine's test results")
    ap.add_argument("--run", nargs="*", metavar="ENGINE", help="run the suites (all, or the named engines) then read")
    ap.add_argument("--lower", nargs=2, metavar=("ENGINE", "FLOOR"), help="lower an engine's floor, with --reason")
    ap.add_argument("--forget", nargs=2, metavar=("ENGINE", "CLASS"),
                    help="a test class was deliberately removed: take it off the class ratchet, with --reason")
    ap.add_argument("--reason", default="")
    ap.add_argument("--ledger", default=LEDGER)
    a = ap.parse_args(argv)
    led = load_ledger(a.ledger)

    if a.lower:
        name, floor = a.lower[0], int(a.lower[1])
        if not a.reason.strip():
            print("lowering a floor needs --reason: it goes into the ledger")
            return 2
        e = led["engines"].setdefault(name, {"floor": 0})
        e.setdefault("lowered", []).append({"from": e.get("floor", 0), "to": floor,
                                            "reason": a.reason.strip(), "at": int(time.time())})
        e["floor"] = floor
        save_ledger(led, a.ledger)
        print("%s floor -> %d (%s)" % (name, floor, a.reason.strip()))
        return 0

    if a.forget:
        # A CLASS THAT WENT AWAY ON PURPOSE IS STILL A FACT ABOUT THE SUITE.
        # Deleting its floor silently would make the ratchet a thing you can
        # step over; recording that it was deliberately removed, by whom-said
        # reason and when, keeps the shrink on the record and lets the check
        # pass. Same shape as --lower, one level down.
        name, cls = a.forget
        if not a.reason.strip():
            print("forgetting a test class needs --reason: it goes into the ledger")
            return 2
        e = led["engines"].setdefault(name, {"floor": 0})
        had = (e.get("classFloor") or {}).pop(cls, None)
        e.setdefault("forgotten", []).append({"class": cls, "had": had,
                                              "reason": a.reason.strip(), "at": int(time.time())})
        save_ledger(led, a.ledger)
        print("%s: %s forgotten (was %s) -- %s" % (name, cls, had, a.reason.strip()))
        return 0

    if a.run is not None:
        only = set(a.run) or None
        for name, repo, modules, note in ENGINES:
            if only and name not in only and repo not in only:
                continue
            if repo == "CSRBT" and name != "csrbt-core":
                continue                                  # one gradlew run covers both modules
            rc, why = run_suite(repo)
            print("%-20s %s" % (repo, why))
    if a.read or a.run is not None:
        read, missing = read_all(led, set(a.run) if a.run else None)
        led["at"] = int(time.time())
        save_ledger(led, a.ledger)
        print("")
        print("%-20s %6s %6s %7s %5s  %s" % ("engine", "tests", "floor", "green", "skip", "read"))
        for name, repo, modules, note in ENGINES:
            e = led["engines"].get(name, {})
            if "tests" in e:
                print("%-20s %6d %6d %7s %5d  %s" % (name, e["tests"], e["floor"], e["green"], e["skipped"],
                                                    time.strftime("%Y-%m-%d %H:%M", time.localtime(e["at"]))))
            else:
                print("%-20s %6s %6d %7s %5s  %s" % (name, "-", e.get("floor", 0), "-", "-", "no results here"))
        total = sum(e.get("tests", 0) for e in led["engines"].values())
        print("\n%d engines read, %d without results here%s; %d tests on the record"
              % (len(read), len(missing), (": " + ", ".join(missing)) if missing else "", total))
        print("wrote %s" % a.ledger)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
