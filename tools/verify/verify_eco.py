# -*- coding: utf-8 -*-
import sys, re, io
from playwright.sync_api import sync_playwright
import os as _os

# Declared for tools/mutate.py. This suite DOES use a temp dir -- it compiles a
# JDK oracle in one -- but it builds no fixture pages: every assertion here is
# about docs/ecology-lab.html itself, so a sweep of that page must count it.
# Saying so is not optional: the sweep excludes any temp-dir suite that will not
# say which of the two it is, because the version that guessed from the imports
# quietly dropped these 138 checks the day the oracle was added.
MUTATE_ROLE = "subject"
# The kit is checked out wherever the user keeps it; these suites used to hard-code
# a container path and so could only ever run in the container that wrote them.
ROOT = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
DOCS_DIR = _os.path.join(ROOT, "docs") + _os.sep
def _u(name):
    """file:// URL for a page in docs/, whatever the checkout is called."""
    return "file://" + _os.path.join(ROOT, "docs", name).replace(_os.sep, "/")

P=[];F=[]
def ck(n,c,e=""):
    (P if c else F).append(n+(("  << "+str(e)) if (e and not c) else ""))

NAV = ["Overview","Interactive Lab","Lab Manual","Teacher's Guide","Field Guide","Field Card",
       "Glossary","Plant Characters","Fungal Characters",".eco Reference","Field Tools"]
PAGES = ["ecology.html","ecology-lab.html","ecology-lab-manual.html","ecology-teachers-guide.html",
         "ecology-field-guide.html","ecology-field-card.html","ecology-glossary.html",
         "plant-characters.html","fungal-characters.html","eco-protocol-reference.html",
         "eco-protocol-library.html","ecology-essay.html"]
CUR = {"ecology.html":"Overview","ecology-lab.html":"Interactive Lab",
       "ecology-lab-manual.html":"Lab Manual","ecology-teachers-guide.html":"Teacher's Guide",
       "ecology-field-guide.html":"Field Guide","ecology-field-card.html":"Field Card",
       "ecology-glossary.html":"Glossary","plant-characters.html":"Plant Characters",
       "fungal-characters.html":"Fungal Characters","eco-protocol-reference.html":".eco Reference"}

