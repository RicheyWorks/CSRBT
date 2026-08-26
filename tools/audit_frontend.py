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
ALL_PAGES = sorted(f for f in os.listdir(DOCS) if f.endswith(".html"))
# --only limits which pages are SWEPT, not which exist: every file stays on disk
# so internal links still resolve. Re-checking one page after an edit took a full
# 37-page browser sweep before this, which is why nobody ran it that way -- and
# why the canary suite for this audit was taking nine minutes.
_only = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--only=")]
_want = set(",".join(_only).split(",")) if _only else None
PAGES = [f for f in ALL_PAGES if f in _want] if _want else ALL_PAGES
if _want and not PAGES:
    sys.exit("--only matched no page in docs/")
findings = []
ID_REFS = {}
SRC = {}
CITED = {}
ALLOWED_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com", "claude.ai", "github.com")
# Tags whose src/href the BROWSER fetches. <a href> is deliberately absent.
FETCHED = re.compile(
    r'<\s*(?P<tag>link|script|img|iframe|source|video|audio|embed|object|track|input)\b'
    r'[^>]*?\b(?:src|href|data|poster)\s*=\s*"(?P<u>https?://[^"]+)"', re.I)
def F(sev, page, kind, detail):
    findings.append({"sev":sev,"page":page,"kind":kind,"detail":detail})


def IN_SCRIPT(src, i):
    """True if index i falls inside a <script> block -- i.e. the id="X" found
    there is markup the page WRITES, not markup it ships."""
    return src.count("<script", 0, i) > src.count("</script", 0, i)

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
    # External SUBRESOURCES -- things the browser fetches on its own, which is
    # what carries the CSP and offline risk. This rule used to match any src OR
    # href, so every clickable citation in an ADR or a reference page was
    # reported as a resource: 15 of the 16 open rows, none of them a risk,
    # because a link you tap is not a request the page makes. A finder whose
    # rows are all noise trains you to skim the one that is not.
    for m in FETCHED.finditer(src):
        u = m.group("u")
        if any(k in u for k in ALLOWED_HOSTS):
            continue
        F("MED", p, "external-resource", "<%s> %s" % (m.group("tag").lower(), u))
    for m in re.finditer(r'@import\s+(?:url\()?["\']?(https?://[^"\')\s]+)', src):
        if not any(k in m.group(1) for k in ALLOWED_HOSTS):
            F("MED", p, "external-resource", "@import " + m.group(1))
    CITED[p] = sorted({u for u in re.findall(r'<a\b[^>]*?href="(https?://[^"]+)"', src)
                       if not any(k in u for k in ALLOWED_HOSTS)})
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
    # There used to be a rule here called "innerHTML-unescaped-value". It looked
    # for the substring ".value" inside a 200-character window after innerHTML=
    # and no "esc(" in that same window. It was wrong three separate ways:
    # ".value" also matches ".values", a comparison operand (x.value===y) is not
    # an interpolation, and the 200-character window truncated every multi-line
    # template so the esc() call further down was invisible. It reported three
    # findings, all false. Worse: seeding the exact ADR-031 defect -- removing
    # esc() from a real warning path -- produced ZERO findings, because these
    # pages assemble HTML into a variable with += and assign it once, so the
    # assignment expression never contains the concatenation at all.
    #
    # A rule that cannot see the defect it is named for, and whose every row is
    # noise, is not a weak check; it is an anti-check. Following the taint
    # through hand-written JS is real static analysis with a long false-positive
    # tail, and this kit already measures escaping where it is decidable: at
    # runtime, by typing markup into a page and seeing what comes back
    # (audit_escaping.py, verify_escaping_slice.py, and each page's own suite).
    #
    # What IS decidable statically is the crude case: a page that builds HTML by
    # concatenation and has no escaper anywhere in it.
    builds = re.search(r'\.innerHTML\s*(=|\+=)\s*[^;]*?["\'`]\s*\+', src) \
             or re.search(r'insertAdjacentHTML', src)
    # Detect the escaper by its SIGNATURE, not its name. The first cut of this
    # rule looked for a function literally called esc(), and reported
    # field-season -- whose escaper is called escv() and works fine. Naming a
    # helper differently is not a defect; a rule that says it is has just moved
    # the false positives somewhere new.
    has_escaper = re.search(r'replace\s*\(\s*/\[?[&<>"\'\\]+\]?/[gimsu]*', src) \
                  and "&lt;" in src and "&amp;" in src
    # A page with no free-text input has nothing for a person to inject THROUGH.
    takes_text = re.search(r'<(input[^>]*type="text"|textarea)\b', src) \
                 or re.search(r'\bFEK\.(text|note|picker)\b', src) \
                 or re.search(r'type\s*=\s*"text"', src)
    if builds and not has_escaper and takes_text:
        F("MED", p, "html-assembly-with-no-escaper",
          "page concatenates HTML from a text field and defines no escaping helper")
    elif builds and not has_escaper:
        F("LOW", p, "html-assembly-no-escaper-no-input",
          "concatenates HTML with no escaper, but has no free-text field to inject through")

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
                    if not bare:
                        continue
                    # Absent at load AND dereferenced bare -- but all eight rows
                    # this ever reported were controls the page's own script
                    # writes into markup moments before dereferencing them. That
                    # is not an unguarded reference, it is a constructor. If the
                    # script emits id="X" itself, the element exists by the time
                    # the next line runs, and the runtime js-error rows above are
                    # what would say otherwise.
                    built = re.search(
                        r'id=\\?["\']%s\\?["\']' % re.escape(i), SRC[p])
                    if built and IN_SCRIPT(SRC[p], built.start()):
                        continue
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
