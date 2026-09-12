# -*- coding: utf-8 -*-
"""The third transport: MCP over streamable HTTP (ADR-192).

stdio has been enough for two years of this kit's own clients, and it is
exactly the wrong shape for the thing the operator API is for. A stdio server
can only be spoken to by the process that launched it. Every host that matters
-- Claude Desktop's remote servers, an IDE, an agent runtime, anything that
did not start this container -- connects over HTTP.

So: the same four operations, the same Server, a different frame.

    POST   /mcp   a JSON-RPC message (or a batch). The answer is
                  application/json, or text/event-stream when this call
                  produced notifications the host is owed.
    GET    /mcp   an SSE stream for server -> client notifications.
    DELETE /mcp   end the session.

THE SERVER IS NOT REIMPLEMENTED HERE. `harness_mcp.Server.handle` is the only
thing that knows what a method means, and this file imports it. That is the
whole claim of ADR-102 ("a transport maps four operations and decides
nothing") put under load: if a second transport had to re-derive `tools/call`,
the boundary would be in the wrong place. Everything below is HTTP -- routing,
framing, a session id, and the three things a network listener owes that a
pipe does not.

WHAT A PIPE DID NOT OWE
    1. A SECOND SWITCH. The kit is already off unless CSRBT_HARNESS_ENABLED
       and a 24-character token. A listening socket is a larger thing than a
       pipe: a pipe can be written to only by whoever opened it, a port by
       anything that can reach it. CSRBT_HARNESS_HTTP=true is required as
       well, so nobody turns on a network door by copying a stdio command
       line.
    2. LOOPBACK. It binds 127.0.0.1. Binding anywhere else takes
       CSRBT_HARNESS_HTTP_BIND naming the address, and the server says on
       stderr what it did. The MCP specification says a local server SHOULD
       bind localhost; a door with a risk ladder behind it should have to be
       ASKED to do otherwise.
    3. ORIGIN. Every request's Origin header is checked, and a request from a
       page that is not loopback is refused -- DNS rebinding, which is the one
       attack a localhost-only server is still exposed to, because the
       attacker's javascript runs in a browser that can reach localhost. A
       request with NO Origin is a non-browser client and is allowed; that is
       what the header's absence means.

ONE SESSION. This door fronts one browser page, or one organism. Two hosts
driving one page at once is not a smaller version of two hosts driving two
pages -- it is two operators typing into the same form. The first initialize
claims the session; a second is refused with a conflict that says so. The id
is issued in Mcp-Session-Id on the initialize response and required on every
request after it; an id this server does not know is a 404, which is the
specification's way of telling a host to initialize again.

    CSRBT_HARNESS_ENABLED=true CSRBT_HARNESS_HTTP=true \\
    CSRBT_HARNESS_TOKEN=<24+ chars> CSRBT_HARNESS_ALLOW_MUTATE=true \\
    python3 tools/harness_http.py --target organism --port 8931
"""
import argparse, hmac, io, json, os, queue, secrets, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harness_contract import Gateway, Registry
from harness_mcp import Server
from harness_targets import require_policy, stand_up, tear_down

PATH = "/mcp"
SESSION_HEADER = "Mcp-Session-Id"
# A JSON-RPC message is small. A megabyte is already a hundred times the
# largest call this door takes, and a cap that is never reached in normal use
# is the only kind worth having: an unbounded read is how a listener is turned
# into a memory exhaustion.
BODY_CAP = 1 << 20
# How much of an oversized body is read and thrown away before the refusal, so
# the sender sees a 413 rather than a broken pipe. Past it the socket is just
# closed.
DRAIN_CAP = 8 << 20
LOOPBACK = ("127.0.0.1", "::1", "localhost")
SSE = "text/event-stream"
# How often the SSE stream looks for something to send, and how often it sends
# a comment when there is nothing. The comment is not decoration: a proxy that
# sees no bytes for a minute closes the connection, and a host that loses its
# notification stream has no way to know its tool list moved.
POLL_S = 0.2
HEARTBEAT_S = 15.0
# How long a request waits for the one thread that may touch the target. Long,
# because a page action settles (ADR-189) and a science page can take seconds;
# finite, because a request that waits forever on a thread that has died is a
# host that never learns anything went wrong.
TARGET_WAIT_S = 300.0


