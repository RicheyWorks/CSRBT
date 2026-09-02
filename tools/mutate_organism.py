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
    (PLUGIN, "the manifest stops publishing the range cap's bound",
     '                        minimum=1, maximum=RANGE_CAP)',
     '                        minimum=1)',
     "publishes its bound"),
    (PLUGIN, "a dead console is reported as the target failing",
     'raise Unavailable("console exited (rc=%s)" % self.proc.poll())',
     'raise Failed("console exited (rc=%s)" % self.proc.poll())',
     "killed console is reported unavailable"),
    (PLUGIN, "the pump dies without telling the reader",
     "        self._q.put(None)\n\n    def _drain", "        pass\n\n    def _drain",
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
    (CONSOLE, "a wedged Twine is reported as the organism failing",
     '            return refuse("conflict", e.getMessage());',
     '            return refuse("failed", e.getMessage());',
     "is a CONFLICT"),
    (CONSOLE, "a span with start > end is not checked before the route",
     '        if (start > end) {\n            throw new IllegalArgumentException("span start "',
     '        if (false) {\n            throw new IllegalArgumentException("span start "',
     "OVER THE WIRE too"),
    (PLUGIN, "the snapshot stops publishing the generation pool",
     '        s["argumentPools"] = {"generation": s.pop("generationIds", [])}',
     '        s["argumentPools"] = {"generation": []}',
     "argument pool"),
    (CONSOLE, "restart ignores its plan",
     "        o = new Organism(organismRoot, seed, plan, replicaLag);",
     "        o = new Organism(organismRoot, seed, ChaosPlan.none(), replicaLag);",
     "counts one injected fault"),
    # ADR-120: the held items, closed
    (CONSOLE, "restart lets the feed go whatever lag was asked for",
     "        o = new Organism(organismRoot, seed, plan, replicaLag);",
     "        o = new Organism(organismRoot, seed, plan, 0);",
     "reports the replica BEHIND"),
    (PLUGIN, "the plugin never passes the replica lag to the console",
     '            r = c.send("restart", plan, lat, lag, how)',
     '            r = c.send("restart", plan, lat, 0, how)',
     "held back 200 ms"),
    (CONSOLE, "the fleet always reports lag 0",
     'rs.add("{\\"name\\":" + str(st.name()) + ",\\"lag\\":" + st.lag() + ",\\"gapped\\":" + st.gapped()',
     'rs.add("{\\"name\\":" + str(st.name()) + ",\\"lag\\":" + 0 + ",\\"gapped\\":" + st.gapped()',
     "reports the replica BEHIND"),
    # ADR-122: engine 2, observed
    (CONSOLE, "a cold restart closes cleanly after all",
     '        if (how.equals("cold")) {\n            o.crash();',
     '        if (false) {\n            o.crash();',
     "recovered every live key from the log alone and SORTED"),
    (PLUGIN, "the plugin never passes how to the console",
     '            r = c.send("restart", plan, lat, lag, how)',
     '            r = c.send("restart", plan, lat, lag)',
     "recovered every live key from the log alone and SORTED"),
    (CONSOLE, "the recovery report always says sorted",
     '                + ",\\"sorted\\":" + r.sorted() + ",\\"sortStrategy\\":" + str(r.sortStrategy())',
     '                + ",\\"sorted\\":" + true + ",\\"sortStrategy\\":" + str(r.sortStrategy())',
     "checkpoint used, nothing sorted"),
    (PLUGIN, "the bound-pair pools are not published",
     '        s["argumentPools"].update({"range.lo": [0, 1, 50], "range.hi": [200, 999, 100_000],',
     '        {}.update({"range.lo": [0, 1, 50], "range.hi": [200, 999, 100_000],',
     "every low value is below"),
    (CONSOLE, "jvm reports no thread names",
     '            if (ti != null) {\n                names.add(ti.getThreadName());',
     '            if (false) {\n                names.add(ti.getThreadName());',
     "jvm reads the process"),
    (CONSOLE, "compact reports every dead byte as reclaimed",
     'return "{\\"ok\\":true,\\"reclaimed\\":" + reclaimed + ",\\"garbageBefore\\":" + before',
     'return "{\\"ok\\":true,\\"reclaimed\\":" + before + ",\\"garbageBefore\\":" + before',
     "EXACTLY the closed segments"),
]

# Applied, measured, survived, and judged equivalent: the console refuses the
# same input with the same code, and "keep domain validation inside the target
# as well as at the boundary" is the contract's own rule, so the plugin's
# check is a second line, not the only one. Kept here with the measurement so
# the next reader does not re-run it and call the survival a finding.
KNOWN_EQUIVALENT = [
    ("the plugin's own _cap() stops bounding the range cap",
     "since ADR-114 the bound is published in the schema and the gateway refuses cap > 200 "
     "before execute() runs; _cap() is the target-side second line (killed under ADR-112, "
     "equivalent from ADR-114 on -- measured: 0 failures)"),
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
        if not fails and p.returncode != 0:
            # A suite that crashed under mutation asserted nothing either way. Reporting
            # it SURVIVED would be the tool accusing its own suite of a hole it does not
            # have; reporting it killed would be a kill by a traceback. Neither is a result.
            return ("BAD MUTANT", "the suite crashed rather than failed: %s"
                    % (out.strip().split("\n")[-1][:70] if out.strip() else "no output"))
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
    rows = []
    for target, name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(target, find, repl, expect, cp)
        print("  %-9s %-8s %-52s %s" % (verdict, target, name, detail[:60]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        if verdict == "SURVIVED":
            survived += 1
        elif verdict != "killed":
            bad += 1
    import mutant_ledger
    mutant_ledger.record("mutate_organism", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    if survived:
        print("A SURVIVING MUTANT IS THE FINDING: the plugin or the console can be broken "
              "that way and nothing notices.")
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
