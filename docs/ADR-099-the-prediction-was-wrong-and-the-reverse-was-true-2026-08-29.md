# ADR-099 — The prediction was wrong, and the reverse of it was true

**Date:** 2026-08-29
**Status:** accepted
**Extends:** ADR-061 (silent exclusion with a plausible face), ADR-069 (a check that cannot fail is
not a check), ADR-077 (a sentence about the rule can break the rule), ADR-094 (a worklist with a
front), ADR-098 (a signpost is not a claim)

ADR-098 predicted:

> at least one such assertion exists in a suite other than `verify_claims_triage`. **Falsifier: a
> sweep of every `re.sub(r"<[^>]+>"` reader in the suite showing that no assertion built on one names
> a string that only occurs inside a `<script>`.**

The sweep was run. **The prediction is false.** Sixty-six membership tests were judged and not one of
them is vacuous. The falsifier fired.

It also turned up the reverse case, which is the reason this document is longer than a retraction.

## 1. The first instrument was wrong, and said so by finding nothing

The first attempt read the suites with `ast` — find the helper that strips tags, find the variables
bound to it, find `"literal" in var`. It reported **zero**, and it reported zero partly because it
could not see: it only matched helpers bound by a constant filename, so every assertion inside
`for f in (...)` loops was invisible to it, and two suites fell out entirely as "uses the stripper
inline, not through a helper".

An instrument that answers *clean* because it cannot look is the thing this kit keeps finding in other
people's work (ADR-061, ADR-069, ADR-098 §6). It was discarded rather than reported.

## 2. What replaced it: log the membership tests as they happen

No static analysis. Each suite runs with its tag-stripper swapped for one that returns a `str`
subclass recording every `__contains__` call — needle, result, and a hash of the haystack, which is
enough to attribute it to a page. `re.sub` is shadowed for the run so the subclass survives the
whitespace pass.

That is full coverage by construction: loops, comprehensions, conditionals and all. **Seventy-two
membership tests logged, sixty-six attributable to a page**, each then judged against three views of
that page:

| view | what it is |
|---|---|
| raw | the file, whitespace collapsed |
| stripped | what the suite actually saw |
| prose | a real parse — `html.parser`, script and style dropped |

* **vacuous** = in raw, not in stripped. An `in` that can never pass; a `not in` that can never fail.
* **script-only** = in stripped and in raw, but not in prose. Passes only because the mangled
  JavaScript is still in the haystack.

## 3. The result

```
membership tests judged          66
vacuous                           0     <- ADR-098 predicted at least one
script-only                      11
```

**Zero vacuous.** A green suite cannot hold a vacuous `in` — it would already be red — and ADR-098's
prediction was really about `not in`. There are none of those either.

The eleven script-only assertions are a different animal and they are real:

| suite | page | needle |
|---|---|---|
| `verify_claims_slice` | soil-bench | `Rule of thumb, not a measurement` |
| `verify_claims_slice` | soil-bench | `measure your own once` |
| `verify_claims_slice` | cp-characters | `Taylor, 1989` |
| `verify_claims_slice` | micro-bench | `The conventional volumes are` |
| `verify_claims_slice` | micro-bench | `fixed at 0.1 mL in` |
| `verify_claims_triage` | cp-characters | `landward`, `Center for Plant Conservation`, `1 December 2014`, `25 months`, `each plant taken counts as a separate offence`, `extirpated` |

Every one of them passes, and every one of them is checking something real: the text is on the page,
rendered at runtime out of a widget's `help:` option or a keying table in script. What is not real is
the route. Whether any given one is *visible* is decided by whether some unrelated `<` and `>`
elsewhere in the same file happened to pair off around it. That is the mechanism that removed
`The note under this log` from ADR-098's view while leaving a prose sentence four lines away intact.

Nothing here was broken. Eleven verdicts rested on a coin that has not yet come up tails.

## 4. One pair of readers, each saying which view it means

`_kit` now carries them, and nothing rolls its own:

