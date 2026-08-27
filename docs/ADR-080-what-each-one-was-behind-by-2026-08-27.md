# ADR-080: What each one was behind by

**Status:** Accepted and implemented — `docs/food-web.html` and `docs/ecology-field-guide.html`
republished and stamped; `tools/publish_state.py` (the BEHIND message no longer compares two
incomparable sizes).
**Date:** 2026-08-27
**Deciders:** Richmond
**Follows:** ADR-055, ADR-078, ADR-079

---

## 1. BEHIND is a boolean, and boolean was never the useful part

ADR-079 left six pages measurably behind and no reason to prefer any one of them. Republishing costs a
full-line read of the live artifact — 583 to 2,769 lines each — so "republish all six" is a real budget
spent in the dark. Each of the six was read and **diffed** first, which turns one list into five kinds
of thing:

| page | behind by | what a reader gets |
|---|---|---|
| **food-web** | the ten-percent rule stated as a constant | **wrong science** — republished |
| cell-bench | 2 missing rail links | Soil Recipes and Greenhouse unreachable |
| ordination | 2 missing rail links | same |
| deployment-log | 2 missing rail links | same |
| soil-recipes | 1 missing rail link | Greenhouse unreachable |
| stand-sheet | a double-escape removed (`esc(t.dir)` → `t.dir`) | **nothing** — see §3 |

**food-web was the one worth the reads.** Its published copy still told a student that *"energy loss
(~90% per level) usually caps chains at 4–5"* as though 10% were a constant. That is the exact claim
ADR-031's honesty gate caught and the repo corrected: Lindeman 1942 reported **0.1% to 37.5%**, and
never called it a law. The page that teaches food-web structure was teaching the folklore version, four
slices after the kit wrote down why it was wrong.

The other four are one defect wearing four hats. `nav_emit` regenerates every page's rail when a page
joins the kit, so the *repo* rails are all complete — but only a republished page carries the new rail.
**Greenhouse and Soil Recipes are published and reachable from nowhere except the hub.**

## 2. And then the unknowns turned out to be the bigger pile

Sixteen pages were still unknown, and one read each is all a verdict costs. The first one measured —
`ecology-field-guide.html` — came back **BEHIND, and blocking first paint on a font request.**

That is the third page found serving the render-blocking webfont, after `ecology-lab` and `adr-031`.
The field guide is, by its own dek, *"a plain-language guide to the ecology instruments"* — a reference
page, the kind that gets opened on a phone next to the thing it describes. It went white on one bar of
signal. Republished, and stamped.

**The lesson for where to spend next:** measuring an unknown costs one read and found a blocking page
on the first try; republishing a known-BEHIND page costs up to 2,769 lines to add two nav links. The
unknowns are the better queue, and that is a conclusion from measurement rather than a preference.

## 3. Two things I was about to report wrongly

**Stand Sheet's double-escape is not a visible defect.** The diff shows the published copy calling
`esc(t.dir)` where the repo calls `t.dir` raw (FEK escapes `op.sub` itself), so the published page
double-escapes. That sounds like literal `&amp;` on screen — except every `INTER_TYPES.dir` value is a
plain English word (`eats`, `disperses`, `pollinates`, `nests in`). `esc("eats")` is `"eats"`. The fix
is correct and latent; there is no present-day symptom, and calling it one would have been the kind of
claim this kit exists to not make.

**The tool misled me, and it was my tool.** ADR-078's BEHIND message printed
`copy 34526 bytes, publish bytes 23032` side by side, and I read it as *the repo is dropping 11 KB of
published content* — enough to stop and check before overwriting. The two numbers are not comparable:
the copy is the **wrapped** page and carries the publisher's ~12 KB runtime skeleton. The diff was
clean, and the repo in fact had *more* lines. The message now says which is which and that only the
containment test decides. A number that invites the wrong subtraction is a number that will eventually
get one.

## 4. The gate, and one force

The publish gate tracks **line 1** specifically. I had been skipping it — it is the 13 KB frame-runtime
blob and carries nothing of the page — and the refusal named it exactly: *"you have not yet Read line
1."* Reading it is the whole fix, and the sequence is now: fetch → read line 1 and every other line →
publish.

That cost one **force**, reported here as the standing authorisation requires. My first food-web
publish was refused for the unread line 1; the second, after reading it, was refused as a *duplicate* of
the content the first refusal had already seen. That is the branch Richmond pre-authorised — a page read
live in full and diffed — so it was forced. `ecology-field-guide` published first time with line 1 in
the reads, which is the evidence the sequence, not the force, was the fix.

## 5. Where the pile stands

```
19 current, 5 behind, 15 unknown, 0 unmapped
   20 page(s) are NOT known to carry the audited bytes
   of the current: 14 stamped before provenance was recorded,
                    2 stamped at publish time, 3 measured from the live page
```

The five remaining BEHIND are the four rail-link pages plus Stand Sheet — all now **measured, named,
and low-severity**, which is a different thing from an unexplained list of six. Fifteen unknowns remain
at one read each, and the first one opened was a page that goes blank in a field.
