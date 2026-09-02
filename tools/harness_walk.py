# -*- coding: utf-8 -*-
"""The robot, for every target: drives a plugin from its manifest alone.

ADR-114 built this for the organism. ADR-117 makes it target-neutral: the
same client walks the organism, the science lab and a kit page -- whatever
`--target` stands up behind the gateway -- and it still imports nothing from
this kit, still speaks only the four operations over stdio, and still forms
every call from the JSON Schema the manifest publishes plus the argument
pools the snapshot publishes. If an argument cannot be formed, the tool is
UNSCHEMABLE and left alone; a robot that guesses a domain is the thing the
contract exists to make unnecessary.

WHAT IS TARGET-NEUTRAL, AND WHAT IS NOT
    Forming calls, the buckets, the accounting identity and the coverage
    floor know nothing about any target. Pools are read by name: a pool
    "<action>.<argument>" is preferred over "<argument>", so the page plugin
    can say "these selectors are the ones set-text can act on" without the
    robot knowing what a text control is.

    The per-round CROSS-CHECKS are the one place a target's own meaning is
    used -- reads compared against reads, never against what was written:

      csrbt-organism   order size == snapshot size == range count ==
                       count-range over the pool, direct and over the wire;
                       generations and segments match the snapshot; the
                       fleet is caught up; two physicals agree; the fold
                       counts no more than the store holds
      csrbt-lab        the target's own counters (runs, lints, battles,
                       adapts, field days) equal what this walk drove
      csrbt-page       read-page's invariants: exactly one pane open, no NaN
                       or [object Object] rendered, no uncaught error, nothing
                       spilling sideways

    They are keyed by plugin id in INVARIANTS; a target with no entry gets
    the general oracle only, which is still a walk.

THE ORACLE
      driven    ok:true
      refused   ok:false with invalid_argument, not_found or conflict -- the
                target defended itself by its own rules; a random argument set
                will make it do that, and it is counted, not hidden
      declined  ok:false with no code -- the action ran and answered no
      chaos     ok:false, failed, while the snapshot says a Sizzle plan is
                armed and the message names the Crash
      failed    anything else that is not ok -- the finding

THE ACCOUNTING
    commands == driven + refused + declined + chaos + failed, UNACCOUNTED if
    not, per target. Every allowed tool must be driven at least once, or the
    run fails: a tool published tomorrow fails the walk until its schema (or
    a pool) is good enough to form a call to it.

    python3 tools/harness_walk.py --target organism      # 8 rounds, seed 2026
    python3 tools/harness_walk.py --target lab --rounds 3
    python3 tools/harness_walk.py --target page --page collection-sheet.html
    python3 tools/harness_walk.py --target all --no-ledger

    python3 tools/harness_walk.py --target fixture --transport mcp   # the same walk, over MCP (ADR-121)

The ledger, tools/walk_ledger.json, is MERGED per target (and per transport --
a walk over MCP is "<plugin>@mcp"): a walk of one
target keeps the others' entries, each with its own `at` (the harness
ledger's rule, ADR-108). The token is generated per run and passed to the
child through its environment, never on a command line.
"""
import argparse, io, json, os, random, secrets, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "walk_ledger.json")
REFUSAL = ("invalid_argument", "not_found", "conflict")
OPS = ("manifest", "discover", "observe", "execute", "quit")


# ---------------------------------------------------------------------------
# the wire: four operations over a child's stdio, and nothing else
# ---------------------------------------------------------------------------

