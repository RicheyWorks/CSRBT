# -*- coding: utf-8 -*-
"""The csrbt-organism plugin: the fourteen-engine organism, behind the contract.

WHY A SECOND TARGET (ADR-112)
    tools/harness_contract.py was written as "a CSRBT page in a browser, or
    another target", and for eleven ADRs there was exactly one plugin. A
    contract with one implementation is a claim, not a measurement: nothing
    had shown that the gateway, the risk ladder, the replay cache and the
    stdio transport were target-neutral rather than page-shaped. This plugin
    is the measurement. It fronts WholeHog -- the integration organism that
    composes every engine in the ecosystem -- through the same four
    operations, the same policy and the same transport, with NO change to any
    of them. Where a change was needed, that would have been the finding.

WHAT THE TARGET IS
    A WholeHog HarnessConsole process: one Organism (CSRBT index, SmokeHouse
    store, Carver planner, Renderer views, Brine cache, PitBoss replica, DryAge
    vault, Twine batcher, SmokeSignal wire, Jerky archives, Rub observer,
    Sizzle seam) standing up in a scratch directory, driven over stdin/stdout
    by a line protocol that carries numbers only. Keys are integers; a value
    is the organism's own (attr, start, end) triple. Nothing free-text crosses
    the seam, which is what lets the risk of every action be DECLARED here
    rather than inferred from what a caller sends.

THE RISK MAPPING, AND WHY
    READ            observe: meters only -- sizes, sequences, counters, vitals.
                    Never a key, never a value. report/pulse likewise.
    NAVIGATE        tick and quiesce: they advance an instrument (Rub's sample
                    history) or wait, and change no record.
    SENSITIVE_READ  anything that returns a key or a value, or an aggregate
                    over named keys: get, contains, range, count-range, query,
                    cold-scan, and the sensitive half of observe (a record
                    sample). "Does key 5 exist" is data about the data.
    MUTATE          put, delete, batch, preserve. Every one changes what is on
                    disk: the store, the journal, the vault, an archive.
    DESTRUCTIVE     nothing. There is no generic "press this" on an organism;
                    every action here names exactly what it does, so the
                    rung the page plugin needs for "a selector that might be
                    Clear trial" has no member. It is left empty rather than
                    filled for symmetry.

    A write's ROUTE is an argument, not an action: put/delete take via =
    direct | wire, and batch always goes through Twine. The organism's whole
    claim is that every route lands in every index; a client that can name
    the route can test the claim.

WHAT IS HELD
    Chaos (Sizzle) is a constructor seam on the Organism -- a ChaosPlan is
    fixed at standup, not injected at runtime -- so there is no chaos action.
    Publishing one would need an upstream cut, and "a harness that presses
    buttons nobody can reach" is ADR-103's finding, not a thing to repeat.
    The console reports chaosCrashes in every snapshot so the day the seam is
    cut the meter is already wired.

LIVENESS
    The console is a child process. It can die. Every request has a bounded
    wait, and a dead or silent console is reported as `unavailable` -- never
    as a hang, and never as `failed`, which in this harness is a claim that
    the TARGET misbehaved (ADR-111). A transport error is not a finding about
    the organism.
"""
import io, json, os, re, subprocess, sys, tempfile, threading, time
try:
    import queue
except ImportError:  # pragma: no cover
    import Queue as queue

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harness_contract import (ActionSpec, ArgumentSpec, Plugin, PluginDescriptor,
                              HarnessError, Failed, InvalidArgument, NotFound,
                              Unavailable)

ROOT = os.path.normpath(os.path.join(HERE, ".."))
MAIN = "io.github.richeyworks.wholehog.HarnessConsole"
JVM_FLAGS = ["-Dlog4j2.loggerContextFactory="
             "org.apache.logging.log4j.simple.SimpleLoggerContextFactory",
             "-Dorg.apache.logging.log4j.simplelog.StatusLogger.level=OFF"]
REQUEST_TIMEOUT = 30.0      # seconds; quiesce is capped below this by the console
STARTUP_TIMEOUT = 60.0
SAMPLE_CAP = 20             # records in a sensitive snapshot
RANGE_CAP = 200             # records one range/query answer may carry
VIA = ["direct", "wire"]
BATCH_OP = re.compile(r"^(p \d+ \d+ \d+ \d+|d \d+)$")


