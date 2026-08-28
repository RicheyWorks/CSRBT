# ADR-084 — the guard standing in front of its own evidence

*2026-08-28. Status: accepted. Narrows the rule in
[ADR-056](ADR-056-a-copy-older-than-its-page-is-not-evidence-2026-08-26.md) without weakening it; tests the prediction
in [ADR-083](ADR-083-the-kit-was-wrong-about-itself-2026-08-28.md).*

## 1. What happened when I tried to measure

ADR-083 ended with a prediction: the fourteen pages whose CURRENT rests on a stamp written before
provenance was recorded — the weakest evidence in the file — should all verify CURRENT when read at
their URLs. The first attempt:

```
cell-bench.html   the existing stamp carries no time, so this copy cannot be ordered
                  against it -- not stamped
```

The tool refused, and would refuse forever. When a stamp carries no time there is no time for a copy to
be newer than, so that clause **can never be satisfied by any copy**. Every page still on a pre-ADR-056
stamp was permanently unmeasurable, which is exactly the set the prediction was about. I had written a
prediction the tool made untestable and not noticed, because the refusal reads like a normal safety
message.

**A guard with no satisfiable path is not a guard, it is a wall** — and this one was standing in front
of its own evidence.

## 2. What ADR-056 actually protects

Its rule is that a copy older than the stamp it would overwrite describes a page that no longer exists,
so it must not replace the stamp. That protects **the stamp**. It says nothing about:

- reading the copy at all,
- reporting what the copy does with the offline contract,
- recording a BEHIND observation — which writes to `state["observed"]`, never to `state["pages"]`.

Written as a single early `return 2` before the file was even opened, it refused all four. So the check
moved to where the write is, and the rule became a function, for the reason this file already gives
about the decay rule: *"the rule is stated as one function and checked here, both ways."*

```python
def stamp_allowed(prev, taken):
    """May a read taken at `taken` replace the stamp `prev`? -> (bool, why)."""
    at = entry_at(prev)
    if prev is None:  return True,  "no previous stamp"
    if at is None:    return True,  "supersedes an undated stamp with a dated read"
    if taken < at:    return False, "the copy is older than the stamp it would overwrite"
    return True, "the copy is at least as new as the stamp"
```

The middle case is the change, and it is a strengthening of the file rather than a relaxation of the
rule: an undated stamp is the weakest entry `published.json` holds — the report says so on every run —
and a dated read is strictly better evidence. It supersedes, and **says so on the line above the
verdict**, because silently replacing an entry is how a file stops meaning what it says:

```
                                 supersedes an undated stamp with a dated read
greenhouse.html                CURRENT, measured from the live copy taken at 1787879059
```

The dated case is untouched. `verify_publish_reach` grew six checks for the three outcomes plus a
seventh that exists only to prove the rule can still say no:

```
PASS  a dated read supersedes an UNDATED stamp
PASS  a copy OLDER than a dated stamp is still refused (ADR-056, unchanged)
PASS  the rule can say no at all -- exactly one of these six is a refusal
```

That last one is the canary the other six need. A `stamp_allowed` that returned `True` for everything
would pass five of them. 24 → **31 checks**.

## 3. The prediction, tested on a sample

With the wall gone, four of the fourteen were read and measured — the kit hub, the greenhouse monitor,
a bench and a print card, chosen across families rather than at random:

| page | verdict |
|---|---|
| `ecology.html` | CURRENT, measured |
| `greenhouse.html` | CURRENT, measured |
| `soil-bench.html` | CURRENT, measured |
| `ecology-field-card.html` | CURRENT, measured |

Four for four, and each one converted an undated stamp into a dated read. **This is a sample, not a
sweep** — ten pages in that class are still on undated stamps, and saying "the prediction held" on four
of fourteen would be the kind of overclaim ADR-082 was written about. What can be said is that the
prediction survived its first four tests and that the remaining ten are now *testable*, which they were
not this morning.

## 4. Two of the five BEHIND, closed

`soil-recipes` and `cell-bench` are republished and stamped. Both diffs are exactly what ADR-080 said
they were, now confirmed against the live bytes rather than inferred: the published `soil-recipes` rail
is missing **Greenhouse**; `cell-bench` is missing **Greenhouse and Soil Recipes**. Both published
copies already carried the non-blocking webfont, the WCAG ramp and FEK v1.3.0 with `escv` — so unlike
every page in ADR-082, no reader was being served a blank screen or an unescaped name. The severity
ranking in ADR-080 was right.

Three remain: `deployment-log`, `ordination`, `stand-sheet`.

**Ranked deliberately below the guard fix**, and the reason is worth stating rather than assuming: a
missing sibling link in a nav rail costs a reader one extra tap. A measurement tool that cannot measure
a whole class of pages costs every future slice its evidence. When those two competed for the same
hour, the second won.

## 5. Where the pile stands

```
36 current, 3 behind (0 measured at the URL), 0 unknown, 0 unmapped
of the current: 10 stamped before provenance was recorded, 17 at publish time, 9 measured from the live page
```

The evidence is getting stronger under the counts, which is the number to watch rather than the total:
measured-from-the-live-page has gone 4 → 5 → **9** across ADR-082, ADR-083 and this record, and
undated stamps 14 → **10**.

**The next prediction, and its falsifier.** The ten remaining undated stamps should verify CURRENT, on
the same publish-date account that has now survived four tests. **Falsifier: any of the ten coming back
BEHIND at its URL** — which would mean a page can drift after a stamp without anything touching it, and
nothing in the model allows that. The three BEHIND pages are the other open item and need only a
republish each.
