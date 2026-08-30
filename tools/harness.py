# -*- coding: utf-8 -*-
"""Drives every affordance on every page, and refuses to be quiet about the ones
it did not drive.

The per-page suites in tools/verify each know what THEIR page is supposed to do.
None of them knows what is ON a page, so a control nobody wrote a check for is
green by omission -- the failure mode ADR-099 predicted after finding the same
shape twice at the reading layer. This walks the other way round: it discovers
what a user can touch, touches all of it, and accounts for every one.

WHAT COUNTS AS AN AFFORDANCE
    Every element a finger can reach: tabs, the Field Entry Kit's steppers,
    dials, chips, pickers, sliders and instrument fields; the bespoke chip rows
    (.kopt/.ck/.cv/.swc); every other button on the page; every text, number and
    date input; every select and file input; and the navigation rail.

    A control inside a tab is reached the way a user reaches it: the harness
    presses that tab first. An element still not visible after that is HIDDEN --
    a fact about the page, not a failure, because much of this kit reveals
    controls only once a precondition is met.

WHAT "IT WORKED" MEANS
    One general oracle rather than a per-page expectation, because a per-page
    expectation is how a harness ends up asserting what its author remembered.
    An action passes when it leaves an OBSERVABLE trace -- rendered text, a
    toggled class, a form value, a localStorage write, or a call to one of the
    stubbed exits (print, clipboard, alert) -- and breaks nothing:

      * no uncaught error and no console error
      * no NaN / undefined / [object Object] in what the page renders
      * exactly one pane visible, if the page has panes
      * nothing spilling sideways out of a 390px viewport

    An affordance that leaves NO trace is the finding: it is wired to nothing,
    or wired to something that does not answer.

THE ACCOUNTING
    discovered == driven + dead + hidden + failed + excluded, per page and in
    total. The run prints UNACCOUNTED if that identity does not hold, because a
    harness that loses track of an affordance is a harness reporting a coverage
    it does not have. EXCLUDED is the only way out and every entry carries its
    reason (ADR-061).

Run:  python3 tools/harness.py            all pages
      python3 tools/harness.py PAGE ...   named pages
      python3 tools/harness.py -j 4       four at a time
"""
import argparse, concurrent.futures as cf, glob, io, json, os, sys, time
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "verify"))
import _kit
from playwright.sync_api import sync_playwright

LEDGER = os.path.join(HERE, "harness_ledger.json")
VIEWPORT = {"width": 390, "height": 844}          # a phone in a wet field
ACT_TIMEOUT = 2500                                 # ms; nothing here should be slow

# Console noise that is the kit working as designed. ADR-031 loads the webfont
# with media="print" and an error listener precisely so a stylesheet that never
# arrives cannot hold the page blank; offline, that request fails on every page,
# every time. It was reported once as a defect on field-season before being
# chased to fonts.googleapis.com -- the request the offline audit exists to
# permit.
IGNORED_CONSOLE = ("fonts.googleapis.com", "fonts.gstatic.com")
# Typed into rather than pressed: no group to move off.
TYPED = ("text_in", "pick_search", "field_in", "step_val", "select",
         "slider", "file_in")
_TICK = 0

# Affordance kinds, in the order they are driven. Entry before action: a form
# filled and then cleared tells you more than a form cleared and then filled.
KINDS = [
    ("tab",         '.tab[data-pane]'),
    ("step_val",    '.fek-step .val'),
    ("field_in",    '.fek-field input'),
    ("readonly_out", 'input[readonly], textarea[readonly], input[disabled], '
                     'textarea[disabled], select[disabled]'),
    ("text_in",     'input[type=text], input[type=number], input[type=date], textarea'),
    ("select",      'select'),
    ("slider",      '.fek-slide input[type=range]'),
    ("pick_search", '.fek-pick .search'),
    ("pick_opt",    '.fek-pick .opt'),
    ("dial_btn",    '.fek-dial button'),
    ("chip",        '.fek-chip'),
    ("kopt",        '.kopt'),
    ("ck",          '.ck'),
    ("cv",          '.cv'),
    ("swc",         '.swc'),
    ("step_btn",    '.fek-step button'),
    ("file_in",     'input[type=file]'),
    ("action_btn",  'button'),                     # whatever no widget claimed
    ("link",        '.rail a[href]'),
    ("nav_link",    'a[href]'),        # hub and suite cards; whatever the rail left
]

