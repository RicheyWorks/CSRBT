# ADR-078: The published copy can be read

**Status:** Accepted and implemented — `tools/publish_state.py` (`--verify`, `classify`,
`entry_via`, `contains_build`, `blocking_webfont`, an `observed` map, a report that says
*how* it knows), `tools/verify/verify_publish_reach.py` (7 → 24).
**Date:** 2026-08-27
**Deciders:** Richmond
**Follows:** ADR-031, ADR-049, ADR-055, ADR-056, ADR-061, ADR-077

---

## 1. Sixty-four percent of what readers are given was in an unknown state

`publish_state.py` reports three states, and its docstring is right that **unknown** is the
truthful one for pages published before it existed: *"collapsing it into 'up to date' would be the
single most useful lie this tool could tell."*

It stood at **14 current, 6 behind, 19 unknown**. Twenty-five of thirty-nine published pages — the
URLs people are actually handed — were not known to match the repo. And the only way out of unknown
was to republish nineteen artifacts at roughly four Read calls each: a real cost, paid for a
bookkeeping gap rather than for anything a reader would notice.

It is avoidable, and ADR-055's own principle says how. *Staleness is a property of the published
copy.* A published copy can be **read**.

## 2. Containment, not equality, and not skeleton-stripping

`--verify` takes a saved copy of a live artifact and stamps it only when the copy **contains** the
current publish bytes verbatim.

Equality is unavailable — the publisher wraps the build output in a page skeleton. The obvious move
is to parse that skeleton back off, and it is the wrong one: a filter written against today's
wrapper is the same shape that produced `publish_drift`'s twenty-four false findings. Containment
needs no wrapper knowledge, cannot pass by accident at 150 KB, and fails in the harmless
direction — a publisher that rewrote one byte of content would report BEHIND rather than a false
all-clear.

The method was validated before it was trusted, against a page whose answer was already known: the
build content occurs verbatim inside the live page at offset 12,351, and 52 KB matched byte-for-byte
before the first genuine content difference. Outside the skeleton, the publisher does not transform
anything.

## 3. Two kinds of stamp, and they must never read as one

A stamp earned by publishing and a stamp earned by reading are different evidence:

| | what it asserts |
|---|---|
| `via: "publish"` | these are the bytes I handed the publisher — says nothing about what the publisher kept |
| `via: "read"` | the URL was serving these bytes at that moment — stronger about the past, stale the instant someone republishes |

Collapsing them would be the lie the file already refuses, one notch quieter. Entries written before
any of this existed read as `None`, **not** as `"publish"`: all of them were in fact taken at publish
time, but a reader cannot tell that from the file, and writing the stronger word in would assert
provenance the file does not carry. The report says so in those words — *"14 stamped before
provenance was recorded, 1 measured from the live page."*

## 4. A negative measurement is knowledge too

The first version of `--verify` recorded only matches. So after measuring three pages I could report
one, and the two I had *just measured as stale* still printed **"unknown — published state cannot be
asserted."** That is false: I had asserted it, from the URL.

Negative results are now recorded in an `observed` map — with the build sha they were compared
**against**, because that is what makes them safe. An observation is only about the build it was
taken against; the moment the repo moves, *"I read that URL and it was not serving THAT"* says
nothing about what it is serving now, and carrying the verdict forward would be a stale claim about
a live page. The rule now decays back to unknown on its own, and `classify()` exists as one function
so the decay can be **tested** rather than described.

## 5. What the reading found

Three pages measured. The interesting one is not the arithmetic:

- **`tree-proofs.html`** — unknown → **CURRENT**, measured at the URL.
- **`ecology-lab.html`** — unknown → **BEHIND**. The flagship, and the page ADR-076 and ADR-077 spent
  two slices hardening. Its published copy predates all of it.
- **`adr-031.html`** — unknown → **BEHIND**, and this is the finding worth the ADR.

Both stale copies load their webfont stylesheet **render-blocking**. The repo's own comment on the
line they are missing says what that costs: *a stylesheet request that hangs (one bar of signal)
otherwise holds the page blank indefinitely.* On a phone in a field — which is the entire premise of
this kit — those two published pages go white and stay white.

**`adr-031.html` is the page that states the constraint.** Its published copy ships in violation of
it.

`verify_offline_slice` has checked that rule for months. It checks it on the **repo**. Nothing checked
it where a reader is, and ADR-055's principle applies to rules exactly as it applies to bytes. So
`--verify` now measures the offline contract on the published bytes too, and the report says
*"BEHIND — measured at the URL: it was not serving this build, and it blocks first paint on a font
request."* Severity, measured, rather than a boolean anyone has to guess at.

## 6. A hypothesis I checked instead of reporting

Two of the first three copies were blocking, and the tempting write-up was *"the offline hardening
never reached readers."* `tree-proofs.html` is the page that says otherwise — its published copy
carries the deferred loader and its promoter. The defect is **not** systemic; those two pages are
simply old. One more read was the difference between a finding and a false pattern.

## 7. Where this leaves the pile

```
15 current, 8 behind (2 of them measured at the URL), 16 unknown, 0 unmapped
   of the current: 14 stamped before provenance was recorded, 1 measured from the live page
```

Sixteen pages remain unknown and each is now **one read** away from a verdict, with no republish
required:

```
python3 tools/publish_state.py --verify PAGE.html /path/to/saved-live-copy.html
```

**What I did not do, and why it is listed rather than quietly skipped (ADR-047):** I did not
republish the eight. Reading one 3,356-line artifact to satisfy the publish gate costs roughly 50,000
tokens per 560 lines, and eight of those would have bought less than the measurement did — the
measurement is what turns "republish everything, some of it pointlessly" into a list of eight pages
with a reason attached to each. The two measured ones now carry the strongest reason there is: a
reader on bad signal sees nothing at all.
