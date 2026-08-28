# ADR-085 — the date of a copy is not the date of its file

*2026-08-28. Status: accepted. Corrects the dating rule assumed by
[ADR-056](ADR-056-a-copy-older-than-its-page-is-not-evidence-2026-08-26.md) and narrows the carve-out
made by [ADR-084](ADR-084-the-guard-in-front-of-its-own-evidence-2026-08-28.md).*

## 1. Closing the pile, and what closing it exposed

The three remaining BEHIND pages are republished and stamped. Each was measured at its URL before the
republish, so for the first time the BEHIND count was observed rather than inferred, and each diff was
exactly what ADR-080 predicted:

| page | diff, measured against the live bytes |
|---|---|
| `deployment-log` | 2 rail links missing — Soil Recipes, Greenhouse |
| `ordination` | the same 2 rail links |
| `stand-sheet` | one double-escape removed: `esc(t.dir)` → `t.dir` |

Seven diff lines each, nothing else. **39 current, 0 behind, 0 unknown, 0 unmapped** — the first clean
board. All three needed the gate forced: I had read each live copy and diffed it line by line before
publishing, and in all three the only difference was content the repo adds.

Then, checking my own work, I ran `--verify` with the wrong page name against a real copy.

## 2. Two arguments that had to agree, and nothing making them agree

```
$ publish_state.py --verify food-web.html <a copy of deployment-log>
food-web.html    BEHIND, measured: the copy does not carry the current publish bytes
```

`food-web` was current. The tool wrote that verdict into `state["observed"]` with `via: "read"` — the
strongest provenance word the file has — together with an offline-contract verdict about `food-web`
derived from another page's bytes. That is exactly ADR-078's rule (*an observation is only about the
thing it was taken against*) broken by the interface that records the observation.

`copy_is_of` now answers it, with two independent attributors because one that can only say yes is not
a check: the saved copy's filename carries its artifact id, and every page in the kit has exactly one
`<title>` — measured, all 39 distinct, no page with none or two. Either may stay silent; **either may
refuse, and one refusal refuses.** If both stay silent the answer is still no (ADR-061): nothing ties
the copy to the page, and a silent pass is how the interface got here. The title must be the title
*element*, not the string appearing anywhere, or a hub page quoting a title in a card would be
attributed to the page it links to — that one is checked.

## 3. The number underneath all of it was wrong

Chasing the first bug produced a second. `--verify` dated a copy with `os.path.getmtime`. mtime is a
property of the local file: anything that rewrites the cache — a re-read, a copy, a sync — moves it
forward without a byte of the page changing.

Measured across **103 saved copies**: every mtime was later than the version the copy carries. Never
once equal. The gaps ran from 3 seconds to **267,969 seconds — 3.1 days.**

So every date this file ever wrote for a `via: "read"` entry was overstated — all nine of them, and
always in the direction ADR-056 exists to refuse, an old copy looking newer than it is:

```
greenhouse.html         1787879059 -> 1787710960   overstated by 168099 s
tree-visualizer.html    1787878102 -> 1787633327   overstated by 244775 s
```

The honest date was inside the bytes the whole time. A published artifact carries
`<base href="/_f/<epoch>-<hash>/">`, and that epoch is when *this version* was published — which is
the number the ordering question actually needs, since a copy of the version published at V cannot be
evidence about anything published after V, whenever it was fetched. `copy_taken_at` takes it from the
bytes, falls back to the filename, and reaches mtime only as a last resort **with a label saying it is
not the version** — a date whose provenance goes unstated is how the nine got written. Every entry now
carries `dated_by`. The nine were re-derived.

None of the nine verdicts was wrong: containment is a fact about bytes and does not depend on the date.
The date decides ordering, and ordering had exactly one place left where a wrong answer could do harm.

## 4. Which was the place ADR-084 had just opened

ADR-084 carved observations out of the ordering guard, reasoning that they never touch
`state["pages"]`. The reasoning was right. The carve-out was still too wide, because the date feeding
it was always overstated: a copy of a two-day-old version, re-cached a minute ago, recorded
*behind, measured, via read* about a page republished in between. ADR-055's harm, with the strongest
provenance word in the file attached.

A BEHIND observation is a claim about the page **now**. A copy older than the last publish cannot make
it. Running the corrected tool over the ten pre-provenance pages, eight were correctly suppressed —
and **the remaining two recorded the false claim anyway**, because they have no date at all and
`stamp_allowed` returns true for an undated stamp. That is right for stamping: an undated stamp is the
weakest entry the file holds and a dated read beats it. It is wrong for observing: with no time to
order against, the honest answer is *cannot be known*, not *the copy wins*.

Two questions, so two rules. `observation_allowed` is stated separately, and the suite checks them
against each other on the case where they differ:

```
PASS  against an UNDATED stamp, a copy cannot be ordered -- and so may NOT observe
PASS  ...which is the exact case where it MAY stamp -- the two rules differ here
```

`verify_publish_reach` 31 → **54 checks**, each new rule with a control that fails if the function
becomes a constant — stated as *"it both accepts and refuses"* rather than as a pinned count, because
the pinned count was wrong on the first try and ADR-041 already named that mistake.

## 5. What is and is not now known

ADR-084 predicted the ten pre-provenance pages verify CURRENT. **That prediction is still untested.**
The ten runs above used cached copies of versions days old; every one failed containment, and every one
was correctly refused as evidence. A refusal is not a result. Testing the prediction needs ten live
reads and has not been done — recording it as "ten measured BEHIND" would be precisely the
copy-older-than-its-page error this record is about, committed while writing it up.

One thing those runs did show, and it is worth its own look rather than a claim here: six of the ten
cached copies carry a **blocking** webfont link. That is a statement about versions from three days
ago, and ADR-082 already found and fixed that fault across a batch — the live pages may well be fine.
It is a lead, not a finding.

**The next prediction, and its falsifier.** With the pile clean, the number that matters is the
evidence under it: 9 measured from the live page, 20 stamped at publish time, 10 with no provenance at
all. Reading those ten live should move them to measured-CURRENT. **Falsifier: any of them coming back
BEHIND at its URL** — and now, for the first time, a BEHIND that comes back will be one the tool was
entitled to record.
