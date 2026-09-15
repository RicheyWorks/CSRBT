# -*- coding: utf-8 -*-
"""The outbox: what has not left this device, and whether the page can be trusted about it.

ADR-203. KEEP answers "will this survive the tab closing". Nothing in this kit
answered "is any of it anywhere else", which is the question a reader with a few
minutes of satellite actually has.

A ledger about data safety is the most dangerous thing this kit can build,
because a wrong one is read as reassurance. So the checks here are written
against the three ways it would be wrong rather than against the happy path:

  1. IT MARKS ON SUCCESS, NEVER ON CLICK. A copy the browser refused must leave
     the export listed as pending. Checked by making the clipboard fail.
  2. IT IS PER EXPORT. Copying the CSV must not make the Darwin Core look sent.
  3. AN EXPORT IT DOES NOT KNOW IS AN ERROR. A mis-wired call site must turn the
     line red and name the string, not shrug.

And one oracle underneath all of it: the checksum. The page's UTF-8 encoder and
CRC-32 are checked against Python's `str.encode` and `zlib.crc32` on a corpus
that includes an accent, an em dash and a surrogate pair -- because a hash that
is merely self-consistent would report "unchanged" on a sheet that had changed
and nothing else in this kit would notice.
"""
import importlib.util, io, json, os, re, sys, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import url, offline, ROOT, TOOLS_DIR
from playwright.sync_api import sync_playwright

P, F = [], []
def ck(n, c, e=""):
    (P if c else F).append(n + (("  << " + str(e)) if (e and not c) else ""))


def ver(mod):
    src = io.open(os.path.join(TOOLS_DIR, mod), encoding="utf-8").read()
    m = re.search(r'^VERSION\s*=\s*"([\d.]+)"', src, re.M)
    return m.group(1) if m else None


OUTV, KEEPV = ver("outbox.py"), ver("keep.py")
OUT_SRC = io.open(os.path.join(TOOLS_DIR, "outbox.py"), encoding="utf-8").read()

# THE CONSUMER LIST IS THE EMITTER'S (ADR-206, by ADR-204's rule).
#
# It was eight names written here, and ADR-206 wired four more pages. A list
# only one reader reads is the defect ADR-141 named and ADR-204 found again in
# verify_keep; writing it a third time here would have been the third instance.
_oespec = importlib.util.spec_from_file_location(
    "outbox_emit", os.path.join(TOOLS_DIR, "outbox_emit.py"))
_oe = importlib.util.module_from_spec(_oespec)
_oespec.loader.exec_module(_oe)
CONSUMERS = list(_oe.CONSUMERS)

# READ OFF THE PAGES, NOT OFF A COUNT (ADR-207). A count is walked straight past
# by a list that has lost a page; what the claim is about is COVERAGE.
import glob as _glob
_inlined = sorted(os.path.basename(_p) for _p in
                  _glob.glob(os.path.join(ROOT, "docs", "*.html"))
                  if "/* ---- Outbox v" in io.open(_p, encoding="utf-8").read())
ck("EVERY PAGE THAT CARRIES THE OUTBOX IS A PAGE THIS SUITE DRIVES, because the list is the "
   "emitter's rather than a second one kept here: %s"
   % sorted(set(_inlined) - set(CONSUMERS)),
   sorted(CONSUMERS) == _inlined, (sorted(CONSUMERS), _inlined))

ck("tools/outbox.py declares a version", bool(OUTV), OUTV)
ck("KEEP is at the version that exposes its snapshot, which the outbox reads",
   KEEPV and KEEPV >= "1.1.0", KEEPV)


