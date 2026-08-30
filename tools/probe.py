# -*- coding: utf-8 -*-
"""The three questions the swarm does not ask: edges, chaos, and every path.

tools/swarm.py drives each control once, from a sensible state, with a sensible
value, and checks the result. That is the happy path done properly. It says
nothing about what happens when somebody types a minus sign into a count, holds
the plus button down, or presses things in an order nobody designed for -- and
it walks a dichotomous key one lead deep, when the whole point of a key is the
tree behind it.

    EDGES     every field, every value that has ever broken a form:
              empty, whitespace, zero, negative, enormous, a decimal where an
              integer is expected, letters in a number, an impossible date, 400
              characters, emoji, and markup. After each one the page must still
              be a page: no uncaught error, nothing rendering NaN or undefined,
              nothing spilling off a phone, and any number it was showing still
              a number.

    CHAOS     N random actions from whatever is on screen, with a seed. The
              invariants are checked after every single one, and when one breaks
              the run prints the seed and the exact list of actions, so the
              sequence replays instead of being retold.

    EXPLORE   every path through a key. A state is what the page is showing; the
              frontier is every unselected option in every group. The walk goes
              depth-first to a leaf, then reloads and replays the prefix to take
              the next branch -- reload-and-replay rather than undo, because a
              page has no obligation to be reversible and a walk that assumes it
              is will quietly explore a tree that is not there.

None of these passes has a per-page expectation. They have INVARIANTS, which is
the right shape for a question whose answer nobody wrote down: not "did this do
the right thing" but "is the page still standing, and did it say something when
it refused".

Run:  python3 tools/probe.py --edges                 all pages
      python3 tools/probe.py --chaos --seed 7        random, reproducibly
      python3 tools/probe.py --explore PAGE ...      every path through a key
      python3 tools/probe.py --all -j 4
"""
import argparse, concurrent.futures as cf, glob, io, json, os, random, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "verify"))
import _kit
import swarm as S
from harness_contract import HarnessError

LEDGER = os.path.join(HERE, "probe_ledger.json")
EVIDENCE = os.path.join(HERE, "probe_evidence")

# Values that have broken forms before. Each is paired with the reason it is
# here, because a battery nobody can explain becomes a battery nobody prunes.
EDGES = [
    ("", "empty -- the commonest thing a field ever holds"),
    ("   ", "whitespace only, which is not empty and is not a value"),
    ("0", "zero, which is falsy in this language and is a real count"),
    ("-1", "negative, where the quantity cannot be"),
    ("-0.0001", "a negative that rounds to zero when displayed"),
    ("999999999", "larger than any plot, quadrat or trial"),
    ("1e308", "near the top of a double"),
    ("0.1", "a decimal where an integer is expected"),
    ("abc", "letters where a number is expected"),
    ("2026-13-45", "a date that does not exist"),
    ("x" * 400, "four hundred characters in a one-line field"),
    ("éñ中文 \U0001f344\U0001f426", "accents, CJK and emoji"),
    ("<script>alert(1)</script>", "markup, which must render as text"),
    ('a,b"c\td', "the separators an export has to quote"),
]

TYPED_KINDS = ("text_in", "field_in", "step_val")
CLICKY = ("pick_opt", "dial_btn", "chip", "kopt", "ck", "cv", "swc", "tab",
          "step_btn", "action_btn", "checkbox")
GROUPY = ("pick_opt", "dial_btn", "chip", "kopt", "ck", "cv", "swc", "tab")


# ---------------------------------------------------------------------------
# The invariants. Not "did it do the right thing" -- "is it still a page".
# ---------------------------------------------------------------------------

def broken(before, after, errors):
    out = []
    if after.get("junkTok") and after.get("junkTok") != before.get("junkTok"):
        out.append("rendered %s: %s" % (after["junkTok"], (after.get("junk") or "")[:80]))
    js = after.get("junkSlot")
    if js and js != before.get("junkSlot"):
        out.append("a readout shows %r (%s)" % (js["text"], js["where"]))
    if after.get("panes") and after.get("onp") != 1:
        out.append("%d panes visible at once" % after["onp"])
    if after.get("overflow", 0) > 1:
        out.append("spills %dpx sideways: %s"
                   % (after["overflow"], ", ".join(after.get("wide") or [])))
    for e in (after.get("errors") or []):
        out.append("uncaught: %s" % e[:120])
    for e in errors:
        out.append(e[:140])
    del errors[:]
    # A page that has stopped rendering anything is broken even if nothing threw.
    if before.get("len", 0) > 200 and after.get("len", 0) < before["len"] / 4:
        out.append("the page lost %d%% of its rendered text"
                   % (100 - int(100.0 * after["len"] / max(1, before["len"]))))
    return out


def _shot(pg, tag):
    try:
        os.makedirs(EVIDENCE, exist_ok=True)
        p = os.path.join(EVIDENCE, tag[:120].replace("/", "_") + ".png")
        pg.screenshot(path=p)
        return p
    except Exception:
        return None


