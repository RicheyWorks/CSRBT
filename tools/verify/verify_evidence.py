# -*- coding: utf-8 -*-
"""The evidence chain, end to end.

The kit acquired its first image on 2026-08-30 and immediately owed an answer to
a question it had never had to answer: HOW IS THE PICTURE STORED, and can that
be shown rather than claimed?

Four links, each checked here from the bytes rather than from the record:

  1. STORAGE      the file's sha256 is what the manifest says it is
  2. ADDRESSING   the filename carries the first 8 hex of that hash, so a file
                  that has been altered no longer matches its own name
  3. DESCRIPTION  every dimension and byte count in the manifest is re-derived
                  from the PNG header, never trusted
  4. PUBLICATION  the data: URI embedded in the page decodes to bytes IDENTICAL
                  to the stored file -- which is the link that actually matters,
                  because an artifact runs under a policy that blocks external
                  images, so what a reader sees is the copy inside the page and
                  nothing else

And two things it refuses to let the kit pretend. First, that a picture whose
creator is recorded in a manifest has been credited: if an entry names a creator,
the page that displays it has to name them too, where a reader will see it.
Second, that a file which carries no EXIF, no timestamp and no GPS can certify
where it was taken. The manifest must say so
in `self_certifying`, and a site attribution that rests on testimony has to be
labelled as testimony. Provenance by instrument and provenance by assertion are
different evidence, and the whole point of ADR-031 is that they never get to
read the same.

Run:  python3 tools/verify/verify_evidence.py
"""
import base64, glob, hashlib, io, json, os, re, struct, sys

# tools/verify/verify_evidence.py -> tools/verify -> tools -> repo root.
# The first draft stopped one level short and looked for tools/docs/evidence.
# It reported that as three clean failures rather than an empty pass, which is
# the ADR-106 rule doing its job on the very check that enforces it.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.path.join(ROOT, "docs")
EV = os.path.join(DOCS, "evidence")

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))

files = sorted(glob.glob(os.path.join(EV, "*.png")) + glob.glob(os.path.join(EV, "*.jpg")))
mpath = os.path.join(EV, "manifest.json")

ck("the evidence store exists", os.path.isdir(EV), EV)
ck("it holds at least one file -- an empty store is not a passing store",
   len(files) >= 1, len(files))
ck("the manifest exists", os.path.isfile(mpath), mpath)
if bad:
    print("-" * 70); print("%d passed, %d failed" % (ok, bad)); sys.exit(1)

man = json.load(io.open(mpath, encoding="utf-8"))["evidence"]
ck("every stored file has a manifest entry",
   all(os.path.basename(f) in man for f in files),
   [os.path.basename(f) for f in files if os.path.basename(f) not in man])
ck("and every manifest entry has a stored file",
   all(os.path.isfile(os.path.join(EV, n)) for n in man),
   [n for n in man if not os.path.isfile(os.path.join(EV, n))])

pages = {os.path.basename(p): io.open(p, encoding="utf-8").read()
         for p in glob.glob(os.path.join(DOCS, "*.html"))}

for name, e in sorted(man.items()):
    raw = open(os.path.join(EV, name), "rb").read()
    real = hashlib.sha256(raw).hexdigest()

    # 1. storage
    ck("%s: stored bytes hash to the recorded sha256" % name, real == e["sha256"], real)
    # 2. content addressing
    stem = os.path.splitext(name)[0].rsplit("-", 1)[-1]
    ck("%s: the filename carries the hash, so tampering breaks the name" % name,
       real.startswith(stem), (stem, real[:8]))
    # 3. description re-derived, not trusted
    ck("%s: recorded byte count matches the file" % name, len(raw) == e["bytes"], len(raw))
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", raw[16:24])
        ck("%s: recorded pixel dimensions match the PNG header" % name,
           (w, h) == (e["width"], e["height"]), (w, h))
    # 3b. the honesty clause
    has_meta = any(t in raw[:len(raw)] for t in (b"eXIf", b"tIME", b"tEXt", b"iTXt"))
    ck("%s: self_certifying reflects what the file actually carries" % name,
       bool(e.get("self_certifying")) == has_meta, (e.get("self_certifying"), has_meta))
    if not e.get("self_certifying"):
        ck("%s: a non-self-certifying file labels its site attribution as testimony" % name,
           "assert" in str(e.get("site_attribution", "")).lower(), e.get("site_attribution"))

    # 3c. PROVENANCE IS NOT JUST BYTES.
    # The first version of this store recorded a hash, a size and a subject, and
    # would have passed a file taken from someone else's work with nothing to say
    # whose it was. A store that can prove WHAT the bytes are but not WHOSE they
    # are has recorded half a provenance, and the missing half is the half with a
    # person in it. So: any file the repository did not itself create must name a
    # creator, a rights holder and a source, and the page that shows it must name
    # the creator on the page -- where a reader is, not only in a JSON file.
    if e.get("creator"):
        for field in ("credit", "rights_holder", "source"):
            ck("%s: credited work records %s" % (name, field), bool(e.get(field)), e.get(field))
        for page in e.get("used_by", []):
            if page.endswith(".html") and pages.get(page):
                ck("%s: %s names the creator on the page itself" % (name, page),
                   e["creator"] in pages[page], "creator absent from rendered page")

    # 4. publication -- the link that decides what a reader sees
    for page in e.get("used_by", []):
        if not page.endswith(".html"):
            continue
        src = pages.get(page)
        ck("%s: %s is present in the kit" % (name, page), src is not None, page)
        if src is None:
            continue
        m = re.search(r'data-evidence="%s"[^>]*?src="data:image/[a-z]+;base64,([A-Za-z0-9+/=]+)"'
                      % re.escape(name), src, re.S)
        ck("%s: %s embeds it as a data URI (an artifact cannot load an external image)"
           % (name, page), m is not None, "no matching <img>")
        if m:
            decoded = base64.b64decode(m.group(1))
            ck("%s: the embedded copy is BYTE-IDENTICAL to the stored file" % name,
               decoded == raw, "%d vs %d bytes" % (len(decoded), len(raw)))
            ck("%s: and the page's declared sha256 is the true one" % name,
               ('data-sha256="%s"' % real) in src, "declared hash absent or wrong")

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
