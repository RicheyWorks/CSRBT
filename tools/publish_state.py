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


def stamp_allowed(prev, taken, same_build=False):
    """May a read taken at `taken` replace the stamp `prev`? -> (bool, why).

    `same_build` says the existing stamp records the build now in build/. It is
    only meaningful where the caller has ALSO measured that the copy carries
    that build -- and --verify only acts on the returned verdict after the
    containment test has passed, which is what makes the three equal: stamp,
    repo, copy. When they are, ORDERING IS NOT A QUESTION: both entries describe
    the same publish, and the only thing being decided is which provenance word
    the file keeps for it. "read" beats "publish" every time -- one says the URL
    was serving these bytes, the other says only that they were handed over.

    That case had to be named because the two dates come from different clocks
    for the same event. --stamp writes time.time() at the moment of the local
    call; the artifact's version epoch is assigned a few seconds EARLIER. So a
    read of exactly the version a stamp describes always looks about five
    seconds stale against it, and without this clause every one of the twenty
    publish-time stamps was permanently unimprovable -- the same shape of wall
    ADR-084 took down, rebuilt by the fix in ADR-085 that made the dates honest.

    Stated as a function because the rule has three cases and inline
    conditionals hid one of them: written as a single early return it also
    refused to READ the copy, and one clause -- "the stamp carries no time, so
    this cannot be ordered" -- could never be satisfied by any copy, because
    there was no time for one to be newer than. Every page still on a
    pre-ADR-056 stamp was therefore permanently unmeasurable.

    An undated stamp is the weakest entry the file holds; a dated read is
    strictly better evidence and supersedes it. A DATED stamp still wins against
    an older copy -- that is ADR-056 and it is unchanged."""
    at = entry_at(prev)
    if prev is None:
        return True, "no previous stamp"
    if same_build:
        return True, ("the copy carries the very build this stamp records -- same "
                      "publish, and a read is better provenance than a publish")
    if at is None:
        return True, "supersedes an undated stamp with a dated read"
    if taken < at:
        return False, "the copy is older than the stamp it would overwrite"
    return True, "the copy is at least as new as the stamp"


def observation_allowed(prev, taken):
    """May a copy taken at `taken` be recorded as an observation about `prev`'s
    page? -> (bool, why).

    A DIFFERENT question from stamp_allowed, and sharing one answer between them
    was a bug. Stamping asks "is this better evidence than what the file holds?"
    -- and an undated stamp is the weakest thing the file holds, so a dated read
    beats it (ADR-084). Observing asks "does this copy describe the page as it is
    NOW?" -- and against an undated stamp there is no time to order against, so
    the honest answer is that it cannot be known, not that the copy wins.

    Run against the ten pre-provenance pages, the shared rule recorded
    "behind, measured, via read" for the two with no date at all, from copies of
    versions three days old. Both pages may well be current; the copies simply
    could not say. An unorderable copy is not licence to make the claim, it is
    the reason not to."""
    at = entry_at(prev)
    if prev is None:
        return True, "nothing published is on record, so nothing is contradicted"
    if at is None:
        return False, ("the stamp carries no time, so this copy cannot be ordered "
                       "against the publish it would speak about")
    if taken < at:
        return False, "the copy is older than the stamp it would overwrite"
    return True, "the copy is at least as new as the last publish"


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


VERSION_IN_BYTES = re.compile(r'<base href="/_f/(\d{9,})-[0-9a-f]+/"')
VERSION_IN_NAME = re.compile(r"artifact-[0-9a-f]+-(\d{9,})-[0-9a-f]+\.html$")


