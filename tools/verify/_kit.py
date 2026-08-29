# -*- coding: utf-8 -*-
"""Shared helpers for the CSRBT verification suites.

The Field Entry Kit replaced the kit's bare <select>/<input> controls with
composed widgets that write through to hidden fields. That means a suite can no
longer drive a control with select_option() or fill() -- it has to do what a
finger does. These helpers do that, in one place, so a future FEK change is one
edit here rather than one per suite.
"""
import html.parser as _html_parser
import io, os, sys, re
from decimal import Decimal, ROUND_HALF_UP

# The boot loader every page in docs/ carries, byte-identical (ADR-066).
# It lives here rather than in the one suite that reads it because a second
# reader arrived -- tools/sweep_ledger.py, which needs to know whether a page's
# only mutable code IS this loader. Two copies of this pattern would drift, and
# a drifted pattern reports "not in the shape this suite reads" on a page that
# is fine (ADR-039).
LOADER = re.compile(r"<script>\(function\(\)\{var l=document\.querySelector\('link\[data-webfont\]'\);"
                    r".*?\}\)\(\);</script>", re.S)

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DOCS_DIR = os.path.join(ROOT, "docs") + os.sep
TOOLS_DIR = os.path.join(ROOT, "tools") + os.sep


def url(name):
    """file:// URL for a page in docs/, whatever the checkout is called."""
    return "file://" + os.path.join(ROOT, "docs", name).replace(os.sep, "/")


# ---- reading a page as text, and meaning one thing by it -------------------
#
# Four suites each rolled their own `re.sub(r"<[^>]+>", " ", src)`. That is a
# fine reader for prose and a bad one for a page: a page's JavaScript contains
# bare < and >, the regex pairs them off, and whole spans -- including prose --
# vanish. ADR-098 hit this writing an assertion about a widget's `help:` string,
# which is script content; ADR-099 measured it and found the reverse hazard as
# well: eleven live assertions that PASS only because the mangled JS is still in
# the haystack, their visibility decided by accidental bracket pairing somewhere
# else in the file.
#
# So there are two readers here and each says which view it means. A suite that
# wants what a reader SEES asks for prose(); one that wants what the file SAYS
# asks for raw(). Neither is a tag-stripper, and no assertion's verdict rests on
# where a stray `<` happened to fall. tools/audit_readers.py reports any
# assertion that still depends on the difference.

class _Prose(_html_parser.HTMLParser):
    """Text a reader would see: script and style dropped, entities left as the
    file writes them (`&nbsp;` stays `&nbsp;`), which is what the readers this
    replaces did and what the suites' assertions are written against."""

    def __init__(self):
        _html_parser.HTMLParser.__init__(self, convert_charrefs=False)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)

    def handle_entityref(self, name):
        if not self.skip:
            self.out.append("&" + name + ";")

    def handle_charref(self, name):
        if not self.skip:
            self.out.append("&#" + name + ";")


def page_src(name):
    """The file, verbatim."""
    return io.open(os.path.join(ROOT, "docs", name), encoding="utf-8").read()


def prose_of(src):
    """prose(), for a page a suite has already read or altered -- a footer
    window, a page with its session literal cut out. Same parse, so the two
    cannot disagree about what a reader sees."""
    p = _Prose()
    p.feed(src)
    p.close()
    return re.sub(r"\s+", " ", " ".join(p.out))


def prose(name):
    """What the page shows: markup resolved, script and style gone, whitespace
    collapsed. Tags join with a space, as the tag-stripper did, so an assertion
    written across a tag boundary reads the same as it always has."""
    return prose_of(page_src(name))


def raw(name):
    """What the file says, whitespace collapsed. For claims the page renders
    from script -- a widget's `help:` option -- which prose() cannot see and
    should not pretend to."""
    return re.sub(r"\s+", " ", page_src(name))