* `prose(name)` / `prose_of(src)` — what the page shows. `html.parser`, script and style dropped,
  entities left as the file writes them, tags joined with a space so an assertion written across a tag
  boundary reads as it always did.
* `raw(name)` — what the file says.

Five suites moved onto them, and the eleven assertions moved to `raw` — where their text actually
lives. `verify_claims_slice`'s `0.2 to 5 mm` absence check moved too: a string gone from the prose but
still sitting in a script is not gone, and it was being asserted against the wrong view.

The moves were made from measurement, not from reading: swapping the reader and re-running each suite
named exactly the eleven, so the refactor was informed before it was made. `verify_kit_consistency`
scored 49/49 with either reader — it moved anyway, because a rule with one exception is a rule that
erodes.

`tools/publish_drift.py` keeps its stripper and is out of scope, for a reason worth stating: it
removes `<script>` and `<style>` **before** it strips, so its regex only ever meets markup. It was
right all along.

## 5. The rule, and the trap in writing it down

`verify_claims_slice` gains a cross-suite lint next to the probe-marker rule it resembles: **no suite
may read a page through a bracket-regex tag stripper.**

Two things about how it is written.

*It assembles the pattern rather than spelling it*, because a rule that contains the string it forbids
reports itself — ADR-077, the same trap that broke the probe-marker split twice in one hour.

*Comments are exempt, deliberately.* The scan blanks `tokenize.COMMENT` tokens first. A suite may
explain the pattern; it may not use one. Without that, `_kit`'s own paragraph describing why the
pattern is wrong would be an offence against the rule it describes.

And it is seeded both ways — a fake suite that uses one, a fake suite that only mentions one in a
comment — because a lint nobody has watched fire is a lint nobody knows the shape of (ADR-069).

## 6. Two silent no-ops, in this slice, in my own hands

Worth recording because they are the slice's subject wearing different clothes.

* A patch to `verify_engine_sessions` printed *"patched both"* and had changed nothing: the anchor was
  indented in my patch and flush-left in the file, `str.replace` found no match, and the script
  announced success anyway. Found only because a later `grep` contradicted it.
* The `grep` I first used to confirm the pattern was gone was itself wrong — an over-escaped regex
  that matched nothing and read as a clean tree.

Both are the shape of ADR-098 §6 and of the push script that reported a commit it had not made. Every
edit in this slice is now made through a helper that asserts the replacement changed the file, and the
confirming search is a fixed-string one.

## 7. The numbers

```
membership tests logged            72   (66 attributed to a page)
vacuous assertions found            0   <- the prediction, falsified
script-only assertions found       11   <- moved to raw()
bracket-regex readers, before        6  (4 suites, 1 shared, 1 tool)
bracket-regex readers, after         1  (tools/publish_drift.py, correct by construction)

suite    60 of 60 jobs green, 4300 of 4300 checks passing   (4295 before; +5)
         verify_claims_slice 51 -> 56; the other four moved with no change in count
finder   1 page, 1 claim, 0 BARE, 1 near (unchanged -- no page was edited)
```

## 8. What is not done

* **No page changed.** This slice is entirely in `tools/verify/`. No mutation sweep is owed.
* **The eleven are not re-homed, only re-read.** `cp-characters` keys its species out of a table in
  script; whether that content ought to be reachable by a prose reader at all is a page question, not
  a reader question, and it was not opened here.
* **`prose()` does not resolve entities.** It leaves `&nbsp;` as written, because that is what the
  readers it replaces did and what every existing assertion is written against. A future slice that
  wants real text will have to move the assertions with it.

**The next prediction, and its falsifier.** The five suites that moved were all *claims* and *session*
suites. The per-page suites — `verify_cs`, `verify_mb`, `verify_ord` and the rest — do not read pages
as text at all; they drive them in a browser. I expect the same class of defect to exist there in a
different form: **an affordance on a page that no suite ever exercises**, passing by omission rather
than by observation. **Falsifier: an enumeration of every control, tab, button and export on all forty
pages showing that each one is driven by some suite.** That enumeration is the harness, and it is the
next slice.
