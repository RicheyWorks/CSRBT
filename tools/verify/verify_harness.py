# -*- coding: utf-8 -*-
"""Shows the harness failing, on pages built to make it fail.

A harness that has only ever been run against a kit it reports as fine is a
harness nobody has watched work. Every verdict it can reach is seeded here on a
fixture page whose defect is known, and asserted: a button wired to nothing, a
value leaking NaN, a row that really does spill sideways, a control that only
exists behind a tab, and a page where everything is in order.

The accounting identity is asserted on every fixture, because the number this
tool reports is a coverage claim: discovered == driven + dead + hidden + failed
+ excluded. A harness that loses an affordance is claiming to have driven what
it never saw (ADR-100).
"""

# Declared for tools/mutate.py. This suite writes synthetic fixture pages and
# every assertion in it is about those fixtures and about tools/harness.py --
# it is a subject, not a fixture-builder for anything else.
MUTATE_ROLE = "subject"
import io, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness

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
        '.pane{display:none}.pane.on{display:block}</style></head><body>')
TAIL = "</body></html>"

FIXTURES = {
    # a button that listens to nothing at all
    "dead": HEAD + '<button id="a">wired to nothing</button>' + TAIL,

    # a button that works
    "live": HEAD + '<button id="a">counts</button><p id="o">0</p>'
            '<script>var n=0;document.getElementById("a").onclick=function(){'
            'document.getElementById("o").textContent=String(++n);};</script>' + TAIL,

    # a value element that leaks NaN when pressed
    "junk": HEAD + '<button id="a">divide</button><p class="v" id="o">ready</p>'
            '<script>document.getElementById("a").onclick=function(){'
            'document.getElementById("o").textContent=String(Number("x")/2);};</script>' + TAIL,

    # a row that genuinely runs off the side of a phone
    "spill": HEAD + '<button id="a">grow</button><div id="o"></div>'
             '<script>document.getElementById("a").onclick=function(){'
             'document.getElementById("o").innerHTML='
             '"<div class=row2 style=\'width:900px;height:20px\'>wide</div>";};</script>' + TAIL,

    # A control that exists only behind a tab the harness has to press first.
    # Built to match the kit's real pattern: the tab itself carries .on, and the
    # control's readout is in the SAME pane as the control. The first draft put
    # the readout in the other pane, where a display:none ancestor kept it out
    # of innerText -- and the fixture, not the harness, was what failed.
    "tabbed": HEAD +
              '<button class="tab on" data-pane="p1">one</button>'
              '<button class="tab" data-pane="p2">two</button>'
              '<section class="pane on" id="p1"><p>first</p></section>'
              '<section class="pane" id="p2"><button id="deep">deep</button>'
              '<p id="o">0</p></section>'
              '<script>var n=0;'
              'document.querySelectorAll(".tab").forEach(function(t){t.onclick=function(){'
              'document.querySelectorAll(".tab").forEach(function(x){'
              'x.classList.toggle("on", x===t);});'
              'document.querySelectorAll(".pane").forEach(function(p){'
              'p.classList.toggle("on", p.id===t.dataset.pane);});};});'
              'document.getElementById("deep").onclick=function(){'
              'document.getElementById("o").textContent=String(++n);};</script>' + TAIL,

    # PROSE THAT LEGITIMATELY SAYS "undefined", DECLARED (ADR-109).
    # field-notebook renders exactly this: Lincoln-Petersen is M*C/R and has no
    # value at R=0, so the page says so. The old detector matched the word and
    # reported the kit's carefulness as a value leak, twice. A declared zone is
    # excused; the next two fixtures prove the excuse is narrow.
    "prose_ok": HEAD + '<button id="a">estimate</button><p id="o">ready</p>'
                '<script>document.getElementById("a").onclick=function(){'
                'document.getElementById("o").innerHTML='
                '"<span data-junk-ok=\'no value at R=0\'>the estimate is undefined'
                ' (R must be at least 1)</span>";};</script>' + TAIL,

    # the same word, NOT declared -- a real value leaking into the page
    "prose_leak": HEAD + '<button id="a">show</button><p class="v" id="o">ready</p>'
                  '<script>var q={};document.getElementById("a").onclick=function(){'
                  'document.getElementById("o").textContent="Total: "+q.missing;};</script>' + TAIL,

    # a declaration wrapped around a REAL NaN. The marker excuses the word
    # "undefined" and nothing else; if this fixture passes, the escape hatch has
    # become the way the next real leak goes unreported.
    "prose_abuse": HEAD + '<button id="a">divide</button><p id="o">ready</p>'
                   '<script>document.getElementById("a").onclick=function(){'
                   'document.getElementById("o").innerHTML='
                   '"<span data-junk-ok=\'trying to hide a real one\'>"'
                   '+String(Number("x")/2)+"</span>";};</script>' + TAIL,

    # an affordance the page throws on
    "throws": HEAD + '<button id="a">boom</button>'
              '<script>document.getElementById("a").onclick=function(){'
              'null.x;};</script>' + TAIL,
}

