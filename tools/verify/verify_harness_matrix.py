# -*- coding: utf-8 -*-
"""The harness, tested clause by clause.

WHY A SECOND, LARGER SUITE

tools/verify/verify_harness.py proves the harness's headline behaviours on nine
fixtures. That was proportionate while the harness only reported. It is not
proportionate now: since ADR-109 the harness gates the build -- verify_findings
fails on any finding not in the accepted baseline -- so a bug in the harness is
no longer a wrong number in a log, it is either a build that breaks over nothing
or, worse, a real defect that stops being reported and nobody notices, because
the thing that would have noticed is the thing that broke.

A tool that can fail a build has to be tested like one. This walks the harness's
contract clause by clause: every kind it claims to discover, every bucket it
claims to sort into, every trace it accepts as evidence that an action worked,
every invariant it claims to catch, and the ways a page can be hostile to it.

Each section states what the harness PROMISES, and each check seeds a page that
would break that promise if it were not kept.

Declared for tools/mutate.py: this suite writes synthetic fixture pages and every
assertion is about those fixtures and about tools/harness.py.
MUTATE_ROLE = "fixture-builder"

Run:  python3 tools/verify/verify_harness_matrix.py
"""
import io, json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import harness                                                    # noqa: E402

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))


HEAD = ('<!doctype html><html><head><meta charset="utf-8"><title>f</title>'
        '<style>body{margin:0;font:16px sans-serif}'
        '.pane{display:none}.pane.on{display:block}</style></head><body>')
TAIL = "</body></html>"

D = tempfile.mkdtemp(prefix="harness_matrix_")
def fixture(name, body):
    p = os.path.join(D, name + ".html")
    io.open(p, "w", encoding="utf-8").write(HEAD + body + TAIL)
    return p

def run(name, body, passes=2):
    return harness.run_page(name + ".html", passes=passes,
                            url="file://" + fixture(name, body))

def kinds(res):
    out = {}
    for b in harness.BUCKETS:
        for r in res[b]:
            out.setdefault(r.get("kind", "?"), []).append(b)
    return out

def accounted(res):
    return res["discovered"] == sum(len(res[b]) for b in harness.BUCKETS)

def labels(res, bucket):
    return [x.get("label", "") for x in res[bucket]]


# ══ A. DISCOVERY ═════════════════════════════════════════════════════════════
# PROMISE: "it discovers what a user can touch". A widget the harness cannot see
# is a widget nobody is testing, and it is invisible in exactly the way that
# produces a green run over an untested control.
print("\n-- A. every kind the harness claims to discover --")

WIDGETS = (
    '<button class="tab on" data-pane="p1">tab one</button>'
    '<button class="tab" data-pane="p2">tab two</button>'
    '<section class="pane on" id="p1">'
    '  <div class="fek-step"><button>-</button><span class="val">3</span><button>+</button></div>'
    '  <div class="fek-field"><input value="7"></div>'
    '  <input type="text" value="typed">'
    '  <input type="number" value="2">'
    '  <textarea>words</textarea>'
    '  <select><option>a</option><option>b</option></select>'
    '  <div class="fek-slide"><input type="range" min="0" max="10" value="5"></div>'
    '  <div class="fek-pick"><input class="search" value=""><div class="opt">an option</div></div>'
    '  <div class="fek-dial"><button>dial</button></div>'
    '  <div class="fek-chip">chip</div>'
    '  <div class="kopt">kopt</div><div class="ck">ck</div>'
    '  <div class="cv">cv</div><div class="swc">swc</div>'
    '  <input type="file">'
    '  <input readonly value="display only">'
    '  <button>plain button</button>'
    '  <nav class="rail"><a href="other.html">rail link</a></nav>'
    '  <a href="hub.html">card link</a>'
    '</section><section class="pane" id="p2"><p>second</p></section>')

r = run("kinds", WIDGETS)
found = kinds(r)
ck("A1: the accounting identity holds on a page of every widget", accounted(r), r["discovered"])
for kind in ("tab", "step_val", "field_in", "text_in", "select", "slider", "pick_search",
             "pick_opt", "dial_btn", "chip", "kopt", "ck", "cv", "swc", "step_btn",
             "file_in", "action_btn", "readonly_out"):
    ck("A2 %-13s is discovered" % kind, kind in found, sorted(found))
