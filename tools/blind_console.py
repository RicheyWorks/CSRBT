# -*- coding: utf-8 -*-
"""A door, and nothing else: the console a BLIND operator drives (ADR-136).

ADR-126 built the instrument -- the MCP server records a trace, the task
grader holds a trace to a task -- and said plainly what it could not do:

    A blind trial: a model that did not write the tasks. The instrument is
    ready; the operator is not in this sandbox.

This is the operator's side of that trial. It speaks JSON-RPC to
tools/harness_mcp.py over a pipe, and it gives an operator exactly what a
host would have: `tools/list`, `resources/list`, and the ability to call a
tool and read a resource. It gives nothing else. In particular it never
reads tools/tasks/, and the trial is run in a checkout with that directory
removed, so "the operator did not see the steps" is a fact about the
filesystem rather than a promise about someone's attention.

    python3 tools/blind_console.py --target organism --moves moves.json \\
            --trace tools/traces/<task>.jsonl

`moves.json` is a list the operator writes:

    [{"list": true},
     {"call": "csrbt_organism__put", "arguments": {"key": 11, "attr": 1}},
     {"read": "harness://csrbt-organism/snapshot"},
     {"observe": "csrbt-organism"}]

Every move's whole response is printed as JSON, in order, so the operator can
plan the next move from what the door actually answered -- which is the only
thing a real host has to go on either.

ONE DOOR, MANY INVOCATIONS (ADR-191)
    That is a batch, and a batch is not how anyone works. Every operator in
    the third blind trial (ADR-187) wrote a moves file, read the answers,
    wrote a longer moves file, and ran it again -- against a NEW browser, a
    NEW page and a store that had forgotten everything, so the first moves of
    every run were the previous run replayed. Four to six runs each, 200-290
    calls to land 73-89.

    --session NAME keeps the door alive between invocations:

        python3 tools/blind_console.py --session s1 --target page \\
                --page collection-sheet.html --moves first.json
        python3 tools/blind_console.py --session s1 --moves next.json
        python3 tools/blind_console.py --session s1 --end

    The first call starts a server holding the Door and a unix socket; the
    rest hand it moves and print what came back. The page is where the last
    call left it, the store holds what was put in it, and a `since` stamp from
    one invocation is still the door's baseline in the next -- which is the
    whole point, and which the batch console could not do at any length.

    The moves are the same moves, with one addition: a move may carry `since`,

        {"observe": "csrbt-page", "since": "s6c984d475ebd"}

    which asks the door for what CHANGED rather than for the snapshot again.
"""
import argparse, errno, io, json, os, re, secrets, socket, subprocess, sys, tempfile, time
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))


def session_dir():
    d = os.environ.get("CSRBT_BLIND_DIR") or os.path.join(tempfile.gettempdir(), "csrbt-blind")
    try:
        os.makedirs(d, 0o700)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    return d


def sock_path(name):
    # A unix socket path is capped near 104 bytes on every platform that has
    # one, so the name is slugged and cut rather than trusted.
    return os.path.join(session_dir(), re.sub(r"[^A-Za-z0-9_.-]", "_", name)[:32] + ".sock")


class Door(object):
    """The MCP server as a child process, spoken to in JSON-RPC."""

    def __init__(self, target, page, seed, trace, token):
        env = dict(os.environ)
        env["CSRBT_HARNESS_ENABLED"] = "true"
        env["CSRBT_HARNESS_TOKEN"] = token
        # the rungs a supervised operator gets: read what is entered, draft,
        # and write. Not DESTRUCTIVE -- an operator that can wipe the store is
        # not being supervised, it is being trusted.
        for rung in ("SENSITIVE_READ", "DRAFT", "MUTATE"):
            env["CSRBT_HARNESS_ALLOW_" + rung] = "true"
        cmd = [sys.executable, os.path.join(HERE, "harness_mcp.py"),
               "--target", target, "--page", page, "--seed", str(seed)]
        if trace:
            cmd += ["--trace", trace]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env, text=True, bufsize=1)
        self.n = 0
        self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                "clientInfo": {"name": "blind-operator", "version": "1"}})

    def rpc(self, method, params=None):
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": method}
        if params is not None:
            msg["params"] = params
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise SystemExit("the door closed: %s" % (self.p.stderr.read() or "")[-400:])
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("id") == self.n:
                return r

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=20)
        except Exception:
            self.p.kill()


