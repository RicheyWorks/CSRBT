# -*- coding: utf-8 -*-
"""What a published page can actually hand you -- checked (ADR-212).

`tools/audit_takeaway.py` says 0 of the 81 controls that hand something over in
this kit are stranded -- reachable only by a page-started download, which a
published artifact refuses silently. It said 3 on the day it was written, and all
three told the reader the file had gone.

Five things have to be right, and a fixture pins each:

  A. THE CHANNEL IS READ FROM THE PAYLOAD, not from the label. A button called
     "Download" that puts the bytes on the clipboard is not stranded; one called
     "Save the sheet" that only downloads is.
  B. A DOWNLOAD IS NOT A PUBLISHABLE CHANNEL and clipboard, copy and print are.
  C. WHAT THE PAGE SAID IS THIS PRESS'S. The live-region log is a running list,
     and the door SPLICES it when it reports what an act said, so a message read
     after that call is gone and one read before it belongs to the entry.
  D. A CLAIM IS AN ASSERTION THAT THE PAYLOAD LEFT, and a message that hedges --
     "some viewers block a page-started download" -- is not one.
  E. THE RATCHET AND THE EXEMPTION. Stranded is a ceiling that only falls; a
     CLAIM fails on sight, with no ceiling, because a page telling a reader their
     sheet is saved when it is not is what this kit exists to refuse.

Run:  python3 tools/verify/verify_takeaway.py
"""
MUTATE_ROLE = "fixture-builder"     # the temp dir here holds fixture pages
import contextlib, io, json, os, sys, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import audit_states as S
import audit_takeaway as A

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


# ---- the two rules, on their own ------------------------------------------
ck(A.PUBLISHABLE == frozenset(["clipboard", "copy", "print"]),
   "A DOWNLOAD IS NOT A PUBLISHABLE CHANNEL and clipboard, copy and print are. A clipboard write "
   "returns a promise that rejects and an execCommand that returns false; a print opens the "
   "reader's own dialog. A page-started download in a sandboxed frame does none of those: %s"
   % sorted(A.PUBLISHABLE))
ck(A.claims(["bench.csv downloaded"]) == "bench.csv downloaded",
   "A CLAIM IS AN ASSERTION THAT THE PAYLOAD LEFT: %s" % A.claims(["bench.csv downloaded"]))
ck(A.claims(["Downloading clashing-study.eco"]) is not None,
   "...in any tense the pages use")
ck(A.claims(["bench.csv downloaded, unless your viewer blocked it"]) is None,
   "A MESSAGE THAT HEDGES IS NOT A CLAIM -- the same verb, and a sentence the page can stand "
   "behind. The fix for a channel that can fail with nothing to test is to say so, and a rule "
   "that called that a claim would push every page back to the confident one: %s"
   % A.claims(["bench.csv downloaded, unless your viewer blocked it"]))
ck(A.claims(["bench.csv copied — some viewers block a page-started download, "
             "so the copy is your sheet"]) is None,
   "...and a message that asserts the COPY and only mentions the download is not a claim about "
   "the download: %s"
   % A.claims(["bench.csv copied — some viewers block a page-started download"]))
ck(A.claims(["Nothing logged yet"]) is None, "a refusal is not a claim")
ck(A.claims([]) is None and A.claims(None) is None, "silence is not a claim")


# ---- the fixtures ----------------------------------------------------------
def fixture(handler):
    return u"""<!doctype html><html><head><meta charset="utf-8"><title>takeaway fixture</title>
<style>body{font:16px sans-serif}button,input{min-height:44px;font-size:16px}</style></head><body>
<h1>takeaway fixture</h1>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<label>Note <input id="f-note" type="text" aria-label="Note"></label>
<button id="add" type="button">Add a row</button>
<button id="hand" type="button">Download the sheet</button>
<button id="mute" type="button">Export the sheet</button>
<div id="rList"></div>
<script>
  var $=function(i){return document.getElementById(i);};
  var recs=[];
  function toast(m){ var t=$("toast"); t.textContent=m; t.classList.add("on"); }
  function paint(){ $("rList").innerHTML = recs.map(function(r){ return '<div>'+r.p+'</div>'; }).join(""); }
  function sheet(){ return "plot,note\\n" + recs.map(function(r){ return r.p+","+$("f-note").value; }).join("\\n"); }
  function down(){
    var a=document.createElement("a");
    a.href=URL.createObjectURL(new Blob([sheet()],{type:"text/csv"}));
    a.download="sheet.csv";
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  }
  $("add").addEventListener("click", function(){ recs.push({p:"p"+(recs.length+1)}); paint(); });
  $("f-note").addEventListener("input", paint);
  $("hand").addEventListener("click", function(){ if(!recs.length){ toast("Nothing logged yet"); return; }
%s
  });
  paint();
</script></body></html>
""" % handler


