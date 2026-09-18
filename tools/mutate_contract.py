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
SUBJECT = ("harness_contract.py", "harness_plugin_page.py",
           "harness_mcp.py", "harness_walk.py",
           "blind_console.py")                     # ADR-191: the code lives in five files

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
     '''                "pluginId": plugin_id, "action": o["action"], "risk": done.risk,''',
     '''                "pluginId": plugin_id, "action": o["action"], "risk": o["declaredRisk"],''',
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
     '''                "declaredRisk": o["declaredRisk"], "riskWhy": o["riskWhy"],''',
     '''                "declaredRisk": o["declaredRisk"], "riskWhy": None,''',
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

MUTANTS += [
    # ---- ADR-189: `stale` is a refusal of its own ------------------------
    ("stale is a spelling of not_found",
     'Stale = _err("stale")',
     'Stale = _err("not_found")',
     "its own code and not a spelling"),
    ("the new code reaches the transport unmapped",
     '        "stale": INVALID_PARAMS,                      # ADR-189: the client\'s, and re-readable',
     '        ',
     "with no code left unmapped"),
    ("the robot counts a moved selector as a failure of the target",
     'REFUSAL = ("invalid_argument", "not_found", "conflict", "stale")   # ADR-189',
     'REFUSAL = ("invalid_argument", "not_found", "conflict")',
     "counts it as a REFUSAL"),
    ("the manifest still says 1.5",
     'PROTOCOL_VERSION = "1.9"',
     'PROTOCOL_VERSION = "1.5"',
     "states a protocol version"),
]

