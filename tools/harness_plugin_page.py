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
import base64, io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "verify"))
import _kit
import harness as H
from harness_contract import (ActionSpec, ArgumentSpec, Plugin, PluginDescriptor,
                              Failed, InvalidArgument, NotFound, Unavailable)

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

SEL_RE = re.compile(r"^[a-z_]+:\d+$")

# Read where a user reads: one round trip, typed, and never a field's contents.
CONTROLS = r"""
() => {
  const out = [];
  document.querySelectorAll("[data-h]").forEach(e => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    out.push({
      selector: e.getAttribute("data-h"),
      kind: (e.getAttribute("data-h") || "").split(":")[0],
      label: (e.getAttribute("aria-label") || e.textContent || e.placeholder ||
              e.getAttribute("title") || "").replace(/\s+/g, " ").trim().slice(0, 60),
      pane: (e.closest(".pane") || {}).id || null,
      target: e.getAttribute("data-pane") || null,
      type: (e.getAttribute("type") || e.tagName).toLowerCase(),
      visible: r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none",
      enabled: !e.disabled && !e.readOnly,
      selected: e.classList.contains("on"),
      commandable: !e.disabled && !e.readOnly && e.type !== "password",
    });
  });
  return { route: (document.querySelector(".pane.on") || {}).id || null,
           title: document.title,
           panes: [...document.querySelectorAll(".pane")].map(p => p.id),
           tabs: [...document.querySelectorAll(".tab[data-pane]")].map(
                   t => ({ pane: t.getAttribute("data-pane"),
                           label: (t.textContent || "").trim().slice(0, 40),
                           open: t.classList.contains("on") })),
           controls: out };
}
"""