# ------------------------------------------------------------------ the wiring
#
# Read off the pages, not off a list kept here: a page that gains an export
# tomorrow has to be covered on the day it gains it, not on the day somebody
# remembers this file exists.
# THE LEDGER IS MARKED FROM TWO PLACES, AND THIS READ ONE OF THEM (ADR-208).
#
# Every mark used to go through a page's own `copyText(...)`, so reading the
# last argument of those calls read every export a page could make. A DOWNLOAD
# cannot: there is no clipboard promise to hang the mark on, so the page calls
# `SENT.sent("id", bytes)` itself in the path where the bytes went. Both benches
# grew one in this slice and both were reported as declaring an export no call
# site could make -- the rule enforced over one of the two shapes the thing it
# measures actually has, which is ADR-141's defect for the sixth time.
#
# The component's own `LIVE.sent(id, bytes)` inside tools/outbox.py is not a
# call site: `id` there is the parameter being forwarded, and it is excluded by
# being a non-literal rather than by naming the file, so a page that wrote the
# same forwarding line would be named too.
SENT_CALL = re.compile(r"\.sent\(\s*([^,)]+)")


def sent_ids(src):
    out = []
    for m in SENT_CALL.finditer(src):
        arg = m.group(1).strip()
        mm = re.fullmatch(r'"([a-z]+)"', arg)
        if mm:
            out.append(mm.group(1))
        elif arg != "id":          # the component forwarding its own parameter
            out.append("NOT A LITERAL: " + arg[:40])
    return out


def call_ids(src):
    """The last argument of every copyText(...) CALL, plus every .sent("id").

    Parsed by balancing parentheses rather than by regex, because the argument
    lists span lines and hold both quote characters, commas inside strings and
    nested calls. A call whose last argument is not a plain string literal comes
    back as the raw text so the check can name it.
    """
    out = list(sent_ids(src))
    for m in re.finditer(r"copyText\(", src):
        if src[:m.start()].rstrip().endswith("function"):
            continue
        i, d = m.end(), 1
        while d and i < len(src):
            c = src[i]
            if c == "(":
                d += 1
            elif c == ")":
                d -= 1
            elif c in "\"'":
                q = c
                i += 1
                while i < len(src) and src[i] != q:
                    if src[i] == "\\":
                        i += 1
                    i += 1
            i += 1
        last = src[m.end():i - 1].rsplit(",", 1)[-1].strip()
        mm = re.fullmatch(r'"([a-z]+)"', last)
        out.append(mm.group(1) if mm else "NOT A LITERAL: " + last[:40])
    return out


def decl_ids(src):
    return re.findall(r'\{ id:"([a-z]+)", label:"', src)


# THE READER ITSELF, over a source written here (ADR-208).
#
# No page in this kit marks the ledger anywhere but through `copyText`, and the
# two downloads this slice added deliberately do NOT mark it -- a hosted viewer
# can refuse a page-started download in silence, so a mark there would report a
# sheet as gone from this device that the browser never let leave. So the second
# half of the reader has no violator in the kit, and a check run only over the
# pages would pass just as well if it had never been written. It is driven here
# instead, which is ADR-207's answer to exactly that: over a source with both
# shapes in it, and over the component's own forwarding line.
_both = 'copyText(sheetText(), "Copied", "sheet"); if(ok) SENT.sent("csvv", n);'
ck("THE LEDGER IS MARKED FROM TWO PLACES and the reader reads both: a copy through the page's own "
   "copyText, and a call site that marks an export copyText cannot carry",
   sorted(call_ids(_both)) == ["csvv", "sheet"], sorted(call_ids(_both)))
ck("and the component forwarding its OWN parameter is not a call site -- excluded by being a "
   "non-literal rather than by naming the file, so a page that wrote the same line would be named",
   call_ids("return LIVE.sent(id, bytes);") == [], call_ids("return LIVE.sent(id, bytes);"))
ck("...while a mark whose id is worked out at run time IS named, rather than passing as nothing",
   [x for x in call_ids('OUT.sent(which, n);') if x.startswith("NOT A LITERAL")],
   call_ids('OUT.sent(which, n);'))

