# -*- coding: utf-8 -*-
"""Mutation testing for the publish pipeline and its reach (ADR-138).

verify_publish_reach now says three things: the document skeleton is stripped
and NOTHING else is; every artifact this kit publishes is mapped, attributed
and measured at its URL; and a page whose bytes were merely handed to a
publisher does not read as one that was looked at. Same rule as every suite
here -- break the pipeline on purpose and require the suite to notice.

The subject is three files, because the claim spans three: `publish.py` makes
the bytes, `publish_state.py` records the evidence, `publish_reach.py` decides
what is still owed. A mutant lives in whichever one carries its anchor.

    python3 tools/mutate_publish.py           # run every mutant
    python3 tools/mutate_publish.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("publish.py", "publish_state.py", "publish_reach.py")

MUTANTS = [
    # ---- the strip that ate a page ----
    ("the shell patterns go back to what they were for four months",
     r"""SHELL = (r'<!doctype[^<>]*>\s*', r'</?html\b[^<>]*>\s*', r'</?head\b[^<>]*>\s*',
         r'</?body\b[^<>]*>\s*')""",
     r"""SHELL = (r'<!doctype[^>]*>\s*', r'</?html[^>]*>\s*', r'</?head[^>]*>\s*', r'</?body[^>]*>\s*')""",
     "a JS comparison that reads like a tag survives"),
    ("the tag names lose their word boundary, so <header> is a <head>",
     r"""r'</?head\b[^<>]*>\s*',""",
     r"""r'</?head[^<>]*>\s*',""",
     "a <header> element survives the shell strip"),
    ("the strip trusts its patterns instead of counting what they removed",
     """    gone = before - html.count("<")
    if gone != tags:""",
     """    gone = before - html.count("<")
    if False:""",
     "REFUSED, not published"),
    ("the guard counts tags but not the '<' they took with them",
     """    gone = before - html.count("<")""",
     """    gone = tags""",
     "REFUSED, not published"),
    ("the skeleton is left in the published bytes",
     """    for pat in SHELL:
        html, n = re.subn(pat, "", html, flags=re.I)""",
     """    for pat in []:
        html, n = re.subn(pat, "", html, flags=re.I)""",
     "the skeleton itself is still removed"),
    # ---- what is mapped ----
    ("artifacts that are not docs pages are not artifacts",
     """    for name, spec in sorted((m.get("others") or {}).items()):
        out[name] = (spec["artifact"], os.path.join(PS.BUILD, name))""",
     """    for name, spec in []:
        out[name] = (spec["artifact"], os.path.join(PS.BUILD, name))""",
     "the Harness Board included"),
    ("publish.py builds the docs pages and leaves the board out",
     """    for name, src in sorted(others().items()):""",
     """    for name, src in []:""",
     "every mapped artifact has bytes in build/publish"),
    # ---- the two stamps are not one stamp ----
    ("a page handed to a publisher counts as one that was measured",
     """            out[name] = ("measured" if PS.entry_via(entry) == "read" else "stamped"), entry""",
     """            out[name] = "measured", entry""",
     "never as measured"),
    ("...and one that was measured counts as merely stamped",
     """            out[name] = ("measured" if PS.entry_via(entry) == "read" else "stamped"), entry""",
     """            out[name] = "stamped", entry""",
     "reads as measured"),
    ("a URL known to be serving other bytes is only a hole, not a failure",
     """        elif kind in ("behind", "measured-behind"):
            out[name] = ("behind", entry)""",
     """        elif kind in ("behind", "measured-behind"):
            out[name] = ("unknown", None)""",
     "a stamp that does not match the bytes that would be published now is BEHIND"),
    # ---- attribution and sweeping ----
    ("a copy is offered to the first page whose id it merely resembles",
     """    return hits[0] if len(hits) == 1 else None""",
     """    return hits[0] if hits else None""",
     "a copy whose id prefix fits two artifacts is attributed to neither"),
    ("a copy that names no artifact is attributed to a page anyway",
     """    m = COPY_OF.search(os.path.basename(copy_path))
    if not m:
        return None""",
     """    m = COPY_OF.search(os.path.basename(copy_path))
    if not m:
        return sorted(art)[0]""",
     "attributed to nothing"),
    ("sweeping keeps the FIRST copy of a page it happens to see",
     """        if name not in done or (at or 0) > done[name][1]:""",
     """        if name not in done:""",
     "takes the newer VERSION"),
    ("sweeping dates a copy by its mtime, the way ADR-078 was wrong before",
     """        at, _how = PS.copy_taken_at(c, io.open(c, encoding="utf-8", errors="replace").read(), told)""",
     """        at = os.path.getmtime(c)""",
     "takes the newer VERSION"),
    ("the plan says nothing is owed",
     """    return [(n, art[n][0], art[n][1]) for n in sorted(r)
            if r[n][0] != "measured"]""",
     """    return []""",
     "--plan names exactly the artifacts that are not measured"),
]


MUTANTS += [
    # ---- ADR-140: dating a copy the reader just fetched ----
    ('a reported fetch time overrides the version marker in the bytes',
     '    if told:\n        return int(told), "the fetch time the reader reported -- about the fetch, not about the version"',
     '    if False:\n        return int(told), "the fetch time the reader reported -- about the fetch, not about the version"',
     'a reader that says when it fetched dates the copy'),
    ('a reported fetch time is passed off as the version',
     '        return int(told), "the fetch time the reader reported -- about the fetch, not about the version"',
     '        return int(told), "the version marker in the copy"',
     'stated as being about the FETCH'),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutpub_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        # The subject BUILDS the kit's pages, so the mutant needs the kit's
        # pages -- a copied tools/ with no docs/ beside it makes every mutant
        # die of "there are pages to check: 0", which is the suite falling over
        # rather than noticing anything. docs/ is linked (read-only in effect:
        # publish.py only reads it) and build/ is left to be regenerated inside
        # the temp tree, so a mutant's bad bytes never touch the real one.
        os.symlink(os.path.join(ROOT, "docs"), os.path.join(tmp, "docs"))
        path = None
        for cand in SUBJECT:
            p2 = os.path.join(dst, cand)
            if io.open(p2, encoding="utf-8").read().count(find) == 1:
                path = p2
                break
        if path is None:
            n = sum(io.open(os.path.join(dst, c), encoding="utf-8").read().count(find)
                    for c in SUBJECT)
            return ("BAD MUTANT", "anchor matched %d times across the subject -- the mutation never applied" % n)
        src = io.open(path, encoding="utf-8").read()
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        suite = os.path.join(dst, "verify", "verify_publish_reach.py")
        p = subprocess.run([sys.executable, suite], capture_output=True, text=True, timeout=900)
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        # A NOT VERIFIED line here is an artifact nobody has measured yet, which
        # is a hole in the EVIDENCE and not a suite that could not run: every
        # clause these mutants touch is asserted on fixtures and on the build
        # output, both of which are present. So, unlike the other runners, this
        # one does not treat it as inconclusive -- it would make the runner
        # unusable for exactly as long as one artifact is unmeasured, which is
        # the state ADR-138 exists to shrink and cannot promise is empty.
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
            print("  %-58s must be killed by  %s" % (n, e))
        return 0
    print("mutation testing the publish pipeline against verify_publish_reach -- %d mutant(s), "
          "%d known equivalent\n" % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-58s %s" % (verdict, name, detail[:58]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    import mutant_ledger
    mutant_ledger.record("mutate_publish", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
