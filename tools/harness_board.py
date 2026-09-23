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
    counts = _load(os.path.join("verify", "counts.json"), {"suites": {}})
    # ADR-241: the tree the counts were measured on, against the tree now. Read
    # here, with the ledgers, so render() stays a function of its input and a
    # fixture can say what the tree situation is.
    try:
        import evidence as EV
        tree = EV.status(counts, ROOT)
    except Exception as e:
        tree = {"error": str(e)[:120]}
    return {
        "counts": counts,
        "tree": tree,
        "walk": _load("walk_ledger.json", {"targets": {}}),
        "tasks": _load("task_ledger.json", {"tasks": {}}),
        "contention": _load("contention_ledger.json", {"suites": {}}),
        "entry": _load("entry_ledger.json", {"pages": {}}),
        # ADR-146: the figures a page publishes that read-report cannot see.
        "readable": _load("readable_ledger.json", {"pages": {}}),
        # ADR-147: what a slice has actually handed over, by content.
        "delivery": _load("delivery_ledger.json", {"paths": {}}),
        "mutants": _load("mutant_ledger.json", {"runners": {}}),
        "ecosystem": _load("ecosystem_ledger.json", {"engines": {}}),
        "routes": _load("routes.json", {"routes": []}),
    }


HARNESS_SUITES = [
    ("verify_contract", "the gateway contract: policy, replay, arguments, redaction"),
    ("verify_organism", "the organism through the gateway: one oracle per engine"),
    ("verify_lab", "the science engine: the shipped protocol reproduced"),
    ("verify_mcp", "the second transport decides nothing"),
    ("verify_brief", "a goal hands over every value its task enters, and holds what the grader scores"),
    ("verify_http", "the third transport, and the first one anything else can reach"),
    ("verify_frames", "the wire under all three: nothing a client sends closes a door, and it hears UTF-8"),
    ("verify_walk", "the robot, every target, both transports, every page"),
    ("verify_tasks", "goals with graded expectations; traces held to them; the science tasks"),
    ("verify_report", "the page reader: every figure, the right option, every control named"),
    ("verify_audit_states", "the audits, everywhere: every state of every page measured, the unreached counted"),
    ("verify_ecosystem", "the engines' own suites, ratcheted; the Atlas"),
    ("verify_engine_sessions", "shipped sessions bound to the engine"),
    ("verify_harness", "the swarm's driver over the kit's pages"),
    ("verify_harness_matrix", "the swarm's verdicts mean something"),
    ("verify_anchors", "the mutant ledger is about the code as it is: every anchor lands, no catalogue drifted"),
    ("verify_addresses", "a control's name outlives pressing it: nothing renamed by its own count, nothing shadowed"),
    ("verify_evidence", "the counts are about this tree, and no suite counts fewer than its floor"),
]

