# -*- coding: utf-8 -*-
"""Front-end sweep: the faults that are not any one page's subject.

Duplicate ids, getElementById calls naming ids that do not exist, internal links
that go nowhere, a missing viewport meta or lang attribute, inputs under 16px
(which makes iOS zoom on focus -- a stated constraint of this kit), unguarded
localStorage, innerHTML built from a raw input value, JS and console errors, and
horizontal overflow at three widths.

This lived at docs/audit-frontend.py with the container path of the session that
wrote it baked in, so it ran nowhere else and nobody could have known it was
broken. Moved here, made relative to the checkout, and wired into
tools/verify/run_all.py so it runs with everything else.

The 40px tap-target check it used to carry is gone: tools/audit_targets.py holds
the whole kit to 44px and measures it properly.

Run:  python3 tools/audit_frontend.py
Exits non-zero if any HIGH finding is present.
"""
import os, re, json, io, sys
from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")
PAGES = sorted(f for f in os.listdir(DOCS) if f.endswith(".html"))
findings = []
ID_REFS = {}
SRC = {}
def F(sev, page, kind, detail):
    findings.append({"sev":sev,"page":page,"kind":kind,"detail":detail})

# ---- static pass ----
for p in PAGES:
    src = io.open(os.path.join(DOCS,p), encoding="utf-8").read()
    # duplicate ids
    ids = re.findall(r'\sid="([^"]+)"', src)
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes: F("HIGH", p, "duplicate-id", ", ".join(dupes))
    # getElementById targets that don't exist in markup
    # Which ids exist is a RUNTIME question. This used to be answered from the
    # markup, and reported three ids on cp-bench as missing that are created by a
    # factory emitting id="'+id+'" into innerHTML -- present, wired, and working,
    # just invisible to a text search. Collected here, checked in the live DOM in
    # the browser pass below, where the answer is not a guess.
    SRC[p] = src
    ID_REFS[p] = sorted(set(re.findall(r'getElementById\("([^"]+)"\)', src))
                        | set(re.findall(r'\$\("([^"]+)"\)', src)))
    # internal links that don't resolve
    for h in set(re.findall(r'href="([^"#][^"]*\.html)(?:#[^"]*)?"', src)):
        if h.startswith("http://") or h.startswith("https://") or h.startswith("//"):
            continue          # an external citation, already counted as one
        if not os.path.exists(os.path.join(DOCS, h.split("#")[0])):
            F("HIGH", p, "dead-link", h)
    # external resources other than google fonts (CSP risk when published)
    for u in set(re.findall(r'(?:src|href)="(https?://[^"]+)"', src)):
        if "fonts.googleapis.com" not in u and "fonts.gstatic.com" not in u and "claude.ai" not in u \
           and "github.com" not in u:
            F("MED", p, "external-resource", u)
    # print stylesheet present?
    if "@media print" not in src: F("MED", p, "no-print-css", "page has no @media print block")
    # viewport meta
    if 'name="viewport"' not in src: F("HIGH", p, "no-viewport-meta", "missing viewport meta")
    # lang attr
    if not re.search(r'<html[^>]*\slang=', src): F("LOW", p, "no-lang", "html has no lang attribute")
    # inputs smaller than 16px font (iOS zoom on focus)
    for m in re.finditer(r'input\[type=[^\]]*\][^{]*\{([^}]*)\}', src):
        fs = re.search(r'font:\s*(\d+(?:\.\d+)?)px', m.group(1))
        if fs and float(fs.group(1)) < 16:
            F("MED", p, "input-font-under-16", "%spx — iOS auto-zooms on focus" % fs.group(1))
    # localStorage without try/catch
    for m in re.finditer(r'localStorage\.(getItem|setItem|clear|removeItem)', src):
        seg = src[max(0,m.start()-160):m.start()]
        if "try" not in seg:
            F("MED", p, "unguarded-localStorage", src[max(0,m.start()-40):m.start()+40].replace("\n"," "))
    # innerHTML with a raw user-ish variable (XSS-ish smell) — flag only unescaped .value
    for m in re.finditer(r'innerHTML\s*=\s*[^;]{0,200}', src):
        seg = m.group(0)
        if ".value" in seg and "esc(" not in seg and "csvCell" not in seg:
            F("MED", p, "innerHTML-unescaped-value", seg[:110].replace("\n"," "))

