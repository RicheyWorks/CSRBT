# -*- coding: utf-8 -*-
"""The csrbt-page plugin: one CSRBT page in a browser, behind the contract.

This is where the kit's own knowledge lives, so that no client needs it:

  * WHAT A CONTROL IS. A "button" on a Field Entry Kit page may be a dial option
    with radio semantics, a stepper arrow, a picker row, or an export. The
    snapshot names the kind, so a caller can decide what to do without pattern
    matching on CSS.

  * WHERE A CONTROL IS. Half of the surface lives inside panes that are closed
    until their tab is pressed. show-pane is a first-class NAVIGATE action and
    every other action opens the owning pane before it acts, because a client
    should not have to know that a control it can see in the snapshot needs a
    tab pressed first.

  * THAT IT MOVES. FEK rebuilds whole subtrees on change, dropping the stamps
    that make a selector resolvable. Every snapshot re-stamps. A client that
    observes, then acts on what it observed, is safe by construction; a client
    holding a stale selector gets not_found rather than the wrong element.

REDACTION
    observe() publishes kind, selector, label, pane, visible, enabled and
    commandable. It does not publish what is in a field. Labels are published,
    and on a page that renders entered records into a list a label CAN contain
    what a user typed -- the manifest says so rather than pretending otherwise.
    Values come back only through read-control, which is SENSITIVE_READ.
"""
import base64, io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "verify"))
import _kit
import harness as H
from harness_contract import (ActionSpec, ArgumentSpec, Plugin, PluginDescriptor,
                              Conflict, Failed, HarnessError, InvalidArgument, NotFound,
                              Stale, Unavailable)

# Bytes the harness hands to a file input or a drop zone. Real files, made
# here rather than read from disk, so a run reads nothing of the operator's
# and needs no fixture directory. DJI_0192.JPG is named the way a drone
# names its frames, because a page that keys on the filename should be
# driven with a filename somebody will really hand it.
FIXTURES = {
    "image": {
        "name": "IMG_0431.jpg",
        "type": "image/jpeg",
        "b64": "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
    },
    "image2": {
        "name": "DJI_0192.JPG",
        "type": "image/jpeg",
        "b64": "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
    },
    "png": {
        "name": "quadrat-A3.png",
        "type": "image/png",
        "b64": "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAEElEQVR4nGNQqrCBIwbiOABaYw1htNAtQQAAAABJRU5ErkJggg=="
    },
    "video": {
        "name": "flight-north-40.webm",
        "type": "video/webm",
        "b64": "GkXfo59ChoEBQoWBAhhTgGcBAAAAAAAAEU2bdLpNu4tTq4QVSalmU6yB"
    },
    "pack": {
        "name": "genus-pack.json",
        "type": "application/json",
        "b64": "eyJraW5kIjogImNzcmJ0LXBhY2siLCAidmVyc2lvbiI6IDEsICJpdGVtcyI6IFt7Im5hbWUiOiAiWnF4OTAxIiwgImd1aWxkIjogInNhcHJvdHJvcGgifV19"
    },
    "eco": {
        "name": "session.eco",
        "type": "text/plain",
        "b64": "IyBlY28gbGluZXMKc2l0ZTogWnF4OTAyCmNvdW50OiAzCg=="
    },
    "csv": {
        "name": "controller.csv",
        "type": "text/csv",
        "b64": "d2hlbix0ZW1wQyxyaAoyMDI2LTA2LTAxVDA4OjAwLDE4LjUsNjIKMjAyNi0wNi0wMVQwOTowMCwyMS4wLDU1Cg=="
    },
    "junk": {
        "name": "corrupt.json",
        "type": "application/json",
        "b64": "AAFub3QganNvbiBhdCBhbGz//nt7ew=="
    }
}

# The kit's own shipped session, read from docs/ rather than pasted here as
# base64 (ADR-135): it is 9 KB of the engine's own arithmetic, and a copy in
# this file would be a second session that drifts from the one the engine
# writes. A page that charts it must chart THE session, not a likeness.
def _shipped_session():
    path = os.path.join(_kit.DOCS_DIR, "ecology-experiment-session.json")
    try:
        raw = io.open(path, "rb").read()
    except (IOError, OSError):
        return None
    return {"name": "ecology-experiment-session.json", "type": "application/json",
            "b64": base64.b64encode(raw).decode("ascii")}


_SESSION = _shipped_session()
if _SESSION:
    FIXTURES["session"] = _SESSION

SEL_RE = re.compile(r"^[a-z_]+:\d+$")
SETTLE_TRIES, SETTLE_MS = 6, 60        # ADR-189: at most ~300ms of waiting for a page to stop building
PICK_CAP, POOL_CAP = 80, 600           # ADR-190: options published per list, and in all
# ADR-188: THE ADDRESS GRAMMAR. A selector is the moment's -- the third blind
# trial watched four operators re-observe after every structural change and
# compute button offsets by hand, and all four noticed that the snapshot
# publishes a stable `id` no tool would accept. These are the forms every
# selector argument now takes:
#
#     text_in:3            the moment's index, exactly as before
#     text_in:3@v1x7k      the same, stamped with the snapshot it came from
#     #cName               the page's own id
#     @working name        the page's own name for it: id, label, host,
#     @rCov/4              host/label, "#n" for the nth such, "kind=" for a
#     @kind=drop_zone      control the page never named   (ADR-128's grammar)
STAMP_RE = re.compile(r"^([a-z_]+:\d+)@(v[0-9a-z]{1,10})$")
ADDR_RE = re.compile(r"^(?:[a-z_]+:\d+(?:@v[0-9a-z]{1,10})?"
                     r"|#[A-Za-z][A-Za-z0-9_.:-]{0,63}"
                     r"|@(?:control:)?[^\s\x00][^\r\n\x00]{0,95})$")

# Which discovered kinds each action can act on -- the same knowledge the
# swarm's DRIVER map holds (verify_contract pins that they agree), published
# here as argument pools so a client that has never read the swarm can pick a
# selector its action will accept.
POOL_KINDS = {
    "set-text": ("text_in", "field_in", "pick_search", "step_val"),
    # NOT pick_search: typing into a picker's search box is what `pick` does,
    # and putting both actions in that pool made the robot choose between them
    # -- the walk of one page then drove type-text where it used to drive pick,
    # and reported pick undriven on a page that offers one. An action added to a
    # pool competes for it (ADR-150).
    "type-text": ("text_in", "field_in", "step_val"),
    "pick": ("pick_search",),
    "choose-option": ("select",),
    "set-slider": ("slider",),
    "press-step": ("step_btn",),
    "set-checkbox": ("checkbox",),
    "attach-file": ("file_in",),
    "drop-files": ("drop_zone",),
    "activate": ("pick_opt", "dial_btn", "chip", "kopt", "ck", "cv", "swc", "action_btn"),
}


def kit_pages():
    import glob
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(_kit.DOCS_DIR, "*.html")))

# ONE definition of "the name a finger reads" (ADR-141). It was written twice
# -- once in the discovery snapshot, once nowhere at all, so read-control
# answered about a control without ever naming it -- and the risk classifier
# added a third reader. A classifier that decides a button is called something
# other than what the snapshot calls it is exactly the failure the classifier
# exists to prevent, so the three share these lines rather than agreeing by
# hand. A dial button is "<span>4</span><small>25-50%</small>", a behaviour key
# "<b class=nm>forage</b><kbd>f</kbd>": the label is the name a finger reads,
# not the whole button's text run together (ADR-128).
LABEL_FN = r"""
  const _label = (e) => (e.getAttribute("aria-label") || (e.querySelector(".nm") || {}).textContent ||
      (() => { const c = e.cloneNode(true);
               // <small> and <kbd> are not the name (ADR-128), and neither is a
               // SMALLER CONTROL living inside this one. The kit's tally chip is
               // one button reading "<span class=x data-x>x</span> clover 3":
               // clicking the button increments, clicking the span deletes, and
               // taking the whole text made the field notebook's primary
               // data-entry control read as a delete (ADR-142).
               c.querySelectorAll("small, kbd, [data-x], .x").forEach(x => x.remove());
               return c.textContent; })() || e.placeholder ||
      e.getAttribute("title") || "").replace(/\s+/g, " ").trim().slice(0, 60);
"""

ADDR_FN = r"""
  /* ADR-188: a control's ADDRESS is a name the page owns; a selector is an
     index the moment owns. This is the runner's find_control (ADR-128), over
     the live DOM, plus the shortest address that resolves back to a control
     and a version stamp for the numbering itself. Kept as one fragment so the
     snapshot, the resolver and the risk read use the same arithmetic. */
  const _rows = () => [...document.querySelectorAll("[data-h]")].map(e => ({
    e: e, selector: e.getAttribute("data-h"),
    kind: (e.getAttribute("data-h") || "").split(":")[0],
    id: e.id || null,
    host: (e.parentElement && e.parentElement.closest("[id]") || {}).id || null,
    label: _label(e) }));
  const _index = (rows) => {
    const id = new Map(), label = new Map(), host = new Map(), hl = new Map(), kind = new Map();
    const push = (m, k, r) => { if (k === null || k === undefined) return;
                                if (!m.has(k)) m.set(k, []); m.get(k).push(r); };
    for (const r of rows) {
      if (!r.selector) continue;
      push(id, r.id, r); push(label, r.label, r); push(host, r.host, r); push(kind, r.kind, r);
      if (r.host !== null && r.label !== null) push(hl, r.host + "\u0001" + r.label, r);
    }
    return { id: id, label: label, host: host, hl: hl, kind: kind };
  };
  /* find_control's own order: id, then label, then host, first hit in document
     order; "kind=" names a control the page never named; a trailing "#n" is the
     nth match; a name that matches WHOLE is taken whole, so a label carrying a
     slash is reachable unscoped (ADR-174). */
  const _named = (name, idx) => {
    let nth = 0;
    const m = /^(.*)#(\d+)$/.exec(name);
    if (m) { name = m[1]; nth = parseInt(m[2], 10); }
    let hits = null;
    if (name.indexOf("kind=") === 0) hits = idx.kind.get(name.slice(5)) || [];
    else {
      hits = idx.id.get(name) || idx.label.get(name) || idx.host.get(name) || null;
      if (!hits && name.indexOf("/") >= 0) {
        const i = name.indexOf("/");
        hits = idx.hl.get(name.slice(0, i) + "\u0001" + name.slice(i + 1)) || null;
      }
      hits = hits || [];
    }
    return nth < hits.length ? hits[nth] : null;
  };
  const _byId = (name, idx) => (idx.id.get(name) || [])[0] || null;
  /* The shortest address that RESOLVES BACK to this control. Every candidate is
     tried through the resolver itself, so a label that happens to end in "#2",
     or an id another control answers to first, falls through to the next form
     rather than being published as a name that does not work. */
  const _address = (r, idx, ver) => {
    const cand = [];
    if (r.id) cand.push("#" + r.id);
    if (r.label) cand.push("@" + r.label);
    if (r.host !== null && r.label !== null) {
      const a = idx.hl.get(r.host + "\u0001" + r.label) || [], n = a.indexOf(r);
      cand.push("@" + r.host + "/" + r.label);
      if (n > 0) cand.push("@" + r.host + "/" + r.label + "#" + n);
    }
    if (r.label) {
      const a = idx.label.get(r.label) || [], n = a.indexOf(r);
      if (n > 0) cand.push("@" + r.label + "#" + n);
    }
    if (r.host) cand.push("@" + r.host);
    for (const c of cand) {
      if (/[\r\n]/.test(c) || c.length > 96) continue;
      const got = c.charAt(0) === "#" ? _byId(c.slice(1), idx) : _named(c.slice(1), idx);
      if (got === r) return c;
    }
    return r.selector + "@" + ver;
  };
  /* The numbering's own version: a digest of every selector and id in document
     order, so it moves exactly when an index could mean a different control. */
  const _version = (rows) => {
    let h = 5381;
    const s = rows.map(r => r.selector + "|" + (r.id || "")).join(",");
    for (let i = 0; i < s.length; i++) h = (Math.imul(h, 33) ^ s.charCodeAt(i)) >>> 0;
    return "v" + h.toString(36);
  };
"""

