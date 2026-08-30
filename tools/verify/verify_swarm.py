# -*- coding: utf-8 -*-
"""Shows each oracle failing, on pages built so that a click alone would pass.

Every fixture here is wired. Every fixture here responds. The harness's question
-- did anything change? -- is answered YES by all of them, which is the point:
a plus button that subtracts changes the page, a filter that keeps the rows that
do NOT match changes the page, an option that refuses to select while bumping a
counter changes the page, and a Copy CSV that copies an empty string changes the
page. Nine fixtures, one per oracle, each of them a control that does something
and the wrong something.

The tenth is in order throughout, and the assertion on it is that nothing is
reported -- an instrument that cannot come back clean is not measuring
(ADR-069).

The accounting identity is asserted on every fixture, because the number the
swarm prints is a coverage claim: discovered == verified + wrong + changed +
dead + hidden + failed + excluded.
"""
import io, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import swarm
import harness_contract as C

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
        '.opt{display:block}.opt.gone{display:none}'
        '.on{font-weight:700}</style></head><body>')
TAIL = "</body></html>"

STEP = ('<div class="fek-step"><button id="dn">-</button>'
        '<input class="val" value="5"><button id="up">+</button></div>')

PICK = ('<div class="fek-pick"><input class="search" placeholder="find">'
        '<div id="opts"><div class="opt">alpha</div><div class="opt">beta</div>'
        '<div class="opt">gamma</div><div class="opt">delta</div></div></div>')

# A correct picker filter, and a lying one, share this shell.
def picker(js):
    return PICK + '<script>' + js + '</script>'


