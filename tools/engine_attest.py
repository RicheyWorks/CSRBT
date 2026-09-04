# -*- coding: utf-8 -*-
"""Running the engine, and the record of having run it (ADR-139).

`docs/ecology-lab-session.json` is supposed to be the output of
`EcologyFieldDay.run().json()`. `verify_engine_sessions` checks that by
RUNNING the engine -- javac, java, byte-compare -- which is the only check
worth having and the one that cannot run on a machine with no JDK, no built
classes, or (the case that actually bites here) built classes and no log4j in
its Gradle cache. On those machines the link reported NOT VERIFIED, and it has
reported NOT VERIFIED on most runs since it was written.

A hole nobody can close is a hole that stays open. This file closes the part
of it that CAN be closed honestly, and is careful about which part that is.

    python3 tools/engine_attest.py            # what is attested, and whether it still applies
    python3 tools/engine_attest.py --attest   # run the engine and record what it emitted
    python3 tools/engine_attest.py --check    # exit non-zero if an attestation no longer applies

WHAT AN ATTESTATION IS, AND WHAT IT IS NOT

It is NOT a cached copy of the engine's output standing in for the engine. A
fixture like that would pass on a machine where the engine has been broken for
a month, which is worse than the hole.

It is a dated observation with a decay rule, the same shape ADR-078 gave a
published page:

    "on <date>, on <java>, the engine emitted exactly these bytes, and the
     engine's sources digested to <sha> at that moment."

On a machine that can run the engine, the live check runs and the attestation
is beside the point. On a machine that cannot, the attestation is evidence
exactly while the engine's sources are UNCHANGED since it was taken. Move one
byte of `csrbt-core` or `csrbt-experimental` and the attestation stops
applying -- by construction, not by anyone remembering -- and the link goes
back to NOT VERIFIED, now naming how many source files moved.

The digest deliberately covers both modules whole rather than the ecology
package alone. Over-broad, and it errs in the safe direction: a change that
could not possibly affect the session invalidates the attestation and costs one
re-run on a machine with a JDK, while a narrow digest that missed a real
dependency would keep saying "still applies" about an engine that had moved.
"""
import argparse, glob, hashlib, io, json, os, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
STATE = os.path.join(HERE, "engine_attest.json")

# What the engine's output depends on. Both modules' main sources, whole.
SOURCE_ROOTS = (os.path.join("csrbt-core", "src", "main", "java"),
                os.path.join("csrbt-experimental", "src", "main", "java"))

# artifact -> the Java expression that regenerates it
ARTIFACTS = {
    "docs/ecology-lab-session.json":
        ("io.github.richeyworks.csrbt.experimental.ecology.EcologyFieldDay",
         "EcologyFieldDay.run().json()"),
}


def source_files():
    out = []
    for r in SOURCE_ROOTS:
        d = os.path.join(ROOT, r)
        out += sorted(glob.glob(os.path.join(d, "**", "*.java"), recursive=True))
    return out


def engine_digest():
    """(sha, file count). A digest of the engine's sources, path and bytes.

    Path AND bytes: a file renamed with its content unchanged is a different
    engine, and a digest of contents alone would call it the same one."""
    h = hashlib.sha256()
    files = source_files()
    for f in files:
        h.update(os.path.relpath(f, ROOT).replace(os.sep, "/").encode("utf-8"))
        h.update(b"\0")
        h.update(io.open(f, "rb").read())
        h.update(b"\0")
    return h.hexdigest(), len(files)


