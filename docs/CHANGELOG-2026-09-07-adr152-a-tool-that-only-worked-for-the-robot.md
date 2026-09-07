# 2026-09-07 — ADR-152: a tool that only worked for the robot

**`collect-output` answered "0 payload(s)" for every caller that was not the
swarm — the same answer a page that emitted nothing gives. 80 Copy, Download,
Export and Print buttons across 19 pages; no task had ever read one.**

## Changed — the harness

- **`tools/harness_plugin_page.py`** — the payload capture (`CATCH`) moves here,
  beside the `collect-output` action that reads it, and `PagePlugin.__init__`
  installs it as a context init script (survives `open`/`reload`) *and* by
  evaluation into the already-open page (the ordinary case). The script guards
  itself so the two install one copy. The copy hook no longer waits for a
  `DOMContentLoaded` that has already happened.
- **`tools/swarm.py`** — imports `CATCH` from the plugin instead of defining it.

## Changed — the page's task

- **`tools/tasks/page-deployment-log-science.json`** — 101 → 139 steps,
  101 → 170 confirmed expectations. Enters the twenty record fields nothing had
  ever filled, logs all three instruments, and holds four branches nothing had
  reached: the field sheet's `coords` line, a firmware string where the log used
  to print `?`, the overcast and clear-sky readings, and a set of optics typed
  by hand rather than chosen from the sensor dial (2.10 cm/px, 84×63 m, 40 lines,
  2,153 images — and, at 20 m/s, the page's refusal at *one image every
  0.47 s*). Reads the deployment CSV off the Copy button with `collect-output`.

## Numbers

    deployment-log.html     17 -> 37 of 37 fields     (100%, sixth page whole)
    task                    101 -> 139 steps, 101 -> 170 confirmed
    the kit                 385 -> 405 of 520 fields  (74% -> 78%)
    verify_report           95 -> 109
    mutate_report           57 -> 64
    copy/download buttons   80 across 19 pages; tasks reading one: 0 -> 1

Every figure in the new steps comes from a Python oracle that mirrors the page's
arithmetic; none was typed by hand.

## Held

- 79 of the 80 buttons are still unread. What changed is that reading them is
  now possible.
- The capture is installed by the plugin, so it covers every route the kit uses
  and is not a claim about every possible one.
- The flight row records the sensor label from the dial and the GSD from the
  numbers in the boxes; with hand-typed optics those describe different cameras.
  The page has always done this and the task now holds it.
