# -*- coding: utf-8 -*-
"""One list, not two -- the delivery manifest, checked (ADR-147).

`tools/deliver.py` generates the tarball and the push script from one manifest,
and `tools/audit_delivery.py` names anything on disk that no slice has handed
over. Between them they are the only thing standing between a file and the fate
of the four that ADR-143 and ADR-144 shipped and never staged, so they have to
be right about four things a fixture can pin exactly:

  A. THE GENERATED SCRIPT. Every path, in order; the subject and the body,
     escaped for PowerShell; deterministic, so --check can compare rather than
     trust.
  B. --check. A manifest naming a file that is not there, a script edited by
     hand, an id that is not its filename, a chain to nothing -- each is a
     failure, and a good manifest is not.
  C. THE BUNDLE. Exactly the manifest's paths, plus the script that commits them.
  D. THE AUDIT. Undelivered is "bytes not in the ledger AND no manifest claims
     it"; recording moves a file to delivered; touching it afterwards moves it
     back; ignoring needs a reason; and it fails with no flag.
  F. INSTALLED BY THE COMMAND THAT PUSHES (ADR-223). A file the bridge will not
     write travels as an ordinary one; the script copies it into place before
     the add and stages the copy; the tarball does not carry it.
  E. A CLAIM EXPIRES (ADR-219). Only an UNSHIPPED manifest claims its paths --
     the file a shipped slice named and a later one changed without naming is
     undelivered, not in flight. Where there is git it is asked, in a real
     repository built here; `--catch-up` writes only what git vouches for, and
     `--check` holds the recording step that nothing held.

Run:  python3 tools/verify/verify_delivery.py
"""
MUTATE_ROLE = "subject"
import contextlib, io, json, os, shutil, subprocess, sys, tarfile, tempfile

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import deliver as D
import audit_delivery as AD

P = F = 0


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


tmp = tempfile.mkdtemp(prefix="delivery_")
os.makedirs(os.path.join(tmp, "tools", "delivery"))
os.makedirs(os.path.join(tmp, "tools", "push"))
os.makedirs(os.path.join(tmp, "tools", "verify"))
os.makedirs(os.path.join(tmp, "docs"))


def put(rel, text):
    p = os.path.join(tmp, rel)
    d = os.path.dirname(p)
    if not os.path.isdir(d):
        os.makedirs(d)
    io.open(p, "w", encoding="utf-8").write(text)
    return p


put("tools/one.py", "one\n")
put("tools/two.py", "two\n")
put("tools/verify/verify_one.py", "check one\n")
put("docs/ADR-999-fixture.md", "# fixture\n")
put("tools/old.py", "old\n")

D.ROOT = tmp
D.MANIFESTS = os.path.join(tmp, "tools", "delivery")
D.PUSH = os.path.join(tmp, "tools", "push")
D.LEDGER = os.path.join(tmp, "tools", "delivery_ledger.json")
AD.ROOT = tmp

MAN = {
    "id": "adr999",
    "chain": "adr998",
    "chain_probe": "tools/old.py",
    "subject": 'ADR-999: a "quoted" subject with a ` backtick and a $var',
    "body": "The body.\nWith a newline, a \"quote\" and a ` backtick.",
    # A slice ships its own manifest and the ledger it moves forward, exactly as
    # the real ones do -- otherwise the two files this mechanism is made of are
    # the first two it reports as undelivered.
    "paths": ["tools/one.py", "tools/two.py", "docs/ADR-999-fixture.md",
              "tools/delivery/adr999.json", "tools/delivery_ledger.json"],
    "clean": ["adr998"],
}


def write_manifest(m, mid=None):
    io.open(os.path.join(D.MANIFESTS, (mid or m["id"]) + ".json"), "w",
            encoding="utf-8").write(json.dumps(m, indent=1, ensure_ascii=False) + "\n")


write_manifest(MAN)
D.save_ledger(D.load_ledger())
# something for the chain to find
io.open(os.path.join(D.PUSH, "push-adr998.ps1"), "w", encoding="utf-8").write("# previous\n")

# ---- A. the generated script ------------------------------------------------
sp = D.write_script("adr999")
txt = io.open(sp, encoding="utf-8", newline="").read().replace("\r\n", "\n")
ck(os.path.basename(sp) == "push-adr999.ps1" and os.path.dirname(sp) == D.PUSH,
   "the script is written into the repo, beside its manifest -- it was the one artefact of a "
   "slice that lived outside it: %s" % sp)
