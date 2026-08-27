# -*- coding: utf-8 -*-
"""The sweep's progress number, and whether anything can check it.

WHY THIS EXISTS

For seven slices "how far has the mutation sweep got" was answered by a
sentence at the bottom of an ADR, carried forward by hand from the previous
one. It drifted: greenhouse.html was swept in ADR-063 and again in ADR-064, and
both ADRs added it to the running total, so from ADR-064 onward the figure was
one too high -- 19 pages where the truth was 18, and 20 to go where the truth
was 21. Nothing could have caught it, because the number had no source.

tools/sweep_ledger.py computes it now, from a row-per-run ledger and the docs/
glob. This suite is what stops the computation from becoming the new unchecked
sentence. It asserts, in order:

  1. the ledger describes pages that exist;
  2. the arithmetic closes -- swept plus remaining is every page, exactly once;
  3. the classifier is not vacuous (its first version returned the same value
     for all twenty-one remaining pages, which is not a classification);
  4. "loader-only" means what it says, measured against the same LOADER bytes
     the offline suite uses;
  5. the printed report and the functions agree, so a future edit cannot make
     the text say one thing while the data says another (ADR-039);
  6. append() adds a row without disturbing the others -- run against a
     throwaway copy, never the real ledger.

Run:  python3 tools/verify/verify_sweep_ledger.py
"""
import io, json, os, re, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import _kit
import sweep_ledger as SL
import mutate as MU

P, F = [], []
def ck(n, c, e=""):
    (P if c else F).append(n + (("  << " + str(e)) if (e and not c) else ""))


# ---- 1. the rows describe real pages ------------------------------------
rows = SL.records()
ck("the ledger has rows", len(rows) > 10, len(rows))
allp = set(SL.all_pages())
ghosts = sorted({r["page"] for r in rows if r["page"] not in allp})
ck("every row names a page that is in docs/", not ghosts, ghosts)
ck("every row names the ADR that reported it",
   all(re.fullmatch(r"ADR-\d{3}", r.get("adr", "")) for r in rows),
   [r for r in rows if not re.fullmatch(r"ADR-\d{3}", r.get("adr", ""))][:2])
ck("every row says whether it was written by the tool or backfilled by hand",
   all(r.get("source") in ("tool", "backfilled") for r in rows),
   [r.get("source") for r in rows if r.get("source") not in ("tool", "backfilled")][:3])

# The re-sweep that caused the drift is still IN the ledger as two rows. A
# ledger that deduplicated on the way in would have hidden the event whose
# absence caused the miscount, so the duplicate is asserted, not tolerated.
_dupes = [p for p in {r["page"] for r in rows}
          if sum(1 for r in rows if r["page"] == p) > 1]
ck("pages swept more than once keep one row per run", bool(_dupes), _dupes)

# ---- 2. the arithmetic closes -------------------------------------------
swept, left = SL.swept_pages(), SL.remaining()
ck("swept and remaining partition docs/ exactly",
   sorted(swept + left) == sorted(allp), (len(swept), len(left), len(allp)))
ck("and they do not overlap", not (set(swept) & set(left)), sorted(set(swept) & set(left)))
ck("swept is the DISTINCT pages, not the row count",
   len(swept) == len({r["page"] for r in rows}) and len(swept) < len(rows),
   (len(swept), len(rows)))

# ---- 3. the classifier separates something ------------------------------
# ADR-039, learned the hard way twenty minutes before this file was written:
# the first classify() called all twenty-one remaining pages "ready", because
# every page carries the webfont loader and so every page has a mutant.
kinds = {p: SL.classify(p) for p in left}
# Not "more than one value across what is LEFT". That is how this check was
# written, and it failed the day the twelve loader-only pages were swept and
# the backlog became homogeneous -- a check firing on correct work, which is
# the failure this kit keeps catching in its own instruments.
#
# The classifier is asked to tell two NAMED pages apart instead. That is what
# non-vacuous means for a classifier, and it stays true when the backlog is
# empty.
ck("the classifier tells a page with code of its own from a loader-only one",
   SL.classify("selection-log.html") == "own-code"
   and SL.classify("ecology-essay.html") == "loader-only",
   (SL.classify("selection-log.html"), SL.classify("ecology-essay.html")))
ck("every value it returns is one of the four it documents",
   set(kinds.values()) <= {"own-code", "no-suite", "loader-only", "prose"},
   sorted(set(kinds.values())))