# Every exclusion says what it is and why. verify_harness asserts this list is
# the only way an affordance escapes being driven.
EXCLUDED = {
    "link": "a rail link navigates away from the page under test; the hrefs are "
            "checked structurally instead -- every one must resolve to a page in "
            "tools/artifact_map.json or to this page itself",
    "nav_link": "the same, for the cards on the hub and the suite pages: a click "
                "would end the run on a different page, so every href is resolved "
                "against the artifact map rather than followed",
    "readonly_out": "a readonly or disabled box is a display, not a control -- "
                    "typing into it is not something a user can do, and five of "
                    "them were reported as affordances the harness failed to "
                    "drive when the truth was that nobody can drive them",
}

# Installed before any page script runs, so an export or a print is a recorded
# call rather than a hung browser.
STUBS = r"""
window.__H = { calls: [], errors: [] };
(function () {
  var rec = function (k) { return function () {
    window.__H.calls.push({ k: k, a: Array.prototype.slice.call(arguments, 0, 1)
      .map(function (x) { return String(x).slice(0, 4000); }) });
    return k === "confirm" ? true : (k === "prompt" ? "" : undefined);
  }; };
  window.print   = rec("print");
  window.alert   = rec("alert");
  window.confirm = rec("confirm");
  window.prompt  = rec("prompt");
  try {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: {
      writeText: function (s) { rec("clipboard")(s); return Promise.resolve(); } } });
  } catch (e) { }
  try { navigator.vibrate = function () { return true; }; } catch (e) { }
  document.addEventListener("DOMContentLoaded", function () {
    var oe = document.execCommand;
    document.execCommand = function (c) {
      if (c === "copy") { rec("copy-legacy")(String(window.getSelection())); return true; }
      return oe ? oe.apply(document, arguments) : false;
    };
  });
  window.addEventListener("error", function (e) {
    window.__H.errors.push(String(e && e.message).slice(0, 300)); });
  window.addEventListener("unhandledrejection", function (e) {
    window.__H.errors.push("rejection: " + String(e && e.reason).slice(0, 300)); });
})();
"""

# One pass, one id per affordance. data-h is stamped on so a later action cannot
# reach the wrong element when the DOM has been rebuilt underneath the walk.
DISCOVER = r"""
(kinds) => {
  const claimed = new Set();
  const out = [];
  for (const [kind, sel] of kinds) {
    let els = [...document.querySelectorAll(sel)];
    if (kind === "action_btn" || kind === "nav_link" || kind === "text_in")
      els = els.filter(e => !claimed.has(e));
    els.forEach(e => claimed.add(e));
    els.forEach((e, i) => {
      const id = kind + ":" + i;
      e.setAttribute("data-h", id);
      out.push({
        id: id, kind: kind,
        label: (e.getAttribute("aria-label") || e.textContent || e.value ||
                e.placeholder || e.id || "").replace(/\s+/g, " ").trim().slice(0, 60),
        href: e.getAttribute("href") || null,
        pane: (e.closest(".pane") || {}).id || null,
        type: (e.getAttribute("type") || e.tagName).toLowerCase(),
      });
    });
  }
  return out;
}
"""

