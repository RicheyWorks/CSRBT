# -*- coding: utf-8 -*-
"""Suite for docs/experiment-guide.html — the experiment guider.

Behaviour, not layout (the kit-wide audits own targets, contrast, print,
offline): that the designer emits a protocol the .eco grammar actually
accepts, that a hostile study name never comes back as markup, that a
two-community metric refuses one community, and that entries survive a
reload. The expected .eco lines below are written from the grammar in
ExperimentSpec's javadoc, not transcribed from the page's JavaScript —
a test that transcribes the implementation agrees with every bug in it.

Run:  python3 tools/verify/verify_experiment_guide.py
"""
import os, re, sys
from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PAGE = "file://" + os.path.join(ROOT, "docs", "experiment-guide.html").replace(os.sep, "/")
SRC = os.path.join(ROOT, "docs", "experiment-guide.html")

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))

src = open(SRC, encoding="utf-8").read()
ids = re.findall(r'\sid="([^"]+)"', src)
dupes = sorted({i for i in ids if ids.count(i) > 1})
ck("no duplicate ids", not dupes, dupes)
refs = {b for a, b in re.findall(r'(getElementById|\$)\("([^"]+)"\)', src)}
missing = sorted(x for x in refs if x not in set(ids))
ck("every literal JS id reference exists", not missing, missing)

errors = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    pg.on("console", lambda m: errors.append(m.text)
          if m.type == "error" and "Failed to load resource" not in m.text else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(PAGE, wait_until="domcontentloaded"); pg.wait_for_timeout(300)

    # tabs actually switch panes
    pg.click("#tab-designer")
    ck("designer pane shows on its tab", pg.is_visible("#pane-designer"))
    ck("method pane hides", not pg.is_visible("#pane-method"))

    # ── build a protocol through the real controls ──
    pg.fill("#e-name", "meadow disturbance study")
    pg.fill("#p-name", "graze"); pg.click("#p-add")
    pg.select_option("#p-kind", "hot"); pg.fill("#p-name", "bloom")
    pg.fill("#p-hotset", "5"); pg.fill("#p-hotshare", "90"); pg.click("#p-add")
    pg.select_option("#p-kind", "churn"); pg.fill("#p-name", "seasons"); pg.fill("#p-addpct", "55"); pg.click("#p-add")
    pg.select_option("#m-kind", "logistic"); pg.fill("#m-params", "0.15 120 5 60"); pg.click("#m-add")
    pg.fill("#d-name", "pondA"); pg.fill("#d-counts", "cattail=18 duckweed=44"); pg.click("#d-add")
    pg.fill("#f-area", "0.5")
    pg.fill("#e-notes", "sampled after two dry weeks\nbloom: five keys took the traffic")
    pg.select_option("#x-metric", "evenness"); pg.fill("#x-args", "graze")
    pg.select_option("#x-op", ">"); pg.fill("#x-val", "0.9"); pg.click("#x-add")
    pg.select_option("#x-metric", "brayCurtis"); pg.fill("#x-args", "graze"); pg.click("#x-add")   # must refuse
    pg.fill("#x-args", "graze, bloom"); pg.fill("#x-val", "0.5"); pg.click("#x-add")
    pg.select_option("#x-metric", "q-survivorship"); pg.select_option("#x-word", "type3"); pg.click("#x-add")

    eco = pg.text_content("#eco-out")
    # Expected lines per the .eco grammar (ExperimentSpec javadoc), not per the page's JS.
    for want in ["name: meadow disturbance study",
                 "phase: graze uniform 2000",
                 "phase: bloom hot 2000 5 90",
                 "phase: seasons churn 2000 55",
                 "factor: area 0.5",
                 "model: logistic 0.15 120 5 60",
                 "data: pondA cattail=18 duckweed=44",
                 "note: sampled after two dry weeks",
                 "note(bloom): five keys took the traffic",
                 "expect: evenness(graze) > 0.9",
                 "expect: brayCurtis(graze, bloom) > 0.5",
                 "expect: survivorship is type3"]:
        ck("eco emits %r" % want, want in eco, eco[:400])
    ck("a two-community metric refused one community", eco.count("expect:") == 3, eco.count("expect:"))
    # every emitted directive line is one the grammar names
    DIRECTIVE = re.compile(r"^(name|keys|seed|window|phase|factor|model|cross|data|note(\([A-Za-z0-9_-]+\))?|tree|expect):")
    stray = [l for l in eco.splitlines() if l.strip() and not l.startswith("#") and not DIRECTIVE.match(l)]
    ck("no line outside the .eco grammar", not stray, stray)
    ck("the run command carries the study's slug",
       "-Pspec=meadow-disturbance-study.eco" in pg.text_content("#eco-cmd"), pg.text_content("#eco-cmd"))

    # ── escaping: what you type never comes back as markup ──
    pg.fill("#e-name", '<img src=x onerror="window.__pwned=1">')
    pg.wait_for_timeout(200)
    ck("hostile study name did not execute", pg.evaluate("!window.__pwned"))
    ck("hostile study name rendered as text", "<img" in pg.text_content("#eco-out"))
    pg.fill("#e-name", "meadow disturbance study")

    # ── engineering track ──
    pg.click("#track-eng")
    ck("engineering track shows", pg.is_visible("#eng-track"))
    ck("ecology track hides", not pg.is_visible("#eco-track"))
    pg.fill("#g-question", "What does one cold scan cost?")
    pg.fill("#g-floor", "reading the bytes once")
    pg.fill("#g-sizes", "20000, 60000")
    pg.fill("#g-rule", "fires above 5x the floor")
    pre = pg.text_content("#eng-out")
    for want in ["What does one cold scan cost?", "reading the bytes once",
                 "Pre-registered rule:", "fires above 5x the floor", "median kept"]:
        ck("pre-registration carries %r" % want, want in pre, pre[:300])
    ck("the verdict slot is explicit and empty before the run", "VERDICT:" in pre and "append after the run" in pre, pre[-160:])

    # ── persistence: entries survive a reload (guarded storage) ──
    pg.click("#tab-checklist"); pg.check("#c1")
    pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(300)
    ck("chosen track persisted", not pg.evaluate("document.getElementById('eng-track').hidden"))
    ck("checklist tick persisted", pg.is_checked("#c1"))
    ck("phases persisted", "graze" in pg.text_content("#p-list"))

    b.close()

ck("zero console/page errors", not errors, errors[:3])
print("%d/%d" % (ok, ok + bad))
sys.exit(0 if bad == 0 else 1)
