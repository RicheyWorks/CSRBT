# -*- coding: utf-8 -*-
"""The organism behind the contract: is the harness target-neutral, and does
the organism do what it says when driven through it?

Two questions, one suite, because the second is the only evidence for the
first. ADR-112 adds a second plugin to a contract that had one, and a second
plugin proves nothing until something drives it the way the swarm drives the
pages: every observation and every action a command through the gateway, with
a request id, against a policy it names.

  A. the descriptor, the manifest, and the transport -- no engine needed
  B. policy: the default rung refuses writes and reads, and a refused command
     never reaches the organism (its meters say so)
  C. redaction: a snapshot carries meters and never a record
  D. the differential oracle: a seeded sequence of writes by every route
     (direct, wire, Twine batch), mirrored in a dict, then every read the
     plugin publishes compared against the mirror
  E. replay: a replayed put is served from the cache and writes nothing
  F. history: cold-scan(gen) == the moment preserve was pressed, and stays
     so after the store moves on
  G. refusals: the boundary and the target both refuse, with the right code,
     and a refused write leaves no trace
  H. the physical never changes the patient
  K. (ADR-113) every read over the wire equals the same read direct
  L. order statistics -- CSRBT's own reads -- against the sorted mirror
  M. Carver over the SPAN interval index against brute force
  N. Renderer's fold against the mirror's attr histogram
  O. Brine answers from the store once and from the cache after
  P. PitBoss: the fleet is caught up, the replica agrees, and survives a
     rebootstrap
  Q. DryAge: as-of reads the frozen moment; retain-newest ages the vault
  R. Jerky: the archive verifies and names its scan run
  S. SmokeHouse: segments account for the garbage; compact changes no read
  T. Twine: a clean journal has nothing to replay
  U. Rub: history grows by one per tick
  V. Sizzle: arm a crash by restart, watch a batch fail, restart clean, read
     the batch back whole -- the recovery road through the gateway
  I. a dead console is `unavailable`, never a hang and never `failed`
  J. the stdio transport serves the organism with no change below its parser

WHAT UNVERIFIED MEANS HERE
    B-J need the engine built: `./gradlew harnessClasspath` in WholeHog, a
    sibling of this repo (or CSRBT_WHOLEHOG). Where it is not, those sections
    are counted and printed NOT VERIFIED, the discipline verify_engine_sessions
    set: a suite that cannot reach its subject says so rather than passing.

Run:  python3 tools/verify/verify_organism.py
"""
import io, json, os, random, subprocess, sys, time

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness_contract as C
import harness_plugin_organism as O
from harness_plugin_page import PagePlugin

P = F = 0
unverified = []
TOKEN = "organism-suite-" + "x" * 20
_rid = [0]


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


def rid():
    _rid[0] += 1
    return "r%d" % _rid[0]


def gw_for(plugin, **allow):
    pol = C.Policy(token=TOKEN, enabled=True, allow=allow or None)
    return C.Gateway(C.Registry([plugin]), pol)


def run(gw, action, **args):
    return gw.execute(TOKEN, O.OrganismPlugin.ID,
                      {"request_id": rid(), "action": action, "arguments": args})


def refused(fn, code):
    try:
        fn()
    except C.HarnessError as e:
        return e.code == code, e.code
    return False, "no refusal"


# ---- A. descriptor, manifest, transport source ---------------------------
plug = O.OrganismPlugin()          # no console yet: the descriptor is static
d = plug.descriptor()
ck(C.SLUG.match(d.id) and d.id == "csrbt-organism", "plugin id is a slug")
names = [a.name for a in d.actions]
ck(len(names) == len(set(names)) and len(names) >= 33,
   "%d distinct actions" % len(names))
ck(all(a.risk in C.RISKS for a in d.actions), "every action declares a risk")
ck(not any(a.risk == "DESTRUCTIVE" for a in d.actions),
   "no action is DESTRUCTIVE: the organism has no generic press, so the rung "
   "the page plugin needs is left empty rather than filled for symmetry")
ck({a.name for a in d.actions if a.risk == "MUTATE"} ==
   {"put", "delete", "batch", "preserve", "rebootstrap", "retain-newest",
    "compact", "recover"},
   "exactly the eight actions that change what is on disk are MUTATE")
ck({a.name for a in d.actions if a.risk == "SENSITIVE_READ"} ==
   {"get", "contains", "range", "count-range", "query", "cold-scan", "order",
    "depth", "overlap", "stab", "groups", "cache-get", "replica-get", "as-of"},
   "everything that returns a key, a value or an aggregate over named keys is "
   "SENSITIVE_READ -- 'does key 5 exist' is data about the data")
ck({a.name for a in d.actions if a.risk == "READ"} ==
   {"report", "pulse", "fleet", "generations", "verify-archive", "archive-names",
    "segments", "history"},
   "READ is meters, lags, generation numbers, archive entry names, segment "
   "sizes and a CRC verdict: never a key, never a value")
ck({a.name for a in d.actions if a.risk == "NAVIGATE"} == {"tick", "quiesce", "restart"},
   "tick, quiesce and restart are NAVIGATE: they move an instrument or reopen, "
   "and change no record")
def _arg(action, name):
    return [a for a in d.action(action).arguments if a.name == name][0]
