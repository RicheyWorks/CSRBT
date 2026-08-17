package test.core;

import io.github.richeyworks.csrbt.OrderedSet;
import io.github.richeyworks.csrbt.TreeContext;
import io.github.richeyworks.csrbt.control.MorphPolicy;
import io.github.richeyworks.csrbt.control.RollingWorkloadMonitor;
import io.github.richeyworks.csrbt.ensemble.EnsembleMember;
import io.github.richeyworks.csrbt.ensemble.EnsembleMode;
import io.github.richeyworks.csrbt.ensemble.EnsembleOrderedSet;
import io.github.richeyworks.csrbt.evolution.PolicyBandit;
import io.github.richeyworks.csrbt.evolution.PolicyEvolutionController;
import io.github.richeyworks.csrbt.evolution.PolicyGenome;
import io.github.richeyworks.csrbt.evolution.PolicySearchController;
import io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.LoadResult;
import io.github.richeyworks.csrbt.persistence.FilePersistenceAdapter;
import io.github.richeyworks.csrbt.persistence.KeySerializer;
import io.github.richeyworks.csrbt.strategy.AVLStrategy;
import io.github.richeyworks.csrbt.strategy.HybridStrategy;
import io.github.richeyworks.csrbt.strategy.RedBlackStrategy;
import io.github.richeyworks.csrbt.strategy.SplayStrategy;
import io.github.richeyworks.csrbt.strategy.TreeStrategy;

import org.apache.logging.log4j.Level;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.apache.logging.log4j.core.appender.AbstractAppender;
import org.apache.logging.log4j.core.config.Configurator;
import org.apache.logging.log4j.core.config.Property;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Wiring audit 2026-08-17 (seventh pass) — the regression pins for findings 1, 2, 5 and 6.
 *
 * <p>Each nested class is one finding, and each was verified red by reverting its fix in
 * isolation. Nothing here mocks the code under test: the persistence probes run against the real
 * filesystem, the controller probes run a real ensemble through a real fan-out.</p>
 */
@DisplayName("Wiring audit 2026-08-17 (seventh pass)")
class SeventhPassWiringTest {

    private static final Path DIR = Paths.get("snapshots");
    private final List<Path> litter = new ArrayList<>();

    @AfterEach
    void cleanUp() throws IOException {
        for (Path p : litter) {
            if (Files.isDirectory(p)) {
                try (Stream<Path> walk = Files.walk(p)) {
                    for (Path q : walk.sorted(Comparator.reverseOrder()).toList()) Files.deleteIfExists(q);
                }
            } else {
                Files.deleteIfExists(p);
            }
        }
        litter.clear();
    }

    private String snap(String base) {
        String name = "p7_" + base + "_" + System.nanoTime();
        litter.add(DIR.resolve(name + ".rbt"));
        return name;
    }

    /**
     * Make the commit rename fail: a NON-EMPTY DIRECTORY at the target path. {@code Files.move}
     * onto it fails on every POSIX filesystem regardless of the running uid, so the probe cannot
     * silently pass under root the way a read-only-directory probe would (ADR-025's own note).
     */
    private void blockCommit(String name) throws IOException {
        Files.createDirectories(DIR.resolve(name + ".rbt").resolve("occupant"));
    }

    private static EnsembleOrderedSet<Integer> mirror(int members) {
        EnsembleOrderedSet.Builder<Integer> b =
                EnsembleOrderedSet.builder(Comparator.<Integer>naturalOrder());
        List<java.util.function.Supplier<TreeStrategy<Integer>>> pool =
                List.of(RedBlackStrategy::new, AVLStrategy::new, SplayStrategy::new, HybridStrategy::new);
        for (int i = 0; i < members; i++) {
            java.util.function.Supplier<TreeStrategy<Integer>> s = pool.get(i % pool.size());
            b.member(s::get);
        }
        return b.build();
    }

    // ── Finding 1 ───────────────────────────────────────────────────────────────────────