class Door(object):
    """One Server, one session, one THREAD, and the lock that keeps a
    notification from being delivered twice.

    THE THREAD IS NOT AN OPTIMISATION, IT IS THE WHOLE REASON THIS CLASS
    EXISTS. An HTTP server answers each request on a thread of its own; the
    page plugin drives Playwright's synchronous API, which is bound to the
    thread that created it and raises "Cannot switch to a different thread" on
    any other. Over stdio nobody noticed, because a pipe is read by one thread
    and there was never a second. The first external host to connect over HTTP
    got `ready: false` and a greenlet error where the collection sheet should
    have been -- a defect this transport did not cause but was the first thing
    to reveal.

    So every gateway call is handed BACK to the thread that stood the target
    up, and that thread is the one calling `pump()`. Requests queue; the target
    is driven serially, which is what "one session, one target" already meant
    and is now enforced rather than assumed."""

    def __init__(self, server):
        self.server = server
        self.session = None
        self.ended = False
        self.streaming = False
        self.lock = threading.Lock()
        self.posts = 0
        self._work = queue.Queue()
        self._stop = threading.Event()

    def pump(self):
        """Run the target's work, forever, on THIS thread. The caller must be
        the thread that stood the target up."""
        while not self._stop.is_set():
            try:
                job = self._work.get(timeout=POLL_S)
            except queue.Empty:
                continue
            fn, box, done = job
            try:
                box["r"] = fn()
            except BaseException as e:                       # noqa: BLE001
                box["e"] = e
            finally:
                done.set()

    def stop(self):
        self._stop.set()

    def on_target_thread(self, fn):
        """Run fn where the target lives, and raise whatever it raised."""
        box, done = {}, threading.Event()
        self._work.put((fn, box, done))
        if not done.wait(TARGET_WAIT_S):
            raise RuntimeError("the thread that owns this target did not answer in %ds"
                               % int(TARGET_WAIT_S))
        if "e" in box:
            raise box["e"]
        return box["r"]

    def claim(self):
        self.session = secrets.token_urlsafe(24)
        self.ended = False
        return self.session

    def release(self):
        self.session = None
        self.ended = True

    def take_notes(self, to_stream):
        """The notices queued so far, for exactly one deliverer.

        A host with an SSE stream open reads its notifications there; one
        without reads them on the POST that caused them. Draining under the
        lock, with the deliverer named, is what stops a notice going to both --
        and a `tools/list_changed` delivered twice is a host that re-reads a
        list it has already re-read, which is merely wasteful, and a notice
        delivered to NEITHER is a host acting on a list that has moved."""
        with self.lock:
            if to_stream != self.streaming:
                return []
            return self.server.drain()


