# ADR-035: The deployment log, and four things it will not tell you

**Status:** Accepted and implemented — `docs/deployment-log.html` (the kit's 24th instrument), `tools/verify/verify_dep.py` at 101 checks, plus `tools/verify/verify_emitters.py` at 67 checks guarding the regenerators.
**Date:** 2026-08-25
**Deciders:** Richmond
**Supersedes:** nothing. **Touches:** `docs/ecology.html`, the rail, and four of the five regenerators

---

## Context

Two gaps met here. The published gap analysis ranked *deployment and calibration records for recorders and
flights* third and it had never been built. Separately, the research request that produced that analysis
asked specifically about **bioacoustic pipelines and drone NDVI processing**, and the kit had nothing on
either.

The problem with both is not the recording. It is that the settings which decide how the files may be read
live on a device, in a config app, or in somebody's head — and by the time a reviewer asks, they are gone.

## Decision

**One page covering the three kinds of unattended instrument the kit's users actually deploy** — an
acoustic recorder, a drone flight, an environmental logger — computing what can be computed and refusing
what cannot.

### What it computes

| Quantity | From | Why it matters before you deploy, not after |
|---|---|---|
| Nyquist limit | sample rate ÷ 2 | a rate too low does not record quietly; it **aliases**, and the false frequency looks like data |
| Card and duty cycle | rate × 2 bytes × channels × on/every × days | a recorder that filled its card leaves a gap whose start you must reconstruct |
| Clock drift | days × 1 s/day, × 343 m/s | see below |
| Ground sample distance | sensor width × altitude ÷ (focal × px) | decides whether the flight can see the thing at all |
| Images, lines, shot interval | footprint × (1 − overlap) | a sub-second trigger interval no sensor can sustain is better known on the ground |
| Logger memory | memory × interval | a wrapped logger silently discards the *start* of the season |

**The drift figure is the one that changes behaviour.** Open Acoustic Devices state that an AudioMoth's
clock is accurate to ±10 ms when set and then drifts up to about one second per day, and that their
GPS-synchronised firmware reaches at least 20 µs. Sound covers 343 m in a second. So a fortnight's
deployment carries **up to 14 seconds — 4.8 kilometres of apparent position error** for time-of-arrival
work. Written that way it settles the array question before anyone buys the second unit.

### The four refusals

1. **No decibels.** Gain settings on these recorders are named, not calibrated, and the manufacturer is
   explicit that an SPL figure needs the *whole chain — microphone, case and recording settings —*
   calibrated against a meter. The page records your gain and refuses to convert. It says what *is* still
   valid: relative amplitude within one unit at one gain.
2. **No NDVI from the wrong sensor.** A stock RGB camera has no NIR band at all; a filter-converted one has
   three overlapping channels and a contaminated red. DroneDeploy's own guidance is VARI for RGB and NDVI
   only for real multispectral. The page names the index after the sensor actually flown.
3. **No cross-flight comparison without radiometric correction.** Pix4D's wording is quoted rather than
   paraphrased: correction *"is required to be able to compare multispectral imagery taken at different
   points in time under different weather conditions."* Panel, DLS, both or neither each get their own
   consequence, and *neither* is logged as **not comparable**.
4. **No radiation-shield correction figure.** da Cunha (2015) found a gill-type multi-plate shelter best of
   those tested; the error magnitudes are paywalled. So the finding ships and the number does not. The page
   asks which shield you used and, for an improvised one, tells you to measure your own offset against a
   proper shelter rather than accept an invented correction.

### A threshold that no equipment could meet

The bandwidth check first carried one number per taxon and set bats at 120 kHz of required *band*, which
demanded a 240 kHz Nyquist and therefore a 480 kHz recorder. Nothing on the market does that, so **192 kHz
— what most bat work actually runs at — reported as a failure.** A threshold no instrument can satisfy is
not rigour; it is a bug that reads like rigour, and it would have trained users to ignore the verdict.

It now carries two numbers, both frequencies in the signal: a minimum below which the survey cannot work,
and a band that covers the high callers as well. Between them the verdict is *"enough for most of it, and
not all of it"*, naming which species the gap removes and warning that **those absences will look like
ecology**.

## The regenerators, which were quietly broken

`verify_emitters.py` exists because the kit has five regenerators and nothing checked that they regenerate.
A regenerator that stops writing is invisible: every page still agrees with every other page, because they
are all equally stale. It does not ask an emitter whether it is happy — it **breaks a consumer page and
checks the emitter notices**, then that a rewrite restores it byte for byte.

It found two live bugs on its first run, both the same mistake in different clothes as the dead `fek_emit`
CSS from ADR-034:

- **`dwc_emit` never converged.** Its CSS boundary was a lookahead for "the next comment", and the block had
  since acquired a comment of its own — so every run replaced the head and left the tail, duplicating it.
  `.dwc-out` appeared **five times** in Relevé before this was caught.
- **`nav_emit` replaced a fifth of the rail.** A non-greedy match to the first indented `</div>` ended at
  the close of the first chip group once the rail was grouped, orphaning the rest. Ten pages carried up to
  four orphaned rail tails.

Both boundaries now come from the source of truth rather than a guess, and `nav_emit` scans line by line
with depth clamped so it also sweeps up the debris earlier runs left.

Then the suite failed its own canary. Deleting the line that writes the CSS **still passed**, because the
canary perturbed only the script banner — the original bug walking straight through the test written to
catch it. A regenerator with two halves needs two canaries, and it has them now; the same fix immediately
exposed the same lookahead bug in `keep_emit`, inherited from `dwc_emit` when it was derived from it.

## Consequences

- Recorders, flights and loggers now leave a record that says how their files must be read.
- Five regenerators are checked against perturbation rather than trusted.
- Still open from the gap analysis: Event Core with `parentEventID`, and the Humboldt Extension.

## Sources

Open Acoustic Devices — [SPL calibration](https://www.openacousticdevices.info/support/device-support/calibration-for-sound-pressure-level-measurement),
[multiple AudioMoths for localisation](https://www.openacousticdevices.info/support/device-support/using-multiple-audiomoths-for-sound-localisation).
Pix4D — [radiometric correction](https://support.pix4d.com/hc/en-us/articles/360022919691),
[image acquisition plan](https://support.pix4d.com/hc/en-us/articles/202557459).
DroneDeploy — [camera filters for NDVI mapping](https://help.dronedeploy.com/hc/en-us/articles/1500004964082-Camera-Filters-for-NDVI-mapping).
da Cunha, A.R. (2015) *Environmental Monitoring and Assessment* 187:236.
