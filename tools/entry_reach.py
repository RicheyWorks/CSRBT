# -*- coding: utf-8 -*-
"""How much of a page's data a task actually enters (ADR-144).

Every one of the 41 routed pages has a task, and 21 of them are science tasks
that enter data and hold the page's report to a hand-checked oracle. That
answers "can the harness enter data on this page?" with a yes. It has never
answered the question underneath, which is the one the standing goal actually
asks: **how much of the data?**

The stand sheet carries 220 controls. Its task drives 25 steps. Those 25 steps
are checked to the last digit -- and the other fields are not entered by
anything, so a field that silently drops what you type, or a figure that only
goes wrong when the third column is filled, is not something any suite here
could notice. A page's report can be correct about what was entered and wrong
about everything else, and "21 science tasks, all green" says nothing about the
difference.

This measures it, per page:

    ENTERABLE   controls that CARRY A VALUE -- text, fields, pickers, steppers,
                sliders, selects, checkboxes, file inputs, and the choice
                controls (dial options, chips, key options, swatches). Not
                Add/Save/Clear: pressing those is not entering data, it is
                doing something with data.
    ENTERED     the enterable controls the page's own entry task actually acted
                on, by the durable data-audit stamp, recorded as the entry runs.

    python3 tools/entry_reach.py                 # the table, and the kit total
    python3 tools/entry_reach.py --page stand-sheet.html
    python3 tools/entry_reach.py --check         # non-zero if a page fell below its floor
    python3 tools/entry_reach.py --raise-floors  # after a task grows, record the new floors
    python3 tools/entry_reach.py --lower stand-sheet.html --reason "..."

WHY A RATCHET AND NOT A TARGET

A target ("every page must enter 80%") would be a number invented here, and the
pages differ honestly: a reference page has no data to enter, and a key with 40
mutually exclusive options cannot have all 40 entered in one pass. What CAN be
said without inventing anything is that a page's coverage must not silently go
DOWN -- the same rule the engine ledger uses for tests (ADR-139). A floor per
page, raised deliberately, lowered only with a reason that goes into the ledger.

WHAT THIS IS NOT

It is not a claim that an entered field is entered CORRECTLY -- that is the
task's oracle, and it is the task's business. It is not a claim that an
un-entered field is broken. It is the worklist: these are the fields nothing in
this kit has ever put a value into, named, per page, so the number that grows is
the one that matters.
"""
import argparse, glob, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import harness as H
import audit_states as S

LEDGER = os.path.join(HERE, "entry_ledger.json")

# A control carries a value, or it does not. These are the plugin's own kinds
# (harness.KINDS), split by that question and by nothing else.
ENTERABLE = ("text_in", "field_in", "pick_search", "step_val", "step_btn", "select",
             "slider", "checkbox", "file_in", "drop_zone",
             "pick_opt", "dial_btn", "chip", "kopt", "ck", "cv", "swc")
# ...and these do something WITH data, or only show it. `readonly_out` is the
# swarm's own name for "a display, not a control"; `link` and `nav_link` go
# somewhere. Every kind harness.KINDS discovers is on one side of this line or
# the other, and verify_entry_reach holds it to that: a kind on neither list
# would be silently outside the accounting.
NOT_ENTERABLE = ("action_btn", "nav_link", "tab", "link", "readonly_out")

# A CHOICE IS ONE FIELD, NOT FORTY (ADR-144). The first reading of the stand
# sheet said "10 of 157", and 157 counted every chip and every key option
# separately -- so a page whose task picks one of four shapes and one of 34
# regions looked like a page ignoring 37 fields. Mutually exclusive choices
# under one host are ONE field, entered when any member of the group is; a text
# box, a stepper, a slider, a select, a checkbox is one field on its own. The
# raw control count is kept beside it, because both numbers are true and they
# answer different questions.
CHOICE_KINDS = ("pick_opt", "dial_btn", "chip", "kopt", "ck", "cv", "swc")