d = tempfile.mkdtemp(prefix="harness_fixtures_")
paths = {}
for k, html in FIXTURES.items():
    paths[k] = os.path.join(d, k + ".html")
    io.open(paths[k], "w", encoding="utf-8").write(html)


def run(k, passes=2):
    return harness.run_page(k + ".html", passes=passes, url="file://" + paths[k])


def labels(res, bucket):
    return [x.get("label", "") for x in res[bucket]]


def accounted(res):
    return res["discovered"] == sum(len(res[b]) for b in harness.BUCKETS)


# ---- 1. a button wired to nothing is reported, and a working one is not ----
r = run("dead")
ck(accounted(r), "dead fixture: every affordance accounted for")
ck(any("wired to nothing" in x for x in labels(r, "dead")),
   "a button that listens to nothing is reported as leaving no trace")

r = run("live")
ck(accounted(r), "live fixture: every affordance accounted for")
ck(not r["dead"], "a button that changes the page is NOT reported: %s" % labels(r, "dead"))
ck(any("counts" in x for x in labels(r, "driven")), "and it is counted as driven")

# ---- 2. a value leaking NaN breaks the invariant ---------------------------
r = run("junk")
ck(accounted(r), "junk fixture: every affordance accounted for")
ck(any("junk rendered" in e for e in r["errors"]),
   "NaN reaching a value element is reported: %s" % r["errors"][:2])

# ---- 2b. the junk rule knows prose from a value leak (ADR-109) ------------
r = run("prose_ok")
ck(accounted(r), "declared-prose fixture: every affordance accounted for")
ck(not any("junk rendered" in e for e in r["errors"]),
   "a DECLARED 'undefined' is prose, not a leak: %s" % r["errors"][:2])

r = run("prose_leak")
ck(accounted(r), "undeclared-leak fixture: every affordance accounted for")
ck(any("junk rendered" in e for e in r["errors"]),
   "an UNDECLARED undefined is still reported: %s" % r["errors"][:2])

r = run("prose_abuse")
ck(accounted(r), "abuse fixture: every affordance accounted for")
ck(any("junk rendered" in e for e in r["errors"]),
   "a declaration CANNOT hide a real NaN -- the hatch is not a way out: %s" % r["errors"][:2])

# ---- 3. a row that really spills is reported, with the element named -------
r = run("spill")
ck(accounted(r), "spill fixture: every affordance accounted for")
ck(any("spills" in e for e in r["errors"]),
   "a 900px row inside a 390px viewport is reported: %s" % r["errors"][:2])
ck(any("row2" in e for e in r["errors"]),
   "and the report names the element that spills, not just the number")

# ---- 4. a control behind a tab is reached by pressing the tab --------------
r = run("tabbed")
ck(accounted(r), "tabbed fixture: every affordance accounted for")
ck(any("deep" in x for x in labels(r, "driven")),
   "a control in a closed pane is driven, because its tab is pressed first")
ck(not any("deep" in x for x in labels(r, "hidden")),
   "and it is not written off as hidden")

# ---- 5. a page that throws is reported, not swallowed ----------------------
r = run("throws")
ck(accounted(r), "throwing fixture: every affordance accounted for")
ck(any("uncaught" in e for e in r["errors"]) or r["errors"],
   "a handler that throws is reported: %s" % r["errors"][:2])

# ---- 6. the exclusions are the only way out, and each says why -------------
ck(set(harness.EXCLUDED) <= set(k for k, _ in harness.KINDS),
   "every excluded kind is a kind the harness actually discovers")
ck(all(len(v) > 40 for v in harness.EXCLUDED.values()),
   "every exclusion carries a reason, not a label")
# Six, since ADR-109. "sequenced" holds affordances the harness's OWN setup
# removed before it could press them -- stepping a stepper the other way, moving
# a radio group off the option under test. Ten of twenty-one dead findings were
# that, and calling them dead was the instrument accusing working code. They stay
# counted and stay visible; they are simply not the same fact as a control wired
# to nothing, and the identity must not fold them together.
ck("BUCKETS" in dir(harness) and set(harness.BUCKETS) ==
   {"driven", "dead", "sequenced", "hidden", "failed", "excluded"},
   "the accounting has exactly the six buckets the report adds up")

# ---- 7. the measurements that were wrong once, asserted -------------------
src = io.open(os.path.join(_kit.TOOLS_DIR, "harness.py"), encoding="utf-8").read()
ck("clientWidth" in src and "innerWidth;" not in src.replace("window.innerWidth", ""),
   "overflow is measured against clientWidth -- innerWidth includes the scrollbar, "
   "and reported 15px of spill on two pages that had none")
ck("junkTok" in src, "junk is compared as a token, not as the text around it")
ck("IGNORED_CONSOLE" in src and "fonts.googleapis.com" in src,
   "the webfont that is SUPPOSED to fail offline (ADR-031) is not a console defect")
ck("HEADROOM" in src and "UNSELECT" in src,
   "a control is judged from a state where its press can show: a stepper is "
   "given room and a selected option is deselected first")

print("---")
print("%d/%d" % (P, P + F))
raise SystemExit(1 if F else 0)
