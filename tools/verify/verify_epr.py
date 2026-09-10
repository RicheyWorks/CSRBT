# -*- coding: utf-8 -*-
"""Suite for docs/eco-protocol-reference.html -- the .eco grammar, as the page states it (ADR-179).

The reference is the page a reader writes a protocol FROM. It names the
directives, the phase shapes, the factors, the models and their argument order,
the expect: metrics, operators and qualitative bands. Nothing held any of it to
the grammar it describes, and ADR-178 found the bands wrong (`even / uneven`
where the engine says very-even / moderate / uneven / dominated), a metric that
does not exist (`dispersion`), an operator the engine refuses (`=`), three
models missing from the table, and the page's own header example refused by
the parser (three directives on one line). This suite holds the page to the
parser's SOURCE -- ExperimentSpec.java, read here, no build needed -- and,
where the engine is built, runs the page's own examples through it.

  A. the grammar, read from ExperimentSpec.java: quantitative metrics and their
     arity, the operators, the qualitative metrics and every band word, the
     models and their parameter counts, the phase shapes, the factors, the
     directives.
  B. the page says exactly that: every metric, operator, band, model, phase
     shape and factor the page names is one the engine accepts, and every one
     the engine accepts is on the page; the model table's argument count
     matches the parser's; every directive the engine parses has a section.
  C. the page's examples run: each keyword section's example is accepted with
     no spec problem where it stands alone, and the examples assembled in page
     order are one protocol the engine accepts -- zero problem lines, every
     expect: graded, the line marked deliberately wrong the one refuted.
     Skipped and said so where the engine is not built.
  D. the lab's importer reads the assembled protocol with zero problems.

Run:  python3 tools/verify/verify_epr.py
"""
# Declared for tools/mutate.py. This suite uses a temp dir for the engine's
# session and export bundle; it builds no fixture pages -- every assertion is
# about docs/eco-protocol-reference.html itself.
MUTATE_ROLE = "subject"
import html, io, json, os, re, subprocess, sys, tempfile, shutil
from html.parser import HTMLParser
from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PAGE = os.path.join(ROOT, "docs", "eco-protocol-reference.html")
LAB = "file://" + os.path.join(ROOT, "docs", "ecology-lab.html").replace(os.sep, "/")
SPEC_JAVA = os.path.join(ROOT, "csrbt-experimental", "src", "main", "java", "io", "github", "richeyworks",
                         "csrbt", "experimental", "ecology", "ExperimentSpec.java")
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


# ---- A. the grammar, from the parser's source ---------------------------------
JAVA = io.open(SPEC_JAVA, encoding="utf-8").read()

def cases(block, arrow_value=r"\d+"):
    """`case "a", "b" -> N;` lines in a block -> {name: N}."""
    out = {}
    for names, val in re.findall(r'case ((?:"[a-z0-9]+"(?:,\s*)?)+)\s*->\s*(%s)' % arrow_value, block):
        for n in re.findall(r'"([a-z0-9]+)"', names):
            out[n] = int(val) if val.isdigit() else val
    return out

def block(start_pat, end_pat):
    m = re.search(start_pat, JAVA); assert m, start_pat
    e = re.search(end_pat, JAVA[m.end():]); assert e, end_pat
    return JAVA[m.end():m.end() + e.start()]

QUANT = cases(block(r"int wantArgs = switch \(metric\) \{", r"default ->"))                # metric -> arity
Q_OPS = re.findall(r'op\.equals\("([<>=]+)"\)', block(r"String op = tail\[0\];", r"int wantArgs"))
QUAL = cases(block(r"private static Expectation parseQualitative", r"default ->"))            # metric -> arity
BANDS = dict((m, re.findall(r'"([a-z0-9-]+)"', ws))
             for m, ws in re.findall(r'case "([a-z]+)" -> List\.of\(([^)]*)\)', block(r"static List<String> wordsFor", r"default ->")))
MODELS = cases(block(r"int want = switch \(kind\) \{", r"default ->"))                        # model -> parameter count
MODELS["eulerlotka"] = None                                                                   # variable-length lx:mx pairs
PHASES = list(cases(block(r"return switch \(p\[1\]\.toLowerCase\(Locale\.ROOT\)\) \{", r"default ->"), arrow_value=r"[^;]*").keys()) \
    if re.search(r"return switch \(p\[1\]\.toLowerCase\(Locale\.ROOT\)\) \{", JAVA) else \
    re.findall(r'case "([a-z]+)" -> (?:new Phase|\{)', block(r"private static Phase parsePhase", r"private static"))
