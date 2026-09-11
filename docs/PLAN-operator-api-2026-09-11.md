# PLAN — the operator API: a door an automated host can drive correctly

**Date:** 2026-09-11 · **Status:** outline, not yet built · **Grounds:** the third blind trial (ADR-187). Four fresh operators reached every figure their goal named, and every one of them did it by re-observing the page after each structural change, computing button offsets by hand, and re-running a whole plan from a fresh page — four to six times each, 200–290 calls to land 73–89. The door works; it is not yet an API. This is the outline of the build that makes it one.

## 1. What "correctly" means

An operator — a model in a host, a script, a person at a console — should be able to:

1. open a target once and keep it open across many calls (no fresh page per plan);
2. name a control by something that does not move when the page changes;
3. learn everything the page offers without guessing (every option of a picker, every control's name, the rules a page states about its own arithmetic);
4. read what the page says in a form that parses (figures, boxes with separators, tables), and read what changed since the last look;
5. be refused for the right reason, in a vocabulary that distinguishes *does not exist*, *moved*, *withheld by rung* and *invalid*;
6. be scored by what it reached, not by whether it took the author's route.

Every one of those six is a finding from a blind trial (ADR-136, ADR-141, ADR-187). None of them is a new idea; the sixth was built in ADR-187 and the other five are the build.

## 2. The surface

The contract stays what it is — `list`, `describe`, `call`, `observe`, a risk ladder with declared floors and raises (ADR-141) — and gains a session and an address space. Names below are provisional.

**Session.** `open(target, page?, seed?, clock?) → session`; `close(session)`. The page is *settled* before `open` returns: every script-built control exists, the first snapshot is taken, a version stamp is issued. Every later call carries the session; a target closed by the host or dead underneath answers `unavailable`, never a hang (ADR-111 holds).

**Addressing.** Every control gets a stable address, published in the snapshot and accepted by every acting tool:

    #tAdd                    the page's own id, when it has one
    @rCov/4                  host id / label, the runner's ADR-128 grammar, resolved by the DOOR
    @iList/died#2            the third such label under that host
    action_btn:45@v17        the positional selector, stamped with the snapshot version it came from

A positional selector whose stamp is behind the current version is refused as `stale` with the address that now sits there — never resolved to a different control (the ADR-141 stem-deletion), never escalated to a rung.

**Discovery.** `describe(session)` is the page's manual, computed, not typed: panes; every control with its stable address, kind, label, host, type, and *which pane reveals it*; every picker's **complete** option list (not the first six); every figure the page publishes and the box it lives in; and the rules the page itself states in prose — the scoring formula the pheno tracker prints, the "unscored traits are dropped" line, the Reineke and van Wagner citations — pulled from the page text by the same reader that finds figures. The snapshot carries `version`; `observe(since=version)` returns only what changed.

**Reading.** `read_report` as now (figures, by, tables, charts, rows), with box text joined by a separator the reader guarantees; `read_control(address)` returns the control's address, label, host and value, never a bare value; `collect_output` unchanged.

**Acting.** `set_text`, `pick`, `activate`, `choose_option`, `set_slider`, `press_step`, `set_checkbox`, `attach_file`, `drop_files`, `show_pane`, `set_clock`, `set_seed` — the same actions, addressed by stable address, each answer carrying the snapshot version after the act and the *diff* (which controls appeared, moved, vanished). An optional `expect` on any act — the task grammar's expectations — makes the door confirm a post-condition in the same round trip.

**Refusals.** One vocabulary: `not_found` (no such address on this page), `stale` (a positional address behind the version), `withheld` (the rung the session lacks, named, with the raise reason), `invalid_argument`, `conflict`, `unavailable`. A gated tool is *listed* with its rung and refuses `withheld`, so a blind operator can tell a locked door from a missing one (ADR-141 §3, generalised).

**Outcomes.** `goal(task) → outcomes`: the readings a task holds, with their claims, so a host can self-grade as it goes; `grade(trace, mode=route|outcomes)` the grader ADR-187 built, callable through the door.

**Transport.** stdio MCP as now, plus streamable HTTP with a bearer token, so a host outside the container — Claude Desktop, an IDE, an agent runtime — can connect. `blind_console.py` becomes a client of the session: a REPL that keeps one door open and appends moves, so an attempt is a conversation rather than a replay.

**The organism and the lab** get the same session and version semantics; their addresses are already stable (keys are integers, actions are named), so the change there is the session and the diff.

## 3. What it is held by

- `verify_api`: every address form resolves to the control the snapshot published; a stale positional is refused `stale` and names the replacement; `describe` lists every option `pick` accepts (the pool equals the page's option list, held page by page); every control the walk (ADR-118) can reach has a non-null address; box text splits on the separator into the boxes the page has.
- `mutate_api`: an address that resolves positionally after the page changed; a pool cut to six; a `withheld` that says `not_found`; a settle that returns before the controls exist.
- The measure that matters: **the fourth blind trial**, the same four goals through the new door. Success is numeric: attempts fall to one or two, calls per goal fall toward the task's own step count, and the outcome grade rises to what the goal names. Anything else is not "correct".

## 4. Build order (one slice each, in the usual ritual)

1. **ADR-188 — names at the door.** Move `@control` resolution from the task runner into the page plugin; accept `#id`; stamp positional selectors with the version and refuse `stale`. The tasks keep working unchanged (the runner now passes names through). Smallest change with the largest effect on the trial's findings 1 and 2.
2. **ADR-189 — settle before the first act; typed refusals.** `open` waits for script-built controls; `not_found` vs `stale` vs `withheld`; a gated tool stays listed with its rung.
3. **ADR-190 — the manual.** Complete pools; ids/labels on `read_control`; separated box text; page-stated rules gathered into `describe`.
4. **ADR-191 — the session.** One door across calls; `observe(since)`; the diff on every act; `blind_console` as a REPL.
5. **ADR-192 — HTTP.** Streamable-HTTP MCP with a token; the first external host connected and its trace kept.
6. **ADR-193 — goals that say what they hold.** Widen the 44 science goals to name every reading their task holds (the ADR-187 gap between goal and task), with `goal()` exposed.
7. **ADR-194 — the fourth blind trial**, graded by outcomes, against the floors ADR-187 set.

Steps 1–3 can land before any host exists; 4–5 are what "an API" adds over "a door"; 6–7 are how it is measured.
