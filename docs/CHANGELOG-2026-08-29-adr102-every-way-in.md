# 2026-08-29 — ADR-102: every way into the kit, and three ways to break it

Companion to `docs/ADR-102-the-harness-had-never-touched-the-camera-2026-08-29.md`.

## Four surfaces no harness had touched

| surface | how many | what the harness did |
|---|---:|---|
| `input[type=checkbox]` | 12 | no kind's selector matched — invisible |
| `input[type=time]` | 1 | the text kind listed three types; not this one |
| `input[type=file]` | 5 | **excluded on purpose**, with a wrong reason |
| drop zones | 3 | no CSS selector finds one — never driven |

ADR-101 excluded file inputs because "a file chooser needs OS focus". That
confused the native **dialog** with the act of **handing a page some bytes**. The
dialog is still out of scope and never opens; the bytes were always ours to supply.
Behind that sat the kit's only photo entry.

## Photo and drone entry, wired

* **Eight real fixture files made in the harness** — JPEG, PNG, WebM, JSON pack,
  `.eco`, CSV, and a corrupt file. A run reads nothing of the operator's disk. One
  is `DJI_0192.JPG`, because a page that keys on a filename should be driven with a
  filename somebody will really hand it.
* **Hidden file inputs are driven** — three of the five are `display:none` with a
  camera or Load-pack button in front of them.
* **Drop zones are found by wrapping `addEventListener`** and stamping the element
  as the drop listener registers. No selector can find one otherwise.
* **The chooser-opener is verified against what it does** — `HTMLInputElement.click`
  is wrapped, so the dialog never opens and the request is counted. `📷 Add photos`
  was a false finding in ADR-101's eighteen; it is verified now.

```
stand-sheet  file_in    verified   IMG_0431.jpg, DJI_0192.JPG named on the page
stand-sheet  drop_zone  verified   IMG_0431.jpg named on the page
stand-sheet  action_btn verified   opens the file chooser
```

**A real defect, read against the source.** stand-sheet's photo drop zone discards
anything that is not an image in silence — `if(!/^image\//.test(f.type)) return;`
and `if(added)` gates the only message it gives. Drop the drone's flight log beside
its frames and the frames appear and the rest is gone without a word.

**Video:** no page in the kit takes one. Rather than invent a surface, the harness
carries a `.webm` fixture so a page that *should* refuse one can be shown refusing
it — which is how the silent discard above was found.

## The harness records what it did

Every page run is filmed at 390×844 and a still is taken in the state each finding
was reported in. A film is kept only where there is something to watch — **17 of 40
pages**; the rest are deleted.

## `tools/probe.py` — edges, chaos, every path

No per-control expectation, only invariants: *is this still a page, and did it say
something when it refused*.

```
edges     344 fields x 14 values = 4284 entries      16 findings
chaos     2786 random actions, seeded               151 findings
explore   859 paths, 413 leaves, 657 options,         0 findings
          276 distinct states, deepest 14
```

A chaos finding carries the **seed and the exact list of actions**, so it replays
rather than being retold. `explore` backtracks by reload-and-replay, because a page
has no obligation to be reversible.

### What they found

* **field-season throws 26 uncaught TypeErrors** under random pressing; ordination
  throws twice.
* **farm-scout loses 76% of its rendered text** after a particular sequence.
* **ecology-lab renders `NaN–∞`** in a readout on an edge value.
* **A 400-character entry breaks eight pages' layout by 3,400–3,700px.**

That last closes a loop: ADR-100 found `.row2 .g span` declaring
`text-overflow:ellipsis` with no `white-space:nowrap` on fifteen pages — a rule
that can never fire. This is what it was for. Ethogram's `div.row2` measured
**3,092px** under chaos and `div.g` — the element whose text was meant to be
truncated — **3,010px**, on a 390px phone.

## Six defects, all the instrument's

| what it did | why it was wrong |
|---|---|
| tested 3 of breeding-bench's 14 fields | filtered on visibility recorded before any pane was opened; now 196 values instead of 42 |
| said deployment-log threw an entry away | a `type="time"` field handed a text sentinel — the browser discards it before the page sees it |
| said ethogram took a file and said nothing | ethogram says it with `alert()`; the harness counted only toasts |
| said a value leaked "undefined" | it was English: *"R = 0: the estimate is undefined"*. NaN and `[object Object]` count anywhere; `undefined`/`null` only in a value slot |
| explore reported zero paths on every fixture | it backtracked by re-opening the page *by kit name*; a `reload` action was published |
| excluded file inputs | the dialog is not the bytes |

## Showing it fail

`verify_probe` (25) asserts each pass both ways. The tree fixture is a real binary
key — 14 nodes, 8 leaves — and the assertion is that the walk saw **all fourteen**,
reached **depth 3**, and touched **more distinct states than the key has leaves**,
then found a NaN leaf three levels down with the path and a picture of it.

`verify_swarm` (40, was 28) gains a photo fixture, a page that takes the photo and
never says so, and a checkbox that will not stay ticked.

## Suite

```
64 of 64 jobs green, 4457 of 4457 checks passing   (63 / 4415 before)
verify_swarm     40/40   (28 before)
verify_probe     25/25   new
verify_contract  70/70   (65 before)
```

## The worklist

**Swarm (17):** eleven exports carrying none of the entered values after a record
was saved; three Adds that add no row and say nothing; two clears that clear
nothing; one Delete. **Probe (167):** the throws, the lost text, the NaN readouts,
and the layout breaking on a long name. **The front of it is one line of CSS on
fifteen pages** — no longer a tidiness defect, but the reason a long species name
takes the page with it.