for p in MAN["paths"]:
    ck(p in txt, "the script stages %s, because the manifest names it -- the two lists are one "
                 "list now" % p)
ck(txt.index("tools/one.py") < txt.index("tools/two.py") < txt.index("docs/ADR-999-fixture.md"),
   "...in the manifest's order, so the same manifest always makes the same script")
ck("tools/push/push-adr999.ps1" in txt.split("git -C $csrbt commit")[0],
   "and the script stages ITSELF, without the manifest having to remember it: it is generated, "
   "so a manifest that listed it would be the same two-lists problem one level down -- and the "
   "record of what a slice staged would be the one file the slice never staged")
ck('-m "ADR-999: a `"quoted`" subject with a `` backtick and a `$var"' in txt,
   "the subject is escaped for PowerShell -- a quote, a BACKTICK and a $ each, and the backtick "
   "first, since it is the escape character and doing it last escapes every other escape:\n%s"
   % [l for l in txt.split("\n") if l.startswith('git -C $csrbt commit')])
ck("The body. With a newline" in txt,
   "the body is one line: a newline inside a PowerShell double-quoted argument ends nothing, but "
   "it makes the script unreadable and the commit message ragged")
ck("$PSScriptRoot" in txt and '".."' in txt,
   "the script finds the repo from ITS OWN location, because it no longer sits in the directory "
   "the operator runs it from")
ck("push-adr998.ps1" in txt and "status --porcelain -- tools/old.py" in txt
   and "& $prev" in txt,
   "the chain probes the file the previous slice was supposed to commit, and RUNS its script if "
   "that file is still uncommitted -- a chain that only looks is not a chain")
ck('_to_delete\\adr998.tgz' in txt, "and the tarballs it names are cleaned up")
ck(D.script_text(D.load_manifest("adr999")) == txt,
   "generating it twice gives the same bytes -- which is the whole of why --check can compare "
   "instead of trust")

# ---- A1b. a script cannot say it pushed when it did not (ADR-217) -------------
# ADR-215's subject quoted a phrase with a space in it; PowerShell re-quoted the
# argument on its way to git.exe, the quotes did not survive, git re-split on the
# spaces and read the pieces as pathspecs. Nothing was committed. Then `git push`
# answered "Everything up-to-date" -- true, there was nothing new -- and the
# script printed "ADR215 pushed." A native command's failure is not a PowerShell
# exception, so $ErrorActionPreference = "Stop" said nothing about any of it.
ck(txt.index('$LASTEXITCODE') < txt.index("git -C $csrbt push"),
   "THE COMMIT'S EXIT CODE IS READ BEFORE ANYTHING IS PUSHED: a commit that did nothing ran "
   "straight on to the push and then to the word 'pushed' (ADR-217)")
ck(txt.count("$LASTEXITCODE") >= 2 and
   txt.index("git -C $csrbt push") < txt.rindex("$LASTEXITCODE") < txt.rindex("Write-Host"),
   "...and the push's exit code before the word: a commit that is local and a remote that does "
   "not have it are different states, and only one of them is 'pushed'")
ck("refusing to report a push that did not happen" in txt
   and txt.index("refusing to report a push that did not happen") < txt.index("git -C $csrbt push"),
   "AND THE POST-CONDITION, not only the exit code: this slice's own manifest must be in HEAD "
   "afterwards, which is the one thing that is true if and only if the commit happened -- an exit "
   "code is what the tool says about itself and this is what the repository says about it")
_esc = D.ps_quote(u'he said "tight" and \u201ccurly\u201d here')
ck('`"tight`"' in _esc and "'curly'" in _esc
   and not any(ch in _esc for ch in D.CURLY),
   "A STRAIGHT QUOTE IS ESCAPED AND A TYPOGRAPHIC ONE IS NOT SENT AT ALL. ADR-217's first answer "
   "was to CURL the straight quote, and the curly one turned out to delimit a PowerShell string "
   "too -- and unlike the straight one it cannot be backtick-escaped, so the argument ended at "
   "the opening curly quote and git read the rest as pathspecs. Same failure, one character "
   "further along: %r" % _esc)
