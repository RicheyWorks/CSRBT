# -*- coding: utf-8 -*-
"""Mutation testing for the wire (ADR-221).

verify_frames says nothing a client can send closes a door and that the door
hears what was sent. Every clause of that is a line somebody could delete --
the strict decode, the duplicate-key hook, the bounded read, a type check in
front of a .startswith, the backstop -- and a door that lost one would go on
passing every suite that sends it well-formed ASCII, which until ADR-221 was
every suite there was.

    python3 tools/mutate_frames.py           # run every mutant
    python3 tools/mutate_frames.py --list    # the catalogue

Cheap on purpose (ADR-193's lesson): verify_frames drives fixture targets and no
browser, so a mutant costs seconds. A mutant in harness_contract.py also runs
verify_contract, where the envelope's claims are made.

SAFETY: tools/ is copied to a temp directory (without its traces) and the COPY
is mutated. The real files are never written to.
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("harness_frames.py", "harness_stdio.py", "harness_mcp.py", "harness_http.py",
           "harness_contract.py")

MUTANTS = [
    # ---- the reader -----------------------------------------------------------
    ("bytes that are not UTF-8 are decoded anyway, with whatever fits",
     '            text = data.decode("utf-8")\n',
     '            text = data.decode("utf-8", "replace")\n',
     "a byte that is not UTF-8 is refused"),
    ("text carrying a lone surrogate is let through",
     '        try:\n            text.encode("utf-8")\n',
     '        try:\n            text.encode("utf-8", "surrogatepass")\n',
     "and so is TEXT carrying a lone surrogate"),
    ("a byte-order mark is part of the message",
     '        if data.startswith(BOM):',
     '        if False:',
     "a byte-order mark in front of a frame"),
    ("a key given twice keeps the last one, as json.loads does",
     '        if k in out:\n            raise FrameError("duplicate_key",',
     '        if False:\n            raise FrameError("duplicate_key",',
     "A KEY GIVEN TWICE IS NOT ONE MESSAGE"),
    ("NaN and Infinity are taken as numbers",
     'parse_constant=_constant,\n                          parse_float=_float)',
     'parse_float=_float)',
     "NaN is refused"),
    ("a float too large to be one becomes infinity",
     '    if v != v or v in (float("inf"), float("-inf")):',
     '    if False:',
     "1e999 is refused"),
    ("a nesting too deep to parse leaves as RecursionError",
     '    except RecursionError:\n        raise FrameError("not_json", "nested too deeply to be a message")',
     '    except RecursionError:\n        raise',
     "100,000 open brackets are refused"),
    ("a refused frame ends the reading",
     '        try:\n            yield loads(line), None\n        except FrameError as e:\n            yield None, e',
     '        try:\n            yield loads(line), None\n        except FrameError as e:\n            yield None, e\n            return',
     "A REFUSED FRAME IS FOLLOWED BY THE NEXT ONE"),
    ("an oversized line is read whole",
     '        line = src.readline(cap + 2)',
     '        line = src.readline()',
     "it is never held whole"),
    ("an oversized line is refused and the rest of it is read as the next frame",
     '                if not more or more.endswith(nl):\n                    break',
     '                break',
     "AN OVERSIZED LINE IS DRAINED AND REFUSED AS ONE FRAME"),
    ("the bound is off by one",
     '        if len(line) > cap:\n            yield None, FrameError("too_large"',
     '        if len(line) > cap + 1:\n            yield None, FrameError("too_large"',
     "the bound is exact"),
    ("the pipe doors get a bound of their own, larger than the HTTP door's",
     'FRAME_CAP = 1 << 20',
     'FRAME_CAP = 1 << 25',
     "the bound is the HTTP door's 1 MiB"),
    ("the text face of stdin is read, not the bytes under it",
     '    src = getattr(stream, "buffer", stream)',
     '    src = stream',
     "is read THROUGH it"),
    # ---- stdio ------------------------------------------------------------------
    ("the stdio door does not check a request's shape",
     '        try:\n            _shape(req)\n',
     '        try:\n',
     "stdio, a plugin that is a list: refused invalid_argument"),
    ("a request that is not an object reaches .get",
     '    if not isinstance(req, dict):\n        raise InvalidArgument("a request is one JSON object per line")',
     '    if False:\n        raise InvalidArgument("a request is one JSON object per line")',
     "stdio, a bare list: refused invalid_argument"),
    ("a field the stdio door does not know is dropped without a word",
     '        if extra:\n            raise InvalidArgument("%s takes %s and has no field %s',
     '        if False:\n            raise InvalidArgument("%s takes %s and has no field %s',
     "A MISSPELT FIELD IS REFUSED, NOT IGNORED"),
    ("every op takes every field",
     '        extra = sorted(k for k in req if k not in FIELDS[op])',
     '        extra = sorted(k for k in req if not any(k in f for f in FIELDS.values()))',
     "a field that belongs to ANOTHER op"),
    ("the stdio door has no backstop",
     '        except Exception as e:\n            # THE BACKSTOP. Whatever this is',
     '        except ZeroDivisionError as e:\n            # THE BACKSTOP. Whatever this is',
     "STDIO BACKSTOP"),
    ("a refused frame on stdio is answered with nothing",
     '            _w(stdout, {"ok": False, "code": "invalid_argument",\n                        "message": "%s: %s" % (bad.code, bad.message)})\n            continue',
     '            continue',
     "THE STDIO DOOR OUTLIVES EVERY FRAME"),
    # ---- MCP --------------------------------------------------------------------
    ("a method that is not a string reaches .startswith",
     '        if not isinstance(method, str):\n            return self._error(mid, INVALID_REQUEST, "method must be a string")',
     '        if False:\n            return self._error(mid, INVALID_REQUEST, "method must be a string")',
     "MCP, method is a number: refused"),
    ("params that are not an object reach a lookup",
     '        if not isinstance(params, dict):\n            return self._error(mid, INVALID_PARAMS, "params must be an object")',
     '        if False:\n            return self._error(mid, INVALID_PARAMS, "params must be an object")',
     "MCP, params is a list: refused"),
    ("a tool name that is not a string reaches a dict",
     '        if not isinstance(name, str):\n            raise HarnessError("invalid_argument", "a tool is named by a string")',
     '        if False:\n            raise HarnessError("invalid_argument", "a tool is named by a string")',
     "MCP, the tool name is a list: refused"),
    ("a uri that is not a string reaches .partition",
     '        if not isinstance(uri, str):',
     '        if False:',
     "MCP, the uri is a number: refused"),
    ("the MCP door has no backstop",
     '        except Exception as e:\n            # THE BACKSTOP (ADR-221)',
     '        except ZeroDivisionError as e:\n            # THE BACKSTOP (ADR-221)',
     "MCP BACKSTOP"),
    ("the backstop answers with no id, so the host cannot tell which request failed",
     '            return self._error(mid, INTERNAL_ERROR, "the door raised %s while answering %s: %s"',
     '            return self._error(None, INTERNAL_ERROR, "the door raised %s while answering %s: %s"',
     "MCP BACKSTOP"),
    ("the MCP door reads its lines as the machine decodes them, as it did before ADR-221",
     '    for msg, bad in frames(stdin):\n        if bad is not None:\n            _w(stdout, server._error(None, PARSE_ERROR,',
     '    for msg, bad in ((__import__("harness_frames").loads(l), None) for l in stdin if l.strip()):\n        if bad is not None:\n            _w(stdout, server._error(None, PARSE_ERROR,',
     "THE MCP DOOR OUTLIVES EVERY FRAME"),
    # ---- HTTP -------------------------------------------------------------------
    ("the bearer is compared as text, and an accent raises inside the handler",
     '        if not got.startswith("Bearer ") or not hmac.compare_digest(\n                got[7:].encode("latin-1", "replace"), want.encode("utf-8", "surrogatepass")):',
     '        if not got.startswith("Bearer ") or not hmac.compare_digest(got[7:], want):',
     "a wrong bearer with an accent is ANSWERED 401"),
    ("the HTTP door parses its body leniently, as it did before ADR-221",
     '            body = FR.loads(raw) if raw else None',
     '            body = json.loads(raw.decode("utf-8")) if raw else None',
     "HTTP, a key given twice"),
    # ---- the contract -----------------------------------------------------------
    ("the token is compared as text, and an accent raises TypeError",
     '        if not isinstance(token, str) or not hmac.compare_digest(\n                token.encode("utf-8", "surrogatepass"),\n                self.token.encode("utf-8", "surrogatepass")):',
     '        if not isinstance(token, str) or not hmac.compare_digest(token, self.token):',
     "a wrong non-ASCII token"),
    ("a token that is not text reaches .encode",
     '        if not isinstance(token, str) or not hmac.compare_digest(\n                token.encode("utf-8", "surrogatepass"),',
     '        if not hmac.compare_digest(\n                token.encode("utf-8", "surrogatepass"),',
     "stdio, a token that is a number: refused unauthorized"),
    ("a field a command does not have is ignored, as it was before ADR-221",
     '        if extra:\n            raise InvalidArgument("a command has no field %s; it has %s',
     '        if False:\n            raise InvalidArgument("a command has no field %s; it has %s',
     "a command carrying dry_run"),
    ("two spellings of the id that disagree are filed under the first",
     '        if ("request_id" in command and "requestId" in command\n                and command["request_id"] != command["requestId"]):',
     '        if False:',
     "both spellings of the id, disagreeing"),
    ("two spellings of the id are refused even when they agree",
     '                and command["request_id"] != command["requestId"]):',
     '                and True):',
     "both spellings AGREEING"),
    ("a command that is not an object reaches .get",
     '        if not isinstance(command, dict):\n            raise InvalidArgument("a command is an object")',
     '        if False:\n            raise InvalidArgument("a command is an object")',
     "a command that is null"),
    ("an action that is not a string is looked up anyway",
     '        if not isinstance(name, str):\n            raise InvalidArgument("action must be a string',
     '        if False:\n            raise InvalidArgument("action must be a string',
     "an action that is a list"),
    ("a plugin named by a list reaches a dict lookup",
     '        if not isinstance(plugin_id, str):\n            raise InvalidArgument("a plugin is named by a string")',
     '        if False:\n            raise InvalidArgument("a plugin is named by a string")',
     "a plugin named by a list"),
    ("the manifest does not say what a command may carry",
     '                "commandFields": list(COMMAND_FIELDS),\n',
     '',
     "the manifest lists what a command may carry"),
]

KNOWN_EQUIVALENT = [
]

SUITES = {"harness_contract.py": ["verify_frames.py", "verify_contract.py"]}


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutframes_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence",
                                                                  "traces", "push"))
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
        fails, out, rc = [], "", 0
        for s in SUITES.get(os.path.basename(path), ["verify_frames.py"]):
            try:
                p = subprocess.run([sys.executable, os.path.join(dst, "verify", s)],
                                   capture_output=True, text=True, timeout=900,
                                   env=dict(os.environ, CSRBT_DOCS_DIR=os.path.join(ROOT, "docs")))
            except subprocess.TimeoutExpired:
                return ("BAD MUTANT", "the suite hung rather than failed -- a suite must not be "
                                      "hangable by its own subject (ADR-192)")
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
    print("mutation testing the wire -- %d mutant(s), %d known equivalent\n"
          % (len(todo), len(KNOWN_EQUIVALENT)))
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
        mutant_ledger.record("mutate_frames", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             "" if a.only is not None else " (recorded)"))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
