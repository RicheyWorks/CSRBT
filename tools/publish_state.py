# -*- coding: utf-8 -*-
"""What is actually published, versus what is in the repo.

Thirty-seven pages of this kit are published as Artifacts, and those URLs are
the ones people are given. Nothing recorded which version of a page each URL was
serving, so after any slice the honest answer to "is the published Relevé the
Relevé in this repo?" was: nobody knows. A stale artifact is not a missing
feature, it is a wrong page in front of a reader who has no way to tell.

This records a hash of the exact bytes handed to the publisher, and reports
drift against it.

    python3 tools/publish_state.py                  # report
    python3 tools/publish_state.py --stamp a.html   # record what was just published
    python3 tools/publish_state.py --check          # exit non-zero if anything is behind

A page that has never been stamped reports as **unknown**, not as current.
Unknown is the truthful state for the pages published before this file existed,
and collapsing it into "up to date" would be the single most useful lie this
tool could tell.

WHY EACH STAMP CARRIES A TIME (ADR-056)

The hash alone answers "is the repo ahead of what I last published?". It cannot
answer "is this saved copy of the live page still evidence?", and publish_drift
needs that second answer: a copy fetched BEFORE the last publish describes a
page that no longer exists. Twice now a copy older than its own page produced a
list of corrections that were already live -- once reported to the user as harm
(ADR-055), once caught by the caveat (this ADR). A stamp with no time cannot
distinguish the two cases, so every stamp records when it was taken.

Entries are {"sha": ..., "at": epoch seconds}. A bare string is the pre-ADR-056
format and reads back with at=None -- ordering unknown, which is its own state
and not a licence to assume either order.

WHY A STAMP RECORDS HOW IT WAS TAKEN (ADR-078)

"Unknown" was the truthful state for pages published before this file existed,
and it stayed unknown because the only way to leave it was to republish
nineteen artifacts. That is a real cost paid for a bookkeeping gap, and it is
avoidable: the published copy can be READ, and ADR-055's own principle is that
staleness is a property of the published copy. So a stamp can also be earned by
measuring the live page instead of by publishing it.

Those two stamps are not the same evidence and must not read as if they were:

  via "publish"   these are the bytes I handed the publisher. Says nothing
                  about whether the publisher kept them.
  via "read"      the URL was serving these bytes at that moment. Stronger
                  about the past, and stale the instant someone republishes.

--verify takes a saved copy of a live artifact and stamps via "read" ONLY when
the copy CONTAINS the current publish bytes verbatim. Containment, not equality:
the publisher wraps the content in a page skeleton, and parsing that skeleton
back off would be a filter written against today's wrapper. Containment needs no
wrapper knowledge, cannot pass by accident at these sizes, and fails safe -- a
publisher that rewrote one byte of content would report BEHIND, which is the
wrong answer in the harmless direction.

A copy older than the last publish describes a page that no longer exists
(ADR-056), so --verify refuses a copy it cannot date, and refuses to stamp a
copy taken before the entry it would overwrite.
"""
import glob, hashlib, io, json, os, re, subprocess, sys, time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")
BUILD = os.path.join(ROOT, "build", "publish")
STATE = os.path.join(ROOT, "tools", "published.json")
MAP = os.path.join(ROOT, "tools", "artifact_map.json")

BLANK = {
    "_comment": "sha256 of the bytes last handed to the publisher, per page, "
                "with the epoch second the stamp was taken. A page absent from "
                "this map has never been stamped and its published state is "
                "UNKNOWN -- which is not the same as current. An entry that is "
                "a bare string is the pre-ADR-056 format: hash known, time not.",
    "pages": {},
    "_observed": "Measurements of the LIVE copy that did NOT match. A negative "
                 "result is knowledge too: 'I read that URL at T and it was not "
                 "serving this build' is a stronger statement than 'unknown', "
                 "and dropping it on the floor is how a page stays unknown "
                 "forever after somebody has already looked. Each entry records "
                 "the build sha it was compared AGAINST, so the observation "
                 "decays back to unknown the moment the repo moves under it.",
    "observed": {},
}


def entry_sha(e):
    """The recorded hash, whichever format the entry is in."""
    return e if isinstance(e, str) else (e or {}).get("sha")


def entry_at(e):
    """When the stamp was taken, or None when the entry predates ADR-056.

    None is not zero and not now. A caller that treats it as either is asserting
    an ordering the file does not record."""
    return None if isinstance(e, str) else (e or {}).get("at")


def entry_via(e):
    """How the stamp was earned: "publish", "read", or None for entries written
    before ADR-078. None is not "publish" -- the old entries were all taken at
    publish time, but a reader cannot tell that from the file, and writing the
    stronger word in would be asserting provenance the file does not carry."""
    return None if isinstance(e, str) else (e or {}).get("via")


def contains_build(live_text, build_path):
    """Is this saved copy serving exactly these publish bytes?

    Containment rather than equality, and rather than skeleton-stripping. The
    build output is the body content the publisher wraps; at 150 KB a verbatim
    occurrence is not something that happens by chance, and asking the question
    this way means this file never has to know what the wrapper looks like."""
    return io.open(build_path, encoding="utf-8").read() in live_text


