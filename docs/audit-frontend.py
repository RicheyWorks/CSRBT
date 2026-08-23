# -*- coding: utf-8 -*-
"""Front-end full sweep: JS errors, console errors, dead links, orphan getElementById,
   viewport overflow, tap targets, print CSS, duplicate ids, a11y basics."""
import os, re, json, io
from playwright.sync_api import sync_playwright

DOCS = "/tmp/eco/CSRBT/docs"
PAGES = sorted(f for f in os.listdir(DOCS) if f.endswith(".html"))
findings = []
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
    refs = set(re.findall(r'getElementById\("([^"]+)"\)', src)) | set(re.findall(r'\$\("([^"]+)"\)', src))
    # ids can also be assigned at runtime (el.id = "x" / setAttribute("id","x")) — those are real
    idset = set(ids) | set(re.findall(r'\.id\s*=\s*"([^"]+)"', src)) \
                     | set(re.findall(r'setAttribute\(\s*"id"\s*,\s*"([^"]+)"', src))
    missing = sorted(r for r in refs if r not in idset)
    if missing: F("HIGH", p, "js-refs-missing-id", ", ".join(missing))
    # internal links that don't resolve
    for h in set(re.findall(r'href="([^"#][^"]*\.html)(?:#[^"]*)?"', src)):
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
            ctx = b.new_context(viewport={"width":w,"height":h})
            pg = ctx.new_page()
            errs=[]; cons=[]
            pg.on("pageerror", lambda e, L=errs: L.append(str(e)))
            pg.on("console", lambda m, L=cons: L.append(m.type+": "+m.text) if m.type=="error" else None)
            try:
                pg.goto("file://"+os.path.join(DOCS,p), wait_until="load", timeout=25000)
                pg.wait_for_timeout(500)
            except Exception as e:
                F("HIGH", p, "load-failed", "%s @%s: %s" % (p,label,e)); ctx.close(); continue
            for e in errs: F("HIGH", p, "js-error@"+label, e)
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
            if label=="phone":
                # tap targets under 40px that are interactive and visible
                small = pg.evaluate("""()=>{const out=[];
                  document.querySelectorAll('button,a,input,select,summary').forEach(el=>{
                    const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
                    if(s.display==='none'||s.visibility==='hidden'||r.width===0) return;
                    if(r.height<40&&r.height>0&&el.offsetParent!==null)
                      out.push((el.tagName+(el.id?'#'+el.id:'')+'.'+(el.className||'')).slice(0,46)+' h='+Math.round(r.height));});
                  return out;}""")
                if small: F("LOW", p, "tap-target<40px@phone", "%d found: %s" % (len(small), small[:5]))
            ctx.close()
    b.close()

order={"HIGH":0,"MED":1,"LOW":2}
findings.sort(key=lambda f:(order[f["sev"]], f["page"], f["kind"]))
io.open("/tmp/fe-findings.json","w",encoding="utf-8").write(json.dumps(findings,indent=1,ensure_ascii=False))
from collections import Counter
c=Counter(f["sev"] for f in findings)
print("pages swept: %d   findings: HIGH=%d MED=%d LOW=%d\n" % (len(PAGES), c["HIGH"], c["MED"], c["LOW"]))
for f in findings:
    print("[%s] %-28s %-26s %s" % (f["sev"], f["page"], f["kind"], f["detail"][:120]))
