# -*- coding: utf-8 -*-
"""The only place an exemption is granted, and it records what it took out.

(ADR-224; the rebuild of ADR-218, whose paragraph reached origin and whose code
never did.)

Six audits in this kit let a finding be DECLARED: a figure the reader cannot
take away (carried), a box that says nothing about a rejected keystroke
(badinput), a reading that differs after a reload (restored), a control whose
only channel a published page refuses (takeaway), a bulk remover that does not
ask (destructive), a button that hands nothing over or a page that has no
outputs at all (outputs). Each declaration stores a sentence written by hand
about ONE thing on ONE page, and the sentence is the whole point: it is the
difference between a defect and a property of the data.

All six applied the exemption the same way -- filter the finding out of the
list, write the FILTERED list to the ledger -- so the evidence was discarded at
the moment the exemption was applied, and nothing in the kit could then tell a
declaration covering a real finding from one naming a control the page no
longer has. A declaration is keyed by a LABEL, and a label is not a durable
identity: delete the control and the exemption stays; add a control that takes
the same label and the exemption is waiting for it, carrying a reason written
about something else. An exemption that outlives its subject does not fail
loudly. It sits there being green.

So the exemption is applied HERE, once, and applying it records two things
beside the filtered list:

    raw    what was flagged BEFORE the exemption -- the evidence
    seen   everything the reading COULD have flagged -- the universe

`seen` is the half that is easy to leave out and cannot be: without it, "this
finding is covered now" and "this thing is gone" are the same absence, and they
need different fixes. tools/audit_declared.py reads both and gives every
declaration a verdict. A seventh audit that copies this rule copies both halves
or neither, because there is one call and it does both.
"""


def declared_of(state, page, which="declared"):
    """The declarations a ledger holds for one page, as a fresh dict."""
    return dict(((state.get("pages") or {}).get(page) or {}).get(which) or {})


def declare(state, page, key, reason, which="declared"):
    """Grant one exemption. A blank reason is refused: a list of things an audit
    is choosing not to care about is only useful if every line says why."""
    if not (reason or "").strip():
        raise ValueError("a declaration needs a reason")
    (state.setdefault("pages", {}).setdefault(page, {})
     .setdefault(which, {}))[key] = reason.strip()
    return reason.strip()


def apply(entry, flagged, declared, seen, raw="raw", universe="seen"):
    """FILTER AND RECORD IN ONE CALL. -> the flagged keys that are not declared.

    `entry` is the page's ledger row; `flagged` is what the reading found;
    `declared` maps keys to reasons; `seen` is every key the reading could have
    found. The row gets copies of `flagged` and `seen` under `raw` and
    `universe` -- copies, because a row holding the audit's own live list would
    be rewritten by whatever the audit did to that list next. An audit with two
    ratchets on one row names two raw keys and keeps two records."""
    flagged = list(flagged)
    entry[raw] = list(flagged)
    entry[universe] = sorted(set(str(k) for k in seen) | set(str(k) for k in flagged))
    return [k for k in flagged if k not in declared]
