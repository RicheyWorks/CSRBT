# ADR-152 — A tool that only worked for the robot

**Status:** accepted · **Date:** 2026-09-07 · **`collect-output` is published by the page plugin, is in the manifest, and is the only way to read what leaves a page through a Copy button, a download or a print. What it reads was installed by the robot, on the robot's context. Every other caller got "0 payload(s)" — the same answer a page that emitted nothing gives. 80 such buttons across 19 pages; no task had ever read one. Now one has, and `deployment-log.html` is the sixth page taken whole: 17 → 37 of 37 fields.**

## The tool that answered like a page with nothing to say

`collect-output` is one of the 22 actions `csrbt-page` publishes. It reads
`window.__S.out` — the payload buffer filled by a capture script that wraps
`Blob`, `URL.createObjectURL`, the download anchor, `navigator.clipboard`,
`window.print` and `document.execCommand("copy")`.

That capture lived in `tools/swarm.py` and was added as an init script on the
context **the robot builds**. A task's runner, an audit, a suite, or a person
driving the gateway by hand all got a page where `window.__S` was undefined,
and:

    TAKE_OUT = "() => (window.__S ? window.__S.out.splice(0) : [])"

answered `[]`. Not an error. Not a refusal. **"0 payload(s)" — which is exactly
what a page that copied nothing says.** A tool cannot fail more quietly than by
returning the successful answer for the other case.

So this is the shape ADR-146 and ADR-151 keep finding, one level up: the reader
stopped where nobody looked, and the stopping had the same face as the truth.

    19 pages in this kit carry a Copy, Download, Export or Print button
    80 such buttons in all
     0 tasks had ever read what came out of one

Those buttons are not decoration. The collection sheet's Darwin Core export,
the experiment guide's `.eco` protocol, the ethogram's budget CSV, the
deployment log's "thing a reviewer asks for and the thing nobody writes down" —
in this kit, the button *is* the product. All of it was outside the harness.

## The fix

The capture moves to `harness_plugin_page.py`, beside the action that reads it,
and `swarm.py` imports it from there — a rule written twice is a rule that
drifts. `PagePlugin.__init__` installs it **both ways, and neither is enough
alone**:

- as a **context init script**, so it survives `open` and `reload` — what a
  session that navigates needs;
- **evaluated into the page that is already loaded**, because the ordinary case
  is a plugin built around a page somebody has just opened, and an init script
  added then does not run until the next navigation.

The script guards itself (`if (!window.__S)`), so the two together install one
copy: a second install would start a fresh buffer — throwing away payloads
nobody had collected — and wrap every wrapper around its own wrapper, counting
each toast twice with nothing to say so.

One more thing had to change. The copy hook was installed on `DOMContentLoaded`,
which is free when the script always runs before the document. Evaluated into a
page that has already loaded, that event has been and gone and **the hook was
never installed at all** — so the retrofit would have captured downloads and
prints and quietly missed the one output most of this kit produces. It installs
immediately when the document is past loading.

`verify_report` **109** (+14) drives a fixture with the hidden-textarea Copy
pattern every page in this kit uses, a Blob download and a print, through a
plugin built the way a task's runner builds one — and holds that the payload is
taken rather than copied, that the download is captured with its filename and
not followed, that a second plugin installs nothing again, and that all of it
survives a reload. `mutate_report` **64** (+7).

## The sixth page taken whole

`deployment-log.html` was the largest data-entry gap left, named as such since
ADR-150: **17 of 37 fields**. It is three instruments and a log — an acoustic
recorder, a drone flight, an environmental logger — and what it computes is
mostly refusals: a sample rate that cannot survey bats, a card that fills before
you come back, a clock that has wandered 10.3 km of sound, a converted camera
that cannot produce NDVI, a logger reading its own casing.

The twenty fields nothing had filled were the *record* fields, and that is not a
coincidence: they are the ones that carry no arithmetic, so no expectation ever
needed them. They are also the entire point of a deployment log.

    deployment-log.html   17 -> 37 of 37 fields   (101 -> 170 confirmed expectations)
    the task              101 -> 139 steps
    the kit               385 -> 405 of 520 fields   (74% -> 78%)

Six pages are now entered whole: collection sheet, stand sheet, ecology lab,
relevé, experiment guide, deployment log.

**Four branches nothing had reached.** The field sheet prints a `coords` line
only when both latitude and longitude are there, and nothing had ever put either
in. The firmware box emits a literal `?` into the log when blank, and the page
says in its own prose that firmware is not bookkeeping — it had never held a
version. The two skies the page treats as *good* — fully overcast and clear —
were never asked for; only the broken-cloud warning had been. And the optics:
every GSD this task had ever held came from one of the three sensors on the
dial, which fills all four boxes at once, so the four inputs beside it — the
ones a reader with any other camera has to fill in — had never had a number put
in them. Typed by hand at 6.17 mm / 8.8 mm / 4000 px, the page gives 2.10 cm/px,
an 84×63 m footprint, 40 lines and 2,153 images; wound up to 20 m/s it refuses
the plan outright — *one image every 0.47 s* — which is a sentence no task in
this kit had ever made it say.

And the CSV: **`collect-output` now reads what the Copy button put on the
clipboard**, so the deployment CSV — header and three rows, one per instrument —
is held by a task for the first time.

## Held

- **79 of the 80 buttons are still unread.** One task reads one output. The
  other eighteen pages' exports are exactly as unmeasured as they were
  yesterday; what changed is that reading them is now possible. That is a
  worklist, stated rather than done, and the obvious next slice.
- The capture is installed by the plugin, so a caller who reaches a page some
  other way still gets nothing — the fix is scoped to "a plugin was built over
  this page", which is every route the kit actually uses and not a claim about
  every possible one.
- `collect-output` reads what the page handed the clipboard API or the anchor.
  It is not a claim about the operating system's clipboard, and a page that
  copies by some route none of these wrappers cover would still be silent. The
  wrappers are named in one place now, which is the condition for widening them.
- The flight row logs the sensor's *label* from the dial and the GSD from the
  numbers actually in the boxes. With hand-typed optics those two describe
  different cameras. The page has always done this; the task now holds it, which
  is the first step to deciding whether it should.
