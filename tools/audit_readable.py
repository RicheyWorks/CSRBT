# -*- coding: utf-8 -*-
"""The figures a page publishes that no task can read (ADR-146).

ADR-128 gave the harness `read-report`, and every science task since has held a
page's figures with it. What nobody measured is the other half of that sentence:
`read-report` reads the elements the kit NAMES as outputs -- an analysis (`an*`),
an `*Out`, a `*Box`, `*Stats`, `*Verdict`, `*Card`, `*List` and the rest of the
convention in `harness_plugin_page.REPORT`. An element the page WRITES A FIGURE
INTO under any other name is invisible to it, and to every task, and to every
suite built on one.

Silently. A task cannot fail to hold a figure it cannot see, so the page renders
the plot area, the expansion factor and the McCune & Keon heat-load band, and
the sheet's own suite is green, and nothing in the harness has ever read them.
Same shape as ADR-140's charts: the reader stops where nobody looked.

WHAT IS MEASURED, AND HOW

Not by a second copy of the naming regex -- a rule written twice is a rule that
drifts. The page is asked instead:

    WRITTEN    every element with an id whose rendered text CHANGED while the
               page's own entry task ran (audit_states.enter -- the same entry
               the three audits and entry_reach replay), counted at the deepest
               id in each chain, because a parent's text changes when its child's
               does and the innermost element is the one that owns the figure.
               Controls are excluded: a stepper's readout moving is the control,
               not a report.
    READABLE   the ids `read-report` actually returned as boxes, from the plugin
               itself.

    UNREADABLE = WRITTEN - READABLE - furniture

FURNITURE IS DECLARED, NOT GUESSED

A clock, a scroll ruler, a text editor's own box and a hint that repeats what a
control already says are written elements that are not figures, and renaming
them would be cargo cult. They are declared in the ledger with a REASON, one
line each, the same shape as the mutant ledger's known equivalents -- so the
list of things this audit is choosing not to care about is readable by the next
person, and short.

    python3 tools/audit_readable.py                 # the table and the worklist
    python3 tools/audit_readable.py --page stand-sheet.html
    python3 tools/audit_readable.py --check         # symmetry; a rise fails either way
    python3 tools/audit_readable.py --raise-floors  # after a page is fixed, record it
    python3 tools/audit_readable.py --furniture stand-sheet.html:tClock --reason "..."

A RATCHET DOWNWARD

The floor here is a CEILING: the number of unreadable written elements per page
may not go UP. A page that grows a new figure under a name outside the
convention fails the day it does, rather than being found a month later by
someone wondering why a task never noticed a wrong number. It ratchets DOWN as
pages are fixed, and it fails by default with no flag, because `run_all` runs an
audit with no arguments.

WHAT THIS IS NOT

It is not a claim that a readable figure is HELD -- whether a task holds it is
the task's business, and entry_reach is the file that measures the other half.
It is not a claim that an unreadable element is wrong: it says the harness
cannot see it, which is a fact about the instrument.
"""
import argparse, glob, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import harness as H
import audit_states as S
import harness_plugin_page as PP

LEDGER = os.path.join(HERE, "readable_ledger.json")

# The rendered text of every element that HAS an id, keyed by id. Controls are
# skipped: a stepper's value input and a text box carry values, not reports, and
# entry_reach is the file that accounts for those.
TEXT_JS = r"""
(skipHosts) => {
  const out = {};
  document.querySelectorAll("[id]").forEach(e => {
    if (e.hasAttribute("data-h")) return;
    const t = (e.tagName || "").toLowerCase();
    if (t === "input" || t === "textarea" || t === "select" || t === "option") return;
    // AN ENTRY HOST IS NOT A REPORT. The Field Entry Kit mounts its widgets
    // into a div and the div's text then changes -- so geoEntry, physEntry,
    // covEntry and their forty siblings across the kit read as "written
    // elements the harness cannot see", which is true of the string and false
    // of the thing: what is inside them is CONTROLS, and entry_reach is the
    // file that accounts for those. Structural rather than by name, because
    // "*Entry" is a convention and this is a fact: it holds a control.
    if (skipHosts && e.querySelector("[data-h]")) return;
    out[e.id] = (e.textContent || "").replace(/\s+/g, " ").trim().slice(0, 4000);
  });
  return out;
}
"""

