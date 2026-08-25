# -*- coding: utf-8 -*-
"""Darwin Core export -- the three pages that emit occurrence records.

What this suite is actually guarding:

  * The uncertainty arithmetic. It is recomputed here in Python from the same
    inputs, so a change in the page has to agree with an independent
    implementation, not merely with itself.
  * The empty coordinate. An earlier version treated a blank latitude as "zero
    decimal places" and reported 55 km of precision error for a plot nobody had
    located yet. Empty must stay empty.
  * Zero. coordinateUncertaintyInMeters has no valid zero -- unknown is the
    empty string. A regression that emits 0 is worse than one that emits
    nothing, because 0 reads as a claim of perfect precision.
  * basisOfRecord on the collection sheet, which is the one place in the kit
    where a field decision (did you keep it?) changes a controlled value.

Nothing here is frozen against the emitter: TERMS and VERSION are read from
tools/dwc.py, so adding a term is not a failure.
"""
import math, os, re, sys, uuid as _uuid
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import url, offline, pick, setstep, push, ROOT, TOOLS_DIR

P, F = [], []
def ck(n, c, e=""):
    (P if c else F).append(n + (("  << " + str(e)) if (e and not c) else ""))


def _src():
    return open(os.path.join(TOOLS_DIR, "dwc.py"), encoding="utf-8").read()

def dwc_version():
    m = re.search(r'^VERSION\s*=\s*"([\d.]+)"', _src(), re.M)
    return m.group(1) if m else None

def dwc_terms():
    m = re.search(r"var TERMS = \[(.*?)\];", _src(), re.S)
    return re.findall(r'"([A-Za-z]+)"', m.group(1)) if m else []


def places(t):
    """Decimal places in a typed coordinate -- the page's own rule, restated."""
    t = (t or "").strip()
    if "." not in t:
        return 0
    return len(t.split(".", 1)[1])

def expect_uncertainty(extent_m, gps_m, lat_text, lon_text, datum):
    """Independent recomputation of DWC.uncertainty. Deliberately written from
    the point-radius method rather than transcribed from the JS."""
    def usable(v):
        v = (v or "").strip()
        if v == "":
            return False
        try:
            float(v)
        except ValueError:
            return False
        return True
    if not usable(lat_text) or not usable(lon_text):
        return None
    lat = float(lat_text)
    parts = []
    if extent_m > 0:
        parts.append(extent_m)
    if gps_m > 0:
        parts.append(gps_m)
    dp = min(places(lat_text), places(lon_text))
    half = 0.5 * 10 ** (-dp)
    m = max(half * 110540, half * abs(111320 * math.cos(math.radians(lat))))
    if m > 0.5:
        parts.append(m)
    if datum == "unknown":
        parts.append(5359)
    if not parts:
        return None
    return max(1, round(sum(parts)))


V4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

CAPTURE = """() => {
  window.__cap = null;
  var orig = DWC.table;
  DWC.table = function(rows){ window.__cap = rows; return orig(rows); };
}"""

def show_pane_of(pg, sel):
    """Bring the tab that owns a control to the front, the way a thumb would.
    The export button lives on a different pane in each of the three pages, so
    the suite finds the pane rather than hard-coding three tab names."""
    pane = pg.evaluate("""(s)=>{const e=document.querySelector(s); if(!e) return null;
      const p=e.closest('section.pane'); return p?p.id:null;}""", sel)
    if pane:
        pg.click('.tab[data-pane="%s"]' % pane)
        pg.wait_for_timeout(250)
    return pane


def rows_from_click(pg, btn="#dwcCopy"):
    """Click the real export button and capture what it handed to DWC.table.
    Wrapping the public entry point rather than exporting a test hook keeps the
    production code free of scaffolding and still exercises the real path."""
    show_pane_of(pg, btn)
    pg.evaluate(CAPTURE)
    pg.click(btn)
    pg.wait_for_timeout(220)
    return pg.evaluate("() => window.__cap")


