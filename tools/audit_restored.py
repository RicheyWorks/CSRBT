# -*- coding: utf-8 -*-
"""What the page said before the tab closed, and what it says when it comes back.

ADR-207 gave seventeen pages an autosave, so that closing a tab stops costing a
morning. It also created a state of every one of those pages that NOTHING IN
THIS HARNESS HAS EVER LOOKED AT: the page as it comes back.

That state is not the page the audits measure. The audits open a page, replay
its task and measure what is in front of them; a restored page is built by a
different path -- `restore()`, running against a blob, in whatever order that
function happens to paint. ADR-207 found one instance of the difference by hand:
the experiment guide's restored design came back WITHOUT ITS MEASUREMENT ROWS,
because those rows are built from what is in two boxes and the paint ran before
the boxes were filled. That was one page, found by looking. Nothing checks the
other sixteen.

WHAT IS MEASURED, AND HOW

The page is opened, its own task is replayed (the same entry every other audit
makes), the autosave is FLUSHED rather than waited on, and then the tab is
reloaded onto the same storage. Two readings of `read-report`, before and after:

    by        every named figure and its value
    boxes     every named block and the prose in it

and the comparison is over the keys and the values the page itself publishes --
not over a list of what each page ought to bring back, which would be one more
list to keep in step with seventeen pages.

    SAME        every figure and block came back, saying what it said
    LOST        a key the entered page had and the restored page does not, or
                one whose value changed. The worklist.
    NORESTORE   the autosave did not come back at all -- the page reports no
                restore, so the reading is about the instrument, not the page

WHAT CHANGES ON PURPOSE IS DECLARED. A strip that says "saved 4 minutes ago"
SHOULD read differently after a reload, and a rule that called that a loss would
be turned off in a week. Those are named in the ledger with a reason, one line
each, the same shape as audit_readable's furniture and the mutant ledger's known
equivalents.

    python3 tools/audit_restored.py                 # the table and the worklist
    python3 tools/audit_restored.py --page releve.html
    python3 tools/audit_restored.py --check         # symmetry; a rise fails either way
    python3 tools/audit_restored.py --raise-floors  # after a page is fixed, record it
    python3 tools/audit_restored.py --declare PAGE:KEY --reason "..."
"""
import argparse, glob, importlib.util, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import harness as H
import exempt as X
import audit_states as S
import harness_plugin_page as PP

LEDGER = os.path.join(HERE, "restored_ledger.json")

# THE PAGES THAT KEEP, read from the emitter that inlines the autosave rather
# than from a list here -- a page wired tomorrow is covered tomorrow, which is
# the rule ADR-204, ADR-205, ADR-207 and ADR-208 each found broken in turn.
_spec = importlib.util.spec_from_file_location("keep_emit", os.path.join(HERE, "keep_emit.py"))
_ke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ke)
KEEPERS = list(_ke.CONSUMERS)

FLUSH_JS = """()=>{
  try { var h = (typeof KEEP !== "undefined" && KEEP.live) ? KEEP.live() : null;
        if (h && h.flush) { h.flush(); return true; } } catch(e){}
  return false;
}"""
# A PANE IS A CONTAINER, NOT A REPORT. `read-report` names a block whose id ends
# in `out` as a box, and the kit's Export pane is `p-out` -- so a page whose
# autosave strip sits inside that pane reported the PANE as having come back
# different, on top of the strip itself. What is inside a pane is compared on
# its own; comparing the pane too is counting the same difference again under
# the name of whatever happens to contain it.
PANES_JS = """()=>[...document.querySelectorAll("section.pane[id]")].map(e=>e.id)"""

RESTORED_JS = """()=>{
  try { var h = (typeof KEEP !== "undefined" && KEEP.live) ? KEEP.live() : null;
        return !!(h && h.restored && h.restored()); } catch(e){ return false; }
}"""


