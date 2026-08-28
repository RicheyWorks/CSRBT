# ADR-094 — a worklist with a front

*2026-08-28. Status: accepted. Triages the `audit_claims` list; a third instance of the coupling in
[ADR-077](ADR-077-a-rule-a-sentence-about-the-rule-can-break-2026-08-27.md), committed twice in one
hour.*

## 1. Thirty claims, and no way to tell which mattered

The claims worklist has sat near thirty for several slices. Measuring why: **27 of the flagged claims
have provenance somewhere in their own section.** `micro-bench` states the 30–300 countable window in
one paragraph and names FDA BAM, AOAC, USP and ASTM three paragraphs down, in the same card, and says
which one it applies and why. The finder looks at the block, so it reports the sentence and never sees
the card.

It would be easy, and wrong, to widen the test to the section. One citation would then cover every
number under the same heading — including `micro-bench`'s *"0.1 mL spread, 1.0 mL pour"*, which sits in
that same card and comes from none of the four standards named in it. A section-level pass is a silent
exclusion with a plausible face (ADR-061).

**So the test did not move; the report gained a column.**

```
claims to triage: 28 -- 12 BARE (no provenance anywhere in the claim's section)
                        and 16 near (some in the section, so likely covered)
`near` is an ordering hint, NOT an exemption.
```

The list has a front for the first time: twelve claims with nothing anywhere near them.

## 2. Two off it

The two hub cards on `ecology.html` restated figures their tool pages source properly, and a reader who
never clicks through saw a bare number. Both now carry the source in the card: **40 CFR 503 App. B**
for the compost windows, **California Carnivores** for the 160 ppm TDS guidance. 30 → 28, 14 BARE → 12.

## 3. A documented escape nobody is allowed to use

The obvious fix for the third — `ecology-lab`'s heredity reading, whose figures are interpolated from
the session and bound to the engine by `verify_engine_sessions` — is the `data-claim="derived"` marker
the finder's own docstring documents.

`verify_claims_slice` forbids that attribute in `docs/` outright. It was a reverted attempt, and the
suite exists to check the revert held. So the finder documents an escape that no page may take, and it
took writing one to find that out.

The branch stays — removing it would make the two files disagree about their own history — but the
docstring now says the branch is dead and which suite kills it. **A documented mechanism nobody may use
is exactly the silent kind of wrong.** The heredity line stays BARE on the list, correctly: the finder
cannot see a binding that lives in a Python suite, and pretending otherwise would be worse than the
entry.

## 4. The same coupling, twice, in one hour

Three suites read a probe out of a tool by splitting the file on one literal sequence — the letters
P-R-O-B-E followed by a raw-string opener. I added a second constant whose name **ended with that
sequence**, and the split silently handed both readers the wrong body:

```
Page.evaluate: TypeError: Cannot read properties of null (reading 'map')
```

Renaming it fixed that. Then the comment I wrote to warn about it **quoted the sequence verbatim**, and
broke the split again — the same failure, from the explanation of the failure. That is ADR-077 exactly:
a sentence about the rule can break the rule. The paragraph now describes the marker without containing
it.

`verify_claims_slice` gained the check that makes it noticeable rather than memorable — every tool read
this way must carry the marker exactly once — with a seeded canary:

```
FAIL: audit_claims.py carries the extraction marker exactly once (found 2)
```

This is the second slice running in which a fragile textual coupling to `tools/audit_*.py` cost real
time; ADR-092's was a filename, this one is a constant name and then a comment. The coupling itself is
the defect, and a suite that reads a module could import it instead of splitting it. **Not done here,
and named as not done**: it touches three suites and two tools, and the check above makes the current
arrangement fail loudly, which is enough to stop it recurring while it waits.

**The next prediction, and its falsifier.** Twelve BARE claims are the real list. I expect most to
resolve the way the first two did — a source that exists on another page, or a convention that only
needs labelling — rather than as errors. **Falsifier: one of the twelve turning out to be wrong rather
than merely unsourced**, which would say the finder has been measuring the wrong property all along.