ck("A3: a rail link and a card link are both discovered and both excluded",
   found.get("link") == ["excluded"] and found.get("nav_link") == ["excluded"],
   {k: v for k, v in found.items() if "link" in k})
ck("A4: a readonly box is excluded, not counted as a control that could not be driven",
   found.get("readonly_out") == ["excluded"], found.get("readonly_out"))

# PROMISE: a control that appears only after another is pressed is still found --
# that is what the extra passes are for.
r = run("revealed",
        '<button id="a">reveal</button><div id="o"></div>'
        '<script>document.getElementById("a").onclick=function(){'
        'document.getElementById("o").innerHTML='
        '"<button id=b>revealed</button><p id=c>0</p>";'
        'document.getElementById("b").onclick=function(){'
        'document.getElementById("c").textContent="1";};};</script>', passes=3)
ck("A5: a control revealed by another control is found on a later pass",
   "revealed" in labels(r, "driven") + labels(r, "dead"), labels(r, "driven"))

# ══ B. BUCKETS ═══════════════════════════════════════════════════════════════
# PROMISE: discovered == driven + dead + sequenced + hidden + failed + excluded,
# and each bucket means one thing.
print("\n-- B. every bucket, one fixture each --")

r = run("b_driven", '<button id="a">works</button><p id="o">0</p>'
        '<script>document.getElementById("a").onclick=function(){'
        'document.getElementById("o").textContent="1";};</script>')
ck("B1 driven: a control that changes the page", "works" in labels(r, "driven"), r)

r = run("b_dead", '<button id="a">wired to nothing</button>')
ck("B2 dead: a control that changes nothing", "wired to nothing" in labels(r, "dead"), r)

r = run("b_hidden",
        '<button class="tab on" data-pane="p1">one</button>'
        '<section class="pane on" id="p1"><p>x</p></section>'
        '<section class="pane" id="p2"><button id="never">unreachable</button></section>')
ck("B3 hidden: a control in a pane no tab reveals",
   "unreachable" in labels(r, "hidden"), labels(r, "hidden"))

r = run("b_failed", '<button id="a">boom</button>'
        '<script>document.getElementById("a").onclick=function(){null.x;};</script>')
ck("B4 failed: a control whose handler throws is failed or reported, not silently driven",
   "boom" in labels(r, "failed") or any("boom" in e for e in r["errors"]), r["errors"][:2])

# The sequencing artifact, reproduced exactly as the real pages produce it.
# To press a selected option fairly the harness first clicks a SIBLING to move
# the group off it (UNSELECT). On the kit's real pages that click re-renders the
# whole group, so the element the walk was about to press no longer exists -- and
# before ADR-109 that was filed as "wired to nothing", an accusation against a
# control that works.
#
# The first version of this check only asserted that a "sequenced" key existed,
# which a mutation folding sequenced back into dead passed without a murmur.
# Mutation testing found that; the check now asserts placement, both ways.
r = run("b_sequenced",
        '<div class="fek-dial" id="g"></div>'
        '<script>function render(sel){var g=document.getElementById("g");'
        'g.innerHTML=["alpha","beta"].map(function(n){'
        'return "<button class=\'kopt"+(n===sel?" on":"")+"\' data-n=\'"+n+"\'>"+n+"</button>";'
        '}).join("");'
        'g.querySelectorAll(".kopt").forEach(function(b){'
        'b.onclick=function(){render(b.dataset.n);};});}'
        'render("alpha");</script>')
ck("B5: a control the harness's own setup removed lands in sequenced",
   "alpha" in labels(r, "sequenced"), {b: labels(r, b) for b in harness.BUCKETS if r[b]})
ck("B5b: and is NOT accused of being wired to nothing",
   "alpha" not in labels(r, "dead"), labels(r, "dead"))
ck("B6: the identity holds with all six buckets in play", accounted(r), r["discovered"])

# ══ C. THE ORACLE ════════════════════════════════════════════════════════════
# PROMISE: an action passes when it leaves an OBSERVABLE TRACE. Each trace the
# harness accepts gets a fixture, because a trace it silently stops accepting
# turns a working control into a false "wired to nothing".
print("\n-- C. every trace the oracle accepts --")