# WHAT IS SUPPOSED TO COME BACK DIFFERENT.
#
# Three blocks on these pages exist to say WHAT JUST HAPPENED, and a reload is a
# thing that just happened: the autosave strip goes from "saved a moment ago" to
# "restored from this device", the outbox strip recomputes what has not left,
# and the toast holds whatever the last act said. A rule that called those a
# loss would be switched off within a week, and then the analyses that really do
# go missing would be invisible again -- which is ADR-205's lesson, and the
# reason this list is three lines long and each one says why.
#
# It is a list in this file rather than a declaration per page because the claim
# is about the COMPONENT, not about seventeen pages that happen to mount it: a
# page wired tomorrow gets the same judgement without anybody remembering to
# repeat it.
STATUS = {
    "keepBox": "the autosave's own strip: it says when it saved, and after a reload it says "
               "it restored. Reading differently is the whole point of it.",
    "sendBox": "the outbox's own strip: it recomputes what has not left this device against the "
               "sheet as it now stands, and a restored sheet is a new comparison.",
    "toast":   "the transient line that holds whatever the last act said. A reload had no last "
               "act.",
}


def docs_dir():
    return os.environ.get("CSRBT_DOCS_DIR") or os.path.join(ROOT, "docs")


def load():
    if os.path.isfile(LEDGER):
        try:
            return json.load(io.open(LEDGER, encoding="utf-8"))
        except ValueError:
            pass
    return {"_comment": "Written by tools/audit_restored.py. Per page: what read-report said "
                        "after the page's own task ran, what it said after the tab was reloaded "
                        "onto the autosave, and the ceiling the differences may not rise above "
                        "(ADR-210).",
            "pages": {}}


