# -*- coding: utf-8 -*-
"""The brief: what a task GIVES and what it HOLDS (ADR-193).

The third blind trial (ADR-187) graded four operators against what their TASKS
hold and handed them what their GOALS say, and the two are not the same set.
Measured here, on the 21 science tasks: 547 values entered, and a majority of
them appearing nowhere in the goal that was handed over. That is not a hard
trial; it is an unfair one.

A goal is a brief now -- `says` (the prose, unchanged), `gives` (every value
the task supplies, with the control that takes it) and `holds` (every reading
it holds, with its claims). Both new parts are DERIVED FROM THE STEPS, which is
the whole of why they can be trusted: a brief written beside a task goes stale
the first time the task is edited, and a stale brief is worse than none.

This is its own suite rather than another section of verify_tasks, and the
reason is arithmetic. verify_tasks drives real browsers and takes minutes; not
one check below opens anything. A mutant runner over an eight-minute suite is
twelve hours for twenty mutants and therefore never run, which is the same as
having no runner -- so the fast claims live where a runner can afford them.

Run:  python3 tools/verify/verify_brief.py
"""
# Declared for tools/mutate.py: this suite asserts about tools/harness_tasks.py
# and opens nothing -- a subject.
MUTATE_ROLE = "subject"
import glob, io, json, os, re, sys

import _kit

sys.path.insert(0, _kit.TOOLS_DIR.rstrip(os.sep))
import harness_tasks as T

P = F = 0
unverified = []


def ck(c, m):
    global P, F
    if c:
        P += 1
    else:
        F += 1
        print("FAIL:", m)


# ---- the brief --------------------------------------------------
#
# The third blind trial graded four operators against what their TASKS hold and
# handed them what their GOALS say. Measured here, on the same 21 science
# tasks: 547 values entered, and a majority of them appearing nowhere in the
# goal that was handed over. That is not a hard trial; it is an unfair one.
#
# A goal is a brief now: `says` (the prose, unchanged), `gives` (every value
# the task supplies) and `holds` (every reading it holds). Both of the new
# parts are DERIVED FROM THE STEPS, which is the whole of why they can be
# trusted -- a brief written beside a task goes stale the first time the task
# is edited, and a stale brief is worse than none.

ALL = [T.load_task(p) for p in sorted(glob.glob(os.path.join(_kit.TOOLS_DIR, "tasks", "*.json")))]
SCIENCE = [t for t in ALL if t["id"].startswith("page-") and t["id"].endswith("-science")]
briefs = [T.goal_of(t) for t in ALL]
ck(len(briefs) == len(ALL) and all(b["says"] and b["counts"]["steps"] for b in briefs),
   "every one of the %d tasks has a brief" % len(ALL))

# -- gives is COMPLETE ---------------------------------------------------------
#
# Re-walked here rather than re-using gives_of, because a check that asks the
# subject what it found agrees with itself by construction.
# THIS SUITE'S OWN TABLE, not the subject's. Reading T.GIVING here would make
# the check agree with the code by construction: an action dropped from the
# subject's table would be dropped from the check in the same breath, and the
# mutant that dropped it would survive. Written out, so the two can disagree --
# and so the list of what a task can SUPPLY is stated somewhere a reader can
# check it against the tasks.
GIVE_KEYS = {"set-text": ("value",), "type-text": ("value",), "pick": ("value",),
             "choose-option": ("value",), "set-slider": ("value",),
             "set-checkbox": ("checked",), "press-step": ("direction", "times"),
             "attach-file": ("name", "text", "path"), "drop-files": ("files", "names"),
             "set-clock": ("at", "clock"), "set-seed": ("seed",),
             "set-dialog": ("confirm", "prompt"), "answer-dialog": ("confirm", "prompt")}
used = set(st["action"] for t in ALL for st in t["steps"])
ck(set(GIVE_KEYS) >= (used & set(T.GIVING)) and used & set(GIVE_KEYS),
   "every giving action the tasks actually use is in this suite's own table: %s"
   % sorted(used & set(T.GIVING) - set(GIVE_KEYS)))

missing, given = [], 0
for t in ALL:
    have = set()
    for g in T.gives_of(t):
        have.add((g["step"], g["argument"], g["value"]))
        given += 1
    for i, st in enumerate(t["steps"]):
        keys = GIVE_KEYS.get(st["action"])
        if not keys:
            continue
        for k, v in (st.get("arguments") or {}).items():
            if k not in keys or v is None or v == "":
                continue
            text = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
            if (st["id"], k, text) not in have:
                missing.append((t["id"], st["id"], k, text[:40]))