FIXTURES = {
    # 1. a plus that subtracts. The number moves, so the page changed.
    "minus": HEAD + STEP +
             '<script>var v=document.querySelector(".val");'
             'document.getElementById("up").onclick=function(){'
             'v.value=String(Number(v.value)-1);};'
             'document.getElementById("dn").onclick=function(){'
             'v.value=String(Number(v.value)-1);};</script>' + TAIL,

    # 2. a filter that keeps exactly the rows that do NOT match.
    "liar": HEAD + picker(
        'var s=document.querySelector(".search");'
        's.oninput=function(){var q=s.value.toLowerCase();'
        '[...document.querySelectorAll(".opt")].forEach(function(o){'
        'o.classList.toggle("gone", q!=="" && o.textContent.toLowerCase().indexOf(q)>=0);});};'
    ) + TAIL,

    # 3. an option that will not select, but bumps a counter so the page moves.
    "sticky": HEAD + '<div id="g"><button class="fek-chip" id="a">one</button>'
              '<button class="fek-chip" id="b">two</button></div><p id="o">0</p>'
              '<script>var n=0;[...document.querySelectorAll(".fek-chip")].forEach('
              'function(c){c.onclick=function(){'
              'document.getElementById("o").textContent=String(++n);};});</script>' + TAIL,

    # 4. a field that swallows what is typed into it.
    "eats": HEAD + '<input id="t" type="text"><p id="o">typed 0</p>'
            '<script>var n=0;var t=document.getElementById("t");'
            't.oninput=function(){document.getElementById("o").textContent='
            '"typed "+(++n);t.value="";};</script>' + TAIL,

    # 5. a Copy button that copies nothing at all.
    "empty": HEAD + '<input id="t" type="text"><button id="c">Copy CSV</button>'
             '<p id="o">idle</p>'
             '<script>document.getElementById("c").onclick=function(){'
             'document.getElementById("o").textContent="copied";'
             'navigator.clipboard.writeText("");};</script>' + TAIL,

    # 6. an export whose rows do not agree how many columns there are.
    "ragged": HEAD + '<input id="t" type="text"><button id="c">Copy CSV</button>'
              '<script>document.getElementById("c").onclick=function(){'
              'navigator.clipboard.writeText("a,b,c\\n1,2,3\\n4,5\\n6,7,8");};</script>' + TAIL,

    # 7. a well-formed export of somebody else's data. It has an Add, because
    #    an export of saved records is right to contain nothing when nothing was
    #    ever saved -- the swarm only judges this once the page has a record.
    "stranger": HEAD + '<input id="t" type="text"><button id="ad">Add row</button>'
                '<button id="c">Copy CSV</button><div id="rows"></div>'
                '<script>var n=0;document.getElementById("ad").onclick=function(){'
                'var d=document.createElement("div");d.className="rw";'
                'd.textContent="row "+(++n);document.getElementById("rows").appendChild(d);};'
                'document.getElementById("c").onclick=function(){'
                'navigator.clipboard.writeText("a,b,c\\n1,2,3\\n4,5,6");};</script>' + TAIL,

    # 8. a tab that opens its pane without closing the one that was open.
    "twopane": HEAD +
               '<button class="tab on" data-pane="p1">one</button>'
               '<button class="tab" data-pane="p2">two</button>'
               '<section class="pane on" id="p1"><p>first</p></section>'
               '<section class="pane" id="p2"><p>second</p></section>'
               '<script>[...document.querySelectorAll(".tab")].forEach(function(t){'
               't.onclick=function(){'
               '[...document.querySelectorAll(".tab")].forEach(function(x){'
               'x.classList.toggle("on", x===t);});'
               'document.getElementById(t.dataset.pane).classList.add("on");};});</script>'
               + TAIL,

    # 9. an Add that adds nothing, while saying it did.
    "noadd": HEAD + '<button id="a">Add row</button><p id="o">rows: 0</p>'
             '<script>var n=0;document.getElementById("a").onclick=function(){'
             'document.getElementById("o").textContent="rows: "+(++n);};</script>' + TAIL,

    # 10. a file input and a drop zone that take a photo and say so.
    "photo": HEAD + '<input type="file" id="f" accept="image/*" multiple>'
             '<div id="dz">drop here</div><div id="list"></div>'
             '<script>function add(fs){var L=document.getElementById("list");'
             '[].slice.call(fs).forEach(function(f){var d=document.createElement("div");'
             'd.className="ph";d.textContent=f.name;L.appendChild(d);});}'
             'document.getElementById("f").onchange=function(){add(this.files);};'
             'var z=document.getElementById("dz");'
             'z.addEventListener("dragover",function(e){e.preventDefault();});'
             'z.addEventListener("drop",function(e){e.preventDefault();'
             'add(e.dataTransfer.files);});</script>' + TAIL,

    # 11. a file input that takes the photo and never says it did. The bytes are
    #     in the input; the user has no way to know.
    "silent": HEAD + '<input type="file" id="f" accept="image/*">'
              '<p id="o">ready</p>'
              '<script>document.getElementById("f").onchange=function(){};</script>'
              + TAIL,

    # 12. a checkbox that refuses to stay ticked.
    "stuckbox": HEAD + '<label>on <input type="checkbox" id="c"></label><p id="o">0</p>'
                '<script>var n=0;var c=document.getElementById("c");'
                'c.addEventListener("click",function(){'
                'document.getElementById("o").textContent=String(++n);'
                'c.checked=false;});</script>' + TAIL,

    # 13. everything in order. The instrument must be able to come back clean.
    "good": HEAD + STEP +
            '<button class="tab on" data-pane="p1">one</button>'
            '<button class="tab" data-pane="p2">two</button>'
            '<section class="pane on" id="p1"><input id="t" type="text">'
            '<div id="g"><button class="fek-chip" id="ca">one</button>'
            '<button class="fek-chip" id="cb">two</button></div>'
            '<button id="c">Copy CSV</button></section>'
            '<section class="pane" id="p2"><p>second</p></section>'
            '<script>'
            'var v=document.querySelector(".val");'
            'document.getElementById("up").onclick=function(){v.value=String(Number(v.value)+1);};'
            'document.getElementById("dn").onclick=function(){v.value=String(Number(v.value)-1);};'
            '[...document.querySelectorAll(".tab")].forEach(function(t){t.onclick=function(){'
            '[...document.querySelectorAll(".tab")].forEach(function(x){x.classList.toggle("on",x===t);});'
            '[...document.querySelectorAll(".pane")].forEach(function(p){'
            'p.classList.toggle("on", p.id===t.dataset.pane);});};});'
            '[...document.querySelectorAll(".fek-chip")].forEach(function(c){c.onclick=function(){'
            '[...document.querySelectorAll(".fek-chip")].forEach(function(x){'
            'x.classList.toggle("on", x===c);});};});'
            'document.getElementById("c").onclick=function(){'
            'navigator.clipboard.writeText("name,n\\n"+'
            'JSON.stringify(document.getElementById("t").value)+",1");};'
            '</script>' + TAIL,
}

