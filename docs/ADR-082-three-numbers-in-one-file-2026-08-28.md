# ADR-082 — three numbers in one file

*2026-08-28. Status: accepted. Supersedes the family reading in
[ADR-081](ADR-081-the-page-that-promised-it-2026-08-28.md); extends
[ADR-052](ADR-052-binding-the-docs-to-the-engine-2026-08-26.md) and
[ADR-078](ADR-078-the-published-copy-can-be-read-2026-08-27.md).*

## 1. The prediction, and what killed it

ADR-081 offered a falsifier for its own account of which published copies still block first paint:

> **What would falsify it:** any remaining prose-family unknown coming back CURRENT, or any
> tool-family page coming back blocking.

It was falsified on the first test. `farm-scout` is a tool-family page — tabbar, Nunito Sans, the
whole styling that the ADR-081 table put on the "carries the loader" side — and its published copy
carried a plain, blocking `<link rel="stylesheet" href="…fonts.googleapis.com…">`.

Then four more, every one of them tool-family, every one blocking:

| page | published copy | FEK markers | `escv` |
|---|---|---|---|
| farm-scout | blocking | banner 1.1.1 / runtime 1.1.0 | absent |
| breeding-bench | blocking | banner 1.1.1 / runtime 1.1.0 | absent |
| ethogram | blocking | banner 1.1.1 / runtime 1.1.0 | absent |
| field-notebook | blocking | banner 1.1.1 / **1.1** / runtime 1.1.0 | absent |
| field-season | blocking | banner 1.1.1 / **1.1** / runtime 1.1.0 | absent |

Five for five. The family split in ADR-081's table is dead as a predictor, and it was never the
mechanism — that ADR had already said so in the same paragraph that proposed it:

> the real predictor is **when it was last published**, and the family correlation is a consequence of
> when each family was built.

That half survives, and it is now the only half. The table was a picture of *which pages had happened
to be republished*, drawn as though it were a picture of the pages themselves. A correlate that
disappears the moment you sample outside the set that produced it was a description, not an
explanation — and the useful thing about writing the falsifier down was that testing it took one read.

## 2. Three version numbers in one file

Every one of those five published copies reported its Field Entry Kit version three times and gave a
different answer each time. `field-notebook` and `field-season` manage three distinct values:

```
  /* ============ Field Entry Kit v1.1.1 ============     <- CSS banner
  /* ---- Field Entry Kit v1.1 ---- */                    <- a second banner in the page's own script
  return { version:"1.1.0", step:step, … }                <- what the code reports at runtime
```

These come from one `VERSION` constant in `tools/fek.py`, interpolated into `fek.CSS` and `fek.JS`. On
a page the emitter has actually written they cannot disagree. The disagreement is therefore not a
version problem; it is a **signature of an emitter half that stopped running** — which is exactly the
failure `verify_emitters` was built for, recorded in its own docstring:

> It surfaced only because a version bump left the CSS banner reading an older number than the JS
> banner beside it.

The suite catches that by breaking a page and checking the regenerator notices. What it never did was
read the *numbers* and ask whether they agree. It did not need to for `docs/`, because `docs/` gets
re-emitted. It needed to for the copies readers were being served, and nothing was looking there —
ADR-079's finding, arriving for the fourth time in a different costume.

### What rode along with it

The version skew is a symptom worth nothing on its own. What it dates is the payload:

- **No `escv`.** In the published copies, FEK passed option labels, chip labels, dial subs and tile
  values straight to `innerHTML`. On these pages those strings are *typed by the user*:
  `add a visitor type (e.g. hoverfly)`, `add a species (e.g. clover)`, `F-blue / juv-1 / unmarked`,
  `aphids on kale`. To be accurate about the severity: this is a single-file offline page and the only
  person whose input reaches that `innerHTML` is the person typing it, so it is not a cross-user
  vector. The damage is that **a name containing `<` silently vanishes from the tally** — in a tool
  whose entire job is not losing what you recorded. Latent-but-real, the same class as the
  stand-sheet double-escape in ADR-080, and ranked above it only because these pages take free text
  from the field.
