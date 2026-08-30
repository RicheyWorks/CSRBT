package io.github.richeyworks.csrbt.experimental.ecology;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * A reader for <b>Darwin Core</b> occurrence records — the seam between this kit's two halves
 * (ADR-107).
 *
 * <p>The kit's field pages ({@code releve.html}, {@code stand-sheet.html},
 * {@code collection-sheet.html}) already record an observation properly and export Darwin Core.
 * The experiment engine already holds the analysis. Until this class, they could not speak: an
 * observation entered correctly in the field half had to be retyped, badly, to reach the analysis
 * half. That is what a photograph of a hillside above Lake Tahoe surfaced, and it was a worse
 * problem than the six missing directives it was first mistaken for.</p>
 *
 * <p><b>Why a standard rather than six new directives.</b> Every field the {@code .eco} grammar was
 * accused of lacking already exists in Darwin Core, and has since long before this kit:</p>
 *
 * <ul>
 *   <li>coordinates → {@code decimalLatitude}, {@code decimalLongitude},
 *       {@code coordinateUncertaintyInMeters}</li>
 *   <li>elevation → {@code minimumElevationInMeters}</li>
 *   <li>date and observer → {@code eventDate}, {@code recordedBy}</li>
 *   <li>cover as distinct from a count → {@code organismQuantity} +
 *       {@code organismQuantityType}</li>
 *   <li>identification confidence → {@code identificationQualifier}</li>
 *   <li>evidence → {@code associatedMedia}</li>
 * </ul>
 *
 * <p>And because GBIF, iNaturalist, the Consortium of California Herbaria and MyCoPortal all publish
 * this same standard, one reader opens both the kit's own field pages and the public record.</p>
 *
 * <h2>The rule this class exists to enforce</h2>
 *
 * <p>{@code organismQuantityType} is not decoration. A relevé records <b>cover</b>; a trap line
 * records <b>individuals</b>; and the estimators care enormously which. Chao1 and rarefaction are
 * built on counts of individuals — they reason about how many species were missed given how many
 * individuals were caught — and handing them percent cover produces a confident number with no
 * meaning. So an archive knows which kind it holds, {@link Archive#abundance()} <b>refuses</b> to
 * return counts for cover data, and {@link Archive#cover()} refuses the reverse. Shannon, Simpson,
 * evenness and Bray–Curtis are proportional and are fine either way; that distinction is the whole
 * point of keeping the type.</p>
 *
 * <p>Parsing follows the house rule: a malformed row is reported and skipped, never guessed at. An
 * absent coordinate stays absent — it never becomes {@code 0}, which would read as a claim of
 * perfect precision at Null Island, the same discipline {@code verify_dwc} already enforces on the
 * export side.</p>
 */
public final class DarwinCore {

    private DarwinCore() {}

    /** What {@code organismQuantity} is counting. */
    public enum Quantity { INDIVIDUALS, COVER, UNKNOWN }

    /** One occurrence record, with only the terms this kit consumes. */
    public record Occurrence(String occurrenceID, String scientificName,
                             double quantity, Quantity quantityKind, String quantityType,
                             String eventDate, String recordedBy,
                             Double latitude, Double longitude, Double coordinateUncertaintyM,
                             Double elevationM, String basisOfRecord,
                             String identificationQualifier, String associatedMedia,
                             String locality) {

        /** True when the identification is explicitly hedged ({@code cf.}, {@code aff.}, {@code sp.}). */
        public boolean uncertain() {
            return identificationQualifier != null && !identificationQualifier.isBlank();
        }
    }

    /** The event's site, as far as the records agree on one. Any field may be null. */
    public record Site(Double latitude, Double longitude, Double coordinateUncertaintyM,
                       Double elevationM, String locality, String eventDate, String recordedBy) {}

    /** A parsed set of occurrence records plus everything that could not be read. */
    public record Archive(List<Occurrence> records, List<String> problems,
                          Quantity quantityKind, Site site) {

        /**
         * Counts by taxon, for the estimators that assume individuals.
         *
         * @throws IllegalStateException if the archive holds cover, because Chao1 and rarefaction
         *         would return a confident number about a quantity they do not model
         */
        public LinkedHashMap<String, Long> abundance() {
            if (quantityKind == Quantity.COVER) {
                throw new IllegalStateException(
                        "this archive records cover, not individuals — use cover(); Chao1 and "
                        + "rarefaction do not apply to cover data");
            }
            LinkedHashMap<String, Long> out = new LinkedHashMap<>();
            for (Occurrence o : records) {
                out.merge(o.scientificName(), Math.round(o.quantity()), Long::sum);
            }
            return out;
        }

        /**
         * Cover by taxon.
         *
         * @throws IllegalStateException if the archive holds individual counts
         */
        public LinkedHashMap<String, Double> cover() {
            if (quantityKind == Quantity.INDIVIDUALS) {
                throw new IllegalStateException(
                        "this archive records individuals, not cover — use abundance()");
            }
            LinkedHashMap<String, Double> out = new LinkedHashMap<>();
            for (Occurrence o : records) {
                out.merge(o.scientificName(), o.quantity(), Double::sum);
            }
            return out;
        }

        /**
         * Cover scaled to integer parts per ten-thousand, so the proportional indices — Shannon,
         * Simpson, evenness, Bray–Curtis — can be computed by the existing
         * {@code Map<T, Long>} instruments without pretending the values are individuals.
         *
         * <p>This is a deliberate narrow door. It exists so that proportional measures work on
         * cover, and it does not make {@link #abundance()} legal: the richness estimators stay
         * refused, because scaling a percentage does not turn it into a headcount.</p>
         */
        public LinkedHashMap<String, Long> proportionalWeights() {
            LinkedHashMap<String, Double> c = quantityKind == Quantity.COVER ? cover() : null;
            if (c == null) return abundance();
            double total = c.values().stream().mapToDouble(Double::doubleValue).sum();
            LinkedHashMap<String, Long> out = new LinkedHashMap<>();
            if (total <= 0) return out;
            for (Map.Entry<String, Double> e : c.entrySet()) {
                out.put(e.getKey(), Math.round(e.getValue() / total * 10_000.0));
            }
            return out;
        }

        /** Taxa whose identification the recorder hedged. */
        public List<String> uncertainTaxa() {
            List<String> out = new ArrayList<>();
            for (Occurrence o : records) {
                if (o.uncertain() && !out.contains(o.scientificName())) out.add(o.scientificName());
            }
            return out;
        }
    }

    // ── Reading ───────────────────────────────────────────────────────────────

    /**
     * Read Darwin Core records from a header row plus data rows. Comma- or tab-delimited: GBIF
     * ships tab-separated, the kit's own pages export comma-separated, and the delimiter is taken
     * from whichever the header actually contains.
     */
    public static Archive read(List<String> lines) {
        List<Occurrence> records = new ArrayList<>();
        List<String> problems = new ArrayList<>();
        List<String> rows = new ArrayList<>();
        for (String l : lines) {
            if (l != null && !l.isBlank()) rows.add(l);
        }
        if (rows.isEmpty()) {
            return new Archive(List.of(), List.of("empty input: no header row"),
                    Quantity.UNKNOWN, new Site(null, null, null, null, null, null, null));
        }

        boolean tab = rows.get(0).indexOf('\t') >= 0;
        String[] header = split(rows.get(0), tab);
        Map<String, Integer> col = new LinkedHashMap<>();
        for (int i = 0; i < header.length; i++) {
            col.put(header[i].trim().toLowerCase(Locale.ROOT), i);
        }
        if (!col.containsKey("scientificname")) {
            problems.add("no scientificName column — this is not a Darwin Core occurrence table");
            return new Archive(List.of(), problems, Quantity.UNKNOWN,
                    new Site(null, null, null, null, null, null, null));
        }

        Quantity kind = Quantity.UNKNOWN;
        Site site = null;

        for (int r = 1; r < rows.size(); r++) {
            String[] f = split(rows.get(r), tab);
            String name = get(f, col, "scientificname");
            if (name == null || name.isBlank()) {
                problems.add("row " + (r + 1) + ": no scientificName");
                continue;
            }
            String qType = get(f, col, "organismquantitytype");
            Quantity rowKind = classify(qType);
            double q;
            String qRaw = get(f, col, "organismquantity");
            String iRaw = get(f, col, "individualcount");
            try {
                if (qRaw != null && !qRaw.isBlank()) {
                    q = Double.parseDouble(qRaw.trim());
                } else if (iRaw != null && !iRaw.isBlank()) {
                    q = Double.parseDouble(iRaw.trim());
                    if (rowKind == Quantity.UNKNOWN) rowKind = Quantity.INDIVIDUALS;
                } else {
                    q = 1;                       // a record with no quantity is one occurrence
                    if (rowKind == Quantity.UNKNOWN) rowKind = Quantity.INDIVIDUALS;
                }
            } catch (NumberFormatException bad) {
                problems.add("row " + (r + 1) + ": quantity '"
                        + (qRaw != null && !qRaw.isBlank() ? qRaw : iRaw) + "' is not a number");
                continue;
            }
            if (q < 0) {
                problems.add("row " + (r + 1) + ": negative quantity " + q);
                continue;
            }
            if (rowKind == Quantity.UNKNOWN) {
                problems.add("row " + (r + 1) + ": organismQuantityType '" + qType
                        + "' is neither individuals nor a cover measure");
                continue;
            }
            if (kind == Quantity.UNKNOWN) {
                kind = rowKind;
            } else if (kind != rowKind) {
                problems.add("row " + (r + 1) + ": mixes " + rowKind + " into a "
                        + kind + " archive — these cannot be pooled");
                continue;
            }

            Double lat = num(get(f, col, "decimallatitude"), problems, r, "decimalLatitude");
            Double lon = num(get(f, col, "decimallongitude"), problems, r, "decimalLongitude");
            Double unc = num(get(f, col, "coordinateuncertaintyinmeters"), problems, r,
                    "coordinateUncertaintyInMeters");
            Double elev = num(get(f, col, "minimumelevationinmeters"), problems, r,
                    "minimumElevationInMeters");

            Occurrence o = new Occurrence(
                    get(f, col, "occurrenceid"), name.trim(), q, rowKind, qType,
                    get(f, col, "eventdate"), get(f, col, "recordedby"),
                    lat, lon, unc, elev, get(f, col, "basisofrecord"),
                    get(f, col, "identificationqualifier"), get(f, col, "associatedmedia"),
                    get(f, col, "locality"));
            records.add(o);

            if (site == null) {
                site = new Site(lat, lon, unc, elev, o.locality(), o.eventDate(), o.recordedBy());
            } else if (lat != null && site.latitude() != null
                    && (Math.abs(lat - site.latitude()) > 1e-6
                        || (lon != null && site.longitude() != null
                            && Math.abs(lon - site.longitude()) > 1e-6))) {
                problems.add("row " + (r + 1) + ": coordinates differ from the first record — "
                        + "this file holds more than one site and must be split before analysis");
            }
        }
        if (site == null) site = new Site(null, null, null, null, null, null, null);
        return new Archive(List.copyOf(records), List.copyOf(problems), kind, site);
    }

    /**
     * Which quantity a {@code organismQuantityType} names. Recognises the cover vocabularies a
     * vegetation plot actually uses — percent cover, Braun-Blanquet, Domin — because reading one of
     * those as a headcount is the specific mistake this class prevents.
     */
    public static Quantity classify(String type) {
        if (type == null || type.isBlank()) return Quantity.UNKNOWN;
        String t = type.trim().toLowerCase(Locale.ROOT);
        if (t.contains("cover") || t.contains("braun") || t.contains("blanquet")
                || t.contains("domin") || t.contains("daubenmire") || t.equals("%")) {
            return Quantity.COVER;
        }
        if (t.contains("individual") || t.contains("count") || t.contains("stem")
                || t.contains("specimen")) {
            return Quantity.INDIVIDUALS;
        }
        return Quantity.UNKNOWN;
    }

    private static String[] split(String line, boolean tab) {
        return tab ? line.split("\t", -1) : ExperimentExport.splitCsv(line);
    }

    private static String get(String[] f, Map<String, Integer> col, String term) {
        Integer i = col.get(term);
        if (i == null || i >= f.length) return null;
        String v = f[i];
        return v == null || v.isBlank() ? null : v.trim();
    }

    /** Absent stays absent. A blank coordinate must never become 0. */
    private static Double num(String v, List<String> problems, int row, String term) {
        if (v == null || v.isBlank()) return null;
        try {
            return Double.valueOf(v.trim());
        } catch (NumberFormatException bad) {
            problems.add("row " + (row + 1) + ": " + term + " '" + v + "' is not a number");
            return null;
        }
    }
}
