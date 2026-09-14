# -*- coding: utf-8 -*-
"""Mutation testing for the shared entry layer, against verify_fek.

WHY THIS FILE EXISTS AT ALL (ADR-201). Every other suite in this kit has a
runner that breaks its subject on purpose and demands the suite notice. The
Field Entry Kit did not -- the one file that every data-entry page in the kit
inlines, and the one whose bugs therefore arrive nineteen times at once. That
gap was invisible until ADR-201 put a file reader and a checksum into it and
asked what would catch a checksum that was quietly wrong.

The subject is `tools/fek.py`, which is the SOURCE: verify_fek builds its
harness page from that file rather than from a page, exactly so it cannot test
a stale copy, and that is what makes mutating the source meaningful here.

    python3 tools/mutate_fek.py           # run every mutant
    python3 tools/mutate_fek.py --list    # the catalogue
"""
import argparse, io, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SUBJECT = ("fek.py",)

MUTANTS = [
    # ---- the checksum -----------------------------------------------------
    ("the checksum is not padded, so a small crc is a different string",
     '    return ("0000000" + c.toString(16)).slice(-8);',
     '    return c.toString(16);',
     "eight hex digits ALWAYS"),
    ("the table is built with the wrong polynomial",
     '      for (k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);',
     '      for (k = 0; k < 8; k++) c = (c & 1) ? (0x82F63B78 ^ (c >>> 1)) : (c >>> 1);',
     "the standard check value"),
    ("the register is not pre-loaded, so the leading bytes stop mattering",
     '    var c = 0xFFFFFFFF, i;',
     '    var c = 0, i;',
     "the standard check value"),
    ("the checksum is of the file's SIZE rather than its bytes",
     '      var bytes = new Uint8Array(rd.result);',
     '      var bytes = new Uint8Array([f.size & 255]);',
     "the checksum is of the FILE'S BYTES"),

    # ---- what the record carries ------------------------------------------
    ("the capture time is when the file was dropped, not when it was taken",
     '                      bytes: bytes.length, captured: iso(f.lastModified),',
     '                      bytes: bytes.length, captured: iso(Date.now()),',
     "the file's own timestamp"),
    ("the image itself rides in the record",
     '        return { name: p.name, bytes: p.bytes, captured: p.captured, crc: p.crc,\n'
     '                 label: p.label, note: p.note, have: true };',
     '        return { name: p.name, bytes: p.bytes, captured: p.captured, crc: p.crc,\n'
     '                 label: p.label, note: p.note, have: true,\n'
     '                 data: "data:image/jpeg;base64,AAAA" };',
     "THE RECORD IS THE REFERENCE, NOT THE IMAGE"),
    ("media() joins with a comma, which a filename may contain",
     '        }).join(" | ");',
     '        }).join(", ");',
     "THE SEPARATOR IS ' | ', NOT A COMMA"),
    ("media() drops the checksum and keeps only the name",
     '          return p.name + " (crc32 " + p.crc + (p.captured ? ", " + p.captured : "") + ")";',
     '          return p.name;',
     "Darwin Core shaped"),

    # ---- a restore cannot bring a photograph back (ADR-206) ---------------
    ("a restored sheet keeps the frames to itself, so it comes back quietly one short",
     '        renderAwait();\n        return await_.length;',
     '        await_ = [];\n        return 0;',
     "SAYS WHICH PHOTOGRAPHS IT NO LONGER HOLDS"),
    ("a frame this browser does not hold is dropped from the record, breaking the only "
     "link between a row and a file on a camera",
     '      }).concat(await_.map(function(p){',
     '      }).concat([].map(function(p){',
     "IS IN THE RECORD WHETHER OR NOT THIS BROWSER HOLDS IT"),
    ("media() forgets the frames that are not on this device",
     '        return list.concat(await_).map(function(p){',
     '        return list.map(function(p){',
     "media() names both"),
    ("a returning frame is matched by NAME, which a camera roll changes on export",
     '            if (await_[i].crc === sum && await_[i].bytes === bytes.length) {',
     '            if (await_[i].name === (f.name || "")) {',
     "MATCHED BY CHECKSUM AND NOT BY NAME"),
    ("the caption is not carried back with the frame it was written about",
     '              lab = await_[i].label || ""; note = await_[i].note || "";',
     '              lab = ""; note = "";',
     "RETURNS THE CAPTION"),
    ("a returning frame is swapped in silently, with nothing said",
     '        if (back) parts.push(back + " matched by checksum, caption restored");',
     '        if (back) parts.push("");',
     "says it matched one rather than silently swapping"),
    ("clear() leaves the awaited frames behind, so a cleared sheet keeps asking for a "
     "photograph belonging to work nobody has",
     '        list = []; await_ = []; render(); renderAwait(); say(""); changed();',
     '        list = []; render(); renderAwait(); say(""); changed();',
     "clear() forgets the awaited frames too"),
    ("adding a photograph announces nothing, so every autosave in the kit sits still "
     "while a reader photographs four stations",
     '      try { wrap.dispatchEvent(new CustomEvent("fek-change", { bubbles: true })); }',
     '      try { if (false) wrap.dispatchEvent(new CustomEvent("fek-change", { bubbles: true })); }',
     "ADDING A PHOTOGRAPH ANNOUNCES ITSELF"),

    # ---- the refusal ------------------------------------------------------
    ("a file that is not an image is added anyway",
     '      fs = fs.filter(function(f){ return /^image\\//.test(f.type || ""); });',
     '      fs = fs.slice();',
     "is not added"),
    ("the refusal is counted but not said",
     '          parts.push(notImages.length + " not an image: "\n'
     '                     + notImages.map(function(f){ return f.name; }).slice(0, 3).join(", "));',
     '          parts.push("");',
     "THE REFUSAL IS SAID AND NAMES THE FILE"),
    ("the component's message element is not a live region",
     '    shot.setAttribute("role", "status"); shot.setAttribute("aria-live", "polite");',
     '    shot.setAttribute("data-role", "status");',
     "a live region of its own"),

    # ---- the zone ---------------------------------------------------------
    ("the drop zone loses the id that is its address",
     '    zone.id = o.dropId || (o.field ? o.field + "Drop" : "");',
     '    zone.id = "";',
     "a drop zone with an ADDRESS"),
    ("set() pretends it can restore a photograph",
     '      set: function(){ return false; },',
     '      set: function(){ return true; },',
     "set() cannot put a photograph back"),
]

