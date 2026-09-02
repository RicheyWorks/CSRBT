# -*- coding: utf-8 -*-
"""The Whole Hog Atlas's engine table, regenerated from the ledger (ADR-120).

WHY

The Atlas (WholeHog/docs/atlas.html, published as an artifact) carries one row
per engine with its version and its suite count. Both were typed by hand on
2026-08-20 and never again: by 2026-09-02 seven versions and eleven suite
counts had moved, and a held item it listed had been cut for ten days. ADR-118
built the ledger the table should come from; this is the consumer that makes
the table come from it, and the check that fails when it does not.

WHAT

    python3 tools/atlas.py            # rewrite the rows between the markers
    python3 tools/atlas.py --check    # exit 1 if the file's rows are not what the ledger says

Rows are generated between <!-- engines:begin --> and <!-- engines:end -->
in the Atlas, and the stamp between <!-- stamp:begin --> / <!-- stamp:end -->
says when the counts were read. The ROLE prose is the one hand-written part
and lives here, beside the numbers it decorates. Versions are read from each
repo's build.gradle.kts (csrbt-core's for CSRBT). A suite is a green pill
only when the ledger read it green; an engine the ledger has no reading for
gets a grey "no reading" pill, never an invented number.
"""
import io, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ecosystem as E

ATLAS = os.path.normpath(os.path.join(E.SIBLINGS, "WholeHog", "docs", "atlas.html"))
GITHUB = "https://github.com/RicheyWorks/"

# (number, repo, ledger engines summed into its pill, role prose)
ROWS = [
    (1, "CSRBT", ("csrbt-core", "csrbt-experimental"),
     "the adaptive ordered index — Red-Black/AVL/Splay/Hybrid strategies, ensembles, evolution, "
     "ecology instruments, classroom seam; the harness's lab console (core + experimental suites)"),
    (2, "SuperBeefSort", ("SuperBeefSort",),
     "the intake tract — profiles, sorts, feeds in O(n); the recovery engine (main suite; the native "
     "kernels need JDK 22 + Rust and skip themselves elsewhere)"),
    (3, "SmokeHouse", ("SmokeHouse",),
     "the log-structured store — durability, tail, watchers, replicas, sorted-run exports, "
     "configurable ring, bounded as-of recovery, the replication feed seam"),
    (4, "Carver", ("Carver",),
     "the read planner — costs access paths with CSRBT order statistics as its histogram"),
    (5, "Renderer", ("Renderer",),
     "the materialized-view engine — folds the tail into live ranked aggregates"),
    (6, "Brine", ("Brine",),
     "the adaptive cache — eviction policy evolved by csrbt-experimental's machine"),
    (7, "PitBoss", ("PitBoss",),
     "the fleet conductor — lag watched from the conductor's seat, gap re-bootstrap, the promotion runbook"),
    (8, "DryAge", ("DryAge",),
     "time travel — CRC'd generations, scan-carrying preserves, retention as one call, as-of a record"),
    (9, "Twine", ("Twine",),
     "crash-atomic batches — journaled commit, idempotent replay, enforced single writer, metered"),
    (10, "SmokeSignal", ("SmokeSignal",),
     "the wire — loopback protocol: reads, routed writes, whole batches, ranges, its own meter; "
     "framing errors close, execution errors answer"),
    (11, "Jerky", ("Jerky",),
     "cold storage — compressed CRC-verified archives, targeted extraction"),
    (12, "WholeHog", ("WholeHog",),
     "the integration organism — all of them at once, one composed oracle, the findings ledger, "
     "the harness console"),
    (13, "Rub", ("Rub",),
     "observability — tail meter fused with store gauge into vitals; the pulse; honest gaps"),
    (14, "Sizzle", ("Sizzle",),
     "chaos — deterministic fault + latency injection at the write seam, the tail and the replication feed"),
]

VERSION = re.compile(r'^version\s*=\s*"([^"]+)"', re.M)


def version_of(repo):
    f = os.path.join(E.repo_dir(repo), "csrbt-core" if repo == "CSRBT" else "", "build.gradle.kts")
    if not os.path.isfile(f):
        return None
    m = VERSION.search(io.open(f, encoding="utf-8").read())
    return m.group(1) if m else None


def pill(led, engines):
    es = [led.get("engines", {}).get(n) for n in engines]
    if any(e is None or "tests" not in e for e in es):
        return '<span class="pill na">no reading</span>'
    tests = sum(e["tests"] for e in es)
    green = all(e.get("green") for e in es)
    return ('<span class="pill green">%d ✓</span>' % tests) if green else \
           ('<span class="pill" style="color:var(--bad);border-color:var(--bad)">%d ✗</span>' % tests)


def rows(led):
    out = []
    for no, repo, engines, role in ROWS:
        v = version_of(repo)
        vp = ('<span class="pill v">%s</span>' % v) if v else '<span class="pill na">—</span>'
        out.append('          <tr><td class="no">%d</td><td class="eng"><a href="%s%s">%s</a></td>'
                   '<td class="role">%s</td><td>%s</td><td class="num">%s</td></tr>'
                   % (no, GITHUB, repo, repo, role, vp, pill(led, engines)))
    return "\n".join(out)


def stamp(led):
    ats = [e.get("at", 0) for e in led.get("engines", {}).values() if "tests" in e]
    if not ats:
        return "suites: no reading"
    total = sum(e.get("tests", 0) for e in led.get("engines", {}).values())
    return "suites read %s · %d tests" % (time.strftime("%Y-%m-%d", time.localtime(min(ats))), total)


def splice(html, begin, end, body):
    i = html.index(begin) + len(begin)
    j = html.index(end)
    return html[:i] + "\n" + body + "\n" + html[j:] if "\n" in html[i:j] else html[:i] + body + html[j:]


def render(html, led):
    html = splice(html, "<!-- engines:begin -->", "<!-- engines:end -->", rows(led))
    html = splice(html, "<!-- stamp:begin -->", "<!-- stamp:end -->", stamp(led))
    return html


def main(argv):
    check = "--check" in argv
    if not os.path.isfile(ATLAS):
        print("no Atlas at %s" % ATLAS)
        return 2
    led = E.load_ledger()
    html = io.open(ATLAS, encoding="utf-8").read()
    new = render(html, led)
    if check:
        if new == html:
            print("the Atlas's engine table is what the ledger says")
            return 0
        print("the Atlas's engine table has drifted from the ledger: run tools/atlas.py")
        return 1
    io.open(ATLAS, "w", encoding="utf-8", newline="\n").write(new)
    print("wrote %s (%s)" % (ATLAS, stamp(led)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