# One round trip: is it there, is it reachable, and the state fingerprint and
# invariants in the same breath. Two evaluates per action, not five.
PROBE = r"""
(id) => {
  const h = s => { let x = 0; for (let i = 0; i < s.length; i++) x = (x * 31 + s.charCodeAt(i)) | 0; return x; };
  const t = document.body ? (document.body.innerText || "") : "";
  const vals = [...document.querySelectorAll("input,textarea,select")]
    .map(e => (e.type === "checkbox" || e.type === "radio") ? String(e.checked) : String(e.value))
    .join("");
  let ls = -1; try { ls = JSON.stringify(localStorage).length; } catch (e) { }
  const junk = t.match(/\bNaN\b|\bundefined\b|\[object Object\]/);
  const panes = document.querySelectorAll(".pane").length;
  const el = id ? document.querySelector('[data-h="' + id + '"]') : null;
  let vis = false, on = false;
  if (el) {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    vis = r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
    on = el.classList.contains("on");
  }
  return {
    // WHICH things are on, not how many. Counting caught a toggle going on and
    // missed a selection MOVING between two options in the same dial -- one
    // loses .on, one gains it, and the count never budges. Ten live dials read
    // as wired-to-nothing before this was a list.
    fp: { text: h(t), len: t.length, vals: h(vals), ls: ls,
          on: h([...document.querySelectorAll(".on")].map(
                e => (e.getAttribute("data-h") || "") + "/" + e.className + "/" +
                     (e.textContent || "").slice(0, 16)).join("|")),
          calls: (window.__H ? window.__H.calls.length : 0) },
    present: !!el, visible: vis, wasOn: on,
    junk: junk ? t.slice(Math.max(0, junk.index - 60), junk.index + 60).replace(/\s+/g, " ") : null,
    junkTok: junk ? junk[0] : null,
    panes: panes, onp: document.querySelectorAll(".pane.on").length,
    // clientWidth, NOT innerWidth. innerWidth includes the vertical scrollbar;
    // clientWidth does not. The moment a page grew tall enough to need one, the
    // difference read as 15px of horizontal spill and the harness reported a
    // layout defect on two pages. Fifteen pixels is not a bug, it is a
    // scrollbar. Measured against the wrong edge, an instrument will report
    // confidently about the wrong thing.
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    // Naming the element that spills is the difference between a number and a
    // thing to fix: "spills 15px" sent the first triage looking in the wrong
    // place for twenty minutes.
    wide: [...document.querySelectorAll("*")]
      .filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
      .slice(0, 2).map(e => e.tagName.toLowerCase() + "." +
        String(e.className || "").split(/\s+/)[0] + " w=" +
        Math.round(e.getBoundingClientRect().width)),
    errors: (window.__H ? window.__H.errors.splice(0, 3) : []),
  };
}
"""

ACTIVE_PANE = "() => (document.querySelector('.pane.on') || {}).id || null"

# A toast is on screen for 1.7s and the walk moves faster than that. Twelve
# spore-print swatches in a row each raised the same "Pick a collection first"
# toast, and because it was already up with the same words none of them changed
# anything measurable -- twelve live controls accused of being wired to nothing.
# Transient feedback is taken down before the baseline is read, so raising it
# again is a change.
QUIESCE = r"""
() => {
  document.querySelectorAll(".toast").forEach(t => t.classList.remove("on"));
}
"""

# A stepper sitting at its minimum does nothing when minus is pressed, and that
# is correct behaviour, not a dead control. Give the value somewhere to go by
# pressing the other button first, then take the baseline -- the same move as
# UNSELECT, for the same reason: judge a press from a state where it can show.
HEADROOM = r"""
(id) => {
  const el = document.querySelector('[data-h="' + id + '"]');
  if (!el || !el.parentElement) return null;
  const other = [...el.parentElement.querySelectorAll("button")].find(b => b !== el);
  if (!other) return null;
  other.click();
  return true;
}
"""

CLEAR_SEARCH = r"""
(id) => {
  const el = document.querySelector('[data-h="' + id + '"]');
  if (!el) return;
  el.value = "";
  el.dispatchEvent(new Event("input", { bubbles: true }));
}
"""

# Pressing something already selected is a no-op on purpose: a tab that is open,
# the chosen option of a dial built with clearable:false. Ten such controls read
# as wired-to-nothing until the walk stopped pressing them from the state they
# were already in. Rather than excuse the result, move the group off the target
# first -- then the press IS a state change and the oracle applies at full
# strength. The setup click is a plain DOM click; it is not the action under
# test, and if there is no sibling to move to, nothing is done and the note says
# so.
UNSELECT = r"""
(id) => {
  const el = document.querySelector('[data-h="' + id + '"]');
  if (!el || !el.parentElement) return null;
  const sib = [...el.parentElement.children].find(
    c => c !== el && c.getAttribute("data-h") && !c.classList.contains("on"));
  if (!sib) return null;
  sib.click();
  return sib.getAttribute("data-h");
}
"""


def show_pane(pg, pane):
    """Reach a control the way a user does: press its tab first."""
    if not pane:
        return True
    if pg.evaluate(ACTIVE_PANE) == pane:
        return True
    tab = pg.query_selector('.tab[data-pane="%s"]' % pane)
    if tab is None:
        return False
    try:
        tab.click(timeout=ACT_TIMEOUT)
        pg.wait_for_timeout(40)
    except Exception:
        return False
    return pg.evaluate(ACTIVE_PANE) == pane


