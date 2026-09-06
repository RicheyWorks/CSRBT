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

Run:  python3 tools/verify/verify_delivery.py
"""
MUTATE_ROLE = "subject"
import contextlib, io, json, os, subprocess, sys, tarfile, tempfile

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

print("---")
print("%d/%d" % (P, P + F))
sys.exit(1 if F else 0)
