# 2026-09-11 — ADR-188: names at the door

**Every `selector` argument now takes a control ADDRESS — the page's own id or
its own name for the control — and every control in a snapshot publishes one.
The first of the seven slices of `docs/PLAN-operator-api-2026-09-11.md`, and
the answer to the complaint all four blind operators made.**

## Changed — the door

- `tools/harness_plugin_page.py`:
  - `ADDR_RE` / `STAMP_RE`: a selector may be `kind:index` (unchanged),
    `kind:index@v<digest>`, `#<id>`, or `@<name>` — ADR-128's grammar, down to
    the whole-name rule for a label with a slash and the trailing `#n`;
    `@control:<name>` is accepted verbatim.
  - `ADDR_FN` / `RESOLVE`: the grammar over the live DOM, plus the shortest
    address that resolves back to a given control and a digest of the
    numbering.
  - `observe` carries `version`; every control carries `address`; the pools
    carry `address` beside `selector`.
  - `execute` validates the grammar and resolves before acting, leaving the
    caller's own spelling in the request a trace records.
  - `risk_for` resolves first — or every stable address would have been read as
    "resolves to nothing" and refused at DESTRUCTIVE — and does not raise a
    *name* that resolves to nothing; an unresolvable *positional* selector is
    still raised (ADR-141), and a destructive control still is through either
    spelling.

## Changed — suites

- `verify_report` 120 → 140: section F. On the collection sheet, the stand
  sheet and the pheno tracker — every published address resolves back to its
  own control; the door answers every id, label and host/label exactly as the
  runner's `find_control` does; a stamp from this snapshot resolves and one
  from any other is refused as stale and told what is at that index now; `#`
  is not a synonym for `@`; the version holds when a value is typed and moves
  when a filter takes options out of the document; a name that names nothing
  is not-found and unraised while an unresolvable index is still DESTRUCTIVE;
  a destructive control raises the same by either spelling; the manifest's
  pattern takes every form and nothing else; the pools publish an address per
  selector; `@control:` is accepted verbatim.
  And on a page built for it, because the kit's own pages name everything: an
  id another control wears as a label goes to the id, a label repeated under
  one host is reached by its number and publishes that as its address, and a
  control with no name at all publishes its index, stamped.
- `mutate_report` 75 → 89 / 89: the round-trip check dropped, the fallback
  emptied, id/label order swapped, `#n` taken as part of the name, a scoped
  name split on the last slash, the version reduced to a count, the stamp
  ignored, the stale refusal silenced, `#` made a synonym, the risk read left
  unresolved, a name raised like a stale index, the pool emptied, the pattern
  narrowed, the runner's spelling taken as a label.

## Numbers

    controls with a stable address   collection sheet 307 of 307, stand sheet 280 of 280
    address forms published          33 #id + 274 @name (collection sheet), no index left

No page and no task was edited; the walk drives the same 25,392 commands.
