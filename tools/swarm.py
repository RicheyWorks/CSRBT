# -*- coding: utf-8 -*-
"""Enters every field, presses every control from a state where its effect can
show, and checks the RESULT -- not that something happened.

WHY THIS EXISTS SEPARATELY FROM tools/harness.py
    The harness asks one question of every affordance: did anything change? That
    question is answered YES by a plus button that subtracts, by a filter that
    keeps the wrong rows, by a picker option that selects its neighbour, and by a
    Copy CSV that puts an empty string on the clipboard. It found 2357
    affordances that do SOMETHING. It could not tell you that one of them does
    the RIGHT thing, and reporting those two as one number was over-claiming.

    This keeps the harness's discovery and its accounting and replaces the
    oracle. Every kind of control carries an expectation written in terms of what
    a user would see:

      tab            exactly one pane is open afterwards and it is the named one
      step + / -     the number moved, in the direction the label promises
      field          what was typed is what the control holds
      slider         the number the widget displays is the number that was set
      select         the chosen option is the one the box reports
      option         clicking an option SELECTS it -- and in a radio group it
                     becomes the only one selected
      picker search  the survivors all match the query, some were removed, and
                     clearing the query brings every one of them back
      add            exactly one more row exists
      remove         exactly one fewer
      clear          no field is left holding anything
      undo           the page is back in a state it was in earlier this run
      export         a payload left the page, it parses, and it contains what
                     was typed into the form

    A control with no expectation attached is not called verified. It is called
    CHANGED, which is the honest name for what the harness was measuring, and the
    split between the two is the number this tool exists to print.

THE SEED
    Every one of those checks needs a page with something on it: an empty form
    exports an empty file perfectly correctly. So the run begins by entering a
    recorded sentinel into every text field and pressing every add-shaped button,
    and the export round trip can then ask a question worth asking -- is what the
    user typed in the file the page produced?

EVERYTHING GOES THROUGH THE CONTRACT
    Not one line of this file touches the DOM. Every observation and every action
    is a command to the gateway in tools/harness_contract.py, addressed to the
    csrbt-page plugin, with a request id, against a policy. The swarm is the
    contract's first client and is deliberately not a privileged one: if an
    affordance cannot be driven through the published actions, that is a hole in
    the contract, and it shows up here as a failure rather than being routed
    around. The run prints the policy it required and the number of commands it
    issued, because a contract nobody has driven forty pages through is a
    contract nobody has tested.

THE ACCOUNTING
    discovered == verified + wrong + changed + dead + hidden + failed + excluded,
    per page and in total, and UNACCOUNTED if it does not hold: the number this
    prints is a coverage claim, and a claim that loses an affordance between
    discovery and verdict is a claim about work that was not done.

Run:  python3 tools/swarm.py            all pages
      python3 tools/swarm.py PAGE ...   named pages
      python3 tools/swarm.py -j 4       four at a time
"""
import argparse, concurrent.futures as cf, glob, io, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "verify"))
import _kit
import harness as H
from harness_contract import Gateway, HarnessError, Policy, Registry
from harness_plugin_page import PagePlugin
from playwright.sync_api import sync_playwright

LEDGER = os.path.join(HERE, "swarm_ledger.json")
VIEWPORT = H.VIEWPORT
IGNORED_CONSOLE = H.IGNORED_CONSOLE

VERDICTS = ("verified", "wrong", "changed", "dead", "hidden", "failed", "excluded")

# The policy a supervised verification run needs, stated once and printed. It is
# the whole ladder, because the swarm's job is to press everything -- which is
# exactly the session an operator should have to opt into deliberately.
SWARM_POLICY = {"READ": True, "NAVIGATE": True, "SENSITIVE_READ": True,
                "DRAFT": True, "MUTATE": True, "DESTRUCTIVE": True}

# Ordinary-looking but unique: finding one in a CSV means it came out of the
# field it was typed into and not out of the page's own furniture. Making a page
# survive hostile input is the escaping suites' job, not this one's.
SENTINEL = "Zqx%03d"
SENT_RE = re.compile(r"Zqx\d{3}")

# Which kind is driven by which published action. A typed contract is only worth
# having if its client uses the typed action: pressing a stepper with a generic
# activate would tell the gateway nothing about what was being asked for.
DRIVER = {
    "tab": "show-pane", "step_btn": "press-step", "step_val": "set-text",
    "text_in": "set-text", "field_in": "set-text", "pick_search": "set-text",
    "select": "choose-option", "slider": "set-slider",
    "pick_opt": "activate", "dial_btn": "activate", "chip": "activate",
    "kopt": "activate", "ck": "activate", "cv": "activate", "swc": "activate",
    "action_btn": "activate",
}

EXCLUDED = dict(H.EXCLUDED)
EXCLUDED["file_in"] = (
    "a file chooser is a platform-specific extension, not part of the automation "
    "contract: choosing a file needs OS focus and an approval policy the gateway "
    "does not own, so the contract publishes no action for it and the swarm does "
    "not reach around the contract to drive one")