def _spawn(script, token, seed, target, page, python=None):
    env = dict(os.environ)
    env.update({"CSRBT_HARNESS_ENABLED": "true", "CSRBT_HARNESS_TOKEN": token,
                "CSRBT_HARNESS_ALLOW_SENSITIVE_READ": "true",
                "CSRBT_HARNESS_ALLOW_DRAFT": "true",
                "CSRBT_HARNESS_ALLOW_MUTATE": "true",
                "CSRBT_HARNESS_ALLOW_DESTRUCTIVE": "true"})
    return subprocess.Popen(
        [python or sys.executable, script, "--target", target, "--seed", str(seed), "--page", page],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", bufsize=1, env=env)


class Wire(object):
    """The stdio transport: JSON lines, the four operations by name."""
    transport = "stdio"

    def __init__(self, token, seed=42, python=None, stdio=None, target="organism", page="ecology.html"):
        self.token = token
        self.target = target
        self.proc = _spawn(stdio or os.path.join(HERE, "harness_stdio.py"), token, seed, target, page, python)
        self.sent = 0

    def op(self, op, **fields):
        assert op in OPS
        req = {"op": op, "token": self.token}
        req.update(fields)
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        self.sent += 1
        line = self.proc.stdout.readline()
        if not line:
            err = (self.proc.stderr.read() or "")[-400:]
            raise RuntimeError("transport closed (rc=%s): %s" % (self.proc.poll(), err.strip()))
        return json.loads(line)

    def close(self):
        try:
            self.op("quit")
        except Exception:
            pass
        try:
            self.proc.wait(timeout=30)
        except Exception:
            self.proc.kill()


class McpWire(object):
    """The MCP transport (ADR-121): the same four operations, spoken as JSON-RPC
    to tools/harness_mcp.py, and folded back into the shape the walk reads --
    so the walk does not know which transport it is on. What MCP says
    differently, and how it is read:

      manifest   tools/list + resources/list. A tool's `_meta` carries the
                 contract's pluginId and action (the slug csrbt_page__set_text
                 cannot give "set-text" back); the plugins are the snapshot
                 resources. Only allowed tools are listed, so `forbidden` is
                 what the policy hid: nothing, under this walk's policy.
      observe    resources/read of harness://<plugin>/snapshot.
      execute    tools/call with the request id AS the JSON-RPC id (a retry is
                 a replay). A JSON-RPC error whose message begins with a
                 gateway code ("invalid_argument: ...") is that code -- the
                 target defended itself; isError:true with a body is the
                 target's no (declined). MCP returns no snapshot with a call, so
                 the wire reads the resource after every call and prices it by
                 its own clock: over MCP the snapshot is a second round trip,
                 and snapshotMs is what THIS client waited, not what the
                 gateway measured.
    """
    transport = "mcp"

    def __init__(self, token, seed=42, python=None, target="organism", page="ecology.html"):
        self.token = token
        self.target = target
        self.proc = _spawn(os.path.join(HERE, "harness_mcp.py"), token, seed, target, page, python)
        self.sent = 0
        self._id = 0
        self._tools = None
        self._plugins = None

    def rpc(self, method, params=None, mid=None):
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": mid if mid is not None else "w%d" % self._id, "method": method}
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        self.sent += 1
        line = self.proc.stdout.readline()
        if not line:
            err = (self.proc.stderr.read() or "")[-400:]
            raise RuntimeError("transport closed (rc=%s): %s" % (self.proc.poll(), err.strip()))
        return json.loads(line)

    def op(self, op, **fields):
        assert op in OPS
        if op == "discover":
            r = self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                        "clientInfo": {"name": "harness_walk", "version": "1"}})
            if "error" in r:
                return {"ok": False, "error": r["error"]}
            self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            self.proc.stdin.flush()
            self._version = r["result"]["serverInfo"].get("version")
            return {"ok": True, "serverInfo": r["result"]["serverInfo"]}
        if op == "manifest":
            if not hasattr(self, "_version"):
                self.op("discover")                            # MCP: initialize comes first
            tools = self.rpc("tools/list")["result"]["tools"]
            res = self.rpc("resources/list")["result"]["resources"]
            plugins = [{"id": x["uri"][len("harness://"):-len("/snapshot")]} for x in res]
            man = {"protocolVersion": getattr(self, "_version", None), "plugins": plugins, "tools": []}
            for t in tools:
                meta = t.get("_meta") or {}
                man["tools"].append({"name": t["name"], "pluginId": meta.get("pluginId"),
                                     "action": meta.get("action"), "risk": meta.get("risk"),
                                     "allowed": True, "inputSchema": t["inputSchema"]})
            return {"ok": True, "manifest": man}
        if op == "observe":
            r = self.rpc("resources/read", {"uri": "harness://%s/snapshot" % fields["plugin"]})
            if "error" in r:
                return {"ok": False, "code": self._code(r["error"]), "message": r["error"]["message"]}
            return {"ok": True, "snapshot": json.loads(r["result"]["contents"][0]["text"])}
        if op == "execute":
            cmd = fields["command"]
            name = self._name(fields["plugin"], cmd["action"])
            r = self.rpc("tools/call", {"name": name, "arguments": cmd.get("arguments") or {}},
                         mid=cmd["request_id"])
            if "error" in r:
                out = {"ok": False, "code": self._code(r["error"]), "message": r["error"]["message"],
                       "output": {}, "requestId": cmd["request_id"]}
            else:
                body = json.loads(r["result"]["content"][0]["text"])
                # isError is MCP's own word for "this happened and it was a
                # no"; the body's ok is the gateway's, and they agree. The
                # wire reads the protocol's signal, as a host would.
                out = {"ok": not r["result"].get("isError"), "message": body.get("message"),
                       "output": body.get("output") or {}, "requestId": body.get("requestId"),
                       "ms": body.get("ms"), "replayed": body.get("replayed")}
            t0 = time.time()
            snap = self.op("observe", plugin=fields["plugin"])
            out["snapshotMs"] = int((time.time() - t0) * 1000)
            out["snapshot"] = snap.get("snapshot") or {}
            return out
        if op == "quit":
            self.proc.stdin.close()
            return {"ok": True}

    def _name(self, plugin, action):
        if self._tools is None:
            self._tools = {}
            for t in self.op("manifest")["manifest"]["tools"]:
                self._tools[(t["pluginId"], t["action"])] = t["name"]
        name = self._tools.get((plugin, action))
        if name is None:
            raise RuntimeError("no MCP tool for %s/%s: the list must name it in _meta" % (plugin, action))
        return name

    @staticmethod
    def _code(err):
        msg = err.get("message") or ""
        head = msg.split(":", 1)[0].strip()
        return head if head in REFUSAL + ("forbidden", "unauthorized", "unavailable", "failed") else "failed"

    def close(self):
        try:
            self.op("quit")
        except Exception:
            pass
        try:
            self.proc.wait(timeout=30)
        except Exception:
            self.proc.kill()


