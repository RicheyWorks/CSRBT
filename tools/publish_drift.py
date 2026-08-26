# -*- coding: utf-8 -*-
"""What a reader of a stale published page would read differently.

publish_state.py answers "is this page behind?" with a hash comparison. That is
the right question and a useless answer on its own: BEHIND is a boolean, and
acting on it means republishing thirty-odd pages at roughly four Read calls each
to satisfy the publish gate. Saying "the rest is cosmetic" without measuring it
is the habit ADR-049 was written about.

WHERE THE EVIDENCE COMES FROM

Fetching a live artifact saves its full HTML to a file. The newest such file per
artifact is a real copy of what that URL served at that moment. This reads them
and fetches nothing.

WHAT IT MEASURES, AND WHY NOT LINES

The first version diffed lines and called any line whose digits changed
"numeric". Every page came back with numeric drift, which was the tell. It was
counting hex colours (#8B8B7B -> #6B6B5E is a contrast fix, not a claim),
artifact UIDs inside new rail links, font weights in a Google Fonts URL, and --
worst -- difflib replace-blocks where an INSERTED line was zipped against ""
and read as a number changing from nothing to something. Twenty-four pages, and
essentially every finding false, which is the same shape as audit_frontend's 26
for 26 before it was deleted.

Numbers live in three places and only two of them can mislead a reader:

  SENTENCE   a number in rendered prose -- "60 g", "the 160 ppm guidance".
             A reader reads this. If it changed, the stale page states
             something the repo no longer states.
  CODE       a numeric literal in a <script> -- a class midpoint, a threshold,
             a coefficient. A reader does not see it; the number it computes
             for them is downstream of it.
  SURFACE    colours, font weights, sizes, coordinates in an SVG path, digits
             inside a URL or an identifier. Presentation. Never a claim.

Sentences are compared as sentences and code as code. Surface is discarded by
construction rather than by a filter, because a filter over line diffs is what
produced the false positives.

WHAT IT WILL NOT CLAIM

A saved copy can predate the live page. This reports a difference between THE
NEWEST COPY ON DISK and the repo, stamps that copy's age on every row, and never
says "the live page is wrong". Where publish_state says a page is CURRENT its
saved copy is superseded and is skipped.

    python3 tools/publish_drift.py --live DIR
    python3 tools/publish_drift.py --live DIR --page food-web.html
"""
import argparse, datetime, difflib, glob, hashlib, importlib.util, io, json, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")

_spec = importlib.util.spec_from_file_location("_pub", os.path.join(ROOT, "tools", "publish.py"))
_pub = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_pub)

BODY = re.compile(r"<!--\s*/frame-runtime\s*-->.*?<body>", re.S)
TAIL = re.compile(r"</body>\s*</html>\s*$")
SAVED = re.compile(r"^artifact-([0-9a-f]{8})-(\d+)-[0-9a-f]+\.html$")

SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)
STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.S | re.I)
COMMENT = re.compile(r"<!--.*?-->", re.S)
TAG = re.compile(r"<[^>]+>")

# A digit a reader could READ AS A QUANTITY. The lookbehind is the whole point
# and it is load-bearing: without it, "see ADR-031", "Field Entry Kit v1.3.0"
# and every "#8B8B7B" in prose become numeric sentences, and a page whose only
# change is a version bump ranks as misstating a figure. A mutation sweep
# deleted this lookbehind and no fixture noticed, which is why there are now
# three.
DIGIT = re.compile(r"(?<![\w#.-])\d")
SENT = re.compile(r"(?<=[.!?;:])\s+|\n")

ENT = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'",
       "&nbsp;": " ", "&mdash;": "-", "&ndash;": "-", "&minus;": "-",
       "&times;": "x", "&divide;": "/", "&radic;": "sqrt", "&plusmn;": "+/-",
       "&frac14;": "1/4", "&deg;": "deg", "&middot;": "-", "&hellip;": "..."}


def unwrap(html):
    m = BODY.search(html)
    if m:
        html = html[m.end():]
    return TAIL.sub("", html).strip()