    /**
     * A {@code null} {@code KeySerializer} is a caller defect on <em>both</em> ensemble-load
     * branches. It used to be checked only inside {@code tryLoadOrderedSet}, i.e. only on the
     * structured branch; against a {@code PersistentTreeEngine} (flat) snapshot the null reached
     * {@code readFlatKeys}, NPE'd on the first key token, and was reported
     * {@link io.github.richeyworks.csrbt.interfaces.TreePersistenceAdapter.LoadStatus#MALFORMED} —
     * the adapter blaming a perfectly good file for the caller's bug, which is the exact class of
     * wrong answer ADR-026 exists to remove.
     */
    @Nested
    @DisplayName("finding 1 — loadEnsemble validates its serializer on both branches, before any I/O")
    class EnsembleLoadArgumentParity {

        private EnsembleOrderedSet<Integer> target() {
            return EnsembleOrderedSet.<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(RedBlackStrategy::new).member(AVLStrategy::new).build();
        }

        @Test
        @DisplayName("the flat (persistent-engine) branch throws instead of calling a good file malformed")
        void flatBranchRejectsNullSerializer() {
            FilePersistenceAdapter io = new FilePersistenceAdapter();
            String name = snap("flat");

            EnsembleOrderedSet<Integer> source = EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .persistentMember().member(RedBlackStrategy::new).build();
            for (int i = 0; i < 20; i++) source.add(i);
            io.saveSnapshot(name, source, KeySerializer.INTEGER);

            EnsembleOrderedSet<Integer> dst = target();
            assertThrows(IllegalArgumentException.class,
                    () -> io.tryLoadEnsemble(name, null, dst),
                    "a null KeySerializer is a caller defect: deterministic, not retryable, "
                            + "and fixed by changing code rather than by changing the disk");
            assertThrows(IllegalArgumentException.class,
                    () -> io.loadEnsemble(name, null, dst),
                    "the published boolean shape must agree with its reporting twin");

            // And the file it used to blame is intact and still loadable.
            assertTrue(io.loadEnsemble(name, KeySerializer.INTEGER, dst));
            assertEquals(20, dst.size());
        }

        @Test
        @DisplayName("the structured branch behaves identically (the parity this restores)")
        void structuredBranchRejectsNullSerializer() {
            FilePersistenceAdapter io = new FilePersistenceAdapter();
            String name = snap("struct");

            OrderedSet<Integer> source = new OrderedSet<>(new RedBlackStrategy<Integer>(),
                    Comparator.<Integer>naturalOrder());
            for (int i = 0; i < 20; i++) source.add(i);
            io.saveSnapshot(name, source, KeySerializer.INTEGER);

            EnsembleOrderedSet<Integer> dst = target();
            assertThrows(IllegalArgumentException.class, () -> io.tryLoadEnsemble(name, null, dst));
        }

        @Test
        @DisplayName("validation precedes I/O: an absent snapshot still throws, not ABSENT")
        void argumentCheckPrecedesTheFilesystem() {
            FilePersistenceAdapter io = new FilePersistenceAdapter();
            EnsembleOrderedSet<Integer> dst = target();
            assertThrows(IllegalArgumentException.class,
                    () -> io.tryLoadEnsemble("p7_nothing_here_" + System.nanoTime(), null, dst));
            assertThrows(IllegalArgumentException.class,
                    () -> io.tryLoadEnsemble("whatever", KeySerializer.INTEGER, null));
        }