def wire_for(transport, token, **kw):
    return McpWire(token, **kw) if transport == "mcp" else Wire(token, **kw)


# ---------------------------------------------------------------------------
# forming a call from a schema
# ---------------------------------------------------------------------------

class Unschemable(Exception):
    pass


def form(schema, rnd, tick, pools=None, action=None):
    """One argument set from an inputSchema. Raises Unschemable naming the
    argument that cannot be formed without knowledge the manifest withholds.

    pools: the snapshot's argumentPools, if the plugin publishes any -- values
    that are a fact of the moment (which generations exist right now) rather
    than of the schema. A client observes, then acts on what it observed."""
    args = {}
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    for name, p in props.items():
        if name not in required and rnd.random() < 0.35:
            continue                                     # optionals are sometimes left out
        args[name] = value(name, p, rnd, tick, pools, action)
    return args


def value(name, p, rnd, tick, pools=None, action=None):
    t = p.get("type")
    ex = p.get("examples")
    pools = pools or {}
    # "<action>.<argument>" first -- a pool scoped to what this action can act
    # on -- then the plain "<argument>" pool.
    scoped = pools.get("%s.%s" % (action, name)) if action else None
    if scoped and t in ("integer", "number", "string"):
        return rnd.choice(scoped)          # the target said "these"; nothing to mix in
    pool = pools.get(name)
    if pool and t in ("integer", "number", "string") and rnd.random() < 0.7:
        return rnd.choice(pool)
    if p.get("enum"):
        return p["enum"][tick % len(p["enum"])]
    if t == "boolean":
        return bool(tick % 2)
    if t in ("integer", "number"):
        lo, hi = p.get("minimum"), p.get("maximum")
        if ex and rnd.random() < 0.5:
            return rnd.choice(ex)
        if lo is not None and hi is not None:
            pick = rnd.choice(("lo", "hi", "mid", "mid"))
            v = lo if pick == "lo" else hi if pick == "hi" else rnd.uniform(lo, hi)
            return int(round(v)) if t == "integer" else v
        if ex:
            return rnd.choice(ex)
        if lo is not None:
            return lo + rnd.randint(0, 16)
        if hi is not None:
            return hi - rnd.randint(0, 16)
        return rnd.randint(0, 16)
    if t == "string":
        if ex:
            return rnd.choice(ex)
        raise Unschemable("%s: a string with no enum and no examples" % name)
    if t == "array":
        items = p.get("items") or {}
        if items.get("type") == "string":
            if not ex:
                raise Unschemable("%s: an array of strings with no examples" % name)
            return [rnd.choice(ex) for _ in range(1 + tick % 3)]     # one first: a single-file input
        if items.get("type") in ("integer", "number"):
            return [rnd.randint(0, 16) for _ in range(1 + tick % 3)]
        raise Unschemable("%s: an array of %s" % (name, items.get("type")))
    raise Unschemable("%s: type %s" % (name, t))


