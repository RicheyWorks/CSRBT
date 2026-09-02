# -*- coding: utf-8 -*-
"""Mutation testing for the robot itself (ADR-119; the MCP wire, ADR-121).

WHY

tools/harness_walk.py is the instrument behind every "operable from the
manifest" claim since ADR-114, and its suite had only ever watched it walk
targets that mostly succeed. A walker that filed every refusal as driven, or
never raised when the target went away, would have passed those walks. Same
rule as every suite in the kit: break the walker on purpose and require the
suite to notice. Each mutant names the check that must kill it.

The suite runs in CSRBT_WALK_QUICK mode -- the generator checks, the
committed ledger, the scoped-pool checks and the csrbt-fixture walk; no
engine, no browser -- so a mutant takes well under a second. The fixture
(harness_plugin_fixture.py) is what makes that enough: every one of its
actions lands in a known bucket, every time, so a misfiled bucket is a
wrong count and not a coin toss.

SAFETY

Mutants run against a copy of tools/ in a temp dir; the ledger in that copy
is read, never written (the suite walks with W.walk, not main).

    python3 tools/mutate_walk.py           # run every mutant
    python3 tools/mutate_walk.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
WALKER = os.path.join(TOOLS, "harness_walk.py")

# (name, find, replace, substring of the check that must fail)
MUTANTS = [
    ("a refusal is filed as driven",
     '        if code in REFUSAL:\n            return "refused"',
     '        if code in REFUSAL:\n            return "driven"',
     "REFUSED, never driven"),
    ("a decline is filed as failed",
     '        if code is None and "requestId" in r:\n            return "declined"',
     '        if code is None and "requestId" in r:\n            return "failed"',
     "DECLINED"),
    ("chaos is never recognised",
     '            if snap.get("chaos", "none") != "none" and "Crash" in (r.get("message") or ""):',
     '            if False:',
     "is CHAOS"),
    ("any raise under an armed plan is chaos, Crash or not",
     '            if snap.get("chaos", "none") != "none" and "Crash" in (r.get("message") or ""):',
     '            if snap.get("chaos", "none") != "none":',
     "FAILED -- the finding"),
    ("failures are not noted",
     '                if b == "failed":\n                    notes.append(',
     '                if False:\n                    notes.append(',
     "every failure is noted"),
    ("a scoped pool is not preferred",
     '    if scoped and t in ("integer", "number", "string"):\n        return rnd.choice(scoped)',
     '    if False:\n        return rnd.choice(scoped)',
     "pooled is driven"),
    ("pools are not refreshed from each response",
     '        snap = r.get("snapshot") or {}\n        if isinstance(snap.get("argumentPools"), dict):\n'
     '            pools.clear()\n            pools.update(snap["argumentPools"])\n        return r',
     '        return r',
     "pooled is driven"),
    ("arrays are never one item first",
     '            return [rnd.choice(ex) for _ in range(1 + tick % 3)]',
     '            return [rnd.choice(ex) for _ in range(2 + tick % 2)]',
     "one item first"),
    ("an unschemable tool is skipped without being named",
     '                except Unschemable as e:\n                    unschemable[tool["name"]] = str(e)\n                    break',
     '                except Unschemable as e:\n                    break',
     "UNSCHEMABLE, named"),
    ("a target that went away is walked on",
     '                if r.get("code") == "unavailable":\n                    raise RuntimeError',
     '                if False:\n                    raise RuntimeError',
     "went away was walked"),
    ("the cross-checks never run",
     '        if invariants:\n            for why in invariants(call, observe, tools, per) or []:',
     '        if False:\n            for why in invariants(call, observe, tools, per) or []:',
     "cross-check ran every round"),
    ("unreachable is never reported",
     '                         if not ever and per[n]["driven"] == 0)',
     '                         if False)',
     "UNREACHABLE"),
    ("unreachable ignores whether anything was driven",
     '                         if not ever and per[n]["driven"] == 0)',
     '                         if not ever)',
     "was REACHED"),
    ("relevant pools are looked up plain, never scoped",
     '        if scoped in pools:\n            keys.append(scoped)',
     '        if False:\n            keys.append(scoped)',
     "UNREACHABLE"),
    ("undriven counts the unreachable and the unschemable",
     '    undriven = [t["name"] for t in tools if per[t["name"]]["driven"] == 0\n'
     '                and t["name"] not in unschemable and t["name"] not in unreachable]',
     '    undriven = [t["name"] for t in tools if per[t["name"]]["driven"] == 0]',
     "undriven names exactly"),
    ("the verdict ignores failures",
     '            or res["invariants_broken"] or res["totals"]["failed"])',
     '            or res["invariants_broken"])',
     "verdict is failing on any one of"),
    # ADR-121: the MCP wire
    ("over MCP, isError is not read as the target's no",
     '                out = {"ok": not r["result"].get("isError"), "message": body.get("message"),',
     '                out = {"ok": True, "message": body.get("message"),',
     "same bucket the same number of times as over"),
    ("over MCP, a gateway code in a JSON-RPC error is not read back",
     '        return head if head in REFUSAL + ("forbidden", "unauthorized", "unavailable", "failed") else "failed"',
     '        return "failed"',
     "same bucket the same number of times as over"),
    ("over MCP, the snapshot is not read after a call",
     '            out["snapshot"] = snap.get("snapshot") or {}',
     '            out["snapshot"] = {}',
     "same bucket the same number of times as over"),
    ("over MCP, the action is guessed from the slug instead of read from _meta",
     '                man["tools"].append({"name": t["name"], "pluginId": meta.get("pluginId"),\n'
     '                                     "action": meta.get("action"), "risk": meta.get("risk"),',
     '                man["tools"].append({"name": t["name"], "pluginId": meta.get("pluginId"),\n'
     '                                     "action": t["name"].split("__", 1)[1].replace("_", "-"), "risk": meta.get("risk"),',
     "never guesses it back out of the slug"),
    # ADR-123: the leak checks
    ("a new thread is never reported",
     '    if names and grown:\n        out.append("threads grew since round one: %s" % grown[:5])',
     '    if False:\n        out.append("threads grew since round one: %s" % grown[:5])',
     "reported by name"),
    ("descriptors may grow without bound",
     '        if fds > allowed:',
     '        if False:',
     "more than the segments explain"),
    ("the baseline is retaken every round",
     '    first = FIRST.setdefault(pid, {"threads": threads, "names": set(names or []), "fds": fds, "segments": segments})',
     '    first = {"threads": threads, "names": set(names or []), "fds": fds, "segments": segments}',
     "reported by name"),
    # ADR-124: argument-set pools
    ("an argument-set pool is never read",
     '    if isinstance(sets, list) and sets and all(isinstance(x, dict) for x in sets):\n        args.update(rnd.choice(sets))',
     '    if False:\n        args.update(rnd.choice(sets))',
     "taken whole"),
    ("a set pool is not a relevant pool",
     '        keys.append(tool["action"])                      # the argument-set pool covers them all',
     '        pass',
     "first relevant pool"),
    ("the verdict ignores unschemable tools",
     '    return (res["identity"] != "holds" or res["undriven"] or res["unschemable"]',
     '    return (res["identity"] != "holds" or res["undriven"]',
     "verdict is failing on any one of"),
]

KNOWN_EQUIVALENT = [
    ("accounted is set to commands instead of summed from the rows",
     "every execute adds one to exactly one row of exactly one tool, so the sum of the rows IS the "
     "command count unless the walk crashes; the identity is a tripwire for a bucket added without a "
     "row, not a runtime measurement (measured 2026-09-02: 0 failures)"),
    ("the plain-pool 70% becomes 100%",
     "the fixture publishes only scoped pools and the suite's plain-pool check asks only that the "
     "pool is used sometimes (measured 2026-09-02: 0 failures); a walk of a page would still pass"),
]


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutwalk_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        path = os.path.join(dst, "harness_walk.py")
        src = io.open(path, encoding="utf-8").read()
        if src.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times -- the mutation never applied" % src.count(find))
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        suite = os.path.join(dst, "verify", "verify_walk.py")
        env = dict(os.environ, CSRBT_WALK_QUICK="1")
        p = subprocess.run([sys.executable, suite], capture_output=True, text=True, timeout=600, env=env)
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        if "NOT VERIFIED" in out:
            return ("BAD MUTANT", "the suite could not run under mutation")
        if not fails and p.returncode != 0:
            return ("BAD MUTANT", "the suite crashed rather than failed: %s"
                    % (out.strip().split("\n")[-1][:70] if out.strip() else "no output"))
        if not fails:
            return ("SURVIVED", "no check failed -- this clause is asserted by nobody")
        hit = any(expect in f for f in fails)
        return ("killed" if hit else "killed by the wrong check",
                "%d failure(s); first: %s" % (len(fails), fails[0][6:80]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    if a.list:
        for n, _, _, e in MUTANTS:
            print("  %-56s must be killed by  %s" % (n, e))
        for n, why in KNOWN_EQUIVALENT:
            print("  %-56s EQUIVALENT: %s" % (n, why[:50]))
        return 0
    print("mutation testing the robot against verify_walk (quick) -- %d mutant(s), %d known equivalent\n"
          % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    for name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-56s %s" % (verdict, name, detail[:60]))
        if verdict == "SURVIVED":
            survived += 1
        elif verdict != "killed":
            bad += 1
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
