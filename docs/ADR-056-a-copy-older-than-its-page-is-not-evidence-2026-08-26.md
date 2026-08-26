# ADR-056 — A saved copy older than its page is not evidence

**Date:** 2026-08-26
**Status:** accepted
**Supersedes nothing. Fixes the defect ADR-055 only recorded.**

## What happened, twice

`publish_drift.py` ranks published pages by what a reader of a stale copy would
read differently. Its evidence is the newest saved copy of each artifact on
disk. It has always printed, at the bottom of every run:

> A page republished since that copy was saved will OVERSTATE its drift.

That sentence is true, it is unmissable, and it has now been walked past twice.

**First** (ADR-055): food-web, soil-bench and collection-sheet were reported to
the user as live harm — three pages each missing the same two rail links. All
three were already fixed live. The copies on disk predated the fix.

**Second** (today): `ecology-glossary` ranked as INCOMPLETE with *37 sentences
the reader never sees*. The saved copy was four days old. Fetching the live page
showed all thirty-seven already published; the only real difference was a
non-blocking webfont wrapper, which changes nothing a reader reads.

Two occurrences of the same error is not carelessness. It is a tool that ranks
evidence of unknown age beside evidence of known age and asks the reader to
remember the difference.

## The decision

**A caveat is not a classification.** The ordering that the footnote asked the
reader to keep in their head is now computed, and a copy that cannot be ordered
against its page is not ranked at all.

`published.json` entries gain the time the stamp was taken:

```json
"ecology-field-card.html": { "sha": "8bf115c5…", "at": 1787777383 }
```

The saved copy's filename already carries when it was fetched. That is enough to
decide, per page, whether the copy is still evidence:

| stamp hash == repo hash | — | **current** — repo is what was last published |
| copy fetched **after** the stamp | ordering known | **rankable** — the copy is what that URL served |
| copy fetched **before** the stamp | ordering known | **superseded** — not ranked; the difference may already be live |
| no stamp, or a stamp with no time | **no ordering** | **unordered** — reported apart from the ranked lists |

The fourth row is the one that bit both times. An unstamped page is *not*
superseded (that would hide real staleness) and *not* rankable (that is the
phantom). It is its own answer, and it prints under its own heading:

```
? UNORDERED -- these differ from their saved copy, but nothing
records whether that copy predates the live page, so the difference
is not evidence of anything. Fetch the artifact before acting:
```

A bare-string entry is the pre-ADR-056 format and reads back with `at=None`.
`None` is not zero and not now; a caller that treats it as either is asserting
an ordering the file does not record.

## Why the rule is one function

`evidence(entry, cur_sha, copy_ts)` is called once by the report and directly by
every fixture. ADR-039 keeps being the ADR that matters: when the rule was
written twice — once in the live loop, once in a fixture runner — five mutants
died with nothing noticing. Thirteen mutants were seeded against this one:
collapsing `superseded` into `rankable`, flipping the boundary to `<=`, treating
`unordered` as evidence, hiding it as superseded, inventing `0` for a missing
time. All thirteen die.

## The gap the canary found

The first eight mutants all targeted the *readers*, and the writer mutant —
deleting the timestamp from `--stamp` — **survived all twenty-one checks**.
Every entry the fixtures read was hand-built, so the code that builds real
entries was never exercised. The suite now runs the real `--stamp` path against
a throwaway state file and reads back what it actually wrote, asserting the time
lies between two clock reads bracketing the call rather than pinning a constant
(ADR-041 — an expected timestamp would fail every day after the one it was
written on).

Two of those writer mutants then *crashed* the suite rather than failing it,
masking the checks after them. Guarded. A suite that dies on a mutant reports
nothing about what follows, which is worse than the fault it was testing for.

## What this does not fix

Fifteen published pages still have no saved copy at all, and nothing can be said
about them. Seventeen carry pre-ADR-056 stamps and will read as `unordered`
until they are next published and stamped. That is the honest state, and it is
visibly different from clean — which is the whole point.

## Cost

`publish_state.py` +2 accessors, entries become objects; `publish_drift.py` +1
function, 3 call sites; `verify_publish_drift.py` 29 → 50 checks. 49/49 jobs
green, 3503 checks.