# What the label says the control is for. Order matters: a Copy CSV is an export
# even though its label carries no verb this list would otherwise reach for, and
# "New random tree" is a reset rather than an add.
# A form that has been filled is not a record. These commit one.
SAVE_RE = re.compile(r"(?i)\b(save|record|log it|commit|store|keep|submit|"
                     r"file it|enter)\b")

VERBS = [
    ("export", r"(?i)\b(copy|export|download|csv|tsv|json|dwc|darwin|clipboard)\b|\.eco"),
    ("print",  r"(?i)\b(print|pdf)\b"),
    ("undo",   r"(?i)(\bundo\b|↩)"),
    ("clear",  r"(?i)\b(clear|reset|start over|new trial|new random)\b"),
    ("remove", r"(?i)(\bremove\b|\bdelete\b|^\s*[✕✖×x]\s*$)"),
    ("add",    r"(?i)(\badd\b|\bnew\b|\bappend\b|^\s*\+\s*$)"),
]

# Captures what leaves the page. A CSV that arrives as a Blob download and one
# that arrives on the clipboard are the same event to a user, and were two
# different invisibilities to the harness: it recorded the clipboard and let the
# download navigate away. Anchor downloads are intercepted rather than followed,
# both so the payload can be read and so the run does not wander off the page.
CATCH = r"""
window.__S = { out: [], toasts: 0 };
(function () {
  var map = {};
  // A toast raised while an identical toast is still on screen changes nothing
  // any observer of the DOM can see: the class is already there, so adding it
  // again is not a mutation. Twelve live controls were accused of being wired
  // to nothing for exactly this reason (ADR-100). Count the raise where it
  // happens -- at the call -- rather than hoping to see its result.
  try {
    var TA = DOMTokenList.prototype.add;
    DOMTokenList.prototype.add = function () {
      try {
        if (this.contains("toast") &&
            Array.prototype.indexOf.call(arguments, "on") >= 0)
          window.__S.toasts++;
      } catch (e) { }
      return TA.apply(this, arguments);
    };
  } catch (e) { }
  try {
    var NB = window.Blob;
    var WB = function (parts, opts) {
      var b = new NB(parts || [], opts);
      try { b.__t = (parts || []).map(String).join(""); } catch (e) { }
      return b;
    };
    WB.prototype = NB.prototype;
    window.Blob = WB;
    var CO = URL.createObjectURL.bind(URL);
    URL.createObjectURL = function (b) {
      var u = CO(b);
      try { map[u] = b.__t || ""; } catch (e) { }
      return u;
    };
  } catch (e) { }
  var push = function (k, name, text) {
    window.__S.out.push({ k: k, name: String(name || "").slice(0, 80),
                          text: String(text == null ? "" : text).slice(0, 40000) });
  };
  var AC = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function () {
    if (this.hasAttribute("download")) {
      var t = map[this.href] || "";
      if (!t && this.href.slice(0, 5) === "data:") {
        try { t = decodeURIComponent(this.href.split(",").slice(1).join(",")); } catch (e) { }
      }
      push("download", this.getAttribute("download"), t);
      return;                            /* captured, not followed */
    }
    return AC.apply(this, arguments);
  };
  try {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: {
      writeText: function (s) { push("clipboard", "", s); return Promise.resolve(); } } });
  } catch (e) { }
  window.print = function () { push("print", "", ""); };
  document.addEventListener("DOMContentLoaded", function () {
    var oe = document.execCommand;
    document.execCommand = function (c) {
      if (c === "copy") { push("copy", "", String(window.getSelection())); return true; }
      return oe ? oe.apply(document, arguments) : false;
    };
  });
})();
"""


def verb(label):
    for name, pat in VERBS:
        if re.search(pat, label or ""):
            return name
    return None


# ---------------------------------------------------------------------------
# A client of the contract, and nothing more privileged than that
# ---------------------------------------------------------------------------

class Client(object):
    def __init__(self, gateway, token, plugin="csrbt-page"):
        self.gw, self.tok, self.plugin = gateway, token, plugin
        self.n = 0
        self.refused = []

    def do(self, action, **args):
        self.n += 1
        return self.gw.execute(self.tok, self.plugin,
                               {"request_id": "swarm-%06d" % self.n,
                                "action": action, "arguments": args})

    def out(self, action, **args):
        return self.do(action, **args)["output"]

    def page_state(self):
        return self.out("read-page")

    def control(self, sel):
        return self.out("read-control", selector=sel)

    def snapshot(self):
        return self.gw.observe(self.tok, self.plugin)


# ---------------------------------------------------------------------------
# The oracles. Each returns (verdict, name, expected, got).
# ---------------------------------------------------------------------------

def _moved(a, b):
    return (a["thash"] != b["thash"] or a["vals"] != b["vals"] or a["on"] != b["on"]
            or a["outs"] != b["outs"] or a["els"] != b["els"])


def _rows(before, after):
    """Which repeated structure gained or lost exactly one instance."""
    up, down = [], []
    for c, n in after["cls"].items():
        d = n - before["cls"].get(c, 0)
        if d == 1:
            up.append(c)
        elif d == -1:
            down.append(c)
    for c, n in before["cls"].items():
        if c not in after["cls"] and n == 1:
            down.append(c)
    return up, down


