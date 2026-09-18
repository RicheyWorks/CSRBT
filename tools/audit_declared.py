# -*- coding: utf-8 -*-
"""Is every written exemption still about anything? (ADR-224 -- ADR-218, rebuilt)

Thirty declarations stand in four of this kit's ledgers, each a sentence written
by hand about ONE thing on ONE page: this figure is right to stay on the screen,
this box is right to say nothing, this control is right not to ask. Six audits
grant them and, until ADR-224, all six applied them by filtering the finding out
of the list and writing the FILTERED list down -- so the evidence was gone at the
moment the exemption was used, and nothing could say whether a declaration still
covered a finding, covered nothing, or named a control the page no longer has.
A declaration is keyed by a label, and a label is not a durable identity.

tools/exempt.py now records, beside the filtered list, `raw` (what was flagged
before the exemption) and `seen` (everything the reading could have flagged).
This audit reads those and gives every declaration one of four verdicts:

    COVERING   the key is in raw: the audit still flags it, the exemption is doing work
    IDLE       the key is in seen and not in raw: the thing is there and clean, so the
               exemption is slack that would hide the defect coming back
    STALE      the key is in neither: nothing by that name -- the reason is about
               something that is gone, or was renamed, or never was
    UNREAD     no reading: the page has no row, the row has no universe, or the row is
               older than the rest of its own ledger, which means the audit did not
               visit that page on its last pass

Only COVERING passes. It opens no browser: the six audits do the measuring, and
run_all runs this LAST so that it judges this run's readings.

THIS AUDIT HAS NO --declare. An exemption mechanism on the audit that checks
exemptions is the same defect one level up, and the level above that has no
audit at all. It can only take a declaration AWAY, and --forget prints the
reason it removes, because a reason is the only record that a judgement was
ever made.

    python3 tools/audit_declared.py                       # the table; exits 1 if any is not covering
    python3 tools/audit_declared.py --source restored     # one source
    python3 tools/audit_declared.py --json                # every declaration, with its reason
    python3 tools/audit_declared.py --forget SOURCE:PAGE:KEY
"""
import argparse, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))

# A reading taken on the pass that wrote the ledger's newest row is within this
# many seconds of it. A full run of the six audits takes well under an hour; a
# page the audit skipped keeps a row from a week ago, and a declaration judged
# against that row is judged against nothing this run saw.
FRESH = 6 * 3600

VERDICTS = ("covering", "idle", "stale", "unread")

# Every place a declaration can live. `whole` sources declare a SUBJECT (a page,
# a pairing) rather than a key on it, and are judged by the audit's own recorded
# verdict instead of by raw/seen. `one_pass` says the ledger is rewritten whole
# by one pass of its audit, so a row older than the rest was skipped; the
# contention ledger is written by a sweep that takes readings one pairing at a
# time over days, and gets no freshness test.
SOURCES = [
    {"id": "carried", "ledger": "carried_ledger.json", "rows": "pages", "declared": "declared",
     "raw": "raw", "seen": "seen", "one_pass": True,
     "declare": "python3 tools/audit_carried.py --declare PAGE:LABEL"},
    {"id": "restored", "ledger": "restored_ledger.json", "rows": "pages", "declared": "declared",
     "raw": "raw", "seen": "seen", "one_pass": True,
     "declare": "python3 tools/audit_restored.py --declare PAGE:KEY"},
    {"id": "takeaway", "ledger": "takeaway_ledger.json", "rows": "pages", "declared": "declared",
     "raw": "raw", "seen": "seen", "one_pass": True,
     "declare": "python3 tools/audit_takeaway.py --declare PAGE:KEY"},
    {"id": "destructive", "ledger": "destructive_ledger.json", "rows": "pages", "declared": "declared",
     "raw": "raw", "seen": "seen", "one_pass": True,
     "declare": "python3 tools/audit_destructive.py --declare PAGE:KEY"},
    {"id": "badinput", "ledger": "badinput_ledger.json", "rows": "pages", "declared": "declared",
     "raw": "raw", "seen": "seen", "one_pass": True,
     "declare": "python3 tools/audit_badinput.py --declare PAGE:ID"},
    {"id": "outputs", "ledger": "outputs_ledger.json", "rows": "pages", "declared": "declared",
     "raw": "raw", "seen": "seen", "one_pass": True,
     "declare": "python3 tools/audit_outputs.py --declare PAGE:KEY"},
    {"id": "outputs-mute", "ledger": "outputs_ledger.json", "rows": "pages", "declared": "mute_declared",
     "raw": "mute_raw", "seen": "mute_seen", "one_pass": True,
     "declare": "python3 tools/audit_outputs.py --declare-mute PAGE:KEY"},
    {"id": "outputs-page", "ledger": "outputs_ledger.json", "rows": "pages", "declared": "no_outputs",
     "whole": True, "verdict": "trap", "one_pass": True,
     # a page that has grown an export is not the page the reason was about
     "stale_when": lambda row: (row.get("buttons") or 0) > 0,
     "declare": "python3 tools/audit_outputs.py --declare-page PAGE"},
    {"id": "contend", "ledger": "contention_ledger.json", "rows": "suites", "declared": "declared",
     "whole": True, "verdict": lambda row: (row.get("failed") or 0) > 0, "one_pass": False,
     "declare": "python3 tools/contend.py --declare PAIRING"},
]


