# -*- coding: utf-8 -*-
"""What a suite says when the machine is busy (ADR-142).

Every number in this kit -- 5,794 checks, 309 mutants, 42 measured artifacts --
was produced by a suite that was, at the moment it answered, the only thing
this container was seriously doing. That is not the condition the kit actually
runs in. `run_all -j 2` puts two jobs on two cores, one of them usually driving
a browser and one of them sometimes a JVM, and it took SIX full runs to close
ADR-141 because three of them failed on a check that passed every time it was
run alone:

    verify_organism   "two consecutive physicals are identical through the
                       gateway"           -- failed in 2 of 6 full runs
    audit_targets     one control "never measured"
                                          -- failed in 1 of 6 full runs

Both were called flakes and re-rolled. A flake that is re-rolled is a
measurement nobody took: it might be a race in the instrument, a race in the
subject, or a claim that is simply false when the machine is busy -- and those
are three different bugs with the same symptom. ADR-134 already stated the
principle for the walk's settle time: an instrument whose answer depends on
what else is running is not an instrument. This file measures that dependence
instead of asserting it away.

    python3 tools/contend.py --suite verify_organism --runs 12
    python3 tools/contend.py --suite audit_targets --beside verify_tasks --runs 6
    python3 tools/contend.py --sweep                 # the standing set
    python3 tools/contend.py --list                  # what the standing set is
    python3 tools/contend.py --report                # the ledger, no runs

WHAT THE LOAD IS, AND WHY IT IS NAMED

The load is other REAL suites of this kit, restarted for as long as the target
runs, plus optional busy-loop processes. Not synthetic sleep, not a fixed CPU
percentage: the condition being reproduced is `run_all -j 2`, whose co-tenant
is always another suite of this kit, and the closest thing to that condition is
that suite. The ledger records which co-tenants ran and how many burners, for
the ADR-078 reason: a measurement without its conditions is not a measurement,
it is a number with a story attached.

WHAT A GREEN RUN HERE DOES NOT MEAN

Zero failures in N runs is not proof of stability; it is an upper bound on how
often the thing fails, and a loose one at small N. This file is a FINDER in the
sense mutate.py is: it produces evidence for triage, and its ledger says how
many runs the evidence rests on so that "0 of 4" is never read as "never".
It exits non-zero when a run actually failed, because a failure under load is a
failure -- the kit's own runs are under load.
"""
import argparse, io, json, os, re, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
VERIFY = os.path.join(HERE, "verify")
LEDGER = os.path.join(HERE, "contention_ledger.json")

sys.path.insert(0, VERIFY)
try:
    from run_all import score, FAIL_LINE            # one definition of "what a suite said"
except Exception:                                   # pragma: no cover - a copied tree without verify/
    FAIL_LINE = re.compile(r"^[ \t]*FAIL\b", re.M)

    def score(out):
        for line in reversed(out.strip().split("\n")):
            m = re.search(r"(\d+)\s*/\s*(\d+)\s*$", line.strip())
            if m:
                return int(m.group(1)), int(m.group(2))
        return None, None

# The standing set: what to run under load, and what to run it beside. The
# co-tenants are the kit's LONG jobs, because a co-tenant that finishes in two
# seconds is not a co-tenant. Each entry is (target, [beside], runs).
STANDING = [
    # verify_organism twice, under two different loads on purpose: it failed in
    # two of ADR-141's six closing runs and in none of eight runs beside a
    # browser suite, so the co-tenant that matters may be the one that also
    # starts a JVM. A reading under each condition is kept separately -- they
    # are two answers to two questions, not two samples of one.
    ("verify_organism", ["verify_tie_render"], 6),
    ("verify_organism", ["verify_tasks"], 6),
    ("audit_targets", ["verify_tasks"], 3),
    # ADR-143's own closing run produced a THIRD instance of the same family --
    # audit_contrast, one control never exposed, clean standing alone -- so it
    # is in the standing set rather than in a sentence.
    ("audit_contrast", ["verify_tasks"], 3),
    ("verify_contract", ["verify_tie_render"], 4),
    ("verify_report", ["verify_tie_render"], 4),
]

FAIL_TEXT = re.compile(r"^[ \t]*FAIL[: ]\s*(.+?)\s*$", re.M)


