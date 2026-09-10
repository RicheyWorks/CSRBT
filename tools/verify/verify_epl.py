# -*- coding: utf-8 -*-
"""Suite for docs/eco-protocol-library.html -- the five ready-made .eco experiments (ADR-177).

The library is a reference page with one thing to hand over: each protocol's
Copy button puts the protocol on the clipboard, "ready to copy, edit, and run".
audit_outputs found that Copy read by nothing -- the task pressed it and read
the toast, never the text. This suite holds what leaves the page to the two
things that can judge it:

  A. the page itself: five protocols, each named *.eco, each with one Copy that
     puts exactly the protocol's text on the clipboard, byte for byte.
  B. the engine the page says to run it in: every copied protocol is parsed by
     ExperimentSpec with no problem line, its summary counts the phases, models
     and expectations the text carries, and its pre-registered hypotheses are
     graded -- the line the page marks "deliberately wrong" is the one REFUTED,
     and every other prediction the page makes is CONFIRMED. (ADR-177 found two
     protocols whose predictions the engine refuted; ADR-178 rewrote them to
     the bands the data sits in, and this suite holds that no protocol carries
     a refuted prediction the page did not call wrong.)
  C. the TASK's literal -- what page-eco-protocol-library-reference.json holds
     the first Copy to -- is that same text.

The engine is optional here as everywhere: with csrbt-experimental unbuilt the
B checks say so and skip.

Run:  python3 tools/verify/verify_epl.py
"""
# Declared for tools/mutate.py. This suite uses a temp dir -- the engine writes
# each copied protocol's session and export bundle into one -- but it builds no
# fixture pages: every assertion is about docs/eco-protocol-library.html itself,
# so a sweep of that page must count it.
MUTATE_ROLE = "subject"
import io, json, os, re, subprocess, sys, tempfile, shutil
from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PAGE = "file://" + os.path.join(ROOT, "docs", "eco-protocol-library.html").replace(os.sep, "/")
TASK = os.path.join(ROOT, "tools", "tasks", "page-eco-protocol-library-reference.json")
CP_FILE = os.path.join(ROOT, "csrbt-experimental", "build", "harness", "classpath.txt")
MAIN = "io.github.richeyworks.csrbt.experimental.ecology.ExperimentLab"

ok = bad = 0
SKIP = []
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))
def skip(name, why):
    SKIP.append(name); print("SKIP  %s  (%s)" % (name, why))


def classpath():
    cp = os.environ.get("CSRBT_LAB_CLASSPATH")
    if not cp:
        if not os.path.isfile(CP_FILE):
            return None
        cp = io.open(CP_FILE, encoding="utf-8").read().strip()
    return cp if os.path.isdir(cp.split(os.pathsep)[0]) else None


COMMENT = re.compile(r"\s+#.*$")
def directives(text, kind):
    """Every `kind:` line of a protocol, comment stripped -> [(body, comment)].
    `note(x):` is a `note:` -- the parenthesis scopes it (verify_eco_experiment)."""
    out = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not re.match(r"^%s(\([^)]*\))?:" % re.escape(kind), line):
            continue
        body = COMMENT.sub("", line).split(":", 1)[1].strip()
        note = raw[len(COMMENT.sub("", raw)):].strip()
        out.append((body, note))
    return out


