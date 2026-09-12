# -*- coding: utf-8 -*-
"""Mutation testing for the HTTP transport (ADR-192).

The other two transports can only be spoken to by the process that started
them. This one listens on a socket, and every claim `verify_http` makes about
that -- the origin check, the bearer token, the one session, the one thread
that may touch the target -- is a claim about what happens when something the
operator did not start knocks on the door. A suite that asserted those and
could not be broken by removing them would be decoration on a network
listener, which is the worst place in this kit to have any.

    python3 tools/mutate_http.py           # run every mutant
    python3 tools/mutate_http.py --list    # the catalogue

SAFETY: tools/ is copied to a temp directory and the COPY is mutated. The real
harness_http.py is never written to.
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("harness_http.py",)

MUTANTS = [
    # ---- the switch ------------------------------------------------------
    ("a network door opens on the kit's switch alone",
     '''    if (os.environ.get("CSRBT_HARNESS_HTTP") or "").lower() not in ("1", "true", "yes"):''',
     '''    if False:''',
     "says which switch it wants"),

    # ---- the origin ------------------------------------------------------
    ("any page anywhere may drive the door",
     '''        if not _origin_ok(self.headers.get("Origin")):''',
     '''        if False:''',
     "DNS rebinding"),
    ("an origin is a substring match, so evil.example.127.0.0.1.nip.io gets in",
     '''    return (u.hostname or "").lower() in LOOPBACK''',
     '''    return any(x in (origin or "").lower() for x in LOOPBACK)''',
     "DNS rebinding"),
    ("a request with no Origin is refused, and every non-browser host with it",
     '''    if not origin:
        return True''',
     '''    if not origin:
        return False''',
     "a non-browser client and is allowed through"),
    ("the token is checked first, so a rebinding request is told to try a token",
     '''        if not _origin_ok(self.headers.get("Origin")):
            self._refuse(403, "Origin %r is not loopback: a page served from somewhere else "
                              "may not drive this door" % self.headers.get("Origin"))
            return False
        got = (self.headers.get("Authorization") or "")''',
     '''        got = (self.headers.get("Authorization") or "")''',
     "origin is checked BEFORE the token"),

    # ---- the token -------------------------------------------------------
    ("the door takes anyone",
     '''        if not got.startswith("Bearer ") or not hmac.compare_digest(got[7:], want):''',
     '''        if False:''',
     "no bearer token is 401"),
    ("a token is compared in whatever time it takes",
     '''hmac.compare_digest(got[7:], want)''',
     '''got[7:] == want''',
     "constant-time comparison"),
    ("any bearer token will do",
     '''        if not got.startswith("Bearer ") or not hmac.compare_digest(got[7:], want):''',
     '''        if not got.startswith("Bearer "):''',
     "a token that is nearly right is 401"),
    ("the route is checked after the token, so a wrong path asks for credentials",
     '''        if urlparse(self.path).path != PATH:
            self._refuse(404, "no resource %r; this server serves %s only"
                         % (self.path, PATH))
            return False''',
     '''        if False:
            return False''',
     "the route is answered BEFORE the token"),

    # ---- the session -----------------------------------------------------
    ("a second host claims the same page",
     '''            if door.session is not None:''',
     '''            if False:''',
     "a SECOND initialize is a conflict"),
    ("any session id is this door's",
     '''        if door.session is None or given != door.session:''',
     '''        if False:''',
     "a request with no session id is 404"),
    ("an ended session's id keeps working",
     '''    def release(self):
        self.session = None''',
     '''    def release(self):
        self.ended = True''',
     "the id it issued is then one it does not know"),
    ("a session id is a name rather than a secret",
     '''        self.session = secrets.token_urlsafe(24)''',
     '''        self.session = "session"''',
     "long enough not to be guessed"),

    # ---- the frame -------------------------------------------------------
    ("a body of any size is read whole",
     '''        if n > BODY_CAP:''',
     '''        if False:''',
     "over the cap is refused"),
    ("a batch is answered as one message",
     '''
        return self._send(200, out if batch else out[0], extra=extra)''',
     '''
        return self._send(200, out[0], extra=extra)''',
     "answered as a batch, in order"),
    ("a notification is answered with a body it did not ask for",
     '''        if not out and not notes:''',
     '''        if False:''',
     "202 and no body"),
    ("PUT and PATCH are served",
     '''    def _not_allowed(self):
        self._refuse(405, "this door takes POST, GET and DELETE",''',
     '''    def _not_allowed(self):
        self._send(200, {"ok": True},''',
     "PUT is not one of this door's three methods"),
    ("a GET is a GET, stream or no stream",
     '''        if SSE not in (self.headers.get("Accept") or ""):
            return self._refuse(405, "GET %s is the notification stream; ask for %s"
                                % (PATH, SSE))''',
     '''        if False:
            return None''',
     "told what GET is for here"),

    # ---- the thread ------------------------------------------------------
    ("the target is driven from whatever thread the request landed on",
     '''            out = door.on_target_thread(
                lambda: [r for r in (door.server.handle(m) for m in msgs) if r is not None])''',
     '''            out = [r for r in (door.server.handle(m) for m in msgs) if r is not None]''',
     "refuses any thread but its own"),
    ("the pump runs on a thread of its own, which is not the one that stood the target up",
     '''    spin = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.2},
                            daemon=True)
    spin.start()
    try:
        door.pump()''',
     '''    spin = threading.Thread(target=door.pump, daemon=True)
    spin.start()
    try:
        httpd.serve_forever(poll_interval=0.2)''',
     "the real collection sheet"),

    # ---- the notices -----------------------------------------------------
    ("a notice is delivered to the stream AND to the POST",
     '''        with self.lock:
            if to_stream != self.streaming:
                return []
            return self.server.drain()''',
     '''        with self.lock:
            return self.server.drain()''',
     "NOT also on the POST"),
    ("the answer goes out before the notice that its list moved",
     '''                      for x in notes + out]''',
     '''                      for x in out + notes]''',
     "they come FIRST"),
    ("a notice a client could not take is thrown away",
     '''                with door.lock:
                    door.server._notes[0:0] = notes''',
     '''                with door.lock:
                    pass''',
     "the next POST that CAN take a stream"),
    ("two readers share one queue",
     '''            if door.streaming:
                return self._refuse(409, "a notification stream is already open on this session")''',
     '''            if False:
                return None''',
     "a second stream on one session is a conflict"),

    # ---- the bind --------------------------------------------------------
    ("the door binds everywhere by default",
     '''    want = os.environ.get("CSRBT_HARNESS_HTTP_BIND")
    if not want:
        return "127.0.0.1", None''',
     '''    want = os.environ.get("CSRBT_HARNESS_HTTP_BIND")
    if not want:
        return "0.0.0.0", None''',
     "binds loopback with nothing set"),
    ("binding off loopback says nothing about it",
     '''    return want, ("bound to %s, NOT loopback, because CSRBT_HARNESS_HTTP_BIND said so: "''',
     '''    return want, ("bound to %s, because CSRBT_HARNESS_HTTP_BIND said so: "''',
     "says loudly what it"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="muthttp_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        # verify_http stands a real page server up, and _kit resolves docs/
        # beside tools/. Linked, not copied: nothing here writes to the kit and
        # a mutant must not be able to.
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
        try:
            p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_http.py")],
                               capture_output=True, text=True, timeout=900,
                               env=dict(os.environ, CSRBT_DOCS_DIR=os.path.join(ROOT, "docs")))
        except subprocess.TimeoutExpired:
            # A MUTANT THAT HANGS THE SUITE IS A VERDICT, NOT AN EXCEPTION. This
            # runner lost a whole sweep to one: a door that answers a request it
            # should have refused by opening an endless stream leaves the suite
            # reading it forever, and an uncaught TimeoutExpired takes the other
            # twenty-five mutants down with it. Reported as inconclusive, which
            # is what it is -- and which is fixed in the SUITE, by giving the
            # check a timeout shorter than the stream's heartbeat.
            return ("BAD MUTANT", "the suite never finished: this mutant hangs it rather "
                                  "than failing it, so nothing was measured")
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        if not fails and p.returncode != 0:
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
            print("  %2d  %-62s must be killed by  %s" % (i, n, e))
        return 0
    todo = [MUTANTS[a.only]] if a.only is not None else MUTANTS
    print("mutation testing the HTTP transport -- %d mutant(s), %d known equivalent\n"
          % (len(todo), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in todo:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-62s %s" % (verdict, name, detail[:54]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    if a.only is None:
        sys.path.insert(0, TOOLS)
        import mutant_ledger
        mutant_ledger.record("mutate_http", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             "" if a.only is not None else " (recorded)"))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
