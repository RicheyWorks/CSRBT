# -*- coding: utf-8 -*-
"""What the page works out, and whether any of it can leave the device.

ADR-153 asked whether anything READS what a page hands over, and ADR-208 asked
whether a button that is supposed to hand something over hands anything over at
all. Both are questions about the CHANNEL. Neither one opens the envelope.

This is the question inside it: OF THE FIGURES A PAGE COMPUTES AND PUTS ON THE
SCREEN, HOW MANY COME OUT WHEN YOU PRESS EXPORT?

It is the whole point of these pages. A relevé sheet is filled in a wet field on
a phone and then has to become a row in somebody's analysis; an ethogram session
is scored once and then argued about for a year. The screen is where the work is
done and the export is the only thing that survives the tab. A page that renders
a correct analysis and exports half of it has lost the half it did not export,
and every audit in this kit was green while it happened -- `read-report` sees the
figure, `audit_outputs` sees the button, `audit_readable` sees that the figure is
legible, `verify_restored` sees that it comes back after a reload. Nobody ever
put the two readings side by side.

Put side by side, 135 of the 317 figures nineteen exporting pages compute were
in no export at all. The ethogram was the clearest: three exports of a scored
session -- the interval CSV, the .eco sheet, the time-budget CSV -- and Cohen's
kappa, the raw agreement and the agreement expected by chance, the entire panel
that says whether the session is worth anything, in none of them. The soil bench
exported its mix recipe and none of the fourteen figures of its compost log.

WHAT IS MEASURED, AND HOW

The page is opened, its own task is replayed -- the same entry `entry_reach`,
`audit_outputs` and `audit_restored` make, and necessary here for the same
reason: an export pressed on an empty page carries nothing, and every figure
would read as lost for a reason that is about the audit. Then every control the
gateway itself would press and whose name says it hands something over is
pressed (the rule is `audit_outputs.candidates`, not a second copy of it), the
payloads are collected, and `read-report` is asked what the page is showing.

    CARRIED   the number the page shows is in at least one payload
    LOST      it is in none of them -- the worklist

A FIGURE IS MATCHED AS A NUMBER, NOT AS A STRING, and that is most of the work
in this file. `6.00x10^5` on screen is `600000` in a CSV; `1,234` is `1234`;
`25%` is `25`; a minus sign may be U+2212 and an exponent may be superscript
digits. A string comparison called all of those losses -- 171 rather than 135 --
and an audit that reports a third more losses than exist is an audit that gets
switched off. So both sides are parsed to floats and compared at the precision
the PAGE displays: a page showing 0.72 is carried by an export saying 0.7217.

THE BIAS IS TOWARDS CARRIED, ON PURPOSE. A bare `4` in a figure matches any `4`
anywhere in any payload, including a row count that has nothing to do with it.
So this under-reports: every LOST here is a figure whose value appears NOWHERE
in anything the page hands over, which is as close to certain as a measurement
of this shape gets. The direction matters -- a finder that cries wolf is worse
than one that misses -- and it is the reason this is a ratchet on a count rather
than a per-figure certificate.

WHAT IS NOT MEASURED. A page that hands nothing over is not measured here; that
is `audit_outputs`'s TRAP_ENTRY and its mute ratchet, and saying it twice in two
files is the defect ADR-141 keeps finding. Whether the exported value is RIGHT
is the task's business, as it is in ADR-153: this says the number left the page,
not that it is true.

    python3 tools/audit_carried.py                 # the table and the worklist
    python3 tools/audit_carried.py --page ethogram.html
    python3 tools/audit_carried.py --check         # symmetry; a rise fails either way
    python3 tools/audit_carried.py --raise-floors  # after a page is fixed, record it
    python3 tools/audit_carried.py --declare PAGE:LABEL --reason "..."
"""
import argparse, glob, io, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import harness as H
import exempt as X
import audit_states as S
import harness_plugin_page as PP
import audit_outputs as AO

LEDGER = os.path.join(HERE, "carried_ledger.json")