BLOCKING_FONT = re.compile(
    r'<link[^>]*rel=["\']stylesheet["\'][^>]*fonts\.googleapis\.com[^>]*>')


def blocking_webfont(live_text):
    """Does this PUBLISHED copy hold first paint on a font request?

    The kit's own rule, from ADR-031: a webfont stylesheet is requested with
    media="print" and promoted to "all" once it arrives, so a request that hangs
    on one bar of signal cannot hold the page blank. verify_offline_slice checks
    that rule -- on the REPO. Nothing checked it on the published copies, and
    the published copies are the ones a reader opens (ADR-055).

    Measured, not assumed: a blocking link is one with rel=stylesheet pointing
    at the font host and NO media attribute deferring it. The deferred link
    carries data-webfont and media="print", so it is excluded by the same test
    that finds the blocking one, and the promoting script is looked for
    separately -- a page with the link but not the script never promotes and
    renders in fallback fonts forever."""
    bad = [m.group(0) for m in BLOCKING_FONT.finditer(live_text)
           if "data-webfont" not in m.group(0)]
    # <noscript> carries a deliberately blocking copy; that is the fallback, not
    # the defect, and counting it would report every correct page.
    ns = re.findall(r"<noscript>.*?</noscript>", live_text, re.S)
    bad = [b for b in bad if not any(b in n for n in ns)]
    has_promoter = "link[data-webfont]" in live_text
    return bad, has_promoter


def classify(name, build_sha, state):
    """The state of one page's published copy: the whole rule, in one place.

    Returns ("current"|"behind"|"measured-behind"|"unknown", entry_or_None).

    Pulled out of the report so the decay rule can be tested rather than
    described. That rule is the subtle one: an observation is only about the
    build it was taken against, so once the repo moves, "I read that URL and it
    was not serving THAT" says nothing about what it is serving now. Carrying
    the verdict forward would be a stale claim about a live page, which is the
    exact failure ADR-055 is named for."""
    stamp = state.get("pages", {}).get(name)
    if stamp is not None:
        return ("current" if entry_sha(stamp) == build_sha else "behind"), stamp
    obs = state.get("observed", {}).get(name)
    if obs is not None and entry_sha(obs) == build_sha:
        return "measured-behind", obs
    return "unknown", None


def load(path, blank):
    if not os.path.exists(path):
        return json.loads(json.dumps(blank))
    return json.load(io.open(path, encoding="utf-8"))


def save(state):
    io.open(STATE, "w", encoding="utf-8").write(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()


def build_current(names):
    """Regenerate the publish bytes so the comparison is against what WOULD be
    published now, not against a stale build directory."""
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "publish.py")] + list(names),
                   cwd=os.path.join(ROOT, "tools"), capture_output=True, text=True)