# A RULE WITH NO VIOLATOR CANNOT SHOW THAT IT FIRES (ADR-207). A manifest that
# quotes a phrase with a space is written into the fixture directory and --check
# is required to name it -- and one that quotes a phrase WITHOUT a space is not,
# because six manifests in this kit do exactly that and pushed cleanly.
_SPACED = dict(MAN, id="adr995",
               subject=u'ADR-995: a subject quoting "two words" in it')
_TIGHT = dict(MAN, id="adr994",
              subject=u'ADR-994: a subject quoting "oneword" in it')
_CURLY = dict(MAN, id="adr993",
              subject=u"ADR-993: a subject quoting \u201coneword\u201d in it")
write_manifest(_SPACED)
write_manifest(_TIGHT)
write_manifest(_CURLY)
D.write_script("adr995")
D.write_script("adr994")
D.write_script("adr993")
_probs = D.check()
ck(any("adr993" in b and "typographic double quote" in b for b in _probs),
   "A TYPOGRAPHIC DOUBLE QUOTE IS REFUSED WHATEVER IS INSIDE IT, because it cannot be escaped: %s"
   % [b for b in _probs if "adr993" in b])
ck(any("adr995" in b and "quoted phrase with a SPACE" in b for b in _probs),
   "A MANIFEST THAT QUOTES A PHRASE WITH A SPACE IN IT IS REFUSED: %s"
   % [b for b in _probs if "adr995" in b])
ck(not any("adr994" in b and "quoted phrase with a SPACE" in b for b in _probs),
   "...AND ONE THAT QUOTES A PHRASE WITHOUT A SPACE IS NOT. Six manifests in this kit quote "
   '"_in", "buttons" and "3e" and every one of them pushed cleanly: the quote characters do not '
   "survive PowerShell's re-quoting, git re-splits on whitespace, and an argument with no "
   "whitespace inside its quotes comes out the far side unharmed. The rule is the mechanism, not "
   "a blanket ban: %s" % [b for b in _probs if "adr994" in b])
for _m in ("adr995", "adr994", "adr993"):
    os.remove(os.path.join(D.MANIFESTS, _m + ".json"))
    os.remove(os.path.join(D.PUSH, "push-%s.ps1" % _m))

# ---- A2. a script that pushes once (ADR-184) ---------------------------------
# push-adr182.ps1 run a second time committed ADR-183's changes to the paths the
# two slices share under ADR-182's message, and left ADR-183's own files behind.
# A manifest that says "once" generates a guard: the slice's own manifest in
# HEAD's tree means it was committed, and from then on the script pushes an
# undelivered commit or does nothing. The fixture cannot run PowerShell, so the
# guard is held by its text -- where it sits, what it asks git, what it does.
ck("$mine = git" not in txt and "already pushed" not in txt,
   "a manifest that does not ask for it gets no ONCE guard -- and the check is for the guard "
   "rather than for the words `ls-tree HEAD`, because ADR-217 gave EVERY script a post-condition "
   "that asks git the same question for a different reason: every script before ADR-184 still "
   "generates byte for byte")
ONCE = dict(MAN, id="adr996", chain="adr999", chain_probe="tools/one.py", once=True,
            paths=["tools/one.py", "tools/delivery/adr996.json", "tools/delivery_ledger.json"], clean=[])
write_manifest(ONCE)
otxt = D.script_text(ONCE)
_head = otxt.split("git -C $csrbt add -A")[0]
ck('$mine = git -C $csrbt ls-tree HEAD -- tools/delivery/adr996.json' in _head,
   "the guard asks whether the slice's OWN manifest is in HEAD's tree -- the one file that is "
   "this slice's and no later one's -- and asks with ls-tree, which prints the entry or nothing "
   "and writes no stderr for a Stop preference to trip on")
ck("ls-tree HEAD" in _head and "& $prev" in _head and _head.find("ls-tree HEAD") < _head.find("& $prev"),
   "...and asks BEFORE the chain runs the previous script and before anything is staged: a "
   "second run must touch nothing")
ck('if ([int]$ahead -gt 0) { Write-Host "adr996 is committed but not pushed -- pushing"; git -C $csrbt push;' in otxt
   and 'rev-list --count "@{u}..HEAD"' in otxt,
   "a commit the push never delivered is the one thing a second run may finish: it counts the "
   "commits ahead of upstream and pushes them")
ck('Write-Host "adr996 is already pushed -- nothing to do (modified paths belong to a later slice; run its script)"; exit 0' in otxt
   and otxt.count("exit 0") == 2,
   "otherwise it says so and exits 0 -- the modified paths it lists are a later slice's, and it "
   "names where to go")