def classpath():
    """(classpath, why_not). Two things can be missing and they are not the same
    thing, so this says which.

    The single message this used to return -- "engine classes or log4j not found
    -- run ./gradlew classes" -- named the wrong cause on the machine where it
    actually fires. In the desktop Linux VM the classes ARE built (they come
    over the mount from the Windows host) and it is the log4j jars that are
    absent, because they live in the HOST's ~/.gradle cache and that is not
    mounted. The advice was worse than vague: `./gradlew classes` cannot run
    there at all -- Gradle 9 needs JVM 17+ and that VM has 11 -- so a reader
    following it got a second failure that explained nothing about the first.
    """
    written = os.path.join(ROOT, "csrbt-experimental", "build", "harness", "classpath.txt")
    if os.path.isfile(written):
        cp = io.open(written, encoding="utf-8").read().strip()
        head = cp.split(os.pathsep)[0]
        if os.path.isdir(head):
            return cp, None
    parts = [os.path.join(ROOT, "csrbt-experimental", "build", "classes", "java", "main"),
             os.path.join(ROOT, "csrbt-core", "build", "classes", "java", "main")]
    missing = [p for p in parts if not os.path.isdir(p)]
    if missing:
        return None, ("engine classes not built (%s) -- run ./gradlew classes on a JDK 17+"
                      % os.path.relpath(missing[0], ROOT))
    for pat in ("log4j-api-*.jar", "log4j-core-*.jar"):
        hit = glob.glob(os.path.join(os.path.expanduser("~"), ".gradle", "caches",
                                     "modules-2", "files-2.1", "**", pat), recursive=True)
        if not hit:
            return None, ("classes are built but %s is not in this machine's "
                          "~/.gradle cache -- run this suite where the engine was built"
                          % pat)
        parts.append(sorted(hit)[-1])
    return os.pathsep.join(parts), None


def engine_output(artifact="docs/ecology-lab-session.json"):
    """(text, why_not). Never raises: an engine that will not start is an
    UNVERIFIED result, not a crash and certainly not a pass."""
    cls, expr = ARTIFACTS[artifact]
    cp, why_not = classpath()
    if cp is None:
        return None, why_not
    src = ('import %s;\n'
           'public class _Regen { public static void main(String[] a) throws Exception {\n'
           '  System.out.print(%s); } }\n' % (cls, expr))
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "_Regen.java")
        io.open(f, "w", encoding="utf-8").write(src)
        try:
            c = subprocess.run(["javac", "-cp", cp, "-d", d, f],
                               capture_output=True, text=True, timeout=180)
            if c.returncode:
                return None, "javac failed: " + c.stderr.strip().splitlines()[-1][:120]
            r = subprocess.run(["java", "-cp", cp + os.pathsep + d, "_Regen"],
                               capture_output=True, text=True, timeout=300)
            if r.returncode:
                return None, "engine run failed: " + r.stderr.strip().splitlines()[-1][:120]
            return r.stdout, None
        except (OSError, subprocess.TimeoutExpired) as e:
            return None, "%s: %s" % (type(e).__name__, e)


def java_version():
    try:
        r = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=60)
        # "Picked up JAVA_TOOL_OPTIONS: ..." is printed BEFORE the version on
        # machines that set it, and taking line one recorded the environment
        # variable as the JVM.
        lines = [l.strip() for l in (r.stderr or r.stdout).splitlines()
                 if l.strip() and not l.startswith("Picked up ")]
        return lines[0][:80] if lines else "unknown"
    except Exception:
        return "unknown"


def load():
    if os.path.isfile(STATE):
        try:
            return json.load(io.open(STATE, encoding="utf-8"))
        except ValueError:
            pass
    return {"_comment": "Written by tools/engine_attest.py --attest, only on a machine that RAN "
                        "the engine. Each entry says what the engine emitted, and digests the "
                        "engine's sources as they stood at that moment -- so the record stops "
                        "applying the instant the engine moves (ADR-139).",
            "artifacts": {}}


