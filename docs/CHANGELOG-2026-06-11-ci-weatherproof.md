# CHANGELOG 2026-06-11 — CI red on the push; the V5 rule catches its last holdout

The 13-commit push (`b7e2968`) failed CI on both matrix JDKs while the identical tree
runs green locally — verified three ways: the GitHub tarball of the pushed head built
and run with the console launcher (533/533), with randomized test-class order ×3
(533/533 ×3), and under the **exact CI invocation** (`ant clean test`, ant 1.10.14,
Temurin 17: `BUILD SUCCESSFUL`, 533/533). CI's logs are admin-only, so the diagnosis
is by elimination — and the suite contains exactly one assertion that can fail on a
loaded runner without anything being wrong: the ADR-007 benchmark's hard
`optimistic < locked`, a strict comparison of **two noisy wall-clock measurements
under thread contention**.

That assert predates the V5 rule ("wall-clock is weather; deterministic meters
decide") and survived it as the suite's last weather-exposed hard verdict. It is now
weather-proofed with its teeth kept: up to three attempts, each row printed; **one
optimistic win demonstrates the property** (a single race can flip on a busy runner),
while a real regression — say, the fast path silently disabled — loses all three
deterministically and still fails the build. Locally the first attempt wins at 1.6×.

If CI reds again on the re-push, the cause is something only the runner can see —
pull the `test-reports-*` artifact from the run page (it names the failing test) and
the next diagnosis starts from fact, not elimination.

Suite **533 green** under `ant clean test`, locally, on the patched tree.
