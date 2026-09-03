# ADR-138 — What the reader actually sees: measurement made the default, and the strip that ate a page

**Status:** accepted · **Date:** 2026-09-03 · **Twenty-two of forty-one artifacts carried the weaker stamp — "these bytes were handed to a publisher" — because measuring one meant a human remembering to fetch it. `publish_reach.py` makes the measurement mechanical, an unmeasured artifact is now a hole in the count rather than a pass, and the Harness Board is an artifact like any other. Measuring all forty-two found that `publish.py`'s shell-stripping regex had been eating `<header>` on eight pages and 321 characters of JavaScript out of the published greenhouse, whose every interactive feature was therefore dead — invisible to every audit in the kit, by construction**

## 1. The two stamps, and why only one of them answers the question

ADR-078 split the evidence `publish_state.py` records, and refused to let the
halves read as one:

    via "publish"   these are the bytes I handed the publisher. Says nothing
                    about whether the publisher kept them.
    via "read"      the URL was serving these bytes at that moment.

Every audit and every suite in this kit measures **`docs/`** — the repo. The
sentence "the kit is clean" is a claim about a reader only for the pages whose
published copy carries those same bytes, and `via "read"` is the only evidence
that says so. On the morning of this slice, 19 of 41 pages had it.

The other 22 did not, for a reason with nothing to do with judgement: measuring
a page meant a human remembering to fetch its artifact and hand the copy to
`--verify`, one page at a time. **A stronger form of evidence that costs more to
obtain is a form of evidence you do not have.**

## 2. `publish_reach.py`

    python3 tools/publish_reach.py            # who is measured, who is not
    python3 tools/publish_reach.py --plan     # the work list, one artifact per line
    python3 tools/publish_reach.py --sweep DIR  # verify every saved copy in DIR
    python3 tools/publish_reach.py --check    # non-zero unless every artifact is measured

It does **not** fetch, and says so in its own docstring. An artifact is read
through the host's Artifact tool, not over HTTP from this container, and a
script that pretended otherwise — scraping a mirror, trusting an undated cache —
would be manufacturing exactly the evidence it exists to demand. So the boundary
is stated: `--plan` emits precisely what to read, the operator (or an agent with
the tool) reads it, and `--sweep` attributes and verifies whatever comes back
through `publish_state.py`'s existing rules — the same containment test, the
same dating from the version marker in the bytes, the same refusal to record a
copy of one page as evidence about another.

`--sweep` adds one rule of its own: with two copies of a page in a directory,
the newer **version** wins, not the newer file. mtime is a property of the local
file, and ADR-078 measured 103 saved copies where every mtime was later than the
version it held.

### The board is an artifact too

ADR-127 published the Harness Board and held that it is republished by hand — so
the one page that reports on everything else was the one page nothing reported
on. `artifact_map.json` gained an `others` section, `publish.py` builds
`tools/harness_board.html` into `build/publish/_harness-board.html`, and from
there it is measured or it is a hole, like the rest. 42 artifacts, not 41.

## 3. What measuring all forty-two found

`publish.py` removes the document skeleton, because the Artifact runtime wraps
the file in its own. It did it with

    r'</?head[^>]*>\s*'

and that pattern is wrong twice.

**It matches `<header>`.** `head` then `[^>]*` eating `er class="hero"`. It
matches `</header>` the same way. Eight pages of this kit open with a
`<header class="hero">` banner, and every published copy of them had **both**
tags deleted — the content survived unwrapped, `.hero` never applied, and the
banner rendered as loose text.

**And a character class matches newlines.** In `greenhouse.html`,
`for(var i=0;i<headers.length;i++){` gave the pattern a `<head` to start from,
and `[^>]*` ran forward — past the loop body, past the next statement — to the
next `>` anywhere in the file. **321 characters of JavaScript were deleted from
`mapHeaders()`**, the CSV column matcher. The published page carried

    for(var i=0;i= 0){ map[field]=i; used[i]=1; return; }

a syntax error, so the whole `<script>` block failed to parse and **every
interactive feature on the published greenhouse was dead**.

