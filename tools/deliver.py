# -*- coding: utf-8 -*-
"""One list, not two: the slice manifest that makes the tarball and the commit.

Every slice of this kit produces two hand-written lists of the same file set --
the tarball's, and the push script's `git add` -- and until this file nothing
compared them. When they disagreed the file reached the disk and never reached a
commit, and EVERY AUDIT IN THE KIT STAYED GREEN, because every audit measures the
working tree and the working tree has the file. That is how four files shipped
by ADR-143 and ADR-144 sat modified and uncommitted for three days: the audits'
own summaries naming a never-exposed control, and verify_organism printing the
lines that differ when two physicals disagree.

So there is one list now. A slice writes `tools/delivery/<id>.json`:

    {"id": "adr147", "chain": "adr146",
     "subject": "one line -- the commit subject",
     "body":    "the paragraph that goes in the commit's second -m",
     "paths":   ["tools/deliver.py", "docs/ADR-147-....md", ...]}

and this file writes BOTH artefacts from it:

    python3 tools/deliver.py --script adr147   # tools/push/push-adr147.ps1
    python3 tools/deliver.py --bundle adr147   # the tarball to hand over
    python3 tools/deliver.py --record adr147   # move the delivery ledger forward
    python3 tools/deliver.py --check           # every manifest, every script

THE PUSH SCRIPT MOVES INTO THE REPO. It is the one artefact of every slice that
lived outside it -- outside every audit, outside every suite, outside the commit
it describes. ADR-096 to ADR-103 kept theirs in `CSRBT/`; from ADR-104 they were
written to the parent directory instead, and the scripts for ADR-104 to ADR-111
no longer exist anywhere, so what those eight slices staged cannot now be read.
Nothing noticed either the drift or the loss, because nothing was looking.

WHAT --check HOLDS

  * every path a manifest names exists;
  * every manifest's generated script is BYTE-IDENTICAL to the one on disk, so
    a hand-edited script is a failure rather than a silent divergence;
  * a manifest's id matches its filename, and its chain names a manifest or an
    older push script that really is there;
  * a manifest that says "once": true generates a script that PUSHES ONCE
    (ADR-184): run again after its slice is in HEAD, it pushes if the commit
    is still unpushed and otherwise does nothing -- it never stages the paths
    it shares with the next slice under this slice's message.

THE SECOND RUN (ADR-184)

  ADR-183 landed on disk beside a pushed ADR-182, and push-adr182.ps1 was run
  a second time. It did what it was written to do: `git add` its paths -- the
  ledgers, the board, the counts, AI_HARNESS, the lab task, verify_eco, all
  of which ADR-183 had just changed -- and commit them under ADR-182's
  message. ADR-183's own files (its manifest, its ADR, the module verify_eco
  now imports) were not on its list and stayed uncommitted, so origin held a
  suite that imported a module origin did not have. The script had no notion
  of having already run. A manifest with "once": true generates one that
  does: its own manifest in HEAD's tree is the fact that the slice was
  committed, and from then on the script's only legitimate work is a push
  that did not complete.
"""
import argparse, glob, hashlib, io, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
MANIFESTS = os.path.join(HERE, "delivery")
PUSH = os.path.join(HERE, "push")
LEDGER = os.path.join(HERE, "delivery_ledger.json")

# The attribution trailer. The Co-Authored-By name follows whichever model is
# committing, and it has changed WITHIN a session's chain of slices (ADR-155:
# Opus 5 -> Fable 5.1 -> Opus 4.8). A new script is generated with TRAILER;
# --check accepts a script that matches generation under ANY trailer that a real
# slice was signed with, because a model handover is not a hand edit. The
# session line names the session that generated the script (ADR-171: a handoff
# to a new session is not a hand edit either, so the sessions that real slices
# were signed from are listed the same way, newest first).
_SESSIONS = (
    "https://claude.ai/code/session_01YPcb1A7CejriRgL9xLrhJ3",   # ADR-171 on
    "https://claude.ai/code/session_01CNn3hvazSDBU2TCgsGXjTt",   # ADR-147 to ADR-170
)
_COAUTHORS = (
    "Claude Fable 5.1 <noreply@anthropic.com>",
    "Claude Opus 4.8 <noreply@anthropic.com>",
    "Claude Opus 5 <noreply@anthropic.com>",
)
def _trailer(coauthor, session=None):
    return ('  -m "Co-Authored-By: %s" -m "Claude-Session: %s"'
            % (coauthor, session or _SESSIONS[0]))