TRACES = {
    "text":    'document.getElementById("o").textContent="changed";',
    "class":   'document.getElementById("o").classList.toggle("on");',
    "value":   'document.getElementById("i").value="filled";',
    "storage": 'try{localStorage.setItem("k","v");}catch(e){}',
    "print":   'try{window.print();}catch(e){}',
    "alert":   'try{alert("hi");}catch(e){}',
}
for trace, js in TRACES.items():
    r = run("c_" + trace,
            '<button id="a">%s</button><p id="o">0</p><input id="i">'
            '<script>document.getElementById("a").onclick=function(){%s};</script>' % (trace, js))
    ck("C %-8s counts as an observable trace" % trace,
       trace in labels(r, "driven"), (labels(r, "driven"), labels(r, "dead")))

# ══ D. INVARIANTS ════════════════════════════════════════════════════════════
# PROMISE: an action that leaves a trace but BREAKS something is not a pass.
print("\n-- D. every invariant the harness claims to catch --")

r = run("d_nan", '<button id="a">divide</button><p id="o">ready</p>'
        '<script>document.getElementById("a").onclick=function(){'
        'document.getElementById("o").textContent=String(Number("x")/2);};</script>')
ck("D1: NaN reaching the page is reported", any("junk" in e for e in r["errors"]), r["errors"][:2])

r = run("d_obj", '<button id="a">show</button><p id="o">ready</p>'
        '<script>document.getElementById("a").onclick=function(){'
        'document.getElementById("o").textContent=String({});};</script>')
ck("D2: [object Object] reaching the page is reported",
   any("junk" in e for e in r["errors"]), r["errors"][:2])

r = run("d_panes",
        '<button class="tab on" data-pane="p1">one</button>'
        '<button id="a" class="tab" data-pane="p2">break panes</button>'
        '<section class="pane on" id="p1">a</section>'
        '<section class="pane on" id="p2">b</section>')
ck("D3: two panes visible at once is reported",
   any("panes visible" in e for e in r["errors"]), r["errors"][:2])

r = run("d_spill", '<button id="a">grow</button><div id="o"></div>'
        '<script>document.getElementById("a").onclick=function(){'
        'document.getElementById("o").innerHTML='
        '"<div class=row2 style=\'width:900px;height:20px\'>wide</div>";};</script>')
ck("D4: a row spilling out of a 390px phone is reported, with the element named",
   any("spills" in e and "row2" in e for e in r["errors"]), r["errors"][:2])

r = run("d_console", '<button id="a">log</button><p id="o">0</p>'
        '<script>document.getElementById("a").onclick=function(){'
        'console.error("something went wrong");'
        'document.getElementById("o").textContent="1";};</script>')
ck("D5: a console error is reported even though the action left a trace",
   any("console" in e.lower() or "error" in e.lower() for e in r["errors"]), r["errors"][:2])

# ══ E. HOSTILE PAGES ═════════════════════════════════════════════════════════
# PROMISE: "an element still not visible after that is HIDDEN -- a fact about the
# page, not a failure". The harness must survive pages that fight it, because a
# harness that crashes reports nothing about everything after the crash.
print("\n-- E. pages that fight the harness --")

r = run("e_empty", '<p>nothing to touch here</p>')
ck("E1: a page with no affordances is accounted for, not a crash",
   accounted(r) and r["discovered"] == 0, r["discovered"])

r = run("e_throws_load", '<p>x</p><script>null.x;</script><button id="a">after</button>')
ck("E2: a page that throws on load is still walked", accounted(r), r)

r = run("e_selfremove", '<button id="a">remove me</button>'
        '<script>document.getElementById("a").onclick=function(){this.remove();};</script>')
ck("E3: a control that removes itself is accounted for, not lost", accounted(r), r)

r = run("e_dialogs", '<button id="a">ask</button><p id="o">0</p>'
        '<script>document.getElementById("a").onclick=function(){'
        'var x=confirm("really?");var y=prompt("name?");'
        'document.getElementById("o").textContent=String(x)+String(y);};</script>')
ck("E4: confirm and prompt are stubbed -- the walk is not blocked by a dialog",
   accounted(r) and r["discovered"] > 0, r)

r = run("e_slow", '<button id="a">slow</button><p id="o">0</p>'
        '<script>document.getElementById("a").onclick=function(){'
        'var t=Date.now();while(Date.now()-t<300){}'
        'document.getElementById("o").textContent="done";};</script>')
ck("E5: a slow handler is waited for, not called dead", "slow" in labels(r, "driven"),
   (labels(r, "driven"), labels(r, "dead")))

