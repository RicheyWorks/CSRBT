# -*- coding: utf-8 -*-
"""What each page PRODUCES, and whether its own task ever reads it (ADR-153).

ADR-152 found that `collect-output` -- the one action that reads what leaves a
page through a Copy button, a download or a print -- only worked for the robot,
and fixed it. It also counted what that had been hiding: 19 pages of this kit
carry 80 such buttons, and exactly one task read one of them.

In this kit the button IS the product. The collection sheet's Darwin Core
export, the experiment guide's .eco protocol, the ethogram's budget CSV, the
deployment log's "thing a reviewer asks for and the thing nobody writes down" --
the pages exist to hand somebody a file, and what the tasks hold is the figures
ON SCREEN. A page can render a correct analysis and export a wrong one, and
every suite in this kit would be green.

`entry_reach` measures how much of a page's data its own task ENTERS. This is
the other end of the same sentence: how much of what a page PRODUCES its own
task READS.

WHAT IS MEASURED, AND HOW

The page is walked through its states and entered with its own task -- the same
replay entry_reach and the other audits make, and necessary here, because an
export button on an empty page exports nothing and would read as silent for a
reason that is about the audit rather than the page. Then every control whose
NAME says it hands something over is pressed, and collect-output is asked what
came out:

    EMITS       a payload came back -- a copy, a download or a print
    SILENT      the button was pressed and nothing left the page
    HELD        it emits, AND the page's own task presses it and then calls
                collect-output
    BLIND       it emits, and no task has ever looked -- the worklist

WHAT COUNTS AS A BUTTON THAT HANDS SOMETHING OVER is its label: copy, download,
export, print, save. Not the payload -- a button is a candidate BEFORE it is
pressed or there is no experiment -- and not a hand-written list of control ids,
which would go stale the first time a page grew one.

A CONTROL NAMED FOR REMOVING SOMETHING IS NOT PRESSED. "Forget this device's
copy" matches `copy` and would be pressed by a naive verb list, and the answer
would be a lost autosave. The rule is not written twice: it is
`harness_plugin_page.destroys`, the same rule the gateway's own risk ladder
raises DESTRUCTIVE on, and this audit refuses whatever that refuses.

    python3 tools/audit_outputs.py                 # the table and the worklist
    python3 tools/audit_outputs.py --page ethogram.html
    python3 tools/audit_outputs.py --check         # symmetry; a rise fails either way
    python3 tools/audit_outputs.py --raise-floors  # after a page is fixed, record it
    python3 tools/audit_outputs.py --declare PAGE:LABEL --reason "..."

A RATCHET DOWNWARD. The floor is a CEILING on the number of outputs a page
emits that nothing reads. It may not go up: a page that grows an export no task
looks at fails the day it does. It comes down as tasks are extended.

WHAT THIS IS NOT

It is not a claim that a held export is CORRECT -- whether the bytes are right
is the task's business, and a task that calls collect-output and asserts nothing
about the payload would count as holding it here. It measures reach, the way
entry_reach does, and says so.

It is not a claim that a silent button is broken: a page with nothing to export
is right to export nothing, and the entry that ran before it is only as complete
as the page's own task.
"""
import argparse, glob, io, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import harness as H
import audit_states as S
import harness_plugin_page as PP

LEDGER = os.path.join(HERE, "outputs_ledger.json")

# A control that hands something over says so in its own name. Whole words, so
# that "Copy" matches and "Copyright" does not, plus the two file extensions
# this kit names buttons after.
HANDS_OVER = re.compile(r"\b(copy|download|export|print|save)\b|\.csv\b|\.eco\b", re.I)


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
    return {"_comment": "Written by tools/audit_outputs.py. Per page: the buttons that hand "
                        "something over, what came out of each, whether the page's own task "
                        "reads it, and the ceiling the unread count may not rise above "
                        "(ADR-153).",
            "pages": {}}


