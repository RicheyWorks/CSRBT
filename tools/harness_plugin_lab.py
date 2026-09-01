# -*- coding: utf-8 -*-
"""The csrbt-lab plugin: the science engine, behind the contract (ADR-116).

WHAT THE TARGET IS
    csrbt-experimental's LabConsole: the classroom runner (an .eco protocol
    parsed, run against a live adaptive tree, its pre-registered hypotheses
    graded CONFIRMED / REFUTED / UNGRADEABLE, its theory models and crosses
    computed, its exports rendered), the strategy arena
    (StrategyBattleRunner: four strategies ranked on a seeded workload), the
    adaptive controller (GenomeDrivenTreeController over a three-regime
    workload, its morph log), and the field day. This is what the kit's pages
    describe and what students run; it had never been reachable by a robot.

THE RISK MAPPING
    READ       protocols (the shipped .eco files by name), lint (parse only)
    NAVIGATE   run-protocol, run, battle, adapt, field-day -- compute that
               changes no record and persists nothing; bounded by op caps
    MUTATE     export -- writes the full bundle (CSVs, HTML, xlsx, pptx)
               into a scratch directory the plugin owns
    SENSITIVE_READ / DESTRUCTIVE  none. A protocol is the caller's own text;
               the reports are derived from it and from seeded workloads.
               The snapshot's lastName is the caller's protocol name and is
               shown only under SENSITIVE_READ, because a name can be data.

WHAT THE HARNESS REFUSES
    A protocol's `dwc:` line names a file on disk for the runner to read.
    Through the harness that would be the harness reading the operator's
    disk, which no target in this kit does (the page plugin hands file inputs
    bytes from its own fixture table for the same reason). The console
    refuses it before parsing, and the plugin refuses it before the console.

    A protocol is free text and crosses the seam as one base64 token, capped
    at 64 KiB. Its schema carries an example a schema-driven client can use
    verbatim, so the lab is operable from the manifest alone (ADR-114).
"""
import base64, glob, io, json, os, re, subprocess, sys, tempfile, threading
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
DOCS = os.path.join(ROOT, "docs")
MAIN = "io.github.richeyworks.csrbt.experimental.LabConsole"
JVM_FLAGS = ["-Dlog4j2.loggerContextFactory="
             "org.apache.logging.log4j.simple.SimpleLoggerContextFactory",
             "-Dorg.apache.logging.log4j.simplelog.level=WARN",
             "-Dorg.apache.logging.log4j.simplelog.StatusLogger.level=OFF"]
REQUEST_TIMEOUT = 120.0
STARTUP_TIMEOUT = 60.0
SPEC_CAP = 64 * 1024
OPS_MIN, OPS_MAX = 100, 50_000
WORKLOADS = ["RANDOM_UNIFORM", "SEQUENTIAL", "LOCALITY_BURST", "MIXED",
             "INSERT_HEAVY", "SEARCH_HEAVY", "DELETE_HEAVY"]
DWC = re.compile(r"^\s*dwc\s*:", re.I | re.M)
EXAMPLE_SPEC = ("name: harness example\nkeys: 50\nseed: 7\nwindow: 100\n"
                "phase: graze uniform 400\nphase: bloom hot 400 5 90\n"
                "model: logistic 0.15 120 5 40\n"
                "expect: evenness(graze) > 0.9\nexpect: hill1(bloom) < 20\n")


def shipped_protocols():
    """The .eco files the kit ships, by name."""
    out = []
    for p in sorted(glob.glob(os.path.join(DOCS, "*.eco"))):
        out.append(os.path.basename(p)[:-4])
    return out


def classpath():
    cp = os.environ.get("CSRBT_LAB_CLASSPATH")
    if not cp:
        f = os.path.join(ROOT, "csrbt-experimental", "build", "harness", "classpath.txt")
        if not os.path.isfile(f):
            return None
        cp = io.open(f, encoding="utf-8").read().strip()
    head = cp.split(os.pathsep)[0]
    if not os.path.isdir(head):
        return None
    return cp