def _split(line, sep):
    """A separator inside quotes is not a column boundary. Counting it as one is
    how a correct CSV gets reported as ragged."""
    out, cur, q = [], [], False
    for ch in line:
        if ch == '"':
            q = not q
        elif ch == sep and not q:
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    out.append("".join(cur))
    return out


def shape(text):
    """Does the payload parse as the thing its shape claims to be?"""
    t = (text or "").strip()
    if t[:1] in "{[":
        try:
            json.loads(t)
            return "json", "valid JSON"
        except Exception as e:
            return "bad", "claims JSON, does not parse: %s" % str(e)[:60]
    lines = [l for l in t.splitlines() if l.strip()]
    if len(lines) >= 2:
        sep = "\t" if lines[0].count("\t") > lines[0].count(",") else ","
        head = len(_split(lines[0], sep))
        # A header of two or more columns, and a body that agrees with it. The
        # first version asked only whether line one contained a comma, and
        # called three of the kit's AI-prompt exports -- English prose with
        # commas in it -- ragged tables. A comma is not a column.
        widths = [len(_split(l, sep)) for l in lines[:200]]
        modal = max(set(widths), key=widths.count)
        agree = widths.count(modal)
        # A table is a payload most of whose rows agree on a width of three or
        # more. Prose does not: an AI prompt with commas in it has a width that
        # wanders, and asking only whether line one had a comma called three of
        # the kit's prompt exports ragged tables.
        if modal >= 3 and agree >= max(2, 0.6 * len(widths)):
            if agree < len(widths):
                return "bad", ("ragged table: %d of %d rows are not %d fields"
                               % (len(widths) - agree, len(widths), modal))
            return "table", "%d rows x %d columns" % (len(lines) - 1, modal)
    return "text", "%d line(s) of text" % len(lines)


def declined(before, after):
    """Did the page refuse, and say so?

    Most of what the first run of this tool called wrong was a control
    correctly declining: an export with nothing saved to export, a spore swatch
    pressed before a collection exists, an Add with nothing selected to add.
    Reading a correct refusal as a wrong result is the ADR-100 defect wearing
    the oracle's clothes -- judging a control from a state where its effect
    could not appear.

    So a refusal is allowed, on one condition, which is the rule this kit
    already holds itself to everywhere else: it has to TELL the user. A control
    that declines with a toast is doing its job. A control that declines in
    silence is indistinguishable from one that is broken, to the harness and to
    the person holding the phone, and stays a finding.
    """
    return after.get("toasts", 0) > before.get("toasts", 0)


def _decline(before, after, what):
    return ("changed", "decline", what,
            "declined and said so: %s" % (after.get("toastText") or "(a toast)")[:60])


