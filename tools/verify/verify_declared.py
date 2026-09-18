# -*- coding: utf-8 -*-
"""The exemption reader: whether a written reason is still about anything (ADR-224).

tools/audit_declared.py gives every declaration in the kit's ledgers one of four
verdicts -- COVERING, IDLE, STALE, UNREAD -- and only the first passes. This
suite builds ledgers in which each verdict is the right one and requires the
audit to say so, count the kinds separately, exit non-zero, and print one
--forget line per failure and none for the pass. --forget is held to remove one
declaration, print its reason, refuse a key that was never declared, and leave
the page's reading untouched. Then the check a fixture cannot fake: the LIVE
ledgers obey the rule the six audits are held to -- filtered within raw within
seen, and raw minus filtered exactly the declared keys.

Run:  python3 tools/verify/verify_declared.py
"""
MUTATE_ROLE = "subject"
import contextlib, io, json, os, sys, tempfile, time

import _kit

TOOLS = _kit.TOOLS_DIR.rstrip(os.sep)
sys.path.insert(0, TOOLS)
import audit_declared as D
import exempt as X

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


NOW = int(time.time())
# The ledger's newest row is NOT now: a reading's age and its distance behind its
# own ledger are different numbers, and a fixture where they coincide cannot
# tell a reader that measures the wrong one from one that measures the right one.
TOP = NOW - 1000
tmp = tempfile.mkdtemp(prefix="declared_")


def put(name, state):
    io.open(os.path.join(tmp, name), "w", encoding="utf-8").write(json.dumps(state, indent=1) + "\n")


def row(raw, seen, filtered, declared, at=TOP, **more):
    r = {"raw": raw, "seen": seen, "lost": filtered, "at": at}
    if declared:
        r["declared"] = declared
    r.update(more)
    return r


# ---- A. one ledger, four verdicts ----------------------------------------------
put("carried_ledger.json", {"pages": {
    "covering.html": row(["a", "b"], ["a", "b", "c"], ["b"], {"a": "a is right to stay"}),
    "idle.html": row([], ["a", "b"], [], {"a": "a used to be lost"}),
    "stale.html": row([], ["b"], [], {"a": "a is gone"}),
    "old.html": row(["a"], ["a"], [], {"a": "read last week"}, at=TOP - D.FRESH - 1),
    "edge.html": row(["a"], ["a"], [], {"a": "read on the pass"}, at=TOP - D.FRESH),
    "blind.html": {"lost": [], "at": TOP, "declared": {"a": "no universe was recorded"}},
    "clean.html": row([], ["a"], [], {}),
}})
got = dict(((r["page"], r["key"]), r) for r in D.judge("carried", root=tmp))
ck(got[("covering.html", "a")]["verdict"] == "covering",
   "a key the audit still flags is COVERING: %s" % got.get(("covering.html", "a")))
ck(got[("idle.html", "a")]["verdict"] == "idle",
   "a key that is THERE and not flagged is IDLE -- the exemption is slack that would hide the "
   "defect coming back: %s" % got.get(("idle.html", "a")))
ck(got[("stale.html", "a")]["verdict"] == "stale",
   "a key that is not there at all is STALE -- its reason is about something that is gone: %s"
   % got.get(("stale.html", "a")))
ck(got[("idle.html", "a")]["verdict"] != got[("stale.html", "a")]["verdict"],
   "idle and stale are different verdicts, because they need different fixes")
ck(got[("old.html", "a")]["verdict"] == "unread" and got[("old.html", "a")]["behind"] == D.FRESH + 1,
   "A READING FROM AN EARLIER PASS IS NOT EVIDENCE: a row older than the newest row of its own "
   "ledger by more than the window is UNREAD, and BEHIND is measured against that newest row: %s"
   % got.get(("old.html", "a")))
ck(got[("edge.html", "a")]["verdict"] == "covering",
   "...and the window is inclusive, so a pass that takes exactly the window reads as taken")
ck(got[("blind.html", "a")]["verdict"] == "unread" and "raw/seen" in got[("blind.html", "a")]["why"],
   "an entry with no `seen` list cannot be judged, even when the key would be covering: %s"
   % got.get(("blind.html", "a")))