ck(not missing and given > 600,
   "EVERY value every task supplies is in its brief -- %d of them, nothing left out: %s"
   % (given, missing[:3]))

sci_given = sum(len(T.gives_of(t)) for t in SCIENCE)
ck(sci_given > 500,
   "and %d of those are the 21 science tasks', which is the number ADR-187's operators were "
   "graded on and not handed" % sci_given)

# THE GAP, MEASURED. This is the claim the slice exists to make, so it is held
# as a number rather than as a sentence: how much of the data a task enters the
# PROSE alone names, against how much the brief hands over.
def _named(prose, v):
    g, v = prose.lower(), v.strip()
    if not v or v.lower() in g:
        return True
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", v):
        return any(f and f.lower() in g
                   for f in {v, v.lstrip("+"), v.rstrip("0").rstrip("."), "+" + v.lstrip("+")})
    return False


unnamed = [(t["id"], g["value"][:30]) for t in SCIENCE for g in T.gives_of(t)
           if not _named(t["goal"], g["value"])]
ck(len(unnamed) > 200,
   "the prose alone names %d of the %d -- %d values an operator could not have reached by "
   "reasoning, because nobody had told them: %s"
   % (sci_given - len(unnamed), sci_given, len(unnamed), [u[1] for u in unnamed[:3]]))
ck(all(any(g["value"] == u[1] or g["value"][:30] == u[1] for g in T.gives_of(t))
       for t in SCIENCE for u in unnamed if u[0] == t["id"]),
   "and every one of them is in the brief, which is the whole of what this slice changed")

# -- nothing is typed ----------------------------------------------------------
typed = [t["id"] for t in ALL if "gives" in t or "holds" in t or "brief" in t]
ck(not typed,
   "no task file carries a brief of its own: `gives` and `holds` are computed from the steps, "
   "so a task edited without its brief being edited cannot leave the brief lying: %s" % typed)
one = json.loads(json.dumps(SCIENCE[0]))
before = len(T.gives_of(one))
one["steps"] = [x for x in one["steps"] if x["action"] not in GIVE_KEYS][:5] + [
    {"id": "zz-new", "action": "set-text",
     "arguments": {"selector": "@control:zz", "value": "a value nobody wrote a brief for"}}]
ck(len(T.gives_of(one)) == 1 and T.gives_of(one)[0]["control"] == "zz",
   "and a step added to a task is in its brief at once, with the control it is pointed at: "
   "%d -> %s" % (before, T.gives_of(one)))

# -- holds is exactly what the grader scores -----------------------------------
drift = []
for t in ALL:
    h, o = T.holds_of(t), T.outcomes_of(t)
    if [x["step"] for x in h] != [s["id"] for s, _ in o] or \
       [x["claims"] for x in h] != [c for _, c in o]:
        drift.append(t["id"])
ck(not drift,
   "what a brief HOLDS is exactly what the outcome grader scores, step for step and claim for "
   "claim -- a brief that promised a reading the grader did not want, or wanted one the brief "
   "did not promise, would make a host that satisfied it fail anyway: %s" % drift[:3])
claims = sum(b["counts"]["claims"] for b in briefs)
ck(claims == sum(len(c) for t in ALL for _, c in T.outcomes_of(t)) and claims > 1900,
   "%d claims across the kit, and the brief's count is the grader's count" % claims)

blind3 = sorted(glob.glob(os.path.join(_kit.TOOLS_DIR, "traces", "blind3", "*.jsonl.gz")))
if not blind3:
    unverified.append("no ADR-187 traces here, so the brief was not held against a real grade")
else:
    by_id = dict((t["id"], t) for t in ALL)
    rows = 0
    for p in blind3:
        tid = os.path.basename(p).split("@")[0][:-len(".jsonl.gz")]
        t = by_id.get(tid)
        if not t:
            continue
        got = T.grade_outcomes(t, T.load_trace(p))
        held = T.holds_of(t)
        ck([x["id"] for x in got["steps"]] == [h["step"] for h in held]
           and got["outcomes"] == len(held)
           and got["claims"] == sum(len(h["claims"]) for h in held),
           "%s: the grader scores exactly the readings the brief holds, in order and claim for "
           "claim -- %d/%d outcome(s), %d/%d claim(s)"
           % (tid, got["outcomes"], len(held), got["claims"],
              sum(len(h["claims"]) for h in held)))
        rows += 1
    ck(rows == len(blind3),
       "and every one of the %d third-trial traces was graded against its own brief" % rows)

