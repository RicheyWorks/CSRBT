# -*- coding: utf-8 -*-
"""Kit-wide touch-target audit.

Every page in the kit is tested against a 44px floor for its own controls, but
each suite only tested the page it covered. This walks all of them at phone
width and reports anything interactive under 44px that a finger is expected to
hit. Checkboxes and inline text links are exempt (they are not primary targets
and 44px would wreck running prose).
"""
import glob, os, sys
from playwright.sync_api import sync_playwright

# THE PATH WAS THE POLISH LOOP'S CLONE, NOT THIS CHECKOUT (ADR-106)
#
# This read DOCS = "/tmp/eco/CSRBT/docs/" -- the directory the autonomous
# polish job clones into, which exists in exactly one container and nowhere
# else. Everywhere else glob returned [], the page loop never ran, and the
# audit printed a clean bill of health having examined ZERO pages. It has
# been green on Richmond's machine on that basis, and that green was counted
# in the kit's headline numbers.
#
# Two changes, and the second matters more than the first: the path now comes
# from this file's own location, so the audit reads the checkout it was run
# from; and finding no pages is now a LOUD FAILURE rather than a clean result,
# because the next hardcoded path will fail the same silent way and "I looked
# at nothing" must never again render as "nothing is wrong".
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs") + os.sep
pages=sorted(glob.glob(DOCS+"*.html"))
if not pages:
    print("NO PAGES FOUND under %s -- refusing to report a clean audit of nothing" % DOCS)
    sys.exit(2)
bad_total=0
rows=[]

with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":390,"height":900})
    pg.set_default_timeout(20000)
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    for path in pages:
        name=os.path.basename(path)
        errs=[]
        pg.on("pageerror", lambda e: errs.append(str(e)))
        try:
            pg.goto("file://"+path, wait_until="domcontentloaded"); pg.wait_for_timeout(700)
        except Exception as e:
            rows.append((name,"LOAD FAIL",str(e)[:60])); continue
        r=pg.evaluate("""()=>{const bad={};
          document.querySelectorAll('button,input,select,[role=button]').forEach(e=>{
            const bb=e.getBoundingClientRect();
            if(bb.width===0&&bb.height===0) return;
            if(e.type==='checkbox'||e.type==='radio') return;
            if(bb.height<44){
              const k=e.tagName.toLowerCase()+(e.className?('.'+String(e.className).split(' ')[0]):'');
              bad[k]=(bad[k]||0)+1;}});
          return bad;}""")
        n=sum(r.values())
        bad_total+=n
        rows.append((name, n, r))

    b.close()

print("%-30s %s" % ("PAGE","UNDER 44px"))
print("-"*62)
for name, n, detail in rows:
    if n==0:
        print("%-30s ok" % name)
    else:
        print("%-30s %s   %s" % (name, n, detail))
print("-"*62)
print("total under 44px across the kit:", bad_total)
sys.exit(1 if bad_total else 0)