def save(state):
    io.open(LEDGER, "w", encoding="utf-8").write(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def declared_of(state, name):
    return X.declared_of(state, name)


def flat(rep):
    """One dict of everything the page publishes under a name: its figures and
    the prose of its blocks. Keyed as `by/<box>/<label>` and `box/<id>`, which
    is how the ledger names a loss."""
    out = {}
    for box, vals in (rep.get("by") or {}).items():
        if isinstance(vals, dict):
            for lab, v in vals.items():
                out["by/%s/%s" % (box, lab)] = v
    for box, txt in (rep.get("boxes") or {}).items():
        out["box/%s" % box] = txt
    return out


def report(plug):
    try:
        _ok, _m, out = plug.execute("read-report", {})
        return out or {}
    except Exception:
        return {}


def measure(ctx, name, tasks_dir=None):
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
    try:
        url = "file://" + os.path.join(docs_dir(), name).replace(os.sep, "/")
        pg.goto(url, wait_until="domcontentloaded")
        pg.wait_for_timeout(250)
        plug = PP.PagePlugin(pg, name)
        has_task = S.task_for(name, tasks_dir) is not None

        def probe():
            return None

        for _state, _r in S.each_state(pg, name, probe, entered=True):
            pass
        if has_task and getattr(pg, "_audit_entered", None) is None:
            return {"error": "the page's own task did not replay"}
        # FLUSHED, NOT WAITED ON. The autosave is debounced; a sleep long enough
        # to be safe on a slow run is a second of every page's measurement spent
        # doing nothing, and a sleep that is short on one is a page reported as
        # keeping nothing.
        if not pg.evaluate(FLUSH_JS):
            return {"error": "no live autosave handle -- is KEEP wired on this page?"}
        before = flat(report(plug))
        pg.reload(wait_until="domcontentloaded")
        pg.wait_for_timeout(400)
        S._settle(pg)
        plug2 = PP.PagePlugin(pg, name)
        restored = bool(pg.evaluate(RESTORED_JS))
        after = flat(report(plug2))
        lost = sorted(k for k, v in before.items()
                      if k not in after or after[k] != v)
        try:
            panes = set(pg.evaluate(PANES_JS) or [])
        except Exception:
            panes = set()
        lost = [k for k in lost
                if k.split("/")[1] not in STATUS and k.split("/")[1] not in panes]
        keys = [k for k in sorted(before)
                if k.split("/")[1] not in STATUS and k.split("/")[1] not in panes]
        return {"restored": restored, "before": len(before), "after": len(after),
                "keys": keys, "lost": lost, "errors": errs[:3]}
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
    names = [only] if only else KEEPERS
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport=H.VIEWPORT)
        ctx.set_offline(True)
        ctx.add_init_script(H.STUBS)
        # Each page starts from a clean device and keeps its own storage across
        # its own reload -- the context is shared, so without this the reading
        # would carry the previous page's sheet (ADR-209's defect, next door).
        for name in names:
            c2 = b.new_context(viewport=H.VIEWPORT)
            c2.set_offline(True)
            c2.add_init_script(H.STUBS)
            out[name] = measure(c2, name, tasks_dir)
            c2.close()
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
    ap.add_argument("--declare", metavar="PAGE:KEY",
                    help="declare one difference expected, with a reason (needs --reason)")
    ap.add_argument("--reason", default="", help="why it is right to come back different")
    ap.add_argument("--names", type=int, default=4, help="how many to name per row")
    ap.add_argument("--json", action="store_true", help="the whole reading, for a suite to read")
    a = ap.parse_args(argv)
    state = load()
    ledger = state.setdefault("pages", {})

    if a.declare:
        if ":" not in a.declare:
            print("--declare takes PAGE:KEY, e.g. 'releve.html:box/keepBox'")
            return 2
        page, key = a.declare.split(":", 1)
        try:
            X.declare(state, page, key, a.reason)
        except ValueError:
            print("declaring a difference expected needs --reason: a page that comes back saying "
                  "something\nelse is either broken or right, and only the reason says which")
            return 2
        save(state)
        print("%s: %s declared right to come back different" % (page, key))
        return 0

    got = walk(a.page)
    if a.json:
        print(json.dumps(got, indent=1, sort_keys=True))
        return 0
    print("%-30s %6s %6s %6s   %s"
          % ("PAGE", "LOST", "said", "back", "what the page no longer says when it comes back"))
    print("-" * 116)
    tot = dict(lost=0, said=0, back=0)
    above, broken = [], []
    for name in sorted(got):
        r = got[name]
        if r.get("error"):
            broken.append((name, r["error"]))
            print("%-30s %6s %6s %6s   %s" % (name, "-", "-", "-", r["error"]))
            continue
        dec = declared_of(state, name)
        e = ledger.setdefault(name, {})
        bad = X.apply(e, r.get("lost", []), dec, r.get("keys", []))      # ADR-224
        tot["lost"] += len(bad)
        tot["said"] += r.get("before", 0)
        tot["back"] += r.get("after", 0)
        ceiling = e.get("ceiling")
        if ceiling is not None and len(bad) > ceiling:
            above.append((name, len(bad), ceiling, bad))
        if a.raise_floors and (ceiling is None or len(bad) < ceiling):
            e["ceiling"] = len(bad)
        e.update({"lost": bad, "said": r.get("before", 0), "back": r.get("after", 0),
                  "restored": r.get("restored"), "at": int(time.time())})
        mark = "  ABOVE CEILING %d" % ceiling if ceiling is not None and len(bad) > ceiling else ""
        note = "" if r.get("restored") else "  NO RESTORE"
        print("%-30s %6d %6d %6d   %s%s%s"
              % (name, len(bad), r.get("before", 0), r.get("after", 0),
                 ", ".join(bad[:a.names]) + (" ..." if len(bad) > a.names else ""), note, mark))
    print("-" * 116)
    print("%-30s %6d %6d %6d   %s"
          % ("the kit", tot["lost"], tot["said"], tot["back"],
             "%d thing(s) the pages said before the tab closed and do not say when it comes back"
             % tot["lost"]))
    if not a.page:
        save(state)
    if above:
        print("\n%d page(s) come back saying less than they said. A page that keeps your morning "
              "and\nthen redraws it differently has kept the bytes and lost the work -- and the "
              "restored\npage is built by a path no audit walks. Fix it, or say why it is right "
              "to differ:\n"
              "    python3 tools/audit_restored.py --declare PAGE:KEY --reason \"...\""
              % len(above))
        for name, now, ceiling, keys in above:
            print("    %-30s %d, ceiling %d: %s" % (name, now, ceiling, ", ".join(keys[:a.names])))
    return 1 if (above or broken) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