ck(_arg("range", "cap").maximum == O.RANGE_CAP and _arg("put", "attr").maximum == 999 and
   _arg("put", "end").maximum == 99_999 and _arg("quiesce", "ms").maximum == 30_000 and
   _arg("restart", "latency-ms").maximum == 5000 and _arg("groups", "top").minimum == 1 and
   _arg("overlap", "hi").maximum == 99_999 and _arg("query", "attr-hi").maximum == 999,
   "every bounded integer publishes its bound in the manifest (ADR-114)")
ck(_arg("batch", "ops").pattern == O.BATCH_OP.pattern and len(_arg("batch", "ops").examples) >= 2 and
   _arg("restart", "chaos").pattern == O.CHAOS.pattern and "once:2" in _arg("restart", "chaos").examples,
   "the two string grammars are published as patterns WITH examples")
ck(len(_arg("put", "key").examples) >= 5 and _arg("cold-scan", "generation").examples,
   "unbounded keys and generations carry example values, so a schema-driven "
   "client has a pool to draw from without guessing the domain")
ck(all(any(a.name == "via" for a in d.action(n).arguments)
       for n in ("get", "contains", "range", "count-range", "order", "put", "delete")),
   "every read that the wire can answer takes via, the same way the writes do")
ENGINES = {"CSRBT": ("order", "depth"), "SmokeSignal": ("get",), "Carver": ("query", "overlap", "stab"),
           "Renderer": ("groups",), "Brine": ("cache-get",),
           "PitBoss": ("fleet", "replica-get", "rebootstrap"),
           "DryAge": ("generations", "as-of", "retain-newest", "preserve"),
           "Jerky": ("verify-archive", "archive-names", "cold-scan"),
           "SmokeHouse": ("compact", "segments"), "Twine": ("batch", "recover"),
           "Rub": ("tick", "pulse", "history", "report"), "Sizzle": ("restart",)}
ck(all(n in names for acts in ENGINES.values() for n in acts),
   "every engine in the organism is reachable by name through the manifest: %s"
   % sorted(ENGINES))
ck(all(len(a.description) > 15 for a in d.actions), "every action says what it does")
batch = d.action("batch")
ck(batch.arguments[0].type == "array" and batch.arguments[0].items == "string",
   "batch ops are a typed array so an adapter can build the schema")
put = d.action("put")
ck([a.name for a in put.arguments] == ["key", "attr", "start", "end", "via"] and
   put.arguments[4].enum == O.VIA,
   "a write's route is an argument with an enum, not a separate action")

page_desc = PagePlugin(None, None).descriptor()
both = C.Gateway(C.Registry([plug, PagePlugin(None, None)]),
                 C.Policy(token=TOKEN, enabled=True))
man = both.manifest(TOKEN)
tools = [t["name"] for t in man["tools"]]
ck({p["id"] for p in man["plugins"]} == {"csrbt-organism", "csrbt-page"},
   "one manifest publishes both targets")
ck(len(tools) == len(set(tools)) and
   len(tools) == len(d.actions) + len(page_desc.actions),
   "tool names stay distinct across two plugins: %d" % len(tools))
ck(all(C.TOOL_NAME_OK.match(t) and len(t) <= 64 for t in tools),
   "and every one is provider-safe")
ck(all(t["allowed"] is False for t in man["tools"]
       if t["risk"] in ("MUTATE", "SENSITIVE_READ")),
   "the default policy marks every write and every record read of the "
   "organism as not allowed, in the manifest an adapter bootstraps from")

stdio_src = io.open(os.path.join(_kit.TOOLS_DIR, "harness_stdio.py"),
                    encoding="utf-8").read()
serve_src = stdio_src[stdio_src.index("def serve("):stdio_src.index("def _w(")]
ck("organism" not in serve_src and "page" not in serve_src.replace("plugin", ""),
   "the transport's serve() names no target: nothing below the argument "
   "parser knows which it got")
ck("--target" in stdio_src and "OrganismPlugin" in stdio_src,
   "and the parser offers the organism")

# ---- the engine ------------------------------------------------------------
CP = O.classpath()
ENGINE = [
    "B  the default policy refuses writes and record reads and the refusal never reaches the organism",
    "C  a snapshot is meters only unless SENSITIVE_READ is open",
    "D  every write route lands: the differential oracle against a mirror",
    "E  a replayed put is served from the cache and writes nothing",
    "F  cold-scan equals the preserved moment and keeps equalling it",
    "G  boundary and target both refuse, with the right code, leaving no trace",
    "H  the physical never changes the patient",
    "I  a dead console is unavailable -- not a hang, not a failure of the target",
    "J  the stdio transport serves the organism unchanged",
]
if CP is None:
    for e in ENGINE:
        unverified.append(e + " -- WholeHog is not built: ./gradlew harnessClasspath in "
                          + os.path.normpath(O.wholehog_dir()))
