# -*- coding: utf-8 -*-
"""Mutation testing for the MCP transport (ADR-115).

verify_mcp passed 31 of 31 on the afternoon it was written. Same rule as
every suite in this kit: a suite nobody has watched fail is a suite nobody
knows the shape of. Seven mutations were applied to tools/harness_mcp.py by
hand that afternoon; six died and one was equivalent under the gateway. They
live here so the number is recomputed, not remembered.

SAFETY: a copy of tools/ is mutated in a temp dir; the real file is never
written to.

    python3 tools/mutate_mcp.py            # run every mutant
    python3 tools/mutate_mcp.py --list
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")

MUTANTS = [
    ("a target's no is never isError",
     '"isError": not r["ok"]}', '"isError": False}',
     "isError, not a protocol error"),
    ("tools/list lists what the policy does not allow",
     '            if not t["allowed"]:\n                continue',
     '            if False:\n                continue',
     "exactly what the policy allows"),
    ("every call gets a fresh request id, so a retry writes twice",
     'rid = "mcp-%s" % mid if mid is not None else None',
     'rid = "mcp-%s-%d" % (mid, id(object())) if mid is not None else None',
     "same JSON-RPC id is a replay"),
    ("every tool is annotated read-only",
     '    ro = risk in ("READ", "NAVIGATE", "SENSITIVE_READ")', '    ro = True',
     "MCP annotations"),
    ("notifications are answered",
     '        if method.startswith("notifications/"):\n            return None',
     '        if False:\n            return None',
     "silence"),
    ("a tool that is not listed runs anyway",
     '        if name not in self._tools:', '        if False:',
     "never reached the plugin"),
]

KNOWN_EQUIVALENT = [
    ("the resource URI shape is not checked",
     "the registry refuses an unknown plugin id with not_found, so a foreign URI ends in "
     "the same -32602 either way (measured 2026-09-01: 0 failures)"),
]


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutmcp_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        path = os.path.join(dst, "harness_mcp.py")
        src = io.open(path, encoding="utf-8").read()
        if src.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times -- the mutation never applied" % src.count(find))
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        env = dict(os.environ, CSRBT_WHOLEHOG="/nonexistent")   # section C is not what these test
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_mcp.py")],
                           capture_output=True, text=True, timeout=600, env=env)
        fails = [l for l in (p.stdout + p.stderr).split("\n") if l.startswith("FAIL")]
        if not fails and p.returncode != 0:
            # A suite that crashed under mutation asserted nothing either way. Reporting
            # it SURVIVED would be the tool accusing its own suite of a hole it does not
            # have; reporting it killed would be a kill by a traceback. Neither is a result.
            return ("BAD MUTANT", "the suite crashed rather than failed: %s"
                    % (out.strip().split("\n")[-1][:70] if out.strip() else "no output"))
        if not fails:
            return ("SURVIVED", "no check failed -- this clause is asserted by nobody")
        return ("killed" if any(expect in f for f in fails) else "killed by the wrong check",
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
    print("mutation testing tools/harness_mcp.py against verify_mcp -- %d mutant(s), %d known equivalent\n"
          % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    for name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-56s %s" % (verdict, name, detail[:60]))
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
