# -*- coding: utf-8 -*-
"""Rewrite the cross-page rail in every page that carries one.

    python3 tools/nav_emit.py           # rewrite
    python3 tools/nav_emit.py --check   # report drift, write nothing

Only pages that ALREADY have a `<div class="rail">` are touched. Adding a rail
to a page that never had one is a design decision, not a regeneration, so this
refuses to make it: it lists such pages instead.
"""
import glob, importlib.util, io, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")
_spec = importlib.util.spec_from_file_location("nav", os.path.join(ROOT, "tools", "nav.py"))
nav = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(nav)

def rail_span(src):
    """Where the rail block starts and ends, including anything a previous
    broken run orphaned after it.

    Three attempts, and the first two are the lesson. A non-greedy match to the
    first indented </div> ended at the close of the first .chips group, so every
    run replaced a fifth of the rail and left the other four fifths behind as an
    orphan with no wrapping div -- five times over before verify_emitters.py
    caught it. Depth counting fixed the boundary but not the debris.

    So the scan is line-based and depth-aware: from the rail's opening line,
    consume while nested, and at depth zero keep consuming any line that is
    itself rail content -- which is exactly what an orphaned tail is. A line
    that is neither ends the span. The enclosing </div> of the page shell is
    never rail content, so it survives.
    """
    lines = src.split("\n")
    first = None
    for i, l in enumerate(lines):
        if '<div class="rail">' in l:
            first = i
            break
    if first is None:
        return None
    RAIL_LINE = ('<p class="rl"', '<div class="chips"', '<div class="rail">')

    def rail_follows(j):
        """Is the next thing with content part of a rail? A truncated run can
        leave a stray closing </div> at depth zero ahead of its orphan, and
        stopping at that stray leaves the orphan behind."""
        while j < len(lines) and not lines[j].strip():
            j += 1
        return j < len(lines) and lines[j].strip().startswith(RAIL_LINE)

    depth, i = 0, first
    last = first
    while i < len(lines):
        l = lines[i]
        stripped = l.strip()
        if depth == 0 and i > first and not stripped.startswith(RAIL_LINE):
            if not (stripped == "</div>" and rail_follows(i + 1)):
                break
        # Clamp at zero. A stray closer left by a truncated run is deliberately
        # consumed above, and letting it take the depth negative made the scan
        # give up on exactly the pages it was written to repair.
        depth = max(0, depth + l.count("<div") - l.count("</div>"))
        last = i
        i += 1
    start = sum(len(x) + 1 for x in lines[:first])
    end = sum(len(x) + 1 for x in lines[:last + 1])
    return start, end


def main(argv):
    check = "--check" in argv
    changed, clean, missing = [], [], []
    known = set(nav.hrefs())
    for path in sorted(glob.glob(os.path.join(DOCS, "*.html"))):
        name = os.path.basename(path)
        src = io.open(path, encoding="utf-8").read()
        span = rail_span(src)
        if not span:
            if name in known:
                missing.append(name)
            continue
        indent = re.match(r"[ \t]*", src[span[0]:]).group(0)
        block = nav.rail(name if name in known else None)
        block = "\n".join((indent + l if l else l) for l in block.split("\n")) + "\n"
        out = src[:span[0]] + block + src[span[1]:]
        (clean if out == src else changed).append(name)
        if out != src and not check:
            io.open(path, "w", encoding="utf-8").write(out)

    # The banner used to say "3 references" flatly, which stopped being true the
    # day pages could carry a fourth of their own. A banner that misdescribes the
    # thing it introduces is a small lie in a place people trust.
    print("kit rail v%s -- %d chips in %d groups, %d shared references"
          " + a suite link on %d page(s)"
          % (nav.VERSION, sum(len(c) for _, c in nav.GROUPS), len(nav.GROUPS),
             len(nav.REFS), len(nav.UP)))
    print("-" * 64)
    for n in changed:
        print("%-28s %s" % (n, "would be rewritten" if check else "rewritten"))
    print("%-28s %d already current" % ("", len(clean)))
    if missing:
        print("-" * 64)
        print("in the rail but carrying none of their own (decide, do not regenerate):")
        for n in missing:
            print("  %s" % n)
    print("-" * 64)
    print("%d page(s) %s" % (len(changed), "would change" if check else "rewritten"))
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