# ---------------------------------------------------------------------------
# the walk
# ---------------------------------------------------------------------------

BUCKETS = ("driven", "refused", "declined", "chaos", "failed")


def relevant_pools(tool, pools):
    """The pool keys a tool's REQUIRED arguments would draw from, if the
    target publishes any: "<action>.<argument>" when present, else
    "<argument>". Empty means the target publishes nothing about them."""
    keys = []
    schema = tool["inputSchema"]
    for name in schema.get("required") or []:
        scoped = "%s.%s" % (tool["action"], name)
        if scoped in pools:
            keys.append(scoped)
        elif name in pools:
            keys.append(name)
    return keys


def walk(wire, rounds=8, seed=2026, per_round=3, log=None):
    """Walk every plugin the manifest names. Returns {plugin_id: result}."""
    man = wire.op("manifest")["manifest"]
    out = {}
    for p in man["plugins"]:
        out[p["id"]] = walk_one(wire, man, p["id"], rounds, seed, per_round, log)
    return out


def walk_one(wire, man, pid, rounds, seed, per_round, log=None):
    rnd = random.Random(seed)
    say = log or (lambda *a: None)
    tools = [t for t in man["tools"] if t["allowed"] and t["pluginId"] == pid]
    forbidden = [t["name"] for t in man["tools"] if not t["allowed"] and t["pluginId"] == pid]
    per = dict((t["name"], dict((b, 0) for b in BUCKETS)) for t in tools)
    unschemable, notes, broken = {}, [], []
    count = {"commands": 0}
    pools = {}
    rid = [0]
    empty_pools = {}          # tool name -> ever saw a non-empty scoped pool
    price = {"snapshot": [], "action": []}   # ms per response: the snapshot's and the action's

    def observe():
        snap = wire.op("observe", plugin=pid).get("snapshot") or {}
        if isinstance(snap.get("argumentPools"), dict):
            pools.clear()
            pools.update(snap["argumentPools"])
        return snap

    def execute(tool, args):
        rid[0] += 1
        count["commands"] += 1
        r = wire.op("execute", plugin=pid,
                    command={"request_id": "walk-%s-%d" % (pid, rid[0]), "action": tool["action"],
                             "arguments": args})
        if isinstance(r.get("snapshotMs"), int):
            price["snapshot"].append(r["snapshotMs"])
        if isinstance(r.get("ms"), int):
            price["action"].append(r["ms"])           # a refusal ran no action: no price, not zero
        snap = r.get("snapshot") or {}
        if isinstance(snap.get("argumentPools"), dict):
            pools.clear()
            pools.update(snap["argumentPools"])
        return r

    def bucket(tool, r):
        if r.get("ok"):
            return "driven"
        code = r.get("code")
        if code in REFUSAL:
            return "refused"
        if code is None and "requestId" in r:
            return "declined"
        if code == "failed":
            snap = observe()
            if snap.get("chaos", "none") != "none" and "Crash" in (r.get("message") or ""):
                return "chaos"
        return "failed"

    cc = per.setdefault("_cross_checks", dict((b, 0) for b in BUCKETS))

    def call(action, **args):
        """A cross-check's read: counted, and a refusal is a broken check."""
        r = execute(dict(action=action), args)
        if r.get("ok"):
            cc["driven"] += 1
        else:
            cc["failed"] += 1
            broken.append("cross-check %s %s -> %s %s"
                          % (action, args, r.get("code"), (r.get("message") or "")[:80]))
            r = {"ok": False, "output": {}, "snapshot": observe()}
        return r

    invariants = INVARIANTS.get(pid)
    observe()                                              # the first pools
    t0 = time.time()
    for round_no in range(1, rounds + 1):
        order = list(tools)
        rnd.shuffle(order)
        for tool in order:
            if tool["name"] in unschemable:
                continue
            for i in range(per_round):
                # The tool's own call number, from zero: the first call to any
                # tool takes the first enum value and a one-item array (a
                # single-file input gets one file before it gets three). The
                # fixture walk found the old round*100+i tick handing out two
                # items first -- "one first" was true in the generator's unit
                # check and false in every walk.
                tick = (round_no - 1) * per_round + i
                relevant = relevant_pools(tool, pools)
                if relevant:
                    empty_pools[tool["name"]] = empty_pools.get(tool["name"], False) or \
                        all(pools[k] for k in relevant)
                try:
                    args = form(tool["inputSchema"], rnd, tick, pools, tool["action"])
                except Unschemable as e:
                    unschemable[tool["name"]] = str(e)
                    break
                r = execute(tool, args)
                b = bucket(tool, r)
                per[tool["name"]][b] += 1
                if b == "failed":
                    notes.append("%s %s -> %s: %s" % (tool["action"], json.dumps(args)[:120],
                                                       r.get("code"), (r.get("message") or "")[:100]))
                if r.get("code") == "unavailable":
                    raise RuntimeError("%s went away: %s" % (pid, r.get("message")))
        if invariants:
            for why in invariants(call, observe, tools, per) or []:
                broken.append("round %d: %s" % (round_no, why))
        say("%s round %d/%d  commands=%d  broken=%d" % (pid, round_no, rounds, count["commands"], len(broken)))

    commands = count["commands"]
    totals = dict((b, sum(v[b] for v in per.values())) for b in BUCKETS)
    accounted = sum(totals.values())
    # A tool whose scoped pool ("<action>.<argument>") the target published
    # EMPTY every time it was looked at has nothing to act on here -- a page
    # with no file input cannot have attach-file driven. That is a fact about
    # the target, reported as unreachable, not a hole in the schema or the walk.
    # ... and only when nothing was driven: a tool that got through on a
    # schema example despite an empty pool was reached, whatever the pool said.
    unreachable = sorted(n for n, ever in empty_pools.items()
                         if not ever and per[n]["driven"] == 0)
    undriven = [t["name"] for t in tools if per[t["name"]]["driven"] == 0
                and t["name"] not in unschemable and t["name"] not in unreachable]
    def stats(xs):
        if not xs:
            return {"n": 0}
        xs = sorted(xs)
        return {"n": len(xs), "median": xs[len(xs) // 2], "p95": xs[min(len(xs) - 1, int(len(xs) * 0.95))],
                "max": xs[-1], "total": sum(xs)}
    return {
        "at": int(time.time()), "plugin": pid, "seed": seed, "rounds": rounds, "per_round": per_round,
        "transport": getattr(wire, "transport", "stdio"),
        # ADR-120: the snapshot every response carries, priced from the
        # responses themselves -- what the target charged to be asked about
        # itself, beside what the actions cost.
        "price": {"snapshotMs": stats(price["snapshot"]), "actionMs": stats(price["action"])},
        "protocolVersion": man["protocolVersion"],
        "tools": len(tools), "forbidden": forbidden,
        "commands": commands, "accounted": accounted,
        "identity": "holds" if accounted == commands else "UNACCOUNTED",
        "totals": totals, "per_action": per,
        "undriven": undriven, "unreachable": unreachable, "unschemable": unschemable,
        "invariants_broken": broken, "failures": notes,
        "seconds": round(time.time() - t0, 1),
    }


# ---------------------------------------------------------------------------
# cross-checks: reads against reads, keyed by plugin id
# ---------------------------------------------------------------------------

def organism_checks(call, observe, tools, per):
    broken = []
    snap = call("quiesce", ms=15000)["snapshot"]
    if snap.get("chaos", "none") != "none":
        snap = call("restart", chaos="none")["snapshot"]
        call("quiesce", ms=15000)
    size = snap["size"]
    keys = [a for a in tools if a["action"] == "put"][0]["inputSchema"]["properties"]["key"]["examples"]
    lo, hi = min(keys) - 1, max(keys) + 1
    got = {
        "order size": call("order", kind="size")["output"].get("answer"),
        "order size wire": call("order", kind="size", via="wire")["output"].get("answer"),
        "count-range": call("count-range", lo=lo, hi=hi)["output"].get("count"),
        "count-range wire": call("count-range", lo=lo, hi=hi, via="wire")["output"].get("count"),
        "range count": call("range", lo=lo, hi=hi, cap=1)["output"].get("count"),
    }
    for k, v in got.items():
        if v != size:
            broken.append("%s = %s but snapshot size = %s" % (k, v, size))
    g = call("generations")["output"].get("generations", [])
    if len(g) != snap["generations"]:
        broken.append("generations %s vs snapshot %s" % (g, snap["generations"]))
    segs = call("segments")["output"].get("segments", [])
    if len(segs) != snap["segments"] or sum(x["garbageBytes"] for x in segs) != snap["garbageBytes"]:
        broken.append("segments do not account for the snapshot")
    fl = call("fleet")["output"].get("replicas", [])
    if not fl or fl[0]["lag"] != 0 or fl[0]["gapped"]:
        broken.append("fleet not caught up after quiesce: %s" % fl)
    if call("report")["output"].get("report") != call("report")["output"].get("report"):
        broken.append("two physicals differ")
    grp = call("groups", top=3)["output"]
    if grp and (grp["groups"] > size or sum(x["total"] for x in grp["top"]) > size):
        broken.append("the fold counts more than the store holds")
    return broken


def lab_checks(call, observe, tools, per):
    """The lab's own counters must equal what this walk drove -- an oracle
    that needs no knowledge of what any run computed."""
    snap = observe()
    driven = lambda *names: sum(per.get("csrbt_lab__" + n, {}).get("driven", 0) for n in names)
    want = {"runs": driven("run", "run_protocol", "export"), "lints": driven("lint"),
            "battles": driven("battle"), "adapts": driven("adapt"), "fieldDays": driven("field_day")}
    return ["%s: target counts %s, the walk drove %s" % (k, snap.get(k), v)
            for k, v in want.items() if snap.get(k) != v]


def page_checks(call, observe, tools, per):
    """The page's own general oracle, as read-page publishes it."""
    st = call("read-page")["output"]
    if not st:
        return ["read-page answered nothing"]
    broken = []
    if st.get("panes") and st.get("onp") != 1:
        broken.append("%d pane(s) open, not exactly one" % st.get("onp"))
    if st.get("junk"):
        broken.append("junk rendered: %s" % st["junk"][:80])
    if st.get("errors"):
        broken.append("uncaught: %s" % str(st["errors"][0])[:80])
    if (st.get("overflow") or 0) > 1:
        broken.append("spills %dpx sideways: %s" % (st["overflow"], st.get("wide")))
    return broken


def fixture_checks(call, observe, tools, per):
    """The fixture's counters must equal what the walk sent it, and its
    consistent flag must hold -- which it will not once `broken` has run,
    so a walker that stops collecting cross-checks is visible."""
    snap = observe()
    broken = []
    if not snap.get("ready"):
        return ["the fixture is not ready"]
    for t in tools:
        sent = sum(per.get(t["name"], {}).values())
        got = snap.get("calls", {}).get(t["action"], 0)
        if t["name"] not in per or sent != got:
            broken.append("%s: the walk sent %d, the fixture counted %d" % (t["action"], sent, got))
    if not snap.get("consistent", True):
        broken.append("the fixture reports it is not consistent")
    return broken


INVARIANTS = {"csrbt-organism": organism_checks, "csrbt-lab": lab_checks, "csrbt-page": page_checks,
              "csrbt-fixture": fixture_checks}


def report(pid, res, out=print):
    out("")
    out("== %s  (over %s)" % (pid, res.get("transport", "stdio")))
    out("%-30s %7s %7s %8s %6s %6s" % ("action", "driven", "refused", "declined", "chaos", "failed"))
    for name in sorted(res["per_action"]):
        c = res["per_action"][name]
        out("%-30s %7d %7d %8d %6d %6d" % (name, c["driven"], c["refused"], c["declined"], c["chaos"], c["failed"]))
    t = res["totals"]
    out("%-30s %7d %7d %8d %6d %6d" % ("total", t["driven"], t["refused"], t["declined"], t["chaos"], t["failed"]))
    out("commands %d == accounted %d: %s" % (res["commands"], res["accounted"], res["identity"]))
    out("tools %d, undriven %s, unreachable %s, unschemable %s"
        % (res["tools"], res["undriven"] or "none", res["unreachable"] or "none",
           res["unschemable"] or "none"))
    pr = res.get("price") or {}
    if pr.get("snapshotMs", {}).get("n"):
        out("price: snapshot median %d ms, p95 %d, max %d; action median %d ms, max %d (%d responses)"
            % (pr["snapshotMs"]["median"], pr["snapshotMs"]["p95"], pr["snapshotMs"]["max"],
               pr["actionMs"]["median"], pr["actionMs"]["max"], pr["snapshotMs"]["n"]))
    out("invariants broken: %d" % len(res["invariants_broken"]))
    for b in res["invariants_broken"][:10]:
        out("  " + b)
    for f in res["failures"][:10]:
        out("  FAILED " + f)


def bad(res):
    return (res["identity"] != "holds" or res["undriven"] or res["unschemable"]
            or res["invariants_broken"] or res["totals"]["failed"])


def merge_ledger(results, path=LEDGER):
    """Per target, keep what this run did not walk (ADR-108's ledger rule)."""
    led = {"_comment": "Written by harness_walk.py. One entry per target; a walk updates only the "
                       "targets it drove and keeps the rest, each with its own at.", "targets": {}}
    if os.path.isfile(path):
        try:
            led = json.load(io.open(path, encoding="utf-8"))
        except ValueError:
            pass
    # ADR-121: a walk over MCP is its own entry, "<plugin>@mcp"; the stdio
    # entries keep the plain key they have had since ADR-114.
    keyed = dict((pid if res.get("transport", "stdio") == "stdio" else "%s@%s" % (pid, res["transport"]), res)
                 for pid, res in results.items())
    led.setdefault("targets", {}).update(keyed)
    json.dump(led, io.open(path, "w", encoding="utf-8"), indent=1, sort_keys=True)
    return led


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="organism", choices=["page", "organism", "lab", "both", "all", "fixture"])
    ap.add_argument("--page", default="collection-sheet.html",
                    help="the page to walk under --target page (the hub has only links)")
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--per-round", type=int, default=3)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--organism-seed", type=int, default=42)
    ap.add_argument("--no-ledger", action="store_true")
    ap.add_argument("--transport", default="stdio", choices=["stdio", "mcp"],
                    help="which transport to walk through (ADR-121): the walk itself does not know")
    a = ap.parse_args(argv)

    token = "walk-" + secrets.token_urlsafe(24)
    try:
        wire = wire_for(a.transport, token, seed=a.organism_seed, target=a.target, page=a.page)
        hello = wire.op("discover")
    except Exception as e:
        print("cannot start the transport: %s" % e)
        return 2
    if not hello.get("ok"):
        print("the transport refused discovery: %s" % hello)
        return 2
    try:
        results = walk(wire, rounds=a.rounds, seed=a.seed, per_round=a.per_round, log=print)
    finally:
        wire.close()
    for pid, res in results.items():
        report(pid, res)
    if not a.no_ledger:
        merge_ledger(results)
        print("\nwrote %s" % LEDGER)
    return 1 if any(bad(r) for r in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
