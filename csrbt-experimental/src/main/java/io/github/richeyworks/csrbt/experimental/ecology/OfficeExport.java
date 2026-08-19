package io.github.richeyworks.csrbt.experimental.ecology;

import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.util.WorkbookUtil;
import org.apache.poi.xslf.usermodel.XMLSlideShow;
import org.apache.poi.xslf.usermodel.XSLFSlide;
import org.apache.poi.xslf.usermodel.XSLFTable;
import org.apache.poi.xslf.usermodel.XSLFTableCell;
import org.apache.poi.xslf.usermodel.XSLFTableRow;
import org.apache.poi.xslf.usermodel.XSLFTextBox;
import org.apache.poi.xslf.usermodel.XSLFTextParagraph;
import org.apache.poi.xslf.usermodel.XSLFTextRun;
import org.apache.poi.xssf.usermodel.XSSFCellStyle;
import org.apache.poi.xssf.usermodel.XSSFFont;
import org.apache.poi.xssf.usermodel.XSSFRow;
import org.apache.poi.xssf.usermodel.XSSFSheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;

import java.awt.Color;
import java.awt.geom.Rectangle2D;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * The native Office side of the experiment bundle — ADR-019 §2.6's held trigger,
 * fired: alongside the Excel-ready CSVs and the PowerPoint-ready HTML, the bundle
 * now carries a real {@code workbook.xlsx} and a real {@code report.pptx}.
 *
 * <p>Both files are <b>derived verbatim from the text bundle</b> ({@code *.csv},
 * {@code report.txt}) — nothing is recomputed here, so a cell in the workbook is
 * exactly the value in the CSV and a verdict on a slide is exactly the verdict in
 * the report. The workbook gets one sheet per logical CSV, in bundle order, with a
 * bold header row and properly typed cells (numbers are numeric cells, not text).
 * The deck gets a title slide, the phases summary table, the graded hypotheses in
 * the report's own ✅/❌/⚠ wording, and the field notebook.</p>
 *
 * <p><b>Determinism contract (structural, not byte).</b> OOXML files are zip
 * archives whose entry metadata (and docProps timestamps) POI stamps with the wall
 * clock, so the bytes are <i>not</i> pinned. What is pinned — by
 * {@code OfficeExportTest} — is everything a reader can observe: running the same
 * spec twice yields identical sheet names, cell types and cell values, and an
 * identical slide count with identical slide text. The CSV/HTML/JSON side of the
 * bundle keeps its stronger byte-for-byte pin untouched.</p>
 */
public final class OfficeExport {

    private OfficeExport() {}

    /** A field is a number iff it is exactly a plain decimal — never guessed. */
    private static final Pattern NUMERIC =
            Pattern.compile("-?\\d+(\\.\\d+)?([eE][+-]?\\d+)?");

    /** One shared body font so the deck renders the same everywhere. */
    private static final String FONT = "Calibri";

    private static final Color INK = new Color(0x1a, 0x1a, 0x19);
    private static final Color MUTED = new Color(0x66, 0x66, 0x60);
    private static final Color HEADER_FILL = new Color(0xf0, 0xf0, 0xed);
    private static final Color CONFIRMED_GREEN = new Color(0x0a, 0x7a, 0x0a);
    private static final Color REFUTED_RED = new Color(0xc0, 0x30, 0x30);
    private static final Color UNGRADEABLE_AMBER = new Color(0xa0, 0x70, 0x00);

    // ── workbook.xlsx ─────────────────────────────────────────────────────────