# Superscript digits and signs, because an exponent on these pages is written
# the way a journal writes it and a CSV writes it the way a parser reads it.
SUP = {u"⁰": "0", u"¹": "1", u"²": "2", u"³": "3", u"⁴": "4",
       u"⁵": "5", u"⁶": "6", u"⁷": "7", u"⁸": "8", u"⁹": "9",
       u"⁻": "-", u"⁺": "+"}

# One number, with the two things that say how precisely it was written: how
# many decimals the mantissa carries, and what exponent it is scaled by.
NUM = re.compile(r"-?\d+(?:\.(\d+))?(?:[eE]([-+]?\d+))?")


def normal(s):
    """One spelling of a number, so that the screen and the file can be compared.

    Everything here is a difference of NOTATION, never of value: a typographic
    minus for a hyphen, a thousands separator inside a number, superscript
    exponent digits, and `x10^n` for `en`. A rule that skipped this step reports
    a page as losing a figure it exported in full, which is the way an audit
    earns its exemption."""
    s = s or ""
    s = s.replace(u"−", "-").replace(u"×", "x").replace(u"–", "-")
    # A separator only BETWEEN DIGITS and only before a group of three: `1,234`
    # is one number and `12, 34` is two.
    s = re.sub(r"(?<=\d),(?=\d\d\d(?!\d))", "", s)
    s = "".join(SUP.get(ch, ch) for ch in s)
    s = re.sub(r"x\s*10\s*\^?\s*([-+]?\d+)", r"e\1", s)
    return s


def atoms(s):
    """Every number in `s`, each with the SIZE OF ITS OWN LAST DIGIT.

    Per number, not per figure, and reading the exponent as well as the decimals
    -- `2.83x10^2` is written to three significant figures, so its last digit is
    a whole unit, not a hundredth. A tolerance taken from the mantissa alone
    called the cell bench's 2.83x10^2 uM lost against a file carrying 2.834e+2,
    which is the same number written with one more figure."""
    out = []
    for m in NUM.finditer(normal(s)):
        dec = len(m.group(1) or "")
        exp = int(m.group(2) or 0)
        # A TOKEN IN A PAGE IS NOT ALWAYS A QUANTITY. A stand sheet carries
        # accession codes and checksums, and one of them parses as a number with
        # an exponent no float can hold: `10 ** (exp - dec)` raised OverflowError
        # and the whole page came back as an error rather than a reading. A
        # token that cannot be a figure on any of these pages is skipped, and
        # the page is still measured.
        if not (-300 < exp - dec < 300):
            continue
        out.append((float(m.group(0)), 10.0 ** (exp - dec)))
    return out


def nums(s):
    return [v for v, _g in atoms(s)]


def grain(txt):
    """The size of the last digit the PAGE shows -- its first number's. The
    comparison is made at the page's own precision, never at the export's: an
    export carrying 0.7217 has carried the 0.72 on the screen, and one carrying
    0.7 has not."""
    a = atoms(txt)
    return a[0][1] if a else 1.0


def carried(val, pool):
    """-> True (in a payload), False (in none), or None (no number in it).

    EVERY number in the figure has to be found, because a figure is often two --
    "3/3", "50 / 50", "0.61-1.41 kPa" -- and half of a ratio is not the ratio.

    MATCHED WITHIN THE SCREEN'S OWN LAST DIGIT, not by rounding both sides to it.
    The first draft rounded the export's number to the page's precision and
    compared: the greenhouse shows g/kWh at two places and exports it at three,
    and 4.8249 becomes 4.82 on screen and 4.825 in the file, which rounds back to
    4.83. The figure was carried in more detail than the page shows it and the
    audit called it lost -- DOUBLE ROUNDING, the shape ADR-087 and audit_ties are
    about, arriving in the instrument rather than in a page. So the test is
    distance: the exported number is within one unit of the last digit the page
    displays. An export carrying 0.7217 carries the 0.72 on the screen; one
    carrying 0.7 does not."""
    want = atoms(val)
    if not want:
        return None
    for w, tol in want:
        if not any(abs(p - w) < tol for p in pool):
            return False
    return True