def main(argv):
    state = load(STATE, BLANK)
    mapped = load(MAP, {"pages": {}})["pages"]

    if "--verify" in argv:
        # publish_state.py --verify PAGE.html /path/to/saved-live-copy.html
        names = [a for a in argv if a.endswith(".html") and not os.sep in a
                 and not a.startswith("/")]
        copies = [a for a in argv if a.endswith(".html") and a not in names]
        if len(names) != 1 or len(copies) != 1:
            print("--verify needs exactly one page name and one path to a saved live copy")
            return 2
        n, copy = names[0], copies[0]
        if not os.path.exists(copy):
            print("%-30s no such copy: %s" % (n, copy)); return 2
        build_current([n])
        bp = os.path.join(BUILD, n)
        if not os.path.exists(bp):
            print("%-30s NOT BUILT -- nothing verified" % n); return 2
        # ADR-056: a copy that cannot be dated cannot be ordered against the
        # publish it would be evidence about, so it is not evidence.
        try:
            taken = int(os.path.getmtime(copy))
        except OSError:
            print("%-30s the copy cannot be dated -- not stamped" % n); return 2
        prev = state["pages"].get(n)
        prev_at = entry_at(prev)
        if prev is not None and prev_at is None:
            print("%-30s the existing stamp carries no time, so this copy cannot be "
                  "ordered against it -- not stamped" % n); return 2
        if prev_at is not None and taken < prev_at:
            print("%-30s the copy is OLDER than the stamp it would overwrite "
                  "(%d < %d) -- not stamped" % (n, taken, prev_at)); return 2
        live = io.open(copy, encoding="utf-8", errors="replace").read()
        # Whether it is behind or not, say what the LIVE copy does about the
        # offline contract. That is the number that decides how urgent a
        # republish is, and it is only knowable from the published bytes.
        bad, promoter = blocking_webfont(live)
        if bad:
            print("%-30s   the PUBLISHED copy blocks first paint on a font request "
                  "-- ADR-031's rule, broken where the reader is" % "")
            print("%-30s   %s" % ("", bad[0][:110]))
        elif not promoter:
            print("%-30s   the published copy has no webfont promoter; if it also has "
                  "no font link that is fine, and worth a look if not" % "")
        if not contains_build(live, bp):
            print("%-30s BEHIND, measured: the copy does not carry the current publish "
                  "bytes" % n)
            # Labelled, because the two are not comparable and reading them as if
            # they were is a trap I walked into myself: the copy is the WRAPPED
            # page and carries the publisher's ~12 KB runtime skeleton, so a
            # correct page whose content is identical still shows a copy that
            # looks 12 KB "larger". The gap between them is not drift.
            print("%-30s   copy %d chars INCLUDING the publisher's wrapper; publish bytes %d "
                  "-- the two are not comparable, only the containment test is"
                  % ("", len(live), os.path.getsize(bp)))
            print("%-30s   republish, then --stamp" % "")
            state.setdefault("observed", {})[n] = {
                "sha": sha(bp), "at": taken, "via": "read", "state": "behind",
                "blocking_webfont": bool(bad)}
            save(state)
            return 1
        state["pages"][n] = {"sha": sha(bp), "at": taken, "via": "read"}
        state.get("observed", {}).pop(n, None)
        print("%-30s CURRENT, measured from the live copy taken at %d" % (n, taken))
        save(state)
        return 0

    if "--stamp" in argv:
        names = [a for a in argv if a.endswith(".html")]
        if not names:
            print("--stamp needs at least one page name"); return 2
        build_current(names)
        for n in names:
            p = os.path.join(BUILD, n)
            if not os.path.exists(p):
                print("%-30s NOT BUILT -- nothing stamped" % n); return 2
            state["pages"][n] = {"sha": sha(p), "at": int(time.time()), "via": "publish"}
            print("%-30s stamped %s" % (n, entry_sha(state["pages"][n])[:12]))
        save(state)
        return 0

    build_current([])
    pages = sorted(os.path.basename(p) for p in glob.glob(os.path.join(DOCS, "*.html")))
    behind, unknown, current, unmapped, measured = [], [], [], [], []
    for n in pages:
        if n not in mapped:
            unmapped.append(n); continue
        p = os.path.join(BUILD, n)
        if not os.path.exists(p):
            unknown.append(n); continue
        kind, entry = classify(n, sha(p), state)
        if kind == "current":          current.append((n, entry_via(entry)))
        elif kind == "behind":         behind.append(n)
        elif kind == "measured-behind": measured.append((n, entry))
        else:                          unknown.append(n)

    print("published state  --  %d pages mapped to an artifact" % len(mapped))
    print("-" * 68)
    for n in behind:
        print("%-30s BEHIND    the repo has moved since it was published" % n)
    for n, o in measured:
        print("%-30s BEHIND    measured at the URL: it was not serving this build%s"
              % (n, ", and it blocks first paint on a font request"
                    if o.get("blocking_webfont") else ""))
    for n in unknown:
        print("%-30s unknown   never stamped; published state cannot be asserted" % n)
    for n in unmapped:
        print("%-30s unmapped  no artifact URL" % n)
    print("-" * 68)
    # Current is not one state. A page whose stamp was earned by READING the
    # live copy is evidence about that URL; a page stamped at publish time is
    # evidence about what was handed to the publisher, which is a weaker claim
    # (ADR-078). Collapsing them would be the same lie as collapsing unknown
    # into current, one notch quieter.
    _by = {}
    for _n, _v in current: _by.setdefault(_v, []).append(_n)
    print("%d current, %d behind (%d of them measured at the URL), %d unknown, "
          "%d unmapped" % (len(current), len(behind) + len(measured), len(measured),
                           len(unknown), len(unmapped)))
    # What this figure is actually FOR (ADR-079). Every audit and suite in this
    # kit measures docs/ -- the repo. A green contrast audit is a claim about
    # what a reader sees only for the pages whose published copy carries those
    # same bytes, and this line is the only place that link is stated. Measured
    # on 2026-08-27: the published flagship was serving --muted at 2.98:1 and a
    # render-blocking font link, months after the audits that catch both went
    # green, because they were green about the repo.
    if behind or measured or unknown:
        print("   %d page(s) are NOT known to carry the audited bytes -- for those, a "
              "green audit\n   of docs/ says nothing about what a reader sees"
              % (len(behind) + len(measured) + len(unknown)))
    if current:
        print("   of the current: %s"
              % ", ".join("%d %s" % (len(v), {"read": "measured from the live page",
                                              "publish": "stamped at publish time",
                                              None: "stamped before provenance was recorded"}[k])
                          for k, v in sorted(_by.items(), key=lambda kv: str(kv[0]))))
    _all_behind = behind + [n for n, _ in measured]
    if _all_behind:
        print("\nRepublish those, then:  python3 tools/publish_state.py --stamp "
              + " ".join(_all_behind))
    if unknown:
        print("\nUnknown is honest, not clean: those pages were published before this")
        print("file existed and nothing recorded what they were serving. Each can be")
        print("resolved WITHOUT republishing, by reading its artifact and measuring the")
        print("copy:  python3 tools/publish_state.py --verify PAGE.html /path/to/copy.html")
    return 1 if ("--check" in argv and (behind or measured or unknown)) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