# ---- 4. loader-only means loader-only -----------------------------------
# Measured, not asserted from the label: for each page called loader-only,
# EVERY mutant the sweep would generate has to fall inside the loader span --
# and the loader is _kit.LOADER, the same pattern verify_offline_slice reads.
for name in [p for p, k in kinds.items() if k == "loader-only"][:4]:
    src = io.open(os.path.join(SL.DOCS, name), encoding="utf-8").read()
    spans = [(m.start(), m.end()) for m in _kit.LOADER.finditer(src)]
    _s, muts = MU.mutants_for(os.path.join(SL.DOCS, name), 999)
    outside = [m["line"] for m in muts
               if not any(a <= m["at"] < b for a, b in spans)]
    ck("%s really has no mutable code outside the shared loader" % name,
       bool(muts) and not outside, outside[:4])
# And the opposite, so the bucket is not just always true: a page with its own
# code must NOT land there.
ck("a page with real code of its own is not called loader-only",
   SL.classify("selection-log.html") == "own-code", SL.classify("selection-log.html"))

# ---- 4b. "39 of 39" is a sample, and has to say so ----------------------
# The headline number reads as coverage. It is not: a swept page was swept at
# four to eight mutants, and the kit has thousands. The status block carries
# both figures now, and this asserts they are the ones the functions compute --
# because a denominator that drifts from its numerator is how "19 swept, 20 to
# go" happened in the first place.
_run, _counted = SL.mutants_run()
_avail = SL.mutants_available()
ck("some rows record what they ran, so the sample size is knowable",
   _counted > 10 and _run > 0, (_counted, _run))
ck("the sample is a small fraction of the mutants that exist -- and is not claimed otherwise",
   0 < _run < sum(_avail.values()), (_run, sum(_avail.values())))
ck("every page contributes mutants to the denominator",
   all(v > 0 for v in _avail.values()),
   sorted(k for k, v in _avail.items() if v == 0))

# ---- 5. the report and the data cannot drift ----------------------------
text = "\n".join(SL.status_lines())
m = re.search(r"(\d+) of (\d+) page\(s\) swept, (\d+) to go", text)
ck("the status line reports the same numbers the functions compute",
   bool(m) and (int(m.group(1)), int(m.group(2)), int(m.group(3)))
   == (len(swept), len(allp), len(left)),
   m.groups() if m else text[:120])
_m3 = re.search(r"at least (\d+) mutant\(s\) run", text)
ck("the status block reports the sample size the function computes",
   bool(_m3) and int(_m3.group(1)) == _run, (_m3.group(1) if _m3 else None, _run))
_m4 = re.search(r"(\d+) mutant\(s\) exist", text)
ck("and the denominator it computes",
   bool(_m4) and int(_m4.group(1)) == sum(_avail.values()),
   (_m4.group(1) if _m4 else None, sum(_avail.values())))
m2 = re.search(r"(\d+) with code of their own, (\d+) with no suite, "
               r"(\d+) loader-only, (\d+) prose", text)
ck("and the same bucket sizes",
   bool(m2) and [int(g) for g in m2.groups()]
   == [sum(1 for v in kinds.values() if v == k)
       for k in ("own-code", "no-suite", "loader-only", "prose")],
   m2.groups() if m2 else text[:200])
for name in left:
    ck("%s is listed as not yet swept" % name, name in text, "")

# ---- 6. append() is safe to run --------------------------------------
# Against a copy. A suite that appends to the real ledger would inflate the
# very number it exists to protect, one row per run.
tmp = tempfile.mkdtemp(prefix="ledger-")
try:
    fake = os.path.join(tmp, "sweep_ledger.json")
    shutil.copyfile(SL.LEDGER, fake)
    real, SL.LEDGER = SL.LEDGER, fake
    before = len(SL.records())
    SL.append("food-web.html", "ADR-999", killed=3, survived=1, fresh=0)
    after = SL.records()
    ck("append adds exactly one row", len(after) == before + 1, (before, len(after)))
    ck("and leaves every earlier row untouched",
       after[:before] == json.load(io.open(fake, encoding="utf-8"))["records"][:before]
       and after[before]["adr"] == "ADR-999", after[-1])
    ck("a tool-written row is marked as such", after[-1]["source"] == "tool", after[-1])
    ck("and carries what the run measured",
       (after[-1].get("killed"), after[-1].get("survived")) == (3, 1), after[-1])
finally:
    SL.LEDGER = real
    shutil.rmtree(tmp, ignore_errors=True)
ck("the real ledger was not written to",
   len(SL.records()) == len(rows), (len(SL.records()), len(rows)))

print("PASS %d" % len(P))
for x in F: print("FAIL:", x)
print("-" * 70)
print("%d/%d" % (len(P), len(P) + len(F)))
sys.exit(1 if F else 0)