RUNNERS = [
    ("mutate_organism", "the organism plugin and console"),
    ("mutate_lab", "the lab plugin and console"),
    ("mutate_mcp", "the MCP transport"),
    ("mutate_http", "the HTTP transport: origin, token, session, thread"),
    ("mutate_frames", "the wire: strict bytes, strict JSON, typed refusals, the backstop, the envelope"),
    ("mutate_walk", "the robot"),
    ("mutate_tasks", "the task runner and grader"),
    ("mutate_brief", "the brief: what a task gives, what it holds, and the goal's figures bound to its claims"),
    ("mutate_report", "the page reader, picker and naming"),
    ("mutate_audit_states", "the audits' state walker and accounting"),
    ("mutate_harness", "the swarm's driver"),
    ("mutate_publish", "the publish pipeline and its reach"),
    ("mutate_engines", "the engine ledger's ratchet and the engine attestation"),
    ("mutate_contract", "the door itself: the risk ladder, the raise, the replay"),
    ("mutate_contend", "the contention instrument"),
    ("mutate_entry", "the entry-reach measurement"),
    ("mutate_readable", "the readable-figures audit"),
    ("mutate_badinput", "the rejected-buffer audit"),
    ("mutate_outputs", "the outputs audit"),
    ("mutate_destructive", "the destructive audit: what one tap takes, and whether the page asks"),
    ("mutate_restored", "the restored-page audit: what a page says when it comes back"),
    ("mutate_carried", "the carried-figures audit: what a page works out that no export carries"),
    ("mutate_takeaway", "the take-away audit: which channels survive publication, and what the page says"),
    ("mutate_delivery", "the delivery manifest and its audit"),
    ("mutate_declared", "the exemption reader: whether a written reason is still about anything"),
    ("mutate_fek", "the shared entry layer every data-entry page inlines"),
    ("mutate_ci", "the CI workflow's path filter, and the matcher that holds it"),
    ("mutate_outbox", "the outbox: what has not left this device"),
    ("mutate_keep", "the local autosave layer, and the sentence it says when it cannot save"),
    ("mutate_board", "this page: the arithmetic behind every tile, the verdict, and what each row renders"),
    ("mutate_mb", "the micro bench's reports: the saturation sentence, the breakpoint band, organism and medium"),
    ("mutate_proofs", "the tree proofs' worst-case sentence, read off the tree it describes"),
    ("mutate_anchors", "the anchor audit: whether the ledger's kills are about the code as it is"),
    ("mutate_ord", "the ordination page's verdicts: a perfect fit, the unreadable-value count, the toast"),
    ("mutate_sel", "the selection log's next-individual line: a cleared dial said, the missing named"),
    ("mutate_addresses", "the address audit and the door's resolver: a name read off the page as it stands"),
    ("mutate_etho", "the ethogram's budget: the note's three numbers, the sheet's bouts, the CSV's whole"),
    ("mutate_evidence", "what the evidence is about: the tree every count was taken on, and the floor no suite falls below"),
    ("mutate_rv", "the relevé's voucher dials: unset until said, the next voucher named, no phenophase invented"),
]


def esc(x):
    return html.escape(str(x))


