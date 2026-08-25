# ADR-034: Local autosave, and the save that lied

**Status:** Accepted and implemented — `tools/keep.py` v1.0.0 across five pages, FEK at v1.3.0 with a field registry, `tools/verify/verify_keep.py` at 89 checks, canaried against four seeded faults.
**Date:** 2026-08-25
**Deciders:** Richmond
**Supersedes:** nothing. **Touches:** every FEK consumer (the registry), five pages (autosave)

---

## Context

Richmond read the Ordination page's method tab, saw *"it does not save your data — closing the tab loses
the matrix"*, and said that needs wiring. He was right, and the problem was larger than the one page.

Counted before this slice: of thirty-five pages, **one** saved anything. A field worker could fill a
complete relevé — plot, coordinates, twenty species with cover classes — take a phone call, and lose all
of it. Stand Sheet and Collection Sheet the same.

And the one page that did save, saved like this:

```js
function save(){ try{ localStorage.setItem(KEY, JSON.stringify(S)); }catch(e){} }
```

A full quota, a private window, and storage disabled by policy all produce the same result through that
line: nothing saved, nothing said. A user who had watched the page work for an hour had every reason to
believe their data was safe. **A save layer that fails silently is worse than none, because it teaches
trust it has not earned** — which is the same failure this kit refuses everywhere else, sitting inside the
kit.

## Decision

**A shared layer, `tools/keep.py`, inlined by `tools/keep_emit.py` — and honesty as a feature of it.**

KEEP does three things a bare `setItem` does not:

1. **Probes storage at wire time**, so a browser that is not keeping anything says so up front rather than
   at the moment of loss.
2. **Surfaces a refused write.** A full quota now turns the strip red and says *"What is on screen is not
   saved. Export it now."*
3. **States what a browser copy is**, in the page, where the user reads it: one browser, one device, gone
   when site data is cleared. It is recovery from a closed tab. It is **not a backup**, and there is a
   *Forget this device's copy* button next to the sentence.

The exports remain the durable path. That has not changed and the page says so.

### On SmokeHouse

Richmond asked whether this should land in SmokeHouse, the ecosystem's log-structured store. It cannot,
not from here: SmokeHouse is a JVM engine and needs a running process, while these pages are single static
files that must work in a field with no signal — the offline constraint from ADR-031. Wiring them to it
means a server between them, and that stops the kit being a kit. Recorded as a decision, not an oversight;
if durable server-side ingest is wanted, it is a separate slice with a queue-when-offline design.

### FEK v1.3.0: a field registry

Restoring turned out to be only half a job. Every kit component writes *through* to a hidden field via the
page's own `onchange` — fine going out, useless coming back, because nothing could put a restored value
back **into** the widget. The first working restore showed correct data under default-looking dials, which
is a lie on screen and worse than no restore.

So a component may now declare `field:"sElev"`, FEK registers it, and `FEK.setField` puts a value back
through the widget's own `set()`. Purely additive — a component with no `field` behaves exactly as before.
**53 components across six pages** were missing the declaration and are now registered; a kit-wide static
check in `verify_keep.py` asserts that any component writing to a hidden field declares it, so the next one
cannot be forgotten.

## What the verification found

**The forget button re-saved immediately.** The delegated click listener that makes any button press mark
the sheet dirty also fired on *Forget this device's copy*, and the debounced write landed a few hundred
milliseconds later and put the copy straight back. The button appeared to do nothing. Two fixes: `forget()`
cancels the pending timer, and the page listeners ignore events from inside the strip.

**The quota test was not testing anything.** Filling storage with 200 KB blocks stops at the first refusal
and leaves enough room for the page's own small blob, so the failure path never ran and the check passed
for the wrong reason. It now fills with large blocks, then medium, then small, until even a tiny write is
refused.

## And a bug that had been sitting there

`tools/fek_emit.py` **had never written the CSS**. It defined a `CSS_RE` and a `block_bounds()` helper, and
`main()` called neither: the stylesheet half of the regenerator was dead code from the day it was written.
Every bump to `fek.CSS` since has silently failed to reach a single page. Found because v1.3.0 left all
fifteen pages' CSS banner reading v1.2.0.

Worse than the dead code was what it hid. The WCAG AA contrast fix had been applied to the *pages*, by
hand, and never came back to `tools/fek.py` — which still held the three pre-fix ramp colours. Source and
pages agreed only by accident. **The moment the emitter was repaired it pushed the failing colours back
into all fifteen pages**, and `verify_contrast_slice` failed on all three within seconds. That suite is the
reason this is a paragraph in an ADR rather than a contrast regression in production.

The boundary is no longer guessed by a lookahead. It runs from the banner to the end of `fek.CSS`'s own
last rule; a page that does not contain that rule is reported rather than guessed at.

Three more frozen constants fell in the same pass — `verify_escaping_slice` and `verify_contrast_slice`
each froze `"1.2.0"` and *"exactly 14 consumers"*, and seven pages carried hand-written prose comments
naming a FEK version they could not keep current. That is the seventh, eighth and ninth this month, and the
pattern is now well enough established to state as a rule: **an assertion that a legitimate change breaks
is not a test, it is a future ignored failure.**
