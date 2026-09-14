# -*- coding: utf-8 -*-
"""Mutation testing for the local autosave layer, against verify_keep.

ADR-204. verify_keep is 112 checks about the thing in this kit that is read as a
PROMISE -- "Saved on this device" -- and nothing has ever shown that a single one
of them can fail. That is the same gap ADR-201 found in the entry layer and
ADR-203 wrote into the outbox: a suite whose subject has never been broken on
purpose is a suite whose verdict is a guess.

It matters more here than almost anywhere else in the kit, because KEEP exists
to replace a `try{ setItem }catch(e){}` that swallowed every failure. A user who
had watched the page work for an hour had every reason to believe their data was
safe. If the checks that hold KEEP to doing better are themselves asleep, the kit
has replaced a silent failure with a silent failure that prints a reassuring
sentence -- which is worse.

So the subject is `tools/keep.py`, the SOURCE, re-inlined into the pages by
`keep_emit.py` before the suite runs -- exactly the path a real edit takes. Every
mutant is a plausible edit: a probe that assumes instead of probing, a classifier
that stops classifying, an escape dropped, a guard inverted, a format stamp left
off.

    python3 tools/mutate_keep.py           # run every mutant
    python3 tools/mutate_keep.py --list    # the catalogue
    python3 tools/mutate_keep.py --only 3  # one, by index
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")

MUTANTS = [
    # ---- the probe: the difference between knowing and assuming ------------
    ("storage is assumed usable rather than probed",
     '    } catch(e){ return false; }\n  }\n\n  function when(ts){',
     '    } catch(e){ return true; }\n  }\n\n  function when(ts){',
     "IS KEEPING NOTHING SAYS SO"),
    ("a browser that keeps nothing is told only when a write fails, not when the page opens",
     '      if(!ok){\n        msg = "<b>This browser is not keeping anything.</b> Storage is '
     'unavailable here &mdash; a "\n            + "private window, or site data switched off. '
     'Nothing is being saved, so export before "\n            + "you close the tab.";\n'
     '      } else if(lastErr){',
     '      if(false){\n        msg = "";\n      } else if(lastErr){',
     "IS KEEPING NOTHING SAYS SO"),

    # ---- the failure that must not be swallowed ---------------------------
    ("a failed write is swallowed again, which is the whole bug KEEP exists to fix",
     '        lastErr = (e && e.name === "QuotaExceededError")\n'
     '          ? "this browser\'s storage is full" : "this browser refused the write";',
     '        lastErr = null;',
     "a full quota is reported, not swallowed"),
    ("the classifier stops classifying: every write failure reads as a full store",
     '        lastErr = (e && e.name === "QuotaExceededError")\n'
     '          ? "this browser\'s storage is full" : "this browser refused the write";',
     '        lastErr = "this browser\'s storage is full";',
     "reports a REFUSED write, not a full store"),
    ("a failure is reported but the strip is not styled as one",
     '      host.className = "keep noprint" + ((!ok || lastErr) ? " bad" : "");',
     '      host.className = "keep noprint";',
     "styled as a failure"),

    # ---- what is written down, and what is read back ----------------------
    ("the saved blob carries no format stamp",
     '        window.localStorage.setItem(key, JSON.stringify({ format:fmt, at:Date.now(), body:body }));',
     '        window.localStorage.setItem(key, JSON.stringify({ at:Date.now(), body:body }));',
     "carries a format stamp"),
    ("the saved blob carries no time, so nothing can say WHEN it saved",
     '        window.localStorage.setItem(key, JSON.stringify({ format:fmt, at:Date.now(), body:body }));',
     '        window.localStorage.setItem(key, JSON.stringify({ format:fmt, body:body }));',
     "carries a timestamp"),
    ("a blob from a format this page can no longer read is applied anyway",
     '        if(!p || p.format !== fmt) return null;',
     '        if(!p) return null;',
     "ignored, not half-applied"),
    ("unreadable storage is not caught, so one bad blob takes the page down",
     '      } catch(e){ return null; }\n    }\n\n    function write(){',
     '      } catch(e){ throw e; }\n    }\n\n    function write(){',
     "does not break the page"),

    # ---- the banner renders page text, and must not render page MARKUP ----
    ("the noun is not escaped on the first-run banner",
     '        msg = "Autosave is on. " + esc(noun.charAt(0).toUpperCase() + noun.slice(1))',
     '        msg = "Autosave is on. " + (noun.charAt(0).toUpperCase() + noun.slice(1))',
     "does not become markup in the banner"),
    ("the noun is not escaped on the restored banner",
     '        msg = "Restored " + esc(noun) + " from <b>" + esc(when(restoredFrom)) + "</b> on this device.";',
     '        msg = "Restored " + noun + " from <b>" + esc(when(restoredFrom)) + "</b> on this device.";',
     "escaped on the RESTORED path too"),

    # ---- what the page says about what this is ----------------------------
    ("the strip stops saying that a browser copy is not a backup",
     "+ '<p class=\"note\"><b>This is not a backup.</b> It is one browser on one device, and it goes '",
     "+ '<p class=\"note\"><b>Autosave.</b> '",
     "is not a backup"),
    ("the strip stops offering a way to remove the saved copy",
     '+ \'<button type="button" data-keep-forget>Forget this device\\\\\'s copy</button>\'',
     "+ ''",
     "offers a way to remove the saved copy"),

    # ---- forgetting really forgets ----------------------------------------
    ("forget does not cancel the pending write, so the debounced save puts the copy straight back",
     '      if(timer){ clearTimeout(timer); timer = null; }\n'
     '      try { window.localStorage.removeItem(key); }catch(e){}',
     '      try { window.localStorage.removeItem(key); }catch(e){}',
     "forget removes the stored copy"),
    ("forget clears the store but leaves the strip claiming a saved copy",
     '      savedAt = null; restoredFrom = null; lastErr = null; paint();',
     '      paint();',
     "forget resets the status strip"),

    # ---- the snapshot and the restore -------------------------------------
    ("the snapshot takes only the first field it finds",
     '      out[e.id] = (e.type === "checkbox" || e.type === "radio") ? (e.checked ? "1" : "") : e.value;',
     '      if(!Object.keys(out).length) out[e.id] = (e.type === "checkbox" || e.type === "radio") ? (e.checked ? "1" : "") : e.value;',
     "a hidden write-through field comes back"),
    ("the restore puts the value in the box and never through the widget, so a correct "
     "value sits under a wrong-looking dial",
     '      if(typeof FEK !== "undefined" && FEK.setField){',
     '      if(false){',
     "push through FEK when FEK is present"),
    ("the FEK guard becomes an OR, so a page without FEK throws on restore",
     '      if(typeof FEK !== "undefined" && FEK.setField){',
     '      if(typeof FEK !== "undefined" || FEK.setField){',
     "restores the input itself when FEK is absent"),
    # ---- the tab closing, and a restore the page refused -------------------
    ("nothing flushes when the tab is hidden, so the last edit dies in the debounce",
     '      window.addEventListener("pagehide", function(){ if(timer) flush(); });',
     '      window.addEventListener("pagehide", function(){});',
     "MID-DEBOUNCE FLUSHES"),
    ("a restore the page REFUSED is announced as one anyway",
     '      try { accepted = o.restore(got.body) !== false; } catch(e){ accepted = false; }',
     '      try { o.restore(got.body); accepted = true; } catch(e){ accepted = true; }',
     "REFUSED IS NOT ANNOUNCED AS ONE"),
    ("a restore that THREW is announced as a success",
     '      try { accepted = o.restore(got.body) !== false; } catch(e){ accepted = false; }',
     '      try { accepted = o.restore(got.body) !== false; } catch(e){ accepted = true; }',
     "THAT THREW IS NOT ANNOUNCED AS ONE EITHER"),
    # ---- the list the suite reads, in the file that owns it ----------------
    # Not keep.py: this is the defect ADR-204 found, and it lives in the
    # emitter. The suite reads the emitter's list so that a page wired
    # tomorrow is covered tomorrow; drop a page from that list and the suite
    # must notice it is opening fewer pages than carry the layer.
    ("a page that inlines the autosave layer is dropped from the list the suite reads",
     '             "survey-design.html", "greenhouse.html"]',
     '             "survey-design.html"]',
     "is a page this suite opens", "keep_emit.py"),

    ("formRestore reports nothing restored, so a caller cannot tell a restore from a no-op",
     '      n++;\n    }\n    return n;',
     '    }\n    return 0;',
     "restores the input itself when FEK is absent"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect, where="keep.py"):
    tmp = tempfile.mkdtemp(prefix="mutkeep_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        # docs is COPIED, not linked: KEEP is inlined into the pages, so a
        # mutant in the module reaches the suite only by way of the emitter --
        # which is how a real edit reaches them too.
        shutil.copytree(os.path.join(ROOT, "docs"), os.path.join(tmp, "docs"))
        target = os.path.join(dst, where)
        body = io.open(target, encoding="utf-8").read()
        if body.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times -- the mutation never applied"
                    % body.count(find))
        io.open(target, "w", encoding="utf-8", newline="\n").write(body.replace(find, repl, 1))
        e = subprocess.run([sys.executable, os.path.join(dst, "keep_emit.py")],
                           capture_output=True, text=True, timeout=300)
        if e.returncode != 0:
            return ("BAD MUTANT", "the emitter refused the mutated module: %s"
                    % (e.stdout + e.stderr).strip()[-70:])
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_keep.py")],
                           capture_output=True, text=True, timeout=1800)
        out = p.stdout + p.stderr
        fails = [l for l in out.split("\n") if l.startswith("FAIL")]
        if not fails and p.returncode != 0:
            return ("BAD MUTANT", "the suite crashed rather than failed: %s"
                    % (out.strip().split("\n")[-1][:70] if out.strip() else "no output"))
        if not fails:
            return ("SURVIVED", "no check failed -- this clause is asserted by nobody")
        return ("killed" if any(expect in f for f in fails) else "killed by the wrong check",
                "%d failure(s); first: %s" % (len(fails), fails[0][6:90]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", type=int, default=None)
    a = ap.parse_args(argv)
    if a.list:
        for i, m in enumerate(MUTANTS):
            print("  %2d %-10s %-70s killed by  %s"
                  % (i, m[4] if len(m) > 4 else "keep.py", m[0][:70], m[3]))
        return 0
    todo = MUTANTS if a.only is None else [MUTANTS[a.only]]
    print("mutation testing the local autosave layer against verify_keep -- %d mutant(s), "
          "%d known equivalent\n" % (len(todo), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for m in todo:
        name, find, repl, expect = m[0], m[1], m[2], m[3]
        verdict, detail = run_one(find, repl, expect, m[4] if len(m) > 4 else "keep.py")
        print("  %-9s %-78s %s" % (verdict, name[:78], detail[:48]))
        sys.stdout.flush()
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    if a.only is None:
        sys.path.insert(0, TOOLS)
        import mutant_ledger
        mutant_ledger.record("mutate_keep", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             " (recorded)" if a.only is None else ""))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
