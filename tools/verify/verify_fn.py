# -*- coding: utf-8 -*-
"""Suite for docs/field-notebook.html -- the tap-to-tally field notebook (ADR-173).

The notebook had no suite of its own: its task (ADR-165) held the page's figures
to hand-checked literals, and the three things the page HANDS OVER -- the .eco
lines, the CSV, the print -- were read by nothing. This suite drives the page
to the state the task leaves it in and holds what the page computes and what it
exports to independent statements:

  A. the arithmetic, from the formulas the page states in its own prose:
     Shannon H' = -sum p ln p, Pielou J' = H'/ln S, Hill N1 = e^H', the
     quadrats' variance/mean and Morisita's index n*sum(x(x-1))/(N(N-1)),
     and the Lincoln-Petersen estimate N = M*C/R.
  B. the .eco lines, from the .eco grammar (one directive per line; `data:`
     is a community name followed by name=count pairs; `model: markrecapture
     M C R`), and the CSV from RFC 4180 (a field holding a comma is quoted).
  C. the TASK's literals -- what page-field-notebook-science.json holds the
     copied .eco and CSV to -- are those same texts, so a literal that merely
     transcribed whatever the page emitted is caught here.

Run:  python3 tools/verify/verify_fn.py
"""
import io, json, math, os, re, sys
from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PAGE = "file://" + os.path.join(ROOT, "docs", "field-notebook.html").replace(os.sep, "/")
TASK = os.path.join(ROOT, "tools", "tasks", "page-field-notebook-science.json")

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))

# ---- the state the task leaves the notebook in --------------------------------
SPECIES = [("species-a", 6), ("species-b", 3), ("clover", 1)]     # clover is added
QUADS = [0, 1, 2, 9]
MR = (5, 4, 2)                                                     # marked, caught, recaptured
ETHO = [("forage", 4), ("preen", 2)]                               # preen is added
SESSION = ("oak ridge, plot 3", "R. Ellison", "2026-09-09")

# ---- A. the arithmetic, stated independently ----------------------------------
def shannon(counts):
    n = float(sum(counts))
    return -sum((c / n) * math.log(c / n) for c in counts if c > 0)
def evenness(counts):
    s = sum(1 for c in counts if c > 0)
    return shannon(counts) / math.log(s) if s > 1 else 1.0
def dispersion(counts):
    n = len(counts); mean = sum(counts) / float(n)
    var = sum((c - mean) ** 2 for c in counts) / (n - 1)
    big = sum(counts)
    mor = n * sum(c * (c - 1) for c in counts) / float(big * (big - 1))
    return mean, var / mean, mor

# ---- B. the exports, from the grammar and RFC 4180 ------------------------------
def eco_lines(session, etho, species, quads, mr):
    site, obs, date = session
    lines = ["# Field Notebook export — paste into your .eco protocol",
             "# site %s — observer %s — %s" % (site, obs, date),
             "data: focal " + " ".join("%s=%d" % x for x in etho),
             "data: site " + " ".join("%s=%d" % x for x in species),
             "# quadrat counts (per frame): " + " ".join(str(q) for q in quads),
             "model: markrecapture %d %d %d" % mr,
             "note: tallied in the field with the Field Notebook"]
    return "\n".join(lines)

def csv_cell(s):
    s = str(s)
    return '"' + s.replace('"', '""') + '"' if re.search(r'[",\n]', s) else s
def csv_text(session, etho, species, quads, mr):
    site, obs, date = session
    rows = [["section", "item", "count"], ["session", "site", site],
            ["session", "observer", obs], ["session", "date", date]]
    rows += [["ethogram", n, c] for n, c in etho]
    rows += [["species", n, c] for n, c in species]
    rows += [["quadrat", "Q%d" % (i + 1), q] for i, q in enumerate(quads)]
    rows += [["markrecapture", "marked", mr[0]], ["markrecapture", "caught", mr[1]],
             ["markrecapture", "recaptured", mr[2]]]
    return "\n".join(",".join(csv_cell(c) for c in r) for r in rows)