# SENSITIVE_READ. Bounded on every axis: one control, capped text, capped option
# lists, and a truncated flag rather than a silent clip.
READ_ONE = r"""
(sel) => {
  const e = document.querySelector('[data-h="' + sel + '"]');
  if (!e) return null;
  if (e.type === "password") return { refused: "password" };
  const cap = (s, n) => { s = String(s == null ? "" : s);
    return { text: s.slice(0, n), truncated: s.length > n }; };
  const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
  const o = { selector: sel, kind: sel.split(":")[0], tag: e.tagName.toLowerCase(),
              type: (e.getAttribute("type") || "").toLowerCase(),
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

ACT = r"""
([sel, kind, value]) => {
  const e = document.querySelector('[data-h="' + sel + '"]');
  if (!e) return { ok: false, why: "gone" };
  if (kind === "text") {
    const proto = e.tagName === "TEXTAREA" ? HTMLTextAreaElement : HTMLInputElement;
    const set = Object.getOwnPropertyDescriptor(proto.prototype, "value").set;
    set.call(e, String(value));
    e.dispatchEvent(new Event("input", { bubbles: true }));
    e.dispatchEvent(new Event("change", { bubbles: true }));
    return { ok: true, value: String(e.value) };
  }
  if (kind === "range") {
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
  if (e.checked !== want) e.click();
  return { ok: true, checked: !!e.checked };
}
"""

OPEN_PANES = "() => [...document.querySelectorAll('.pane.on')].map(p => p.id)"

TAKE_OUT = "() => (window.__S ? window.__S.out.splice(0) : [])"


class PagePlugin(Plugin):
    """One page, one browser tab, behind the four operations."""

    ID = "csrbt-page"

    def __init__(self, page, name=None, kinds=None):
        self.page = page
        self.name = name
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
                                         "File name, e.g. collection-sheet.html",
                                         required=True)]),
                ActionSpec("reload",
                           "Reload whatever page is loaded, discarding its state. "
                           "A client backtracking through a key needs this and "
                           "should not have to know the page's URL to get it.",
                           "NAVIGATE", []),
                ActionSpec("show-pane", "Open the pane with this id by pressing its tab.",
                           "NAVIGATE",
                           [ArgumentSpec("pane", "string", "Pane element id.",
                                         required=True)]),
                ActionSpec("set-text",
                           "Type a value into a text, number, date or textarea control.",
                           "DRAFT",
                           [ArgumentSpec("selector", "string",
                                         "Control selector from a snapshot, e.g. text_in:3",
                                         required=True),
                            ArgumentSpec("value", "string", "Value to enter.",
                                         required=True)]),
                ActionSpec("choose-option",
                           "Choose an option of a select box by value or visible label.",
                           "DRAFT",
                           [ArgumentSpec("selector", "string", "Selector of a select.",
                                         required=True),
                            ArgumentSpec("value", "string",
                                         "Option value or its visible text.",
                                         required=True)]),
                ActionSpec("set-slider", "Move a slider to a value.", "MUTATE",
                           [ArgumentSpec("selector", "string", "Selector of a slider.",
                                         required=True),
                            ArgumentSpec("value", "number", "Value within min and max.",
                                         required=True)]),
                ActionSpec("press-step", "Press a stepper's up or down arrow.", "MUTATE",
                           [ArgumentSpec("selector", "string",
                                         "Selector of a stepper control.", required=True),
                            ArgumentSpec("direction", "string", "up or down",
                                         required=True, enum=["up", "down"])]),
                ActionSpec("activate",
                           "Activate a control generically. Classified DESTRUCTIVE "
                           "because a selector on these pages may resolve to Add "
                           "row, to Clear trial, or to an export, and deciding "
                           "which from its label is a guess.",
                           "DESTRUCTIVE",
                           [ArgumentSpec("selector", "string", "Control selector.",
                                         required=True)]),
                ActionSpec("read-control",
                           "Read one control including its entered value, group "
                           "state, stepper number, slider position and picker rows.",
                           "SENSITIVE_READ",
                           [ArgumentSpec("selector", "string", "Control selector.",
                                         required=True)]),
                ActionSpec("set-checkbox", "Tick or clear a checkbox.", "DRAFT",
                           [ArgumentSpec("selector", "string", "Selector of a checkbox.",
                                         required=True),
                            ArgumentSpec("checked", "boolean", "Desired state.",
                                         required=True)]),
                ActionSpec("attach-file",
                           "Hand files to a file input, the way a chooser would. "
                           "The bytes come from the caller, so nothing on the "
                           "operator's disk is read and no OS dialog opens.",
                           "DRAFT",
                           [ArgumentSpec("selector", "string",
                                         "Selector of a file input.", required=True),
                            ArgumentSpec("files", "array",
                                         "Names of built-in fixture files: image, "
                                         "image2, pack, eco, csv, junk, video.",
                                         required=True, items="string")]),
                ActionSpec("drop-files",
                           "Drop files onto a drop zone, dispatching the same "
                           "dragenter, dragover and drop a hand would.",
                           "DRAFT",
                           [ArgumentSpec("selector", "string",
                                         "Selector of a drop zone.", required=True),
                            ArgumentSpec("files", "array", "Fixture file names.",
                                         required=True, items="string")]),
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
            # Re-stamp first: the widgets rebuild, and a selector a client was
            # just given must resolve to the same control it named.
            self.page.evaluate(H.DISCOVER, self.kinds)
            s = self.page.evaluate(CONTROLS)
        except Exception as e:
            return {"ready": False, "why": str(e)[:200]}
        s["ready"] = True
        s["page"] = self.name
        s["sensitive"] = bool(sensitive)
        if not sensitive:
            s["redacted"] = ("entered values omitted; use read-control with "
                             "SENSITIVE_READ enabled")
        return s

    # -- execution ----------------------------------------------------------
    def execute(self, action, args):
        if action == "open":
            name = args["page"]
            if not re.match(r"^[a-z0-9][a-z0-9.\-]{0,60}\.html$", name):
                raise InvalidArgument("page must be a kit file name")
            self.page.goto(_kit.url(name), wait_until="domcontentloaded")
            self.page.wait_for_timeout(300)
            self.name = name
            return True, "opened %s" % name, {"page": name}

        if action == "reload":
            self.page.reload(wait_until="domcontentloaded")
            self.page.wait_for_timeout(250)
            return True, "reloaded %s" % (self.name or ""), {"page": self.name}

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

        sel = args.get("selector")
        if sel is not None and not SEL_RE.match(sel):
            raise InvalidArgument("selector must be kind:index as published by a "
                                  "snapshot, e.g. dial_btn:2")

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
        tab = self.page.query_selector('.tab[data-pane="%s"]' % pane)
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
            raise NotFound("no control %r on this page right now" % sel)
        if pane:
            self._open_pane(pane)