def sentences(html):
    """Rendered prose, as sentences, with script/style/markup gone."""
    h = COMMENT.sub(" ", html)
    h = SCRIPT.sub(" ", h)
    h = STYLE.sub(" ", h)
    h = TAG.sub(" ", h)
    for k, v in ENT.items():
        h = h.replace(k, v)
    h = re.sub(r"&[a-zA-Z#0-9]+;", " ", h)
    out = []
    for s in SENT.split(h):
        s = " ".join(s.split())
        if s:
            out.append(s)
    return out


# A numeric literal in code: a bare number, not a hex colour, not inside a
# string that looks like a URL or an id, not a CSS length in a style string.
CODE_NUM = re.compile(r"(?<![\w#.$-])(\d+(?:\.\d+)?)(?![\w%-]|px|em|rem|vh|vw)")
URLISH = re.compile(r"https?://\S+|[0-9a-f]{8}-[0-9a-f]{4}-")


def code_lines(html):
    """Script lines paired with the numeric literals they carry."""
    out = []
    for m in SCRIPT.finditer(COMMENT.sub(" ", html)):
        for line in m.group(1).split("\n"):
            # No hex strip here: CODE_NUM's (?<![\w#.$-]) already excludes
            # every digit of a colour -- the first because '#' precedes it, the
            # rest because a hex digit is \w. An explicit strip was written
            # first, was dead code, and a mutation sweep proved it equivalent by
            # deleting it with no fixture noticing. The guarantee is asserted
            # against the lookbehind in verify_publish_drift, where it lives.
            nums = CODE_NUM.findall(URLISH.sub(" ", line))
            if nums:
                out.append((" ".join(line.split()), tuple(nums)))
    return out


def publish_bytes(name):
    src = io.open(os.path.join(DOCS, name), encoding="utf-8").read()
    base, pages = _pub.load()
    return _pub.wire(_pub.strip(src), base, pages)


def newest_saved(live_dir):
    best = {}
    for p in glob.glob(os.path.join(live_dir, "artifact-*.html")):
        m = SAVED.match(os.path.basename(p))
        if not m:
            continue
        uid8, ts = m.group(1), int(m.group(2))
        if uid8 not in best or ts > best[uid8][1]:
            best[uid8] = (p, ts)
    return best


def numeric_sentence_drift(old, new):
    """Sentences carrying a digit that the repo no longer states, or now states.

    Sentences without a digit are ignored entirely -- prose edits are real but
    they are not a reader being told a different NUMBER, and conflating the two
    is how the first version made every page look urgent.
    """
    o = [s for s in sentences(old) if DIGIT.search(s)]
    n = [s for s in sentences(new) if DIGIT.search(s)]
    oset, nset = set(o), set(n)
    gone = [s for s in o if s not in nset]
    came = [s for s in n if s not in oset]
    # Pair each vanished sentence with its closest arrival, so a changed figure
    # reads as one change rather than as a deletion plus an unrelated addition.
    pairs, used = [], set()
    for g in gone:
        best, score = None, 0.0
        for i, c in enumerate(came):
            if i in used:
                continue
            r = difflib.SequenceMatcher(None, g, c).ratio()
            if r > score:
                best, score = i, r
        if best is not None and score >= 0.6:
            used.add(best); pairs.append((g, came[best]))
        else:
            pairs.append((g, None))
    for i, c in enumerate(came):
        if i not in used:
            pairs.append((None, c))
    return pairs