def docs_dir():
    return os.environ.get("CSRBT_DOCS_DIR") or os.path.join(ROOT, "docs")


def pages():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(docs_dir(), "*.html")))


def load():
    if os.path.isfile(LEDGER):
        try:
            return json.load(io.open(LEDGER, encoding="utf-8"))
        except ValueError:
            pass
    return {"_comment": "Written by tools/audit_carried.py. Per page: how many of the figures it "
                        "computes appear in something it hands over, which ones do not, and the "
                        "ceiling that count may not rise above (ADR-211).",
            "pages": {}}


def save(state):
    io.open(LEDGER, "w", encoding="utf-8").write(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def declared_of(state, name):
    return X.declared_of(state, name)


def payloads(pg, plug, name, tasks_dir=None, budget=24):
    """Press every control that hands something over and keep what came out.

    WHICH CONTROLS THOSE ARE IS NOT DECIDED HERE. `audit_outputs.candidates` is
    the kit's rule -- a label that says it hands something over, minus whatever
    the gateway's own risk ladder calls destructive, minus any kind the door
    would not press -- and a second copy of it here would be the list ADR-204,
    205, 207, 208 and 210 each found drifting."""
    pg.evaluate(S.OPEN_DETAILS_JS)
    S._settle(pg)
    got = {}
    left = [budget]
    has_task = S.task_for(name, tasks_dir) is not None

    def probe():
        if left[0] <= 0:
            return None
        if has_task and getattr(pg, "_audit_entered", None) is None:
            return None
        try:
            snap = plug.observe(sensitive=True)
        except Exception:
            return None
        for c in AO.candidates(snap):
            k = AO.key_of(c)
            if k in got or left[0] <= 0:
                continue
            left[0] -= 1
            try:
                plug.execute("activate", {"selector": c["selector"]})
                S._settle(pg)
                _ok, _m, out = plug.execute("collect-output", {})
                got[k] = "\n".join(p.get("text") or "" for p in (out.get("payloads") or []))
            except Exception:
                got[k] = ""
        return None

    for _state, _r in S.each_state(pg, name, probe, entered=True):
        pass
    return got


def report(plug):
    try:
        _ok, _m, out = plug.execute("read-report", {})
        return out or {}
    except Exception:
        return {}


def measure(ctx, name, tasks_dir=None):
    pg = ctx.new_page()
    try:
        url = "file://" + os.path.join(docs_dir(), name).replace(os.sep, "/")
        pg.goto(url, wait_until="domcontentloaded")
        pg.wait_for_timeout(250)
        plug = PP.PagePlugin(pg, name)
        got = payloads(pg, plug, name, tasks_dir)
        blob = "\n".join(got.values())
        if not blob.strip():
            return {"exports": len(got), "figures": 0, "lost": [], "noexport": True}
        pool = nums(blob)
        figs = (report(plug).get("figures") or {})
        lost, labels = [], []
        for lab in sorted(figs):
            c = carried(figs[lab], pool)
            if c is None:
                continue
            labels.append(lab)
            if not c:
                lost.append(lab)
        return {"exports": len(got), "bytes": len(blob), "figures": len(labels),
                "labels": labels, "lost": lost, "noexport": False}
    except Exception as exc:
        return {"error": str(exc).split("\n")[0][:140]}
    finally:
        try:
            pg.close()
        except Exception:
            pass


def walk(only=None, tasks_dir=None):
    from playwright.sync_api import sync_playwright
    out = {}
    names = [only] if only else pages()
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for name in names:
            # Its own context, so that one page's autosave is not another page's
            # starting data -- ADR-209's defect, found next door.
            ctx = b.new_context(viewport=H.VIEWPORT)
            ctx.set_offline(True)
            ctx.add_init_script(H.STUBS)
            out[name] = measure(ctx, name, tasks_dir)
            ctx.close()
        b.close()
    return out


def losses(r, declared):
    return [k for k in r.get("lost", []) if k not in declared]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="one page")
    ap.add_argument("--check", action="store_true",
                    help="accepted for symmetry with the kit's other ratchets; a page above its "
                         "ceiling exits non-zero with or without it")
    ap.add_argument("--raise-floors", action="store_true",
                    help="record today's reading as the ceiling wherever it is LOWER")
    ap.add_argument("--declare", metavar="PAGE:LABEL",
                    help="declare one figure right to stay on the screen (needs --reason)")
    ap.add_argument("--reason", default="", help="why it is right that it never leaves")
    ap.add_argument("--names", type=int, default=4, help="how many to name per row")
    ap.add_argument("--json", action="store_true", help="the whole reading, for a suite to read")
    a = ap.parse_args(argv)
    state = load()
    ledger = state.setdefault("pages", {})

    if a.declare:
        if ":" not in a.declare:
            print("--declare takes PAGE:LABEL, e.g. 'releve.html:taxa in pack'")
            return 2
        page, key = a.declare.split(":", 1)
        try:
            X.declare(state, page, key, a.reason)
        except ValueError:
            print("declaring a figure right to stay needs --reason: a number the page works out "
                  "and\nnever lets you take is either a defect or a property of the reference "
                  "data, and\nonly the reason says which")
            return 2
        save(state)
        print("%s: %s declared right to stay on the screen" % (page, key))
        return 0

    got = walk(a.page)
    if a.json:
        print(json.dumps(got, indent=1, sort_keys=True))
        return 0
    print("%-30s %6s %6s %6s   %s"
          % ("PAGE", "LOST", "figs", "exp", "figures the page works out that no export carries"))
    print("-" * 116)
    tot = dict(lost=0, figs=0)
    above, broken = [], []
    for name in sorted(got):
        r = got[name]
        if r.get("error"):
            broken.append((name, r["error"]))
            print("%-30s %6s %6s %6s   %s" % (name, "-", "-", "-", r["error"]))
            continue
        if r.get("noexport"):
            continue
        dec = declared_of(state, name)
        e = ledger.setdefault(name, {})
        # ADR-224: the exemption is applied by the one function that also
        # records what it took out (raw) and what it could have (seen).
        bad = X.apply(e, r.get("lost", []), dec, r.get("labels", []))
        tot["lost"] += len(bad)
        tot["figs"] += r.get("figures", 0)
        ceiling = e.get("ceiling")
        if ceiling is not None and len(bad) > ceiling:
            above.append((name, len(bad), ceiling, bad))
        if a.raise_floors and (ceiling is None or len(bad) < ceiling):
            e["ceiling"] = len(bad)
        e.update({"lost": bad, "figures": r.get("figures", 0), "exports": r.get("exports", 0),
                  "at": int(time.time())})
        mark = "  ABOVE CEILING %d" % ceiling if ceiling is not None and len(bad) > ceiling else ""
        print("%-30s %6d %6d %6d   %s%s"
              % (name, len(bad), r.get("figures", 0), r.get("exports", 0),
                 ", ".join(bad[:a.names]) + (" ..." if len(bad) > a.names else ""), mark))
    print("-" * 116)
    print("%-30s %6d %6d %6s   %s"
          % ("the kit", tot["lost"], tot["figs"], "",
             "%d figure(s) these pages work out that nothing they hand over carries"
             % tot["lost"]))
    if not a.page:
        save(state)
    if above:
        print("\n%d page(s) work out more than they let you take. The screen is where the work is "
              "done\nand the export is the only part that survives the tab: a figure in neither "
              "is a figure\nthat has to be worked out again from scratch. Fix it, or say why it "
              "is right to stay:\n"
              "    python3 tools/audit_carried.py --declare PAGE:LABEL --reason \"...\""
              % len(above))
        for name, now, ceiling, keys in above:
            print("    %-30s %d, ceiling %d: %s" % (name, now, ceiling, ", ".join(keys[:a.names])))
    return 1 if (above or broken) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
