# -*- coding: utf-8 -*-
"""The Harness Board: every ledger, rendered, never typed (ADR-127).

WHY

The harness keeps seven ledgers -- the suites' counts, the walks, every
page, the tasks, the traces, the mutant runners, the engines' own suites --
and the only place they were read together was an ADR's closing paragraph,
typed by hand on the day and stale the next. The Atlas taught the rule
(ADR-120): a published page carries no number a tool did not write, and a
check fails when the page and the ledgers disagree.

WHAT

    python3 tools/harness_board.py            # render tools/harness_board.html
    python3 tools/harness_board.py --check    # exit 1 if the file is not what the ledgers say

The page is rendered whole from the ledgers: nothing in it is edited by
hand. It is published as an artifact; verify_board holds the file to the
ledgers and the ledgers to each other. Prose that explains a section is the
one hand-written part and lives in this file, beside the numbers it frames.
"""
import html, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(HERE, "harness_board.html")


def _load(name, default):
    p = os.path.join(HERE, name)
    if not os.path.isfile(p):
        return default
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except ValueError:
        return default


def ledgers():
    return {
        "counts": _load(os.path.join("verify", "counts.json"), {"suites": {}}),
        "walk": _load("walk_ledger.json", {"targets": {}}),
        "tasks": _load("task_ledger.json", {"tasks": {}}),
        "mutants": _load("mutant_ledger.json", {"runners": {}}),
        "ecosystem": _load("ecosystem_ledger.json", {"engines": {}}),
        "routes": _load("routes.json", {"routes": []}),
    }


HARNESS_SUITES = [
    ("verify_contract", "the gateway contract: policy, replay, arguments, redaction"),
    ("verify_organism", "the organism through the gateway: one oracle per engine"),
    ("verify_lab", "the science engine: the shipped protocol reproduced"),
    ("verify_mcp", "the second transport decides nothing"),
    ("verify_walk", "the robot, every target, both transports, every page"),
    ("verify_tasks", "goals with graded expectations; traces held to them; the science tasks"),
    ("verify_report", "the page reader: every figure, the right option, every control named"),
    ("verify_audit_states", "the audits, everywhere: every state of every page measured, the unreached counted"),
    ("verify_ecosystem", "the engines' own suites, ratcheted; the Atlas"),
    ("verify_engine_sessions", "shipped sessions bound to the engine"),
    ("verify_harness", "the swarm's driver over the kit's pages"),
    ("verify_harness_matrix", "the swarm's verdicts mean something"),
]

RUNNERS = [
    ("mutate_organism", "the organism plugin and console"),
    ("mutate_lab", "the lab plugin and console"),
    ("mutate_mcp", "the MCP transport"),
    ("mutate_walk", "the robot"),
    ("mutate_tasks", "the task runner and grader"),
    ("mutate_report", "the page reader, picker and naming"),
    ("mutate_audit_states", "the audits' state walker and accounting"),
    ("mutate_harness", "the swarm's driver"),
]


def esc(x):
    return html.escape(str(x))