def act(pg, a):
    """Do to the affordance what a finger would. Returns a note, or raises."""
    sel = '[data-h="%s"]' % a["id"]
    el = pg.query_selector(sel)
    if el is None:
        return "gone"
    k, t = a["kind"], a["type"]
    if k in ("text_in", "pick_search", "field_in", "step_val"):
        # A different value every time. Filling a field with what it already
        # holds changes nothing, and on the second pass the walk was doing
        # exactly that -- then reporting the field as wired to nothing.
        global _TICK
        _TICK += 1
        if t == "date":
            v = "2026-06-%02d" % (1 + _TICK % 28)
        elif t == "number":
            v = str(1 + _TICK % 9)
        else:
            v = "harness-%d" % _TICK
        el.fill(v, timeout=ACT_TIMEOUT)
        el.dispatch_event("input")
        el.dispatch_event("change")
        return "filled"
    if k == "select":
        if len(el.query_selector_all("option")) > 1:
            el.select_option(index=1, timeout=ACT_TIMEOUT)
            return "selected"
        return "one option"
    if k == "slider":
        el.evaluate("e => { e.value = e.max; e.dispatchEvent(new Event('input', {bubbles:true})); }")
        return "slid"
    if k == "file_in":
        # tempfile, not a hardcoded Linux scratch path (ADR-106): on Windows
        # this wrote to the current drive's root, which is a permission error
        # rather than a fixture, and the chaos pass would have lost the one
        # action that exercises file import.
        p = os.path.join(tempfile.gettempdir(), "_harness_import.json")
        io.open(p, "w", encoding="utf-8").write('{"not":"a valid pack"}')
        el.set_input_files(p, timeout=ACT_TIMEOUT)
        return "imported"
    el.click(timeout=ACT_TIMEOUT)
    return "clicked"


def drive_all(pg, found, res, console):
    for a in found:
        rec = {"id": a["id"], "kind": a["kind"], "label": a["label"], "pane": a["pane"]}
        if a["kind"] in EXCLUDED:
            rec["href"] = a["href"]
            rec["why"] = a["kind"]
            res["excluded"].append(rec)
            continue
        try:
            show_pane(pg, a["pane"])
            # Re-stamp first. FEK widgets rebuild whole subtrees on change --
            # fillGenera, fillHosts, fillPicks, renderAll -- which drops the
            # data-h attributes stamped at discovery. Stamping once and
            # walking cost 941 of 1026 affordances to "the page rebuilt it
            # away", almost the entire picker surface of the kit. The ids are
            # positional within a kind, so re-running the same discovery pass
            # restores them.
            pg.evaluate(DISCOVER, KINDS)
            pg.evaluate(QUIESCE)
            before = pg.evaluate(PROBE, a["id"])
        except Exception as e:
            rec["why"] = "unreadable before the action"
            rec["got"] = str(e).split("\n")[0][:160]
            res["failed"].append(rec)
            continue
        if not before["present"]:
            rec["why"] = "the page rebuilt it away before it could be driven"
            res["hidden"].append(rec)
            continue
        if not before["visible"]:
            rec["why"] = "not visible with its own pane open"
            res["hidden"].append(rec)
            continue

        # Pressing something already selected is a no-op on purpose -- an
        # open tab, the chosen option of a clearable:false dial. Move the
        # group off it first so the press is a real state change, and take
        # the baseline AFTER that move: the first version of this compared
        # against the pre-setup state, so a setup and a press that cancelled
        # out read as a control wired to nothing. Two live controls were
        # accused before the baseline moved to the right side of the setup.
        prep = ""
        if a["kind"] == "step_btn" or (a["kind"] == "action_btn"
                                       and a["label"] in ("+", "-", "\u2212")):
            if pg.evaluate(HEADROOM, a["id"]) is not None:
                pg.wait_for_timeout(15)
                before = pg.evaluate(PROBE, a["id"])
                prep = " (stepped the other way first)"
        elif before["wasOn"] and a["kind"] not in TYPED:
            if pg.evaluate(UNSELECT, a["id"]) is not None:
                pg.wait_for_timeout(20)
                before = pg.evaluate(PROBE, a["id"])
                prep = " (group moved off it first)"
            else:
                prep = " (already selected, nothing to deselect it with)"
        n0 = len(console)
        try:
            rec["note"] = act(pg, a) + prep
        except Exception as e:
            rec["why"] = "action raised"
            rec["got"] = str(e).split("\n")[0][:160]
            res["failed"].append(rec)
            continue
        pg.wait_for_timeout(15)
        try:
            after = pg.evaluate(PROBE, a["id"])
            if a["kind"] == "pick_search":
                # Leaving "harness" in a picker's filter hides every option
                # behind it, and the walk would then report the whole list as
                # unreachable -- damage the harness did to itself.
                pg.evaluate(CLEAR_SEARCH, a["id"])
        except Exception as e:
            rec["why"] = "page unreadable after the action"
            rec["got"] = str(e).split("\n")[0][:160]
            res["failed"].append(rec)
            continue

        moved = before["fp"] != after["fp"]
        if moved or rec["note"] == "gone":
            if rec["note"] == "gone":
                rec["note"] = "rebuilt out from under the walk"
            res["driven"].append(rec)
        else:
            res["dead"].append(rec)

        bad = []
        if after["junkTok"] and after["junkTok"] != res.get("junk_on_load"):
            bad.append(("junk rendered", after["junk"]))
        if after["panes"] and after["onp"] != 1:
            bad.append(("%d panes visible" % after["onp"], ""))
        if after["overflow"] > 1:
            bad.append(("spills %dpx sideways" % after["overflow"],
                        ", ".join(after["wide"])))
        for e in after["errors"]:
            bad.append(("uncaught", e))
        for c in console[n0:]:
            if any(x in c for x in IGNORED_CONSOLE):
                continue
            bad.append(("console error", c[:160]))
        for why, got in bad:
            res["errors"].append("%s [%s %s]: %s" % (why, a["id"], a["label"][:30], got))


