# -*- coding: utf-8 -*-
"""The first transport. One JSON object per line in, one per line out.

A transport is an adapter over four operations and nothing else -- manifest,
discover, observe, execute. It holds no policy, knows no CSS, and decides
nothing. That is the whole claim this file exists to make good on, and it is
why it is this short: if a second transport (REST, MCP, a websocket) needed
more than this, the boundary would be in the wrong place.

    {"op":"manifest","token":"..."}
    {"op":"discover","token":"..."}
    {"op":"observe","token":"...","plugin":"csrbt-page"}
    {"op":"execute","token":"...","plugin":"csrbt-page",
     "command":{"request_id":"...","action":"show-pane",
                "arguments":{"pane":"log"}}}

OFF BY DEFAULT. It refuses to start unless CSRBT_HARNESS_ENABLED is true and
CSRBT_HARNESS_TOKEN is at least 24 characters, whatever else is set, and it
reads no token from a command line -- an argument is visible in a process list
and in a shell history.

    CSRBT_HARNESS_ENABLED=true \
    CSRBT_HARNESS_TOKEN=<at least 24 random characters> \
    CSRBT_HARNESS_ALLOW_DRAFT=true \
    python3 tools/harness_stdio.py --page collection-sheet.html

    python3 tools/harness_stdio.py --target organism      # the engines (ADR-112)
    python3 tools/harness_stdio.py --target both --page ecology.html

--target chooses what stands behind the gateway: a kit page in a browser, the
WholeHog organism in a child process, or both in one registry. The transport
does not change between them -- that is the measurement ADR-112 exists to
make -- so nothing below the argument parser knows which it got.

Enable only the capability the supervised session needs, then unset the
variables. Do not put the token in a URL, a prompt, a source file, a screenshot
or a transcript.
"""
import argparse, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "verify"))
from harness_contract import Gateway, HarnessError, Registry
from harness_targets import require_policy, stand_up, tear_down


def serve(gateway, stdin, stdout):
    """The entire adapter: parse a line, call one of four, write a line."""
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            _w(stdout, {"ok": False, "code": "invalid_argument",
                        "message": "not JSON: %s" % str(e)[:120]})
            continue
        op, tok = req.get("op"), req.get("token")
        try:
            if op == "manifest":
                res = {"ok": True, "manifest": gateway.manifest(tok)}
            elif op == "discover":
                res = {"ok": True, "plugins": gateway.discover(tok)}
            elif op == "observe":
                res = {"ok": True, "snapshot": gateway.observe(tok, req.get("plugin"))}
            elif op == "execute":
                res = dict(gateway.execute(tok, req.get("plugin"),
                                           req.get("command") or {}))
                res["ok"] = res.get("ok", True)
            elif op == "quit":
                _w(stdout, {"ok": True, "message": "bye"})
                return 0
            else:
                res = {"ok": False, "code": "not_found",
                       "message": "unknown op %r" % op}
        except HarnessError as e:
            res = e.as_dict()
        _w(stdout, res)
    return 0


def _w(out, obj):
    out.write(json.dumps(obj, default=str) + "\n")
    out.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default="ecology.html",
                    help="page to open in the browser the plugin drives")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--target", default="page", choices=["page", "organism", "lab", "both", "all"],
                    help="what the gateway fronts: a kit page, the WholeHog "
                         "organism, the science lab, both (organism+page) or all "
                         "(default: page)")
    ap.add_argument("--seed", type=int, default=42, help="organism seed")
    a = ap.parse_args()

    policy = require_policy()
    if policy is None:
        return 2
    plugins, closers = stand_up(a.target, page=a.page, seed=a.seed, headed=a.headed)
    gw = Gateway(Registry(plugins), policy)
    sys.stderr.write("harness ready on stdio: %s, policy %s\n"
                     % (", ".join(p.descriptor().id for p in plugins),
                        ",".join(k for k, v in policy.allow.items() if v)))
    try:
        rc = serve(gw, sys.stdin, sys.stdout)
    finally:
        tear_down(closers)
    return rc


if __name__ == "__main__":
    sys.exit(main())