# read-report has three channels, not one: boxes by name, TABLES by their host
# id, and CHARTS by the svg's host id (ADR-140). An element that IS or CONTAINS
# a table or an svg is therefore readable through one of the other two, and
# counting it as unseeable would be this audit disagreeing with the reader it
# exists to measure. Structural, and independent of whether the pane happened to
# be open at the end -- the chart channel skips a hidden svg, which is a fact
# about the moment and not about the page.
CHANNEL_JS = r"""
() => {
  const out = {};
  document.querySelectorAll("svg, table").forEach(e => {
    const host = e.id || ((e.closest("[id]") || {}).id) || "";
    if (host) out[host] = e.tagName.toLowerCase() === "svg" ? "chart" : "table";
  });
  return out;
}
"""

# Which of a set of ids has NO descendant that also has an id -- the innermost
# owner of a change. A parent's text changes whenever a child's does, so without
# this every figure is also reported against <body> and every card around it.
DEEPEST_JS = r"""
(ids) => {
  const set = new Set(ids);
  return ids.filter(id => {
    const e = document.getElementById(id);
    if (!e) return true;
    return ![...e.querySelectorAll("[id]")].some(k => set.has(k.id));
  });
}
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
    return {"_comment": "Written by tools/audit_readable.py. Per page: the elements the page "
                        "writes a figure into that read-report cannot see, and the ceiling that "
                        "count may not rise above. Furniture is declared with a reason (ADR-146).",
            "pages": {}}


def save(state):
    io.open(LEDGER, "w", encoding="utf-8").write(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def furniture_of(state, name):
    return dict((k, v) for k, v in
                (state.get("pages", {}).get(name, {}).get("furniture") or {}).items())


def measure(pg, name, tasks_dir=None, before=None):
    """-> {"written": [...], "readable": [...], "unreadable": [...], "task", "driven"}.

    The page is walked the way the audits walk it and then ENTERED with its own
    task, because most of this kit renders nothing at rest: a figure that only
    exists once a stem is tallied is exactly the figure a reader most wants
    held, and measuring the page at rest would report every one of them as
    absent rather than as unreadable."""
    # "Before" is the page WITH ITS SCRIPTS OFF -- what the file says, not what
    # the page has already made of it. Snapshotting after load misses every
    # figure painted at boot: the stand sheet writes its plot area and expansion
    # factor before a user touches anything, and against a post-boot baseline
    # those read as unchanged and therefore as not written at all.
    pg.evaluate(S.OPEN_DETAILS_JS)
    S._settle(pg)
    # every state the page can be put in, then the entry -- the same walk
    # entry_reach makes, for the same reason: a figure behind a tab is a figure.
    for _state, _r in S.each_state(pg, name, lambda: None, entered=False):
        pass
    ent = S.enter(pg, name, tasks_dir=tasks_dir)
    S._settle(pg)
    # Stamp the controls FIRST. The entry-host rule is structural -- "it holds a
    # control" -- and a control is a control because H.DISCOVER said so, so a
    # page with no task (discovery never runs) would otherwise report every
    # Field Entry Kit mount on it as a figure the harness cannot read.
    try:
        pg.evaluate(H.DISCOVER, H.KINDS)
    except Exception:
        pass
    after = pg.evaluate(TEXT_JS, True)

    before = before or {}
    changed = sorted(k for k, v in after.items() if before.get(k) != v)
    written = pg.evaluate(DEEPEST_JS, changed) if changed else []

    channels = pg.evaluate(CHANNEL_JS) or {}
    plug = PP.PagePlugin(pg, name)
    try:
        _ok, _msg, rep = plug.execute("read-report", {})
        boxes = sorted((rep.get("boxes") or {}).keys())
    except Exception:
        boxes = []
    readable = sorted(set(boxes) | set(channels))
    return {"task": (ent or {}).get("task"), "driven": (ent or {}).get("driven", 0),
            "written": sorted(written), "readable": readable,
            "channels": channels}


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
        # A second context with SCRIPTS OFF holds the baseline: the same file,
        # rendered by nothing. Two contexts rather than two loads in one,
        # because java_script_enabled is a context setting.
        dead = b.new_context(viewport=H.VIEWPORT, java_script_enabled=False)
        dead.set_offline(True)          # the baseline is the FILE, not the web
        dpg = dead.new_page()
        for name in names:
            url = "file://" + os.path.join(docs_dir(), name).replace(os.sep, "/")
            try:
                dpg.goto(url, wait_until="domcontentloaded")
                before = dpg.evaluate(TEXT_JS, False)
            except Exception:
                before = {}
            try:
                pg.goto(url, wait_until="domcontentloaded")
                pg.wait_for_timeout(250)
                out[name] = measure(pg, name, tasks_dir, before)
            except Exception as exc:
                out[name] = {"error": str(exc)[:140], "written": [], "readable": []}
        dead.close()
        ctx.close()
        b.close()
    return out


def unreadable(r, furniture):
    return [i for i in r.get("written", [])
            if i not in set(r.get("readable", [])) and i not in furniture]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="one page")
    ap.add_argument("--check", action="store_true",
                    help="accepted for symmetry with the kit's other ratchets; a page above its "
                         "ceiling exits non-zero with or without it")
    ap.add_argument("--raise-floors", action="store_true",
                    help="record today's reading as the ceiling wherever it is LOWER (this ratchet "
                         "runs downward: the flag keeps the name the kit's other ratchets use)")
    ap.add_argument("--furniture", metavar="PAGE:ID",
                    help="declare one written element to be furniture, not a figure (needs --reason)")
    ap.add_argument("--reason", default="", help="why an element is furniture")
    ap.add_argument("--names", type=int, default=8, help="how many unreadable elements to name")
    a = ap.parse_args(argv)
    state = load()
    ledger = state.setdefault("pages", {})

    if a.furniture:
        if ":" not in a.furniture:
            print("--furniture takes PAGE:ID, e.g. stand-sheet.html:tClock")
            return 2
        page, eid = a.furniture.split(":", 1)
        if not a.reason.strip():
            print("declaring furniture needs --reason: it goes into the ledger, and a list of "
                  "things\nthis audit is choosing not to care about is only useful if each line "
                  "says why")
            return 2
        ledger.setdefault(page, {}).setdefault("furniture", {})[eid] = a.reason.strip()
        save(state)
        print("%s: %s declared furniture" % (page, eid))
        return 0

    got = walk(a.page)
    print("%-30s %10s %8s %8s   %s"
          % ("PAGE", "UNREADABLE", "written", "readable", "the figures no task can read"))
    print("-" * 112)
    tot_u = tot_w = 0
    above = []
    for name in sorted(got):
        r = got[name]
        if r.get("error"):
            print("%-30s %10s %8s %8s   %s" % (name, "-", "-", "-", r["error"]))
            continue
        furn = furniture_of(state, name)
        bad = unreadable(r, furn)
        if not r["written"] and not bad:
            continue
        tot_u += len(bad)
        tot_w += len(r["written"])
        e = ledger.setdefault(name, {})
        ceiling = e.get("ceiling")
        if ceiling is not None and len(bad) > ceiling:
            above.append((name, len(bad), ceiling))
        if a.raise_floors and (ceiling is None or len(bad) < ceiling):
            e["ceiling"] = len(bad)
        e.update({"unreadable": bad, "written": len(r["written"]),
                  "task": r["task"], "at": int(time.time())})
        mark = "  ABOVE CEILING %d" % ceiling if ceiling is not None and len(bad) > ceiling else ""
        print("%-30s %10d %8d %8d   %s%s"
              % (name, len(bad), len(r["written"]), len(r["readable"]),
                 ", ".join(bad[:a.names]) + (" ..." if len(bad) > a.names else ""), mark))
    print("-" * 112)
    print("%-30s %10d %8d %8s   %s"
          % ("the kit", tot_u, tot_w, "",
             "%d of %d written element(s) are outside read-report's naming" % (tot_u, tot_w)))
    if not a.page:
        save(state)
    if above:
        print("\n%d page(s) grew a figure the harness cannot read. A task cannot fail to hold a\n"
              "figure it cannot see:" % len(above))
        for name, now, ceiling in above:
            print("    %-30s %d, ceiling %d" % (name, now, ceiling))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