for name in CONSUMERS:
    src = io.open(os.path.join(ROOT, "docs", name), encoding="utf-8").read()
    decl, used = decl_ids(src), call_ids(src)
    # ONE IS ENOUGH. The bar was two, which is a claim about how many exports a
    # page ought to have rather than about the ledger; the carnivorous-plant
    # bench makes exactly one copy and its outbox is no less true for it.
    ck("%s declares its exports" % name, len(decl) >= 1, decl)
    ck("%s declares each export once" % name, len(decl) == len(set(decl)), decl)
    bad = [u for u in used if u.startswith("NOT A LITERAL")]
    ck("%s: every copy this sheet makes names the export it is" % name, not bad, bad[:2])
    undeclared = sorted(set(u for u in used if not u.startswith("NOT A")) - set(decl))
    ck("EVERY COPY %s CAN MAKE IS IN ITS OUTBOX. A call site naming an export the ledger does not "
       "know hands bytes out that nothing records -- the ledger then reports a sheet as fully sent "
       "while an export of it is walking around unlisted" % name,
       not undeclared, undeclared)
    unused = sorted(set(decl) - set(u for u in used if not u.startswith("NOT A")))
    ck("and every export %s declares can actually be made. A declared id no call site passes is an "
       "entry that can never stop being pending, which trains the reader to ignore the list" % name,
       not unused, unused)
    ck("%s hooks the ledger exactly once, in one copy helper" % name,
       src.count("OUT.sent(") == 1, src.count("OUT.sent("))
    ck("%s's copy helper takes the export it is copying" % name,
       re.search(r"function copyText\(\w+,\s*\w+,\s*id\)", src) is not None, "")
    ck("%s mounts the outbox next to the autosave strip" % name,
       src.count('<div id="sendBox"></div>') == 1, src.count('<div id="sendBox"></div>'))

# ---- one hash for the kit -------------------------------------------------
ck("THE OUTBOX HAS NO CHECKSUM OF ITS OWN. It borrows FEK's, because a sheet whose photographs and "
   "whose outbox disagreed about what a byte string hashes to is a sheet nobody can reconcile -- and "
   "a second table here would drift with nothing comparing them",
   "FEK.crc32" in OUT_SRC and "CRCT" not in OUT_SRC, "")
ck("and it REFUSES rather than falling back when FEK is not there. A fallback hash would agree with "
   "nothing, so `unchanged` would mean `hashed with something else`",
   "return null" in OUT_SRC.split("function hash(o)")[1][:200], "")

