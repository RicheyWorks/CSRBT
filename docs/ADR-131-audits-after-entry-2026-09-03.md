# ADR-131 — Audits, after entry: the page with its own data in it

**Status:** accepted · **Date:** 2026-09-03 · **Every audit now measures a page in the state its own science task leaves it in — a row built, a species picked, a season filed — and 42 touch-target faults that only exist once there is data are fixed. An entry that drove nothing is itself a fault.**

## 1. What ADR-130 left

ADR-130 took the audits into every state the page can reach **on its own**:
each tab, every `<details>`, the season started, the comparison opened. It
said so in its *Held*: those are the reveals of an **empty** page. Half of an
instrument does not exist until something has been entered — the greenhouse's
`runOut` table, the sheet's analysis with figures in it, the survey's
hierarchy, the relevé's cover editor, every row's remove button. Auditing the
empty page measures the form and never the report.

## 2. The decision

### The entry is the page's own task (`audit_states.enter`)

There is already an artifact that says what "entered" means for each page, in
the page's own vocabulary, kept honest by a ledger: its **science task**
(ADR-128, ADR-129). So the entered state is that task, replayed.

Replayed *in process*, on the browser the audit already has open — the same
`PagePlugin` the gateway drives, without the gateway, without a second child
and a second browser. The task file is the single source of what entering
means, so a task that grows a field grows the audited state with it. What is
replayed is the **entry** only: a read changes nothing, and a task's
expectations are the task runner's business — an audit does not grade a page,
it measures one.

Which task, exactly, matters more than it sounds. Not a reference task (all
reads). Not a **canary** — a task written to be refuted enters what the page
must reject, and the collection sheet's canary was the first thing this picked
up. Not another page's. The science task wins; the suite pins all four rules.

Then every tab is pressed again from there (`entered/pane:<id>`), because the
report a reader goes back to is behind one.

### An entry that did not happen is a fault

`entry_fault` names the case: the plugin would not load, or every step was
refused. Then the states after it were the empty page's wearing the label
"entered", and each audit counts one fault — the ADR-130 rule again, that "I
never measured it" must not print as "it is fine". A **refusal** on its own is
not a fault: a science task drives refusal paths on purpose (the guide refusing
a JPEG, a key with no match), and an audit that called those faults would be
reading the task's intent wrong.

### What the audits found, now that there was data

**Forty-two controls under 44 px**, every one of them rendered only by an
entry, none of them ever measured:

- **survey-design (32)** — every button on a hierarchy node (`copy ID`,
  `remove`) at 38 px; the tree exists only once a design does.
- **stand-sheet (4)** — the per-stem remove `✕` at 40 px.
- **experiment-guide (3)** — a chip's `×` at 32 px, on a chip 36 px tall;
  chips appear only when something has been added.
- **relevé (2)** — the cover editor's C-value box at 40 px.
- **pheno-tracker (3)** — *not* the page's: see below.

And two inputs with **no accessible name** — the relevé's C-value boxes, built
per taxon, now labelled `C-value for <taxon>`.

### Two artefacts of the instrument, fixed in the instrument

Both are the same shape as ADR-130's pointer-click discovery: a measurement
that was about the harness, not the page.

- **Mid-transition geometry.** pheno-tracker's 44 px keys measured 43.99997 px
  under a pane still sliding 0.17 px when the click returned. `audit_states`
  now waits for `document.getAnimations()` to stop running before it measures.
- **The browser's mood, again.** The state walker presses its states with
  `el.click()` precisely to keep Chromium in its keyboard mood, where
  `:focus-visible` paints on programmatic focus. The **entry** cannot have that:
  it drives the page the way a finger does, because that is what entering data
  *is*. The mood flipped and the focus audit reported **1,384** "no visible
  focus" faults that were the entry's pointer. The audit now asserts its own
  precondition — one keypress before every probe, then release it, so the
  question "is focus visible" is always asked of a keyboard user. (Pressing
  without releasing was worse than not pressing: the element the keypress left
  focused shows no change between before and after, and reported itself.)

### The stamp had to stop being a number

The accounting's stamp was a per-pass index (`a0`, `a1`, …), and a control the
entry built part-way down the document took a number an earlier element already
carried: two controls under one stamp is one control as far as coverage is
concerned, and the second silently stops being measured. A monotonic counter
fixes that and breaks something worse — these pages rebuild whole regions with
`innerHTML`, so the *same* control comes back as a new element with a new
number and every state that measured it is forgotten. pheno-tracker went from
106/106 measured to **27/106** on that alone, and the audit reported 79 faults
that were the counter's.

A stamp is now what the element **is**: tag, id, non-state classes, input type,
plus its occurrence among identical siblings. A region rebuilt from the same
template keeps its stamps and its measurements; a control that did not exist
before gets a new one. State classes (`on`, `open`, `active`, `selected`, …) are
stripped — a chip that gains `on` when you pick it is the same chip, and keying
on the class it wears while selected loses every measurement taken before the
click. The label is deliberately not part of it: a value that changes as data is
entered would re-key a control that never moved.

### And the reveals, again

A reveal pressed *before* the entry can be undone by it. The experiment guide's
engineering track is opened by `#track-eng` and closed again when the designer
re-renders, so the six measurement inputs the entry builds inside it had a box
in **no state at all** — reported, correctly, as never measured, by an audit
that had simply not looked again. Every declared reveal is now pressed a second
time after the entry (`entered/state:<sel>`), the way the tabs are.

## 3. Verification

`verify_audit_states` gains **section F** (52 checks, +19): a fixture page whose
row builder produces a button that exists in no state of the empty page, and
four task files beside it — a science task, a reference task, a canary, and
another page's — so "the page's own science task" is a claim the suite can
refute four ways. It pins the state order (the entered states last, each tab
walked again), that the entry drives its three entry steps and skips its two
reads, that the row's button is stamped uniquely, exposed and measured, and
every branch of `entry_fault` — and the stamp itself: that a state class does
not re-key a control, and that a region genuinely re-rendered (its `data-audit`
attributes stripped, the way a page's own template writes it) comes back under
the same stamp.

`mutate_audit_states` **34** mutants (+14): the page never entered, the entered
tabs not walked, a canary or a reference task or another page's task taken as
the entry, the science task not preferred, the reads replayed, the steps not
driven, the reveals not pressed again after the entry, the stamp reduced to a
counter or stripped of its occurrence index, a state class re-keying a control,
and each of `entry_fault`'s three answers inverted.

## 4. Held

- `audit_print`, `audit_offline`, `audit_escaping` still sweep at rest. The
  print audit is the interesting one now: what a filled sheet puts on paper is
  the artifact a field scientist actually keeps, and it has never been measured
  with data in it. Next.
- The entry is one task's worth of data. A page has states beyond it — a full
  sheet, a season at capacity, a refused import left on screen.
- The lab's session station cards still have no ids; `#bRand`, `#bRand10`,
  `#spRand` are not driven.

## 5. First reading

    audit_targets   0 under 44 px or never measured   (every page, every state, entered)
    audit_contrast  0 faults                           (every page, every state, entered)
    audit_focus     0 faults                           (every page, every state, entered)
    verify_audit_states 52 / 52 · mutate_audit_states 34 killed, 0 survived
    kit  77 / 77 jobs, 5,535 / 5,535 checks