        @Test
        @DisplayName("a real malformed flat snapshot is still MALFORMED — the guard is not a blanket")
        void genuineMalformationStillReported() throws IOException {
            FilePersistenceAdapter io = new FilePersistenceAdapter();
            String name = snap("trunc");

            EnsembleOrderedSet<Integer> source = EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .persistentMember().member(RedBlackStrategy::new).build();
            for (int i = 0; i < 40; i++) source.add(i);
            io.saveSnapshot(name, source, KeySerializer.INTEGER);

            Path file = DIR.resolve(name + ".rbt");
            List<String> lines = Files.readAllLines(file);
            Files.write(file, List.of(lines.get(0), lines.get(1).substring(0, lines.get(1).length() / 2)));

            EnsembleOrderedSet<Integer> dst = target();
            for (int i = 900; i < 905; i++) dst.add(i);
            LoadResult<EnsembleOrderedSet<Integer>> r = io.tryLoadEnsemble(name, KeySerializer.INTEGER, dst);
            assertTrue(r.malformed(), "a truncated file is still the file's fault: " + r);
            assertEquals(5, dst.size(), "and the target is still left untouched");
        }
    }

    // ── Finding 2 ───────────────────────────────────────────────────────────────────────

    /**
     * {@code TreeContext.saveSnapshot} logged {@code "Snapshot saved: 'x'"} unconditionally, so a
     * failed save produced the adapter's ERROR line followed immediately by the facade announcing
     * success. ADR-025 gave the adapter the signal and ADR-026 migrated the facade's <em>load</em>
     * onto its twin; the save-side twin in the same class was left behind.
     */
    @Nested
    @DisplayName("finding 2 — TreeContext.saveSnapshot does not announce a save that failed")
    class FacadeSaveReporting {

        /** Minimal programmatic Log4j2 appender (the MorphControllerTest pattern). */
        private final class Capture extends AbstractAppender {
            final List<String> messages = Collections.synchronizedList(new ArrayList<>());
            Capture() { super("p7SaveCap", null, null, true, Property.EMPTY_ARRAY); }
            @Override public void append(LogEvent e) { messages.add(e.getMessage().getFormattedMessage()); }
        }

        /**
         * Run {@code body} with {@code TreeContext}'s logger raised to INFO and captured. The
         * success line is INFO, so without the raise the appender would never see it and the
         * assertions below would pass vacuously against the pre-fix code.
         */
        private List<String> capturing(Runnable body) {
            String loggerName = TreeContext.class.getName();
            Configurator.setLevel(loggerName, Level.INFO);
            Logger core = (Logger) LogManager.getLogger(TreeContext.class);
            Capture cap = new Capture();
            cap.start();
            core.addAppender(cap);
            try {
                body.run();
            } finally {
                core.removeAppender(cap);
                cap.stop();
                Configurator.setLevel(loggerName, Level.WARN);
            }
            return cap.messages;
        }

        private TreeContext context(int n) {
            TreeContext ctx = new TreeContext(new RedBlackStrategy<Integer>());
            for (int i = 0; i < n; i++) ctx.add(i);
            return ctx;
        }

        @Test
        @DisplayName("a save whose commit cannot publish is reported as not saved")
        void failedSaveIsNotAnnouncedAsSuccess() throws IOException {
            String name = snap("failsave");
            blockCommit(name);
            TreeContext ctx = context(9);

            List<String> lines = capturing(() -> ctx.saveSnapshot(name));

            assertFalse(lines.stream().anyMatch(m -> m.contains("Snapshot saved")),
                    "the facade must not announce a save that did not happen: " + lines);
            assertTrue(lines.stream().anyMatch(m -> m.contains("was NOT saved")),
                    "the caller is told, in the facade's own voice: " + lines);
        }

        @Test
        @DisplayName("a save that does publish is still announced — the pin is not vacuous")
        void successfulSaveIsStillAnnounced() {
            String name = snap("oksave");
            TreeContext ctx = context(9);

            List<String> lines = capturing(() -> ctx.saveSnapshot(name));

            assertTrue(lines.stream().anyMatch(m -> m.contains("Snapshot saved")),
                    "a real save still reports success: " + lines);
            assertTrue(Files.exists(DIR.resolve(name + ".rbt")));
        }

