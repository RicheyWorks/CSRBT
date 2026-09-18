# -*- coding: utf-8 -*-
"""What the page works out, and whether any of it can leave -- checked (ADR-211).

`tools/audit_carried.py` says N of the figures the exporting pages of this kit
compute appear in nothing those pages hand over. It said 135 of 317 on the day
it was written. That number is a worklist and a ratchet, and a wrong one is
worse than none: too high and the audit is switched off as noise, after which a
page that quietly stops exporting its analysis is invisible again; too low and a
session is scored, exported, and argued about for a year without the statistic
that says whether it is worth anything -- with every suite in this kit green.

Six things have to be right, and a fixture pins each:

  A. THE PAGE IS ENTERED FIRST, AND THE READING IS THE PAGE'S OWN. An export
     pressed on an empty page carries nothing.
  B. A FIGURE IS MATCHED AS A NUMBER, NOT AS A STRING. 6.00x10^5 on screen is
     600000 in a CSV, 1,234 is 1234, and 25% is 25.
  C. ...AT THE PRECISION THE PAGE SHOWS. An export carrying 0.7217 has carried
     the 0.72 on the screen; one carrying 0.7 has not.
  D. EVERY NUMBER IN THE FIGURE MUST BE FOUND, because a figure is often two --
     "3 / 5", "0.61-1.41" -- and half of a ratio is not the ratio.
  E. WHICH CONTROLS ARE PRESSED IS AUDIT_OUTPUTS' RULE, not a second copy: a
     button the gateway calls destructive is not pressed to see what it exports.
  F. THE RATCHET AND THE EXEMPTION. The ceiling falls on request and never rises
     silently; an exemption needs a reason and the reason is stored.

Run:  python3 tools/verify/verify_carried.py
"""
MUTATE_ROLE = "fixture-builder"     # the temp dir here holds fixture pages
import contextlib, io, json, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import audit_states as S
import audit_carried as A

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


# ---- the oracle, on its own ------------------------------------------------
ck(A.nums(u"6.00×10⁵") == [600000.0],
   "a superscript exponent is a number: %s" % A.nums(u"6.00×10⁵"))
ck(A.nums(u"2.83×10⁻⁴ M") == [0.000283],
   "...and a negative one: %s" % A.nums(u"2.83×10⁻⁴ M"))
ck(A.nums("1,234 kg") == [1234.0], "a thousands separator is not a second number: %s"
   % A.nums("1,234 kg"))
ck(A.nums("12, 34") == [12.0, 34.0],
   "A SEPARATOR IS ONLY ONE BETWEEN DIGITS AND BEFORE A GROUP OF THREE. A rule that stripped "
   "every comma next to a digit would read a two-column line as one number: %s" % A.nums("12, 34"))
ck(A.nums("1,2345") == [1.0, 2345.0],
   "...and a comma before four digits is not a separator either: %s" % A.nums("1,2345"))
ck(A.nums(u"−3.5") == [-3.5], "a typographic minus is a minus: %s" % A.nums(u"−3.5"))
ck(A.nums("3 / 5") == [3.0, 5.0], "a ratio is two numbers: %s" % A.nums("3 / 5"))
ck(A.nums("no figure here") == [], "prose with no number yields none")
try:
    _hex = A.nums("colour 8E8160 on the swatch")
except Exception as _e:                      # the point of the check: it must not raise
    _hex = "raised %s" % type(_e).__name__
ck(_hex == [],
   "A TOKEN IN A PAGE IS NOT ALWAYS A QUANTITY. Half of a hex colour parses as a number with an "
   "exponent no float can hold; `10 ** exp` raised OverflowError and the stand sheet came back as "
   "an error rather than a reading -- a page reported as broken by its own stylesheet: %s" % (_hex,))
ck(A.grain("0.72") == 0.01 and A.grain("14") == 1.0,
   "the precision read is the PAGE's -- the size of the last digit it shows: %s"
   % [A.grain("0.72"), A.grain("14")])
