# -*- coding: utf-8 -*-
"""A control's name outlives pressing it (ADR-239).

Holds `tools/audit_addresses.py` and the door fix it found:

  1. classify() on readings stated here, one per verdict, so the verdicts are
     about the rule and not about whatever a page happens to do;
  2. a scratch page with one control of every shape -- a counter that rewrites
     its own label, a tally board that re-renders with the count in the name,
     a control that deletes itself, a key that moves to its next couplet, a
     control that inserts a namesake ahead of itself, a list that rebuilds
     under the same names, a button rebuilt under its id with a new label --
     walked by the audit itself, each read as what it is;
  3. THE DOOR: a press that rebuilds a list, then a NAME from the snapshot
     before it, with no observe between. Before ADR-239 the resolver read
     `data-h` stamps from the last observe, the rebuilt list had none, and a
     name the door had just published answered "no control answers to it";
  4. the real kit, from the ledger the audit writes: every page walked, none
     renamed, none shadowed, none unreadable, and the two pages the audit
     found (the field notebook's and the farm scout's tally cards) read by
     name after a press.

Run:  python3 tools/verify/verify_addresses.py
"""
# Declared for tools/mutate.py: this suite asserts about tools/audit_addresses.py.
MUTATE_ROLE = "subject"
import io, json, os, shutil, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import audit_addresses as A
import harness_plugin_page as PP

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


# ---- 1. the rule, on readings stated here -----------------------------------
B = {"host": "grid", "label": "apple3", "id": None, "address": "@grid/apple3"}
kept_same = {"kept": True, "resolvedIsMark": True, "address": "@grid/apple3", "hosts": []}
ck(A.classify(B, "action_btn:1", kept_same) == ("held", None),
   "the old name resolves to the node that was pressed: HELD")
ck(A.classify(B, "action_btn:0", {"kept": True, "resolvedIsMark": False, "address": "@grid/apple3#1",
                                  "hosts": []}) == ("shadowed", "@grid/apple3#1"),
   "the old name resolves to ANOTHER control while the pressed one is still there: SHADOWED, "
   "and says what the pressed one is called now")
ck(A.classify(B, None, {"kept": True, "label": "apple4", "address": "@grid/apple4", "hosts": []})
   == ("renamed", "@grid/apple4"),
   "the old name resolves to nothing and the pressed node is still there: RENAMED, with its new name")
ck(A.classify(B, None, {"kept": False, "hosts": [["grid", "apple4", "@grid/apple4"]]})
   == ("renamed", "@grid/apple4"),
   "rebuilt, and a control under the same host differs from the old name only in its digits: RENAMED")
ck(A.classify(B, None, {"kept": False, "hosts": [["other", "apple4", "@other/apple4"]]}) == ("gone", None),
   "...but not a namesake under another host")
ck(A.classify({"host": "key", "label": "gills", "id": None, "address": "@gills"}, None,
              {"kept": False, "hosts": [["key", "pores", "@pores"]]}) == ("gone", None),
   "a list rebuilt into other WORDS is gone, not renamed: those are different controls")
ck(A.classify({"host": "key", "label": "leaf 1", "id": None, "address": "@leaf 1"}, None,
              {"kept": False, "hosts": [["key", "stem 2", "@stem 2"]]}) == ("gone", None),
   "...even when both carry a digit, if the words differ")
ck(A.classify({"host": "grid", "label": "apple", "id": None, "address": "@apple"}, None,
              {"kept": False, "hosts": [["grid", "apple", "@apple"]]}) == ("gone", None),
   "a label with no digit cannot be a renamed count")
ck(A.classify({"host": "nav", "label": "#5 →", "id": "pNext", "address": "#pNext"}, "action_btn:9",
              {"kept": False, "resolvedIsMark": False, "resolvedId": "pNext", "resolvedHost": "nav",
               "resolvedLabel": "#6 →", "hosts": []}) == ("held", None),
   "a control rebuilt under the SAME ID is the same control, whatever it reads now: HELD")
ck(A.classify({"host": "nav", "label": "go", "id": None, "address": "@go"}, "action_btn:2",
              {"kept": False, "resolvedIsMark": False, "resolvedId": None, "resolvedHost": "elsewhere",
               "resolvedLabel": "go", "hosts": []}) == ("shadowed", None),
   "rebuilt, and the old name now lands under another host: SHADOWED")
ck(A.digitless("species-a12") == A.digitless("species-a3") != A.digitless("species-b3"),
   "digits are what is ignored, and only digits")