CORPUS = ["", "plain", "Relevé — plot 3", "a,b\nc", "\U0001F4F7 frame",
          "åäö 中文", '{"a":1}']

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context()

    def page(name, clear=False):
        """Open a consumer. `clear` wipes the origin's storage FIRST.

        Every docs page shares one file:// origin, so a section that filled a
        sheet and marked its exports leaves both the autosave and the ledger
        behind for the next one -- which reads as "pending 0" and passes a check
        that was never exercised. Loading blank, clearing, and reloading is the
        only order that starts from nothing.
        """
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        offline(pg)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(url(name), wait_until="domcontentloaded")
        if clear:
            pg.evaluate("()=>{try{localStorage.clear();}catch(e){}}")
            del errs[:]
            pg.reload(wait_until="domcontentloaded")
        pg.wait_for_timeout(900)
        return pg, errs

    # ------------------------------------------ every consumer carries it
    for name in CONSUMERS:
        pg, errs = page(name)
        ck("%s loads clean with the outbox on it" % name, not errs, errs[:2])
        ck("%s carries OUT at the emitted version" % name,
           pg.evaluate("()=>typeof OUT!=='undefined' && OUT.version") == OUTV,
           pg.evaluate("()=>typeof OUT==='undefined'?'absent':OUT.version"))
        ck("%s mounts the outbox" % name,
           pg.eval_on_selector_all("#sendBox.outbox", "e=>e.length") == 1, "")
        ck("%s says what the outbox is NOT -- a ledger, not a transport. A page opened from a card "
           "cannot send anything, and a status strip that let a reader believe otherwise would be "
           "the worst lie in the kit" % name,
           "not a transport" in pg.inner_text("#sendBox"), pg.inner_text("#sendBox")[:70])
        ck("%s's outbox line is a live region, so ADR-199's channel carries it with no new "
           "protocol: the thing that changes when an export lands is announced" % name,
           pg.eval_on_selector_all('#sendBox p.st[role=status][aria-live=polite]', "e=>e.length") == 1,
           "")
        ck("%s reads its state through KEEP's snapshot and not a second description of the page"
           % name,
           pg.evaluate("()=>{var s=OUT.status(); return !!s && (s.empty || s.crc!==null);}"), "")
        pg.close()

    # ------------------------------------------ the oracle
    pg, _ = page("releve.html")
    for s in CORPUS:
        got = pg.evaluate("(s)=>OUT.utf8(s)", s)
        want = list(s.encode("utf-8"))
        ck("the page's UTF-8 encoder agrees with Python's on %r" % (s[:14],), got == want,
           "%s vs %s" % (got[:8], want[:8]))
    for s in CORPUS:
        got = pg.evaluate("(s)=>FEK.crc32(OUT.utf8(s))", s)
        want = "%08x" % zlib.crc32(s.encode("utf-8"))
        ck("THE CHECKSUM IS THE ONE PYTHON COMPUTES for %r. Everything the outbox claims rests on "
           "this: a hash that were merely self-consistent would report `unchanged` on a sheet that "
           "had changed, and nothing else in the kit would notice" % (s[:14],),
           got == want, "%s vs %s" % (got, want))
    both = pg.evaluate("""()=>{var o={a:1,b:"x \\u2014 y"};
        return [OUT.hash(o), FEK.crc32(OUT.utf8(JSON.stringify(o)))];}""")
    ck("and hash() is that same checksum over the state's JSON", both[0] == both[1], both)

    # FEK gone -> refuse, loudly, rather than report clean.
    pg.evaluate("()=>{ window.__c = FEK.crc32; FEK.crc32 = null; }")
    ck("with the kit's checksum gone the outbox REFUSES: it reports unreadable rather than "
       "reporting a sheet unchanged because it could not tell",
       pg.evaluate("()=>OUT.hash({a:1})") is None, "")
    pg.evaluate("()=>{ FEK.crc32 = window.__c; }")
    pg.close()

    # ------------------------------------------ it counts per export
    def fill_releve(pg):
        pg.click('.tab[data-pane="p-plot"]'); pg.wait_for_timeout(250)
        for k, v in [("sPlot", "OUT-01"), ("sObs", "R. Test"), ("sComm", "fen")]:
            pg.evaluate("""([i,v])=>{var e=document.getElementById(i); e.value=v;
              e.dispatchEvent(new Event('input',{bubbles:true}));
              e.dispatchEvent(new Event('change',{bubbles:true}));}""", [k, v])
        pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(250)
        pg.fill("#rFree", "Carex aquatilis")
        pg.evaluate("""()=>{const d=document.querySelector('#rCov .fek-dial')||document.querySelector('#rCov');
          [...d.querySelectorAll('button')][2].click();}""")
        pg.wait_for_timeout(200)
        pg.click("#rAdd"); pg.wait_for_timeout(900)

    def st(pg):
        return pg.evaluate("()=>OUT.status()")

    def show(pg, elid):
        """Bring the pane holding an element to the front.

        The exports live on a different tab in each consumer, and naming the
        tab here would be one more list to keep in step with the pages.
        """
        pane = pg.evaluate("""(i)=>{var e=document.getElementById(i);
            var p=e&&e.closest&&e.closest('section.pane'); return p?p.id:null;}""", elid)
        if pane:
            pg.evaluate("""(p)=>{var t=document.querySelector('.tab[data-pane="'+p+'"]');
                if(t) t.click();}""", pane)
            pg.wait_for_timeout(300)

    pg, errs = page("releve.html", clear=True)
    s0 = st(pg)
    ck("a sheet nobody has typed on has nothing to send",
       s0["empty"] is True and s0["pending"] == 0, {k: s0[k] for k in ("empty", "pending")})
    fill_releve(pg)
    pg.wait_for_timeout(700)
    s1 = st(pg)
    carry = [r["id"] for r in s1["carry"]]
    ck("once there is something on the sheet, EVERY export that carries it is pending and named",
       s1["pending"] == len(carry) and set(r["id"] for r in s1["never"]) == set(carry),
       {"pending": s1["pending"], "carry": carry})
    ck("and the AI prompt and the species pack are not among them -- declared, so no call site can "
       "hand out bytes unlisted, and never counted, because an outbox that nagged about re-copying "
       "a prompt is an outbox nobody reads",
       "prompt" not in carry and "pack" not in carry
       and set(r["id"] for r in s1["rows"]) >= {"prompt", "pack"}, carry)
    ck("the strip says so in words, in the live region",
       "have not left this device" in pg.inner_text("#sendBox"), pg.inner_text("#sendBox")[:90])

    # one export leaves
    pg.evaluate("()=>{ window.__copied=null;"
                " navigator.clipboard.writeText = function(t){ window.__copied=t;"
                "   return Promise.resolve(); }; }")
    show(pg, "csvCopy")
    pg.click("#csvCopy"); pg.wait_for_timeout(700)
    s2 = st(pg)
    ck("copying one export marks THAT ONE and no other. A ledger with one stamp for the sheet would "
       "go quiet about the Darwin Core the moment the CSV was copied, which is the direction that "
       "loses data",
       s2["pending"] == s1["pending"] - 1
       and [r["id"] for r in s2["rows"] if r["id"] == "csv"][0] == "csv"
       and [r["sent"] for r in s2["rows"] if r["id"] == "csv"] == [True]
       and [r["sent"] for r in s2["rows"] if r["id"] == "dwc"] == [False],
       {"was": s1["pending"], "now": s2["pending"]})
    ck("and it recorded how much left, not just that something did",
       [r["bytes"] for r in s2["rows"] if r["id"] == "csv"][0] > 20,
       [r["bytes"] for r in s2["rows"] if r["id"] == "csv"])

    # the sheet changes underneath it
    pg.click('.tab[data-pane="p-rec"]'); pg.wait_for_timeout(250)
    pg.fill("#rFree", "Menyanthes trifoliata")
    pg.evaluate("""()=>{const d=document.querySelector('#rCov .fek-dial')||document.querySelector('#rCov');
      [...d.querySelectorAll('button')][1].click();}""")
    pg.click("#rAdd"); pg.wait_for_timeout(900)
    s3 = st(pg)
    ck("A RECORD ADDED AFTER AN EXPORT MAKES THAT EXPORT STALE, and the strip says which one and "
       "since when -- not `saved`, which is the question the page was already answering",
       [r["stale"] for r in s3["rows"] if r["id"] == "csv"] == [True]
       and s3["pending"] == s1["pending"], s3["pending"])
    ck("and the reason is spelled out rather than left as a count",
       "changed since" in pg.inner_text("#sendBox"), pg.inner_text("#sendBox")[:120])

    # everything leaves
    for i in [r["id"] for r in s3["carry"]]:
        pg.evaluate("(i)=>OUT.sent(i, 1)", i)
    pg.wait_for_timeout(200)
    s4 = st(pg)
    ck("when everything has gone, the strip says so plainly instead of staying silent",
       s4["pending"] == 0 and "Everything here has left this device" in pg.inner_text("#sendBox"),
       pg.inner_text("#sendBox")[:80])

    # an export the sheet does not declare
    pg.evaluate("()=>OUT.sent('nosuchthing', 10)")
    pg.wait_for_timeout(100)
    txt = pg.inner_text("#sendBox")
    ck("AN EXPORT THE LEDGER DOES NOT KNOW IS AN ERROR, NOT A SHRUG -- and it names the string. "
       "This is what makes a mis-wired call site loud, which is the failure ADR-201 found the hard "
       "way when a typeof guard hid a wrong function name for a season",
       "does not declare" in txt and "nosuchthing" in txt, txt[:120])
    ck("and the strip goes red, so it is not read as a detail",
       "bad" in pg.get_attribute("#sendBox", "class"), pg.get_attribute("#sendBox", "class"))
    ck("the page did not throw doing it", not errs, errs[:2])
    pg.close()

    # ------------------------------------------ the mark follows the clipboard
    pg, errs = page("releve.html", clear=True)
    fill_releve(pg)
    pg.wait_for_timeout(600)
    before = st(pg)["pending"]
    pg.evaluate("""()=>{ navigator.clipboard.writeText = function(){
        return Promise.reject(new Error('denied')); };
      document.execCommand = function(){ return false; };
      window.__fail = true; }""")
    show(pg, "csvCopy")
    pg.click("#csvCopy"); pg.wait_for_timeout(900)
    after = st(pg)
    ck("A COPY THE BROWSER REFUSED IS NOT A COPY. The mark lives in the clipboard's resolve path, "
       "not the button's listener -- a ledger that stamped on the click would tell a reader their "
       "morning is safe when it is on no device but this one",
       after["pending"] == before
       and [r["sent"] for r in after["rows"] if r["id"] == "csv"] == [False],
       {"before": before, "after": after["pending"]})
    pg.close()

    # ------------------------------------------ and on EVERY page, not just this one
    #
    # The releve check above found the fault; a check written only there would
    # have left it standing on four other sheets. execCommand reports failure by
    # RETURNING FALSE and throws in only some of the ways it can fail, so a
    # fallback that ignores the return value toasts "Copied" over a copy that
    # never happened -- and the ledger then records it as gone. Every consumer,
    # driven through a real button, with both clipboard paths refusing.
    REFUSE = [("ordination.html",       "demo1",  "copyCoord", "coords"),
              ("releve.html",           None,     "ecoCopy",   "sheet"),
              ("stand-sheet.html",      None,     "ecoCopy",   "sheet"),
              ("collection-sheet.html", None,     "ecoCopy",   "sheet"),
              ("pheno-tracker.html",    None,     "ecoCopy",   "sheet"),
              ("deployment-log.html",   None,     "ecoCopy",   "sheet"),
              ("survey-design.html",    None,     "cpRead",    "readme"),
              ("greenhouse.html",       None,     "ghCopy",    "summary"),
              # ADR-206. The execCommand fault ADR-203 fixed on five pages was
              # alive on four more, because the check was written over the
              # pages that had an OUTBOX rather than over the pages that have a
              # CLIPBOARD. Every consumer, and the list is the emitter's.
              ("ethogram.html",         None,     "ecoCopy",   "sheet"),
              ("field-notebook.html",   None,     "ecoCopy",   "sheet"),
              ("selection-log.html",    None,     "ecoCopy",   "sheet"),
              ("farm-scout.html",       None,     "ecoCopy",   "sheet"),
              # ADR-207: the benches, which ADR-205 gave exports and this slice
              # gave a ledger.
              ("cell-bench.html",       None,     "ecoCopy",   "sheet"),
              ("micro-bench.html",      None,     "ecoCopy",   "sheet"),
              ("cp-bench.html",         None,     "mCopy",     "recipe"),
              # ADR-208: the data trap. Eighteen typed values, no export at all,
              # and an audit that missed it because the one control it did press
              # was a number box whose caption says "save".
              ("breeding-bench.html",   "tDemo",  "bCopy",     "sheet")]
    ck("EVERY CONSUMER IS DRIVEN THROUGH A REAL EXPORT BUTTON, not a representative. The "
       "execCommand fault this checks for was fixed on five pages by ADR-203 and was still alive "
       "on four more, because that check was written over the pages that had an outbox rather "
       "than over the pages that have a clipboard",
       sorted(x[0] for x in REFUSE) == sorted(CONSUMERS),
       sorted(set(CONSUMERS) - set(x[0] for x in REFUSE)))
    STUB_OK = """()=>{ window.__hits=0;
        navigator.clipboard.writeText = function(){ window.__hits++; return Promise.resolve(); };
        document.execCommand = function(){ window.__hits++; return true; }; }"""
    STUB_NO = """()=>{ window.__hits=0;
        navigator.clipboard.writeText = function(){ window.__hits++;
          return Promise.reject(new Error('denied')); };
        document.execCommand = function(){ window.__hits++; return false; }; }"""

    def sent_flag(pg, eid):
        return pg.evaluate("""(i)=>{var r=OUT.status().rows.filter(function(x){return x.id===i;});
            return r.length ? r[0].sent : "no such export";}""", eid)

    for name, prep, btn, eid in REFUSE:
        # first: the copy SUCCEEDS, so the check below is not passing for the
        # boring reason that this button never copies anything at all.
        pg, errs = page(name, clear=True)
        if prep:
            show(pg, prep)       # ADR-208: a worked example can live behind a tab too
            pg.click("#" + prep); pg.wait_for_timeout(700)
        # A PRESS THAT REFUSES IS NOT A COPY EITHER. Some exports decline on an
        # empty sheet ("Empty mix"), which would make both halves of this pair
        # pass for the wrong reason; the page's own preset gives them something
        # to hand over.
        if name == "cp-bench.html":
            pg.evaluate("""()=>{var b=document.querySelector('#mPresets button');
                if(b) b.click();}""")
            pg.wait_for_timeout(400)
        pg.evaluate(STUB_OK)
        show(pg, btn)
        pg.click("#" + btn); pg.wait_for_timeout(700)
        ck("%s: a copy the browser ACCEPTS is recorded (otherwise the refusal check below would "
           "pass for the wrong reason)" % name,
           sent_flag(pg, eid) is True and pg.evaluate("()=>window.__hits") > 0,
           {"sent": sent_flag(pg, eid), "hits": pg.evaluate("()=>window.__hits")})
        pg.close()

        pg, errs = page(name, clear=True)
        if prep:
            show(pg, prep)
            pg.click("#" + prep); pg.wait_for_timeout(700)
        if name == "cp-bench.html":
            pg.evaluate("""()=>{var b=document.querySelector('#mPresets button');
                if(b) b.click();}""")
            pg.wait_for_timeout(400)
        pg.evaluate(STUB_NO)
        show(pg, btn)
        pg.click("#" + btn); pg.wait_for_timeout(900)
        ck("%s: AND A COPY IT REFUSES IS NOT. execCommand says no by returning false, not by "
           "throwing -- a fallback that ignores the return value marks an export as gone that is "
           "still only on this device" % name,
           sent_flag(pg, eid) is False, sent_flag(pg, eid))
        ck("%s: and the toast does not claim it copied either. The wrong toast is forgotten in a "
           "second; it is the same bug" % name,
           "opied" not in pg.inner_text("#toast"), pg.inner_text("#toast")[:60])
        ck("%s raised nothing while refusing" % name, not errs, errs[:2])
        pg.close()

    # ------------------------------------------ it survives the tab closing
    pg, _ = page("releve.html", clear=True)
    fill_releve(pg)
    pg.wait_for_timeout(700)
    pg.evaluate("()=>OUT.sent('csv', 123)")
    pg.wait_for_timeout(200)
    raw = pg.evaluate("()=>localStorage.getItem('csrbtReleveOut')")
    ck("the ledger is written down", raw and '"csv"' in raw, (raw or "")[:70])
    ck("with a format stamp, so a ledger this page can no longer read is dropped rather than "
       "misread", '"format":1' in (raw or ""), (raw or "")[:50])
    pg.close()

    pg, errs = page("releve.html")
    pg.wait_for_timeout(600)
    s5 = st(pg)
    ck("and it is still there after the tab closed and the sheet came back",
       [r["sent"] for r in s5["rows"] if r["id"] == "csv"] == [True],
       [r for r in s5["rows"] if r["id"] == "csv"])
    ck("THE RESTORED SHEET HASHES THE SAME AS THE ONE THAT WAS EXPORTED. If a restore did not "
       "round-trip exactly, every export would read as stale the moment the tab reopened, and a "
       "strip that cries wolf on every reload is a strip that is never read",
       [r["stale"] for r in s5["rows"] if r["id"] == "csv"] == [False],
       [r for r in s5["rows"] if r["id"] == "csv"])

    # A RESTORED SHEET IS ENTIRELY OUTSTANDING.
    # The baseline that stops a blank sheet nagging must NOT be taken after a
    # restore: a morning's work that came back from the autosave has been on
    # exactly one device, and a strip that greeted it with "nothing on this
    # sheet yet" would be the most expensive sentence in the kit.
    pg.evaluate("()=>{try{localStorage.removeItem('csrbtReleveOut');}catch(e){}}")
    pg.close()
    pg, _ = page("releve.html")
    pg.wait_for_timeout(700)
    s6 = st(pg)
    ck("A SHEET THE AUTOSAVE BROUGHT BACK IS ENTIRELY OUTSTANDING. It has been on one device and "
       "nowhere else, and the baseline that keeps a blank sheet quiet must not be read off it",
       s6["empty"] is False and s6["pending"] == len(s6["carry"]),
       {"empty": s6["empty"], "pending": s6["pending"], "carry": len(s6["carry"])})
    pg.close()

    # ---- storage that fails mid-session -----------------------------------
    pg, _ = page("releve.html", clear=True)
    fill_releve(pg)
    pg.wait_for_timeout(600)
    pg.evaluate("""()=>{ localStorage.setItem = function(){
        var e = new Error('full'); e.name = 'QuotaExceededError'; throw e; }; }""")
    pg.evaluate("()=>OUT.sent('csv', 10)")
    pg.wait_for_timeout(200)
    txt = pg.inner_text("#sendBox")
    ck("A LEDGER THAT CANNOT BE WRITTEN DOWN SAYS SO. A full quota that failed silently would leave "
       "a reader trusting a list that goes when the tab does -- the exact failure KEEP was built to "
       "refuse, one component along",
       "storage is full" in txt and "bad" in pg.get_attribute("#sendBox", "class"), txt[:110])
    pg.evaluate("()=>{try{localStorage.clear();}catch(e){}}")
    pg.close()

    pg, _ = page("releve.html", clear=True)
    # a ledger entry for an export this sheet no longer has
    pg.evaluate("""()=>localStorage.setItem('csrbtReleveOut', JSON.stringify(
        {format:1, sends:{ csv:{crc:"deadbeef",at:1,bytes:1}, gone:{crc:"x",at:1,bytes:1} }}))""")
    pg.close()
    pg, _ = page("releve.html")
    pg.wait_for_timeout(500)
    ids = [r["id"] for r in st(pg)["rows"]]
    ck("an export the sheet no longer has does not appear in what the strip reports",
       "gone" not in ids, ids)
    # ...and it is not carried forward in what is written back either. Reading it
    # and not showing it would leave the stamp in the file for ever, so a sheet
    # that renamed an export in one release and put the name back in another
    # would inherit a claim to have exported something it never exported.
    pg.evaluate("()=>OUT.sent('csv', 7)")
    pg.wait_for_timeout(200)
    kept = pg.evaluate("()=>localStorage.getItem('csrbtReleveOut')") or ""
    ck("A STAMP FOR AN EXPORT THE SHEET NO LONGER HAS IS DROPPED, not carried forward in the file "
       "claiming a copy of something that no longer exists",
       '"gone"' not in kept and '"csv"' in kept, kept[:90])
    pg.evaluate("()=>localStorage.clear()")
    pg.close()

    # ------------------------------------------ no storage at all
    ctx2 = b.new_context()
    pg = ctx2.new_page()
    pg.set_default_timeout(20000)
    offline(pg)
    pg.add_init_script("""Object.defineProperty(window,'localStorage',{get:function(){
        throw new Error('denied'); }});""")
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url("releve.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(900)
    ck("a browser that refuses storage does not break the page", not errs, errs[:2])
    ck("and the outbox says the list starts again when the tab closes, rather than implying it is "
       "kept", "starts again when the tab closes" in pg.inner_text("#sendBox"),
       pg.inner_text("#sendBox")[:110])
    fill_releve(pg)
    pg.wait_for_timeout(700)
    ck("it still tracks within the session, which is the part it can honestly do",
       st(pg)["pending"] > 0, st(pg)["pending"])
    pg.close()
    ctx2.close()

    b.close()

for x in F:
    print("FAIL:", x)
print("PASS", len(P))
print("---")
print("%d/%d" % (len(P), len(P) + len(F)))
raise SystemExit(1 if F else 0)