def wholehog_dir():
    """Where WholeHog is. A sibling of this repo, the way the composite build
    finds it, unless CSRBT_WHOLEHOG says otherwise."""
    return os.environ.get("CSRBT_WHOLEHOG") or os.path.join(ROOT, "..", "WholeHog")


def classpath():
    """The classpath `./gradlew harnessClasspath` wrote, or None if the engine
    is not built. None is an answer, not an error: the suite that reads it
    prints NOT VERIFIED rather than guessing at jar locations."""
    # CSRBT_ORGANISM_CLASSPATH overrides the file: tools/mutate_organism.py
    # compiles a mutated console into a scratch dir and puts it FIRST, so the
    # real build is never written to while the tester is being tested.
    cp = os.environ.get("CSRBT_ORGANISM_CLASSPATH")
    if not cp:
        f = os.path.join(wholehog_dir(), "build", "harness", "classpath.txt")
        if not os.path.isfile(f):
            return None
        cp = io.open(f, encoding="utf-8").read().strip()
    # A classpath written on another machine points at paths that are not
    # here; the first entry is the organism's own classes and must exist.
    head = cp.split(os.pathsep)[0]
    if not os.path.isdir(head):
        return None
    return cp


class Console(object):
    """The child process and its line protocol. No policy, no contract."""

    def __init__(self, root=None, seed=42, java="java", cp=None):
        cp = cp or classpath()
        if not cp:
            raise Unavailable("WholeHog is not built: run ./gradlew harnessClasspath "
                              "in %s" % os.path.normpath(wholehog_dir()))
        self.root = root or tempfile.mkdtemp(prefix="csrbt-organism-")
        self.seed = int(seed)
        self._q = queue.Queue()
        self._lock = threading.Lock()
        self.proc = subprocess.Popen(
            [java] + JVM_FLAGS + ["-cp", cp, MAIN, "--root", self.root,
                                  "--seed", str(self.seed)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1)
        threading.Thread(target=self._pump, daemon=True).start()
        hello = self._recv(STARTUP_TIMEOUT)
        if not hello.get("ready"):
            raise Unavailable("console did not come up: %r" % hello)
        self.hello = hello

    def _pump(self):
        try:
            for line in self.proc.stdout:
                self._q.put(line)
        except Exception:
            pass
        self._q.put(None)

    def _recv(self, timeout):
        try:
            line = self._q.get(timeout=timeout)
        except queue.Empty:
            raise Unavailable("console gave no answer within %.0fs" % timeout)
        if line is None:
            err = ""
            try:
                err = (self.proc.stderr.read() or "")[-300:]
            except Exception:
                pass
            raise Unavailable("console exited (rc=%s) %s" % (self.proc.poll(), err.strip()))
        try:
            return json.loads(line)
        except ValueError:
            raise Unavailable("console spoke something other than JSON: %r" % line[:120])

    def alive(self):
        return self.proc.poll() is None

    def send(self, verb, *args):
        """One request, one reply. Refusals from the console become the
        contract's own error codes; everything else is a dict."""
        with self._lock:
            if not self.alive():
                raise Unavailable("console exited (rc=%s)" % self.proc.poll())
            line = " ".join([verb] + [str(a) for a in args])
            try:
                self.proc.stdin.write(line + "\n")
                self.proc.stdin.flush()
            except (OSError, ValueError) as e:
                raise Unavailable("console pipe closed: %s" % e)
            r = self._recv(REQUEST_TIMEOUT)
        if r.get("ok"):
            return r
        code, why = r.get("code"), r.get("why", "")
        if code == "invalid_argument":
            raise InvalidArgument(why)
        if code == "not_found":
            raise NotFound(why)
        raise Failed(why)

    def close(self):
        try:
            if self.alive():
                with self._lock:
                    self.proc.stdin.write("quit\n")
                    self.proc.stdin.flush()
                self.proc.wait(timeout=15)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


def _key(name, required=True):
    return ArgumentSpec(name, "integer", "A record key (integer).", required=required)


def _triple():
    return [ArgumentSpec("attr", "integer", "Attribute 0-999; feeds the secondary index and Renderer's grouping.", required=True),
            ArgumentSpec("start", "integer", "Span start 0-99999; feeds the interval index.", required=True),
            ArgumentSpec("end", "integer", "Span end 0-99999.", required=True)]


class OrganismPlugin(Plugin):
    """One organism, one child process, behind the four operations."""

    ID = "csrbt-organism"

    def __init__(self, console=None, seed=42, root=None):
        self.console = console
        self.seed, self.root = seed, root
        self._desc = PluginDescriptor(
            self.ID, "CSRBT organism",
            "The WholeHog integration organism -- every engine of the CSRBT "
            "ecosystem composed over one store -- standing up in a scratch "
            "directory. Writes name their route (direct or over the wire; "
            "batches through Twine) so a client can test that every route "
            "lands in every index. Snapshots carry meters only; records need "
            "SENSITIVE_READ.",
            "1.0", [
                ActionSpec("put", "Write one record by the route named.", "MUTATE",
                           [_key("key")] + _triple() +
                           [ArgumentSpec("via", "string",
                                         "direct: the indexed store's fan-out. "
                                         "wire: a fresh SmokeSignal client over loopback.",
                                         enum=VIA)]),
                ActionSpec("delete", "Delete one record by the route named.", "MUTATE",
                           [_key("key"),
                            ArgumentSpec("via", "string", "direct or wire.", enum=VIA)]),
                ActionSpec("batch",
                           "Commit one crash-atomic batch through Twine's journal. "
                           "Each op is 'p KEY ATTR START END' or 'd KEY'.",
                           "MUTATE",
                           [ArgumentSpec("ops", "array", "Batch ops in order.",
                                         required=True, items="string")]),
                ActionSpec("preserve",
                           "Preserve the current moment into the vault and cure it "
                           "into a verified cold archive carrying its scan run.",
                           "MUTATE", []),
                ActionSpec("get", "Read one record.", "SENSITIVE_READ", [_key("key")]),
                ActionSpec("contains", "Whether a key is live.", "SENSITIVE_READ",
                           [_key("key")]),
                ActionSpec("range", "Records with keys in lo..hi, in key order, capped.",
                           "SENSITIVE_READ",
                           [_key("lo"), _key("hi"),
                            ArgumentSpec("cap", "integer",
                                         "At most this many records (1-%d)." % RANGE_CAP)]),
                ActionSpec("count-range", "How many live keys lie in lo..hi.",
                           "SENSITIVE_READ", [_key("lo"), _key("hi")]),
                ActionSpec("query",
                           "A Carver cost-based query: keys in lo..hi whose attr is "
                           "in attr-lo..attr-hi. Returns the plan it chose and the keys.",
                           "SENSITIVE_READ",
                           [_key("lo"), _key("hi"),
                            ArgumentSpec("attr-lo", "integer", "Attribute lower bound.", required=True),
                            ArgumentSpec("attr-hi", "integer", "Attribute upper bound.", required=True),
                            ArgumentSpec("cap", "integer", "At most this many keys.")]),
                ActionSpec("cold-scan",
                           "Count the records in a cured archive by streaming its "
                           "scan run, without resurrecting a store.",
                           "SENSITIVE_READ",
                           [ArgumentSpec("generation", "integer",
                                         "Generation number preserve returned.", required=True)]),
                ActionSpec("report", "The physical: every engine's meters in one read-only call.",
                           "READ", []),
                ActionSpec("pulse", "Rub's op-relative delta between the last two ticks.",
                           "READ", []),
                ActionSpec("tick", "Take a Rub vitals sample into the observer's history.",
                           "NAVIGATE", []),
                ActionSpec("quiesce",
                           "Wait until every tail consumer (views, replica) has caught "
                           "up with the primary, or the timeout passes.",
                           "NAVIGATE",
                           [ArgumentSpec("ms", "integer", "Timeout in milliseconds, 0-30000.")]),
            ])

    def descriptor(self):
        return self._desc

    # -- lifecycle ------------------------------------------------------------
    def _c(self):
        if self.console is None:
            self.console = Console(root=self.root, seed=self.seed)
        return self.console

    def close(self):
        if self.console is not None:
            self.console.close()

    # -- observation ----------------------------------------------------------
    def observe(self, sensitive=False):
        try:
            s = self._c().send("observe")
        except HarnessError as e:
            # Unavailable is a factory over HarnessError, not a class: a dead
            # console, a missing build, a silent pipe all arrive here.
            return {"ready": False, "why": e.message}
        s["target"] = "organism"
        s["seed"] = self.seed
        s["sensitive"] = bool(sensitive)
        s.pop("ok", None)
        if sensitive:
            try:
                s["sample"] = self._c().send("sample", SAMPLE_CAP)
                s["sample"].pop("ok", None)
            except HarnessError as e:
                s["sample"] = {"ready": False, "why": e.message}
        else:
            s["redacted"] = ("records omitted; get, range and the sample need "
                             "SENSITIVE_READ")
        return s

    # -- execution ------------------------------------------------------------
    def execute(self, action, args):
        c = self._c()
        if action == "put":
            via = args.get("via") or "direct"
            r = c.send("put", args["key"], args["attr"], args["start"], args["end"], via)
            return True, "put %d via %s" % (args["key"], via), _out(r)
        if action == "delete":
            via = args.get("via") or "direct"
            r = c.send("delete", args["key"], via)
            return True, "delete %d via %s (existed=%s)" % (args["key"], via, r["existed"]), _out(r)
        if action == "batch":
            ops = args["ops"]
            if not ops:
                raise InvalidArgument("an empty batch is not a batch")
            for op in ops:
                if not BATCH_OP.match(op):
                    raise InvalidArgument("batch op must be 'p KEY ATTR START END' or "
                                          "'d KEY', not %r" % op)
            r = c.send("batch", " | ".join(ops))
            return True, "batch of %d committed" % r["ops"], _out(r)
        if action == "preserve":
            r = c.send("preserve")
            return True, "preserved generation %d" % r["generation"], _out(r)
        if action == "get":
            r = c.send("get", args["key"])
            return True, "get %d (found=%s)" % (args["key"], r["found"]), _out(r)
        if action == "contains":
            r = c.send("contains", args["key"])
            return True, "contains %d = %s" % (args["key"], r["found"]), _out(r)
        if action == "range":
            cap = _cap(args.get("cap"))
            r = c.send("range", args["lo"], args["hi"], cap)
            return True, "%d record(s) in %d..%d" % (r["count"], args["lo"], args["hi"]), _out(r)
        if action == "count-range":
            r = c.send("count", args["lo"], args["hi"])
            return True, "%d key(s) in %d..%d" % (r["count"], args["lo"], args["hi"]), _out(r)
        if action == "query":
            cap = _cap(args.get("cap"))
            r = c.send("query", args["lo"], args["hi"], args["attr-lo"], args["attr-hi"], cap)
            return True, "%d key(s): %s" % (r["count"], r["plan"]), _out(r)
        if action == "cold-scan":
            r = c.send("coldscan", args["generation"])
            return True, "%d record(s) in generation %d" % (r["records"], r["generation"]), _out(r)
        if action == "report":
            r = c.send("report")
            return True, "the physical", {"report": r["report"],
                                          "lines": r["report"].split("\n")}
        if action == "pulse":
            r = c.send("pulse")
            return r["pulse"] is not None, ("pulse" if r["pulse"] else r.get("why", "no pulse")), _out(r)
        if action == "tick":
            r = c.send("tick")
            return True, "ticked", _out(r)
        if action == "quiesce":
            ms = args.get("ms", 5000)
            if not 0 <= ms <= 30000:
                raise InvalidArgument("ms must be 0-30000")
            r = c.send("quiesce", ms)
            return bool(r["quiet"]), ("quiet" if r["quiet"] else "not quiet within %dms" % ms), _out(r)
        raise NotFound("unknown action %r" % action)


def _cap(v):
    if v is None:
        return RANGE_CAP
    if not 1 <= v <= RANGE_CAP:
        raise InvalidArgument("cap must be 1-%d" % RANGE_CAP)
    return v


def _out(r):
    r = dict(r)
    r.pop("ok", None)
    return r
