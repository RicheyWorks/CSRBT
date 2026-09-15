# -*- coding: utf-8 -*-
"""What a single tap can destroy, and whether the page asks first (ADR-209).

The gateway has raised DESTRUCTIVE on these controls since ADR-112. It is the
same rule ADR-153's outputs audit refuses to press, the same rule ADR-142 makes
a task declare a rung for, and the same rule `activate.destructive` publishes as
its own argument pool. Every layer of the harness treats "Clear trial" as an act
that needs permission.

THE PAGE DOES NOT. A tap clears the trial, empties the list, and says
"Cleared" -- on a phone, in a wet field, next to the Add button, with a thumb.
The door's classification never reaches the person doing the tapping.

This audit is the door's own rule, asked of the page: for every control the
gateway calls DESTRUCTIVE, press it with the page's own data in it and measure

    ASKS       a confirm() fired before anything went (the harness's stub
               records it, and answers true, so the loss is still measured)
    NOTHING    the page held the same number of records afterwards -- a chip
               that untoggles, a filter that clears, a button pressed on an
               empty sheet
    ONE        exactly one record went. Every list in this kit that can lose a
               row has an Undo beside it, and a rule that demanded a
               confirmation for every crossed-off chip would be the classifier
               crying wolf on its first day (ADR-112's phrase, its lesson)
    BULK       TWO OR MORE records went and nothing asked. The worklist.

WHAT A RECORD IS, and why it is not counted here: `read-report` already returns
`rows` -- the kit's own `.row2` convention, per host -- and the body rows of
every table it can read. Those are what a page holds. Counting them again with
a rule of this file's own would be a second copy that drifts, which is the
defect ADR-141 named and ADR-204, ADR-205, ADR-207 and ADR-208 each found again.

A RATCHET DOWNWARD, like every other in this kit. The ceiling is the number of
bulk removers a page may carry, it may not go up, and a control that is right to
take a sheet without asking is declared with a reason stored word for word.

    python3 tools/audit_destructive.py                  # the table and the worklist
    python3 tools/audit_destructive.py --page ethogram.html
    python3 tools/audit_destructive.py --check          # symmetry; a rise fails either way
    python3 tools/audit_destructive.py --raise-floors   # after a page is fixed, record it
    python3 tools/audit_destructive.py --declare PAGE:KEY --reason "..."
"""
import argparse, glob, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import harness as H
import audit_states as S
import harness_plugin_page as PP

LEDGER = os.path.join(HERE, "destructive_ledger.json")

# THE SAME POSITIVE RULE ADR-208 WROTE: a control the door does not press is not
# a control anybody taps. Read from the door's own pool rather than restated.
PRESSED = frozenset(PP.POOL_KINDS["activate"])

# HOW MANY RECORDS MAKE A LOSS WORTH ASKING ABOUT. Two, because one is what an
# Undo is for and every list in this kit that can lose a row has one, and
# because a rule that fired on a single crossed-off chip would be turned off
# within a week -- after which the sheet-clearing ones would be invisible again
# (ADR-205's lesson, written down where the number is).
BULK = 2


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
    return {"_comment": "Written by tools/audit_destructive.py. Per page: every control the "
                        "gateway calls DESTRUCTIVE, how many records one tap of it took, whether "
                        "the page asked first, and the ceiling the unasked bulk removers may not "
                        "rise above (ADR-209).",
            "pages": {}}


