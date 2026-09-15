# ADR-210 — A page with your work already in it is a page nobody had ever looked at

**ADR-207 gave seventeen pages an autosave, so that closing a tab stops costing a morning. It also created a state of every one of those pages that nothing in this harness had ever measured: the page as it comes back. 125 things those pages said before the tab closed, they did not say when it came back — a greenhouse's entire reading log, a relevé's point-intercept transect and every wetland indicator in it, a stand sheet's loaded species packs, a collection sheet's herbarium labels, an ordination's stress and verdict, a κ that two observers' sequences were still sitting above.**

## 1. The audits measure the page in front of them

Open a page, replay its task, look. A restored page is built by a different
path — `restore()`, running against a blob, in whatever order that function
happens to paint — and no audit walks it.

ADR-207 found one instance by hand: the experiment guide's restored design came
back without its measurement rows, because those rows are built from what is in
two boxes and the paint ran before the boxes were filled. One page, found by
looking. Nothing checked the other sixteen.

`tools/audit_restored.py` opens the page, replays its task, **flushes** the
autosave rather than waiting on it, reloads onto the same storage, and compares
two readings of `read-report`: every named figure and its value, every named
block and its prose. What the page publishes — not a list here of what each page
ought to bring back, which would be one more list to keep in step with
seventeen pages.

A loss is a key that went **or a value that changed**. Both, because a relevé
that came back with a 13 m coordinate uncertainty where 43 m had been typed has
lost nothing a key count could see — and lost it in the direction that makes a
record look better than it is.

## 2. What was going missing

**The snapshot was a second list.** Every page enumerates its own state by hand
for the autosave, and everything the page grew afterwards was silently not kept:

- **greenhouse** — kept the saved *runs* and not the **reading log the runs are
  built from**, nor the yield, rated wattage, tariff, lux reading or
  photoperiod. Close the tab: the environment analysis, the light integral, the
  electricity cost and the log table all came back empty while the strip said
  the page had been restored.
- **relevé** — kept records, scale and photographs. Not the **vouchers**, not
  the **LPI transect**, not the **wetland indicator per species**. The wetland
  analysis said *"no indicator statuses entered"* over a sheet that had four.
- **stand sheet** — kept stems and intercepts. Not the **species packs** a
  reader had pasted in, so the key filter, the tally list and the *"species
  loaded"* tile all reported the kit's own shipped numbers over a morning of
  somebody else's data.
- **collection sheet** — kept collections. Not the **herbarium labels** made
  from them: *"No labels yet."*
- **pheno tracker** — kept the run. Not the boxes beside it: the segregation
  counts and the cross being tested.
- **breeding bench** — kept the roguing log and the yield trial, and **nothing
  typed into eighteen FEK controls**, because not one of them declared a field.

**And the repaint was a second list too.** cp bench painted six panes of
thirteen; field notebook brought the quadrats back and not the Morisita index;
ordination brought the matrix back and **not the ordination** — the stress, the
verdict, the scree and Shepard notes, all blank over a sheet that had them. *A
restore that brings the data back and not the answer has brought back the half a
person can re-derive and left the half they were reading.*

## 3. A control that writes to nothing is a control the autosave cannot see

`verify_keep` has a rule for this: *every write-through component declares its
field*. It reads a page's components and flags any that `push()` to exactly one
hidden input without declaring `field:`. A component that pushes to **nothing**
is invisible to it — and that is what eighteen of the breeding bench's controls
were. **The rule was enforced over the components that already write.** ADR-204,
ADR-205, ADR-207 and ADR-208 in turn; a sixth time.

The answer this slice takes is not a better list. It is to **stop enforcing the
rule over a list and measure the outcome**: what the page said, and what it says
coming back.

**FEK 1.7.0** gives the registry a way out as well as in — `FEK.values()` reads
every registered widget through its own `get()` — and **KEEP 1.4.0** captures
the registered fields the DOM walk did not find, and puts them back through
`setField` on restore. So a control declares `field:"selN"` and is kept, with no
hidden input to remember to write to.

## 4. Two orderings that cost a morning each

**A restore that runs before the boot paint is repainted over it.** And on pages
that rebuild their entry controls from their own records — the cp bench's plant
picker, the selection log's trait chips — **a value restored before that rebuild
is one the rebuild replaces with its default**, so the report card came back
drawn for the wrong trait and the collection analysis for the wrong plant.
Restore the values, paint, restore the values again. Ugly, and true of a page
that builds its controls out of its data.

## 5. What is supposed to come back different, and says so

Three blocks exist to say **what just happened** — the autosave strip, the
outbox strip, the toast — and a reload is a thing that just happened. A pane is
a container and changes when anything inside it changes; what is inside it is
compared on its own. Those are named in the audit with a reason each, because a
rule that called them losses would be switched off within a week, and then the
analyses that really do go missing would be invisible again.

Nine more are declared per page, each with its sentence: a pack loader's verdict
on the last paste, a session clock, a voucher label that regenerates from the
record and comes back with *more* than it had.

## 6. What is checked

`verify_restored` 25, over four fixtures built from one template that differ
only in what they keep and what they repaint: one whole, one that leaves its
records out of the snapshot, one that leaves the typed note out, and one that
keeps everything and repaints half of it. Plus a fifth whose restore refuses the
blob, because **a reading taken from a page that never came back is about the
instrument**. The fixture's boot paint runs *before* the autosave is wired, as
it does on every page of this kit — a restore with the whole page repainted over
it by a boot line further down would hide the defect the fixture exists to show.

`mutate_restored` 19. The pages walked are the emitter's list, so a page wired
tomorrow is measured tomorrow.

## 7. What stands

**0 of 552.** Every figure and every block that these seventeen pages publish
before the tab closes, they publish when it comes back. Seventeen pages carry a
ceiling of zero.
