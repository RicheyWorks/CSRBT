# -*- coding: utf-8 -*-
"""Mutation testing for the organism plugin and its console (ADR-112).

WHY

tools/verify/verify_organism.py passed 231 of 231 on the afternoon it was
written, which in this kit is a reason for suspicion. The same afternoon the
tester was tested the only way a tester can be: break the plugin, break the
console, and require the suite to notice. The first sweep applied twelve
mutants and killed eight. Three of the four survivors were real holes -- the
documented default write route, the plugin's own cap, and the reader's death
sentinel were each asserted by nobody -- and are now killed by checks written
for them. The fourth is equivalent under the contract and recorded below with
its measurement rather than quietly dropped.

Each mutant names the check that must kill it, by a substring of that check's
message. A mutant killed by some OTHER check has proved nothing about the
clause it targets, and is reported as such.

SAFETY

Nothing real is written to. Plugin mutants run against a copy of tools/ in a
temp dir. Console mutants compile a copy of HarnessConsole.java with javac
into a scratch directory that is put FIRST on the classpath through
CSRBT_ORGANISM_CLASSPATH, so the built organism under WholeHog/build is never
touched. Needs the engine built (`./gradlew harnessClasspath` in WholeHog) and
a javac on the path; without either it says so and exits 2, not 0.

    python3 tools/mutate_organism.py           # run every mutant
    python3 tools/mutate_organism.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)
import harness_plugin_organism as O

CONSOLE_REL = os.path.join("src", "main", "java", "io", "github", "richeyworks",
                           "wholehog", "HarnessConsole.java")

# (target, name, find, replace, substring of the check that must fail)
PLUGIN, CONSOLE = "plugin", "console"
MUTANTS = [
    (PLUGIN, "a plain snapshot leaks the record sample",
     "        if sensitive:\n            try:", "        if True:\n            try:",
     "carries no record field"),
    (PLUGIN, "a put that names no route goes over the wire",
     'via = args.get("via") or "direct"\n            r = c.send("put"',
     'via = args.get("via") or "wire"\n            r = c.send("put"',
     "names no route goes direct"),
    (PLUGIN, "the plugin stops bounding the range cap",
     "    if not 1 <= v <= RANGE_CAP:\n        raise InvalidArgument",
     "    if False:\n        raise InvalidArgument",
     "cap past the published"),
    (PLUGIN, "a dead console is reported as the target failing",
     'raise Unavailable("console exited (rc=%s)" % self.proc.poll())',
     'raise Failed("console exited (rc=%s)" % self.proc.poll())',
     "killed console is reported unavailable"),
    (PLUGIN, "the pump dies without telling the reader",
     "        self._q.put(None)\n\n    def _recv", "        pass\n\n    def _recv",
     "pump's sentinel"),
    (CONSOLE, "count-range is off by one",
     ': o.primary().countRange(lo, hi);', ': o.primary().countRange(lo, hi + 1);',
     "count-range agrees with the mirror"),
    (CONSOLE, "delete always claims the key existed",
     "existed = o.store().delete(k);", "existed = true; o.store().delete(k);",
     "reports existed="),
    (CONSOLE, "the sensitive sample ignores its cap",
     # Anchored on the sample's own range call: the same two lines occur in
     # range() too, and an ambiguous anchor is a BAD MUTANT, which is what this
     # one reported the day the console grew (ADR-113).
     "o.primary().range(first, last, (k, v) -> {\n                if (seen[0]++ < cap) {",
     "o.primary().range(first, last, (k, v) -> {\n                if (seen[0]++ < 1000) {",
     "sensitive sample is capped"),
    (CONSOLE, "cold-scan reports the live store instead of the archive",
     "int scanned = Organism.coldScan(a, (k, v) -> n[0]++);", "int scanned = o.primary().size();",
     "archive still reads the moment"),
    (CONSOLE, "a wire put quietly goes direct",
     "            try (SmokeSignalClient<Long, String> w = o.wire()) {\n                w.put(k, v);\n            }",
     "            o.store().put(k, v);",
     "metered exactly the traffic"),
    (CONSOLE, "a batch is built and never committed",
     '        b.commit();\n        return "{\\"ok\\":true,\\"ops\\":"',
     '        return "{\\"ok\\":true,\\"ops\\":"',
     "size"),
    # ---- ADR-113: every engine ------------------------------------------------
    (PLUGIN, "reads drop their route and always go direct",
     '        via = args.get("via") or "direct"\n        if action == "get":',
     '        via = "direct"\n        if action == "get":',
     "wire's own meters counted them"),
    (PLUGIN, "restart is relabelled MUTATE",
     '                           "NAVIGATE",\n                           [ArgumentSpec("chaos"',
     '                           "MUTATE",\n                           [ArgumentSpec("chaos"',
     "NAVIGATE"),
    (PLUGIN, "groups is relabelled READ, leaking the histogram under the default policy",
     '                           "SENSITIVE_READ",\n                           [ArgumentSpec("top"',
     '                           "READ",\n                           [ArgumentSpec("top"',
     "SENSITIVE_READ"),
    (CONSOLE, "median answers the first key",
     'case "median":     answer = w ? wire(SmokeSignalClient::medianKey) : p.medianKey(); break;',
     'case "median":     answer = w ? wire(SmokeSignalClient::firstKey) : p.firstKey(); break;',
     "median is the lower median"),
    (CONSOLE, "overlap runs a stab",
     "        var q = stab ? o.carver().query().stabbing(Organism.SPAN, lo)\n                     : o.carver().query().overlapping(Organism.SPAN, lo, hi);",
     "        var q = o.carver().query().stabbing(Organism.SPAN, lo);",
     "overlap agrees with brute force"),
    (CONSOLE, "the cache reports a hit when the store answered",
     ',\\"hit\\":" + (after.valueHits() > before.valueHits())',
     ',\\"hit\\":" + (after.storeReads() > before.storeReads())',
     "cache hit under champion"),
    (CONSOLE, "as-of reads the live store instead of the aged view",
     "            String v = past.store().get(k);",
     "            String v = o.store().get(k);",
     "as-of reads the frozen moment"),
    (CONSOLE, "restart ignores its plan",
     "        o = new Organism(organismRoot, seed, plan);",
     "        o = new Organism(organismRoot, seed);",
     "counts one injected fault"),
]

# Applied, measured, survived, and judged equivalent: the console refuses the
# same input with the same code, and "keep domain validation inside the target
# as well as at the boundary" is the contract's own rule, so the plugin's
# check is a second line, not the only one. Kept here with the measurement so
# the next reader does not re-run it and call the survival a finding.
KNOWN_EQUIVALENT = [
    ("the plugin's batch-op regex accepts anything",
     "the console refuses 'zap 3' with invalid_argument before the journal sees it; "
     "the suite observes the same code either way (measured 2026-09-01: 0 failures)"),
    ("the plugin's order-arg check is removed",
     "the console refuses 'order median 3' (3 is not a route) and 'order rank' (no key) "
     "with invalid_argument itself; same code either way (ADR-113, reasoned not run: "
     "identical shape to the batch-op case)"),
    ("replica-get reads the primary",
     "after quiesce the replica and the primary agree by construction, and the suite "
     "cannot hold the replica behind the primary without a Sizzle.slow seam on the "
     "replication tail, which the organism does not expose (ADR-113, held)"),
]


def run_one(target, find, repl, expect, cp):
    tmp = tempfile.mkdtemp(prefix="mutorganism_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        env = dict(os.environ, CSRBT_WHOLEHOG=os.path.normpath(O.wholehog_dir()),
                   CSRBT_ORGANISM_CLASSPATH=cp)
        if target == PLUGIN:
            path = os.path.join(dst, "harness_plugin_organism.py")
        else:
            path = os.path.join(tmp, "HarnessConsole.java")
            shutil.copy(os.path.join(O.wholehog_dir(), CONSOLE_REL), path)
        src = io.open(path, encoding="utf-8").read()
        if src.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times -- the mutation never applied"
                    % src.count(find))
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        if target == CONSOLE:
            classes = os.path.join(tmp, "classes")
            os.makedirs(classes)
            jc = subprocess.run(["javac", "-cp", cp, "-d", classes, path],
                                capture_output=True, text=True, timeout=300)
            if jc.returncode != 0:
                return ("BAD MUTANT", "mutant does not compile: %s" % jc.stderr.strip()[:80])
            env["CSRBT_ORGANISM_CLASSPATH"] = classes + os.pathsep + cp
        suite = os.path.join(dst, "verify", "verify_organism.py")
        p = subprocess.run([sys.executable, suite], capture_output=True, text=True,
                           timeout=1800, env=env)
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        if "NOT VERIFIED" in out:
            return ("BAD MUTANT", "the suite could not reach the engine under mutation")
        if not fails:
            return ("SURVIVED", "no check failed -- this clause is asserted by nobody")
        hit = any(expect in f for f in fails)
        return ("killed" if hit else "killed by the wrong check",
                "%d failure(s); first: %s" % (len(fails), fails[0][6:80]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    if a.list:
        for t, n, _, _, e in MUTANTS:
            print("  %-8s %-52s must be killed by  %s" % (t, n, e))
        for n, why in KNOWN_EQUIVALENT:
            print("  %-8s %-52s EQUIVALENT: %s" % ("plugin", n, why[:50]))
        return 0
    cp = O.classpath()
    if not cp:
        print("WholeHog is not built: ./gradlew harnessClasspath in %s"
              % os.path.normpath(O.wholehog_dir()))
        return 2
    if not shutil.which("javac"):
        print("no javac on the path; console mutants cannot be compiled")
        return 2
    print("mutation testing the organism plugin and console against verify_organism -- "
          "%d mutant(s), %d known equivalent\n" % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    for target, name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(target, find, repl, expect, cp)
        print("  %-9s %-8s %-52s %s" % (verdict, target, name, detail[:60]))
        if verdict == "SURVIVED":
            survived += 1
        elif verdict != "killed":
            bad += 1
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    if survived:
        print("A SURVIVING MUTANT IS THE FINDING: the plugin or the console can be broken "
              "that way and nothing notices.")
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
