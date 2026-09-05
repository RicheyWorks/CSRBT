# ADR-141 — The door that could not press a button: a declared risk is a floor

**Status:** accepted · **Date:** 2026-09-04 · **Four blind operators, given one science page each and a supervised session — `SENSITIVE_READ`, `DRAFT`, `MUTATE`, no `DESTRUCTIVE` — independently found the same thing: this harness could fill every field on a data-entry page and commit none of them, because every button on these pages is pressed through `activate` and `activate` was `DESTRUCTIVE`. Protocol 1.5 makes a declared risk a FLOOR: an action may declare `mayRise`, and the target that knows what the selector resolved to raises the call — never lowers it — with a reason the response carries. Five more findings from the same trial are fixed with it**

## 1. What four operators found

ADR-136 ran the first blind trial and it worked: every miss turned out to be a
defect in the instrument, not in the operator. This is the second, pointed at
the pages this harness exists for. Four general-purpose subagents, fresh context
each, working in a checkout with `tools/tasks/`, every ADR, every changelog and
both harness guides **removed from the filesystem**, each given one task's goal
sentence verbatim and `tools/blind_console.py` with the rungs a supervised
operator gets. The traces are in `tools/traces/blind2/`, with the conditions.

They converged, without seeing each other's work:

> *"The door as specified cannot press a button."*

Every control on a science page — *Add stem*, *Record collection*, a dial
option, a behaviour key, a chip — is pressed through `activate`. `activate` was
`DESTRUCTIVE` (ADR-112), for an honest reason: a selector may resolve to *Add
row* and the next one to *Clear trial*, and deciding which from a label was
called a guess. But `DESTRUCTIVE` is the wipe-the-store rung, and a supervised
session does not hold it. So:

- the `pheno-tracker` operator refused to escalate, and reached only the
  segregation figures it could read without pressing anything;
- the other three finished **only** by inheriting
  `CSRBT_HARNESS_ALLOW_DESTRUCTIVE=true` — which is to say, by being handed the
  rung that can wipe the store in order to press *Add stem*.

A safety classification that is routinely escalated around is not a safety
classification. It is a speed bump that teaches operators to disable the brake.

Five more, all of them the door's fault:

2. **The snapshot advertised what the door then denied.** Every snapshot
   published `activate.selector` — 65 selectors on one page — to a session with
   no tool of that name in its list.
3. **A gated tool refused as `not_found`**: *"no tool
   `csrbt_page__activate` is listed for this session"*. An operator that cannot
   tell "withheld" from "misspelled" spends its next moves hunting for a
   spelling.
4. **Positional selectors renumber silently.** A stale `action_btn:45`
   **deleted a tallied stem** and answered `ok: true`.
5. **`read-control` returned no id and no label** — only the selector the caller
   already had.
6. **`blind_console.py` truncated every response to 4000 characters**, silently.
   The snapshot is the documented discovery path and it is ~40 KB on these
   pages, so it arrived as JSON that would not parse; two of the four operators
   abandoned the console and wrote their own JSON-RPC client. The trial was
   partly measuring the console rather than the door.

## 2. Protocol 1.5: a declared risk is a floor

The fix is not to lower `activate`. It is to let the one thing that knows what
a selector resolved to say so, per call.

    ActionSpec(..., risk="MUTATE", may_rise=True)     # the FLOOR
    Plugin.risk_for(action, arguments) -> (risk, why) | None

The gateway asks only actions that declared `mayRise`, with *this* call's
arguments, and takes the answer only if it is **higher** than the declared risk.
Four rules make that safe rather than merely convenient:

| rule | why |
|---|---|
| a target may raise, never lower | a target that could talk its way down the ladder would be the policy asking the subject for permission |
| an answer that is not a rung, or is at or below the floor, is discarded | the floor is a floor |
| a target that **throws** while deciding is held at `DESTRUCTIVE` | a call whose subject cannot be named is the dangerous case, not the safe one |
| a `HarnessError` raised while deciding reaches the caller unchanged | a target that says "I am gone" is refusing, not failing to classify |

