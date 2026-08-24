# ADR-031: A shared entry layer, and three domain suites

**Status:** Accepted, and fully implemented — FEK v1.0.0 with four field pages migrated to it, all three suites built with front doors, and the honesty gate applied throughout. All eight actions closed.
**Date:** 2026-08-24
**Deciders:** Richmond
**Supersedes:** nothing. **Touches:** every instrument in `CSRBT/docs/`

---

## Context

The kit is now **nineteen instruments** in `CSRBT/docs/`, built one slice at a time over many sessions.
That growth has produced three problems that are architectural rather than cosmetic, and a fourth that is
an opportunity.

**1. Data entry was re-invented nineteen times.** Every page hand-rolls its own inputs. A numeric field is
a bare `<input type=number>` in Stand Sheet, a stepper in the Workbench, and a slider in Farm Scout. The
touch-target rule (≥44 px) has been enforced by *testing each page separately* and has regressed twice —
once in `field-notebook`'s `.top a`, once in the friendly-entry slice. There is no single place to change
how the kit takes a number, which means "make entry bigger and clearer" is currently a nineteen-file edit
with nineteen chances to miss one.

**2. The hub is carrying more than a hub can carry.** `#field-tools` reached fourteen cards, got regrouped
into four groups last slice, and is now at eighteen. Adding three domain suites at four to six instruments
each would take it past thirty. A flat list stops being navigation at roughly a dozen items.

**3. The honesty pattern is real but undocumented.** Four instruments already refuse to ship numbers they
cannot source — coefficients of conservatism in Relevé, edibility in the fungal pair, breakpoints in Micro
Bench, and now nutrient-free verification in Soil Bench. That refusal is the most distinctive thing about
this kit and it exists only as a habit. New suites will get it wrong unless it is written down as a rule
with a decision procedure.

**4. The three requested domains are unusually well-suited to this treatment**, because each has a small
number of genuinely load-bearing numbers that growers currently keep in their heads or in a notebook, and
each has a large body of folklore that is confidently wrong. Research findings are in Appendix A.

### Constraints (non-negotiable, inherited)

| Constraint | Consequence |
|---|---|
| **One self-contained file per page** | No shared stylesheet, no bundler, no npm. Artifact CSP blocks external hosts; pages must work offline in a field with no signal. |
| **Prints cleanly** | Interactivity is never load-bearing for the reference content. |
| **Tablet-first** | 16 px minimum inputs (iOS zoom), thumb-reachable, works with cold or gloved hands. |
| **No build step** | The user runs PowerShell scripts; there is no CI to run a bundler. |
| **Honest science** | Every number carries what it is worth. Unsourceable numbers are not shipped. |

---

## Decision

Three decisions, taken together.

**D1 — Introduce a Field Entry Kit (FEK): one versioned CSS+JS component layer, generated inline into
every page.** Built and shipping at v1.0.0.

**D2 — Package new domains as suites with their own hub sections, not as more cards on the kit hub.**

**D3 — Write the honesty pattern down as a three-way test that every new number must pass before it ships.**

---

## D1 — The Field Entry Kit

### Options considered

#### Option A: Keep hand-rolling per page (status quo)

| Dimension | Assessment |
|---|---|
| Complexity | Low per page, high in aggregate |
| Cost | A UI change is a 19-file edit |
| Scalability | Fails at ~20 pages — already failing |
| Consistency | Two regressions already shipped |

**Pros:** No new machinery. Each page can diverge where it genuinely needs to.
**Cons:** "Make entry bigger and more colourful" is unimplementable as a single change. Every new page
re-litigates the same decisions and re-introduces the same bugs.

#### Option B: Shared external stylesheet + script

| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Cost | Low |
| Scalability | Good |
| **Viability** | **Zero** |

**Cons:** Violates the hard constraint. The artifact CSP blocks external hosts outright, and a page that
needs a sibling file is not a page you can hand someone to open in a field.

#### Option C: Inlined, generated, versioned component layer — **chosen**

A Python module (`fek.py`) holds the canonical CSS and JS. Page generators inline both. The version string
is embedded in the emitted JS and asserted by tests.

