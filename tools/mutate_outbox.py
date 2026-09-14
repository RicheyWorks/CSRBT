# -*- coding: utf-8 -*-
"""Mutation testing for the outbox, against verify_outbox.

ADR-203. A ledger about data safety is the most dangerous thing this kit can
build: a wrong one is not read as a bug, it is read as reassurance. "Everything
here has left this device" on a sheet that has left nothing is a sentence that
costs somebody a field season, and it looks exactly like the true one.

So the subject is broken on purpose in the ways it would plausibly be wrong --
the mark taken on the click rather than the copy, one stamp for the whole sheet
rather than one per export, a hash that agrees with itself and nothing else, a
baseline read off a restored sheet -- and verify_outbox has to notice every one.

TWO PLACES A MUTANT CAN LAND, because the component and its hook are separate
things and fail differently. "module" is tools/outbox.py, the source, which is
re-inlined into the pages before the suite runs -- exactly as a real edit would
be. "page" is the wiring inside one consumer: the success path the mark sits in,
and the export ids the call sites pass. A fault in the module arrives on eight
pages at once; a fault in the wiring arrives on one, silently, which is the more
dangerous of the two and the reason the suite drives every consumer rather than
a representative.

    python3 tools/mutate_outbox.py           # run every mutant
    python3 tools/mutate_outbox.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")

MUTANTS = [
    # ---- the checksum, which everything else rests on ---------------------
    ("the hash falls back instead of refusing when the kit's checksum is gone",
     '    if (typeof FEK === "undefined" || !FEK || typeof FEK.crc32 !== "function") return null;',
     '    if (typeof FEK === "undefined" || !FEK || typeof FEK.crc32 !== "function") return "00000000";',
     "the outbox REFUSES", "module"),
    ("a character outside the basic plane is encoded as two halves",
     '        u = 0x10000 + ((c - 0xD800) << 10) + (c2 - 0xDC00); i++;',
     '        u = 0xFFFD; ',
     "agrees with Python's", "module"),
    ("a three-byte character loses its top bits",
     '      out.push(0xE0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));',
     '      out.push(0x80 | ((c >> 6) & 63), 0x80 | (c & 63));',
     "agrees with Python's", "module"),

    # ---- what "pending" means ---------------------------------------------
    ("an export never goes stale, so a sheet edited after its export still reads as sent",
     '                    stale: !!s && crc !== null && crc !== "" && s.crc !== crc });',
     '                    stale: false });',
     "MAKES THAT EXPORT STALE", "module"),
    ("staleness is decided on the size of the export rather than its content",
     '                    stale: !!s && crc !== null && crc !== "" && s.crc !== crc });',
     '                    stale: !!s && crc !== null && crc !== "" && s.bytes !== 0 });',
     "copying one export marks THAT ONE", "module"),
    ("a copy that carries no records is counted like one that does, so the strip nags "
     "about the AI prompt",
     '        if(!rows[i].records) continue;',
     '        if(false) continue;',
     "an outbox that nagged", "module"),
    ("a sheet nobody has typed on reports every export overdue",
     '      var blank = (crc === "") || (base !== null && crc === base);',
     '      var blank = false;',
     "nothing to send", "module"),
    ("THE BASELINE IS READ OFF A RESTORED SHEET, so a morning the autosave brought back "
     "reports itself as nothing to send",
     '    base = (keep && typeof keep.restored === "function" && keep.restored()) ? null : nowCrc();',
     '    base = nowCrc();',
     "ENTIRELY OUTSTANDING", "module"),

    # ---- an export it does not know ---------------------------------------
    ("an export the sheet never declared is quietly filed under the first one",
     '    function def(id){ var i; for(i=0;i<defs.length;i++) if(defs[i].id === id) return defs[i]; return null; }',
     '    function def(id){ var i; for(i=0;i<defs.length;i++) if(defs[i].id === id) return defs[i]; return defs[0] || null; }',
     "NOT A SHRUG", "module"),

    # ---- the ledger itself -------------------------------------------------
    ("a stamp for an export the sheet no longer has is carried forward",
     '        for(id in p.sends) if(p.sends.hasOwnProperty(id) && def(id)) sends[id] = p.sends[id];',
     '        for(id in p.sends) if(p.sends.hasOwnProperty(id)) sends[id] = p.sends[id];',
     "NO LONGER HAS IS DROPPED", "module"),
    ("the ledger is written without a format stamp",
     '      try { window.localStorage.setItem(key, JSON.stringify({format:fmt, sends:sends})); }',
     '      try { window.localStorage.setItem(key, JSON.stringify({sends:sends})); }',
     "with a format stamp", "module"),
    ("a ledger that cannot be written down fails quietly",
     '        lastErr = (e && e.name === "QuotaExceededError")',
     '        lastErr = (e && e.name === "__never__")',
     "CANNOT BE WRITTEN DOWN SAYS SO", "module"),

    # ---- what the strip says ----------------------------------------------
    ("the strip stops being a live region, so nothing announces an export landing",
     '\'<p class="st" role="status" aria-live="polite">\' + msg + \'</p>\'',
     '\'<p class="st">\' + msg + \'</p>\'',
     "is a live region", "module"),
    ("the strip stops saying it is a ledger and not a transport",
     "+ '<p class=\"note\"><b>This is a ledger, not a transport.</b> A page opened from a card '",
     "+ '<p class=\"note\"><b>The outbox.</b> '",
     "not a transport", "module"),
    ("a stale export is listed without saying since when",
     '        else if(r.stale) li += "<li>" + esc(r.label) + " <span class=\\\\"why\\\\">changed since "',
     '        else if(r.stale) li += "<li>" + esc(r.label) + " <span class=\\\\"why\\\\">stale "',
     "spelled out rather than left as a count", "module"),
    ("nothing repaints the strip after an edit, so it reports the sheet as it was at load",
     '        document.addEventListener(ev, touch, true); });',
     '        document.addEventListener(ev, function(){}, true); });',
     "says so in words", "module"),

    # ---- the hook, in one page --------------------------------------------
    ("THE MARK IS TAKEN ON THE CLICK RATHER THAN ON THE COPY",
     '    function done(){ toast(msg); buzz(); OUT.sent(id, text.length); }',
     '    OUT.sent(id, text.length);\n    function done(){ toast(msg); buzz(); }',
     "REFUSED IS NOT A COPY", "page:releve.html"),
    ("one page's fallback goes back to ignoring what execCommand returned",
     '      if(okc) done(); else toast("Select & copy manually"); }',
     '      done(); }',
     "A COPY IT REFUSES IS NOT", "page:releve.html"),
    ("a call site stops naming the export it is copying",
     'copyText($("ecoOut").textContent,"Relevé sheet copied","sheet");',
     'copyText($("ecoOut").textContent,"Relevé sheet copied");',
     "names the export it is", "page:releve.html"),
    ("the sheet declares an export no call site can make",
     '      { id:"sheet", label:"the relev\\u00e9 sheet" },',
     '      { id:"sheet", label:"the relev\\u00e9 sheet" },\n      { id:"ghost", label:"a ghost" },',
     "can actually be made", "page:releve.html"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect, where):
    tmp = tempfile.mkdtemp(prefix="mutout_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        # docs is COPIED, not linked: the component is inlined into the pages,
        # so a mutant in the module only reaches the suite by way of the
        # emitter -- which is exactly how a real edit reaches them.
        shutil.copytree(os.path.join(ROOT, "docs"), os.path.join(tmp, "docs"))
        if where == "module":
            target = os.path.join(dst, "outbox.py")
        else:
            target = os.path.join(tmp, "docs", where.split(":", 1)[1])
        body = io.open(target, encoding="utf-8").read()
        if body.count(find) != 1:
            return ("BAD MUTANT", "anchor matched %d times in %s -- the mutation never applied"
                    % (body.count(find), where))
        io.open(target, "w", encoding="utf-8", newline="\n").write(body.replace(find, repl, 1))
        if where == "module":
            e = subprocess.run([sys.executable, os.path.join(dst, "outbox_emit.py")],
                               capture_output=True, text=True, timeout=300)
            if e.returncode != 0:
                return ("BAD MUTANT", "the emitter refused the mutated module: %s"
                        % (e.stdout + e.stderr).strip()[-70:])
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_outbox.py")],
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
        for i, (n, _, _, e, w) in enumerate(MUTANTS):
            print("  %2d %-9s %-72s killed by  %s" % (i, w, n[:72], e))
        return 0
    todo = MUTANTS if a.only is None else [MUTANTS[a.only]]
    print("mutation testing the outbox against verify_outbox -- %d mutant(s), "
          "%d known equivalent\n" % (len(todo), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect, where in todo:
        verdict, detail = run_one(find, repl, expect, where)
        print("  %-9s %-74s %s" % (verdict, name[:74], detail[:50]))
        sys.stdout.flush()
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    if a.only is None:
        sys.path.insert(0, TOOLS)
        import mutant_ledger
        mutant_ledger.record("mutate_outbox", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent%s"
          % (len(todo) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT),
             " (recorded)" if a.only is None else ""))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