The response carries all three facts — `risk` (what it was authorised at),
`declaredRisk`, `riskWhy` — the audit records the risk the call was **authorised
at**, and the replay cache re-authorises at that same raised risk, so a payload
captured while a gate was open stops flowing the moment it closes.

And the refusal says so. *"DESTRUCTIVE is not enabled for this session"* about
an action the manifest calls `MUTATE` reads as the door contradicting itself;
it now reads *"…— activate was raised from MUTATE to DESTRUCTIVE because
action_btn:12 is the control 'Clear trial' in #trialBar, and its label 'Clear
trial' reads as clear"*.

## 3. The classifier, and why guessing is now the safe thing

`PagePlugin.risk_for("activate", …)` resolves the selector **at the moment of
the call**, reads the control's own name, and raises in three cases:

- the label or title is in the kit's **destructive vocabulary** — clear, delete,
  remove, erase, wipe, discard, revert, undo, forget, trash, purge, abandon,
  reset, start over, restart, at word boundaries — or carries a row-removing
  **mark** (✕ ✖ ✗ ✘ ⌫ 🗑) at its start or its end;
- the control carries **no label, id or title at all**: what pressing it would
  do cannot be read;
- the selector **resolves to nothing**. This is the one that looks wrong at
  first glance — a selector that resolves to nothing cannot destroy anything —
  and it is finding 4 above. These selectors are the *moment's*: `action_btn:45`
  is the 46th activatable control on the page right now, and the trial watched a
  stale index of exactly that shape delete a tallied stem.

Two decisions in that first clause were made by measurement, not by taste, and
both were wrong in the first draft. A mark counts at the **start or the end** of
a label, because a remover is a mark attached to the thing it removes
(`✕honeybee0`, `subject 1 ✕`) or a mark on its own — in the middle it is
punctuation between words, and *Copy host × taxon matrix* is an export. And
**× (U+00D7) is not ✕ (U+2715)**: the first is a multiplication sign, and this
kit writes it on a playback speed (`1×`, `2×`, `4×`) and between the factors of
a cross. It raises only when it is the entire label, which is a close button and
nothing else. Left as first written, the classifier would have cried wolf on
three speed buttons and an export on its first day.

The vocabulary is not invented. It is what an inventory of all 41 routed
pages found: **956 distinct labels over 1,453 activatable controls**,
of which the classifier raises **110** — 7.6% of them.

Every snapshot now also publishes the pool **`activate.destructive`**, so a
client is told which buttons those are *before* it spends a call — beside the
selectors, not instead of them. A pool that merely omitted them would leave a
caller to discover the rung by being refused.

The guess is made, and its direction is what makes it safe. A false positive
costs one refusal a session can lift deliberately. A false negative is what
every other button already was.

## 4. The other five

- **The snapshot never advertises what the door would refuse.** The gateway
  filters `argumentPools` by the policy: pools keyed by an action this session
  may not call are withheld and **named** in `poolsWithheld`, with the rung that
  withheld them. Pools that belong to no action — `selector`, `pane`, `page` —
  are facts about the target and stay. The filtering is the gateway's: a plugin
  never has to know what policy it is being read under, and a gateway that
  filtered in place would be editing the target's own state.
- **Withheld is not unknown.** `tools/call` on a real action this session may
  not have is a policy refusal (`-32001`) naming the rung. Only a name that is
  nobody's action is `not_found`.
- **`read-control` names what it read** — id, label, host, pane — using the
  *same* label expression the snapshot publishes. There is one definition of
  "the name a finger reads" now (`LABEL_FN`), read by the discovery snapshot, by
  `read-control` and by the classifier. A classifier that decided a button was
  called something other than what the snapshot calls it is exactly the failure
  the classifier exists to prevent.