def play(door, moves):
    """Run moves against an open door and return the answers. The only place
    a move is interpreted, so the batch console and the session server cannot
    drift into meaning different things by the same move."""
    out = []
    for i, m in enumerate(moves):
        t0 = time.time()
        if m.get("list"):
            r = door.rpc("tools/list")
        elif "read" in m:
            r = door.rpc("resources/read", {"uri": m["read"]})
        elif "observe" in m:
            # ADR-191: `since` is the stamp of the last snapshot this session
            # read. It rides in the resource URI because that is where the MCP
            # transport takes it, so this console is asking for the change the
            # same way any host would.
            uri = "harness://%s/snapshot" % m["observe"]
            if m.get("since"):
                uri += "?since=" + quote(str(m["since"]), safe="")
            r = door.rpc("resources/read", {"uri": uri})
        elif "call" in m:
            r = door.rpc("tools/call", {"name": m["call"], "arguments": m.get("arguments") or {}})
        else:
            r = {"error": {"message": "a move is one of list, call, read, observe: %r" % m}}
        out.append({"move": i, "asked": m, "answer": r, "ms": int((time.time() - t0) * 1000)})
    return out


def serve_session(name, a, token):
    """Hold one door open behind a unix socket until someone says end.

    Serial by construction -- one connection at a time, one operator. A
    session with two clients talking to the same page at once would be a
    different experiment than the one this console is for."""
    path = sock_path(name)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        os.unlink(path)
    except OSError:
        pass
    srv.bind(path)
    os.chmod(path, 0o600)
    srv.listen(1)
    door = Door(a.target, a.page, a.seed, a.trace, token)
    sys.stderr.write("blind session %r open on %s\n" % (name, path))
    sys.stderr.flush()
    try:
        while True:
            conn, _ = srv.accept()
            f = conn.makefile("rwb")
            try:
                line = f.readline()
                if not line:
                    continue
                req = json.loads(line.decode("utf-8"))
                if req.get("end"):
                    # The socket goes BEFORE the answer, not after. A caller
                    # that has been told the session ended must not be able to
                    # connect to it a moment later -- and unlinking in the
                    # `finally` alone is a race the suite loses about half the
                    # time, because the answer reaches the client first.
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                    f.write((json.dumps({"ended": name,
                                         "socketRemoved": not os.path.exists(path)})
                             + "\n").encode("utf-8"))
                    f.flush()
                    return 0
                if req.get("ping"):
                    f.write((json.dumps({"alive": name, "target": a.target,
                                         "page": a.page}) + "\n").encode("utf-8"))
                    f.flush()
                    continue
                ans = play(door, req.get("moves") or [])
                f.write((json.dumps({"answers": ans}, ensure_ascii=False) + "\n").encode("utf-8"))
                f.flush()
            except Exception as e:
                try:
                    f.write((json.dumps({"error": str(e)[:300]}) + "\n").encode("utf-8"))
                    f.flush()
                except Exception:
                    pass
            finally:
                try:
                    f.close()
                    conn.close()
                except Exception:
                    pass
    finally:
        door.close()
        try:
            os.unlink(path)
        except OSError:
            pass


def ask_session(name, payload, timeout=600):
    """One request to a running session. Returns None if nothing is listening
    -- a stale socket file is not a session, and is treated as its absence."""
    path = sock_path(name)
    if not os.path.exists(path):
        return None
    c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    c.settimeout(timeout)
    try:
        c.connect(path)
    except OSError:
        try:
            os.unlink(path)
        except OSError:
            pass
        return None
    try:
        f = c.makefile("rwb")
        f.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        f.flush()
        line = f.readline()
        return json.loads(line.decode("utf-8")) if line else {"error": "the session closed"}
    finally:
        try:
            c.close()
        except Exception:
            pass