WANT_ECO = eco_lines(SESSION, ETHO, SPECIES, QUADS, MR)
WANT_CSV = csv_text(SESSION, ETHO, SPECIES, QUADS, MR)

errors = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844})
    ctx.add_init_script(
        "Object.defineProperty(navigator, 'clipboard', {get: () => ({"
        "writeText: t => { window.__copied = t; return Promise.resolve(); }})});"
        "window.print = () => { window.__printed = (window.__printed || 0) + 1; };")
    pg = ctx.new_page()
    pg.on("console", lambda m: errors.append(m.text)
          if m.type == "error" and "Failed to load resource" not in m.text else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(PAGE, wait_until="domcontentloaded"); pg.wait_for_timeout(300)

    def tap(grid, name, n):
        for _ in range(n):
            pg.click("#%s .tally:has(.name:text-is('%s'))" % (grid, name))
    def step(sel, n):
        for _ in range(n):
            pg.click(sel)
    def tile(box, label):
        return pg.evaluate("""([b,l])=>{const t=[...document.querySelectorAll('#'+b+' .tile')]
          .find(x=>x.querySelector('.l').textContent.trim()===l);
          return t ? t.querySelector('.v').textContent.trim() : null;}""", [box, label])

    # species
    pg.click(".tab[data-pane='p-spec']")
    tap("specGrid", "species-a", 6); tap("specGrid", "species-b", 3)
    pg.fill("#specNew", "clover"); pg.click("#specAdd"); tap("specGrid", "clover", 1)
    counts = [c for _, c in SPECIES]
    ck("species: individuals and species counted", tile("specResults", "individuals") == "10"
       and tile("specResults", "species") == "3", (tile("specResults", "individuals"), tile("specResults", "species")))
    ck("species: Shannon H' is -sum p ln p to two places", tile("specResults", "Shannon H′") == "%.2f" % shannon(counts),
       (tile("specResults", "Shannon H′"), shannon(counts)))
    ck("species: Pielou J' is H'/ln S", tile("specResults", "evenness J′") == "%.2f" % evenness(counts),
       tile("specResults", "evenness J′"))
    ck("species: the effective number is e^H'", tile("specResults", "effective (species)") == "%.1f" % math.exp(shannon(counts)),
       tile("specResults", "effective (species)"))
    # quadrats
    pg.click(".tab[data-pane='p-quad']")
    for i, q in enumerate(QUADS):
        step("#quadGrid .quad:nth-child(%d) .step[data-d='1']" % (i + 1), q)
    mean, vmr, mor = dispersion(QUADS)
    ck("quadrats: mean per frame", tile("quadResults", "mean / quadrat") == "%.2f" % mean, tile("quadResults", "mean / quadrat"))
    ck("quadrats: variance/mean (sample variance)", tile("quadResults", "variance / mean") == "%.2f" % vmr,
       (tile("quadResults", "variance / mean"), vmr))
    ck("quadrats: Morisita's index n*sum(x(x-1))/(N(N-1))", tile("quadResults", "Morisita") == "%.2f" % mor,
       (tile("quadResults", "Morisita"), mor))
    ck("quadrats: a variance/mean above 1.4 reads clumped", "clumped" in pg.text_content("#quadResults") and vmr > 1.4,
       pg.text_content("#quadResults")[:80])
    # mark-recapture
    pg.click(".tab[data-pane='p-more']")
    step(".step[data-mr='M'][data-d='1']", MR[0]); step(".step[data-mr='C'][data-d='1']", MR[1])
    ck("mark-recapture: no recapture, no estimate -- and the page says so in words",
       "undefined" in pg.text_content("#mrOut"), pg.text_content("#mrOut")[:80])
    step(".step[data-mr='R'][data-d='1']", MR[2])
    n_hat = MR[0] * MR[1] / float(MR[2])
    ck("mark-recapture: Lincoln-Petersen N = M*C/R, rounded", ("N̂ ≈ %d" % round(n_hat)) in pg.text_content("#mrOut"),
       pg.text_content("#mrOut")[:80])
    # ethogram
    pg.click(".tab[data-pane='p-etho']")
    tap("ethoGrid", "forage", 4)
    pg.fill("#ethoNew", "preen"); pg.click("#ethoAdd"); tap("ethoGrid", "preen", 2)
    ck("ethogram: the added behaviour is in the budget", tile("ethoResults", "observations") == "6"
       and tile("ethoResults", "behaviors") == "2", (tile("ethoResults", "observations"), tile("ethoResults", "behaviors")))
    # session
    pg.click(".tab[data-pane='p-more']")
    pg.fill("#sSite", SESSION[0]); pg.fill("#sObs", SESSION[1]); pg.fill("#sDate", SESSION[2])
    pg.dispatch_event("#sDate", "input")

    # ---- B. what the page hands over ----
    ck("the .eco box shows the grammar's lines, byte for byte", pg.text_content("#ecoOut") == WANT_ECO,
       pg.text_content("#ecoOut"))
    pg.click("#ecoCopy"); pg.wait_for_timeout(100)
    ck("Copy .eco lines puts exactly those lines on the clipboard", pg.evaluate("window.__copied || ''") == WANT_ECO,
       pg.evaluate("window.__copied || ''")[:120])
    pg.click("#csvCopy"); pg.wait_for_timeout(100)
    got_csv = pg.evaluate("window.__copied || ''")
    ck("Copy CSV puts one row per tally under section,item,count", got_csv == WANT_CSV, got_csv[:160])
    ck("...and a site that carries a comma is quoted (RFC 4180), not split", '"oak ridge, plot 3"' in got_csv
       and len(got_csv.split("\n")) == 16, got_csv.split("\n")[1])
    pg.click("#p-more button:has-text('Print / save PDF')"); pg.wait_for_timeout(50)
    ck("Print / save PDF prints, once", pg.evaluate("window.__printed || 0") == 1, pg.evaluate("window.__printed"))
    b.close()

# ---- C. the task holds those same texts ---------------------------------------
task = json.load(io.open(TASK, encoding="utf-8")) if os.path.isfile(TASK) else {"steps": []}
steps = dict((s["id"], s) for s in task["steps"])
ck("the task holds the copied .eco lines to the grammar's text",
   steps.get("g173-eco", {}).get("expect", {}).get("output.payloads.0.text") == WANT_ECO
   and steps.get("g173-eco", {}).get("expect", {}).get("output.payloads.0.k") == "clipboard", steps.get("g173-eco"))
ck("the task holds the copied CSV to RFC 4180's text",
   steps.get("g173-csv", {}).get("expect", {}).get("output.payloads.0.text") == WANT_CSV
   and steps.get("g173-csv", {}).get("expect", {}).get("output.payloads.0.k") == "clipboard", steps.get("g173-csv"))
ck("the task holds the print to a print, and nothing else leaving with it",
   steps.get("g173-printed", {}).get("expect", {}).get("output.payloads.0.k") == "print"
   and steps.get("g173-printed", {}).get("expect", {}).get("output.payloads.1") == {"op": "exists", "value": False},
   steps.get("g173-printed"))
ck("the task's figures are the arithmetic's: N = %d, H' = %.2f, Morisita %.2f" % (round(n_hat), shannon(counts), mor),
   any(("N̂ ≈ %d" % round(n_hat)) in json.dumps(s.get("expect", {}), ensure_ascii=False) for s in task["steps"])
   and any(s.get("expect", {}).get("output.by.specResults.Shannon H′") == "%.2f" % shannon(counts) for s in task["steps"])
   and any(s.get("expect", {}).get("output.by.quadResults.Morisita") == "%.2f" % mor for s in task["steps"]))

ck("zero console/page errors", not errors, errors[:3])
print("%d/%d" % (ok, ok + bad))
sys.exit(0 if bad == 0 else 1)
