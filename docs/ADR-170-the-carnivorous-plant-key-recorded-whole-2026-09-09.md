# ADR-170 — The carnivorous-plant key, recorded whole — and with it the entire kit

**Status:** accepted · **Date:** 2026-09-09 · **The key had a question no one ever answered: whether the trap moves. Answering it closes the last unentered field in the kit — 521 of 521 value-carrying fields, 27 of 27 pages entered whole.**

## The branch never taken

`cp-characters.html` is the 18-genus dichotomous key that narrows a carnivorous
plant by trap type, habit, region and whether the trap **moves**. Its task
walked the key three ways — a snap trap to Aldrovanda/Dionaea, bladders under
water, a North American pitcher — but **one answer was never given**: the
`qMove` question, *does the trap move?*, both of whose options sat untouched.
It was the **last unentered field in the kit**. A key with a question no one
ever answers is a branch of the identification never taken.

## Answered, and the kit made whole

The existing scenario is kept verbatim — the three walks and their results all
hold — and the missing answer is given: the key is reset and asked whether the
trap moves. **Yes**, and it narrows to the **five genera** whose traps bend,
roll or snap — Dionaea, Aldrovanda, Drosera, Pinguicula, Utricularia — the
result held to name Dionaea among them. Answering only `qMove` gives every
moving-trap genus a full one-of-one match, so the five are exactly the genera
with `moves:"y"` in the key's own table, a categorical fact read off the data
rather than a number typed by hand.

## What moved — and what it completes

    cp-characters   3 → 4 of 4 fields entered      (the last unentered field
                                                    in the kit)
    cp-characters  19 → 22 confirmed expectations     0 refuted
    the kit        520 → 521 of 521 fields            27 of 27 pages whole

Every control that carries a value on every routed page of the kit has now had
a value put into it by a task and read back against an oracle. The data-entry
coverage the standing program set out to reach — that the harness can enter all
the data, everywhere, especially in the science pages — is **complete**.

## Held

Answering only `qMove` gives every moving-trap genus a full one-of-one match,
so the five named are exactly the `moves:"y"` genera; the answer is given after
every earlier walk has been graded. No page was edited: a task-only slice, the
twentieth page driven end to end and the last one the kit was missing.