def save(state):
    io.open(STATE, "w", encoding="utf-8").write(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def sha_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def applies(entry, digest):
    """Does this attestation still describe THIS engine? -> (bool, why)."""
    if not entry:
        return False, "nothing attested"
    if entry.get("engineDigest") != digest:
        return False, ("the engine has moved since this was attested (%s, %d source files then)"
                       % (time.strftime("%Y-%m-%d", time.localtime(entry.get("at", 0))),
                          entry.get("sourceFiles", 0)))
    return True, ("attested %s on %s, engine sources unchanged since"
                  % (time.strftime("%Y-%m-%d", time.localtime(entry.get("at", 0))),
                     entry.get("java", "an unrecorded JVM")))


def check(artifact, shipped_text, state=None, digest=None):
    """What can be said about this shipped artifact WITHOUT running the engine.

    -> ("attested", why) the engine emitted exactly these bytes, and has not
                         moved since
       ("differs", why)  an attestation applies and the shipped bytes are NOT
                         what the engine emitted -- a real failure, on any
                         machine, with no JDK needed
       ("stale", why)    an attestation exists but the engine has moved
       ("absent", why)   nothing has ever been attested here
    """
    state = state if state is not None else load()
    digest = digest if digest is not None else engine_digest()[0]
    e = (state.get("artifacts") or {}).get(artifact)
    ok, why = applies(e, digest)
    if not ok:
        return ("absent" if e is None else "stale"), why
    if e.get("sha") != sha_text(shipped_text):
        return "differs", ("the engine emitted %s; the shipped file is %s -- %s"
                           % (e["sha"][:12], sha_text(shipped_text)[:12], why))
    return "attested", why


def attest(artifact, state=None):
    """Run the engine and record what it emitted. -> (entry, why_not)."""
    state = state if state is not None else load()
    text, why = engine_output(artifact)
    if text is None:
        return None, why
    digest, n = engine_digest()
    entry = {"sha": sha_text(text), "bytes": len(text.encode("utf-8")),
             "engineDigest": digest, "sourceFiles": n,
             "java": java_version(), "at": int(time.time()),
             "expr": ARTIFACTS[artifact][1]}
    state.setdefault("artifacts", {})[artifact] = entry
    return entry, None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--attest", action="store_true",
                    help="run the engine and record what it emitted (needs a JDK and the build)")
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero unless every artifact is attested and the attestation applies")
    a = ap.parse_args(argv)
    state = load()
    digest, n = engine_digest()
    rc = 0

    if a.attest:
        for art in sorted(ARTIFACTS):
            entry, why = attest(art, state)
            if entry is None:
                print("%-34s NOT ATTESTED  %s" % (art, why))
                rc = 2
                continue
            shipped = io.open(os.path.join(ROOT, art), encoding="utf-8").read()
            same = sha_text(shipped) == entry["sha"]
            print("%-34s attested %s (%d bytes) -- the shipped file %s"
                  % (art, entry["sha"][:12], entry["bytes"],
                     "matches" if same else "DIFFERS, and this attestation now says so"))
            if not same:
                rc = 1
        save(state)
        print("engine digest %s over %d source file(s); wrote %s"
              % (digest[:12], n, os.path.relpath(STATE, ROOT)))
        return rc

    print("engine attestation  --  digest %s over %d source file(s)" % (digest[:12], n))
    print("-" * 72)
    for art in sorted(ARTIFACTS):
        shipped_path = os.path.join(ROOT, art)
        if not os.path.exists(shipped_path):
            print("%-34s MISSING   %s" % (art, art))
            rc = 1
            continue
        kind, why = check(art, io.open(shipped_path, encoding="utf-8").read(), state, digest)
        print("%-34s %-9s %s" % (art, kind.upper(), why))
        if kind in ("differs",):
            rc = 1
        elif kind in ("stale", "absent") and a.check:
            rc = 1
    print("-" * 72)
    cp, why_not = classpath()
    print("this machine %s run the engine%s"
          % ("CAN" if cp else "cannot", "" if cp else ": " + (why_not or "")))
    if not cp:
        print("The live check is the one that matters and it is not available here. What an\n"
              "attestation can say is narrower and it is said in those words above.")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
