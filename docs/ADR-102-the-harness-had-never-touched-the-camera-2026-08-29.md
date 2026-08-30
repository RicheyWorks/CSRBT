# ADR-102 — The harness had never touched the camera

**Date:** 2026-08-29
**Status:** accepted
**Extends:** ADR-061 (silent exclusion with a plausible face), ADR-069 (a check
that cannot fail is not a check), ADR-094 (a worklist with a front), ADR-100 (the
instrument was the first thing it found), ADR-101 (a click is not a result)

ADR-101 reported that 1,966 controls had been checked against a stated
expectation. A deep audit of what a user can actually *enter* was run against
that claim, and it found four surfaces the harness had never touched at all:

| surface | how many | what the harness did with it |
|---|---:|---|
| `input[type=checkbox]` | 12 | no kind's selector matched — invisible |
| `input[type=time]` | 1 | the text kind listed three types; this was not one |
| `input[type=file]` | 5 | **excluded on purpose**, with a reason that was wrong |
| drop zones | 3 | no CSS selector can find one — never driven |

The file exclusion is the one worth naming plainly. ADR-101 wrote that a file
chooser "needs OS focus and an approval policy the gateway does not own". That
confused the native **dialog** with the **act of handing a page some bytes**. The
dialog is still out of scope and still never opens. The bytes were always ours to
supply. Behind that confusion sat the kit's only photo entry — `accept="image/*"
multiple` on stand-sheet — never once driven, and the `📷 Add photos` button in
front of it reported as an Add that added no row.

## 1. Photo entry, and what a drone hands you

Three fixes make the camera path testable:

* **Real bytes, made rather than read.** A fixture table of eight files — a JPEG,
  a PNG, a WebM, a JSON pack, an `.eco` session, a CSV, and a deliberately corrupt
  file — built in the harness. A run reads nothing of the operator's disk and
  needs no fixture directory. One of them is called `DJI_0192.JPG`, because a page
  that keys on a filename should be driven with a filename somebody will really
  hand it.
* **Hidden inputs are driven.** Three of the five file inputs in this kit are
  `display:none` by design, with a camera or Load-pack button standing in front of
  them. A user reaches them; refusing on grounds of visibility would have left the
  photo and pack paths untested for the sake of a rule that does not apply.
* **Drop zones are found by instrumenting the page.** A drop listener leaves no
  mark in the markup and no selector finds it, so `addEventListener` is wrapped
  and the element is stamped as the listener is registered. Three pages take
  photos and data by drag-and-drop and none had ever had anything dropped on it.

The result, measured:

```
stand-sheet  file_in    verified   IMG_0431.jpg, DJI_0192.JPG named on the page
stand-sheet  drop_zone  verified   IMG_0431.jpg named on the page
stand-sheet  action_btn verified   opens the file chooser
```

The camera button is verified now against what it actually does. Opening the
chooser **is** its result, recorded by wrapping `HTMLInputElement.click` so the
native dialog never opens and the request is counted instead. One of ADR-101's
eighteen findings retires as a false positive.

**And a real defect, read against the source.** stand-sheet's photo drop zone
discards anything that is not an image, in silence:

```js
if(!/^image\//.test(f.type)) return;
...
if(added){ renderPhotos(); buzz(); toast(added+" photo"+... ); }
```

Drop a folder with a video in it, or the drone's flight log beside its frames, and
the photos appear and the rest is gone without a word — `if(added)` gates the only
message the page ever gives. Under this harness's own rule, a control that
declines has to say so.

**Video: the kit does not take any.** No page in the kit accepts a video file or
records one; the word appears only in the teachers' guide, describing scoring
behaviour from a recording made elsewhere. Rather than invent a surface, the
harness now carries a `.webm` fixture so that a page which *should* refuse one can
be shown refusing it — which is how stand-sheet's silent discard was found.

## 2. The harness records what it did

A defect nobody can watch happen is one somebody has to reproduce by hand before
they will believe it. Every page run is now filmed at 390×844, and a still is
taken in the state each finding was reported in. **A film is kept only where there
is something to watch** — 17 of 40 pages this run; the rest are deleted, because
forty films of a page behaving is forty films nobody opens.

## 3. Three questions the swarm does not ask

`tools/probe.py` adds passes whose shape is different: no per-control expectation,
only invariants — *is this still a page, and did it say something when it refused*.

**EDGES.** Every field, every value that has ever broken a form: empty, whitespace,
zero, negative, enormous, `1e308`, a decimal where an integer belongs, letters in a
number, an impossible date, 400 characters, emoji, markup, and the separators an
export has to quote. **344 fields, 4,284 values, 16 findings.**

**CHAOS.** N random actions drawn from whatever is on screen, seeded, invariants
checked after every single one. When one breaks, the finding carries the seed and
the exact list of actions, so the sequence **replays** instead of being retold.
**2,786 actions, 151 findings.**

**EXPLORE.** Every path through a key. Depth-first to a leaf, then reload and
replay the prefix to take the next branch — reload-and-replay rather than undo,
because a page has no obligation to be reversible and a walk that assumes it is
will quietly explore a tree that is not there. **859 paths, 413 leaves, 657
options, 276 distinct states, deepest 14. No findings: the keys are sound.**

## 4. What the new passes found

* **field-season throws.** 26 uncaught `TypeError: Cannot read properties of null`
  under random pressing. **ordination** throws too, twice.
* **farm-scout loses 76% of its rendered text** after a particular sequence — the
  page is still there and most of it is not.
* **ecology-lab renders `NaN–∞` in a readout** (`div.v`) when a field is given an
  edge value, and NaN in its Hardy–Weinberg block.
* **tree-proofs renders NaN** under random pressing.
* **A 400-character entry breaks the layout of eight pages**, pushing content
  3,400–3,700px sideways on a 390px phone.

That last one closes a loop. **ADR-100 found a rule that can never fire** —
`.row2 .g span` declaring `text-overflow:ellipsis` with no `white-space:nowrap`,
copied into fifteen pages. This is what it was supposed to prevent: ethogram's
`div.row2` measured **3,092px wide** under chaos, and `div.g` — the very element
whose text was meant to be truncated — **3,010px**. A dead rule was filed as a
tidiness defect. It is a layout failure waiting for a long species name.

## 5. Six defects, all of them the instrument's

1. **The battery was testing a tenth of the fields.** `edges` and `chaos` filtered
   candidates on the visibility recorded in the snapshot taken at load, and most
   fields in this kit live in a pane that is shut. breeding-bench: 3 fields, 42
   values. After: **14 fields, 196 values.** cell-bench went to 26 fields, 364
   values. Judging a control from a state where its effect could not appear, one
   more time, in one more place.
2. **A time field was handed a text sentinel.** The browser discards it before the
   page sees it, and deployment-log's start time was reported as throwing an entry
   away. The moment a wider set of input types became visible, the old two-case
   value maker started lying about them; every type now gets a value of its own
   kind.
3. **A decline was only counted in one voice.** ethogram explains a bad pack
   through `alert()`, and the harness — counting only toasts — reported it as
   taking a file and saying nothing. Counting one channel and calling it "nothing
   was said" is the same mistake as counting one kind of control and calling it
   "everything a user can do".
4. **"undefined" in a sentence was read as a value leaking.** ecology-lab writes
   *"R = 0: the estimate is undefined"* as a careful sentence. `NaN` and
   `[object Object]` are never English and still count anywhere; `undefined` and
   `null` now count only where a value belongs — in a readout slot or a form
   control.
5. **`explore` could not back up.** It reloaded by asking the plugin to open the
   page *by kit name*, which no fixture has, so every fixture reported zero paths.
   A `reload` action was published: backtracking must not depend on a client
   knowing where the page came from.
6. **The excluded list had grown a fourth member with a wrong reason** — the one
   this document opens with.

## 6. The numbers

```
SWARM
pages driven                            40
affordances discovered                3571   (3554 before the surface widened)
  verified against an expectation      1975
  WRONG                                  17
  changed, no expectation stated        273   (208 unclassified, 50 declined
                                               and said so, 15 unjudgeable)
  left no trace at all                   32
  never visible                         220
  the harness could not drive             3
  excluded, each with a reason         1051
commands issued                      15474
films kept                              17 of 40

newly reached: checkbox verified 2, hidden 10   file_in verified 1, changed 3
               drop_zone verified 1, hidden 1   chooser verified 1

PROBE
edges     344 fields x 14 values = 4284 entries     16 findings
chaos     2786 random actions, seeded              151 findings
explore   859 paths, 413 leaves, 657 options,        0 findings
          276 distinct states, deepest 14

suite   64 of 64 jobs green, 4457 of 4457 checks passing   (63 / 4415 before)
        verify_swarm     40/40   (28 before; photo, drop, silent-take, checkbox)
        verify_probe     25/25   new
        verify_contract  70/70   (65 before)
```

## 7. Showing it fail

`verify_probe` writes five fixtures and asserts each pass **both ways**: a readout
that goes NaN on a letter is reported and a guarded one is not; a page that breaks
on the third press is found by random pressing, and the finding carries the seed
and the exact actions; the same seed twice gives the same run; a sound page reports
nothing. The tree fixture is a real binary key — 14 nodes, 8 leaves, every node its
own control — and the assertion is not that the walk went in but that it saw **all
fourteen**, reached **depth 3**, and touched **more distinct states than the key has
leaves**. "Explored the key" is a counting claim, so it is asserted as one. A NaN
leaf three levels down is found, with the path taken to reach it and a picture of
it.

`verify_swarm` gains a photo fixture (a file input and a drop zone that name what
they were handed), a page that takes the photo and never says so, and a checkbox
that will not stay ticked — each asserted to be caught by its own oracle by name.

## 8. What is not done

* **No page changed.** Nothing was republished; no staleness is owed.
* **The export/import round trip is not built.** The strongest question to ask a
  pack importer is whether the page's own export comes back in — export, re-import,
  compare. `attach-file` takes fixture names only, so this slice could not ask it.
* **220 hidden is worse than ADR-101's 204** because the surface widened: ten of
  experiment-guide's checkboxes are in a pane no tab opens.
* **The probe passes are not gates**, for ADR-100's reason.

## 9. The worklist

**From the swarm (17):** eleven exports carrying none of the values entered even
after a record was saved; three Adds that add no row and say nothing; two clears
that clear nothing; one Delete that removes nothing.

**From the probe (167):** field-season's 26 uncaught throws and ordination's 2;
farm-scout losing three quarters of its text; ecology-lab's `NaN–∞`; tree-proofs'
NaN; and a long entry breaking the layout of eight pages by 3,400px — the
consequence of ADR-100's dead `white-space` rule, now measured rather than
predicted.

**The front of it is one line of CSS on fifteen pages.** ADR-100 filed it as a rule
that can never fire. It should be filed as the reason a species name too long for a
phone takes the page with it.

**The next prediction, and its falsifier.** field-season throws twenty-six times
under random pressing and ordination twice, and I claim these are the same defect:
a handler reading a selection that chaos has cleared. **I expect that to be wrong —
that they are two unrelated null reads, and that at least one of them also fires on
an ordinary path a user would take, not only under random pressing.** **Falsifier:
replaying both seeds, reading the two handlers, and finding a single shared cause
that only a random order can reach.** The replay is already in the ledger; the
reading is the next slice.
