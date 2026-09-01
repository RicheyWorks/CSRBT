# -*- coding: utf-8 -*-
"""Mutation testing for the lab plugin and its console (ADR-116).

WHY

verify_lab passed 33 of 34 on the afternoon it was written -- and the one
failure was real (the shipped session was behind the engine). Same rule as
every suite in the kit: break the plugin and the console on purpose and
require the suite to notice. Each mutant names the check that must kill it.

SAFETY

Nothing real is written to. Plugin mutants run against a copy of tools/ in a
temp dir. Console mutants compile a copy of HarnessConsole.java with javac
into a scratch directory that is put FIRST on the classpath through
CSRBT_LAB_CLASSPATH, so the built organism under csrbt-experimental/build is never
touched. Needs the engine built (`./gradlew :csrbt-experimental:harnessClasspath`) and
a javac on the path; without either it says so and exits 2, not 0.

    python3 tools/mutate_lab.py           # run every mutant
    python3 tools/mutate_lab.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)
import harness_plugin_lab as O

CONSOLE = os.path.join(ROOT, "csrbt-experimental", "src", "main", "java", "io", "github",
                       "richeyworks", "csrbt", "experimental", "LabConsole.java")

# (target, name, find, replace, substring of the check that must fail)
PLUGIN, CONSOLE_T = "plugin", "console"
MUTANTS = [
    (PLUGIN, "verdicts are all counted as CONFIRMED",
     '            verdicts[h.get("verdict")] = verdicts.get(h.get("verdict"), 0) + 1',
     '            verdicts["CONFIRMED"] = verdicts.get("CONFIRMED", 0) + 1',
     "six confirmed, one refuted"),
    (PLUGIN, "the protocol's name is shown under every policy",
     '            s.pop("lastName", None)', '            pass',
     "shows only under SENSITIVE_READ"),
    (PLUGIN, "exports land beside the operator's files instead of in scratch",
     '        d = os.path.join(self.scratch, "export-%d" % (len(os.listdir(self.scratch)) + 1))',
     '        d = os.path.join(tempfile.gettempdir(), "csrbt-lab-loose")',
     "plugin's scratch"),
    (CONSOLE_T, "the console stops refusing dwc: lines",
     '            if (l.trim().toLowerCase(Locale.ROOT).startsWith("dwc:")) {',
     '            if (false) {',
     "console itself"),
    (CONSOLE_T, "lint swallows the problems",
     '                + ",\\"trees\\":" + s.trees().size() + ",\\"problems\\":" + strs(s.problems()) + "}";',
     '                + ",\\"trees\\":" + s.trees().size() + ",\\"problems\\":[]}";',
     "names the malformed line"),
    (CONSOLE_T, "the arena ignores its seed",
     "        List<StrategyBattleRunner.BattleResult> rs = StrategyBattleRunner.run(w, ops, seed);",
     "        List<StrategyBattleRunner.BattleResult> rs = StrategyBattleRunner.run(w, ops, 0L);",
     "different seed is a different workload"),
    (CONSOLE_T, "the morph log is never reported",
     "        for (GenomeDrivenTreeController.MorphEvent e : c.getMorphLog()) {",
     "        for (GenomeDrivenTreeController.MorphEvent e : java.util.List.<GenomeDrivenTreeController.MorphEvent>of()) {",
     "morph log has"),
    (CONSOLE_T, "run returns the wrong session",
     '                + ",\\"session\\":" + str(files.get("session.json"))',
     '                + ",\\"session\\":" + str("{}")',
     "session the repository ships"),
    (CONSOLE_T, "export writes nothing",
     "            Files.write(d.resolve(e.getKey()), e.getValue());",
     "            ;",
     "on disk and equals"),
]

KNOWN_EQUIVALENT = [
    ("the plugin's own dwc: check is removed",
     "the console refuses the same line with the same code before parsing; the suite "
     "sees invalid_argument either way (measured 2026-09-01: 0 failures)"),
]


def run_one(target, find, repl, expect, cp):
    tmp = tempfile.mkdtemp(prefix="mutlab_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        # The plugin lists docs/*.eco and the suite reads the shipped session, both
        # relative to the tree the tools live in; give the copy what it will look for.
        docs = os.path.join(tmp, "docs")
        os.makedirs(docs)
        for f in os.listdir(os.path.join(ROOT, "docs")):
            if f.endswith(".eco") or f == "ecology-experiment-session.json":
                shutil.copy(os.path.join(ROOT, "docs", f), docs)
        env = dict(os.environ, CSRBT_LAB_CLASSPATH=cp)
        if target == PLUGIN:
            path = os.path.join(dst, "harness_plugin_lab.py")
        else:
            path = os.path.join(tmp, "LabConsole.java")
            shutil.copy(CONSOLE, path)
        src = io.open(path, encoding="utf-8").read()
        if src.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times -- the mutation never applied" % src.count(find))
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        if target == CONSOLE_T:
            classes = os.path.join(tmp, "classes")
            os.makedirs(classes)
            jc = subprocess.run(["javac", "-cp", cp, "-d", classes, path],
                                capture_output=True, text=True, timeout=300)
            if jc.returncode != 0:
                return ("BAD MUTANT", "mutant does not compile: %s" % jc.stderr.strip()[:80])
            env["CSRBT_LAB_CLASSPATH"] = classes + os.pathsep + cp
        suite = os.path.join(dst, "verify", "verify_lab.py")
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
        print("csrbt-experimental is not built: ./gradlew :csrbt-experimental:harnessClasspath")
        return 2
    if not shutil.which("javac"):
        print("no javac on the path; console mutants cannot be compiled")
        return 2
    print("mutation testing the lab plugin and console against verify_lab -- "
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
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
