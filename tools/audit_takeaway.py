# -*- coding: utf-8 -*-
"""Which of a page's take-away channels survive publication -- and what it says.

This kit is READ AS PUBLISHED ARTIFACTS. Every audit in it drives `docs/` from a
`file://` URL in a browser this container owns, where a page-started download
works. The published page runs in a sandboxed frame that does not permit one:
`a.click()` on a `blob:` URL returns nothing, throws nothing, and downloads
nothing. ADR-138 found this shape once already -- every audit measured docs/, and
docs/ was fine -- and it is here again in a different channel.

Three controls of this kit hand their payload over by download and by no other
route. In the kit as anyone actually reads it, all three do nothing.

AND THE KIT HAD ALREADY WORKED THIS OUT. Two of the three carry a comment saying
so, word for word: "A hosted viewer can refuse a page-started download silently
-- no throw, no return value, nothing to test -- so a mark here would be the
exact ADR-203 defect one layer along". That reasoning is right, and it was used
to keep the OUTBOX honest. Then the same handler raised

    toast("bench.csv downloaded")

which is the sentence the outbox was spared from telling. The ledger was made
truthful and the thing the reader actually reads was not.

WHAT IS MEASURED

Every control `audit_outputs` counts as one that hands something over is pressed,
and the payloads are read back by their CHANNEL, which the door already records:

    clipboard / copy   survives publication -- a clipboard write reports failure
    print              survives publication
    download           DOES NOT -- a sandboxed frame refuses it silently

    CARRIES     at least one channel that survives publication
    STRANDED    its only channel is a download: nothing reaches the reader
    CLAIMS      STRANDED, and the page announced that the payload left

STRANDED is a ratchet per page. CLAIMS is not a ratchet: a page that tells a
reader their sheet is saved when it is not is the defect this kit exists to
refuse, and it fails on sight.

    python3 tools/audit_takeaway.py                 # the table and the worklist
    python3 tools/audit_takeaway.py --page cp-bench.html
    python3 tools/audit_takeaway.py --check         # symmetry; a rise fails either way
    python3 tools/audit_takeaway.py --raise-floors  # after a page is fixed, record it
    python3 tools/audit_takeaway.py --declare PAGE:KEY --reason "..."
"""
import argparse, glob, io, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import harness as H
import audit_states as S
import harness_plugin_page as PP
import audit_outputs as AO

LEDGER = os.path.join(HERE, "takeaway_ledger.json")

# THE CHANNELS THAT SURVIVE BEING PUBLISHED. Not a taste: a clipboard write
# returns a promise that rejects and an execCommand that returns false, and a
# print opens the reader's own dialog. A page-started download in a sandboxed
# frame does none of those -- it is the one channel that can fail with nothing
# to test, which is why it is the one that needs saying out loud.
PUBLISHABLE = frozenset(["clipboard", "copy", "print"])

# WHAT COUNTS AS THE PAGE CLAIMING THE PAYLOAD LEFT. Past tense about the
# transfer, not about the bytes: "downloaded", "saved", "exported to". A message
# that says what to do next, or that hedges, is not a claim.
CLAIMED = re.compile(r"\b(download(ed|ing)|sav(ed|ing)|export(ed)?|writ(ten)?)\b", re.I)
# ...unless it says the transfer might not have happened. A page that tells the
# reader the viewer may refuse it has not claimed anything.
HEDGED = re.compile(r"\b(if|may|might|unless|block\w*|refus\w*|instead|some viewers?)\b", re.I)


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
    return {"_comment": "Written by tools/audit_takeaway.py. Per page: the controls that hand "
                        "something over whose only channel is a download -- which a published "
                        "artifact refuses silently -- and whether the page claimed it left "
                        "(ADR-212).",
            "pages": {}}


