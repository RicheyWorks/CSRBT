# The ecology of a tree

*How the library that said no to self-tuning learned to see — by borrowing the
instruments of field biology, auditing them as ruthlessly as it audits itself, and
riding them to the one number its old negative results had been waiting for. Sequel to
"The machine that said no." Everything below has a receipt in this repository — an ADR,
a changelog, a pinned test, or a session file you can drop onto a web page.*

---

## After the no

The first essay ended with a closed research program. The evolution machine had run the
experiment everyone skips and published the answer nobody wants: the searched policies
don't beat the fixed four; the adaptive selector's ceiling is *matching* the best fixed
strategy without hindsight; switching costs more than the prize at any regime length
anyone had measured. ADR-012 parked its mechanism phase behind named re-arming triggers
and called the instruments — the viability map, the diversity metrics, the lineage
recorder — the real deliverable.

Which left a question the optimization program never had to ask: if the machinery's
value is *seeing* rather than *winning*, how well does it actually see? The answer, in
August 2026, was: worse than anyone had checked. And the path to fixing it ran through
an unexpected discipline — not machine learning, not database theory, but the field
methods of community ecology, applied with the same falsifiable-or-it-didn't-happen
rules the project applies to everything else.

## The audit that found constants where instruments should be

The experimental module had carried a `TreeEcology` class since the early days —
Shannon diversity, island biogeography, niche overlap, r/K scores, all mapped onto tree
structure with literature citations at every method. It looked rigorous. The 2026-08-09
audit asked the one question that matters about any instrument: *can this needle
actually move?*

Four of them could not. The tree is a set — every stored key has abundance exactly one
— so Shannon diversity was identically ln(S), evenness identically 1, the empirical
species-area exponent identically 1. Best of all, the Pianka niche-overlap index
between left and right subtrees was identically **zero**, because a binary search
tree's subtrees are disjoint *by the ordering invariant*. The instrument wasn't
measuring niche partitioning; it was measuring the BST property, which the invariant
tests already assert directly. An index that cannot vary carries no information — the
audit line that named the failure also named the fix: **the abundance distribution of
a data structure is not which keys are stored but how often the workload touches
them.** Membership is the habitat. Access is the ecology.

Everything that followed grew from that one correction.

## Refounding: instruments that move

The rebuild (ADR-015) put a deterministic recorder on the operation stream — per-key
touch tallies, cumulative and in windows, plus births and deaths in *operation time*,
never wall-clock — and rebuilt the classical toolkit on top of it: Shannon and Simpson
and the Hill numbers, rank-abundance curves fitted against the geometric series and
MacArthur's broken stick, Deevey life tables, Verhulst growth. Every function pure,
every formula cited, every one oracle-tested against hand-computed vectors, in the
same style the strategy scorer earns its trust.

The falsifiable hook was the audit's own complaint inverted: on a live tree under two
access regimes — uniform round-robin versus 90-percent-on-five-keys — the refounded
indices must *separate* what the structural ones provably cannot. They do, decisively:
evenness 1.00 versus 0.52, a hundred effective species versus eleven, and consecutive
hot windows showing temporal niche overlap above 0.9 where the structural form pins
zero. The instrument finally measures something. That test is the EC-1 fix,
demonstrated on the tree, pinned forever.

## One model per engine, or none

The tempting next move was to spray the new indices across every engine in the family.
The audit had taught the opposite lesson: a model bolted where the structure doesn't
carry it produces constants. So ADR-016's design rule was a *matching* problem — each
engine gets the one ecological model its actual dynamics support, or nothing.

