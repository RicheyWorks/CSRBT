# -*- coding: utf-8 -*-
"""Where typed text can reach a component option label, and where it cannot.

WHY THIS IS A MODULE AND NOT A SECTION OF A SUITE

Two questions used to live in one file, and ADR-055 already had to separate
them once: **reachability** is a property of the SOURCE, and **staleness** is a
property of the PUBLISHED COPY. The suite was rewritten to stop conflating them
and still kept both, which cost something nobody had noticed until ADR-070's
guards went in.

The staleness half compares each page against a digest, so it fails on ANY edit
to that page -- and a mutation sweep edits pages by construction. The sweep
therefore threw the WHOLE suite out on all five reachable pages, and the
escaping rules in sections 1 to 4, which are perfectly good witnesses, stopped
being able to testify about anything.

So the detector lives here, both suites import it, and neither has to
reimplement it -- because two copies of this tracer would drift, and a drifted
tracer fails OPEN: it calls typed input a constant (ADR-039).
"""
import io, os, re

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DOCS = os.path.join(ROOT, "docs")


# A label or sub-label written into a component option, anywhere in a page.
LABEL = re.compile(r'\b(?:label|sub)\s*:\s*"((?:[^"\\]|\\.)*)"')
ANGLE = re.compile(r"[<>]")

# An option list built from something other than an inline array literal.
#
# This used to require `.map(` at the options site itself, and that is how it
# missed selection-log: the page writes `options:opts`, and `opts` came from
# `traitOptions()` four lines up. The trait list is PUSHED to by the page's own
# "add trait" button, so typed text was reaching a component option label on a
# page this suite listed as safe. Any bare identifier counts now; an inline
# `options:[{...}]` still does not match, because `[` is not an identifier.
DYNAMIC = re.compile(r'options\s*:\s*([A-Za-z_$][\w$.]*)\s*(?:\.map\s*\(|[,}\n])')


ASSIGN = r"\b(?:var|let|const)\s+%s\s*=\s*([A-Za-z_$][\w$.\[\]]*)"
CALL = r"\b(?:var|let|const)\s+%s\s*=\s*([A-Za-z_$][\w$]*)\s*\("
# An ALL-CAPS name is the kit's convention for "a table the page authored". It
# is a convention, not a guarantee, and selection-log breaks it: `TRAITS` is
# ALL-CAPS and the "add trait" button PUSHES typed text into it. So the shape of
# the name is not the test -- whether anything writes to it is.
GROWS = r"\b%s\s*(?:\.(?:push|unshift|splice)\s*\(|=(?!=))"


def grows_at_runtime(name, src):
    """Does anything write to this table after it is declared?"""
    for m in re.finditer(GROWS % re.escape(name), src):
        before = src[max(0, m.start() - 12):m.start()]
        if re.search(r"\b(?:var|let|const)\s+$", before):
            continue                         # the declaration itself
        return True
    return False

def roots_in_constant(head, src, pos):
    """True if `head` at offset `pos` is an ALL-CAPS table, or reaches one.

    Scoped to the NEAREST PRECEDING binding, which is what a reader does. The
    first version searched the whole file for `var n=` and found
    `var n=parseFloat(x)` inside the FEK module -- a different `n`, hundreds of
    lines away, in another scope -- and concluded soil-bench was runtime data.
    A finder that matches the wrong binding is not a weaker check, it is a
    check of something else.
    """
    seen = set()
    while head and head not in seen:
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", head):
            return not grows_at_runtime(head, src)
        seen.add(head)
        call = [m for m in re.finditer(CALL % re.escape(head), src) if m.start() < pos]
        before = [m for m in re.finditer(ASSIGN % re.escape(head), src) if m.start() < pos]
        # A call binding wins when it is at least as near as a plain one.
        # `>=` and not `>`, because on `var opts = famOptions()` BOTH patterns
        # match at the same offset -- ASSIGN captures the callee's name as
        # though it were a variable, and with `>` the assignment branch won,
        # went looking for `var famOptions =`, found nothing, and reported a
        # page built entirely from a constant table as runtime data. On
        # `var opts = PACK.slice(...)` only ASSIGN matches, so the plain branch
        # still governs there.
        if before and not (call and call[-1].start() >= before[-1].start()):
            m = before[-1]                   # nearest preceding, not first in file
            pos = m.start()
            head = m.group(1).split(".")[0].split("[")[0]
            continue
        # One hop through a helper: `var opts = traitOptions()` and
        # `function traitOptions(){ return TRAITS.map(...) }`. Deliberately one
        # shape and one hop -- a general answer needs the JS parsed, and the
        # last attempt at that in this kit had to be withdrawn (ADR-062).
        # Everything that does not match this exact shape is treated as runtime
        # data, so the failure direction is a page NAMED that need not have
        # been, never a page missed.
        if not call:
            return False
        fn = call[-1].group(1)
        body = re.search(r"\bfunction\s+%s\s*\([^)]*\)\s*\{" % re.escape(fn), src)
        if not body:
            return False
        ret = re.search(r"\breturn\s+([A-Za-z_$][\w$.]*)", src[body.end():body.end() + 600])
        if not ret:
            return False
        pos = body.start()
        head = ret.group(1).split(".")[0].split("[")[0]
    return False



def angled_pages(pages):
    """{page: [labels]} for labels that CONTAIN angle brackets.

    Banning them would be wrong: "<2 m" is a legitimate stratum height. What
    matters is that the component escapes them, and that a page carrying them
    is known to be one where a stale published copy renders visibly wrong.
    """
    out = {}
    for p in pages:
        src = io.open(p, encoding="utf-8").read()
        hits = sorted({m.group(1) for m in LABEL.finditer(src) if ANGLE.search(m.group(1))})
        if hits:
            out[os.path.basename(p)] = hits[:6]
    return out


def runtime_pages(pages):
    """{page: [identifiers]} for option lists built from something that is not
    a page constant."""
    out = {}
    for p in pages:
        src = io.open(p, encoding="utf-8").read()
        for m in DYNAMIC.finditer(src):
            head = m.group(1).split(".")[0]
            if not roots_in_constant(head, src, m.start()):
                out.setdefault(os.path.basename(p), []).append(m.group(1))
    return out


def reachable(pages):
    """Pages where a STALE published copy would render text as markup."""
    return set(angled_pages(pages)) | set(runtime_pages(pages))