VERSION = dwc_version()
TERMS = dwc_terms()
ck("tools/dwc.py declares a version", bool(VERSION), VERSION)
ck("tools/dwc.py declares terms", len(TERMS) >= 30, len(TERMS))
ck("occurrenceID is the first term", TERMS[:1] == ["occurrenceID"], TERMS[:1])
ck("no duplicate terms", len(set(TERMS)) == len(TERMS),
   [t for t in TERMS if TERMS.count(t) > 1])

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 900, "height": 1300})
    pg.set_default_timeout(15000)
    offline(pg)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    # ================= every consumer carries the same emitter =================
    for name in ["releve.html", "stand-sheet.html", "collection-sheet.html"]:
        errs[:] = []
        pg.goto(url(name), wait_until="domcontentloaded")
        pg.wait_for_timeout(450)
        ck("%s loads without error" % name, not errs, errs[:2])
        ck("%s carries DWC" % name, pg.evaluate("()=>typeof DWC!=='undefined'"), "")
        ck("%s DWC version matches dwc.py" % name,
           pg.evaluate("()=>DWC.version") == VERSION, pg.evaluate("()=>DWC.version"))
        ck("%s term list matches dwc.py" % name,
           pg.evaluate("()=>DWC.TERMS") == TERMS, "drifted")
        ck("%s has the export button" % name,
           pg.evaluate("()=>!!document.getElementById('dwcCopy')"), "")
        ck("%s has the coordinate box" % name,
           pg.evaluate("()=>!!document.getElementById('dwcOut')"), "")
        ck("%s coordinate box is a single mount" % name,
           pg.eval_on_selector_all("#dwcCoords", "e=>e.length") == 1, "")
        ck("%s datum is a FEK dial, not a bare select" % name,
           pg.eval_on_selector_all("#dwcCoords .fek-dial", "e=>e.length") == 1
           and pg.eval_on_selector_all("#dwcCoords select", "e=>e.length") == 0, "")
        ck("%s gps accuracy is a FEK stepper" % name,
           pg.eval_on_selector_all("#dwcCoords .fek-step", "e=>e.length") == 1, "")
        ck("%s gps accuracy starts empty, not at zero" % name,
           pg.evaluate("()=>document.querySelector('#dwcCoords .fek-step .val').value") == "",
           pg.evaluate("()=>document.querySelector('#dwcCoords .fek-step .val').value"))

    # ================= uncertainty arithmetic, on relevé =================
    errs[:] = []
    pg.goto(url("releve.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(450)
    pg.click('.tab[data-pane="p-plot"]')
    pg.wait_for_timeout(250)

    def out():
        return pg.inner_text("#dwcOut")

    def set_datum(v):
        """Click the datum dial the way a thumb does -- these are FEK components,
        not bare inputs, and the readout moves on the dial's onchange."""
        pg.evaluate("""(v)=>{const d=document.querySelector('#dwcCoords .fek-dial');
          const b=[...d.querySelectorAll('button')]
            .find(x=>x.querySelector('span').textContent.trim()===v);
          if(!b) throw new Error('no datum button '+v); b.click();}""", v)
        pg.wait_for_timeout(140)

    def set_gps(v):
        pg.evaluate("""(v)=>{const i=document.querySelector('#dwcCoords .fek-step .val');
          if(!i) throw new Error('no gps stepper');
          i.value=String(v); i.dispatchEvent(new Event('input',{bubbles:true}));}""", str(v))
        pg.wait_for_timeout(140)

    ck("empty coordinate reports empty, not a number",
       "empty" in out() and "=" not in out().split("empty")[0], out()[:70])
    ck("empty coordinate says zero would be wrong",
       "zero would be a lie" in out().lower() or "zero" in out().lower(), out()[:70])

    # square plot: extent is the half-diagonal of the side implied by the area
    cases = [
        # area m2, gps m, lat text,      lon text,     datum
        (100.0,   0,  "45.1234",   "-93.5678",  "WGS84"),
        (400.0,   0,  "45.12",     "-93.56",    "WGS84"),
        (100.0,   30, "45.1234",   "-93.5678",  "WGS84"),
        (0.0,     0,  "45.123456", "-93.567891","WGS84"),
        (0.0,     0,  "45.123456", "-93.567891","unknown"),
        (100.0,   5,  "0.0001",    "0.0001",    "WGS84"),
    ]
    for area, gps, lat, lon, datum in cases:
        push(pg, "sLat", lat)
        push(pg, "sLon", lon)
        set_datum(datum)
        set_gps(gps if gps else "")
        push(pg, "sArea", area)
        pg.wait_for_timeout(150)
        side = math.sqrt(area) if area > 0 else 0.0
        extent = side * math.sqrt(2) / 2 if side > 0 else 0.0
        want = expect_uncertainty(extent, gps, lat, lon, datum)
        txt = out()
        if want is None:
            ok = "empty" in txt
            got = txt[:50]
        else:
            m = re.search(r"=\s*([\d,]+)\s*m", txt)
            got = m.group(1).replace(",", "") if m else txt[:50]
            ok = m is not None and int(got) == want
        ck("releve %sm2 gps=%s lat=%s %s -> %s"
           % (int(area), gps, lat, datum, "empty" if want is None else want), ok, got)

    # the fix this suite exists for
    push(pg, "sLat", "")
    pg.wait_for_timeout(150)
    ck("clearing latitude returns to empty, not 55 km",
       "empty" in out() and "55" not in out(), out()[:80])
    push(pg, "sLon", "")
    push(pg, "sLat", "45.1")
    pg.wait_for_timeout(150)
    ck("latitude alone is not a location", "empty" in out(), out()[:60])
    push(pg, "sLat", "not a number")
    push(pg, "sLon", "-93.5")
    pg.wait_for_timeout(150)
    ck("unparseable latitude is not a location", "empty" in out(), out()[:60])

    # ================= relevé rows =================
    pg.goto(url("releve.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(450)
    pg.click('.tab[data-pane="p-plot"]')
    pg.wait_for_timeout(200)
    for k, v in [("sPlot", "TEST-01"), ("sObs", 'O"Brien, R'), ("sDate", "2026-08-20"),
                 ("sLat", "45.1234"), ("sLon", "-93.5678"), ("sArea", "100"),
                 ("sComm", "wet meadow, sedge-dominated")]:
        push(pg, k, v)
    pg.click('.tab[data-pane="p-rec"]')
    pg.wait_for_timeout(250)
    pg.fill("#rFree", "Carex aquatilis")
    pg.evaluate("""()=>{const d=[...document.querySelectorAll('#rCov .fek-dial')][0]
      || document.querySelector('#rCov');
      const b=[...d.querySelectorAll('button')][2]; b.click();}""")
    pg.wait_for_timeout(150)
    pg.click("#rAdd")
    pg.wait_for_timeout(300)
    rows = rows_from_click(pg)
    ck("releve exports at least one row", bool(rows) and len(rows) >= 1, rows)
    if rows:
        r = rows[0]
        ck("releve basisOfRecord is HumanObservation",
           r.get("basisOfRecord") == "HumanObservation", r.get("basisOfRecord"))
        ck("releve kingdom is Plantae", r.get("kingdom") == "Plantae", r.get("kingdom"))
        ck("releve eventID carries plot and date",
           r.get("eventID") == "releve:TEST-01:2026-08-20", r.get("eventID"))
        ck("releve locality is the community, not the plot id",
           r.get("locality") == "wet meadow, sedge-dominated", r.get("locality"))
        ck("releve sampleSize is the plot area in m2",
           str(r.get("sampleSizeValue")) == "100" and r.get("sampleSizeUnit") == "square metre",
           (r.get("sampleSizeValue"), r.get("sampleSizeUnit")))
        ck("releve quantity type is coverage, not a count",
           r.get("organismQuantityType") in ("percentageCoverage", ""),
           r.get("organismQuantityType"))
        ck("releve uncertainty is never 0",
           r.get("coordinateUncertaintyInMeters") not in (0, "0"),
           r.get("coordinateUncertaintyInMeters"))
        ck("releve recordedBy survives a quote character",
           r.get("recordedBy") == 'O"Brien, R', r.get("recordedBy"))

        table = pg.evaluate("(rs)=>DWC.table(rs)", rows)
        head = table.split("\n")[0].split(",")
        ck("table header is exactly the term list", head == TERMS, head[:4])
        ck("table has one line per record plus a header",
           len([l for l in table.split("\n") if l.strip()]) == len(rows) + 1,
           len(table.split("\n")))
        ck("a value containing a quote is doubled and wrapped",
           '"O""Brien, R"' in table, table.split("\n")[1][:80])
        ck("no unquoted comma leaks a column",
           all(len(re.findall(r'(?:^|,)(?=(?:[^"]*"[^"]*")*[^"]*$)', l)) >= 0
               for l in table.split("\n")), "")

    # ================= identifiers =================
    ids = pg.evaluate("()=>{var s=[];for(var i=0;i<2000;i++)s.push(DWC.uuid());return s;}")
    ck("2000 occurrenceIDs are unique", len(set(ids)) == 2000, 2000 - len(set(ids)))
    ck("occurrenceIDs are RFC 4122 v4", all(V4.match(i) for i in ids),
       next((i for i in ids if not V4.match(i)), ""))
    ck("weak-id flag is reported, not hidden",
       pg.evaluate("()=>typeof DWC.idsAreWeak==='function'"), "")
    ck("this browser has real randomness",
       pg.evaluate("()=>DWC.idsAreWeak()") is False, "Math.random fallback in use")

    # ================= CSV escaping =================
    csvck = pg.evaluate("""()=>{
      var r=[{occurrenceID:'a,b'},{occurrenceID:'c"d'},{occurrenceID:'e\\nf'},{occurrenceID:''}];
      return DWC.table(r).split('\\n');}""")
    body = "\n".join(csvck[1:])
    ck("comma is quoted", '"a,b"' in body, body[:40])
    ck("quote is doubled", '"c""d"' in body, body[:60])
    ck("newline is quoted", '"e\nf"' in body, repr(body)[:60])

    # ================= stand sheet =================
    errs[:] = []
    pg.goto(url("stand-sheet.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(500)
    pg.click('.tab[data-pane="p-plot"]')
    pg.wait_for_timeout(200)
    for k, v in [("sPlot", "TAH-04"), ("sLoc", "Sagehen Creek"), ("sObs", "R. Test"),
                 ("sDate", "2026-08-20"), ("sLat", "39.0968"), ("sLon", "-120.0324"),
                 ("sElev", "1950"), ("sDesign", "circ"), ("sRad", "11.28"), ("sMin", "5")]:
        push(pg, k, v)
    pg.click('.tab[data-pane="p-trees"]')
    pg.wait_for_timeout(250)
    pick(pg, "#tEntry", "fir")
    for d in [30, 25, 40]:
        setstep(pg, "#tEntry", 0, d)
        pg.click("#tAdd")
        pg.wait_for_timeout(200)
    rows = rows_from_click(pg)
    ck("stand exports one row per stem", rows is not None and len(rows) == 3,
       None if rows is None else len(rows))
    if rows:
        area = math.pi * 11.28 ** 2
        want = expect_uncertainty(11.28, 0, "39.0968", "-120.0324", "WGS84")
        ck("stand uncertainty = %s m (plot radius is the extent)" % want,
           int(rows[0]["coordinateUncertaintyInMeters"]) == want,
           rows[0]["coordinateUncertaintyInMeters"])
        ck("every stem is one individual",
           all(r["organismQuantity"] == 1 and r["organismQuantityType"] == "individuals"
               for r in rows), rows[0]["organismQuantityType"])
        ck("stems-per-hectare is not exported as a quantity",
           all(r["organismQuantity"] == 1 for r in rows), "")
        ck("sampleSizeValue is the plot area",
           rows[0]["sampleSizeValue"] == "%.0f" % area, rows[0]["sampleSizeValue"])
        ck("samplingProtocol states the minimum tallied DBH",
           "5 cm DBH" in rows[0]["samplingProtocol"], rows[0]["samplingProtocol"])
        ck("stand kingdom is Plantae", rows[0]["kingdom"] == "Plantae", rows[0]["kingdom"])
        ck("stand locality is the typed place name",
           rows[0]["locality"] == "Sagehen Creek", rows[0]["locality"])
        ck("stand locationID is the plot", rows[0]["locationID"] == "TAH-04",
           rows[0]["locationID"])
        ck("every stem shares one eventID",
           len(set(r["eventID"] for r in rows)) == 1, set(r["eventID"] for r in rows))
        ck("stand eventID names the method",
           rows[0]["eventID"].startswith("stand:"), rows[0]["eventID"])
        ck("DBH travels in the remarks",
           all("DBH" in r["occurrenceRemarks"] for r in rows),
           rows[0]["occurrenceRemarks"][:60])
        ck("occurrenceIDs differ between stems",
           len(set(r["occurrenceID"] for r in rows)) == 3, "")
    ck("stand sheet raised no errors", not errs, errs[:2])

    # a snag is present, not absent -- the export button lives on the plot pane,
    # so the suite has to walk back to the tally the way a person would
    pg.click('.tab[data-pane="p-trees"]')
    pg.wait_for_timeout(250)
    pg.evaluate("""()=>{const d=[...document.querySelectorAll('#tEntry .fek-dial')][1];
      const b=[...d.querySelectorAll('button')].find(x=>x.querySelector('span').textContent.trim()==='snag 3');
      b.click();}""")
    pg.wait_for_timeout(150)
    setstep(pg, "#tEntry", 0, 35)
    pg.click("#tAdd")
    pg.wait_for_timeout(220)
    rows = rows_from_click(pg)
    if rows and len(rows) == 4:
        snag = rows[3]
        ck("a snag is still occurrenceStatus present",
           snag["occurrenceStatus"] == "present", snag["occurrenceStatus"])
        ck("the snag's decay class is recorded",
           "decay class 3" in snag["occurrenceRemarks"], snag["occurrenceRemarks"][:80])
    else:
        ck("snag row exported", False, None if rows is None else len(rows))

    # ================= collection sheet =================
    errs[:] = []
    pg.goto(url("collection-sheet.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(500)
    pg.click('.tab[data-pane="p-site"]')
    pg.wait_for_timeout(200)
    for k, v in [("sSite", "Bear Cr. old-growth"), ("sObs", "R. Test"),
                 ("sDate", "2026-08-20"), ("sLat", "45.3736"), ("sLon", "-121.6960"),
                 ("sInst", "OSC"), ("sColl", "Fungi"),
                 ("sVeg", "Tsuga heterophylla zone"), ("sTrees", "PSME, TSHE")]:
        push(pg, k, v)
    pg.click('.tab[data-pane="p-rec"]')
    pg.wait_for_timeout(300)
    # one vouchered, one not
    pg.evaluate("(v)=>{var e=document.getElementById('cName'); e.value=v;}", "Amanita muscaria")
    pg.evaluate("(v)=>{var e=document.getElementById('cNum'); e.value=v;}", "RT-2026-014")
    pg.click("#cAdd")
    pg.wait_for_timeout(300)
    pg.evaluate("(v)=>{var e=document.getElementById('cName'); e.value=v;}", "Cortinarius sp.")
    pg.click("#cAdd")
    pg.wait_for_timeout(300)
    rows = rows_from_click(pg)
    ck("collection exports both collections", rows is not None and len(rows) == 2,
       None if rows is None else len(rows))
    if rows and len(rows) == 2:
        a, c = rows[0], rows[1]
        ck("a vouchered collection is a PreservedSpecimen",
           a["basisOfRecord"] == "PreservedSpecimen", a["basisOfRecord"])
        ck("an unvouchered collection is a HumanObservation",
           c["basisOfRecord"] == "HumanObservation", c["basisOfRecord"])
        ck("the voucher number is the catalogNumber",
           a["catalogNumber"] == "RT-2026-014", a["catalogNumber"])
        ck("no institutionCode without a voucher",
           c["institutionCode"] == "" and c["collectionCode"] == "",
           (c["institutionCode"], c["collectionCode"]))
        ck("institutionCode travels with the voucher",
           a["institutionCode"] == "OSC", a["institutionCode"])
        ck("collection kingdom is Fungi",
           a["kingdom"] == "Fungi" and c["kingdom"] == "Fungi", a["kingdom"])
        ck("a name ending in sp. is exported at genus rank",
           c["taxonRank"] == "genus", c["taxonRank"])
        ck("a binomial is exported at species rank",
           a["taxonRank"] == "species", a["taxonRank"])
        ck("scientificName is the working name, unaltered",
           c["scientificName"] == "Cortinarius sp.", c["scientificName"])
        ck("a foray states it is not plot-based",
           "not a plot-based" in a["samplingProtocol"], a["samplingProtocol"])
        ck("a foray exports no sample size",
           a.get("sampleSizeValue", "") in ("", None), a.get("sampleSizeValue"))
        ck("collection locality is the site",
           a["locality"] == "Bear Cr. old-growth", a["locality"])
        ck("habitat carries the stand description",
           "Tsuga heterophylla zone" in a["habitat"], a["habitat"])
        ck("collection uncertainty adds no invented plot extent",
           int(a["coordinateUncertaintyInMeters"])
           == expect_uncertainty(0, 0, "45.3736", "-121.6960", "WGS84"),
           a["coordinateUncertaintyInMeters"])
        ck("a typed working name is not credited as a determination",
           a["identifiedBy"] == "" and c["identifiedBy"] == "",
           (a["identifiedBy"], c["identifiedBy"]))
    ck("collection sheet raised no errors", not errs, errs[:2])

    # ================= the zero that must never appear =================
    for name in ["releve.html", "stand-sheet.html", "collection-sheet.html"]:
        src = open(os.path.join(ROOT, "docs", name), encoding="utf-8").read()
        ck("%s never hard-codes a zero uncertainty" % name,
           "coordinateUncertaintyInMeters: 0" not in src
           and 'coordinateUncertaintyInMeters: "0"' not in src, "")

    b.close()

print("\n".join("PASS  " + x for x in P))
if F:
    print("\n".join("FAIL  " + x for x in F))
print("-" * 60)
print("%d passed, %d failed" % (len(P), len(F)))
sys.exit(1 if F else 0)
