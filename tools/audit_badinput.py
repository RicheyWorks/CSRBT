# -*- coding: utf-8 -*-
"""The number box that shows text and reads as blank (ADR-151).

ADR-150 found one of these by hand. `<input type=number>` has a value the page
reads and a raw keystroke buffer the page cannot see, and when the browser
cannot parse the buffer the value it hands the page is the EMPTY STRING -- the
same string a box nobody touched hands it. So a page that treats blank as
meaningful ("no seed given, use 42"; "not filled in yet, say nothing") cannot
tell a user who typed something it rejected from a user who typed nothing. The
box shows their characters. The page reads a blank. Nobody is told.

Only `validity.badInput` separates the two, because badInput is about the
buffer rather than the value, and it is the one signal an ASSIGNMENT cannot
produce -- which is why nothing in this kit could ask the question until
type-text existed. ADR-150 fixed three fields on one page and wrote the rest
down as a worklist: "anywhere a page treats a blank field as meaningful the
same silence is possible and nothing here has looked". This is the looking.

WHAT IS MEASURED, AND IT IS AN EXPERIMENT WITH A CONTROL

Per number box, the page is put in three states and read each time:

    GOOD    a value inside the box's own min/max, ASSIGNED (set-text)
    BLANK   the empty string, ASSIGNED
    BAD     "3e" -- a number the user has started and not finished -- TYPED
            (type-text), with validity.badInput confirmed TRUE afterwards

and the page's rendered report is compared:

    GOOD != BLANK   the page READS THIS BOX LIVE. Without this, a box whose
                    figure only appears when a button is pressed would read as
                    a page that cannot tell anything apart, and the worklist
                    would be four hundred lines of pages doing nothing wrong.
                    This is the control, and it is why the finding is a finding.
    BLANK != BAD    the page CAN TELL THEM APART -- it checks badInput, or
                    checkValidity, or marks the control aria-invalid. Fine.
    BLANK == BAD    CANNOT TELL. The page is demonstrably reading this box, and
                    a rejected keystroke buffer reaches it as an empty one.

A box the browser accepts the token into (badInput never goes true) has no
subject and is reported as such rather than counted: the experiment did not
run. A box the entry leaves unreachable -- hidden, covered, disabled -- is
reported the same way, because type-text refuses those AT ONCE by design.

WHAT IS COMPARED IS WHAT THE PAGE RENDERS

The report is every element with an id, minus controls and entry hosts (the
same rule audit_readable uses, and for the same reason), PLUS each element's
class list, aria-invalid and hidden/disabled state -- because marking the box
red is telling them apart just as much as printing a sentence is, and a text-
only comparison would call a page that does it silent. Elements are keyed by id
where they have one and by where they sit in the document where they do not, so
a page that answers in an unnamed element is not called silent by the kit's own
naming convention -- and each key belongs to one element, so a clock takes only
its own key out of the comparison and not every card around it.

Ids that move on their own are dropped first: the page is read twice at rest
and anything that differs between the two readings is a clock or an animation,
not an answer, and leaving it in would make every box on that page look like
it was being told apart.

    python3 tools/audit_badinput.py                 # the table and the worklist
    python3 tools/audit_badinput.py --page releve.html
    python3 tools/audit_badinput.py --check         # symmetry; a rise fails either way
    python3 tools/audit_badinput.py --raise-floors  # after a page is fixed, record it
    python3 tools/audit_badinput.py --declare PAGE:ID --reason "..."

A RATCHET DOWNWARD, AND A DECLARED EXEMPTION

The ceiling is the number of boxes a page cannot tell apart. It may not go UP:
a page that grows a live number box which reads a rejected buffer as blank
fails the day it does. It comes down as pages are fixed. A box that genuinely
should not care is DECLARED with a reason in the ledger, one line each, the
same shape as the mutant ledger's known equivalents -- so the list of things
this audit is choosing not to care about is readable, and short.

WHAT THIS IS NOT

It is not a claim that a page which tells them apart says the RIGHT thing --
only that it says a different thing. It is not a claim about `type=text` boxes
that hold numbers: those have no badInput, the page gets the characters, and
there is nothing here to be blind to. And it does not press the page's buttons:
a box read only on submit is INERT to this audit, which is a fact about how the
box was measured and is stated rather than hidden.
"""
import argparse, glob, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import harness as H
import audit_states as S
import harness_plugin_page as PP

