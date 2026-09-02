# ADR-124 — Every page, walked

**Status:** accepted · **Date:** 2026-09-02 · **One robot for every page, and two things it found that forty-one suites and a swarm had not**

## 1. Two pages of forty-one

The robot walks a target from its manifest alone and has since ADR-117
walked the page target — on two pages. The committed ledger held
`collection-sheet.html` and the suite added `ecology-lab.html`. The kit
has forty-one routed pages. The swarm (`harness.py`) drives all of them,
but the swarm knows the kit; the robot does not, and the robot is the one
whose refusals mean something. ADR-117's two pages found five plugin
defects. Thirty-nine pages had never been asked.

## 2. The decision

`harness_walk.py --target page --page all` walks every page the published
route table (`tools/routes.json`) names — each on its own transport child,
a fresh browser page — and keeps each in the ledger as
`csrbt-page/<page>`, with the page's own unreachable list as a fact about
the page. One line per page, the coverage matrix at the end ("tools driven
on no page at all"), and a verdict. Forty-one pages: **336 seconds**.

`verify_walk` section **I** holds the committed ledger to it: one entry per
routed page and none unrouted; every page at the same bar as every target
(identity, coverage, nothing broken, nothing failed); every one of the
fifteen page tools driven on at least one page; unreachable a fact about
the page (a bench offers nearly everything, a guide offers little). And it
pins the two fixes below live.

## 3. What the first walk of every page found

**38 ok, 3 bad.**

- **`douglas-explorer.html`: `reload` failed twice with
  `net::ERR_INTERNET_DISCONNECTED`.** The page had not failed. The robot,
  finding no activate-kind control, had fallen back to the plain selector
  pool, activated a `nav_link`, and *followed it to the internet*; every
  action after that was on a page that was not the kit's, and `reload`
  re-fetched a site the sandbox cannot reach. The same thing, quieter,
  on `ecology-teachers-guide.html` (`set-text` "undriven" rather than
  "unreachable", because a nav link had carried the walk to a page *with*
  text controls) — and on `soil-suite.html`, which read as 53 driven and 4
  unreachable when it was really 37 and 9: the extra coverage belonged to
  whatever page its first link went to. A walk of a page that leaves the
  page is a walk of something else, filed under the page's name. Right
  about what it drove; wrong about what it was driving.

  **Fix (page plugin):** `activate` on an anchor whose `href` leaves the
  document is refused — "a link that leaves the page: use open". Leaving is
  `open`'s job, and `open` has stayed on its page since ADR-117.
  Same-document links (`#id`) are still clicks.

- **`experiment-guide.html`: `choose-option` refused six of six**, "no
  such option". The pool `choose-option.value` is the union of every
  select's options on the page; a value from one select is no such option
  on another, and with five selects the odds were against every try. No
  per-argument pool can say which value goes with which select.

  **Fix (contract, protocol 1.3):** `argumentPools` may carry **argument
  sets** — a list of whole argument dicts, keyed by the action name alone,
  meaning "these combinations are valid right now". The page plugin
  publishes `choose-option: [{selector, value}, …]` for every enabled
  select's options. The robot takes one set whole, forms anything it does
  not cover as before, and counts the set pool as the first relevant pool
  of its action (so an empty one, throughout, is unreachable). The fixture
  gains `paired`, an action only a set-reading robot can drive (12 tools),
  and `mutate_walk` two mutants (a set pool never read; not a relevant
  pool) — **26 killed, 0 survived, 2 equivalent**.

Second walk of every page: **41 ok, 0 bad, 0 failed to walk**; every tool
driven somewhere.

## 4. Numbers

`verify_walk` 107 → **120** (sections B and F for sets, I for the pages);
`verify_contract` at 1.3; `mutate_walk` 26/0/2; walk ledger: 6 target
entries + 41 page entries, page@stdio and page@mcp regenerated with the
set pool in force.

## 5. Held

- The page plugin has no mutant runner of its own (`mutate_harness` breaks
  `harness.py`, the swarm's driver). Its two fixes here are pinned live in
  section I; a runner over a page walk would cost a browser per mutant.
- `--page all` is a ledger job (five to six minutes), not a suite step.
  The suite reads the ledger, the way it reads the eight-round walks.
- Over MCP, every page is not walked; the fixture and the organism have
  shown the transport decides nothing (ADR-121), and `page@mcp` stands for
  the page target there.