# ---- 2. a scratch page, walked by the audit ---------------------------------
FIXTURE = r"""<!doctype html><html><head><meta charset="utf-8"><title>fixture</title></head><body>
<div id="counter"><button type="button" id="cBtn0" onclick="this.textContent='clicks '+(++window.cn)">clicks 0</button></div>
<script>window.cn=0;</script>
<div id="stable"><button type="button" id="keep">keep me</button></div>
<div id="grid"></div>
<script>
var ts=[{n:"apple",c:0},{n:"pear",c:0}];
function tr(){ var g=document.getElementById("grid"); g.innerHTML="";
  ts.forEach(function(t){ var b=document.createElement("button"); b.type="button";
    b.innerHTML='<div class="name">'+t.n+'</div><div class="count">'+t.c+'</div>';
    b.onclick=function(){ t.c++; tr(); }; g.appendChild(b); }); }
tr();
</script>
<div id="named"></div>
<script>
var ns=[{n:"plum",c:0}];
function nr(){ var g=document.getElementById("named"); g.innerHTML="";
  ns.forEach(function(t){ var b=document.createElement("button"); b.type="button";
    b.innerHTML='<div class="nm">'+t.n+'</div><div class="count">'+t.c+'</div>';
    b.onclick=function(){ t.c++; nr(); }; g.appendChild(b); }); }
nr();
</script>
<div id="bin"><button type="button" onclick="this.remove()">remove me</button></div>
<div id="key"></div>
<script>
var kq=[["gills","pores"],["cap dry","cap slimy"]], ki=0;
function kr(){ var g=document.getElementById("key"); g.innerHTML="";
  kq[Math.min(ki,1)].forEach(function(w){ var b=document.createElement("button"); b.type="button";
    b.textContent=w; b.onclick=function(){ ki++; kr(); }; g.appendChild(b); }); }
kr();
</script>
<div id="twin"><button type="button" onclick="var b=document.createElement('button');b.type='button';b.textContent='echo';this.parentNode.insertBefore(b,this);">echo</button></div>
<div id="pick"></div>
<script>
function pr(){ var g=document.getElementById("pick"); g.innerHTML="";
  ["oak","ash"].forEach(function(w){ var b=document.createElement("button"); b.type="button";
    b.textContent=w; b.onclick=pr; g.appendChild(b); }); }
pr();
</script>
<div id="nav"></div>
<script>
var pn=5;
function navr(){ document.getElementById("nav").innerHTML='<button type="button" id="pNext">#'+pn+' →</button>';
  document.getElementById("pNext").onclick=function(){ pn++; navr(); }; }
navr();
</script>
</body></html>"""

tmp = tempfile.mkdtemp(prefix="addresses_")
try:
    io.open(os.path.join(tmp, "fixture.html"), "w", encoding="utf-8").write(FIXTURE)
    got = A.walk(["fixture.html"], docs=tmp)["fixture.html"]
    ck(not got.get("error"), "the fixture walks: %s" % got.get("error"))
    by = dict((r["address"], r) for r in got.get("rows", []))
    v = lambda a: (by.get(a) or {}).get("verdict")
    ck(v("#keep") == "held", "a stable button is HELD: %s" % v("#keep"))
    ck(v("#cBtn0") == "held",
       "a counter that rewrites its own label is still HELD by its id -- an id cannot carry a count: %s"
       % v("#cBtn0"))
    ck(v("@apple0") == "renamed" and by["@apple0"].get("now") == "@apple1",
       "A TALLY WHOSE NAME CARRIES ITS COUNT IS RENAMED, and says it is @apple1 now: %s" % by.get("@apple0"))
    ck(v("@pear0") == "renamed", "...and so is every card of that board: %s" % v("@pear0"))
    ck(v("@plum") == "held",
       "the same board with its name in a .nm is HELD -- the fix the two pages took: %s" % v("@plum"))
    ck(v("@remove me") == "gone", "a control that deletes itself is GONE: %s" % v("@remove me"))
    ck(v("@gills") == "gone", "a key that moves to its next couplet is GONE, not renamed: %s" % v("@gills"))
    ck(v("@echo") == "shadowed",
       "a control that puts a namesake ahead of itself is SHADOWED -- its old name now presses the other "
       "one: %s" % v("@echo"))
    ck(v("@oak") == "held",
       "a list that rebuilds under the same names is HELD, through the door's resolver: %s" % v("@oak"))
    ck(v("#pNext") == "held", "a button rebuilt under its id with a new label is HELD: %s" % v("#pNext"))
    ck(got["renamed"] == 2 and got["shadowed"] == 1 and got["pressed"] == got["held"] + got["gone"]
       + got["renamed"] + got["shadowed"],
       "the counts add up, and are the two renamed and the one shadowed: %s"
       % dict((k, got.get(k)) for k in ("pressed", "held", "gone", "renamed", "shadowed")))
    ck(A.problems({"fixture.html": got}) == ["fixture.html"] and A.problems({"x": {"renamed": 0, "shadowed": 0}}) == []
       and A.problems({"x": {"renamed": 0, "shadowed": 1}}) == ["x"]
       and A.problems({"x": {"renamed": 1, "shadowed": 0}}) == ["x"]
       and A.problems({"x": {"error": "boom"}}) == ["x"],
       "a page with a renamed or shadowed control, or that could not be walked, is a problem; a clear one is not")

    # ---- 3. the door: a name from BEFORE a rebuild, with no observe between --
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        pg.goto("file://" + os.path.join(tmp, "fixture.html").replace(os.sep, "/"), wait_until="domcontentloaded")
        pg.wait_for_timeout(200)
        plug = PP.PagePlugin(pg, "fixture.html")
        plug.observe()
        ok1 = plug.execute("activate", {"selector": "@pick/oak"})[0]
        try:
            ok2, msg, _ = plug.execute("activate", {"selector": "@pick/ash"})
        except Exception as e:
            ok2, msg = False, "%s: %s" % (type(e).__name__, str(e)[:120])
        ck(ok1 and ok2,
           "A NAME SURVIVES THE REBUILD IT WAS PUBLISHED BEFORE: pressing @pick/oak rebuilds the list, and "
           "@pick/ash still resolves with no observe between (before ADR-239: 'no control answers'): %s" % msg)
        plug.execute("activate", {"selector": "@plum"})
        ok3, msg3, _ = plug.execute("activate", {"selector": "@named/plum"})
        ck(ok3 and pg.evaluate("() => window.ns[0].c") == 2,
           "and a tally named by its .nm is pressed twice by the same name: %s" % msg3)
        b.close()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---- 4. the real kit --------------------------------------------------------
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]
pages = A.pages()
ck(set(led) == set(pages), "every page of the kit is in the ledger and nothing else: %s" % sorted(set(led) ^ set(pages)))
ck(not [n for n, r in led.items() if r.get("error")],
   "no page failed to walk: %s" % [(n, r["error"]) for n, r in led.items() if r.get("error")])