ck(A.grain(u"6.00×10⁵") == 1000.0,
   "AND THE EXPONENT COUNTS. 6.00x10^5 is written to three significant figures, so its last digit "
   "is a thousand, not a hundredth. A tolerance read off the mantissa alone called the cell "
   "bench's 2.83x10^2 uM lost against a file carrying 2.834e+2 -- the same number, one figure "
   "further out: %s" % A.grain(u"6.00×10⁵"))
ck(A.carried(u"2.83×10²", [283.4]) is True,
   "...so a figure in scientific notation is carried by a file that writes it with one more "
   "figure: %s" % A.carried(u"2.83×10²", [283.4]))

ck(A.carried("0.72", [0.7217]) is True,
   "AN EXPORT CARRYING MORE PRECISION HAS CARRIED THE FIGURE: 0.7217 carries the 0.72 on screen")
ck(A.carried("0.72", [0.7]) is False,
   "...and one carrying LESS has not: a page showing 0.72 and a file saying 0.7 do not agree")
ck(A.carried("4.82", [4.825]) is True,
   "A FIGURE IS MATCHED WITHIN THE SCREEN'S OWN LAST DIGIT, NOT BY ROUNDING BOTH SIDES TO IT. The "
   "greenhouse shows g/kWh at two places and exports it at three: 4.8249 is 4.82 on screen and "
   "4.825 in the file, and rounding that back to two places gives 4.83. A rule that rounded both "
   "sides called a figure exported in MORE detail than the page shows it lost -- double rounding, "
   "the shape ADR-087 is about, arriving in the instrument rather than in a page")
ck(A.carried("3 / 5", [3.0]) is False,
   "EVERY NUMBER IN THE FIGURE MUST BE FOUND -- half of a ratio is not the ratio")
ck(A.carried("3 / 5", [5.0, 3.0]) is True, "...and both, in any order, is the ratio")
ck(A.carried("> 3.0", [3.0]) is True, "a threshold is its number")
ck(A.carried("fruiting", [1.0]) is None,
   "A FIGURE WITH NO NUMBER IN IT IS NOT MEASURED HERE rather than counted lost: a page's "
   "phenophase or its datum is a word, and a rule that demanded a word appear in a CSV would "
   "report every page as losing most of what it shows")

# ---- the fixtures ----------------------------------------------------------
def fixture(export):
    """A page that works out four figures and hands over `export` (JS producing
    the text that goes on the clipboard)."""
    return u"""<!doctype html><html><head><meta charset="utf-8"><title>carried fixture</title>
<style>body{font:16px sans-serif}button,input{min-height:44px;font-size:16px}</style></head><body>
<h1>carried fixture</h1>
<label>Note <input id="f-note" type="text" aria-label="Note"></label>
<button id="add" type="button">Add a row</button>
<button id="csvCopy" type="button">Copy the sheet</button>
<button id="wipe" type="button">Clear the sheet and its copy</button>
<div id="rList"></div>
<div id="anStat"></div>
<script>
  var $=function(i){return document.getElementById(i);};
  var recs=[];
  function paint(){
    $("rList").innerHTML = recs.map(function(r){ return '<div>'+r.plot+'</div>'; }).join("");
    var n = recs.length, mean = n ? (n + 0.567) : 0;
    $("anStat").innerHTML = n ? (
        '<div class="tile"><div class="v">'+n+'</div><div class="l">rows on this sheet</div></div>'
      + '<div class="tile"><div class="v">'+mean.toFixed(2)+'</div><div class="l">mean value</div></div>'
      + '<div class="tile"><div class="v">6.00\\u00d710\\u2075</div><div class="l">cells per mL</div></div>'
      + '<div class="tile"><div class="v">'+n+' / 5</div><div class="l">scored</div></div>'
      + '<div class="tile"><div class="v">fruiting</div><div class="l">phenophase</div></div>')
      : 'Nothing yet.';
  }
  $("add").addEventListener("click", function(){ recs.push({plot:"p"+(recs.length+1)}); paint(); });
  $("f-note").addEventListener("input", paint);
  $("wipe").addEventListener("click", function(){ recs=[]; paint(); });
  $("csvCopy").addEventListener("click", function(){
    var n = recs.length, mean = n ? (n + 0.567) : 0;
    navigator.clipboard.writeText(%s);
  });
  paint();
</script></body></html>
""" % export


