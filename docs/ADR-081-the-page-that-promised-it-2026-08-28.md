# ADR-081: The page that promised it

**Status:** Accepted and implemented — `docs/ecology-essay.html`, `docs/eco-protocol-reference.html`
and `docs/ecology-teachers-guide.html` republished and stamped.
**Date:** 2026-08-28
**Deciders:** Richmond
**Follows:** ADR-031, ADR-055, ADR-078, ADR-079, ADR-080

---

## 1. The queue ADR-080 chose paid immediately

ADR-080 concluded that measuring an unknown — one read — beats republishing a known-BEHIND page that
needs 2,769 lines read to gain two nav links. Four unknowns were opened this slice. **All four came
back BEHIND, and all four were blocking first paint on a font request.** Three are republished here;
the fourth, `ecology-field-guide`, was ADR-080's.

Every one of the four diffs contained **exactly one substantive region**: the webfont block. No other
drift at all. These pages were correct in every other respect and had simply never been republished
since the offline hardening landed.

## 2. The promise and the breach, on the same page

`ecology-teachers-guide.html` is written for *"the teacher deciding on a Tuesday whether to use this
on Monday."* Its ninety-second answer opens with:

> **Does it need internet in the field?** Only to load the page the first time. After that a tablet in
> airplane mode in the middle of a field works fine.

Its section on tablets says *"Load the page indoors before you leave. Once it's open it needs no
signal."* Its footer says *"Every page here works offline and prints clean."*

**The published copy of that page held first paint on a Google Fonts request.** A teacher opening it
on school wifi at the edge of a field — the exact circumstance it describes — got a white screen from
the document making the promise.

That is the sharpest form the ADR-079 finding takes. The repo has been right about this for months.
`verify_offline_slice` has been green about it for months. The reader was getting the other thing.

## 3. The pattern, stated as a prediction rather than a conclusion

Four for four is a pattern, and the kit's own discipline says to write it down as something that can
be wrong.

**Prediction:** the pages missing the loader are the *prose* family — `.kit-nav` chips, Newsreader
body, no tab bar — because they were published before the offline hardening and have not been
republished since. The *tool* family — the rail, the fixed tab bar, Nunito Sans — all carry the
loader, because they were republished after it.

Evidence so far, all measured at the URL:

| carries the loader | does not |
|---|---|
| food-web, soil-recipes, cell-bench, ordination, deployment-log, stand-sheet, tree-proofs (tool family) | ecology-lab, adr-031, ecology-field-guide, ecology-essay, eco-protocol-reference, ecology-teachers-guide (prose family) |

`ecology-lab` and `adr-031` are the two that would falsify a naive "prose vs tool" split on styling
alone — both were also blocking, and neither is a plain prose page. So the real predictor is **when it
was last published**, and the family correlation is a consequence of when each family was built.

**What would falsify it:** any remaining prose-family unknown coming back CURRENT, or any tool-family
page coming back blocking. Twelve unknowns remain to test it against; the prose ones among them are
`plant-characters`, `cp-characters`, `tree-visualizer`, `eco-protocol-library`, and the three suite
hubs.

## 4. Where the pile stands

```
22 current, 5 behind, 12 unknown, 0 unmapped
```

Four pages have moved from unknown to current across ADR-080 and this record, every one of them a page
that was serving a blank screen to a reader on bad signal. The five BEHIND are the low-severity list
ADR-080 measured and named (four missing rail links, one latent double-escape) — unchanged, and still
correctly ranked below this.

**Not done, and stated rather than skipped:** twelve unknowns. At one read each and a republish only
where a read finds something, that is the queue, and it has now returned a blocking page on four
consecutive tries.