def oracle(a, before, after, cx):
    k, label = a["kind"], a["label"] or ""

    if k == "tab":
        want = a.get("target")
        if after["onp"] != 1:
            return "wrong", "tab", "exactly one pane open", "%d open" % after["onp"]
        got = cx.get("route")
        if want and got != want:
            return "wrong", "tab", "pane %s open" % want, "pane %s open" % got
        return "verified", "tab", "pane %s open, and only it" % (want or got), str(got)

    if k == "step_btn" or (k == "action_btn" and label.strip() in ("+", "-", "−")):
        b, c = cx.get("step_before"), cx.get("step_after")
        if not b or not c:
            return None
        if b.get("number") is None or c.get("number") is None:
            # Not "no opinion": a stepper showing something that is not a number
            # is a result worth reporting, and staying quiet about it is how the
            # first version of this lost a live control to NaN.
            return ("wrong", "step", "a stepper holds a number",
                    "before %r, after %r" % (b.get("raw"), c.get("raw")))
        up = "+" in label or cx.get("direction") == "up"
        d = c["number"] - b["number"]
        if d == 0:
            return "wrong", "step", "%s moves the number" % (label or "?"), \
                   "stayed at %s" % b["raw"]
        if (d > 0) != up:
            return ("wrong", "step", "%s changes it by %s" % (label or "?", "+" if up else "-"),
                    "%s -> %s" % (b["raw"], c["raw"]))
        return "verified", "step", "%s to %s" % ("up" if up else "down", c["raw"]), "%+g" % d

    if k in ("step_val", "text_in", "field_in"):
        want, got = cx.get("typed"), cx.get("held")
        if want is None or got is None:
            return None
        if got == want:
            return "verified", "field", "holds %s" % want, got
        if got.strip() == "":
            return "wrong", "field", "holds %s" % want, "empty -- the entry was discarded"
        return "changed", "field", "holds %s" % want, "reformatted to %s" % got[:24]

    if k == "slider":
        s, want = cx.get("slide_after"), str(cx.get("slide_want"))
        if not s:
            return None
        if s.get("value") != want:
            return "wrong", "slider", "value %s" % want, "value %s" % s.get("value")
        if want and want in (s.get("shown") or ""):
            return "verified", "slider", "displays %s" % want, s["shown"][:40]
        return ("changed", "slider", "displays %s" % want,
                "widget shows: %s" % ((s.get("shown") or "")[:40] or "(no number)"))

    if k == "select":
        want, got = cx.get("opt_want"), cx.get("sel_after")
        if want is None or got is None:
            return None
        if got == want["value"]:
            return "verified", "select", "reports %s" % (want["label"] or want["value"]), got
        return "wrong", "select", "reports %s" % want["value"], got

    if k == "pick_search":
        p, q, full = cx.get("pick_after"), cx.get("query"), cx.get("pick_full")
        r = cx.get("pick_restored")
        if not p or not q or not full:
            return None
        if cx.get("undiscriminating"):
            return ("changed", "filter",
                    "a query some options match and others do not",
                    "%d option(s) offered, none of which any query separates"
                    % full["visible"])
        if p["visible"] == 0:
            return "wrong", "filter", "options matching %s" % q, "filtered to nothing"
        if p["visible"] >= full["visible"]:
            return ("wrong", "filter", "fewer than %d options" % full["visible"],
                    "still %d -- nothing was filtered" % p["visible"])
        bad = [l for l in p["labels"] if q.lower() not in l.lower()]
        if bad:
            return ("wrong", "filter", "every survivor matches %s" % q,
                    "%d do not, e.g. %s" % (len(bad), bad[0][:40]))
        if r and r["visible"] != full["visible"]:
            return ("wrong", "filter", "clearing restores %d" % full["visible"],
                    "restored %d" % r["visible"])
        return ("verified", "filter",
                "%d of %d match %s, all restored" % (p["visible"], full["visible"], q), "ok")

    if k in ("pick_opt", "dial_btn", "chip", "kopt", "ck", "cv", "swc"):
        b, c = cx.get("grp_before"), cx.get("grp_after")
        if not b or not c:
            return None
        if b.get("meSelected") and not c.get("meSelected"):
            return "verified", "option", "toggles off", "off"
        if not b.get("meSelected") and c.get("meSelected"):
            if b.get("selected", 0) <= 1 and c.get("selected") == 1:
                return "verified", "option", "selects, alone in its group", \
                       "1 of %d on" % c.get("size")
            return "verified", "option", "selects", \
                   "%d of %d on" % (c.get("selected"), c.get("size"))
        if not c.get("meSelected"):
            if declined(before, after):
                return _decline(before, after, "clicking an option selects it")
            return ("wrong", "option", "clicking an option selects it",
                    "still not selected (%d of %d on), and nothing told the user why"
                    % (c.get("selected"), c.get("size")))
        return None

    if k == "action_btn":
        v = verb(label)
        if v == "add":
            up, _ = _rows(before, after)
            if up and after["els"] > before["els"]:
                return "verified", "add", "one more row", "+1 %s" % up[0]
            if declined(before, after):
                return _decline(before, after, "one more row")
            return ("wrong", "add", "one more row",
                    "no repeated element gained one, and nothing told the user why")
        if v == "remove":
            _, down = _rows(before, after)
            if down and after["els"] < before["els"]:
                return "verified", "remove", "one fewer row", "-1 %s" % down[0]
            if declined(before, after):
                return _decline(before, after, "one fewer row")
            return ("wrong", "remove", "one fewer row",
                    "no repeated element lost one, and nothing told the user why")
        if v == "clear":
            # "no field left holding anything" was the first version of this and
            # it was wrong about a real control: breeding-bench's Clear trial
            # empties the trial, not the page, and was reported as a defect for
            # being correctly scoped. A label does not say how far a clear
            # reaches, so the expectation is the part that does not depend on
            # knowing: a clear takes entries away and never puts any back.
            if before["filled"] == 0:
                return None
            if after["filled"] < before["filled"]:
                return ("verified", "clear", "fewer fields left holding anything",
                        "%d -> %d" % (before["filled"], after["filled"]))
            if declined(before, after):
                return _decline(before, after, "fewer fields left holding anything")
            if _moved(before, after):
                # field-notebook's Reset resets the stopwatch and its Clear
                # empties the quadrat list. Both were reported as failing to
                # clear the form, which they never promised to do. A label says
                # that something is cleared, not what -- so the expectation
                # retreats to the part a label can carry, and the finding is
                # kept for a clear that clears nothing at all.
                return ("changed", "clear", "fewer fields left holding anything",
                        "cleared something other than the form fields")
            return ("wrong", "clear", "something is cleared",
                    "%d fields before and after, and nothing else changed either"
                    % before["filled"])
        if v == "undo":
            if after["thash"] in cx.get("history", ()):
                return "verified", "undo", "returns to an earlier state", \
                       "matched a state this run had been in"
            if not _moved(before, after):
                return "wrong", "undo", "returns to an earlier state", "nothing changed"
            return ("changed", "undo", "returns to an earlier state",
                    "changed to a state not seen in this run")
        if v == "print":
            if any(o["k"] == "print" for o in cx.get("out") or []):
                return "verified", "print", "the page asks to print", "print()"
            if declined(before, after):
                return _decline(before, after, "the page asks to print")
            return "wrong", "print", "the page asks to print", "no print call"
        if v == "export":
            pay = [o for o in (cx.get("out") or [])
                   if o["k"] in ("clipboard", "download", "copy")]
            if not pay:
                if declined(before, after):
                    return _decline(before, after, "a payload leaves the page")
                return ("wrong", "export", "a payload leaves the page",
                        "nothing was copied or downloaded, and nothing told the "
                        "user why")
            text = max((o["text"] for o in pay), key=len)
            if not text.strip():
                return "wrong", "export", "a payload with something in it", "empty payload"
            sh, note = shape(text)
            if sh == "bad":
                return "wrong", "export", "a payload that parses", note
            seeds = cx.get("seeds") or []
            hit = [s for s in seeds if s in text]
            if seeds and not hit:
                if not cx.get("committed"):
                    # Nothing was ever saved, so an export of saved records is
                    # right to contain none of it. Claiming otherwise would be
                    # asserting that a form and a record are the same thing.
                    return ("changed", "export",
                            "contains what was typed into the form",
                            "%s, %d chars -- nothing had been saved to export, "
                            "so this is unjudged" % (note, len(text)))
                return ("wrong", "export", "contains what was typed into the form",
                        "%s, %d chars, none of the %d entered values"
                        % (note, len(text), len(seeds)))
            return ("verified", "export",
                    "%s carrying %d entered value(s)" % (note, len(hit)),
                    "%d chars" % len(text))
    return None


