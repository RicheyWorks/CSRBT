# 2026-08-29 — ADR-099: the sweep ADR-098 asked for, and one pair of readers

Companion to `docs/ADR-099-the-prediction-was-wrong-and-the-reverse-was-true-2026-08-29.md`.

## The prediction, falsified

ADR-098 predicted at least one assertion passing on text its reader could not see. **Sixty-six
membership tests judged, zero vacuous.** The falsifier fired.

Method: not static analysis — the first attempt at that reported zero because it could not see past
`for` loops, and was discarded. Instead each suite ran with its tag-stripper swapped for a `str`
subclass that logs every `__contains__`, with `re.sub` shadowed so the subclass survives. Full
coverage by construction. Each needle was then judged against the raw file, the stripped text the
suite saw, and a real `html.parser` extraction.

## What the sweep did find — eleven, and the reverse defect

Eleven live assertions pass **only because** the mangled JavaScript is still in the haystack: their
text is rendered at runtime from a widget's `help:` option or a keying table in script. They were
checking something real by a route decided by where a stray `<` fell.

| suite | needles |
|---|---|
| `verify_claims_slice` | soil-bench ×2, cp-characters ×1, micro-bench ×2 |
| `verify_claims_triage` | cp-characters ×6 |

## `_kit` gains one honest pair

* `prose(name)` / `prose_of(src)` — what the page shows: `html.parser`, script and style dropped,
  entities left as written, tags joined with a space so assertions across a tag boundary read as
  before.
* `raw(name)` — what the file says.

Five suites moved onto them and now roll nothing of their own:

| suite | change |
|---|---|
| `verify_claims_slice` | reader swapped; 5 assertions to `raw`; the `0.2 to 5 mm` absence check too — a string gone from prose but still in a script is not gone |
| `verify_claims_triage` | reader swapped, its local `raw()` retired to `_kit`; 6 assertions to `raw` |
| `verify_engine_sessions` | two readers; the prose search no longer meets mangled JS |
| `verify_kit_consistency` | `plain()` and three more sites; 49/49 with either reader, moved anyway |
| `verify_visualizer_sessions` | the footer-window reader |

Each move was made from measurement: swapping the reader and re-running named exactly the eleven
before anything was rewritten.

`tools/publish_drift.py` keeps its stripper and is out of scope — it removes `<script>` and `<style>`
**before** stripping, so its regex only ever meets markup.

## The rule

`verify_claims_slice` gains a cross-suite lint: **no suite reads a page through a bracket-regex tag
stripper.** It assembles the forbidden pattern rather than spelling it (ADR-077 — a rule that contains
what it forbids reports itself), blanks `tokenize.COMMENT` tokens first so a suite may *explain* the
pattern without using one, and is seeded both ways so it has been watched to fire (ADR-069).

Plus three assertions that the two readers really differ, on the case ADR-098 hit: `raw()` sees
`The note under this log`, `prose()` does not, and `prose()` does see the page's own prose.

## Two silent no-ops, mine, recorded

A patch printed "patched both" having changed nothing (indented anchor, flush-left file,
`str.replace` no-op), and the `grep` that first confirmed the tree was clean was an over-escaped
regex matching nothing. Every edit here now goes through a helper that asserts the replacement
changed the file; the confirming search is fixed-string.

## The numbers

```
membership tests logged        72  (66 attributed to a page)
vacuous                         0  <- the prediction, falsified
script-only                    11  <- moved to raw()
bracket-regex readers  6 -> 1      (the one left is correct by construction)

suite   60 of 60 jobs green, 4300 of 4300 checks passing   (4295 before; +5)
        verify_claims_slice 51 -> 56
finder  1 page, 1 claim, 0 BARE, 1 near   (unchanged; no page was edited)
```

## Verification

* `python3 tools/verify/run_all.py` — 60/60 jobs, 4300/4300 checks.
* `python3 tools/audit_claims.py` — unchanged at 1 near.
* `grep -rnF '<[^>]+>' tools/ --include=*.py` — two hits, both prose about the pattern or the one
  tool that removes script and style first.

## Next

An enumeration of every control, tab, button and export on all forty pages, asserting each is driven
by some suite — the defect ADR-099 predicts next is an affordance nobody exercises, passing by
omission. That enumeration is the harness.
