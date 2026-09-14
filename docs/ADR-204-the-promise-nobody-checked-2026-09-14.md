# ADR-204 — The promise nobody checked

**KEEP prints the only sentence in this kit that a reader takes as a promise: *Saved on this device.* It has 112 checks and no mutant runner, so nothing had ever shown that a single one of them can fail. Breaking it on purpose found that its most important sentence — the one it exists for — was asserted by nobody, and that three of the eight pages carrying the layer were never opened by its suite at all.**

## 1. Why this suite, and why now

KEEP replaced a `try{ localStorage.setItem(...) }catch(e){}` that swallowed
every failure. A full quota, a private window and storage disabled by policy all
produced the same result — nothing saved, nothing said — and a user who had
watched the page work for an hour had every reason to believe their data was
safe.

If the checks that hold KEEP to doing better are themselves asleep, the kit has
not fixed that. It has replaced a silent failure with a silent failure that
prints a reassuring sentence, which is worse, because the sentence is believed.

Every other instrument in this kit has a runner that breaks its subject on
purpose. ADR-201 closed that gap for the entry layer; ADR-203 opened the outbox
with one. This closes it for the layer that makes the promise.

## 2. What the mutants found

**The sentence nobody checked.** Make `usable()` return `true` without probing —
the single most plausible regression in the file — and *no check failed*. A
browser keeping nothing would have gone on saying "Autosave is on" until the
first write failed, which on a page in a private window is never, because the
write fails at once and reads as a *refused write* rather than as *this browser
is not keeping anything*. Those are different sentences calling for different
actions, and only one of them is true in a private window.

The suite's own comment, eighty lines further down, **describes** that behaviour
— and then uses it to explain a different check. Prose about a behaviour is not
a check on it.

**Three pages the suite never opened.** `keep_emit.py` inlines KEEP into eight
pages; this suite listed five. The deployment log, the survey design and the
greenhouse carried the autosave layer and nothing here ever loaded them. That is
ADR-141's defect again — a list only one reader reads — so the list is now the
emitter's, and a page wired tomorrow is covered tomorrow. All three were fine,
which is the good outcome and not the point.

**Two more behaviours with no test.** A tab hidden or closed inside the
half-second debounce must flush rather than lose the last edit — the exact case
this component exists for, never driven. And a restore the page *refuses*
(`restore()` returning `false`, or throwing) must not be announced as one:
"Restored your work from today 09:14" over a sheet that is still empty would be
the worst sentence this component could produce.

## 3. What is checked now

`verify_keep` 112 → 151.

- A browser that throws on the `localStorage` accessor itself: the strip says it
  is keeping nothing, says to export instead, is styled as the failure it is,
  and `KEEP.usable()` answers honestly — at page open, not at first write.
- A `pagehide` inside the debounce window writes the pending edit.
- A refused restore announces neither a restore nor a save.
- All **eight** consumers, from the emitter's list, and each must have written
  **nothing at all** before anything is entered — not "nothing under one known
  key", which a renamed key would pass by writing somewhere the suite was not
  looking.

`mutate_keep`, 23 mutants, all killed: the probe that assumes, the swallow that
comes back, the classifier that stops classifying, both escapes dropped, the
format stamp and the timestamp left off, the format guard removed, `JSON.parse`
unguarded, the "not a backup" sentence and the forget button removed, forget not
cancelling its own pending write, the snapshot taking one field, the FEK bridge
disabled and its guard inverted, the flush not wired, a refused restore
announced, and — in `keep_emit.py` rather than `keep.py` — a page dropped from
the list the suite reads.

## 4. And three faults in the suite itself

A runner's first run is an audit of the suite, not of the subject, and this one
returned three.

**Two mutants survived a suite that looked complete.** Removing the `try` around
the stored blob's parse left every check green — "unparseable storage does not
break the page" was passing because the *first* version of that mutant replaced
`JSON.parse` with an `eval` that throws inside the same guard, which is not the
same edit. And a `restore()` that **threw** was announced as a restore, because
the check drove a restore that returned `false` and never one that blew up. Both
gaps are closed, with a check each.

**One mutant crashed the suite instead of failing it.** Remove the forget button
and `verify_keep` timed out reaching for it: no pass, no fail, just a fallen
instrument. A sweep should be told what it broke. The press is now conditional
on a check that the button is there.

## 5. One thing worth writing down

Two mutants are also caught by the suite's **source-shape canaries** — the
checks ADR-063 added to hold `lastErr` to string literals we chose. A mutation
that rewrites those assignments trips them before it reaches a browser. That is
not noise: it is evidence those canaries are load-bearing rather than decorative,
which is exactly what a runner is for.

## 6. What this does not do

**It does not test the restore of every page's state shape.** The suite drives
relevé end to end and holds the other seven to loading clean, mounting the strip,
and saving nothing on a blank sheet. A page whose own `restore()` silently
dropped half its records would pass. That is a per-page suite's job, and it is
filed rather than claimed here.