class Console(object):
    """The child process and its line protocol. No policy, no contract."""

    def __init__(self, java="java", cp=None):
        cp = cp or classpath()
        if not cp:
            raise Unavailable("csrbt-experimental is not built: run ./gradlew "
                              ":csrbt-experimental:harnessClasspath in %s" % ROOT)
        self._q = queue.Queue()
        self._lock = threading.Lock()
        self.proc = subprocess.Popen(
            [java] + JVM_FLAGS + ["-cp", cp, MAIN],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1)
        threading.Thread(target=self._pump, daemon=True).start()
        hello = self._recv(STARTUP_TIMEOUT)
        if not hello.get("ready"):
            raise Unavailable("lab console did not come up: %r" % hello)
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
            raise Unavailable("lab console gave no answer within %.0fs" % timeout)
        if line is None:
            err = ""
            try:
                err = (self.proc.stderr.read() or "")[-300:]
            except Exception:
                pass
            raise Unavailable("lab console exited (rc=%s) %s" % (self.proc.poll(), err.strip()))
        try:
            return json.loads(line)
        except ValueError:
            raise Unavailable("lab console spoke something other than JSON: %r" % line[:120])

    def alive(self):
        return self.proc.poll() is None

    def send(self, verb, *args):
        with self._lock:
            if not self.alive():
                raise Unavailable("lab console exited (rc=%s)" % self.proc.poll())
            line = " ".join([verb] + [str(a) for a in args])
            try:
                self.proc.stdin.write(line + "\n")
                self.proc.stdin.flush()
            except (OSError, ValueError) as e:
                raise Unavailable("lab console pipe closed: %s" % e)
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


def _spec_arg():
    return ArgumentSpec("protocol", "string",
                        "An .eco protocol: name/keys/seed/window, phase:, model:, cross:, "
                        "data:, note:, tree:, expect: lines. dwc: lines are refused. "
                        "At most 64 KiB.", required=True, examples=[EXAMPLE_SPEC])


def _seed():
    return ArgumentSpec("seed", "integer", "Workload seed; same seed, same workload.",
                        examples=[7, 42, 2026])