# ---------------------------------------------------------------------------
# Driving one affordance, entirely through published actions
# ---------------------------------------------------------------------------

def _value_for(a, tick, seeds):
    t = (a.get("type") or "").lower()
    if t == "date":
        return "2026-06-%02d" % (1 + tick % 28)
    if t == "number":
        return str(1 + tick % 9)
    if a.get("kind") == "step_val":
        # A stepper holds a number. Typing a sentinel into it is not something a
        # user does; it is something a careless client does, and it makes the
        # widget unjudgeable for the rest of the run -- the next press computes
        # NaN from it, the press after that computes NaN from NaN, and a live
        # plus button reports as leaving no trace. The harness was creating the
        # state it then failed to measure, which is the ADR-100 defect in a new
        # place.
        return str(2 + tick % 7)
    s = SENTINEL % (tick % 1000)
    seeds.append(s)
    return s


def _query_from(labels):
    """A query worth judging a filter by is one that tells the options APART.

    Returns (query, discriminating). A picker with one option cannot be filtered
    below one, and a query every option matches correctly removes nothing --
    both were reported as filters that failed to filter, which is the harness
    asking a question the control was never given the material to answer.
    """
    labels = list(labels or ())
    if len(labels) < 2:
        return (labels[0][:5] if labels else None), False
    best = None
    for l in labels:
        for w in re.findall(r"[A-Za-z]{4,}", l):
            q = w[:5].lower()
            if q in ("true", "none", "with", "from", "that"):
                continue
            hits = sum(1 for x in labels if q in x.lower())
            if 0 < hits < len(labels):
                return w[:5], True
            if best is None:
                best = w[:5]
    return best, False


