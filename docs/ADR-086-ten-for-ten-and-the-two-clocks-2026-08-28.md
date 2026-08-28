# ADR-086 — ten for ten, and the two clocks that nearly stopped it

*2026-08-28. Status: accepted. Settles the prediction in
[ADR-084](ADR-084-the-guard-in-front-of-its-own-evidence-2026-08-28.md) and the open lead in
[ADR-085](ADR-085-the-date-of-a-copy-is-not-the-date-of-its-file-2026-08-28.md).*

## 1. The prediction, tested properly this time

ADR-084 predicted that the ten pages whose CURRENT rested on a stamp written before provenance was
recorded — the weakest evidence in the file — would all verify CURRENT when read at their URLs.
ADR-085 declined to count ten runs against *cached* copies as a test, because every one of those copies
was days old and every one was correctly refused as evidence. A refusal is not a result.

Ten live reads. **Ten CURRENT, measured from the live copy, dated by the version marker in the bytes.**
The falsifier — any one coming back BEHIND at its URL — did not fire.

```
39 current, 0 behind, 0 unknown, 0 unmapped
of the current: 20 stamped at publish time, 19 measured from the live page
```

The line that used to read *"10 stamped before provenance was recorded"* is gone, because the class is
empty. Every remaining entry says how it was earned and what dated it.

## 2. The lead from ADR-085, settled

ADR-085 flagged that six of the ten cached copies carried a **blocking** webfont link, and refused to
call it a finding on the grounds that it was a statement about three-day-old versions. Measured against
the live bytes:

| | blocking first paint |
|---|---|
| the ten pages, live now | **0 of 10** |
| the cached versions that raised the lead | 6 |

Every one of the six had already been fixed by ADR-082's sweep. **The lead was entirely an artefact of
stale copies**, which is what the hedge said it might be — and the reason to write the hedge rather
than the finding is that the finding would have sent a slice chasing work that was already done.

## 3. What nearly stopped all of it: two clocks for one event

The first of the ten refused to stamp:

```
collection-sheet.html   the copy carries this build, but the copy is older than the
                        stamp it would overwrite (1787810032 < 1787810037)
                        -- measured, not stamped
```

Five seconds. `--stamp` writes `time.time()` at the moment of the local call; the artifact's version
epoch was assigned by the publisher a few seconds **earlier**. Two clocks timing the same event, and
the honest date that ADR-085 had just installed made the read look stale against the stamp it was
supposed to improve. **Every one of the twenty publish-time stamps was unimprovable** — ADR-084's wall,
rebuilt by ADR-085's own fix, one slice later.

Note what the tool did NOT do: it did not report BEHIND. It said the copy carries this build and
declined only the stamp. The measurement was right; the bookkeeping refused it.

The fix is not a tolerance window — a five-second fudge is a number nobody can defend, and the next
publisher change moves it. **Ordering is only a question when the two entries describe different
builds.** When the stamp records the build the copy was measured to carry, they are the same publish,
and the only thing being decided is which provenance word the file keeps: `read` beats `publish`,
because one says the URL was serving these bytes and the other says only that they were handed over.

```python
if same_build:
    return True, ("the copy carries the very build this stamp records -- same "
                  "publish, and a read is better provenance than a publish")
```

It must not leak into `observation_allowed`, which has no such case and takes no such argument: a copy
of the same build that is genuinely older still cannot say the page is behind now. That is checked
rather than left to the reader:

```
PASS  a read of the SAME build supersedes a publish-time stamp it looks older than
PASS  the same-build case is the ONLY thing that changed that verdict
PASS  observation_allowed has no same-build escape -- it takes no such argument
```

`verify_publish_reach` 54 → **58 checks**.

## 4. Three slices, one shape

ADR-084 removed a guard with no satisfiable path. ADR-085 found the date feeding that guard had never
once been right, and narrowed the carve-out ADR-084 had opened. This record found that the corrected
date collided with a second clock, and that the collision was invisible because the tool's refusal
message reads like a normal safety line — the same way ADR-084's did.

The shape each time: **a rule that can only ever refuse looks exactly like a rule that is working.**
The only thing that caught all three was running the tool against real pages and reading what it said,
rather than trusting that green meant measured. Each fix was found by using the thing, not by
inspecting it.

**The next prediction, and its falsifier.** Twenty pages remain on publish-time stamps — "these are the
bytes I handed the publisher", which says nothing about whether the publisher kept them. Reading them
should move all twenty to measured. **Falsifier: any of the twenty coming back BEHIND**, which would
mean the publisher does not always keep what it is handed, and the twenty stamps are worth less than
the file claims. Ten reads at a time; the first ten cost nothing but the reading.
