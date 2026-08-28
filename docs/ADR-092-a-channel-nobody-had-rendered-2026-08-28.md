# ADR-092 — a channel nobody had rendered

*2026-08-28. Status: accepted. The falsifier named in
[ADR-091](ADR-091-the-blind-spot-named-after-the-wrong-mechanism-2026-08-28.md) fires.*

## 1. The falsifier fires

ADR-091 defined what "on screen" means — innerText, SVG `<text>`, every tooltip a chart yields — and
named the channel outside it: *a print stylesheet is the likeliest, since the kit has print cards and
they are not rendered by any pass.*

Rendered under `emulate_media(media="print")` and diffed against the screen view, page by page:

```
17 of 39 pages put text on paper that no screen shows
1682 lines, 328 of them carrying digits
```

| page | print-only lines | carrying digits |
|---|---|---|
| `stand-sheet` | 238 | 36 |
| `releve` | 164 | 40 |
| `greenhouse` | 161 | 32 |
| `collection-sheet` | 138 | 17 |
| `cp-bench` | 133 | 9 |
| …twelve more | | |

The field sheets build an entire tab-separated record under `@media print` — plot method, date, the
whole data table — and **no suite had ever rendered a line of it.** `verify_print_slice` checks print
*fidelity*: that things which should be hidden are hidden and the layout survives. Nothing checked what
appears.

## 2. What it does not mean

The ties are unaffected, and the reason is worth stating rather than assumed: **`ecology-lab.html` adds
nothing in print.** Every rounding-tie verdict in ADR-089–091 is taken from that page's screen view,
and those verdicts are complete only if the page has no print channel. It does not — measured, and now
a check, sitting in the control list of the new suite for exactly that purpose.

So the falsifier fired for *content* and not for *ties*: the channel is large, and it is not on the
pages the ties live on. Those are two different sentences and the first does not license the second.

## 3. What is locked

`tools/audit_print_channel.py` is the finder — same shape as `audit_claims` and `audit_ties`, named in
`run_all`'s FINDERS list so it cannot be quietly forgotten. It compares a page against **itself**, one
media away, so nothing in it depends on knowing which selector does the hiding.

`verify_print_channel.py` is the gate, **5 checks**, and the inventory is declared:

```
PASS  every page declared to print a report still prints one
PASS  CONTROL: a page declared to print nothing extra prints nothing extra
PASS  ...and the control is not vacuous
PASS  the printed reports carry FIGURES, not just headings
PASS  ecology-lab adds nothing in print, so the tie verdicts are not missing a channel
```

Checked **both ways** deliberately. A page that stops emitting its report has lost something a reader
carries into the field; a page that starts emitting one has gained a surface nothing checks. Either way
the declared list is wrong, and a one-way check would only notice one of them. The control also carries
the method's own vacuity guard: if the media switch stopped working every page would print nothing and
the first check would fail; if the observation were unstable every page would differ and the control
would fail.

## 4. The count that changed

Three records in a row have widened what counts as looking at a page:

| | what a pass could see |
|---|---|
| ADR-089 | innerText of one page |
| ADR-090 | + the pages a reader loads a file into |
| ADR-091 | + SVG text, + chart tooltips |
| here | + what a page prints |

Each widening was found by taking the previous record's own stated limit seriously enough to go and
measure it. None of the four was found by inspecting code.

## 5. And I wrote it over a tool that already existed

The finder was called `audit_print.py` for about an hour. That name was taken: `tools/audit_print.py`
audits print **fidelity** — what a page LOSES when printed, content that goes `display:none` on paper —
and has done since ADR-031's work. I wrote a new file over it.

Nothing in my own testing caught it. `verify_print_channel` passed 5 of 5 against my file;
`audit_print_channel` ran clean; the page sweep was correct. The kit run caught it, because
`verify_print_slice` reads a `PROBE` block out of the original by name and got an `IndexError`:

```
FAILURES
verify_print_slice
   IndexError: list index out of range
```

The original is restored from the copy on the machine this work ships to, byte-identical
(`37d70d73e586`), and the new file is `audit_print_channel.py`. The two ask opposite questions about
the same channel — what print loses, what print adds — which is the reason both should exist and the
reason one of them should not have been silently replaced.

The cost of checking would have been one `ls tools/audit_*.py`. That is the fourth assumption in five
slices that a single command would have settled: the reader of a fixture, the mechanism of a chart, the
precision a nudge measures, and now whether a filename was free. The pattern is not carelessness about
hard things; it is not checking easy ones.

**The next prediction, and its falsifier.** 328 print-only lines carry digits and **not one of them has
ever been checked by anything** — not for arithmetic, not for escaping, not for agreement with the
screen. That is the largest unexamined surface the kit has left. **Falsifier: reading those lines and
finding they are all already correct** — which would be a genuine surprise, since every other surface
in this kit had something wrong with it the first time anyone looked.