TASK = {
    "id": "page-fixture-science", "target": "page", "page": "fixture.html",
    "goal": "put a note and two rows on the fixture, then hand the sheet over",
    "steps": [
        {"id": "obs", "action": "observe"},
        {"id": "note", "action": "set-text",
         "arguments": {"selector": "@control:f-note", "value": "north slope"}},
        {"id": "a1", "action": "activate", "arguments": {"selector": "@control:add"}},
        {"id": "a2", "action": "activate", "arguments": {"selector": "@control:add"}},
    ],
}

tmp = tempfile.mkdtemp(prefix="takeaway_")
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


# a download and nothing else, saying nothing
write("quiet.html", fixture('    down();'))
# a download and nothing else, saying the file went
write("loud.html", fixture('    down(); toast("sheet.csv downloaded");'))
# a download and nothing else, saying what is actually true
write("honest.html", fixture(
    '    down(); toast("sheet.csv downloaded, unless your viewer blocked it");'))
# the clipboard, and a confident sentence: the payload DOES reach the reader, so
# the sentence is answerable and is not the kind of claim this rule is about
write("copyloud.html", fixture(
    '    navigator.clipboard.writeText(sheet()); toast("sheet.csv saved");'))
# a download AND the clipboard: the payload reaches a published reader
write("both.html", fixture(
    '    down(); navigator.clipboard.writeText(sheet());'
    ' toast("sheet.csv copied \\u2014 some viewers block a page-started download");'))
# no download at all: the print channel
write("paper.html", fixture('    window.print(); toast("sent to print");'))

S.TASKS_DIR = tasks_dir
os.environ["CSRBT_DOCS_DIR"] = docs
A.LEDGER = os.path.join(tmp, "takeaway_ledger.json")

got = A.walk(tasks_dir=tasks_dir)


def one(name):
    for b in got[name]["buttons"]:
        if b["key"] == "hand":
            return b
    return {}


# ---- A/B. the channel is read from the payload -----------------------------
ck(all(not r.get("error") for r in got.values()),
   "every fixture was entered and its controls pressed: %s"
   % [(k, v.get("error")) for k, v in got.items() if v.get("error")])
ck(one("quiet.html")["kinds"] == ["download"] and one("quiet.html")["stranded"],
   "A CONTROL WHOSE ONLY CHANNEL IS A DOWNLOAD IS STRANDED -- a published artifact is a sandboxed "
   "frame that refuses a page-started download with no throw, no return value and nothing to "
   "test, so nothing reaches the reader: %s" % one("quiet.html"))
ck(one("both.html")["kinds"] == ["clipboard", "download"]
   and not one("both.html")["stranded"],
   "A CONTROL WHOSE LABEL SAYS DOWNLOAD AND WHOSE PAYLOAD ALSO GOES ON THE CLIPBOARD IS NOT "
   "STRANDED. The channel is read from what came out, not from what the button is called: %s"
   % one("both.html"))
ck(one("paper.html")["kinds"] == ["print"] and not one("paper.html")["stranded"],
   "...and print is a channel a published page keeps: %s" % one("paper.html"))
ck(got["quiet.html"]["stranded"] == ["hand"] and got["both.html"]["stranded"] == [],
   "the worklist is the stranded controls and nothing else: %s, %s"
   % (got["quiet.html"]["stranded"], got["both.html"]["stranded"]))
_mute = [b for b in got["both.html"]["buttons"] if b["key"] == "mute"]
ck(_mute and _mute[0]["kinds"] == [] and not _mute[0]["stranded"],
   "A CONTROL THAT HANDS NOTHING OVER AT ALL IS NOT STRANDED HERE. Every fixture carries an "
   "'Export the sheet' button wired to nothing: whether a silent export is a defect is "
   "audit_outputs' mute ratchet (ADR-208), and a rule that answered it again here would give the "
   "kit two readers of the same question and one of them would drift: %s" % (_mute,))

# ---- C/D. what the page said -----------------------------------------------
ck(one("loud.html")["said"] == "sheet.csv downloaded",
   "WHAT THE PAGE SAID IS THIS PRESS'S: %s" % one("loud.html")["said"])
ck(got["loud.html"]["claims"] == [("hand", "sheet.csv downloaded")],
   "...and a STRANDED control that says the payload left is the claim: %s"
   % got["loud.html"]["claims"])
