# -*- coding: utf-8 -*-
"""Stable signatures for what the harness found, so a finding can be tracked.

A harness that reports is not a harness that guards. tools/harness.py has been
finding real defects for weeks -- controls wired to nothing, actions that raise,
rows spilling out of a phone -- and printing them into a run nobody's build
depended on. The suite was green throughout, because nothing converted a finding
into a failure.

The obstacle to guarding was never willingness; it was IDENTITY. To say "this is
a new defect" you must be able to say which defects you already had, and the
harness's own ids (action_btn:14) renumber the moment a page changes. So a
finding is signed by what a person would recognise it by:

    page | category | label

Categories are the harness's own buckets and invariant names: dead, failed,
spill, junk, panes. The label is the control's visible text, which is what
survives a renumber and what a maintainer actually searches for.

Duplicates are kept and counted, because eight identical `remove` buttons each
spilling nine pixels is a different fact from one, and collapsing them would let
seven regressions hide behind one baseline entry.
"""
import collections, re

CATS = ("dead", "failed")
SPILL = re.compile(r"^spills (\d+)px sideways \[[a-z_]+:\d+ (.*?)\]", re.S)
JUNK = re.compile(r"^junk rendered \[[a-z_]+:\d+ (.*?)\]")
PANES = re.compile(r"^(\d+) panes visible \[[a-z_]+:\d+ (.*?)\]")


# A LABEL HAS TO SURVIVE THE NEXT RUN (ADR-110)
#
# The first version took the control's visible text verbatim. That is stable for
# a button reading "Undo" and useless for a row generated at run time, whose text
# carries an id like "harness-373:plot:01". Every run minted new signatures, every
# one of them read as a regression, and the ratchet would have cried wolf until
# nobody looked at it -- the exact failure a defect register dies of.
#
# So generated ids and row numbers are collapsed. What is left is the FAMILY of
# finding: "the plot rows spill", not "plot row 03 spills". That is also the more
# truthful description -- survey-design has one defect that shows on every row,
# not twenty-three defects.
GENERATED = re.compile(r"harness-\d+[:\w]*|\b\d{2,}\b|\b\d+\b(?=\s*[·:])")


def _norm(text):
    """The same normalisation for a label read off a record and one parsed out of
    an error string. The first version applied it only to records, so every spill
    -- which is reported as an error -- kept its generated row id and minted a new
    signature every run."""
    t = GENERATED.sub("#", " ".join(str(text).split()))
    return re.sub(r"#(\s*#)+", "#", t)[:60]


def _label(rec):
    lab = (rec.get("label") or rec.get("id") or "?") if isinstance(rec, dict) else str(rec)
    return _norm(lab)


def signatures(ledger):
    """Counter of 'page | category | label' -> how many times it occurs."""
    sigs = collections.Counter()
    for p in ledger.get("pages", []):
        page = p.get("page", "?")
        for cat in CATS:
            for rec in p.get(cat, []):
                sigs["%s | %s | %s" % (page, cat, _label(rec))] += 1
        for e in p.get("errors", []):
            m = SPILL.match(e)
            if m:
                sigs["%s | spill%spx | %s" % (page, m.group(1), _norm(m.group(2)))] += 1
                continue
            m = JUNK.match(e)
            if m:
                sigs["%s | junk | %s" % (page, _norm(m.group(1)))] += 1
                continue
            m = PANES.match(e)
            if m:
                sigs["%s | panes%s | %s" % (page, m.group(1), _norm(m.group(2)))] += 1
                continue
            sigs["%s | other | %s" % (page, _norm(e))] += 1
    return sigs


def diff(baseline, current):
    """(new, fixed) -- signatures that appeared, and accepted ones that are gone.

    Both directions matter. A new finding is a regression. A baseline entry that
    no longer occurs is debt that was PAID and never written off, and leaving it
    there means the next person reads a longer defect list than the kit has --
    the same rot tools/mutate.py flags in a stale fixture-builder marker.

    COUNTS ARE RECORDED BUT NOT COMPARED. How many rows a walk creates before it
    reaches a spilling one is a property of the WALK, not of the kit: adding the
    second-chance retry (ADR-110) moved one signature from seven occurrences to
    nine without a line of page code changing. A count that moves when the harness
    changes is not evidence about the pages, and a ratchet built on it fires on
    its own maintenance. The set of distinct signatures is the evidence, and after
    label normalisation a family of identical row spills is one signature, which
    is what it actually is.
    """
    new = [sig for sig in sorted(current) if sig not in baseline]
    fixed = ["%s   (accepted %d, now gone)" % (sig, n)
             for sig, n in sorted(baseline.items()) if sig not in current]
    return new, fixed
