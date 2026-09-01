# -*- coding: utf-8 -*-
"""The first robot: drives the organism from its manifest alone (ADR-114).

WHAT THIS IS
    A client that knows nothing about the organism. It imports nothing from
    this kit. It starts `harness_stdio.py --target organism` as a child, speaks
    the four operations over stdin/stdout, reads the manifest, and forms every
    call from the JSON Schema the manifest publishes -- enum values, bounds,
    patterns' examples, example pools -- and nothing else. If an argument
    cannot be formed from the schema, the tool is reported UNSCHEMABLE and
    left alone, because a robot that guesses a domain from a description is
    the thing the contract exists to make unnecessary.

    That is the claim being measured: that the manifest is sufficient to
    OPERATE the organism, not merely to describe it. verify_organism proves
    the organism does the right thing when a suite that read the source drives
    it. This proves a client that read only the manifest can drive all of it.

THE ORACLE
    General, not per-action -- a per-action expectation is how a walker ends
    up asserting what its author remembered (ADR-100). Every response is one
    of:

      driven    ok:true
      refused   ok:false with invalid_argument, not_found or conflict -- the
                target defended itself by its own rules; a random argument set
                will make it do that, and it is counted, not hidden
      declined  ok:false with no code -- the action ran and answered no (a
                quiesce that timed out, an archive that did not verify)
      chaos     ok:false, failed, while the snapshot says a Sizzle plan is
                armed and the message names the Crash -- the plan doing what
                the manifest says it does
      failed    anything else that is not ok -- the finding

    and after every round a set of cross-checks that need no knowledge of
    what was written, only of what the manifest says the reads mean:

      order size == snapshot size == range count == count-range over the pool,
      direct and over the wire; generations and segments match the snapshot;
      the fleet is caught up after quiesce; two physicals agree.

THE ACCOUNTING
    commands == driven + refused + declined + chaos + failed, UNACCOUNTED if not.
    Every allowed tool must be driven at least once -- a tool the walk never
    got an ok from is UNDRIVEN and fails the run, which is the coverage floor:
    a new action published tomorrow fails this walk until the schema is good
    enough to form a call to it.

    python3 tools/organism_walk.py                 # 8 rounds, seed 2026
    python3 tools/organism_walk.py --rounds 3 --seed 7
    python3 tools/organism_walk.py --no-ledger     # do not write the ledger

Needs the engine built (./gradlew harnessClasspath in WholeHog). The token is
generated per run and passed to the child through its environment, never on
a command line.
"""
import argparse, io, json, os, random, secrets, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "organism_ledger.json")
REFUSAL = ("invalid_argument", "not_found", "conflict")
OPS = ("manifest", "discover", "observe", "execute", "quit")


# ---------------------------------------------------------------------------
# the wire: four operations over a child's stdio, and nothing else
# ---------------------------------------------------------------------------