ck(sum(r.get("pressed", 0) for r in led.values()) >= 1600,
   "the audit pressed the kit, not a corner of it: %d presses" % sum(r.get("pressed", 0) for r in led.values()))
ck(not [n for n, r in led.items() if r.get("renamed")],
   "NO RENAMED CONTROL: every name the door publishes still names its control after a press -- %s"
   % [(n, r.get("renamed_names")) for n, r in led.items() if r.get("renamed")])
ck(not [n for n, r in led.items() if r.get("shadowed")],
   "NO SHADOWED CONTROL: no name presses something else after a press -- %s"
   % [(n, r.get("shadowed_names")) for n, r in led.items() if r.get("shadowed")])
# The two pages the audit found are walked LIVE, not read from the ledger: a
# ledger is what the last audit run saw, and a regression on the page would sit
# behind it until the audit ran again.
live = A.walk(["field-notebook.html", "farm-scout.html"])
for n in ("field-notebook.html", "farm-scout.html"):
    r = live.get(n) or {}
    ck(not r.get("error") and r.get("pressed", 0) >= 30 and not r.get("renamed") and not r.get("shadowed"),
       "%s, the page the audit found, holds its names now: %s"
       % (n, r.get("error") or dict((k, r.get(k)) for k in ("pressed", "held", "gone", "renamed", "shadowed"))))
# ...and the names its task presses are names the page publishes: a stepper
# that says which quadrat and which catch it counts.
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page()
    pg.goto(_kit.url("field-notebook.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(300)
    plug = PP.PagePlugin(pg, "field-notebook.html")
    plug.observe()
    for _ in range(2):
        plug.execute("activate", {"selector": "#quadAdd"})
    miss = []
    for nm in ("@specGrid/species-a", "@ethoGrid/forage", "@add one to Q2", "@take one from Q1",
               "@add one to Marked (M)", "@add one to 2nd catch (C)", "@add one to Recaptured (R)"):
        try:
            plug._resolve(nm)
        except Exception as e:
            miss.append(nm)
    ck(not miss, "every tally and stepper on the field notebook answers to a name that says what it counts: "
                 "missing %s" % miss)
    b.close()
for n, want in (("field-notebook.html", ("specGrid/species-a", "add one to Q4", "add one to Marked (M)",
                                         "ethoGrid/preen")),
                ("farm-scout.html", ("poGrid/honeybee", "poGrid/mason"))):
    t = json.load(io.open(os.path.join(_kit.TOOLS_DIR, "tasks", "page-%s-science.json" % n[:-5]), encoding="utf-8"))
    sels = set((s.get("arguments") or {}).get("selector") for s in t["steps"] if isinstance(s.get("arguments"), dict))
    ck(all("@control:" + w in sels for w in want) and not [s for s in sels if s and s.startswith("@control:")
                                                             and ("Grid#" in s or "p-more#" in s)],
       "%s's task presses its tallies and steppers by NAME, no index left: %s"
       % (n, sorted(s for s in sels if s and "#" in s)))

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
