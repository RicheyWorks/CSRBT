package core.export;

import core.OrderedSet;
import core.TreeNode1;

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

    /** Render the set's current state as JSON per the class schema. */
    public static <K> String toJson(OrderedSet<K> set) {
        Objects.requireNonNull(set, "set cannot be null");
        StringBuilder sb = new StringBuilder(256);
        sb.append("{\n");
        sb.append("  \"type\": \"OrderedSet\",\n");
        sb.append("  \"strategy\": \"").append(set.getStrategy().getClass().getSimpleName()).append("\",\n");
        sb.append("  \"size\": ").append(set.size()).append(",\n");
        TreeNode1<K> root = set.getEngine().getRoot();
        sb.append("  \"height\": ").append(depthOf(root)).append(",\n");
        sb.append("  \"meters\": { \"avgInsertMs\": ").append(round(set.avgInsertTimeMs()))
          .append(", \"avgDeleteMs\": ").append(round(set.avgDeleteTimeMs())).append(" },\n");
        sb.append("  \"root\": ");
        node(sb, root, 1, 1);
        sb.append("\n}");
        return sb.toString();
    }

    private static <K> void node(StringBuilder sb, TreeNode1<K> n, int depth, int indent) {
        if (n == null || n.isNil()) {
            sb.append("null");
            return;
        }
        String pad = "  ".repeat(indent + 1);
        sb.append("{\n");
        sb.append(pad).append("\"key\": \"").append(escape(String.valueOf(n.getData()))).append("\", ");
        sb.append("\"color\": \"").append(n.getColor()).append("\", ");
        sb.append("\"size\": ").append(n.getSize()).append(", ");
        sb.append("\"depth\": ").append(depth).append(",\n");
        sb.append(pad).append("\"left\": ");
        node(sb, n.getLeft(), depth + 1, indent + 1);
        sb.append(",\n");
        sb.append(pad).append("\"right\": ");
        node(sb, n.getRight(), depth + 1, indent + 1);
        sb.append("\n").append("  ".repeat(indent)).append("}");
    }

    private static <K> int depthOf(TreeNode1<K> n) {
        if (n == null || n.isNil()) return 0;
        return 1 + Math.max(depthOf(n.getLeft()), depthOf(n.getRight()));
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
