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
     '  const BOX = /^(an|out|rep|res|sum)[A-Za-z0-9-]*$|(box|out|stats?|plan|matrix|verdict|tiles|warn|coh|tell|note|advice|refuse|table|chart|typical|list|results|grid|export|lint|cmd|meas|help|card|legend|msg|check|read|desc|left|res)$|^(coherence|report|results|outputs|toast|journal)$|^station-[a-z]+$/i;',
     '  const BOX = /^(an|out|rep|res|sum)[A-Za-z]*$/;',
     "kit's naming"),
    ("every identified element is a box",
     '    if (!BOX.test(e.id)) return;\n    if (Object.keys(boxes).length >= 64) return;',
     '    if (Object.keys(boxes).length >= 64) return;',
     "nothing outside the conventions"),
    ("a box behind a closed tab is dropped again",
     '    boxes[e.id] = norm(e.textContent).slice(0, 4000);\n    if (vis(e)) shown.push(e.id);',
     '    if (!vis(e)) return;\n    boxes[e.id] = norm(e.textContent).slice(0, 4000);\n    shown.push(e.id);',
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
     '      if (label && picks.length < 200) picks.push({ selector: s.getAttribute("data-h"), value: label });',
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
    ("a control carries no id",
     '      // "@control:cName" and is readable; the selector is the moment\'s.\n      id: e.id || null,',
     '      // "@control:cName" and is readable; the selector is the moment\'s.\n      id: null,',
     "keeps its id"),
    ("a control's host is its pane, not its nearest identified ancestor",
     '      id: e.id || null,\n      host: (e.parentElement && e.parentElement.closest("[id]") || {}).id || null,',
     '      id: e.id || null,\n      host: (e.closest(".pane") || {}).id || null,',
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
     '    [...sv.querySelectorAll("path")].slice(0, 40).forEach(e => {\n      const pts = ((e.getAttribute("d") || "").match(/[ML]/g) || []).length;',
     '    [].forEach(e => {\n      const pts = ((e.getAttribute("d") || "").match(/[ML]/g) || []).length;',
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
     '                   at: centres.slice(0, 40)};',
     '                   at: []};',
     'every mark centre is there whether or not anything labelled it'),
    ('text positions are dropped',
     '      {t: norm(t.textContent).slice(0, 60), x: num(t.getAttribute("x")), y: num(t.getAttribute("y"))}));',
     '      {t: norm(t.textContent).slice(0, 60), x: null, y: null}));',
     'each text carries the position the page gave it'),
    ('a rect is placed by its corner, not its middle',
     '      if (x !== null && y !== null) centres.push([x + (w || 0) / 2, y + (h || 0) / 2]);',
     '      if (x !== null && y !== null) centres.push([x, y]);',
     'a rect by its middle'),
    ('the space the chart was drawn in is not reported',
     '    charts[key] = {viewBox: vb, texts: texts, n: texts.length, marks: marks,',
     '    charts[key] = {viewBox: "", texts: texts, n: texts.length, marks: marks,',
     'the space it was drawn in'),
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
    # ---- ADR-145: a picker with nothing showing is still a picker ----
    ("a picker that currently shows no option is not a picker",
     '  const pick = s.closest(".fek-pick");',
     '  const pick = null;',
     "NEXT pick still works"),
    ("anything with a search box is a picker, whatever it is inside",
     '  if (!root || (!pick && !root.querySelector(":scope > .opt, :scope > .opts > .opt")))\n    return { ok: false, why: "not a picker" };',
     '  if (false)\n    return { ok: false, why: "not a picker" };',
     "a pick on a plain text input was accepted"),
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
