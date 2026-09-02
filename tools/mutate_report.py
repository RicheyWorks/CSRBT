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
     '  const BOX = /^(an|out|rep|res|sum)[A-Za-z0-9-]*$|(box|out|stats?|plan|matrix|verdict|tiles|warn|coh|tell|note|advice|refuse|table|chart|typical|list|results|grid|export|lint|cmd|meas|help|card|legend)$|^(coherence|report|results|outputs|toast|journal)$/i;',
     '  const BOX = /^(an|out|rep|res|sum)[A-Za-z]*$/;',
     "kit's naming"),
    ("every identified element is a box",
     '    if (!BOX.test(e.id)) return;\n    if (Object.keys(boxes).length >= 64) return;',
     '    if (Object.keys(boxes).length >= 64) return;',
     "nothing outside the conventions"),
    ("a box behind a closed tab is dropped again",
     '    boxes[e.id] = norm(e.textContent).slice(0, 1500);\n    if (vis(e)) shown.push(e.id);',
     '    if (!vis(e)) return;\n    boxes[e.id] = norm(e.textContent).slice(0, 1500);\n    shown.push(e.id);',
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
    ("a control carries no id",
     '      id: e.id || null,',
     '      id: null,',
     "keeps its id"),
    ("a control's host is its pane, not its nearest identified ancestor",
     '      host: (e.parentElement && e.parentElement.closest("[id]") || {}).id || null,',
     '      host: (e.closest(".pane") || {}).id || null,',
     "mount host"),
    ("a dial option is labelled by its whole text",
     '              (() => { const c = e.cloneNode(true); c.querySelectorAll("small, kbd").forEach(x => x.remove());',
     '              (() => { const c = e.cloneNode(true);',
     "labelled by its <span>"),
    ("a behaviour key is labelled by its whole text",
     '      label: (e.getAttribute("aria-label") || (e.querySelector(".nm") || {}).textContent ||',
     '      label: (e.getAttribute("aria-label") ||',
     "labelled by its .nm child"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutreport_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        path = os.path.join(dst, "harness_plugin_page.py")
        src = io.open(path, encoding="utf-8").read()
        if src.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times -- the mutation never applied" % src.count(find))
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