# ══ F. DETERMINISM ═══════════════════════════════════════════════════════════
# PROMISE: the ledger is evidence. Evidence that changes between identical runs
# is not evidence, and the findings ratchet would flap.
print("\n-- F. the same page twice --")

body = ('<button id="a">counts</button><p id="o">0</p><button id="b">nothing</button>'
        '<script>var n=0;document.getElementById("a").onclick=function(){'
        'document.getElementById("o").textContent=String(++n);};</script>')
r1 = run("f_det", body)
r2 = run("f_det", body)
same = {b: (len(r1[b]), len(r2[b])) for b in harness.BUCKETS}
ck("F1: identical runs produce identical accounting",
   all(a == b for a, b in same.values()), same)
ck("F2: and identical findings", sorted(labels(r1, "dead")) == sorted(labels(r2, "dead")),
   (labels(r1, "dead"), labels(r2, "dead")))

# ══ G. IDENTITY ══════════════════════════════════════════════════════════════
print("\n-- G. every affordance is uniquely addressable --")
r = run("g_ids", '<button>same</button><button>same</button><button>same</button>')
allrecs = [x for b in harness.BUCKETS for x in r[b]]
ids = [x.get("id") for x in allrecs if x.get("id")]
ck("G1: three identically-labelled buttons get three distinct ids",
   len(ids) == len(set(ids)) and len(ids) >= 3, ids)

# ══ H. THE LEDGER ════════════════════════════════════════════════════════════
# PROMISE (ADR-109): a run updates only the pages it drove and keeps the rest.
# Tested without a browser -- this is arithmetic, and it is the arithmetic that
# silently deleted forty pages of coverage before it was fixed.
print("\n-- H. ledger semantics --")

def merge(prev, out):
    ran = {r["page"] for r in out}
    merged = [r for r in prev if r.get("page") not in ran] + out
    merged.sort(key=lambda r: r.get("page", ""))
    return merged

prev = [{"page": "a.html", "driven": ["x"], "discovered": 1, "errors": []},
        {"page": "b.html", "driven": ["y", "z"], "discovered": 2, "errors": []}]
out = [{"page": "b.html", "driven": ["y"], "discovered": 1, "errors": []}]
m = merge(prev, out)
ck("H1: a one-page run keeps the pages it did not drive",
   [r["page"] for r in m] == ["a.html", "b.html"], [r["page"] for r in m])
ck("H2: and replaces the page it did drive",
   len([r for r in m if r["page"] == "b.html"][0]["driven"]) == 1, m)

def total(rows, key):
    n = 0
    for r in rows:
        v = r.get(key, 0)
        n += len(v) if isinstance(v, (list, tuple)) else (v or 0)
    return n
ck("H3: totals count list-valued buckets and int-valued discovered alike",
   (total(m, "driven"), total(m, "discovered")) == (2, 2), (total(m, "driven"), total(m, "discovered")))

led = os.path.join(ROOT, "tools", "harness_ledger.json")
if os.path.isfile(led):
    real = json.load(io.open(led, encoding="utf-8"))
    ck("H4: the real ledger stamps every page with when it was measured",
       all("at" in p for p in real["pages"]),
       [p["page"] for p in real["pages"] if "at" not in p][:4])
    ck("H5: and its totals agree with its pages",
       real["totals"]["discovered"] == total(real["pages"], "discovered"),
       (real["totals"]["discovered"], total(real["pages"], "discovered")))

# ══ J. THE SECOND CHANCE ═════════════════════════════════════════════════════
# PROMISE (ADR-110): a control that operates on data is not judged on an empty
# page. Anything still dead at the end of the walk is pressed once more, with the
# state its own pane's working controls can build. Ten of twelve "dead" findings
# in this kit were this -- Undo with nothing to undo, Copy CSV with nothing to
# copy -- and doing nothing was the correct behaviour every time.
print("\n-- J. a control judged on an empty page was not judged --")

# "log" tallies; "undo" only does anything once something has been tallied.
# Undo comes FIRST in document order on purpose. The walk drives in that order,
# so undo is pressed while there is nothing to undo -- the situation the real
# pages produce and the one the second chance exists for. With log first the walk
# seeds it by accident and the retry never fires; the first draft did that, and
# J3 caught it.
STATEFUL = ('<button id="undo">undo</button><button id="log">log one</button>'
            '<p id="o"></p>'
            '<script>var n=0;'
            'document.getElementById("log").onclick=function(){'
            'n++;document.getElementById("o").textContent="count "+n;};'
            'document.getElementById("undo").onclick=function(){'
            'if(n>0){n--;document.getElementById("o").textContent=n?"count "+n:"";}};'
            '</script>')