def run_page(name, passes=3, url=None):
    started = time.time()
    res = {"page": name, "discovered": 0, "driven": [], "dead": [], "hidden": [],
           "failed": [], "excluded": [], "errors": [], "calls": []}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport=VIEWPORT)
        ctx.set_offline(True)
        ctx.add_init_script(STUBS)
        pg = ctx.new_page()
        pg.set_default_timeout(ACT_TIMEOUT)
        console = []
        def _console(m):
            if m.type != "error":
                return
            url = (m.location or {}).get("url", "")
            if any(x in url or x in m.text for x in IGNORED_CONSOLE):
                return
            console.append(m.text + "  <- " + url[:80])
        pg.on("console", _console)
        pg.on("pageerror", lambda e: res["errors"].append(str(e)[:200]))
        pg.goto(url or _kit.url(name), wait_until="domcontentloaded")
        pg.wait_for_timeout(400)

        opening = pg.evaluate(PROBE, None)
        # A page may legitimately contain the WORD undefined -- field-notebook
        # says "the estimate is undefined (R must be at least 1)", which is the
        # page being careful, not a value leaking. Only junk that was not there
        # when the page loaded counts.
        res["junk_on_load"] = opening["junkTok"] or ""
        if opening["junk"]:
            res["errors"].append("junk on load: " + opening["junk"])

        # PASSES. A page that has had a record added to it offers controls that
        # were not on it when it loaded -- a row's delete button, an export that
        # only appears once there is something to export. One walk can only ever
        # reach the affordances of an empty page, so the walk repeats until a
        # pass turns up nothing new, or the cap is reached. Every id seen in any
        # pass is accounted for; nothing is discovered and then forgotten.
        seen, res["passes"] = set(), 0
        for _ in range(passes):
            res["passes"] += 1
            fresh = [a for a in pg.evaluate(DISCOVER, KINDS) if a["id"] not in seen]
            if not fresh:
                break
            for a in fresh:
                seen.add(a["id"])
            drive_all(pg, fresh, res, console)
        res["discovered"] = len(seen)
        res["calls"] = pg.evaluate("() => window.__H.calls.map(c => c.k)")
        ctx.close()
        b.close()
    res["secs"] = round(time.time() - started, 1)
    return res