def _origin_ok(origin):
    """A request from a page that is not loopback is refused.

    No Origin at all is a non-browser client -- curl, an SDK, a host process --
    and is allowed, because that is what the header's absence means. A browser
    always sends one, so this is the whole of the DNS-rebinding defence: an
    attacker's page on evil.example can reach 127.0.0.1, and this is what says
    no when it does."""
    if not origin:
        return True
    try:
        u = urlparse(origin)
    except Exception:
        return False
    if u.scheme not in ("http", "https"):
        return False
    return (u.hostname or "").lower() in LOOPBACK


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "csrbt-harness"
    sys_version = ""

    # -- the frame ----------------------------------------------------------
    def log_message(self, fmt, *args):
        """Silent by default. This server's stderr is where the operator reads
        what it bound to, and a request log would bury it -- and would write
        every URL, which is where ADR-191 put a session's stamp."""
        if os.environ.get("CSRBT_HARNESS_HTTP_LOG"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code, body=None, ctype="application/json", extra=None):
        raw = b"" if body is None else (
            body if isinstance(body, bytes) else json.dumps(body, default=str).encode("utf-8"))
        self.send_response(code)
        if raw:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def _refuse(self, code, why, extra=None):
        self._send(code, {"error": {"code": code, "message": why}}, extra=extra)
        return None

    def _gate(self):
        """Route, origin, token -- in that order, and the order is the point.

        A wrong path is answered before anything is checked because it reveals
        nothing. Origin comes before the token because a rebinding request has
        already been MADE by the time it arrives: the answer to it is "that
        browser may not talk to me", not "try a token". And the token last,
        because it is the thing worth being careful with."""
        if urlparse(self.path).path != PATH:
            self._refuse(404, "no resource %r; this server serves %s only"
                         % (self.path, PATH))
            return False
        if not _origin_ok(self.headers.get("Origin")):
            self._refuse(403, "Origin %r is not loopback: a page served from somewhere else "
                              "may not drive this door" % self.headers.get("Origin"))
            return False
        got = (self.headers.get("Authorization") or "")
        want = self.server.door.server.token
        if not got.startswith("Bearer ") or not hmac.compare_digest(got[7:], want):
            self._refuse(401, "this door takes a bearer token",
                         extra={"WWW-Authenticate": 'Bearer realm="csrbt-harness"'})
            return False
        return True

    def _session_ok(self, is_init):
        door = self.server.door
        given = self.headers.get(SESSION_HEADER)
        if is_init:
            if door.session is not None:
                self._refuse(409, "a session is already open on this door, and it fronts one "
                                  "target: two hosts driving one page at once is two operators "
                                  "typing into the same form. DELETE %s to end it." % PATH)
                return False
            return True
        if door.session is None or given != door.session:
            # 404 is the specification's "initialize again", and it is the
            # right answer for an id from a door that has since restarted.
            self._refuse(404, "no session %r on this door: initialize to start one" % given)
            return False
        return True

    # -- POST ---------------------------------------------------------------
    def do_POST(self):
        if not self._gate():
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._refuse(400, "Content-Length is not a number")
        if n > BODY_CAP:
            # DRAIN, BOUNDED, THEN REFUSE. Answering without reading anything
            # leaves the client writing into a socket nobody is reading, which
            # it sees as a broken pipe rather than as a 413 -- so the refusal
            # never arrives and the caller cannot tell a cap from a crash. So
            # the body is read and thrown away in chunks, never held, and only
            # up to a bound: past that the connection is simply closed, because
            # a sender still going at eight megabytes is not making a mistake
            # this door owes an explanation for.
            left = min(n, DRAIN_CAP)
            while left > 0:
                got = self.rfile.read(min(65536, left))
                if not got:
                    break
                left -= len(got)
            self.close_connection = True
            return self._refuse(413, "a JSON-RPC message over %d bytes is not one of this "
                                     "door's" % BODY_CAP, extra={"Connection": "close"})
        raw = self.rfile.read(n) if n else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else None
        except Exception as e:
            return self._send(400, {"jsonrpc": "2.0", "id": None,
                                    "error": {"code": -32700,
                                              "message": "parse error: %s" % str(e)[:80]}})
        batch = isinstance(body, list)
        msgs = body if batch else [body]
        if not msgs or not all(isinstance(m, dict) for m in msgs):
            return self._send(400, {"jsonrpc": "2.0", "id": None,
                                    "error": {"code": -32600,
                                              "message": "not a JSON-RPC 2.0 request or batch"}})
        door = self.server.door
        is_init = len(msgs) == 1 and msgs[0].get("method") == "initialize"
        if not self._session_ok(is_init):
            return
        extra = {}
        if is_init:
            extra[SESSION_HEADER] = door.claim()
        door.posts += 1
        try:
            out = door.on_target_thread(
                lambda: [r for r in (door.server.handle(m) for m in msgs) if r is not None])
        except RuntimeError as e:
            return self._refuse(503, str(e))
        notes = door.take_notes(to_stream=False)
        if not out and not notes:
            # Every message was a notification. The specification says 202 and
            # no body, and a body here would be a response to something that
            # asked for none.
            return self._send(202, None, extra=extra)
        if notes:
            # THE NOTICE GOES OUT BEFORE THE ANSWER (ADR-137), which over a
            # stream is not a convention but the only ordering there is: a host
            # must never read the response to `attach` -- which names the tools
            # it may now call -- before the notice that its list moved. A
            # single JSON object cannot carry two messages, so this is what the
            # specification's event stream is FOR, and why it requires a POST's
            # Accept to list `text/event-stream` beside `application/json`.
            if SSE not in (self.headers.get("Accept") or ""):
                # A NOTICE IS NEVER DISCARDED BECAUSE OF AN ACCEPT HEADER. The
                # specification requires a POST to accept both, and a client
                # that does not is not a reason to drop what it is owed or --
                # worse -- to refuse a call that has ALREADY been executed. The
                # answer goes back as the one JSON object it asked for, the
                # notices go back on the queue for a stream or the next POST
                # that can take them, and the header says how many are waiting.
                with door.lock:
                    door.server._notes[0:0] = notes
                extra["Mcp-Notifications-Pending"] = str(len(notes))
                return self._send(200, out if batch else out[0], extra=extra)
            chunks = [b"data: " + json.dumps(x, default=str).encode("utf-8") + b"\n\n"
                      for x in notes + out]
            return self._send(200, b"".join(chunks), ctype=SSE, extra=extra)
        return self._send(200, out if batch else out[0], extra=extra)

    # -- GET: the notification stream ---------------------------------------
    def do_GET(self):
        if not self._gate():
            return
        if SSE not in (self.headers.get("Accept") or ""):
            return self._refuse(405, "GET %s is the notification stream; ask for %s"
                                % (PATH, SSE))
        if not self._session_ok(False):
            return
        door = self.server.door
        with door.lock:
            if door.streaming:
                return self._refuse(409, "a notification stream is already open on this session")
            door.streaming = True
        try:
            self.send_response(200)
            self.send_header("Content-Type", SSE)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            last = time.time()
            while not door.ended:
                for note in door.take_notes(to_stream=True):
                    self.wfile.write(b"data: " + json.dumps(note, default=str).encode("utf-8")
                                     + b"\n\n")
                    self.wfile.flush()
                    last = time.time()
                if time.time() - last > HEARTBEAT_S:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    last = time.time()
                time.sleep(POLL_S)
        except Exception:
            pass                                  # the host hung up; that is allowed
        finally:
            with door.lock:
                door.streaming = False

    # -- DELETE -------------------------------------------------------------
    def do_DELETE(self):
        if not self._gate():
            return
        if not self._session_ok(False):
            return
        self.server.door.release()
        self._send(204, None)

    def do_PUT(self):
        self._not_allowed()

    def do_PATCH(self):
        self._not_allowed()

    def _not_allowed(self):
        self._refuse(405, "this door takes POST, GET and DELETE",
                     extra={"Allow": "POST, GET, DELETE"})