    /**
     * One sheet per logical CSV in the bundle, in bundle order (phases, data, drift,
     * notes, trees, model-series, punnett, crosses, hypotheses — whichever the run
     * produced). Header row bold; every field that is exactly a plain decimal
     * becomes a numeric cell, everything else stays text.
     */
    public static byte[] workbook(Map<String, String> files) {
        try (XSSFWorkbook wb = new XSSFWorkbook();
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            XSSFFont bold = wb.createFont();
            bold.setBold(true);
            XSSFCellStyle headerStyle = wb.createCellStyle();
            headerStyle.setFont(bold);

            for (Map.Entry<String, String> f : files.entrySet()) {
                if (!f.getKey().endsWith(".csv")) continue;
                String sheetName = WorkbookUtil.createSafeSheetName(
                        f.getKey().substring(0, f.getKey().length() - ".csv".length()));
                XSSFSheet sheet = wb.createSheet(sheetName);
                String[] lines = f.getValue().split("\n");
                int rowIdx = 0;
                for (String line : lines) {
                    if (line.isEmpty()) continue;
                    XSSFRow row = sheet.createRow(rowIdx);
                    String[] fields = ExperimentExport.splitCsv(line);
                    for (int c = 0; c < fields.length; c++) {
                        Cell cell = row.createCell(c);
                        if (rowIdx == 0) {
                            cell.setCellValue(fields[c]);
                            cell.setCellStyle(headerStyle);
                        } else if (NUMERIC.matcher(fields[c]).matches()) {
                            cell.setCellValue(Double.parseDouble(fields[c]));
                        } else {
                            cell.setCellValue(fields[c]);
                        }
                    }
                    rowIdx++;
                }
            }
            wb.write(out);
            return out.toByteArray();
        } catch (IOException e) {
            throw new UncheckedIOException("workbook.xlsx assembly failed", e);
        }
    }

    // ── report.pptx ───────────────────────────────────────────────────────────

