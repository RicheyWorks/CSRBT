package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Phylogenetic trees for tree-thinking labs (ADR-020) — parse the standard
 * <b>Newick</b> format ({@code (A,(B,C));}, optional branch lengths {@code A:0.5},
 * optional internal-node labels), walk it, print it, and hand it to the lab page to
 * draw as a cladogram.
 *
 * <p>This is the format every phylogenetics course and tool uses, so trees transfer:
 * a student can take a Newick string from a course handout or a published paper,
 * paste it into a protocol file ({@code tree: <label> <newick>}) or the Workbench,
 * and get it drawn, counted, and exported. It is also the one place the repo's two
 * senses of "tree" meet honestly: a CSRBT is a search tree, a phylogeny is a
 * hypothesis of descent — same picture, different meaning, and the lab materials say
 * so rather than blur it.</p>
 *
 * <p>Parsing follows the house rule: malformed input throws with a reason (unbalanced
 * parentheses, empty subtree, trailing junk) — never a guessed tree.</p>
 */
public final class PhyloTree {

    /** One node: leaf (no children) or clade. {@code length} is NaN when absent. */
    public record Node(String name, double length, List<Node> children) {
        public boolean isLeaf() { return children.isEmpty(); }
    }

    private final Node root;

    private PhyloTree(Node root) { this.root = root; }

    public Node root() { return root; }

    // ── Parsing ───────────────────────────────────────────────────────────────

    /** Parse a Newick string (the trailing {@code ;} is optional). */
    public static PhyloTree parse(String newick) {
        String s = newick.trim();
        if (s.endsWith(";")) s = s.substring(0, s.length() - 1).trim();
        if (s.isEmpty()) throw new IllegalArgumentException("empty tree");
        int[] pos = { 0 };
        Node root = parseNode(s, pos);
        if (pos[0] != s.length()) {
            throw new IllegalArgumentException(
                    "trailing characters after tree: '" + s.substring(pos[0]) + "'");
        }
        return new PhyloTree(root);
    }

    private static Node parseNode(String s, int[] pos) {
        List<Node> children = new ArrayList<>();
        if (pos[0] < s.length() && s.charAt(pos[0]) == '(') {
            pos[0]++;                                     // consume '('
            while (true) {
                children.add(parseNode(s, pos));
                if (pos[0] >= s.length()) throw new IllegalArgumentException("unbalanced '('");
                char c = s.charAt(pos[0]);
                if (c == ',') { pos[0]++; continue; }
                if (c == ')') { pos[0]++; break; }
                throw new IllegalArgumentException("expected ',' or ')' at index " + pos[0]);
            }
        }
        // Optional label (leaf name or internal clade name), then optional :length.
        int start = pos[0];
        while (pos[0] < s.length() && ",():;".indexOf(s.charAt(pos[0])) < 0) pos[0]++;
        String name = s.substring(start, pos[0]).trim();
        double length = Double.NaN;
        if (pos[0] < s.length() && s.charAt(pos[0]) == ':') {
            pos[0]++;
            int ls = pos[0];
            while (pos[0] < s.length() && ",()".indexOf(s.charAt(pos[0])) < 0) pos[0]++;
            try {
                length = Double.parseDouble(s.substring(ls, pos[0]).trim());
            } catch (NumberFormatException bad) {
                throw new IllegalArgumentException(
                        "bad branch length '" + s.substring(ls, pos[0]) + "'");
            }
        }
        if (children.isEmpty() && name.isEmpty()) {
            throw new IllegalArgumentException("empty node (missing name) at index " + start);
        }
        return new Node(name, length, List.copyOf(children));
    }

    // ── Walks ─────────────────────────────────────────────────────────────────

    /** Leaf names, left to right — the taxa this tree relates. */
    public List<String> leaves() {
        List<String> out = new ArrayList<>();
        collectLeaves(root, out);
        return out;
    }

    private static void collectLeaves(Node n, List<String> out) {
        if (n.isLeaf()) { out.add(n.name()); return; }
        for (Node c : n.children()) collectLeaves(c, out);
    }

    /** Maximum node depth (root = 1) — how nested the deepest clade is. */
    public int depth() { return depth(root); }

    private static int depth(Node n) {
        int d = 0;
        for (Node c : n.children()) d = Math.max(d, depth(c));
        return d + 1;
    }

    // ── Output ────────────────────────────────────────────────────────────────

    /** Re-serialize to Newick (round-trips modulo whitespace). */
    public String newick() {
        StringBuilder sb = new StringBuilder();
        writeNewick(root, sb);
        return sb.append(';').toString();
    }

    private static void writeNewick(Node n, StringBuilder sb) {
        if (!n.isLeaf()) {
            sb.append('(');
            for (int i = 0; i < n.children().size(); i++) {
                if (i > 0) sb.append(',');
                writeNewick(n.children().get(i), sb);
            }
            sb.append(')');
        }
        sb.append(n.name());
        if (!Double.isNaN(n.length())) {
            sb.append(':').append(String.format(Locale.ROOT, "%s", trimmed(n.length())));
        }
    }

    private static String trimmed(double v) {
        String s = String.format(Locale.ROOT, "%.6f", v);
        s = s.replaceAll("0+$", "");
        return s.endsWith(".") ? s.substring(0, s.length() - 1) : s;
    }

    /** A printable cladogram for the narrated report. */
    public String ascii() {
        StringBuilder sb = new StringBuilder();
        ascii(root, "", "", sb);
        return sb.toString();
    }

    private static void ascii(Node n, String prefix, String childPrefix, StringBuilder sb) {
        sb.append(prefix);
        sb.append(n.name().isEmpty() ? "┐" : n.name());
        if (!Double.isNaN(n.length())) {
            sb.append(String.format(Locale.ROOT, "  (%.3g)", n.length()));
        }
        sb.append('\n');
        for (int i = 0; i < n.children().size(); i++) {
            boolean last = i == n.children().size() - 1;
            ascii(n.children().get(i),
                    childPrefix + (last ? "└─ " : "├─ "),
                    childPrefix + (last ? "   " : "│  "), sb);
        }
    }

    /** The lab page's schema: nested {@code {name, length?, children?}} objects. */
    public String json() {
        StringBuilder sb = new StringBuilder();
        json(root, sb);
        return sb.toString();
    }

    private static void json(Node n, StringBuilder sb) {
        sb.append("{ \"name\": \"").append(WorkloadTrace.escapeJson(n.name())).append('"');
        if (!Double.isNaN(n.length())) {
            sb.append(String.format(Locale.ROOT, ", \"length\": %.6f", n.length()));
        }
        if (!n.isLeaf()) {
            sb.append(", \"children\": [");
            for (int i = 0; i < n.children().size(); i++) {
                if (i > 0) sb.append(',');
                json(n.children().get(i), sb);
            }
            sb.append(']');
        }
        sb.append(" }");
    }
}
