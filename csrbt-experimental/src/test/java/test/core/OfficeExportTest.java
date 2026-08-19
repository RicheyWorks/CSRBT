package test.core;

import io.github.richeyworks.csrbt.experimental.ecology.ExperimentLab;
import io.github.richeyworks.csrbt.experimental.ecology.ExperimentSpec;
import io.github.richeyworks.csrbt.experimental.ecology.OfficeExport;

import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.CellType;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.xslf.usermodel.XMLSlideShow;
import org.apache.poi.xslf.usermodel.XSLFShape;
import org.apache.poi.xslf.usermodel.XSLFSlide;
import org.apache.poi.xslf.usermodel.XSLFTable;
import org.apache.poi.xslf.usermodel.XSLFTableCell;
import org.apache.poi.xslf.usermodel.XSLFTableRow;
import org.apache.poi.xslf.usermodel.XSLFTextShape;
import org.apache.poi.xssf.usermodel.XSSFSheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * ADR-030 — the native Office exports (ADR-019 §2.6's held trigger, fired):
 * workbook.xlsx mirrors every CSV as a typed sheet, report.pptx narrates the run as
 * slides, and both obey the <b>structural determinism contract</b>: OOXML bytes are
 * not pinned (zip metadata carries wall-clock timestamps), but two runs of the same
 * spec must read back with identical sheet names, cell types, cell values, slide
 * count, and slide text. The CSV/HTML side keeps its byte pin, verified here too.
 */
@DisplayName("OfficeExport — native workbook.xlsx and report.pptx")
class OfficeExportTest {

    /** Same shape as ExperimentLabTest's spec: every verdict, every export family. */
    private static final List<String> SPEC = List.of(
            "name: unit test experiment",
            "keys: 60",
            "seed: 9",
            "window: 100",
            "phase: calm uniform 600",
            "phase: storm hot 600 4 85",
            "phase: churny churn 400 60",
            "model: logistic 0.2 100 5 30",
            "cross: Rr x Rr observed 5474 1850",
            "data: siteA oak=3 fern=2 moss",
            "data: siteB oak=1 pine=4",
            "note: a general note",
            "note(calm): looked even all morning",
            "tree: mini (A,(B,C));",
            "expect: evenness(calm) > 0.9",
            "expect: evenness(storm) > 0.9",          // will be refuted
            "expect: richness(nowhere) > 1");         // ungradeable

    // ── workbook.xlsx ─────────────────────────────────────────────────────────

    @Test
    @DisplayName("workbook: one sheet per CSV in bundle order, bold headers, typed cells")
    void workbookStructure() throws IOException {
        Map<String, String> files = ExperimentLab.runWithExports(ExperimentSpec.parse(SPEC));
        List<String> expectedSheets = new ArrayList<>();
        for (String name : files.keySet()) {
            if (name.endsWith(".csv")) expectedSheets.add(name.replace(".csv", ""));
        }
        try (XSSFWorkbook wb = open(OfficeExport.workbook(files))) {
            assertEquals(expectedSheets.size(), wb.getNumberOfSheets());
            for (int i = 0; i < expectedSheets.size(); i++) {
                assertEquals(expectedSheets.get(i), wb.getSheetName(i));
            }
            XSSFSheet phases = wb.getSheet("phases");
            // Header row: the CSV's own column names, bold.
            assertEquals("phase", phases.getRow(0).getCell(0).getStringCellValue());
            assertTrue(phases.getRow(0).getCell(0).getCellStyle().getFont().getBold(),
                    "header row must be bold");
            // Typed cells: names are text, counts and metrics are real numbers.
            Row calm = phases.getRow(1);
            assertEquals(CellType.STRING, calm.getCell(0).getCellType());
            assertEquals("calm", calm.getCell(0).getStringCellValue());
            assertEquals(CellType.NUMERIC, calm.getCell(2).getCellType());
            assertEquals(600.0, calm.getCell(2).getNumericCellValue(), 0.0);
            // The evenness cell equals the CSV's own value exactly — derived, not recomputed.
            String csvEvenness = files.get("phases.csv").split("\n")[1].split(",")[6];
            assertEquals(Double.parseDouble(csvEvenness),
                    calm.getCell(6).getNumericCellValue(), 0.0);
            // hypotheses sheet: verdict words ride through as text.
            XSSFSheet hyp = wb.getSheet("hypotheses");
            assertEquals("CONFIRMED", hyp.getRow(1).getCell(2).getStringCellValue());
            assertEquals(CellType.NUMERIC, hyp.getRow(1).getCell(1).getCellType());
        }
    }

    // ── report.pptx ───────────────────────────────────────────────────────────

    @Test
    @DisplayName("slides: title + phases table + graded hypotheses + notebook, report wording")
    void slidesStructure() throws IOException {
        ExperimentSpec spec = ExperimentSpec.parse(SPEC);
        Map<String, String> files = ExperimentLab.runWithExports(spec);
        try (XMLSlideShow ppt = openSlides(OfficeExport.slides(spec, files))) {
            assertEquals(4, ppt.getSlides().size());
            List<String> texts = new ArrayList<>();
            for (XSLFSlide s : ppt.getSlides()) texts.add(slideText(s));
            // Title slide: the experiment's name and its deterministic identity line
            // (keys/seed/window from the spec — never the wall clock).
            assertTrue(texts.get(0).contains("unit test experiment"));
            assertTrue(texts.get(0).contains("60 keys, seed 9, window 100 ops"));
            // Phases slide: the summary table, straight from phases.csv.
            assertTrue(texts.get(1).contains("The phases"));
            assertTrue(texts.get(1).contains("calm"));
            assertTrue(texts.get(1).contains("richness"));
            // Hypotheses slide: all three verdicts, in the report's own wording.
            assertTrue(texts.get(2).contains("✅ CONFIRMED"));
            assertTrue(texts.get(2).contains("❌ REFUTED"));
            assertTrue(texts.get(2).contains("⚠ UNGRADEABLE"));
            assertTrue(texts.get(2).contains("evenness(storm) > 0.9"));
            // Notebook slide: both notes, same shape as report.txt.
            assertTrue(texts.get(3).contains("a general note"));
            assertTrue(texts.get(3).contains("[calm]"));
            assertTrue(texts.get(3).contains("looked even all morning"));
        }
    }

    @Test
    @DisplayName("a run without notes simply has no notebook slide — nothing invented")
    void noNotesNoSlide() throws IOException {
        ExperimentSpec spec = ExperimentSpec.parse(List.of(
                "phase: calm uniform 200",
                "expect: evenness(calm) > 0.5"));
        Map<String, String> files = ExperimentLab.runWithExports(spec);
        try (XMLSlideShow ppt = openSlides(OfficeExport.slides(spec, files))) {
            assertEquals(3, ppt.getSlides().size());   // title, phases, hypotheses
        }
    }

    // ── The determinism contract ──────────────────────────────────────────────

    @Test
    @DisplayName("structural determinism: two runs, identical sheets/cells and slides/text")
    void structuralDeterminism() throws IOException {
        Map<String, byte[]> a = ExperimentLab.runWithAllExports(ExperimentSpec.parse(SPEC));
        Map<String, byte[]> b = ExperimentLab.runWithAllExports(ExperimentSpec.parse(SPEC));
        // The Office files are NOT byte-pinned (OOXML zip metadata is wall-clock);
        // the contract is that everything a reader observes is identical.
        assertEquals(workbookContent(a.get("workbook.xlsx")),
                workbookContent(b.get("workbook.xlsx")));
        assertEquals(slidesContent(a.get("report.pptx")),
                slidesContent(b.get("report.pptx")));
    }

    @Test
    @DisplayName("the full bundle: every old file byte-identical, plus the two Office files")
    void bundleGainsOfficeFiles() {
        ExperimentSpec spec = ExperimentSpec.parse(SPEC);
        Map<String, String> text = ExperimentLab.runWithExports(spec);
        Map<String, byte[]> all = ExperimentLab.runWithAllExports(spec);
        assertEquals(text.size() + 2, all.size());
        for (Map.Entry<String, String> e : text.entrySet()) {
            assertArrayEquals(e.getValue().getBytes(StandardCharsets.UTF_8),
                    all.get(e.getKey()), e.getKey() + " must stay byte-identical");
        }
        for (String office : new String[]{ "workbook.xlsx", "report.pptx" }) {
            byte[] bytes = all.get(office);
            assertTrue(bytes != null && bytes.length > 4, "missing " + office);
            assertEquals('P', bytes[0]);   // both are OOXML zip containers
            assertEquals('K', bytes[1]);
        }
    }

    // ── Readback helpers (the contract is defined by what POI reads back) ─────

    private static XSSFWorkbook open(byte[] bytes) throws IOException {
        return new XSSFWorkbook(new ByteArrayInputStream(bytes));
    }

    private static XMLSlideShow openSlides(byte[] bytes) throws IOException {
        return new XMLSlideShow(new ByteArrayInputStream(bytes));
    }

    /** Every sheet name and every cell as "type:value", in order. */
    private static List<String> workbookContent(byte[] bytes) throws IOException {
        List<String> out = new ArrayList<>();
        try (XSSFWorkbook wb = open(bytes)) {
            for (int s = 0; s < wb.getNumberOfSheets(); s++) {
                XSSFSheet sheet = wb.getSheetAt(s);
                out.add("sheet:" + sheet.getSheetName());
                for (Row row : sheet) {
                    for (Cell cell : row) {
                        out.add(cell.getCellType() == CellType.NUMERIC
                                ? String.format(Locale.ROOT, "n:%.10f", cell.getNumericCellValue())
                                : "s:" + cell.getStringCellValue());
                    }
                }
            }
        }
        return out;
    }

    /** Every slide's visible text, in order. */
    private static List<String> slidesContent(byte[] bytes) throws IOException {
        List<String> out = new ArrayList<>();
        try (XMLSlideShow ppt = openSlides(bytes)) {
            for (XSLFSlide slide : ppt.getSlides()) {
                out.add(slideText(slide));
            }
        }
        return out;
    }

    private static String slideText(XSLFSlide slide) {
        StringBuilder sb = new StringBuilder();
        for (XSLFShape shape : slide.getShapes()) {
            if (shape instanceof XSLFTextShape ts) {
                sb.append(ts.getText()).append('\n');
            } else if (shape instanceof XSLFTable table) {
                for (XSLFTableRow row : table.getRows()) {
                    for (XSLFTableCell cell : row.getCells()) {
                        sb.append(cell.getText()).append('|');
                    }
                    sb.append('\n');
                }
            }
        }
        return sb.toString();
    }
}
