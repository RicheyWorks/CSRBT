# The machine that said no

*How a tree library built an evolution machine, ran the experiment everyone skips, and
closed its own research program with negative results worth keeping. Everything below has
a receipt in this repository — an ADR, a changelog, a pinned test, or a replayable
session file.*

---

## The temptation

Every data-structure library eventually meets the same temptation: *what if it tuned
itself?* The pitch writes itself — workloads vary, parameters trade off, machine
learning exists. What almost no project does is state, in advance, what "self-tuning
works" would have to mean as a falsifiable claim, build the experiment into the design
document, and commit to publishing the answer either way.

CSRBT is a Java ordered-set engine whose balancing strategy — Red-Black, AVL, Splay,
Hybrid, and a parameterized weight-balanced family — is pluggable and can be swapped at
runtime behind a health gate: the candidate tree is built off to the side, validated
(contents, size, the strategy's own structural invariant, order-statistics spot-checks),
and only then promoted; a failed validation keeps the incumbent untouched. In mid-2026
the project pointed that machinery at the temptation directly. ADR-011 proposed an
*evolution machine*: a policy genome over the weight-balanced parameter plane, a UCB1
bandit and a (μ+λ) population search evaluating candidates as live shadow members of a
tree ensemble, and — this is the part that matters — an acceptance experiment written
into the ADR before any of it ran:

> Success criterion: the evolved/selected policy beats the best of the four fixed
> strategies by ≥10% realized cost on at least one workload family, sustained across
> ≥3 seeds. **The negative result is a documented finding.** Only an unrun experiment
> is a failure.

The answer turned out to be no. Then the project spent the next phase finding out *why*
no — and the why is more useful than a yes would have been.

## What made it buildable at all

Evolutionary search over data-structure parameters has an obvious failure mode: an
unsound parameterization doesn't just perform badly, it produces a wrong tree. Research
toys ignore this; production libraries never try. CSRBT could try because the safety
architecture predated the ambition. The health gate validates every candidate against
*its own* parameters before promotion (a strategy supplies its own invariant via a hook),
and the ensemble quarantines members that misbehave mid-write. The worst case of an
evolutionary misstep is a discarded candidate — recorded, visible, harmless. Never
corruption.

That claim got tested before the evolution machinery even existed. The very first slice
(V1) ported the literature's weight-balanced BB[α] rebalance to the strategy seam with
(Δ, Γ) as constructor arguments, and the very first suite run produced the machine's
first finding: **(5, 3) — a point everyone assumed was a sound arm — is unsound.** At op
500 of seeded delete churn the repair walk fails to restore balance and the strategy's
own invariant catches it. The discovery is a pinned regression test with two assertions
worth quoting: the violation *must* appear (if it ever stops appearing, the repair
changed and the sound region needs re-mapping), and even the unsound arm *never loses
data* — contents stay oracle-exact; only balance degrades. The self-disqualification
mechanism demonstrated itself before the bandit that would rely on it was written.

## The experiment, and the no

The machine went up in staged slices, each green through the full suite: the genome
(bounds-aware mutation and crossover, pure and unit-tested), an explainable fitness over
realized meters, the bandit driving shadow evaluations through the same anti-thrash
promotion gates the production controller uses, then (μ+λ) population search with
births, deaths, and lineages recorded and replayable in a browser-based arena.

V5 ran the registered experiment: five workload families (uniform, hot-key, sequential,
delete-heavy, regime-switching), three seeds each; per family the controller searches on
a live stream, then its selected policy races the four fixed strategies on identical
fresh streams. Cost is **comparisons per operation, counted at the comparator seam** —
chosen after wall-clock measurements flipped the verdict between two runs on shared
hardware. (That methodological note is itself a finding: time doesn't reproduce,
comparison counts were byte-identical across runs.)

The verdict line, printed by the suite: `success=false sustainedFamilies=[]`. No family
sustained a ≥10% win. The searched policy beat three of the four fixed strategies almost
everywhere — against Red-Black on uniform it was ~15% fewer comparisons — but on every
family some hand-written specialist was already within 10% or far ahead, and on
Splay's home turf (sequential access) the evolved policy lost by 33–39%.

The second-order result was sharper: **every (family, seed) pair converged to WB(3, ·)**
— the exact neighborhood of the literature's verified default, the point the project had
shipped all along because a 2010 fix to a Haskell containers library validated it. The
machine searched the box and independently rediscovered the textbook. A negative result
with teeth: four textbook structures are sufficient, and here is the instrument that
shows it.

## The turn: from optimizer to microscope

A weaker program would have stopped there, or worse, widened the genome and re-run until
something cleared the bar. ADR-012 did something else: it noticed what V5 *hadn't*
measured. V5 searched once per family and raced on a stationary stream — exactly the
case where a fixed specialist should win. The adaptive premise was never about steady
state; it was about *change*. And the machinery left standing — population, lineages,
viability oracle, recorder — was an instrument for questions the optimization framing
never asked: What is the shape of the viable region? What actually collapses diversity?
What does exploration cost under a hard viability constraint?

The ecology turn's design rule: **instruments before mechanisms.** Measure the dynamics
before building machinery to improve them. Each slice carried a falsifiable thesis,
registered before the run. Three of them came back with answers sharper than their
questions.

**The viable region is a sliver.** E1 swept the health gate's lethality oracle across
the whole (Δ, Γ) plane — 46 cells, in-box and beyond, identical seeded churn streams per
cell so that what dies, dies of its parameters. Two cells survived: (3, 2), the
literature point, and (4, 2). Everything else dies, most of it by op 300. The Γ=1 row
dies across every Δ from 2 to 32. This reproduces, with the project's own gate, the
literature's narrowness result for integer-parameter weight-balanced trees — and it
retroactively explains V5: the search converged to WB(3, ·) every time because *there
was almost nowhere else viable to go*. Mutational robustness made literal: a one-step
mutation from (3, 2) is lethal in most directions.

**The filter does the collapsing, not selection.** E2's thesis was the classic one:
(μ+λ) under a stationary workload collapses diversity within K generations — quantify K.
Measured from four deliberately unsound founders at the corners of the box: **K = 1, every
seed.** Three of four founders die by their own invariant in the first generation. The
population is one lineage from generation 1 onward — *selection never had any diversity
to squander*. The thesis's attribution was wrong and the instrument caught it: the
viability filter collapses the population, not selection pressure. Selection's
contribution is the slow part — a ±1 mutation walk from the surviving corner down to the
sliver, six to seven generations, Δ literally stepping 6 → 5 → 4 → 3 while Γ finds 2.
The literature point, found from outside the sliver. Two instruments — the map and the
collapse — agreeing through different ends of the microscope.

**Exploration costs O(n) while serving costs O(log n).** E3 finally ran the axis V5
skipped: a 48k-op run whose workload shifts regime on a schedule, with live evolution
controllers racing the fixed four on byte-identical streams, exploration *on the bill*
(the meter counts the ensemble's comparator, not just the primary's). No adaptive scheme
came close: 2.7× the best fixed strategy's integrated cost for a converged elite, ~5×
for a diverse population. The mechanism is visible in the per-block series: every
generation's candidate materialization is an O(n) build-aside rebuild, so exploration
scales with n while the serving it hopes to improve scales with log n. Live structural
evolution pays a tree-sized toll per generation to keep trying things.

## The perception failure, and the economics that excused it

E3's schedule had a flaw the project named in its own changelog: AVL dominated every
block, so the adaptive premise (no single structure covers the run) was false there. E3b
fixed this with the most careful protocol of the program — a **pre-registered
discriminating schedule** built only from already-published costs (alternating V5's
uniform and sequential families, block winners AVL ×4 / Splay ×2, premise hard-asserted
in the test), with a free-switching oracle ~13.5% ahead of the best single fixed
strategy. A perfect switcher could clear the bar in principle.

The production selector — the cost-model controller that picks specialists, the thing
V5 said the adaptive claim belonged to — **never morphed once** through a 36%
opportunity. Its hand-written cost model told it Red-Black was 30% better on diets where
the realized meter showed AVL ahead on *every* diet probed. The premise survived; the
perception failed. So the constants were recalibrated against the realized tables
already on the record (shape kept, constants refit, the old pins re-pinned with their
evidence), after which the selector went from never moving to **tying hindsight-best
fixed within ~1–3.5% while paying its own rebuilds** — still not the registered ≥10%
win. Both verdicts stand. Calibrating a model against its own realized meter sounds
obvious; the changelog that does it is titled "the scorer learns to see."

Which left one question: the residual ~13% oracle gap — claimable by *anything*? E3c
answered with the program's cleanest instrument. Two **clairvoyant** switchers were
handed the per-block winners table outright — perfect perception, an upper bound on any
detector. One morphs at each boundary (real health-gated O(n) rebuilds); one holds a
pre-built ensemble and promotes in O(1), paying the standing write fan-out instead.
Verdict: `claimable=false`, zero seeds of three, both contestants **losing to the best
fixed strategy by ~50%**. The free oracle dangles ~2.4 comparisons/op of prize; the
cheapest real way to switch costs ~8.6. The switching quantum exceeds the prize more
than threefold at this regime granularity. The planned perception feature was retired
with receipts — no detector can be better than the winners table both contestants
already had — and the selector's refusal to chase blocks was re-judged as **correct
economics**. "Match the best fixed strategy without knowing the future, and don't pay to
chase regime blocks" is not a limitation of the selector. It is the optimum, and the
program measured the optimum's edges.

## The transfer

One staged slice survived the disposition that parked the mechanism phase: does the
*pattern* — genome, viability oracle, shadow evaluation, gated selection, recorded
lineages — transfer to a second policy space with no change to the machinery? The test
bed was cache eviction: a two-gene genome over segmented-LRU parameters, deliberately
containing a lethal point (a configuration that evicts every admitted key on arrival —
that space's (5, 3)), a viability oracle over segment invariants, realized hit rate as
fitness.

The verdict was split, and registered before the run: **pattern transferred, loop did
not.** The generation protocol had to be re-typed (~345 lines) because the controller
class names tree-specific types — so the thesis's "no change to the loop" is false by
inspection, published as such. But the seams crossed unchanged: the anti-thrash
promotion policy slotted in without modification, the event vocabulary carried cache
lineages as naturally as tree lineages, and the recorder and replay arena consumed the
new space's history as-is. The lethal founder died at the gate on every seed, on the
record.

And the performance row delivered the program's motif one more time, in a space the tree
never saw: on a drifting workload, the evolved cache policy walked to **pure LRU** —
beating the textbook segmented configurations — and tied the best fixed founder at
Δ+0.000, all three seeds. Evolution under a viability filter, asked to beat a good fixed
policy on a fair meter, once again answered: *the textbook was already there.*

## What the program actually established

Strip the tree away and the findings generalize to any adaptive informational system
with a hard viability constraint:

The viable region of a parameterized policy family can be a sliver, and a cheap
viability oracle maps it empirically — the same instrument that makes online search safe
makes the search space legible. Viability filters, not selection pressure, can be what
collapses population diversity, and the distinction is measurable (K=1 with the
attribution flipped). The cost of exploration has different asymptotics than the cost of
serving — O(n) candidate materialization against O(log n) operation — so live structural
search pays a toll that no fitness landscape can refund. Whether *switching* policies
can ever pay is an arithmetic question — quantum versus prize — answerable by
clairvoyant upper bounds before building any detector; and a hand-written cost model
drifts from reality until it is calibrated against the realized meter it claims to
predict.

None of these came from a win. All of them came from instruments built around a
falsifiable claim, run honestly, with the negative published at the same volume as the
build.

## The discipline, since that's the real export

The pattern that produced this is small enough to state. Write the acceptance criterion
into the design document before building; a negative result is a finding, an unrun
experiment is the only failure. Decide on a deterministic meter and let it overrule the
noisy one (wall-clock flipped a verdict; comparisons/op never did). Pre-register
discriminating schedules from already-published numbers, and hard-assert the premise so
the experiment can't silently test nothing. Give clairvoyant upper bounds the first shot
at any "perception" feature — if perfect information loses, no detector wins. When a
premise is measured away, park the work with named re-arming triggers instead of letting
it haunt the backlog. And record everything: every death in this program is a gate
verdict in a session file the arena can replay.

The repository's history tells this story commit by commit: the strategy that found an
unsound point on its first run, the search that rediscovered the literature, the map
that explained the search, the collapse that indicted the filter, the bills for
exploration and switching, the selector that was right to hold still, and the pattern
that moved to a cache and converged to LRU. A self-balancing tree is a solved problem.
A system that can run an honest experiment on itself and publish the no — that turned
out to be the thing worth building.

---

*The record: ADR-011 (the evolution machine) and ADR-012 (the ecology turn) in
`docs/`, with per-slice changelogs — V1 through V5, E1 through E3c, the scorer
calibration, and the E6 transfer. Replayable sessions: `docs/arena-session.json` and
`docs/arena-search-session.json`, loaded by `demo/visualizer.html`. The viability map:
`docs/viability-map.json`. The suite that holds every pinned finding:
`./gradlew build`.*