- **The WCAG AA ramp.** `--ramp-1` at its old teal measured 3.94:1 for white label text and 3.59:1 for
  the `.92`-white sub-line, both under AA. Five published copies were serving the failing values.
- **Dead links.** `breeding-bench`'s published copy carries `href="adr-031.html"` and
  `href="selection-log.html"` inside two banner bodies — relative paths that resolve in `docs/` and
  are dead on the artifact host. The publisher rewrites those from `tools/artifact_map.json`; that
  copy predates the rewriter. `build/publish/breeding-bench.html` has zero relative `.html` links.
- **The blocking webfont**, ADR-031's rule, broken where the reader is.

All five are republished and stamped. All five had been green in `docs/` for months.

## 3. The check

`verify_emitters` now asserts that **every version marker inside a block equals the module's
`VERSION`** — CSS banner, JS banner, and the runtime literal — for every emitter and every consumer.

The difficulty is entirely attribution, and getting it wrong is easy enough that I did:

> a bare grep for `version:"..."` across a page matches FEK's literal AND Keep's AND Ordination's AND
> Greenhouse's, which legitimately differ

A first probe reported six pages "disagreeing" — `greenhouse` showed `1.0.0, 1.1.0, 1.3.0` — and every
one of them was correct: FEK is at 1.3.0, Keep at 1.0.0, Greenhouse at 1.1.0, all in the same file.
Measuring before writing the check turned a would-be six false findings into a helper that reads each
marker inside the block its emitter owns, using that emitter's own `JS_RE` and `css_span` — the same
discipline the duplicate-stylesheet canary already used, for the same reason.

Three canaries, built from a real page mutated one token at a time:

```
PASS  a consumer page at rest carries no version disagreement (canary control)
PASS  a stale RUNTIME literal beside a current banner is caught
PASS  a stale CSS BANNER beside a current runtime literal is caught
```

The control matters as much as the two positives: without it, a detector that returns "disagreement"
for everything would pass both. And the CSS banner gets its own canary because the CSS half is the
half that went dead — a regenerator with two halves needs two canaries, which is already this suite's
own rule and would have been quietly broken by a check that only probed the script.

`nav_emit` stamps no version marker into a page at all. It reports that in a named passing check
rather than falling through the loop, because "no markers found" and "all markers agree" are
indistinguishable in a tally (ADR-061).

**Scope, stated rather than implied:** the tree is clean today, so this check finds nothing now. It is
a regression guard. Its justification is not a hypothetical — it is that the exact shape it catches was
live at five URLs this morning.

`verify_emitters`: 94 → **130 checks** (36 of them new: three canaries, one for
`nav_emit`'s absence of markers, and one per emitter-and-consumer pair).

## 4. Where the pile stands

```
27 current, 5 behind (0 measured at the URL), 7 unknown, 0 unmapped
of the current: 14 stamped before provenance was recorded, 9 at publish time, 4 measured from the live page
```

Up from 22 / 5 / 12. Nine pages have moved out of unknown across ADR-080, ADR-081 and this record, and
every single one was serving a blank screen to a reader on bad signal. The five BEHIND are unchanged
and still correctly ranked below the unknowns: four missing rail links, one latent double-escape,
none of them a blank page.

**The next prediction, and its falsifier.** Seven unknowns remain — `breeding-suite`, `cp-characters`,
`cp-suite`, `eco-protocol-library`, `plant-characters`, `soil-suite`, `tree-visualizer`. On the
publish-date account, which is the one still standing, all seven predate the offline hardening and all
seven should come back blocking, regardless of family. **Falsifier: any one of the seven coming back
CURRENT, or carrying `link[data-webfont]`.** Nine consecutive reads have now returned a blocking page;
the tenth is the test.
