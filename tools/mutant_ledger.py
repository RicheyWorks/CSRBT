# -*- coding: utf-8 -*-
"""The mutant runners' ledger (ADR-127).

Six runners break six instruments on purpose and print a verdict line --
"31 killed, 0 survived, 0 inconclusive, 4 equivalent" -- that the next
reader copies into an ADR by hand. A number a tool can compute is never
pinned as a constant (ADR-041), and a coverage claim has a ledger with a
consumer (ADR-108): this is the ledger, merged per runner, and the board
(tools/harness_board.py) and verify_board are the consumers.

    record("mutate_walk", rows, equivalent)   # from a runner's main, after its loop
"""
import io, json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "mutant_ledger.json")


def record(runner, rows, equivalent=(), path=LEDGER):
    """rows: [{"name", "verdict", "detail"}]; equivalent: [(name, why)]."""
    led = {"_comment": "Written by the mutant runners through tools/mutant_ledger.py. One entry per runner; "
                       "a run updates only its own entry and keeps the rest, each with its own at.", "runners": {}}
    if os.path.isfile(path):
        try:
            led = json.load(io.open(path, encoding="utf-8"))
        except ValueError:
            pass
    killed = sum(1 for r in rows if r["verdict"] == "killed")
    survived = sum(1 for r in rows if r["verdict"] == "SURVIVED")
    bad = sum(1 for r in rows if r["verdict"] not in ("killed", "SURVIVED"))
    led.setdefault("runners", {})[runner] = {
        "at": int(time.time()), "mutants": len(rows), "killed": killed, "survived": survived,
        "inconclusive": bad, "equivalent": len(equivalent),
        "rows": [{"name": r["name"], "verdict": r["verdict"], "detail": (r.get("detail") or "")[:80]} for r in rows],
        "equivalents": [{"name": n, "why": w} for n, w in equivalent],
    }
    json.dump(led, io.open(path, "w", encoding="utf-8"), indent=1, sort_keys=True)
    return led["runners"][runner]


def load(path=LEDGER):
    if not os.path.isfile(path):
        return {"runners": {}}
    return json.load(io.open(path, encoding="utf-8"))