| Dimension | Assessment |
|---|---|
| Complexity | Medium — a generator per page, already the pattern |
| Cost | ~15 KB per page, inlined |
| Scalability | Good to ~40 pages |
| Team familiarity | It is the pattern already used for glyphs and species packs |

**Pros:** One place to change. The constraint is honoured exactly. Version-in-artifact means a page can be
asked which FEK it was built against, so a rollout can be audited rather than assumed.
**Cons:** Duplicated bytes across pages. Rolling out a new FEK version means regenerating consumers — this
is real work and is the main cost of the decision.

#### Option D: Web components

**Cons:** Solves the reuse problem but not the distribution problem — the definitions still have to be
inlined, so it buys encapsulation at the cost of a shadow-DOM styling story and worse print behaviour. The
encapsulation is not worth much when every page is a single file with one author.

### What v1 contains

Sizing is driven by **one token**, `--tap` (60 px, 56 px under 420 px width), so the whole kit retunes for
gloves or a wall-mounted tablet by changing one number. Colour is a six-stop semantic ramp
(`--ramp-0`…`--ramp-5`, cold→hot / low→high) used consistently for ordinal meaning rather than decoration.

| Component | Replaces | Why it is better for this user |
|---|---|---|
| `FEK.step` | `<input type=number>` | 60 px ± buttons, hold-to-repeat, 30 px tabular value. Usable without looking. |
| `FEK.dial` | radio group / `<select>` | Ordinal choices as big colour-ramped buttons; the colour *is* the scale. |
| `FEK.chips` | checkboxes | 48 px toggles, single or multi. |
| `FEK.slider` | `<input type=range>` | 34 px thumb, gradient track, 26 px live value. |
| `FEK.picker` | `<select>` with 20+ options | Filter box + 48 px rows. A `<select>` of 65 genera is unusable on a tablet. |
| `FEK.tiles` | ad-hoc stat rows | 30 px readouts, tone-coded good/warn/bad/cold. |
| `FEK.banner` | ad-hoc verdict divs | The verdict, at 17.5 px, colour-coded to the same ramp. |

**"Polish by iteration" is the versioning.** FEK v1 ships on Soil Bench only. Each subsequent slice migrates
a batch of instruments and may bump the version; the version assertion in each page's test suite makes an
incomplete rollout visible instead of silent.

---

## D2 — Suite packaging

### Options considered

#### Option A: More cards on the kit hub
Simple, and it is what happens by default. Fails at ~30 cards; also wrong, because a carnivorous-plant
grower has no use for Relevé and should not have to scroll past it.

#### Option B: Separate hubs per suite, sharing FEK and the design system — **chosen**
Each suite gets its own front door and its own rail. The kit hub gains a short **"Suites"** section linking
to the three hubs, so the science kit stays the front door for science and the suites are front doors for
practice.

| Dimension | Assessment |
|---|---|
| Complexity | Medium — three more hub pages |
| Cost | Low |
| Discoverability | Better for a grower, one hop worse for a browser |
| Cross-linking | Rails already handle this |

#### Option C: One hub with audience filters
A JS filter over one card set. Rejected: it makes the *printed* hub incoherent, and the suites want their
own framing text, not the same cards with some hidden.

---

## D3 — The honesty test

Every number a page displays must pass one of three gates. This is the rule the kit has been following by
instinct; it is now explicit.

1. **Ship it** — the number is a *definition* or a *published standard with a citable source and a stable
   value*. Examples: `BA = 0.00007854 × DBH²`; Chao1's formula; PFRP's 55 °C for 3 days; NOP's 25:1–40:1.
   Cite the source next to the number.
2. **Ship it labelled a convention** — widely used, useful, but arbitrary or contested. Examples:
   Landis & Koch κ bands; A260/A280 ≈ 1.8; the 30–300 plate window; 20–50 cells per haemocytometer square;
   40–45 °C for drying fungal vouchers. The word *conventional* must appear beside it.
3. **Refuse to ship it** — regionally assigned, revised on a schedule, or safety-critical. The page takes
   the user's value and records its provenance. Examples: coefficients of conservatism (regional panels);
   CLSI/EUCAST breakpoints (revised annually); wetland indicator status; **edibility, ever**.

