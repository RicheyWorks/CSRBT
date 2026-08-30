# -*- coding: utf-8 -*-
"""Shows the edge, chaos and key-exploration passes failing, and coming back clean.

Each pass answers a question nobody wrote a per-page expectation for, so each is
seeded twice: on a page built to break under it, and on a page built to survive
it. A pass that only ever reports something is a pass with a stuck needle; a
pass that never reports anything is not measuring (ADR-069). Both halves are
asserted here.

The tree fixture is a real binary key: fourteen nodes, eight leaves, every node
its own control. The assertion is not that the walk went in -- it is that the
walk saw every one of the fourteen and reached more distinct states than the
tree has leaves. "Explored the key" is a counting claim, and this is the count.
"""
import io, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import probe

MUTATE_ROLE = "subject"

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


HEAD = ('<!doctype html><html><head><meta charset="utf-8"><title>f</title>'
        '<style>body{margin:0;font:16px sans-serif}'
        '.pane{display:none}.pane.on{display:block}'
        '.g{display:none}.g.show{display:block}.on{font-weight:700}'
        '</style></head><body>')
TAIL = "</body></html>"


def tree(depth=3):
    """A binary key: 2 + 4 + 8 = 14 nodes, 8 leaves, each node its own control."""
    html, js = [], []
    nodes = [""]
    for d in range(depth):
        nxt = []
        for pref in nodes:
            gid = "g" + (pref or "root")
            html.append('<div class="g%s" id="%s">' % (" show" if d == 0 else "", gid))
            for side in ("L", "R"):
                nid = pref + side
                html.append('<button class="kopt" id="n%s">lead %s</button>' % (nid, nid))
                js.append('document.getElementById("n%s").onclick=function(){'
                          'this.classList.add("on");'
                          'var t=document.getElementById("g%s");'
                          'if(t) t.classList.add("show");'
                          'document.getElementById("out").textContent="at %s";};'
                          % (nid, nid, nid))
                nxt.append(nid)
            html.append('</div>')
        nodes = nxt
    return (HEAD + "".join(html) + '<p id="out">start</p><script>'
            + "".join(js) + '</script>' + TAIL)


FIXTURES = {
    # a readout that becomes NaN the moment a letter is typed
    "edgy": HEAD + '<input id="t" type="text"><p>count <span class="v" id="o">3</span></p>'
            '<script>var t=document.getElementById("t");'
            't.oninput=function(){document.getElementById("o").textContent='
            'String(Number(t.value)*2);};</script>' + TAIL,

    # the same field, guarded the way a page ought to guard one
    "sturdy": HEAD + '<input id="t" type="text"><p>count <span class="v" id="o">3</span></p>'
              '<script>var t=document.getElementById("t");'
              't.oninput=function(){var n=parseFloat(t.value);'
              'document.getElementById("o").textContent='
              'isFinite(n)?String(n*2):"--";};</script>' + TAIL,

    # nothing wrong until the same button has been pressed three times
    "fragile": HEAD + '<button id="a">press</button><p class="v" id="o">0</p>'
               '<script>var n=0;document.getElementById("a").onclick=function(){'
               'n++;document.getElementById("o").textContent='
               'n>2?String(undefined+1):String(n);};</script>' + TAIL,

    "tree": tree(3),

    # a tree with a leaf that leaks NaN, three levels down
    "deeptrap": tree(3).replace(
        'document.getElementById("out").textContent="at RRR";',
        'document.getElementById("out").textContent="at RRR";'
        'document.getElementById("out").className="v";'
        'document.getElementById("out").textContent=String(Number("x")+1);'),
}

d = tempfile.mkdtemp(prefix="probe_fixtures_")
paths = {}
for k, html in FIXTURES.items():
    paths[k] = os.path.join(d, k + ".html")
    io.open(paths[k], "w", encoding="utf-8").write(html)


def _url(k):
    return "file://" + paths[k]


# probe's passes take a page name and resolve it through _kit; point them at the
# fixtures instead, the same way verify_swarm does.
_open = probe.S.open_session


def patched(name, url=None, video_dir=None):
    return _open(name, url=url or _url(name[:-5]), video_dir=video_dir)


probe.S.open_session = patched


def run(which, k, **kw):
    return probe.PASSES[which](k + ".html", **kw)


# ---- EDGES ----------------------------------------------------------------
r = run("edges", "edgy")
ck(r["tried"] >= len(probe.EDGES),
   "every edge value is tried against the field: %d" % r["tried"])
