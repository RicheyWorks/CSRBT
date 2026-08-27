# -*- coding: utf-8 -*-
"""Deployment Log: the arithmetic, and the four refusals.

The arithmetic here is multiplication, which is easy to get right and easy to
get wrong in a way nobody notices -- so every figure the page prints is
recomputed in Python from the definition rather than read back from the page.

The refusals are the reason the page exists, and they are checked as behaviour,
not as the presence of a paragraph:

  * no dB SPL from an uncalibrated recorder
  * no NDVI from a filter-converted or stock RGB camera
  * no cross-flight comparison without radiometric correction
  * no invented radiation-shield correction figure
"""
import io, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import url, offline, ROOT, TOOLS_DIR
from playwright.sync_api import sync_playwright

P, F = [], []
def ck(n, c, e=""):
    (P if c else F).append(n + (("  << " + str(e)) if (e and not c) else ""))

PAGE = "deployment-log.html"
SRC = io.open(os.path.join(ROOT, "docs", PAGE), encoding="utf-8").read()

# ---- independent implementations -------------------------------------------
C_AIR = 343

def bytes_per_sec(sr, ch):
    return sr * 2 * ch                      # 16-bit PCM

def card_gb(sr, ch, on, every, days):
    frac = min(1.0, on / every)
    return days * 86400 * frac * bytes_per_sec(sr, ch) / 1e9

def gsd_cm_px(sensor_w_mm, alt_m, focal_mm, img_w_px):
    return (sensor_w_mm * alt_m * 100) / (focal_mm * img_w_px)