**A number that fits none of the three does not go on the page.** Appendix A shows this biting immediately:
carnivorous-plant dormancy temperatures and photoperiods are all over the hobbyist literature with no
citable primary source, so Suite A takes them per-species from the grower.

---

## The three suites

### Suite C — Soil & compost — **BUILT THIS SLICE**

`soil-bench.html`, five tabs, first consumer of FEK v1. 64/64 verified.

- **Compost** — pile log against the method you pick, live compliance against PFRP/NOP, temperature chart
  with the 55 °C and 66 °C lines drawn, turning ticks, squeeze-test moisture, stall and over-heat warnings.
- **Recipe** — C:N on **dry mass and nitrogen**, not buckets, with the "average the ratios" mistake called
  out explicitly, plus how many litres of browns or greens would reach 30:1.
- **Mix** — parts-based mix designer with ordinal indices, and a **nutrient-free flag** built for the
  carnivorous-plant case in Suite A.
- **Texture** — the USDA ribbon-and-grit key as a stepped colour dial, eleven terminal classes.

### Suite A — Carnivorous plants — *specified, next*

`cp-bench.html` (grow log) + `cp-characters.html` (the reference card).

| Tab | Content | Honesty gate |
|---|---|---|
| Water | TDS/ppm log per source, filter-change tracking | **Ship**: <160 ppm cited (California Carnivores); 50 ppm as the stricter hobby target, labelled convention |
| Media | Mix designer reusing Soil Bench's engine, nutrient-free enforced | Ship — it is arithmetic on parts |
| Plants | Per-plant log: pitcher/trap counts, new growth, division, flowering | Ship |
| Season | Dormancy tracker: entry/exit dates, chill accumulation, photoperiod | **Refuse** — per-genus targets are grower-entered, because the hobbyist literature has no citable primary source |
| Crosses | Pollination log, seed set, sowing, germination timing | Ship |

The refusal in **Season** is the interesting design decision: it would be easy and popular to hard-code
"Sarracenia need 3 months below 10 °C". The literature does not support a single number, so the app asks
for the grower's target, records it, and tracks against it.

### Suite B — Vegetable breeding — *specified*

`breeding-bench.html`, extending Pheno Tracker rather than replacing it.

| Tab | Content | Honesty gate |
|---|---|---|
| Population | Minimum population against the goal | **Ship**: ≥20 inbreeders / ≥100 outbreeders; sweet corn ≥100, preferably 200+ |
| Isolation | Distance calculator by crop and barrier | **Ship** where cited (corn 2 miles, squash ½ mile); **refuse** where it depends on local pollinators and terrain — take the grower's figure |
| Selection | Roguing log, selection differential, reuses Selection Log's engine | Ship |
| Trial | Replicated variety trial: plots, blocks, yield, days to maturity | Ship |
| Seed | Harvest, dry-down, germination test, viability by year | **Convention**: "3–5 years for most well-stored seed" |

**Suite B reuses Selection Log's mathematics directly** — a vegetable breeder measuring selection on fruit
size is doing exactly what the field biologist measuring selection on bill depth is doing. That reuse is
the strongest argument for D1: the engine is already written and verified, and only the entry layer differs.

---

## Trade-off analysis

**The central trade-off is duplication against distribution.** Inlining FEK into every page costs ~15 KB
each and makes a version bump a multi-file regeneration. The alternative — a shared file — is not available
under the constraints, and every other option trades away either offline use or print fidelity. Paying the
bytes is correct.

**Second: suite hubs cost a hop and buy relevance.** A biologist browsing the kit now needs one extra click
to reach carnivorous-plant tools. A carnivorous-plant grower gets a front door that is entirely about their
plants. The second user is the one being served.

**Third, and most consequential: the honesty test will make some pages less immediately useful.** A CP grower
opening the Season tab wants to be told the dormancy temperature. Being asked for it instead is worse UX and
better software, and it is the same trade already taken four times in this kit. The cost is real and should
be stated in each page rather than hidden.

---

## Consequences