def code_num_drift(old, new):
    o, n = code_lines(old), code_lines(new)
    onum = {}
    for line, nums in o:
        onum.setdefault(line, []).append(nums)
    changed = []
    oset = {l for l, _ in o}
    nset = {l for l, _ in n}
    for line, nums in n:
        if line in oset:
            continue
        # A code line the published copy did not have. Only interesting if a
        # near-identical line existed with DIFFERENT numbers -- otherwise it is
        # new code, which is a feature, not a wrong number.
        best, score = None, 0.0
        for oline, onums in o:
            if oline in nset:
                continue
            r = difflib.SequenceMatcher(None, oline, line).ratio()
            if r > score:
                best, score = (oline, onums), r
        if best and score >= 0.85 and best[1] != nums:
            changed.append((best[0], line))
    return changed


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", required=True)
    ap.add_argument("--page")
    a = ap.parse_args(argv)

    mapped = json.load(io.open(os.path.join(ROOT, "tools", "artifact_map.json"),
                               encoding="utf-8"))["pages"]
    stamps = json.load(io.open(os.path.join(ROOT, "tools", "published.json"),
                               encoding="utf-8"))["pages"]
    saved = newest_saved(a.live)

    rows, no_copy = [], []
    for name, uid in sorted(mapped.items()):
        got = saved.get(uid[:8])
        if not got:
            no_copy.append(name); continue
        cur = publish_bytes(name)
        if stamps.get(name) == hashlib.sha256(cur.encode("utf-8")).hexdigest():
            rows.append((name, got[1], "CURRENT", [], [])); continue
        old = unwrap(io.open(got[0], encoding="utf-8").read())
        if old.strip() == cur.strip():
            rows.append((name, got[1], "same", [], [])); continue
        rows.append((name, got[1], "differs",
                     numeric_sentence_drift(old, cur), code_num_drift(old, cur)))

    if a.page:
        for name, ts, state, sdrift, cdrift in rows:
            if name != a.page:
                continue
            when = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
            print("%s  --  newest copy on disk: %s UTC  (%s)" % (name, when, state))
            for g, c in sdrift:
                print("")
                print("  published: " + (g[:260] if g else "(not present)"))
                print("  repo:      " + (c[:260] if c else "(removed)"))
            for o, n in cdrift:
                print("")
                print("  [code] published: " + o[:260])
                print("  [code] repo:      " + n[:260])
            if not sdrift and not cdrift:
                print("  no numeric drift in prose or code.")
            return 0
        print("no saved copy for %s" % a.page); return 2

    print("publish drift  --  measured against saved live copies, nothing fetched")
    print("-" * 74)
    # Three columns, not one. A CHANGED figure means the stale page tells a
    # reader something the repo says is wrong. A DROPPED one means it states a
    # claim the repo has withdrawn. An ADDED one means the stale page is merely
    # missing something -- real drift, and not the same harm. Ranking them
    # together made ecology-glossary (37 additions, nothing wrong) outrank
    # soil-bench (a ratio stated as eight-fold that is ten-fold).
    print("%-30s %-16s %7s %7s %7s %6s"
          % ("page", "copy seen (UTC)", "changed", "dropped", "added", "code"))
    worst = []
    for name, ts, state, sdrift, cdrift in rows:
        when = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        if state != "differs":
            print("%-30s %-16s %s" % (name, when, state)); continue
        ch = sum(1 for g, c in sdrift if g and c)
        dr = sum(1 for g, c in sdrift if g and not c)
        ad = sum(1 for g, c in sdrift if c and not g)
        print("%-30s %-16s %7d %7d %7d %6d" % (name, when, ch, dr, ad, len(cdrift)))
        if ch or dr or ad or cdrift:
            worst.append((name, ch, dr, ad, len(cdrift)))
    print("-" * 74)
    print("%d page(s) with a saved copy; %d with none (nothing can be said)"
          % (len(rows), len(no_copy)))
    if no_copy:
        print("no copy on disk: " + ", ".join(sorted(no_copy)))
    print()
    wrong = [w for w in worst if w[1] or w[2] or w[4]]
    missing = [w for w in worst if not (w[1] or w[2] or w[4]) and w[3]]
    if wrong:
        print("WRONG -- a stale copy of these states a figure the repo contradicts,")
        print("or computes one from a changed literal. Republish these first:")
        for n, ch, dr, ad, c in sorted(wrong, key=lambda r: -(r[1] * 3 + r[2] * 2 + r[4] * 3)):
            bits = []
            if ch: bits.append("%d changed" % ch)
            if dr: bits.append("%d withdrawn" % dr)
            if c:  bits.append("%d code literal(s)" % c)
            print("   %-28s %s" % (n, ", ".join(bits)))
    if missing:
        print()
        print("INCOMPLETE -- these state nothing wrong; they are missing content")
        print("the repo has added. Lower priority, and still real:")
        for n, ch, dr, ad, c in sorted(missing, key=lambda r: -r[3]):
            print("   %-28s %d sentence(s) the reader never sees" % (n, ad))
    if not worst:
        print("No numeric drift in prose or code on any page with a saved copy.")
    if worst:
        print()
        print("Read any one with --page <name> before acting on it.")
    print()
    print("Newest copy ON DISK versus the repo. A page republished since that")
    print("copy was saved will OVERSTATE its drift. Nothing understates it except")
    print("having no copy at all, which is listed above.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
