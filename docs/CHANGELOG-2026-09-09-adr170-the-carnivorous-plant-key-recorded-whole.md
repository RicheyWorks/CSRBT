# 2026-09-09 — ADR-170: the carnivorous-plant key, recorded whole (the kit reaches 100%)

**The key's move-question was never answered — the last unentered field in the
kit. Answering it closes cp-characters to 4/4 and the kit to 521/521, 27 of 27
pages entered whole.**

## Changed — `tools/tasks/page-cp-characters-key.json`

14 → 17 steps, 19 → 22 confirmed expectations. The three existing key walks are
kept verbatim, and the never-answered `qMove` question (does the trap move?) is
answered: reset, then yes, narrowing the key to the five moving-trap genera
(Dionaea, Aldrovanda, Drosera, Pinguicula, Utricularia), held to name Dionaea.

## Numbers

    cp-characters.html    3 -> 4 of 4 fields entered    (100%)
                         19 -> 22 confirmed, 0 refuted
    the kit             520 -> 521 of 521 fields          (27/27 pages whole)

## The milestone

Every value-carrying control on every routed page of the kit has now been
entered by a task and read back against an oracle. Data-entry coverage is
complete — 27 of 27 pages whole.

## Held

- Answering only `qMove` gives every moving-trap genus a full match, so the five
  named are exactly the `moves:"y"` genera in the key's own table.
- The answer is given after every earlier key walk has been graded.
- No page was edited — a task-only slice, the twentieth page entered whole.
