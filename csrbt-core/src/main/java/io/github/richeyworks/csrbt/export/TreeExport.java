package io.github.richeyworks.csrbt.export;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.TreeNode1;

import java.util.Objects;

/**
 * Tree-state JSON export (ADR-009 P3) — the visualizer's <em>contract</em>, not the
 * visualizer. One static method renders an {@link OrderedSet}'s live structure — strategy,
 * size, meters, and the node tree (key / color / subtree size / depth / children) — as
 * dependency-free JSON a p5.js or JavaFX drawer can consume directly. The reference output
 * is checked in at {@code docs/visualizer-contract.json}.
 *
 * <p>Schema (stable; additions will be backward-compatible):</p>
 * <pre>{@code
 * {
 *   "type": "OrderedSet",
 *   "strategy": "RedBlackStrategy",
 *   "size": 7,
 *   "height": 3,
 *   "meters": { "avgInsertMs": 0.0012, "avgDeleteMs": 0.0 },
 *   "root": {
 *     "key": "42", "color": "BLACK", "size": 7, "depth": 1,
 *     "left":  { ... } | null,
 *     "right": { ... } | null
 *   } | null
 * }
 * }</pre>
 *
 * <p>Keys are rendered with {@code String.valueOf} and JSON-escaped, so any key type
 * exports (the visualizer treats keys as labels). Like {@code getTree()}/{@code getEngine()},
 * the walk reads live internal structure outside the R1 read guard — call it from the
 * writer thread or a quiesced set; it is a diagnostics/export seam, not a concurrent read
 * path.</p>
 */
public final class TreeExport {

    private TreeExport() { }

    /** Render the set's current state as JSON per the class schema (live meters included). */
    public static <K> String toJson(OrderedSet<K> set) {
        return toJson(set, true);
    }

    /**
     * As {@link #toJson(OrderedSet)}, with the wall-clock meters optionally zeroed
     * (B3, consolidation 2026-08-12): the meters were the ONLY nondeterministic bytes
     * in an otherwise fully deterministic recorded session, so regenerating a canonical
     * replay file always produced spurious VCS diffs and defeated byte-level
     * verification. {@link TreeSessionRecorder} passes {@code false}; zeros keep the
     * schema intact for the visualizer.
     */
    public static <K> String toJson(OrderedSet<K> set, boolean includeMeters) {
        Objects.requireNonNull(set, "set cannot be null");
        StringBuilder sb = new StringBuilder(256);
        sb.append("{\n");
        sb.append("  \"type\": \"OrderedSet\",\n");
        sb.append("  \"strategy\": \"").append(set.getStrategy().getClass().getSimpleName()).append("\",\n");
        sb.append("  \"size\": ").append(set.size()).append(",\n");
        TreeNode1<K> root = set.getEngine().getRoot();
        sb.append("  \"height\": ").append(depthOf(root)).append(",\n");
        sb.append("  \"meters\": { \"avgInsertMs\": ")
          .append(includeMeters ? round(set.avgInsertTimeMs()) : "0")
          .append(", \"avgDeleteMs\": ")
          .append(includeMeters ? round(set.avgDeleteTimeMs()) : "0").append(" },\n");
        sb.append("  \"root\": ");
        node(sb, root, 1, 1);
        sb.append("\n}");
        return sb.toString();
    }

    /**
     * Emit the node subtree as nested JSON, iteratively (explicit stack). Recursion here
     * would be bounded by tree <em>height</em>, and a degenerate tree — a Splay spine after
     * sorted inserts, the very state worth visualizing — is O(n) deep; this codebase has
     * already met that stack overflow once (the E5a benchmark). The JSON nests just as
     * deep, but that costs heap, not stack.
     */
    private static <K> void node(StringBuilder sb, TreeNode1<K> root, int depth, int indent) {
        if (root == null || root.isNil()) {
            sb.append("null");
            return;
        }
        final class Frame {
            final TreeNode1<K> n; final int depth, indent; int stage = 0;
            Frame(TreeNode1<K> n, int depth, int indent) { this.n = n; this.depth = depth; this.indent = indent; }
        }
        java.util.ArrayDeque<Frame> stack = new java.util.ArrayDeque<>();
        stack.push(new Frame(root, depth, indent));
        while (!stack.isEmpty()) {
            Frame f = stack.peek();
            // Indentation caps at 64 levels: un-capped, a spine's output is O(n^2) characters
            // (gigabytes at 50k keys) purely in whitespace. The JSON stays valid; readability
            // at depth 64 was never on the table anyway.
            String pad = "  ".repeat(Math.min(f.indent + 1, 64));
            if (f.stage == 0) {
                f.stage = 1;
                sb.append("{\n");
                sb.append(pad).append("\"key\": \"").append(escape(String.valueOf(f.n.getData()))).append("\", ");
                sb.append("\"color\": \"").append(f.n.getColor()).append("\", ");
                sb.append("\"size\": ").append(f.n.getSize()).append(", ");
                sb.append("\"depth\": ").append(f.depth).append(",\n");
                sb.append(pad).append("\"left\": ");
                TreeNode1<K> left = f.n.getLeft();
                if (left == null || left.isNil()) sb.append("null");
                else stack.push(new Frame(left, f.depth + 1, f.indent + 1));
            } else if (f.stage == 1) {
                f.stage = 2;
                sb.append(",\n").append(pad).append("\"right\": ");
                TreeNode1<K> right = f.n.getRight();
                if (right == null || right.isNil()) sb.append("null");
                else stack.push(new Frame(right, f.depth + 1, f.indent + 1));
            } else {
                sb.append("\n").append("  ".repeat(Math.min(f.indent, 64))).append("}");
                stack.pop();
            }
        }
    }

    /** Iterative height walk — same stack-overflow reasoning as {@link #node}. */
    private static <K> int depthOf(TreeNode1<K> n) {
        if (n == null || n.isNil()) return 0;
        java.util.ArrayDeque<TreeNode1<K>> nodes = new java.util.ArrayDeque<>();
        java.util.ArrayDeque<Integer> depths = new java.util.ArrayDeque<>();
        nodes.push(n);
        depths.push(1);
        int max = 0;
        while (!nodes.isEmpty()) {
            TreeNode1<K> cur = nodes.pop();
            int d = depths.pop();
            if (d > max) max = d;
            TreeNode1<K> l = cur.getLeft(), r = cur.getRight();
            if (l != null && !l.isNil()) { nodes.push(l); depths.push(d + 1); }
            if (r != null && !r.isNil()) { nodes.push(r); depths.push(d + 1); }
        }
        return max;
    }

    private static double round(double ms) {
        return Math.round(ms * 1_000_000.0) / 1_000_000.0;   // 6 decimal places is plenty
    }

    private static String escape(String s) {
        StringBuilder out = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"'  -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) out.append(String.format("\\u%04x", (int) c));
                    else out.append(c);
                }
            }
        }
        return out.toString();
    }
}