LEDGER = os.path.join(HERE, "badinput_ledger.json")

# The token typed into every box. It is a number the user has STARTED and not
# finished: Chromium keeps "3e" in the buffer, hands the page "" and sets
# badInput. A token the browser drops on the way in (letters, for one) would
# leave badInput FALSE and there would be nothing to measure -- so the audit
# confirms badInput afterwards rather than assuming this token works
# everywhere, and says so when it does not.
TOKEN = "3e"

# WHERE AN ELEMENT IS, WHEN IT HAS NO NAME. An id is how the rest of this kit
# names a figure, and a page that answers in an element carrying none would read
# as silent against an id-keyed comparison -- the audit calling a page blind for
# the kit's own naming convention rather than for anything the reader would see.
# The FEK's own bad-buffer line is exactly that element, on seven pages.
PATH_FN = r"""
  const path = e => { const p = [];
    for (let n = e; n && n.tagName && p.length < 10; n = n.parentElement) {
      const sib = n.parentElement ? [...n.parentElement.children].indexOf(n) : 0;
      p.unshift(n.tagName.toLowerCase() + sib); }
    return p.join("/"); };
"""

# What the page RENDERS, keyed so that each key belongs to ONE element:
#
#   t:  the text an element holds DIRECTLY -- its own text nodes, not its
#       children's. A parent's text changes whenever a child's does, and keying
#       by the whole subtree would report one sentence against every card
#       around it; worse, a page with a clock in it would have every ancestor of
#       that clock read as moving on its own, and the whole page would drop out
#       of the comparison. Controls and the divs the entry kit mounts them into
#       are left out, the same rule audit_readable uses.
#   m:  the state marks a page uses instead of a sentence -- class, aria-invalid,
#       hidden, disabled -- for every element including the controls, because
#       marking the box red is telling them apart as surely as printing a line
#       is. A control's VALUE is not in here: it is what was typed, not what the
#       page said about it.
REPORT_JS = r"""
() => {
  %s
  const out = {};
  let n = 0;
  document.querySelectorAll("*").forEach(e => {
    if (++n > 6000) return;
    const t = (e.tagName || "").toLowerCase();
    if (t === "script" || t === "style" || t === "head") return;
    const at = e.id ? ("#" + e.id) : ("@" + path(e));
    out["m:" + at] = [e.className || "", e.getAttribute("aria-invalid") || "",
                      e.hidden ? "h" : "", e.disabled ? "d" : ""].join("|");
    const control = e.hasAttribute("data-h") ||
                    t === "input" || t === "textarea" || t === "select" || t === "option";
    if (control || e.querySelector("[data-h]")) return;
    let txt = "";
    for (const k of e.childNodes) if (k.nodeType === 3) txt += k.nodeValue;
    txt = txt.replace(/\s+/g, " ").trim();
    if (txt) out["t:" + at] = txt.slice(0, 4000);
  });
  return out;
}
""" % PATH_FN

# Every number box the swarm has stamped, with the bounds its own attributes
# declare -- the GOOD value is picked from those rather than from a constant,
# because a box that only accepts 0..1 would read a 7 as out of range and the
# control reading would be about the range and not about the box.
FIELDS_JS = r"""
() => {
  %s
  return [...document.querySelectorAll('input[type="number"][data-h]')].map(e => ({
  h: e.getAttribute("data-h"), id: e.id || "",
  // A NAME THAT SURVIVES THE NEXT STAMP. data-h is kind:index, re-issued every
  // time the swarm discovers, so a box keyed by it is a different box in the
  // next state and the same box gets measured twice under two names.
  key: e.id || e.name || (e.getAttribute("aria-label") || "").trim() || ("@" + path(e)),
  label: (e.getAttribute("aria-label") || e.getAttribute("placeholder") || e.name || "").slice(0, 60),
  min: e.getAttribute("min"), max: e.getAttribute("max"), step: e.getAttribute("step"),
  value: String(e.value)
  })); }
""" % PATH_FN

