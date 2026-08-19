package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.FieldData;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * One definition of "digit" across both of {@code FieldData}'s number decisions (audit 2026-08-18,
 * item C).
 *
 * <p>The bare-number check and the count field used to answer "is this a number?" two different
 * ways. The check was the regex {@code [+-]?\p{Nd}+}, which walks by <em>code point</em>; the count
 * is read by {@link Long#parseLong}, which walks by {@code char} and calls
 * {@code Character.digit(char, 10)}. They agree on every digit in the BMP — Arabic-Indic
 * {@code ١٢} is twelve to both — and disagree on every decimal digit above it, because a
 * supplementary-plane digit is one code point and two chars.</p>
 *
 * <p>The consequence was a report a student could not act on: a line reading {@code 𝟏𝟐} was
 * called ambiguous and told to write {@code name,𝟏𝟐} "for a count", and doing so produced
 * {@code count '𝟏𝟐' is not an integer}. These tests pin both halves of the resolution — the two
 * paths agree, and they agree on {@code parseLong}'s answer, which is the one that is true of the
 * program.</p>
 */
@DisplayName("FieldData — one definition of digit for both number decisions")
class BareNumberDigitAgreementTest {

    /** MATHEMATICAL BOLD DIGIT ONE/TWO: category Nd, U+1D7CF and U+1D7D0, a surrogate pair each. */
    private static final String ASTRAL_12 = "𝟏𝟐";

    /** ARABIC-INDIC DIGIT ONE/TWO: category Nd, in the BMP — twelve to parseLong. */
    private static final String ARABIC_12 = "١٢";

    private static FieldData.Parsed parse(String... lines) {
        return FieldData.parseLines(List.of(lines));
    }

    @Test
    @DisplayName("the premise the probe rests on: parseLong reads ١٢ and refuses 𝟏𝟐")
    void theTwoDigitSetsReallyDoDiverge() {
        assertEquals(12L, Long.parseLong(ARABIC_12), "Character.digit accepts BMP Nd digits");
        assertEquals(4, ASTRAL_12.length(), "two supplementary digits are four chars");
        assertTrue(ASTRAL_12.codePoints().allMatch(Character::isDigit),
                "…and they are genuinely Nd digits by code point, which is what the old regex saw");
        assertThrowsNumberFormat(ASTRAL_12);
    }

    private static void assertThrowsNumberFormat(String s) {
        try {
            Long.parseLong(s);
            throw new AssertionError("expected parseLong to refuse " + s);
        } catch (NumberFormatException expected) {
            // the point of the test
        }
    }

    @Test
    @DisplayName("a supplementary-plane 'number' is not a number on either path")
    void bothPathsAgreeItIsNotANumber() {
        // The count field: unchanged, and the honest answer — parseLong cannot read it.
        FieldData.Parsed asCount = parse("oak," + ASTRAL_12);
        assertTrue(asCount.counts().isEmpty(), "nothing was counted: " + asCount.counts());
        assertEquals(1, asCount.problems().size());
        assertTrue(asCount.problems().get(0).contains("is not an integer"), asCount.problems().get(0));

        // The bare-line check: now the same answer, so the ambiguity claim is gone. What is left
        // is the one reading that survives — a species whose name happens to be those characters,
        // which is exactly what the old message offered as its second fix.
        FieldData.Parsed alone = parse(ASTRAL_12);
        assertTrue(alone.problems().isEmpty(),
                "no line may be reported ambiguous when only one reading is available: "
                        + alone.problems());
        assertEquals(1, alone.counts().size());
        assertEquals(1L, alone.counts().get(ASTRAL_12));
    }

    @Test
    @DisplayName("the advice the parser gives is advice the parser will take")
    void everyBareNumberReportIsActionable() {
        // The property behind the fix: if a line is reported as an ambiguous bare number, then
        // rewriting it the way the message says must actually produce that count.
        for (String token : List.of("12", "+7", "-5", "0", ARABIC_12, "9223372036854775807")) {
            FieldData.Parsed alone = parse(token);
            if (alone.problems().isEmpty()) continue;          // not claimed to be a bare number
            String problem = alone.problems().get(0);
            if (!problem.contains("bare number is ambiguous")) continue;

            FieldData.Parsed rewritten = parse("sp1," + token);
            long expected = Long.parseLong(token);
            if (expected > 0) {
                assertEquals(expected, rewritten.counts().get("sp1"),
                        "the message told the student to write \"name," + token + "\" for a count");
            } else {
                // 0 and -5 are refused as counts by design (absence is expressed by omission),
                // and that refusal is a *different* message about a different thing.
                assertTrue(rewritten.problems().get(0).contains("count must be positive"),
                        rewritten.problems().get(0));
            }
        }
    }

    @Test
    @DisplayName("BMP digits are unaffected — ١٢ is still a bare number and still counts twelve")
    void theBmpDigitSetIsUntouched() {
        FieldData.Parsed alone = parse(ARABIC_12);
        assertTrue(alone.counts().isEmpty());
        assertEquals(1, alone.problems().size());
        assertTrue(alone.problems().get(0).contains("bare number is ambiguous"),
                alone.problems().get(0));

        assertEquals(12L, parse("oak," + ARABIC_12).counts().get("oak"));
    }

    @Test
    @DisplayName("range stays a separate question from digits")
    void magnitudeIsNotPartOfTheDigitDecision() {
        // Genuinely a number, genuinely one this program cannot store: both statements are true
        // and neither is a disagreement about what a digit is.
        FieldData.Parsed alone = parse("9223372036854775808");
        assertEquals(1, alone.problems().size());
        assertTrue(alone.problems().get(0).contains("bare number is ambiguous"),
                alone.problems().get(0));

        FieldData.Parsed asCount = parse("oak,9223372036854775808");
        assertTrue(asCount.problems().get(0).contains("is not an integer"),
                asCount.problems().get(0));
    }

    @Test
    @DisplayName("a lone sign is not a number, and neither is a mixed run")
    void theShapeCheckStillRequiresDigits() {
        assertFalse(parse("+").problems().stream().anyMatch(p -> p.contains("bare number")),
                "\"+\" is a species name, not a number — parseLong refuses it too");
        assertEquals(1L, parse("+").counts().get("+"));
        assertEquals(1L, parse("12a").counts().get("12a"));
        assertEquals(1L, parse("1" + ASTRAL_12).counts().get("1" + ASTRAL_12),
                "one ASCII digit followed by chars parseLong cannot read is not a number");
    }
}