        @Test
        @DisplayName("behavior is unchanged: still void, still non-throwing, previous file intact")
        void publishedBehaviorIsUnchanged() throws IOException {
            String good = snap("keep");
            TreeContext ctx = context(9);
            ctx.saveSnapshot(good);
            long before = Files.size(DIR.resolve(good + ".rbt"));

            String blocked = snap("blocked");
            blockCommit(blocked);
            ctx.saveSnapshot(blocked);   // must not throw

            assertEquals(before, Files.size(DIR.resolve(good + ".rbt")),
                    "a failed save leaves every other snapshot alone");
            assertEquals(9, ctx.getSize(), "and leaves the live context alone");
        }
    }

    // ── Finding 5 ───────────────────────────────────────────────────────────────────────

    /**
     * {@code EnsembleOrderedSet.buildAllFromSorted} — the ensemble face of ADR-014's O(n) bulk
     * build — had no production caller and no test at all, while
     * {@code AUDIT-2026-07-14-capability-coverage.md} listed it as covered by "BulkBuildTest |
     * BulkBuildFeeder ensemble path", which does not exist. The capability works; this is the
     * coverage the table claimed.
     */
    @Nested
    @DisplayName("finding 5 — buildAllFromSorted is exercised, not merely claimed")
    class EnsembleBulkBuild {

        private static List<Integer> ascending(int n) {
            List<Integer> keys = new ArrayList<>(n);
            for (int i = 0; i < n; i++) keys.add(i);
            return keys;
        }

        @Test
        @DisplayName("every member ends an exact mirror, in MIRROR and in VERIFIED")
        void buildsEveryMemberExactly() {
            for (EnsembleMode mode : List.of(EnsembleMode.MIRROR, EnsembleMode.VERIFIED)) {
                EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet
                        .<Integer>builder(Comparator.<Integer>naturalOrder())
                        .member(RedBlackStrategy::new).member(AVLStrategy::new)
                        .member(SplayStrategy::new).mode(mode).build();
                List<Integer> keys = ascending(64);
                ens.buildAllFromSorted(keys);

                assertEquals(64, ens.size(), mode + ": logical size");
                assertEquals(keys, ens.inOrder(), mode + ": logical contents");
                for (EnsembleMember<Integer> m : ens.members()) {
                    assertEquals(keys, m.set().inOrder(), mode + ": " + m.strategyName() + " is a mirror");
                    assertTrue(m.isExact(), mode + ": " + m.strategyName() + " is marked exact");
                }
                assertEquals(32, ens.select(33), mode + ": order statistics are live immediately");
            }
        }

        @Test
        @DisplayName("an engine-tier member takes the element-wise fallback and still mirrors")
        void engineTierMemberFallsBack() {
            EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(RedBlackStrategy::new).persistentMember().build();
            List<Integer> keys = ascending(50);
            ens.buildAllFromSorted(keys);
            for (EnsembleMember<Integer> m : ens.members()) {
                assertEquals(keys, m.set().inOrder(), m.strategyName());
            }
        }

        @Test
        @DisplayName("a bounded window is honoured by every member's bulk build")
        void respectsTheSharedWindow() {
            EnsembleOrderedSet<Integer> ens = mirror(2);
            ens.setMaxSize(10);
            ens.buildAllFromSorted(ascending(64));
            assertEquals(10, ens.size(), "the shared bound applies to a bulk build too");
            assertEquals(ascending(64).subList(54, 64), ens.inOrder());
            for (EnsembleMember<Integer> m : ens.members()) assertEquals(10, m.set().size());
        }

        @Test
        @DisplayName("the gates are real: non-empty, wrong mode, and closed all refuse")
        void gatesRefuse() {
            EnsembleOrderedSet<Integer> nonEmpty = mirror(2);
            nonEmpty.add(1);
            assertThrows(IllegalStateException.class, () -> nonEmpty.buildAllFromSorted(ascending(8)));

            EnsembleOrderedSet<Integer> sampled = EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(RedBlackStrategy::new).member(AVLStrategy::new)
                    .mode(EnsembleMode.SAMPLED_SHADOW).build();
            assertThrows(IllegalStateException.class, () -> sampled.buildAllFromSorted(ascending(8)));

            EnsembleOrderedSet<Integer> closed = mirror(2);
            closed.close();
            assertThrows(IllegalStateException.class, () -> closed.buildAllFromSorted(ascending(8)));
        }
    }