def copy_taken_at(copy_path, live_text):
    """When was this copy taken? -> (epoch, how).

    NOT the file's mtime. mtime is a property of the local file and anything
    that rewrites the cache -- a re-read, a copy, a sync -- moves it forward
    without a byte of the page changing. Measured across 103 saved copies:
    every single mtime was LATER than the version the copy actually carries,
    by up to 3.1 days, and never once equal. Every date this file has ever
    written for a via="read" entry was overstated, all nine of them, and always
    in the unsafe direction -- an old copy looking newer is the exact thing
    ADR-056 exists to refuse.

    The honest date is inside the bytes. A published artifact carries
    <base href="/_f/<epoch>-<hash>/">, and that epoch is when THIS VERSION was
    published, which is the number the ordering question actually needs: a copy
    of the version published at V cannot be evidence about anything published
    after V, no matter when it was fetched.

    Three sources, in order of what they are about:
      bytes   the version marker in the copy itself. About the page.
      name    the same epoch in a saved copy's filename. About the file, but
              written from the page.
      mtime   about the local filesystem and nothing else. Last resort, and it
              says so, because a date whose provenance is unstated is how the
              nine got written.
    If bytes and name disagree the copy was renamed or edited; take the older
    of the two, which is the reading that can only understate."""
    b = VERSION_IN_BYTES.search(live_text)
    n = VERSION_IN_NAME.search(os.path.basename(copy_path))
    if b and n:
        vb, vn = int(b.group(1)), int(n.group(1))
        if vb != vn:
            return min(vb, vn), "version marker, disagreeing with the filename -- taking the older"
        return vb, "the version marker in the copy"
    if b:
        return int(b.group(1)), "the version marker in the copy"
    if n:
        return int(n.group(1)), "the version epoch in the filename"
    try:
        return int(os.path.getmtime(copy_path)), "the file's mtime -- NOT the version, only when this file was last written"
    except OSError:
        return None, "nothing in the copy or on disk dates it"


TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
COPY_OF = re.compile(r"artifact-([0-9a-f]{6,})-")


def copy_is_of(name, copy_path, live_text, build_path, mapped):
    """Is this saved copy a copy of THIS page? -> (ok, why).

    `--verify` takes a page name and a path, and NOTHING made them agree. Handing
    it a copy of one page under another page's name produced a confident
    "BEHIND, measured" about a page that was current, and wrote it into
    state["observed"] with via="read" -- the strongest provenance this file
    records -- alongside an offline-contract verdict about the named page
    derived from another page's bytes. That is ADR-078's rule (an observation is
    only about the thing it was taken against) broken by the interface that
    records the observation. Measured, not supposed: run it and the false
    BEHIND lands in the file.

    Two independent attributors, because one that can only ever say yes is not a
    check:

      the path   a saved artifact copy is named artifact-<id>-...; if the
                 basename carries an id and the map has one for this page, they
                 must be the same artifact.
      the title  every page in this kit has exactly one <title> and all 39 are
                 distinct, so the copy's title element must be this page's. Not
                 "the title appears somewhere" -- a hub page quoting a title in
                 a card would pass that.

    Either one may stay silent (a copy saved under a hand-chosen name; a page
    with no title). Either one may refuse, and a single refusal refuses. If BOTH
    stay silent the answer is still no: nothing ties this copy to this page, and
    a silent pass is how the interface got here (ADR-061).

    A title mismatch can also mean this page's title changed since it was
    published. That is not a case worth an override: in both readings the copy
    must not be stamped CURRENT, and if the title changed the page is behind by
    that fact alone -- republish and stamp, no measurement needed."""
    said = []
    want_id = (mapped.get(name) or "")
    m = COPY_OF.search(os.path.basename(copy_path))
    if m and want_id:
        got = m.group(1)
        if not want_id.startswith(got):
            return False, ("this copy is a copy of artifact %s; %s is artifact %s"
                           % (got, name, want_id[:len(got)]))
        said.append("path names this page's artifact")
    bt = TITLE.findall(io.open(build_path, encoding="utf-8").read())
    lt = TITLE.findall(live_text)
    if len(bt) == 1 and len(lt) == 1:
        if bt[0].strip() != lt[0].strip():
            return False, ("the copy's title is %r; this page's is %r"
                           % (lt[0].strip()[:60], bt[0].strip()[:60]))
        said.append("title matches")
    if not said:
        return False, "nothing in this copy ties it to this page"
    return True, " and ".join(said)


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


def mapped_artifacts():
    """Every artifact this kit publishes, build name -> id: the docs pages, and
    (ADR-138) the ones that are not pages -- the Harness Board. publish.py
    builds both into build/publish, so everything below treats them alike."""
    m = load(MAP, {"pages": {}})
    out = dict(m.get("pages", {}))
    for name, spec in (m.get("others") or {}).items():
        out[name] = spec["artifact"]
    return out


