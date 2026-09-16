# ADR-212 — Three buttons handed the reader a file the published kit cannot deliver, and told them it had arrived

**This kit is read as published artifacts. Every audit in it drives `docs/` from a `file://` URL in a browser this container owns, where a page-started download works. The published page runs in a sandboxed frame that does not permit one: `a.click()` on a `blob:` URL returns nothing, throws nothing, and downloads nothing. Three controls of this kit — the breeding bench's and the cp bench's *Download bench.csv*, and the experiment guide's *Download .eco* — hand their payload over by download and by no other route. In the kit as anyone actually reads it, all three did nothing. And all three said they had.**

## 1. The kit had already worked this out

Two of the three carry a comment saying so, word for word:

> A hosted viewer can refuse a page-started download silently — no throw, no
> return value, nothing to test — so a mark here would be the exact ADR-203
> defect one layer along: the ledger reporting a sheet as gone from this device
> when the browser never let it leave.

That reasoning is right and it was acted on: the outbox is deliberately **not**
marked on a download. Then the same handler, four lines down, raised

```js
toast("bench.csv downloaded");
```

The ledger was made truthful and the thing the reader actually reads was not. The
experiment guide's was `toast("Downloading " + a.download)`. A message is the
only evidence a reader has about a channel that fails with nothing to test, and
these three were wrong wherever the kit is published.

## 2. Why no audit could see it

ADR-138 found this shape once already: `publish.py` was deleting `<header>` tags
from every published page, and no audit could see it *by construction* — every
audit measured `docs/`, and `docs/` was fine. It took measuring what the URL was
actually serving to find it, four months later.

This is the same gap in a different channel. `audit_outputs` presses the button,
sees a payload come back, and records EMITS — correctly, for the browser it is
driving. The payload's **channel** was never part of the question.

## 3. What is measured

`tools/audit_takeaway.py` presses every control `audit_outputs` counts as one
that hands something over — its rule, asked rather than copied — and reads the
payloads back by the channel the door already records:

| channel | survives publication | because |
|---|---|---|
| `clipboard` | yes | a write returns a promise that rejects, and an `execCommand` that returns false |
| `copy` | yes | same |
| `print` | yes | it opens the reader's own dialog |
| `download` | **no** | a sandboxed frame refuses it with nothing to test |

    CARRIES     at least one channel that survives publication
    STRANDED    its only channel is a download: nothing reaches the reader
    CLAIMS      STRANDED, and the page announced that the payload left

**STRANDED is a ratchet per page. CLAIMS is not.** A page that tells a reader
their sheet is saved when it is not is the defect this kit exists to refuse; it
fails on sight, with no ceiling and no flag.

**A HEDGED MESSAGE IS NOT A CLAIM.** "some viewers block a page-started
download" is true and useful, and a rule that counted it would push every page
back to the confident sentence. The audit reads the assertion, not the topic.

**WHAT THE PAGE SAID IS THIS PRESS'S.** The live-region log is a running list for
the whole page, and the door SPLICES it when it reports what an act said — so a
message read *after* that call is gone and one read *before* it belongs to the
entry. The first draft read it afterwards and found no claims at all: the audit
reported three stranded controls and zero liars, which is the comfortable half of
the truth.

## 4. What was done

All three still attempt the download, because where it works it is the better
route. All three now also put the bytes on the **clipboard** — a channel that
reports failure — and say which of the two the reader can count on:

```
bench.csv copied — some viewers block a page-started download, so the copy is your sheet
```

The outbox mark now goes where it belongs: the copy succeeded or it did not, and
the ledger records the answer. The experiment guide's `copyText` grew a third
argument so a caller can say what happened rather than having the message
assembled from a label.

The experiment guide's task holds both payloads — the download and the clipboard,
the same bytes on both — rather than asserting there is exactly one.

**3 of 81 → 0 of 81. 3 claims → 0.**

## 5. The instrument is broken on purpose

`tools/verify/takeaway` — 28 checks over six fixtures built from one template,
differing only in what the handler does and what it says: a download that says
nothing, one that says the file went, one that says the same thing and hedges it,
one that copies and says so confidently, one that downloads *and* copies, and one
that prints. Plus the two rules tested on their own.

`tools/mutate_takeaway.py` — 19 mutants, no known equivalents.

## 6. Filed, not fixed

The publisher reports that a hosted artifact **can** be given a real download:
declare the `downloads` capability and hand the bytes to
`window.claude.downloads.save(...)`. That is a change to what this kit declares
at publish time, not a change to a page, and it would make the three buttons do
what their labels say rather than what their fallback says. Filed. Until then the
copy is the channel that reaches every reader, and the message says so.

## 7. The shape

ADR-141's, again, at one remove: a rule enforced in one environment and relied on
in another. The kit knew the sentence was unsafe, wrote the reason down, applied
it to the ledger, and left it on the screen.