BADINPUT_JS = r"""
(sel) => { const e = document.querySelector('[data-h="' + sel + '"]');
           return e ? {value: String(e.value), bad: !!(e.validity && e.validity.badInput)}
                    : null; }
"""


def docs_dir():
    return os.environ.get("CSRBT_DOCS_DIR") or os.path.join(ROOT, "docs")


def pages():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(docs_dir(), "*.html")))


def load():
    if os.path.isfile(LEDGER):
        try:
            return json.load(io.open(LEDGER, encoding="utf-8"))
        except ValueError:
            pass
    return {"_comment": "Written by tools/audit_badinput.py. Per page: the live number boxes "
                        "that read a rejected keystroke buffer as an empty one, and the ceiling "
                        "that count may not rise above. Exemptions are declared with a reason "
                        "(ADR-151).",
            "pages": {}}


def save(state):
    io.open(LEDGER, "w", encoding="utf-8").write(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def declared_of(state, name):
    return dict((k, v) for k, v in
                (state.get("pages", {}).get(name, {}).get("declared") or {}).items())


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def good_value(f):
    """A value the box's own attributes accept. -> str"""
    lo, hi = _num(f.get("min")), _num(f.get("max"))
    if lo is not None and hi is not None and hi >= lo:
        v = lo + (hi - lo) / 2.0
    elif lo is not None:
        v = lo + 1.0
    elif hi is not None:
        v = hi - 1.0
    else:
        v = 7.0
    st = _num(f.get("step"))
    if st and st >= 1:
        v = round(v / st) * st
        if lo is not None and v < lo:
            v = lo
        if hi is not None and v > hi:
            v = hi
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return ("%.4f" % v).rstrip("0").rstrip(".")


def _report(pg):
    S._settle(pg)
    return pg.evaluate(REPORT_JS) or {}


def _diff(a, b, drop):
    """Which keys differ between two readings, ignoring the ones that move on
    their own. -> sorted list"""
    keys = (set(a) | set(b)) - drop
    return sorted(k for k in keys if a.get(k) != b.get(k))


# THE PAGE GETS EVERY CHANCE TO SAY SOMETHING. A verdict only ever moves UP
# this ladder: a box hidden behind a tab is not a box that says nothing, a box
# that is inert while the page holds no rows may be live once the entry has put
# some in, and -- the one that matters -- a box that cannot tell them apart in
# the state it was first asked in may tell them apart in another. The finding
# is "in NO state this audit could put the page in did it say a different
# thing", so a box is re-asked until it TELLS, or until the retries run out.
RANK = {"": 0, "unreachable": 1, "inert": 2, "no-bad-input": 3, "cannot-tell": 4, "tells": 5}
TRIES = 4


def _key(f):
    return f.get("key") or f["id"] or ("h:" + f["h"])


def _probe_state(pg, plug, seen, unstable, budget):
    """Measure every number box on the page RIGHT NOW that is still open."""
    try:
        pg.evaluate(H.DISCOVER, H.KINDS)
    except Exception:
        return
    for f in pg.evaluate(FIELDS_JS) or []:
        k = _key(f)
        was = seen.get(k)
        if was is not None and (RANK[was["verdict"]] >= 5 or was.get("tries", 1) >= TRIES):
            continue
        if budget["left"] <= 0:
            return
        budget["left"] -= 1
        rec = _one(pg, plug, f, unstable)
        # AN UNREACHABLE BOX WAS NEVER ASKED. Spending one of its tries on a
        # state where type-text refused to focus it would retire a box the audit
        # has not put a single question to -- and the states that reveal a box
        # are exactly the ones that come last.
        spent = (was or {}).get("tries", 0) + (0 if rec["verdict"] == "unreachable" else 1)
        rec["tries"] = spent
        if was is None or RANK[rec["verdict"]] >= RANK[was["verdict"]]:
            seen[k] = rec
        else:
            was["tries"] = spent


def _one(pg, plug, f, unstable):
    """The experiment, on one box. -> record"""
    rec = {"h": f["h"], "id": f["id"], "key": _key(f), "label": f["label"],
           "verdict": "", "why": ""}
    was = f["value"]
    try:
        plug.execute("set-text", {"selector": f["h"], "value": good_value(f)})
        g = _report(pg)
        plug.execute("set-text", {"selector": f["h"], "value": ""})
        b = _report(pg)
        plug.execute("type-text", {"selector": f["h"], "value": TOKEN})
        st = pg.evaluate(BADINPUT_JS, f["h"]) or {}
        x = _report(pg)
    except Exception as exc:
        rec["verdict"] = "unreachable"
        rec["why"] = str(exc).split("\n")[0][:120]
        return rec
    finally:
        try:
            plug.execute("set-text", {"selector": f["h"], "value": was})
            S._settle(pg)
        except Exception:
            pass
    if not st.get("bad"):
        rec["verdict"] = "no-bad-input"
        rec["why"] = ("the browser did not reject %r here -- value %r, badInput false; "
                      "nothing to be blind to" % (TOKEN, st.get("value")))
        return rec
    live = _diff(g, b, unstable)
    told = _diff(b, x, unstable)
    rec["live"], rec["told"] = live[:6], told[:6]
    if not live:
        rec["verdict"] = "inert"
        rec["why"] = "nothing the page renders changed between a real number and none"
    elif told:
        rec["verdict"] = "tells"
    else:
        rec["verdict"] = "cannot-tell"
    return rec


def measure(pg, name, tasks_dir=None, budget=260):
    """-> {"task", "fields": [...], "unstable": n, "states": n}

    EVERY STATE, NOT THE LAST ONE. The first draft measured the page where the
    entry left it and reported twelve of the experiment guide's twenty boxes as
    unreachable -- true of that moment and a fact about the audit, not the page.
    The states are walked the way audit_states walks them, the entry included,
    and a box is asked again in each state until it gives an answer that cannot
    be improved on."""
    pg.evaluate(S.OPEN_DETAILS_JS)
    S._settle(pg)
    # WHAT MOVES ON ITS OWN IS NOT AN ANSWER. Two readings at rest, 300 ms
    # apart: a clock, a marquee or a css animation differs between them, and
    # left in, every box on that page would look like it was being told apart.
    r0 = _report(pg)
    pg.wait_for_timeout(300)
    r1 = _report(pg)
    unstable = set(k for k in (set(r0) | set(r1)) if r0.get(k) != r1.get(k))

    plug = PP.PagePlugin(pg, name)
    seen, budget = {}, {"left": budget}
    states = [0]

    def probe():
        states[0] += 1
        _probe_state(pg, plug, seen, unstable, budget)
        return None

    for _state, _r in S.each_state(pg, name, probe, entered=True):
        pass
    ent = getattr(pg, "_audit_entered", None)
    return {"task": (ent or {}).get("task"), "driven": (ent or {}).get("driven", 0),
            "fields": [seen[k] for k in sorted(seen)], "unstable": len(unstable),
            "states": states[0]}


def walk(only=None, tasks_dir=None):
    from playwright.sync_api import sync_playwright
    out = {}
    names = [only] if only else pages()
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport=H.VIEWPORT)
        ctx.set_offline(True)
        ctx.add_init_script(H.STUBS)
        pg = ctx.new_page()
        for name in names:
            url = "file://" + os.path.join(docs_dir(), name).replace(os.sep, "/")
            try:
                pg.goto(url, wait_until="domcontentloaded")
                pg.wait_for_timeout(250)
                out[name] = measure(pg, name, tasks_dir)
            except Exception as exc:
                out[name] = {"error": str(exc).split("\n")[0][:140], "fields": []}
        ctx.close()
        b.close()
    return out