def when(ts):
    # UTC, NOT LOCAL TIME. verify_board holds the committed page byte-for-byte to
    # what the ledgers render, and a page stamped in the renderer's zone is a
    # different page on every machine in a different one: the copy rendered in
    # the container (UTC-7) failed that check on the operator's VM (UTC) with
    # every ledger identical (ADR-226).
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts)) if ts else "—"


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
    runs = {k: e for k, e in T.items() if not k.endswith(("@trace", "@blind"))}
    traces = {k: e for k, e in T.items() if k.endswith(("@trace", "@blind"))}   # ADR-136: blind traces count too
    M = L["mutants"]["runners"]
    E = L["ecosystem"]["engines"]
    tree = L.get("tree") or {}
    return {
        "checks": n, "of": of, "holes": holes, "suites": len(c), "green": green,
        # ADR-241: whether every count is about the tree as it stands, and
        # which suites counted fewer checks than their committed floor.
        "tree_ok": bool(tree.get("same")) and not tree.get("off") and not tree.get("moved")
                   and not tree.get("unstamped"),
        "tree_now": tree.get("now") or "", "tree_recorded": tree.get("recorded") or "",
        "tree_files": tree.get("files") or 0,
        "tree_diff": tree.get("diff") or {"changed": [], "added": [], "removed": []},
        "tree_off": tree.get("off") or [], "tree_moved": tree.get("moved") or [],
        "tree_unstamped": tree.get("unstamped") or [],
        "below_floor": sorted((k, v.get("n"), v.get("below_floor")) for k, v in c.items() if v.get("below_floor")),
        "targets": len(targets), "pages": len(pages), "bad_walks": bad_walks,
        "commands": sum(e.get("commands", 0) for e in W.values()),
        "tasks": len(runs), "tasks_held": sum(1 for e in runs.values() if e.get("held")),
        # ADR-193: what the briefs HAND OVER and what they HOLD. The third
        # blind trial graded four operators against readings their goals never
        # named and data they were never given; these two numbers are the
        # difference between a hard trial and an unfair one, so they are on the
        # board rather than in a paragraph.
        "given": sum(e.get("gives") or 0 for e in runs.values()),
        "held_readings": sum(e.get("holds") or 0 for e in runs.values()),
        "held_claims": sum(e.get("claims") or 0 for e in runs.values()),
        # ADR-142: how many of them entered their data with no destructive rung.
        # An entry written before that ADR carries no rungs at all and is not
        # counted either way -- a ledger row from a run that did not record the
        # thing cannot be read as a row that recorded the good answer.
        # ADR-143: what the kit says when the machine is busy. Two numbers,
        # because one of them alone lies: how many readings have never failed,
        # and how many RUNS that rests on -- "0 failed" over three runs is an
        # upper bound, not a promise.
        # ADR-144: how much of the kit's data its own tasks actually enter.
        # Pages with nothing to enter (a reference page, a glossary) have no
        # fields and drop out of both halves on their own.
        "fields": sum(e.get("fields", 0) for e in (L["entry"].get("pages") or {}).values()),
        "fields_entered": sum(e.get("entered", 0) for e in (L["entry"].get("pages") or {}).values()),
        "entry_pages": sum(1 for e in (L["entry"].get("pages") or {}).values() if e.get("fields")),
        # ADR-146: an element the page writes a figure into that read-report
        # cannot see is a figure no task can hold, and no suite can fail on.
        "written": sum(e.get("written", 0) for e in (L["readable"].get("pages") or {}).values()),
        "unreadable": sum(len(e.get("unreadable") or [])
                          for e in (L["readable"].get("pages") or {}).values()),
        "blind_pages": sum(1 for e in (L["readable"].get("pages") or {}).values()
                           if e.get("unreadable")),
        # ADR-147: a file on disk and in no commit is present in every
        # measurement this kit takes and absent from the repository.
        "delivered": len(L["delivery"].get("paths") or {}),
        "slices": len(set(e.get("by") for e in (L["delivery"].get("paths") or {}).values()
                          if e.get("by"))),
        "load_readings": len(L["contention"].get("suites") or {}),
        "load_clean": sum(1 for e in (L["contention"].get("suites") or {}).values()
                          if not e.get("failed")),
        "load_runs": sum(e.get("runs", 0) for e in (L["contention"].get("suites") or {}).values()),
        "load_failed": sum(e.get("failed", 0) for e in (L["contention"].get("suites") or {}).values()),
        "supervised": sum(1 for e in runs.values()
                          if e.get("rungs") and "DESTRUCTIVE" not in e["rungs"]),
        "rung_known": sum(1 for e in runs.values() if e.get("rungs")),
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


def tree_line(S):
    """ADR-241: which tree the counts are about, said on the page. A board that
    was green about a tree that no longer exists says so, and names the files."""
    if S["tree_ok"]:
        return ('<p class="tree">Measured on tree <span class="mono">%s</span>, %d subject files, '
                'which is the tree as it stands.</p>' % (esc(S["tree_now"]), S["tree_files"]))
    d = S["tree_diff"]
    parts = []
    if not S["tree_recorded"]:
        parts.append("no run has recorded a tree")
    for k in ("changed", "added", "removed"):
        if d.get(k):
            parts.append("%d %s: %s%s" % (len(d[k]), k, ", ".join(d[k][:5]), "…" if len(d[k]) > 5 else ""))
    if S["tree_moved"]:
        parts.append("the tree moved DURING the run: " + ", ".join(S["tree_moved"][:5]))
    if S["tree_off"]:
        parts.append("%d count(s) from another tree: %s" % (len(S["tree_off"]), ", ".join(S["tree_off"][:5])))
    if S["tree_unstamped"]:
        parts.append("%d count(s) carry no tree: %s" % (len(S["tree_unstamped"]), ", ".join(S["tree_unstamped"][:5])))
    return ('<p class="tree bad">The counts are about tree <span class="mono">%s</span>; this tree is '
            '<span class="mono">%s</span> \u2014 %s. Rerun <span class="mono">run_all</span>.</p>'
            % (esc(S["tree_recorded"] or "none"), esc(S["tree_now"]), esc("; ".join(parts) or "the digests differ")))


def render(L):
    S = summary(L)
    c = L["counts"]["suites"]
    W = L["walk"]["targets"]
    T = L["tasks"]["tasks"]
    M = L["mutants"]["runners"]
    E = L["ecosystem"]["engines"]
    # WHAT THE VERDICT IS COMPUTED FROM, WRITTEN DOWN AND SHOWN (ADR-215).
    #
    # This was a hand-written conjunction over seven summary fields, and the
    # board rendered eleven tiles. Six of the eleven do not gate the verdict --
    # including "6 / 7 clean under load", which reads exactly like a failing
    # ratio and sat beside "Everything the harness knows how to check is green."
    # A reader with those two on one screen has to distrust one of them, and
    # nothing on the page said which.
    #
    # Two of the gates have no tile at all (the walks and the traces), so the
    # honest shape is not "every tile gates" -- it is the list, named, rendered,
    # and the verdict DERIVED from it rather than restated beside it. A gate
    # added here appears on the page the same day; the old conjunction could be
    # extended without the page ever mentioning it.
    GATES = [
        ("every suite check passes", S["of"] == S["checks"], "suite checks passing"),
        ("every walk of every target holds", not S["bad_walks"], None),
        ("every task is held", S["tasks_held"] == S["tasks"], "tasks held"),
        ("every trace is held", S["traces_held"] == S["traces"], None),
        ("no mutant survived", S["survived"] == 0, "mutants killed"),
        ("no mutant was inconclusive", S["inconclusive"] == 0, "mutants killed"),
        ("no engine suite failed", S["engine_failures"] == 0, "engine tests"),
        # ADR-241, ported from the FlowersForever harness: evidence is about
        # the tree it was taken on, and a suite may not shrink below its floor.
        ("the counts are about this tree", S["tree_ok"], None),
        ("no suite counts fewer than its floor", not S["below_floor"], "suite checks passing"),
    ]
    all_green = all(ok for _n, ok, _t in GATES)
    GATED = set(t for _n, _ok, t in GATES if t)

    o = []
    o.append('<title>Harness Board</title>')
    o.append('<link rel="preconnect" href="https://fonts.googleapis.com">')
    # ADR-031's rule, and the board had been breaking it where the reader is:
    # a webfont stylesheet requested with media="all" holds first paint until
    # the font server answers. Every page of the kit asks for it as print and
    # promotes it on load; the board is a page of this kit. Found by measuring
    # the PUBLISHED copy (ADR-140), which is the only place it was ever true.
    _f = ("https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;"
          "12..96,600;12..96,800&family=IBM+Plex+Mono:wght@400;500;600&"
          "family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap")
    o.append('<link rel="stylesheet" href="%s" media="print" data-webfont>' % _f)
    o.append('<noscript><link rel="stylesheet" href="%s"></noscript>' % _f)
    o.append('<script>(function(){var l=document.querySelector("link[data-webfont]");if(!l)return;'
             'var on=function(){l.media="all";};'
             'if(l.sheet){on();}else{l.addEventListener("load",on);l.addEventListener("error",function(){});}'
             '})();</script>')
    o.append(STYLE)
    o.append('<div class="wrap">')
    o.append('<header class="hero"><div class="eyebrow">CSRBT · the automation harness · every ledger, rendered</div>'
             '<h1>Harness Board</h1>'
             '<p class="lede">What the harness can currently vouch for, read from its own ledgers and never typed: '
             'the suites, the robot\'s walks of every target and every page, the tasks and the traces graded against them, '
             'the mutant runners, and the fourteen engines\' own suites. A number here that disagrees with a ledger '
             'fails <span class="mono">verify_board</span>.</p>'
             '<div class="verdict %s">%s</div>'
             '<p class="gates">The verdict is these %d and nothing else: %s. '
             'Every other number below is a READING -- a measurement with a ratchet or a worklist '
             'behind it, which moves on its own schedule and does not decide whether this page is '
             'green.</p>%s</header>'
             % ("good" if all_green else "bad",
                "Everything the harness knows how to check is green." if all_green else
                "Something is not green — read down.",
                len(GATES),
                "; ".join("%s%s" % (n, "" if ok else " \u2014 NOT MET") for n, ok, _t in GATES),
                tree_line(S)))

    # summary strip
    o.append('<section><div class="stats">')
    tiles = [
        ("%d / %d" % (S["checks"], S["of"]), "suite checks passing", "%d suites, %d green%s; the audits are run_all's%s" % (
            S["suites"], S["green"], (", %d NOT VERIFIED" % S["holes"]) if S["holes"] else ", no holes",
            ("; BELOW FLOOR: " + ", ".join("%s %s<%s" % b for b in S["below_floor"])) if S["below_floor"] else "")),
        ("%d" % S["commands"], "commands walked", "%d targets × 2 transports, %d pages" % (S["targets"] // 2, S["pages"])),
        ("%d / %d" % (S["tasks_held"], S["tasks"]), "tasks held", "%d / %d traces held, %d expectations confirmed"
         % (S["traces_held"], S["traces"], S["confirmed"])),
        ("%d" % S["given"], "values handed over",
         "every value the %d tasks enter is in the brief an operator is given -- %d reading(s) "
         "and %d claim(s) held, which is what a trial may fairly mark" % (
             S["tasks"], S["held_readings"], S["held_claims"])),
        ("%d / %d" % (S["supervised"], S["rung_known"]), "entered supervised",
         "tasks that enter their data with no destructive rung; the rest declare it, with a reason"),
        ("%d / %d" % (S["fields_entered"], S["fields"]), "fields entered",
         "of the controls that carry a value across %d page(s), how many any task has ever put "
         "a value into" % S["entry_pages"]),
        ("%d / %d" % (S["written"] - S["unreadable"], S["written"]), "figures readable",
         "of the elements the pages write a figure into, how many read-report can see; %d page(s) "
         "still publish one it cannot" % S["blind_pages"]),
        ("%d" % S["delivered"], "files delivered",
         "paths whose exact bytes a slice has handed over, across %d slice(s); anything else on "
         "disk is in no commit" % S["slices"]),
        ("%d / %d" % (S["load_clean"], S["load_readings"]), "clean under load",
         "readings taken while other suites of this kit ran beside them: %d run(s), %d failed"
         % (S["load_runs"], S["load_failed"])),
        ("%d / %d" % (S["killed"], S["mutants"]), "mutants killed", "%d survived, %d inconclusive, %d recorded equivalent"
         % (S["survived"], S["inconclusive"], S["equivalent"])),
        ("%d" % S["engine_tests"], "engine tests", "%d suites, %d failures" % (S["engines"], S["engine_failures"])),
    ]
    # ADR-215: EVERY TILE SAYS WHICH IT IS. A tile whose label is named by a gate
    # above carries the verdict; every other tile says, in one line, what kind of
    # number it is instead -- because a ratio that reads like a score beside a
    # green banner makes a reader distrust one of the two, and until now the page
    # gave them nothing to decide with. The reasons live here, beside the tiles,
    # rather than in a comment nobody renders.
    WHY = {
        "commands walked": "a count of what the robot drove; the walks' own verdicts gate, and "
                           "they are in the table below",
        "values handed over": "a count of what the briefs give an operator, with a floor rather "
                              "than a target",
        "entered supervised": "a ratio with a REASON on the other side -- the rest declare a "
                              "destructive rung, in writing",
        "fields entered": "entry reach: a ratchet that only comes down, not a pass mark",
        "figures readable": "a ratchet that only comes down, not a pass mark",
        "files delivered": "a running total; audit_delivery is the gate, and it runs in run_all",
        # ADR-216: THIS SENTENCE USED TO ASSERT A RATCHET THAT DID NOT EXIST. The
        # line ADR-215 wrote here called the reading "a known flake with a
        # ratchet", and the contention ledger had no ceiling, no declaration and
        # nothing that ran it -- a reassuring sentence about a mechanism nobody
        # had built, on the one page whose job is to say what the harness can
        # vouch for. The ratchet exists now, and the sentence says what it does.
        "clean under load": "a ceiling per pairing that only comes down: a pairing that fails "
                            "more under load than it did fails tools/contend.py, which run_all "
                            "runs. The sweep that takes the readings is opt-in and slow; reading "
                            "them is not",
        "engine tests": "a count; the failures beside it are what gate, and they are zero",
    }
    for big, what, note in tiles:
        gate = what in GATED
        assert gate or what in WHY, "a tile must gate the verdict or say what it is instead: " + what
        o.append('<div class="stat"><div class="big">%s</div><div class="what">%s</div><p>%s</p>'
                 '<p class="kind %s">%s</p></div>'
                 % (esc(big), esc(what), esc(note),
                    "gate" if gate else "reading",
                    esc("counts toward the verdict" if gate else "a reading, not a gate \u2014 "
                        + WHY[what])))
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
             '<th>confirmed</th><th>trace</th><th>blind trace</th><th>calls for steps</th></tr></thead><tbody>')
    for k in sorted(k for k in T if not k.endswith(("@trace", "@blind"))):
        e = T[k]
        tr = T.get(k + "@trace")
        bl = T.get(k + "@blind")
        o.append('<tr><td class="mono">%s</td><td class="mono">%s</td><td>%s</td><td class="num">%d</td><td>%s</td>'
                 '<td>%s</td><td class="num">%s</td></tr>'
                 % (esc(k), esc(e.get("target")), pill("%s%s" % (e.get("verdict"), " · must FAIL" if e.get("must") == "FAIL" else ""),
                                                        "good" if e.get("held") else "bad"), e.get("confirmed", 0),
                    pill("%s" % tr.get("verdict"), "good" if tr.get("held") else "bad") if tr else pill("no trace", "na"),
                    pill("%s" % bl.get("verdict"), "good" if bl.get("held") else "bad") if bl else pill("—", "na"),
                    esc("%d for %d" % ((bl or tr).get("calls", 0), (bl or tr).get("required", 0))) if (tr or bl) else "—"))
    o.append('</tbody></table></div><p class="note">A run follows the task\'s steps through the gateway. A trace is what '
             'an operator given only the goal did through the MCP door, held to the same expectations; its economy is '
             'calls made for required steps. A BLIND trace (ADR-136) is one an operator produced who had never seen the '
             'task at all -- the goal sentence verbatim, a JSON-RPC console, and a checkout with the tasks, the traces, '
             'the ledger and every ADR deleted.</p></section>')

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
             '<span class="mono">ecosystem_ledger.json</span>, <span class="mono">routes.json</span>; newest reading %s; every time on this page is UTC.'
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
  .gates { font-size: 0.86rem; color: var(--muted); max-width: 80ch; margin: 10px 0 0; }
  .kind { font-family: "IBM Plex Mono", monospace; font-size: 0.64rem; letter-spacing: 0.05em;
          text-transform: uppercase; margin: 8px 0 0; }
  .kind.gate { color: var(--good); }
  .kind.reading { color: var(--na); text-transform: none; letter-spacing: 0; font-size: 0.7rem; }
  .tree { margin-top: 10px; font-size: 13px; color: var(--muted); }
  .tree.bad { color: var(--bad); }
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
