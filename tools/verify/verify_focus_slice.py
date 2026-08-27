# Functional guard for the accessible-name slice: the labels must be real AND
# the controls they name must still work.
from playwright.sync_api import sync_playwright
import os as _os
# The kit is checked out wherever the user keeps it; these suites used to hard-code
# a container path and so could only ever run in the container that wrote them.
ROOT = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
DOCS_DIR = _os.path.join(ROOT, "docs") + _os.sep
def _u(name):
    """file:// URL for a page in docs/, whatever the checkout is called."""
    return "file://" + _os.path.join(ROOT, "docs", name).replace(_os.sep, "/")

P=F=0
def ck(c,m):
    global P,F
    if c: P+=1
    else: F+=1; print("FAIL:",m)

with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1100,"height":900})
    pg.route("**://fonts.googleapis.com/**", lambda r:r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r:r.abort())

    # ---------- ecology-lab ----------
    pg.goto(_u("ecology-lab.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(900)

    lbls=pg.eval_on_selector_all(".fe-add input[type=number]","es=>es.map(e=>e.getAttribute('aria-label'))")
    ck(lbls==["count","site A count","site B count"], "count aria-labels distinct and ordered: %r"%(lbls,))
    names=pg.eval_on_selector_all(".fe-add input[type=text]","es=>es.map(e=>e.getAttribute('aria-label'))")
    ck(names==["add a species (e.g. robin)","site A species","site B species"], "name aria-labels mirror placeholders: %r"%(names,))
    ck(pg.eval_on_selector_all(".fe-add input[type=text]","es=>es.every(e=>e.getAttribute('aria-label')===e.placeholder)"),
       "aria-label equals placeholder on every name box")

    # the add row still adds — the labels must not have broken the template
    W=".fe-wrap:nth-of-type(1)"
    before=pg.eval_on_selector_all(W+" .fe-chip","e=>e.length")
    pg.fill(W+" .fe-add input[type=text]","kestrel")
    pg.fill(W+" .fe-add input[type=number]","7")
    pg.click(W+" .fe-addbtn"); pg.wait_for_timeout(500)
    after=pg.eval_on_selector_all(W+" .fe-chip","e=>e.length")
    ck(after==before+1, "add button still adds a chip (%d -> %d)"%(before,after))
    txt=pg.eval_on_selector_all(W+" .fe-chip",
        "es=>(es.map(e=>e.textContent).find(t=>t.indexOf('kestrel')>-1)||'NOT FOUND')")
    ck("kestrel" in txt and "7" in txt, "the new chip carries the typed name and count: %r"%txt)
    # and the chip UI still mirrors back into the hidden textarea it shadows
    mirrored=pg.eval_on_selector("#wb-field","e=>e.value")
    ck("kestrel 7" in mirrored, "new chip mirrored into the wb-field textarea: %r"%mirrored[-40:])

    for tid,lab in [("wb-decklist","drill list - one card per line"),
                    ("wb-eco-out",".eco lines built from your entries")]:
        got=pg.get_attribute("#"+tid,"aria-label")
        ck(got==lab, "%s aria-label == %r (got %r)"%(tid,lab,got))
    ck(pg.eval_on_selector("#wb-eco-out","e=>e.readOnly"), "wb-eco-out stays read-only")

    # ---------- the paste path (ADR-077) ----------
    # "edit as text (paste from a spreadsheet)" is how anyone with real data gets it
    # into this page. Everything above drives the ADD ROW; nothing drove the textarea,
    # so chipify's parse() -- comments, blanks, bare names, bare numbers, duplicate
    # accumulation -- had no test at all. One paste exercises every branch of it.
    pg.eval_on_selector("#wb-field", "e=>e.closest('details.fe-raw').open=true")
    pg.wait_for_timeout(150)
    PASTE = ("# quadrat A notes\n"      # comment-only line: dropped whole
             "\n"                        # blank line: dropped
             "robin, 4\n"                # comma separator
             "wren 2\n"                  # space separator
             "sparrow\n"                 # bare name: counts as one
             "12\n"                      # bare number: NOT a species
             "oak 3 # the big one\n"     # trailing comment stripped off a data line
             "robin 1\n")                # duplicate name accumulates
    pg.fill("#wb-field", PASTE); pg.wait_for_timeout(400)
    chips = pg.eval_on_selector("#wb-field", """e=>{
        var w = e.closest('details.fe-raw').previousElementSibling;
        return [...w.querySelectorAll('.fe-chip')].map(c=>[
            c.querySelector('.fe-name').textContent,
            c.querySelector('.fe-count').textContent]);
    }""")
    ck(chips == [["robin","5"],["wren","2"],["sparrow","1"],["oak","3"]],
       "pasted block parses to robin 5 / wren 2 / sparrow 1 / oak 3: %r" % (chips,))
    # Each of those four facts, stated so a failure names which branch broke.
    names = [c[0] for c in chips]
    ck("12" not in names, "a bare number is not read as a species named 12: %r" % (names,))
    ck("sparrow" in names, "a bare name with no count is still read as one individual")
    ck("#" not in "".join(names) and "quadrat A notes" not in " ".join(names),
       "a comment-only line contributes no species: %r" % (names,))
    ck(dict(chips).get("robin") == "5",
       "the same name on two lines accumulates (4 + 1 = 5), it does not overwrite")
    ck(dict(chips).get("oak") == "3", "a trailing # comment is stripped off a data line")
    # and typing in the raw box must not rewrite the raw box under the user's cursor
    ck(pg.eval_on_selector("#wb-field","e=>e.value") == PASTE,
       "parsing does not re-serialize over what the user is typing")

    # the deck textarea is still populated by its select
    ck(pg.eval_on_selector("#wb-decklist","e=>e.value.length>0") , "wb-decklist still auto-fills from the deck picker")

    # ---------- tree-visualizer ----------
    pg.goto(_u("tree-visualizer.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(900)
    for lid,tid,word in [("selK","selK","select k-th"),("rnkK","rnkK","rank of")]:
        l=pg.eval_on_selector('label[for="%s"]'%lid,"e=>e.textContent.trim()")
        ck(l==word, "label for %s reads %r (got %r)"%(lid,word,l))
    # clicking the label must focus its input — that is the point of label/for
    pg.click('label[for="selK"]')
    ck(pg.evaluate("()=>document.activeElement.id")=="selK", "clicking the selK label focuses the input")
    # and the input still drives its output
    pg.fill("#selK","3"); pg.dispatch_event("#selK","input"); pg.wait_for_timeout(300)
    ck(pg.inner_text("#selOut").strip() not in ("","—"), "selK still updates selOut")
    pg.fill("#rnkK","42"); pg.dispatch_event("#rnkK","input"); pg.wait_for_timeout(300)
    ck(pg.inner_text("#rnkOut").strip() not in ("","—"), "rnkK still updates rnkOut")

    b.close()
print("---"); print("%d/%d"%(P,P+F))
raise SystemExit(1 if F else 0)