# ---------------------------------------------------------------------------
# EDGES
# ---------------------------------------------------------------------------

def edges(name, cap=14):
    res = {"page": name, "pass": "edges", "fields": 0, "tried": 0,
           "findings": [], "secs": 0}
    t0 = time.time()
    with S.open_session(name) as (cl, pg, errs):
        snap = cl.snapshot()
        # Not filtered on the snapshot's visibility. Most fields in this kit live
        # in a pane that is shut until its tab is pressed, so judging from the
        # snapshot taken at load left the battery testing one field of the
        # twenty-nine on stand-sheet. Take every field of the right kind, open
        # its pane, and let the live read decide.
        fields = [c for c in snap["controls"] if c["kind"] in TYPED_KINDS][:60]
        res["fields"] = len(fields)
        for c in fields:
            for value, why in EDGES[:cap]:
                try:
                    if c["pane"]:
                        try:
                            cl.do("show-pane", pane=c["pane"])
                        except HarnessError:
                            pass
                    cur = cl.control(c["selector"])
                    if not cur or not cur.get("visible") or not cur.get("enabled"):
                        break
                    before = cl.page_state()
                    cl.do("set-text", selector=c["selector"], value=value)
                    res["tried"] += 1
                    after = cl.page_state()
                except HarnessError as e:
                    if e.code == "not_found":
                        break
                    continue
                for b in broken(before, after, errs):
                    tag = "%s-%s-%d" % (name[:-5], c["selector"].replace(":", "_"),
                                        len(res["findings"]))
                    res["findings"].append({
                        "selector": c["selector"], "label": (c["label"] or "")[:40],
                        "value": value[:40], "why": why, "broke": b,
                        "shot": _shot(pg, tag)})
    res["secs"] = round(time.time() - t0, 1)
    return res


# ---------------------------------------------------------------------------
# CHAOS
# ---------------------------------------------------------------------------

def chaos(name, steps=120, seed=1):
    res = {"page": name, "pass": "chaos", "seed": seed, "steps": 0,
           "findings": [], "secs": 0}
    rng = random.Random("%s/%d" % (name, seed))
    t0 = time.time()
    log = []
    with S.open_session(name) as (cl, pg, errs):
        snap = cl.snapshot()
        for i in range(steps):
            pool = [c for c in snap["controls"] if c["kind"] in CLICKY + TYPED_KINDS]
            if not pool:
                break
            c = rng.choice(pool)
            act, arg = _random_action(c, rng)
            try:
                if c["pane"]:
                    try:
                        cl.do("show-pane", pane=c["pane"])
                    except HarnessError:
                        pass
                before = cl.page_state()
                cl.do(act, **dict(arg, selector=c["selector"]))
                log.append({"n": i, "action": act, "selector": c["selector"],
                            "label": (c["label"] or "")[:30], "arg": arg})
                res["steps"] += 1
                after = cl.page_state()
            except HarnessError:
                snap = cl.snapshot()
                continue
            bad = broken(before, after, errs)
            if bad:
                tag = "chaos-%s-%d" % (name[:-5], len(res["findings"]))
                res["findings"].append({
                    "step": i, "broke": bad[0],
                    "all": bad,
                    # The whole sequence, not a description of it: a bug you have
                    # to reconstruct from prose is a bug nobody reproduces.
                    "replay": log[-12:], "seed": seed, "shot": _shot(pg, tag)})
            if i % 10 == 9:
                snap = cl.snapshot()
    res["secs"] = round(time.time() - t0, 1)
    return res


def _random_action(c, rng):
    k = c["kind"]
    if k in TYPED_KINDS:
        v = rng.choice([e[0] for e in EDGES] + ["3", "7", "Zqx404"])
        if k == "step_val":
            v = rng.choice(["1", "9", "0", "-2", "abc"])
        return "set-text", {"value": v}
    if k == "checkbox":
        return "set-checkbox", {"checked": rng.random() < 0.5}
    if k == "step_btn":
        return "press-step", {"direction": rng.choice(["up", "down"])}
    if k == "tab":
        return "activate", {}
    return "activate", {}


# ---------------------------------------------------------------------------
# EXPLORE -- every path through a key
# ---------------------------------------------------------------------------