def serve(server, host="127.0.0.1", port=0, ready=None):
    """Serve until stopped, with THIS thread doing the target's work.

    The listener runs on a thread of its own and the caller's thread becomes
    the pump -- which is the wrong way round for an HTTP server and the only
    way round for this one, because the caller is the thread that stood the
    target up and Playwright will not be driven from anywhere else.

    `ready` is called with the HTTPServer once it is bound, which is how a
    caller learns the port the kernel chose without racing the bind."""
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    door = httpd.door = Door(server)
    if ready:
        ready(httpd)
    spin = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.2},
                            daemon=True)
    spin.start()
    try:
        door.pump()
    finally:
        door.stop()
        httpd.shutdown()
    return httpd


def bind_address():
    """127.0.0.1 unless asked otherwise, and asking is explicit.

    A door with MUTATE behind it that binds 0.0.0.0 because someone copied a
    command line is the failure this returns a constant to avoid."""
    want = os.environ.get("CSRBT_HARNESS_HTTP_BIND")
    if not want:
        return "127.0.0.1", None
    return want, ("bound to %s, NOT loopback, because CSRBT_HARNESS_HTTP_BIND said so: "
                  "every host that can reach this address can reach this door, and the "
                  "token is all that is between them" % want)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default="ecology.html")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--target", default="page",
                    choices=["page", "organism", "lab", "both", "all", "fixture"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--port", type=int, default=0,
                    help="0 (the default) takes a free port and prints it")
    ap.add_argument("--trace", default=os.environ.get("CSRBT_HARNESS_TRACE"),
                    help="append every tools/call and its response here (ADR-126)")
    ap.add_argument("--attachable", action="store_true")
    a = ap.parse_args()

    if (os.environ.get("CSRBT_HARNESS_HTTP") or "").lower() not in ("1", "true", "yes"):
        sys.stderr.write("the HTTP transport is off: set CSRBT_HARNESS_HTTP=true as well as "
                         "CSRBT_HARNESS_ENABLED. A listening socket is a larger thing than a "
                         "pipe, and it takes its own switch.\n")
        return 2
    policy = require_policy()
    if policy is None:
        return 2
    host, warn = bind_address()
    plugins, closers = stand_up(a.target, page=a.page, seed=a.seed, headed=a.headed)
    registry = Registry(plugins)
    if a.attachable:
        from harness_plugin_session import SessionPlugin
        sp = SessionPlugin(registry, page=a.page, seed=a.seed, headed=a.headed)
        registry.register(sp, quiet=True)
        closers.append(sp.close)
    gw = Gateway(registry, policy)
    srv = Server(gw, policy.token, trace=a.trace)

    def announce(httpd):
        if warn:
            sys.stderr.write("WARNING: %s\n" % warn)
        sys.stderr.write("harness ready on http://%s:%d%s : %s, policy %s%s\n"
                         % (httpd.server_address[0], httpd.server_address[1], PATH,
                            ", ".join(d.id for d in registry.descriptors()),
                            ",".join(k for k, v in policy.allow.items() if v),
                            ", attachable" if a.attachable else ""))
        sys.stderr.flush()

    try:
        serve(srv, host=host, port=a.port, ready=announce)
    except KeyboardInterrupt:
        pass
    finally:
        tear_down(closers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