def drive(cl, a, res, cx0):
    rec = {"selector": a["selector"], "kind": a["kind"], "label": a["label"],
           "pane": a["pane"]}
    kind = a["kind"]
    if kind in EXCLUDED:
        rec["why"] = EXCLUDED[kind][:120]
        res["excluded"].append(rec)
        return
    action = DRIVER.get(kind)
    if action is None:
        rec["why"] = "no published action drives a %s" % kind
        res["failed"].append(rec)
        return
    sel = a["selector"]
    cx = {"seeds": cx0["seeds"], "history": cx0["history"],
          "committed": cx0.get("committed", False)}

    # ---- reach it and read the state its verdict will be computed from -----
    try:
        if a["pane"]:
            try:
                cl.do("show-pane", pane=a["pane"])
            except HarnessError:
                # A pane no tab opens is not a failure to drive: experiment-guide
                # reveals its designer pane another way, and 54 of its controls
                # were written off as undriveable because the harness insisted on
                # a route the page does not use. Let visibility decide instead.
                pass
        # Re-observe before judging. A selector is positional within its kind,
        # and these widgets rebuild: by the time action_btn:30 is driven it may
        # no longer be the Copy .eco lines button that was discovered under that
        # name. The first version carried the discovery-time label into the
        # verdict, so an export oracle was applied to a quadrat arrow and
        # reported three live exports as producing nothing -- the harness
        # judging one control by another control's promise.
        snap = cl.snapshot()
        cx0["controls"] = snap["controls"]
        fresh = None
        for c in snap["controls"]:
            if c["selector"] == sel:
                fresh = c
                break
        if fresh is not None:
            a = fresh
        before = cl.page_state()
        cbefore = cl.control(sel)
    except HarnessError as e:
        if e.code == "not_found":
            # The page rebuilt between the snapshot and the read. That is a fact
            # about the page, not an affordance the harness could not drive, and
            # filing it as a failure inflated the one bucket that means "this
            # tool could not do its job".
            rec["why"] = "the page rebuilt it away before it could be read"
            res["hidden"].append(rec)
            return
        rec["why"] = "unreadable before the action"
        rec["got"] = "%s: %s" % (e.code, e.message[:120])
        res["failed"].append(rec)
        return
    if not cbefore:
        rec["why"] = "the page rebuilt it away before it could be driven"
        res["hidden"].append(rec)
        return
    if not cbefore.get("visible"):
        rec["why"] = "not visible with its own pane open"
        res["hidden"].append(rec)
        return

    # ---- put it in a state where its effect can show ----------------------
    prep = ""
    try:
        if kind == "step_btn":
            other = "down" if "+" in (a["label"] or "") else "up"
            cl.do("press-step", selector=sel, direction=other)
            prep = " (stepped the other way first)"
            cbefore = cl.control(sel)
            before = cl.page_state()
        elif kind == "action_btn" and (a["label"] or "").strip() in ("+", "-", "\u2212"):
            # The kit grew bespoke plus and minus buttons before the Field Entry
            # Kit existed. One at its bound does nothing, correctly, and six of
            # them read as wired to nothing until they were given somewhere to
            # go -- the same correction ADR-100 made for fek steppers, which had
            # not been carried across to their older cousins.
            other = _opposite(cx0["controls"], a)
            if other:
                cl.do("activate", selector=other)
                prep = " (pressed the other way first)"
                cbefore = cl.control(sel)
                before = cl.page_state()
        elif kind in ("pick_opt", "dial_btn", "chip", "kopt", "ck", "cv", "swc") \
                and cbefore.get("group", {}).get("meSelected"):
            sib = _sibling(cx0["controls"], a)
            if sib:
                cl.do("activate", selector=sib)
                prep = " (group moved off it first)"
                cbefore = cl.control(sel)
                before = cl.page_state()
            else:
                prep = " (already selected, nothing to deselect it with)"
    except HarnessError:
        prep = " (could not be given room)"

    # ---- the action itself, with the typed argument it deserves -----------
    cx["step_before"] = cbefore.get("step")
    cx["grp_before"] = cbefore.get("group")
    kwargs, note = {}, ""
    try:
        if action == "show-pane":
            if not a.get("target"):
                rec["why"] = "a tab with no data-pane names no pane to open"
                res["failed"].append(rec)
                return
            cl.do("show-pane", pane=a["target"])
            note = "opened %s" % a["target"]
        elif action == "press-step":
            d = "up" if "+" in (a["label"] or "") else "down"
            cx["direction"] = d
            cl.do("press-step", selector=sel, direction=d)
            note = "pressed %s" % d
        elif action == "set-text":
            if kind == "pick_search":
                full = cbefore.get("picker") or {}
                q, discriminating = _query_from(full.get("labels"))
                if not q:
                    rec["why"] = "the picker offered no option to build a query from"
                    res["hidden"].append(rec)
                    return
                cx["pick_full"], cx["query"] = full, q
                cx["undiscriminating"] = not discriminating
                cl.do("set-text", selector=sel, value=q)
                note = "searched %s" % q
            else:
                cx0["tick"] += 1
                v = _value_for(a, cx0["tick"], cx0["seeds"])
                cx["typed"] = v
                cl.do("set-text", selector=sel, value=v)
                note = "entered %s" % v
        elif action == "choose-option":
            opts = cbefore.get("options") or []
            pick = None
            for o in opts:
                if o["value"] != (cbefore.get("value") or ""):
                    pick = o
                    break
            if pick is None:
                rec["why"] = "a select with one option offers nothing to choose"
                res["hidden"].append(rec)
                return
            cx["opt_want"] = pick
            cl.do("choose-option", selector=sel, value=pick["value"])
            note = "chose %s" % (pick["label"] or pick["value"])[:24]
        elif action == "set-slider":
            s = cbefore.get("slider") or {}
            lo = float(s.get("min") or 0)
            hi = float(s.get("max") or 100)
            cur = float(s.get("value") or lo)
            want = lo if abs(cur - hi) < 1e-9 else hi
            if abs(want - cur) < 1e-9:
                want = (lo + hi) / 2.0
            want = int(want) if float(want).is_integer() else want
            cx["slide_want"] = want
            cl.do("set-slider", selector=sel, value=want)
            note = "set to %s" % want
        else:
            cl.do("activate", selector=sel)
            note = "activated"
    except HarnessError as e:
        rec["why"] = "the action was refused"
        rec["got"] = "%s: %s" % (e.code, e.message[:140])
        res["failed"].append(rec)
        return

    # ---- read the result --------------------------------------------------
    try:
        after = cl.page_state()
        cafter = cl.control(sel) or {}
        cx["step_after"] = cafter.get("step")
        cx["grp_after"] = cafter.get("group")
        cx["held"] = cafter.get("value")
        cx["sel_after"] = cafter.get("value")
        cx["slide_after"] = cafter.get("slider")
        cx["route"] = cl.snapshot().get("route")
        cx0["controls"] = []  # stale the moment the action landed
        if kind == "pick_search":
            cx["pick_after"] = cafter.get("picker")
            cl.do("set-text", selector=sel, value="")
            r = cl.control(sel) or {}
            cx["pick_restored"] = r.get("picker")
        if kind == "action_btn" and verb(a["label"]) in ("export", "print"):
            # A page that builds its payload in a promise or a timeout has not
            # finished when the click returns. Collecting immediately reported
            # three live exports as producing nothing.
            time.sleep(0.15)
            after = cl.page_state()
            cx["out"] = cl.out("collect-output")["payloads"]
    except HarnessError as e:
        rec["why"] = "the page was unreadable after the action"
        rec["got"] = "%s: %s" % (e.code, e.message[:120])
        res["failed"].append(rec)
        return

    rec["note"] = note + prep
    cx0["history"].add(after["thash"])

    # ---- the verdict ------------------------------------------------------
    v = oracle(a, before, after, cx)
    if v is not None:
        verdict, name, expected, got = v
        rec["oracle"], rec["expected"], rec["got"] = name, expected, got
        res[verdict].append(rec)
        if verdict == "wrong":
            res["findings"].append("%s expected %s, got %s  [%s %s]"
                                   % (name, expected, got, sel, (a["label"] or "")[:28]))
    elif _moved(before, after):
        rec["oracle"] = "none"
        rec["why"] = "changed the page, but this kind carries no expectation to check"
        res["changed"].append(rec)
    else:
        rec["oracle"] = "trace"
        rec["why"] = "left no trace at all"
        res["dead"].append(rec)

    _invariants(a, after, res)