TASK = {
    "id": "page-fixture-science", "target": "page", "page": "fixture.html",
    "goal": "put a note and three rows on the fixture, so that what it shows can be compared "
            "with what it hands over",
    "steps": [
        {"id": "obs", "action": "observe"},
        {"id": "note", "action": "set-text",
         "arguments": {"selector": "@control:f-note", "value": "north slope"}},
        {"id": "a1", "action": "activate", "arguments": {"selector": "@control:add"}},
        {"id": "a2", "action": "activate", "arguments": {"selector": "@control:add"}},
        {"id": "a3", "action": "activate", "arguments": {"selector": "@control:add"}},
        {"id": "look", "action": "read-report"},
    ],
}

tmp = tempfile.mkdtemp(prefix="carried_")
docs = os.path.join(tmp, "docs")
os.mkdir(docs)
tasks_dir = os.path.join(tmp, "tasks")
os.mkdir(tasks_dir)


def write(name, html):
    io.open(os.path.join(docs, name), "w", encoding="utf-8").write(html)
    t = dict(TASK)
    t["id"] = "page-%s-science" % name.replace(".html", "")
    t["page"] = name
    io.open(os.path.join(tasks_dir, t["id"] + ".json"), "w", encoding="utf-8").write(
        json.dumps(t, indent=1))


# EVERY figure, in the page's own notation.
write("whole.html", fixture(
    u'"rows,"+n+"\\nmean,"+mean.toFixed(2)+"\\ncells,6.00\\u00d710\\u2075\\nscored,"+n+" / 5"'))
# The analysis panel, minus the one figure that took work to compute.
write("half.html", fixture(
    u'"rows,"+n+"\\ncells,6.00\\u00d710\\u2075\\nscored,"+n+" / 5"'))
# Every figure, in the notation a FILE uses rather than the one a page uses.
write("notation.html", fixture(
    u'"rows,"+n+"\\nmean,"+mean.toFixed(2)+"\\ncells,600000\\nscored,"+n+",5"'))
# More precision than the screen, which carries the screen.
write("deeper.html", fixture(
    u'"rows,"+n+"\\nmean,"+(mean+0.001).toFixed(4)+"\\ncells,6.0e5\\nscored,"+n+" of 5"'))
# Less precision than the screen, which does not.
write("coarser.html", fixture(
    u'"rows,"+n+"\\nmean,"+mean.toFixed(1)+"\\ncells,6.00\\u00d710\\u2075\\nscored,"+n+" / 5"'))
# Half of the ratio.
write("halfratio.html", fixture(
    u'"rows,"+n+"\\nmean,"+mean.toFixed(2)+"\\ncells,6.00\\u00d710\\u2075\\nscored,"+n'))

# A page that works out figures and hands NOTHING over. Not this audit's
# business -- that is audit_outputs' TRAP_ENTRY and its mute ratchet -- and
# saying it twice in two files is the defect ADR-141 keeps finding.
write("noexport.html", fixture(u'""').replace(
    '<button id="csvCopy" type="button">Copy the sheet</button>', ''))

S.TASKS_DIR = tasks_dir
os.environ["CSRBT_DOCS_DIR"] = docs
A.LEDGER = os.path.join(tmp, "carried_ledger.json")

got = A.walk(tasks_dir=tasks_dir)


def lost(name):
    return sorted(got[name].get("lost", []))


# ---- A. entered first, and the reading is the page's own --------------------
ck(all(not r.get("error") for r in got.values()),
   "every fixture was entered and its exports pressed: %s"
   % [(k, v.get("error")) for k, v in got.items() if v.get("error")])
ck(got["whole.html"]["figures"] == 4,
   "THE FIGURES ARE THE ONES THE PAGE PUBLISHES, read from read-report rather than listed here: "
   "%s" % got["whole.html"]["figures"])
ck(got["whole.html"].get("bytes", 0) > 0 and got["whole.html"]["exports"] >= 1,
   "...and the payload is what the page HANDED OVER, after its own task filled it in -- an "
   "export pressed on an empty page carries nothing and every figure would read as lost for a "
   "reason that is about the audit: %s" % got["whole.html"])

