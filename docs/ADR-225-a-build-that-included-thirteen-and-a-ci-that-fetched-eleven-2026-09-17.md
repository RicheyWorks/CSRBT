# ADR-225 — WholeHog's build includes thirteen siblings and its CI checked out eleven, so every push failed before a test ran

**A composite build resolves `includeBuild("../Rub")` against the directory
beside it. WholeHog's CI job checks the siblings out one by one, by name, and
the list was written when there were eleven. Rub and Sizzle joined
`settings.gradle.kts` and never joined the workflow, so every push since has
failed at configuration — *Included build '../Rub' does not exist* — which is a
red that looks like a broken build and is a missing directory.**

The September handoff had it as a known fact ("WholeHog CI fails from missing
sibling Rub checkout") and nothing held it, because the two lists live in two
files of one repo that nothing compared.

## What changed

- **`ecosystem.py`** reads an engine's CI checkouts off its workflow files and
  its composite closure off its settings file, and `ci_gap(repo)` is the
  difference. A repo with no workflow answers `None`, which is NOT VERIFIED and
  not clean.
- **`verify_ecosystem`** holds every engine's gap to empty — one check per
  engine, fourteen, written before the fix and failing on WholeHog with exactly
  `['Rub', 'Sizzle']` — plus a fixture in which a transitive include is the one
  missing, since a job that checks out its direct includes and not what they
  include is the likely next mistake. 99 → 116 with the fixture (fourteen engine checks and three fixture checks); three mutants
  in `mutate_engines`.
- **WholeHog's workflow** checks out Rub and Sizzle. It travels as
  `WholeHog/ci/ci.yml` and is installed by `push-adr225-siblings.ps1`, the
  operator's own command, for the reason ADR-223 gives.

## Also measured

The same comparison over all fourteen engines: thirteen agree with their
builds. Only WholeHog did not.

## Held

- ~~`mutate_engines`: "every test class is read under the same name" SURVIVED
  here~~ — it did, on the first run, and was killed on 3 September: the check
  that kills it is NOT VERIFIED on a machine with no engine test results, so
  the mutant's fate depends on whether the engines have been built beside the
  kit. The engines' tests were then run here (a Maven Central 429 cost the
  first attempt) and the runner re-run: 16 of 16 killed. Recorded because a
  runner whose verdict depends on what is installed is a runner that will say
  SURVIVED on the next fresh machine, and whoever reads that should know why.
- ~~SmokeHouse's concurrent-compaction test failure~~ — **found and fixed
  here.** `rangeSurvivesAConcurrentCompactionCommit` failed about one run in
  five: `range()` and `get()` read the log outside the store lock and re-resolve
  when a compaction commit moves the address they hold, a bounded eight times,
  and the test's writer — overwrite the keyset, compact, repeat — commits a
  compaction between every re-resolution and the read after it. Eight tries
  were eight losses on a healthy store, and the bound threw *log/index
  divergence*. The commit runs under the store lock, so the ninth read now
  happens under it, where a commit cannot intervene, and settles the question:
  live at a readable address, gone, or a genuine divergence — only the last is
  an error. 82 of 82, three consecutive runs of the probe. `SmokeHouse.java`
  travels in the sibling tarball and `push-adr225-siblings.ps1` commits it.