def _opposite(controls, a):
    """The plus for this minus, or the minus for this plus, in the same pane."""
    mine = (a["label"] or "").strip()
    want = "+" if mine in ("-", "\u2212") else "-"
    best = None
    for c in controls:
        if c["kind"] != "action_btn" or c["pane"] != a["pane"] or not c["visible"]:
            continue
        lab = (c["label"] or "").strip()
        if lab == want or (want == "-" and lab == "\u2212"):
            best = c["selector"]
            if abs(int(c["selector"].split(":")[1]) -
                   int(a["selector"].split(":")[1])) == 1:
                return c["selector"]
    return best


def _sibling(controls, a):
    """A selector in the same group that is not this one and is not selected."""
    for c in controls:
        if (c["pane"] == a["pane"] and c["kind"] == a["kind"]
                and c["selector"] != a["selector"] and not c["selected"]
                and c["visible"]):
            return c["selector"]
    return None


def _invariants(a, after, res):
    bad = []
    if after.get("junkTok") and after["junkTok"] != res.get("junk_on_load"):
        bad.append(("junk rendered", after["junk"]))
    if after.get("panes") and after.get("onp") != 1:
        bad.append(("%d panes visible" % after["onp"], ""))
    if after.get("overflow", 0) > 1:
        bad.append(("spills %dpx sideways" % after["overflow"],
                    ", ".join(after.get("wide") or [])))
    for e in after.get("errors") or []:
        bad.append(("uncaught", e))
    for why, got in bad:
        res["errors"].append("%s [%s %s]: %s"
                             % (why, a["selector"], (a["label"] or "")[:30], got))


# ---------------------------------------------------------------------------
# One page
# ---------------------------------------------------------------------------

def seed(cl, controls, cx0, res):
    """Give the page something to be about. An empty form exports an empty file
    perfectly correctly, and every question worth asking of an export needs a
    form with an answer in it."""
    n = 0
    for c in controls:
        if c["kind"] not in ("text_in", "field_in") or not c["visible"]:
            continue
        if n >= 40:
            break
        try:
            if c["pane"]:
                cl.do("show-pane", pane=c["pane"])
            cx0["tick"] += 1
            cl.do("set-text", selector=c["selector"],
                  value=_value_for(c, cx0["tick"], cx0["seeds"]))
            n += 1
        except HarnessError:
            continue
    # Filling a form is not the same as having a record, and an export of saved
    # records is right to contain nothing when nothing was saved. The first run
    # of this tool called four such exports wrong for that reason. So the seed
    # commits: it presses the adds, and then the saves.
    adds = saves = 0
    for c in controls:
        if c["kind"] != "action_btn" or not c["visible"]:
            continue
        v = verb(c["label"])
        if v == "add" and adds < 5:
            try:
                if c["pane"]:
                    cl.do("show-pane", pane=c["pane"])
                cl.do("activate", selector=c["selector"])
                adds += 1
            except HarnessError:
                pass
        elif SAVE_RE.search(c["label"] or "") and saves < 5:
            try:
                if c["pane"]:
                    cl.do("show-pane", pane=c["pane"])
                cl.do("activate", selector=c["selector"])
                saves += 1
            except HarnessError:
                pass
    cx0["committed"] = bool(saves or adds)
    res["seeded"] = {"fields": n, "adds": adds, "saves": saves,
                     "sentinels": len(cx0["seeds"]), "committed": cx0["committed"]}


