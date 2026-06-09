package core.ensemble;

/**
 * Read mode for an {@link EnsembleOrderedSet} (ADR-003).
 *
 * <ul>
 *   <li>{@link #MIRROR} (default) -- reads are served by the primary alone (1x read cost). Members
 *       are kept in exact sync; promotion (E2) and the cadence health check (E3) provide adaptation
 *       and fault recovery.</li>
 *   <li>{@link #VERIFIED} -- every read is fanned out to a quorum of ACTIVE members, the
 *       strict-majority answer is served, and a dissenting member is quarantined (E4). This is
 *       N-version programming applied to the data structure: it catches a strategy bug or memory
 *       corruption that is internally self-consistent and so escapes the per-member health check
 *       (including a wrong primary). It costs a quorum-many reads and needs at least three members
 *       to adjudicate.</li>
 * </ul>
 */
public enum EnsembleMode {
    MIRROR,
    VERIFIED
}