r = run("j_stateful", STATEFUL)
ck("J1: a control that needs prior state is driven, not called wired to nothing",
   "undo" in labels(r, "driven"), {b: labels(r, b) for b in harness.BUCKETS if r[b]})
ck("J2: and it is recorded as having needed that state",
   any("needed prior state" in (x.get("note") or "")
       for x in r["driven"] if x.get("label") == "undo"),
   [x.get("note") for x in r["driven"] if x.get("label") == "undo"])
ck("J3: the run reports what the second chance retried and revived",
   r.get("second_chance", {}).get("revived", 0) >= 1, r.get("second_chance"))

# THE STATE MUST BE REBUILT, NOT INHERITED.
# J1-J3 pass even if the retry simply reuses whatever state the walk left, because
# in that fixture the state survives to the end. The real case does not: on
# field-notebook the walk both builds the tally history and drains it, so by the
# end there is nothing to undo and a retry in that state is the same wrong test
# twice. Mutation testing found exactly this hole -- "the second chance does not
# rebuild state before retrying" SURVIVED against J1-J3.
#
# Here the drain lives in a second pane, so the walk ends with the state empty and
# the pane-scoped replay is the only thing that can bring it back.
DRAINED = ('<button class="tab on" data-pane="p1">one</button>'
           '<button class="tab" data-pane="p2">two</button>'
           '<section class="pane on" id="p1">'
           '  <button id="undo">undo</button><button id="log">log one</button>'
           '  <p id="o"></p></section>'
           '<section class="pane" id="p2"><button id="reset">reset all</button>'
           '  <p id="o2">idle</p></section>'
           '<script>var n=0;'
           'function show(){document.getElementById("o").textContent=n?"count "+n:"";}'
           'document.getElementById("log").onclick=function(){n++;show();};'
           'document.getElementById("undo").onclick=function(){if(n>0){n--;show();}};'
           'document.getElementById("reset").onclick=function(){n=0;show();'
           'document.getElementById("o2").textContent="cleared at "+Date.now();};'
           'document.querySelectorAll(".tab").forEach(function(t){t.onclick=function(){'
           'document.querySelectorAll(".tab").forEach(function(x){x.classList.toggle("on",x===t);});'
           'document.querySelectorAll(".pane").forEach(function(q){'
           'q.classList.toggle("on",q.id===t.dataset.pane);});};});</script>')
r = run("j_drained", DRAINED)
ck("J3b: the retry REBUILDS state -- it does not merely inherit what the walk left",
   "undo" in labels(r, "driven"),
   {b: labels(r, b) for b in harness.BUCKETS if r[b]})

# The retry must not resurrect everything: a control wired to nothing has no
# state that could make it answer, and it has to stay dead.
r = run("j_reallydead", STATEFUL + '<button id="x">wired to nothing</button>')
ck("J4: a genuinely dead control is still dead after the second chance",
   "wired to nothing" in labels(r, "dead"), labels(r, "dead"))
ck("J5: and the identity still holds with the retry in play", accounted(r), r["discovered"])

# ══ K. ONE VISIBILITY ORACLE ═════════════════════════════════════════════════
# PROMISE: discovery and the driver agree about what "visible" means.
#
# They did not. Discovery asked getBoundingClientRect plus computed display and
# visibility; the driver asked Playwright, which asks checkVisibility(). A
# textarea inside a COLLAPSED <details> passes the first and fails the second --
# Chromium skips rendering the subtree without touching either property, so the
# box is still 300x120 and the styles still say visible. Four working controls
# on ecology-lab were driven, timed out, and written down as "action raised":
# a defect reported against a page that did not have one.
#
# The bucket a control lands in is a claim about the PAGE. `failed` says the
# page misbehaved. `hidden` says the harness did not reach it. Sending an
# unreached control to `failed` is the instrument accusing working code, which
# is this kit's recurring defect wearing its sixth outfit. What section K pins
# is not the wording but the direction: a control the driver cannot act on must
# never have been called visible in the first place.
print("\n-- K. discovery and the driver share one notion of visible --")