ck(otxt.split("if ($mine) {")[1].split("}")[0].count("git -C $csrbt add") == 0
   and "git -C $csrbt add -A" in otxt.split("if ($mine) {")[1],
   "nothing inside the guard stages a path; the add and the commit come after it, for a first run")
ck(D.script_text(ONCE) == otxt, "the guarded script is as deterministic as the plain one")
os.remove(os.path.join(D.MANIFESTS, "adr996.json"))

# ---- B. --check -------------------------------------------------------------
ck(D.check() == [], "a good manifest with its generated script beside it is clean: %s" % D.check())

io.open(sp, "a", encoding="utf-8").write("# a hand edit\n")
bad = D.check()
ck(any("edited by hand" in b for b in bad),
   "a script edited by hand is a FAILURE, not a silent divergence: this is the exact shape of "
   "the bug -- two lists that agreed once and stopped: %s" % bad)
D.write_script("adr999")

m2 = dict(MAN, paths=MAN["paths"] + ["tools/never_written.py"])
write_manifest(m2)
D.write_script("adr999")
bad = D.check()
ck(any("not there" in b and "never_written" in b for b in bad),
   "a manifest naming a file that is not there fails: the commit would stage nothing for it and "
   "say so in no way the operator would read: %s" % bad)
write_manifest(MAN)
D.write_script("adr999")

write_manifest(dict(MAN, id="somethingelse"), mid="adr999")
bad = D.check()
ck(any("not its filename" in b for b in bad),
   "a manifest whose id is not its filename fails -- everything downstream keys on the "
   "filename: %s" % bad)
write_manifest(MAN)

write_manifest(dict(MAN, chain="adr000"))
D.write_script("adr999")
bad = D.check()
ck(any("no manifest or script by that name" in b for b in bad),
   "a chain to a slice that does not exist fails, because a chain that silently does nothing is "
   "worse than no chain: %s" % bad)
write_manifest(MAN)
D.write_script("adr999")
ck(D.check() == [], "and it is clean again")

# ---- C. the bundle ----------------------------------------------------------
out = os.path.join(tmp, "adr999.tgz")
_o, paths = D.bundle("adr999", out)
names = sorted(n.split("/", 1)[1] for n in tarfile.open(out).getnames()
               if "/" in n and not n.endswith("/"))
want = sorted(set(MAN["paths"]) | {"tools/push/push-adr999.ps1"})
ck(names == want,
   "the tarball holds exactly the manifest's paths and the script that commits them -- the two "
   "lists cannot disagree because there is only one:\n  got  %s\n  want %s" % (names, want))

# ---- D. the audit -----------------------------------------------------------
r = AD.measure()
ck(sorted(r["undelivered"]) == ["tools/old.py", "tools/verify/verify_one.py"],
   "everything the ledger has never seen and no manifest claims is UNDELIVERED -- on disk, in no "
   "commit, and read as present by every other audit in the kit: %s" % r["undelivered"])
ck(sorted(r["claimed"]) == sorted(MAN["paths"]),
   "...and what a manifest claims is IN FLIGHT rather than undelivered, which is what makes this "
   "runnable during a slice: %s" % r["claimed"])
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    AD.main([])
said = buf.getvalue()
ck("tools/old.py" in said and "tools/verify/verify_one.py" in said,
   "...and they are NAMED in what it prints, because the worklist is the point: a count tells "
   "the operator that something is uncommitted and not which file to go and look at:\n%s" % said)
import re as _re
ck(not _re.search(r"^\s*\d+\s*/\s*\d+\b", said.strip().split("\n")[-1]),
   "the audit's last line -- the one run_all puts in its row -- is NOT in the shape run_all "
   "scores: written that way the kit's headline check count grew by 621 in one commit, because "
   "621 FILES were counted as 621 checks. A row that reads is worth having; a score that is not "
   "a score is not: %r" % said.strip().split("\n")[-1])
ck(AD.main([]) == 1, "an undelivered file fails with NO FLAG -- run_all runs an audit with no "
                     "arguments, and a check that only bit under --check would be a check "
                     "nothing ever ran")
ck(AD.main(["--check"]) == 1, "--check is accepted for symmetry, and refuses too")

D.record("adr999", adopt=["tools/old.py", "tools/verify/verify_one.py"])
r = AD.measure()
ck(r["undelivered"] == [] and "tools/old.py" in r["delivered"],
   "recording a delivery moves those files to delivered: %s" % r)