def explore(name, max_paths=300, max_depth=14):
    """Depth-first over the option groups, reloading and replaying to backtrack.

    A page has no obligation to be reversible -- a key that has committed to a
    lead may offer no way back to the fork. Reload-and-replay costs a page load
    per branch and is the only way to be sure the branch was reached from the
    same place a user would reach it from.
    """
    res = {"page": name, "pass": "explore", "paths": 0, "leaves": 0,
           "deepest": 0, "options_seen": 0, "states_seen": 0,
           "findings": [], "secs": 0}
    t0 = time.time()
    # How many DISTINCT states the walk actually reached, which is the number
    # that says whether a tree was explored or merely entered.
    seen_opts, states, frontier, done = set(), set(), [[]], set()
    with S.open_session(name) as (cl, pg, errs):
        while frontier and res["paths"] < max_paths:
            path = frontier.pop()
            key = tuple(path)
            if key in done:
                continue
            done.add(key)
            res["paths"] += 1
            try:
                # Reload rather than re-open by name: backtracking must not
                # depend on the client knowing where the page came from, and a
                # fixture served from a temporary directory has no kit name to
                # resolve.
                cl.do("reload")
            except HarnessError:
                break
            ok = True
            before = cl.page_state()
            for sel in path:
                try:
                    c = cl.control(sel)
                    if not c or not c.get("visible"):
                        ok = False
                        break
                    cl.do("activate", selector=sel)
                except HarnessError:
                    ok = False
                    break
            if not ok:
                continue
            after = cl.page_state()
            states.add(after.get("thash"))
            for b in broken(before, after, errs):
                res["findings"].append({
                    "path": path, "depth": len(path), "broke": b,
                    "shot": _shot(pg, "explore-%s-%d" % (name[:-5], len(res["findings"])))})
            res["deepest"] = max(res["deepest"], len(path))
            snap = cl.snapshot()
            opts = [c for c in snap["controls"]
                    if c["kind"] in GROUPY and c["visible"] and not c["selected"]
                    and c["selector"] not in path]
            for c in opts:
                seen_opts.add(c["selector"])
            if not opts or len(path) >= max_depth:
                res["leaves"] += 1
                continue
            # Breadth at each fork, depth overall: take every unselected option
            # that is on screen at this node.
            for c in opts[:12]:
                frontier.append(path + [c["selector"]])
    res["options_seen"] = len(seen_opts)
    res["states_seen"] = len(states)
    res["secs"] = round(time.time() - t0, 1)
    return res


# ---------------------------------------------------------------------------

PASSES = {"edges": edges, "chaos": chaos, "explore": explore}


def _run(job):
    which, name, kw = job
    try:
        return PASSES[which](name, **kw)
    except Exception as e:
        return {"page": name, "pass": which, "findings": [],
                "crashed": "%s: %s" % (type(e).__name__, str(e)[:200]), "secs": 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*")
    ap.add_argument("--edges", action="store_true")
    ap.add_argument("--chaos", action="store_true")
    ap.add_argument("--explore", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--steps", type=int, default=120)
    ap.add_argument("--max-paths", type=int, default=300)
    ap.add_argument("-j", type=int, default=3)
    ap.add_argument("--ledger", default=LEDGER)
    a = ap.parse_args()

    which = [w for w in ("edges", "chaos", "explore")
             if getattr(a, w) or a.all] or ["edges"]
    names = a.pages or sorted(os.path.basename(p) for p in
                              glob.glob(os.path.join(_kit.ROOT, "docs", "*.html")))
    jobs = []
    for w in which:
        kw = {}
        if w == "chaos":
            kw = {"steps": a.steps, "seed": a.seed}
        if w == "explore":
            kw = {"max_paths": a.max_paths}
        jobs += [(w, n, kw) for n in names]

    print("probe -- %s over %d page(s), %d at a time"
          % (" + ".join(which), len(names), a.j))
    print("-" * 88)
    out = []
    with cf.ThreadPoolExecutor(max_workers=a.j) as ex:
        for r in ex.map(_run, jobs):
            out.append(r)
            extra = ""
            if r["pass"] == "edges":
                extra = "%d fields, %d values" % (r.get("fields", 0), r.get("tried", 0))
            elif r["pass"] == "chaos":
                extra = "%d actions, seed %s" % (r.get("steps", 0), r.get("seed"))
            else:
                extra = ("%d paths, %d leaves, depth %d, %d options, %d states"
                         % (r.get("paths", 0), r.get("leaves", 0),
                            r.get("deepest", 0), r.get("options_seen", 0),
                            r.get("states_seen", 0)))
            print("%-8s %-28s %3d finding(s)  %-38s %6.1fs%s"
                  % (r["pass"], r["page"], len(r["findings"]), extra, r["secs"],
                     "  CRASHED" if r.get("crashed") else ""))

    tot = sum(len(r["findings"]) for r in out)
    print("-" * 88)
    print("%d finding(s) across %d run(s)" % (tot, len(out)))
    for r in out:
        for f in r["findings"][:6]:
            where = f.get("selector") or ("path of %d" % f.get("depth", 0)) \
                or ("step %s" % f.get("step"))
            print("  %-8s %-24s %-22s %s"
                  % (r["pass"], r["page"][:24], str(where)[:22], str(f["broke"])[:70]))
    crashed = [r for r in out if r.get("crashed")]
    for r in crashed:
        print("  CRASHED %-24s %s" % (r["page"], r["crashed"]))

    json.dump({"at": int(time.time()), "edges": [e[0][:40] for e in EDGES],
               "totals": {"findings": tot, "runs": len(out),
                          "crashed": len(crashed)},
               "runs": out}, io.open(a.ledger, "w", encoding="utf-8"), indent=1)
    print("\nwrote %s" % a.ledger)
    return 0


if __name__ == "__main__":
    sys.exit(main())
