# ADR-202 — A check nobody can afford is a check that does not run

**Status:** accepted · **Date:** 2026-09-14 · **The CI workflow rebuilds the Java tree on two JDKs for every push to every branch. The last dozen slices are harness and page work containing no Java at all, so the minutes went on rebuilding a tree nothing in them had changed — and they ran out. A check that cannot run is not a check, and a green history that means *did not run* is worse than a red one.**

## 1. The filter, and the new way to be wrong it introduces

`on.push.paths` and `on.pull_request.paths`, the same list in both. That is the
whole change to the workflow.

It buys minutes and costs a guarantee: **a filter that does not cover a file the
build reads makes the build skip a change that could break it, and nothing says
so.** The history stays green, and green now means *the build did not run*. That
is a worse failure than the one being fixed, because it is silent.

So the filter is not a setting. It is a claim about the build, and it is held to
the build: `verify_ci` walks the tree, collects every file Gradle compiles,
packages or is configured by, and fails if one of them falls outside.

**An allow-list, not a deny-list.** A module added tomorrow lands under
`**/*.java` and `**/src/**` on the day it appears. A deny-list would silently
stop covering it, and the check would notice — but only after somebody had
pushed a broken build and read a green tick.

**The workflow is inside its own filter.** A change to the build's definition
that does not run the build cannot be told from one that skipped it on purpose,
so the first push after breaking `ci.yml` would look exactly like a push that
had nothing to build.

## 2. The matcher is the load-bearing part, and it is approximate

Every check here rests on being able to answer *does this path match this
pattern*. GitHub's filter syntax is its own thing; what is implemented covers
the forms this workflow uses — a literal path, a `*` that does not cross a
separator, and a `**` that does.

Two properties, both checked, because getting either wrong makes the whole
suite decoration:

- **`**` is consumed before `*`.** Otherwise the second star of a `**` reads as
  a separate single-segment wildcard, the pattern quietly stops matching across
  directories, and a filter that looks right covers nothing.
- **A pattern out of scope is refused, not treated as covering everything.** A
  matcher that answered yes to a pattern it had not understood would hold the
  filter to nothing while reporting that it held.

And the other direction: a check that the files the last dozen slices actually
changed — `AI_HARNESS.md`, a page, `harness_tasks.py`, `fek.py`, a delivery
manifest — do **not** match. If they did, the filter would be a filter in name
only.

## 3. What this does not fix

**The Actions minutes are still spent.** This stops the waste; it does not
refund it. Until the quota resets, the CI check is dark on every push including
the ones that touch Java.

**A path filter on a required status check is a trap**, and this repo is one
workflow change away from it. If `ci` is ever made a required check for merging,
a pull request touching no Java will never run it and will sit pending forever —
GitHub's own answer to that is a second, trivial job that always runs. This repo
pushes straight to `main` through the delivery scripts and has no required
checks, so the trap is not sprung; it is written down here because the next
person to add branch protection will not otherwise know.

**Nothing here covers the harness.** `run_all`, the mutant runners and the page
suites have never run in CI — they need Playwright and about three hours. The
Java matrix is the only thing that has ever run there, which is exactly why
filtering it to Java is safe.

## 4. What is checked

`verify_ci`, 12 checks: both events carry a filter; the two lists are identical;
every pattern is one the matcher can evaluate; a pattern out of scope is
refused; every file the build reads is inside the filter; the workflow is inside
its own filter; the harness files are outside it; and the matcher's `**` and `*`
behave as claimed.

`mutate_ci`, 10 mutants, all killed — each of the three coverage patterns
dropped from **both** lists (the realistic mistake: the filter is written once
and copied), the workflow dropped from its own filter, the two lists drifted
apart, `pull_request` losing its filter entirely, and three against the matcher
itself: `**` read as two single-segment stars, `*` crossing a separator, and an
unreadable pattern treated as covering everything. Plus one that files nothing
as a build file, which would make every coverage check pass on an empty list.

The suite was written before the fix and failed 7/11 against the unfiltered
workflow, naming the four things that were wrong.