def save(state):
    io.open(LEDGER, "w", encoding="utf-8").write(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def declared_of(state, name):
    return dict((k, v) for k, v in
                (state.get("pages", {}).get(name, {}).get("declared") or {}).items())


def key_of(c):
    """A button's name, stable across re-stamps: its id if it has one, else its
    label under its host. data-h is kind:index and is re-issued every time the
    swarm discovers, so it names a different control in the next state."""
    return c.get("id") or ((c.get("host") + "/") if c.get("host") else "") + (c.get("label") or "?")


def candidates(snap):
    """The controls whose NAME says they hand something over, minus the ones
    the gateway's own risk rule would call DESTRUCTIVE."""
    out = []
    for c in snap.get("controls", []):
        label = (c.get("label") or "").strip()
        if not label or not HANDS_OVER.search(label):
            continue
        if PP.destroys(label, c.get("title") or ""):
            continue
        if c.get("kind", "").endswith("_in") or c.get("kind") in ("pick_search",):
            continue
        out.append(c)
    return out


def task_reads(task):
    """Which control names does this task press AND then read? -> set of names.

    A task holds an output when it presses the button and asks what came out.
    The selector grammar is `@control:<id | label | host/label>`, so the name
    is whatever follows the colon -- compared against the same name this audit
    keys a button by, from the other side."""
    if not task:
        return set(), set()
    pressed, read = set(), set()
    for s in task.get("steps", []):
        a = s.get("action")
        sel = (s.get("arguments") or {}).get("selector") or ""
        if a == "activate" and sel.startswith("@control:"):
            pressed.add(sel[len("@control:"):].split("#")[0])
        elif a == "collect-output":
            # WHAT HAS BEEN PRESSED SO FAR, not everything the task ever
            # presses. A collect-output reads the payloads waiting at that
            # moment, so a button pressed later in the task is not one this
            # call could have read.
            read |= pressed
    return pressed, read


def measure(pg, name, tasks_dir=None, budget=24):
    """-> {"task", "buttons": [...]}"""
    pg.evaluate(S.OPEN_DETAILS_JS)
    S._settle(pg)
    plug = PP.PagePlugin(pg, name)
    seen = {}
    left = [budget]
    has_task = S.task_for(name, tasks_dir) is not None

    def probe():
        if left[0] <= 0:
            return None
        # A PAGE WITH A TASK IS MEASURED WITH ITS OWN DATA IN IT. The states are
        # walked from rest, and an export pressed on an empty page hands over
        # the placeholder line the page shows when there is nothing to hand
        # over -- "# log a deployment - the sheet builds itself". That is a
        # payload, so the button would be recorded as emitting, with the empty
        # page's bytes, and never asked again. The entry runs partway through
        # the state walk and every state after it is a page with rows in it.
        if has_task and getattr(pg, "_audit_entered", None) is None:
            return None
        try:
            snap = plug.observe(sensitive=True)
        except Exception:
            return None
        for c in candidates(snap):
            k = key_of(c)
            # ONE PRESS EACH. An earlier draft asked a button again in every
            # later state, on the theory that one hidden behind a tab could not
            # be pressed until its pane was open. It can: the plugin's own
            # `_reach` opens the pane before it acts, which is why a task never
            # has to. Every candidate is reachable from the state the entry
            # leaves the page in, and a second press of an export button is a
            # second copy of the same file.
            if k in seen or left[0] <= 0:
                continue
            left[0] -= 1
            rec = {"key": k, "label": c.get("label"), "host": c.get("host") or "",
                   "id": c.get("id") or ""}
            try:
                plug.execute("activate", {"selector": c["selector"]})
                S._settle(pg)
                _ok, _m, out = plug.execute("collect-output", {})
                pays = out.get("payloads") or []
            except Exception as exc:
                rec["verdict"] = "unreachable"
                rec["why"] = str(exc).split("\n")[0][:110]
                pays = []
            else:
                rec["kinds"] = sorted(set(p.get("k") for p in pays))
                rec["bytes"] = sum(len(p.get("text") or "") for p in pays)
                rec["head"] = (pays[0].get("text") or "")[:80].replace("\n", " / ") if pays else ""
                rec["verdict"] = "emits" if pays else "silent"
            seen[k] = rec
        return None

    for _state, _r in S.each_state(pg, name, probe, entered=True):
        pass
    ent = getattr(pg, "_audit_entered", None)
    task = S.task_for(name, tasks_dir)
    pressed, read = task_reads(task)
    for k, rec in seen.items():
        rec["pressed"] = k in pressed or rec["id"] in pressed or (rec["label"] or "") in pressed
        rec["held"] = (rec["verdict"] == "emits"
                       and (k in read or rec["id"] in read or (rec["label"] or "") in read))
    return {"task": (ent or {}).get("task") or (task or {}).get("id"),
            "buttons": [seen[k] for k in sorted(seen)]}


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
            url = "file://" + os.path.join(docs_dir(), name).replace(os.sep, "/")
            try:
                pg.goto(url, wait_until="domcontentloaded")
                pg.wait_for_timeout(250)
                out[name] = measure(pg, name, tasks_dir)
            except Exception as exc:
                out[name] = {"error": str(exc).split("\n")[0][:140], "buttons": []}
        ctx.close()
        b.close()
    return out


def blind(r, declared):
    return [b["key"] for b in r.get("buttons", [])
            if b.get("verdict") == "emits" and not b.get("held") and b["key"] not in declared]


def counts(r):
    c = {"emits": 0, "silent": 0, "unreachable": 0, "held": 0}
    for b in r.get("buttons", []):
        c[b.get("verdict", "silent")] = c.get(b.get("verdict", "silent"), 0) + 1
        if b.get("held"):
            c["held"] += 1
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
                    help="declare one output exempt, with a reason (needs --reason)")
    ap.add_argument("--reason", default="", help="why an output is exempt")
    ap.add_argument("--names", type=int, default=5, help="how many unread outputs to name")
    ap.add_argument("--json", action="store_true", help="the whole reading, for a suite to read")
    a = ap.parse_args(argv)
    state = load()
    ledger = state.setdefault("pages", {})

    if a.declare:
        if ":" not in a.declare:
            print("--declare takes PAGE:KEY, e.g. ethogram.html:Copy budget CSV")
            return 2
        page, key = a.declare.split(":", 1)
        if not a.reason.strip():
            print("declaring an output exempt needs --reason: it goes into the ledger, and a "
                  "list of\noutputs this audit is choosing not to care about is only useful if "
                  "each line says why")
            return 2
        ledger.setdefault(page, {}).setdefault("declared", {})[key] = a.reason.strip()
        save(state)
        print("%s: %s declared exempt" % (page, key))
        return 0

    got = walk(a.page)
    if a.json:
        print(json.dumps(got, indent=1, sort_keys=True))
        return 0
    print("%-30s %6s %6s %6s %6s   %s"
          % ("PAGE", "UNREAD", "emits", "held", "silent",
             "what the page hands over that no task reads"))
    print("-" * 116)
    tot = dict(blind=0, emits=0, held=0, silent=0)
    above = []
    for name in sorted(got):
        r = got[name]
        if r.get("error"):
            print("%-30s %6s %6s %6s %6s   %s" % (name, "-", "-", "-", "-", r["error"]))
            continue
        if not r.get("buttons"):
            continue
        dec = declared_of(state, name)
        bad = blind(r, dec)
        c = counts(r)
        tot["blind"] += len(bad)
        for k in ("emits", "held", "silent"):
            tot[k] += c.get(k, 0)
        e = ledger.setdefault(name, {})
        ceiling = e.get("ceiling")
        if ceiling is not None and len(bad) > ceiling:
            above.append((name, len(bad), ceiling))
        if a.raise_floors and (ceiling is None or len(bad) < ceiling):
            e["ceiling"] = len(bad)
        e.update({"unread": bad, "buttons": len(r["buttons"]), "task": r.get("task"),
                  "counts": c, "at": int(time.time())})
        mark = "  ABOVE CEILING %d" % ceiling if ceiling is not None and len(bad) > ceiling else ""
        print("%-30s %6d %6d %6d %6d   %s%s"
              % (name, len(bad), c.get("emits", 0), c.get("held", 0), c.get("silent", 0),
                 ", ".join(bad[:a.names]) + (" ..." if len(bad) > a.names else ""), mark))
    print("-" * 116)
    print("%-30s %6d %6d %6d %6d   %s"
          % ("the kit", tot["blind"], tot["emits"], tot["held"], tot["silent"],
             "%d of %d output(s) leave a page with nothing reading them"
             % (tot["blind"], tot["emits"])))
    if not a.page:
        save(state)
    if above:
        print("\n%d page(s) grew an output nothing reads. A page can render a correct analysis\n"
              "and export a wrong one, and every suite in this kit would be green:" % len(above))
        for name, now, ceiling in above:
            print("    %-30s %d, ceiling %d" % (name, now, ceiling))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