def save(state):
    io.open(LEDGER, "w", encoding="utf-8").write(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def declared_of(state, name):
    return dict((k, v) for k, v in
                (state.get("pages", {}).get(name, {}).get("declared") or {}).items())


def claims(said):
    """Did any of these messages assert the payload left? -> the message, or None."""
    for m in said or []:
        t = (m or "").strip()
        if t and CLAIMED.search(t) and not HEDGED.search(t):
            return t[:120]
    return None


def measure(ctx, name, tasks_dir=None, budget=24):
    pg = ctx.new_page()
    try:
        url = "file://" + os.path.join(docs_dir(), name).replace(os.sep, "/")
        pg.goto(url, wait_until="domcontentloaded")
        pg.wait_for_timeout(250)
        plug = PP.PagePlugin(pg, name)
        pg.evaluate(S.OPEN_DETAILS_JS)
        S._settle(pg)
        seen = {}
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
            # The rule for what a button that hands something over IS belongs to
            # audit_outputs, and asking it is the whole point (ADR-141).
            for c in AO.candidates(snap):
                k = AO.key_of(c)
                if k in seen or left[0] <= 0:
                    continue
                left[0] -= 1
                rec = {"key": k, "label": c.get("label") or "", "kinds": [], "said": None}
                try:
                    # WHAT THIS PRESS SAID IS TAKEN FROM THE ACT, not read off the
                    # page afterwards. The door's own `activate` SPLICES the
                    # live-region log when it reports what the act said, so a
                    # message read after that call is already gone -- the first
                    # draft read it afterwards, found nothing, and reported three
                    # stranded controls and zero liars, which is the comfortable
                    # half of the truth.
                    _o, _m2, act = plug.execute("activate", {"selector": c["selector"]})
                    S._settle(pg)
                    rec["said"] = claims([m.get("text") if isinstance(m, dict) else m
                                          for m in ((act or {}).get("said") or [])])
                    _ok, _m, out = plug.execute("collect-output", {})
                    pays = out.get("payloads") or []
                    rec["kinds"] = sorted(set(p.get("k") for p in pays if p.get("k")))
                except Exception as exc:
                    rec["error"] = str(exc).split("\n")[0][:100]
                seen[k] = rec
            return None

        for _state, _r in S.each_state(pg, name, probe, entered=True):
            pass
        rows = [seen[k] for k in sorted(seen)]
        for r in rows:
            r["publishable"] = bool(set(r["kinds"]) & PUBLISHABLE)
            r["stranded"] = bool(r["kinds"]) and not r["publishable"]
        return {"buttons": rows,
                "stranded": [r["key"] for r in rows if r["stranded"]],
                "claims": [(r["key"], r["said"]) for r in rows if r["stranded"] and r["said"]]}
    except Exception as exc:
        return {"error": str(exc).split("\n")[0][:140], "buttons": [],
                "stranded": [], "claims": []}
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
            ctx = b.new_context(viewport=H.VIEWPORT, accept_downloads=True)
            ctx.set_offline(True)
            ctx.add_init_script(H.STUBS)
            out[name] = measure(ctx, name, tasks_dir)
            ctx.close()
        b.close()
    return out


def stranded(r, declared):
    return [k for k in r.get("stranded", []) if k not in declared]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="one page")
    ap.add_argument("--check", action="store_true",
                    help="accepted for symmetry with the kit's other ratchets; a page above its "
                         "ceiling exits non-zero with or without it")
    ap.add_argument("--raise-floors", action="store_true",
                    help="record today's reading as the ceiling wherever it is LOWER")
    ap.add_argument("--declare", metavar="PAGE:KEY",
                    help="declare one stranded control expected, with a reason (needs --reason)")
    ap.add_argument("--reason", default="", help="why it is right that nothing reaches the reader")
    ap.add_argument("--names", type=int, default=4, help="how many to name per row")
    ap.add_argument("--json", action="store_true", help="the whole reading, for a suite to read")
    a = ap.parse_args(argv)
    state = load()
    ledger = state.setdefault("pages", {})

    if a.declare:
        if ":" not in a.declare:
            print("--declare takes PAGE:KEY, e.g. 'cp-bench.html:bDown'")
            return 2
        page, key = a.declare.split(":", 1)
        if not a.reason.strip():
            print("declaring a stranded control expected needs --reason: a button that hands "
                  "nothing\nover where the kit is read is either a defect or a deliberate local-"
                  "only route,\nand only the reason says which")
            return 2
        ledger.setdefault(page, {}).setdefault("declared", {})[key] = a.reason.strip()
        save(state)
        print("%s: %s declared right to reach no published reader" % (page, key))
        return 0

    got = walk(a.page)
    if a.json:
        print(json.dumps(got, indent=1, sort_keys=True))
        return 0
    print("%-30s %6s %6s %6s   %s"
          % ("PAGE", "STRAND", "CLAIM", "hands", "controls whose only channel a published page refuses"))
    print("-" * 116)
    tot = dict(strand=0, claim=0, hands=0)
    above, lying, broken = [], [], []
    for name in sorted(got):
        r = got[name]
        if r.get("error"):
            broken.append((name, r["error"]))
            print("%-30s %6s %6s %6s   %s" % (name, "-", "-", "-", r["error"]))
            continue
        dec = declared_of(state, name)
        bad = stranded(r, dec)
        said = [(k, m) for k, m in r.get("claims", []) if k not in dec]
        n = len([b for b in r.get("buttons", []) if b.get("kinds")])
        tot["strand"] += len(bad)
        tot["claim"] += len(said)
        tot["hands"] += n
        if not n and not bad:
            continue
        e = ledger.setdefault(name, {})
        ceiling = e.get("ceiling")
        if ceiling is not None and len(bad) > ceiling:
            above.append((name, len(bad), ceiling, bad))
        if a.raise_floors and (ceiling is None or len(bad) < ceiling):
            e["ceiling"] = len(bad)
        e.update({"stranded": bad, "claims": said, "hands": n, "at": int(time.time())})
        if said:
            lying.append((name, said))
        mark = "  ABOVE CEILING %d" % ceiling if ceiling is not None and len(bad) > ceiling else ""
        print("%-30s %6d %6d %6d   %s%s"
              % (name, len(bad), len(said), n,
                 ", ".join(bad[:a.names]) + (" ..." if len(bad) > a.names else ""), mark))
    print("-" * 116)
    print("%-30s %6d %6d %6d   %s"
          % ("the kit", tot["strand"], tot["claim"], tot["hands"],
             "%d control(s) hand nothing to a reader of the published kit, %d of them say otherwise"
             % (tot["strand"], tot["claim"])))
    if not a.page:
        save(state)
    if lying:
        print("\n%d page(s) TELL THE READER A PAYLOAD LEFT THAT CANNOT LEAVE. A sandboxed frame "
              "refuses a\npage-started download silently -- no throw, no return value, nothing to "
              "test -- so the\nmessage is the only thing the reader has, and it is wrong. Say what "
              "is true, or give the\npayload a channel that survives publication:" % len(lying))
        for name, said in lying:
            for k, m in said:
                print("    %-24s %-14s %s" % (name, k, m))
    if above:
        print("\n%d page(s) strand more than they did:" % len(above))
        for name, now, ceiling, keys in above:
            print("    %-30s %d, ceiling %d: %s" % (name, now, ceiling, ", ".join(keys[:a.names])))
    return 1 if (above or lying or broken) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