KNOWN_EQUIVALENT = []


def run_one(find, repl, expect):
    tmp = tempfile.mkdtemp(prefix="mutfek_")
    try:
        dst = os.path.join(tmp, "tools")
        shutil.copytree(TOOLS, dst, ignore=shutil.ignore_patterns("__pycache__", "*_evidence"))
        os.symlink(os.path.join(ROOT, "docs"), os.path.join(tmp, "docs"))
        path = None
        for cand in SUBJECT:
            p2 = os.path.join(dst, cand)
            if io.open(p2, encoding="utf-8").read().count(find) == 1:
                path = p2
                break
        if path is None:
            n = sum(io.open(os.path.join(dst, c), encoding="utf-8").read().count(find)
                    for c in SUBJECT)
            return ("BAD MUTANT",
                    "anchor matched %d times across the subject -- the mutation never applied" % n)
        src = io.open(path, encoding="utf-8").read()
        io.open(path, "w", encoding="utf-8", newline="\n").write(src.replace(find, repl, 1))
        p = subprocess.run([sys.executable, os.path.join(dst, "verify", "verify_fek.py")],
                           capture_output=True, text=True, timeout=900)
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
    a = ap.parse_args(argv)
    if a.list:
        for n, _, _, e in MUTANTS:
            print("  %-58s must be killed by  %s" % (n, e))
        return 0
    print("mutation testing the shared entry layer against verify_fek -- %d mutant(s), "
          "%d known equivalent\n" % (len(MUTANTS), len(KNOWN_EQUIVALENT)))
    survived = bad = 0
    rows = []
    for name, find, repl, expect in MUTANTS:
        verdict, detail = run_one(find, repl, expect)
        print("  %-9s %-58s %s" % (verdict, name, detail[:58]))
        rows.append({"name": name, "verdict": verdict, "detail": detail})
        survived += verdict == "SURVIVED"
        bad += verdict not in ("killed", "SURVIVED")
    sys.path.insert(0, TOOLS)
    import mutant_ledger
    mutant_ledger.record("mutate_fek", rows, KNOWN_EQUIVALENT)
    print("\n%d killed, %d survived, %d inconclusive, %d equivalent (recorded)"
          % (len(MUTANTS) - survived - bad, survived, bad, len(KNOWN_EQUIVALENT)))
    return 1 if (survived or bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