def when(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "—"


def pill(text, kind):
    return '<span class="pill %s">%s</span>' % (kind, esc(text))


def summary(L):
    c = L["counts"]["suites"]
    n = sum(v.get("n", 0) for v in c.values())
    of = sum(v.get("of", 0) for v in c.values())
    holes = sum(v.get("unverified", 0) for v in c.values())
    green = sum(1 for v in c.values() if v.get("green"))
    W = L["walk"]["targets"]
    targets = [k for k in W if not k.startswith("csrbt-page/")]
    pages = [k for k in W if k.startswith("csrbt-page/")]
    bad_walks = [k for k, e in W.items() if e.get("identity") != "holds" or e.get("undriven") or e.get("unschemable")
                 or e.get("invariants_broken") or (e.get("totals") or {}).get("failed")]
    T = L["tasks"]["tasks"]
    runs = {k: e for k, e in T.items() if not k.endswith("@trace")}
    traces = {k: e for k, e in T.items() if k.endswith("@trace")}
    M = L["mutants"]["runners"]
    E = L["ecosystem"]["engines"]
    return {
        "checks": n, "of": of, "holes": holes, "suites": len(c), "green": green,
        "targets": len(targets), "pages": len(pages), "bad_walks": bad_walks,
        "commands": sum(e.get("commands", 0) for e in W.values()),
        "tasks": len(runs), "tasks_held": sum(1 for e in runs.values() if e.get("held")),
        "traces": len(traces), "traces_held": sum(1 for e in traces.values() if e.get("held")),
        "confirmed": sum(e.get("confirmed", 0) for e in T.values()),
        "mutants": sum(e.get("mutants", 0) for e in M.values()),
        "killed": sum(e.get("killed", 0) for e in M.values()),
        "survived": sum(e.get("survived", 0) for e in M.values()),
        "inconclusive": sum(e.get("inconclusive", 0) for e in M.values()),
        "equivalent": sum(e.get("equivalent", 0) for e in M.values()),
        "engine_tests": sum(e.get("tests", 0) for e in E.values()),
        "engine_failures": sum(e.get("failures", 0) + e.get("errors", 0) for e in E.values()),
        "engines": len(E),
        "newest": max([v.get("at", 0) for v in c.values()] + [e.get("at", 0) for e in W.values()] +
                      [e.get("at", 0) for e in T.values()] + [e.get("at", 0) for e in M.values()] +
                      [e.get("at", 0) for e in E.values()] + [0]),
    }


def render(L):
    S = summary(L)
    c = L["counts"]["suites"]
    W = L["walk"]["targets"]
    T = L["tasks"]["tasks"]
    M = L["mutants"]["runners"]
    E = L["ecosystem"]["engines"]
    all_green = (S["of"] == S["checks"] and not S["bad_walks"] and S["tasks_held"] == S["tasks"] and
                 S["traces_held"] == S["traces"] and S["survived"] == 0 and S["inconclusive"] == 0 and
                 S["engine_failures"] == 0)

    o = []
    o.append('<title>Harness Board</title>')
    o.append('<link rel="preconnect" href="https://fonts.googleapis.com">')
    o.append('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,800&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">')
    o.append(STYLE)
    o.append('<div class="wrap">')
    o.append('<header class="hero"><div class="eyebrow">CSRBT · the automation harness · every ledger, rendered</div>'
             '<h1>Harness Board</h1>'
             '<p class="lede">What the harness can currently vouch for, read from its own ledgers and never typed: '
             'the suites, the robot\'s walks of every target and every page, the tasks and the traces graded against them, '
             'the mutant runners, and the fourteen engines\' own suites. A number here that disagrees with a ledger '
             'fails <span class="mono">verify_board</span>.</p>'
             '<div class="verdict %s">%s</div></header>'
             % ("good" if all_green else "bad",
                "Everything the harness knows how to check is green." if all_green else
                "Something is not green — read down."))

    # summary strip
    o.append('<section><div class="stats">')
    tiles = [
        ("%d / %d" % (S["checks"], S["of"]), "suite checks passing", "%d suites, %d green%s; the audits are run_all's" % (
            S["suites"], S["green"], (", %d NOT VERIFIED" % S["holes"]) if S["holes"] else ", no holes")),
        ("%d" % S["commands"], "commands walked", "%d targets × 2 transports, %d pages" % (S["targets"] // 2, S["pages"])),
        ("%d / %d" % (S["tasks_held"], S["tasks"]), "tasks held", "%d / %d traces held, %d expectations confirmed"
         % (S["traces_held"], S["traces"], S["confirmed"])),
        ("%d / %d" % (S["killed"], S["mutants"]), "mutants killed", "%d survived, %d inconclusive, %d recorded equivalent"
         % (S["survived"], S["inconclusive"], S["equivalent"])),
        ("%d" % S["engine_tests"], "engine tests", "%d suites, %d failures" % (S["engines"], S["engine_failures"])),
    ]
    for big, what, note in tiles:
        o.append('<div class="stat"><div class="big">%s</div><div class="what">%s</div><p>%s</p></div>'
                 % (esc(big), esc(what), esc(note)))
    o.append('</div></section>')

    # suites
    o.append('<section><div class="sec-head"><h2>The harness suites</h2><span class="count">%d of the kit\'s %d suites'
             '</span></div><div class="tablewrap"><table><thead><tr><th>suite</th><th>what it holds</th>'
             '<th>checks</th><th>holes</th><th>scored</th></tr></thead><tbody>' % (len(HARNESS_SUITES), len(c)))
    for name, what in HARNESS_SUITES:
        e = c.get(name)
        if not e:
            o.append('<tr><td class="mono">%s</td><td class="role">%s</td><td colspan="3">%s</td></tr>'
                     % (esc(name), esc(what), pill("no reading", "na")))
            continue
        kind = "good" if e.get("green") and e.get("n") == e.get("of") else "bad"
        o.append('<tr><td class="mono">%s</td><td class="role">%s</td><td class="num">%s</td><td class="num">%s</td>'
                 '<td class="num dim">%s</td></tr>'
                 % (esc(name), esc(what), pill("%d / %d" % (e.get("n", 0), e.get("of", 0)), kind),
                    esc(e.get("unverified", 0) or "—"), esc(when(e.get("at")))))
    o.append('</tbody></table></div><p class="note">The other %d suites are the kit\'s pages\' own; <span class="mono">'
             'run_all</span> scores them all and writes <span class="mono">counts.json</span>.</p></section>'
             % (len(c) - len(HARNESS_SUITES)))

    # walks
    o.append('<section><div class="sec-head"><h2>The robot\'s walks</h2><span class="count">from the manifest alone · '
             'commands == driven + refused + declined + chaos + failed</span></div><div class="tablewrap"><table><thead>'
             '<tr><th>target</th><th>transport</th><th>tools</th><th>driven</th><th>refused</th><th>declined</th>'
             '<th>chaos</th><th>failed</th><th>unreachable</th><th>broken</th><th>snapshot ms</th><th>verdict</th></tr>'
             '</thead><tbody>')
    for k in sorted(k for k in W if not k.startswith("csrbt-page/")):
        e = W[k]
        t = e.get("totals") or {}
        bad = k in S["bad_walks"]
        pr = ((e.get("price") or {}).get("snapshotMs") or {})
        o.append('<tr><td class="mono">%s</td><td class="mono">%s</td><td class="num">%d</td><td class="num">%d</td>'
                 '<td class="num">%d</td><td class="num">%d</td><td class="num">%d</td><td class="num">%d</td>'
                 '<td class="num">%d</td><td class="num">%d</td><td class="num">%s</td><td>%s</td></tr>'
                 % (esc(k.split("@")[0]), esc(e.get("transport", "stdio")), e.get("tools", 0), t.get("driven", 0),
                    t.get("refused", 0), t.get("declined", 0), t.get("chaos", 0), t.get("failed", 0),
                    len(e.get("unreachable") or []), len(e.get("invariants_broken") or []),
                    esc(pr.get("median", "—")), pill("holds" if not bad else "BAD", "good" if not bad else "bad")))
    o.append('</tbody></table></div></section>')

    # pages
    pages = sorted(k for k in W if k.startswith("csrbt-page/"))
    o.append('<section><div class="sec-head"><h2>Every page</h2><span class="count">%d routed pages · %d walked</span>'
             '</div><div class="pages">' % (len({r["page"] for r in L["routes"]["routes"]}), len(pages)))
    for k in pages:
        e = W[k]
        t = e.get("totals") or {}
        bad = k in S["bad_walks"]
        o.append('<div class="page %s"><span class="pname">%s</span><span class="pnum">%d driven · %d refused · %d unreachable'
                 '</span></div>' % ("bad" if bad else "", esc(k[len("csrbt-page/"):]), t.get("driven", 0),
                                    t.get("refused", 0), len(e.get("unreachable") or [])))
    o.append('</div><p class="note">Unreachable is a fact about the page — a guide offers few controls, a bench nearly '
             'all fifteen — and never a hole. A red page failed the walk\'s bar.</p></section>')

    # tasks and traces
    o.append('<section><div class="sec-head"><h2>Tasks and traces</h2><span class="count">goals with graded expectations'
             '</span></div><div class="tablewrap"><table><thead><tr><th>task</th><th>target</th><th>run</th>'
             '<th>confirmed</th><th>trace</th><th>calls for steps</th></tr></thead><tbody>')
    for k in sorted(k for k in T if not k.endswith("@trace")):
        e = T[k]
        tr = T.get(k + "@trace")
        o.append('<tr><td class="mono">%s</td><td class="mono">%s</td><td>%s</td><td class="num">%d</td><td>%s</td>'
                 '<td class="num">%s</td></tr>'
                 % (esc(k), esc(e.get("target")), pill("%s%s" % (e.get("verdict"), " · must FAIL" if e.get("must") == "FAIL" else ""),
                                                        "good" if e.get("held") else "bad"), e.get("confirmed", 0),
                    pill("%s" % tr.get("verdict"), "good" if tr.get("held") else "bad") if tr else pill("no trace", "na"),
                    esc("%d for %d" % (tr.get("calls", 0), tr.get("required", 0))) if tr else "—"))
    o.append('</tbody></table></div><p class="note">A run follows the task\'s steps through the gateway. A trace is what '
             'an operator given only the goal did through the MCP door, held to the same expectations; its economy is '
             'calls made for required steps.</p></section>')

    # mutants
    o.append('<section><div class="sec-head"><h2>The mutant runners</h2><span class="count">each instrument, broken on '
             'purpose</span></div><div class="tablewrap"><table><thead><tr><th>runner</th><th>breaks</th><th>mutants</th>'
             '<th>killed</th><th>survived</th><th>inconclusive</th><th>equivalent</th><th>run</th></tr></thead><tbody>')
    for name, what in RUNNERS:
        e = M.get(name)
        if not e:
            o.append('<tr><td class="mono">%s</td><td class="role">%s</td><td colspan="6">%s</td></tr>'
                     % (esc(name), esc(what), pill("no reading", "na")))
            continue
        kind = "good" if e.get("survived", 0) == 0 and e.get("inconclusive", 0) == 0 else "bad"
        o.append('<tr><td class="mono">%s</td><td class="role">%s</td><td class="num">%d</td><td class="num">%s</td>'
                 '<td class="num">%d</td><td class="num">%d</td><td class="num">%d</td><td class="num dim">%s</td></tr>'
                 % (esc(name), esc(what), e.get("mutants", 0), pill(str(e.get("killed", 0)), kind), e.get("survived", 0),
                    e.get("inconclusive", 0), e.get("equivalent", 0), esc(when(e.get("at")))))
    o.append('</tbody></table></div></section>')

    # engines
    o.append('<section><div class="sec-head"><h2>The engines\' own suites</h2><span class="count">JUnit, read by '
             '<span class="mono">tools/ecosystem.py</span></span></div><div class="engines">')
    for name in sorted(E, key=lambda n: (-E[n].get("tests", 0), n)):
        e = E[name]
        if "tests" not in e:
            o.append('<div class="engine"><span class="ename">%s</span>%s</div>' % (esc(name), pill("no reading", "na")))
            continue
        kind = "good" if e.get("green") else "bad"
        o.append('<div class="engine"><span class="ename">%s</span>%s<span class="floor">floor %d</span></div>'
                 % (esc(name), pill("%d %s" % (e["tests"], "✓" if e.get("green") else "✗"), kind), e.get("floor", 0)))
    o.append('</div></section>')

    o.append('<footer><span>Rendered from the ledgers by <span class="mono">tools/harness_board.py</span>: '
             '<span class="mono">counts.json</span>, <span class="mono">walk_ledger.json</span>, '
             '<span class="mono">task_ledger.json</span>, <span class="mono">mutant_ledger.json</span>, '
             '<span class="mono">ecosystem_ledger.json</span>, <span class="mono">routes.json</span>; newest reading %s.'
             '</span><span class="mono">nothing here was typed.</span></footer>'
             % esc(when(S["newest"])))
    o.append('</div>')
    return "\n".join(o) + "\n"


STYLE = """<style>
  :root {
    --ground: #F5F3EF; --panel: #FDFCFA; --ink: #26231F; --muted: #6E675E; --line: #DDD8D0;
    --ember: #C4501B; --ember-soft: #F3E2D6; --seam: #5E7C8A; --good: #3E7A45; --good-soft: #E4EFE5;
    --bad: #A83232; --bad-soft: #F4DEDE; --na: #8A8378;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --ground: #191613; --panel: #211D18; --ink: #EAE4DA; --muted: #9A9186; --line: #3A342C;
      --ember: #E0672E; --ember-soft: #33241A; --seam: #7FA0AF; --good: #6FAE76; --good-soft: #1F2E21;
      --bad: #C96A6A; --bad-soft: #3A2222; --na: #8A8378;
    }
  }
  :root[data-theme="dark"] {
    --ground: #191613; --panel: #211D18; --ink: #EAE4DA; --muted: #9A9186; --line: #3A342C;
    --ember: #E0672E; --ember-soft: #33241A; --seam: #7FA0AF; --good: #6FAE76; --good-soft: #1F2E21;
    --bad: #C96A6A; --bad-soft: #3A2222; --na: #8A8378;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--ground); color: var(--ink); font-family: "Source Serif 4", Georgia, serif; font-size: 16px; line-height: 1.5; }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 44px 24px 80px; }
  h1, h2 { font-family: "Bricolage Grotesque", "Arial Black", sans-serif; text-wrap: balance; margin: 0; }
  h1 { font-size: clamp(2.2rem, 5vw, 3.4rem); font-weight: 800; line-height: 1.02; letter-spacing: -0.015em; }
  h2 { font-size: 1.35rem; font-weight: 800; }
  .mono, td.num, .pname, .pnum, .ename, .floor { font-family: "IBM Plex Mono", ui-monospace, monospace; }
  .eyebrow { font-family: "IBM Plex Mono", monospace; font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ember); font-weight: 600; }
  .hero .lede { font-size: 1.02rem; max-width: 66ch; color: var(--muted); margin: 12px 0 0; }
  .verdict { display: inline-block; margin-top: 16px; font-family: "Bricolage Grotesque", sans-serif; font-weight: 600; padding: 6px 12px; border-radius: 3px; border: 1px solid; }
  .verdict.good { color: var(--good); border-color: var(--good); background: var(--good-soft); }
  .verdict.bad { color: var(--bad); border-color: var(--bad); background: var(--bad-soft); }
  section { margin-top: 44px; }
  .sec-head { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; border-bottom: 2px solid var(--ink); padding-bottom: 8px; margin-bottom: 14px; }
  .sec-head .count { font-family: "IBM Plex Mono", monospace; color: var(--muted); font-size: 0.82rem; }
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
  .stat { background: var(--panel); border: 1px solid var(--line); border-top: 3px solid var(--ember); border-radius: 3px; padding: 14px 16px 12px; }
  .stat .big { font-family: "Bricolage Grotesque", sans-serif; font-weight: 800; font-size: 1.9rem; line-height: 1; color: var(--ember); font-variant-numeric: tabular-nums; }
  .stat .what { font-family: "IBM Plex Mono", monospace; font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-top: 8px; }
  .stat p { margin: 6px 0 0; font-size: 0.84rem; color: var(--muted); }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  .tablewrap { overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 3px; }
  th { font-family: "IBM Plex Mono", monospace; font-size: 0.68rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); text-align: left; padding: 9px 11px; border-bottom: 2px solid var(--line); white-space: nowrap; }
  td { padding: 8px 11px; border-bottom: 1px solid var(--line); vertical-align: baseline; }
  tr:last-child td { border-bottom: none; }
  td.num { font-variant-numeric: tabular-nums; white-space: nowrap; text-align: right; }
  td.dim { color: var(--muted); font-size: 0.8rem; }
  .role { color: var(--muted); font-size: 0.86rem; }
  .pill { display: inline-block; font-family: "IBM Plex Mono", monospace; font-size: 0.72rem; padding: 1px 7px; border-radius: 2px; border: 1px solid var(--line); white-space: nowrap; }
  .pill.good { color: var(--good); border-color: var(--good); background: var(--good-soft); }
  .pill.bad { color: var(--bad); border-color: var(--bad); background: var(--bad-soft); }
  .pill.na { color: var(--na); }
  .note { font-size: 0.86rem; color: var(--muted); max-width: 80ch; margin: 10px 0 0; }
  .pages { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 6px; }
  .page { display: flex; flex-direction: column; gap: 2px; background: var(--panel); border: 1px solid var(--line); border-left: 3px solid var(--good); border-radius: 2px; padding: 7px 10px; }
  .page.bad { border-left-color: var(--bad); }
  .pname { font-size: 0.8rem; font-weight: 600; }
  .pnum { font-size: 0.7rem; color: var(--muted); }
  .engines { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 6px; }
  .engine { display: flex; align-items: baseline; gap: 10px; background: var(--panel); border: 1px solid var(--line); border-radius: 2px; padding: 7px 10px; }
  .ename { font-size: 0.82rem; font-weight: 600; flex: 1; }
  .floor { font-size: 0.7rem; color: var(--muted); }
  footer { margin-top: 56px; border-top: 2px solid var(--ink); padding-top: 12px; font-size: 0.82rem; color: var(--muted); display: flex; flex-wrap: wrap; gap: 8px 24px; }
  footer .mono { font-size: 0.76rem; }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
</style>"""


def main(argv):
    L = ledgers()
    page = render(L)
    if "--check" in argv:
        cur = io.open(OUT, encoding="utf-8").read() if os.path.isfile(OUT) else ""
        if cur == page:
            print("the board is what the ledgers say")
            return 0
        print("the board has drifted from the ledgers: run tools/harness_board.py")
        return 1
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(page)
    S = summary(L)
    print("wrote %s: %d/%d checks, %d commands walked, %d/%d tasks, %d/%d traces, %d/%d mutants, %d engine tests"
          % (OUT, S["checks"], S["of"], S["commands"], S["tasks_held"], S["tasks"], S["traces_held"], S["traces"],
             S["killed"], S["mutants"], S["engine_tests"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