def run_page(name, passes=3, url=None):
    started = time.time()
    res = {"page": name, "discovered": 0, "errors": [], "findings": [],
           "commands": 0, "seeded": {}}
    for v in VERDICTS:
        res[v] = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport=VIEWPORT)
        ctx.set_offline(True)
        ctx.add_init_script(H.STUBS)
        ctx.add_init_script(CATCH)
        pg = ctx.new_page()
        pg.set_default_timeout(H.ACT_TIMEOUT)
        pg.on("pageerror", lambda e: res["errors"].append("pageerror: " + str(e)[:200]))
        pg.goto(url or _kit.url(name), wait_until="domcontentloaded")
        pg.wait_for_timeout(400)

        token = "swarm-" + "s" * 24
        policy = Policy(token=token, allow=SWARM_POLICY, enabled=True)
        gw = Gateway(Registry([PagePlugin(pg, name)]), policy)
        cl = Client(gw, token)

        opening = cl.page_state()
        res["junk_on_load"] = opening.get("junkTok") or ""
        if opening.get("junk"):
            res["errors"].append("junk on load: " + opening["junk"])

        cx0 = {"tick": 0, "seeds": [], "history": set([opening["thash"]]),
               "controls": [], "committed": False}
        snap = cl.snapshot()
        cx0["controls"] = snap["controls"]
        seed(cl, snap["controls"], cx0, res)

        seen = set()
        res["passes"] = 0
        for _ in range(passes):
            res["passes"] += 1
            snap = cl.snapshot()
            cx0["controls"] = snap["controls"]
            fresh = [c for c in snap["controls"] if c["selector"] not in seen]
            if not fresh:
                break
            for c in fresh:
                seen.add(c["selector"])
            for c in fresh:
                drive(cl, c, res, cx0)
        res["discovered"] = len(seen)
        res["commands"] = cl.n
        res["policy"] = dict(policy.allow)
        ctx.close()
        b.close()
    res["secs"] = round(time.time() - started, 1)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*")
    ap.add_argument("-j", type=int, default=2)
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--passes", type=int, default=3)
    a = ap.parse_args()

    names = a.pages or sorted(os.path.basename(p)
                              for p in glob.glob(os.path.join(_kit.ROOT, "docs", "*.html")))
    print("swarm -- %d page(s), %d at a time, %dx%d offline, every action through "
          "the gateway" % (len(names), a.j, VIEWPORT["width"], VIEWPORT["height"]))
    print("policy: " + ", ".join(k for k, v in sorted(SWARM_POLICY.items()) if v))
    print("-" * 92)
    out = []
    with cf.ThreadPoolExecutor(max_workers=a.j) as ex:
        for r in ex.map(run_page, names, [a.passes] * len(names)):
            out.append(r)
            n = dict((k, len(r[k])) for k in VERDICTS)
            print("%-28s %4d ok %3d WRONG %4d chg %3d dead %3d hid %3d fail %4d excl "
                  "%5d cmd %5.1fs"
                  % (r["page"], n["verified"], n["wrong"], n["changed"], n["dead"],
                     n["hidden"], n["failed"], n["excluded"], r["commands"], r["secs"]))
    out.sort(key=lambda r: r["page"])

    tot = dict((k, sum(len(r[k]) for r in out)) for k in VERDICTS)
    disc = sum(r["discovered"] for r in out)
    cmds = sum(r["commands"] for r in out)
    print("-" * 92)
    print("discovered %d = %s  %s"
          % (disc, " + ".join("%s %d" % (k, tot[k]) for k in VERDICTS),
             "OK" if disc == sum(tot.values()) else "<-- UNACCOUNTED"))
    judged = tot["verified"] + tot["wrong"]
    print("checked against a stated expectation: %d of %d driven (%d%%); "
          "%d only observed to change"
          % (judged, judged + tot["changed"],
             (100 * judged) // max(1, judged + tot["changed"]), tot["changed"]))
    print("commands issued through the gateway: %d" % cmds)

    rows = [(r["page"], f) for r in out for f in r["findings"]]
    if rows:
        print("\nRESULTS THAT WERE NOT WHAT THE CONTROL PROMISES (%d)" % len(rows))
        for page, f in rows[:80]:
            print("  %-26s %s" % (page, f[:120]))
    rows = [(r["page"], d) for r in out for d in r["dead"]]
    if rows:
        print("\nLEFT NO TRACE AT ALL (%d)" % len(rows))
        for page, d in rows[:40]:
            print("  %-26s %-11s %s" % (page, d["kind"], (d["label"] or "")[:40]))
    rows = [(r["page"], e) for r in out for e in r["errors"]]
    if rows:
        print("\nBROKEN INVARIANTS (%d)" % len(rows))
        for page, e in rows[:40]:
            print("  %-26s %s" % (page, e[:110]))

    json.dump({"at": int(time.time()), "viewport": VIEWPORT,
               "excluded_kinds": EXCLUDED, "policy": SWARM_POLICY,
               "totals": dict(tot, discovered=disc, commands=cmds,
                              invariant_breaks=sum(len(r["errors"]) for r in out)),
               "pages": out},
              io.open(a.ledger, "w", encoding="utf-8"), indent=1)
    print("\nwrote %s" % a.ledger)
    return 0


if __name__ == "__main__":
    sys.exit(main())
