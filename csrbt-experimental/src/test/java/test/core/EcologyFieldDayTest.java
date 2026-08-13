package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.EcologyFieldDay;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The field-day demo — byte-determinism (the V5 standard applied to the demo), every
 * station present in both the narrated report and the JSON artifact, and the JSON's
 * structural sanity (balanced, top-level keys present, no locale-broken numbers).
 */
@DisplayName("EcologyFieldDay — deterministic full-ecosystem demo")
class EcologyFieldDayTest {

    @Test
    @DisplayName("byte-determinism: two runs produce identical report and JSON")
    void byteDeterminism() {
        EcologyFieldDay.Session a = EcologyFieldDay.run();
        EcologyFieldDay.Session b = EcologyFieldDay.run();
        assertEquals(a.report(), b.report());
        assertEquals(a.json(), b.json());
    }

    @Test
    @DisplayName("all six stations narrate, and every reading sentence is interpreted")
    void stationsPresent() {
        String report = EcologyFieldDay.run().report();
        assertTrue(report.contains("THE MEADOW"));
        assertTrue(report.contains("THE CENSUS"));
        assertTrue(report.contains("THE ARCHIPELAGO"));
        assertTrue(report.contains("THE FOSSIL RECORD"));
        assertTrue(report.contains("THE SURVEY GRID"));
        assertTrue(report.contains("THE ISLAND"));
        // Interpreted sentences, not raw numbers: the hot patch must read as skewed
        // (its J' ≈ 0.52 sits in the "uneven" band), the patchy grid as clumped, the
        // sown grid as regular.
        assertTrue(report.contains("hot keys carry") || report.contains("strongly dominated"),
                "hot-patch regime should read as skewed");
        assertTrue(report.contains("clumped"));
        assertTrue(report.contains("regular"));
    }

    @Test
    @DisplayName("JSON artifact: balanced braces, all top-level stations, dot-decimal numbers")
    void jsonSanity() {
        String json = EcologyFieldDay.run().json();
        assertTrue(json.startsWith("{"));
        assertTrue(json.endsWith("}\n"));
        long open = json.chars().filter(c -> c == '{').count();
        long close = json.chars().filter(c -> c == '}').count();
        assertEquals(open, close, "unbalanced braces");
        long openB = json.chars().filter(c -> c == '[').count();
        long closeB = json.chars().filter(c -> c == ']').count();
        assertEquals(openB, closeB, "unbalanced brackets");

        for (String key : new String[]{ "\"meadow\"", "\"demography\"", "\"growth\"",
                "\"archipelago\"", "\"fossils\"", "\"grid\"", "\"island\"" }) {
            assertTrue(json.contains(key), "missing " + key);
        }
        for (String key : new String[]{ "\"structural\"", "\"meanStructural\"",
                "\"clusteredLeaves\"", "\"fill\"" }) {
            assertTrue(json.contains(key), "missing ADR-017 key " + key);
        }
        assertTrue(!json.contains(",}") && !json.contains(",]"), "dangling commas");
        assertTrue(!json.matches("(?s).*\\d,\\d{6}.*"), "locale comma leaked into a number");
    }
}