def save(state):
    io.open(LEDGER, "w", encoding="utf-8").write(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def declared_of(state, name):
    return dict((k, v) for k, v in
                (state.get("pages", {}).get(name, {}).get("declared") or {}).items())


def key_of(c):
    """A control's name, stable across re-stamps -- the same keying the outputs
    audit uses, from the other side: its id, else its label under its host."""
    return c.get("id") or ((c.get("host") + "/") if c.get("host") else "") + (c.get("label") or "?")


def entered(pg, has_task):
    """Has this page's own task run yet?

    A PAGE WITH A TASK IS MEASURED WITH ITS OWN DATA IN IT (ADR-153's rule, and
    here it is the whole measurement): the entry runs partway through the state
    walk, and a Clear pressed before it clears nothing. Written once and read by
    all three walks, so a mutant that removes it removes it everywhere -- the
    first draft had the same line three times and breaking one of them changed
    nothing any check could see."""
    return (not has_task) or getattr(pg, "_audit_entered", None) is not None


def removers(snap):
    """Every control the GATEWAY'S OWN RULE calls DESTRUCTIVE, that the door
    would press. Not a list kept here: `destroys` is the function the risk
    ladder raises on and the outputs audit refuses to press."""
    out = []
    for c in snap.get("controls", []):
        if c.get("kind") not in PRESSED:
            continue
        why = PP.destroys((c.get("label") or "").strip(), c.get("title") or "")
        if why:
            out.append((c, why))
    return out


# WHAT THE PAGE IS HOLDING, asked of the page's own autosave (ADR-209).
#
# The autosave already describes the page's state once -- that description is
# what a restore rebuilds from and what the outbox checksums, so it is the one
# thing in the page that is exercised on every save. KEEP 1.3.0 makes the live
# handle reachable, and this asks it.
#
# ROWS ON THE SCREEN ARE NOT RECORDS, which is why the first draft of this audit
# was wrong in both directions at once: a plate shown once in its list and once
# in a results table is ONE record counted twice, so a row remover read as a
# bulk delete; and a trait whose thirteen measurements live in a table the
# remove also empties read as the same size as the row itself.
#
# A record is an element of an array the page keeps, or a form field with
# something in it. Counted generically rather than per page, because a rule
# with a per-page shape in it is a rule that stops covering the page that
# changed.
KEPT_JS = """()=>{
  if (typeof KEEP === "undefined" || !KEEP || typeof KEEP.live !== "function") return null;
  var h = KEEP.live(); if (!h || typeof h.snapshot !== "function") return null;
  var b; try { b = h.snapshot(); } catch (e) { return null; }
  if (!b) return 0;
  var n = 0, seen = 0, k;
  /* A RECORD IS AN ELEMENT OF AN ARRAY THE PAGE KEEPS -- not a field of one.
     Counting the strings inside a record too made an Undo that pops a single
     measurement read as taking five, which is the same crying-wolf the row
     counting did, one layer in. */
  (function arrays(v, depth){
    if (v == null || depth > 6 || seen++ > 20000) return;
    if (Array.isArray(v)) { n += v.length;
      for (var i = 0; i < v.length; i++) arrays(v[i], depth + 1); return; }
    if (typeof v === "object") {
      for (var kk in v) if (Object.prototype.hasOwnProperty.call(v, kk)) arrays(v[kk], depth + 1);
    }
  })(b, 0);
  /* ...and a form field with something typed in it. The kappa pane of the
     ethogram keeps two observers' sequences in two textareas and no array at
     all; a rule that counted only arrays would score clearing both as nothing. */
  var f = b.fields;
  if (f && typeof f === "object" && !Array.isArray(f)) {
    for (k in f) if (Object.prototype.hasOwnProperty.call(f, k)
                     && String(f[k] == null ? "" : f[k]).trim() !== "") n += 1;
  }
  return n;
}"""


def kept(pg):
    try:
        return pg.evaluate(KEPT_JS)
    except Exception:
        return None


def records(rep):
    """The fallback, for a page with no autosave: `read-report`'s own answer --
    the kit's `.row2` rows per host, plus every table body row it can see. It
    over-reads a record the page shows twice, which is why the autosave is
    asked first."""
    n = 0
    for v in (rep.get("rows") or {}).values():
        try:
            n += int(v)
        except (TypeError, ValueError):
            pass
    for t in (rep.get("tables") or {}).values():
        rows = t if isinstance(t, list) else (t.get("rows") if isinstance(t, dict) else None)
        if isinstance(rows, list):
            # MINUS THE HEADER, which is a column of names and not a record. It
            # would cancel in a before/after comparison of a table that stays,
            # and it does not cancel for the one that matters: a table whose
            # last row goes takes its heading row off the page with it, and a
            # rule that counted the heading would score that as one record more
            # than the page ever held.
            n += max(0, len(rows) - 1)
    return n


def asked(pg):
    """Did the page ASK before it took anything? The harness's own stubs record
    every confirm/alert/prompt as a call and answer confirm with true, so the
    act still happens and the loss is still measured -- a rule that only knew
    the page had asked would not know whether asking stopped anything."""
    try:
        calls = pg.evaluate("()=>window.__H ? window.__H.calls.map(c=>c.k) : []") or []
    except Exception:
        return False
    return "confirm" in calls


def clear_calls(pg):
    try:
        pg.evaluate("()=>{ if(window.__H) window.__H.calls.length = 0; }")
    except Exception:
        pass


def report(plug):
    try:
        _ok, _m, out = plug.execute("read-report", {})
        return out or {}
    except Exception:
        return {}


def find_key(snap, key):
    for c in snap.get("controls", []):
        if key_of(c) == key:
            return c
    return None


def survey(pg, name, tasks_dir=None):
    """Pass one: every destructive control this page offers, in any state."""
    plug = PP.PagePlugin(pg, name)
    seen = {}

    has_task = S.task_for(name, tasks_dir) is not None

    def probe():
        if not entered(pg, has_task):
            return None
        try:
            snap = plug.observe(sensitive=True)
        except Exception:
            return None
        for c, why in removers(snap):
            k = key_of(c)
            if k not in seen:
                seen[k] = {"key": k, "label": c.get("label"), "host": c.get("host") or "",
                           "id": c.get("id") or "", "kind": c.get("kind") or "", "why": why}
        return None

    for _state, _r in S.each_state(pg, name, probe, entered=True):
        pass
    return seen


# ANSWERING NO (ADR-210).
#
# The harness's stub answers confirm() with TRUE, which is what makes the loss
# measurable: the act happens and the records that went can be counted. It also
# means the rule ADR-209 wrote only ever watched the YES path. A page can ask a
# question, ignore the answer and destroy anyway -- and that is worse than never
# asking, because it teaches the person that the question is noise. A refusal
# nobody has watched is not a refusal (ADR-127), and this is that rule arriving
# on the confirmation the previous slice put between a person and their morning.
SAY_NO = """()=>{ window.__H = window.__H || {calls:[]};
  window.confirm = function(m){ window.__H.calls.push({k:"confirm", a:[String(m).slice(0,200)]});
                                return false; }; }"""


def press_one(ctx, name, key, tasks_dir=None):
    """Pass two, in a page of its own: enter the page's data, find this one
    control wherever it lives, read what the page holds, press it once, and read
    again.

    A FRESH PAGE PER CONTROL, because the measurement is what one tap takes and
    a page that has already been cleared has nothing left to lose. The outputs
    audit can press every candidate on one page -- a second export is a second
    copy of the same file; a second Clear is nothing at all."""
    pg = ctx.new_page()
    try:
        url = "file://" + os.path.join(docs_dir(), name).replace(os.sep, "/")
        pg.goto(url, wait_until="domcontentloaded")
        pg.wait_for_timeout(250)
        plug = PP.PagePlugin(pg, name)
        found = [None]
        has_task = S.task_for(name, tasks_dir) is not None

        def probe():
            if found[0]:
                return None
            if not entered(pg, has_task):
                return None
            try:
                snap = plug.observe(sensitive=True)
            except Exception:
                return None
            c = find_key(snap, key)
            if c:
                found[0] = c
            return None

        for _state, _r in S.each_state(pg, name, probe, entered=True):
            if found[0]:
                break
        if not found[0]:
            return {"verdict": "unreachable", "why": "not on the page once its task had run"}
        kb = kept(pg)
        before = records(report(plug)) if kb is None else kb
        clear_calls(pg)
        try:
            plug.execute("activate", {"selector": found[0]["selector"]})
            S._settle(pg)
        except Exception as exc:
            return {"verdict": "unreachable", "why": str(exc).split("\n")[0][:110]}
        ka = kept(pg)
        after = records(report(plug)) if kb is None else (ka if ka is not None else before)
        out = {"asked": asked(pg), "before": before, "after": after,
               "read": "screen" if kb is None else "autosave",
               "loss": max(0, before - after)}
        if out["asked"]:
            out["said"] = said_no(ctx, name, key, tasks_dir, kb is None)
        return out
    finally:
        try:
            pg.close()
        except Exception:
            pass


def said_no(ctx, name, key, tasks_dir, screen):
    """The SAME press, on a page of its own, with the question answered NO.
    -> how many records went anyway."""
    pg = ctx.new_page()
    try:
        url = "file://" + os.path.join(docs_dir(), name).replace(os.sep, "/")
        pg.goto(url, wait_until="domcontentloaded")
        pg.wait_for_timeout(250)
        plug = PP.PagePlugin(pg, name)
        found = [None]
        has_task = S.task_for(name, tasks_dir) is not None

        def probe():
            if found[0]:
                return None
            if not entered(pg, has_task):
                return None
            try:
                snap = plug.observe(sensitive=True)
            except Exception:
                return None
            c = find_key(snap, key)
            if c:
                found[0] = c
            return None

        for _state, _r in S.each_state(pg, name, probe, entered=True):
            if found[0]:
                break
        if not found[0]:
            return None
        kb = None if screen else kept(pg)
        before = records(report(plug)) if screen else kb
        # installed AFTER the entry, because a replay that answered no to
        # everything would be a different entry, not the same one
        pg.evaluate(SAY_NO)
        try:
            plug.execute("activate", {"selector": found[0]["selector"]})
            S._settle(pg)
        except Exception:
            return None
        ka = None if screen else kept(pg)
        after = records(report(plug)) if screen else (ka if ka is not None else before)
        if before is None or after is None:
            return None
        return {"before": before, "after": after, "lost": max(0, before - after)}
    finally:
        try:
            pg.close()
        except Exception:
            pass


def verdict_of(m):
    if m.get("verdict"):
        return m["verdict"]
    if m.get("asked"):
        # A QUESTION WHOSE ANSWER CHANGES NOTHING IS NOT A QUESTION (ADR-210).
        said = m.get("said")
        if isinstance(said, dict) and said.get("lost", 0) > 0:
            return "ignores"
        return "asks"
    loss = m.get("loss", 0)
    if loss <= 0:
        return "nothing"
    if loss < BULK:
        return "one"
    return "bulk"


def walk(only=None, tasks_dir=None):
    from playwright.sync_api import sync_playwright
    out = {}
    names = [only] if only else pages()
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport=H.VIEWPORT)
        ctx.set_offline(True)
        ctx.add_init_script(H.STUBS)
        # EVERY MEASUREMENT STARTS FROM A CLEAN DEVICE.
        #
        # One control is pressed per page and every page shares this context, so
        # the autosave ADR-207 gave these pages carried a sheet from the
        # previous measurement into the next one: the same button read as taking
        # three records on one run and six on another, depending on how many
        # pages had been opened before it. The audit was measuring its own
        # history (ADR-155's defect, on storage instead of on a fill counter).
        # Cleared before the page's own scripts run, so a restore has nothing to
        # restore from -- clearing after load would race the restore.
        ctx.add_init_script("try{localStorage.clear();sessionStorage.clear();}catch(e){}")
        pg = ctx.new_page()
        for name in names:
            url = "file://" + os.path.join(docs_dir(), name).replace(os.sep, "/")
            try:
                pg.goto(url, wait_until="domcontentloaded")
                pg.wait_for_timeout(250)
                seen = survey(pg, name, tasks_dir)
            except Exception as exc:
                out[name] = {"error": str(exc).split("\n")[0][:140], "controls": []}
                continue
            recs = []
            for k in sorted(seen):
                rec = dict(seen[k])
                rec.update(press_one(ctx, name, k, tasks_dir) or {})
                rec["verdict"] = verdict_of(rec)
                recs.append(rec)
            out[name] = {"controls": recs}
        ctx.close()
        b.close()
    return out


