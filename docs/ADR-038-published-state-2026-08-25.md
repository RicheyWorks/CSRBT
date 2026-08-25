# ADR-038: What is published, versus what is in the repo

**Status:** Accepted and implemented — `tools/publish_state.py`, registered as a finder in `run_all.py`. Nine pages stamped current; two republished to clear a live defect; ten remain behind and are now named.
**Date:** 2026-08-25
**Deciders:** Richmond
**Supersedes:** nothing. **Touches:** `tools/verify/run_all.py`, and every published artifact

---

## Context

Thirty-seven pages of this kit are published as Artifacts, and those URLs are the ones people are actually
given. **Nothing recorded which version of a page each URL was serving.** After any slice, the honest
answer to *"is the published Relevé the Relevé in this repo?"* was: nobody knows.

That is not a cosmetic gap. It means the kit that exists and the kit that people open had silently diverged
with no instrument capable of measuring the distance.

## What the measurement found

The first run turned up something worse than stale navigation. **The live Pheno Tracker was running Field
Entry Kit v1.1.1** — the version that builds dial options as `'<span>'+op.label+'</span>'`, unescaped. That
is the exact `Sarracenia <hybrid>` injection ADR-031 fixed in v1.2.0.

Cell Bench was the same. Both were published before v1.2.0 shipped, and so were roughly a dozen others.

**The kit's headline claim is that it fixed that bug. The pages people open still had it.** The severity is
low — these are single files with no server and no other users' data, so the worst case is a user's own
typed text rendering as markup on their own screen — but the gap between what the repo says and what the
published surface does is exactly the kind of thing this kit exists to refuse.

Both have been republished, along with the WCAG contrast fix and the honest autosave layer they were also
missing.

## Decision

**Record a hash of the exact bytes handed to the publisher, and report drift against it.**

```
python3 tools/publish_state.py                  # report
python3 tools/publish_state.py --stamp a.html   # record what was just published
python3 tools/publish_state.py --check          # exit non-zero if anything is behind
```

It regenerates the publish bytes before comparing, so the answer is against what *would* be published now
rather than against a stale build directory.

### Unknown is a state, and it is not "current"

A page that has never been stamped reports as **unknown**. It would have been trivial — and much tidier —
to stamp all thirty-seven at once and declare the kit green. That would have been the single most useful
lie this tool could tell: twenty-eight of those pages have a published state nobody has verified, and
recording a hash of today's bytes would assert they match when nothing checked.

So the report has four columns — current, behind, unknown, unmapped — and *unknown* stays until a page is
actually republished. The tool is registered in `run_all.py` as a **finder**, alongside `audit_claims`:
it prints a worklist and does not gate, because a page being behind is a fact about the outside world
rather than a fault in the tree.

## Consequences

- Nine pages are stamped current. Ten instrument pages remain behind and are named by the report.
- Every future publish is stampable, so this cannot silently accumulate again.
- The remaining ten each cost a full read of the live version before overwrite — the publisher's protection
  against clobbering someone else's saved content, which is correct and expensive. They are being cleared a
  few per slice rather than in one sitting.

## What was measured and not acted on

Coverage was checked at the same time: of thirty-seven pages, **one instrument has no verification suite
naming it** — `food-web.html`, which computes trophic levels, connectance and a keystone knockout test.
That is a real gap and it is recorded here rather than fixed, because it is a slice of its own.
