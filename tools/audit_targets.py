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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_states as S

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
# verify_audit_states runs this audit on a fixture directory whose faults are
# known; the env var is that hook, and nothing else sets it.
DOCS = (os.environ.get("CSRBT_DOCS_DIR") or DOCS).rstrip(os.sep) + os.sep
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
        # ADR-130: measured in every state of the page -- each tab pressed,
        # every <details> open, the page-specific reveals -- and the controls no
        # state exposed are named and counted as faults: an unmeasured control
        # must not print as a good one. ADR-131 adds the ENTERED state: the
        # page's own science task replayed, then every tab again, so a control
        # that exists only in a built row is measured too.
        PROBE = """()=>{const bad={};
          document.querySelectorAll('button,input,select,[role=button]').forEach(e=>{
            const bb=e.getBoundingClientRect();
            if(bb.width===0&&bb.height===0) return;
            if(e.type==='checkbox'||e.type==='radio') return;
            if(bb.height<44){
              const k=e.tagName.toLowerCase()+(e.className?('.'+String(e.className).split(' ')[0]):'')+'@'+(e.getAttribute('data-audit')||'');
              bad[k]=1;}});
          return bad;}"""
        merged={}; nstates=0
        for state, r in S.each_state(pg, name, lambda: pg.evaluate(PROBE)):
            nstates+=1
            for k in r: merged.setdefault(k, state)
        r={}
        for k, state in merged.items():
            kk=k.split('@')[0]; r[kk]=r.get(kk,0)+1
        cov=S.coverage(pg)
        ent=getattr(pg,"_audit_entered",None)
        efault=S.entry_fault(ent)
        n=sum(r.values())+len(cov["never"])+(1 if efault else 0)
        if efault: r["ENTRY NOT REACHED"]=efault
        bad_total+=n
        if cov["never"]: r["NEVER EXPOSED in %d states"%nstates]=cov["never"][:8]
        # ADR-143: a look that found what an earlier look had missed is
        # contention, and it is printed rather than absorbed -- a page that
        # needed the second or third look is a page whose measurement depended
        # on what else the machine was doing.
        late=cov.get("lateLooks") or []
        if len(late)>1 and sum(late[1:]): r["LATE (found on look %d)"%(1+max(i for i,v in enumerate(late) if v))]=sum(late[1:])
        rows.append((name, n, r, nstates, cov, ent))

    b.close()

print("%-30s %s" % ("PAGE","UNDER 44px (every state; controls no state exposed count too)"))
print("-"*62)
for row in rows:
    if len(row) == 3:
        print("%-30s %s %s" % row); continue
    name, n, detail, nstates, cov, ent = row
    # ADR-131: what the entry did, so "audited entered" is a fact on the row
    tail = ("" if ent is None else
            "   entry %s %d/%d driven%s" % (ent["task"], ent["driven"], ent["steps"],
                                            (" -- " + ent["error"]) if ent.get("error") else
                                            (", %d refused" % ent["refused"] if ent["refused"] else "")))
    if n==0:
        print("%-30s ok   %d states, %d/%d controls measured%s" % (name, nstates, cov["exposed"], cov["exist"], tail))
    else:
        print("%-30s %s   %s   (%d states, %d/%d measured)%s" % (name, n, detail, nstates, cov["exposed"], cov["exist"], tail))
print("-"*62)
print("total under 44px or never measured across the kit:", bad_total)
sys.exit(1 if bad_total else 0)