ck(AD.main([]) == 0, "and the audit passes")

put("tools/old.py", "old, but changed since it was handed over\n")
r = AD.measure()
ck(r["undelivered"] == ["tools/old.py"],
   "a file whose BYTES have changed since it was delivered is undelivered again -- the evidence "
   "is content, because there is no git here to ask: %s" % r["undelivered"])
ck(AD.main(["--ignore", "tools/old.py"]) == 2,
   "declaring a path outside delivery WITHOUT a reason is refused: a list of files this audit is "
   "choosing not to care about is only useful if every line says why")
ck(AD.main(["--ignore", "tools/old.py", "--reason", "a fixture, not a deliverable"]) == 0
   and D.load_ledger()["ignored"]["tools/old.py"] == "a fixture, not a deliverable",
   "...and with one, the reason is what is stored: %s" % D.load_ledger().get("ignored"))
ck(AD.measure()["undelivered"] == [] and AD.main([]) == 0,
   "an ignored path leaves the worklist: %s" % AD.measure()["undelivered"])

os.remove(os.path.join(tmp, "tools/verify/verify_one.py"))
r = AD.measure()
ck(r["gone"] == ["tools/verify/verify_one.py"] and AD.main([]) == 0,
   "a file delivered once and since removed is reported as GONE and is not a failure -- deleting "
   "a file is a thing a slice may do, and the commit that removes it is the operator's: %s" % r)

# the adoption is labelled as what it is
D.LEDGER = os.path.join(tmp, "tools", "adopt_ledger.json")
put("tools/three.py", "three\n")
D.main(["--adopt", "adr997"])
led = D.load_ledger()
ck(led["_adopted"]["by"] == "adr997" and "not evidence" in led["_adopted"]["why"],
   "an adoption says in the ledger that it is an adoption: seeding a ratchet from a tree "
   "believed to be committed is a baseline, not a measurement, and a reader must be able to "
   "tell: %s" % led.get("_adopted"))
ck("tools/one.py" not in led["paths"],
   "...and it does not adopt what a manifest CLAIMS -- adopting a slice's own work in flight "
   "would record as delivered exactly the files that have not been: %s"
   % sorted(led["paths"].keys()))

# ---- E. a claim expires when its slice ships (ADR-218) -----------------------
# THE ADR-207 SHAPE, EXACTLY. A slice ships. A later slice changes one of the
# files it named and does not name it. Until ADR-218 the first slice's manifest
# went on claiming the path, so this audit called the change "in flight" -- for
# ten slices, while origin/main failed verify_keep and every run here was green.
D.LEDGER = os.path.join(tmp, "tools", "delivery_ledger.json")
D.record("adr999")
ck("adr999" in (D.load_ledger().get("recorded") or []),
   "recording a slice says BY NAME that it is over: %s" % D.load_ledger().get("recorded"))
put("tools/one.py", "one, changed by a later slice that did not name it\n")
r = AD.measure(view=None)
ck("tools/one.py" in r["undelivered"] and "tools/one.py" not in r["claimed"],
   "WITHOUT GIT: a slice that has been recorded no longer claims its paths, so a later change to "
   "one of them is UNDELIVERED and not excused as in flight -- a claim that never ends covers "
   "every hot file in the kit within a month, and did: %s / %s"
   % (r["undelivered"], r["claimed"]))
ck(r["evidence"] == "ledger" and r["unshipped"] == [],
   "and the audit says which evidence it read and which slices are still open: %s, %s"
   % (r["evidence"], r["unshipped"]))
put("tools/one.py", "one\n")

E_CHECKS = 13
_git = shutil.which("git")
unverified = []
if not _git:
    unverified = ["ADR-218 git evidence, check %d of %d: there is no git on this machine to ask"
                  % (i + 1, E_CHECKS) for i in range(E_CHECKS)]