No audit in this kit could have found it. Every audit measures `docs/`, and
`docs/` was fine. It took reading what the URL was actually serving.

### The fix, and the general form of it

The patterns now carry `\b` after each tag name and `[^<>]*` for the attributes,
because a tag cannot contain `<`. More importantly, `strip()` no longer trusts
its patterns:

> Stripping N shell tags removes exactly N `<` characters. Anything else means a
> pattern spanned something that is not part of the document skeleton, and the
> right response is to refuse to build rather than to publish a page with a hole
> in it.

That guard would have caught this the day publish.py was written, and it catches
the next one whatever shape it takes.

Nine artifacts were republished from corrected bytes — the eight `<header>`
pages and greenhouse among them — and re-measured at their URLs.

## 4. A hole is a hole; a stale URL is a failure

`verify_publish_reach` now separates two outcomes that had never been
distinguished, because they are not the same claim:

- **`behind`** — the repo has moved past what that URL was last known to serve.
  A reader is being handed an old page. That is a **failure**.
- **`stamped` / `unknown`** — nobody has looked. That is a gap in the evidence,
  reported as **`NOT VERIFIED`**, one line per artifact, naming the command that
  closes it. Never a pass, and never quietly folded into one.

## 5. Verification

`verify_publish_reach` gains **28** checks (**78**): every artifact mapped
(the board included) and built; the reach known for each; `--plan` naming
exactly what is owed; attribution by artifact id, refusing an ambiguous prefix
and a copy of nothing; the two stamps kept apart (a `publish` stamp reads as
`stamped`, a `read` stamp as `measured`, a mismatched sha as `behind`); the
sweep taking the newer version even when the older file was touched last; and
the strip: a `<header>` pair surviving, a JS comparison that reads like a tag
surviving, the real skeleton still removed in any case, and a span-eating
pattern **refused rather than published**. Every page of the kit that opens with
a `<header>` is required to still have one in the bytes handed to the publisher.

`tools/mutate_publish.py` is new: **15** mutants across all three files of the
pipeline — the historical patterns restored, the word boundary dropped, the
guard disabled and then miscounted, the skeleton left in, the board unmapped and
unbuilt, the two stamps collapsed each way, a behind URL demoted to a hole, an
ambiguous id accepted, an unnamed copy attributed anyway, the sweep taking the
first copy and then dating by mtime, and the plan claiming nothing is owed.
**15 killed, 0 survived.**

Two things the mutants forced: the runner links `docs/` into its temp tree (a
subject that *builds the kit's pages* cannot be tested without them — every
mutant was dying of "there are pages to check: 0", which is a suite falling over,
not noticing), and the suite picks a page whose build output exists, since a
mutation that makes `publish.py` refuse a page otherwise kills the suite with a
`FileNotFoundError` instead of a report.

## 6. Held

- **A measurement is stale the instant someone republishes.** These 42 were
  measured today. `publish_reach` reports what the ledger holds, and the ledger
  decays by ADR-078's rule the moment the repo moves; it does not decay when
  someone else republishes the same URL. Nothing here can see that.
- **`--sweep` cannot fetch**, and that is by design, but it means the count is
  only as current as the last time an agent ran `--plan` and read what it named.
  Wiring the read into a scheduled task is the obvious next step and is not cut.
- **The eight `<header>` pages were republished, not re-audited at the URL for
  layout.** The bytes now match; whether `.hero` renders as intended on the live
  page is a claim this slice does not make.
- `publish_state --verify` still takes one page at a time; `--sweep` is the only
  batch path, and it lives in the new file rather than in the old one.

## 7. First reading

    publish reach   42 mapped artifacts, 42 MEASURED — the first time
    published state 42 current, 0 behind, 0 unknown, 0 stamped-only
    verify_publish_reach  78 / 78  ·  mutate_publish 15 killed, 0 survived
    verify_board    48 / 48
    kit  77 / 77 jobs, 5,674 / 5,674 checks
    board 5,264 checks, 54 / 54 tasks, 12 traces, 243 / 243 mutants
