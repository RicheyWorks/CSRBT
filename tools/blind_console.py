# -*- coding: utf-8 -*-
"""A door, and nothing else: the console a BLIND operator drives (ADR-136).

ADR-126 built the instrument -- the MCP server records a trace, the task
grader holds a trace to a task -- and said plainly what it could not do:

    A blind trial: a model that did not write the tasks. The instrument is
    ready; the operator is not in this sandbox.

This is the operator's side of that trial. It speaks JSON-RPC to
tools/harness_mcp.py over a pipe, and it gives an operator exactly what a
host would have: `tools/list`, `resources/list`, and the ability to call a
tool and read a resource. It gives nothing else. In particular it never
reads tools/tasks/, and the trial is run in a checkout with that directory
removed, so "the operator did not see the steps" is a fact about the
filesystem rather than a promise about someone's attention.

    python3 tools/blind_console.py --target organism --moves moves.json \\
            --trace tools/traces/<task>.jsonl

`moves.json` is a list the operator writes:

    [{"list": true},
     {"call": "csrbt_organism__put", "arguments": {"key": 11, "attr": 1}},
     {"read": "harness://csrbt-organism/snapshot"},
     {"observe": "csrbt-organism"}]

Every move's whole response is printed as JSON, in order, so the operator can
plan the next move from what the door actually answered -- which is the only
thing a real host has to go on either.
"""
import argparse, io, json, os, secrets, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))


class Door(object):
    """The MCP server as a child process, spoken to in JSON-RPC."""

    def __init__(self, target, page, seed, trace, token):
        env = dict(os.environ)
        env["CSRBT_HARNESS_ENABLED"] = "true"
        env["CSRBT_HARNESS_TOKEN"] = token
        # the rungs a supervised operator gets: read what is entered, draft,
        # and write. Not DESTRUCTIVE -- an operator that can wipe the store is
        # not being supervised, it is being trusted.
        for rung in ("SENSITIVE_READ", "DRAFT", "MUTATE"):
            env["CSRBT_HARNESS_ALLOW_" + rung] = "true"
        cmd = [sys.executable, os.path.join(HERE, "harness_mcp.py"),
               "--target", target, "--page", page, "--seed", str(seed)]
        if trace:
            cmd += ["--trace", trace]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env, text=True, bufsize=1)
        self.n = 0
        self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                "clientInfo": {"name": "blind-operator", "version": "1"}})

    def rpc(self, method, params=None):
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": method}
        if params is not None:
            msg["params"] = params
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise SystemExit("the door closed: %s" % (self.p.stderr.read() or "")[-400:])
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("id") == self.n:
                return r

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=20)
        except Exception:
            self.p.kill()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="organism",
                    choices=["page", "organism", "lab", "both", "all", "fixture"])
    ap.add_argument("--page", default="collection-sheet.html")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--moves", help="a JSON file of moves; omit to just list what the door offers")
    ap.add_argument("--trace", help="record every call here (the file the grader reads)")
    ap.add_argument("--cap", type=int, default=0, metavar="N",
                    help="print at most N characters of each answer, saying so when it bites. "
                         "The default, 0, prints the whole answer -- a snapshot is the discovery "
                         "path and a clipped one does not parse (ADR-141).")
    a = ap.parse_args(argv)

    token = "blind-" + secrets.token_urlsafe(24)
    door = Door(a.target, a.page, a.seed, a.trace, token)
    out = []
    try:
        if not a.moves:
            tools = door.rpc("tools/list").get("result", {}).get("tools", [])
            res = door.rpc("resources/list").get("result", {}).get("resources", [])
            print(json.dumps({"tools": tools, "resources": res}, indent=1, ensure_ascii=False))
            return 0
        moves = json.load(io.open(a.moves, encoding="utf-8"))
        for i, m in enumerate(moves):
            t0 = time.time()
            if m.get("list"):
                r = door.rpc("tools/list")
            elif "read" in m:
                r = door.rpc("resources/read", {"uri": m["read"]})
            elif "observe" in m:
                r = door.rpc("resources/read", {"uri": "harness://%s/snapshot" % m["observe"]})
            elif "call" in m:
                r = door.rpc("tools/call", {"name": m["call"], "arguments": m.get("arguments") or {}})
            else:
                r = {"error": {"message": "a move is one of list, call, read, observe: %r" % m}}
            out.append({"move": i, "asked": m, "answer": r, "ms": int((time.time() - t0) * 1000)})
            # ADR-141: WHOLE, by default. This printed [:4000] and said nothing
            # about it, so a snapshot -- the documented way to discover a page's
            # controls, and 40KB on the science pages -- arrived as truncated
            # JSON that would not parse. Two of the four blind operators gave up
            # on this console and wrote their own JSON-RPC client, which means
            # the trial was measuring the console rather than the door. A cap is
            # available and, when it bites, SAYS it bit.
            line = json.dumps(out[-1], ensure_ascii=False)
            if a.cap and len(line) > a.cap:
                line = (line[:a.cap] + '\n... [%d of %d characters shown: this console was run '
                        'with --cap %d]' % (a.cap, len(line), a.cap))
            print(line)
    finally:
        door.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
