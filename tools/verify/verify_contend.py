# -*- coding: utf-8 -*-
"""What a suite says when the machine is busy -- the instrument, checked (ADR-143).

`tools/contend.py` runs a suite N times while other named suites of this kit
run beside it, and records the flake rate with its conditions. It exists
because three of the six full runs it took to close ADR-141 failed on checks
that passed every time they were run alone, and "flake, re-roll" is a
measurement nobody took.

An instrument for measuring flakiness that is itself wrong is worse than no
instrument: it produces a number, and a number gets believed. So every part of
it is put to fixtures here -- scripts that pass, scripts that fail, scripts that
crash, a co-tenant that exits and must be restarted -- and the ledger's merge
rules are asserted the way every other ledger in this kit is.

Run:  python3 tools/verify/verify_contend.py
"""
MUTATE_ROLE = "subject"
import io, json, os, subprocess, sys, tempfile, time

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import contend as C

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


TMP = tempfile.mkdtemp(prefix="contend_")
VERIFY = os.path.join(TMP, "verify")
os.makedirs(VERIFY)


def script(name, body, where=None):
    p = os.path.join(where or VERIFY, name + ".py")
    io.open(p, "w", encoding="utf-8", newline="\n").write(body)
    return p


# The fixtures: one of each thing a suite can do at the end of its run.
script("fx_pass", "print('12/12')\n")
script("fx_fail", "print('FAIL: the thing was not the thing')\nprint('11/12')\nraise SystemExit(1)\n")
script("fx_crash", "raise RuntimeError('the suite fell over')\n")
script("fx_passfail", "print('3 passed, 1 failed')\nraise SystemExit(1)\n")
script("fx_slow", "import time\ntime.sleep(1.2)\nprint('2/2')\n")
script("fx_tool", "print('7/7')\n", where=TMP)
script("fx_tenant", "import time\ntime.sleep(0.3)\n")     # exits, and must be restarted

C.HERE, C.VERIFY, C.ROOT = TMP, VERIFY, TMP
C.LEDGER = os.path.join(TMP, "contention_ledger.json")

# ---- A. finding the thing to run ---------------------------------------------
ck(C.script_for("fx_pass") == os.path.join(VERIFY, "fx_pass.py"), "a suite is found in verify/")
ck(C.script_for("fx_tool") == os.path.join(TMP, "fx_tool.py"),
   "a TOOL is found beside it: an audit is not in verify/ and is exactly the thing this file "
   "was written to measure")
ck(C.script_for("no_such_thing") is None, "and a name that is neither is None, not a guess")

# ---- B. what one run says ----------------------------------------------------
idle = C.Load([], 0)
r = C.one_run(C.script_for("fx_pass"), idle)
ck(r["got"] == 12 and r["of"] == 12 and not r["failed"] and r["rc"] == 0 and not r["checks"],
   "a passing suite: its score, its exit code, and nothing failed: %s" % r)
r = C.one_run(C.script_for("fx_fail"), idle)
ck(r["failed"] and r["got"] == 11 and r["checks"] == ["the thing was not the thing"],
   "a failing suite: the score it printed AND the text of the check that failed, which is the "
   "whole point -- 'it failed' is not a finding, 'it failed HERE' is: %s" % r)
ck(r["lines"] and any("FAIL" in l for l in r["lines"]) and len(r["lines"]) <= 40,
   "...and the run's own words around it are kept, bounded: a failure that takes twenty minutes "
   "to reproduce must not be reproduced twice because nobody kept the output: %s" % r["lines"][:3])
ok_run = C.one_run(C.script_for("fx_pass"), idle)
ck(ok_run["lines"] == [],
   "a passing run keeps none: a ledger that stored every green run's output would be a log, and "
   "nobody reads a log")
r = C.one_run(C.script_for("fx_crash"), idle)
ck(r["failed"] and r["rc"] != 0 and not r["checks"],
   "a suite that crashed is FAILED even with no FAIL line: a run that could not finish is not a "
   "pass, and this file must never turn one into one: %s" % {k: r[k] for k in ("failed", "rc")})
