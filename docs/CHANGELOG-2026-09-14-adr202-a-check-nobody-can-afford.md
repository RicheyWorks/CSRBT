# 2026-09-14 — ADR-202: a check nobody can afford

**The CI workflow rebuilt the Java tree on two JDKs for every push to every
branch. The last dozen slices are harness and page work containing no Java at
all, so the minutes went on rebuilding a tree nothing in them had changed — and
they ran out. A green history that means *did not run* is worse than a red one.**

## Fixed

- `.github/workflows/ci.yml` — `on.push.paths` and `on.pull_request.paths`, the
  same list in both. An **allow-list**, so a module added tomorrow lands under
  `**/*.java` and `**/src/**` on the day it appears rather than after somebody
  has pushed a broken build and read a green tick. The workflow is inside its
  own filter, because a change to the build's definition that does not run the
  build cannot be told from one that skipped it on purpose.

## Added

- `verify_ci` (12 checks). A path filter is not a setting, it is a claim about
  the build, so it is held to the build: the suite walks the tree, collects
  every file Gradle compiles, packages or is configured by, and fails if one
  falls outside the filter. It also checks the other direction — the files the
  last dozen slices actually changed must **not** match, or the filter is a
  filter in name only. Written before the fix; it failed 7/11 against the
  unfiltered workflow and named all four faults.
- `mutate_ci` (10 mutants, all killed). Each coverage pattern dropped from
  **both** lists, which is the realistic mistake — the filter is written once
  and copied. Three of the ten are against the suite's own matcher: `**` read
  as two single-segment stars, `*` crossing a separator, and an unreadable
  pattern treated as covering everything. A filter held by a matcher that says
  yes to everything is a filter held by nothing.

## Noted, not fixed

- **This stops the waste; it does not refund it.** Until the quota resets, the
  CI check is dark on every push, including the ones that touch Java.
- **A path filter on a required status check is a trap.** If `ci` is ever made
  required for merging, a pull request touching no Java will never run it and
  will sit pending forever. This repo pushes straight to `main` through the
  delivery scripts and has no required checks, so the trap is not sprung — it
  is written down because the next person to add branch protection will not
  otherwise know.