d = tempfile.mkdtemp(prefix="swarm_fixtures_")
paths = {}
for k, html in FIXTURES.items():
    paths[k] = os.path.join(d, k + ".html")
    io.open(paths[k], "w", encoding="utf-8").write(html)


def run(k, passes=2):
    return swarm.run_page(k + ".html", passes=passes, url="file://" + paths[k])


def findings(res):
    return " | ".join(res["findings"])


def accounted(r):
    return r["discovered"] == sum(len(r[v]) for v in swarm.VERDICTS)


def wrongs(r, oracle):
    return [x for x in r["wrong"] if x.get("oracle") == oracle]


# ---- the clean page, first: an instrument that cannot pass is not measuring --
r = run("good")
ck(accounted(r), "good fixture: every affordance accounted for")
ck(not r["wrong"], "a page where everything works reports nothing wrong: %s"
   % findings(r))
ck(len(r["verified"]) >= 5,
   "and its controls are VERIFIED, not merely observed to change: %d verified, "
   "%d changed" % (len(r["verified"]), len(r["changed"])))
ck(any(x.get("oracle") == "export" for x in r["verified"]),
   "including the export, whose payload carried the value that was typed")

# ---- 1. a plus that subtracts ----------------------------------------------
r = run("minus")
ck(accounted(r), "minus fixture: every affordance accounted for")
ck(wrongs(r, "step"),
   "a plus button that decrements is reported, though the number did move: %s"
   % findings(r))

# ---- 2. a filter that keeps what does not match -----------------------------
r = run("liar")
ck(accounted(r), "liar fixture: every affordance accounted for")
ck(wrongs(r, "filter"),
   "a filter whose survivors do not match the query is reported, though it "
   "did filter: %s" % findings(r))

# ---- 3. an option that will not select --------------------------------------
r = run("sticky")
ck(accounted(r), "sticky fixture: every affordance accounted for")
ck(wrongs(r, "option"),
   "an option that changes the page without selecting itself is reported: %s"
   % findings(r))

# ---- 4. a field that eats what is typed -------------------------------------
r = run("eats")
ck(accounted(r), "eats fixture: every affordance accounted for")
ck(wrongs(r, "field"),
   "a field that discards the entry is reported, though the page reacted: %s"
   % findings(r))

# ---- 5, 6, 7. three ways for an export to be wrong --------------------------
r = run("empty")
ck(accounted(r), "empty-export fixture: every affordance accounted for")
ck(wrongs(r, "export"), "a Copy that copies an empty string is reported: %s"
   % findings(r))

r = run("ragged")
ck(accounted(r), "ragged fixture: every affordance accounted for")
ck(any("ragged" in (x.get("got") or "") for x in wrongs(r, "export")),
   "a CSV whose rows disagree about the column count is reported: %s"
   % findings(r))

r = run("stranger")
ck(accounted(r), "stranger fixture: every affordance accounted for")
ck(any("none of the" in (x.get("got") or "") for x in wrongs(r, "export")),
   "a well-formed export containing nothing the user typed is reported: %s"
   % findings(r))

# ---- 8. two panes open at once ---------------------------------------------
r = run("twopane")
ck(accounted(r), "twopane fixture: every affordance accounted for")
ck(wrongs(r, "tab") or any("panes visible" in e for e in r["errors"]),
   "a tab that opens a pane without closing the other is reported: %s | %s"
   % (findings(r), r["errors"][:2]))