else:
    plug = O.OrganismPlugin(seed=7)
    snap0 = plug.observe()
    ck(snap0.get("ready") and snap0.get("size") == 0 and snap0.get("target") == "organism",
       "the organism stands up and reports an empty store: %r" % snap0.get("why"))
    hello = plug.console.hello
    ck(hello.get("protocol") == "1.0" and hello.get("seed") == 7,
       "the console announces its protocol and seed")

    # ---- B. policy ----
    gw = gw_for(plug)                                   # READ + NAVIGATE only
    ok_, code = refused(lambda: run(gw, "put", key=1, attr=1, start=1, end=2), "forbidden")
    ck(ok_, "put is refused by default: %s" % code)
    ok_, code = refused(lambda: run(gw, "put", key=1, attr=1, start=1, end=2, via="wire"),
                        "forbidden")
    ck(ok_, "put over the wire is refused by default: %s" % code)
    ok_, code = refused(lambda: run(gw, "get", key=1), "forbidden")
    ck(ok_, "get is refused by default: %s" % code)
    ok_, code = refused(lambda: run(gw, "batch", ops=["p 1 1 1 1"]), "forbidden")
    ck(ok_, "batch is refused by default: %s" % code)
    s = plug.observe()
    ck(s["size"] == 0 and s["wire"]["puts"] == 0 and s["wire"]["connectionsAccepted"] == 0
       and s["twine"]["batchesCommitted"] == 0 and s["tailSequence"] == 0,
       "and none of it reached the organism: the store, the wire and the "
       "journal all still read zero")
    r = run(gw, "report")
    ck(r["ok"] and r["risk"] == "READ" and len(r["output"]["lines"]) >= 5,
       "report is allowed by default and reads every engine's meter line")
    r = run(gw, "tick")
    ck(r["ok"] and r["risk"] == "NAVIGATE", "tick is allowed by default")
    ck(r["snapshot"]["size"] == 0 and "sample" not in r["snapshot"],
       "every response carries a snapshot, redacted under the same policy")

    # ---- C. redaction ----
    def keys_of(x):
        """Every key name in a nested object. The first draft grepped the JSON
        text for 'records' and failed on the redaction NOTICE, which says the
        word: a check right about what it matched and wrong about what the
        match meant, in a file about exactly that."""
        if isinstance(x, dict):
            return set(x) | set().union(*(keys_of(v) for v in x.values()))
        if isinstance(x, list):
            return set().union(*(keys_of(v) for v in x)) if x else set()
        return set()
    s = plug.observe(sensitive=False)
    ck(not ({"sample", "records", "value", "key"} & keys_of(s)) and "redacted" in s,
       "a plain snapshot carries no record field and says so: %s" % sorted(keys_of(s))[:8])
    gwS = gw_for(plug, SENSITIVE_READ=True)
    s = gwS.observe(TOKEN, plug.ID)
    ck("sample" in s and s["sample"]["records"] == [] and s["sensitive"] is True,
       "a sensitive snapshot carries the sample, empty on an empty store")

    # ---- D. the differential oracle ----
    gwW = gw_for(plug, SENSITIVE_READ=True, MUTATE=True)
    rnd = random.Random(2026_09_01)
    model = {}
    routes = {"direct": 0, "wire": 0, "batch": 0}
    for _ in range(160):
        roll = rnd.random()
        if roll < 0.10:
            ops, mirror = [], []
            for _ in range(rnd.randint(1, 4)):
                k = rnd.randint(0, 120)
                if rnd.random() < 0.3:
                    ops.append("d %d" % k); mirror.append(("d", k, None))
                else:
                    v = (rnd.randint(0, 7), rnd.randint(0, 999), rnd.randint(1000, 1999))
                    ops.append("p %d %d %d %d" % ((k,) + v)); mirror.append(("p", k, v))
            r = run(gwW, "batch", ops=ops)
            ck(r["ok"], "batch committed: %s" % r["message"])
            for op, k, v in mirror:
                if op == "p":
                    model[k] = v
                else:
                    model.pop(k, None)
            routes["batch"] += 1
        elif roll < 0.30:
            k = rnd.randint(0, 120)
            via = rnd.choice(O.VIA)
            r = run(gwW, "delete", key=k, via=via)
            ck(r["ok"] and r["output"]["existed"] == (k in model),
               "delete %d via %s reports existed=%s, mirror says %s"
               % (k, via, r["output"]["existed"], k in model))
            model.pop(k, None)
            routes[via] += 1
        else:
            k = rnd.randint(0, 120)
            v = (rnd.randint(0, 7), rnd.randint(0, 999), rnd.randint(1000, 1999))
            via = rnd.choice(O.VIA)
            r = run(gwW, "put", key=k, attr=v[0], start=v[1], end=v[2], via=via)
            ck(r["ok"], "put %d via %s" % (k, via))
            model[k] = v
            routes[via] += 1
    ck(all(n > 0 for n in routes.values()), "every route was used: %s" % routes)
    w0 = plug.observe()["wire"]["puts"]
    r = run(gwW, "put", key=60, attr=1, start=1, end=2)           # no via named
    model[60] = (1, 1, 2)
    ck(r["output"]["via"] == "direct" and plug.observe()["wire"]["puts"] == w0,
       "a put that names no route goes direct, and the wire's meter agrees "
       "(a mutant that defaulted to wire survived until this line)")
    r = run(gwW, "quiesce", ms=15000)
    ck(r["ok"], "every tail consumer caught up: %s" % r["message"])
    s = plug.observe()
    ck(s["size"] == len(model), "size %d == mirror %d" % (s["size"], len(model)))
    ck(s["wire"]["puts"] + s["wire"]["deletes"] == routes["wire"] and
       s["twine"]["batchesCommitted"] == routes["batch"],
       "the wire and the journal metered exactly the traffic sent their way: %s vs %s"
       % ({"wire": s["wire"]["puts"] + s["wire"]["deletes"],
           "batch": s["twine"]["batchesCommitted"]}, routes))
    ck(s["rub"]["liveKeys"] == len(model) and s["replica"]["liveKeys"] == len(model),
       "Rub on the primary and Rub on the replica both count the mirror's keys")
    miss = []
    for k in sorted(model):
        r = run(gwW, "get", key=k)
        got = r["output"].get("value")
        if not (r["output"]["found"] and
                (got["attr"], got["start"], got["end"]) == model[k]):
            miss.append(k)
    ck(not miss, "every mirrored key reads back with its last value: misses %s" % miss[:5])
    absent = [k for k in range(0, 121) if k not in model][:15]
    ck(all(not run(gwW, "contains", key=k)["output"]["found"] for k in absent),
       "every absent key is absent")
    r = run(gwW, "range", lo=0, hi=120)
    got = [(x["key"], (x["value"]["attr"], x["value"]["start"], x["value"]["end"]))
           for x in r["output"]["records"]]
    ck(got == sorted(model.items()) and not r["output"]["truncated"],
       "a full range returns the mirror in key order")
    r = run(gwW, "range", lo=0, hi=120, cap=3)
    ck(len(r["output"]["records"]) == 3 and r["output"]["truncated"] and
       r["output"]["count"] == len(model),
       "a capped range says truncated and still reports the true count")
    bad = []
    for _ in range(12):
        lo = rnd.randint(0, 120); hi = rnd.randint(lo, 120)
        want = sum(1 for k in model if lo <= k <= hi)
        got = run(gwW, "count-range", lo=lo, hi=hi)["output"]["count"]
        if got != want:
            bad.append((lo, hi, got, want))
    ck(not bad, "count-range agrees with the mirror on 12 random windows: %s" % bad)
    bad = []
    for _ in range(8):
        lo = rnd.randint(0, 120); hi = rnd.randint(lo, 120)
        alo = rnd.randint(0, 7); ahi = rnd.randint(alo, 7)
        want = sorted(k for k, v in model.items() if lo <= k <= hi and alo <= v[0] <= ahi)
        r = run(gwW, "query", lo=lo, hi=hi, **{"attr-lo": alo, "attr-hi": ahi})
        if sorted(r["output"]["keys"]) != want or r["output"]["count"] != len(want):
            bad.append((lo, hi, alo, ahi, sorted(r["output"]["keys"]), want))
    ck(not bad, "Carver's plan over the secondary index agrees with brute force on "
       "8 random attribute windows: %s" % bad[:2])
    ck("drive" in r["output"]["plan"], "and the plan it chose is published: %r" % r["output"]["plan"])
    s = gwW.observe(TOKEN, plug.ID)
    ck(s["sample"]["truncated"] == (len(model) > O.SAMPLE_CAP) and
       len(s["sample"]["records"]) == min(O.SAMPLE_CAP, len(model)) and
       s["sample"]["medianKey"] == sorted(model)[(len(model) - 1) // 2],
       "the sensitive sample is capped, says so, and its median is the mirror's")

    # ---- E. replay ----
    newk = max(model) + 100
    before = plug.observe()
    r1 = run(gwW, "put", key=newk, attr=1, start=2, end=3)
    mid = plug.observe()
    r2 = gwW.execute(TOKEN, plug.ID, {"request_id": r1["requestId"], "action": "put",
                                       "arguments": {"key": newk, "attr": 1, "start": 2, "end": 3}})
    after = plug.observe()
    ck(r2["replayed"] is True and not r1["replayed"], "the second send is a replay")
    ck(mid["size"] == before["size"] + 1 and after["size"] == mid["size"] and
       after["tailSequence"] == mid["tailSequence"],
       "and it wrote nothing: size and tail sequence unchanged (%d -> %d -> %d)"
       % (before["size"], mid["size"], after["size"]))
    model[newk] = (1, 2, 3)
    ok_, code = refused(lambda: gwW.execute(TOKEN, plug.ID, {
        "request_id": r1["requestId"], "action": "put",
        "arguments": {"key": newk, "attr": 9, "start": 2, "end": 3}}), "conflict")
    ck(ok_, "the same id with a different body is a conflict: %s" % code)
    rG = run(gwW, "get", key=newk)
    # a replay is re-authorised on the gateway that cached it
    gwW.policy.allow["SENSITIVE_READ"] = False
    ok_, code = refused(lambda: gwW.execute(TOKEN, plug.ID, {
        "request_id": rG["requestId"], "action": "get", "arguments": {"key": newk}}),
        "forbidden")
    gwW.policy.allow["SENSITIVE_READ"] = True
    ck(ok_, "a cached record read stops flowing once the gate closes: %s" % code)

    # ---- F. history ----
    r = run(gwW, "preserve")
    gen = r["output"]["generation"]
    frozen = dict(model)
    moment = plug.observe()["size"]
    ck(r["ok"] and r["snapshot"]["generations"] == 1 and moment == len(model),
       "preserve returns generation %d and the vault holds one" % gen)
    r = run(gwW, "cold-scan", generation=gen)
    ck(r["output"]["records"] == moment,
       "cold-scan streams %d records == the moment (%d), no store resurrected"
       % (r["output"]["records"], moment))
    for k in range(500, 520):
        run(gwW, "put", key=k, attr=2, start=1, end=2)
        model[k] = (2, 1, 2)
    run(gwW, "delete", key=min(model))
    model.pop(min(model))
    now = plug.observe()["size"]
    r = run(gwW, "cold-scan", generation=gen)
    ck(now != moment and r["output"]["records"] == moment,
       "the store moved on (%d) and the archive still reads the moment (%d)"
       % (now, r["output"]["records"]))
    ok_, code = refused(lambda: run(gwW, "cold-scan", generation=gen + 40), "not_found")
    ck(ok_, "a generation that was never preserved is not_found: %s" % code)

    # ---- G. refusals ----
    s0 = plug.observe()
    ok_, code = refused(lambda: run(gwW, "put", key=1, attr=1, start=1, end=2, via="teleport"),
                        "invalid_argument")
    ck(ok_, "an unknown route is refused at the boundary: %s" % code)
    ok_, code = refused(lambda: run(gwW, "put", key="one", attr=1, start=1, end=2),
                        "invalid_argument")
    ck(ok_, "a key that is not an integer is refused at the boundary: %s" % code)
    ok_, code = refused(lambda: run(gwW, "put", key=1, attr=1000, start=1, end=2),
                        "invalid_argument")
    ck(ok_, "an attribute outside the organism's domain is refused BY THE TARGET, "
       "which keeps its own rules: %s" % code)
    ok_, code = refused(lambda: run(gwW, "put", key=1, attr=1, start=9, end=1, via="wire"),
                        "invalid_argument")
    ck(ok_, "a span with start > end is invalid_argument OVER THE WIRE too -- the first robot "
       "found it answered failed on that route and invalid_argument on the other: %s" % code)
    ok_, code = refused(lambda: run(gwW, "order", kind="nth", arg=10_000, via="wire"), "invalid_argument")
    ck(ok_, "and so is a rank past the size over the wire: %s" % code)
    ok_, code = refused(lambda: run(gwW, "range", lo=9, hi=1), "invalid_argument")
    ck(ok_, "range with lo > hi is refused by the target: %s" % code)
    ok_, code = refused(lambda: run(gwW, "range", lo=1, hi=9, cap=0), "invalid_argument")
    ck(ok_, "a zero cap is refused: %s" % code)
    ok_, code = refused(lambda: run(gwW, "range", lo=1, hi=9, cap=O.RANGE_CAP + 300),
                        "invalid_argument")
    ck(ok_, "a cap past the published %d is refused by the PLUGIN -- the console "
       "accepts up to 1000, so this one is the boundary's own rule: %s" % (O.RANGE_CAP, code))
    ok_, code = refused(lambda: run(gwW, "batch", ops=[]), "invalid_argument")
    ck(ok_, "an empty batch is not a batch: %s" % code)
    ok_, code = refused(lambda: run(gwW, "batch", ops=["p 1 1 1 1", "zap 3"]),
                        "invalid_argument")
    ck(ok_, "a malformed batch op is refused before the journal sees any of it: %s" % code)
    ok_, code = refused(lambda: run(gwW, "put", key=1, attr=1, start=1, end=2, extra=1),
                        "invalid_argument")
    ck(ok_, "an argument the action does not declare is refused: %s" % code)
    ok_, code = refused(lambda: run(gwW, "quiesce", ms=99999), "invalid_argument")
    ck(ok_, "a quiesce past the cap is refused: %s" % code)
    s1 = plug.observe()
    ck(s1["size"] == s0["size"] and s1["tailSequence"] == s0["tailSequence"] and
       s1["twine"]["batchesCommitted"] == s0["twine"]["batchesCommitted"] and
       s1["wire"]["puts"] == s0["wire"]["puts"],
       "and none of the nine refused writes left a trace on any meter")

    # ---- H. the physical ----
    a = run(gwW, "report")["output"]["report"]
    b = run(gwW, "report")["output"]["report"]
    ck(a == b, "two consecutive physicals are identical through the gateway")
    run(gwW, "tick")
    r = run(gwW, "pulse")
    ck(r["ok"] and r["output"]["pulse"] is not None, "after a second tick there is a pulse")
    s = gwW.observe(TOKEN, plug.ID)
    ck(s["argumentPools"]["generation"] == run(gwW, "generations")["output"]["generations"],
       "the snapshot publishes the generations that exist right now as an argument pool "
       "(ADR-114), so a manifest-only client can form an as-of it will not be refused")

    # ---- K. the wire agrees with the store ----
    keys_live = sorted(model)
    sample_keys = keys_live[::max(1, len(keys_live) // 10)][:10] + [999]
    same = all(run(gwW, "get", key=k, via="wire")["output"].get("value") ==
               run(gwW, "get", key=k, via="direct")["output"].get("value")
               for k in sample_keys)
    ck(same, "get over the wire equals get direct on %d keys (one absent)" % len(sample_keys))
    r = run(gwW, "range", lo=0, hi=999, via="wire")
    rd = run(gwW, "range", lo=0, hi=999, via="direct")
    ck(r["output"]["records"] == rd["output"]["records"] and r["output"]["via"] == "wire",
       "a full range over the wire is the same records in the same order")
    same = all(run(gwW, "count-range", lo=lo, hi=hi, via="wire")["output"]["count"] ==
               run(gwW, "count-range", lo=lo, hi=hi, via="direct")["output"]["count"]
               for lo, hi in ((0, 50), (30, 120), (500, 600), (0, 999)))
    ck(same, "count-range over the wire equals direct on four windows")
    w = plug.observe()["wire"]
    ck(w["gets"] >= len(sample_keys) and w["rangeQueries"] >= 5,
       "and the wire's own meters counted them: gets=%d ranges=%d" % (w["gets"], w["rangeQueries"]))

    # ---- L. order statistics against the sorted mirror ----
    n = len(keys_live)
    def order(kind, arg=None, via="direct"):
        a = {"kind": kind, "via": via}
        if arg is not None:
            a["arg"] = arg
        return run(gwW, "order", **a)["output"]["answer"]
    ck(order("size") == n and order("first") == keys_live[0] and order("last") == keys_live[-1],
       "size, first and last are the mirror's")
    ck(order("median") == keys_live[(n - 1) // 2],
       "median is the lower median of the sorted mirror (%s)" % order("median"))
    ck(all(order("nth", r) == keys_live[r - 1] for r in (1, 2, n // 2, n)),
       "nth (1-based) selects the mirror's r-th key")
    ck(all(order("rank", k) == keys_live.index(k) + 1 for k in keys_live[::7]),
       "rank of a live key is its 1-based position")
    ck(order("percentile", 0) == keys_live[0] and order("percentile", 100) == keys_live[-1],
       "percentile 0 and 100 are the ends")
    ck(all(order(kind, None, "wire") == order(kind) for kind in ("size", "first", "last", "median")) and
       all(order(kind, 2, "wire") == order(kind, 2) for kind in ("nth", "rank", "percentile")),
       "every order statistic answers the same over the wire")
    ok_, code = refused(lambda: run(gwW, "order", kind="nth", arg=0), "invalid_argument")
    ck(ok_, "nth 0 is invalid_argument, not a crash: %s" % code)
    ok_, code = refused(lambda: run(gwW, "order", kind="nth", arg=n + 1), "invalid_argument")
    ck(ok_, "nth past the size is invalid_argument: %s" % code)
    ok_, code = refused(lambda: run(gwW, "order", kind="median", arg=3), "invalid_argument")
    ck(ok_, "an arg on a kind that takes none is refused at the boundary: %s" % code)
    ok_, code = refused(lambda: run(gwW, "order", kind="rank"), "invalid_argument")
    ck(ok_, "rank without a key is refused at the boundary: %s" % code)
    d_live = run(gwW, "depth", key=keys_live[0])["output"]
    d_gone = run(gwW, "depth", key=999)["output"]
    ck(d_live["depth"] >= 1 and d_live["live"] and d_gone["depth"] < 0 and not d_gone["live"],
       "depth is >= 1 for a live key and ~depth (negative) for an absent one: %d / %d"
       % (d_live["depth"], d_gone["depth"]))

    # ---- M. Carver over the interval index ----
    bad = []
    for _ in range(6):
        lo = rnd.randint(0, 1999); hi = rnd.randint(lo, 1999)
        want = sorted(k for k, v in model.items() if v[1] <= hi and v[2] >= lo)
        r = run(gwW, "overlap", lo=lo, hi=hi)
        if sorted(r["output"]["keys"]) != want:
            bad.append((lo, hi, sorted(r["output"]["keys"]), want))
    ck(not bad, "overlap agrees with brute force on 6 random spans: %s" % bad[:1])
    ck("INTERVAL" in r["output"]["plan"], "and Carver drove the interval index: %r" % r["output"]["plan"])
    bad = []
    for _ in range(6):
        pt = rnd.randint(0, 1999)
        want = sorted(k for k, v in model.items() if v[1] <= pt <= v[2])
        r = run(gwW, "stab", point=pt)
        if sorted(r["output"]["keys"]) != want:
            bad.append((pt, sorted(r["output"]["keys"]), want))
    ck(not bad, "stab agrees with brute force on 6 random points: %s" % bad[:1])
    ok_, code = refused(lambda: run(gwW, "overlap", lo=9, hi=1), "invalid_argument")
    ck(ok_, "overlap lo > hi is refused by the target: %s" % code)

    # ---- N. Renderer's fold ----
    run(gwW, "quiesce", ms=15000)
    hist = {}
    for v in model.values():
        hist[v[0]] = hist.get(v[0], 0) + 1
    r = run(gwW, "groups", top=3)["output"]
    top_want = sorted(hist.items(), key=lambda kv: (-kv[1], -kv[0]))[:3]
    ck(r["groups"] == len(hist), "groups == distinct attrs in the mirror (%d)" % len(hist))
    ck([(g["attr"], g["total"]) for g in r["top"]] == top_want and not r["gapped"],
       "top-3 by total matches the mirror's histogram, gap-free: %s" % r["top"])

    # ---- O. Brine ----
    k0 = keys_live[3]
    a = run(gwW, "cache-get", key=k0)["output"]
    b = run(gwW, "cache-get", key=k0)["output"]
    ck((a["value"]["attr"], a["value"]["start"], a["value"]["end"]) == model[k0] and
       b["value"] == a["value"], "Brine's answer is the mirror's, twice")
    ck(b["hit"] and not b["storeRead"] and a["champion"],
       "the second read is a cache hit under champion %s" % a["champion"])

    # ---- P. PitBoss ----
    f = run(gwW, "fleet")["output"]
    ck(len(f["replicas"]) == 1 and f["replicas"][0]["lag"] == 0 and not f["replicas"][0]["gapped"],
       "the fleet has one replica, caught up and gap-free: %s" % f["replicas"])
    same = all(run(gwW, "replica-get", key=k)["output"].get("value") ==
               run(gwW, "get", key=k)["output"].get("value") for k in sample_keys)
    ck(same, "the replica's store agrees with the primary on %d keys" % len(sample_keys))
    r = run(gwW, "rebootstrap")
    ck(r["ok"] and r["snapshot"]["replicaObserverDetached"] is True,
       "rebootstrap says the replica observer is now detached, in every snapshot")
    run(gwW, "put", key=777, attr=5, start=5, end=6); model[777] = (5, 5, 6); keys_live = sorted(model)
    run(gwW, "quiesce", ms=15000)
    f = run(gwW, "fleet")["output"]["replicas"][0]
    ck(run(gwW, "replica-get", key=777)["output"]["found"] and f["lag"] == 0 and
       not f["rebootstrapped"],
       "the reborn replica catches a later write, lag 0 -- and the tick's rebootstrapped "
       "flag stays false, because it reports what THE TICK did about a gap, not what a "
       "caller asked for (the first draft of this check read it the other way)")

    # ---- Q. DryAge ----
    r = run(gwW, "generations")["output"]
    ck(r["generations"] == [gen], "generations lists the one preserved: %s" % r["generations"])
    changed = keys_live[5]
    was = frozen[changed]
    run(gwW, "put", key=changed, attr=0, start=0, end=0); model[changed] = (0, 0, 0)
    a = run(gwW, "as-of", generation=gen, key=changed)["output"]
    ck((a["value"]["attr"], a["value"]["start"], a["value"]["end"]) == was and a["size"] == len(frozen),
       "as-of reads the frozen moment for a key changed since: %s then, %s now" % (was, model[changed]))
    a = run(gwW, "as-of", generation=gen, key=777)["output"]
    ck(not a["found"], "and a key written after the moment is not in it")
    gen2 = run(gwW, "preserve")["output"]["generation"]
    ck(run(gwW, "generations")["output"]["generations"] == [gen, gen2], "a second preserve, two generations")
    r = run(gwW, "retain-newest", count=1)["output"]
    ck(r["released"] == [gen] and run(gwW, "generations")["output"]["generations"] == [gen2],
       "retain-newest 1 releases the older generation and keeps the newest")
    ok_, code = refused(lambda: run(gwW, "as-of", generation=gen, key=changed), "not_found")
    ck(ok_, "as-of a released generation is not_found: %s" % code)

    # ---- R. Jerky ----
    r = run(gwW, "verify-archive", generation=gen2)
    ck(r["ok"] and r["output"]["verified"] is True and r["risk"] == "READ", "the archive verifies")
    r = run(gwW, "archive-names", generation=gen2)["output"]
    ck("scan.run" in r["names"] and any(x.startswith("manifest") for x in r["names"]),
       "and names its scan run and manifest: %s" % r["names"])
    ok_, code = refused(lambda: run(gwW, "archive-names", generation=gen2 + 50), "not_found")
    ck(ok_, "names of an archive never cured is not_found: %s" % code)

    # ---- S. SmokeHouse ----
    segs = run(gwW, "segments")["output"]["segments"]
    snap = plug.observe()
    ck(segs and sum(x["garbageBytes"] for x in segs) == snap["garbageBytes"] and
       sum(1 for x in segs if x["active"]) == 1 and len(segs) == snap["segments"],
       "segments account for the snapshot's garbage, one active: %d segment(s)" % len(segs))
    before = run(gwW, "range", lo=0, hi=999)["output"]["records"]
    r = run(gwW, "compact")["output"]
    after = run(gwW, "range", lo=0, hi=999)["output"]["records"]
    ck(r["garbageAfter"] <= r["garbageBefore"] and after == before,
       "compact reclaimed %d bytes (garbage %d -> %d) and changed no read"
       % (r["reclaimed"], r["garbageBefore"], r["garbageAfter"]))

    # ---- T. Twine ----
    r = run(gwW, "recover")["output"]
    ck(r["replayed"] is False, "a clean journal has nothing to replay")

    # ---- U. Rub ----
    h0 = len(run(gwW, "history")["output"]["history"])
    t = run(gwW, "tick")["output"]["vitals"]
    h = run(gwW, "history")["output"]["history"]
    ck(len(h) == h0 + 1 and h[-1] == t, "history grew by one and its last sample is the tick's")

    # ---- V. Sizzle: the recovery road ----
    size0 = plug.observe()["size"]
    r = run(gwW, "restart", chaos="once:2")
    ck(r["ok"] and r["risk"] == "NAVIGATE" and r["output"]["size"] == size0 and
       r["snapshot"]["chaos"] == "once:2" and r["snapshot"]["restarts"] == 1,
       "restart under once:2 reopens the same store (%d keys) with the plan armed" % size0)
    ok_, code = refused(lambda: run(gwW, "batch", ops=["p 900 1 1 1", "p 901 1 1 1", "p 902 1 1 1"]),
                        "failed")
    ck(ok_ and plug.observe()["chaosCrashes"] == 1,
       "a three-op batch crashes at op 2 and the snapshot counts one injected fault: %s" % code)
    ok_, code = refused(lambda: run(gwW, "batch", ops=["p 903 1 1 1"]), "conflict")
    ck(ok_, "a batch while the crashed one is still applying is a CONFLICT -- Twine's own "
       "rule, not the organism failing (the first robot filed it under failed): %s" % code)
    r = run(gwW, "restart")
    ck(r["output"]["chaos"] == "none" and r["output"]["journalReplays"] >= 1,
       "a clean restart replayed the journal: journalReplays=%d" % r["output"]["journalReplays"])
    for k in (900, 901, 902):
        model[k] = (1, 1, 1)
    run(gwW, "quiesce", ms=15000)
    got = [(x["key"], (x["value"]["attr"], x["value"]["start"], x["value"]["end"]))
           for x in run(gwW, "range", lo=0, hi=999)["output"]["records"]]
    ck(got == sorted(model.items()),
       "and the crashed batch is back whole, in every index, alongside everything else")
    ck(run(gwW, "groups", top=1)["output"]["groups"] == len({v[0] for v in model.values()}),
       "the Renderer fold replayed with it")
    ok_, code = refused(lambda: run(gwW, "restart", chaos="bogus"), "invalid_argument")
    ck(ok_, "an unknown plan is refused at the boundary: %s" % code)
    ok_, code = refused(lambda: run(gwW, "restart", **{"latency-ms": 9999}), "invalid_argument")
    ck(ok_, "a latency past the cap is refused: %s" % code)
    ck(plug.observe()["restarts"] == 2, "and neither refusal restarted anything")

    # ---- I. a dead console ----
    plug.console.proc.kill()
    plug.console.proc.wait(timeout=10)
    t0 = time.time()
    ok_, code = refused(lambda: run(gwW, "report"), "unavailable")
    dt = time.time() - t0
    ck(ok_ and dt < 10,
       "a killed console is reported unavailable in %.1fs, not as the target "
       "failing and not by hanging: %s" % (dt, code))
    s = gwW.observe(TOKEN, plug.ID)
    ck(s.get("ready") is False and "why" in s, "and observe says not ready, with why")
    t0 = time.time()
    ok_, code = refused(lambda: plug.console._recv(8.0), "unavailable")
    dt = time.time() - t0
    ck(ok_ and dt < 2,
       "the reader learns of the death from the pump's sentinel in %.2fs, not from "
       "its timeout -- so a console dying MID-request is not an 8s wait either" % dt)
    plug.close()

    # ---- J. the stdio transport ----
    env = dict(os.environ)
    env.update({"CSRBT_HARNESS_ENABLED": "true", "CSRBT_HARNESS_TOKEN": TOKEN,
                "CSRBT_HARNESS_ALLOW_MUTATE": "true"})
    lines = [
        {"op": "manifest", "token": "wrong-" + "w" * 20},
        {"op": "manifest", "token": TOKEN},
        {"op": "observe", "token": TOKEN, "plugin": "csrbt-organism"},
        {"op": "execute", "token": TOKEN, "plugin": "csrbt-organism",
         "command": {"request_id": "s1", "action": "put",
                     "arguments": {"key": 3, "attr": 1, "start": 1, "end": 2, "via": "wire"}}},
        {"op": "execute", "token": TOKEN, "plugin": "csrbt-organism",
         "command": {"request_id": "s2", "action": "get", "arguments": {"key": 3}}},
        {"op": "quit", "token": TOKEN},
    ]
    p = subprocess.run([sys.executable, os.path.join(_kit.TOOLS_DIR, "harness_stdio.py"),
                        "--target", "organism", "--seed", "3"],
                       input="\n".join(json.dumps(l) for l in lines) + "\n",
                       capture_output=True, text=True, env=env, timeout=180)
    outs = [json.loads(l) for l in p.stdout.strip().split("\n") if l.strip()]
    ck(p.returncode == 0 and len(outs) == 6,
       "the transport answered every line and exited clean: rc=%d n=%d %s"
       % (p.returncode, len(outs), p.stderr.strip()[-200:]))
    if len(outs) == 6:
        ck(outs[0]["ok"] is False and outs[0]["code"] == "unauthorized",
           "a wrong token is unauthorized on the wire")
        ck(outs[1]["ok"] and [x["id"] for x in outs[1]["manifest"]["plugins"]] == ["csrbt-organism"],
           "the manifest names the organism and nothing else")
        ck(outs[2]["ok"] and outs[2]["snapshot"]["size"] == 0, "observe over stdio")
        ck(outs[3]["ok"] and outs[3]["risk"] == "MUTATE" and outs[3]["snapshot"]["size"] == 1,
           "a wire put over stdio lands and the snapshot says so")
        ck(outs[4]["ok"] is False and outs[4]["code"] == "forbidden",
           "get is forbidden on this session: only MUTATE was opened")
        ck(outs[5]["ok"] and outs[5].get("message") == "bye", "quit")

total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
