# -*- coding: utf-8 -*-
import sys, re
from playwright.sync_api import sync_playwright
import os as _os
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