# -- a blind brief gives the data and withholds the answers --------------------
t = SCIENCE[0]
full, blind = T.brief_of(t, claims=True), T.brief_of(t, claims=False)
vals = [g["value"] for g in T.gives_of(t) if not g["bulk"]]
ck(all(json.dumps(v, ensure_ascii=False) in blind for v in vals),
   "a BLIND brief hands over every value the task enters")
ck("withheld" in blind and len(blind) < len(full),
   "and withholds what it holds, saying so: an operator told the answers is being asked to "
   "transcribe rather than to operate (%d characters against %d)" % (len(blind), len(full)))
first_claim = json.dumps(T.holds_of(t)[0]["claims"], ensure_ascii=False)[:60]
ck(first_claim in full and first_claim not in blind,
   "and the claims really are absent from the blind one, not merely unmentioned")
ck(T.brief_of(t) == full,
   "and a brief asked for with no argument is the FULL one: blind is what a trial opts into, "
   "so an organiser who forgets the flag gets the brief with the answers in it and notices, "
   "rather than a trial that was accidentally fair and silently useless")

# -- the committed ledger carries the counts -----------------------------------
_led = json.load(io.open(os.path.join(_kit.TOOLS_DIR, "task_ledger.json"),
                         encoding="utf-8"))["tasks"]
_by = dict((t["id"], t) for t in ALL)
_runs = dict((k, v) for k, v in _led.items() if "@" not in k and k in _by)
_wrong = [t["id"] for t in ALL
          if T.brief_counts(t) != {"gives": T.goal_of(t)["counts"]["gives"],
                                   "holds": T.goal_of(t)["counts"]["holds"],
                                   "claims": T.goal_of(t)["counts"]["claims"]}]
ck(not _wrong,
   "what a LEDGER ROW says about a brief is what the brief says about itself -- one function, "
   "both the run's row and the could-not-stand-up's, so a task's counts do not depend on "
   "whether its target came up that morning: %s" % _wrong[:3])

_off = [k for k, e in _runs.items()
        if e.get("gives") != len(T.gives_of(_by[k]))
        or e.get("holds") != len(T.holds_of(_by[k]))
        or e.get("claims") != sum(len(h["claims"]) for h in T.holds_of(_by[k]))]
ck(len(_runs) == len(ALL) and not _off,
   "the ledger counts what every brief hands over and holds, so a task that grew a step "
   "nobody added to its brief is a number that moved rather than a thing nobody saw: %s"
   % _off[:3])
ck(sum(e.get("gives") or 0 for e in _runs.values()) > 600
   and sum(e.get("claims") or 0 for e in _runs.values()) > 1900,
   "%d values handed over and %d claims held, across the committed runs"
   % (sum(e.get("gives") or 0 for e in _runs.values()),
      sum(e.get("claims") or 0 for e in _runs.values())))

# -- the brief is not a gateway action -----------------------------------------
for mod in ("harness_contract.py", "harness_mcp.py", "harness_http.py", "harness_stdio.py",
            "harness_plugin_page.py", "harness_plugin_organism.py", "harness_plugin_lab.py"):
    src = io.open(os.path.join(_kit.TOOLS_DIR, mod), encoding="utf-8").read()
    ck(not re.search(r"^\s*(import|from)\s+harness_tasks\b", src, re.M)
       and not re.search(r'"goal"\s*,\s*"', src),
       "%s does not reach for the tasks: a door that served a client its own task would end "
       "the blind trial that made the brief necessary, and ADR-136's discipline is that the "
       "tasks are REMOVED from the filesystem the operator works in" % mod)

# -- the brief says what the task needs ----------------------------------------
bad = [b["id"] for b, t in zip(briefs, ALL)
       if tuple(b["needs"]["rungs"]) != T.task_rungs(t)[0] or b["needs"]["why"] != T.task_rungs(t)[1]]
ck(not bad,
   "a brief carries the rungs the task declares and the reason it declares them (ADR-142), so "
   "an operator knows before it starts what it will be refused: %s" % bad)
dest = [b for b in briefs if "DESTRUCTIVE" in b["needs"]["rungs"]]
ck(dest and all(b["needs"]["why"] for b in dest),
   "and every brief that asks for the fourth rung says why: %d of them" % len(dest))




total = P + F + len(unverified)
print("---")
for u in unverified:
    print("NOT VERIFIED: " + u)
print("%d/%d" % (P, total))
raise SystemExit(1 if F else 0)