ck(got["whole.html"]["figures"] == 4 and "phenophase" not in lost("whole.html"),
   "A FIGURE WITH NO NUMBER IN IT IS NOT MEASURED rather than counted lost: the fixture publishes "
   "five figures and one of them is the word 'fruiting'. A rule that demanded every figure appear "
   "in a CSV would report every page in this kit as losing most of what it shows: %s, %s"
   % (got["whole.html"]["figures"], lost("whole.html")))

# ---- B/C/D. what counts as carried ------------------------------------------
ck(lost("whole.html") == [],
   "A PAGE THAT EXPORTS WHAT IT WORKS OUT LOSES NOTHING: %s" % lost("whole.html"))
ck(lost("half.html") == ["mean value"],
   "A FIGURE IN NO PAYLOAD IS LOST -- and only that one, so the count is a worklist rather than "
   "a mood: %s" % lost("half.html"))
ck(lost("notation.html") == [],
   "A FIGURE IS MATCHED AS A NUMBER, NOT AS A STRING: 6.00x10^5 on the screen and 600000 in the "
   "file are the same figure, and a string comparison called 171 of this kit's figures lost "
   "where 135 are: %s" % lost("notation.html"))
ck(lost("deeper.html") == [],
   "AN EXPORT CARRYING MORE PRECISION THAN THE SCREEN HAS CARRIED THE SCREEN: %s"
   % lost("deeper.html"))
ck(lost("coarser.html") == ["mean value"],
   "...and one carrying LESS has not: a page showing 3.57 and a file saying 3.6 disagree about "
   "the digit the reader would quote: %s" % lost("coarser.html"))
ck(lost("halfratio.html") == ["scored"],
   "EVERY NUMBER IN THE FIGURE MUST BE FOUND: an export carrying the 3 of '3 / 5' and not the 5 "
   "has carried a count, not the score: %s" % lost("halfratio.html"))

ck(got["noexport.html"].get("noexport") is True
   and got["noexport.html"].get("figures") == 0,
   "A PAGE THAT HANDS NOTHING OVER IS NOT MEASURED HERE, rather than reported as losing "
   "everything it works out: whether a page with a data trap and no export is a defect is "
   "audit_outputs' TRAP_ENTRY and its mute ratchet, and a second copy of that judgement here is "
   "the shape ADR-141 keeps finding: %s" % got["noexport.html"])

# ---- E. which controls are pressed ------------------------------------------
_src = io.open(os.path.join(_kit.TOOLS_DIR, "audit_carried.py"), encoding="utf-8").read()
ck("AO.candidates(" in _src and "HANDS_OVER" not in _src,
   "WHICH CONTROLS HAND SOMETHING OVER IS AUDIT_OUTPUTS' RULE, asked rather than copied -- a "
   "second copy here is the list ADR-204, ADR-205, ADR-207, ADR-208 and ADR-210 each found "
   "drifting out of step with the one reader that read it")
ck(got["whole.html"]["exports"] == 1,
   "...so the fixture's 'Clear the sheet and its copy' is NOT pressed to see what it exports, "
   "even though its label says copy: the gateway calls it destructive and this audit presses "
   "nothing the gateway refuses: %s" % got["whole.html"]["exports"])

# ---- F. the ratchet and the exemption ---------------------------------------
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    rc = A.main([])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]
ck(rc == 0 and led["half.html"]["lost"] and "ceiling" not in led["half.html"],
   "a first reading records what it found and no ceiling: %s" % led["half.html"])
ck("noexport.html" not in led,
   "...AND A PAGE THAT HANDS NOTHING OVER GETS NO ROW AND NO CEILING. A page recorded here at zero "
   "lost reads as a page that exports everything it works out, which is the opposite of what is "
   "true of it: %s" % sorted(led))
with contextlib.redirect_stdout(io.StringIO()):
    rc = A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]
ck(rc == 0 and led["half.html"].get("ceiling") == 1,
   "the ceiling is set on request, at today's reading: %s" % led["half.html"])