FACTORS = re.findall(r'case "([a-z]+)" -> (?:area|temperature|wind|distance) = fv', JAVA)
DIRECTIVES = sorted(set(re.findall(r'case "([a-z]+)" -> (?:name|keys|seed|window|phases|models|crosses|expectations|datasets|dwcSources|trees)\b', JAVA)) | {"note", "factor"})

ck("the parser's source was read: %d quantitative metrics, %d qualitative, %d models, %d phase shapes, %d factors, %d directives"
   % (len(QUANT), len(QUAL), len(MODELS), len(PHASES), len(FACTORS), len(DIRECTIVES)),
   len(QUANT) >= 8 and len(QUAL) == 5 and len(MODELS) >= 9 and len(PHASES) == 3 and len(FACTORS) == 4 and len(DIRECTIVES) >= 12,
   (QUANT, QUAL, MODELS, PHASES, FACTORS, DIRECTIVES))
ck("every qualitative metric has its band words in the source", sorted(BANDS) == sorted(QUAL), (BANDS, QUAL))
ck("the operators are exactly < > <= >=", sorted(Q_OPS) == ["<", "<=", ">", ">="], Q_OPS)

# ---- B. the page says exactly that ---------------------------------------------
SRC = io.open(PAGE, encoding="utf-8").read()
def section(sid):
    m = re.search(r'<section class="kw" id="%s">(.*?)</section>' % sid, SRC, re.S); return m.group(1) if m else ""
def codes(text):
    return [html.unescape(c).strip() for c in re.findall(r"<code>(.*?)</code>", text, re.S)]
class _Text(HTMLParser):
    """The text a fragment shows, markup resolved, whitespace kept -- a <pre>
    example is read line by line, so nothing here collapses it. A parser, not
    a bracket regex (ADR-099: a regex pairs the bare < and > in a page's
    script and eats prose between them)."""
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True); self.out = []
    def handle_data(self, d):
        self.out.append(d)
def text(fragment):
    t = _Text(); t.feed(fragment); t.close(); return "".join(t.out)

EXPECT = section("expect")
ck("the page has a section for every directive the engine parses (name/keys/seed/window under header)",
   all(('id="%s"' % d) in SRC for d in DIRECTIVES if d not in ("name", "keys", "seed", "window", "dwc")) and 'id="header"' in SRC
   and all(("<code>%s:</code>" % d) in section("header") for d in ("name", "keys", "seed", "window")),
   [d for d in DIRECTIVES if ('id="%s"' % d) not in SRC])

# quantitative metrics: the ones the page lists, lowercased, are the parser's -- both ways
quant_para = re.search(r"<p[^>]*><b>Quantitative metrics</b>(.*?)</p>", EXPECT, re.S)
page_quant = [c.lower() for c in codes(quant_para.group(1)) if re.match(r"^[A-Za-z0-9]+$", c)] if quant_para else []
ck("the quantitative metrics the page names are exactly the parser's (%s)" % ", ".join(sorted(QUANT)),
   sorted(page_quant) == sorted(QUANT), (sorted(page_quant), sorted(QUANT)))
ck("...one-scope metrics listed before the pairwise ones, and the page says which take two",
   quant_para is not None and "pairwise" in text(quant_para.group(0)) and
   all(page_quant.index(m) < min(page_quant.index(p) for p in QUANT if QUANT[p] == 2) for m in QUANT if QUANT[m] == 1),
   page_quant)
# the operator list stops where the page says which operator is ABSENT -- that mention is not an offer
page_ops = [c for c in codes(quant_para.group(1).split("there is")[0]) if re.match(r"^[<>=]+$", c)] if quant_para else []
ck("the operators the page lists are exactly the parser's, and = is named as absent",
   sorted(page_ops) == sorted(Q_OPS) and "no <code>=</code>" in (quant_para.group(1) if quant_para else ""), page_ops)
form_row = re.search(r"<td>Quantitative</td><td>(.*?)</td>", EXPECT, re.S)
ck("the form row's operator list is the same four", form_row is not None and
   sorted(text(form_row.group(1)).split("metric(scope)")[1].split("value")[0].split()) == sorted(Q_OPS),
   text(form_row.group(1)) if form_row else None)