# The numbering's version alone (ADR-189): the settle loop asks for it many
# times and has no use for the rest of a snapshot.
VERSION = "() => {" + LABEL_FN + ADDR_FN + r"""
  return _version(_rows());
}
"""

# One address -> the selector of the moment, or why not (ADR-188).
RESOLVE = "([form, name, stamp]) => {" + LABEL_FN + ADDR_FN + r"""
  const rows = _rows(), idx = _index(rows), now = _version(rows);
  const found = (hit) => ({ ok: true, selector: hit.selector, version: now,
                            label: hit.label, address: _address(hit, idx, now) });
  if (form === ":") {
    const at = rows.filter(r => r.selector === name)[0] || null;
    if (stamp !== now) {
      return { ok: false, why: "stale", now: now, stamp: stamp,
               at: at ? { label: at.label, address: _address(at, idx, now) } : null };
    }
    return at ? found(at) : { ok: false, why: "gone", now: now };
  }
  const hit = form === "#" ? _byId(name, idx) : _named(name, idx);
  return hit ? found(hit) : { ok: false, why: "unnamed", now: now };
}
"""


# Read where a user reads: one round trip, typed, and never a field's contents.
CONTROLS = "(sens) => {" + LABEL_FN + ADDR_FN + ("const PICK_CAP = %d, POOL_CAP = %d;" % (PICK_CAP, POOL_CAP)) + r"""
  const out = [];
  const _rw = _rows(), _idx = _index(_rw), _ver = _version(_rw);
  _rw.forEach(w => {
    const e = w.e;
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    out.push({
      selector: w.selector,
      kind: w.kind,
      // The page's own name for the control (ADR-128): a task says
      // "@control:cName" and is readable; the selector is the moment's.
      id: w.id,
      host: w.host,
      label: w.label,
      // ADR-188: the shortest address that resolves back to THIS control, and
      // which every selector argument accepts. Published beside the selector,
      // never instead of it, so a client that was reading indexes still is.
      address: _address(w, _idx, _ver),
      pane: (e.closest(".pane") || {}).id || null,
      target: e.getAttribute("data-pane") || null,
      type: (e.getAttribute("type") || e.tagName).toLowerCase(),
      visible: r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none",
      enabled: !e.disabled && !e.readOnly,
      selected: e.classList.contains("on"),
      commandable: !e.disabled && !e.readOnly && e.type !== "password",
      // ADR-191: WHAT IS IN IT, under SENSITIVE_READ and never otherwise.
      // The redaction line has promised since ADR-108 that entered values are
      // "omitted; use read-control with SENSITIVE_READ enabled", and a client
      // holding that rung had to spend one call per control to collect what
      // the snapshot could have said in the one it was already taking. It also
      // made the observation's stamp (ADR-191) a lie by omission: a set-text
      // that entered a name moved nothing the snapshot could see, so the diff
      // of the act that entered data -- which is what these pages are FOR --
      // answered `nothing changed`. A password is never read: `commandable`
      // already excludes it, and this reads nothing that is not commandable.
      value: (!sens || !(!e.disabled && !e.readOnly && e.type !== "password")) ? undefined
             : (e.type === "checkbox" || e.type === "radio") ? (e.checked ? "on" : "off")
             : (e.value === undefined || e.value === null) ? undefined
             : String(e.value).slice(0, 200),
    });
  });
  // Option VALUES of the page's selects (capped): a client forming a
  // choose-option needs a value that exists, and an option is a choice the
  // page offers, not something a user typed (ADR-117 argument pools). And
  // per select (ADR-124): a value from one select is "no such option" on
  // another, so the union alone left choose-option refused six of six on a
  // page with five selects. The pairs are published as argument SETS.
  const opts = new Set(), choices = [], lists = [];
  document.querySelectorAll("select[data-h]").forEach(sel => {
    const all = [...sel.options];
    const take = all.slice(0, PICK_CAP);
    take.forEach(o => {
      if (opts.size < POOL_CAP) opts.add(String(o.value));
      if (choices.length < POOL_CAP && !sel.disabled)
        choices.push({ selector: sel.getAttribute("data-h"), value: String(o.value) });
    });
    lists.push({ selector: sel.getAttribute("data-h"), kind: "select",
                 host: (sel.parentElement && sel.parentElement.closest("[id]") || {}).id || null,
                 shown: take.length, of: all.length });
  });
  // A picker's options, as (selector, label) SETS (ADR-128): the labels a
  // reader would type are the page's, not the manifest's examples -- the
  // first walk of every page left pick undriven on five pages whose pickers
  // offer no genus. Capped per picker; the label is the option's name
  // without its sub-line.
  const picks = [];
  document.querySelectorAll(".fek-pick .search[data-h]").forEach(s => {
    const root = s.closest(".fek-pick");
    // ADR-190: WHAT THE PICKER OFFERS, not a sample of it. This took six of
    // however many there were, and a blind operator (ADR-187) counted six
    // published against twenty-eight the picker accepted -- a pool that
    // undersells teaches a client that the pool is not the answer, which is
    // the opposite of what a pool is for. Capped, and the cap is REPORTED:
    // `pickers` below says shown-of-how-many per picker, so a client can see
    // that it has the whole list rather than assume it.
    const all = [...root.querySelectorAll(".opt")];
    const take = all.slice(0, PICK_CAP);
    take.forEach(o => {
      const c = o.cloneNode(true); c.querySelectorAll("small").forEach(x => x.remove());
      const label = (c.textContent || "").replace(/\s+/g, " ").trim().slice(0, 80);
      if (label && picks.length < POOL_CAP) picks.push({ selector: s.getAttribute("data-h"), value: label });
    });
    lists.push({ selector: s.getAttribute("data-h"), kind: "pick",
                 host: (s.parentElement && s.parentElement.closest("[id]") || {}).id || null,
                 shown: take.length, of: all.length });
  });
  return { route: (document.querySelector(".pane.on") || {}).id || null,
           title: document.title,
           // ADR-188: the numbering's own version. A selector carrying a
           // different one is refused rather than resolved to whatever moved
           // into that index.
           version: _ver,
           optionValues: [...opts],
           optionChoices: choices,
           pickChoices: picks,
           // ADR-190: every list the page offers, with how much of it is
           // published. A filter takes options OUT of the document on some of
           // these pages, so "of" is what the picker offers NOW, not what it
           // could offer -- which is the honest number for a client deciding
           // whether to clear a filter before it picks.
           pickers: lists,
           panes: [...document.querySelectorAll(".pane")].map(p => p.id),
           tabs: [...document.querySelectorAll(".tab[data-pane]")].map(
                   t => ({ pane: t.getAttribute("data-pane"),
                           label: (t.textContent || "").trim().slice(0, 40),
                           open: t.classList.contains("on") })),
           controls: out };
}
"""

# A FEK picker, driven the way a finger drives it (ADR-128): type into its
# filter, then click the first option still showing. The option list is what
# the page offers; a value nothing matches is refused, never typed in blind.
PICK = r"""
([sel, value]) => {
  const s = document.querySelector('[data-h="' + sel + '"]');
  if (!s) return { ok: false, why: "gone" };
  // WHETHER IT IS A PICKER IS STRUCTURAL; WHETHER IT HAS OPTIONS IS A FACT OF
  // THE MOMENT (ADR-145). This guard used to ask for a ".opt" before typing
  // anything, and a picker whose filter currently matches NOTHING has none --
  // the collection sheet removes non-matching options from the DOM rather than
  // hiding them. So one refused pick left the picker unusable for the rest of
  // the session: every later pick answered "not a picker", including the one
  // that would have cleared the filter. A control cannot stop being a picker
  // because of what someone typed into it.
  const pick = s.closest(".fek-pick");
  const root = pick || s.parentElement;
  // Without a .fek-pick to stand on, the options must be THIS control's own --
  // its siblings, or the list right beside it. Searching the whole subtree of
  // whatever happens to be the parent let a pick aimed at a plain text input
  // reach the options of a picker elsewhere in the same section and click one.
  if (!root || (!pick && !root.querySelector(":scope > .opt, :scope > .opts > .opt")))
    return { ok: false, why: "not a picker" };
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  set.call(s, String(value));
  s.dispatchEvent(new Event("input", { bubbles: true }));
  const want = String(value).trim().toLowerCase();
  const opts = [...root.querySelectorAll(".opt")].filter(o => {
    const r = o.getBoundingClientRect(), cs = getComputedStyle(o);
    return r.width > 0 && r.height > 0 && cs.display !== "none" && cs.visibility !== "hidden";
  });
  // The option's own label is what a reader matches against: the name
  // without its <small> sub-line (the picker filters on both).
  const nameOf = o => { const c = o.cloneNode(true); c.querySelectorAll("small").forEach(x => x.remove());
                        return (c.textContent || "").replace(/\s+/g, " ").trim().toLowerCase(); };
  const exact = opts.find(o => nameOf(o) === want)
             || opts.find(o => nameOf(o).startsWith(want));
  // Not exact, not a prefix: the value is a fragment the filter still
  // narrowed to one option ('Tarnok' in "S. leucophylla 'Tarnok' x ...")
  // -- that one is what a finger would tap. Two or more left is a guess,
  // and a guess is refused, not taken.
  const hit = exact || (opts.length === 1 ? opts[0] : null);
  if (!hit) return { ok: false, why: opts.length ? "ambiguous: " + opts.length + " options match " + JSON.stringify(String(value))
                                                 : "no option matches " + JSON.stringify(String(value)) };
  hit.click();
  return { ok: true, chose: (hit.textContent || "").replace(/\s+/g, " ").trim().slice(0, 80), offered: opts.length };
}
"""

