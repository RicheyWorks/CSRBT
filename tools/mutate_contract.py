# -*- coding: utf-8 -*-
"""Mutation testing for the contract itself (ADR-141).

`verify_contract` is the oldest suite in this kit and, until this file, the
only large one with no mutant runner behind it -- which is precisely backwards.
It is the suite that asserts the door: off by default, a token on every
operation, a rung per action, a replay that is re-authorised rather than merely
re-served. Every other suite here is allowed to assume the door holds. A hole
in this one is a hole under everything.

ADR-141 made the point unavoidable by changing what a declared risk MEANS -- it
is now a floor an action may be raised above, per call, by the target that knows
what it was pointed at. That is a rule about escalation written into the one
place escalation is decided, and a rule about escalation that nothing tries to
break is a rule nobody has tested.

    python3 tools/mutate_contract.py           # run every mutant
    python3 tools/mutate_contract.py --list    # the catalogue

SAFETY: tools/ is copied to a temp directory and the COPY is mutated. The real
harness_contract.py is never written to.
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("harness_contract.py", "harness_plugin_page.py")

MUTANTS = [
    # ---- ADR-141: a declared risk is a FLOOR ----------------------------
    ("an action's declared risk is the last word again",
     '''        if not getattr(spec, "may_rise", False):
            return spec.risk, None''',
     '''        if True:
            return spec.risk, None''',
     "a raise is taken"),
    ("every action is asked what it would touch, whether or not it said it may rise",
     '''        if not getattr(spec, "may_rise", False):
            return spec.risk, None''',
     '''        if False:
            return spec.risk, None''',
     "never asked what it would touch"),
    ("a target may talk its way DOWN the ladder",
     '''        if RISKS.index(risk) <= RISKS.index(spec.risk):
            return spec.risk, None            # a plugin may raise, never lower''',
     '''        if False:
            return spec.risk, None            # a plugin may raise, never lower''',
     "may not LOWER its own action"),
    ("a target that cannot decide is trusted with the lowest rung",
     '''            got = ("DESTRUCTIVE", "the target could not say what this call would touch")''',
     '''            got = None''',
     "fails closed at DESTRUCTIVE"),
    ("a refusal the target raises while deciding is swallowed as ignorance",
     '''        try:
            got = plugin.risk_for(spec.name, args)
        except HarnessError:
            raise''',
     '''        try:
            got = plugin.risk_for(spec.name, args)
        except HarnessError:
            got = None''',
     "reaches the caller unchanged"),
    ("a rung the target invented is taken at face value",
     '''        if risk not in RISKS:
            return spec.risk, None''',
     '''        if risk not in RISKS:
            return risk, why''',
     "may not LOWER its own action"),
    ("the call is authorised at the floor and RUN at the raise",
     '''        risk, risk_why = self._risk_of(plugin, spec, args)
        try:
            self.policy.authorize(risk)''',
     '''        risk, risk_why = self._risk_of(plugin, spec, args)
        try:
            self.policy.authorize(spec.risk)''',
     "was allowed at a MUTATE session"),
    ("the response reports the rung the action DECLARED, not the one it ran at",
     '''                "pluginId": plugin_id, "action": spec.name, "risk": risk,''',
     '''                "pluginId": plugin_id, "action": spec.name, "risk": spec.risk,''',
     "authorised at, and why"),
    ("the audit records the declared rung",
     '''        self.audit.append((time.time(), plugin_id, name, risk,
                           "ok" if ok else "no"))''',
     '''        self.audit.append((time.time(), plugin_id, name, spec.risk,
                           "ok" if ok else "no"))''',
     "AUDIT records the risk the call was authorised at"),
    ("a refusal at a raised rung reads as the manifest contradicting itself",
     '''            if risk_why:
                raise Forbidden("%s -- %s was raised from %s to %s because %s"
                                % (e.message, spec.name, spec.risk, risk, risk_why))''',
     '''            if False:
                raise Forbidden("%s -- %s was raised from %s to %s because %s"
                                % (e.message, spec.name, spec.risk, risk, risk_why))''',
     "says so, and names the target's"),
    ("the reason the call was raised is not carried at all",
     '''                "declaredRisk": spec.risk, "riskWhy": risk_why,''',
     '''                "declaredRisk": spec.risk, "riskWhy": None,''',
     "authorised at, and why"),
    ("a replayed response is re-authorised at the rung it DECLARED",
     '''            self.policy.authorize(hit.risk)''',
     '''            self.policy.authorize(plugin.descriptor().action(name).risk)''',
     "re-authorised at the risk it was RAISED to"),
    # ---- ADR-141: the snapshot advertises nothing it would refuse -------
    ("a snapshot carries every pool, whatever the session may call",
     '''            if r is not None and not self.policy.allow.get(r):
                gone[act] = r''',
     '''            if False:
                gone[act] = r''',
     "not handed that action's argument pools"),
    ("pools that belong to no action are withheld with the rest",
     '''            r = risk_of.get(act)
            if r is not None and not self.policy.allow.get(r):''',
     '''            r = risk_of.get(act) or "DESTRUCTIVE"
            if r is not None and not self.policy.allow.get(r):''',
     "facts about the target and stay"),
    ("what was withheld is dropped silently",
     '''        snap["poolsWithheld"] = [{"action": a, "risk": gone[a],''',
     '''        snap.pop("poolsWithheld", None)
        _unused = [{"action": a, "risk": gone[a],''',
     "what was withheld is NAMED"),
    ("filtering writes through to the target's own snapshot",
     '''        snap = dict(snap)
        snap["argumentPools"] = keep''',
     '''        snap["argumentPools"] = keep''',
     "the target's own snapshot is untouched"),
    # ---- the page's classifier -----------------------------------------
    ("every button is a button: nothing is raised",
     '''        why = destroys(info.get("label"), info.get("title"))''',
     '''        why = None''',
     "raised to DESTRUCTIVE"),
    ("a control nobody can name is assumed harmless",
     '''        if not (info.get("label") or info.get("id") or info.get("title")):''',
     '''        if False:''',
     "no label, id or title is raised"),
    ("a selector that resolves to nothing is somebody else's problem",
     '''        if not info or not info.get("found"):''',
     '''        if False:''',
     "resolves to NOTHING is raised"),
    ("the destructive vocabulary loses the words with a mark for a name",
     '''DESTRUCTIVE_MARK = ("\\u2715", "\\u2716", "\\u2717", "\\u2718", "\\u232b", "\\U0001f5d1")''',
     '''DESTRUCTIVE_MARK = ()''',
     "row-removing mark is caught"),
    ("a mark anywhere in a label is a delete, so an export is one",
     '''            if s.startswith(m) or s.endswith(m):''',
     '''            if m in s:''',
     "MULTIPLICATION sign is not a delete"),
    ("the multiplication sign is a delete wherever it appears",
     '''AMBIGUOUS_MARK = ("\\u00d7", "\\u2a2f")''',
     '''AMBIGUOUS_MARK = ()
DESTRUCTIVE_MARK = DESTRUCTIVE_MARK + ("\\u00d7",)''',
     "MULTIPLICATION sign is not a delete"),
    ("a close button that is nothing but the mark is not raised",
     '''        if s in AMBIGUOUS_MARK:''',
     '''        if False:''',
     "close button and is raised"),
    ("the vocabulary loses its word boundaries, so Nuclear is Clear",
     '''    r"(?:^|\\b)(?:clear|delete|remove|erase|wipe|discard|revert|undo|forget|trash"
    r"|purge|abandon|reset|start over|restart)\\b", re.I)''',
     '''    r"(?:clear|delete|remove|erase|wipe|discard|revert|undo|forget|trash"
    r"|purge|abandon|reset|start over|restart)", re.I)''',
     "stays at the declared MUTATE floor"),
    ("the snapshot stops naming which selectors would be raised",
     '''        pools["activate.destructive"] = [
            c["selector"] for c in live
            if c["kind"] in POOL_KINDS["activate"] and destroys(c.get("label"))]''',
     '''        pools["activate.destructive"] = []''',
     "the snapshot NAMES them"),
    ("naming them is done INSTEAD of publishing them",
     '''            pools[action + ".selector"] = [c["selector"] for c in live if c["kind"] in kinds]''',
     '''            pools[action + ".selector"] = [c["selector"] for c in live if c["kind"] in kinds
                                           and not (action == "activate" and destroys(c.get("label")))]''',
     "beside the selectors, not instead of them"),
    # ---- the door itself, which nothing had ever broken on purpose ------
    ("the harness is on by default",
     '''DEFAULT_POLICY = {"READ": True, "NAVIGATE": True, "SENSITIVE_READ": False,
                  "DRAFT": False, "MUTATE": False, "DESTRUCTIVE": False}''',
     '''DEFAULT_POLICY = {"READ": True, "NAVIGATE": True, "SENSITIVE_READ": True,
                  "DRAFT": True, "MUTATE": True, "DESTRUCTIVE": True}''',
     "blocked by default"),
    ("generic activation may be enabled on its own",
     '''        if p["DESTRUCTIVE"] and not p["MUTATE"]:''',
     '''        if False:''',
     "DESTRUCTIVE was enabled without MUTATE"),
    ("a short token is good enough",
     '''        if not self.token or len(self.token) < TOKEN_MIN:''',
     '''        if not self.token:''',
     "a token under 24 characters"),
    ("the same request id with a different body is served the first answer",
     '''            if hit.body != body:''',
     '''            if False:''',
     "the same request id with different"),
    ("an argument nobody declared is passed through to the target",
     '''        for k in args:
            if k not in declared:''',
     '''        for k in args:
            if False:''',
     "an argument the action does not declare"),
]

KNOWN_EQUIVALENT = [
    # `hmac.compare_digest(token, self.token)` -> `token != self.token`. The two
    # accept and reject exactly the same tokens; they differ only in how long
    # the rejection takes, and a timing difference across a Python comparison of
    # a 24-character string is not something a suite in this repository can
    # observe without measuring noise. Recorded rather than deleted: the clause
    # is real (ADR-061), and the honest thing to say is that no check here
    # defends it -- not to leave a mutant reading SURVIVED as though something
    # had gone wrong today.
    ("a token is compared with ==, in whatever time it takes",
     "compare_digest and != accept and reject exactly the same tokens; they differ only in "
     "how long a rejection takes, and a timing difference across a Python comparison of a "
     "24-character string is not something a suite here can observe without measuring noise. "
     "Recorded rather than deleted: the clause is real (ADR-061), and the honest thing to say "
     "is that no check defends it -- not to leave a mutant reading SURVIVED as though "
     "something had gone wrong today."),
]


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutcon_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        # verify_contract reads the real page plugin's descriptor, and _kit
        # resolves docs/ beside tools/. Linked, not copied: nothing here writes
        # to the kit and a mutant must not be able to.
        os.symlink(os.path.join(ROOT, "docs"), os.path.join(tmp, "docs"))
        path = None
        for cand in SUBJECT:
            p2 = os.path.join(dst, cand)
            if io.open(p2, encoding="utf-8").read().count(find) == 1:
                path = p2
                break
        if path is None:
            n = sum(io.open(os.path.join(dst, c), encoding="utf-8").read().count(find)
                    for c in SUBJECT)
            return ("BAD MUTANT",
                    "anchor matched %d times across the subject -- the mutation never applied" % n)
        src = io.open(path, encoding="utf-8").read()
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        suites = ["verify_contract.py"]
        # A mutant in the page plugin's classifier is asserted by the suite that
        # drives a real page, not by the contract's fixture plugins.
        if os.path.basename(path) == "harness_plugin_page.py":
            suites = ["verify_report.py"]
        fails, out, rc = [], "", 0
        for s in suites:
            p = subprocess.run([sys.executable, os.path.join(dst, "verify", s)],
                               capture_output=True, text=True, timeout=1800,
                               env=dict(os.environ, CSRBT_DOCS_DIR=os.path.join(ROOT, "docs")))
            out += p.stdout + p.stderr
            rc = rc or p.returncode
            fails += [l for l in (p.stdout + p.stderr).split("\n") if l.startswith("FAIL")]
        if not fails and rc != 0:
            return ("BAD MUTANT", "the suite crashed rather than failed: %s"
                    % (out.strip().split("\n")[-1][:70] if out.strip() else "no output"))
        if not fails:
            return ("SURVIVED", "no check failed -- this clause is asserted by nobody")
        return ("killed" if any(expect in f for f in fails) else "killed by the wrong check",
                "%d failure(s); first: %s" % (len(fails), fails[0][6:80]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", type=int, metavar="N", help="run one mutant by index")
    a = ap.parse_args(argv)
    if a.list:
        for i, (n, _, _, e) in enumerate(MUTANTS):
            print("  %2d  %-58s must be killed by  %s" % (i, n, e))
        return 0
    todo = [MUTANTS[a.only]] if a.only is not None else MUTANTS
    print("mutation testing the contract and the page's risk classifier -- %d mutant(s), "
          "%d known equivalent\n" % (len(todo), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in todo:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-58s %s" % (verdict, name, detail[:58]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    if a.only is None:
        import mutant_ledger
        mutant_ledger.record("mutate_contract", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             "" if a.only is not None else " (recorded)"))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
