# -*- coding: utf-8 -*-
"""Run every verification suite and every audit in the kit.

    python3 tools/verify/run_all.py            # everything
    python3 tools/verify/run_all.py --audits   # just the audits
    python3 tools/verify/run_all.py --suites   # just the page suites
    python3 tools/verify/run_all.py -j 4       # four at a time

Exits non-zero if anything fails, so it can gate a commit. Each suite is a
standalone script that prints "n/m" on its last line and exits non-zero on
failure -- no test framework, because the kit has no build step and adding one
to run the tests would defeat the constraint the tests exist to protect.

Requires Playwright with Chromium:  pip install playwright && playwright install chromium
"""
import argparse, concurrent.futures as cf, glob, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
TOOLS = os.path.join(ROOT, "tools")

AUDITS = [
    ("audit_targets",  "44px touch targets"),
    ("audit_focus",    "keyboard reach, visible focus, accessible names"),
    ("audit_contrast", "WCAG AA colour contrast"),
    ("audit_print",    "print fidelity"),
    ("audit_offline",  "works with no signal, and does not hang on one bar"),
    ("audit_frontend", "duplicate ids, dead links, iOS zoom, JS and console errors"),
    ("fek_lint",       "FEK misconfiguration"),
]
# A finder, not a gate: it reports a worklist and always exits zero, so running
# it here would say nothing about pass or fail. Named so it is not forgotten.
FINDERS = [("audit_claims", "unsourced numeric claims (worklist only)")]

TAIL = re.compile(r"(\d+)\s*/\s*(\d+)\s*$")


def run(cmd, cwd):
    t0 = time.time()
    p = subprocess.run([sys.executable, cmd], cwd=cwd, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or ""), time.time() - t0


def score(out):
    for line in reversed(out.strip().split("\n")):
        m = TAIL.search(line.strip())
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audits", action="store_true", help="audits only")
    ap.add_argument("--suites", action="store_true", help="page suites only")
    ap.add_argument("-j", "--jobs", type=int, default=2,
                    help="how many to run at once (each drives a browser; 2 is kind to a laptop)")
    ap.add_argument("-v", "--verbose", action="store_true", help="print failing output in full")
    a = ap.parse_args()
    do_audits = a.audits or not a.suites
    do_suites = a.suites or not a.audits

    jobs = []
    if do_audits:
        for name, what in AUDITS:
            jobs.append(("audit", name, what, os.path.join(TOOLS, name + ".py"), TOOLS))
    if do_suites:
        for path in sorted(glob.glob(os.path.join(HERE, "verify_*.py"))):
            jobs.append(("suite", os.path.basename(path)[:-3], "", path, HERE))

    if not jobs:
        print("nothing to run"); return 1

    print("CSRBT verification  --  %d job(s), %d at a time" % (len(jobs), a.jobs))
    print("root: %s" % ROOT)
    print("-" * 76)

    results, failed = [], []
    with cf.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        futs = {ex.submit(run, path, cwd): (kind, name, what)
                for kind, name, what, path, cwd in jobs}
        for fut in cf.as_completed(futs):
            kind, name, what = futs[fut]
            rc, out, secs = fut.result()
            got, tot = score(out)
            results.append((kind, name, what, rc, got, tot, secs, out))

    order = {"audit": 0, "suite": 1}
    results.sort(key=lambda r: (order[r[0]], r[1]))
    passed = checks = total = 0
    for kind, name, what, rc, got, tot, secs, out in results:
        if rc == 0:
            mark = "ok"
            passed += 1
        else:
            mark = "FAIL"
            failed.append((name, out))
        if got is not None:
            checks += got; total += tot
            detail = "%d/%d" % (got, tot)
        else:
            detail = (out.strip().split("\n")[-1][:34] if out.strip() else "")
        print("%-6s %-24s %-6s %-34s %5.1fs" % (mark, name, detail, what, secs))

    print("-" * 76)
    print("%d of %d jobs green" % (passed, len(results)))
    if total:
        print("%d of %d checks passing" % (checks, total))
    for name, what in FINDERS:
        print("not run here: %s -- %s" % (name, what))

    if failed:
        print()
        print("FAILURES")
        for name, out in failed:
            print("=" * 76)
            print(name)
            lines = [l for l in out.split("\n") if l.startswith("FAIL") or "Error" in l]
            for l in (out.split("\n") if a.verbose else lines[:12]):
                print("   " + l)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