# qualitative bands: `metric(...) is a|b|c` per metric, the words exactly the parser's
qual_para = re.search(r"<p><b>Qualitative bands</b>(.*?)</p>", EXPECT, re.S)
page_bands = {}
for c in codes(qual_para.group(1)) if qual_para else []:
    m = re.match(r"^([a-z]+)(?:\([^)]*\))? is ([a-z0-9|-]+)$", c)
    if m: page_bands[m.group(1)] = m.group(2).split("|")
ck("the qualitative metrics the page names are exactly the parser's (%s)" % ", ".join(sorted(QUAL)),
   sorted(page_bands) == sorted(QUAL), (sorted(page_bands), sorted(QUAL)))
for m in sorted(QUAL):
    ck("%s's bands on the page are the parser's words, in the parser's order: %s" % (m, "|".join(BANDS.get(m, []))),
       page_bands.get(m) == BANDS.get(m), page_bands.get(m))
ck("the page's band forms carry the parser's arity: two scopes for turnover and overlap, one for evenness and fit, none for survivorship",
   all(("%s(a, b) is" % m) in qual_para.group(1) for m in QUAL if QUAL[m] == 2)
   and all(("%s(scope) is" % m) in qual_para.group(1) for m in QUAL if QUAL[m] == 1)
   and "survivorship is" in qual_para.group(1) and "survivorship(" not in qual_para.group(1), qual_para.group(1)[:200] if qual_para else None)
ck("no band word the parser does not know is offered as one (random / regular / clumped, even) -- and no dispersion metric",
   not re.search(r"<code>(random|regular|clumped|even)</code>", EXPECT) and "dispersion</code>" not in EXPECT, EXPECT[:100])

# models: the table's first column is the parser's list, and the argument column counts as the parser does
model_rows = re.findall(r"<tr><td><code>([a-z]+)</code></td><td>(.*?)</td>", section("model"), re.S)
ck("the model table names exactly the models the engine runs (%s)" % ", ".join(sorted(MODELS)),
   sorted(m for m, _ in model_rows) == sorted(MODELS), sorted(m for m, _ in model_rows))
for m, args in model_rows:
    want = MODELS.get(m)
    if want is None:
        ck("%s's arguments are described as lx:mx pairs" % m, "lx:mx" in text(args), text(args))
    else:
        ck("%s's argument column lists %d names, as the parser wants %d parameters" % (m, len(text(args).split()), want),
           len(text(args).split()) == want, text(args))
model_pre = text(re.search(r"<pre>(.*?)</pre>", section("model"), re.S).group(1))
ck("every model in the model example carries the parameter count the parser wants",
   all(MODELS.get(ln.split()[1]) in (None, len(ln.split("#")[0].split()) - 2) for ln in model_pre.split("\n") if ln.startswith("model:")),
   model_pre)

# phases and factors
phase_forms = re.findall(r"<code>phase:</code> &lt;label&gt; <code>([a-z]+)</code>", section("phase"))
ck("the phase table names exactly the parser's shapes (%s)" % ", ".join(PHASES), sorted(phase_forms) == sorted(PHASES), phase_forms)
factor_forms = re.findall(r"<code>factor: ([a-z]+)</code>", section("factor"))
ck("the factor table names exactly the parser's factors (%s)" % ", ".join(sorted(FACTORS)), sorted(factor_forms) == sorted(FACTORS), factor_forms)

# ---- C. the page's examples run --------------------------------------------------
pres = [(sid, text(re.search(r"<pre>(.*?)</pre>", section(sid), re.S).group(1)))
        for sid in ("header", "phase", "factor", "model", "data", "note", "tree", "cross", "expect")]
ck("every keyword section carries an example, and every example line is a directive, a comment or blank",
   len(pres) == 9 and all(re.match(r"^(#|[a-z]+(\([^)]*\))?:)", ln) for _, t in pres for ln in t.split("\n") if ln.strip()),
   [(s, t[:30]) for s, t in pres])
ck("the header example is one directive per line, the way the parser reads it",
   pres[0][1].split("\n")[1:] == ["keys: 100", "seed: 42", "window: 250"] and pres[0][1].startswith("name: "), pres[0][1])
ASSEMBLED = "\n".join(t for _, t in pres)
STANDALONE = ("header", "phase", "factor", "model", "data", "tree", "cross")   # note and expect name the phases above