def tool(name):
    """Import a module out of tools/ and hand it back.

    Three suites used to read a probe out of a tool by SPLITTING its source on
    one literal sequence -- the letters of the constant's name followed by a
    raw-string opener. It broke twice in one hour (ADR-094): first a second
    constant whose name ended with that sequence, then the comment written to
    warn about the first. ADR-094 added a uniqueness check, said plainly that
    the coupling itself was the defect and that a suite could import the module
    instead, and left it. This is that import. A probe is now read by its NAME,
    which is what a name is for, and renaming one is a NameError rather than a
    silently wrong body.
    """
    import importlib
    if TOOLS_DIR.rstrip(os.sep) not in sys.path:
        sys.path.insert(0, TOOLS_DIR.rstrip(os.sep))
    return importlib.import_module(name)


def offline(pg):
    """The container has no DNS; an un-aborted webfont request stalls load."""
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())


def pick(pg, root, name):
    """Type into a FEK picker's filter and click the first match."""
    pg.evaluate("""([r,n])=>{const s=document.querySelector(r+' .search');
      if(!s) throw new Error('no picker search under '+r);
      s.value=n; s.dispatchEvent(new Event('input',{bubbles:true}));}""", [root, name])
    pg.wait_for_timeout(140)
    pg.evaluate("""(r)=>{const o=document.querySelector(r+' .opt');
      if(!o) throw new Error('no match under '+r); o.click();}""", root)
    pg.wait_for_timeout(160)


def setstep(pg, root, idx, val):
    """Set the nth FEK stepper under root, firing the input event readers expect."""
    pg.evaluate("""([r,i,v])=>{const s=[...document.querySelectorAll(r+' .fek-step .val')];
      if(!s[i]) throw new Error('no stepper '+i+' under '+r);
      s[i].value=String(v); s[i].dispatchEvent(new Event('input',{bubbles:true}));}""",
                [root, idx, val])
    pg.wait_for_timeout(130)


def hidden(pg, elid):
    """Read a hidden write-through field by id."""
    return pg.evaluate("(i)=>{const e=document.getElementById(i); return e?e.value:null;}", elid)


def options(pg, root):
    """Labels currently offered by a FEK picker."""
    return pg.evaluate("(r)=>[...document.querySelectorAll(r+' .opt')].map(o=>o.textContent.trim())", root)


def push(pg, elid, value):
    """Write a value into a FEK hidden write-through field exactly as the widget
    does -- set .value, then fire input AND change, because different readers on
    these pages listen for different ones.

    Driving the hidden field rather than the widget is a deliberate division of
    labour, not a shortcut: verify_cs proves the widget writes through to the
    field, so a suite about the science downstream of the field does not need to
    prove it a second time, and does not break when the widget is restyled.
    """
    pg.evaluate("""([i,v])=>{const e=document.getElementById(i);
      if(!e) throw new Error('no field #'+i);
      e.value=String(v);
      e.dispatchEvent(new Event('input',{bubbles:true}));
      e.dispatchEvent(new Event('change',{bubbles:true}));}""", [elid, value])
    pg.wait_for_timeout(120)


def as_page_shows(x, digits, scale=1):
    """The digits a kit page will display for `x * scale` at `digits` places.

    One implementation, here, because there are now three readers and they must
    not each choose a rounding rule. The pages format with toFixed(d) or
    Number(...).toLocaleString("en-US", {maximumFractionDigits: d}); both round
    HALF AWAY FROM ZERO on the double.

    Python's round() is half-to-EVEN, and on the kit's own recorded figures the
    two disagree. Measured, not supposed:

        K = 138.5   page shows 139   round() gives 138
        K =  40.5   page shows  41   round() gives  40

    A check that asserted round() there would contradict the page while looking
    correct, which is ADR-068's failure with the arithmetic moved one step out.
    So the rule the pages use is written down once and borrowed, never
    re-chosen.

    Rounding is applied to the DOUBLE, deliberately: the double is what the page
    has. Whether the exact decimal was a tie is a different question, and
    tools/audit_ties.py is where that one is asked.
    """
    v = float(x) * scale
    q = Decimal(1).scaleb(-digits)
    d = (Decimal(repr(v)) / q).to_integral_value(rounding=ROUND_HALF_UP) * q
    out = ("%.*f" % (digits, d)) if digits else "%d" % d
    return out.rstrip("0").rstrip(".") if digits and "." in out else out