BUCKETS = ("driven", "dead", "hidden", "failed", "excluded")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*")
    ap.add_argument("-j", type=int, default=2)
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--passes", type=int, default=3,
                    help="walk again while a pass keeps turning up new affordances")
    a = ap.parse_args()

    names = a.pages or sorted(os.path.basename(p)
                              for p in glob.glob(os.path.join(_kit.ROOT, "docs", "*.html")))
    print("harness -- %d page(s), %d at a time, up to %d passes, %dx%d offline"
          % (len(names), a.j, a.passes, VIEWPORT["width"], VIEWPORT["height"]))
    print("-" * 78)
    out = []
    with cf.ThreadPoolExecutor(max_workers=a.j) as ex:
        for r in ex.map(run_page, names, [a.passes] * len(names)):
            out.append(r)
            n = {k: len(r[k]) for k in BUCKETS}
            print("%-30s %4d driven %3d dead %3d hidden %3d failed %3d excl %3d err %5.1fs"
                  % (r["page"], n["driven"], n["dead"], n["hidden"], n["failed"],
                     n["excluded"], len(r["errors"]), r["secs"]))
    out.sort(key=lambda r: r["page"])

    tot = {k: sum(len(r[k]) for r in out) for k in BUCKETS}
    disc = sum(r["discovered"] for r in out)
    errs = sum(len(r["errors"]) for r in out)
    print("-" * 78)
    print("discovered %d = %s  %s"
          % (disc, " + ".join("%s %d" % (k, tot[k]) for k in BUCKETS),
             "OK" if disc == sum(tot.values()) else "<-- UNACCOUNTED"))
    print("actions that broke an invariant: %d" % errs)

    for bucket, head in (("dead", "AFFORDANCES THAT LEFT NO TRACE"),
                         ("failed", "AFFORDANCES THE HARNESS COULD NOT DRIVE")):
        rows = [(r["page"], d) for r in out for d in r[bucket]]
        if rows:
            print("\n%s (%d)" % (head, len(rows)))
            for page, d in rows[:60]:
                print("  %-26s %-11s %-34s %s"
                      % (page, d["kind"], (d["label"] or "(no label)")[:34],
                         (d.get("got") or d.get("why") or "")[:40]))
    rows = [(r["page"], e) for r in out for e in r["errors"]]
    if rows:
        print("\nBROKEN INVARIANTS (%d)" % len(rows))
        for page, e in rows[:60]:
            print("  %-26s %s" % (page, e[:110]))

    # MERGE, DO NOT REPLACE (ADR-108, and ADR-104 before it for the counts ledger).
    # This wrote `out` as the whole ledger, so `harness.py one-page.html` silently
    # deleted the coverage of every page it did not run -- and the route contract,
    # which reads this file to answer "is every page covered?", would then report
    # forty uncovered pages that had in fact been driven yesterday. A ledger with a
    # consumer does not corrupt quietly. A run now updates only the pages it drove
    # and keeps the rest, and every page entry carries its own "at" so a kept
    # reading can be told from a fresh one.
    now = int(time.time())
    for r in out:
        r["at"] = now
    prev = []
    if os.path.exists(a.ledger):
        try:
            prev = json.load(io.open(a.ledger, encoding="utf-8")).get("pages", [])
        except (OSError, ValueError):
            prev = []
    ran = {r["page"] for r in out}
    merged = [r for r in prev if r.get("page") not in ran] + out
    merged.sort(key=lambda r: r.get("page", ""))
    kept = len(merged) - len(out)

    def total(key):
        # Per-page entries hold LISTS of affordance labels for driven/dead/hidden/
        # failed/excluded, and an int for discovered. Count either.
        n = 0
        for r in merged:
            v = r.get(key, 0)
            n += len(v) if isinstance(v, (list, tuple)) else (v or 0)
        return n
    mdisc = total("discovered")
    mtot = {k: total(k) for k in ("driven", "dead", "hidden", "failed", "excluded")}
    json.dump({"at": now, "viewport": VIEWPORT, "excluded_kinds": EXCLUDED,
               "totals": dict(mtot, discovered=mdisc,
                              invariant_breaks=sum(len(r.get("errors", [])) for r in merged)),
               "pages": merged}, io.open(a.ledger, "w", encoding="utf-8"), indent=1)
    print("\nwrote %s (%d page%s driven%s)"
          % (a.ledger, len(out), "" if len(out) == 1 else "s",
             ", %d kept from earlier runs" % kept if kept else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