**Easier**
- Changing how the whole kit takes a number — one file, one version bump.
- Building new instruments: pick components, write domain logic. Soil Bench's entry layer was assembled, not designed.
- Auditing a rollout: pages report their FEK version.

**Harder**
- A FEK version bump requires regenerating consumers. This is the standing cost of D1.
- Pages get larger. Soil Bench is 72 KB against ~45 KB for a comparable hand-rolled page.
- Three more hubs to keep wired; the link sweep grows.

**To revisit**
- **At ~40 pages**, inlining may stop being reasonable and a two-file model (page + kit) may be worth
  breaking the single-file constraint for — but only for pages that never need to work offline.
- **Migration order for FEK.** Instruments with the heaviest entry burden first: Stand Sheet (stem tally),
  Relevé (cover classes), Collection Sheet (spore print + spot tests), Ethogram (already close to FEK's
  shape by hand). The reference cards do not need migrating.
- **Whether Pheno Tracker is absorbed into Suite B** or kept as the general tool with Suite B extending it.

---

## Action items

1. [x] Build FEK v1.0.0 — seven components, one sizing token, six-stop ramp
2. [x] Build Soil Bench on FEK v1 as the proving consumer — 64/64 verified
3. [x] Write the honesty test down as a three-way gate
4. [x] Build Suite A: `cp-bench.html` **built and verified 78/78** and `cp-characters.html`
       **built and verified 116/116** — the suite now has its bench and its printable card, matching
       botany and mycology
5. [x] Build Suite B: `breeding-bench.html` — **built and verified 85/85**, reusing Selection Log's engine
6. [x] Add a **Suites** section to the kit hub and a nav chip, and build the **per-suite hubs**:
       `cp-suite.html`, `soil-suite.html`, `breeding-suite.html`, **verified 122/122**. Each opens on a
       numbered path through the work in the order mistakes actually happen, lists the instruments the
       suite uses (including ones it borrows from the wider kit), and closes with a *what this suite will
       and will not tell you* panel naming its own refusals. The hub's suite cards now lead to these front
       doors rather than straight to a bench; the benches stay reachable from the bench group.
7. [x] Migrate Stand Sheet, Relevé, Collection Sheet and Ethogram to FEK. **All four migrated and
       verified**: Stand Sheet 76/76, Relevé 66/66, Collection Sheet 72/72, Ethogram 71/71. v1.0.0
       covered every control the four needed, so no bump; three design decisions the migrations forced
       are recorded below.
8. [x] Add FEK version assertions to every migrated page's test suite. All four assert
       `FEK.version === "1.0.0"` and that no legacy `<select>` survives.

### What the migrations decided

**Aspect is eight compass points, not a free 0–360 field** (Stand Sheet, then Relevé). The old sheet took
aspect as a free 0–360 number. A hand compass read on a slope does not give a degree,
and storing 227° when the observer read "southwest" is a precision that was never measured — the same
failure the honesty gate exists to prevent, arriving through the entry layer rather than through a
published figure. Aspect is now an eight-point dial coloured along the heat-load axis. Nothing is lost:
the value exists to be folded, and |180 − |aspect − 225|| is identical whether the input was a compass
point or a degree. Cover moved to 5% steps for the same reason, since ocular estimates disagree between
observers by 10–20 points.

**Zero and *not recorded* stay distinguishable** (all four). Aspect 0° is north.
FEK controls have no null state, so each writes through to the field the export already reads, and that
field stays empty until the control is touched. Any page migrating to FEK with optional numeric fields
needs the same treatment; a `nullable` option on `FEK.step` and `FEK.slider` is the obvious v1.1 candidate
if a third page needs it.

**The cover dial is coloured by midpoint, not by position** (Relevé). Cover classes are ordinal and a row
of identical buttons hides that. The ramp is keyed to the class midpoint, so Braun-Blanquet 2 and
Daubenmire 2 — both 5–25%, both a midpoint of 15% — read as the same colour, and switching scale
mid-survey cannot silently change what a colour means. The same reasoning put strata, moisture, stand age
and coarse woody debris on dials rather than chips: all ordinal.