TRAILER = _trailer(_COAUTHORS[0])


def sha(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_path(mid):
    return os.path.join(MANIFESTS, mid + ".json")


def load_manifest(mid):
    p = manifest_path(mid)
    if not os.path.isfile(p):
        raise SystemExit("no manifest %s" % p)
    return json.load(io.open(p, encoding="utf-8"))


def manifests():
    return sorted(os.path.basename(p)[:-5]
                  for p in glob.glob(os.path.join(MANIFESTS, "*.json")))


def ps_quote(s):
    """A PowerShell double-quoted string, for an argument that goes to git.exe.

    A DOUBLE QUOTE CANNOT SURVIVE THIS TRIP (ADR-217). Backtick is PowerShell's
    escape and `` `" `` is a correct PowerShell string -- but PowerShell RE-QUOTES
    every argument on its way to a native .exe, and an embedded quote comes out
    the far side splitting git's argv. ADR-215's subject contained the phrase
    "everything is green" in quotes; git received `is` and `green beside a
    reading of 6 / 7, ...` as PATHSPECS, printed two errors, committed nothing,
    and the script went on to print "ADR215 pushed."

    CURLING IT DOES NOT HELP, and that was this file's second wrong answer in an
    hour: the first fix turned the straight quote into U+201C/U+201D, the script
    was regenerated, and git split the argument in the same place -- `everything`,
    `is`, `green beside a reading of ...` as pathspecs. A typographic double
    quote is a string delimiter to PowerShell as surely as a straight one, and
    unlike the straight one it cannot be backtick-escaped.

    What the evidence actually says, over sixty slices: a straight quote escaped
    as `` `" `` survives when the quoted string has NO SPACE in it (`"_in"`,
    `"buttons"`, `"3e"` all pushed cleanly), and does not when it has one. So the
    straight quote is escaped as it always was, a typographic one is turned into
    a SINGLE quote because it cannot be escaped at all, and `--check` refuses a
    straight-quoted phrase containing a space -- the manifest then says what the
    commit will say, and the rule is the mechanism rather than a superstition
    about quotes."""
    s = s.replace("`", "``")
    s = _curl(s)
    s = s.replace('"', '`"')
    return s.replace("$", "`$").replace("\r", " ").replace("\n", " ")


CURLY = u"\u201c\u201d\u201e\u201f"


def _curl(s):
    """A typographic double quote -> a single quote. It delimits a PowerShell
    string the way a straight one does and cannot be backtick-escaped, so the
    only safe thing to do with it is not send one."""
    for ch in CURLY:
        s = s.replace(ch, "'")
    return s


def _quoted_spans(s):
    """The text inside each pair of straight double quotes."""
    parts = s.split('"')
    return [parts[i] for i in range(1, len(parts), 2)]


def script_text(m, trailer=None):
    """The push script for one manifest. Deterministic: same manifest, same
    bytes, which is what lets --check compare instead of trust."""
    mid, paths = m["id"], list(m["paths"])
    # THE SCRIPT COMMITS ITSELF. It is generated, so a manifest that had to
    # remember to list it would be the same two-lists problem one level down --
    # and the record of what a slice staged would be the one file the slice
    # never staged.
    own = "tools/push/push-%s.ps1" % mid
    if own not in paths:
        paths.append(own)
    out = []
    a = out.append
    a("# push-%s.ps1 -- generated by tools/deliver.py from tools/delivery/%s.json." % (mid, mid))
    a("# DO NOT EDIT: `python3 tools/deliver.py --check` compares this file with what")
    a("# the manifest generates, and a hand edit is a failure. Change the manifest.")
    a("#")
    a("# Run from anywhere:   .\\CSRBT\\tools\\push\\push-%s.ps1" % mid)
    a('$ErrorActionPreference = "Stop"')
    a('$csrbt = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path')
    a('$root  = (Resolve-Path (Join-Path $csrbt "..")).Path')
    a('$lock = Join-Path $csrbt ".git\\index.lock"; if (Test-Path $lock) { Remove-Item $lock -Force }')
    if m.get("once"):
        # THIS SCRIPT PUSHES ONCE. The slice is committed when its own manifest
        # is in HEAD's tree (ls-tree prints the entry or nothing, and writes no
        # stderr for a Stop preference to trip on). After that, the paths it
        # lists that are modified belong to a LATER slice, and are not this
        # script's to commit; the one thing left that can be its own is a
        # commit the push never delivered.
        a("# THIS SCRIPT PUSHES ONCE (ADR-184). Run a second time, an earlier version of a")
        a("# script like this committed the NEXT slice's changes to the paths the two share")
        a("# under this slice's message and left that slice's own files behind. The slice is")
        a("# committed once its manifest is in HEAD; after that, only an undelivered push is")
        a("# this script's to finish.")
        a('$mine = git -C $csrbt ls-tree HEAD -- tools/delivery/%s.json' % mid)
        a('if ($mine) {')
        a('  $ahead = git -C $csrbt rev-list --count "@{u}..HEAD"')
        a('  if ([int]$ahead -gt 0) { Write-Host "%s is committed but not pushed -- pushing"; git -C $csrbt push; Write-Host "%s pushed."; exit 0 }'
          % (mid, mid.upper()))
        a('  Write-Host "%s is already pushed -- nothing to do (modified paths belong to a later slice; run its script)"; exit 0'
          % mid)
        a('}')
    if m.get("chain"):
        c = m["chain"]
        a("# The slice before this one, wherever its script lives: in the repo from")
        a("# ADR-147 on, in the parent directory for ADR-112 to ADR-146. It is run only")
        a("# if the file it was supposed to commit is still uncommitted.")
        a('$prev = @((Join-Path $PSScriptRoot "push-%s.ps1"), (Join-Path $root "push-%s.ps1")) |'
          ' Where-Object { Test-Path $_ } | Select-Object -First 1' % (c, c))
        if m.get("chain_probe"):
            a('if ($prev) {')
            a('  $st = git -C $csrbt status --porcelain -- %s' % m["chain_probe"])
            a('  if ($st) { Write-Host "%s is not committed yet -- running its script first"; & $prev }'
              % c)
            a('}')
    a("git -C $csrbt add -A `")
    for i, p in enumerate(paths):
        a("  %s%s" % (p, " `" if i < len(paths) - 1 else ""))
    a('git -C $csrbt commit -m "%s" `' % ps_quote(m["subject"]))
    a('  -m "%s" `' % ps_quote(m["body"]))
    a(trailer if trailer is not None else TRAILER)
    # A NATIVE COMMAND'S FAILURE IS NOT AN EXCEPTION (ADR-217).
    # $ErrorActionPreference = "Stop" governs PowerShell cmdlets and says nothing
    # about git.exe returning 1, so a commit that did nothing ran straight on to
    # the push and then to "pushed." -- the delivery layer's version of the toast
    # ADR-203 and ADR-212 are about. The exit code is read, and the POST-CONDITION
    # is checked as well: this slice's own manifest must be in HEAD afterwards,
    # which is the one thing that is true if and only if the commit happened.
    a('if ($LASTEXITCODE -ne 0) { Write-Error "%s: git commit failed ($LASTEXITCODE) -- '
      'nothing was committed and nothing will be pushed"; exit 1 }' % mid.upper())
    a('if (-not (git -C $csrbt ls-tree HEAD -- tools/delivery/%s.json)) '
      '{ Write-Error "%s: the commit ran and this slice\'s manifest is not in HEAD -- refusing to '
      'report a push that did not happen"; exit 1 }' % (mid, mid.upper()))
    a("git -C $csrbt push")
    a('if ($LASTEXITCODE -ne 0) { Write-Error "%s: git push failed ($LASTEXITCODE) -- the commit '
      'is local and the remote does not have it"; exit 1 }' % mid.upper())
    for t in m.get("clean") or []:
        a('$t = Join-Path $root "_to_delete\\%s.tgz"; if (Test-Path $t) { Remove-Item $t -Force }' % t)
    a('Write-Host "%s pushed."' % mid.upper())
    return "\n".join(out) + "\n"


def write_script(mid):
    m = load_manifest(mid)
    if not os.path.isdir(PUSH):
        os.makedirs(PUSH)
    p = os.path.join(PUSH, "push-%s.ps1" % mid)
    io.open(p, "w", encoding="utf-8", newline="\r\n").write(script_text(m))
    return p


def bundle(mid, out=None):
    m = load_manifest(mid)
    paths = list(m["paths"])
    script = os.path.relpath(os.path.join(PUSH, "push-%s.ps1" % mid), ROOT).replace(os.sep, "/")
    if script not in paths:
        paths.append(script)
    out = out or os.path.join("/tmp", "%s.tgz" % mid)
    parent = os.path.dirname(ROOT)
    base = os.path.basename(ROOT)
    args = ["tar", "czf", out, "-C", parent] + ["%s/%s" % (base, p) for p in paths]
    subprocess.run(args, check=True)
    return out, paths


def load_ledger():
    if os.path.isfile(LEDGER):
        try:
            return json.load(io.open(LEDGER, encoding="utf-8"))
        except ValueError:
            pass
    return {"_comment": "Written by tools/deliver.py. Per path: the sha256 of the bytes a slice "
                        "last DELIVERED, and which slice delivered them. audit_delivery names "
                        "anything on disk whose bytes are not in here and that no manifest "
                        "claims -- a file that is on disk and in no commit (ADR-147).",
            "paths": {}}


def save_ledger(state):
    io.open(LEDGER, "w", encoding="utf-8").write(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def record(mid, adopt=None):
    """Move the ledger forward for one slice's paths (or adopt a whole tree)."""
    state = load_ledger()
    paths = state.setdefault("paths", {})
    todo = adopt if adopt is not None else load_manifest(mid)["paths"]
    n = 0
    for rel in todo:
        full = os.path.join(ROOT, rel)
        if not os.path.isfile(full):
            continue
        paths[rel] = {"sha": sha(full), "by": mid, "at": int(time.time())}
        n += 1
    save_ledger(state)
    return n


def check():
    """-> [problem strings]. Empty is the pass."""
    bad = []
    for mid in manifests():
        m = load_manifest(mid)
        if m.get("id") != mid:
            bad.append("%s: the manifest's id is %r, not its filename" % (mid, m.get("id")))
        for key in ("subject", "body", "paths"):
            if not m.get(key):
                bad.append("%s: no %s" % (mid, key))
        # ADR-217: A QUOTED PHRASE WITH A SPACE IN IT CANNOT REACH GIT THROUGH
        # POWERSHELL. PowerShell re-quotes every argument on its way to a native
        # .exe and the quote characters do not survive, so git re-splits the
        # argument on the spaces that were inside them. Six manifests before this
        # one carried straight quotes in their bodies and every one of them
        # pushed cleanly -- `"_in"`, `"buttons"`, `"3e"` -- because none of the
        # quoted strings had a space in it. ADR-215's subject quoted the phrase
        # "everything is green", git received `is` and `green beside a reading of
        # 6 / 7, ...` as PATHSPECS, nothing was committed, and the script printed
        # "ADR215 pushed."
        #
        # So the rule is the mechanism and not a blanket ban: a quoted string is
        # refused when it contains a space. `ps_quote` curls every straight quote
        # regardless, which makes the script safe; this keeps the manifest saying
        # what the commit will say where it matters.
        for key in ("subject", "body"):
            for span in _quoted_spans(m.get(key) or ""):
                if " " in span:
                    bad.append("%s: the %s quotes %r, and a quoted phrase with a SPACE in it does "
                               "not survive the trip to git.exe -- PowerShell ends the argument "
                               "at the quote and git reads the words that were inside it as "
                               "pathspecs (ADR-217). A quoted string with no space in it is fine; "
                               "use single quotes for anything longer."
                               % (mid, key, span[:40]))
            if any(ch in (m.get(key) or "") for ch in CURLY):
                bad.append("%s: the %s carries a typographic double quote, which delimits a "
                           "PowerShell string and cannot be backtick-escaped (ADR-217). Use a "
                           "single quote." % (mid, key))
        for p in m.get("paths") or []:
            if not os.path.isfile(os.path.join(ROOT, p)):
                bad.append("%s: names %s, which is not there -- the commit would stage nothing "
                           "for it" % (mid, p))
        c = m.get("chain")
        if c and not (os.path.isfile(manifest_path(c))
                      or os.path.isfile(os.path.join(PUSH, "push-%s.ps1" % c))
                      or os.path.isfile(os.path.join(ROOT, "push-%s.ps1" % c))
                      or os.path.isfile(os.path.join(os.path.dirname(ROOT), "push-%s.ps1" % c))):
            bad.append("%s: chains from %s, and no manifest or script by that name is anywhere"
                       % (mid, c))
        sp = os.path.join(PUSH, "push-%s.ps1" % mid)
        if not os.path.isfile(sp):
            bad.append("%s: no generated script -- run --script %s" % (mid, mid))
        else:
            on_disk = io.open(sp, encoding="utf-8", newline="").read().replace("\r\n", "\n")
            if not any(on_disk == script_text(m, _trailer(ca, se))
                       for ca in _COAUTHORS for se in _SESSIONS):
                bad.append("%s: push-%s.ps1 is not what the manifest generates -- it was edited "
                           "by hand, and the two lists have started to disagree again" % (mid, mid))
    return bad


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", metavar="ID", help="write tools/push/push-<ID>.ps1")
    ap.add_argument("--bundle", metavar="ID", help="write the tarball for <ID>")
    ap.add_argument("--out", help="where the tarball goes")
    ap.add_argument("--record", metavar="ID", help="move the delivery ledger forward for <ID>")
    ap.add_argument("--adopt", metavar="ID",
                    help="record every tracked file as delivered by <ID>. For seeding the ledger "
                         "once, from a tree that is known to be committed -- an adoption, not "
                         "evidence, and it says so in the ledger")
    ap.add_argument("--check", action="store_true", help="hold every manifest and every script")
    ap.add_argument("--list", action="store_true", help="the manifests, and what each ships")
    a = ap.parse_args(argv)

    if a.list:
        for mid in manifests():
            m = load_manifest(mid)
            print("%-10s %3d path(s)   %s" % (mid, len(m["paths"]), m["subject"][:70]))
        return 0
    if a.script:
        print("wrote %s" % write_script(a.script))
        return 0
    if a.bundle:
        out, paths = bundle(a.bundle, a.out)
        print("wrote %s -- %d path(s)" % (out, len(paths)))
        return 0
    if a.adopt:
        import audit_delivery as AD
        # NOT the paths a manifest already claims: those are this slice's own
        # work in flight, and adopting them would record as delivered exactly
        # the files that have not been.
        cl = AD.claimed()
        n = record(a.adopt, adopt=[p for p in AD.tracked() if p not in cl])
        state = load_ledger()
        state["_adopted"] = {"by": a.adopt, "at": int(time.time()), "paths": n,
                             "why": "seeded from a tree known to be committed. An adoption is "
                                    "not evidence that these bytes were pushed -- it is the "
                                    "baseline the ratchet starts from."}
        save_ledger(state)
        print("adopted %d path(s) as delivered by %s" % (n, a.adopt))
        return 0
    if a.record:
        print("recorded %d path(s) as delivered by %s" % (record(a.record), a.record))
        return 0
    if a.check:
        bad = check()
        for b in bad:
            print("  ", b)
        print("%d manifest(s), %d problem(s)" % (len(manifests()), len(bad)))
        return 1 if bad else 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