# ---- 9. an Add that adds nothing --------------------------------------------
r = run("noadd")
ck(accounted(r), "noadd fixture: every affordance accounted for")
ck(wrongs(r, "add"),
   "an Add that changes a caption but adds no row is reported: %s" % findings(r))

# ---- 10. photos, drops, and a page that takes a file without a word ---------
r = run("photo")
ck(accounted(r), "photo fixture: every affordance accounted for")
ck(any(x.get("oracle") == "file" for x in r["verified"]),
   "a file input that names the photo it was handed is verified: %s"
   % [(x.get("oracle"), x.get("got")) for x in r["verified"]][:3])
ck(any(x["kind"] == "drop_zone" for x in r["verified"] + r["changed"] + r["wrong"]),
   "and the drop zone is found and driven, though no CSS selector can name one")
ck(any("DJI_" in str(x.get("got", "")) or "IMG_" in str(x.get("got", ""))
       for x in r["verified"]),
   "the file it names is the one it was handed: %s"
   % [x.get("got") for x in r["verified"]][:3])

r = run("silent")
ck(accounted(r), "silent fixture: every affordance accounted for")
ck(any(x.get("oracle") == "file" for x in r["wrong"]),
   "a page that takes the photo and never names it is reported -- the bytes are "
   "in the input and the user cannot tell: %s" % findings(r))

r = run("stuckbox")
ck(accounted(r), "checkbox fixture: every affordance accounted for")
ck(any(x.get("oracle") == "checkbox" for x in r["wrong"]),
   "a checkbox that will not stay ticked is reported: %s" % findings(r))

# ---- the widened surface ---------------------------------------------------
_kinds = set(k for k, _ in swarm.SWARM_KINDS)
ck({"checkbox", "drop_zone", "file_in"} <= _kinds,
   "checkboxes, drop zones and file inputs are all discovered: %s" % sorted(_kinds))
ck("type=time" in dict(swarm.SWARM_KINDS)["text_in"],
   "and the text kind reaches every input type the kit uses, not three of them")
ck("file_in" not in swarm.EXCLUDED and swarm.DRIVER.get("file_in") == "attach-file",
   "file inputs are driven now, not excluded")
ck(set(swarm.EXCLUDED) == {"link", "nav_link", "readonly_out"},
   "and the only ways out left are the three that carry a reason: %s"
   % sorted(swarm.EXCLUDED))

# ---- the seed, without which most of the above cannot be asked --------------
r = run("good")
ck(r["seeded"]["fields"] >= 1 and r["seeded"]["sentinels"] >= 1,
   "the run seeds the page before it judges it: %s" % r["seeded"])
ck(swarm.SENT_RE.match(swarm.SENTINEL % 1),
   "the sentinel a seeded value is made of is the one the export oracle looks for")

# ---- everything went through the contract -----------------------------------
ck(r["commands"] > 20,
   "every observation and action is a gateway command: %d issued" % r["commands"])
ck(r["policy"] == swarm.SWARM_POLICY,
   "and the run records the policy it required: %s" % r["policy"])
ck(set(swarm.DRIVER.values()) <= set(
       a.name for a in __import__("harness_plugin_page").PagePlugin(None).descriptor().actions),
   "and drives only with actions the plugin publishes")

# A client without the gate cannot reach around it: the swarm's own driving is
# refused by the gateway, not quietly skipped.
import harness_plugin_page as PP


class Deaf(C.Plugin):
    def descriptor(self):
        return PP.PagePlugin(None).descriptor()

    def observe(self, sensitive=False):
        return {"ready": True, "controls": []}

    def execute(self, action, arguments):
        return True, "should never be reached", {}


tok = "t" * 24
g = C.Gateway(C.Registry([Deaf()]), C.Policy(token=tok, enabled=True))
try:
    g.execute(tok, "csrbt-page", {"request_id": "x", "action": "activate",
                                  "arguments": {"selector": "action_btn:0"}})
    ck(False, "activation was allowed under the default policy")
except C.HarnessError as e:
    ck(e.code == "forbidden",
       "under the default policy the swarm's own driving action is refused: %s" % e.code)

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