# The page's REPORT (ADR-128): every figure the kit's pages render as a
# labelled value -- a .tile or a .stat .k with a .l label and a .v value --
# every box that carries an analysis (ids beginning an/out/rep/res/sum), and
# the row counts of every list. Read now, capped, values only as the page
# shows them; never a field a user typed.
REPORT = r"""
() => {
  const vis = e => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && cs.display !== "none" && cs.visibility !== "hidden"; };
  const norm = t => (t || "").replace(/\s+/g, " ").trim();
  // A figure is any element that shows a .v value beside a .l label: the
  // kit's .tile, the selection log's .stat .st, the benches' .stat .k, and
  // whatever a page calls it next -- the pair is the convention, the class
  // is not (the first draft named four classes and read nothing on the
  // selection log, whose figures are .st).
  const figures = {}, order = [], seen = new Set(), by = {}, sources = {};
  document.querySelectorAll(".v").forEach(v => {
    const t = v.parentElement;
    if (!t || seen.has(t) || order.length >= 200) return;
    // the label is a sibling .l, or a sibling .k that is itself the label
    // (the visualizer's <span class=k>Nodes</span><span class=v>13</span>)
    const l = [...t.children].find(c => c.classList.contains("l")) ||
              [...t.children].find(c => c.classList.contains("k") && !c.querySelector(".v"));
    if (!l || v.parentElement !== t) return;
    seen.add(t);
    const key = norm(l.textContent).slice(0, 60);
    if (!key) return;
    // A unit set in <small> inside the value is a unit, not a digit: read
    // "38.9 mol/m²/d", not "38.9mol/m²/d".
    const vc = v.cloneNode(true);
    vc.querySelectorAll("small").forEach(x => x.insertAdjacentText("beforebegin", " "));
    const val = norm(vc.textContent).slice(0, 120);
    let k = key, n = 2;
    while (k in figures) { k = key + " #" + (n++); }
    figures[k] = val;
    order.push(k);
    // ...and by the box it sits in: a label is a fact of its box (the
    // relevé's pack shows "families 23" and its analysis "families 2").
    const box = (t.parentElement && t.parentElement.closest("[id]") || {}).id || "";
    if (box) { const b = by[box] = by[box] || {}; let bk = key, m = 2;
               while (bk in b) { bk = key + " #" + (m++); }        // "doubling time" twice in one box
               b[bk] = val; }
    // ...and WHERE IT WAS READ FROM (ADR-171): the id of the value element
    // itself when it has one (the visualizer's #mH, the notebook's #mrC), else
    // the pair's own id (a .tile with an id), else the box. Provenance, not a
    // second value: the readable-figures audit counts a page's written elements
    // by id, and without this a figure read here under its label was counted
    // as one no task could read, because its id is not named like a box.
    const src = v.id || t.id || box;
    if (src) sources[k] = src;
  });
  // A box is read whether or not its pane is open: a report a pane hides is
  // still the page's report, and the robot compares figures, not pixels. Which
  // boxes a reader could see right now is reported beside them, not used to
  // drop them -- the first draft filtered by visibility and read nothing at
  // rest on a page whose analysis lives behind a closed tab.
  // What counts as a box is the kit's naming: an analysis (an*), an output
  // (*Out), a *Box, *Stats, *Plan, *Matrix, *Verdict, *Warn, *Tell, *Note,
  // *Advice, *Refuse, *Table, *Chart, *Typical, *List, *Grid, *Export,
  // *Lint, *Cmd, *Meas, *Help, *Card, *Legend, *Msg, *Check, *Read, *Desc,
  // *Left, *Res (ADR-129: the keys' kres/kRes, the visualizer's msg, the
  // proofs' spCheck, the lab's readings), *Board (ADR-171: the pheno
  // tracker's rankBoard and momBoard -- a ranked run of scored plants and the
  // mothers held in veg, figures both, and the ranking board was skipped by
  // the readable audit as an entry host because each row carries buttons)
  // (any case, hyphens allowed: the experiment guide's eco-out), and the few
  // plain names (coherence, report, results, outputs, toast, journal). Capped
  // in count and in characters; a list's rows are counted separately below.
  // "station-<key>" is the lab's own name for a station (ADR-135): the session
  // key the engine uses, so a figure read off the page is read under the same
  // name the engine reports it under.
  const BOX = /^(an|out|rep|res|sum)[A-Za-z0-9-]*$|(box|out|stats?|plan|matrix|verdict|tiles|warn|coh|tell|note|advice|refuse|table|chart|typical|list|results|grid|export|lint|cmd|meas|help|card|legend|msg|check|read|desc|left|res|board)$|^(coherence|report|results|outputs|toast|journal|tree)$|^station-[a-z]+$/i;
  const boxes = {}, shown = [], lines = {};
  // ADR-190: A BOX'S TEXT, SPLIT WHERE THE PAGE SPLITS IT. `boxes` is one run
  // of text, which is what "bean, common20you plan to keep20" looks like to a
  // reader (ADR-187), and every task in the kit holds it exactly as it is --
  // so this is published BESIDE it rather than instead of it. The rule is the
  // page's own: a LEAF BLOCK is a block element containing no block element,
  // and its text is one line. `figures` and `by` remain the precise read; this
  // is for the prose and the rows between them.
  const BLOCK = "p,li,tr,div,section,h1,h2,h3,h4,h5,figcaption,output,label,pre,blockquote,dt,dd";
  const leafLines = (e) => {
    const blocks = [...e.querySelectorAll(BLOCK)].filter(b => !b.querySelector(BLOCK));
    const out = (blocks.length ? blocks.map(b => norm(b.textContent))
                               : [norm(e.textContent)]).filter(Boolean);
    // a line cut at the cap is trimmed again: the cut lands mid-sentence and
    // would otherwise hand back a trailing space that is not in the page
    return out.slice(0, 40).map(t => t.slice(0, 300).replace(/\s+$/, ""));
  };
  document.querySelectorAll("[id]").forEach(e => {
    if (!BOX.test(e.id)) return;
    if (Object.keys(boxes).length >= 64) return;
    boxes[e.id] = norm(e.textContent).slice(0, 4000);
    lines[e.id] = leafLines(e);
    if (vis(e)) shown.push(e.id);
  });
  // Tables, row by row, cell by cell (capped): the recipe card's
  // ingredient/quantity pairs and the trial's entry means are tables, and a
  // blob of text loses which quantity belongs to which row.
  const tables = {};
  document.querySelectorAll("table").forEach((t, i) => {
    if (Object.keys(tables).length >= 16) return;
    const host = (t.id || (t.parentElement && t.parentElement.closest("[id]") || {}).id || "table") ;
    let key = host, n = 2;
    while (key in tables) { key = host + " #" + (n++); }
    tables[key] = [...t.querySelectorAll("tr")].slice(0, 40).map(
      tr => [...tr.children].slice(0, 8).map(c => norm(c.textContent).slice(0, 60)));
  });
  // ADR-190: WHAT THE PAGE SAYS ABOUT ITSELF. The pheno tracker prints its
  // scoring rule on the page -- a weighted MEAN over the sum of the weights,
  // and an unscored trait dropped rather than counted as a 1 -- and a blind
  // operator had to recover it by experiment, because the door published
  // every figure the page computed and nothing about how. `.hint` and `.fine`
  // are the kit's own two conventions for that prose (21 and 24 pages), so
  // they are what is handed over, each with the identified thing it sits in.
  // Not interpreted: quoted. The door does not know the rule, and says so by
  // giving the reader the page's own words for it.
  const rules = [...document.querySelectorAll("p.hint, p.fine, .hint, .fine")]
    .filter(e => !e.querySelector(".hint, .fine"))
    .slice(0, 40)
    .map(e => ({ t: norm(e.textContent).slice(0, 400),
                 host: (e.parentElement && e.parentElement.closest("[id]") || {}).id || null }))
    .filter(r => r.t);
  // The page's headings, in order (ADR-129): a reference page has no
  // figures and no boxes, and its structure IS its report.
  const headings = [...document.querySelectorAll("h1, h2, h3")].slice(0, 80)
    .map(h => norm(h.textContent).slice(0, 120));
  // THE CHARTS (ADR-140). ADR-128 held that SVG text and geometry are outside
  // read-report, so every page that DRAWS published numbers no task could hold:
  // a chart that plots the wrong series looks exactly like one that plots the
  // right series. Read in the svg's OWN coordinate space (the attributes the
  // page computed), not in rendered pixels -- the rendered size depends on the
  // viewport and the page's own arithmetic does not, so an oracle can
  // recompute it.
  const charts = {};
  const num = a => { const v = parseFloat(a); return isFinite(v) ? Math.round(v * 100) / 100 : null; };
  document.querySelectorAll("svg").forEach(sv => {
    if (Object.keys(charts).length >= 16 || !vis(sv)) return;
    const host = sv.id || ((sv.closest("[id]") || {}).id) || "svg";
    let key = host, n = 2;
    while (key in charts) { key = host + " #" + (n++); }
    const texts = [...sv.querySelectorAll("text")].slice(0, 40).map(t => (
      {t: norm(t.textContent).slice(0, 60), x: num(t.getAttribute("x")), y: num(t.getAttribute("y"))}));
    // Marks, by what they are. A count per tag is what says "this chart plots
    // five sites" or "this histogram has twelve bars".
    const marks = {};
    ["circle", "rect", "path", "line", "polyline", "polygon", "ellipse"].forEach(tag => {
      const k = sv.querySelectorAll(tag).length;
      if (k) marks[tag] = k;
    });
    // The longest drawn series: how many points the biggest polyline or path
    // carries. A curve that lost half its samples still looks like a curve.
    // A path's points are every command that ends somewhere (ADR-182): a
    // step line is drawn with H and V and read as ONE point under [ML].
    let longest = 0;
    [...sv.querySelectorAll("polyline, polygon")].slice(0, 40).forEach(e => {
      const pts = (e.getAttribute("points") || "").trim().split(/\s+/).filter(Boolean).length;
      if (pts > longest) longest = pts;
    });
    [...sv.querySelectorAll("path")].slice(0, 40).forEach(e => {
      const pts = ((e.getAttribute("d") || "").match(/[MLHVCSQTAmlhvcsqta]/g) || []).length;
      if (pts > longest) longest = pts;
    });
    // TEXT THAT LINES UP, in order, without the page having to declare
    // anything. Named for what it IS rather than what it usually means: the
    // longest ROW of text nodes sharing a y, read left to right, and the
    // longest COLUMN sharing an x, read top to bottom. On a chart with axes
    // that row is the x tick sequence and that column is the y tick sequence;
    // on the food web it is the trophic level headings and the species names.
    // Calling it "ticks" would have been a reader deciding what a drawing
    // means, which is the page's business and not this file's.
    const rowsAt = {}, colsAt = {};
    texts.forEach(t => {
      if (t.y !== null) { const k = Math.round(t.y); (rowsAt[k] = rowsAt[k] || []).push(t); }
      if (t.x !== null) { const k = Math.round(t.x); (colsAt[k] = colsAt[k] || []).push(t); }
    });
    const pick = (groups, along, order) => {
      let best = null;
      Object.keys(groups).forEach(k => {
        const g = groups[k];
        if (g.length < 3) return;
        if (!best || g.length > best.length || (g.length === best.length && order(+k, +bestK))) {
          best = g; bestK = +k;
        }
      });
      return best ? best.slice().sort((a, b) => a[along] - b[along]).map(t => t.t) : [];
    };
    let bestK = 0;
    const aligned = {row: pick(rowsAt, "x", (a, b) => a > b),   // the lowest row of labels
                     col: pick(colsAt, "y", (a, b) => a < b)};  // the leftmost column
    // A LABELLED POINT: the nearest mark to each text, in the svg's own units.
    // The ordination draws circle.dot then text.pt at x+8 -- the pairing is the
    // page's, and reading it is how a task can say where a named site landed.
    const centres = [];
    const r2 = v => Math.round(v * 100) / 100;
    [...sv.querySelectorAll("circle, ellipse")].slice(0, 60).forEach(c => {
      const x = num(c.getAttribute("cx")), y = num(c.getAttribute("cy"));
      if (x !== null && y !== null) centres.push([x, y]);      // an unplaced mark is nowhere
    });
    [...sv.querySelectorAll("rect")].slice(0, 60).forEach(r => {
      const x = num(r.getAttribute("x")), y = num(r.getAttribute("y")),
            w = num(r.getAttribute("width")), h = num(r.getAttribute("height"));
      if (x !== null && y !== null) centres.push([r2(x + (w || 0) / 2), r2(y + (h || 0) / 2)]);
    });
    const points = {};
    texts.forEach(t => {
      if (t.x === null || t.y === null || Object.keys(points).length >= 40) return;
      let near = null, d2 = 900;                       // within 30 units, squared
      centres.forEach(c => {
        if (c[0] === null || c[1] === null) return;
        const q = (c[0] - t.x) * (c[0] - t.x) + (c[1] - t.y) * (c[1] - t.y);
        if (q < d2) { d2 = q; near = c; }
      });
      if (near && t.t && !(t.t in points)) points[t.t] = near;
    });
    // WHERE EACH PATH LIES (ADR-182). The lab draws every bar as a rounded
    // path (M V Q H Q V Z) and every curve as one path, and neither has a
    // centre attribute to read -- so a bar chart was read as a row of
    // transparent hit-rects, all at one y, and the bars' heights were
    // nowhere in the report. Each path's box is the smallest [x0, y0, x1, y1]
    // holding every point a command ENDS at, absolute or relative, in the
    // svg's own units; a curve's control points are not on the curve and are
    // not counted, which for the lab's bars (control points at the corners)
    // changes nothing and for a wide curve understates the box a little.
    const spans = [];
    const NEED = {M: 2, L: 2, H: 1, V: 1, C: 6, S: 4, Q: 4, T: 2, A: 7};
    [...sv.querySelectorAll("path")].slice(0, 40).forEach(e => {
      const toks = (e.getAttribute("d") || "").match(/[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:e[-+]?\d+)?/gi) || [];
      let cmd = "", cx = 0, cy = 0, sx = 0, sy = 0, x0 = null, y0 = null, x1 = null, y1 = null, i = 0;
      while (i < toks.length) {
        if (/^[a-zA-Z]$/.test(toks[i])) {
          cmd = toks[i++];
          if (cmd === "Z" || cmd === "z") { cx = sx; cy = sy; continue; }
        }
        const up = cmd.toUpperCase(), rel = cmd !== up, n = NEED[up];
        if (n === undefined) break;
        const a = toks.slice(i, i + n).map(parseFloat); i += n;
        if (a.length < n || a.some(v => !isFinite(v))) break;
        if (up === "H") { cx = (rel ? cx : 0) + a[0]; }
        else if (up === "V") { cy = (rel ? cy : 0) + a[0]; }
        else { cx = (rel ? cx : 0) + a[n - 2]; cy = (rel ? cy : 0) + a[n - 1]; }
        if (x0 === null || cx < x0) x0 = cx; if (x1 === null || cx > x1) x1 = cx;
        if (y0 === null || cy < y0) y0 = cy; if (y1 === null || cy > y1) y1 = cy;
        if (up === "M") { sx = cx; sy = cy; cmd = rel ? "l" : "L"; }   // implicit pairs after M are lines
      }
      if (x0 !== null) spans.push([r2(x0), r2(y0), r2(x1), r2(y1)]);
    });
    const vb = (sv.getAttribute("viewBox") || "").trim();
    // ...and the mark centres themselves, in document order. `points` pairs a
    // mark with a label the page happened to put beside it; a chart whose dots
    // carry no labels still plots them somewhere, and where is the claim.
    charts[key] = {viewBox: vb, texts: texts, n: texts.length, marks: marks,
                   longest: longest, aligned: aligned, points: points,
                   at: centres.slice(0, 40), spans: spans};
  });
  const rows = {};
  document.querySelectorAll(".row2").forEach(r => {
    const p = r.parentElement; const id = p && p.id ? "#" + p.id : (p ? p.className.split(" ")[0] : "?");
    rows[id] = (rows[id] || 0) + 1;
  });
  return { figures: figures, by: by, order: order, sources: sources, boxes: boxes, shown: shown, rows: rows,
           lines: lines, rules: rules,
           tables: tables, headings: headings, charts: charts,
           route: (document.querySelector(".pane.on") || {}).id || null };
}
"""