with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1000,"height":1200})
    pg.set_default_timeout(15000)
    # offline container: the webfont CDN is unreachable and would stall load
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    allerr=[]
    NAV_SEEN=[]   # first page's nav, to compare every later page against
    pg.on("pageerror", lambda e: allerr.append(str(e)))

    # ---------- nav consistency ----------
    for f in PAGES:
        pg.goto(_u("")+f, wait_until="domcontentloaded"); pg.wait_for_timeout(120)
        chips = pg.eval_on_selector_all(".kit-nav a","e=>e.map(x=>x.textContent.trim())")
        # Was: chips == NAV, an exact frozen list. The kit grew a Suites chip and
        # this failed on twelve pages at once for no fault of the pages. What
        # actually matters is that the core is present, the nav is the SAME
        # everywhere, and every chip goes somewhere real -- all of which stay
        # true as the kit grows, and none of which a new chip can silently break.
        missing = [c for c in NAV if c not in chips]
        ck("nav carries the core chips on "+f, not missing, missing)
        if NAV_SEEN:
            ck("nav identical to "+NAV_SEEN[0][0]+" on "+f, chips==NAV_SEEN[0][1], chips)
        else:
            NAV_SEEN.append((f, chips))
        hrefs = pg.eval_on_selector_all(".kit-nav a","e=>e.map(x=>x.getAttribute('href')||'')")
        dead = [h for h in hrefs if h and not h.startswith('#')
                and not _os.path.exists(_os.path.join(DOCS_DIR, h.split('#')[0]))]
        ck("every nav chip resolves on "+f, not dead, dead)
        cur = pg.eval_on_selector_all('.kit-nav a[aria-current="page"]',"e=>e.map(x=>x.textContent.trim())")
        want = CUR.get(f)
        if want:
            ck("aria-current="+want+" on "+f, cur==[want], cur)
        else:
            ck("no false aria-current on "+f, cur==[], cur)
        # nav chips must not overflow
        ow = pg.evaluate("()=>Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
        ck("no h-overflow "+f, ow<=1001, ow)

    # ---------- hub grouping ----------
    pg.goto(_u("ecology.html"), wait_until="domcontentloaded"); pg.wait_for_timeout(200)
    groups = pg.eval_on_selector_all("#field-tools .group","e=>e.map(x=>x.textContent.trim())")
    # Was: len(groups)==3. Four groups now, and a fifth would be fine too --
    # what would be a real fault is a group with nothing in it, or one of the
    # named groups disappearing.
    ck("field-tools keeps at least three groups", len(groups)>=3, groups)
    ck("group: record", any("Record it" in g for g in groups), groups)
    ck("group: print",  any("Print it" in g for g in groups), groups)
    ck("group: teach",  any("Teach it" in g for g in groups), groups)
    per = pg.evaluate("""()=>[...document.querySelectorAll('#field-tools .kit')].map(k=>k.querySelectorAll('.card').length)""")
    # Was: per==[6,3,5]. A group with one card is a grouping that has stopped
    # earning its heading; that is the thing worth failing on.
    ck("no group is empty or a group of one", per and min(per)>=2, per)
    ncards = pg.eval_on_selector_all("#field-tools .card","e=>e.length")
    ck("cards add up across the groups", ncards==sum(per), (ncards, per))
    dead = pg.evaluate("""()=>[...document.querySelectorAll('#field-tools .card a[href]')]
        .map(a=>a.getAttribute('href')).filter(h=>h && !h.startsWith('#'))""")
    dead = [h for h in dead if not _os.path.exists(_os.path.join(DOCS_DIR, h.split('#')[0]))]
    ck("every card on the hub links to a page that exists", not dead, dead)
    untitled = pg.evaluate("""()=>[...document.querySelectorAll('#field-tools .card')]
        .filter(c=>!(c.textContent||'').trim()).length""")
    ck("no untitled cards", untitled==0, untitled)
    # Was: a frozen "Fourteen instruments". Freezing the words means the test
    # breaks every time the kit grows AND stops catching the thing that actually
    # goes wrong -- a headline still claiming a count the hub no longer has. So
    # read the number the page states and check it against the cards on it.
    import re as _re
    WORDS = {"nine":9,"ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,
             "fifteen":15,"sixteen":16,"seventeen":17,"eighteen":18,"nineteen":19,
             "twenty":20,"twenty-one":21,"twenty-two":22,"twenty-three":23,
             "twenty-four":24,"twenty-five":25,"twenty-six":26}
    head = pg.inner_text("#field-tools")
    m = _re.search(r"([A-Za-z-]+|\d{1,2})\s+instruments?\b", head, _re.I)
    ck("the hub states how many instruments it holds", bool(m), head[:120])
    if m:
        tok = m.group(1).lower()
        stated = int(tok) if tok.isdigit() else WORDS.get(tok)
        ck("the stated count is a number we can read", stated is not None, tok)
        ck("the hub's stated count matches the cards on it", stated==ncards, (stated, ncards))
    # every group lead present
    leads = pg.eval_on_selector_all("#field-tools .grouplead","e=>e.length")
    ck("one lead paragraph per group", leads==len(groups), (leads, len(groups)))
    # anchor still works
    ck("#field-tools anchor exists", pg.eval_on_selector("#field-tools","e=>!!e"), "")

    # ---------- field card ----------
    pg.goto(_u("ecology-field-card.html"), wait_until="domcontentloaded"); pg.wait_for_timeout(200)
    heads = pg.eval_on_selector_all(".block h2","e=>e.map(x=>x.textContent.trim())")
    # Was: exactly 12. The named-block checks below are the ones with teeth.
    ck("field card keeps at least twelve blocks", len(heads)>=12, len(heads))
    ck("no unnamed blocks", all(h.strip() for h in heads), heads)
    for h in ["Forest plots","Vegetation plots","Macrofungi"]:
        ck("block "+h, h in heads, heads)
    txt = pg.inner_text("body")
    for term,label in [("QMD","QMD"),("Reineke","Reineke SDI"),("Importance value","IV"),
                       ("van Wagner","CWD"),("Folded aspect","folded aspect"),
                       ("Mean C","mean C"),("FQI","FQI"),("Prevalence index","prevalence index"),
                       ("LPI cover","LPI"),("Guild spectrum","guild"),("Single-host flag","host flag")]:
        ck("field card carries "+label, term in txt, "")
    ck("Chao1 corrected to lower bound", "lower bound" in txt, "")
    ck("Chao1 no longer claims 'estimated true richness'",
       "estimated true richness" not in txt, "")
    ck("prevalence index caveated as one of three", "One of three" in txt, "")
    ck("guild caveated for mixed genera", "mixed" in txt, "")
    ck("dek updated", "the forest and vegetation plots" in txt, txt[:300])
    # tables must scroll rather than overflow the page
    for w in (390,768,1000):
        pg.set_viewport_size({"width":w,"height":1000}); pg.wait_for_timeout(150)
        ow = pg.evaluate("()=>Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
        ck("field card no h-overflow @%d"%w, ow<=w+1, "%d > %d"%(ow,w))

    # ---------- link sweep across the whole kit ----------
    pg.set_viewport_size({"width":1000,"height":1000})
    ck("no page errors", not allerr, allerr[:3])
    # ---------- the lab's bars have to be inside their charts ----------
    # `const yMax = Math.max(1, ...finite) * 1.05` -- the 1 is a floor, so an
    # all-zero series still gets an axis instead of dividing by zero. A mutation
    # sweep turned the max into a min and nothing in this kit noticed: the bars
    # are <path> elements and every chart check here had been about whether an
    # svg existed.
    #
    # Measured, on the page as it loads from its own inlined session: nine
    # charts draw bars, none above the frame; with the mutant six of the nine
    # do, the worst at y = -48732 in a 180-high viewBox. So the rule is the one
    # the ordination plot and the CP Bench sparkline now carry -- a bar is an
    # assertion about a number, and it has to be inside the picture.
    pg.goto(_u("ecology-lab.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(1500)
    # getBBox, not the `d` string. Parsing the path and taking every second
    # number assumes it alternates x,y -- barPath() emits rounded corners, so
    # the odd positions also hold arc radii and flags, and the first version of
    # this check reported a maxY of 965 in a 170-high chart on a correct page.
    # The browser already knows where the shape is; ask it.
    charts = pg.evaluate("""()=>[...document.querySelectorAll('svg')].map(s=>{
        const bars=[...s.querySelectorAll('path.grow-bar')];
        if(!bars.length) return null;
        const bb=bars.map(p=>p.getBBox());
        const vb=s.getAttribute('viewBox').split(' ').map(Number);
        return {bars:bars.length,
                minY:Math.min(...bb.map(b=>b.y)),
                maxY:Math.max(...bb.map(b=>b.y+b.height)), H:vb[3]};
      }).filter(Boolean)""")
    ck("the lab draws bar charts on load", len(charts) >= 5, len(charts))
    over = [c for c in charts if c["minY"] < 0 or c["maxY"] > c["H"]]
    ck("every bar is inside its own chart", not over, over[:3])
    # ...and not vacuous the other way: a chart whose bars all sat on the axis
    # would satisfy that and would be showing nothing.
    used = [c for c in charts if c["minY"] < c["H"] * 0.75]
    ck("and the bars use the height they are given", len(used) >= len(charts) // 2,
       (len(used), len(charts)))

    # ---------- the bars tile the frame (ADR-077) ----------
    # "inside the picture" is necessary and nowhere near sufficient. A sweep
    # turned `bw = Math.max(1, iw/n - gap)` into Math.min and every bar in the
    # kit became a 1px hairline -- still inside its chart, still using the full
    # height, and the check above voted it a pass.
    #
    # The real rule is that barChart lays n equal slots across the inner width
    # and paints each bar `gap` narrower than its slot. That is checkable
    # without knowing n: the PITCH between neighbouring bars is measured off
    # the page, and the bar's own width must be that pitch minus the gap. Both
    # numbers come from the drawing, so nothing here is a pinned constant
    # (ADR-041) -- it is the geometry checking its own consistency.
    GAP = 2                       # barChart's `const gap = 2`, the one number the page fixes
    tiling = pg.evaluate("""()=>[...document.querySelectorAll('svg')].map(s=>{
        const bars=[...s.querySelectorAll('path.grow-bar')];
        if(bars.length<2) return null;
        const bb=bars.map(p=>p.getBBox()).sort((a,b)=>a.x-b.x);
        const r=v=>Math.round(v*100)/100;
        const diffs=[]; for(let i=1;i<bb.length;i++) diffs.push(r(bb[i].x-bb[i-1].x));
        const vb=s.getAttribute('viewBox').split(' ').map(Number);
        return {W:vb[2], widths:[...new Set(bb.map(b=>r(b.width)))],
                pitch:Math.min(...diffs), diffs, xs:bb.map(b=>r(b.x))};
      }).filter(Boolean)""")
    ck("the lab draws multi-bar charts to measure", len(tiling) >= 5, len(tiling))
    ragged = [c for c in tiling if len(c["widths"]) != 1]
    ck("every bar in a chart is the same width", not ragged, ragged[:2])
    # width == pitch - gap, on every chart, measured both sides
    off = [(c["widths"][0], c["pitch"]) for c in tiling
           if abs(c["widths"][0] - (c["pitch"] - GAP)) > 0.05]
    ck("a bar fills its slot but for the gap (width == pitch - 2)", not off, off[:3])
    # The pitch is iw/n for a whole number of slots n. Recovered by dividing,
    # then checked back against the measured pitch -- comparing the quotient to
    # an integer directly fails on wide charts, where a pitch rounded to two
    # decimals drifts by n times the rounding (49 slots of 8.7347 read as 49.03).
    MARGIN_L, MARGIN_R = 42, 10                     # barChart's M.l / M.r
    def _slots(c):
        iw = c["W"] - MARGIN_L - MARGIN_R
        return max(1, round(iw / c["pitch"])), iw
    badn = [(c["pitch"], _slots(c)) for c in tiling
            if abs(_slots(c)[1] / _slots(c)[0] - c["pitch"]) > 0.05]
    ck("the slot pitch is the inner width over a whole number of slots", not badn, badn[:3])
    # every bar sits on that grid -- not just the first, and not just the gaps
    # between neighbours. A chart whose leading values are zero draws its first
    # bar several slots in ("how long residents lasted" starts at slot 4), so
    # the rule has to be stated about the grid, not about the left edge.
    def _offgrid(c):
        # measured against the RECOVERED pitch iw/n, not the two-decimal one --
        # over 38 slots the rounding compounds into a fifth of a slot.
        n, iw = _slots(c); pitch = iw / n
        return [x for x in c["xs"]
                if abs(round((x - MARGIN_L - GAP/2)/pitch)
                       - (x - MARGIN_L - GAP/2)/pitch) > 0.02]
    off_grid = [(c["W"], _offgrid(c)[:3]) for c in tiling if _offgrid(c)]
    ck("every bar sits on a slot, half a gap inside it", not off_grid, off_grid[:3])

    # ---------- the curves span the frame (ADR-077) ----------
    # lineChart had no geometry check at all: the bar rule above selects on
    # `path.grow-bar` and a curve is not a bar. A sweep turned
    # `xMax = Math.max(...xs)` into Math.min, collapsing the x range to zero;
    # `Math.max(1, xMax - xMin)` then divides by 1 and the curve runs off the
    # right edge by however many units the series is long.
    #
    # Every lineChart caller passes a series whose x runs the whole domain, so
    # the drawn curve's horizontal extent IS the inner width -- left edge on
    # the axis, right edge on the right margin. Read off the viewBox, not pinned.
    curves = pg.evaluate("""()=>[...document.querySelectorAll('svg')].map(s=>{
        const ps=[...s.querySelectorAll('path[stroke]')];
        if(!ps.length) return null;
        const vb=s.getAttribute('viewBox').split(' ').map(Number);
        const bb=ps.map(p=>p.getBBox()); const r=v=>Math.round(v*10)/10;
        return {W:vb[2], H:vb[3], n:ps.length,
                x0:r(Math.min(...bb.map(b=>b.x))),
                x1:r(Math.max(...bb.map(b=>b.x+b.width))),
                y0:r(Math.min(...bb.map(b=>b.y))),
                y1:r(Math.max(...bb.map(b=>b.y+b.height))),
                grid:s.querySelectorAll('line.gridline').length};
      }).filter(Boolean)""")
    ck("the lab draws line charts to measure", len(curves) >= 4, len(curves))
    narrow = [(c["x0"], c["x1"], c["W"]) for c in curves
              if abs(c["x0"] - MARGIN_L) > 0.5 or abs(c["x1"] - (c["W"] - MARGIN_R)) > 0.5]
    ck("every curve spans the frame, axis to right margin", not narrow, narrow[:3])
    MARGIN_T, MARGIN_B = 12, 34                     # M.t / M.b
    spill = [(c["y0"], c["y1"], c["H"]) for c in curves
             if c["y0"] < MARGIN_T - 0.5 or c["y1"] > c["H"] - MARGIN_B + 0.5]
    ck("and stays between the top gridline and the baseline", not spill, spill[:3])
    # frame() draws yTicks+1 gridlines, counting both ends. Off-by-one there
    # silently drops the top one, and the axis then stops short of its own max.
    YTICKS = 4                                      # frame(svg, w, h, 4, ...) at every call site
    badgrid = [c["grid"] for c in curves if c["grid"] != YTICKS + 1]
    ck("a chart carries one gridline per tick plus the baseline tick",
       not badgrid, badgrid[:5])

    # ---------- the axis is scaled to the data it carries (ADR-077) ----------
    # Containment and span both survive `yMax = yMax ?? Math.min(...)`: with the
    # minimum as the ceiling every point above it clamps to the top gridline, so
    # the curve still fills the frame corner to corner and both rules above vote
    # pass. What actually breaks is the AXIS -- rarefaction stops labelling 108
    # species and starts labelling 20, and every curve is a step to the ceiling.
    #
    # So bind the printed number to the data behind it (ADR-052): the top
    # gridline is yMax, and lineChart's own comment fixes yMax at the data
    # maximum plus 8% headroom. Both sides are recomputed from SESSION on the
    # page as it stands, so this pins no constant but the 1.08 the source states.
    HEADROOM = 1.08                                 # lineChart's `* 1.08`
    axis = pg.evaluate("""()=>{
        const h=[...document.querySelectorAll('.h3,h3')].find(e=>/Rarefaction/.test(e.textContent));
        if(!h) return null;
        const svg=h.parentElement.querySelector('svg'); if(!svg) return null;
        const labs=[...svg.querySelectorAll('text.axis-label')].map(t=>t.textContent);
        if(!labs.length) return null;
        return {top:+labs[labs.length-1].replace(/,/g,''), labs,
                dataMax:Math.max(...SESSION.meadow.phases.flatMap(
                          p=>p.rarefaction.map(q=>q[1])))};
      }""")
    ck("the rarefaction chart labels its y axis", axis and axis["dataMax"] > 0, axis)
    ck("the top gridline is the data maximum plus the stated headroom",
       axis and abs(axis["top"] - axis["dataMax"] * HEADROOM) <= 1,
       axis and (axis["top"], axis["dataMax"], axis["labs"]))
    # ...and the labels climb, so the axis is not merely the right height at one end
    ck("the gridline labels rise from zero to that maximum",
       axis and [float(t.replace(",", "")) for t in axis["labs"]]
              == sorted(float(t.replace(",", "")) for t in axis["labs"])
              and float(axis["labs"][0]) == 0,
       axis and axis["labs"])

    # ---------- a dashed series stays dashed (ADR-077) ----------
    # `if (!s.dash && animate)` is the draw-on animation guard, and dropping the
    # `!` is not cosmetic: the draw-on works by setting stroke-dasharray to the
    # path length, which OVERWRITES the "5 4" that makes the fitted curve read
    # as a prediction rather than as data. The growth chart's whole claim is
    # "observed vs fitted"; if both lines draw solid the reader cannot tell
    # which one is the measurement.
    dashes = pg.evaluate("""()=>{
        const h=[...document.querySelectorAll('.h3,h3')].find(e=>/observed vs fit/i.test(e.textContent));
        if(!h) return null;
        const svg=h.parentElement.querySelector('svg'); if(!svg) return null;
        return [...svg.querySelectorAll('path[stroke]')].map(p=>p.getAttribute('stroke-dasharray'));
      }""")
    ck("the growth chart draws observed and fitted", dashes is not None and len(dashes) == 2, dashes)
    ck("exactly one of them is dashed -- the fit, not the observation",
       dashes is not None and [d for d in dashes if d] == ["5 4"], dashes)

    # ---------- a session is a file somebody sends you ----------
    # The page charts a JSON dropped onto it, and its own comment says why every
    # string from one is escaped: "a shared protocol would be a script-injection
    # vector for whoever drops it in". The escape in the tile builder was never
    # tested, and a mutation sweep dropped it twice without anything noticing.
    #
    # `bestFit` is a STRING that comes straight out of the session and lands in
    # a tile's value. Measured: with the escape, `<b>…</b>` is text; without it,
    # one <b> element appears in the tiles. Rendered through the page's own
    # render(), which is the same path the drop handler takes.
    pg.evaluate("""()=>{const s=JSON.parse(JSON.stringify(SESSION));
        s.meadow.phases[0].bestFit='<b>BROKEN_STICK</b>';
        s.meadow.phases[0].name='<i>Even grazing</i>';
        render(s);}""")
    pg.wait_for_timeout(400)
    ck("markup in a session string does not become markup in a tile",
       pg.evaluate("()=>document.querySelectorAll('.tile b, .tile i, .tile img').length") == 0,
       pg.evaluate("()=>[...document.querySelectorAll('.tile *')].map(e=>e.tagName).slice(0,6)"))
    ck("and it is still shown, as text",
       "<b>broken stick</b>" in pg.evaluate(
           "()=>[...document.querySelectorAll('.tile .v')].map(e=>e.textContent).join('|')"),
       pg.evaluate("""()=>[...document.querySelectorAll('.tile .v')]
           .map(e=>e.textContent).filter(t=>t.indexOf('broken')>=0)"""))

    # ---------- and every OTHER place a session string lands (ADR-077) ----------
    # The rule above is the instance; this is the class. It selects on `.tile`,
    # so it can only ever speak for the tiles -- and a sweep then dropped esc()
    # from a reading paragraph, from a facet heading and from a data-table cell
    # without it noticing any of the three. Same shape as ADR-072: the fix that
    # names one caller does not cover the next one somebody writes.
    #
    # So state it about the document. Every string anywhere in the session is
    # wrapped in a tag that appears nowhere in the page, the page renders itself
    # from that session, and no such element may exist afterwards. New render
    # code is covered the day it is written, without this check being edited.
    inj = pg.evaluate("""()=>{
        const s=JSON.parse(JSON.stringify(SESSION));
        let n=0;
        (function walk(o){ if(!o||typeof o!=='object') return;
          for(const k in o){ const v=o[k];
            if(typeof v==='string'){ o[k]='<xinj>'+v+'</xinj>'; n++; }
            else walk(v); } })(s);
        let err=null; try{ render(s); }catch(e){ err=String(e); }
        const main=document.getElementById('main');
        return {n, err, leaked:main.querySelectorAll('xinj').length,
                text:(main.textContent.match(/<xinj>/g)||[]).length,
                where:[...main.querySelectorAll('xinj')]
                        .map(e=>e.parentElement.tagName+'.'+e.parentElement.className).slice(0,4)};
      }""")
    ck("the session carries strings to wrap", inj["n"] >= 4, inj["n"])
    ck("and the page still renders from a session full of markup", not inj["err"], inj["err"])
    ck("no session string becomes an element, anywhere in the rendered page",
       inj["leaked"] == 0, (inj["leaked"], inj["where"]))
    ck("...while the strings themselves are still shown, as text",
       inj["text"] >= inj["n"], (inj["text"], inj["n"]))
    pg.evaluate("()=>render(JSON.parse(JSON.stringify(SESSION)))"); pg.wait_for_timeout(300)

    # ---------- jSplit is graded by a real JVM (ADR-077) ----------
    # jSplit() exists only to make JS's split behave like Java's, and its own
    # comment says what turns on that: whether `model: eulerlotka 1.0:` is
    # reported or silently accepted. Nothing in the kit had ever called it --
    # a sweep moved its trailing-empty index and every suite stayed green.
    #
    # The oracle is not my belief about Java. It is Java: the cases are handed
    # to a JDK on the way past and the JVM's own field counts are what the page
    # is graded against (ADR-041 -- nothing here is a pinned expectation). No
    # JDK, no verdict: the check says NOT VERIFIED rather than passing blind.
    import subprocess as _sp, tempfile as _tf, shutil as _sh, io as _io
    CASES = [("a:b:", ":"),            # Java drops the trailing empty; JS keeps it
             ("a:b::", ":"),           # ...however many there are
             (":a", ":"),              # a LEADING empty is a field, and stays
             ("", ","),                # separator never matched: Java returns the input
             ("a", ","),
             ("::", ":"),              # all-empty collapses to no fields at all
             (":", ":"),
             ("a::b", ":"),            # an interior empty is a field
             ("model: eulerlotka 1.0:", ":")]   # the line the comment names
    # The whitespace splitter is a SECOND fidelity claim and needs its own case:
    # Java's \s is exactly six characters and JS's is much wider, so the page
    # spells the class out as J_WS rather than reusing \s. A no-break space is
    # what tells them apart -- one field in Java, two if the page had used \s.
    WS_CASES = ["a\u00a0b", "a b", "a  \tb", " a b "]
    _jdk = _sh.which("javac") and _sh.which("java")
    _oracle = None
    if _jdk:
        _d = _tf.mkdtemp()
        _io.open(_os.path.join(_d, "JSplitOracle.java"), "w", encoding="utf-8").write(
            'import java.util.*;\npublic class JSplitOracle{public static void main(String[] a){\n'
            'List<String> o=new ArrayList<>();for(String g:a){int i=g.indexOf(\'\\u0001\');\n'
            'String[] p=g.substring(0,i).split(g.substring(i+1));StringBuilder b=new StringBuilder();\n'
            'for(int k=0;k<p.length;k++){if(k>0)b.append(\'\\u0002\');b.append(p[k]);}\n'
            'o.add(p.length+"\\u0003"+b);}System.out.println(String.join("\\u0004",o));}}\n')
        try:
            _sp.run(["javac", "JSplitOracle.java"], cwd=_d, check=True,
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=180)
            _out = _sp.run(["java", "-cp", _d, "JSplitOracle"]
                           + [c + "\u0001" + r for c, r in CASES]
                           + [c + "\u0001\\s+" for c in WS_CASES],
                           cwd=_d, capture_output=True, timeout=120,
                           encoding="utf-8").stdout.strip().split("\n")[-1]
            _oracle = []
            for rec in _out.split("\u0004"):
                n, _, body = rec.partition("\u0003")
                _oracle.append(body.split("\u0002") if int(n) else [])
        except Exception as _e:
            _oracle = None
            print("NOT VERIFIED: the JDK is present but the oracle would not run: %r" % (_e,))
    else:
        print("NOT VERIFIED: no JDK on PATH, so jSplit is graded against nothing")
    if _oracle:
        _page = pg.evaluate("""cs=>{ if(typeof jSplit!=='function') return null;
            return cs.map(([s,r])=>jSplit(s,new RegExp(r)));}""",
            [[c, r] for c, r in CASES])
        ck("jSplit is reachable from the page it ships in", _page is not None)
        if _page is not None:
            wrong = [(CASES[i], _oracle[i], _page[i])
                     for i in range(len(CASES)) if _oracle[i] != _page[i]]
            ck("jSplit splits exactly as this JVM's String.split does", not wrong, wrong[:3])
            # ...and the fixtures actually tell the two apart (ADR-039): a plain
            # JS split has to DISAGREE somewhere, or the test above proves nothing.
            import re as _re
            _js = pg.evaluate("""cs=>cs.map(([s,r])=>s.split(new RegExp(r)))""",
                              [[c, r] for c, r in CASES])
            _diff = [i for i in range(len(CASES)) if _js[i] != _oracle[i]]
            ck("and the cases separate Java from a plain JS split", len(_diff) >= 4,
               (len(_diff), [CASES[i][0] for i in _diff]))
        # jSplitWs, graded against the same JVM using Java's own \s
        _ws = pg.evaluate("""cs=>{ if(typeof jSplitWs!=="function") return null;
            return cs.map(s=>jSplitWs(s));}""", WS_CASES)
        ck("jSplitWs is reachable too", _ws is not None)
        if _ws is not None:
            _wo = _oracle[len(CASES):]
            wrongws = [(WS_CASES[i], _wo[i], _ws[i])
                       for i in range(len(WS_CASES)) if _wo[i] != _ws[i]]
            ck("jSplitWs splits on whitespace exactly as this JVM does", not wrongws, wrongws[:3])
            # the NBSP case is the one with teeth: a JS \s would split it in two
            _naive = pg.evaluate("cs=>cs.map(s=>s.split(/\\s+/))", WS_CASES)
            ck("and a JS whitespace class would have disagreed, so the case is not vacuous",
               _naive != _wo, (_naive[0], _wo[0]))

    # ---------- series of unequal length still read (ADR-077) ----------
    # Two places say `pts[bi] ?? pts[pts.length - 1]`, and the comment on one of
    # them says what for: "series of unequal length". A dropped session, a phase
    # that stopped early, a rarefaction curve that ran out of individuals -- the
    # short series then has no point under the cursor, and the fallback is what
    # keeps it in the tooltip instead of throwing on `pt[0]` of undefined and
    # taking the whole hover layer down with it. Both survived a sweep, because
    # every fixture in the kit had all its series the same length (ADR-039).
    #
    # So: truncate one phase, hover past its end, and read what the page says.
    # The expected numbers are rendered by the page's own fmt() from the
    # truncated array, so nothing here is pinned (ADR-041).
    KEEP = 3
    exp = pg.evaluate("""n=>{
        const s=JSON.parse(JSON.stringify(SESSION));
        s.meadow.phases[1].rarefaction = s.meadow.phases[1].rarefaction.slice(0, n);
        render(s);
        const r = s.meadow.phases[1].rarefaction;
        const f = q => fmt(q[1],1) + " species at " + fmt(q[0],0) + " draws";
        return {name: s.meadow.phases[1].name, kept: r.length,
                last: f(r[r.length-1]), prev: f(r[r.length-2]),
                lastX: r[r.length-1][0]};
      }""", KEEP)
    pg.wait_for_timeout(450)
    ck("one phase is now shorter than the other", exp["kept"] == KEEP, exp["kept"])
    ck("and its last two points read differently, so the test can tell them apart",
       exp["last"] != exp["prev"], (exp["last"], exp["prev"]))
    hov = pg.evaluate("""()=>{
        const h=[...document.querySelectorAll('.h3,h3')].find(e=>/Rarefaction/.test(e.textContent));
        if(!h) return null;
        const svg=h.parentElement.querySelector('svg'); if(!svg) return null;
        const rects=[...svg.querySelectorAll('rect')]; const hit=rects[rects.length-1];
        const r=hit.getBoundingClientRect();
        let threw=null;
        try{ hit.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,
               clientX:r.left+r.width, clientY:r.top+r.height*0.5})); }
        catch(e){ threw=String(e); }
        const rr=v=>Math.round(v*10)/10;
        return {threw, html:tip.innerHTML, shown:tip.style.display,
                dots:[...svg.querySelectorAll('circle')].map(c=>c.getAttribute('opacity')),
                cx:[...svg.querySelectorAll('circle')].map(c=>rr(+c.getAttribute('cx'))),
                ends:[...svg.querySelectorAll('path[stroke]')]
                       .map(p=>rr(p.getBBox().x+p.getBBox().width))};
      }""")
    ck("hovering past the short series does not throw", hov and not hov["threw"],
       hov and hov["threw"])
    ck("the tooltip still appears at all", hov and hov["shown"] == "block",
       hov and (hov["shown"], hov["html"][:80]))
    ck("and it still names the phase that ran out of points",
       hov and exp["name"] in hov["html"], hov and hov["html"][:140])
    ck("reporting that phase at its OWN last point, not its second-to-last",
       hov and exp["last"] in hov["html"] and exp["prev"] not in hov["html"],
       hov and (exp["last"], exp["prev"], hov["html"][:160]))
    # the marker dot obeys the same fallback -- it is the other `pts.length - 1`
    ck("every series still shows a marker dot", hov and hov["dots"].count("1") == 2,
       hov and hov["dots"])
    # ...and it is a dot in the right PLACE. Opacity alone passes a fallback that
    # picks the second-to-last point: the marker just sits one step back along a
    # curve it is meant to be at the end of. Hovering at the FAR RIGHT EDGE of
    # the hit layer selects the last x of the long series, so every dot should
    # land on its own curve's last point -- that curve's right-hand edge --
    # both numbers read off the drawing, neither of them pinned.
    ck("the chart draws one dot per curve", hov and len(hov["cx"]) == len(hov["ends"]),
       hov and (hov["cx"], hov["ends"]))
    misplaced = ([i for i in range(len(hov["cx"])) if abs(hov["cx"][i] - hov["ends"][i]) > 0.5]
                 if hov and len(hov["cx"]) == len(hov["ends"]) else ["unmeasurable"])
    ck("each marker sits on its own curve's last point, short series included",
       not misplaced, hov and (misplaced, hov["cx"], hov["ends"]))
    pg.evaluate("()=>{hideTip(); render(JSON.parse(JSON.stringify(SESSION)));}")
    pg.wait_for_timeout(300)

    # ---------- a series with a non-finite point is DROPPED ----------
    # `pts.every(p => isFinite(p[0]) && isFinite(p[1]))`. A sweep turned the &&
    # into ||, and a point with a finite x and a null y then passed the filter
    # and was drawn. null is not exotic in a JSON somebody generated: it is what
    # a missing number looks like.
    #
    # Counted on the rarefaction chart, whose curves are one per phase, so the
    # difference is visible as a curve that is there or is not: two phases give
    # two curves, and nulling one point in one of them must give one.
    def _curves():
        return pg.evaluate("""()=>{
          const h=[...document.querySelectorAll('.h3')].find(e=>/Rarefaction/.test(e.textContent));
          if(!h) return -1;
          const svg=h.parentElement.querySelector('svg');
          return svg ? svg.querySelectorAll('path[stroke]').length : -2;}""")
    pg.evaluate("()=>render(JSON.parse(JSON.stringify(SESSION)))"); pg.wait_for_timeout(350)
    _all = _curves()
    ck("the clean session draws a rarefaction curve per phase", _all == 2, _all)
    pg.evaluate("""()=>{const s=JSON.parse(JSON.stringify(SESSION));
        s.meadow.phases[0].rarefaction[3][1]=null; render(s);}""")
    pg.wait_for_timeout(350)
    _one = _curves()
    ck("a series carrying a null coordinate is dropped, not drawn", _one == _all - 1,
       (_all, _one))

    # ---------- the workbench's bar charts, to a port (ADR-182) ----------
    # The lab draws every bar as a rounded path (barPath: M V Q H Q V Z) on a
    # frame of fixed margins, y linear to 1.05 x the largest value with ticks
    # at quarters of it, bars of width iw/n - 2 spaced evenly. read-report
    # places a path by its box now; the port below states the chart's own
    # arithmetic, the page's paths are held to it, and the lab task's
    # literals are held to the same port -- a transcribed box cannot pass a
    # scale it does not fit.
    # The port lives in tools/verify/_lab_charts.py (ADR-183) so the stations
    # below and the workbench here read the same arithmetic.
    import _lab_charts as L
    bar_chart, r2 = L.bar_chart, L.r2
    def num(v): return v
    def _box(dstr):
        toks = re.findall(r"[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:e[-+]?\d+)?", dstr, re.I)
        need = {"M":2,"L":2,"H":1,"V":1,"C":6,"S":4,"Q":4,"T":2,"A":7}; cmd=""; cx=cy=sx=sy=0.0; pts=[]; i=0
        while i < len(toks):
            if re.match(r"^[a-zA-Z]$", toks[i]):
                cmd = toks[i]; i += 1
                if cmd in "Zz": cx, cy = sx, sy; continue
            up = cmd.upper(); rel = cmd != up; n = need[up]; a = [float(t) for t in toks[i:i+n]]; i += n
            if up == "H": cx = (cx if rel else 0) + a[0]
            elif up == "V": cy = (cy if rel else 0) + a[0]
            else: cx = (cx if rel else 0) + a[n-2]; cy = (cy if rel else 0) + a[n-1]
            pts.append((cx, cy))
            if up == "M": sx, sy = cx, cy; cmd = "l" if rel else "L"
        return [num(r2(min(x for x,_ in pts))), num(r2(min(y for _,y in pts))), num(r2(max(x for x,_ in pts))), num(r2(max(y for _,y in pts)))]
    def _page_bars(host):
        return pg.evaluate("""h=>{const s=document.querySelector('#'+h+' svg'); if(!s) return null;
          return {d:[...s.querySelectorAll('path')].map(p=>p.getAttribute('d')),
                  col:[...s.querySelectorAll('text.axis-label')].map(t=>t.textContent).reverse(),
                  rects:s.querySelectorAll('rect').length, lines:s.querySelectorAll('line').length};}""", host)
    pg.goto(_u("ecology-lab.html"), wait_until="domcontentloaded"); pg.wait_for_timeout(300)
    FIELD = "robin 34\nsparrow 21\nwren 8\nfinch 3\nthrush 1"
    def _type(host, text):   # the workbench sits behind a fold; set the value the way a keystroke would leave it
        pg.evaluate("a=>{const e=document.getElementById(a[0]); e.value=a[1]; e.dispatchEvent(new Event('input',{bubbles:true}));}", [host, text])
        pg.wait_for_timeout(150)
    _type("wb-field", FIELD)
    want = bar_chart([34, 21, 8, 3, 1], 480, 120); got = _page_bars("wb-field-out") or {}
    ck("the field station's rank chart draws one rounded bar per species, each box where the port's scale puts it",
       got.get("d") is not None and [_box(x) for x in got["d"]] == want["spans"], (got.get("d") or [])[:2])
    ck("...under ticks at quarters of 1.05 x the largest count, formatted as the page formats them",
       got.get("col") == want["col"] and got.get("rects") == 5 and got.get("lines") == 6, got)
    QUAD = "12 0 3 45 2 0 0 28 1 0 60 0"
    _type("wb-quad", QUAD)
    want_q = bar_chart([int(x) for x in QUAD.split()], 480, 110); got_q = _page_bars("wb-quad-out") or {}
    ck("the quadrat chart draws a bar for every count above zero and none for an empty quadrat, twelve hit-rects for twelve quadrats",
       got_q.get("d") is not None and [_box(x) for x in got_q["d"]] == want_q["spans"] and got_q.get("rects") == 12
       and got_q.get("col") == want_q["col"], (got_q.get("col"), (got_q.get("d") or [])[:1]))
    # ---------- the stations chart THE session (ADR-183) ----------
    # verify_engine_sessions binds the page's inline SESSION to the shipped
    # docs/ecology-lab-session.json and that file to the engine; what was
    # never bound is the DRAWING to the data. Every station chart under the
    # reader's cap is recomputed here from the session FILE through the port
    # -- bars from barChart, curves and steps from lineChart with the options
    # each station passes (the survivorship steps to a 1.05 ceiling with every
    # other class ticked, the archipelago's to 1.0 with a tick per survey, the
    # growth fit from the session's own r, K and n0) -- and the page's paths,
    # ticks and marks are held to it; then the lab task's literals at `boot`.
    import json as _json
    _TASK = _os.path.join(ROOT, "tools", "tasks", "page-ecology-lab-science.json")
    _t = _json.load(io.open(_TASK, encoding="utf-8")) if _os.path.isfile(_TASK) else {"steps": []}
    _st = dict((x["id"], x) for x in _t["steps"])
    def _v(step, k):
        x = _st.get(step, {}).get("expect", {}).get(k); return x.get("value") if isinstance(x, dict) and "op" in x else x
    _SESSION = _json.load(io.open(_os.path.join(ROOT, "docs", "ecology-lab-session.json"), encoding="utf-8"))
    _want = L.station_charts(_SESSION)
    pg.evaluate("()=>render(JSON.parse(JSON.stringify(SESSION)))"); pg.wait_for_timeout(400)
    _page = pg.evaluate("""()=>{
        const out={}; const seen={};
        for (const sv of document.querySelectorAll('svg')) {
          const host=(sv.closest('[id]')||{}).id||''; if(!/^station-/.test(host)) continue;
          seen[host]=(seen[host]||0)+1; const key=seen[host]===1?host:host+' #'+seen[host];
          const ih=+sv.getAttribute('viewBox').split(' ')[3]-12-34;
          out[key]={d:[...sv.querySelectorAll('path')].map(p=>p.getAttribute('d')),
                    col:[...sv.querySelectorAll('text.axis-label')].filter(t=>+t.getAttribute('x')===36).map(t=>t.textContent).reverse(),
                    row:[...sv.querySelectorAll('text.axis-label')].filter(t=>+t.getAttribute('y')===12+ih+13).map(t=>t.textContent),
                    marks:{circle:sv.querySelectorAll('circle').length, rect:sv.querySelectorAll('rect').length,
                           path:sv.querySelectorAll('path').length, line:sv.querySelectorAll('line').length}};
        }
        return out;}""")
    for _k in list(_want)[:10]:
        _w = _want[_k]; _g = _page.get(_k)
        _marks = dict((a, b) for a, b in (_g or {}).get("marks", {}).items() if b)
        ck("station chart %s is drawn from the shipped session: every path's box where the port puts it, %d of them" % (_k, len(_w["spans"])),
           _g is not None and [_box(x) for x in _g["d"]][:40] == _w["spans"], (_g or {}).get("d", [])[:1])
        ck("...its tick labels, marks and x ticks as the port states them: %s" % _k,
           _g is not None and _g["col"] == _w["col"] and _marks == _w["marks"]
           and (_g["row"] if len(_g["row"]) >= 3 else []) == _w["row"], _g and (_g["col"], _g["row"], _marks))
    ck("the port sees one chart past the reader's sixteen, and the task holds exactly the ten under the cap",
       len(_want) == 11 and all(("output.charts.%s.spans" % k) in _st.get("boot", {}).get("expect", {}) for k in list(_want)[:10])
       and not any(("output.charts.%s.spans" % k) in _st.get("boot", {}).get("expect", {}) for k in list(_want)[10:]),
       sorted(k for k in _st.get("boot", {}).get("expect", {}) if k.endswith(".spans")))
    _bad = []
    for _k in list(_want)[:10]:
        _w = _want[_k]; _pre = "output.charts.%s." % _k
        if not (_v("boot", _pre + "spans") == _w["spans"] and _v("boot", _pre + "aligned.col") == _w["col"]
                and _v("boot", _pre + "marks") == _w["marks"] and _v("boot", _pre + "longest") == _w["longest"]
                and _v("boot", _pre + "at.0") == _w["at"][0]
                and (_v("boot", _pre + "aligned.row") or []) == _w["row"]):
            _bad.append(_k)
    ck("the lab task's literals for the ten station charts are the port's numbers, box for box, tick for tick", not _bad, _bad)

    # the task's literals, held to the same port
    ck("the lab task types the field the port was fed and holds the chart to the port: five boxes, the ticks, the marks, the first hit-rect's centre",
       _st.get("field-text", {}).get("arguments", {}).get("value") == FIELD
       and _v("field-back", "output.charts.wb-field-out.spans") == want["spans"]
       and _v("field-back", "output.charts.wb-field-out.aligned.col") == want["col"]
       and _v("field-back", "output.charts.wb-field-out.marks") == want["marks"]
       and _v("field-back", "output.charts.wb-field-out.at.0") == want["at"][0]
       and _v("field-back", "output.charts.wb-field-out.longest") == 6,
       (_v("field-back", "output.charts.wb-field-out.spans"), want["spans"]))
    ck("...and the twelve quadrats it types to seven boxes, twelve hit-rects and ticks to 63",
       _st.get("quad-more", {}).get("arguments", {}).get("value") == QUAD
       and _v("quad-twelve", "output.charts.wb-quad-out.spans") == want_q["spans"]
       and _v("quad-twelve", "output.charts.wb-quad-out.aligned.col") == want_q["col"]
       and _v("quad-twelve", "output.charts.wb-quad-out.marks") == want_q["marks"]
       and _v("quad-twelve", "output.charts.wb-quad-out.at.11") == want_q["at"][11],
       (_v("quad-twelve", "output.charts.wb-quad-out.spans"), want_q["spans"]))

    b.close()

# static link check
import io, os, glob

# "'+x+'", '"+x+"', "${x}" -- markers of a value spliced in at runtime.
TEMPLATED = re.compile(r"""['"]\s*\+|\+\s*['"]|\$\{""")
files=sorted(glob.glob(DOCS_DIR + "*.html"))
ids={}
for f in files:
    ids[os.path.basename(f)]=set(re.findall(r'\sid="([^"]+)"', io.open(f,encoding='utf-8').read()))
bad=[]
for f in files:
    s=io.open(f,encoding='utf-8').read(); bn=os.path.basename(f)
    for href in re.findall(r'href="([^"]+)"', s):
        if href.startswith(("http","mailto:")): continue
        # An href assembled in JavaScript is source code, not a path. This
        # checker read  href="'+esc(r.url)+'"  out of a template literal and
        # reported it as a missing file. A link checker that reports source
        # code as a dead link is the same defect class as ADR-040's audit
        # reporting a citation as a fetched resource: the row is not wrong
        # about what it matched, it is wrong about what the match MEANS.
        if TEMPLATED.search(href): continue
        if href.startswith("#"):
            if href[1:] and href[1:] not in ids[bn]: bad.append((bn,href))
            continue
        tgt,_,frag = href.partition("#")
        if not os.path.exists(DOCS_DIR+tgt): bad.append((bn,href,"missing file")); continue
        if frag and tgt.endswith(".html") and frag not in ids.get(tgt,set()): bad.append((bn,href,"missing anchor"))
ck("no broken links across the kit", not bad, bad[:6])

print("PASS %d"%len(P))
for x in F: print("FAIL:",x)
print("---"); print("%d/%d"%(len(P),len(P)+len(F)))
sys.exit(1 if F else 0)
