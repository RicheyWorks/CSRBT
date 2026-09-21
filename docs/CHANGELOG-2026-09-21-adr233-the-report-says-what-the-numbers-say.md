# 2026-09-21 — ADR-233: the report says what the numbers say

## Fixed (micro bench, all three filed by the eighth blind trial)

- **The saturation warning is computed.** With points above OD 0.6 in the
  growth fit, the page refits without them and says which way they moved µ,
  with both slopes and the percentage — DOWN is what optical saturation does;
  UP means the points sit above the line, which saturation cannot do, so the
  reading is in question. It used to say "pushes µ down" whatever happened,
  including over the operator's point that pushed µ from 0.6931 to 0.8189.
- **The intermediate band is the rule the page applies**: above R and below S,
  plus the whole-millimetre range when both breakpoints are whole (14–16 mm for
  17/13, not the 13.5–16.5 mm it printed).
- **Organism and medium are kept per zone**, read at Add, and carried into the
  zone list, the bench sheet and two new trailing CSV columns. They were on the
  form and nothing read them.
- **The task certified all three**; its expectations are corrected and it holds
  the computed sentence and the organism/medium besides.

## Checked

verify_mb 65 → 83 against an independent refit and the band rule;
new runner `tools/mutate_mb.py`, 13/13 killed.