# SENSITIVE_READ. Bounded on every axis: one control, capped text, capped option
# lists, and a truncated flag rather than a silent clip.
READ_ONE = "(sel) => {" + LABEL_FN + ADDR_FN + r"""
  const e = document.querySelector('[data-h="' + sel + '"]');
  if (!e) return null;
  if (e.type === "password") return { refused: "password" };
  const cap = (s, n) => { s = String(s == null ? "" : s);
    return { text: s.slice(0, n), truncated: s.length > n }; };
  const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
  const o = { selector: sel, kind: sel.split(":")[0], tag: e.tagName.toLowerCase(),
              type: (e.getAttribute("type") || "").toLowerCase(),
              // ADR-141: the page's own names for it. read-control used to
              // answer about a selector and nothing else -- and the selector is
              // the one thing the caller already had. A blind operator reading
              // controls one at a time could not tell which of them was the
              // "Add stem" the task named, because the answer never said.
              id: e.id || null, label: _label(e),
              host: (e.parentElement && e.parentElement.closest("[id]") || {}).id || null,
              pane: (e.closest(".pane") || {}).id || null,
              // ADR-190: and the address to call it by. A control read one at
              // a time is being IDENTIFIED, and the answer that leaves out the
              // name the caller would use next is the answer that sends them
              // back to the snapshot.
              address: (() => { const rows = _rows(), idx = _index(rows);
                                const me = rows.filter(r => r.e === e)[0];
                                return me ? _address(me, idx, _version(rows)) : null; })(),
              // Read now, not at discovery. Visibility on these pages is a
              // property of the moment: a pane opened, a row added, a widget
              // rebuilt. Judging it from a snapshot taken before the seed put
              // 105 live controls of one page in the hidden bucket.
              visible: r.width > 0 && r.height > 0 && cs.visibility !== "hidden" &&
                       cs.display !== "none",
              enabled: !e.disabled && !e.readOnly,
              selected: e.classList.contains("on") };
  const v = cap(e.value === undefined ? "" : e.value, 8000);
  o.value = v.text; o.valueTruncated = v.truncated;
  const t = cap(e.textContent, 2000);
  o.text = t.text; o.textTruncated = t.truncated;
  if (e.type === "checkbox" || e.type === "radio") {
    o.checkbox = { checked: !!e.checked, name: String(e.name || "") };
  }
  if (e.type === "file") {
    o.file = { accept: String(e.accept || ""), multiple: !!e.multiple,
               taken: e.files ? e.files.length : 0,
               names: e.files ? [...e.files].map(f => f.name).slice(0, 20) : [] };
  }
  if (e.tagName === "SELECT") {
    o.options = [...e.options].slice(0, 200).map(x => ({ value: String(x.value),
      label: (x.textContent || "").trim().slice(0, 120) }));
    o.optionsTruncated = e.options.length > 200;
  }
  const step = e.closest(".fek-step");
  if (step) {
    const val = step.querySelector(".val");
    const raw = val ? ((val.tagName === "INPUT" || val.tagName === "TEXTAREA")
                        ? val.value : val.textContent) : null;
    const n = parseFloat(String(raw).replace(/[^0-9.\-]/g, ""));
    o.step = { raw: String(raw).trim().slice(0, 24), number: isFinite(n) ? n : null };
  }
  const slide = e.closest(".fek-slide");
  if (slide || e.type === "range") {
    o.slider = { value: String(e.value), min: String(e.min || ""),
                 max: String(e.max || ""), stepAttr: String(e.step || ""),
                 shown: ((slide || e.parentElement || {}).innerText || "")
                          .replace(/\s+/g, " ").trim().slice(0, 120) };
  }
  const pick = e.closest(".fek-pick");
  if (pick) {
    const vis = [...pick.querySelectorAll(".opt")].filter(x => {
      const r = x.getBoundingClientRect(), s = getComputedStyle(x);
      return r.height > 0 && s.display !== "none" && s.visibility !== "hidden"; });
    o.picker = { visible: vis.length,
      labels: vis.slice(0, 120).map(x => (x.textContent || "").replace(/\s+/g, " ").trim().slice(0, 80)),
      labelsTruncated: vis.length > 120 };
  }
  const p = e.parentElement;
  if (p) {
    const sibs = [...p.children].filter(c => c.getAttribute && c.getAttribute("data-h"));
    if (sibs.length > 1)
      o.group = { size: sibs.length,
                  selected: sibs.filter(c => c.classList.contains("on")).length,
                  meSelected: e.classList.contains("on") };
  }
  return o;
}
"""

# ---------------------------------------------------------------------------
# What an activation would touch (ADR-141)
# ---------------------------------------------------------------------------
# `activate` was declared DESTRUCTIVE from ADR-112 to ADR-140 for an honest
# reason: one selector may resolve to "Add stem" and the next to "Clear trial",
# and deciding which from a label was called a guess. Four blind operators, each
# given only a task's goal and this door, independently found what that cost:
# a supervised session holding SENSITIVE_READ, DRAFT and MUTATE can fill every
# field on a data-entry page and commit none of them, because every button on
# these pages is pressed through `activate`. Three finished only by being handed
# DESTRUCTIVE -- which is to say by being handed the wipe-the-store rung to
# press "Add stem" -- and the fourth, refusing to escalate, could not enter the
# data at all.
#
# So the guess is made, and its direction is what makes it safe. The classifier
# only ever RAISES: a control whose name reads as destroying work, and a control
# that cannot be identified at all, are held at DESTRUCTIVE; everything else
# stays at the declared MUTATE floor. A false positive costs one refusal a
# session can lift deliberately. A false negative would be the old behaviour of
# every other button, which is what this replaces.
#
# The vocabulary is not invented: it is the destructive vocabulary an inventory
# of all 41 routed pages actually found across 1,470 activatable controls --
# Clear, Clear trial, Clear all runs, Delete, Reset, Start over, Undo, the bare
# row-removing mark, "Forget this device's copy", "remove last".
DESTRUCTIVE_LABEL = re.compile(
    r"(?:^|\b)(?:clear|delete|remove|erase|wipe|discard|revert|undo|forget|trash"
    r"|purge|abandon|reset|start over|restart)\b", re.I)
# A button named by a mark. Two sets, because two of these glyphs are not marks
# at all when a scientist writes them. The kit's own labels, measured across all
# 41 routed pages, say so: the removers are U+2715 ("\u2715honeybee0",
# "subject 1 \u2715"), while U+00D7 is a MULTIPLICATION sign -- "1\u00d7", "2\u00d7",
# "4\u00d7" on a playback speed control, and "Copy host \u00d7 taxon matrix" on the
# parasite page. Raising those three speed buttons and an export would have been
# the classifier crying wolf on its first day.
DESTRUCTIVE_MARK = ("\u2715", "\u2716", "\u2717", "\u2718", "\u232b", "\U0001f5d1")
# ...and the ambiguous ones fire only when the mark is the WHOLE label, which is
# the close button and nothing else.
AMBIGUOUS_MARK = ("\u00d7", "\u2a2f")


def destroys(label, title=""):
    """Does this control's NAME say it removes something? -> reason, or None.

    A mark counts at the START or the END of a label -- a remover is a mark
    attached to the thing it removes ("\u2715honeybee0", "subject 1 \u2715") or a mark
    on its own. In the MIDDLE it is punctuation between words, which is how
    "Copy host \u00d7 taxon matrix" would otherwise have read as a delete."""
    for t in (label, title):
        s = (t or "").strip()
        if not s:
            continue
        for m in DESTRUCTIVE_MARK:
            if s.startswith(m) or s.endswith(m):
                return ("its label is %r, this kit's mark for removing a row or a chip" % s[:40])
        if s in AMBIGUOUS_MARK:
            return "its label is %r, a close mark and nothing else" % s
        hit = DESTRUCTIVE_LABEL.search(s)
        if hit:
            return "its label %r reads as %s" % (s[:40], hit.group(0).lower())
    return None


# The identity of one control, asked at the moment of the call rather than read
# from a snapshot taken before it. `ofKind` is how many selectors of that kind
# the page has NOW, which is what a caller holding a stale index needs to hear.
IDENTIFY = "(sel) => {" + LABEL_FN + r"""
  const kind = String(sel).split(":")[0];
  const n = document.querySelectorAll('[data-h^="' + kind + ':"]').length;
  const e = document.querySelector('[data-h="' + sel + '"]');
  if (!e) return { found: false, kind: kind, ofKind: n };
  return { found: true, selector: sel, kind: kind, ofKind: n,
           id: e.id || null,
           host: (e.parentElement && e.parentElement.closest("[id]") || {}).id || null,
           pane: (e.closest(".pane") || {}).id || null,
           label: _label(e),
           title: String(e.getAttribute("title") || "").slice(0, 80) };
}
"""