def key_for(target, beside, cpu=0):
    """The ledger key: the target AND what it ran under.

    Conditions are part of a reading, not a footnote to it (ADR-078), and the
    first version of this file keyed by target alone and RESET the count when
    the conditions changed -- which threw away a real measurement every time
    the sweep tried a second load. Two loads are two questions; both answers
    are kept, and both say what they were taken under."""
    cond = " beside " + (", ".join(sorted(beside)) if beside else "nothing")
    return target + cond + (" +%dcpu" % int(cpu) if int(cpu) else "")


def script_for(name):
    """A target names a suite in tools/verify/ or a tool in tools/."""
    for cand in (os.path.join(VERIFY, name + ".py"), os.path.join(HERE, name + ".py")):
        if os.path.isfile(cand):
            return cand
    return None


class Load(object):
    """Other suites, kept running for as long as the target does.

    A co-tenant that exits is restarted: the point is a busy machine for the
    whole of the target's run, and the kit's suites are between 4 seconds and
    3 minutes long. Output is discarded -- the co-tenant's own result is not
    being measured here, and reading it would be a second thing to get wrong.
    """

    def __init__(self, beside=(), cpu=0):
        self.beside = [b for b in beside if script_for(b)]
        self.cpu = int(cpu)
        self.procs = []

    def _spawn(self, name):
        return subprocess.Popen([sys.executable, script_for(name)], cwd=ROOT,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)

    def start(self):
        for b in self.beside:
            self.procs.append((b, self._spawn(b)))
        for _ in range(self.cpu):
            self.procs.append((None, subprocess.Popen(
                [sys.executable, "-c", "\nwhile True:\n    pass\n"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True)))
        return self

    def keep(self):
        """Restart whatever has finished. Called while the target runs."""
        for i, (name, p) in enumerate(list(self.procs)):
            if name is not None and p.poll() is not None:
                self.procs[i] = (name, self._spawn(name))

    def stop(self):
        for _name, p in self.procs:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        for _name, p in self.procs:
            try:
                p.wait(timeout=20)
            except Exception:
                pass
        self.procs = []

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()
        return False


def one_run(path, load, timeout=1800):
    """Run the target once while the load is kept alive. -> dict."""
    t0 = time.time()
    p = subprocess.Popen([sys.executable, path], cwd=ROOT, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    out = []
    while True:
        if p.poll() is not None:
            break
        load.keep()
        time.sleep(0.5)
        if time.time() - t0 > timeout:
            p.kill()
            break
    out = p.stdout.read() or ""
    rc = p.returncode
    got, tot = score(out)
    fails = FAIL_TEXT.findall(out)
    lines = [l.rstrip() for l in out.strip().split("\n") if l.strip()]
    failed = bool(fails) or rc != 0
    return {"rc": rc, "got": got, "of": tot, "seconds": round(time.time() - t0, 1),
            "failed": failed,
            "checks": [f[:120] for f in fails[:8]], "tail": lines[-1][:120] if lines else "",
            # WHAT THE RUN SAID AROUND THE FAILURE. A rare failure that is only
            # reproduced once every twenty minutes must not be reproduced twice
            # because the first time nobody kept the output. verify_organism
            # prints the two physicals' differing lines when they differ
            # (ADR-142) -- and the first version of this file threw them away
            # and recorded "1 of 6 failed", which is a rate, not a finding.
            "lines": lines[-40:] if failed else []}


def measure(target, beside, runs, cpu=0, echo=True):
    path = script_for(target)
    if path is None:
        raise SystemExit("no such suite or tool: %s" % target)
    rows = []
    with Load(beside, cpu) as load:
        time.sleep(2)                       # let the co-tenants get going
        for i in range(runs):
            r = one_run(path, load)
            rows.append(r)
            if echo:
                print("  run %-2d %-8s %-12s %5.1fs  %s"
                      % (i + 1, "FAILED" if r["failed"] else "ok",
                         ("%s/%s" % (r["got"], r["of"])) if r["got"] is not None else "-",
                         r["seconds"], (r["checks"][0] if r["checks"] else "")[:60]))
    return rows


def load_ledger():
    if os.path.isfile(LEDGER):
        try:
            return json.load(io.open(LEDGER, encoding="utf-8"))
        except ValueError:
            pass
    return {"_comment": "Written by tools/contend.py. Each entry is what a suite did while "
                        "OTHER named suites of this kit were running beside it -- the condition "
                        "run_all -j 2 actually creates. runs is how much evidence there is; "
                        "0 failed in a small number of runs is an upper bound, not a proof "
                        "(ADR-142).",
            "suites": {}}


def record(target, beside, cpu, rows):
    """MERGE, never replace, under a key that names the conditions.

    Two runs of this file on two days are two samples of the same question, so
    the counts add. A run beside a different co-tenant is a DIFFERENT question,
    so it lands under a different key and both answers survive -- the first
    version of this file reset the count instead, which threw a real
    measurement away every time the sweep tried a second load.
    """
    led = load_ledger()
    suites = led.setdefault("suites", {})
    k = key_for(target, beside, cpu)
    e = suites.get(k)
    if not e:
        e = {"runs": 0, "failed": 0, "checks": {}, "beside": sorted(beside), "cpu": int(cpu),
             "target": target, "since": int(time.time())}
    e["runs"] += len(rows)
    e["failed"] += sum(1 for r in rows if r["failed"])
    for r in rows:
        for c in r["checks"]:
            e["checks"][c] = e["checks"].get(c, 0) + 1
    worst = [r for r in rows if r["failed"]]
    if worst:
        # the most recent failing run's own words, kept whole
        e["lastFailure"] = {"at": int(time.time()), "checks": worst[-1].get("checks") or [],
                            "lines": worst[-1].get("lines") or []}
    secs = [r["seconds"] for r in rows]
    if secs:
        e["slowest"] = max(e.get("slowest", 0), max(secs))
        e["fastest"] = min(e.get("fastest", 10 ** 9), min(secs))
    e["at"] = int(time.time())
    suites[k] = e
    io.open(LEDGER, "w", encoding="utf-8").write(
        json.dumps(led, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return e


def report():
    led = load_ledger()
    suites = led.get("suites") or {}
    if not suites:
        print("nothing measured under load yet: python3 tools/contend.py --sweep")
        return 0
    print("under load  --  what each suite says when the machine is busy")
    print("-" * 74)
    bad = 0
    for name in sorted(suites):
        e = suites[name]
        bad += e["failed"] > 0
        print("%-46s %2d run(s), %d failed" % (name[:46], e["runs"], e["failed"]))
        for c in sorted(e.get("checks") or {}, key=lambda k: -e["checks"][k]):
            print("        x%-3d %s" % (e["checks"][c], c[:70]))
        lf = e.get("lastFailure") or {}
        for l in (lf.get("lines") or [])[-6:]:
            print("             | %s" % l[:88])
    print("-" * 74)
    print("%d of %d reading(s) have failed at least once under load, over %d distinct suite(s). "
          "A reading\nwith 0 failures in a handful of runs is bounded, not proven: read the run "
          "count beside it."
          % (bad, len(suites), len(set(e.get("target", k) for k, e in suites.items()))))
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", help="the suite or tool to run under load")
    ap.add_argument("--beside", action="append", default=[],
                    help="a suite to keep running beside it (repeatable)")
    ap.add_argument("--runs", type=int, default=6)
    ap.add_argument("--cpu", type=int, default=0, help="busy-loop processes to add")
    ap.add_argument("--sweep", action="store_true", help="run the standing set")
    ap.add_argument("--list", action="store_true", help="print the standing set")
    ap.add_argument("--report", action="store_true", help="print the ledger and stop")
    ap.add_argument("--no-ledger", action="store_true")
    a = ap.parse_args(argv)

    if a.list:
        for t, b, n in STANDING:
            print("  %-22s %2d run(s) beside %s" % (t, n, ", ".join(b)))
        return 0
    if a.report:
        return report()

    plan = [(t, b, n) for t, b, n in STANDING] if a.sweep else None
    if plan is None:
        if not a.suite:
            print("name a suite (--suite) or run the standing set (--sweep)")
            return 2
        plan = [(a.suite, a.beside or ["verify_tie_render"], a.runs)]

    rc = 0
    for target, beside, runs in plan:
        print("%s  --  %d run(s) beside %s%s"
              % (target, runs, ", ".join(beside) or "nothing",
                 (" + %d burner(s)" % a.cpu) if a.cpu else ""))
        rows = measure(target, beside, runs, a.cpu)
        n_bad = sum(1 for r in rows if r["failed"])
        if not a.no_ledger:
            e = record(target, beside, a.cpu, rows)
            print("  %d of %d failed this time; %d of %d recorded under %r\n"
                  % (n_bad, len(rows), e["failed"], e["runs"], key_for(target, beside, a.cpu)))
        else:
            print("  %d of %d failed this time\n" % (n_bad, len(rows)))
        rc = rc or (1 if n_bad else 0)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