# ---- runtime pass ----
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for p in PAGES:
        for w,h,label in ((390,844,"phone"),(820,1180,"tablet"),(1280,900,"desktop")):
            # Offline by design: this sweep is about the page's own markup and
            # scripts, and waiting on a webfont CDN adds minutes and nothing
            # else. It also means the sweep runs the same in a field, in CI, and
            # in a container with no DNS -- which is why it used wall-clock
            # minutes before and seconds now.
            ctx = b.new_context(viewport={"width":w,"height":h})
            ctx.set_offline(True)
            pg = ctx.new_page()
            errs=[]; cons=[]
            pg.on("pageerror", lambda e, L=errs: L.append(str(e)))
            pg.on("console", lambda m, L=cons: L.append(m.type+": "+m.text) if m.type=="error" else None)
            try:
                pg.goto("file://"+os.path.join(DOCS,p), wait_until="domcontentloaded", timeout=25000)
                pg.wait_for_timeout(500)
            except Exception as e:
                F("HIGH", p, "load-failed", "%s @%s: %s" % (p,label,e)); ctx.close(); continue
            for e in errs: F("HIGH", p, "js-error@"+label, e)
            if label == "phone":
                gone = pg.evaluate(
                    "(ids)=>ids.filter(i=>!document.getElementById(i))", ID_REFS.get(p, []))
                # An id absent at load is not by itself a fault -- most of these
                # pages build controls on demand, and the code guards with
                # var b = $("x"); if (b) ... . What IS worth listing is a BARE
                # dereference of one: $("x").addEventListener(...) throws the
                # moment it runs before its element exists. Whether that path is
                # reachable is not something a static scan can settle, so this is
                # reported as a risk to look at rather than a proven defect --
                # the js-error rows above are the ones with teeth.
                for i in sorted(gone):
                    bare = re.findall(
                        r'(?:\$|document\.getElementById)\(\s*"%s"\s*\)\s*\.' % re.escape(i), SRC[p])
                    if bare:
                        F("MED", p, "unguarded-ref-to-absent-id",
                          "%s dereferenced directly and absent at load (%d site%s)"
                          % (i, len(bare), "" if len(bare) == 1 else "s"))
            for c in cons:
                if "ERR_" not in c and "favicon" not in c: F("MED", p, "console-error@"+label, c)
            # horizontal overflow
            ow = pg.evaluate("document.documentElement.scrollWidth"); 
            if ow > w + 2:
                worst = pg.evaluate("""(vw)=>{let out=[];document.querySelectorAll('*').forEach(el=>{
                  const r=el.getBoundingClientRect(); if(r.right>vw+2 && r.width>40){
                    let ok=false,q=el; while(q){const s=getComputedStyle(q);
                      if(s.overflowX==='auto'||s.overflowX==='scroll'){ok=true;break;} q=q.parentElement;}
                    if(!ok) out.push((el.tagName+'.'+(el.className||'')).slice(0,50)+' r='+Math.round(r.right));}});
                  return out.slice(0,4);}""", w)
                if worst: F("MED", p, "h-overflow@"+label, "scrollW=%d vw=%d :: %s" % (ow,w,worst))
            ctx.close()
    b.close()

os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
order={"HIGH":0,"MED":1,"LOW":2}
findings.sort(key=lambda f:(order[f["sev"]], f["page"], f["kind"]))
io.open(os.path.join(ROOT, "build", "frontend-findings.json"), "w", encoding="utf-8").write(json.dumps(findings,indent=1,ensure_ascii=False))
from collections import Counter
c=Counter(f["sev"] for f in findings)
print("pages swept: %d   findings: HIGH=%d MED=%d LOW=%d\n" % (len(PAGES), c["HIGH"], c["MED"], c["LOW"]))
for f in findings:
    print("[%s] %-28s %-26s %s" % (f["sev"], f["page"], f["kind"], f["detail"][:120]))

print()
print("%d/%d checks clear" % (len(PAGES) * 8 - c["HIGH"] - c["MED"], len(PAGES) * 8))
sys.exit(1 if c["HIGH"] else 0)
