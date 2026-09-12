# -*- coding: utf-8 -*-
"""Mutation testing for the page plugin's reader, picker and naming (ADR-128).

verify_report.py says read-report finds every figure, pick takes the right
option and refuses a guess, and the snapshot names every control. Same rule
as every suite: break tools/harness_plugin_page.py on purpose and require
the suite to notice. Each mutant is one browser session on a fixture page,
a few seconds.

    python3 tools/mutate_report.py           # run every mutant
    python3 tools/mutate_report.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")

MUTANTS = [
    ("figures are only .tile again",
     '  document.querySelectorAll(".v").forEach(v => {\n    const t = v.parentElement;',
     '  document.querySelectorAll(".tile .v").forEach(v => {\n    const t = v.parentElement;',
     "the .l/.v pair is the convention"),
    ("a second label overwrites the first in the flat map",
     '    while (k in figures) { k = key + " #" + (n++); }',
     '    ',
     "first label wins"),
    ("figures are not kept by their box",
     '    if (box) { const b = by[box] = by[box] || {}; let bk = key, m = 2;',
     '    if (false) { const b = by[box] = by[box] || {}; let bk = key, m = 2;',
     "by the box"),
    ("the same label twice in a box keeps one",
     '               while (bk in b) { bk = key + " #" + (m++); }        // "doubling time" twice in one box',
     '               ',
     "twice in one box"),
    ("a <small> unit is glued to the value",
     '    vc.querySelectorAll("small").forEach(x => x.insertAdjacentText("beforebegin", " "));',
     '    ',
     "spaced off"),
    ("boxes are the old five prefixes only",
     '  const BOX = /^(an|out|rep|res|sum)[A-Za-z0-9-]*$|(box|out|stats?|plan|matrix|verdict|tiles|warn|coh|tell|note|advice|refuse|table|chart|typical|list|results|grid|export|lint|cmd|meas|help|card|legend|msg|check|read|desc|left|res|board)$|^(coherence|report|results|outputs|toast|journal|tree)$|^station-[a-z]+$/i;',
     '  const BOX = /^(an|out|rep|res|sum)[A-Za-z]*$/;',
     "kit's naming"),
    # ADR-171: the regex line above is the anchor of the mutant above it, and
    # ADR-140 found that anchor stale after ADR-135 widened the regex. Widened
    # again here (*Board), the anchor is widened with it, and a mutant of its own
    # holds the new name.
    ("a *Board is not a box",
     '|desc|left|res|board)$|',
     '|desc|left|res)$|',
     "a *Board is a box"),
    # ADR-180: the survey's event tree -- generated IDs, names, dates, a copy
    # and a remove button per row -- was a figure with buttons in it, which
    # the readable audit skipped whole. Named as a box by its whole id.
    ("the survey's event tree is not a box",
     '|^(coherence|report|results|outputs|toast|journal|tree)$|',
     '|^(coherence|report|results|outputs|toast|journal)$|',
     "the event tree is a box"),
    ("a figure does not say where it was read from",
     '    if (src) sources[k] = src;',
     '    ',
     "names the element it was read from"),
    ("a figure's source is its box, never the element itself",
     '    const src = v.id || t.id || box;',
     '    const src = box;',
     "names the element it was read from"),
    ("a figure's source skips the pair's own id",
     '    const src = v.id || t.id || box;',
     '    const src = v.id || box;',
     "the id of the pair it sits in"),
    ("every identified element is a box",
     '    if (!BOX.test(e.id)) return;\n    if (Object.keys(boxes).length >= 64) return;',
     '    if (Object.keys(boxes).length >= 64) return;',
     "nothing outside the conventions"),
    ("a box behind a closed tab is dropped again",
     '    boxes[e.id] = norm(e.textContent).slice(0, 4000);\n    lines[e.id] = leafLines(e);\n    if (vis(e)) shown.push(e.id);',
     '    if (!vis(e)) return;\n    boxes[e.id] = norm(e.textContent).slice(0, 4000);\n    lines[e.id] = leafLines(e);\n    shown.push(e.id);',
     "behind a closed tab is read"),
    ("every box is reported shown",
     '    if (vis(e)) shown.push(e.id);',
     '    shown.push(e.id);',
     "which boxes a reader could see"),
    ("tables are not read",
     '  document.querySelectorAll("table").forEach((t, i) => {\n    if (Object.keys(tables).length >= 16) return;',
     '  document.querySelectorAll("table").forEach((t, i) => {\n    if (true) return;',
     "every table's cells"),
    ("lists are not counted",
     '    rows[id] = (rows[id] || 0) + 1;',
     '    rows[id] = 1;',
     "every .row2 list is counted"),
    ("pick takes the first option whatever the value",
     '  const hit = exact || (opts.length === 1 ? opts[0] : null);',
     '  const hit = opts[0];',
     "refused as ambiguous"),
    ("pick never takes the sole option the filter left",
     '  const hit = exact || (opts.length === 1 ? opts[0] : null);',
     '  const hit = exact || null;',
     "narrows to one option"),
    ("pick matches the sub-line as the label",
     '  const nameOf = o => { const c = o.cloneNode(true); c.querySelectorAll("small").forEach(x => x.remove());',
     '  const nameOf = o => { const c = o.cloneNode(true);',
     "exact label wins"),
    ("a prefix is not a match",
     '             || opts.find(o => nameOf(o).startsWith(want));',
     '             ;',
     "a prefix, case-insensitively"),
    ("no match and ambiguous are the same refusal",
     '  if (!hit) return { ok: false, why: opts.length ? "ambiguous: " + opts.length + " options match " + JSON.stringify(String(value))',
     '  if (!hit) return { ok: false, why: opts.length ? "no option matches " + JSON.stringify(String(value))',
     "naming the count"),
    ("a picker's options are not published as a pool",
     '      if (label && picks.length < POOL_CAP) picks.push({ selector: s.getAttribute("data-h"), value: label });',
     '      ',
     "argument-set pool for pick"),
    ("the pool carries the sub-line in the label",
     '      const c = o.cloneNode(true); c.querySelectorAll("small").forEach(x => x.remove());\n      const label',
     '      const c = o.cloneNode(true);\n      const label',
     "sub-lines stripped"),
    ("a bare .k label is not a figure",
     '              [...t.children].find(c => c.classList.contains("k") && !c.querySelector(".v"));',
     '              null;',
     "bare .k beside the .v"),
    ("the headings are not read",
     '  const headings = [...document.querySelectorAll("h1, h2, h3")].slice(0, 80)',
     '  const headings = [].slice(0, 80)',
     "headings, in order"),
    # Anchored with their neighbours since ADR-141: read-control and the risk
    # classifier now report id and host too, so the bare line appears three
    # times and a one-line anchor would silently never apply.
    # ADR-188 moved the naming into _rows(), which the snapshot, the resolver
    # and the risk read all share; these two anchor there now, so a mutation
    # still reaches exactly one place and reaches every reader of it.
    ("a control carries no id",
     '    kind: (e.getAttribute("data-h") || "").split(":")[0],\n    id: e.id || null,',
     '    kind: (e.getAttribute("data-h") || "").split(":")[0],\n    id: null,',
     "keeps its id"),
    ("a control's host is its pane, not its nearest identified ancestor",
     '    host: (e.parentElement && e.parentElement.closest("[id]") || {}).id || null,\n    label: _label(e) }));',
     '    host: (e.closest(".pane") || {}).id || null,\n    label: _label(e) }));',
     "mount host"),
    # ADR-141: these two used to anchor inside the snapshot's own copy of the
    # label expression. There is one copy now (LABEL_FN), read by the snapshot,
    # by read-control and by the risk classifier -- so one mutation is put to
    # all three, which is the point of having one copy.
    ("a dial option is labelled by its whole text",
     '               c.querySelectorAll("small, kbd, [data-x], .x").forEach(x => x.remove());',
     '               c.querySelectorAll("[data-x], .x").forEach(x => x.remove());',
     "labelled by its <span>"),
    ("a behaviour key is labelled by its whole text",
     '  const _label = (e) => (e.getAttribute("aria-label") || (e.querySelector(".nm") || {}).textContent ||',
     '  const _label = (e) => (e.getAttribute("aria-label") ||',
     "labelled by its .nm child"),
    # ---- the environment as an argument (ADR-134) ----
    ("the clock is never frozen",
     '            self.page.evaluate("(ms) => { window.__D.epoch = ms; }", ms)',
     '            self.page.evaluate("(ms) => { window.__D.epoch = ms; }", 0) if False else None',
     "answer the frozen instant"),
    ("freezing the clock replaces every Date, not just \"now\"",
     '    if (arguments.length === 0 && window.__D.epoch !== null) return new RealDate(window.__D.epoch);',
     '    if (window.__D.epoch !== null) return new RealDate(window.__D.epoch);',
     "every OTHER Date form is untouched"),
    ("the shim changes behaviour before anyone asks",
     '  Math.random = function () {\n    if (window.__D.seed === null) return realRandom();',
     '  Math.random = function () {\n    if (false) return realRandom();',
     "REAL dice"),
    ("the seeded generator is not mulberry32",
     '    t = Math.imul(t ^ (t >>> 15), t | 1);',
     '    t = Math.imul(t ^ (t >>> 13), t | 1);',
     "IS mulberry32"),
    ("the draws are not counted",
     '    window.__D.draws++;',
     '    ',
     "counts the draws"),
    ("a dialog is always answered yes",
     '  window.confirm = say("confirm", function () { return !!window.__D.confirm; });',
     '  window.confirm = say("confirm", function () { return true; });',
     "answered by policy"),
    ("dialogs are counted but not recorded",
     '        window.__D.dialogs.push({ kind: kind, text: String(text == null ? "" : text).slice(0, 300) });',
     '        window.__D.dialogs.push({ kind: kind, text: "" });',
     "recorded by kind and text"),
    ("the environment does not survive a reload",
     '            ctx.add_init_script("(function(){ %s })();" % " ".join(js))',
     '            pass',
     "survives a reload"),
    ("the snapshot hides the environment",
     '            s["environment"] = self.page.evaluate(',
     '            s["environment"] = None if True else self.page.evaluate(',
     "environment is empty"),
    ("a clock that is not an instant is accepted",
     '            except ValueError:\n                raise InvalidArgument("at must be an ISO 8601 instant like 2026-03-01T09:00:00Z")',
     '            except ValueError:\n                d = datetime.datetime(1970, 1, 1)',
     "was accepted"),
    ("set-dialog with nothing to set is accepted",
     '                raise InvalidArgument("set-dialog needs confirm, prompt, or both")',
     '                pass',
     "was accepted"),
]


MUTANTS += [
    # ---- ADR-140: the charts ----
    ('charts are not read at all',
     '    if (Object.keys(charts).length >= 16 || !vis(sv)) return;',
     '    if (true) return;',
     'a visible <svg> is a chart'),
    ('a chart that is not shown is read anyway',
     '    if (Object.keys(charts).length >= 16 || !vis(sv)) return;',
     '    if (Object.keys(charts).length >= 16) return;',
     'one that is not shown is not read'),
    ('marks are counted as one kind',
     '    ["circle", "rect", "path", "line", "polyline", "polygon", "ellipse"].forEach(tag => {',
     '    ["circle"].forEach(tag => {',
     'every mark is counted by what it is'),
    ("a series' length is the number of marks, not its points",
     '      const pts = (e.getAttribute("points") || "").trim().split(/\\s+/).filter(Boolean).length;',
     '      const pts = 1;',
     'the longest drawn series'),
    ("a path's points are not counted, only a polyline's",
     '    [...sv.querySelectorAll("path")].slice(0, 40).forEach(e => {\n      const pts = ((e.getAttribute("d") || "").match(/[MLHVCSQTAmlhvcsqta]/g) || []).length;',
     '    [].forEach(e => {\n      const pts = ((e.getAttribute("d") || "").match(/[MLHVCSQTAmlhvcsqta]/g) || []).length;',
     'the path here, the polyline'),
    ('aligned text is not put in order',
     '      return best ? best.slice().sort((a, b) => a[along] - b[along]).map(t => t.t) : [];',
     '      return best ? best.map(t => t.t) : [];',
     'the leftmost column top to bottom'),
    ('the row taken is the first found, not the lowest',
     '    const aligned = {row: pick(rowsAt, "x", (a, b) => a > b),   // the lowest row of labels\n                     col: pick(colsAt, "y", (a, b) => a < b)};  // the leftmost column',
     '    const aligned = {row: pick(rowsAt, "x", (a, b) => false),\n                     col: pick(colsAt, "y", (a, b) => false)};',
     'the LOWEST row of text that lines up is the one taken'),
    ('a text is paired with any mark, however far',
     '      let near = null, d2 = 900;                       // within 30 units, squared',
     '      let near = null, d2 = 1e9;',
     'a text beside a mark names it'),
    ("a mark's centre is not recorded unless a text named it",
     '                   at: centres.slice(0, 40), spans: spans};',
     '                   at: [], spans: spans};',
     'every mark centre is there whether or not anything labelled it'),
    ('text positions are dropped',
     '      {t: norm(t.textContent).slice(0, 60), x: num(t.getAttribute("x")), y: num(t.getAttribute("y"))}));',
     '      {t: norm(t.textContent).slice(0, 60), x: null, y: null}));',
     'each text carries the position the page gave it'),
    ('a rect is placed by its corner, not its middle',
     '      if (x !== null && y !== null) centres.push([r2(x + (w || 0) / 2), r2(y + (h || 0) / 2)]);',
     '      if (x !== null && y !== null) centres.push([r2(x), r2(y)]);',
     'a rect by its middle'),
    ('the space the chart was drawn in is not reported',
     '    charts[key] = {viewBox: vb, texts: texts, n: texts.length, marks: marks,',
     '    charts[key] = {viewBox: "", texts: texts, n: texts.length, marks: marks,',
     'the space it was drawn in'),
]


MUTANTS += [
    # ---- ADR-182: a path is placed by its box ----
    ("a path's box is not read",
     '      if (x0 !== null) spans.push([r2(x0), r2(y0), r2(x1), r2(y1)]);',
     '      if (false) spans.push([r2(x0), r2(y0), r2(x1), r2(y1)]);',
     "each path's box"),
    ('a relative command is read as absolute',
     '        const up = cmd.toUpperCase(), rel = cmd !== up, n = NEED[up];',
     '        const up = cmd.toUpperCase(), rel = false, n = NEED[up];',
     'drawn with relative commands is placed where it ends up'),
    ('H is not followed, so a bar has no width and a step line no run',
     '        if (up === "H") { cx = (rel ? cx : 0) + a[0]; }',
     '        if (up === "H") { }',
     "each path's box"),
    ("a path's points are M and L only, so a step line is one point",
     '      const pts = ((e.getAttribute("d") || "").match(/[MLHVCSQTAmlhvcsqta]/g) || []).length;',
     '      const pts = ((e.getAttribute("d") || "").match(/[ML]/g) || []).length;',
     'every command that ends somewhere is a point'),
    ('an unplaced mark is placed at nothing',
     '      if (x !== null && y !== null) centres.push([x, y]);      // an unplaced mark is nowhere',
     '      centres.push([x, y]);',
     'an unplaced mark'),
    ("a rect's centre is not rounded",
     '      if (x !== null && y !== null) centres.push([r2(x + (w || 0) / 2), r2(y + (h || 0) / 2)]);',
     '      if (x !== null && y !== null) centres.push([x + (w || 0) / 2, y + (h || 0) / 2]);',
     'centre is rounded'),
]

MUTANTS += [
    # ---- ADR-141: read-control names what it read ----
    ("read-control answers about a selector and nothing else, the way it did "
     "until ADR-141",
     '              id: e.id || null, label: _label(e),',
     '              id: null, label: null,',
     "the page's own names for the control"),
    ("read-control computes the label its own way",
     '              id: e.id || null, label: _label(e),\n              host: (e.parentElement',
     '              id: e.id || null, label: (e.textContent || "").trim().slice(0, 60),\n              host: (e.parentElement',
     "the SAME label the snapshot published"),
    ("a stale selector is refused without saying the numbering moved",
     """            try:
                n = self.page.evaluate(
                    "(k) => document.querySelectorAll('[data-h^=\\"' + k + ':\\"]').length", kind)
            except Exception:
                n = None""",
     """            n = None""",
     "refused by COUNT"),
]


MUTANTS += [
    # ---- ADR-150: typing is not assigning ----
    ("type-text clicks the control instead of focusing it",
     '            try:\n                el.focus()',
     '            try:\n                el.click()',
     "refused at once rather than waited on"),
    ("type-text assigns the value instead of pressing keys",
     '            self.page.keyboard.type(args["value"], delay=1)',
     '            el.evaluate("(e, v) => { e.value = v; }", args["value"])',
     "badInput TRUE"),
    ("a control that cannot take focus is waited on rather than refused",
     '                raise Conflict("control cannot take focus right now -- it is hidden, "\n                               "covered or disabled, so there is nothing to type into")\n            if not self.page.evaluate(',
     '                pass\n            if False and not self.page.evaluate(',
     "was accepted"),
    ("typing does not clear what was there first",
     '            self.page.keyboard.press("Control+a")\n            self.page.keyboard.press("Delete")',
     '            pass',
     "typing an empty value CLEARS"),
    ("type-text accepts a control that is not a text control",
     '            if tag not in ("INPUT", "TEXTAREA"):\n                raise InvalidArgument("not a text control")',
     '            if False:\n                raise InvalidArgument("not a text control")',
     "type-text into a button was accepted"),
    # ---- ADR-145: a picker with nothing showing is still a picker ----
    ("a picker that currently shows no option is not a picker",
     '  const pick = s.closest(".fek-pick");',
     '  const pick = null;',
     "NEXT pick still works"),
    ("anything with a search box is a picker, whatever it is inside",
     '  if (!root || (!pick && !root.querySelector(":scope > .opt, :scope > .opts > .opt")))\n    return { ok: false, why: "not a picker" };',
     '  if (false)\n    return { ok: false, why: "not a picker" };',
     "a pick on a plain text input was accepted"),
    # ---- what leaves the page, for a caller who is not the robot (ADR-152) ----
    ("the capture is only an init script, so a page already open never gets it",
     '            self.page.evaluate("() => { %s }" % CATCH)',
     '            pass',
     "INTO THE PAGE THAT IS ALREADY OPEN"),
    ("the capture is only evaluated, so a reload loses it",
     '            self.page.context.add_init_script(CATCH)',
     '            pass',
     "on the page after a reload"),
    ("the plugin does not install the capture at all",
     '        self._catch()',
     '        pass',
     "INTO THE PAGE THAT IS ALREADY OPEN"),
    ("the capture installs again over itself, doubling every count",
     'if (!window.__S) {',
     'if (true) {',
     "does not install the capture twice"),
    ("the copy hook waits for a DOMContentLoaded that has already been and gone",
     '  if (document.readyState === "loading")\n    document.addEventListener("DOMContentLoaded", hook);\n  else hook();',
     '  document.addEventListener("DOMContentLoaded", hook);',
     "read by collect-output for a caller that is not the robot"),
    ("collect-output reads the payloads and leaves them there",
     'TAKE_OUT = "() => (window.__S ? window.__S.out.splice(0) : [])"',
     'TAKE_OUT = "() => (window.__S ? window.__S.out.slice(0) : [])"',
     "does not report them twice"),
    ("a download leaves no payload, so a page whose product is a file says nothing",
     '      push("download", this.getAttribute("download"), t);\n      return;',
     '      return;',
     "a Blob download is captured with its filename"),
]

MUTANTS += [
    # ---- ADR-188: addresses --------------------------------------------------
    ("a published address is not checked against the resolver that has to accept it",
     '      const got = c.charAt(0) === "#" ? _byId(c.slice(1), idx) : _named(c.slice(1), idx);\n      if (got === r) return c;',
     '      return c;',
     "resolves back to itself"),
    ("the address falls back to nothing when no name fits",
     '    return r.selector + "@" + ver;',
     '    return "";',
     "publishes its INDEX, stamped"),
    ("a name is looked up by label before id",
     '      hits = idx.id.get(name) || idx.label.get(name) || idx.host.get(name) || null;',
     '      hits = idx.label.get(name) || idx.id.get(name) || idx.host.get(name) || null;',
     "another's label is the ID's"),
    ("a trailing #n is part of the name",
     '    const m = /^(.*)#(\\d+)$/.exec(name);\n    if (m) { name = m[1]; nth = parseInt(m[2], 10); }',
     '    const m = null;\n    if (m) { name = m[1]; nth = parseInt(m[2], 10); }',
     "exactly as the runner's find_control"),
    ("a scoped name splits on the LAST slash",
     '        const i = name.indexOf("/");\n        hits = idx.hl.get(name.slice(0, i)',
     '        const i = name.lastIndexOf("/");\n        hits = idx.hl.get(name.slice(0, i)',
     "exactly as the runner's find_control"),
    ("the version ignores the ids and watches only the count",
     '    const s = rows.map(r => r.selector + "|" + (r.id || "")).join(",");',
     '    const s = String(rows.length);',
     "the version IS that digest"),
    ("a stamp from another snapshot is resolved anyway",
     '    if (stamp !== now) {',
     '    if (false) {',
     "refused as stale"),
    ("the stale refusal does not say what is at that index now",
     '               at: at ? { label: at.label, address: _address(at, idx, now) } : null };',
     '               at: null };',
     "told what is at that index now"),
    ("# is a synonym for @",
     '  const hit = form === "#" ? _byId(name, idx) : _named(name, idx);',
     '  const hit = _named(name, idx);',
     "not synonyms"),
    ("an address is resolved for the act but not for the risk read",
     '            sel = self._resolve(sel)\n        except HarnessError:\n            return None',
     '            sel = sel\n        except HarnessError:\n            return None',
     "through its address exactly as"),
    ("a name that names nothing is held at DESTRUCTIVE like a stale index",
     '        except HarnessError:\n            return None\n        try:\n            info = self.page.evaluate(IDENTIFY, sel)',
     '        except HarnessError:\n            return ("DESTRUCTIVE", "unresolvable")\n        try:\n            info = self.page.evaluate(IDENTIFY, sel)',
     "is refused as not-found and is not raised"),
    ("the pools publish the selectors and not the addresses",
     '        pools["address"] = [c["address"] for c in live if c.get("address")]',
     '        pools["address"] = []',
     "an address for every control"),
    ("the manifest still advertises the old index-only pattern",
     'ADDR_RE = re.compile(r"^(?:[a-z_]+:\\d+(?:@v[0-9a-z]{1,10})?"',
     'ADDR_RE = re.compile(r"^(?:[a-z_]+:\\d+()?"',
     "takes every address form"),
    ("the runner's own spelling is taken as a label",
     '            if name.startswith("control:"):        # the runner\'s own spelling, accepted verbatim\n                name = name[len("control:"):]',
     '            if False:\n                name = name[len("control:"):]',
     "the runner's own spelling"),
]

MUTANTS += [
    # ---- ADR-189: settling -----------------------------------------------
    ("the risk read trusts the page as it finds it",
     '        self._ensure_settled()\n        sel = args.get("selector")',
     '        sel = args.get("selector")',
     "still reads as DESTRUCTIVE"),
    ("an act does not settle the page it is about to touch",
     '        if action not in ("open", "reload"):\n            self._ensure_settled()',
     '        if False:\n            self._ensure_settled()',
     "an act can be the first thing"),
    ("the door settles once per SESSION",
     '            if self.page.evaluate("() => window.__H_SETTLED || null"):\n                return',
     '            if getattr(self, "_ever", False):\n                return\n            self._ever = True',
     "settles the page it lands on"),
    ("the settle takes the first reading it gets",
     '            if v == last:\n                break\n            last = v',
     '            if True:\n                break\n            last = v',
     "adds AFTER it finishes loading"),
    ("a reload answers without the version it settled at",
     '            v = self._settle()\n            return True, "reloaded %s" % (self.name or ""), {"page": self.name, "version": v}',
     '            self._settle()\n            return True, "reloaded %s" % (self.name or ""), {"page": self.name}',
     "answers with its version"),
    ("the marker is not the version, so nothing ties the two together",
     "window.__H_SETTLED = v || '1'; }",
     "window.__H_SETTLED = 'x'; }",
     "marks the document with the version it settled at"),
]

MUTANTS += [
    # ---- ADR-190: the manual ---------------------------------------------
    ("a picker publishes a sample of its options again",
     "    const all = [...root.querySelectorAll(\".opt\")];\n    const take = all.slice(0, PICK_CAP);",
     "    const all = [...root.querySelectorAll(\".opt\")];\n    const take = all.slice(0, 6);",
     "every option it offers, not six of them"),
    ("the snapshot does not say how many there were",
     '    lists.push({ selector: s.getAttribute("data-h"), kind: "pick",\n                 host: (s.parentElement && s.parentElement.closest("[id]") || {}).id || null,\n                 shown: take.length, of: all.length });',
     '    lists.push({ selector: s.getAttribute("data-h"), kind: "pick",\n                 host: (s.parentElement && s.parentElement.closest("[id]") || {}).id || null,\n                 shown: take.length, of: take.length });',
     "SAYS how many there were"),
    ("read-control answers about a selector and nothing else again",
     '              address: (() => { const rows = _rows(), idx = _index(rows);',
     '              address: (() => { if (true) return null; const rows = _rows(), idx = _index(rows);',
     "the same address the snapshot publishes"),
    ("a box is published whole and not split",
     "    lines[e.id] = leafLines(e);",
     "    lines[e.id] = [];",
     "split into more"),
    ("the split takes every block, nested ones included",
     '    const blocks = [...e.querySelectorAll(BLOCK)].filter(b => !b.querySelector(BLOCK));',
     '    const blocks = [...e.querySelectorAll(BLOCK)];',
     "no box's lines say more than the box does"),
    ("a line cut at the cap keeps the space the cut landed on",
     '    return out.slice(0, 40).map(t => t.slice(0, 300).replace(/\\s+$/, ""));',
     '    return out.slice(0, 40).map(t => t.slice(0, 300));',
     "nothing invented and nothing"),
    ("the page's prose about itself is not handed over",
     '  const rules = [...document.querySelectorAll("p.hint, p.fine, .hint, .fine")]',
     '  const rules = [...document.querySelectorAll("p.no-such-class-at-all")]',
     "own prose about itself is handed over"),
    ("a piece of prose that contains another is handed over twice",
     '    .filter(e => !e.querySelector(".hint, .fine"))\n    .slice(0, 40)',
     '    .slice(0, 40)',
     "handed over once, as the innermost piece"),
    ("the prose is handed over without the thing it sits in",
     '    .map(e => ({ t: norm(e.textContent).slice(0, 400),\n                 host: (e.parentElement && e.parentElement.closest("[id]") || {}).id || null }))',
     '    .map(e => ({ t: norm(e.textContent).slice(0, 400), host: null }))',
     "with the identified thing it sits in"),
]

MUTANTS += [
    # ---- ADR-191: the session ---------------------------------------------
    ("a control is its index again, so a rebuild reads as a replacement",
     '        return {"keys": {"controls": ["address", "selector"],',
     '        return {"keys": {"controls": ["selector"],',
     "reported as that one field moving"),
    ("a tab is keyed by what it says rather than by what it opens",
     '                         "tabs": ["pane"],',
     '                         "tabs": ["label"],',
     "BOTH tabs"),
    ("the numbering's own version is called noise",
     '                         "argumentPools/activate.destructive": "self"},\n                "noise": []}',
     '                         "argumentPools/activate.destructive": "self"},\n                "noise": ["version"]}',
     "the numbering moved, and the diff says so"),
    ("what is in a field is published whatever rung the session holds",
     '      value: (!sens || !(!e.disabled && !e.readOnly && e.type !== "password")) ? undefined',
     '      value: (false || !(!e.disabled && !e.readOnly && e.type !== "password")) ? undefined',
     "a session WITHOUT that rung gets none of them"),
    ("a control nobody may command hands over its contents too",
     '      value: (!sens || !(!e.disabled && !e.readOnly && e.type !== "password")) ? undefined',
     '      value: (!sens || false) ? undefined',
     "may not command hands over nothing"),
    ("the snapshot's value is a reading of its own rather than the field's",
     '             : String(e.value).slice(0, 200),',
     '             : String(e.value).toLowerCase().slice(0, 200),',
     "the same value read-control answers with"),
]

KNOWN_EQUIVALENT = []


FILES = {"audit": None}


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutreport_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        # the subject is the page plugin AND the determinism shim it drives
        # (tools/harness.py): one catalogue, two files, and the runner finds
        # whichever one carries the anchor rather than making the catalogue
        # say it twice.
        path = None
        for cand in ("harness_plugin_page.py", "harness.py"):
            p2 = os.path.join(dst, cand)
            if io.open(p2, encoding="utf-8").read().count(find) == 1:
                path = p2
                break
        if path is None:
            n = sum(io.open(os.path.join(dst, c), encoding="utf-8").read().count(find)
                    for c in ("harness_plugin_page.py", "harness.py"))
            return ("BAD MUTANT", "anchor matched %d times across the subject -- the mutation never applied" % n)
        src = io.open(path, encoding="utf-8").read()
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        suite = os.path.join(dst, "verify", "verify_report.py")
        env = dict(os.environ, CSRBT_DOCS_DIR=os.path.join(ROOT, "docs"))
        p = subprocess.run([sys.executable, suite], capture_output=True, text=True, timeout=600, env=env)
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        if "NOT VERIFIED" in out:
            return ("BAD MUTANT", "the suite could not run under mutation")
        if not fails and p.returncode != 0:
            return ("BAD MUTANT", "the suite crashed rather than failed: %s"
                    % (out.strip().split("\n")[-1][:70] if out.strip() else "no output"))
        if not fails:
            return ("SURVIVED", "no check failed -- this clause is asserted by nobody")
        hit = any(expect in f for f in fails)
        return ("killed" if hit else "killed by the wrong check",
                "%d failure(s); first: %s" % (len(fails), fails[0][6:80]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


MUTANTS += [
    # ---- ADR-195: the report's own stamp, and its `since` ------------------
    ("a report goes out without a stamp, so there is nothing to ask with",
     '        served["stamp"] = st',
     '        pass',
     "a report carries a stamp beside everything"),
    ("`since` is ignored, so every read is the whole report again",
     '        if not since:',
     '        if True:',
     "does NOT send the report"),
    ("a report whose stamp did not move is sent anyway, as an empty diff",
     '        if st == since:\n            return True, "nothing in the report has changed", {',
     '        if False:\n            return True, "nothing in the report has changed", {',
     "does NOT send the report"),
    ("the baseline is the FIRST report served rather than the last",
     '        prev, self._last_report = self._last_report, (st, r)',
     '        prev = self._last_report\n        if prev is None:\n            self._last_report = (st, r)',
     "the read just before is current"),
    ("a stamp this session never issued is diffed against whatever is nearest",
     '        if prev is None or prev[0] != since:',
     '        if prev is None:',
     "gets the WHOLE report and the reason"),
    ("the report's lists are keyed by a name, so a page's own ids miss",
     '                                "lines/*": "self", "rules": ["t"]},',
     '                                "lines": "self", "rules": ["t"]},',
     "is NAMED rather than counted"),
    ("a table's rows are keyed, so row three is taken for row three",
     '                                "lines/*": "self", "rules": ["t"]},',
     '                                "lines/*": "self", "tables/*": "self", "rules": ["t"]},',
     "a table's rows are NOT keyed"),
    ("the report gets a digest of its own instead of the contract's stamp",
     '        st = stamp_of(r, self.REPORT_IDENTITY)',
     '        st = "s" + __import__("hashlib").sha256(\n            repr(sorted(r.items())).encode("utf-8")).hexdigest()[:12]',
     "uses the contract's OWN stamp and diff"),
]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    if a.list:
        for n, _, _, e in MUTANTS:
            print("  %-60s must be killed by  %s" % (n, e))
        return 0
    print("mutation testing the page reader against verify_report -- %d mutant(s), %d known equivalent\n"
          % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-60s %s" % (verdict, name, detail[:60]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        if verdict == "SURVIVED":
            survived += 1
        elif verdict != "killed":
            bad += 1
    import mutant_ledger
    mutant_ledger.record("mutate_report", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
