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
    MUTATE          put, delete, batch, preserve, and (ADR-113) compact,
                    recover, retain-newest, rebootstrap. Every one changes what
                    is on disk: the store, the journal, the vault, an archive,
                    the replica's directory.
    DESTRUCTIVE     nothing. There is no generic "press this" on an organism;
                    every action here names exactly what it does, so the
                    rung the page plugin needs for "a selector that might be
                    Clear trial" has no member. It is left empty rather than
                    filled for symmetry.

    A write's ROUTE is an argument, not an action: put/delete take via =
    direct | wire, and batch always goes through Twine. The organism's whole
    claim is that every route lands in every index; a client that can name
    the route can test the claim.

EVERY ENGINE, BY NAME (ADR-113)
    ADR-112 reached the organism through the store. ADR-113 reaches each
    organ through its own surface, so the manifest names what the ecosystem
    can do rather than what a key-value store can do:

      CSRBT        order (rank, nth, median, percentile, first, last, size)
                   and depth -- the measuring read
      SmokeSignal  every read takes via = direct | wire, like the writes
      Carver       query (secondary), overlap and stab (the SPAN interval index)
      Renderer     groups -- the materialized fold, top-k attrs with totals
      Brine        cache-get -- and whether the cache or the store answered
      PitBoss      fleet, replica-get, rebootstrap
      DryAge       generations, as-of, retain-newest
      Jerky        verify-archive, archive-names
      SmokeHouse   compact, segments
      Twine        recover
      Rub          history
      Sizzle       restart -- see below

CHAOS, HONESTLY
    Sizzle is a constructor seam on the Organism: a ChaosPlan is fixed at
    standup, not injected at runtime. ADR-112 held chaos on that ground. The
    honest way through is not a runtime knob upstream but the road the
    organism's own tests take: close, reopen at the same root under a plan.
    `restart` does exactly that, and it is also the crash-recovery road --
    Twine's journal replays into every index on construction -- so a client
    can arm a crash, watch a batch fail, restart clean, and read the batch
    back whole. It is NAVIGATE: it changes no record; a plan only makes
    later writes fail, and failing is something MUTATE already permits.

LIVENESS
    The console is a child process. It can die. Every request has a bounded
    wait, and a dead or silent console is reported as `unavailable` -- never
    as a hang, and never as `failed`, which in this harness is a claim that
    the TARGET misbehaved (ADR-111). A transport error is not a finding about
    the organism.