**A prior is labelled as a prior** (Collection Sheet). The genus picker shows the pack's trophic guild as
the option subtitle. That is a prior to check against the substrate actually observed, not a result, and
mixed genera say so. The host picker takes the dominant trees entered on the Site tab when they exist and
falls back to a regional default otherwise — labelled as such — and *host uncertain* is a first-class
option, because for an ectomycorrhizal fungus a guessed host is worse than a recorded uncertainty.

**Defaults are for fields where blank is not a state** (Ethogram). Interval and session length ship filled
in at 30 s and 10 min, which every other numeric field on every migrated page does not. The reason is not
convenience: a scan sample with no interval is not an under-specified design, it is not a design at all.
Everywhere else, blank means blank.

---

## Appendix A — Research findings

Gathered 2026-08-24. Marked with the gate each finding falls under.

### Compost — well sourced, gate 1

- **PFRP, 40 CFR 503 Appendix B**: within-vessel and static aerated pile — 55 °C or higher **for 3 days**;
  windrow — 55 °C or higher **for 15 days** with a minimum of **5 turnings** in that period.
- **USDA NOP**: initial C:N **25:1 to 40:1**; in-vessel or static aerated pile **131–170 °F (55–77 °C) for
  3 days**; windrow, that temperature for **15 days**, turned at least **5 times**.
- **Thermophilic working range** 120–150 °F (48–66 °C); above ~150 °F (66 °C) thermophiles are killed off.
  *Gate 2 — widely agreed, and the exact cut-off varies by source.*
- Finished-compost C:N ~10:1, with nitrogen availability falling sharply above 25:1. *Gate 2.*

### Vegetable breeding — partially sourced

- **≥20 individuals for inbreeders, ≥100 for outbreeders** per variety. *Gate 1.*
- **Sweet corn: at least 100 plants, preferably 200+; 2 miles isolation. Squash: ½ mile** between varieties
  of the same species. *Gate 1.*
- Corn, carrots and onions flagged as most susceptible to inbreeding depression; beans and cucurbits
  maintainable at low numbers. *Gate 1, qualitative.*
- "Most high-quality, correctly stored seed viable at least 3–5 years." *Gate 2 — a range, not a constant.*
- **Gap:** no single source gave a complete crop × isolation × population × longevity table. Suite B ships
  the cited rows and takes the rest from the grower.

### Carnivorous plants — the gate-3 case

- **Water TDS best below 160 ppm.** *Gate 1 — cited.* The stricter ~50 ppm target common in the hobby is
  *Gate 2*.
- Feeding: ¼ tsp MaxSea per gallon, monthly, foliar. *Gate 2 — one vendor's protocol, not a standard.*
- Tray watering excluded for *Nepenthes*, *Cephalotus*, *Drosophyllum*. *Gate 1, qualitative.*
- **Gap, and the important finding:** the sources consulted give **no** citable dormancy temperatures,
  durations, photoperiods, humidity ranges or media ratios by genus. Values circulate widely in the hobby
  and disagree with each other. **Gate 3 applies:** Suite A will not ship them.

### Soil texture — gate 1

- The USDA ribbon-and-grit key is standard across extension services and reliable to within one class with
  practice. Implemented as the Texture tab.

**Sources:** [40 CFR 503 App. B](https://www.ecfr.gov/current/title-40/chapter-I/subchapter-O/part-503/appendix-Appendix%20B%20to%20Part%20503) ·
[USDA AMS compost tipsheet](https://www.ams.usda.gov/sites/default/files/media/Compost_FINAL.pdf) ·
[Sustainable Market Farming — C:N ratios](https://www.sustainablemarketfarming.com/tag/cn-ratios-in-compost/) ·
[Learn Seed Saving — population size](https://www.learnseedsaving.com/population-size/) ·
[NMSU H-262 — vegetable seed saving](https://pubs.nmsu.edu/_h/H262/index.html) ·
[California Carnivores — growing tips](https://www.californiacarnivores.com/blogs/growing-tips/76003845-general-carnivorous-plant-growing-tips) ·
[NRCS soil texture calculator](https://www.nrcs.usda.gov/resources/education-and-teaching-materials/soil-texture-calculator)