- **A stale selector is refused by count**: *"no control 'action_btn:45' on this
  page right now (there are 45 action_btn selector(s), numbered 0-44) — these
  selectors are the moment's, not the page's: observe again"*.
- **`blind_console.py` prints whole answers.** `--cap N` is available and, when
  it bites, says it bit.

## 5. What is now asserted

`verify_contract` **111** (+22) and, for the first time, a mutant runner behind
it: **`tools/mutate_contract.py`**, 31 mutants, **31 killed, 0 survived, 1
recorded equivalent**. The oldest and most load-bearing suite in this kit had
never been broken on purpose — every other suite here is allowed to assume the
door holds, so a hole in this one is a hole under everything. It now covers the
raise in both directions, the fail-closed, the audit, the replay
re-authorisation, the pool filtering, the classifier's vocabulary, and four
clauses of the door itself that predate ADR-141 (off by default, `DESTRUCTIVE`
never alone, a short token, a reused request id, an undeclared argument).

The one equivalent is honest and stays: replacing `hmac.compare_digest` with
`!=` accepts and rejects exactly the same tokens and differs only in *timing*,
which no suite here can observe without measuring noise. Recorded in the ledger
rather than asserted by a check that could not fail.

`verify_report` **79** (+19): the classifier on a real page — a button that adds
stays at the floor, one named for removing is raised with its label quoted, the
bare mark is caught and so is one glued to the chip it removes, an unnamed
control is raised, a nonexistent selector is raised and refused by count,
"Nuclear count" and "2×" and "Copy host × taxon matrix" and "Tally A ✕ B cross"
are **not** raised while a lone "×" is, the destructive pool is exactly the
raised set and a subset of the selectors, and `read-control` gives back the same
label the snapshot published. `mutate_report` **50** (+3), 50 killed, 0 survived.

`verify_mcp` **73** (+3): a withheld tool is refused as withheld with the rung
named, an unknown one is still `not_found`, and a page attached mid-session now
brings **all 21** of its tools rather than 20 — because the page declares no
`DESTRUCTIVE` action any more. `mutate_mcp` **23** (+3), 23 killed, 0 survived,
1 equivalent.

## 6. Held

- **No control in the kit is currently unnamed.** The inventory found zero
  activatable controls with neither label nor id, so the fail-closed clause for
  an unreadable control fires on nothing today. It is defence against a page
  that grows one, and it is asserted on a fixture rather than on the kit.
- **The classifier reads names, not behaviour.** A button labelled *Save* that
  wipes a table is not caught, and would not have been caught by declaring the
  action `DESTRUCTIVE` either — that classification protected nothing except by
  refusing everything. The kit's own pages are the ones under test, and their
  vocabulary is measured above; a page that grows a destructive control with an
  innocuous name is a page-review problem.
- **`DESTRUCTIVE` still means what it meant.** Nothing was moved *down* the
  ladder: the calls that were refused before are refused now, and the calls that
  are allowed now were never destructive.
- **A raise costs a round trip to the page** — one `evaluate` per `activate`,
  measured in the response's `ms` like everything else.
- **Only `activate` rises.** Every other action of every target names what it
  does; nothing else needs the machinery, and nothing else has it.
- **The five traces in `tools/traces/blind2/` are not graded.** They record a
  door that no longer exists; grading them now would be grading the fix against
  the trial that produced it.

## 7. First reading

    protocol            1.5 -- a declared risk is a floor
    page plugin         activate: MUTATE, raised per call; 110 of 1,453 activatable raise
    verify_contract     111 / 111  ·  mutate_contract 31 killed, 0 survived, 1 equivalent
    verify_report        79 /  79  ·  mutate_report   50 killed, 0 survived
    verify_mcp           73 /  73  ·  mutate_mcp      23 killed, 0 survived, 1 equivalent
    kit                 77 / 77 jobs, 5,794 / 5,794 checks
    board               5,384 checks, 309 / 309 mutants  ·  publish reach 42 / 42 measured
    tasks               54 / 54 held  ·  12 / 12 traces PASS