ck(one("quiet.html")["said"] is None and got["quiet.html"]["claims"] == [],
   "a stranded control that says nothing is stranded and not a liar -- two different findings, "
   "and only one of them is a lie: %s" % (one("quiet.html")["said"],))
ck(one("honest.html")["said"] is None and got["honest.html"]["claims"] == [],
   "A HEDGED MESSAGE IS NOT A CLAIM: a page that tells the reader the viewer may refuse the "
   "download has said something true, and a rule that counted it would push every page back to "
   "the confident sentence: %s" % (one("honest.html")["said"],))
ck(one("copyloud.html")["said"] == "sheet.csv saved"
   and got["copyloud.html"]["claims"] == [],
   "A CLAIM IS ONLY A CLAIM ON A CONTROL NOTHING REACHES THE READER BY. The copy said 'sheet.csv "
   "saved' with no hedge at all, and that sentence is fine: a clipboard write reports failure, so "
   "the page is answerable for it. A rule that reported every confident message would bury the "
   "three that are about a channel with no answer: %s, %s"
   % (one("copyloud.html")["said"], got["copyloud.html"]["claims"]))

# ---- the controls are audit_outputs' ---------------------------------------
_src = io.open(os.path.join(_kit.TOOLS_DIR, "audit_takeaway.py"), encoding="utf-8").read()
ck("AO.candidates(" in _src and "HANDS_OVER" not in _src,
   "WHICH CONTROLS HAND SOMETHING OVER IS AUDIT_OUTPUTS' RULE, asked rather than copied -- a "
   "second copy here is the list ADR-204, ADR-205, ADR-207, ADR-208, ADR-210 and ADR-211 each "
   "found drifting out of step with its one reader")

# ---- E. the ratchet and the exemption ---------------------------------------
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    rc = A.main([])
said = _buf.getvalue()
ck(rc != 0 and "loud.html" in said and "sheet.csv downloaded" in said,
   "A PAGE THAT TELLS THE READER A PAYLOAD LEFT THAT CANNOT LEAVE FAILS ON SIGHT, with no flag "
   "and no ceiling, and the run NAMES the page, the control and the sentence: %s"
   % said.strip().split("\n")[-1][:90])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]
ck(led["quiet.html"]["stranded"] == ["hand"] and "ceiling" not in led["quiet.html"],
   "a first reading records what it found and no ceiling: %s" % led["quiet.html"])
with contextlib.redirect_stdout(io.StringIO()):
    A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]
ck(led["quiet.html"].get("ceiling") == 1 and led["both.html"].get("ceiling") == 0,
   "the ceiling is set on request, at today's reading, per page: %s"
   % {k: led[k].get("ceiling") for k in sorted(led)})

state = A.load()
state["pages"]["quiet.html"]["ceiling"] = 0
A.save(state)
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    rc = A.main([])
said = _buf.getvalue()
ck(rc != 0 and any("quiet.html" in l and "ceiling" in l for l in said.split("\n")),
   "A PAGE THAT STRANDS MORE THAN IT DID FAILS, and is named: %s"
   % [l for l in said.split("\n") if "ceiling" in l][:1])
ck(A.main(["--check"]) != 0, "--check is accepted for symmetry, and refuses too")

ck(A.main(["--declare", "quiet.html:hand"]) != 0,
   "declaring a stranded control expected WITHOUT a reason is refused: a button that hands "
   "nothing over where the kit is read is either a defect or a deliberate local-only route, and "
   "only the reason says which")
rc = A.main(["--declare", "quiet.html:hand", "--reason",
             "a demo of the rule, in this suite's own fixture directory"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["quiet.html"]
ck(rc == 0 and led.get("declared", {}).get("hand")
   == "a demo of the rule, in this suite's own fixture directory",
   "...and with one, THE REASON IS WHAT IS STORED, word for word: %s" % led.get("declared"))
ck(A.stranded(got["quiet.html"], A.declared_of(A.load(), "quiet.html")) == [],
   "a declared control leaves the worklist: %s"
   % A.stranded(got["quiet.html"], A.declared_of(A.load(), "quiet.html")))

state = A.load()
state["pages"]["quiet.html"]["ceiling"] = 9
A.save(state)
with contextlib.redirect_stdout(io.StringIO()):
    A.main(["--raise-floors"])
led = json.load(io.open(A.LEDGER, encoding="utf-8"))["pages"]["quiet.html"]
ck(led.get("ceiling") < 9,
   "--raise-floors LOWERS the ceiling, because this ratchet only ever comes down: %s" % led)

print("---")
print("%d/%d" % (P, P + F))
sys.exit(1 if F else 0)
