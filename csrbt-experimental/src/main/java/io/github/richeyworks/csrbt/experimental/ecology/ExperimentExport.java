package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.Map;

/**
 * The export side of the experiment engine (ADR-019): every run of
 * {@link ExperimentLab#runWithExports} produces a bundle a student can hand to any
 * tool — CSVs that open directly in <b>Excel</b>, Google Sheets, or R (long-format
 * model series included, ready to pivot and chart), a plain-text report, the lab-page
 * session JSON, and {@code report.html}: a self-contained, print-friendly report for
 * turning in, printing to PDF, or pasting into <b>PowerPoint</b> slide by slide.
 *
 * <p>Everything here is dependency-free on purpose (this repo vendors nothing and
 * carries one runtime dependency); native {@code .xlsx}/{@code .pptx} writers would
 * require an OOXML library and are held with a named trigger — an instructor workflow
 * that CSV-into-Excel and print-to-PDF genuinely cannot serve.</p>
 */
public final class ExperimentExport {

    private ExperimentExport() {}

    /** Append a CSV row to a named export file, writing the header on first touch. */
    static void row(Map<String, StringBuilder> exports, String file, String header,
                    String... fields) {
        StringBuilder sb = exports.computeIfAbsent(file, k -> new StringBuilder(header + "\n"));
        for (int i = 0; i < fields.length; i++) {
            if (i > 0) sb.append(',');
            sb.append(csv(fields[i]));
        }
        sb.append('\n');
    }

    /** RFC-4180 style quoting: quote when a field contains comma, quote, or newline. */
    public static String csv(String field) {
        if (field.indexOf(',') < 0 && field.indexOf('"') < 0 && field.indexOf('\n') < 0) {
            return field;
        }
        return '"' + field.replace("\"", "\"\"") + '"';
    }

    /**
     * The printable report: the narrated text verbatim, then every CSV in the bundle
     * rendered as a clean table. Self-contained, light, print-friendly (each section
     * page-breaks for handing in or printing to PDF).
     */
    static String html(ExperimentSpec spec, EcologyFieldDay.Session session,
                       Map<String, String> files) {
        StringBuilder h = new StringBuilder();
        h.append("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n");
        h.append("<title>").append(escapeHtml(spec.name())).append(" — experiment report</title>\n");
        h.append("""
                <style>
                  body { font: 14px/1.5 system-ui, sans-serif; color: #1a1a19; margin: 40px auto;
                         max-width: 860px; padding: 0 20px; }
                  h1 { font-size: 24px; } h2 { font-size: 17px; margin-top: 28px;
                       border-bottom: 1px solid #ddd; padding-bottom: 4px; }
                  pre { background: #f6f6f4; border: 1px solid #e4e4e0; border-radius: 8px;
                        padding: 14px 18px; white-space: pre-wrap; font-size: 12.5px; }
                  table { border-collapse: collapse; margin: 10px 0; }
                  td, th { border: 1px solid #d8d8d4; padding: 4px 12px; font-size: 12.5px;
                           text-align: right; }
                  th { background: #f0f0ed; text-align: left; }
                  td:first-child { text-align: left; }
                  .verdict-CONFIRMED { color: #0a7a0a; font-weight: 600; }
                  .verdict-REFUTED { color: #c03030; font-weight: 600; }
                  section { break-inside: avoid; }
                  footer { margin-top: 40px; color: #888; font-size: 12px; }
                </style>
                </head>
                <body>
                """);
        h.append("<h1>🧪 ").append(escapeHtml(spec.name())).append("</h1>\n");
        h.append("<p>An experiment run by the CSRBT ecology engine — deterministic (seed ")
         .append(spec.seed()).append("), every number reproducible.</p>\n");

        h.append("<section><h2>The narrated report</h2>\n<pre>")
         .append(escapeHtml(session.report())).append("</pre></section>\n");

        for (Map.Entry<String, String> f : files.entrySet()) {
            if (!f.getKey().endsWith(".csv")) continue;
            h.append("<section><h2>").append(escapeHtml(f.getKey().replace(".csv", "")))
             .append("</h2>\n<table>\n");
            String[] lines = f.getValue().split("\n");
            for (int i = 0; i < lines.length; i++) {
                if (lines[i].isEmpty()) continue;
                h.append("<tr>");
                for (String cell : splitCsv(lines[i])) {
                    String tag = i == 0 ? "th" : "td";
                    String cls = (cell.equals("CONFIRMED") || cell.equals("REFUTED"))
                            ? " class=\"verdict-" + cell + "\"" : "";
                    h.append('<').append(tag).append(cls).append('>')
                     .append(escapeHtml(cell)).append("</").append(tag).append('>');
                }
                h.append("</tr>\n");
            }
            h.append("</table></section>\n");
        }
        h.append("<footer>Generated by CSRBT's ecology experiment engine (ADR-019). ")
         .append("CSV files in this bundle open directly in Excel, Google Sheets, or R; ")
         .append("this page prints to PDF.</footer>\n</body>\n</html>\n");
        return h.toString();
    }

    static String escapeHtml(String s) {
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }

    /** Minimal RFC-4180 field splitter (the inverse of {@link #csv}). */
    public static String[] splitCsv(String line) {
        java.util.List<String> out = new java.util.ArrayList<>();
        StringBuilder cur = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (quoted) {
                if (c == '"' && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    cur.append('"');
                    i++;
                } else if (c == '"') {
                    quoted = false;
                } else {
                    cur.append(c);
                }
            } else if (c == '"') {
                quoted = true;
            } else if (c == ',') {
                out.add(cur.toString());
                cur.setLength(0);
            } else {
                cur.append(c);
            }
        }
        out.add(cur.toString());
        return out.toArray(new String[0]);
    }
}