class Wire(object):
    def __init__(self, token, seed=42, python=None, stdio=None):
        self.token = token
        env = dict(os.environ)
        env.update({"CSRBT_HARNESS_ENABLED": "true", "CSRBT_HARNESS_TOKEN": token,
                    "CSRBT_HARNESS_ALLOW_SENSITIVE_READ": "true",
                    "CSRBT_HARNESS_ALLOW_DRAFT": "true",
                    "CSRBT_HARNESS_ALLOW_MUTATE": "true",
                    "CSRBT_HARNESS_ALLOW_DESTRUCTIVE": "true"})
        self.proc = subprocess.Popen(
            [python or sys.executable, stdio or os.path.join(HERE, "harness_stdio.py"),
             "--target", "organism", "--seed", str(seed)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1, env=env)
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


# ---------------------------------------------------------------------------
# forming a call from a schema
# ---------------------------------------------------------------------------

class Unschemable(Exception):
    pass


def form(schema, rnd, tick, pools=None):
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
        args[name] = value(name, p, rnd, tick, pools)
    return args


def value(name, p, rnd, tick, pools=None):
    t = p.get("type")
    ex = p.get("examples")
    pool = (pools or {}).get(name)
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
            return [rnd.choice(ex) for _ in range(rnd.randint(1, 3))]
        if items.get("type") in ("integer", "number"):
            return [rnd.randint(0, 16) for _ in range(rnd.randint(1, 3))]
        raise Unschemable("%s: an array of %s" % (name, items.get("type")))
    raise Unschemable("%s: type %s" % (name, t))


# ---------------------------------------------------------------------------
# the walk
# ---------------------------------------------------------------------------

BUCKETS = ("driven", "refused", "declined", "chaos", "failed")


def walk(wire, rounds=8, seed=2026, per_round=3, log=None):
    rnd = random.Random(seed)
    say = log or (lambda *a: None)
    man = wire.op("manifest")["manifest"]
    plugin = [p["id"] for p in man["plugins"]]
    assert plugin == ["csrbt-organism"], plugin
    tools = [t for t in man["tools"] if t["allowed"]]
    forbidden = [t["name"] for t in man["tools"] if not t["allowed"]]
    per = dict((t["name"], dict((b, 0) for b in BUCKETS)) for t in tools)
    unschemable, notes, broken = {}, [], []
    count = {"commands": 0}
    pools = {}
    rid = [0]

    def execute(tool, args):
        rid[0] += 1
        count["commands"] += 1
        r = wire.op("execute", plugin="csrbt-organism",
                    command={"request_id": "walk-%d" % rid[0], "action": tool["action"],
                             "arguments": args})
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
            snap = wire.op("observe", plugin="csrbt-organism")["snapshot"]
            if snap.get("chaos", "none") != "none" and "Crash" in (r.get("message") or ""):
                return "chaos"
        return "failed"

    def cross_checks(round_no):
        """Reads the manifest says agree with each other. No knowledge of
        what was written -- only of what the reads mean."""
        cc = per.setdefault("_cross_checks", dict((b, 0) for b in BUCKETS))

        def call(action, **args):
            r = execute(dict(action=action), args)
            if r.get("ok"):
                cc["driven"] += 1
            else:
                cc["failed"] += 1
                broken.append("round %d: cross-check %s %s -> %s %s"
                              % (round_no, action, args, r.get("code"), (r.get("message") or "")[:80]))
                r = {"ok": False, "output": {}, "snapshot": wire.op("observe", plugin="csrbt-organism")["snapshot"]}
            return r
        r = call("quiesce", ms=15000)
        snap = r["snapshot"]
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
                broken.append("round %d: %s = %s but snapshot size = %s" % (round_no, k, v, size))
        g = call("generations")["output"].get("generations", [])
        if len(g) != snap["generations"]:
            broken.append("round %d: generations %s vs snapshot %s" % (round_no, g, snap["generations"]))
        segs = call("segments")["output"].get("segments", [])
        if len(segs) != snap["segments"] or sum(x["garbageBytes"] for x in segs) != snap["garbageBytes"]:
            broken.append("round %d: segments do not account for the snapshot" % round_no)
        fl = call("fleet")["output"].get("replicas", [])
        if not fl or fl[0]["lag"] != 0 or fl[0]["gapped"]:
            broken.append("round %d: fleet not caught up after quiesce: %s" % (round_no, fl))
        if call("report")["output"].get("report") != call("report")["output"].get("report"):
            broken.append("round %d: two physicals differ" % round_no)
        grp = call("groups", top=3)["output"]
        if grp and grp["groups"] > size or sum(x["total"] for x in grp["top"]) > size:
            broken.append("round %d: the fold counts more than the store holds" % round_no)

    t0 = time.time()
    for round_no in range(1, rounds + 1):
        order = list(tools)
        rnd.shuffle(order)
        for tool in order:
            if tool["name"] in unschemable:
                continue
            for i in range(per_round):
                tick = round_no * 100 + i
                try:
                    args = form(tool["inputSchema"], rnd, tick, pools)
                except Unschemable as e:
                    unschemable[tool["name"]] = str(e)
                    break
                r = execute(tool, args)
                b = bucket(tool, r)
                per[tool["name"]][b] += 1
                if b == "failed":
                    notes.append("%s %s -> %s: %s" % (tool["action"], json.dumps(args),
                                                       r.get("code"), (r.get("message") or "")[:100]))
                if r.get("code") == "unavailable":
                    raise RuntimeError("the organism went away: %s" % r.get("message"))
        cross_checks(round_no)
        say("round %d/%d  commands=%d  broken=%d" % (round_no, rounds, count["commands"], len(broken)))

    commands = count["commands"]
    totals = dict((b, sum(v[b] for v in per.values())) for b in BUCKETS)
    accounted = sum(totals.values())
    undriven = [t["name"] for t in tools if per[t["name"]]["driven"] == 0
                and t["name"] not in unschemable]
    return {
        "at": int(time.time()), "seed": seed, "rounds": rounds, "per_round": per_round,
        "protocolVersion": man["protocolVersion"],
        "tools": len(tools), "forbidden": forbidden,
        "commands": commands, "accounted": accounted,
        "identity": "holds" if accounted == commands else "UNACCOUNTED",
        "totals": totals, "per_action": per,
        "undriven": undriven, "unschemable": unschemable,
        "invariants_broken": broken, "failures": notes,
        "seconds": round(time.time() - t0, 1),
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--per-round", type=int, default=3)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--organism-seed", type=int, default=42)
    ap.add_argument("--no-ledger", action="store_true")
    a = ap.parse_args(argv)

    token = "walk-" + secrets.token_urlsafe(24)
    try:
        wire = Wire(token, seed=a.organism_seed)
        hello = wire.op("discover")
    except Exception as e:
        print("cannot start the transport: %s" % e)
        return 2
    if not hello.get("ok"):
        print("the transport refused discovery: %s" % hello)
        return 2
    try:
        res = walk(wire, rounds=a.rounds, seed=a.seed, per_round=a.per_round, log=print)
    finally:
        wire.close()

    print("")
    print("%-30s %7s %7s %8s %6s %6s" % ("action", "driven", "refused", "declined", "chaos", "failed"))
    for name in sorted(res["per_action"]):
        c = res["per_action"][name]
        print("%-30s %7d %7d %8d %6d %6d" % (name, c["driven"], c["refused"], c["declined"], c["chaos"], c["failed"]))
    t = res["totals"]
    print("%-30s %7d %7d %8d %6d %6d" % ("total", t["driven"], t["refused"], t["declined"], t["chaos"], t["failed"]))
    print("")
    print("commands %d == accounted %d: %s" % (res["commands"], res["accounted"], res["identity"]))
    print("tools %d, undriven %s, unschemable %s" % (res["tools"], res["undriven"] or "none",
                                                     res["unschemable"] or "none"))
    print("invariants broken: %d" % len(res["invariants_broken"]))
    for b in res["invariants_broken"][:10]:
        print("  " + b)
    for f in res["failures"][:10]:
        print("  FAILED " + f)
    if not a.no_ledger:
        json.dump(res, io.open(LEDGER, "w", encoding="utf-8"), indent=1, sort_keys=True)
        print("wrote %s" % LEDGER)
    bad = (res["identity"] != "holds" or res["undriven"] or res["unschemable"]
           or res["invariants_broken"] or t["failed"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
