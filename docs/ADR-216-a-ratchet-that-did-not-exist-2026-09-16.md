# ADR-216 — The fix for a reading that looked like a failure was a sentence asserting a ratchet that did not exist

**ADR-215, an hour old, made every tile on the Harness Board say whether it gates the verdict. The one that started it — `6 / 7 — clean under load` — got this line: *"a failed run out of fifty-two is a known flake with a ratchet, not a red suite."* There was no ratchet. `contention_ledger.json` had no ceiling, no declaration, and nothing that ran it; `contend.py` was the only instrument in this kit whose readings nothing checked on a schedule. The sentence was written to reassure a reader about a mechanism nobody had built, and it was published on the one page whose job is to say what the harness can vouch for.**

## 1. The shape, and who did it

ADR-203's: a message that asserts what cannot be observed. ADR-212's, exactly —
a handler that knew a download could fail silently, declined to mark the outbox
for that reason, and then said *"bench.csv downloaded"* anyway.

The difference is that those were found in code written months ago. This one was
written **while fixing the previous slice**, by the agent that had just spent a
slice on the rule it broke. A kit can hold a page to a standard and lose it in
the prose about the page in the same afternoon.

## 2. What was actually there

    verify_organism beside verify_tie_render    16 run(s), 1 failed
        x1  two consecutive physicals are identical through the gateway

One failure, recorded honestly, with the check named and the co-tenant named —
the instrument did its job. What was missing is what happens NEXT. That reading
had been true for weeks and would have gone on being true at 2, at 5, at 20,
with the board printing the ratio and no rule anywhere deciding when it stopped
being acceptable.

**A flake that is getting worse is a race that is getting likelier**, and the
difference between a flake and a claim that is simply false when the machine is
busy is how often it happens (ADR-142's own words). A count with nothing holding
it cannot tell those apart.

## 3. The ratchet

Every pairing carries a **ceiling that only comes down**. `--raise-floors`
records today's count wherever it is lower; a pairing above its ceiling fails.
A pairing with no ceiling yet is not above one — a first reading records what it
found and waits, the way every other ledger here does.

**`contend.py` bare now reports**, so `run_all` can run it. A ceiling nothing
checks is a number, not a ratchet — and this file held the only readings in the
kit that nothing ran on a schedule, which is how "1 failed of 52" stayed true for
weeks. The *sweep* that takes new readings is slow and stays opt-in; reading them
costs nothing and now happens on every run.

**The one failure is NOT declared.** A declaration would say it is right to fail
beside another suite, and ADR-142's whole point is that a flake that is re-rolled
is a measurement nobody took. It is held at the count it has reached and may not
get worse.

## 4. And the sentence

The board's line now says what the rule is, and `verify_board` requires it to
name the rule:

> a ceiling per pairing that only comes down: a pairing that fails more under
> load than it did fails `tools/contend.py`, which `run_all` runs. The sweep that
> takes the readings is opt-in and slow; reading them is not.

`verify_contend` 36 → 42, including the ratchet against a fixture ledger where
one pairing is over, one is exactly at, and one has no ceiling at all.

## 5. What this record is for

ADR-215 is nine hours old and this is its correction. The useful part is not that
the sentence was wrong — it is **why it was easy to write**: the tile needed a
reason, a reason was written, and nothing in the kit checked the reason against
the thing it described. `verify_board` now does, for that tile, by name. Every
other tile's reason is still prose, and that is the next place this shape will
turn up.