state = A.load()
state["pages"]["half.html"]["ceiling"] = 0
A.save(state)
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    rc = A.main([])
said = _buf.getvalue()
ck(rc != 0,
   "A PAGE THAT EXPORTS LESS THAN IT DID FAILS, with no flag -- run_all runs an audit with no "
   "arguments, and a ratchet nothing runs is a comment")
ck(A.main(["--check"]) != 0, "--check is accepted for symmetry, and refuses too")
ck(any("half.html" in l and "ceiling" in l for l in said.split("\n")),
   "...and it NAMES the page and the figure that stopped leaving: %s"
   % said.strip().split("\n")[-1][:80])

ck(A.main(["--declare", "half.html:mean value"]) != 0,
   "declaring a figure right to stay WITHOUT a reason is refused: a number the page works out "
   "and never lets you take is either a defect or a property of the reference data, and only "
   "the reason says which")
rc = A.main(["--declare", "half.html:mean value", "--reason",
             "a demo of the rule, in this suite's own fixture directory"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["half.html"]
ck(rc == 0 and led.get("declared", {}).get("mean value")
   == "a demo of the rule, in this suite's own fixture directory",
   "...and with one, THE REASON IS WHAT IS STORED, word for word: %s" % led.get("declared"))
ck(A.losses(got["half.html"], A.declared_of(A.load(), "half.html")) == [],
   "a declared figure leaves the worklist: %s"
   % A.losses(got["half.html"], A.declared_of(A.load(), "half.html")))

# ---- THE EXEMPTION RECORDS WHAT IT TOOK OUT (ADR-224) ----------------------
# Filtering the finding out of the list and writing the filtered list to the
# ledger discarded the evidence at the moment the exemption was applied, and no
# reader in the kit could then tell a declaration covering a real finding from
# one naming a thing the page no longer has. The rule lives in tools/exempt.py
# and is asserted HERE, through this audit's own reading, so that a copy of it
# that filtered quietly would fail this suite and not only the reader's.
with contextlib.redirect_stdout(io.StringIO()):
    A.main([])
_row = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["half.html"]
ck('mean value' in (_row.get("raw") or []) and 'mean value' not in (_row.get("lost") or []),
   "the row records what was flagged BEFORE the exemption under `raw`, beside the filtered "
   "list it always recorded -- the declared key is in one and not the other: raw %s, filtered %s"
   % (_row.get("raw"), _row.get("lost")))
ck(isinstance(_row.get("seen"), list) and set(_row.get("raw") or []) <= set(_row.get("seen") or [])
   and set(_row.get("lost") or []) <= set(_row.get("raw") or []),
   "...and everything the reading could have flagged under `seen`, with filtered within raw within "
   "seen -- without the universe, `this finding is covered` and `this thing is gone` are the same "
   "absence: seen %s" % _row.get("seen"))
_live, _e = ["k1"], {}
A.X.apply(_e, _live, {}, ["k1", "other"])
_live.append("added after the record was written")
ck(_e["raw"] == ["k1"] and _e["seen"] == ["k1", "other"],
   "the record is a COPY, not the audit's live list: a row holding the list the audit goes on "
   "using would be rewritten by whatever the audit did to it next: %s" % _e["raw"])

state = A.load()
state["pages"]["half.html"]["ceiling"] = 9
A.save(state)
with contextlib.redirect_stdout(io.StringIO()):
    A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["half.html"]
ck(led.get("ceiling") < 9,
   "--raise-floors LOWERS the ceiling, because this ratchet only ever comes down: %s" % led)
state = A.load()
state["pages"]["half.html"].pop("declared", None)
state["pages"]["half.html"]["ceiling"] = 0
A.save(state)
with contextlib.redirect_stdout(io.StringIO()):
    rc = A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["half.html"]
ck(led.get("ceiling") == 0 and led.get("lost"),
   "...and with the declaration taken away and the page back over its ceiling, a --raise-floors "
   "run leaves the ceiling where it was rather than recording today's worse reading as the new "
   "normal: %s" % led)
ck(rc != 0,
   "...and that run still fails, because --raise-floors lowers what it can and reports what it "
   "cannot")

print("---")
print("%d/%d" % (P, P + F))
sys.exit(1 if F else 0)
