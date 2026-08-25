# ADR-037: A road to the deposit

**Status:** Accepted and implemented — `tools/dwc.py` v1.3.0 (`parentEventID`), the join wired into three sheets and the Survey Design page, `verify_dwc.py` at 138 checks, canaried against four seeded faults.
**Date:** 2026-08-25
**Deciders:** Richmond
**Supersedes:** nothing. **Extends:** ADR-032 (Simple DwC), ADR-036 (Event Core). **Touches:** the three occurrence sheets, `docs/survey-design.html`

---

## Context

ADR-036 built an Event Core deposit: a sampling hierarchy, the Humboldt declaration, and absences a reader
can interpret. It shipped complete and it shipped **unreachable**.

The three sheets that actually record occurrences — Relevé, Stand Sheet, Collection Sheet — each mint their
own `eventID` (`releve:P1:2026-06-14`, `stand:TAH-04:…`, `foray:…`) and had no term for saying which survey
that event sat inside. So a student could design a survey on one page and fill sheets on three others, and
the four outputs would sit beside each other with no edge between them. The destination existed; there was
no road to it.

## Decision

**`dwc:parentEventID`, in the shared emitter, wired at both ends.**

The sheets keep minting their own identifiers. That is correct: a relevé *is* a sampling event and deserves
one. What a parent adds is the edge — which is exactly what `parentEventID` is for. Supplying one renames
nothing; it says which design this sits inside.

At the design end, every node in the hierarchy grows a **copy ID** button. Nobody transcribes an identifier
correctly twice, and a mistyped `parentEventID` is a dangling reference that looks like data.

### Three refusals, because an edge can be wrong in three ways

- **A list where one identifier belongs.** Whitespace or a comma in the field is refused, naming the
  consequence: a dangling reference no reader can resolve.
- **An event as its own parent.** The sheet already knows its own `eventID`; offering it as the parent is a
  cycle, and the page says where the real parent lives — the plot or visit above it.
- **An invented parent.** Blank means blank. The export writes an empty `parentEventID` and never guesses,
  because a wrong edge is worse than no edge.

The confirmation also carries the warning that matters at deposit time: a `parentEventID` pointing at an
event nobody has is *worse* than none, because the reader knows a parent existed and cannot find it.
Deposit the sheets alongside the survey's Event Core and Humboldt tables or not at all.

## What the verification found

The self-parent check failed on the Collection Sheet for a reason that turned out to be the better bug.
Its minted identifier for a site called *Bear Cr.* was `foray:Bear Cr.:2026-06-14` — **an eventID with a
space in it.**

That is legal Darwin Core, which is why nothing had caught it. It is also an identifier that breaks naive
splitting, will not survive a URL, and is the kind of thing that silently halves a column three tools
downstream. All three sheets were minting them from free-text names.

The fix went into the identifier rather than the test: whitespace is squeezed to a hyphen at the point the
`eventID` is built. The name the user typed is preserved in `locality` and the verbatim fields, where it
belongs; the identifier is made safe. A check now asserts no minted `eventID` contains whitespace.

Extracting `eventIdOf()` into one function per sheet was part of the same change — the identifier rule had
been inline in the row builder, and the parent check needed it too. Two copies of an identifier rule is how
they drift apart.

## Consequences

- The kit now produces a deposit end to end: design the survey, fill the sheets, and the rows join.
- `parentEventID` sits immediately after `eventID` in the term list, where a reader expects it.
- Minted identifiers are safe to put in a URL or split on whitespace.
