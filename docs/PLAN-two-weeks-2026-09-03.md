# Two weeks, for the next operator

**Written:** 2026-09-02, at the end of ADR-130 · **For:** a Claude Opus session
picking this program up · **Scope:** ten working days, one slice a day, each
shipped the way every slice in this repo has been shipped

You are continuing the CSRBT harness. Read this file first, then
`docs/AI_HARNESS.md` (what exists), then `docs/AUTOMATION-HARNESS.md` (how it
works), then the last three ADRs (128, 129, 130). Do not read the whole kit
before starting; read the slice's subject.

---

## 0. The standing goal

> The harness has to be able to **operate everything** — especially every user
> interface for data entry, especially in the science pages — and everywhere
> needs serious audits: it must be able to enter all the data, and the reports
> must be correct.

Everything below serves that sentence. When a choice is unclear, pick the one
that makes the harness able to drive more of the kit, or able to catch a wrong
number it currently cannot.

**Do not stop to ask.** Establish the slice, build it, verify it, deliver it,
start the next one. If you find yourself with a question, answer it the way the
last thirty ADRs answered it and write the reasoning into the ADR's *Held*
section.

---

## 1. House rules — these are not negotiable

1. **No stubs, no sketches, no "you could add".** Every file you write is
   complete and runs. If a slice is too big for a day, cut its scope, not its
   finish.