else:
    repo = tempfile.mkdtemp(prefix="delivery_git_")

    def g(*args):
        return subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True,
                              env=dict(os.environ, GIT_AUTHOR_NAME="f", GIT_AUTHOR_EMAIL="f@f",
                                       GIT_COMMITTER_NAME="f", GIT_COMMITTER_EMAIL="f@f",
                                       GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull))

    def rput(rel, text):
        p = os.path.join(repo, rel)
        if not os.path.isdir(os.path.dirname(p)):
            os.makedirs(os.path.dirname(p))
        io.open(p, "w", encoding="utf-8", newline="").write(text)

    for d in ("tools/delivery", "tools/push", "docs"):
        os.makedirs(os.path.join(repo, d))
    D.ROOT = AD.ROOT = repo
    D.MANIFESTS = os.path.join(repo, "tools", "delivery")
    D.PUSH = os.path.join(repo, "tools", "push")
    D.LEDGER = os.path.join(repo, "tools", "delivery_ledger.json")
    ck(AD.git_view(repo) is None,
       "a directory that is not a repository is NO EVIDENCE, never `clean`: the audit falls back "
       "to the ledger rather than reading the absence of git as the absence of changes")
    g("init", "-q")
    ck(AD.git_view(repo) is None,
       "...and neither is a repository with no commit in it yet")
    rput("tools/keep.py", "the emitter\n")
    rput("tools/other.py", "another file\n")
    rput("docs/page.html", "<p>a page</p>\n")
    SHIPPED = {"id": "adr206", "subject": "s", "body": "b",
               "paths": ["tools/keep.py", "tools/delivery/adr206.json"]}
    rput("tools/delivery/adr206.json", json.dumps(SHIPPED, indent=1) + "\n")
    D.write_script("adr206")
    g("add", "-A")
    g("commit", "-q", "-m", "adr206")
    v = AD.git_view(repo)
    ck(v is not None and v["dirty"] == set() and v["shipped"] == {"adr206"},
       "git is asked two things: which bytes are not HEAD's, and which manifests are in HEAD's "
       "tree -- the same fact a push script's own guard reads (ADR-184): %s" % v)
    r = AD.measure()
    ck(r["evidence"] == "git" and "tools/other.py" in r["delivered"] and r["undelivered"] == [],
       "WITH GIT, committed is delivered: a file HEAD holds is accounted for though no ledger has "
       "ever seen it, because the repository can be read and a ledger is only a memory of it: %s"
       % r["undelivered"])

    rput("tools/keep.py", "the emitter, with five more pages -- changed by ADR-207, named by no one\n")
    r = AD.measure()
    ck(r["undelivered"] == ["tools/keep.py"] and r["claimed"] == [],
       "THE FILE THAT NEVER LEFT: a shipped slice's manifest names it, a later slice changed it "
       "and named it nowhere, and it is UNDELIVERED -- it was `in flight` for ten slices: %s / %s"
       % (r["undelivered"], r["claimed"]))
    ck(AD.main([]) == 1, "and the audit fails on it, with no flag")

    OPEN = {"id": "adr207", "subject": "s", "body": "b",
            "paths": ["tools/keep.py", "tools/delivery/adr207.json", "tools/delivery_ledger.json"]}
    rput("tools/delivery/adr207.json", json.dumps(OPEN, indent=1) + "\n")
    r = AD.measure()
    ck(r["undelivered"] == [] and "tools/keep.py" in r["claimed"]
       and set(r["claimed"]) <= set(OPEN["paths"]) and r["unshipped"] == ["adr207"],
       "the slice that is OPEN names it and it is in flight -- the claim still works, it just "
       "has to come from a slice that has not shipped: %s by %s" % (r["claimed"], r["unshipped"]))
    rput("docs/new-page.html", "<p>new</p>\n")
    ck(AD.measure()["undelivered"] == ["docs/new-page.html"],
       "an UNTRACKED file nobody names is undelivered too; git status is asked for every "
       "untracked file, not for the directory that holds them")
    os.remove(os.path.join(repo, "docs/new-page.html"))

    bad = D.check()
    ck(any("adr206" in b and "--catch-up" in b for b in bad)
       and not any("adr207" in b and "--catch-up" in b for b in bad),
       "--check HOLDS THE STEP NOTHING HELD: a slice git says is committed and the ledger never "
       "recorded is a problem, and an open slice is not. `--record` was in every close and in no "
       "check, and it stopped at ADR-190 -- twenty-seven slices ago: %s" % bad)
    got = D.catch_up()
    led = D.load_ledger()
    ck(got is not None and led.get("recorded") == ["adr206"]
       and "tools/keep.py" not in led["paths"]
       and led["paths"]["tools/other.py"]["by"] == "HEAD"
       and led["paths"]["tools/delivery/adr206.json"]["by"] == "adr206"
       and led["paths"]["tools/other.py"].get("evidence") == "git",
       "--catch-up writes only what git vouches for: every path whose bytes ARE HEAD's, by the "
       "last shipped slice that names it or by HEAD; the slice marked over; and NOT the file "
       "that is modified -- this is evidence, where --adopt is a belief: %s / %s"
       % (got, sorted(led["paths"])))
    ck(not any("--catch-up" in b for b in D.check()),
       "and after it --check has nothing to say about the ledger: %s" % D.check())
    r = AD.measure(view=None)
    ck(r["undelivered"] == [] and "tools/keep.py" in r["claimed"],
       "the caught-up ledger agrees with git where git is taken away: the open slice's file is "
       "in flight and nothing else is owed: %s / %s" % (r["undelivered"], r["claimed"]))
    D.ROOT = AD.ROOT = tmp
    ck(D.catch_up() is None,
       "with no git to ask, --catch-up REFUSES: a catch-up without evidence is an adoption, and "
       "there is already a flag for that which says so in the ledger")
    shutil.rmtree(repo, ignore_errors=True)