STAMP_KINDS = r"""
() => {
  const out = {};
  document.querySelectorAll("[data-h][data-audit]").forEach(e => {
    // A FEK widget is one field, whatever it is made of: a stepper is a minus,
    // a value and a plus; a slider is a rail and a readout; a picker is a
    // search box and its options. Entering the value enters the field, and
    // counting the minus button as a field nobody ever filled is counting the
    // same field three times (ADR-144).
    const w = e.closest(".fek-step, .fek-slide, .fek-pick, .fek-dial, .fek-swatch");
    let group = null;
    if (w) {
      const cls = (w.className || "").split(/\s+/).filter(Boolean)[0];
      if (cls) {
        const all = [...document.querySelectorAll("." + cls)];
        group = cls + "#" + all.indexOf(w);
      }
    }
    out[e.getAttribute("data-audit")] = {
      kind: (e.getAttribute("data-h") || "").split(":")[0],
      group: group,
      host: (e.parentElement && e.parentElement.closest("[id]") || {}).id || null};
  });
  return out;
}
"""


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
    return {"_comment": "Written by tools/entry_reach.py. Per page: how many of the controls that "
                        "CARRY A VALUE the page's own entry task acted on, and the floor that "
                        "reading may not fall below. A floor is raised deliberately and lowered "
                        "only with a reason (ADR-144, the ADR-139 rule applied to data entry).",
            "pages": {}}