class LabPlugin(Plugin):
    ID = "csrbt-lab"

    def __init__(self, console=None, scratch=None):
        self.console = console
        self.scratch = scratch
        protocols = shipped_protocols()
        self._desc = PluginDescriptor(
            self.ID, "CSRBT lab",
            "The science engine of the CSRBT kit: the classroom runner that grades an .eco "
            "protocol's pre-registered hypotheses against a live adaptive tree, the strategy "
            "arena, the adaptive controller's morph log, and the field day. Runs are seeded "
            "and deterministic; nothing here reads the operator's disk.",
            "1.0", [
                ActionSpec("protocols", "The .eco protocols the kit ships, by name.", "READ", []),
                ActionSpec("lint",
                           "Parse a protocol without running it: what it declares, and "
                           "every malformed line named. A hypothesis that cannot be tested "
                           "is a protocol bug, not a result.",
                           "READ", [_spec_arg()]),
                ActionSpec("run-protocol",
                           "Run one of the shipped protocols and grade its hypotheses.",
                           "NAVIGATE",
                           [ArgumentSpec("name", "string", "A shipped protocol name.",
                                         required=True, enum=protocols or ["sample-experiment"])]),
                ActionSpec("run",
                           "Run a protocol: phases against a live tree, models, crosses, "
                           "entered data; each expect: line graded CONFIRMED, REFUTED or "
                           "UNGRADEABLE with its observed value. Returns the narrated report, "
                           "the lab-page session, and the export names.",
                           "NAVIGATE", [_spec_arg()]),
                ActionSpec("export",
                           "Run a protocol and write its full bundle -- CSVs, printable "
                           "HTML, workbook.xlsx, report.pptx -- into a scratch directory "
                           "the plugin owns. Returns the file names and sizes.",
                           "MUTATE", [_spec_arg()]),
                ActionSpec("battle",
                           "The strategy arena: Red-Black, AVL, Splay and Hybrid on one "
                           "seeded workload, ranked by time and realized depth.",
                           "NAVIGATE",
                           [ArgumentSpec("workload", "string", "Workload shape.", required=True,
                                         enum=WORKLOADS),
                            ArgumentSpec("ops", "integer", "Operations (%d-%d)." % (OPS_MIN, OPS_MAX),
                                         minimum=OPS_MIN, maximum=OPS_MAX, examples=[1000, 5000]),
                            _seed()]),
                ActionSpec("adapt",
                           "The adaptive controller over a three-regime workload (mixed "
                           "build-up, hot-key reads, heavy writes) under the eager morph "
                           "policy: every morph with its op and pressure, and where it ended.",
                           "NAVIGATE",
                           [ArgumentSpec("keys", "integer", "Key space (1-100000).",
                                         minimum=1, maximum=100_000, examples=[100, 500, 997]),
                            ArgumentSpec("ops", "integer", "Operations (1-%d)." % OPS_MAX,
                                         minimum=1, maximum=OPS_MAX, examples=[1000, 3000]),
                            _seed()]),
                ActionSpec("field-day",
                           "The full-ecosystem survey: meadow, census, archipelago, fossils, "
                           "narrated, with its session JSON.",
                           "NAVIGATE", []),
            ])

    def descriptor(self):
        return self._desc

    def _c(self):
        if self.console is None:
            self.console = Console()
        return self.console

    def close(self):
        if self.console is not None:
            self.console.close()

    # -- observation ----------------------------------------------------------
    def observe(self, sensitive=False):
        try:
            s = self._c().send("observe")
        except HarnessError as e:
            return {"ready": False, "why": e.message}
        s.pop("ok", None)
        s["target"] = "lab"
        s["sensitive"] = bool(sensitive)
        s["protocols"] = shipped_protocols()
        if not sensitive:
            s.pop("lastName", None)
            s["redacted"] = "the last protocol's name is shown only under SENSITIVE_READ"
        return s

    # -- execution ------------------------------------------------------------
    def execute(self, action, args):
        if action == "protocols":
            names = shipped_protocols()
            return True, "%d protocol(s)" % len(names), {"protocols": names}
        if action == "run-protocol":
            name = args["name"]
            if name not in shipped_protocols():
                raise NotFound("no shipped protocol %r" % name)
            text = io.open(os.path.join(DOCS, name + ".eco"), encoding="utf-8").read()
            return self._run(text, name)
        if action in ("lint", "run", "export"):
            text = args["protocol"]
            if len(text.encode("utf-8")) > SPEC_CAP:
                raise InvalidArgument("protocol over 64 KiB")
            if DWC.search(text):
                raise InvalidArgument("dwc: lines are refused through the harness: a protocol "
                                      "that names a file would read the operator's disk")
            if action == "lint":
                r = self._c().send("lint", _b64(text))
                return True, "%s: %d problem(s)" % (r["name"], len(r["problems"])), _out(r)
            if action == "run":
                return self._run(text, None)
            if self.scratch is None:
                self.scratch = tempfile.mkdtemp(prefix="csrbt-lab-")
            d = os.path.join(self.scratch, "export-%d" % (len(os.listdir(self.scratch)) + 1))
            r = self._c().send("export", _b64(text), d)
            return True, "%d file(s) written" % len(r["files"]), _out(r)
        if action == "battle":
            r = self._c().send("battle", args["workload"], args.get("ops", 1000), args.get("seed", 42))
            return True, "%s: %s first" % (r["workload"], r["results"][0]["strategy"]), _out(r)
        if action == "adapt":
            r = self._c().send("adapt", args.get("keys", 500), args.get("ops", 3000), args.get("seed", 42))
            return True, "%d morph(s), ended on %s" % (r["morphs"], r["strategy"]), _out(r)
        if action == "field-day":
            r = self._c().send("fieldday")
            out = _out(r)
            out["session"] = _parse(out.get("session"))
            return True, "the field day", out
        raise NotFound("unknown action %r" % action)

    def _run(self, text, name):
        r = self._c().send("run", _b64(text))
        out = _out(r)
        session = _parse(out.get("session"))
        out["session"] = session
        hyps = (session or {}).get("hypotheses") or []
        out["hypotheses"] = hyps
        verdicts = {}
        for h in hyps:
            verdicts[h.get("verdict")] = verdicts.get(h.get("verdict"), 0) + 1
        out["verdicts"] = verdicts
        if name:
            out["protocol"] = name
        return True, "%s: %s" % (r["name"], ", ".join("%d %s" % (n, v) for v, n in sorted(verdicts.items()))
                                 or "no hypotheses"), out


def _b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _parse(s):
    if not isinstance(s, str):
        return s
    try:
        return json.loads(s)
    except ValueError:
        return {"unparsed": s[:200]}


def _out(r):
    r = dict(r)
    r.pop("ok", None)
    return r
