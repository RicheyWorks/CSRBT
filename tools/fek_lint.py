# -*- coding: utf-8 -*-
"""Source-level lint for FEK consumers.

Catches the one mistake the component cannot catch for itself: passing
`nullable:true` together with an explicit `value:0`. That combination is
legal and means "a recorded zero", so FEK must honour it — but it is almost
never what the author meant when they also asked for nullable, and the
failure is silent. It bit me twice (Cell Bench, Field Season) before this
existed.
"""
import glob, os, re, sys, io

# THE PATH WAS THE POLISH LOOP'S CLONE, NOT THIS CHECKOUT (ADR-106)
#
# This read DOCS = "/tmp/eco/CSRBT/docs/" -- the directory the autonomous
# polish job clones into, which exists in exactly one container and nowhere
# else. Everywhere else glob returned [], the page loop never ran, and the
# audit printed a clean bill of health having examined ZERO pages. It has
# been green on Richmond's machine on that basis, and that green was counted
# in the kit's headline numbers.
#
# Two changes, and the second matters more than the first: the path now comes
# from this file's own location, so the audit reads the checkout it was run
# from; and finding no pages is now a LOUD FAILURE rather than a clean result,
# because the next hardcoded path will fail the same silent way and "I looked
# at nothing" must never again render as "nothing is wrong".
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs") + os.sep
issues = []
consumers = []

_pages = sorted(glob.glob(DOCS + "*.html"))
if not _pages:
    print("NO PAGES FOUND under %s -- refusing to report a clean lint of nothing" % DOCS)
    sys.exit(2)

for path in _pages:
    src = io.open(path, encoding="utf-8").read()
    if "FEK = (function" not in src:
        continue
    name = os.path.basename(path)
    consumers.append(name)

    # every FEK.<ctor>({ ... }) call site, brace-matched
    for m in re.finditer(r'FEK\.(step|field|slider|dial|chips|picker)\s*\(\s*\{', src):
        i = m.end() - 1
        depth = 0
        for j in range(i, min(i + 4000, len(src))):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    break
        body = src[i:j + 1]
        ctor = m.group(1)
        line = src.count("\n", 0, m.start()) + 1

        if ctor in ("step", "slider"):
            nullable = re.search(r'\bnullable\s*:\s*true', body)
            zero = re.search(r'\bvalue\s*:\s*0\b', body)
            if nullable and zero:
                issues.append((name, line, ctor,
                    "nullable:true with an explicit value:0 — that is a RECORDED zero, "
                    "not an empty control. Drop `value` to start empty."))
            # `start` is a stepper concept: a slider has no "first tap", you drag
            # it to a position and that position is the value.
            if ctor == "step" and nullable and not re.search(r'\bstart\s*:', body):
                issues.append((name, line, ctor,
                    "nullable:true without `start` — the first tap will land on 0, "
                    "which is rarely the value the user meant."))

        # a field is nullable by nature; a stepper on a 3-decimal step is the
        # wrong control per the kit's own rule
        if ctor == "step":
            st = re.search(r'\bstep\s*:\s*([0-9.]+)', body)
            if st and float(st.group(1)) < 0.01:
                issues.append((name, line, ctor,
                    "stepper with a step below 0.01 — use FEK.field for a value "
                    "read off an instrument."))

print("FEK consumers scanned: %d" % len(consumers))
for c in consumers:
    print("  " + c)
print()
if issues:
    for name, line, ctor, msg in issues:
        print("LINT %s:%d  FEK.%s  %s" % (name, line, ctor, msg))
    print()
    print("%d issue(s)" % len(issues))
    sys.exit(1)
print("clean — no FEK misconfiguration found")