def save(state):
    io.open(LEDGER, "w", encoding="utf-8").write(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def measure(pg, name, tasks_dir=None):
    """-> {"task", "enterable", "entered", "missed": [names], "driven", "steps"}.

    The page is walked the way the audits walk it, because a control behind a
    tab is enterable too, and the entry is replayed by audit_states.enter --
    one definition of "the entry", shared with the three audits that already
    use it (the LABEL_FN lesson, ADR-142)."""
    try:
        from swarm import SWARM_KINDS as _KINDS
    except Exception:
        _KINDS = H.KINDS

    def note():
        """Stamp both identities and record what is on the page right now.

        BOTH, and in this order. The kind of a control comes from the plugin's
        `data-h` and its durable identity from the audit's `data-audit`, and the
        first draft of this walked the states while stamping only the second --
        so `seen` was empty until the entry ran and the whole state walk
        contributed nothing to the universe it exists to build."""
        try:
            pg.evaluate(H.DISCOVER, _KINDS)
            pg.evaluate(S.MARK_JS, S.CONTROLS)
            seen.update(pg.evaluate(STAMP_KINDS))
        except Exception:
            pass

    pg.evaluate(S.OPEN_DETAILS_JS)
    S._settle(pg)
    seen = {}
    note()
    for _state, _r in S.each_state(pg, name, note, entered=False):
        pass
    ent = S.enter(pg, name, tasks_dir=tasks_dir)
    note()
    universe = dict((k, v) for k, v in seen.items() if v.get("kind") in ENTERABLE)
    touched = (ent or {}).get("touched") or {}
    # A CONTROL THAT WAS ENTERED AND THEN VANISHED IS STILL A FIELD THAT WAS
    # ENTERED. A character key removes the options it has answered, so the
    # kopt the entry pressed is not on the page at the end -- and counting only
    # what survives made cp-characters read "0 of 4 entered" about a task that
    # answers the key. Anything the entry touched is folded into the universe
    # with the kind it had at the moment it was touched.
    for stamp, kind in touched.items():
        if kind in ENTERABLE and stamp not in universe:
            universe[stamp] = {"kind": kind, "group": None, "host": None}

    def field_of(stamp, meta):
        """The FIELD a control belongs to: its widget, its choice group, or itself.

        A choice with no host is ITSELF, not a group. Controls the page has
        since removed are folded in with no host at all, and keying those by
        "kopt@?" put every answered option of every key into one field -- so a
        task that answered two questions was counted as having entered one."""
        if meta.get("group"):
            return "widget:" + meta["group"]
        if meta.get("kind") in CHOICE_KINDS and meta.get("host"):
            return "%s@%s" % (meta["kind"], meta["host"])
        return stamp

    fields = {}
    for stamp, meta in universe.items():
        fields.setdefault(field_of(stamp, meta), []).append(stamp)
    done = set(f for f, members in fields.items() if any(m in touched for m in members))
    missed = sorted(f for f in fields if f not in done)
    # name a field by its first member, which is a control the reader can find
    def naming(members):
        """Name a field by the member that says most. A stepper's minus button
        and its value input are the same field, and "button(-)" tells a reader
        nothing about which field was never filled."""
        ranked = sorted(members, key=lambda m: (universe[m].get("kind") == "step_btn", m))
        return ranked[0]

    names = []
    if missed:
        pick_ = [naming(fields[f]) for f in missed[:400]]
        try:
            names = pg.evaluate(S.NAME_JS, pick_)
        except Exception:
            names = pick_
    return {"task": (ent or {}).get("task"),
            "fields": len(fields), "entered": len(done),
            "controls": len(universe), "touched": len([k for k in universe if k in touched]),
            "missed": names, "driven": (ent or {}).get("driven", 0),
            "steps": (ent or {}).get("steps", 0),
            "kinds": sorted(set(v.get("kind") for v in universe.values()))}


def walk(only=None, tasks_dir=None):
    from playwright.sync_api import sync_playwright
    out = {}
    names = [only] if only else pages()
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport=H.VIEWPORT)
        ctx.set_offline(True)
        ctx.add_init_script(H.STUBS)
        pg = ctx.new_page()
        for name in names:
            try:
                pg.goto("file://" + os.path.join(docs_dir(), name).replace(os.sep, "/"),
                        wait_until="domcontentloaded")
                pg.wait_for_timeout(250)
                out[name] = measure(pg, name, tasks_dir)
            except Exception as exc:
                out[name] = {"error": str(exc)[:120], "enterable": 0, "entered": 0, "missed": []}
        ctx.close()
        b.close()
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="one page")
    ap.add_argument("--check", action="store_true",
                    help="accepted for symmetry with the kit's other ratchets; a page below its "
                         "floor exits non-zero with or without it")
    ap.add_argument("--raise-floors", action="store_true",
                    help="record today's reading as the floor wherever it is higher")
    ap.add_argument("--lower", metavar="PAGE", help="lower one page's floor (needs --reason)")
    ap.add_argument("--reason", default="", help="why a floor is being lowered")
    ap.add_argument("--names", type=int, default=6, help="how many un-entered controls to name")
    a = ap.parse_args(argv)
    state = load()
    ledger = state.setdefault("pages", {})

    if a.lower:
        e = ledger.get(a.lower)
        if not e:
            print("no floor recorded for %s" % a.lower)
            return 2
        if not a.reason.strip():
            print("lowering a floor needs --reason: it goes into the ledger")
            return 2
        e.setdefault("lowered", []).append({"at": int(time.time()), "from": e.get("floor", 0),
                                            "reason": a.reason.strip()})
        e["floor"] = 0
        save(state)
        print("%s: floor cleared, and the reason is in the ledger" % a.lower)
        return 0

    got = walk(a.page)
    print("%-30s %8s %7s %9s   %s"
          % ("PAGE", "ENTERED", "FIELDS", "controls", "the fields nothing has ever filled"))
    print("-" * 108)
    tot_e = tot_n = tot_c = tot_t = 0
    below = []
    for name in sorted(got):
        r = got[name]
        if r.get("error"):
            print("%-30s %8s %7s %9s   %s" % (name, "-", "-", "-", r["error"]))
            continue
        tot_e += r["entered"]
        tot_n += r["fields"]
        tot_c += r["controls"]
        tot_t += r["touched"]
        e = ledger.setdefault(name, {"floor": 0})
        floor = e.get("floor", 0)
        if r["entered"] < floor:
            below.append((name, r["entered"], floor))
        if a.raise_floors and r["entered"] > floor:
            e["floor"] = r["entered"]
        e.update({"entered": r["entered"], "fields": r["fields"], "controls": r["controls"],
                  "touched": r["touched"], "task": r["task"], "at": int(time.time())})
        mark = "  BELOW FLOOR %d" % floor if r["entered"] < floor else ""
        print("%-30s %8d %7d %9d   %s%s"
              % (name, r["entered"], r["fields"], r["controls"],
                 ", ".join(r["missed"][:a.names]) + (" ..." if len(r["missed"]) > a.names else ""),
                 mark))
    print("-" * 108)
    print("%-30s %8d %7d %9d   %s"
          % ("the kit", tot_e, tot_n, tot_c,
             "%.0f%% of the fields that carry a value have ever had one put in them "
             "(%d of %d controls)"
             % (100.0 * tot_e / tot_n if tot_n else 0, tot_t, tot_c)))
    if not a.page:
        save(state)
    if below:
        print("\n%d page(s) entered FEWER fields than before. A task that stopped entering a field "
              "is a\nfield nothing checks any more:" % len(below))
        for name, now, floor in below:
            print("    %-30s %d, floor %d" % (name, now, floor))
    # A RATCHET FAILS BY DEFAULT, like the engine ledger's (ADR-139). run_all
    # runs an audit with no arguments, so a floor that only bit under --check
    # would be a floor nothing ever checked.
    return 1 if below else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