"""
import collections, io, json, os, re, subprocess, sys, tempfile, threading, time
try:
    import queue
except ImportError:  # pragma: no cover
    import Queue as queue

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harness_contract import (ActionSpec, ArgumentSpec, Plugin, PluginDescriptor,
                              HarnessError, Conflict, Failed, InvalidArgument, NotFound,
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
ORDER_KINDS = ["rank", "nth", "median", "percentile", "first", "last", "size"]
CHAOS = re.compile(r"^(none|once:\d+|every:\d+|prob:-?\d+:(0|1|0?\.\d+))$")
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
        # stderr is drained too, into a bounded tail. The first robot found a
        # console that died LOUDLY -- a StackOverflowError prints a thousand
        # frames -- filling the unread stderr pipe, so the JVM blocked on its
        # own trace, never exited, and the reader waited out its whole timeout
        # instead of learning of the death at once. A detector with no alarm.
        self._err = collections.deque(maxlen=200)
        threading.Thread(target=self._drain, daemon=True).start()
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

    def _drain(self):
        try:
            for line in self.proc.stderr:
                self._err.append(line.rstrip()[:200])
        except Exception:
            pass

    def _recv(self, timeout):
        try:
            line = self._q.get(timeout=timeout)
        except queue.Empty:
            raise Unavailable("console gave no answer within %.0fs" % timeout)
        if line is None:
            err = " | ".join(list(self._err)[-3:])[-300:]
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
        if code == "conflict":
            raise Conflict(why)
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
    # Keys are longs and unbounded in the organism; the examples give a
    # schema-driven client a pool to draw from without guessing the domain.
    return ArgumentSpec(name, "integer", "A record key (integer).", required=required,
                        examples=[0, 1, 5, 7, 12, 60, 121, 777])


def _via():
    return ArgumentSpec("via", "string",
                        "direct: the indexed store's fan-out. wire: a fresh SmokeSignal "
                        "client over loopback. Default direct.", enum=VIA)


def _gen():
    return ArgumentSpec("generation", "integer", "Generation number preserve returned.",
                        required=True, minimum=0, examples=[0, 1])


def _cap_arg():
    return ArgumentSpec("cap", "integer", "At most this many records (1-%d)." % RANGE_CAP,
                        minimum=1, maximum=RANGE_CAP)


def _triple():
    return [ArgumentSpec("attr", "integer", "Attribute 0-999; feeds the secondary index and Renderer's grouping.",
                         required=True, minimum=0, maximum=999),
            ArgumentSpec("start", "integer", "Span start 0-99999; feeds the interval index.",
                         required=True, minimum=0, maximum=99_999),
            ArgumentSpec("end", "integer", "Span end 0-99999, not below start.", required=True,
                         minimum=0, maximum=99_999)]


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
                # ---- writes: the four MUTATE routes of ADR-112 ---------------------
                ActionSpec("put", "Write one record by the route named.", "MUTATE",
                           [_key("key")] + _triple() + [_via()]),
                ActionSpec("delete", "Delete one record by the route named.", "MUTATE",
                           [_key("key"), _via()]),
                ActionSpec("batch",
                           "Commit one crash-atomic batch through Twine's journal. "
                           "Each op is 'p KEY ATTR START END' or 'd KEY'.",
                           "MUTATE",
                           [ArgumentSpec("ops", "array", "Batch ops in order.",
                                         required=True, items="string",
                                         pattern=BATCH_OP.pattern,
                                         examples=["p 1 2 3 4", "p 60 5 100 200", "d 1"])]),
                ActionSpec("preserve",
                           "Preserve the current moment into the vault and cure it "
                           "into a verified cold archive carrying its scan run.",
                           "MUTATE", []),
                # ---- reads, by route -----------------------------------------------
                ActionSpec("get", "Read one record.", "SENSITIVE_READ", [_key("key"), _via()]),
                ActionSpec("contains", "Whether a key is live.", "SENSITIVE_READ",
                           [_key("key"), _via()]),
                ActionSpec("range", "Records with keys in lo..hi, in key order, capped.",
                           "SENSITIVE_READ",
                           [_key("lo"), _key("hi"), _cap_arg(), _via()]),
                ActionSpec("count-range", "How many live keys lie in lo..hi.",
                           "SENSITIVE_READ", [_key("lo"), _key("hi"), _via()]),
                # ---- CSRBT: the index's own reads ----------------------------------
                ActionSpec("order",
                           "An order statistic from the adaptive index: rank KEY, "
                           "nth RANK (1-based), median, percentile PCT, first, last, "
                           "size. Null on an empty store. Same names over the wire.",
                           "SENSITIVE_READ",
                           [ArgumentSpec("kind", "string", "Which statistic.",
                                         required=True, enum=ORDER_KINDS),
                            ArgumentSpec("arg", "integer",
                                         "The key for rank, the rank for nth (1-based), the "
                                         "percentile (0-100) for percentile; otherwise omitted.",
                                         examples=[1, 2, 50, 100]),
                            _via()]),
                ActionSpec("depth",
                           "CSRBT's measuring read: nodes the index touched to find a "
                           "key (>= 1 when live; ~depth, negative, when absent).",
                           "SENSITIVE_READ", [_key("key")]),
                # ---- Carver --------------------------------------------------------
                ActionSpec("query",
                           "A Carver cost-based query: keys in lo..hi whose attr is "
                           "in attr-lo..attr-hi. Returns the plan it chose and the keys.",
                           "SENSITIVE_READ",
                           [_key("lo"), _key("hi"),
                            ArgumentSpec("attr-lo", "integer", "Attribute lower bound.", required=True,
                                         minimum=0, maximum=999),
                            ArgumentSpec("attr-hi", "integer", "Attribute upper bound.", required=True,
                                         minimum=0, maximum=999),
                            _cap_arg()]),
                ActionSpec("overlap",
                           "Carver over the SPAN interval index: keys whose span "
                           "overlaps lo..hi. Plan and keys.",
                           "SENSITIVE_READ",
                           [ArgumentSpec("lo", "integer", "Span lower bound.", required=True,
                                         minimum=0, maximum=99_999),
                            ArgumentSpec("hi", "integer", "Span upper bound.", required=True,
                                         minimum=0, maximum=99_999),
                            _cap_arg()]),
                ActionSpec("stab",
                           "Carver over the SPAN interval index: keys whose span "
                           "contains a point.",
                           "SENSITIVE_READ",
                           [ArgumentSpec("point", "integer", "The point.", required=True,
                                         minimum=0, maximum=99_999),
                            _cap_arg()]),
                # ---- Renderer, Brine, PitBoss --------------------------------------
                ActionSpec("groups",
                           "Renderer's materialized fold over attr: how many groups, "
                           "the heaviest k with their totals, and whether the fold has "
                           "caught the tail.",
                           "SENSITIVE_READ",
                           [ArgumentSpec("top", "integer", "How many groups to list (1-1000).",
                                         minimum=1, maximum=1000)]),
                ActionSpec("cache-get",
                           "Brine's answer for a key, and whether the cache or the "
                           "store supplied it; names the champion genome.",
                           "SENSITIVE_READ", [_key("key")]),
                ActionSpec("fleet",
                           "PitBoss's tick: the primary sequence and, per replica, lag, "
                           "gapped, and whether THIS tick rebootstrapped it for a gap "
                           "(a rebootstrap you asked for is not reported here).",
                           "READ", []),
                ActionSpec("replica-get", "Read one record from the replica's own store.",
                           "SENSITIVE_READ", [_key("key")]),
                ActionSpec("rebootstrap",
                           "Cold-start the replica mid-life: its directory is rebuilt "
                           "from the primary. Snapshots then say replicaObserverDetached "
                           "until the next restart, because Rub stays on the old store.",
                           "MUTATE", []),
                # ---- DryAge, Jerky -------------------------------------------------
                ActionSpec("generations", "The vault's generation numbers.", "READ", []),
                ActionSpec("as-of",
                           "One key as it was in a preserved generation. A scratch "
                           "copy is recovered and released.",
                           "SENSITIVE_READ",
                           [_gen(), _key("key")]),
                ActionSpec("retain-newest",
                           "Aging policy: release every generation but the newest n. "
                           "Returns what was released.",
                           "MUTATE",
                           [ArgumentSpec("count", "integer", "Generations to keep.", required=True,
                                         minimum=0, maximum=1_000_000)]),
                ActionSpec("verify-archive",
                           "Jerky's whole-body CRC over a cured archive: true or false.",
                           "READ", [_gen()]),
                ActionSpec("archive-names",
                           "The entry names inside a cured archive (manifest, segments, "
                           "scan run). Names only, never bytes.",
                           "READ", [_gen()]),
                ActionSpec("cold-scan",
                           "Count the records in a cured archive by streaming its "
                           "scan run, without resurrecting a store.",
                           "SENSITIVE_READ",
                           [_gen()]),
                # ---- SmokeHouse, Twine, Rub ----------------------------------------
                ActionSpec("compact",
                           "Compact the store's segments: garbage before and after, "
                           "bytes reclaimed.",
                           "MUTATE", []),
                ActionSpec("segments", "Per-segment bytes, garbage and which is active.",
                           "READ", []),
                ActionSpec("recover",
                           "Replay Twine's journal now: true if a batch was waiting.",
                           "MUTATE", []),
                ActionSpec("history", "Rub's sample history, oldest first.", "READ", []),
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
                           [ArgumentSpec("ms", "integer", "Timeout in milliseconds, 0-30000.",
                                         minimum=0, maximum=30_000)]),
                # ---- Sizzle --------------------------------------------------------
                ActionSpec("restart",
                           "Close the organism and reopen it at the same root -- the "
                           "crash-recovery road (Twine's journal replays into every "
                           "index) -- optionally under a Sizzle plan: none, once:N, "
                           "every:N, prob:SEED:P, plus a per-write latency, plus a "
                           "replica lag: milliseconds every replicated event is held "
                           "back, so the fleet's replica is genuinely behind the primary "
                           "until a quiesce (late, never wrong). Changes no record; a "
                           "plan only makes later writes fail.",
                           "NAVIGATE",
                           [ArgumentSpec("chaos", "string",
                                         "none | once:N | every:N | prob:SEED:P",
                                         pattern=CHAOS.pattern,
                                         examples=["none", "once:2", "every:3", "prob:7:0.1"]),
                            ArgumentSpec("latency-ms", "integer", "0-5000 per write op.",
                                         minimum=0, maximum=5000),
                            ArgumentSpec("replica-lag-ms", "integer",
                                         "0-200 per replicated event; the fleet's lag reads "
                                         "nonzero until the replica catches up.",
                                         minimum=0, maximum=200),
                            ArgumentSpec("how", "string",
                                         "clean: close and reopen (the checkpoint is written, "
                                         "the reopen is warm); cold: the organism DIES without "
                                         "its checkpoint, so the reopen is SmokeHouse's own "
                                         "recovery -- the log scanned, SuperBeefSort sorting "
                                         "it, the index born from what it measured.",
                                         enum=["clean", "cold"])]),
                # ---- the process ---------------------------------------------------
                ActionSpec("jvm",
                           "The organism's own process: live threads by name, open file "
                           "descriptors (-1 where the platform has no count), heap in use. "
                           "Restarts must leave these where they found them; descriptors "
                           "rise one per segment until a compact.",
                           "READ", []),
                # ---- SuperBeefSort ------------------------------------------------
                ActionSpec("recovery",
                           "Engine 2's report of the last open: entries recovered, whether "
                           "the checkpoint was used, whether SuperBeefSort sorted (and by "
                           "which strategy, at what cost, over how disordered a feed), and "
                           "the tree the index was born as. A clean restart sorts nothing; "
                           "a cold one does.",
                           "READ", []),
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
        # ADR-114: values that are a fact of the moment rather than of the schema
        # -- which generations exist right now -- are published here so a client
        # holding only the manifest and a snapshot can form a valid call. READ
        # level: generation numbers are not records.
        s["argumentPools"] = {"generation": s.pop("generationIds", [])}
        # ADR-123: a bound pair (lo..hi, a span's start..end) is a domain the
        # schema cannot express -- lo <= hi -- so a client forming each side
        # from its own bounds is refused about half the time, and a short walk
        # can miss a tool by seed-luck (the first 2x2 suite walk at 35 tools
        # never drove overlap). The pools say which pairs are always valid:
        # every low value is below every high one. A robot that reads scoped
        # pools first forms a valid pair every time; refusals remain where the
        # target's own rules make them (a missing key, a released generation).
        s["argumentPools"].update({"range.lo": [0, 1, 50], "range.hi": [200, 999, 100_000],
                                   "count-range.lo": [0, 1, 50], "count-range.hi": [200, 999, 100_000],
                                   "overlap.lo": [0, 1, 40], "overlap.hi": [60, 500, 99_999]})
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
        via = args.get("via") or "direct"
        if action == "get":
            r = c.send("get", args["key"], via)
            return True, "get %d via %s (found=%s)" % (args["key"], via, r["found"]), _out(r)
        if action == "contains":
            r = c.send("contains", args["key"], via)
            return True, "contains %d = %s" % (args["key"], r["found"]), _out(r)
        if action == "range":
            r = c.send("range", args["lo"], args["hi"], _cap(args.get("cap")), via)
            return True, "%d record(s) in %d..%d via %s" % (r["count"], args["lo"], args["hi"], via), _out(r)
        if action == "count-range":
            r = c.send("count", args["lo"], args["hi"], via)
            return True, "%d key(s) in %d..%d via %s" % (r["count"], args["lo"], args["hi"], via), _out(r)
        if action == "order":
            kind = args["kind"]
            needs = kind in ("rank", "nth", "percentile")
            if needs and args.get("arg") is None:
                raise InvalidArgument("order %s needs arg" % kind)
            if not needs and args.get("arg") is not None:
                raise InvalidArgument("order %s takes no arg" % kind)
            r = c.send("order", kind, *([args["arg"]] if needs else []), via)
            return True, "%s = %s via %s" % (kind, r["answer"], via), _out(r)
        if action == "depth":
            r = c.send("depth", args["key"])
            return True, "depth of %d = %d" % (args["key"], r["depth"]), _out(r)
        if action == "query":
            cap = _cap(args.get("cap"))
            r = c.send("query", args["lo"], args["hi"], args["attr-lo"], args["attr-hi"], cap)
            return True, "%d key(s): %s" % (r["count"], r["plan"]), _out(r)
        if action == "overlap":
            r = c.send("overlap", args["lo"], args["hi"], _cap(args.get("cap")))
            return True, "%d key(s): %s" % (r["count"], r["plan"]), _out(r)
        if action == "stab":
            r = c.send("stab", args["point"], _cap(args.get("cap")))
            return True, "%d key(s): %s" % (r["count"], r["plan"]), _out(r)
        if action == "groups":
            top = args.get("top", 5)
            if not 1 <= top <= 1000:
                raise InvalidArgument("top must be 1-1000")
            r = c.send("groups", top)
            return True, "%d group(s)" % r["groups"], _out(r)
        if action == "cache-get":
            r = c.send("cacheget", args["key"])
            return True, "cache-get %d (%s)" % (args["key"], "hit" if r["hit"] else "store"), _out(r)
        if action == "fleet":
            r = c.send("fleet")
            return True, "%d replica(s)" % len(r["replicas"]), _out(r)
        if action == "replica-get":
            r = c.send("replicaget", args["key"])
            return True, "replica-get %d (found=%s)" % (args["key"], r["found"]), _out(r)
        if action == "rebootstrap":
            r = c.send("rebootstrap")
            return True, "replica rebootstrapped", _out(r)
        if action == "generations":
            r = c.send("generations")
            return True, "%d generation(s)" % len(r["generations"]), _out(r)
        if action == "as-of":
            r = c.send("asof", args["generation"], args["key"])
            return True, "as of %d: %d found=%s" % (args["generation"], args["key"], r["found"]), _out(r)
        if action == "retain-newest":
            if args["count"] < 0:
                raise InvalidArgument("count must be >= 0")
            r = c.send("retain", args["count"])
            return True, "released %s" % r["released"], _out(r)
        if action == "verify-archive":
            r = c.send("verify", args["generation"])
            return bool(r["verified"]), "verified=%s" % r["verified"], _out(r)
        if action == "archive-names":
            r = c.send("names", args["generation"])
            return True, "%d entries" % len(r["names"]), _out(r)
        if action == "cold-scan":
            r = c.send("coldscan", args["generation"])
            return True, "%d record(s) in generation %d" % (r["records"], r["generation"]), _out(r)
        if action == "compact":
            r = c.send("compact")
            return True, "reclaimed %d bytes" % r["reclaimed"], _out(r)
        if action == "segments":
            r = c.send("segments")
            return True, "%d segment(s)" % len(r["segments"]), _out(r)
        if action == "recover":
            r = c.send("recover")
            return True, "replayed=%s" % r["replayed"], _out(r)
        if action == "history":
            r = c.send("history")
            return True, "%d sample(s)" % len(r["history"]), _out(r)
        if action == "restart":
            plan = args.get("chaos") or "none"
            if not CHAOS.match(plan):
                raise InvalidArgument("chaos must be none | once:N | every:N | prob:SEED:P")
            lat = args.get("latency-ms", 0)
            if not 0 <= lat <= 5000:
                raise InvalidArgument("latency-ms must be 0-5000")
            lag = args.get("replica-lag-ms", 0)
            if not 0 <= lag <= 200:
                raise InvalidArgument("replica-lag-ms must be 0-200")
            how = args.get("how", "clean")
            if how not in ("clean", "cold"):
                raise InvalidArgument("how must be clean or cold")
            r = c.send("restart", plan, lat, lag, how)
            return True, "restarted %s under %s%s" % (how, r["chaos"], (", replica held back %d ms/event" % lag) if lag else ""), _out(r)
        if action == "jvm":
            r = c.send("jvm")
            return True, "%d thread(s), %d fd(s), %d MB" % (r["threads"], r["fds"], r["heapUsedMb"]), _out(r)
        if action == "recovery":
            r = c.send("recovery")
            rr = r["recovery"]
            msg = (("engine 2 sorted %d entries by %s" % (rr["entries"], rr["sortStrategy"])) if rr["sorted"]
                   else ("warm: %d entries from the checkpoint, nothing sorted" % rr["entries"]))
            return True, msg, _out(r)
        if action == "report":
            r = c.send("report")
            return True, "the physical", {"report": r["report"],
                                          "lines": r["report"].split("\n")}
        if action == "pulse":
            r = c.send("pulse")
            return True, ("pulse" if r["pulse"] else r.get("why", "no pulse yet")), _out(r)
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