r = C.one_run(C.script_for("fx_passfail"), idle)
ck(r["got"] == 3 and r["of"] == 4 and r["failed"],
   "the other score format the kit uses ('N passed, M failed') is read too -- run_all's own "
   "parser, imported rather than written twice: %s" % r)
r = C.one_run(C.script_for("fx_slow"), idle)
ck(r["seconds"] >= 1.0, "and a run is timed: %.2fs" % r["seconds"])

# ---- C. the load -------------------------------------------------------------
load = C.Load(["fx_tenant", "no_such_thing"], 1)
ck(load.beside == ["fx_tenant"],
   "a co-tenant that is not a script of this kit is dropped rather than silently 'started': %s"
   % load.beside)
load.start()
try:
    ck(len(load.procs) == 2, "one co-tenant and one burner are running: %d" % len(load.procs))
    first = [p.pid for n, p in load.procs if n]
    time.sleep(0.9)                       # fx_tenant exits after 0.3s
    load.keep()
    again = [p.pid for n, p in load.procs if n]
    ck(again != first and all(p.poll() is None for n, p in load.procs if n),
       "a co-tenant that finished is RESTARTED: the load is meant to last as long as the target "
       "runs, and the kit's suites are 4 seconds to 3 minutes long: %s -> %s" % (first, again))
    pids = [p.pid for _n, p in load.procs]
finally:
    load.stop()
time.sleep(0.4)
alive = []
for pid in pids:
    try:
        os.kill(pid, 0)
        alive.append(pid)
    except OSError:
        pass
ck(not alive and not load.procs,
   "and stop() leaves nothing behind -- a burner that outlives the measurement poisons every "
   "measurement after it: %s" % alive)

# ---- D. the ledger -----------------------------------------------------------
rows_ok = [{"failed": False, "checks": [], "seconds": 2.0}]
rows_bad = [{"failed": True, "checks": ["a check that did not hold"], "seconds": 5.0},
            {"failed": False, "checks": [], "seconds": 3.0}]
e = C.record("fx_pass", ["fx_tenant"], 0, rows_ok)
ck(e["runs"] == 1 and e["failed"] == 0 and e["beside"] == ["fx_tenant"], "a first reading: %s" % e)
e = C.record("fx_pass", ["fx_tenant"], 0, rows_bad)
ck(e["runs"] == 3 and e["failed"] == 1 and e["checks"] == {"a check that did not hold": 1},
   "two runs of this file on two days are two samples of the same question, so the counts ADD, "
   "and the checks that failed are counted by name: %s" % e)
ck(e["fastest"] == 2.0 and e["slowest"] == 5.0, "with the range of what it cost: %s" % e)
e2 = C.record("fx_pass", ["fx_tenant", "fx_slow"], 0, rows_ok)
ck(e2["runs"] == 1 and e2["failed"] == 0 and e2["beside"] == ["fx_slow", "fx_tenant"],
   "...but a reading taken beside a DIFFERENT co-tenant is a different QUESTION and lands under "
   "its own key: conditions are part of the reading (ADR-078), not a footnote to it: %s" % e2)
led = json.load(io.open(C.LEDGER, encoding="utf-8"))["suites"]
ck(led[C.key_for("fx_pass", ["fx_tenant"])]["runs"] == 3,
   "and the first reading is still there, whole -- a second load must not cost a real "
   "measurement: %s" % {k: v["runs"] for k, v in led.items()})
e3 = C.record("fx_pass", ["fx_tenant", "fx_slow"], 2, rows_ok)
ck(e3["runs"] == 1 and e3["cpu"] == 2 and len(json.load(io.open(C.LEDGER, encoding="utf-8"))["suites"]) == 3,
   "and so is the number of burners: three keys now, one per condition: %s" % e3)
ck(C.key_for("verify_organism", ["a", "b"], 2) == "verify_organism beside a, b +2cpu"
   and C.key_for("x", []) == "x beside nothing",
   "the key READS as what it is, because a ledger nobody can read is a ledger nobody checks: %r"
   % C.key_for("verify_organism", ["a", "b"], 2))