def readings(interval_s, days):
    return int(days * 86400 // interval_s)

def fills_after_days(memory, interval_s):
    return memory * interval_s / 86400.0


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 950, "height": 1400})
    pg.set_default_timeout(20000)
    offline(pg)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console: " + m.text)
          if m.type == "error" and "ERR_" not in m.text else None)
    pg.goto(url(PAGE), wait_until="domcontentloaded")
    pg.wait_for_timeout(800)

    ck("page loads clean", not errs, errs[:3])
    ck("five tabs", pg.eval_on_selector_all(".tab", "e=>e.length") == 5, "")
    ck("entry layer is FEK, no bare selects",
       pg.eval_on_selector_all("select", "e=>e.length") == 0,
       pg.eval_on_selector_all("select", "e=>e.map(x=>x.id)"))
    ck("every write-through control is registered with FEK",
       len(pg.evaluate("()=>FEK.fields()")) >= 15,
       len(pg.evaluate("()=>FEK.fields()")))
    ck("autosave is wired", pg.eval_on_selector_all("#keepBox.keep", "e=>e.length") == 1, "")

    def dial(label, root=None):
        pg.evaluate("""([r,l])=>{
          const ds=[...document.querySelectorAll((r||'')+' .fek-dial')];
          for(const d of ds){ const bt=[...d.querySelectorAll('button')]
            .find(x=>x.querySelector('span').textContent.trim()===l);
            if(bt){ bt.click(); return; } }
          throw new Error('no dial option '+l);}""", [root or "", label])
        pg.wait_for_timeout(400)

    def stat(box, label):
        return pg.evaluate("""([b,l])=>{const k=[...document.querySelectorAll('#'+b+' .k')]
          .find(x=>x.querySelector('.l').textContent.trim()===l);
          return k ? k.querySelector('.v').textContent.trim() : null;}""", [box, label])

    def numstat(box, label):
        v = stat(box, label)
        if v is None:
            return None
        m = re.search(r"-?[\d,.]+", v)
        return float(m.group(0).replace(",", "")) if m else None

    def setstep(label, value):
        pg.evaluate("""([l,v])=>{
          const pane=document.querySelector('section.pane.on')||document;
          const rows=[...pane.querySelectorAll('.fek-row')];
          for(const r of rows){
            const lab=r.querySelector('.fek-lab');
            if(!lab || lab.textContent.replace(/\\s+/g,' ').trim().indexOf(l)!==0) continue;
            const i=r.querySelector('.fek-step .val') || r.querySelector('input[type=range]');
            if(!i) continue;
            i.value=String(v); i.dispatchEvent(new Event('input',{bubbles:true}));
            return; }
          throw new Error('no stepper '+l);}""", [label, value])
        pg.wait_for_timeout(300)

    # ================= bandwidth: the sampling theorem =================
    ck("48 kHz reports 24 kHz of usable band",
       numstat("nyqBox", "records up to") == 24, stat("nyqBox", "records up to"))
    dial("bats", "#acEntry")
    v = pg.inner_text("#nyqBox")
    ck("48 kHz is refused for bats", "cannot survey bats" in v, v[:80])
    ck("the refusal names aliasing, not just loss",
       "aliases down" in v, v[:200])
    ck("a refused setting is styled as a stop",
       pg.eval_on_selector_all("#nyqBox .verdict.act", "e=>e.length") == 1, "")
    dial("192 kHz", "#acEntry")
    v = pg.inner_text("#nyqBox")
    # The nuance that a single threshold got wrong: 192 kHz is what most bat
    # work runs at, and reporting it as a failure would be the page being wrong.
    ck("192 kHz for bats is partial coverage, not a failure",
       "Enough for most of it" in v, v[:90])
    ck("the partial verdict says which species the gap removes",
       "Rhinolophus" in v, v[:220])
    ck("the partial verdict warns the absences will look like ecology",
       "look like ecology" in v, v[:300])
    dial("384 kHz", "#acEntry")
    ck("384 kHz gives bats full coverage",
       "Full coverage" in pg.inner_text("#nyqBox"), pg.inner_text("#nyqBox")[:80])

    # ================= cards and duty cycle =================
    dial("48 kHz", "#acEntry")
    dial("birds", "#acEntry")
    for on, every, days, card in [(60, 600, 14, 32), (300, 3600, 30, 64), (60, 60, 7, 128)]:
        setstep("record for", on)
        setstep("once every", every)
        setstep("deployment", days)
        setstep("SD card", card)
        want_gb = card_gb(48000, 1, on, every, days)
        got = numstat("dutyStat", "card needed")
        ck("card for %ds in %ds over %dd = %.2f GB" % (on, every, days, want_gb),
           got is not None and abs(got - want_gb) < 0.02, got)
        want_duty = 100 * min(1.0, on / every)
        ck("duty cycle %ds/%ds = %.1f%%" % (on, every, want_duty),
           abs((numstat("dutyStat", "duty cycle") or -1) - want_duty) < 0.1,
           stat("dutyStat", "duty cycle"))

    # a card that cannot hold the deployment must say so
    # ---- the duty cycle at the smallest values a user can set ----
    # Every reading here divides by `every`, and the panel had never been read
    # at the bottom of its own ranges. Typing 0 does NOT reach zero: aOn and
    # aEvery are FEK steppers with min:1 and no nullable flag, so both clamp --
    # measured, which is also why the sweep's `every <= 0` -> `every < 0` mutant
    # is recorded as equivalent rather than killed here. What this does check is
    # that the floor of the reachable range produces numbers and not NaN.
    for lbl in ("record for", "once every", "deployment", "SD card"):
        setstep(lbl, 0)
    pg.wait_for_timeout(250)
    for el in ("#dutyStat", "#dutyLegend", "#dutyBox"):
        txt = pg.inner_text(el)
        ck("the duty panel is NaN-free at the floor of its ranges (%s)" % el,
           "NaN" not in txt, txt[:120])
    ck("and it shows no Infinity either", "Infinity" not in pg.inner_text("#dutyStat"),
       pg.inner_text("#dutyStat")[:120])

    setstep("record for", 600)
    setstep("once every", 600)
    setstep("deployment", 30)
    setstep("SD card", 8)
    v = pg.inner_text("#dutyBox")
    ck("an undersized card is a stop, not a note",
       "fills before you get back" in v
       and pg.eval_on_selector_all("#dutyBox .verdict.act", "e=>e.length") == 1, v[:90])
    ck("it says which day it stops on", re.search(r"after about \*?\*?\d+ days", v) is not None, v[:140])
    ck("battery life is refused, not guessed",
       "a number invented for it would be worse than none" in v, v[-200:])

    # ================= clock drift =================
    for days in [1, 7, 14, 30]:
        setstep("deployment", days)
        ck("%d d of drift = %d s" % (days, days),
           numstat("driftStat", "clock may be out by") == days,
           stat("driftStat", "clock may be out by"))
        want_m = days * C_AIR
        got = stat("driftStat", "as a distance")
        want_txt = ("%.1f km" % (want_m / 1000)) if want_m >= 1000 else ("%d m" % round(want_m))
        ck("%d s of drift = %s of position error" % (days, want_txt),
           got is not None and got.replace(" ", " ").startswith(want_txt.split()[0]),
           got)
    ck("GPS sync figure is stated", stat("driftStat", "with GPS sync") is not None, "")
    ck("an unsynchronised array is told it cannot localise",
       "cannot localise" in pg.inner_text("#driftBox"), pg.inner_text("#driftBox")[:120])

    # ================= refusal 1: no decibels =================
    v = pg.inner_text("#splBox")
    ck("the page refuses to produce dB SPL",
       "will not convert your recordings to decibels" in v, v[:90])
    ck("the refusal cites the whole-chain requirement",
       "microphone, case and recording settings" in v, v[:250])
    ck("it says what IS measurable without a calibrator",
       "one unit at one gain" in v, v[:400])
    ck("no dB SPL figure is printed anywhere on the page",
       not re.search(r"\d+(\.\d+)?\s*dB\s*SPL", pg.inner_text("body")),
       re.findall(r".{0,30}dB\s*SPL.{0,20}", pg.inner_text("body"))[:2])

    # ================= flight arithmetic =================
    pg.click('.tab[data-pane="p-fl"]')
    pg.wait_for_timeout(350)
    CAMS = [("MicaSense RedEdge", 4.8, 5.4, 1280), ("P4 Multispectral", 4.87, 5.74, 1600),
            ("Parrot Sequoia", 4.8, 3.98, 1280)]
    for name, sw, fl, pw in CAMS:
        dial(name, "#camEntry")
        for alt in [60, 120]:
            setstep("altitude AGL", alt)
            want = gsd_cm_px(sw, alt, fl, pw)
            got = numstat("gsdStat", "GSD")
            ck("%s at %d m = %.2f cm/px" % (name, alt, want),
               got is not None and abs(got - want) < 0.011, got)
    ck("the page shows the GSD arithmetic, not just the answer",
       "sensor width × altitude ÷" in pg.inner_text("#gsdBox"), pg.inner_text("#gsdBox")[:90])

    # overlap: Pix4D's own recommendation, cited
    dial("MicaSense RedEdge", "#camEntry")
    setstep("altitude AGL", 120)
    setstep("frontal overlap", 70)
    setstep("side overlap", 60)
    v = pg.inner_text("#gsdBox")
    ck("under-overlap for vegetation is flagged",
       "Below Pix4D" in v, v[:80])
    ck("the flag carries all three Pix4D figures",
       "75/60" in v and "80/80" in v and "85/85" in v, v[:260])
    ck("it says why a canopy needs more, not just that it does",
       "repeating texture" in v, v[:400])
    setstep("frontal overlap", 85)
    setstep("side overlap", 85)
    ck("85/85 meets the recommendation",
       "meets Pix4D" in pg.inner_text("#gsdBox"), pg.inner_text("#gsdBox")[:90])

    # ================= refusal 2: NDVI from the wrong sensor =================
    dial("converted RGB", "#camEntry")
    v = pg.inner_text("#radBox")
    ck("a converted camera is refused NDVI",
       "does not give you NDVI" in v, v[:80])
    ck("the refusal explains band contamination",
       "red channel is contaminated" in v, v[:400])
    ck("it names what the sensor CAN do",
       "relative" in v, v[:500])
    dial("stock RGB", "#camEntry")
    v = pg.inner_text("#radBox")
    ck("a stock RGB camera is refused NDVI outright",
       "cannot produce NDVI at all" in v, v[:80])
    ck("VARI is offered as the honest alternative", "VARI" in v, v[:300])
    dial("MicaSense RedEdge", "#camEntry")
    ck("a real multispectral sensor gets no NDVI refusal",
       "cannot produce NDVI" not in pg.inner_text("#radBox"), pg.inner_text("#radBox")[:80])

    # ================= refusal 3: no comparison without correction =========
    for opt, must in [("neither", "cannot be compared to another one"),
                      ("panel only", "broken cloud mid-flight is invisible"),
                      ("DLS only", "not comparable to another flight"),
                      ("panel + DLS", "makes two flights comparable")]:
        dial(opt, "#radEntry")
        v = pg.inner_text("#radBox")
        ck("radiometric '%s' states its consequence" % opt, must in v, v[:200])
    dial("neither", "#radEntry")
    ck("no correction is styled as a stop",
       pg.eval_on_selector_all("#radBox .verdict.act", "e=>e.length") == 1, "")
    ck("the Pix4D wording is quoted, not paraphrased into a claim",
       "is required to be able to compare" in pg.inner_text("#radBox"), "")

    # broken cloud
    pg.evaluate("""()=>{var e=document.getElementById('fCloud'); e.value='4';
      e.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.wait_for_timeout(300)
    v = pg.inner_text("#skyBox")
    ck("broken cloud is flagged as the worst case", "hardest sky to fly in" in v, v[:80])
    ck("it says overcast can be better than broken", "better" in v, v[:280])

    # ================= refusal 4: no invented shield figure =================
    pg.click('.tab[data-pane="p-lg"]')
    pg.wait_for_timeout(350)
    for iv, days, mem in [(600, 90, 84650), (60, 30, 20000), (3600, 365, 84650)]:
        setstep("logging interval", iv)
        setstep("deployment", days)
        setstep("memory", mem)
        ck("%ds interval over %dd = %d readings" % (iv, days, readings(iv, days)),
           numstat("logStat", "readings") == readings(iv, days), stat("logStat", "readings"))
        ck("%d readings at %ds fills after %.0f d" % (mem, iv, fills_after_days(mem, iv)),
           abs((numstat("logStat", "fills after") or -1) - round(fills_after_days(mem, iv))) < 1.01,
           stat("logStat", "fills after"))
    setstep("logging interval", 60)
    setstep("deployment", 90)
    setstep("memory", 20000)
    v = pg.inner_text("#logBox")
    ck("a logger that fills early says so", "Memory fills after" in v, v[:80])
    ck("and gives the interval that would fit", re.search(r"to \*?\*?\d+ minutes", v) is not None, v[:200])
    ck("wrap-versus-stop is raised", "wrapped logger" in v, v[:300])

    ck("an unrecorded shield is itself flagged",
       "Record what the logger was inside" in pg.inner_text("#shBox"), pg.inner_text("#shBox")[:80])
    for opt, must in [("gill-type multi-plate", "the gill-type gave the best protection"),
                      ("improvised", "The page will not invent a correction"),
                      ("natural shade only", "measure your own offset"),
                      ("none", "reading its own casing")]:
        dial(opt, "#shEntry")
        v = pg.inner_text("#shBox")
        ck("shield '%s' states its consequence" % opt, must in v, v[:200])
    dial("gill-type multi-plate", "#shEntry")
    ck("the paywalled figure is named as unavailable, not skipped",
       "behind a paywall" in pg.inner_text("#shBox"), pg.inner_text("#shBox")[:200])
    body = pg.inner_text("body")
    ck("no shield error figure in degrees is printed anywhere",
       not re.search(r"shield.{0,60}\d+(\.\d+)?\s*°C", body, re.I | re.S),
       re.findall(r".{0,40}°C.{0,20}", body)[:3])

    # ================= the log itself =================
    pg.click('.tab[data-pane="p-ac"]')
    pg.wait_for_timeout(300)
    pg.evaluate("""()=>{var e=document.getElementById('aUnit'); e.value='AM-014';
      e.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.click("#addAc")
    pg.wait_for_timeout(400)
    pg.click('.tab[data-pane="p-log"]')
    pg.wait_for_timeout(300)
    ck("a logged recorder appears in the table",
       pg.eval_on_selector_all("#logTable table tr", "e=>e.length") == 2,
       pg.eval_on_selector_all("#logTable table tr", "e=>e.length"))
    row = pg.inner_text("#logTable")
    ck("the log row carries the sample rate", "kHz" in row, row[:120])
    ck("the log row carries the SPL caveat", "no SPL calibration" in row, row[:200])
    ck("the log row carries the drift figure", "clock may drift" in row, row[:200])

    pg.click('.tab[data-pane="p-fl"]')
    pg.wait_for_timeout(300)
    pg.evaluate("""()=>{var e=document.getElementById('fId'); e.value='SGH-01';
      e.dispatchEvent(new Event('input',{bubbles:true}));}""")
    dial("neither", "#radEntry")
    dial("converted RGB", "#camEntry")
    pg.click("#addFl")
    pg.wait_for_timeout(400)
    pg.click('.tab[data-pane="p-log"]')
    pg.wait_for_timeout(300)
    row = pg.inner_text("#logTable")
    ck("an uncorrected flight is logged as not comparable",
       "NOT comparable between flights" in row, row[-300:])
    ck("a converted camera is logged as unable to produce NDVI",
       "cannot produce NDVI" in row, row[-300:])
    ck("the field sheet carries both deployments",
       pg.inner_text("#ecoOut").count("[") >= 2, pg.inner_text("#ecoOut")[:80])

    # escaping: an ID typed as markup
    pg.click('.tab[data-pane="p-ac"]')
    pg.wait_for_timeout(300)
    pg.evaluate("""()=>{var e=document.getElementById('aUnit');
      e.value='<x-probe>p</x-probe>'; e.dispatchEvent(new Event('input',{bubbles:true}));}""")
    pg.click("#addAc")
    pg.wait_for_timeout(400)
    ck("a unit ID typed as markup does not become markup",
       pg.eval_on_selector_all("x-probe", "e=>e.length") == 0,
       pg.eval_on_selector_all("x-probe", "e=>e.length"))

    ck("no errors through the whole run", not errs, errs[:3])

    # ================= the method page keeps its promises =================
    met = re.sub(r"\s+", " ", pg.inner_text("#p-met"))
    for phrase, why in [
        ("not calibrated", "gain settings are named, not calibrated"),
        ("Relative amplitude", "what is still measurable"),
        ("VARI", "the honest index for an RGB sensor"),
        ("is required to be able to compare", "the Pix4D wording, quoted"),
        ("behind a paywall this page cannot read", "the figure that is not shipped"),
        ("343", "the speed of sound, since the drift claim rests on it"),
        ("da Cunha", "the shield study is named even though its figures are not used"),
    ]:
        ck("method page: %s" % why, phrase in met, phrase)

    b.close()

# ---- static: the refusals must not be quietly deleted ----------------------
for phrase, why in [
    ("openacousticdevices.info", "the recorder source is linked"),
    ("pix4d.com", "the calibration source is linked"),
    ("dronedeploy.com", "the NDVI source is linked"),
    ("will not convert your recordings to decibels", "the SPL refusal"),
    ("produce NDVI at all", "the stock-RGB refusal"),
    ("does not give you NDVI", "the converted-camera refusal"),
    ("It cannot be compared to another one", "the uncorrected-flight refusal"),
    ("will not invent a", "the shield refusal"),
]:
    ck("source still carries %s" % why, phrase in SRC, phrase)

print("\n".join("PASS  " + x for x in P))
if F:
    print("\n".join("FAIL  " + x for x in F))
print("-" * 60)
print("%d passed, %d failed" % (len(P), len(F)))
sys.exit(1 if F else 0)
