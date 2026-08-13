package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.EcologyFieldDay;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentLab;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentSpec;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probe (bug audit 2026-08-12): a {@code model:} line whose kind and arity are valid but
 * whose VALUES violate the model function's domain must be a reported spec problem — the
 * same contract {@code cross:}, {@code tree:}, and {@code data:} already honour, and the
 * exact guarantee {@code ExperimentLabTest.badLinesReported} states ("never guesses or
 * crashes"). Before the fix, {@code parseModel} validated only structure, so these lines
 * parsed clean and then threw from {@code ExperimentLab.run} → the whole report was lost.
 */
@DisplayName("Model-domain probe — a parseable-but-invalid model is a spec problem, not a crash")
class ExperimentModelDomainProbeTest {

    /** R > min(M, C): MarkRecapture.estimate throws. Must be caught at parse, run must survive. */
    @Test
    @DisplayName("markrecapture with recaptured > min(marked, caught) is reported, run survives")
    void markRecaptureOutOfDomain() {
        ExperimentSpec spec = ExperimentSpec.parse(List.of(
                "phase: calm uniform 200",
                "model: markrecapture 100 90 95"));   // R=95 > min(100,90)=90
        assertEquals(0, spec.models().size(), "the invalid model must not be accepted");
        assertFalse(spec.problems().isEmpty(), "the invalid model must be reported as a problem");
        EcologyFieldDay.Session s = assertDoesNotThrow(() -> ExperimentLab.run(spec));
        assertTrue(s.report().contains("⚠ spec:"), "the report must flag the spec problem");
    }

    /** Negative genotype count: PopulationGenetics.hardyWeinberg throws. */
    @Test
    @DisplayName("hardyweinberg with a negative genotype count is reported, run survives")
    void hardyWeinbergNegative() {
        ExperimentSpec spec = ExperimentSpec.parse(List.of(
                "phase: calm uniform 200",
                "model: hardyweinberg -1 50 25"));
        assertEquals(0, spec.models().size());
        assertFalse(spec.problems().isEmpty());
        assertDoesNotThrow(() -> ExperimentLab.run(spec));
    }

    /** All fecundity zero ⇒ R0 = 0: PopulationGenetics.eulerLotka throws. */
    @Test
    @DisplayName("eulerlotka with R0 = 0 is reported, run survives")
    void eulerLotkaZeroR0() {
        ExperimentSpec spec = ExperimentSpec.parse(List.of(
                "phase: calm uniform 200",
                "model: eulerlotka 1.0:0 0.8:0 0.5:0"));   // every mx = 0 ⇒ R0 = 0
        assertEquals(0, spec.models().size());
        assertFalse(spec.problems().isEmpty());
        assertDoesNotThrow(() -> ExperimentLab.run(spec));
    }

    /** A valid model beside an invalid one still runs; only the bad line is dropped. */
    @Test
    @DisplayName("a valid model survives alongside a rejected one")
    void goodModelSurvivesBadNeighbour() {
        ExperimentSpec spec = ExperimentSpec.parse(List.of(
                "phase: calm uniform 200",
                "model: markrecapture 100 60 15",     // valid — LP N̂ = 400
                "model: markrecapture 5 5 9"));       // R=9 > min(5,5)=5 — invalid
        assertEquals(1, spec.models().size(), "the one valid model must remain");
        assertFalse(spec.problems().isEmpty());
        EcologyFieldDay.Session s = assertDoesNotThrow(() -> ExperimentLab.run(spec));
        assertTrue(s.report().contains("Lincoln–Petersen N̂=400.0"),
                "the surviving model must still be narrated");
    }
}