ACT = r"""
([sel, kind, value]) => {
  const e = document.querySelector('[data-h="' + sel + '"]');
  if (!e) return { ok: false, why: "gone" };
  if (kind === "text") {
    // The first robot (ADR-117) sent set-text to a button and got "TypeError:
    // Illegal invocation" from the value setter -- a raise, filed as the page
    // failing. A wrong-kind selector is the CALLER's, and says so.
    if (e.tagName !== "TEXTAREA" && e.tagName !== "INPUT") return { ok: false, why: "not a text control" };
    if (e.tagName === "INPUT" && ["button", "submit", "checkbox", "radio", "file", "range", "reset"].indexOf(e.type) >= 0)
      return { ok: false, why: "not a text control" };
    const proto = e.tagName === "TEXTAREA" ? HTMLTextAreaElement : HTMLInputElement;
    const set = Object.getOwnPropertyDescriptor(proto.prototype, "value").set;
    set.call(e, String(value));
    e.dispatchEvent(new Event("input", { bubbles: true }));
    e.dispatchEvent(new Event("change", { bubbles: true }));
    return { ok: true, value: String(e.value) };
  }
  if (kind === "range") {
    if (e.tagName !== "INPUT" || e.type !== "range") return { ok: false, why: "not a slider" };
    e.value = String(value);
    e.dispatchEvent(new Event("input", { bubbles: true }));
    e.dispatchEvent(new Event("change", { bubbles: true }));
    return { ok: true, value: String(e.value) };
  }
  if (kind === "option") {
    if (e.tagName !== "SELECT") return { ok: false, why: "not a select" };
    const m = [...e.options].find(o => String(o.value) === String(value) ||
                                       (o.textContent || "").trim() === String(value));
    if (!m) return { ok: false, why: "no such option" };
    e.value = m.value;
    e.dispatchEvent(new Event("change", { bubbles: true }));
    return { ok: true, value: String(e.value) };
  }
  if (kind === "step") {
    const w = e.closest(".fek-step");
    if (!w) return { ok: false, why: "not a stepper" };
    const btns = [...w.querySelectorAll("button")];
    const b = btns.find(x => (x.textContent || "").indexOf(value === "up" ? "+" : "-") >= 0 ||
                             (value === "down" && (x.textContent || "").indexOf("−") >= 0));
    const t = b || (value === "up" ? btns[btns.length - 1] : btns[0]);
    if (!t) return { ok: false, why: "stepper has no buttons" };
    t.click();
    return { ok: true };
  }
  // A link that leaves the document is not an activation of this page: the
  // robot's walk of every page (ADR-124) followed one to another kit page
  // and walked THAT, and on douglas-explorer followed one to the internet,
  // after which reload failed with ERR_INTERNET_DISCONNECTED and was filed
  // as the page failing. Leaving is `open`'s job. Same-document links (#id)
  // and links with no destination are still clicks.
  const a = e.closest("a[href]");
  if (a) {
    const href = a.getAttribute("href") || "";
    if (href && !href.startsWith("#") && !href.startsWith("javascript:")) {
      return { ok: false, why: "a link that leaves the page (" + href.slice(0, 60) + "): use open" };
    }
  }
  e.click();
  return { ok: true };
}
"""

# Everything a verdict may be computed from, in one round trip. SENSITIVE_READ:
# rendered text on these pages is largely what somebody typed into them.
PAGE_STATE = r"""
() => {
  const h = s => { let x = 0; for (let i = 0; i < s.length; i++) x = (x * 31 + s.charCodeAt(i)) | 0; return x; };
  const t = document.body ? (document.body.innerText || "") : "";
  const fields = [...document.querySelectorAll("input,textarea,select")]
    .filter(e => !e.readOnly && !e.disabled &&
                 e.type !== "hidden" && e.type !== "file" && e.type !== "range");
  const cls = {};
  document.querySelectorAll("[class]").forEach(e => {
    String(e.className).split(/\s+/).forEach(c => { if (c) cls[c] = (cls[c] || 0) + 1; });
  });
  // NaN and [object Object] are never English. "undefined" and "null" are:
  // ecology-lab writes "R = 0: the estimate is undefined" as a careful sentence,
  // and field-notebook says the same thing, and both were reported as values
  // leaking. So those two count only where a VALUE belongs -- in a readout slot
  // or a form control -- and not in a paragraph.
  const junk = t.match(/\bNaN\b|\[object Object\]/);
  const SLOT = ".v,.val,.num,.stat,.reading,output,input,textarea,.tile .v,.big,.res";
  let slot = null;
  for (const e of document.querySelectorAll(SLOT)) {
    const s = String(e.tagName === "INPUT" || e.tagName === "TEXTAREA"
                       ? e.value : e.textContent).trim();
    if (/^(NaN|undefined|null|\[object Object\])$/.test(s) ||
        /\bNaN\b|\[object Object\]/.test(s)) {
      slot = { where: e.tagName.toLowerCase() + "." +
                      String(e.className || "").split(/\s+/)[0], text: s.slice(0, 60) };
      break;
    }
  }
  return {
    text: t.slice(0, 40000), thash: h(t), len: t.length,
    filled: fields.filter(e => String(e.value || "").trim() !== "").length,
    fieldn: fields.length,
    vals: h(fields.map(e => String(e.value)).join("")),
    on: [...document.querySelectorAll(".on")].map(e =>
          (e.getAttribute("data-h") || "") + "/" + e.className + "/" +
          (e.textContent || "").slice(0, 16)).join("|"),
    cls: cls, els: document.querySelectorAll("*").length,
    outs: window.__S ? window.__S.out.length : 0,
    toasts: window.__S ? window.__S.toasts : 0,
    choosers: window.__S ? window.__S.choosers : 0,
    // A page can refuse in more than one voice. ethogram explains a bad pack
    // through alert(), and the harness -- counting only toasts -- reported it as
    // taking a file and saying nothing. Counting one channel and calling it
    // "nothing was said" is the same mistake as counting one kind of control and
    // calling it "everything a user can do".
    said: (window.__H && window.__H.calls
             ? window.__H.calls.filter(c => c.k === "alert" || c.k === "confirm" ||
                                            c.k === "prompt").length : 0),
    toastText: [...document.querySelectorAll(".toast")]
      .map(t => (t.textContent || "").replace(/\s+/g, " ").trim()).join(" / ").slice(0, 120),
    junkTok: junk ? junk[0] : null,
    junkSlot: slot,
    junk: junk ? t.slice(Math.max(0, junk.index - 60), junk.index + 60).replace(/\s+/g, " ") : null,
    panes: document.querySelectorAll(".pane").length,
    onp: document.querySelectorAll(".pane.on").length,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    wide: [...document.querySelectorAll("*")]
      .filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
      .slice(0, 2).map(e => e.tagName.toLowerCase() + "." +
        String(e.className || "").split(/\s+/)[0] + " w=" +
        Math.round(e.getBoundingClientRect().width)),
    errors: (window.__H ? window.__H.errors.splice(0, 3) : []),
  };
}
"""

DROP = r"""
([sel, files]) => {
  const el = document.querySelector('[data-h="' + sel + '"]');
  if (!el) return { ok: false, why: "gone" };
  // Only a registered drop zone. Dispatching drag events at anything else
  // "succeeds" and nothing happens -- a driven that drove nothing (ADR-117).
  if (!el.hasAttribute("data-h-drop")) return { ok: false, why: "not a drop zone" };
  let dt;
  try { dt = new DataTransfer(); } catch (e) { return { ok: false, why: "no DataTransfer" }; }
  for (const f of files) {
    const bin = atob(f.b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    dt.items.add(new File([arr], f.name, { type: f.type }));
  }
  for (const t of ["dragenter", "dragover", "drop"]) {
    el.dispatchEvent(new DragEvent(t, { bubbles: true, cancelable: true, dataTransfer: dt }));
  }
  return { ok: true, dropped: files.length };
}
"""

SET_CHECK = r"""
([sel, want]) => {
  const e = document.querySelector('[data-h="' + sel + '"]');
  if (!e) return { ok: false, why: "gone" };
  if (e.tagName !== "INPUT" || (e.type !== "checkbox" && e.type !== "radio"))
    return { ok: false, why: "not a checkbox" };
  if (e.checked !== want) e.click();
  return { ok: true, checked: !!e.checked };
}
"""

OPEN_PANES = "() => [...document.querySelectorAll('.pane.on')].map(p => p.id)"

# A TOOL THAT ONLY WORKED FOR THE ROBOT (ADR-152). `collect-output` is
# published by THIS plugin -- it is in the manifest, every task may call it, and
# it is the only way to read what leaves a page through a Copy button, a
# download or a print. What it reads is `window.__S`, and `window.__S` was
# installed by tools/swarm.py, as an init script, on the context the ROBOT
# builds. Any other caller -- a task, an audit, a suite, a person driving the
# gateway by hand -- got a page with no __S at all, and `collect-output`
# answered "0 payload(s)": the same answer a page that emitted nothing gives.
# So every Copy button, every download and every print in a 41-page kit whose
# pages produce their real product through exactly those buttons was unreadable
# to every task, and nothing said so. The capture belongs with the tool that
# reads it; swarm.py imports CATCH from here, because a rule written twice is a
# rule that drifts.
CATCH = r"""
// INSTALLED ONCE PER WINDOW. It is now added both as a context init script
// (so it survives open and reload) and evaluated straight into a page that is
// already loaded, and installing the wrappers twice would double-count every
// toast and re-wrap Blob around its own wrapper.
if (!window.__S) {
window.__S = { out: [], toasts: 0, choosers: 0, lastChooser: "" };
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
  // A page cannot be asked where its drop zones are: a drop listener leaves no
  // mark in the markup and no CSS selector finds it. Three pages in this kit
  // take photos and data by drag-and-drop and the harness had never dropped
  // anything on any of them. Stamp the element as the listener is registered.
  try {
    var AEL = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (type, fn, opt) {
      try {
        if (type === "drop") {
          if (this.setAttribute && this.nodeType === 1) this.setAttribute("data-h-drop", "1");
          // A page whose drop target is the WINDOW had no element to stamp, so
          // it published no drop zone and the harness could not drop anything
          // on it at all -- which is how the interactive lab's "drop a session
          // anywhere to reload" went undriven through four ADRs (ADR-135). The
          // surface a reader drops onto is then the page itself.
          else if (this === window || this === document) {
            var mark = function () {
              if (document.body && !document.body.hasAttribute("data-h-drop"))
                document.body.setAttribute("data-h-drop", "1");
            };
            mark();
            if (document.readyState === "loading")
              document.addEventListener("DOMContentLoaded", mark);
          }
        }
      } catch (e) { }
      return AEL.call(this, type, fn, opt);
    };
  } catch (e) { }

  // A button whose whole job is to open the file chooser does nothing else, and
  // was being judged as an Add that added no row. Opening the chooser IS its
  // result, so record it as one.
  try {
    var IC = HTMLInputElement.prototype.click;
    HTMLInputElement.prototype.click = function () {
      try {
        if (this.type === "file") {
          window.__S.choosers++;
          window.__S.lastChooser = this.getAttribute("data-h") || this.id || "";
          return;                          /* the native dialog never opens */
        }
      } catch (e) { }
      return IC.apply(this, arguments);
    };
  } catch (e) { }

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
  // A COPY IS CAUGHT WHETHER THIS RAN BEFORE THE DOCUMENT OR AFTER IT (ADR-152).
  // As an init script this always ran before DOMContentLoaded, so waiting for
  // that event was free; evaluated into a page that has already loaded, the
  // event has been and gone and the hook was never installed at all -- and the
  // one action this whole file exists to serve, collect-output, came back
  // empty with nothing to say it had not been listening.
  var hook = function () {
    var oe = document.execCommand;
    document.execCommand = function (c) {
      if (c === "copy") { push("copy", "", String(window.getSelection())); return true; }
      return oe ? oe.apply(document, arguments) : false;
    };
  };
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", hook);
  else hook();
})();
}
"""

TAKE_OUT = "() => (window.__S ? window.__S.out.splice(0) : [])"