    // ── Finding 6 ───────────────────────────────────────────────────────────────────────

    /**
     * The V3/V4 data-plane facades fed {@code recordSearch} a literal {@code 0} depth while
     * advertising themselves as mirroring {@code EnsembleController}, which measures the realized
     * walk through {@code EnsembleOrderedSet.searchDepth}. The read-side twin of the literal-0
     * rotation feed sixth-pass fix S6-12 removed from these very classes.
     */
    @Nested
    @DisplayName("finding 6 — the evolution facades record the depth they actually walked")
    class SearchDepthFeed {

        @Test
        @DisplayName("PolicySearchController.contains measures the walk")
        void searchControllerFeedsRealDepth() {
            EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(RedBlackStrategy::new).member(RedBlackStrategy::new).build();
            RollingWorkloadMonitor monitor = new RollingWorkloadMonitor();
            PolicySearchController<Integer> c = new PolicySearchController<>(
                    ens, ens.members().get(1), monitor,
                    new PolicyBandit(List.of(PolicyGenome.weightBalanced(3, 2))),
                    MorphPolicy.defaults());

            for (int i = 0; i < 500; i++) c.add(i);
            for (int i = 0; i < 300; i++) assertTrue(c.contains(i));

            double depth = monitor.snapshot().meanSearchDepth();
            assertTrue(depth > 1.0,
                    "a 500-key balanced tree is several nodes deep; the monitor recorded " + depth);
            assertFalse(c.contains(10_000), "absent keys are still answered correctly");
        }

        @Test
        @DisplayName("PolicyEvolutionController.contains measures the walk")
        void evolutionControllerFeedsRealDepth() {
            EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(RedBlackStrategy::new).member(RedBlackStrategy::new).build();
            RollingWorkloadMonitor monitor = new RollingWorkloadMonitor();
            PolicyEvolutionController<Integer> c = new PolicyEvolutionController<>(
                    ens, List.of(ens.members().get(1)), monitor, MorphPolicy.defaults(),
                    List.of(PolicyGenome.weightBalanced(3, 2)), 1, false, 7L);

            for (int i = 0; i < 500; i++) c.add(i);
            for (int i = 0; i < 300; i++) assertTrue(c.contains(i));

            double depth = monitor.snapshot().meanSearchDepth();
            assertTrue(depth > 1.0, "the monitor recorded " + depth);
            assertFalse(c.contains(10_000));
        }

        @Test
        @DisplayName("an unmeasurable read still records an honest zero, not a fabricated number")
        void votedReadsStayUnmeasured() {
            EnsembleOrderedSet<Integer> ens = EnsembleOrderedSet
                    .<Integer>builder(Comparator.<Integer>naturalOrder())
                    .member(RedBlackStrategy::new).member(AVLStrategy::new)
                    .member(SplayStrategy::new).mode(EnsembleMode.VERIFIED).build();
            RollingWorkloadMonitor monitor = new RollingWorkloadMonitor();
            PolicySearchController<Integer> c = new PolicySearchController<>(
                    ens, ens.members().get(1), monitor,
                    new PolicyBandit(List.of(PolicyGenome.weightBalanced(3, 2))),
                    MorphPolicy.defaults());

            for (int i = 0; i < 200; i++) c.add(i);
            for (int i = 0; i < 200; i++) assertTrue(c.contains(i));

            assertEquals(0.0, monitor.snapshot().meanSearchDepth(), 1e-12,
                    "every VERIFIED read votes at the default stride, and members legitimately "
                            + "disagree on depth — so no depth is voted and none is invented");
        }
    }
}
