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

def io_open(path):
    import io
    return io.open(path, encoding="utf-8").read()

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
    # a dataset may not take a name a phase already holds — even the FIRST one
    n_ds = pg.eval_on_selector_all("#d-list .chip", "c => c.length")
    pg.fill("#d-name", "graze"); pg.fill("#d-counts", "x=1"); pg.click("#d-add")
    ck("dataset colliding with a phase name refused",
       pg.eval_on_selector_all("#d-list .chip", "c => c.length") == n_ds)
    ck("collision refusal names the rule", "is taken" in pg.text_content("#toast"),
       pg.text_content("#toast"))
    pg.fill("#d-name", ""); pg.fill("#d-counts", "")
    # a malformed eulerlotka is refused with the parser's own words
    pg.select_option("#m-kind", "eulerlotka"); pg.fill("#m-params", "1.0:0"); pg.click("#m-add")
    ck("eulerlotka refusal uses the parser's message",
       "eulerlotka needs >= 2 lx:mx pairs" in pg.text_content("#toast"), pg.text_content("#toast"))
    pg.fill("#m-params", "")
    pg.fill("#f-area", "0.5")
    # one note targets graze — the FIRST community, index 0, the classic off-by-one seat
    pg.fill("#e-notes", "sampled after two dry weeks\nbloom: five keys took the traffic\ngraze: even traffic, as designed")
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
                 "note(graze): even traffic, as designed",
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

    # ── pre-flight lint mirrors ExperimentSpec.parse ──
    lint = pg.text_content("#lint")
    ck("a well-formed protocol lints clean", "would parse clean" in lint, lint)
    # an expectation naming a community that doesn't exist → UNGRADEABLE warning
    pg.select_option("#x-metric", "shannon"); pg.fill("#x-args", "ghost")
    pg.fill("#x-val", "1"); pg.click("#x-add")
    lint = pg.text_content("#lint")
    ck("unknown community warned as UNGRADEABLE", "ghost" in lint and "UNGRADEABLE" in lint, lint)
    # a phase-vs-dataset comparison → UNGRADEABLE warning (they share no species)
    pg.select_option("#x-metric", "jaccard"); pg.fill("#x-args", "graze, pondA")
    pg.fill("#x-val", "0.5"); pg.click("#x-add")
    lint = pg.text_content("#lint")
    ck("phase-vs-data compare warned as UNGRADEABLE", "share no species" in lint, lint)
    # remove the two bad hypotheses (last two chips) and the lint goes clean again
    pg.eval_on_selector_all("#x-list .chip button", "b => { b[b.length-1].click(); }")
    pg.eval_on_selector_all("#x-list .chip button", "b => { b[b.length-1].click(); }")
    ck("lint clean after removing them", "would parse clean" in pg.text_content("#lint"),
       pg.text_content("#lint"))
    # a model with the wrong arity is refused at the door (logistic needs 4)
    n_models = pg.eval_on_selector_all("#m-list .chip", "c => c.length")
    pg.select_option("#m-kind", "logistic"); pg.fill("#m-params", "0.15 120 5"); pg.click("#m-add")
    ck("wrong-arity model refused", pg.eval_on_selector_all("#m-list .chip", "c => c.length") == n_models)
    pg.fill("#m-params", "")
    # a duplicate community name is refused (expectations address communities by name)
    n_ph = pg.eval_on_selector_all("#p-list .chip", "c => c.length")
    pg.fill("#p-name", "graze"); pg.click("#p-add")
    ck("duplicate phase name refused", pg.eval_on_selector_all("#p-list .chip", "c => c.length") == n_ph)
    # junk in the extra-directives box → PROBLEM row
    pg.fill("#e-extra", "wibble: 3")
    lint = pg.text_content("#lint")
    ck("unknown extra directive flagged", "unknown directive 'wibble'" in lint, lint)
    pg.fill("#e-extra", "cross: Rr x Rr observed 5474 1850")
    ck("a known extra directive passes", "would parse clean" in pg.text_content("#lint"),
       pg.text_content("#lint"))
    pg.fill("#e-extra", "")
    # keys below the parser's floor → PROBLEM row
    pg.fill("#e-keys", "1")
    ck("keys below [2, 1000000] flagged", "keys out of range" in pg.text_content("#lint"))
    pg.fill("#e-keys", "100")
    # a note targeting an undeclared name stays a plain note (the parser would report it)
    pg.fill("#e-notes", "ghost: a note for nobody")
    eco2 = pg.text_content("#eco-out")
    ck("note with unknown target stays unattached", "note: ghost: a note for nobody" in eco2
       and "note(ghost)" not in eco2, eco2[-200:])
    pg.fill("#e-notes", "sampled after two dry weeks\nbloom: five keys took the traffic")

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
    ck("empty pre-registration lints as missing", "MISSING" in pg.text_content("#eng-lint"),
       pg.text_content("#eng-lint"))
    pg.fill("#g-question", "What does one cold scan cost?")
    pg.fill("#g-floor", "reading the bytes once")
    pg.fill("#g-sizes", "20000, 60000")
    pg.fill("#g-rule", "fires above 5x the floor")
    # empty measurement rows print blanks, never the token "undefined"
    ck("blank rows print blanks", "undefined" not in pg.text_content("#eng-out"),
       pg.text_content("#eng-out"))
    lint = pg.text_content("#eng-lint")
    ck("eng lint clean once question, floor, rule, sizes are in",
       "pre-registration complete" in lint, lint)
    pre = pg.text_content("#eng-out")
    for want in ["What does one cold scan cost?", "reading the bytes once",
                 "Pre-registered rule:", "fires above 5x the floor", "median kept"]:
        ck("pre-registration carries %r" % want, want in pre, pre[:300])
    ck("the verdict slot is explicit and empty before the run", "VERDICT:" in pre and "append after the run" in pre, pre[-160:])

    # ── the verdict step: computed ratios, and a declaration the page guards ──
    # a verdict clicked before any measured row leaves the slot empty
    pg.click("#vd-fires")
    ck("verdict refused before measurements", "append after the run" in pg.text_content("#eng-out"),
       pg.text_content("#eng-out")[-160:])
    pg.fill("#g-phases", "inflate, recover, scan")
    n_inputs = pg.eval_on_selector_all("#meas input", "i => i.length")
    ck("measurement inputs: (3 phases + floor) x 2 sizes", n_inputs == 8, n_inputs)
    # the cold-scan numbers at n=60000; expected values recomputed here, not transcribed
    inflate, recover, scan, floor = 29.0, 61.0, 434.0, 1.0
    total = inflate + recover + scan
    ratio = round(total / floor)
    pg.fill('input[aria-label="inflate (ms) at n = 60000"]', "29")
    pg.fill('input[aria-label="recover (ms) at n = 60000"]', "61")
    pg.fill('input[aria-label="scan (ms) at n = 60000"]', "434")
    pg.fill('input[aria-label="floor (ms) at n = 60000"]', "1")
    pre = pg.text_content("#eng-out")
    want_row = "| 60000 | 29 | 61 | 434 | 1 | %g | %d× |" % (total, ratio)
    ck("table row computed from entered numbers", want_row in pre, pre)
    # rows are in, verdict is not declared yet: the slot stays honestly empty,
    # and no incomplete cell ever prints as the token "undefined" (the NaN-in-
    # session.json failure class, ADR-019's edge-case pass, on this page)
    ck("verdict slot still empty with rows in but nothing declared",
       "append after the run" in pre, pre[-200:])
    ck("no undefined leaks into the table", "undefined" not in pre, pre)
    ck("computed line shows the ratio against the floor",
       ("%d× the floor" % ratio) in pg.text_content("#meas"), pg.text_content("#meas"))
    # with a rule and a complete row, the declaration lands verbatim
    pg.fill("#g-verdict-note", "524x against a 5x bar - fire it")
    pg.click("#vd-fires")
    pre = pg.text_content("#eng-out")
    ck("declared verdict lands in house style",
       "**VERDICT: THE TRIGGER FIRES** — 524x against a 5x bar - fire it" in pre, pre[-220:])
    # a floor of zero yields no ratio, never a division artifact
    pg.fill('input[aria-label="inflate (ms) at n = 20000"]', "1")
    pg.fill('input[aria-label="recover (ms) at n = 20000"]', "1")
    pg.fill('input[aria-label="scan (ms) at n = 20000"]', "1")
    pg.fill('input[aria-label="floor (ms) at n = 20000"]', "0")
    ck("zero floor shows no ratio", "| 20000 | 1 | 1 | 1 | 0 | 3 | — |" in pg.text_content("#eng-out"),
       pg.text_content("#eng-out"))
    ck("no Infinity or NaN leaks into the report",
       "Infinity" not in pg.text_content("#eng-out") and "NaN" not in pg.text_content("#eng-out"))

    # ── persistence: entries survive a reload (guarded storage) ──
    pg.click("#tab-checklist"); pg.check("#c1"); pg.check("#c10")
    pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(300)
    ck("chosen track persisted", not pg.evaluate("document.getElementById('eng-track').hidden"))
    ck("checklist tick persisted", pg.is_checked("#c1"))
    ck("the LAST checklist tick persisted too (inclusive loop bound)", pg.is_checked("#c10"))
    pg.click("#tab-checklist"); pg.click("#cl-clear")
    ck("clear reaches the last box as well", not pg.is_checked("#c10") and not pg.is_checked("#c1"))
    pg.check("#c1"); pg.check("#c3")
    ck("phases persisted", "graze" in pg.text_content("#p-list"))
    ck("measurements persisted", pg.input_value('input[aria-label="scan (ms) at n = 60000"]') == "434",
       pg.input_value('input[aria-label="scan (ms) at n = 60000"]'))
    ck("verdict persisted", "THE TRIGGER FIRES" in pg.text_content("#eng-out"),
       pg.text_content("#eng-out")[-160:])

    # ── import: the reverse path, against the shipped sample ──
    # Expected counts recomputed from the sample file itself, comments stripped
    # the way the parser strips them — not transcribed from the page's JS.
    sample = io_open(os.path.join(ROOT, "docs", "sample-experiment.eco"))
    dirs = [l for l in (re.sub(r"#.*$", "", raw).strip() for raw in sample.split("\n")) if l]
    want = {p: sum(1 for l in dirs if l.startswith(p + ":"))
            for p in ("phase", "model", "data", "expect", "cross", "tree")}
    pg.click("#tab-designer"); pg.click("#track-eco")
    pg.click("#imp-card summary")
    pg.fill("#imp-text", sample); pg.click("#imp-go")
    ck("import restored every phase", pg.eval_on_selector_all("#p-list .chip", "c => c.length") == want["phase"],
       (pg.eval_on_selector_all("#p-list .chip", "c => c.length"), want["phase"]))
    ck("import restored every model", pg.eval_on_selector_all("#m-list .chip", "c => c.length") == want["model"],
       (pg.eval_on_selector_all("#m-list .chip", "c => c.length"), want["model"]))
    ck("import restored every dataset", pg.eval_on_selector_all("#d-list .chip", "c => c.length") == want["data"],
       (pg.eval_on_selector_all("#d-list .chip", "c => c.length"), want["data"]))
    ck("import restored every hypothesis", pg.eval_on_selector_all("#x-list .chip", "c => c.length") == want["expect"],
       (pg.eval_on_selector_all("#x-list .chip", "c => c.length"), want["expect"]))
    ck("import kept the study name", pg.input_value("#e-name") == "meadow disturbance study",
       pg.input_value("#e-name"))
    extra = pg.input_value("#e-extra")
    ck("cross and tree directives kept in the extra box",
       extra.count("cross:") == want["cross"] and extra.count("tree:") == want["tree"], extra)
    ck("the shipped sample lints clean", "would parse clean" in pg.text_content("#lint"),
       pg.text_content("#lint"))
    # emit → import → emit is a fixed point
    emit1 = pg.text_content("#eco-out")
    pg.fill("#imp-text", emit1); pg.click("#imp-go")
    emit2 = pg.text_content("#eco-out")
    ck("emit-import-emit is a fixed point", emit1 == emit2,
       [a for a, b2 in zip(emit1.split("\n"), emit2.split("\n")) if a != b2][:3])
    # junk survives import into the extra box, where the lint names it
    pg.fill("#imp-text", "wibble: 1\nphase: x wobble 5"); pg.click("#imp-go")
    lint = pg.text_content("#lint")
    ck("imported unknown directive named", "unknown directive 'wibble'" in lint, lint)
    # a photograph dropped on the import card is refused by name, and nothing
    # is imported (ADR-128: the harness's page walk dropped one and a run of
    # its bytes pushed the page 30px sideways on a phone)
    before = pg.text_content("#eco-out")
    pg.evaluate("""() => {
      const dt = new DataTransfer();
      dt.items.add(new File([new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0, 16, 74, 70, 73, 70, 0, 1])], "IMG_0431.jpg", {type: "image/jpeg"}));
      const e = new DragEvent("drop", {bubbles: true, cancelable: true, dataTransfer: dt});
      document.getElementById("imp-card").dispatchEvent(e); }""")
    pg.wait_for_timeout(200)
    ck("a JPEG dropped on the import card is refused by name", "Not a text file: IMG_0431.jpg" in pg.text_content("#toast"),
       pg.text_content("#toast"))
    ck("and nothing was imported", pg.text_content("#eco-out") == before, pg.text_content("#eco-out")[:80])
    pg.evaluate("""() => {
      const dt = new DataTransfer();
      dt.items.add(new File([new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0, 16])], "no-type.bin", {type: ""}));
      document.getElementById("imp-card").dispatchEvent(new DragEvent("drop", {bubbles: true, cancelable: true, dataTransfer: dt})); }""")
    pg.wait_for_timeout(300)
    ck("a typeless binary is refused by its bytes", "Not a text file: no-type.bin" in pg.text_content("#toast"),
       pg.text_content("#toast"))
    ck("a lint row cannot push the page sideways: long tokens wrap",
       pg.evaluate("() => getComputedStyle(document.querySelector('.lint .row') || document.body).overflowWrap") == "anywhere"
       or "overflow-wrap:anywhere" in src.replace(" ", ""), "no .lint .row / no rule")
    ck("imported unknown phase kind named", "unknown phase kind 'wobble'" in lint, lint)
    # the smallest legal data line — label plus ONE count — imports as a dataset
    pg.fill("#imp-text", "name: tiny\ndata: solo cattail=3"); pg.click("#imp-go")
    ck("two-token data line imports as a dataset",
       pg.eval_on_selector_all("#d-list .chip", "c => c.length") == 1
       and "solo" in pg.text_content("#d-list"), pg.text_content("#d-list"))

    # ── the copy path, exercised both ways ──
    # (a) clipboard present: capture what lands on it and pin the emitted texts
    ctx2 = b.new_context(viewport={"width": 390, "height": 844})
    ctx2.add_init_script(
        "Object.defineProperty(navigator, 'clipboard', {get: () => ({"
        "writeText: t => { window.__copied = t; return Promise.resolve(); }})});")
    p2 = ctx2.new_page()
    p2.on("pageerror", lambda e: errors.append("clip: " + str(e)))
    p2.goto(PAGE, wait_until="domcontentloaded"); p2.wait_for_timeout(300)
    p2.click("#tab-designer"); p2.click("#track-eco")
    p2.fill("#e-name", "copy check"); p2.fill("#p-name", "graze"); p2.click("#p-add")
    p2.click("#eco-copy"); p2.wait_for_timeout(100)
    copied = p2.evaluate("window.__copied || ''")
    ck("Copy .eco puts the emitted protocol on the clipboard",
       "name: copy check" in copied and "phase: graze uniform 2000" in copied, copied[:200])
    p2.click("#track-eng"); p2.click("#eng-skel"); p2.wait_for_timeout(100)
    skel = p2.evaluate("window.__copied || ''")
    for want in ["static final long SEED", "TIMED_PASSES", "java.util.Arrays.sort(t)",
                 "t[TIMED_PASSES / 2]", "Math.max(1, floor)", "measureFloor"]:
        ck("skeleton carries %r" % want, want in skel, skel[:300])
    # (b) clipboard absent: the fallback path answers with a toast, never a crash
    ctx3 = b.new_context(viewport={"width": 390, "height": 844})
    ctx3.add_init_script("Object.defineProperty(navigator, 'clipboard', {get: () => undefined});")
    p3 = ctx3.new_page()
    p3.on("pageerror", lambda e: errors.append("noclip: " + str(e)))
    p3.goto(PAGE, wait_until="domcontentloaded"); p3.wait_for_timeout(300)
    p3.click("#tab-designer"); p3.click("#track-eco"); p3.click("#eco-copy"); p3.wait_for_timeout(150)
    ck("copy without a clipboard falls back and speaks",
       p3.text_content("#toast").strip() != "", p3.text_content("#toast"))

    b.close()

ck("zero console/page errors", not errors, errors[:3])
print("%d/%d" % (ok, ok + bad))
sys.exit(0 if bad == 0 else 1)