2. **A number a tool can compute is never typed.** Every expectation in a task,
   every figure in an ADR, comes from an oracle you wrote in Python (or from the
   suite's own output pasted verbatim). Agents' hand arithmetic has been wrong
   in this repo *every single time* it was trusted — breeding ΔF, the card days,
   the greenhouse percentage, χ² critical values, Hardy–Weinberg p. Write the
   oracle, run it, use what it says. If the oracle and the page disagree, that
   is a finding, not a nuisance: find out which is right before you write either
   number down.
3. **Every suite gets a mutant runner.** A check nobody can break is a check
   nobody is running. `tools/mutate_<x>.py` breaks the subject on purpose N ways
   and requires the suite to notice each, naming which check must kill it.
   `SURVIVED` is a defect in the suite, not a curiosity.
4. **An audit that measured nothing must never print as clean.** This has bitten
   the repo twice (ADR-106's hardcoded path; ADR-130's at-rest audits). Any new
   finder counts what it could not reach and reports it as a fault.
5. **Git is host-side.** You cannot write `.git` from the sandbox. Every slice
   ends with a delivered tarball and a PowerShell script Richmond runs himself.
6. **Terse replies.** He is reading output, not prose. One or two sentences on
   what shipped, then the push line.

---

## 2. The ritual that ends every slice

Do all of it, in this order. A slice is not done until the push line is printed.

```bash
cd /home/claude/eco/CSRBT

# 1. the suite, and its mutants
python3 tools/verify/verify_<slice>.py
setsid nohup python3 tools/mutate_<slice>.py > /tmp/mut.log 2>&1 &

# 2. docs: the ADR, the changelog, and the two harness docs
#    docs/ADR-1NN-<slug>-2026-09-NN.md      -- decision, evidence, Held, First reading
#    docs/CHANGELOG-2026-09-NN-adr1NN-<slug>.md
#    docs/AI_HARNESS.md    -- one paragraph at the top of the ADR list
#    docs/AUTOMATION-HARNESS.md -- the Verification section

# 3. if any docs/*.html changed: rebuild, republish, stamp
python3 tools/publish.py
#    republish each changed page's artifact from build/publish/<page>.html
#    (subagent per page: Artifact action:"read" the url, read the local file in
#     <=450-line chunks, then publish with that url; no favicon, no title)
python3 tools/publish_state.py --stamp <pages...>
python3 tools/publish_state.py            # must read "N current, 0 behind"

# 4. the whole kit, in the background (~15 min, do NOT foreground it)
setsid nohup python3 tools/verify/run_all.py -j 3 > /tmp/run_all.log 2>&1 &

# 5. the board, republished from the ledgers run_all just wrote
python3 tools/harness_board.py
#    republish tools/harness_board.html to artifact d1e5e7fd-99ed-4431-8f19-64e907fe900b

# 6. the bundle and the push script
tar -czf /tmp/adr1NN.tgz -C /home/claude/eco <the changed paths, relative to projects/>
#    write push-adr1NN.ps1 chaining the previous ADR's script
#    SendUserFile the tarball and the script; commit them to
#    C:\Users\730ri\projects\_to_delete\ and extract host-side when the bridge is up
```

Then print exactly one fenced line:

````
```
cd C:\Users\730ri\projects ; .\push-adr1NN.ps1
```
````

And append what you learned to memory `/areas/csrbt-harness.md` (read it first
for the version token).

**Background jobs.** A `Bash` call that blocks longer than two minutes is killed
and takes its children with it. Anything long — `run_all`, a mutant runner, a
`--page all` walk — starts with `setsid nohup ... &` and is polled with
`sleep 90; tail`.

---

## 3. Where things stand on day 0

| | |
|---|---|
| Kit pages | 41, all routed, all walked, all published as artifacts, 41 current / 0 behind |
| Tasks | 44 page tasks (27 science with independent oracles, 14 reference, a read-back, a canary), 1,807 expectations confirmed |
| Harness | gateway contract 1.3, stdio + MCP transports, robot (`harness_walk`), tasks (`harness_tasks`), page plugin with 17 actions |
| Audits | targets, contrast, focus — every state of every page, 0 faults; frontend, escaping, print, offline — at rest |
| Mutants | eight runners, all killing 100 % |
| Board | `tools/harness_board.py` → artifact `d1e5e7fd-99ed-4431-8f19-64e907fe900b` |

The last three slices: **ADR-128** gave the harness a reader (`read-report`) and
a picker (`pick`); **ADR-129** gave every routed page a task; **ADR-130** took
the audits into every state of every page and found 35 defects plus three pages
of dead CSS.

---

## 4. The ten slices

Each one is a day. Each has a subject, an oracle, a suite, a mutant runner, and
a delivery. **Do them in this order** — later ones lean on earlier ones. If a
slice finishes early, start the next; if one runs long, finish it tomorrow and
push the rest down. Do not skip a slice to get to a more interesting one.

---

### Day 1 — ADR-131: audits after entry

**Why.** ADR-130's states are the page's own reveals, *before any data exists*.
The greenhouse's `runOut` table, the collection sheet's analysis, the season's
recap: the audits measure them empty. A 44 px button that only appears in a
built row, a contrast fault in a rendered figure, a focus trap in a chip that
only exists after you type — none of these can be seen yet. This is the named
successor in ADR-130's *Held*.

**Build.** Extend `tools/audit_states.py` with an `entered` state: for a page
that has a science task, run that task's entry steps through the page plugin
(reuse `harness_tasks`'s runner — do **not** re-implement entry), then yield
`entered` and walk the tabs again from there (`entered/pane:<id>`). Pages with
no task keep today's states. The accounting must still reconcile: a control
that exists only after entry counts as exposed, and one that never appears in
any state — entered or not — is still a fault.

**Oracle.** None needed; the task files are the oracle for what to enter.

**Suite.** Extend `verify_audit_states.py`: the fixture grows a row-building
form; `entered` reaches a control that has no box before entry; a page whose
task fails to run is `NOT VERIFIED`, never silently skipped (ADR-104's rule).
Add mutants to `mutate_audit_states.py`: entry skipped, entered state not
walked for tabs, a failed task reported as a clean audit.

**Expect to find defects.** Budget half the day for fixing pages. Every one you
fix is republished and stamped.

---

### Day 2 — ADR-132: `excludes`, and saying what is absent

**Why.** The task grammar (`tools/harness_tasks.py`) has ops
`== != > >= < <= in contains exists` and no way to say *does not contain*. A
task that wants to assert a page stopped printing a warning has to guess what
replaced it. ADR-128 held this deliberately: "added when a task needs it, with
its mutant." Several tasks need it now — the refusal paths especially.

**Build.** Add `excludes` (and `not-in` if it falls out naturally) to the op
table, with the same DEFECT messages as the rest when the reference is missing
or the type is wrong. Then *use* it: convert at least six existing expectations
that currently assert a replacement string into direct absence assertions, and
add the refusal-path assertions that were impossible before (the experiment
guide's JPEG refusal, the keys' no-match conflicts, `pick`'s ambiguity refusal).

**Suite.** `verify_tasks.py` section A gains the op's grammar; section G re-pins
the converted tasks. Mutants: the op inverted, the op accepting a non-string,
the op silently passing on a missing reference.

**Ledger.** Re-run `--target page`; the confirmed count moves. Put the new
number in the ADR from the ledger, not from memory.

---

### Day 3 — ADR-133: a task with two targets

**Why.** ADR-125 held it: "a task that needs two targets — write through the
organism, look through a page — has no shape yet." That is the shape of every
real operator workflow, and until a task can do it the harness cannot stand in
for one.

**Build.** A task file gains an optional per-step `target`. The runner opens
each named target's session once, keeps them for the task's life, and closes
them in reverse order; references (`@1.field`) resolve across targets. The
grader is unchanged — an expectation is still graded against the response it
names.

**Write two of them.** One that writes a batch through the organism and then
reads the fixture page's rendering of it; one that runs a lab protocol and holds
the science page's report to the lab's own session numbers. The second is the
better test: two independent instruments must agree, and if they do not, one of
them is wrong and you have found something.

**Suite + mutants.** Sessions leaked, sessions closed in the wrong order,
a reference resolved against the wrong target, a step's target silently
defaulting to the task's.

---

### Day 4 — ADR-134: the clocks, the dice and the dialogs

**Why.** ADR-128 held this list on purpose, and it is now the largest undriven
surface in the kit: the ethogram's time budget, the ordination's `Date.now()`
NMDS seeds, the greenhouse's demo log read against a real clock, `confirm()` on
every Clear button, and `#bRand` / `#bRand10` / `#spRand` (`Math.random`). Five
pages have behaviour no task can reach and no audit can measure.

**Build.** A determinism protocol in the page plugin, installed as an init
script before the page loads (`ctx.add_init_script`, the way `harness.STUBS`
already stubs the network): a frozen `Date.now()`/`new Date()` the task sets, a
seeded `Math.random` (mulberry32 — the port already exists in `/tmp/season.py`
from ADR-129; move it into `tools/` as a real module this time), and
`window.confirm`/`alert` answered by policy with the answer recorded on the
observation so a task can assert *that a dialog was raised*.

**This is a contract change.** The plugin publishes new actions
(`set-clock`, `set-seed`) — so `harness_contract.py`'s manifest, the risk table,
`verify_contract.py`'s "every action the swarm drives with is one the plugin
publishes" check, and both transports all move together. Bump the protocol
version and say so in the ADR.

**Oracle.** Port the seeded generators to Python and compute what the pages must
print. Do not read the numbers off the pages and call them expectations — that
is a screenshot, not a test.

**Then drive them:** new expectations on ethogram, ordination, greenhouse,
tree-visualizer and tree-proofs for the paths that were unreachable.

---

### Day 5 — ADR-135: the lab's stations, named

**Why.** Held since ADR-129: the interactive lab's session station cards have no
`id`s, so their figures collide under `#main` in `read-report`'s `by` map, and
the science task reads the workbench and the terrarium only. Part of the page —
the part a student actually walks through — is unheld.

**Build.** Give each station card a stable `id` in `docs/ecology-lab.html`
(`station-<slug>`, matching the protocol's own station names), then extend the
lab science task to hold every station's figures against the lab engine's
shipped session. The engine already computes them; `verify_lab.py` has the
canonical oracle. Where the page and the engine disagree, the engine is right
until proven otherwise — investigate before you change either.

**Careful:** an `id` change can move `read-report`'s box detection. Re-run
`verify_report.py` and the page walk, and republish the page.

---

### Day 6 — ADR-136: the blind trial

**Why.** ADR-126 shipped the instrument (the MCP server records a trace; the
grader holds a trace to a task) and said plainly that it was **not a blind
trial**: the assistant that ran it had written the tasks. The provenance file
says so. That honesty is the reason this slice exists — the instrument's whole
claim is "a model that has never seen these tasks can operate the kit through
the door", and that claim is untested.

**Build.** Run it properly. A subagent with **no** access to `tools/tasks/`, no
prior context from this session, given only: the MCP endpoint, `tools/list`, and
each task's `goal` sentence in words. Record the trace. Grade it. Publish the
result *whatever it is* — a 3-of-8 that names each miss and whose fault it was
is worth far more than a 8-of-8 you helped.

**Then fix the instrument, not the score.** Every miss is a hypothesis about
the harness: an action whose description does not say what it does, a manifest
that does not publish an argument's shape, a refusal whose message does not tell
the operator what to do instead. Fix those, re-run, and report both numbers.

**Write the provenance file** the way ADR-126 did: what the operator could see,
what it could not, and who wrote the tasks.

---

### Day 7 — ADR-137: `listChanged`, with a consumer

**Why.** Held twice (ADR-115, ADR-121): the MCP transport declares notification
capabilities it has never sent, because nothing consumes them. A capability that
is advertised and never exercised is a lie the manifest tells.

**Build.** Either send them with a real consumer — the robot subscribes, a
target's tool list changes mid-session (a page navigates, a plugin's actions
change with policy), the robot notices and re-reads — **or** stop advertising
them and say why in the ADR. Both are honest; only silence is not. Prefer the
first: `harness_walk` re-reading a tool list after a page changes is exactly the
"robots plugged into the harness" story this program is for.

**Suite.** `verify_mcp.py` gains the notification round-trip; mutants for the
notification never sent, sent to the wrong session, sent without the capability
declared.

---

### Day 8 — ADR-138: what the reader actually sees

**Why.** `publish_state.py` distinguishes *stamped at publish time* (we believe
the bytes match) from *measured from the live page* (we fetched the artifact and
checked). Today: 22 stamped, 19 measured. For 22 pages, a green audit of `docs/`
is a claim about a file, not about what a reader gets.

**Build.** Make measurement the default, not the exception: a checker that
fetches every mapped artifact and compares to `build/publish/<page>.html`, byte
for byte, reporting the diff's shape when they differ. Wire it into
`verify_publish_reach` so an unmeasured page is a hole in the count (`NOT
VERIFIED`), never a pass. Then measure all 41 and fix what disagrees.

**Expect** the board's own artifact to be behind — ADR-127 held that it is
republished by hand. Bring it into the same checker.

---

### Day 9 — ADR-139: the engines, ratcheted forward

**Why.** Fourteen Java repos sit under the same roof and the harness's
relationship to them is a read-only ledger (`ecosystem.py --read`,
`verify_ecosystem.py`, the Atlas). `verify_engine_sessions` reports `NOT
VERIFIED` on any machine without a built engine — which is most runs, so the
count carries a hole nobody has closed.

**Build.** Two things. First: make the ecosystem ledger *ratchet* — a suite's
test count may rise and may not fall, and a fall is a failure naming which
engine and by how much. Second: close the `NOT VERIFIED` hole where it can be
closed — a cached session fixture, checked in, that lets the engine-session
suite run without a JDK, with the live path still preferred when the engine is
there. Say precisely which checks remain holes and why.

**This is the one slice where the sandbox may not have what you need** (Gradle
9 wants JVM 17+). If the JDK is absent, build the ratchet and the fixture path,
declare the live path `NOT VERIFIED` honestly, and move on. Do not fake a green.

---

### Day 10 — ADR-140: the charts, read

**Why.** ADR-128 held it: "SVG text and geometry are outside `read-report`; the
suites that check them keep doing so with Playwright." Every page that draws —
ordination's NMDS, the food web, the survivorship curves, the tree visualizer —
publishes numbers to the reader that no task can hold. A chart that plots the
wrong series looks exactly like a chart that plots the right one.

**Build.** Extend `read-report` with a `charts` section: per `<svg>`, its `text`
nodes with their positions, its series' point counts, and each axis's tick
labels in order. Cap it the way everything else is capped (16 charts × 40 texts).
Then hold at least four charts to oracles: the tick labels, the point count, and
the position of a named point against a Python recomputation of the same
projection.

**Suite + mutants.** `verify_report.py` gains a chart fixture; the mutants break
the reader (text dropped, ticks unordered, series miscounted). Re-run every page
task — `charts` is new output on every read, and the read-back canary must still
refute.

---

## 5. If you finish all ten

In priority order, all of them long-held:

- **A mutant runner for the page plugin's walk** (ADR-124: "a runner over a page
  walk would cost a browser per mutant" — it is affordable now that the suites
  run in-process).
- **Every page over MCP**, not just the fixture and the organism (ADR-124).
- **Timing as an expectation** — an op's `ms` graded against a bound, with the
  flake analysis to justify the bound (ADR-125).
- **`audit_print`, `audit_offline`, `audit_escaping` per state** — ADR-130 left
  them at rest because they are about the document; check whether that is still
  true after Day 1.

---

## 6. Things that have gone wrong before, so they do not go wrong again

- **A path that exists in one container.** `audit_targets` read `/tmp/eco/...`
  for weeks and reported a clean audit of zero pages. Derive every path from
  `__file__`. Finding nothing is a loud failure.
- **A pointer click where a programmatic one belongs.** Real mouse clicks make
  the browser hide focus rings on programmatic focus; the focus audit reported
  1,461 faults that were the mouse's. `pg.evaluate("(el) => el.click()", el)`.
- **A suite that silently stops voting.** `mutate.py` skips fixture-builders;
  a suite that reaches for `tempfile` must declare `MUTATE_ROLE`.
- **A score line that hides a hole.** A suite that cannot reach its subject
  prints `NOT VERIFIED:` and counts the check in its denominator. Never pass,
  never quietly skip.
- **The board rendered but not republished.** It is a hand step; do it, or the
  numbers Richmond looks at are last week's.
- **`pkill` matching your own shell.** It has killed the session twice. Match
  narrowly or do not use it.
- **Trusting your own arithmetic.** See rule 2. It has never once been right.

---

## 7. The one-line summary of every day

> Find the thing the harness cannot yet do, make it able to do it, prove it with
> an oracle it cannot fake, break the proof twenty ways to show it holds, write
> down what is still held, and ship it.
