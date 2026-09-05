# Changelog — 2026-09-04 — ADR-141: a declared risk is a floor

Four blind operators, one science page each, a supervised session
(`SENSITIVE_READ` + `DRAFT` + `MUTATE`, no `DESTRUCTIVE`). All four found that
this harness could fill every field on a data-entry page and commit none of
them: every button on these pages is pressed through `activate`, and `activate`
was `DESTRUCTIVE`. Three finished only by inheriting
`CSRBT_HARNESS_ALLOW_DESTRUCTIVE=true` — the wipe-the-store rung, to press *Add
stem*. The traces and the conditions are in `tools/traces/blind2/`.

## The contract — `tools/harness_contract.py`, protocol **1.5**

- `ActionSpec(..., may_rise=True)` and `Plugin.risk_for(action, arguments)`. A
  declared risk is now a **floor**: the gateway asks an action that declared
  `mayRise` what *this* call's arguments point at, and takes the answer **only
  if it is higher**. Not a rung, or at or below the floor → discarded. A target
  that **throws** while deciding → held at `DESTRUCTIVE`, because a call whose
  subject cannot be named is the dangerous case. A `HarnessError` raised while
  deciding reaches the caller unchanged.
- Every response carries `risk` (authorised at), `declaredRisk` and `riskWhy`.
  The audit records the **authorised** risk; the replay cache re-authorises at
  it, so a payload captured while a gate was open stops flowing when it closes.
- A refusal at a raised rung says it was raised, from what, to what, and why —
  otherwise "DESTRUCTIVE is not enabled" about an action the manifest calls
  MUTATE reads as the door contradicting itself.
- `Gateway._fit`: a snapshot never advertises what the door would refuse. Pools
  keyed by an action this session may not call are withheld and named in
  **`poolsWithheld`** with the rung. Pools that belong to no action —
  `selector`, `pane`, `page` — are facts about the target and stay. Filtering is
  the gateway's and never touches the plugin's own dict.

## The page plugin — `tools/harness_plugin_page.py`

- `activate` is **`MUTATE`, `mayRise`**. `risk_for` resolves the selector at the
  moment of the call and raises to `DESTRUCTIVE` when the control is named for
  removing something, carries no label/id/title, or resolves to nothing (a stale
  positional index — the trial watched `action_btn:45` delete a tallied stem and
  answer `ok: true`).
- `destroys()` and the vocabulary, measured rather than invented: across all 41
  routed pages there are **956 distinct labels over 1,453 activatable controls**,
  of which **110** raise. A mark counts at the **start or end** of a label, and
  **× (U+00D7) is not ✕ (U+2715)** — the kit writes the first on a playback
  speed (`1×`, `2×`, `4×`), between the factors of a cross, and in *Copy host ×
  taxon matrix*. It raises only when it is the whole label.
- New pool **`activate.destructive`**, published *beside* `activate.selector`:
  a client is told which buttons those are before it spends a call.
- **`LABEL_FN`** — one definition of "the name a finger reads", read by the
  discovery snapshot, by `read-control` and by the classifier. A classifier that
  called a button something other than what the snapshot calls it is the failure
  the classifier exists to prevent.
- `read-control` returns **id, label, host, pane**. It used to answer about a
  selector and nothing else — the one thing the caller already had.
- A selector that resolves to nothing is refused **by count**: "there are 45
  `action_btn` selector(s), numbered 0-44 — these selectors are the moment's,
  not the page's: observe again".

## The transport — `tools/harness_mcp.py`

- A tool that **exists but is withheld** by policy is `forbidden` (`-32001`)
  naming the rung; only a name that is nobody's action is `not_found`. An
  operator that cannot tell the two apart hunts for a spelling.

## The console — `tools/blind_console.py`

- Prints **whole** answers. It truncated every response to 4000 characters
  silently; the snapshot is the documented discovery path and ~40 KB on these
  pages, so it arrived as JSON that would not parse and two of the four
  operators abandoned the console for their own client. `--cap N` is available
  and, when it bites, says it bit.

## Verification

- **`tools/mutate_contract.py` — new.** The oldest and most load-bearing suite
  in this kit had no mutant runner: every other suite is allowed to assume the
  door holds. 31 mutants, **31 killed, 0 survived, 1 recorded equivalent**
  (`compare_digest` → `!=` differs only in timing, which nothing here can
  observe without measuring noise).
- `verify_contract` **111** (+22): the raise in both directions, the discard
  rules, fail-closed, the propagating refusal, the audit, the replay
  re-authorisation, the pool filtering and `poolsWithheld`.
- `verify_report` **79** (+19): the classifier on a real page, the mark rules,
  "Nuclear count" and "Tally A ✕ B cross" left alone, the destructive pool, the
  refusal by count, and `read-control` giving back the same label the snapshot
  published. `mutate_report` **50** (+3), 50 killed, 0 survived.
- `verify_mcp` **73** (+3): withheld ≠ unknown, and a page attached mid-session
  brings **all 21** of its tools (was 20 — the page declares no `DESTRUCTIVE`
  action any more). `mutate_mcp` **23** (+3), 23 killed, 0 survived, 1
  equivalent.

54 tasks held, both canaries refuted, 12 traces PASS. Kit **77 / 77 jobs,
5,794 / 5,794 checks**; board 5,384 checks / 309 mutants; publish reach
**42 / 42 measured**.

## Two flakes seen on the way, neither caused by this slice

Three of the six full runs it took to close this failed on something that
passed standing alone, and both are worth naming rather than re-rolling away:

- `verify_organism`: *"two consecutive physicals are identical through the
  gateway"* failed in two runs under `run_all -j 2` and passed six times
  concurrently, standalone, under four CPU burners. Something in the physical
  moves without a write. That check now **prints the lines that differ** when it
  fails, because a failure that names nothing costs a whole run to reproduce.
- `audit_targets`: one control "never measured" in one run, zero standing
  alone — the same family as ADR-140's phantom `never exposed`, which the frame
  wait and the `coverage()` re-look shrank but did not close.

Both are contention, and an instrument whose answer depends on what else is
running is not an instrument (ADR-134). Named here as the next slice's subject.

## Docs

`docs/ADR-141-the-door-that-could-not-press-a-button-2026-09-04.md`;
`docs/AUTOMATION-HARNESS.md` (the risk table, the floor, the action table);
`tools/traces/blind2/PROVENANCE.md`.