The ensemble got metapopulation theory, because it literally is one: members are
habitat patches, quarantine is local extinction, healing from the primary is
recolonization from a mainland. The persistent engine got descent-with-modification,
because path copying literally produces a fossil record — every snapshot a stratum
that later edits cannot rewrite (a property the tests pin by calling `clear()` after
capture and checking the record didn't flinch). The B+tree — and every other engine —
got quadrat sampling, the field method applied so literally that the grid is laid over
the key range the way a transect grid is laid over a meadow. The cache got MacArthur
and Wilson unabridged: a bounded habitat where admissions immigrate, evictions go
extinct, and the equilibrium signature — *richness flat while composition churns* —
shows up in a test as a cache pinned at capacity that is never the same cache twice.

The honesty notes matter as much as the models. The ensemble instrument documents its
own blindness — a patch that dies and recovers entirely between surveys is invisible
to state-diff sampling, and the test asserts the blindness rather than hiding it. The
cache instrument had the same blindness and the same-day bug audit caught something
sharper: a resident evicted and re-admitted between sweeps silently *lost its first
life* from the record, and the books stopped balancing. Both probe tests failed against
the unfixed code before the fix counted — the project's audit discipline applied to
its own week-old code, which is where audit discipline is easiest to skip.

## Heredity, made physical

The content-based lineage instrument could say *which keys* survived a generation. It
could not say whether a surviving key kept its *node* — and under path copying those
are different questions, because every edit rewrites the ancestors of its site even
though their keys persist. ADR-017 opened the two seams ADR-016 had deliberately held
(the program's first core changes, both read-only, both oracle-tested in core before
any consumer touched them), and the measurement they unlocked is the kind of number
that reframes a design choice:

**At twenty percent key turnover per generation, eighty percent of keys survive — but
only fifty-seven percent of physical nodes do.** The twenty-three-point gap *is* the
write amplification of persistence, measured per generation, by reference identity,
with an exact-oracle test suite behind it (an untouched twin shares 100 percent; a
rebuilt tree with identical keys shares zero). The B+tree seam did the same for page
folklore: sequential loading at small fanout settles at 51 percent leaf fill — "a
split-heavy history left slack in the leaves" — the textbook signature, now a chart on
a web page instead of an assertion in a lecture.

## Perception: the early-warning experiment

All of this pointed at the oldest open wound in the project. E3b's diagnosis of the
adaptive selector's failure was not economics but *perception* — "the selector never
morphed once" through a 36 percent opportunity. Ecology has a name for the missing
sense: regime-shift detection, the study of how community statistics move when an
ecosystem tips.

The pre-registered experiment asked two questions with the method fixed in advance.
On abrupt shifts, consecutive-window Bray–Curtis turnover detects at **lag zero, with
zero false positives and zero fabricated precursors** — the precursor null matters,
because an instantaneous shift is precursor-free by construction, and a method that
"warns" before one is manufacturing signal. On gradual drift, displacement from the
baseline community crosses threshold at window seven of a six-to-twelve ramp — **five
windows of warning before the new regime establishes**, every seed.

The experiment also disciplined its own tooling twice, which is the part worth
retelling. Its first run failed because raw Bray–Curtis between a single window and a
five-times-larger merged baseline reads 0.67 for *identical* composition — the classic
unequal-effort mistake, caught by the harness, fixed by adding the size-fair Renkonen
index with the motivating contrast pinned in its oracle test. And a third test exists
solely to document why the gradual question uses displacement at all: consecutive
differencing provably smears slow drift into baseline noise. The methods section is
executable.

## The frontier: perception meets economics

With perception solved, the last question closed the loop on three months of negative
results. E3c had priced switching at six-thousand-op regime blocks and found the
quantum exceeded the prize threefold; its re-arming trigger asked for "blocks long
enough that the quantum amortizes" without knowing how long that was. ADR-018 measured
it.

The design honored E3b's discipline: premise first, hard-asserted — there must exist
regimes whose best strategy *flips* on the comparator meter, or the race is theater.
(It exists, with a mechanism the probe itself surfaced: an ascending-built Red-Black
tree holds its smallest keys shallow and wins hot-small-key reads; AVL's uniform depth
wins scans with misses. The honesty note is in the test javadoc: that advantage
belongs to the rebuild *shape*, reproduced deterministically by the morph seam — the
claim is the mechanism, not a strategy ranking.) Then three contestants on identical
seeded streams: fixed AVL, fixed Red-Black, and a morpher whose perception is entirely
the ecology layer — window turnover detects, window evenness classifies — and whose
every rebuild lands on the meter, health-gate validation included.

The result is a frontier, monotone and clean: the switcher loses by 2.24× at
two-thousand-op blocks, 1.30 at eight thousand, 1.06 at thirty-two thousand, breaks
even at **about 128,000 operations per regime block**, and wins — by one honest
percent — at 256,000. Three findings, each pinned: perception is no longer the
bottleneck (every shift detected, correctly classified, exactly one morph each);
E3c's negative stands exactly where it was measured; and the re-arming trigger
finally has its number. A production workload whose trace shows regime stretches of
order 10⁵ operations is the signal to reopen the mechanism phase — and the instrument
that spots such workloads is already shipped, in the same repository, as the drift
station of the trace replayer.

## What the biology actually bought

It would be easy to file all this under enthusiasm — a tree library cosplaying as a
nature preserve. The record argues otherwise. Every borrowed instrument earned its
place by answering an engineering question that had no native vocabulary:

Diversity indices turned "is this workload skewed?" from a vibe into a graded reading
with fixed thresholds and an effective-species count a non-specialist can repeat.
Turnover statistics became a shift detector with measured lag and a false-positive
record. Life tables gave eviction policies a survivorship curve; rarefaction and Chao1
gave surveys a completeness estimate ("roughly four rare keys likely went unseen");
physical-inheritance fractions priced path copying; leaf-occupancy histograms replaced
page-fill folklore. And the whole apparatus — narrated in plain English by a report
layer whose every sentence is threshold-pinned, rendered in a lab page with a live
terrarium, replayable over anyone's CSV — is the kind of observability the optimization
program wished it had when its selector was going blind.

The discipline transferred intact in both directions. The ecology layer was audited
twice in its first week (four confirmed defects, every one probe-verified before its
fix counted, including a 34-second-to-40-millisecond algorithmic repair whose
regenerated artifacts came out byte-identical). And the biology kept the project
honest in return: every mapping had to be structurally faithful or it produced
constants, every classifier had to survive its degenerate cohorts, every model
prediction was printed *next to* the direct measurement — the Levins card on the lab
page exists mostly to show the model disagreeing with observation and to explain why
that gap is a lesson about survey design rather than an error.

## Coda

The first essay's machine said no, and the no was the contribution. This arc's
contribution is quieter: a data structure that can now describe itself — its traffic
as a community, its churn as demography, its history as strata, its cache as an
island — in an idiom precise enough to pin in tests and plain enough to hand a
first-year biology student, with every number deterministic and every sentence graded
against a documented threshold. The machinery that failed to out-evolve four fixed
strategies turned out to be pointed the wrong way. Pointed at the workload instead of
the parameter space, it sees clearly enough to know, at last, exactly how long a
regime has to last before adapting to it pays: about a hundred and twenty-eight
thousand operations. Anything shorter, hold still. The tree already knew how to hold
still. Now it knows why.