def main(argv):
    state = load(STATE, BLANK)
    mapped = mapped_artifacts()

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
        live_early = io.open(copy, encoding="utf-8", errors="replace").read()
        taken, how_taken = copy_taken_at(copy, live_early)
        if taken is None:
            print("%-30s %s -- not stamped" % (n, how_taken)); return 2
        prev = state["pages"].get(n)
        prev_at = entry_at(prev)
        # WHAT THE ORDERING GUARD IS FOR, AND WHAT IT IS NOT FOR.
        #
        # ADR-056's rule is that a copy older than the stamp it would overwrite
        # describes a page that no longer exists, so it must not replace the
        # stamp. That protects the STAMP. It has nothing to say about reading
        # the copy, about what the copy does with the offline contract, or about
        # recording a BEHIND observation -- none of which touch state["pages"].
        #
        # Written as a single early `return 2` it refused all four, and one of
        # its two clauses could never be satisfied by anything: when the stamp
        # carries no time, there is no time for the copy to be newer than, so
        # every page still on a pre-ADR-056 stamp was permanently unmeasurable.
        # Fourteen pages were in that state, which is exactly the set ADR-083
        # predicted would verify CURRENT -- a prediction the tool made
        # untestable. A guard with no satisfiable path is not a guard, it is a
        # wall, and it was standing in front of its own evidence.
        #
        # So the check moved to where the write is, and split in two:
        #   * an untimed stamp is the weakest entry in the file (the report says
        #     so on every run). A dated read is strictly better evidence, so it
        #     supersedes -- and says so, because silently replacing one is how a
        #     file stops meaning what it says.
        #   * a TIMED stamp still wins against an older copy, unchanged.
        # Does the existing stamp record the build now in build/? A fact about
        # bytes, and where the containment test below also passes it means stamp,
        # repo and copy are the same publish -- so the dates need not be compared
        # at all. Read here, acted on only past that test.
        same_build = (entry_sha(prev) == sha(bp)) if prev is not None else False
        may_stamp, why_stamp = stamp_allowed(prev, taken, same_build)
        live = live_early
        # Before ANY claim is printed or written: is this a copy of this page?
        # Everything below -- the offline-contract line, the BEHIND observation,
        # the CURRENT stamp -- is a statement about `n`, and each one is false in
        # the same way if the copy is of something else.
        ok_of, why_of = copy_is_of(n, copy, live, bp, mapped)
        if not ok_of:
            print("%-30s NOT A COPY OF THIS PAGE -- nothing measured" % n)
            print("%-30s   %s" % ("", why_of))
            return 2
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
            # ADR-084 carved observations out of the ordering guard, on the
            # reasoning that they never touch state["pages"]. The reasoning was
            # right and the carve-out was still too wide, because the date
            # feeding it was the file's mtime and therefore always overstated:
            # a copy of a version published two days ago, re-cached a minute
            # ago, recorded "behind, measured, via read" about a page that had
            # been republished in between. That is ADR-055's harm with the
            # strongest provenance word in the file attached to it.
            #
            # A BEHIND observation is a claim about the page NOW. A copy older
            # than the last publish cannot make it, so it does not get to.
            may_obs, why_obs = observation_allowed(prev, taken)
            if not may_obs:
                print("%-30s   but %s -- so this copy is not evidence that the page "
                      "is behind NOW. Not recorded." % ("", why_obs))
                save(state)
                return 0
            state.setdefault("observed", {})[n] = {
                "sha": sha(bp), "at": taken, "via": "read", "state": "behind",
                "blocking_webfont": bool(bad), "dated_by": how_taken}
            save(state)
            return 1
        if not may_stamp:
            print("%-30s the copy carries this build, but %s (%d < %d) "
                  "-- measured, not stamped" % (n, why_stamp, taken, prev_at))
            save(state)
            return 0
        if prev is not None and entry_at(prev) is None:
            print("%-30s   %s" % ("", why_stamp))
        state["pages"][n] = {"sha": sha(bp), "at": taken, "via": "read",
                             "dated_by": how_taken}
        state.get("observed", {}).pop(n, None)
        print("%-30s CURRENT, measured from the live copy taken at %d" % (n, taken))
        print("%-30s   dated by %s" % ("", how_taken))
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
    pages += sorted(n for n in mapped if n not in pages)      # ADR-138: the board is an artifact too
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