def run_engine(cp, name, text, tmp):
    """ExperimentLab on the copied text -> (report.txt, session dict) or (None, err)."""
    spec = os.path.join(tmp, name)
    io.open(spec, "w", encoding="utf-8", newline="\n").write(text + "\n")
    sess = spec[:-4] + "-session.json"
    outd = spec[:-4] + "-out"
    p = subprocess.run(["java", "-cp", cp, MAIN, spec, sess, outd],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if p.returncode != 0:
        return None, (p.stderr or p.stdout)[-300:]
    rep = io.open(os.path.join(outd, "report.txt"), encoding="utf-8").read()
    return rep, json.load(io.open(sess, encoding="utf-8"))


# A line commented "deliberately wrong" must be REFUTED; every other prediction
# on the page must be CONFIRMED. ADR-177 found two-ponds.eco grading 1 of 3 and
# activity-budget.eco 0 of 2 -- predictions the page presented as the
# experiment's, refuted by the engine -- and recorded them here as the reading;
# ADR-178 rewrote those four lines to the bands the data sits in (evenness
# moderate and very-even, turnover moderate, Bray-Curtis > 0.2), so the
# recorded exceptions are gone and a new protocol with the same fault fails.
KNOWN_REFUTED = {}

errors = []
protos = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1000, "height": 1200})
    ctx.add_init_script(
        "Object.defineProperty(navigator, 'clipboard', {get: () => ({"
        "writeText: t => { window.__copied = t; return Promise.resolve(); }})});")
    pg = ctx.new_page()
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    pg.on("console", lambda m: errors.append(m.text)
          if m.type == "error" and "Failed to load resource" not in m.text else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(PAGE, wait_until="domcontentloaded"); pg.wait_for_timeout(300)

    # ---- A. the page: five protocols, each copied whole ----
    protos = pg.evaluate("""() => [...document.querySelectorAll('.protobox')].map(b => ({
        name: (b.querySelector('.fn') || {}).textContent || '',
        copies: b.querySelectorAll('button.copy').length,
        text: (b.querySelector('pre') || {}).textContent || ''}))""")
    dek = pg.text_content(".dek") or ""
    ck("the page promises five complete .eco experiments, and carries five protocol boxes",
       "Five complete" in dek and len(protos) == 5, (dek[:40], len(protos)))
    ck("every protocol is named *.eco and has exactly one Copy",
       all(p["name"].endswith(".eco") and p["copies"] == 1 for p in protos), [(p["name"], p["copies"]) for p in protos])
    ck("no two protocols share a name", len(set(p["name"] for p in protos)) == len(protos), [p["name"] for p in protos])
    ck("every protocol names itself on its first line, and every line is a directive, a comment or blank",
       all(p["text"].startswith("name: ") and
           all(re.match(r"^(#|[a-z]+(\([^)]*\))?:)", ln) for ln in p["text"].split("\n") if ln.strip())
           for p in protos), [p["text"][:30] for p in protos])
    for i, p in enumerate(protos):
        pg.evaluate("window.__copied = null")
        pg.click(".protobox >> nth=%d >> button.copy" % i); pg.wait_for_timeout(120)
        got = pg.evaluate("window.__copied")
        ck("Copy on %s puts the protocol on the clipboard, byte for byte, and only it" % p["name"],
           got == p["text"] and got.count("name: ") == 1, (got or "")[:80])
    ck("...and the page says so: the toast reads Copied, save as a .eco file",
       (pg.text_content("#toast") or "").strip() == "Copied — save as a .eco file", pg.text_content("#toast"))
    meadow = protos[0]["text"] if protos else ""
    ck("the meadow protocol carries the hot 2000 5 90 line the prose points at, and one deliberately wrong expectation",
       "hot 2000 5 90" in meadow and
       sum(1 for _, c in directives(meadow, "expect") if "deliberately wrong" in c) == 1, meadow[:120])
    b.close()

# ---- B. the engine: every copied protocol parses, and is graded as the page says ----
cp = classpath()
if not cp:
    skip("engine checks on the five protocols", "csrbt-experimental is not built: ./gradlew :csrbt-experimental:harnessClasspath")
else:
    tmp = tempfile.mkdtemp(prefix="epl_")
    try:
        for p in protos:
            rep, sess = run_engine(cp, p["name"], p["text"], tmp)
            if rep is None:
                ck("%s runs in the engine" % p["name"], False, sess); continue
            probs = [ln for ln in rep.split("\n") if "⚠ spec:" in ln]
            ck("%s parses with no problem line" % p["name"], not probs, probs[:3])
            head = re.search(r"seed (\d+), window \d+ ops, (\d+) phase\(s\), (\d+) model\(s\), (\d+) hypothesis", rep)
            seed = directives(p["text"], "seed")
            want = (seed[0][0] if seed else "42", str(len(directives(p["text"], "phase"))),
                    str(len(directives(p["text"], "model"))), str(len(directives(p["text"], "expect"))))
            ck("%s: the engine counts the seed, phases, models and expectations the text carries %s" % (p["name"], want),
               head is not None and head.groups() == want, head.groups() if head else rep[:200])
            hyp = sess.get("hypotheses") or []
            ck("%s: every expect: line is graded, in order" % p["name"],
               [h["expr"] for h in hyp] == [b_ for b_, _ in directives(p["text"], "expect")],
               [h["expr"] for h in hyp])
            refuted = [h["expr"] for h in hyp if h["verdict"] == "REFUTED"]
            wrong = [b_ for b_, c in directives(p["text"], "expect") if "deliberately wrong" in c]
            ck("%s: the line marked deliberately wrong is refuted, and the rest grade as recorded (%d of %d confirmed)"
               % (p["name"], len(hyp) - len(refuted), len(hyp)),
               all(w in refuted for w in wrong) and
               sorted(set(refuted) - set(wrong)) == sorted(KNOWN_REFUTED.get(p["name"], [])), refuted)
            ck("%s: the notes reach the field notebook, the datasets and crosses the bench (%d note(s), %d dataset(s), %d cross(es))"
               % (p["name"], len(directives(p["text"], "note")), len(directives(p["text"], "data")), len(directives(p["text"], "cross"))),
               len(sess.get("notes") or []) == len(directives(p["text"], "note"))
               and len(sess.get("entered") or []) == len(directives(p["text"], "data"))
               and len(sess.get("crosses") or []) == len(directives(p["text"], "cross")),
               (len(sess.get("notes") or []), len(sess.get("entered") or []), len(sess.get("crosses") or [])))
        ck("no protocol carries a refuted prediction the page did not call wrong: the library's own predictions all hold",
           KNOWN_REFUTED == {}, KNOWN_REFUTED)
        ck("the two-pond and activity-budget protocols grade against the bands the data sits in (ADR-178)",
           any("evenness(pondA) is moderate" in p["text"] and "turnover(pondA, pondB) is moderate" in p["text"] for p in protos)
           and any("evenness(morning) is very-even" in p["text"] and "brayCurtis(morning, afternoon) > 0.2" in p["text"] for p in protos),
           [p["name"] for p in protos])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ---- C. the task holds the first protocol ----
task = json.load(io.open(TASK, encoding="utf-8")) if os.path.isfile(TASK) else {"steps": []}
steps = dict((s["id"], s) for s in task["steps"])
ck("the task holds the first Copy to the meadow protocol's text, as one clipboard payload and nothing else",
   bool(protos) and steps.get("g177-eco", {}).get("expect", {}).get("output.payloads.0.text") == protos[0]["text"]
   and steps.get("g177-eco", {}).get("expect", {}).get("output.payloads.0.k") == "clipboard"
   and steps.get("g177-eco", {}).get("expect", {}).get("output.payloads.1") == {"op": "exists", "value": False},
   steps.get("g177-eco"))
ck("...read right after the press it holds", [s["id"] for s in task["steps"]][:4] == ["look", "outline", "copy", "g177-eco"],
   [s["id"] for s in task["steps"]])
ck("the task holds the second Copy to the two-pond protocol's text -- the one ADR-178 rewrote -- whole",
   len(protos) > 1 and steps.get("g178-eco2", {}).get("expect", {}).get("output.payloads.0.text") == protos[1]["text"]
   and steps.get("g178-eco2", {}).get("expect", {}).get("output.payloads.1") == {"op": "exists", "value": False},
   steps.get("g178-eco2"))

ck("zero console/page errors", not errors, errors[:3])
print("%d/%d%s" % (ok, ok + bad, ("  (%d skipped)" % len(SKIP)) if SKIP else ""))
sys.exit(0 if bad == 0 else 1)