ck(("clean.html", None) not in got and all(r["page"] != "clean.html" for r in got.values()),
   "a page with no declaration has no row here")
put("carried_ledger.json", {"pages": {"gone.html": row([], [], [], {})}})
put("restored_ledger.json", {"pages": {"x.html": {"declared": {"k": "r"}, "lost": [], "at": NOW}}})
ck([r["verdict"] for r in D.judge("restored", root=tmp)] == ["unread"],
   "a row that holds a declaration and no reading at all is UNREAD, not stale: %s"
   % [r["why"] for r in D.judge("restored", root=tmp)])
put("restored_ledger.json", {"pages": {}})
put("takeaway_ledger.json", {"pages": {"y.html": {"declared": {"k": "r"}, "raw": [], "seen": [], "at": NOW}}})
ck([r["verdict"] for r in D.judge("takeaway", root=tmp)] == ["stale"],
   "a page whose row is there and names nothing by the key is STALE")
put("takeaway_ledger.json", {"pages": {}})
# a key that is in raw but the universe was never recorded still cannot be judged
put("destructive_ledger.json", {"pages": {"z.html": {"declared": {"k": "r"}, "raw": ["k"], "bare": [], "at": NOW}}})
ck([r["verdict"] for r in D.judge("destructive", root=tmp)] == ["unread"],
   "the raw list alone is not enough either: the universe is what tells idle from stale")
put("destructive_ledger.json", {"pages": {}})

# ---- B. the newest row is found whatever the ledger calls its rows --------------
ck(D.newest({"a": {"at": 5}, "b": {"at": 9}, "c": {"x": 1}, "d": "junk"}) == 9,
   "the newest reading is the largest `at` among the rows that have one")
ck(D.newest({}) is None, "and a ledger with no readings has no newest one")

# ---- C. two ratchets on one page keep two records --------------------------------
put("outputs_ledger.json", {"pages": {
    "two.html": {"raw": ["a"], "seen": ["a", "b"], "unread": [], "declared": {"a": "blind, and right"},
                 "mute_raw": ["m"], "mute_seen": ["m", "n"], "mute": [], "mute_declared": {"n": "quiet, and right"},
                 "trap": False, "buttons": 2, "at": NOW},
    "trap.html": {"trap": True, "buttons": 0, "no_outputs": "a page that takes nothing", "at": NOW},
    "grew.html": {"trap": False, "buttons": 1, "no_outputs": "it had none", "at": NOW},
    "fine.html": {"trap": False, "buttons": 0, "no_outputs": "under the bar now", "at": NOW},
}})
o = dict(((r["source"], r["page"], r["key"]), r["verdict"]) for r in D.judge(root=tmp)
         if r["source"].startswith("outputs"))
ck(o.get(("outputs", "two.html", "a")) == "covering" and o.get(("outputs-mute", "two.html", "n")) == "idle",
   "EACH RATCHET READS ITS OWN RAW LIST: `a` is covering by the blind ratchet's raw, and `n` is "
   "idle by the mute ratchet's -- a reader that took `raw` for both would call `n` stale: %s" % o)
ck(o.get(("outputs-page", "trap.html", None)) == "covering",
   "a page the audit still calls a data trap is COVERING for its whole-page declaration")
ck(o.get(("outputs-page", "grew.html", None)) == "stale",
   "A PAGE THAT HAS GROWN AN EXPORT IS NOT THE PAGE THE REASON WAS ABOUT: stale")
ck(o.get(("outputs-page", "fine.html", None)) == "idle",
   "a page that is no longer a trap and still hands nothing over is idle")

# ---- D. the sweep's ledger is not one pass ----------------------------------------
put("contention_ledger.json", {"suites": {
    "a beside b": {"failed": 1, "runs": 9, "declared": "a known race, ceiling 1", "at": NOW - 40 * 86400},
    "c beside d": {"failed": 0, "runs": 9, "declared": "it never fails now", "at": NOW},
}})
c = dict((r["page"], r) for r in D.judge("contend", root=tmp))
c.setdefault("a beside b", {}); c.setdefault("c beside d", {})
ck(c["a beside b"].get("verdict") == "covering" and c["a beside b"].get("behind") is None,
   "A LEDGER NOT WRITTEN IN ONE PASS GETS NO FRESHNESS TEST: a pairing forty days behind its "
   "ledger's newest row is judged on its reading, and BEHIND is not recorded: %s" % c["a beside b"])
