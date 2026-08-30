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


def _label(rec):
    lab = (rec.get("label") or rec.get("id") or "?") if isinstance(rec, dict) else str(rec)
    return " ".join(str(lab).split())[:60]


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
                sigs["%s | spill%spx | %s" % (page, m.group(1), " ".join(m.group(2).split())[:60])] += 1
                continue
            m = JUNK.match(e)
            if m:
                sigs["%s | junk | %s" % (page, " ".join(m.group(1).split())[:60])] += 1
                continue
            m = PANES.match(e)
            if m:
                sigs["%s | panes%s | %s" % (page, m.group(1), " ".join(m.group(2).split())[:60])] += 1
                continue
            sigs["%s | other | %s" % (page, " ".join(e.split())[:60])] += 1
    return sigs


def diff(baseline, current):
    """(new, fixed) -- signatures that appeared, and accepted ones that are gone.

    Both directions matter. A new finding is a regression. A baseline entry that
    no longer occurs is debt that was PAID and never written off, and leaving it
    there means the next person reads a longer defect list than the kit has --
    the same rot tools/mutate.py flags in a stale fixture-builder marker.
    """
    new, fixed = [], []
    for sig, n in sorted(current.items()):
        was = baseline.get(sig, 0)
        if n > was:
            new.append("%s   (%d, accepted %d)" % (sig, n, was) if was else sig)
    for sig, n in sorted(baseline.items()):
        have = current.get(sig, 0)
        if have < n:
            fixed.append("%s   (accepted %d, now %d)" % (sig, n, have))
    return new, fixed
