package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.PhyloTree;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Probe (bug audit 2026-08-17, finding 37): {@code json()} formatted branch lengths with
 * {@code %.6f} — exactly the defect {@code trimmed()} was patched to avoid for
 * {@code newick()} (F-6 residual, AUDIT-2026-08-14). Anything below ~5e-7 serialized as
 * {@code 0.000000}, and molecular trees routinely carry lengths that small, so the JSON
 * export silently dropped the very quantity a substitution-rate tree is about.
 */
@DisplayName("PhyloTree.json — branch lengths survive serialization exactly")
class PhyloTreeJsonLengthProbeTest {

    private static final Pattern LENGTH = Pattern.compile("\"length\": ([^,}\\s]+)");

    @Test
    @DisplayName("a 1e-7 branch length round-trips through json() instead of becoming 0")
    void tinyLengthSurvivesJson() {
        PhyloTree t = PhyloTree.parse("(A:1e-7,B:0.5);");
        String json = t.json();
        assertFalse(json.contains("0.000000"), "a real branch length was zeroed:\n" + json);

        Matcher m = LENGTH.matcher(json);
        assertTrue(m.find(), "no branch length in:\n" + json);
        assertEquals(1e-7, Double.parseDouble(m.group(1)), 0.0, "A's length must be exact");
        assertTrue(m.find());
        assertEquals(0.5, Double.parseDouble(m.group(1)), 0.0, "B's length must be exact");
    }

    @Test
    @DisplayName("json() and newick() agree on every length, and the tree re-parses")
    void jsonAgreesWithNewickRoundTrip() {
        String in = "(A:1.0E-7,(B:0.25,C:1.0E-9)BC:0.4)root;";
        PhyloTree t = PhyloTree.parse(in);
        assertEquals(in, t.newick());                       // Newick was already exact
        PhyloTree again = PhyloTree.parse(t.newick());
        assertEquals(t.json(), again.json());               // and JSON matches it

        for (double expected : new double[]{ 1e-7, 0.4, 0.25, 1e-9 }) {
            assertTrue(t.json().contains(String.valueOf(expected)),
                    "missing " + expected + " in:\n" + t.json());
        }
    }
}