def classpath():
    cp = os.environ.get("CSRBT_LAB_CLASSPATH")
    if not cp:
        if not os.path.isfile(CP_FILE):
            return None
        cp = io.open(CP_FILE, encoding="utf-8").read().strip()
    return cp if os.path.isdir(cp.split(os.pathsep)[0]) else None

def run_engine(cp, name, body, tmp):
    spec = os.path.join(tmp, name + ".eco")
    io.open(spec, "w", encoding="utf-8", newline="\n").write(body + "\n")
    sess, outd = spec[:-4] + "-session.json", spec[:-4] + "-out"
    p = subprocess.run(["java", "-cp", cp, MAIN, spec, sess, outd],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if p.returncode != 0:
        return None, (p.stderr or p.stdout)[-300:]
    return io.open(os.path.join(outd, "report.txt"), encoding="utf-8").read(), json.load(io.open(sess, encoding="utf-8"))

cp = classpath()
if not cp:
    skip("the engine runs the page's examples", "csrbt-experimental is not built: ./gradlew :csrbt-experimental:harnessClasspath")
else:
    tmp = tempfile.mkdtemp(prefix="epr_")
    try:
        for sid, t in pres:
            if sid not in STANDALONE:
                continue
            rep, sess = run_engine(cp, sid, t, tmp)
            probs = [ln.strip() for ln in (rep or "").split("\n") if "⚠ spec:" in ln]
            ck("the %s example is accepted by the parser on its own" % sid, rep is not None and not probs, probs or sess)
        rep, sess = run_engine(cp, "assembled", ASSEMBLED, tmp)
        probs = [ln.strip() for ln in (rep or "").split("\n") if "⚠" in ln]
        ck("the examples assembled in page order are one protocol the engine accepts: no problem line, nothing ungradeable",
           rep is not None and not probs, probs or sess)
        hyp = (sess or {}).get("hypotheses") or []
        exp_lines = [ln.split("#")[0].split(":", 1)[1].strip() for ln in pres[-1][1].split("\n") if ln.startswith("expect:")]
        ck("every expect: line on the page is graded, in order (%d)" % len(exp_lines), [h["expr"] for h in hyp] == exp_lines, [h["expr"] for h in hyp])
        wrong = [ln.split("#")[0].split(":", 1)[1].strip() for ln in pres[-1][1].split("\n") if "deliberately wrong" in ln]
        ck("the line marked deliberately wrong is the one refuted; every other prediction on the page is confirmed",
           [h["expr"] for h in hyp if h["verdict"] == "REFUTED"] == wrong and len(wrong) == 1, [(h["expr"], h["verdict"]) for h in hyp])
        ck("the survivorship claim is graded, not ungradeable: the churn phase the page says it needs gives it a census",
           any(h["expr"].startswith("survivorship") and h["verdict"] in ("CONFIRMED", "REFUTED") for h in hyp), hyp[-1:] if hyp else None)
        ck("the assembled run carries the page's datasets, notes, trees and crosses",
           len(sess.get("entered") or []) == 3 and len(sess.get("notes") or []) == 3 and len(sess.get("trees") or []) == 1
           and len(sess.get("crosses") or []) == 3, {k: len(sess.get(k) or []) for k in ("entered", "notes", "trees", "crosses")})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ---- D. the lab's importer reads it ------------------------------------------------
errors = []
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1000, "height": 1200})
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort()); pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(LAB, wait_until="domcontentloaded"); pg.wait_for_timeout(600)
    pg.fill("#wb-eco-in", ASSEMBLED); pg.click("#wb-eco-import"); pg.wait_for_timeout(400)
    out = pg.inner_text("#wb-eco-in-out")
    m = re.search(r"Read (\d+) line\(s\): (\d+) loaded into the Workbench, (\d+) read but shown here only, (\d+) problems", out)
    n_dir = sum(1 for ln in ASSEMBLED.split("\n") if ln.strip() and not ln.startswith("#"))
    ck("the lab's importer reads the assembled protocol: every directive line read, zero problems",
       m is not None and int(m.group(1)) == n_dir and int(m.group(4)) == 0, out[:160])
    ck("...and lists each expect: line as read", all(e in out for e in exp_lines) if cp else "expect:" in out, out[-400:])
    b.close()
ck("zero page errors in the lab", not errors, errors[:3])

print("%d/%d%s" % (ok, ok + bad, ("  (%d skipped)" % len(SKIP)) if SKIP else ""))
sys.exit(0 if bad == 0 else 1)