def source(sid):
    for s in SOURCES:
        if s["id"] == sid:
            return s
    return None


def load(path):
    if not os.path.isfile(path):
        return None                    # A LEDGER THAT IS NOT THERE IS NOT AN EMPTY ONE
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except ValueError:
        return None


def save(path, state):
    io.open(path, "w", encoding="utf-8").write(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def newest(rows):
    """The newest `at` among a ledger's rows, whatever the ledger calls them."""
    ats = [r.get("at") for r in rows.values() if isinstance(r, dict) and isinstance(r.get("at"), (int, float))]
    return max(ats) if ats else None


def _verdict(src, row, key, top):
    """-> (verdict, why, behind)."""
    behind = None
    if row is None:
        return "unread", "no reading for this subject in %s" % src["ledger"], behind
    if src.get("one_pass") and top is not None and isinstance(row.get("at"), (int, float)):
        behind = int(top - row["at"])
        if behind > FRESH:
            return ("unread", "the reading is %d s behind the newest row of its own ledger: the "
                              "audit did not visit this subject on its last pass" % behind, behind)
    if src.get("whole"):
        stale_when = src.get("stale_when")
        if stale_when and stale_when(row):
            return ("stale", "the subject is no longer the shape the reason was about", behind)
        v = src["verdict"]
        flagged = v(row) if callable(v) else row.get(v)
        if flagged is None:
            return "unread", "the row carries no verdict to hold the declaration to", behind
        if flagged:
            return "covering", "the audit still flags it", behind
        return "idle", "the audit no longer flags it, and the exemption would hide its return", behind
    raw, seen = row.get(src["raw"]), row.get(src["seen"])
    if not isinstance(seen, list) or not isinstance(raw, list):
        return ("unread", "the row has no %s/%s record: it was written before ADR-224, or by "
                          "something that filtered quietly" % (src["raw"], src["seen"]), behind)
    if key in raw:
        return "covering", "the audit still flags it", behind
    if key in seen:
        return "idle", "the thing is there and clean, and the exemption would hide its return", behind
    return "stale", "nothing by that name was seen", behind


def judge(only=None, root=None):
    """Every declaration in every source -> [row dicts]. `only` limits to one source id."""
    root = root or HERE
    out = []
    for src in SOURCES:
        if only and src["id"] != only:
            continue
        path = os.path.join(root, src["ledger"])
        state = load(path)
        rows = (state or {}).get(src["rows"]) or {}
        top = newest(rows) if src.get("one_pass") else None
        for subject in sorted(rows):
            row = rows[subject]
            if not isinstance(row, dict):
                continue
            dec = row.get(src["declared"])
            if not dec:
                continue
            if src.get("whole"):
                pairs = [(None, dec)]
            else:
                pairs = sorted(dec.items()) if isinstance(dec, dict) else []
            for key, reason in pairs:
                v, why, behind = _verdict(src, row, key, top)
                out.append({"source": src["id"], "page": subject, "key": key, "verdict": v,
                            "why": why, "reason": reason, "behind": behind,
                            "declaredBy": src["declare"], "ledger": src["ledger"]})
        if state is None and not only:
            # named, not skipped: a source whose ledger is missing is a source
            # whose declarations cannot be judged, and a reader must be told
            out.append({"source": src["id"], "page": None, "key": None, "verdict": "unread",
                        "why": "no ledger at %s" % src["ledger"], "reason": None, "behind": None,
                        "declaredBy": src["declare"], "ledger": src["ledger"]})
    return out


def consistency(root=None):
    """The rule the six audits are held to, checked against the LIVE ledgers:
    filtered within raw within seen, and raw minus filtered exactly the declared
    keys that raw holds. -> [problem strings]."""
    root = root or HERE
    filtered_key = {"carried": "lost", "restored": "lost", "takeaway": "stranded",
                    "destructive": "bare", "badinput": "blind", "outputs": "unread",
                    "outputs-mute": "mute"}
    bad = []
    for src in SOURCES:
        fk = filtered_key.get(src["id"])
        if not fk:
            continue
        state = load(os.path.join(root, src["ledger"]))
        for page, row in sorted(((state or {}).get(src["rows"]) or {}).items()):
            if not isinstance(row, dict) or not isinstance(row.get(src["raw"]), list):
                continue
            raw, seen = row[src["raw"]], row.get(src["seen"]) or []
            filt = row.get(fk) or []
            dec = row.get(src["declared"]) or {}
            if not set(filt) <= set(raw):
                bad.append("%s %s: filtered is not within raw: %s" % (src["id"], page, sorted(set(filt) - set(raw))))
            if not set(raw) <= set(seen):
                bad.append("%s %s: raw is not within seen: %s" % (src["id"], page, sorted(set(raw) - set(seen))))
            if sorted(set(raw) - set(filt)) != sorted(k for k in raw if k in dec):
                bad.append("%s %s: raw minus filtered is not the declared keys: %s vs %s"
                           % (src["id"], page, sorted(set(raw) - set(filt)), sorted(k for k in raw if k in dec)))
    return bad


def forget(spec, root=None):
    """SOURCE:PAGE:KEY (or SOURCE:PAGE for a whole-subject source) -> (ok, message)."""
    root = root or HERE
    parts = spec.split(":", 2)
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return False, ("--forget takes SOURCE:PAGE:KEY, or SOURCE:PAGE for a whole-subject source "
                       "(a key may itself contain a colon; only the first two are split on)")
    src = source(parts[0])
    if src is None:
        return False, "no source %r; the sources are %s" % (parts[0], ", ".join(s["id"] for s in SOURCES))
    page = parts[1]
    key = parts[2] if len(parts) > 2 else None
    if src.get("whole") and key is not None:
        return False, "%s declares a whole subject: --forget %s:%s" % (src["id"], src["id"], page)
    if not src.get("whole") and key is None:
        return False, "%s declares a key on a subject: --forget %s:%s:KEY" % (src["id"], src["id"], page)
    path = os.path.join(root, src["ledger"])
    state = load(path)
    row = ((state or {}).get(src["rows"]) or {}).get(page)
    if not isinstance(row, dict):
        return False, "%s has no row for %r; nothing to forget" % (src["ledger"], page)
    if src.get("whole"):
        reason = row.get(src["declared"])
        if not reason:
            return False, "%s is not declared in %s; nothing to forget" % (page, src["id"])
        del row[src["declared"]]
    else:
        dec = row.get(src["declared"]) or {}
        if key not in dec:
            return False, "%s:%s is not declared in %s; nothing to forget" % (page, key, src["id"])
        reason = dec.pop(key)
        if not dec:
            del row[src["declared"]]          # the last one removed takes the empty block with it
    save(path, state)
    return True, "forgot %s: %s -- the reason it carried was: %s" % (spec, "declared" if src.get("whole")
                                                                    else key, reason)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="one source id")
    ap.add_argument("--json", action="store_true", help="every declaration with its verdict and reason")
    ap.add_argument("--forget", metavar="SOURCE:PAGE:KEY", help="remove one declaration, printing its reason")
    ap.add_argument("--check", action="store_true",
                    help="accepted for symmetry with the kit's other audits; a declaration that is "
                         "not covering fails with or without it")
    a = ap.parse_args(argv)
    if a.source and source(a.source) is None:
        print("no source %r; the sources are %s" % (a.source, ", ".join(s["id"] for s in SOURCES)))
        return 2
    if a.forget:
        ok, msg = forget(a.forget)
        print(msg)
        return 0 if ok else 2
    rows = judge(a.source)
    if a.json:
        print(json.dumps(rows, indent=1, sort_keys=True))
        return 0 if all(r["verdict"] == "covering" for r in rows) else 1
    print("%-13s %-26s %-28s %-9s %s" % ("SOURCE", "PAGE", "KEY", "VERDICT", "why"))
    print("-" * 118)
    for r in rows:
        print("%-13s %-26s %-28s %-9s %s" % (r["source"], (r["page"] or "-")[:26], (r["key"] or "-")[:28],
                                             r["verdict"].upper(), r["why"][:60]))
    print("-" * 118)
    n = dict((v, sum(1 for r in rows if r["verdict"] == v)) for v in VERDICTS)
    failing = [r for r in rows if r["verdict"] != "covering"]
    for r in failing:
        if r["page"] is None:
            continue
        spec = "%s:%s" % (r["source"], r["page"]) + ("" if r["key"] is None else ":%s" % r["key"])
        print("    python3 tools/audit_declared.py --forget %s   # %s: %s"
              % (spec, r["verdict"].upper(), (r["reason"] or "")[:50]))
    if failing:
        print("\nA STALE declaration names nothing: forget it. An IDLE one is slack: fix the thing it "
              "excused for good and forget it, or\nleave it and know the defect can come back "
              "unseen. An UNREAD one has no reading to be judged by: run its audit.")
    print("%d declaration(s): %d covering, %d idle, %d stale, %d unread"
          % (len(rows), n["covering"], n["idle"], n["stale"], n["unread"]))
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