MUTANTS += [
    # ---- ADR-191: the session ---------------------------------------------
    # The stamp
    ("a number that moves on its own moves the stamp with it",
     '    noise = set(spec.get("noise") or ())\n    if not isinstance(snap, dict):',
     '    noise = set()\n    if not isinstance(snap, dict):',
     "the same observation twice gets the same stamp"),
    ("the stamp reads a rebuilt list in the order the rebuild produced",
     '''    keys = spec.get("keys") or {}
    for p in list(paths):
        fields = key_for(p, keys)''',
     '''    keys = spec.get("keys") or {}
    for p in []:
        fields = key_for(p, keys)''',
     "the STAMP does not move with the order"),
    # The diff
    ("a list nobody keyed is diffed entry by entry anyway",
     '        spec_k = key_for(p, keys)',
     '        spec_k = key_for(p, keys) or "self"',
     "is counted, never diffed entry by entry"),
    ("an entry with no identity is named by its whole body",
     '''        k = _key_of(e, fields)
        if k is None:
            na += 1
        else:
            ma[k] = e''',
     '''        k = _key_of(e, fields)
        if k is None:
            ma[json.dumps(e, sort_keys=True, default=str)] = e
        else:
            ma[k] = e''',
     "no identity AT ALL is counted, not named"),
    ("a bucket stops naming entries and says nothing about it",
     '''    if total > cap:
        d["capped"].append({"where": where, "named": cap, "of": total})''',
     '''    if total > cap:
        pass''',
     "SAYS where it stopped"),
    ("a long value rides the diff whole, twice",
     '''    if isinstance(v, str) and len(v) > BRIEF_CAP:
        return v[:BRIEF_CAP] + "…"''',
     '''    if isinstance(v, str) and False:
        return v[:BRIEF_CAP] + "…"''',
     "a diff never carries a value whole"),
    # The session
    ("a stamp the door never issued is diffed against whatever it holds",
     '        if prev is None or prev[0] != since:',
     '        if prev is None:',
     "having a baseline is not the same as having THAT one"),
    ("the act is diffed against the page it made rather than the one it was planned from",
     '            diff = diff_of(before[1], raw, self._spec(plugin, raw))',
     '            diff = diff_of(raw, raw, self._spec(plugin, raw))',
     "LAST SNAPSHOT THIS SESSION SAW"),
    ("an act does not move the session on, so every act diffs from the same morning",
     '''                            str(e)[:160], rid))
        if isinstance(snap, dict):
            self._seen[plugin_id] = (st, raw)''',
     '''                            str(e)[:160], rid))
        if False:
            self._seen[plugin_id] = (st, raw)''',
     "a chain of calls is a chain of changes"),
    ("the baseline carries the stamp, so every diff reports the answer changing",
     '        return served, snap, st',
     '        return served, served, st',
     "the stamp itself is never a field that changed"),
    ("a session with no baseline is handed a diff and no explanation",
     '''            diff = {"since": None,
                    "why": "this session had not observed %s before this call, so there is "
                           "no baseline to diff against" % plugin_id}''',
     '''            diff = {"since": None}''',
     "is TOLD it has no baseline"),
    ("a retired target's baseline outlives it",
     '''        for pid in [k for k in self._seen if k not in live]:
            self._seen.pop(pid, None)''',
     '''        for pid in []:
            self._seen.pop(pid, None)''',
     "is a NEW target"),
    ("a plugin that cannot say what identity means takes the door down",
     '''        try:
            spec = plugin.identity(snap)
        except Exception:
            return {}''',
     '''        if True:
            spec = plugin.identity(snap)''',
     "rather than taking the door down"),
    ("the manifest keeps the session to itself",
     '                "session": {"stamp": "every snapshot carries one; it moves when a value a "',
     '                "_session": {"stamp": "every snapshot carries one; it moves when a value a "',
     "the manifest says the session exists"),
    # The transport
    ("the stamp in the URI is read and thrown away",
     '                since = _unquote(v)',
     '                since = None',
     "answers `nothing changed` and not the snapshot"),
    ("a tool result says what it did and not what it changed",
     '                "stamp": r.get("stamp"), "diff": r.get("diff")}',
     '                }',
     "carries the diff against the snapshot the client planned"),
    ("a tool result carries the whole snapshot after all",
     '                "stamp": r.get("stamp"), "diff": r.get("diff")}',
     '                "stamp": r.get("stamp"), "diff": r.get("diff"),\n                "snapshot": r.get("snapshot")}',
     "and never the snapshot"),
    ("the resource does not say a stamp may ride its URI",
     '                                "Append ?since=<stamp> -- the `stamp` of the last snapshot this "',
     '                                "The stamp is available. "',
     "resources/list says so"),
    # The console
    ("every request gets its own door, so a session remembers nothing",
     '                ans = play(door, req.get("moves") or [])',
     '                ans = play(Door(a.target, a.page, a.seed, a.trace, token), req.get("moves") or [])',
     "reaches the SAME door"),
    ("the console keeps the stamp to itself",
     '''            if m.get("since"):
                uri += "?since=" + quote(str(m["since"]), safe="")''',
     '''            if False:
                uri += "?since=" + quote(str(m["since"]), safe="")''',
     "is still the door's baseline in the next"),
    # ADR-228: the console offers the two things a command says about itself
    ("the console strips both fields off a call, so an operator can send neither",
     '            meta = {k: m[k] for k in ("expires_at", "if_stamp") if m.get(k) is not None}',
     '            meta = {}',
     "refused `stale`, naming the deadline"),
    ("the console forwards a deadline but never a stamp",
     '            meta = {k: m[k] for k in ("expires_at", "if_stamp") if m.get(k) is not None}',
     '            meta = {k: m[k] for k in ("expires_at",) if m.get(k) is not None}',
     "offered to the operator at last"),
    # ---- ADR-194: the rungs are the operator's -----------------------------
    ("the console hands out whatever rungs it likes",
     '''        for rung in (rungs or SUPERVISED):''',
     '''        for rung in RUNGS:''',
     "lists what the supervised three do not"),
    ("a rung named on the command line is ignored",
     '''        for rung in (rungs or SUPERVISED):''',
     '''        for rung in SUPERVISED:''',
     "lists what the supervised three do not"),
    ("the rung a session was opened with is lost when the server is spawned",
     '''    if a.rungs:
        cmd += ["--rungs", ",".join(a.rungs)]''',
     '''    if False:
        cmd += ["--rungs", ",".join(a.rungs)]''',
     "lists what the supervised three do not"),
    ("a rung that is not on the ladder is taken anyway",
     '''    bad = [r for r in (a.rungs or ()) if r not in RUNGS]''',
     '''    bad = []''',
     "refused by name rather than silently dropped"),
    ("a closed session leaves its socket behind, so the next one talks to a corpse",
     '''                    try:
                        os.unlink(path)
                    except OSError:
                        pass''',
     '''                    try:
                        pass
                    except OSError:
                        pass''',
     "takes its socket with it"),
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
        # ADR-191: and a mutant in the MCP adapter or in the console is asserted
        # where the transport is driven. The contract's suite runs too, for the
        # adapter, because ADR-189's refusal-code mapping is held there -- one
        # file, two suites, and the mutant is killed by whichever one made the
        # claim rather than by whichever the runner happened to pick.
        elif os.path.basename(path) == "harness_mcp.py":
            suites = ["verify_contract.py", "verify_mcp.py"]
        elif os.path.basename(path) == "blind_console.py":
            suites = ["verify_mcp.py"]
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


MUTANTS += [
    # ---- ADR-195: a keyed path may carry a wildcard ------------------------
    ("a pattern in the key spec is not a pattern, only a name",
     '        if "*" not in pat:\n            continue',
     '        continue',
     "keys every list under"),
    ("a pattern matches however many segments the path has",
     '        if len(segs) == len(want) and all(a == "*" or a == b for a, b in zip(segs, want)):',
     '        if all(a == "*" or a == b for a, b in zip(segs, want)):',
     "a different length"),
    ("an exact path is looked up through the pattern loop like any other",
     '    if path in keys:\n        return keys[path]',
     '    if path in keys and not any("*" in k for k in keys):\n        return keys[path]',
     "an exact path"),
    ("the stamp reads the key spec the old way, so it cannot see a wildcard",
     '    for p in list(paths):\n        fields = key_for(p, keys)',
     '    for p in list(paths):\n        fields = keys.get(p)',
     "the stamp reads the wildcard the same way the diff does"),
    ("the diff reads the key spec the old way, so it cannot see a wildcard",
     '        spec_k = key_for(p, keys)',
     '        spec_k = keys.get(p)',
     "names what appeared rather than counting it"),
]


MUTANTS += [
    # ---- ADR-196: a diff is evidence ---------------------------------------
    ("a diff does not say what it shortened",
     '    d["trimmed"] = sorted(set(d["trimmed"]))',
     '    d["trimmed"] = []',
     "is NAMED as trimmed"),
    ("both sides of a moved value are cut from the start again",
     '        start = 0 if i <= BRIEF_CAP else i - BRIEF_CAP // 4',
     '        start = 0',
     "both sides of a moved box DIFFER"),
    ("a window does not say it is one",
     '    return ("…" if start else "") + piece + ("…" if start + BRIEF_CAP < len(v) else "")',
     '    return piece',
     "it says it is a window rather than the value"),
    ("a list the diff only counted is called restored",
     '    lost.update(diff.get("counts") or ())',
     '    lost.update(())',
     "COUNTED by the diff and therefore"),
    ("trimmed and unrestored are the same thing after all",
     '    return {"after": after, "approximate": sorted(approx - lost),\n            "unrestored": sorted(lost)}',
     '    return {"after": after, "approximate": [],\n            "unrestored": sorted(lost | approx)}',
     "comes back approximate"),
    ("a diff with no register is taken as having trimmed nothing",
     '    if "trimmed" not in diff:',
     '    if False:',
     "a diff with no register still says what it trimmed"),
    ("what appeared in a keyed list is not put back",
     '        _put(after, p, (list(cur) if isinstance(cur, list) else []) + list(entries))',
     '        _put(after, p, list(cur) if isinstance(cur, list) else [])',
     "and so does a keyed list"),
    ("a path is split back on every separator, whether or not it is one",
     '    node, rest, out = root, path, []',
     '    return path.split(PATH_SEP)\n    node, rest, out = root, path, []',
     "A KEY MAY CONTAIN THE PATH SEPARATOR"),
    ("a stand-in for a whole list that appeared is taken for the list",
     '        if _stand_in(v):\n            lost.add(p)',
     '        if False:\n            lost.add(p)',
     "is UNRESTORED"),
]


MUTANTS += [
    # ---- ADR-220: the receipt is written before the look --------------------
    ("the receipt is written after the look again, so a failed look loses it",
     '        done = _Done(body, None, risk, _held(outcome), outcome=outcome)\n        self._keep(key, done)',
     '        done = _Done(body, None, risk, _held(outcome), outcome=outcome)',
     "leaves the receipt where it is"),
    ("a receipt waiting for its look is completed by ACTING again",
     '                return self._complete(key, plugin, plugin_id, rid, hit, True)',
     '                self._bytes -= self._done.pop(key).nbytes\n                return self.execute(token, plugin_id, command)',
     "THE RETRY IS ANSWERED FROM THE RECEIPT"),
    ("a failed look is reported as an ordinary raise, with nothing about the act having landed",
     '            raise Failed("%s/%s LANDED (ok=%s: %s) and the look afterwards failed: %s -- retry "',
     '            raise Failed("%s/%s (ok=%s: %s): the look afterwards failed: %s -- retry "',
     "AN ACT WHOSE LOOK AFTERWARDS FAILED"),
    ("a command that raised keeps no receipt, and its retry runs it again",
     '            self._keep(key, _Done(body, None, risk, _held(msg), error=msg))\n',
     '',
     "A COMMAND THAT RAISED KEEPS A RECEIPT"),
    ("a failed receipt is served without being re-authorised",
     '            self.policy.authorize(hit.risk)\n            if hit.error is not None:',
     '            if hit.error is not None:',
     "replaying a FAILED receipt"),
    ("a refusal keeps a receipt, so the id it was refused under is spent",
     '        except HarnessError:\n            self.audit.append((time.time(), plugin_id, name, risk, "refused"))\n            raise',
     '        except HarnessError as e:\n            self.audit.append((time.time(), plugin_id, name, risk, "refused"))\n            self._keep(key, _Done(body, None, risk, 0, error=e.message))\n            raise',
     "A REFUSAL KEEPS NO RECEIPT"),
    ("the budget counts the output and not the snapshot, as it did before ADR-220",
     '        self._keep(key, _Done(done.body, resp, done.risk, _held(resp), outcome=o))',
     '        self._keep(key, _Done(done.body, resp, done.risk, _held(o["output"]), outcome=o))',
     "THE BUDGET COUNTS WHAT THE CACHE HOLDS"),
    ("a receipt completed late keeps its old place, and the trim evicts it",
     '        old = self._done.pop(key, None)\n        if old is not None:\n            self._bytes -= old.nbytes',
     '        old = self._done.get(key)\n        if old is not None:\n            self._bytes -= old.nbytes',
     "a receipt completed late moves to the newest position"),
    ("rewriting a receipt counts its bytes twice",
     '        if old is not None:\n            self._bytes -= old.nbytes\n        self._done[key] = done',
     '        if False:\n            self._bytes -= old.nbytes\n        self._done[key] = done',
     "THE BUDGET COUNTS WHAT THE CACHE HOLDS"),
    ("a response that cannot be sized sits in the cache for free",
     '    except Exception:\n        return REPLAY_CACHE_BYTE_LIMIT',
     '    except Exception:\n        return 0',
     "CANNOT BE SIZED"),
    ("the second identical command is run again, not replayed",
     '        hit = self._done.get(key)\n        if hit is not None:',
     '        hit = None\n        if hit is not None:',
     "the second identical command is answered from the cache"),
    ("a different command under a used id is answered with the old command's response",
     '            if hit.body != body:',
     '            if False:',
     "the same request id with different contents"),
    ("the manifest does not state the retry rule",
     '                "replay": {"rule": "retrying a request_id never runs anything twice",',
     '                "replayRule": {"rule": "retrying a request_id never runs anything twice",',
     "the manifest states the retry rule"),
]


MUTANTS += [
    # ---- ADR-222: a command may say when, and from what --------------------
    ("a deadline is read and not enforced",
     '        if self._now() >= when.timestamp():',
     '        if False:',
     "a command that arrives one second after its deadline"),
    ("a command is still wanted AT its deadline",
     '        if self._now() >= when.timestamp():',
     '        if self._now() > when.timestamp():',
     "a command that arrives AT its deadline"),
    ("a deadline with no zone is read as this machine's own",
     '        if when is None or when.tzinfo is None:',
     '        if when is None:',
     "a deadline with no zone"),
    ("a deadline's offset is dropped and its wall time read as UTC",
     '        if self._now() >= when.timestamp():',
     '        if self._now() >= when.replace(tzinfo=datetime.timezone.utc).timestamp():',
     "an offset is read as an offset"),
    ("a deadline guards a receipt too, so an act that happened stops being answerable",
     '        hit = self._done.get(key)\n        if hit is not None:',
     '        self._fresh(command)\n        hit = self._done.get(key)\n        if hit is not None:',
     "A RECEIPT IS SERVED WHATEVER THE CLOCK SAYS"),
    ("a deadline is part of the command, so a retry with a new one is a conflict",
     '        body = json.dumps({"a": name, "g": args}, sort_keys=True)',
     '        body = json.dumps({"a": name, "g": args, "e": command.get("expires_at")}, sort_keys=True)',
     "a retry with a NEW deadline is the same request"),
    ("a bound command is run whether or not the target moved",
     '        if now != want:\n            raise Stale(',
     '        if False:\n            raise Stale(',
     "a command bound to a look the target has moved past"),
    ("the look that checks a binding becomes the session's baseline",
     '            _snap, _raw, now = self._stamped(plugin, plugin.observe(\n                sensitive=bool(self.policy.allow.get("SENSITIVE_READ"))))\n        except Exception as e:\n            raise Unavailable(',
     '            _snap, _raw, now = self._stamped(plugin, plugin.observe(\n                sensitive=bool(self.policy.allow.get("SENSITIVE_READ"))))\n            self._seen[plugin_id] = (now, _raw)\n        except Exception as e:\n            raise Unavailable(',
     "was NOT served or remembered"),
    ("a bound command whose target cannot be looked at is run blind",
     '        except Exception as e:\n            raise Unavailable("%s could not be looked at to check if_stamp',
     '        except Exception as e:\n            return\n            raise Unavailable("%s could not be looked at to check if_stamp',
     "a bound command whose target cannot be looked at"),
    ("an empty if_stamp reads as not asked",
     '        if not isinstance(want, str) or not want:',
     '        if not isinstance(want, str) and want:',
     "an if_stamp that is empty"),
    ("a binding is never checked",
     '        self._unmoved(plugin, plugin_id, command)\n        t0 = time.time()',
     '        t0 = time.time()',
     "a command bound to a look the target has moved past"),
    ("a caller that may not act is given a look for asking",
     '        self._fresh(command)\n        spec = plugin.descriptor().action(name)',
     '        self._fresh(command)\n        self._unmoved(plugin, plugin_id, command)\n        spec = plugin.descriptor().action(name)',
     "is not given a look for asking"),
    ("every command pays for a look, whether or not it asked",
     '        want = command.get("if_stamp")\n        if want is None:\n            return',
     '        want = command.get("if_stamp")\n        if want is None:\n            plugin.observe()\n            return',
     "a command that does not ask pays nothing"),
    ("over MCP a call cannot say either",
     '                if meta.get(k) is not None:\n                    command[k] = meta[k]',
     '                if False:\n                    command[k] = meta[k]',
     "OVER MCP both ride"),
    ("over MCP everything in _meta becomes a field of the command",
     '            for k in ("expires_at", "if_stamp"):\n                if meta.get(k) is not None:',
     '            for k in list(meta):\n                if meta.get(k) is not None:',
     "OVER MCP both ride"),
    ("the manifest does not say what the two fields mean",
     '                "freshness": {"expires_at":',
     '                "freshnessNotes": {"expires_at":',
     "the manifest says what both fields mean"),
    # ---- ADR-229: a stamp says which series it is ---------------------------
    ("every stamp is in the snapshot series, whatever it was asked for",
     '    assert series in STAMP_SERIES, series\n    return series + h',
     '    assert series in STAMP_SERIES, series\n    return "s" + h',
     "one algorithm and the series is one character"),
    ("a report stamp reads as a snapshot stamp",
     '    return STAMP_SERIES.get(stamp[0]) if all(c in "0123456789abcdef" for c in stamp[1:]) else None',
     '    return "snapshot" if all(c in "0123456789abcdef" for c in stamp[1:]) else None',
     "a report stamp is `r` + the same 12 hex"),
    ("if_stamp handed a report stamp goes on to compare it with the snapshot and says the page moved",
     '        if series_of(want) == "report":\n            # ADR-229',
     '        if False:\n            # ADR-229',
     "the wrong KIND, not a moved target"),
    ("if_stamp takes a look before deciding the stamp is the wrong kind",
     '            raise InvalidArgument(\n                "if_stamp guards the SNAPSHOT and %r is a REPORT stamp',
     '            plugin.observe()\n            raise InvalidArgument(\n                "if_stamp guards the SNAPSHOT and %r is a REPORT stamp',
     "no look was taken to find that out"),
    ("observe handed a report stamp calls it unknown",
     '            if series_of(since) == "report":\n                # ADR-229: not unknown',
     '            if False:\n                # ADR-229: not unknown',
     "NAMES THE KIND"),
    ("the manifest does not say which stamp is which",
     '                "stamps": {"snapshot": "s + 12 hex',
     '                "stampNotes": {"snapshot": "s + 12 hex',
     "the manifest publishes both series"),
]


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