# THE WORKLIST IS BOTH SHAPES (ADR-210). A control that takes a sheet without
# asking, and one that asks and takes it whatever the answer, are the same
# defect from the person's side -- and the second is worse, because the question
# teaches them that questions on this page mean something.
BAD = ("bulk", "ignores")


def bare(r, declared):
    return [c["key"] for c in r.get("controls", [])
            if c.get("verdict") in BAD and c["key"] not in declared]


def counts(r):
    c = {"asks": 0, "nothing": 0, "one": 0, "bulk": 0, "ignores": 0, "unreachable": 0}
    for x in r.get("controls", []):
        c[x.get("verdict", "unreachable")] = c.get(x.get("verdict", "unreachable"), 0) + 1
    return c


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="one page")
    ap.add_argument("--check", action="store_true",
                    help="accepted for symmetry with the kit's other ratchets; a page above its "
                         "ceiling exits non-zero with or without it")
    ap.add_argument("--raise-floors", action="store_true",
                    help="record today's reading as the ceiling wherever it is LOWER (this "
                         "ratchet runs downward)")
    ap.add_argument("--declare", metavar="PAGE:KEY",
                    help="declare one bulk remover right to take a sheet without asking, with a "
                         "reason (needs --reason)")
    ap.add_argument("--reason", default="", help="why it is right to ask nothing")
    ap.add_argument("--names", type=int, default=4, help="how many to name per row")
    ap.add_argument("--json", action="store_true", help="the whole reading, for a suite to read")
    a = ap.parse_args(argv)
    state = load()
    ledger = state.setdefault("pages", {})

    if a.declare:
        if ":" not in a.declare:
            print("--declare takes PAGE:KEY, e.g. 'ethogram.html:tClear'")
            return 2
        page, key = a.declare.split(":", 1)
        if not a.reason.strip():
            print("declaring a bulk remover exempt needs --reason: a control that takes a sheet "
                  "without\nasking is either a defect or a judgement, and only the reason says "
                  "which")
            return 2
        ledger.setdefault(page, {}).setdefault("declared", {})[key] = a.reason.strip()
        save(state)
        print("%s: %s declared right to ask nothing" % (page, key))
        return 0

    got = walk(a.page)
    if a.json:
        print(json.dumps(got, indent=1, sort_keys=True))
        return 0
    print("%-30s %6s %6s %6s %6s %6s   %s"
          % ("PAGE", "BARE", "asks", "one", "none", "n", "what one tap takes without asking"))
    print("-" * 116)
    tot = dict(bare=0, asks=0, one=0, nothing=0, n=0)
    above = []
    for name in sorted(got):
        r = got[name]
        if r.get("error"):
            print("%-30s %6s %6s %6s %6s %6s   %s"
                  % (name, "-", "-", "-", "-", "-", r["error"]))
            continue
        if not r.get("controls"):
            continue
        dec = declared_of(state, name)
        bad = bare(r, dec)
        c = counts(r)
        tot["bare"] += len(bad)
        tot["n"] += len(r["controls"])
        for k in ("asks", "one", "nothing"):
            tot[k] += c.get(k, 0)
        e = ledger.setdefault(name, {})
        ceiling = e.get("ceiling")
        if ceiling is not None and len(bad) > ceiling:
            above.append((name, len(bad), ceiling, bad))
        if a.raise_floors and (ceiling is None or len(bad) < ceiling):
            e["ceiling"] = len(bad)
        e.update({"bare": bad, "controls": len(r["controls"]), "counts": c,
                  "at": int(time.time())})
        mark = "  ABOVE CEILING %d" % ceiling if ceiling is not None and len(bad) > ceiling else ""
        worst = sorted((x for x in r["controls"] if x["key"] in bad),
                       key=lambda x: -x.get("loss", 0))
        print("%-30s %6d %6d %6d %6d %6d   %s%s"
              % (name, len(bad), c.get("asks", 0), c.get("one", 0), c.get("nothing", 0),
                 len(r["controls"]),
                 ", ".join("%s (-%d)" % (x["key"], x.get("loss", 0)) for x in worst[:a.names]),
                 mark))
    print("-" * 116)
    print("%-30s %6d %6d %6d %6d %6d   %s"
          % ("the kit", tot["bare"], tot["asks"], tot["one"], tot["nothing"], tot["n"],
             "%d of %d destructive control(s) take two or more records on one tap and ask nothing"
             % (tot["bare"], tot["n"])))
    if not a.page:
        save(state)
    if above:
        print("\n%d page(s) let one tap take a sheet with no question asked. The gateway has "
              "called\nthese controls DESTRUCTIVE since ADR-112 -- a task must declare a rung to "
              "reach one,\nand the outputs audit refuses to press one -- while the page next to "
              "the thumb\nasks nothing. Give it a confirmation, or say why it is right as it is:\n"
              "    python3 tools/audit_destructive.py --declare PAGE:KEY --reason \"...\""
              % len(above))
        for name, now, ceiling, keys in above:
            print("    %-30s %d, ceiling %d: %s" % (name, now, ceiling, ", ".join(keys[:a.names])))
    return 1 if above else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
