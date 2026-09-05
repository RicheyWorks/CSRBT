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
     '            if not t["allowed"]:\n                self._withheld[t["name"]] = t["risk"]\n                continue',
     '            if False:\n                self._withheld[t["name"]] = t["risk"]\n                continue',
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
     # Since ADR-141 the transport does more than refuse an unlisted name: it
     # says WHICH kind of not-listed it is. With the lookup gone, the call falls
     # through to the gateway, which refuses it -- correctly, but with no idea
     # whether the name was withheld or misspelled, which is the whole of what
     # this branch is for.
     "withheld by policy says so"),
    ("tools drop their _meta, so a client must guess the action from the slug",
     '                        "_meta": {"pluginId": t["pluginId"], "action": t["action"], "risk": t["risk"]}})',
     '                        "_meta": {"pluginId": t["pluginId"], "action": t["name"].split("__", 1)[1], "risk": t["risk"]}})',
     "never guesses an action"),
]


MUTANTS += [
    # ---- ADR-137: listChanged, with a consumer ----
    ('the server announces the change and keeps the name map it cached',
     '        self._tools = None\n        self._withheld = {}\n        self._notes.append({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})',
     '        self._notes.append({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})',
     'DROPS its own name map'),
    ('a plugin arriving takes no resource with it',
     '        if kind == "plugins":',
     '        if False:',
     'changes both lists'),
    ('listChanged is declared whatever the session can do',
     '        self._can_change = (any(p["id"] == SESSION_PLUGIN_ID for p in gateway.discover(token))\n                            if list_changed is None else bool(list_changed))',
     '        self._can_change = True',
     'declares listChanged FALSE'),
    ('listChanged is never declared, so the notices are sent unannounced',
     '        self._can_change = (any(p["id"] == SESSION_PLUGIN_ID for p in gateway.discover(token))\n                            if list_changed is None else bool(list_changed))',
     '        self._can_change = False',
     'declares listChanged TRUE'),
    ('the notice is written after the response it explains',
     '        for note in server.drain():\n            _w(stdout, note)\n        if resp is not None:\n            _w(stdout, resp)',
     '        if resp is not None:\n            _w(stdout, resp)\n        for note in server.drain():\n            _w(stdout, note)',
     'writes the notifications first'),
    ('building a registry is a change, so every session opens by announcing one',
     '            self.register(p, quiet=True)          # construction is not a change',
     '            self.register(p)          # construction is not a change',
     'construction is not a change'),
    ('retiring a plugin announces nothing',
     '        plugin = self._by_id.pop(plugin_id)\n        self._announce("plugins")',
     '        plugin = self._by_id.pop(plugin_id)',
     'retire hands the plugin back and announces'),
    ('a watcher that raises takes the registry down with it',
     '        for fn in list(self._watchers):\n            try:\n                fn(kind)\n            except Exception:\n                pass',
     '        for fn in list(self._watchers):\n            fn(kind)',
     'took the registry down with it'),
    ("a retired plugin's replayable responses outlive it",
     '        for key in [k for k in self._done if k.split("\\x00", 1)[0] not in live]:\n            self._bytes -= self._done.pop(key).nbytes',
     '        pass',
     'is a NEW target'),
    ('detach takes the target out of the registry and leaves it running',
     '        TG.tear_down(closers)\n        return True, "%s detached; %d plugin(s) gone" % (target, len(gone)), {',
     '        return True, "%s detached; %d plugin(s) gone" % (target, len(gone)), {',
     'AND closes it'),
    ('detach retires whatever it is named, attached by this session or not',
     '        if target not in self.attached:\n            raise NotFound("%s was not attached by this session (attached: %s)"',
     '        if False:\n            raise NotFound("%s was not attached by this session (attached: %s)"',
     'did not attach'),
    ('the consumer hears the notice and keeps its cache',
     '        if method == "notifications/tools/list_changed":\n            self._tools = None',
     '        if method == "notifications/tools/list_changed":\n            pass',
     'drops its cached tool-name map'),
    ('the client takes the next line for its answer',
     '        while True:\n            line = self.proc.stdout.readline()',
     '        for _once in (1,):\n            line = self.proc.stdout.readline()',
     'reads until its id comes back'),
]

KNOWN_EQUIVALENT = [
    ("the resource URI shape is not checked",
     "the registry refuses an unknown plugin id with not_found, so a foreign URI ends in "
     "the same -32602 either way (measured 2026-09-01: 0 failures)"),
]


MUTANTS += [
    # ---- ADR-141: withheld is not unknown ----
    ('a tool the policy withheld answers as a name nobody has',
     '            rung = (self._withheld or {}).get(name)\n            if rung:',
     '            rung = (self._withheld or {}).get(name)\n            if False:',
     'names the rung that withheld it'),
    ('the server never records what it was not shown',
     '                self._withheld[t["name"]] = t["risk"]\n                continue',
     '                continue',
     'names the rung that withheld it'),
    ('a name nobody has answers as a tool that was withheld',
     '            raise HarnessError("not_found", "no tool %r is listed for this session" % name)',
     '            raise HarnessError("forbidden", "tool %r is withheld" % name)',
     "is still not_found"),
]


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutmcp_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        # ADR-137: listChanged is not one file's clause. The notice is the
        # server's, the change is the registry's, the forgetting is the
        # gateway's, the attach is the session plugin's, and the CONSUMER is
        # the robot's wire -- so a mutant may live in any of the five.
        path, src = None, None
        for cand in ("harness_mcp.py", "harness_contract.py", "harness_plugin_session.py",
                     "harness_walk.py"):
            t = io.open(os.path.join(dst, cand), encoding="utf-8").read()
            if t.count(find) == 1:
                path, src = os.path.join(dst, cand), t
                break
        if src is None:
            src = io.open(os.path.join(dst, "harness_mcp.py"), encoding="utf-8").read()
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
    rows = []
    for name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-56s %s" % (verdict, name, detail[:60]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    import mutant_ledger
    mutant_ledger.record("mutate_mcp", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