def start_session(name, a):
    """Start the server as a detached child and wait for its socket.

    Detached on purpose: the point of a session is that it outlives the
    invocation that made it, so it must not die with this process's terminal
    or with this process."""
    path = sock_path(name)
    cmd = [sys.executable, os.path.abspath(__file__), "--serve-session", name,
           "--target", a.target, "--page", a.page, "--seed", str(a.seed)]
    if a.trace:
        cmd += ["--trace", a.trace]
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                     stdout=open(os.devnull, "w"), stderr=open(path + ".log", "w"),
                     start_new_session=True)
    for _ in range(600):
        if ask_session(name, {"ping": True}, timeout=20):
            return True
        time.sleep(0.25)
    return False


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="organism",
                    choices=["page", "organism", "lab", "both", "all", "fixture"])
    ap.add_argument("--page", default="collection-sheet.html")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--moves", help="a JSON file of moves; omit to just list what the door offers")
    ap.add_argument("--trace", help="record every call here (the file the grader reads)")
    ap.add_argument("--session", metavar="NAME",
                    help="keep the door open between invocations under this name (ADR-191). "
                         "The first call with --target starts it; later calls need only "
                         "--session and --moves; --end closes it.")
    ap.add_argument("--end", action="store_true", help="close the named session")
    ap.add_argument("--serve-session", metavar="NAME",
                    help=argparse.SUPPRESS)
    ap.add_argument("--cap", type=int, default=0, metavar="N",
                    help="print at most N characters of each answer, saying so when it bites. "
                         "The default, 0, prints the whole answer -- a snapshot is the discovery "
                         "path and a clipped one does not parse (ADR-141).")
    a = ap.parse_args(argv)

    token = "blind-" + secrets.token_urlsafe(24)

    if a.serve_session:
        return serve_session(a.serve_session, a, token)

    if a.session:
        if a.end:
            r = ask_session(a.session, {"end": True}, timeout=60)
            print(json.dumps(r if r is not None
                             else {"ended": a.session, "note": "it was not running"}))
            return 0
        if ask_session(a.session, {"ping": True}, timeout=20) is None:
            if not start_session(a.session, a):
                print(json.dumps({"error": "session %r would not start; see %s.log"
                                           % (a.session, sock_path(a.session))}))
                return 2
        moves = json.load(io.open(a.moves, encoding="utf-8")) if a.moves else [{"list": True}]
        r = ask_session(a.session, {"moves": moves})
        if r is None or "answers" not in r:
            print(json.dumps(r or {"error": "the session went away mid-call"}))
            return 2
        for one in r["answers"]:
            line = json.dumps(one, ensure_ascii=False)
            if a.cap and len(line) > a.cap:
                line = (line[:a.cap] + '\n... [%d of %d characters shown: this console was run '
                        'with --cap %d]' % (a.cap, len(line), a.cap))
            print(line)
        return 0

    door = Door(a.target, a.page, a.seed, a.trace, token)
    out = []
    try:
        if not a.moves:
            tools = door.rpc("tools/list").get("result", {}).get("tools", [])
            res = door.rpc("resources/list").get("result", {}).get("resources", [])
            print(json.dumps({"tools": tools, "resources": res}, indent=1, ensure_ascii=False))
            return 0
        moves = json.load(io.open(a.moves, encoding="utf-8"))
        for one in play(door, moves):
            out.append(one)
            # ADR-141: WHOLE, by default. This printed [:4000] and said nothing
            # about it, so a snapshot -- the documented way to discover a page's
            # controls, and 40KB on the science pages -- arrived as truncated
            # JSON that would not parse. Two of the four blind operators gave up
            # on this console and wrote their own JSON-RPC client, which means
            # the trial was measuring the console rather than the door. A cap is
            # available and, when it bites, SAYS it bit.
            line = json.dumps(out[-1], ensure_ascii=False)
            if a.cap and len(line) > a.cap:
                line = (line[:a.cap] + '\n... [%d of %d characters shown: this console was run '
                        'with --cap %d]' % (a.cap, len(line), a.cap))
            print(line)
    finally:
        door.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