    /**
     * The deck a student can present from: a title slide (the experiment's name and
     * its identity line — keys, seed, window; deterministic, never the wall clock),
     * then one slide per major section that exists in this run: the phases summary
     * table, the graded hypotheses in the report's own ✅/❌/⚠ wording, and the
     * field notebook. Everything on a slide is quoted from the bundle's own files.
     */
    public static byte[] slides(ExperimentSpec spec, Map<String, String> files) {
        try (XMLSlideShow ppt = new XMLSlideShow();
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {

            titleSlide(ppt, spec);
            if (files.containsKey("phases.csv")) {
                phasesSlide(ppt, files.get("phases.csv"));
            }
            if (files.containsKey("hypotheses.csv")) {
                hypothesesSlide(ppt, files.get("hypotheses.csv"));
            }
            if (!spec.notes().isEmpty()) {
                notesSlide(ppt, spec.notes());
            }

            ppt.write(out);
            return out.toByteArray();
        } catch (IOException e) {
            throw new UncheckedIOException("report.pptx assembly failed", e);
        }
    }

    private static void titleSlide(XMLSlideShow ppt, ExperimentSpec spec) {
        XSLFSlide slide = ppt.createSlide();
        XSLFTextBox title = slide.createTextBox();
        title.setAnchor(new Rectangle2D.Double(40, 170, 640, 120));
        run(title.addNewTextParagraph(), "🧪 " + spec.name(), 34.0, true, INK);

        XSLFTextBox sub = slide.createTextBox();
        sub.setAnchor(new Rectangle2D.Double(40, 300, 640, 90));
        run(sub.addNewTextParagraph(), String.format(Locale.ROOT,
                "%d keys, seed %d, window %d ops — %d phase(s), %d model(s), %d hypothesis(es)",
                spec.keys(), spec.seed(), spec.window(), spec.phases().size(),
                spec.models().size(), spec.expectations().size()), 16.0, false, MUTED);
        run(sub.addNewTextParagraph(),
                "Run by the CSRBT ecology experiment engine — deterministic; "
                        + "every number on these slides reproduces from the spec.",
                13.0, false, MUTED);
    }

    private static void phasesSlide(XMLSlideShow ppt, String phasesCsv) {
        XSLFSlide slide = sectionSlide(ppt, "The phases");
        List<String[]> rows = new ArrayList<>();
        for (String line : phasesCsv.split("\n")) {
            if (!line.isEmpty()) rows.add(ExperimentExport.splitCsv(line));
        }
        if (rows.isEmpty()) return;
        int cols = rows.get(0).length;
        XSLFTable table = slide.createTable(rows.size(), cols);
        table.setAnchor(new Rectangle2D.Double(30, 90, 660, 40.0 + 22.0 * rows.size()));
        double colWidth = 660.0 / cols;
        for (int c = 0; c < cols; c++) {
            table.setColumnWidth(c, colWidth);
        }
        for (int r = 0; r < rows.size(); r++) {
            XSLFTableRow row = table.getRows().get(r);
            row.setHeight(22);
            String[] fields = rows.get(r);
            for (int c = 0; c < cols; c++) {
                XSLFTableCell cell = row.getCells().get(c);
                if (r == 0) cell.setFillColor(HEADER_FILL);
                XSLFTextRun tr = cell.setText(c < fields.length ? fields[c] : "");
                tr.setFontFamily(FONT);
                tr.setFontSize(r == 0 ? 11.0 : 10.0);
                tr.setBold(r == 0);
                tr.setFontColor(INK);
            }
        }
    }

    private static void hypothesesSlide(XMLSlideShow ppt, String hypothesesCsv) {
        XSLFSlide slide = sectionSlide(ppt, "The hypotheses, graded");
        XSLFTextBox body = slide.createTextBox();
        body.setAnchor(new Rectangle2D.Double(40, 100, 640, 380));
        String[] lines = hypothesesCsv.split("\n");
        for (int i = 1; i < lines.length; i++) {           // skip the CSV header
            if (lines[i].isEmpty()) continue;
            String[] f = ExperimentExport.splitCsv(lines[i]);   // hypothesis,observed,verdict
            String verdict = f.length > 2 ? f[2] : "";
            // The report's own wording, verbatim (✅ CONFIRMED / ❌ REFUTED / ⚠ UNGRADEABLE).
            String marker = switch (verdict) {
                case "CONFIRMED" -> "✅ CONFIRMED";
                case "REFUTED" -> "❌ REFUTED";
                default -> "⚠ UNGRADEABLE";
            };
            Color color = switch (verdict) {
                case "CONFIRMED" -> CONFIRMED_GREEN;
                case "REFUTED" -> REFUTED_RED;
                default -> UNGRADEABLE_AMBER;
            };
            XSLFTextParagraph p = body.addNewTextParagraph();
            p.setSpaceAfter(8.0);
            run(p, marker + "  ", 15.0, true, color);
            run(p, f[0], 15.0, false, INK);
            if (f.length > 1 && !f[1].isEmpty()) {
                run(p, "   (observed " + f[1] + ")", 12.0, false, MUTED);
            }
        }
    }

    private static void notesSlide(XMLSlideShow ppt, List<ExperimentSpec.Note> notes) {
        XSLFSlide slide = sectionSlide(ppt, "The field notebook");
        XSLFTextBox body = slide.createTextBox();
        body.setAnchor(new Rectangle2D.Double(40, 100, 640, 380));
        for (ExperimentSpec.Note n : notes) {
            XSLFTextParagraph p = body.addNewTextParagraph();
            p.setSpaceAfter(8.0);
            // Same shape as report.txt: "• text" or "[about] text".
            run(p, n.about() == null ? "•" : "[" + n.about() + "]", 15.0, true, MUTED);
            run(p, " " + n.text(), 15.0, false, INK);
        }
    }

    private static XSLFSlide sectionSlide(XMLSlideShow ppt, String heading) {
        XSLFSlide slide = ppt.createSlide();
        XSLFTextBox title = slide.createTextBox();
        title.setAnchor(new Rectangle2D.Double(40, 25, 640, 50));
        run(title.addNewTextParagraph(), heading, 24.0, true, INK);
        return slide;
    }

    private static void run(XSLFTextParagraph p, String text, double size, boolean bold,
                            Color color) {
        XSLFTextRun r = p.addNewTextRun();
        r.setText(text);
        r.setFontFamily(FONT);
        r.setFontSize(size);
        r.setBold(bold);
        r.setFontColor(color);
    }
}
