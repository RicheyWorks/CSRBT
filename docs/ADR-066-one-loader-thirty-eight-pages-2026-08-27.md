# ADR-066 — One loader, thirty-eight pages

**Date:** 2026-08-27
**Status:** accepted
**Extends:** ADR-061 (the excluded audits), ADR-062 (the fixture predicate)

## The mutant

ADR-065 left this open: a `neg-guard` survivor on `cp-characters` line 14, in
the shared webfont loader.

```js
var l = document.querySelector('link[data-webfont]'); if(!l) return;
```

Turned into `if(l) return`, the loader stops before flipping `media` from
`"print"` back to `"all"`. **The page renders in fallback fonts, forever,
silently.** The snippet is on 38 of 39 pages.

I expected to find nothing testing it. That was wrong twice over, and both
mistakes are more useful than the guess would have been.

## Wrong once: it is tested

`verify_offline_slice` routes `fonts.googleapis.com` to a fulfilled 200, loads a
page, and asserts both that the link is promoted to `media="all"` **and** that
the stylesheet then applies. That is a good test and it was already there.

## Wrong twice: the sweep could not reach it

`suites_for()` keeps the suites whose source *names* the page.
`verify_offline_slice` globs `docs/*.html` and names none — the exact ADR-061
defect, in a `verify_*` suite rather than an audit. Cross-cutting suites are now
run as a **last resort**, only on a mutant still alive after its named suites
and the mapped audits. They are the slowest thing in the sweep and the rarest to
fire, so paying for them only when the alternative is a false survivor is the
right trade: seventeen seconds of CPU against a human triaging a non-bug.

Deriving that set turned up ADR-062's fixture predicate again, and this time it
was **not** harmless. `"tempfile" and ("shutil" or "mkdtemp")` drops
`verify_offline_slice`, which writes one fixture file. Measured across the four
suites that touch tempfile, **`shutil` is the discriminating signal**: it marks
the two that copy a whole scratch tree to test tooling (`verify_emitters`,
`verify_audit_frontend`) and not the two that write a fixture file and otherwise
assert about the real kit (`verify_offline_slice`, `verify_claims_triage`). The
cross-cutting bucket uses the sharper test; `suites_for` is left alone, because
ADR-062 measured that its remaining exclusion costs nothing.

## And it still did not die

With the suite finally reachable, the seeded mutant on `cp-characters` produced
**166 of 166 passing**.

Section 1 reads every page's link *attributes*. Section 2 exercises the loader's
*behaviour* — on `BIG`, the single largest page. So the behaviour was verified
once and generalised to thirty-eight pages by assumption. A mutation to any
other page's snippet body was invisible.

The snippets *are* byte-identical — but nothing said so, and an untested
assumption is what the whole sweep exists to find. Section 1b now extracts the
loader from every page that carries one and asserts they are the same bytes,
plus that the page section 2 exercises is one of them. That is what turns one
behavioural test into honest coverage for all of them rather than a sample
presented as a rule.

Seeded on `cp-characters`, the suite now fails and names the page:

```
FAIL: every page's webfont loader is byte-identical
      (2 distinct: [['adr-031.html', ...], ['cp-characters.html']])
```

`tree-visualizer` is the one page without a loader, and correctly so — checked,
not assumed: it uses system font stacks and links no webfont at all.

## One parked, honestly

`num-shift` on `from 0.2 to 5 mm` — an uncited size range for *Utricularia*
bladders. Shifting it is a wrong fact and nothing catches it. It is recorded as
**OPEN, not equivalent**: the fix is a source, which is `audit_claims`' job, not
a pinned constant in a suite (ADR-041). Parked so it stops crowding the fresh
list while it waits.

## Cost

`verify_offline_slice` 166 → 207 checks; `mutate.py` gains the cross-cutting
last-resort pass and one parked entry. No page changed. 52/52 jobs green,
3789 checks. cp-characters 50% → 75%.

**Swept: 16 pages. 23 to go.**