ck(c["c beside d"].get("verdict") == "idle",
   "...and a pairing that no longer fails is idle: the declaration would hide it starting to")
ck(all(s.get("one_pass") is not None for s in D.SOURCES) and not D.source("contend")["one_pass"]
   and D.source("carried")["one_pass"],
   "which is which is stated per source, not decided in the reader")

# ---- E. the table, the exit code, the --forget lines ------------------------------
put("carried_ledger.json", {"pages": {
    "covering.html": row(["a"], ["a"], [], {"a": "still lost, and right"}),
    "stale.html": row([], [], [], {"gone": "was about a figure that is gone"}),
}})
# main() reads beside its own file; judge(root=) is the seam, so main is driven through a
# root switch for the fixture
D.HERE, _real = tmp, D.HERE
try:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = D.main(["--source", "carried"])
    said = buf.getvalue()
    ck(rc == 1, "G. A LEDGER WITH A BAD EXEMPTION IN IT FAILS. exit %s" % rc)
    ck("--forget carried:stale.html:gone" in said and "--forget carried:covering.html:a" not in said,
       "...one --forget line per failing declaration, and none for the pass:\n%s" % said)
    ck("was about a figure" in said, "...carrying the reason, because a reason is the only record")
    tail = said.strip().split("\n")[-1]
    ck("1 covering" in tail and "1 stale" in tail and "0 idle" in tail and "0 unread" in tail,
       "the tail counts each kind separately: %s" % tail)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = D.main(["--source", "carried", "--json"])
    js = json.loads(buf.getvalue())
    ck(rc == 1 and any(r["reason"] == "was about a figure that is gone" for r in js)
       and all("audit_carried.py --declare" in (r.get("declaredBy") or "") for r in js),
       "--json carries the reason and which --declare granted it, so the removal can be reasoned "
       "about: %s" % [(r["key"], r["verdict"]) for r in js])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = D.main(["--source", "restored"])
    ck(rc == 0 and "0 declaration(s)" in buf.getvalue(),
       "--source restored reads no carried declarations: %s" % buf.getvalue().strip().split("\n")[-1])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = D.main(["--source", "outputs"])
    ck(rc == 0, "--source outputs does NOT pick up outputs-mute or outputs-page: it matches exactly")
    ck(D.main(["--source", "nope"]) == 2, "a source that does not exist is refused and named")
    # a missing ledger is named, not skipped
    os.remove(os.path.join(tmp, "contention_ledger.json"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = D.main([])
    ck(rc == 1 and "no ledger at contention_ledger.json" in buf.getvalue(),
       "A LEDGER THAT IS NOT THERE IS NOT AN EMPTY ONE: its declarations cannot be judged, and "
       "the reader is told which ledger: %s" % [l for l in buf.getvalue().split("\n") if "no ledger" in l])
    put("contention_ledger.json", {"suites": {}})

    # ---- F. --forget --------------------------------------------------------------
    put("restored_ledger.json", {"pages": {"p.html": {
        "raw": ["box/a:b"], "seen": ["box/a:b", "j"], "lost": [], "at": NOW, "restored": True,
        "declared": {"box/a:b": "a key with a colon in it", "j": "a second one on the same page"}}}})
    ok, msg = D.forget("restored:p.html:box/a:b")
    led = json.load(io.open(os.path.join(tmp, "restored_ledger.json")))["pages"]["p.html"]
    ck(ok and "a key with a colon in it" in msg,
       "THE REMOVAL IS NOT SILENT: --forget prints the reason it removes. A KEY MAY CONTAIN A "
       "COLON, and a control's key in this kit often does -- only the first two are split on: %s" % msg)
    ck(led["declared"] == {"j": "a second one on the same page"},
       "...that one and no other: %s" % led["declared"])
    ck(led.get("raw") == ["box/a:b"] and led.get("restored") is True,
       "...while the reading itself is untouched: %s" % {k: led.get(k) for k in ("raw", "restored")})
    ok, msg = D.forget("restored:p.html:never")
    ck(not ok and "not declared" in msg,
       "...a key that is not declared is refused rather than reported as removed: %s" % msg)
    ok, msg = D.forget("restored:p.html:j")
    led = json.load(io.open(os.path.join(tmp, "restored_ledger.json")))["pages"]["p.html"]
    ck(ok and "declared" not in led and led.get("raw") == ["box/a:b"],
       "...and the last one removed takes the empty block with it, and nothing else: %s" % sorted(led))
    ok, msg = D.forget("restored")
    ck(not ok and "SOURCE:PAGE:KEY" in msg, "...and a spec with too few parts says the shape: %s" % msg)
    ok, msg = D.forget("nope:p.html:k")
    ck(not ok and "no source" in msg, "...so is a source that does not exist, and it lists them: %s" % msg)
    put("outputs_ledger.json", {"pages": {"t.html": {"trap": True, "buttons": 0, "at": NOW,
                                                     "no_outputs": "a whole-page reason"}}})
    ok, msg = D.forget("outputs-page:t.html:extra")
    ck(not ok and "whole subject" in msg, "a whole-subject source refuses a key: %s" % msg)
    ok, msg = D.forget("outputs-page:t.html")
    led = json.load(io.open(os.path.join(tmp, "outputs_ledger.json")))["pages"]["t.html"]
    ck(ok and "a whole-page reason" in msg and "no_outputs" not in led and led.get("trap") is True,
       "H. a page-level declaration is removed by name, printing its reason, and the reading stays: %s" % led)
    ok, msg = D.forget("carried:covering.html")
    ck(not ok and "KEY" in msg, "a key-level source refuses a spec with no key: %s" % msg)
finally:
    D.HERE = _real

# ---- G. the rule, against a ledger that filtered quietly --------------------------
put("carried_ledger.json", {"pages": {
    "quiet.html": {"raw": ["a", "b"], "seen": ["a", "b"], "lost": [], "declared": {"a": "r"}, "at": NOW},
    "honest.html": {"raw": ["a", "b"], "seen": ["a", "b", "c"], "lost": ["b"], "declared": {"a": "r"}, "at": NOW},
    "wide.html": {"raw": ["a", "z"], "seen": ["a"], "lost": ["z"], "at": NOW},
}})
bad = D.consistency(root=tmp)
ck(any("quiet.html" in b and "declared keys" in b for b in bad),
   "a row whose raw minus filtered is NOT its declared keys is a recording that silently stopped: %s" % bad)
ck(any("wide.html" in b and "not within seen" in b for b in bad), "raw outside seen is caught: %s" % bad)
ck(not any("honest.html" in b for b in bad), "and an honest row is not named")

# ---- H. THE LIVE LEDGERS obey the rule ---------------------------------------------
live = D.consistency()
ck(live == [], "THE CHECK THAT CANNOT BE FAKED WITH A FIXTURE: the kit's own ledgers obey filtered "
               "within raw within seen and raw minus filtered exactly the declared keys, so a "
               "recording that silently stops fails against the kit's own data: %s" % live[:4])
ck(X.apply({}, ["a"], {"a": "r"}, ["a", "b"]) == [] and X.apply({}, ["a", "b"], {"a": "r"}, []) == ["b"],
   "the shared rule filters by the declared keys")
_e = {}
X.apply(_e, ["a", "b"], {"a": "r"}, ["c"])
ck(_e.get("raw") == ["a", "b"] and _e.get("seen") == ["a", "b", "c"],
   "the shared rule records raw and seen in the same call that filters: %s" % _e)
try:
    X.declare({}, "p", "k", "   ")
    ck(False, "a declaration with no reason, or only whitespace, was accepted")
except ValueError:
    ck(True, "a declaration with no reason, or only whitespace, is refused at the one place it is granted")
ck(D.source("carried")["declare"] and all(s.get("declare") for s in D.SOURCES),
   "every source says how a declaration is granted, so --json can say who granted one")
_src = io.open(os.path.join(TOOLS, "audit_declared.py"), encoding="utf-8").read()
ck('"--declare"' not in _src and '"--forget"' in _src,
   "THIS AUDIT HAS NO --declare: an exemption mechanism on the audit that checks exemptions is "
   "the same defect one level up. It can only take a declaration away")

print("---")
print("%d/%d" % (P, P + F))
sys.exit(1 if F else 0)