led = json.load(io.open(C.LEDGER, encoding="utf-8"))
ck("_comment" in led and "suites" in led and C.key_for("fx_pass", ["fx_tenant"]) in led["suites"],
   "the ledger says what it is, the way every ledger here does")
e_one = led["suites"][C.key_for("fx_pass", ["fx_tenant"])]
ck(e_one.get("at") and e_one.get("since") and e_one.get("target") == "fx_pass",
   "and carries when the reading started, when it was last added to, and the suite it is about")

# ---- E. measuring, and what the exit code means ------------------------------
rows = C.measure("fx_pass", ["fx_tenant"], 2, 0, echo=False)
ck(len(rows) == 2 and not any(r["failed"] for r in rows), "measure runs the target N times: %s"
   % [(r["got"], r["of"]) for r in rows])
rc = C.main(["--suite", "fx_pass", "--beside", "fx_tenant", "--runs", "1", "--no-ledger"])
ck(rc == 0, "a target that passed exits 0")
rc = C.main(["--suite", "fx_fail", "--beside", "fx_tenant", "--runs", "1", "--no-ledger"])
ck(rc == 1, "a target that FAILED under load exits non-zero: the kit's own runs are under load, "
   "so a failure there is a failure")
ck(C.main(["--list"]) == 0 and C.main(["--report"]) == 0, "--list and --report run without a target")
before = io.open(C.LEDGER, encoding="utf-8").read()
C.main(["--suite", "fx_fail", "--beside", "fx_tenant", "--runs", "1", "--no-ledger"])
ck(io.open(C.LEDGER, encoding="utf-8").read() == before,
   "--no-ledger writes nothing: a run taken to try something out must not become evidence")
rc = C.main(["--suite", "fx_fail", "--beside", "fx_tenant", "--runs", "1"])
led = json.load(io.open(C.LEDGER, encoding="utf-8"))["suites"][C.key_for("fx_fail", ["fx_tenant"])]
ck(led["failed"] == 1 and led["checks"] == {"the thing was not the thing": 1},
   "and a run that is kept records WHICH check failed, not just that one did: %s" % led)
ck(led.get("lastFailure", {}).get("lines") and led["lastFailure"]["checks"],
   "...with the most recent failing run's output beside it: %s" % (led.get("lastFailure") or {}))
C.main(["--suite", "fx_pass", "--beside", "fx_tenant", "--runs", "1"])
after = json.load(io.open(C.LEDGER, encoding="utf-8"))["suites"][C.key_for("fx_fail", ["fx_tenant"])]
ck(after.get("lastFailure", {}).get("lines"),
   "and a later PASSING run of another suite does not erase it: the last failure is the thing "
   "you came back for")

# ---- F. the standing set is real ---------------------------------------------
import contend as C2
sys.path.insert(0, os.path.join(_kit.ROOT, "tools"))
real_verify = os.path.join(_kit.ROOT, "tools", "verify")
missing = []
for target, beside, runs in C.STANDING:
    for name in [target] + list(beside):
        if not (os.path.isfile(os.path.join(real_verify, name + ".py"))
                or os.path.isfile(os.path.join(_kit.ROOT, "tools", name + ".py"))):
            missing.append(name)
ck(not missing, "every suite the standing set names exists in this kit: %s" % missing)
ck(all(runs >= 2 for _t, _b, runs in C.STANDING),
   "and every entry asks for more than one run: one run is not a rate")
ck(any(t == "verify_organism" for t, _b, _r in C.STANDING)
   and any(t == "audit_targets" for t, _b, _r in C.STANDING),
   "the two that actually flaked in ADR-141's closing runs are in it: %s"
   % [t for t, _b, _r in C.STANDING])
ck(len(set(C.key_for(t, b, 0) for t, b, _r in C.STANDING)) == len(C.STANDING),
   "and no two entries of the standing set share a key -- two loads for one suite are two "
   "readings, and a sweep that overwrote one with the other would be measuring nothing twice")

import shutil
shutil.rmtree(TMP, ignore_errors=True)
print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