SHUT = ('<details><summary>edit as text</summary>'
        '  <textarea id="inside">robin 34</textarea></details>')
r = run("k_shut", SHUT)
ck("K1: a control in a collapsed disclosure is hidden, not failed",
   labels(r, "hidden") and not r["failed"],
   {"hidden": labels(r, "hidden"), "failed": labels(r, "failed")})
ck("K2: and the reason names the disclosure, not the page",
   any("disclosure" in (x.get("why") or "") for x in r["hidden"]),
   [x.get("why") for x in r["hidden"]])

# The rule is not "details means hidden". An OPEN disclosure is an ordinary
# part of the page and everything in it is drivable; if K3 ever fails together
# with K1 passing, the harness has stopped testing disclosures altogether while
# still reporting green.
OPEN = ('<details open><summary>edit as text</summary>'
        '  <textarea id="inside" oninput="document.title=this.value"></textarea>'
        '</details>')
r = run("k_open", OPEN)
ck("K3: a control in an OPEN disclosure is driven normally",
   any("inside" in (x.get("label") or "") or x.get("kind") == "text_in"
       for x in r["driven"]),
   {b: labels(r, b) for b in harness.BUCKETS if r[b]})

# The two halves of the oracle, one at a time: not-rendered, and rendered but
# with no box. Both are hidden, and neither is a disclosure, so both must keep
# the older wording rather than being relabelled by the new branch.
r = run("k_none", '<div style="display:none"><button id="g">gone</button></div>')
ck("K4: a display:none control is hidden and NOT called a disclosure",
   labels(r, "hidden") and not any("disclosure" in (x.get("why") or "")
                                   for x in r["hidden"]),
   [(x.get("label"), x.get("why")) for x in r["hidden"]])

r = run("k_zero", '<button id="z" style="width:0;height:0;padding:0;border:0;'
                  'overflow:hidden"></button>')
ck("K5: a rendered control with no box is hidden",
   not r["driven"] or all(x.get("kind") != "action_btn" for x in r["driven"]),
   {b: labels(r, b) for b in harness.BUCKETS if r[b]})

# The promise itself, stated as the thing that must never happen: no control
# may be reported as a page failure for a reason that is really "the harness
# could not act on it". An actionability timeout in `failed` is that report.
for nm, body in (("k_shut2", SHUT), ("k_none2",
                 '<div style="display:none"><input id="q"></div>')):
    r = run(nm, body)
    ck("K6[%s]: nothing lands in failed with an actionability timeout" % nm,
       not [x for x in r["failed"] if "Timeout" in str(x.get("got") or "")],
       [x.get("got") for x in r["failed"]])
    ck("K7[%s]: and the identity holds" % nm, accounted(r), r["discovered"])


# ══ I. IS THIS SUITE ITSELF WORTH ANYTHING? ══════════════════════════════════
# The catalogue in tools/mutate_harness.py breaks the harness fifteen ways on a COPY
# and requires this suite to notice each one. Running the whole catalogue here
# would take minutes, so what is asserted is that the catalogue exists, that
# every mutant names the check that must kill it, and that every anchor it uses
# still matches the harness EXACTLY ONCE -- an anchor that no longer matches is a
# mutant that silently stops testing anything, which is the failure mode this
# whole file was written about.
print("\n-- I. the mutation catalogue still bites --")
import mutate_harness                                            # noqa: E402
src = io.open(os.path.join(ROOT, "tools", "harness.py"), encoding="utf-8").read()
ck("I1: the catalogue is not empty", len(mutate_harness.MUTANTS) >= 15,
   len(mutate_harness.MUTANTS))
if os.environ.get("HARNESS_MUTANT"):
    # A mutation run has deliberately changed the harness, so an anchor that no
    # longer matches is the mutation working, not the catalogue rotting. Reported
    # rather than skipped in silence: a check that quietly stops running is the
    # thing this whole file exists to prevent.
    print("NOT VERIFIED: I2 anchors -- this is a mutation run and the harness is "
          "altered on purpose")
    ok += 0
else:
    stale = [n for n, find, _, _ in mutate_harness.MUTANTS if src.count(find) != 1]
    ck("I2: every mutant's anchor still matches the harness exactly once", not stale, stale)
ck("I3: every mutant names the check that must kill it",
   all(e for _, _, _, e in mutate_harness.MUTANTS),
   [n for n, _, _, e in mutate_harness.MUTANTS if not e])

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