ck(r["findings"],
   "a readout that goes NaN on a letter is reported: %s" % r["findings"][:1])
ck(any("NaN" in f["broke"] for f in r["findings"]),
   "and the report names what appeared: %s"
   % [f["broke"][:50] for f in r["findings"][:2]])
ck(all(f.get("value") is not None and f.get("why") for f in r["findings"]),
   "each finding carries the value that caused it and why that value is tried")
ck(any(f.get("shot") and os.path.exists(f["shot"]) for f in r["findings"]),
   "and a picture of the page in the state it was reported in")

r = run("edges", "sturdy")
ck(r["tried"] >= len(probe.EDGES), "the guarded page is driven just as hard")
ck(not r["findings"],
   "a field that guards its input reports nothing: %s" % r["findings"][:2])

ck(len(probe.EDGES) >= 12 and any(v == "" for v, _ in probe.EDGES)
   and any(len(v) > 200 for v, _ in probe.EDGES)
   and any("<script" in v for v, _ in probe.EDGES),
   "the battery covers empty, enormous and markup: %d values" % len(probe.EDGES))

# ---- CHAOS ----------------------------------------------------------------
r = run("chaos", "fragile", steps=40, seed=11)
ck(r["steps"] > 5, "chaos actually acts: %d actions" % r["steps"])
ck(r["findings"], "a page that breaks on the third press is found by random "
                  "pressing: %s" % r["findings"][:1])
if r["findings"]:
    f = r["findings"][0]
    ck(f.get("seed") == 11 and f.get("replay"),
       "and the finding carries the seed and the exact actions, so it replays "
       "rather than being retold: seed %s, %d step(s)"
       % (f.get("seed"), len(f.get("replay") or [])))
    ck(all("selector" in x and "action" in x for x in f["replay"]),
       "every replay step names the action and the control it was aimed at")
else:
    ck(False, "no finding to carry a replay")

r = run("chaos", "sturdy", steps=40, seed=11)
ck(not r["findings"],
   "random pressing of a sound page reports nothing: %s" % r["findings"][:2])

a = run("chaos", "fragile", steps=25, seed=5)
b = run("chaos", "fragile", steps=25, seed=5)
ck([x["step"] for x in a["findings"]] == [x["step"] for x in b["findings"]],
   "the same seed gives the same run: %s vs %s"
   % ([x["step"] for x in a["findings"]], [x["step"] for x in b["findings"]]))

# ---- EXPLORE --------------------------------------------------------------
r = run("explore", "tree", max_paths=120)
ck(r["options_seen"] == 14,
   "every node of a 14-node binary key is seen: %d" % r["options_seen"])
ck(r["deepest"] >= 3,
   "the walk reaches the bottom of a 3-deep key: depth %d" % r["deepest"])
ck(r["states_seen"] >= 8,
   "and reaches at least as many distinct states as the key has leaves: %d"
   % r["states_seen"])
ck(r["leaves"] >= 1, "and recognises a leaf when there is nothing left to choose")
ck(not r["findings"], "a sound key reports nothing: %s" % r["findings"][:2])

r = run("explore", "deeptrap", max_paths=120)
ck(r["findings"],
   "a leaf three levels down that leaks NaN is found: %s" % r["findings"][:1])
if r["findings"]:
    f = r["findings"][0]
    ck(f.get("path") and len(f["path"]) >= 1,
       "and the finding carries the path taken to reach it: %s" % (f.get("path"),))
    ck(f.get("shot") and os.path.exists(f["shot"]),
       "with a picture of the leaf it broke on")
else:
    ck(False, "no path recorded")
    ck(False, "no picture recorded")

# ---- the invariants themselves --------------------------------------------
ck(probe.broken({"junkTok": None, "junkSlot": None, "len": 100},
                {"junkTok": None, "junkSlot": None, "len": 100,
                 "onp": 1, "panes": 1, "overflow": 0}, []) == [],
   "a page that did not move breaks no invariant")
ck(probe.broken({"len": 4000, "junkSlot": None},
                {"len": 100, "junkSlot": None, "overflow": 0, "onp": 1,
                 "panes": 1}, []),
   "a page that stopped rendering is broken even though nothing threw")
ck(any("undefined" not in b for b in
       probe.broken({"junkTok": None, "junkSlot": None},
                    {"junkTok": None, "onp": 2, "panes": 2, "overflow": 0,
                     "junkSlot": None}, [])),
   "two panes open at once is an invariant break")

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