# ---- F. a file the bridge will not write is installed by the command that pushes (ADR-223) ----
D.ROOT = AD.ROOT = tmp
D.MANIFESTS = os.path.join(tmp, "tools", "delivery")
D.PUSH = os.path.join(tmp, "tools", "push")
D.LEDGER = os.path.join(tmp, "tools", "delivery_ledger.json")
put("tools/ci/ci.yml", "on: push\n")
INST = {"id": "adr995", "subject": "s", "body": "b",
        "paths": ["tools/ci/ci.yml", "tools/delivery/adr995.json"],
        "install": [{"from": "tools/ci/ci.yml", "to": ".github/workflows/ci.yml"}]}
write_manifest(INST)
itxt = D.script_text(INST)
_copy = 'Copy-Item -Force (Join-Path $csrbt "tools\\ci\\ci.yml") (Join-Path $csrbt ".github\\workflows\\ci.yml")'
ck(_copy in itxt,
   "THE COMMAND THAT PUSHES INSTALLS IT: ADR-202 said its workflow `is copied into place by the "
   "same command that pushes the slice` and generated a script with no such step, so the path "
   "filter sat in tools/ci/ for fifteen slices and the workflow never changed:\n%s"
   % [l for l in itxt.split("\n") if "Copy-Item" in l])
ck(_copy in itxt and itxt.index(_copy) < itxt.index("git -C $csrbt add -A"),
   "...BEFORE the add, or the commit stages the old bytes")
_staged = itxt.split("git -C $csrbt add -A")[1].split("git -C $csrbt commit")[0]
ck(".github/workflows/ci.yml" in _staged,
   "...and the copy is STAGED, though the manifest's paths do not name it -- they cannot: the "
   "tarball is made from them, and the bridge refuses a tarball that writes there")
ck("install" not in MAN and "Copy-Item" not in D.script_text(MAN),
   "a manifest with nothing to install generates the script it always did")
D.write_script("adr995")
put(".github/workflows/ci.yml", "the old workflow\n")
_o, _paths = D.bundle("adr995", os.path.join(tmp, "adr995.tgz"))
ck(not any(".github" in n for n in tarfile.open(os.path.join(tmp, "adr995.tgz")).getnames()),
   "the tarball does NOT carry the installed path, though the file is there to be carried: %s" % _paths)
ck(not any("adr995" in b for b in D.check()), "a good install is clean: %s" % D.check())
for _bad, _say in ((dict(INST, install=[{"from": "tools/never.yml", "to": ".github/workflows/ci.yml"}]),
                    "which its paths do not name"),
                   (dict(INST, paths=INST["paths"] + [".github/workflows/ci.yml"]),
                    "both delivered and installed"),
                   (dict(INST, install=[{"from": "tools/ci/ci.yml", "to": "docs/ci.yml"}]),
                    "an ordinary path"),
                   (dict(INST, install=["tools/ci/ci.yml"]), "an install is {from, to}")):
    write_manifest(_bad)
    put(".github/workflows/ci.yml", "x\n")
    ck(any(_say in b for b in D.check()),
       "--check refuses an install that is wrong -- %s: %s" % (_say, [b for b in D.check() if "adr995" in b]))
os.remove(os.path.join(D.MANIFESTS, "adr995.json"))

print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, P + F + len(unverified)))
sys.exit(1 if F else 0)