def blind(r, declared):
    """The boxes on the worklist: live, rejected the token, and said nothing."""
    return [_key(f) for f in r.get("fields", [])
            if f.get("verdict") == "cannot-tell" and _key(f) not in declared]


def counts(r):
    c = {}
    for f in r.get("fields", []):
        c[f.get("verdict", "?")] = c.get(f.get("verdict", "?"), 0) + 1
    return c


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="one page")
    ap.add_argument("--check", action="store_true",
                    help="accepted for symmetry with the kit's other ratchets; a page above its "
                         "ceiling exits non-zero with or without it")
    ap.add_argument("--raise-floors", action="store_true",
                    help="record today's reading as the ceiling wherever it is LOWER (this "
                         "ratchet runs downward: the flag keeps the name the kit's others use)")
    ap.add_argument("--declare", metavar="PAGE:ID",
                    help="declare one box exempt, with a reason (needs --reason)")
    ap.add_argument("--reason", default="", help="why a box is exempt")
    ap.add_argument("--names", type=int, default=6, help="how many blind boxes to name")
    ap.add_argument("--json", action="store_true", help="the whole reading, for a suite to read")
    a = ap.parse_args(argv)
    state = load()
    ledger = state.setdefault("pages", {})

    if a.declare:
        if ":" not in a.declare:
            print("--declare takes PAGE:ID, e.g. releve.html:rvCover")
            return 2
        page, eid = a.declare.split(":", 1)
        if not a.reason.strip():
            print("declaring a box exempt needs --reason: it goes into the ledger, and a list of "
                  "boxes\nthis audit is choosing not to care about is only useful if each line "
                  "says why")
            return 2
        ledger.setdefault(page, {}).setdefault("declared", {})[eid] = a.reason.strip()
        save(state)
        print("%s: %s declared exempt" % (page, eid))
        return 0

    got = walk(a.page)
    if a.json:
        print(json.dumps(got, indent=1, sort_keys=True))
        return 0
    print("%-30s %11s %6s %6s %6s %6s   %s"
          % ("PAGE", "CANNOT TELL", "tells", "inert", "unrch", "no-bad",
             "live number boxes that read a rejected buffer as blank"))
    print("-" * 122)
    tot = dict(blind=0, tells=0, inert=0, unreachable=0, nb=0)
    above = []
    for name in sorted(got):
        r = got[name]
        if r.get("error"):
            print("%-30s %11s %6s %6s %6s %6s   %s"
                  % (name, "-", "-", "-", "-", "-", r["error"]))
            continue
        if not r.get("fields"):
            continue
        dec = declared_of(state, name)
        bad = blind(r, dec)
        c = counts(r)
        tot["blind"] += len(bad)
        tot["tells"] += c.get("tells", 0)
        tot["inert"] += c.get("inert", 0)
        tot["unreachable"] += c.get("unreachable", 0)
        tot["nb"] += c.get("no-bad-input", 0)
        e = ledger.setdefault(name, {})
        ceiling = e.get("ceiling")
        if ceiling is not None and len(bad) > ceiling:
            above.append((name, len(bad), ceiling))
        if a.raise_floors and (ceiling is None or len(bad) < ceiling):
            e["ceiling"] = len(bad)
        e.update({"blind": bad, "boxes": len(r["fields"]), "task": r.get("task"),
                  "counts": c, "at": int(time.time())})
        mark = "  ABOVE CEILING %d" % ceiling if ceiling is not None and len(bad) > ceiling else ""
        print("%-30s %11d %6d %6d %6d %6d   %s%s"
              % (name, len(bad), c.get("tells", 0), c.get("inert", 0),
                 c.get("unreachable", 0), c.get("no-bad-input", 0),
                 ", ".join(bad[:a.names]) + (" ..." if len(bad) > a.names else ""), mark))
    print("-" * 122)
    print("%-30s %11d %6d %6d %6d %6d   %s"
          % ("the kit", tot["blind"], tot["tells"], tot["inert"], tot["unreachable"], tot["nb"],
             "%d live box(es) cannot tell a rejected buffer from an empty one" % tot["blind"]))
    if not a.page:
        save(state)
    if above:
        print("\n%d page(s) grew a number box that reads a rejected buffer as blank. The box "
              "shows\ntheir characters; the page reads a blank; nobody is told:" % len(above))
        for name, now, ceiling in above:
            print("    %-30s %d, ceiling %d" % (name, now, ceiling))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