class PagePlugin(Plugin):
    """One page, one browser tab, behind the four operations."""

    ID = "csrbt-page"

    def __init__(self, page, name=None, kinds=None):
        # ADR-134: what this session has said the environment is. Kept here and
        # re-installed as an init script after every set, because a page that
        # reloads or opens another page starts with a fresh window -- and an
        # environment that survives one navigation and not the next would be
        # worse than none at all.
        self._env = {}
        self.page = page
        self.name = name
        self._catch()
        # ADR-100's kind list plus whatever the caller adds. It is a parameter
        # rather than an edit to harness.py so that widening what the swarm sees
        # does not silently restate the harness's own published ledger.
        self.kinds = kinds or H.KINDS
        self._desc = PluginDescriptor(
            self.ID, "CSRBT page",
            "One page of the CSRBT science kit, driven the way a user drives it: "
            "panes are opened before their controls are touched, and selectors "
            "are re-stamped on every observation because the widgets rebuild.",
            "1.0", [
                ActionSpec("open", "Load a page of the kit by file name.",
                           "NAVIGATE",
                           [ArgumentSpec("page", "string",
                                         "File name, e.g. collection-sheet.html. The example "
                                         "and the snapshot pool name the page this plugin is "
                                         "on, so a walk stays on its page; every kit page is "
                                         "listed in tools/routes.json.",
                                         required=True, pattern=r"^[a-z0-9][a-z0-9.\-]{0,60}\.html$",
                                         examples=[name or "collection-sheet.html"])]),
                ActionSpec("reload",
                           "Reload whatever page is loaded, discarding its state. "
                           "A client backtracking through a key needs this and "
                           "should not have to know the page's URL to get it.",
                           "NAVIGATE", []),
                ActionSpec("show-pane", "Open the pane with this id by pressing its tab.",
                           "NAVIGATE",
                           [ArgumentSpec("pane", "string",
                                         "Pane element id; the snapshot pool 'pane' lists this page's.",
                                         required=True, examples=["log", "data", "setup"])]),
                ActionSpec("set-text",
                           "Type a value into a text, number, date or textarea control.",
                           "DRAFT",
                           [ArgumentSpec("selector", "string", "A control address: the snapshot's index (text_in:3), the page's id (#cName) or its name (@working name)", required=True, pattern=ADDR_RE.pattern, examples=["dial_btn:2", "#cName", "@working name"]),
                            ArgumentSpec("value", "string", "Value to enter.",
                                         required=True,
                                         examples=["12", "3.5", "Quercus alba", "2026-06-01"])]),
                ActionSpec("type-text",
                           "Type a value into a text, number, date or textarea control "
                           "with real keystrokes, the way a person does. Differs from "
                           "set-text where a control can tell them apart: typing "
                           "letters into <input type=number> leaves the value empty "
                           "AND validity.badInput true, while assigning them leaves "
                           "badInput false, so a page that reports bad input has a "
                           "branch only this action can reach.",
                           "DRAFT",
                           [ArgumentSpec("selector", "string", "A control address: the snapshot's index (text_in:3), the page's id (#cName) or its name (@working name)", required=True, pattern=ADDR_RE.pattern, examples=["dial_btn:2", "#cName", "@working name"]),
                            ArgumentSpec("value", "string", "Value to type.",
                                         required=True,
                                         examples=["12", "one hundred", "2026-06-01"])]),
                ActionSpec("choose-option",
                           "Choose an option of a select box by value or visible label.",
                           "DRAFT",
                           [ArgumentSpec("selector", "string", "Selector of a select.", required=True, pattern=ADDR_RE.pattern, examples=["dial_btn:2", "#cName", "@working name"]),
                            ArgumentSpec("value", "string",
                                         "Option value or its visible text; the snapshot "
                                         "pool choose-option.value lists the page's; the "
                                         "set pool choose-option lists valid (selector, value) pairs.",
                                         required=True, examples=["1", "0"])]),
                ActionSpec("set-slider", "Move a slider to a value.", "MUTATE",
                           [ArgumentSpec("selector", "string", "Selector of a slider.", required=True, pattern=ADDR_RE.pattern, examples=["dial_btn:2", "#cName", "@working name"]),
                            ArgumentSpec("value", "number", "Value within min and max.",
                                         required=True, examples=[0, 1, 50])]),
                ActionSpec("press-step", "Press a stepper's up or down arrow.", "MUTATE",
                           [ArgumentSpec("selector", "string", "Selector of a stepper control.", required=True, pattern=ADDR_RE.pattern, examples=["dial_btn:2", "#cName", "@working name"]),
                            ArgumentSpec("direction", "string", "up or down",
                                         required=True, enum=["up", "down"])]),
                ActionSpec("activate",
                           "Press a control. Declared MUTATE and RAISED per call "
                           "(protocol 1.5): the target re-reads the control this "
                           "selector resolves to at the moment of the call, and "
                           "holds the call at DESTRUCTIVE when that control is "
                           "named for removing something -- Clear, Delete, Reset, "
                           "Undo, the row-removing mark -- or cannot be identified "
                           "at all. The snapshot's activate.destructive pool names "
                           "which selectors those are before you spend a call. "
                           "Until ADR-141 this was DESTRUCTIVE always, which meant "
                           "a supervised session could fill a page and press "
                           "nothing.",
                           "MUTATE",
                           [ArgumentSpec("selector", "string", "Control selector.", required=True, pattern=ADDR_RE.pattern, examples=["dial_btn:2", "#cName", "@working name"])],
                           may_rise=True),
                ActionSpec("pick",
                           "Choose a picker's option by the label a reader sees: type it "
                           "into the picker's filter and take the first match. Pool "
                           "pick.selector lists the pickers; a label nothing matches is "
                           "refused, not typed in blind.",
                           "DRAFT",
                           [ArgumentSpec("selector", "string", "Selector of a picker's search box.", required=True,
                                         pattern=ADDR_RE.pattern, examples=["pick_search:0", "@genEntry"]),
                            ArgumentSpec("value", "string", "The option's label, e.g. a genus.",
                                         required=True, examples=["Amanita", "Pinus contorta", "Quercus"])]),
                ActionSpec("read-report",
                           "The page's report as it stands: every labelled figure (a .l label "
                           "beside a .v value) flat, by the box it sits in and by the id it was "
                           "read from, every analysis "
                           "box's text (by the kit's id conventions: an*, *Out, *Box, *Stats, "
                           "*Note, *List, *Table, toast...), which boxes a reader can see, "
                           "every table's cells, the row count of every list, and the "
                           "headings in order. What an "
                           "operator checks a data-entry page's arithmetic against.",
                           "SENSITIVE_READ", []),
                # ---- the environment as an argument (ADR-134) ----
                #
                # A page that reads the clock or the dice answers differently
                # every run, so no expectation could hold it and no audit could
                # measure it: the ethogram's time budget, the ordination's
                # Date.now()-seeded starts, the greenhouse's demo log, and the
                # three Math.random buttons were driven by nobody. These say
                # what "now" and "chance" are for this run. NAVIGATE, not
                # MUTATE: they change the world the page is in, not the data
                # the page holds.
                ActionSpec("set-clock",
                           "Freeze the page's clock. Date.now() and new Date() answer this "
                           "instant until the run ends; every other Date form is untouched. "
                           "Omit `at` to hand the page back the real clock.",
                           "NAVIGATE",
                           [ArgumentSpec("at", "string",
                                         "An ISO 8601 instant, e.g. 2026-03-01T09:00:00Z. Omit to unfreeze.",
                                         pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$",
                                         examples=["2026-03-01T09:00:00Z", "2024-07-04T12:34:56Z"])]),
                ActionSpec("set-seed",
                           "Seed the page's Math.random with mulberry32, the generator the kit's "
                           "own pages use, so a run that draws chance draws the same chance twice. "
                           "Omit `seed` to hand the page back the real generator.",
                           "NAVIGATE",
                           [ArgumentSpec("seed", "integer",
                                         "A 32-bit seed. Omit to unseed.",
                                         minimum=0, maximum=4294967295, examples=[42, 1, 20260301])]),
                ActionSpec("set-dialog",
                           "Decide what a dialog gets answered with. A page that asks "
                           "\"really clear?\" is answered yes by default; this makes it "
                           "answerable no, so the path where a reader says no can be driven.",
                           "NAVIGATE",
                           [ArgumentSpec("confirm", "boolean", "The answer window.confirm() gets."),
                            ArgumentSpec("prompt", "string", "The text window.prompt() gets.",
                                         examples=["", "cancelled"])]),
                ActionSpec("read-dialogs",
                           "Every dialog the page raised since it loaded, in order, with its "
                           "text: what it asked before it cleared, and what it told you when "
                           "it refused.",
                           "SENSITIVE_READ", []),
                ActionSpec("read-control",
                           "Read one control including its entered value, group "
                           "state, stepper number, slider position and picker rows.",
                           "SENSITIVE_READ",
                           [ArgumentSpec("selector", "string", "Control selector.", required=True, pattern=ADDR_RE.pattern, examples=["dial_btn:2", "#cName", "@working name"])]),
                ActionSpec("set-checkbox", "Tick or clear a checkbox.", "DRAFT",
                           [ArgumentSpec("selector", "string", "Selector of a checkbox.", required=True, pattern=ADDR_RE.pattern, examples=["dial_btn:2", "#cName", "@working name"]),
                            ArgumentSpec("checked", "boolean", "Desired state.",
                                         required=True)]),
                ActionSpec("attach-file",
                           "Hand files to a file input, the way a chooser would. "
                           "The bytes come from the caller, so nothing on the "
                           "operator's disk is read and no OS dialog opens.",
                           "DRAFT",
                           [ArgumentSpec("selector", "string", "Selector of a file input.", required=True, pattern=ADDR_RE.pattern, examples=["dial_btn:2", "#cName", "@working name"]),
                            ArgumentSpec("files", "array",
                                         "Names of built-in fixture files: image, "
                                         "image2, png, pack, eco, csv, junk, video, "
                                         "session (the kit's own shipped experiment session).",
                                         required=True, items="string",
                                         enum=sorted(FIXTURES), examples=["image", "eco"])]),
                ActionSpec("drop-files",
                           "Drop files onto a drop zone, dispatching the same "
                           "dragenter, dragover and drop a hand would.",
                           "DRAFT",
                           [ArgumentSpec("selector", "string", "Selector of a drop zone.", required=True, pattern=ADDR_RE.pattern, examples=["dial_btn:2", "#cName", "@working name"]),
                            ArgumentSpec("files", "array", "Fixture file names.",
                                         required=True, items="string",
                                         enum=sorted(FIXTURES), examples=["image", "csv"])]),
                ActionSpec("read-page",
                           "The whole visible state at once: rendered text, how "
                           "many fields hold something, which elements are "
                           "selected, repeated-element counts, and the layout "
                           "invariants. SENSITIVE_READ because rendered text "
                           "contains what a user entered.",
                           "SENSITIVE_READ", []),
                ActionSpec("collect-output",
                           "Take the payloads the page has copied, downloaded or "
                           "printed since the last collection. These contain what "
                           "a user entered.",
                           "SENSITIVE_READ", []),
                ActionSpec("capture-screen",
                           "A PNG of the page as rendered, base64 encoded.",
                           "SENSITIVE_READ", []),
            ])

    def descriptor(self):
        return self._desc

    # -- observation --------------------------------------------------------
    def observe(self, sensitive=False):
        try:
            # ADR-189: settle once per document, then re-stamp: the widgets
            # rebuild, and a selector a client was just given must resolve to
            # the same control it named.
            self._ensure_settled()
            self.page.evaluate(H.DISCOVER, self.kinds)
            s = self.page.evaluate(CONTROLS, bool(sensitive))
        except Exception as e:
            return {"ready": False, "why": str(e)[:200]}
        s["ready"] = True
        s["page"] = self.name
        # ADR-134: the environment this run is happening in, on every snapshot.
        # A figure that came out of a seeded draw or a frozen clock is only
        # reproducible if the reader can see what the clock and the seed were,
        # and a snapshot that hides them makes every such figure unfalsifiable.
        try:
            s["environment"] = self.page.evaluate(
                "() => window.__D ? {clock: window.__D.epoch, seed: window.__D.seed, "
                "draws: window.__D.draws, confirm: window.__D.confirm, "
                "dialogs: window.__D.dialogs.length} : null")
        except Exception:
            s["environment"] = None
        s["sensitive"] = bool(sensitive)
        s["argumentPools"] = self._pools(s)
        if not sensitive:
            s["redacted"] = ("entered values omitted; use read-control with "
                             "SENSITIVE_READ enabled")
        return s

    def identity(self, snapshot=None):
        """ADR-191: a control is its ADDRESS, and order is not change.

        These pages rebuild their controls on nearly every act -- a chip row
        redrawn, a picker filtered, a row added -- so the positional selector
        of a control that did not change is different a call later, and a diff
        that compared the controls list position by position would report the
        whole page as having moved every time. Keyed by the ADR-188 address,
        which is what does not move, falling back to the selector for the few
        controls that have no name at all; the diff then says the two things
        that are true: which controls appeared, and which of the ones that
        stayed had a value, a visibility or a position change.

        The argument pools are NOT keyed, with one exception, and the reason
        is that every one of them is derived from `controls` -- so a keyed pool
        would say a second time, in selectors, what the controls list has
        already said in addresses, and a picker filtered from sixty-six to six
        would pay for that sentence twice. They are compared by length, and the
        stamp still covers their contents, so a pool that changed is never
        reported as unchanged. The exception is `activate.destructive`: it is
        short, and a button that removes work arriving in or leaving the set
        the door holds at DESTRUCTIVE is worth a line of its own.

        Nothing here is noise. A page has no self-moving number -- even
        `environment.draws` is a fact a reader wants (a seeded draw was spent),
        not a clock ticking underneath."""
        return {"keys": {"controls": ["address", "selector"],
                         "pickers": ["selector"],
                         "tabs": ["pane"],
                         "panes": "self",
                         "optionValues": "self",
                         "argumentPools/activate.destructive": "self"},
                "noise": []}

    def _pools(self, s):
        """ADR-117: what a client holding only the manifest and this snapshot
        can form a call from. Selectors are a fact of the moment (the widgets
        rebuild), so they are published per action -- "set-text.selector" is
        the text controls, "attach-file.selector" the file inputs -- plus the
        plain "selector" pool of everything commandable. Panes, kit pages and
        the page's own option values complete the set. Nothing here is a
        value a user typed."""
        # Commandable, and either visible now or inside a pane -- every action
        # opens a control's pane before acting (_reach), so a control behind a
        # tab is reachable; a control hidden any other way is not.
        live = [c for c in s.get("controls", [])
                if c.get("commandable") and (c.get("visible") or c.get("pane"))]
        pools = {"selector": [c["selector"] for c in live],
                 "pane": list(s.get("panes") or []),
                 "page": [self.name] if self.name else kit_pages(),
                 "choose-option.value": list(s.get("optionValues") or []),
                 # ADR-124: an argument SET pool, keyed by the action alone --
                 # whole (selector, value) pairs that are valid right now,
                 # because a value's validity depends on the select it goes to
                 # and no per-argument pool can say so.
                 "choose-option": [c for c in (s.get("optionChoices") or [])
                                   if any(l["selector"] == c["selector"] for l in live)],
                 # ADR-128: the same for pickers -- a label the page offers
                 # now, paired with the picker that offers it.
                 "pick": [c for c in (s.get("pickChoices") or [])
                          if any(l["selector"] == c["selector"] for l in live)]}
        for action, kinds in POOL_KINDS.items():
            pools[action + ".selector"] = [c["selector"] for c in live if c["kind"] in kinds]
        # ADR-141: and which of the activatable ones this door will hold at
        # DESTRUCTIVE. Published BESIDE the selectors rather than instead of
        # them: the client is told, before spending a call, which buttons are
        # the ones that remove work. A pool that merely omitted them would
        # leave a caller to discover the rung by being refused.
        # ADR-188: and the stable address of every one of them. A pool that
        # published only indexes is what taught four blind operators to
        # recompute offsets by hand; these do not move when the page rebuilds.
        # Keyed "address" rather than "<action>.selector" because it is not a
        # second pool to choose a call from -- it is the same controls, named.
        pools["address"] = [c["address"] for c in live if c.get("address")]
        pools["activate.destructive"] = [
            c["selector"] for c in live
            if c["kind"] in POOL_KINDS["activate"] and destroys(c.get("label"))]
        return pools

    # -- execution ----------------------------------------------------------
    def _catch(self):
        """Install the payload capture this plugin's collect-output reads.

        BOTH WAYS, AND NEITHER IS ENOUGH ALONE. As a context init script it
        survives `open` and `reload`, which is what a session that navigates
        needs; evaluated into the page that is already loaded, it covers the
        ordinary case of a plugin built around a page somebody has just opened,
        where an init script added now would not run until the next navigation.
        The script guards itself, so the two together install one copy.

        Never raises. A capture that could not be installed leaves
        collect-output answering exactly what it answered before this existed,
        and a plugin that refused to be constructed over it would be worse.
        """
        try:
            self.page.context.add_init_script(CATCH)
        except Exception:
            pass
        try:
            self.page.evaluate("() => { %s }" % CATCH)
        except Exception:
            pass

    def _reinstall(self):
        """Make this session's environment survive the next navigation.

        An init script runs before any page script, which is the only place a
        clock can be frozen for a page that reads it at load. Playwright's
        init scripts accumulate and cannot be removed, so each set adds one
        more -- they run in order and the last one wins, and a session sets
        these a handful of times at most.
        """
        try:
            ctx = self.page.context
        except Exception:
            return
        js = ["window.__D = window.__D || {};"]
        if "clock" in self._env:
            js.append("window.__D.epoch = %s;" % ("null" if self._env["clock"] is None else self._env["clock"]))
        if "seed" in self._env:
            if self._env["seed"] is None:
                js.append("window.__D.seed = null;")
            else:
                js.append("window.__D.seed = %d; window.__D.state = %d; window.__D.draws = 0;"
                          % (self._env["seed"], self._env["seed"]))
        if "confirm" in self._env:
            js.append("window.__D.confirm = %s;" % ("true" if self._env["confirm"] else "false"))
        if "prompt" in self._env:
            js.append("window.__D.prompt = %s;" % json.dumps(self._env["prompt"]))
        try:
            ctx.add_init_script("(function(){ %s })();" % " ".join(js))
        except Exception:
            pass

    def _settle(self):
        """ADR-189: stamp the page, and wait for the numbering to stop moving.

        The kit's pages build controls in script at load -- a region chip row,
        a key's options, a picker's list -- so a page that has just been
        navigated to has `data-h` on nothing until DISCOVER has run, and may
        still be growing when it has. Three of the four blind operators
        (ADR-187) opened with a `pick` or an `activate` and were told the page
        had no control of that kind AT ALL; one had the call escalated to
        DESTRUCTIVE for naming nothing. A leading `observe` fixed it, and
        needing one is the door asking the client to do its bookkeeping.

        ADR-188's version digest is exactly the signal to wait on: it moves
        when a control appears or an index shifts, so two consecutive readings
        that agree mean the page has stopped building. Bounded, because a page
        that rewrites controls on a timer would never settle, and a door that
        hangs is worse than one that acts a moment early."""
        v = last = None
        for _ in range(SETTLE_TRIES):
            try:
                self.page.evaluate(H.DISCOVER, self.kinds)
                v = self.page.evaluate(VERSION)
            except Exception:
                return None
            if v == last:
                break
            last = v
            self.page.wait_for_timeout(SETTLE_MS)
        try:
            self.page.evaluate("(v) => { window.__H_SETTLED = v || '1'; }", v)
        except Exception:
            pass
        return v

    def _ensure_settled(self):
        """Once per document. The marker lives on `window`, so a navigation or
        a reload takes it with the old document and the next call settles the
        new one -- no bookkeeping in the plugin about where the page has been."""
        try:
            if self.page.evaluate("() => window.__H_SETTLED || null"):
                return
        except Exception:
            return                                        # a page that cannot be asked cannot be settled
        self._settle()

    def _resolve(self, sel):
        """ADR-188: an address -> the selector of the moment, or a refusal.

        A PLAIN POSITIONAL SELECTOR IS PASSED THROUGH UNTOUCHED. It is what
        every client wrote before this slice and what the pools still publish
        first; `_reach` already answers one the page has moved past with the
        numbering it has now, and that answer is not improved by being given
        twice. Only the three forms this slice added are resolved here: a
        stamped positional, an id, and a name."""
        if not isinstance(sel, str):
            return sel
        if sel.startswith("#"):
            form, name, stamp = "#", sel[1:], None
        elif sel.startswith("@"):
            name = sel[1:]
            if name.startswith("control:"):        # the runner's own spelling, accepted verbatim
                name = name[len("control:"):]
            form, stamp = "@", None
        else:
            m = STAMP_RE.match(sel)
            if not m:
                return sel
            form, name, stamp = ":", m.group(1), m.group(2)
        try:
            r = self.page.evaluate(RESOLVE, [form, name, stamp])
        except Exception as e:
            raise Unavailable("page not readable: %s" % str(e)[:120])
        if r.get("ok"):
            return r["selector"]
        if r.get("why") == "stale":
            at = r.get("at") or None
            # ADR-189: its own code. This is not invalid_argument -- the
            # selector was well formed and true when the client read it -- and
            # not not_found -- the control is on the page; the caller's NAME
            # for it is what expired. "Read again" is a different instruction
            # from "you sent nonsense", and a client that cannot tell them
            # apart retries the wrong thing.
            raise Stale(
                "%s is stale: it names the numbering of snapshot %s and this page is at %s. %s "
                "Address a control by the page's own name instead -- every control in a snapshot "
                "carries one, and a name does not move when the page rebuilds."
                % (sel, stamp, r.get("now"),
                   ("%s is %r (%s) now." % (name, at.get("label") or "", at.get("address"))) if at
                   else "Nothing is at %s now." % name))
        if r.get("why") == "gone":
            raise NotFound("%s named the right numbering but there is no %s on the page now" % (sel, name))
        raise NotFound(
            "no control answers to %r on this page right now. An address is the page's own name for "
            "a control: an id (#cName), a label (@working name), a label under its host (@rCov/4, "
            "@iList/died#2), or a kind for a control the page never named (@kind=drop_zone). Every "
            "control in a snapshot publishes one, and they are pooled as \"address\"." % sel)

    def risk_for(self, action, args):
        """ADR-141: the risk of THIS activation, read off the live page.

        Only ever upward -- the gateway would ignore anything else -- and only
        for `activate`, the one action whose subject is not knowable from the
        action name. Three answers:

            the control is named for removing something   DESTRUCTIVE
            the selector resolves to nothing, or to a
              control with no name at all                 DESTRUCTIVE
            anything else                                 the declared floor

        The second is the one that matters most and it is the one that looks
        wrong at first glance: a selector that resolves to nothing cannot
        destroy anything, so why hold it at the top? Because these selectors
        are the MOMENT's. `action_btn:45` is the 46th activatable control on
        the page right now, and the blind trial watched a stale index of
        exactly that shape delete a tallied stem and answer `ok: true`. A call
        whose subject the caller and the page disagree about is the dangerous
        case, not the safe one."""
        if action != "activate":
            return None
        # ADR-189: SETTLE BEFORE THE RISK READ, not only before the act. The
        # gateway asks for the risk first, so a plugin that settled only in
        # `execute` would read the risk of an unbuilt page -- every name
        # answering to nothing, nothing raised -- and then settle and press
        # whatever the name turned out to mean. Settling here is what keeps
        # "@Clear trial" DESTRUCTIVE on the first call of a session.
        self._ensure_settled()
        sel = args.get("selector")
        try:
            # ADR-188: an ADDRESS is resolved before the read, or every stable
            # name would arrive here as "resolves to nothing" and be raised to
            # DESTRUCTIVE -- the door refusing the very thing it now accepts.
            # And an address that names nothing is NOT raised: the rule above
            # is about a POSITIONAL selector, which is the moment's and which
            # the trial watched delete a stem while answering ok. A name is not
            # the moment's, so a name that resolves to nothing is a typo, and
            # `execute` says so as a not-found.
            sel = self._resolve(sel)
        except HarnessError:
            return None
        try:
            info = self.page.evaluate(IDENTIFY, sel)
        except Exception as e:
            return ("DESTRUCTIVE",
                    "the page could not be asked what %r is (%s)" % (sel, str(e)[:80]))
        if not info or not info.get("found"):
            n, kind = (info or {}).get("ofKind", 0), (info or {}).get("kind", "?")
            return ("DESTRUCTIVE",
                    "%r names no control on this page right now (%s), and a call whose "
                    "subject cannot be named is treated as the worst it could be"
                    % (sel, ("the page has %d %s selector(s), numbered 0-%d"
                             % (n, kind, n - 1)) if n else
                       "this page has no %s control at all" % kind))
        where = " in #%s" % info["host"] if info.get("host") else ""
        why = destroys(info.get("label"), info.get("title"))
        if why:
            return ("DESTRUCTIVE", "%s is the control %r%s, and %s"
                    % (sel, (info.get("label") or "")[:40], where, why))
        if not (info.get("label") or info.get("id") or info.get("title")):
            return ("DESTRUCTIVE",
                    "%s%s carries no label, id or title, so what pressing it would do "
                    "cannot be read from the page" % (sel, where))
        return None

    def execute(self, action, args):
        # ADR-189: every action that is about the page as it stands waits for
        # the page to stand still first. `open` and `reload` are the two that
        # are about changing it, and they settle the document they arrive in.
        if action not in ("open", "reload"):
            self._ensure_settled()
        if action == "open":
            name = args["page"]
            if not re.match(r"^[a-z0-9][a-z0-9.\-]{0,60}\.html$", name):
                raise InvalidArgument("page must be a kit file name")
            self.page.goto(_kit.url(name), wait_until="domcontentloaded")
            self.page.wait_for_timeout(300)
            self.name = name
            v = self._settle()
            return True, "opened %s" % name, {"page": name, "version": v}

        if action == "reload":
            self.page.reload(wait_until="domcontentloaded")
            self.page.wait_for_timeout(250)
            v = self._settle()
            return True, "reloaded %s" % (self.name or ""), {"page": self.name, "version": v}

        if action == "show-pane":
            # Success is "this pane is now open", not "this pane is the first
            # open one". The first version asked the stricter question and a
            # page that opens a second pane without closing the first came back
            # as no-such-tab -- the contract refusing before the oracle could
            # report, which turned a finding into a failure.
            ok = self._open_pane(args["pane"])
            if not ok:
                raise NotFound("no tab opens pane %r" % args["pane"])
            return True, "opened pane %s" % args["pane"], {
                "pane": args["pane"], "open": self.page.evaluate(OPEN_PANES)}

        if action == "read-page":
            return True, "read the page", self.page.evaluate(PAGE_STATE)

        if action == "collect-output":
            out = self.page.evaluate(TAKE_OUT)
            return True, "%d payload(s)" % len(out), {"payloads": out}

        if action == "capture-screen":
            png = self.page.screenshot(full_page=False)
            if len(png) > 4 * 1024 * 1024:
                raise Failed("screenshot over 4 MiB")
            return True, "%d bytes" % len(png), {
                "mime": "image/png", "bytes": len(png),
                "data": base64.b64encode(png).decode("ascii")}

        if action == "read-report":
            try:
                r = self.page.evaluate(REPORT)
            except Exception as e:
                raise Unavailable("page not readable: %s" % str(e)[:120])
            return True, "%d figure(s), %d box(es), %d list(s), %d table(s), %d heading(s)" % (
                len(r["figures"]), len(r["boxes"]), len(r["rows"]), len(r["tables"]), len(r["headings"])), r

        sel = args.get("selector")
        if sel is not None:
            if not ADDR_RE.match(sel):
                raise InvalidArgument(
                    "selector must be a control address: kind:index as a snapshot publishes it "
                    "(dial_btn:2), that stamped with the snapshot's version (dial_btn:2@v1x7k), "
                    "the page's own id (#cName), or the page's own name for it (@working name, "
                    "@rCov/4, @iList/died#2, @kind=drop_zone)")
            # The caller's own spelling stays in the request the trace records;
            # everything downstream works on the selector it resolved to.
            args = dict(args)
            args["selector"] = sel = self._resolve(sel)

        if action == "set-clock":
            at = args.get("at")
            if at is None:
                self.page.evaluate("() => { window.__D.epoch = null; }")
                self._env["clock"] = None
                self._reinstall()
                return True, "the page has the real clock back", {"clock": None}
            import calendar, datetime
            try:
                d = datetime.datetime.strptime(at.replace("Z", "").split(".")[0], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                raise InvalidArgument("at must be an ISO 8601 instant like 2026-03-01T09:00:00Z")
            ms = calendar.timegm(d.timetuple()) * 1000
            self.page.evaluate("(ms) => { window.__D.epoch = ms; }", ms)
            self._env["clock"] = ms
            self._reinstall()
            # A page that reads the clock ONCE, at load -- the ethogram stamps its
            # date field that way -- has already read the real one by the time an
            # action can run. The freeze is in place for everything from here on
            # and for the whole of the next load, so the answer says so rather
            # than leaving a caller to find out from a wrong date.
            return True, "the clock is frozen at %s; reload for code that reads it at load" % at, \
                   {"clock": at, "epochMs": ms, "reloadForLoadTime": True}

        if action == "set-seed":
            seed = args.get("seed")
            if seed is None:
                self.page.evaluate("() => { window.__D.seed = null; }")
                self._env["seed"] = None
                self._reinstall()
                return True, "the page has the real generator back", {"seed": None}
            self.page.evaluate("(n) => { window.__D.seed = n; window.__D.state = n >>> 0; window.__D.draws = 0; }", int(seed))
            self._env["seed"] = int(seed)
            self._reinstall()
            return True, "Math.random is mulberry32 seeded %d; reload for code that draws at load" % int(seed), \
                   {"seed": int(seed), "reloadForLoadTime": True}

        if action == "set-dialog":
            if "confirm" not in args and "prompt" not in args:
                raise InvalidArgument("set-dialog needs confirm, prompt, or both")
            if "confirm" in args:
                self.page.evaluate("(v) => { window.__D.confirm = !!v; }", bool(args["confirm"]))
                self._env["confirm"] = bool(args["confirm"])
            if "prompt" in args:
                self.page.evaluate("(v) => { window.__D.prompt = String(v); }", args["prompt"])
                self._env["prompt"] = args["prompt"]
            self._reinstall()
            return True, "dialogs answered %s" % self._env, {"confirm": self._env.get("confirm"),
                                                            "prompt": self._env.get("prompt")}

        if action == "read-dialogs":
            d = self.page.evaluate("() => (window.__D && window.__D.dialogs) ? window.__D.dialogs.slice(0, 32) : []")
            return True, "%d dialog(s)" % len(d), {"dialogs": d, "count": len(d)}

        if action == "read-control":
            r = self.page.evaluate(READ_ONE, sel)
            if r is None:
                raise NotFound("no control %r on this page right now" % sel)
            if r.get("refused"):
                raise InvalidArgument("password controls are not readable")
            return True, "read %s" % sel, r

        self._reach(sel)
        if action == "set-checkbox":
            r = self.page.evaluate(SET_CHECK, [sel, bool(args["checked"])])
        elif action == "attach-file":
            files = [FIXTURES[n] for n in args["files"] if n in FIXTURES]
            if not files:
                raise InvalidArgument("no such fixture file: %s" % args["files"])
            el = self.page.query_selector('[data-h="%s"]' % sel)
            if el is None:
                raise NotFound("control %r is no longer on the page" % sel)
            kind = el.evaluate("e => (e.tagName === 'INPUT' && e.type === 'file') ? (e.multiple ? 'multi' : 'single') : 'no'")
            if kind == "no":
                raise InvalidArgument("%s is not a file input" % sel)
            if kind == "single" and len(files) > 1:
                raise InvalidArgument("%s takes one file; %d were given" % (sel, len(files)))
            el.set_input_files([{"name": f["name"], "mimeType": f["type"],
                                 "buffer": base64.b64decode(f["b64"])}
                                for f in files], timeout=H.ACT_TIMEOUT)
            r = {"ok": True, "attached": [f["name"] for f in files]}
        elif action == "drop-files":
            files = [FIXTURES[n] for n in args["files"] if n in FIXTURES]
            if not files:
                raise InvalidArgument("no such fixture file: %s" % args["files"])
            r = self.page.evaluate(DROP, [sel, files])
            r["attached"] = [f["name"] for f in files]
        elif action == "set-text":
            r = self.page.evaluate(ACT, [sel, "text", args["value"]])
        elif action == "type-text":
            # ASSIGNING A VALUE IS NOT TYPING (ADR-150). set-text writes through
            # the value setter, which is what a script does; a person presses
            # keys. For most controls the two are the same, and for
            # `<input type=number>` they are not: assigning "one hundred" leaves
            # `.value` as "" with `validity.badInput` FALSE, while typing it
            # leaves `.value` as "" with badInput TRUE. A page that tells the
            # two apart -- and the kit has two that do -- has a whole branch no
            # task in this kit could reach, because the harness had only the
            # first way.
            el = self.page.query_selector('[data-h="%s"]' % sel)
            if el is None:
                raise NotFound("control %r is no longer on the page" % sel)
            tag = el.evaluate("e => e.tagName")
            if tag not in ("INPUT", "TEXTAREA"):
                raise InvalidArgument("not a text control")
            # FOCUS, NOT CLICK. The first draft clicked the control to put the
            # caret in it, and the robot drives every tool at every control --
            # including ones a pane reveals but a layout still covers, where a
            # click waits thirty seconds for a hit test that never comes and
            # the walk records a FAILURE against the page. Typing needs the
            # focus, not the pointer; a control that cannot take focus is a
            # fact about the page (HIDDEN's family), reported as a refusal
            # rather than waited on.
            try:
                el.focus()
            except Exception:
                raise Conflict("control cannot take focus right now -- it is hidden, "
                               "covered or disabled, so there is nothing to type into")
            if not self.page.evaluate(
                    "(sel) => document.activeElement === "
                    "document.querySelector('[data-h=\"' + sel + '\"]')", sel):
                raise Conflict("control cannot take focus right now -- it is hidden, "
                               "covered or disabled, so there is nothing to type into")
            self.page.keyboard.press("Control+a")
            self.page.keyboard.press("Delete")
            if args["value"]:
                self.page.keyboard.type(args["value"], delay=1)
            r = self.page.evaluate(
                "(sel) => { const e = document.querySelector('[data-h=\"' + sel + '\"]');"
                "  e.dispatchEvent(new Event('input', {bubbles:true}));"
                "  e.dispatchEvent(new Event('change', {bubbles:true}));"
                "  return {ok: true, value: String(e.value),"
                "          badInput: !!(e.validity && e.validity.badInput)}; }", sel)
        elif action == "pick":
            r = self.page.evaluate(PICK, [sel, args["value"]])
            self.page.wait_for_timeout(120)
        elif action == "choose-option":
            r = self.page.evaluate(ACT, [sel, "option", args["value"]])
        elif action == "set-slider":
            r = self.page.evaluate(ACT, [sel, "range", args["value"]])
        elif action == "press-step":
            r = self.page.evaluate(ACT, [sel, "step", args["direction"]])
        elif action == "activate":
            r = self.page.evaluate(ACT, [sel, "click", None])
        else:
            raise NotFound("unknown action %r" % action)
        self.page.wait_for_timeout(15)
        if not r.get("ok"):
            if r.get("why") == "gone":
                raise NotFound("control %r is no longer on the page -- observe again"
                               % sel)
            raise InvalidArgument("%s: %s" % (sel, r.get("why")))
        return True, "%s %s" % (action, sel), r

    def _open_pane(self, pane):
        if pane in (self.page.evaluate(OPEN_PANES) or []):
            return True
        # A tab names its pane by data-pane (the kit's convention) or by
        # aria-controls (the experiment guide's); either opens it.
        tab = (self.page.query_selector('.tab[data-pane="%s"]' % pane) or
               self.page.query_selector('[aria-controls="%s"]' % pane))
        if tab is None:
            return False
        try:
            tab.click(timeout=H.ACT_TIMEOUT)
            self.page.wait_for_timeout(40)
        except Exception:
            return False
        return pane in (self.page.evaluate(OPEN_PANES) or [])

    def _reach(self, sel):
        """Open the control's own pane first, the way a finger reaches it."""
        try:
            pane = self.page.evaluate(
                "(s) => { const e = document.querySelector('[data-h=\"' + s + '\"]');"
                " return e ? ((e.closest('.pane') || {}).id || null) : false; }", sel)
        except Exception as e:
            raise Unavailable("page not readable: %s" % str(e)[:120])
        if pane is False:
            # ADR-141: how many selectors of that kind exist NOW. "no control
            # action_btn:45 on this page right now" reads as a typo; a caller
            # holding an index from a snapshot the page has since rebuilt needs
            # to hear that the numbering moved, not that it misspelled something.
            kind = str(sel).split(":")[0]
            try:
                n = self.page.evaluate(
                    "(k) => document.querySelectorAll('[data-h^=\"' + k + ':\"]').length", kind)
            except Exception:
                n = None
            raise NotFound("no control %r on this page right now%s -- these selectors are "
                           "the moment's, not the page's: observe again and re-read the pool"
                           % (sel, "" if n is None else
                              (" (there are %d %s selector(s), numbered 0-%d)" % (n, kind, n - 1)
                               if n else " (this page has no %s control at all)" % kind)))
        if pane:
            self._open_pane(pane)
