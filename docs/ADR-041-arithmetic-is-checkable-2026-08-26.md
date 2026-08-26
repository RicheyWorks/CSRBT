# ADR-041: Thirteen of the forty claims were arithmetic, so they were settleable

**Status:** Accepted and implemented — `tools/verify/verify_claims_math.py` (37 checks), one arithmetic error corrected, five derivations made visible, `--full` added to the claims finder.
**Date:** 2026-08-26
**Deciders:** Richmond
**Supersedes:** nothing. **Touches:** `docs/soil-bench.html`, `docs/stand-sheet.html`, `docs/releve.html`, `docs/micro-bench.html`, `tools/audit_claims.py`

---

## Context

ADR-040 ended on a rule: *an unexamined backlog of findings is a claim you have stopped checking.*
`audit_frontend`'s backlog turned out to be entirely noise. The kit had a second one — **40 numeric
claims on the `audit_claims` worklist, across 20 of 37 pages** — and after ADR-040 the obvious
suspicion was that these were noise too.

They are not. They divide into three quite different piles, and the division is the useful part.

## What the forty actually were

**Thirteen are arithmetic.** A slope percentage, a binomial standard error, a Poisson coefficient of
variation, a selection intensity, a haemocytometer chamber factor, a unit conversion, a bulk-density
ratio. These do not need a citation and do not need judgement. **They can be computed.** So they were.

Twelve of the thirteen check out exactly. One does not:

> soil-bench: *"bulk density varies roughly **eight-fold** across common feedstocks — straw is around
> 60 kg/m³ and fresh manure around 600"*

600 ÷ 60 is **ten**. The page stated a ratio and then, in the same sentence, gave two numbers that
contradict it. Corrected to ten-fold with the division shown, so the reader does the check rather
than trusting the adjective.

**Six carry provenance the finder cannot recognise.** "Open Acoustic Devices state that…", "the
Fungal Diversity Survey's collection guide recommends…", Reineke's `N(QMD/25)^1.605` written without
an `=`, a chamber factor derived in words with "because". The finder's citation pattern wants
`(Author, Year)`. **These were left alone.** Widening a finder until the number goes down is the
error ADR-040 is about, and a named organisation's published guidance is a citation a reader can
follow, so the honest record is that these six are sourced and the finder is narrow. That is a note
about the finder, not a licence to change it during a slice whose count I would like to see fall.

**The rest need judgement** — a convention to label, a source to find, or a claim to withdraw. They
stay on the worklist, which is where an unresolved question belongs.

## Decision: put the derivation in the sentence

Where a number follows from arithmetic, **show the arithmetic**. Not in a `data-claim` attribute —
in the prose, where the reader gets it:

| before | after |
|---|---|
| 100% is a 45° slope | rise ÷ run × 100, so 100% = a 45° slope (tan 45° = 1) |
| slope distance overestimates by about 2% | the slope distance is √(1 + 0.20²) = 1.02 times the horizontal, so about 2% |
| the binomial error on 50 points is about 7 percentage points | the binomial standard error is √(p(1−p)/n), so at 50% cover on 50 points that is √(0.25 ÷ 50) ≈ 7 |
| thirty colonies carries a CV of about 18% | counting is Poisson, so the CV is 1 ÷ √N: thirty gives 1 ÷ √30 ≈ 18% |

This is strictly better than the attribute the finder also honours. The attribute silences the check;
the sentence answers it. **The worklist fell from 40 to 34 without a single rule being loosened** —
the six that dropped off are ones a reader can now verify unaided.

(The attribute route turns out to be unavailable anyway: `verify_claims_slice` forbids
`data-claim` on every page, from a reverted earlier attempt. A documented affordance that no page can
use is worth its own look, but it is not this slice.)

## The suite: recompute, never assert

`tools/verify/verify_claims_math.py` is deliberately **not** a table of expected constants. A test
that asserts "the page says 7" fails the moment somebody legitimately changes 50 sample points to 80,
and *an assertion that a legitimate change breaks is not a test, it is a future ignored failure* —
this kit found nine of those in one month.

Every case pulls the **inputs** out of the page and recomputes the **answer**. Both properties were
canaried:

**Nine seeded errors, nine caught** — the slope answer changed to 40°, `tan 45°` restated as 2, the
binomial error changed to 5 pp, the Poisson CV to 12%, the selection intensity to 1.900, the chamber
depth to 0.2 mm, the density ratio to 12, the tray equivalence to 400 ppm, and the whole claim
deleted from the page.

**Two legitimate edits, both stayed green** — changing the relevé sample from 50 points to 200 and
its error from 7 pp to 4, and changing the two bulk densities from 60/600 to 80/800. The numbers
moved; the arithmetic still held; the suite said nothing. That is the property the test exists to
have.

Deleting a claim is a **failure**, not a skip: each case first checks its pattern still matches the
page. A suite that goes quiet when the thing it measures disappears is measuring nothing.

## Consequences

`--full` was added to `audit_claims`: the worklist truncated every claim at 150 characters, which cut
several of them mid-number. Triage needs the sentence.

One more thing found on the way and deliberately **not** "fixed": the finder reported cp-characters
as *"the tellNo true roots"*. That is not a page defect — the label is `display:block` and renders on
its own line. It is the finder reading `textContent`, which ignores block boundaries, where a reader
sees `innerText`. Worth knowing when reading the worklist; a wrong reason to edit a page.

**The rule this leaves behind:** before arguing about a number, check whether it is the kind of number
that can be settled. A third of this backlog needed no judgement at all — only arithmetic nobody had
done.

---

## Addendum: the republish gate found a link the rail generator had eaten

soil-bench carried the one real arithmetic error, so it was republished. The publish gate refuses
until the live version has been read, and comparing the two turned up something the slice was not
looking for: **the live page links to the Soil & compost suite and the repo page does not.**

`nav.py` builds every rail from one fixed list of three references — kit hub, field card, glossary.
It has no concept of a page-specific link, so the day the rail became generated, the *"↑ Soil &
compost suite"* chip stopped existing in the repo. Four pages lost their "up one level" link that
way: soil-bench, cp-bench, breeding-bench and selection-log. The suites themselves are still
reachable from the hub, so nothing was broken enough to notice, and nothing did — for weeks, until a
byte-level comparison with the published copy forced the question.

**Generated navigation is only as good as what the generator knows about**, and it did not know about
this. `nav.py` now carries an `UP` map and renders a page's suite link above the shared references.
An entry for `cp-characters` was written and then removed: that page is a chip *in* the rail but
carries no rail of its own, so the entry could never have fired — config that cannot fire is a claim
that something is handled when it is not.

The emitter's banner was also saying "3 references" flatly, which stopped being true the moment a
page could carry a fourth. It now says what it does. A banner that misdescribes the thing it
introduces is a small lie in a place people trust.

The same read showed the published soil-bench was still serving **Field Entry Kit v1.1.1** — the
version with the unescaped `'<span>'+op.label+'</span>'` dial that ADR-031 fixed. The republish
clears that too, which is the second page found in that state since ADR-038 started measuring.
