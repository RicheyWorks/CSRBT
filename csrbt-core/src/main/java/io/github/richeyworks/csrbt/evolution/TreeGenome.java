package io.github.richeyworks.csrbt.evolution;

import java.util.Locale;
import java.util.Objects;
import java.util.Random;
import java.util.UUID;

/**
 * Iteration 5 TreeGenome.
 *
 * <p>This version upgrades the genome from a descriptive hereditary model into
 * a self-interpreting recommendation engine. The genome can now:</p>
 *
 * <ul>
 *     <li>score structural fitness across candidate morph targets</li>
 *     <li>recommend a preferred structure from its own traits</li>
 *     <li>generate diagnostic scorecards</li>
 *     <li>detect internal conflicts in its own configuration</li>
 *     <li>explain why a given structure is recommended</li>
 * </ul>
 *
 * <p>Still intentionally kept as one flagship class and one file.</p>
 */
// Hardening L-3: Serializable removed — this deprecated type kept the Java-serialization door ajar
// (no readObject validation) for any app deserializing untrusted streams with this jar on the
// classpath. Nothing in the codebase serializes it; the evolution machine's real genome is
// PolicyGenome, which was never Serializable.
public class TreeGenome implements Cloneable {

    private static final double MIN_TRAIT = 0.0;
    private static final double MAX_TRAIT = 1.0;
    private static final double DEFAULT_MUTATION_DELTA = 0.10;
    private static final Random RNG = new Random();

    public enum StructureType {
        RED_BLACK,
        AVL,
        SPLAY,
        FIBONACCI_HEAP,
        VAN_EMDE_BOAS,
        PERSISTENT_TREE,
        HYBRID,
        /** ADR-029 (fires ADR-008 D3): the large-n cache-friendly engine's registry slot. */
        B_PLUS_TREE
    }

    public enum AdaptationMode {
        BALANCED,
        STABILITY_FOCUSED,
        SPEED_FOCUSED,
        MEMORY_FOCUSED,
        ECOLOGY_FOCUSED,
        AGGRESSIVE_MUTATION
    }

    public enum GenomeOrigin {
        SEEDED,
        MANUAL,
        MUTATED,
        CROSSED,
        CLONED
    }

    // -------------------------------------------------
    // Identity / provenance
    // -------------------------------------------------

    private UUID genomeId;
    private UUID parentAId;
    private UUID parentBId;

    private int generation;
    private long createdAtEpochMillis;
    private GenomeOrigin origin;

    private String lineageTag;
    private String notes;

    // -------------------------------------------------
    // Structural bias
    // -------------------------------------------------

    private StructureType preferredStructure;
    private AdaptationMode adaptationMode;

    // -------------------------------------------------
    // Grouped trait blocks
    // -------------------------------------------------

    private BalanceTraits balanceTraits;
    private EcologyTraits ecologyTraits;
    private WorkloadTraits workloadTraits;
    private MorphTraits morphTraits;
    private CapabilityProfile capabilityProfile;

    public TreeGenome() {
        this.genomeId = UUID.randomUUID();
        this.parentAId = null;
        this.parentBId = null;
        this.generation = 0;
        this.createdAtEpochMillis = System.currentTimeMillis();
        this.origin = GenomeOrigin.SEEDED;

        this.preferredStructure = StructureType.RED_BLACK;
        this.adaptationMode = AdaptationMode.BALANCED;

        this.balanceTraits = new BalanceTraits(0.75, 0.50, 0.50);
        this.ecologyTraits = new EcologyTraits(0.60, 0.50);
        this.workloadTraits = new WorkloadTraits(0.40, 0.70, 0.20);
        this.morphTraits = new MorphTraits(0.05, 0.70);
        this.capabilityProfile = CapabilityProfile.defaultSearchTreeProfile();

        this.lineageTag = "FoundingGenome";
        this.notes = "";

        validate();
    }

    public TreeGenome(UUID genomeId,
                      UUID parentAId,
                      UUID parentBId,
                      int generation,
                      long createdAtEpochMillis,
                      GenomeOrigin origin,
                      StructureType preferredStructure,
                      AdaptationMode adaptationMode,
                      BalanceTraits balanceTraits,
                      EcologyTraits ecologyTraits,
                      WorkloadTraits workloadTraits,
                      MorphTraits morphTraits,
                      CapabilityProfile capabilityProfile,
                      String lineageTag,
                      String notes) {

        this.genomeId = (genomeId == null) ? UUID.randomUUID() : genomeId;
        this.parentAId = parentAId;
        this.parentBId = parentBId;
        this.generation = Math.max(0, generation);
        this.createdAtEpochMillis = createdAtEpochMillis <= 0
                ? System.currentTimeMillis()
                : createdAtEpochMillis;
        this.origin = Objects.requireNonNull(origin, "origin cannot be null");

        this.preferredStructure = Objects.requireNonNull(preferredStructure, "preferredStructure cannot be null");
        this.adaptationMode = Objects.requireNonNull(adaptationMode, "adaptationMode cannot be null");

        this.balanceTraits = Objects.requireNonNull(balanceTraits, "balanceTraits cannot be null").copy();
        this.ecologyTraits = Objects.requireNonNull(ecologyTraits, "ecologyTraits cannot be null").copy();
        this.workloadTraits = Objects.requireNonNull(workloadTraits, "workloadTraits cannot be null").copy();
        this.morphTraits = Objects.requireNonNull(morphTraits, "morphTraits cannot be null").copy();
        this.capabilityProfile = Objects.requireNonNull(capabilityProfile, "capabilityProfile cannot be null").copy();

        this.lineageTag = normalizeLineageTag(lineageTag);
        this.notes = normalizeNotes(notes);

        validate();
    }

    public static Builder builder() {
        return new Builder();
    }

    public Builder toBuilder() {
        return new Builder()
                .genomeId(genomeId)
                .parentAId(parentAId)
                .parentBId(parentBId)
                .generation(generation)
                .createdAtEpochMillis(createdAtEpochMillis)
                .origin(origin)
                .preferredStructure(preferredStructure)
                .adaptationMode(adaptationMode)
                .balanceTraits(balanceTraits.copy())
                .ecologyTraits(ecologyTraits.copy())
                .workloadTraits(workloadTraits.copy())
                .morphTraits(morphTraits.copy())
                .capabilityProfile(capabilityProfile.copy())
                .lineageTag(lineageTag)
                .notes(notes);
    }

    public static TreeGenome crossover(TreeGenome parentA, TreeGenome parentB) {
        Objects.requireNonNull(parentA, "parentA cannot be null");
        Objects.requireNonNull(parentB, "parentB cannot be null");

        int childGeneration = Math.max(parentA.generation, parentB.generation) + 1;

        TreeGenome child = new TreeGenome(
                UUID.randomUUID(),
                parentA.genomeId,
                parentB.genomeId,
                childGeneration,
                System.currentTimeMillis(),
                GenomeOrigin.CROSSED,
                RNG.nextBoolean() ? parentA.preferredStructure : parentB.preferredStructure,
                RNG.nextBoolean() ? parentA.adaptationMode : parentB.adaptationMode,
                BalanceTraits.average(parentA.balanceTraits, parentB.balanceTraits),
                EcologyTraits.average(parentA.ecologyTraits, parentB.ecologyTraits),
                WorkloadTraits.average(parentA.workloadTraits, parentB.workloadTraits),
                MorphTraits.average(parentA.morphTraits, parentB.morphTraits),
                CapabilityProfile.average(parentA.capabilityProfile, parentB.capabilityProfile),
                parentA.lineageTag + "×" + parentB.lineageTag,
                "Crossover child of " + parentA.genomeId + " and " + parentB.genomeId
        );

        if (RNG.nextDouble() < child.morphTraits.getMutationRate()) {
            // In-womb trait mutation must not rewrite the child's provenance (bug audit
            // 2026-08-12, G-C): mutatedCopy() re-frames the copy as a MUTATED child of
            // the intermediate — losing both real parents (parentA became a phantom
            // UUID matching neither), the CROSSED origin, and double-bumping the
            // generation. Mutate the traits, then restore the crossover frame.
            TreeGenome mutated = child.mutatedCopy();
            mutated.parentAId  = parentA.genomeId;
            mutated.parentBId  = parentB.genomeId;
            mutated.origin     = GenomeOrigin.CROSSED;
            mutated.generation = childGeneration;
            mutated.lineageTag = child.lineageTag + "*";
            mutated.notes      = normalizeNotes(child.notes + " (trait mutation at birth)");
            child = mutated;
        }

        return child;
    }

    public TreeGenome mutatedCopy() {
        TreeGenome copy = this.clone();

        copy.genomeId = UUID.randomUUID();
        copy.parentAId = this.genomeId;
        copy.parentBId = null;
        copy.generation = this.generation + 1;
        copy.createdAtEpochMillis = System.currentTimeMillis();
        copy.origin = GenomeOrigin.MUTATED;

        copy.balanceTraits = copy.balanceTraits.mutatedCopy();
        copy.ecologyTraits = copy.ecologyTraits.mutatedCopy();
        copy.workloadTraits = copy.workloadTraits.mutatedCopy();
        copy.morphTraits = copy.morphTraits.mutatedCopy();
        copy.capabilityProfile = copy.capabilityProfile.mutatedCopy();

        if (RNG.nextDouble() < 0.15) {
            copy.preferredStructure = randomEnum(StructureType.values());
        }

        if (RNG.nextDouble() < 0.15) {
            copy.adaptationMode = randomEnum(AdaptationMode.values());
        }

        copy.lineageTag = this.lineageTag + "*";
        copy.notes = normalizeNotes(this.notes + " | Mutated from " + this.genomeId);
        copy.validate();

        return copy;
    }

    public void mutate() {
        TreeGenome mutated = mutatedCopy();

        this.genomeId = mutated.genomeId;
        this.parentAId = mutated.parentAId;
        this.parentBId = mutated.parentBId;
        this.generation = mutated.generation;
        this.createdAtEpochMillis = mutated.createdAtEpochMillis;
        this.origin = mutated.origin;
        this.preferredStructure = mutated.preferredStructure;
        this.adaptationMode = mutated.adaptationMode;
        this.balanceTraits = mutated.balanceTraits.copy();
        this.ecologyTraits = mutated.ecologyTraits.copy();
        this.workloadTraits = mutated.workloadTraits.copy();
        this.morphTraits = mutated.morphTraits.copy();
        this.capabilityProfile = mutated.capabilityProfile.copy();
        this.lineageTag = mutated.lineageTag;
        this.notes = mutated.notes;
    }

    // -------------------------------------------------
    // Runtime stress / morph pressure
    // -------------------------------------------------

    /**
     * @deprecated ADR-002 step 6 Phase D: the live loop derives workload pressure from
     *     {@code core.control.WorkloadMonitor} features, not the genome. Retained for the
     *     legacy (flag-off) decision body and diagnostics; off the default decision path.
     */
    @Deprecated
    public double computeMorphPressure(double currentStress,
                                       double currentEntropy,
                                       double currentFragmentation) {

        currentStress = clamp(currentStress);
        currentEntropy = clamp(currentEntropy);
        currentFragmentation = clamp(currentFragmentation);

        double stressGap = Math.max(0.0, currentStress - balanceTraits.getDepthStressTolerance());
        double entropyGap = Math.max(0.0, ecologyTraits.getEntropyPreference() - currentEntropy);
        double fragmentationGap = Math.max(0.0,
                currentFragmentation - balanceTraits.getFragmentationTolerance());

        return clamp(
                (stressGap * 0.45) +
                (entropyGap * 0.25) +
                (fragmentationGap * 0.30)
        );
    }

    /**
     * @deprecated ADR-002 step 6 Phase D: morph gating now lives in
     *     {@code core.control.MorphPolicy}, fed by {@code core.control.StrategyScorer}. Retained
     *     for the legacy (flag-off) decision body; off the default decision path.
     */
    @Deprecated
    public boolean shouldMorph(double currentStress,
                               double currentEntropy,
                               double currentFragmentation) {
        return computeMorphPressure(currentStress, currentEntropy, currentFragmentation)
                >= morphTraits.getMorphThreshold();
    }

    // -------------------------------------------------
    // Compatibility
    // -------------------------------------------------

    public double compatibilityScore(TreeGenome other) {
        Objects.requireNonNull(other, "other cannot be null");

        double score = 0.0;

        if (preferredStructure == other.preferredStructure) {
            score += 0.10;
        }

        if (adaptationMode == other.adaptationMode) {
            score += 0.08;
        }

        score += balanceTraits.compatibilityScore(other.balanceTraits) * 0.18;
        score += ecologyTraits.compatibilityScore(other.ecologyTraits) * 0.12;
        score += workloadTraits.compatibilityScore(other.workloadTraits) * 0.18;
        score += morphTraits.compatibilityScore(other.morphTraits) * 0.10;
        score += capabilityProfile.compatibilityScore(other.capabilityProfile) * 0.24;

        return clamp(score);
    }

    // -------------------------------------------------
    // Bias families
    // -------------------------------------------------

    public boolean prefersSearchTreeFamily() {
        return preferredStructure == StructureType.RED_BLACK
                || preferredStructure == StructureType.AVL
                || preferredStructure == StructureType.SPLAY
                || preferredStructure == StructureType.PERSISTENT_TREE
                || preferredStructure == StructureType.HYBRID
                || preferredStructure == StructureType.B_PLUS_TREE;
    }

    public boolean prefersPriorityFamily() {
        return preferredStructure == StructureType.FIBONACCI_HEAP;
    }

    public double searchBiasScore() {
        double structural = clamp(
                (balanceTraits.getBalancePreference() * 0.25) +
                (workloadTraits.getOrderStatisticPreference() * 0.20) +
                (ecologyTraits.getEntropyPreference() * 0.10) +
                ((1.0 - workloadTraits.getPriorityQueuePreference()) * 0.10)
        );

        double capability = clamp(
                (capabilityProfile.getOrderedSearchWeight() * 0.30) +
                (capabilityProfile.getPredecessorSuccessorWeight() * 0.20) +
                (capabilityProfile.getRankSelectWeight() * 0.25) +
                (capabilityProfile.getIntervalQueryWeight() * 0.25)
        );

        return clamp((structural * 0.55) + (capability * 0.45));
    }

    public double priorityBiasScore() {
        double structural = clamp(
                (workloadTraits.getPriorityQueuePreference() * 0.35) +
                (workloadTraits.getLocalityPreference() * 0.08) +
                (ecologyTraits.getDuplicateTolerance() * 0.07) +
                ((1.0 - balanceTraits.getBalancePreference()) * 0.10)
        );

        double capability = clamp(
                (capabilityProfile.getMeldWeight() * 0.28) +
                (capabilityProfile.getDecreaseKeyWeight() * 0.28) +
                (capabilityProfile.getExtractMinWeight() * 0.28) +
                (capabilityProfile.getLocalityExploitationWeight() * 0.16)
        );

        return clamp((structural * 0.45) + (capability * 0.55));
    }

    public double persistenceBiasScore() {
        return clamp(
                (capabilityProfile.getPersistenceWeight() * 0.65) +
                (adaptationMode == AdaptationMode.MEMORY_FOCUSED ? 0.20 : 0.0) +
                (workloadTraits.getOrderStatisticPreference() * 0.05) +
                (balanceTraits.getBalancePreference() * 0.10)
        );
    }

    public double intervalBiasScore() {
        return clamp(
                (capabilityProfile.getIntervalQueryWeight() * 0.70) +
                (workloadTraits.getOrderStatisticPreference() * 0.15) +
                (ecologyTraits.getEntropyPreference() * 0.15)
        );
    }

    public String dominantBiasLabel() {
        double search = searchBiasScore();
        double priority = priorityBiasScore();
        double persistence = persistenceBiasScore();
        double interval = intervalBiasScore();

        double max = Math.max(Math.max(search, priority), Math.max(persistence, interval));

        if (max == search) return "SEARCH_DOMINANT";
        if (max == priority) return "PRIORITY_DOMINANT";
        if (max == persistence) return "PERSISTENCE_DOMINANT";
        return "INTERVAL_DOMINANT";
    }

    // -------------------------------------------------
    // Iteration 5: structure scoring / recommendation / diagnostics
    // -------------------------------------------------

    public ScoreCard scoreCard() {
        double rb = fitnessFor(StructureType.RED_BLACK);
        double avl = fitnessFor(StructureType.AVL);
        double splay = fitnessFor(StructureType.SPLAY);
        double fib = fitnessFor(StructureType.FIBONACCI_HEAP);
        double veb = fitnessFor(StructureType.VAN_EMDE_BOAS);
        double persistent = fitnessFor(StructureType.PERSISTENT_TREE);
        double hybrid = fitnessFor(StructureType.HYBRID);
        double bPlus = fitnessFor(StructureType.B_PLUS_TREE);

        return new ScoreCard(rb, avl, splay, fib, veb, persistent, hybrid, bPlus);
    }

    public StructureType recommendedStructure() {
        return scoreCard().bestStructure();
    }

    /**
     * @deprecated ADR-002 step 6 Phase D: live morph selection is now the cost-model
     *     {@code core.control.StrategyScorer}, not genome fitness. Retained for the genome's own
     *     {@link #scoreCard()} / diagnostics; off the default decision path.
     */
    @Deprecated
    public double fitnessFor(StructureType candidate) {
        Objects.requireNonNull(candidate, "candidate cannot be null");

        double score;
        switch (candidate) {
            case RED_BLACK -> score = redBlackFitness();
            case AVL -> score = avlFitness();
            case SPLAY -> score = splayFitness();
            case FIBONACCI_HEAP -> score = fibonacciFitness();
            case VAN_EMDE_BOAS -> score = vanEmdeBoasFitness();
            case PERSISTENT_TREE -> score = persistentFitness();
            case HYBRID -> score = hybridFitness();
            case B_PLUS_TREE -> score = bPlusFitness();
            default -> score = 0.0;
        }

        if (candidate == preferredStructure) {
            score += 0.04;
        }

        return clamp(score);
    }

    public String explainRecommendedStructure() {
        StructureType best = recommendedStructure();
        ScoreCard card = scoreCard();

        return "Recommended structure: " + best +
                " with fitness " + format(card.scoreOf(best)) +
                ". " + explainStructureFitness(best);
    }

    public String explainStructureFitness(StructureType structure) {
        Objects.requireNonNull(structure, "structure cannot be null");

        StringBuilder sb = new StringBuilder();
        sb.append("Fitness rationale for ").append(structure).append(": ");

        switch (structure) {
            case RED_BLACK -> sb.append(
                    "weighted toward balanced ordered search, moderate update stability, " +
                    "and broad general-purpose capability. ");
            case AVL -> sb.append(
                    "weighted toward strict balance, strong ordered search quality, " +
                    "and rank/select friendly structure. ");
            case SPLAY -> sb.append(
                    "weighted toward locality exploitation, adaptive hot-path access, " +
                    "and tolerance for structural instability in exchange for access adaptation. ");
            case FIBONACCI_HEAP -> sb.append(
                    "weighted toward meld, decrease-key, extract-min, and relaxed structural discipline. ");
            case VAN_EMDE_BOAS -> sb.append(
                    "weighted toward fast bounded-universe lookup style and ordered integer operations. ");
            case PERSISTENT_TREE -> sb.append(
                    "weighted toward historical branching, version retention, and memory-oriented persistence. ");
            case HYBRID -> sb.append(
                    "weighted toward mixed capability balance, compromise behavior, and structural flexibility. ");
            case B_PLUS_TREE -> sb.append(
                    "weighted toward cache-line locality, ordered bulk scans and rank/select over " +
                    "large runs, and a disk-page-ready layout; modest below ~10⁵ keys where " +
                    "pointer BSTs have better constants (ADR-008). ");
            default -> sb.append("generic evaluation. ");
        }

        sb.append("Current score=").append(format(fitnessFor(structure))).append(".");
        return sb.toString();
    }

    public String conflictReport() {
        StringBuilder sb = new StringBuilder();
        int conflictCount = 0;

        if (balanceTraits.getBalancePreference() > 0.85
                && workloadTraits.getPriorityQueuePreference() > 0.85) {
            sb.append("Conflict: strict balance preference is extremely high while priority-queue bias is also extremely high. ");
            conflictCount++;
        }

        if (capabilityProfile.getPersistenceWeight() > 0.85
                && adaptationMode != AdaptationMode.MEMORY_FOCUSED) {
            sb.append("Conflict: persistence weight is very high but adaptation mode is not memory-focused. ");
            conflictCount++;
        }

        if (capabilityProfile.getMeldWeight() > 0.85
                && capabilityProfile.getOrderedSearchWeight() > 0.85) {
            sb.append("Tension: both meld-heavy and ordered-search-heavy priorities are strongly present. ");
            conflictCount++;
        }

        if (workloadTraits.getLocalityPreference() > 0.85
                && balanceTraits.getBalancePreference() > 0.90
                && capabilityProfile.getLocalityExploitationWeight() > 0.85) {
            sb.append("Tension: strong locality adaptation and strict balance discipline may compete. ");
            conflictCount++;
        }

        if (capabilityProfile.getIntervalQueryWeight() > 0.85
                && workloadTraits.getOrderStatisticPreference() < 0.30) {
            sb.append("Conflict: interval-query emphasis is high while order-statistic support is weak. ");
            conflictCount++;
        }

        if (conflictCount == 0) {
            return "No major internal conflicts detected.";
        }

        sb.append("Total conflicts/tensions detected: ").append(conflictCount).append('.');
        return sb.toString();
    }

    public boolean hasMajorConflicts() {
        return !"No major internal conflicts detected.".equals(conflictReport());
    }

    public String summary() {
        return "Genome[" +
                "id=" + genomeId +
                ", gen=" + generation +
                ", origin=" + origin +
                ", structure=" + preferredStructure +
                ", mode=" + adaptationMode +
                ", lineage=" + lineageTag +
                ", bias=" + dominantBiasLabel() +
                ", recommended=" + recommendedStructure() +
                ']';
    }

    public String explainGenome() {
        return "TreeGenome explanation: " +
                "This genome prefers " + preferredStructure +
                " under " + adaptationMode +
                ", with balance=" + format(balanceTraits.getBalancePreference()) +
                ", depthTolerance=" + format(balanceTraits.getDepthStressTolerance()) +
                ", fragmentationTolerance=" + format(balanceTraits.getFragmentationTolerance()) +
                ", entropyPreference=" + format(ecologyTraits.getEntropyPreference()) +
                ", duplicateTolerance=" + format(ecologyTraits.getDuplicateTolerance()) +
                ", localityPreference=" + format(workloadTraits.getLocalityPreference()) +
                ", orderStatisticPreference=" + format(workloadTraits.getOrderStatisticPreference()) +
                ", priorityQueuePreference=" + format(workloadTraits.getPriorityQueuePreference()) +
                ", mutationRate=" + format(morphTraits.getMutationRate()) +
                ", morphThreshold=" + format(morphTraits.getMorphThreshold()) +
                ", orderedSearchWeight=" + format(capabilityProfile.getOrderedSearchWeight()) +
                ", rankSelectWeight=" + format(capabilityProfile.getRankSelectWeight()) +
                ", intervalQueryWeight=" + format(capabilityProfile.getIntervalQueryWeight()) +
                ", meldWeight=" + format(capabilityProfile.getMeldWeight()) +
                ", decreaseKeyWeight=" + format(capabilityProfile.getDecreaseKeyWeight()) +
                ", extractMinWeight=" + format(capabilityProfile.getExtractMinWeight()) +
                ", persistenceWeight=" + format(capabilityProfile.getPersistenceWeight()) +
                ", recommendedStructure=" + recommendedStructure() + ".";
    }

    // -------------------------------------------------
    // Fitness internals
    // -------------------------------------------------

    private double redBlackFitness() {
        double ordered = clamp(
                (capabilityProfile.getOrderedSearchWeight() * 0.20) +
                (capabilityProfile.getPredecessorSuccessorWeight() * 0.12) +
                (capabilityProfile.getRankSelectWeight() * 0.10)
        );

        double structure = clamp(
                (balanceTraits.getBalancePreference() * 0.18) +
                (balanceTraits.getDepthStressTolerance() * 0.08) +
                ((1.0 - balanceTraits.getFragmentationTolerance()) * 0.05)
        );

        double workload = clamp(
                (workloadTraits.getOrderStatisticPreference() * 0.08) +
                ((1.0 - workloadTraits.getPriorityQueuePreference()) * 0.10) +
                (ecologyTraits.getEntropyPreference() * 0.05)
        );

        double adaptation = adaptationMode == AdaptationMode.BALANCED ? 0.04 : 0.0;

        return clamp(ordered + structure + workload + adaptation);
    }

    private double avlFitness() {
        double ordered = clamp(
                (capabilityProfile.getOrderedSearchWeight() * 0.18) +
                (capabilityProfile.getRankSelectWeight() * 0.12) +
                (capabilityProfile.getPredecessorSuccessorWeight() * 0.08)
        );

        double strictBalance = clamp(
                (balanceTraits.getBalancePreference() * 0.24) +
                ((1.0 - balanceTraits.getFragmentationTolerance()) * 0.08)
        );

        double workload = clamp(
                (workloadTraits.getOrderStatisticPreference() * 0.10) +
                ((1.0 - workloadTraits.getPriorityQueuePreference()) * 0.08)
        );

        double adaptation = adaptationMode == AdaptationMode.STABILITY_FOCUSED ? 0.05 : 0.0;

        return clamp(ordered + strictBalance + workload + adaptation);
    }

    private double splayFitness() {
        double locality = clamp(
                (workloadTraits.getLocalityPreference() * 0.24) +
                (capabilityProfile.getLocalityExploitationWeight() * 0.22)
        );

        double adaptive = clamp(
                (balanceTraits.getDepthStressTolerance() * 0.10) +
                (balanceTraits.getFragmentationTolerance() * 0.08)
        );

        double ordered = clamp(
                (capabilityProfile.getOrderedSearchWeight() * 0.08) +
                (capabilityProfile.getPredecessorSuccessorWeight() * 0.05)
        );

        double adaptation = adaptationMode == AdaptationMode.SPEED_FOCUSED ? 0.05 : 0.0;

        return clamp(locality + adaptive + ordered + adaptation);
    }

    private double fibonacciFitness() {
        double heapOps = clamp(
                (capabilityProfile.getMeldWeight() * 0.20) +
                (capabilityProfile.getDecreaseKeyWeight() * 0.20) +
                (capabilityProfile.getExtractMinWeight() * 0.18)
        );

        double structuralRelaxation = clamp(
                ((1.0 - balanceTraits.getBalancePreference()) * 0.10) +
                (balanceTraits.getDepthStressTolerance() * 0.06) +
                (balanceTraits.getFragmentationTolerance() * 0.06)
        );

        double workload = clamp(
                (workloadTraits.getPriorityQueuePreference() * 0.14) +
                (ecologyTraits.getDuplicateTolerance() * 0.04)
        );

        double adaptation = adaptationMode == AdaptationMode.AGGRESSIVE_MUTATION ? 0.02 : 0.0;

        return clamp(heapOps + structuralRelaxation + workload + adaptation);
    }

    private double vanEmdeBoasFitness() {
        double ordered = clamp(
                (capabilityProfile.getOrderedSearchWeight() * 0.16) +
                (capabilityProfile.getPredecessorSuccessorWeight() * 0.12) +
                (capabilityProfile.getRankSelectWeight() * 0.08)
        );

        double discipline = clamp(
                (balanceTraits.getBalancePreference() * 0.10) +
                ((1.0 - balanceTraits.getFragmentationTolerance()) * 0.05)
        );

        double speed = adaptationMode == AdaptationMode.SPEED_FOCUSED ? 0.04 : 0.0;

        double mildBonus = 0.04; // bounded-universe aspirational bias

        return clamp(ordered + discipline + speed + mildBonus);
    }

    private double persistentFitness() {
        double memory = clamp(
                (capabilityProfile.getPersistenceWeight() * 0.28) +
                (workloadTraits.getOrderStatisticPreference() * 0.06)
        );

        double structure = clamp(
                (balanceTraits.getBalancePreference() * 0.12) +
                ((1.0 - workloadTraits.getPriorityQueuePreference()) * 0.06)
        );

        double ecology = clamp(
                (ecologyTraits.getEntropyPreference() * 0.05) +
                ((1.0 - ecologyTraits.getDuplicateTolerance()) * 0.03)
        );

        double adaptation = adaptationMode == AdaptationMode.MEMORY_FOCUSED ? 0.08 : 0.0;

        return clamp(memory + structure + ecology + adaptation);
    }

    /**
     * ADR-029 (fires ADR-008 D3): the B+ tree's fitness model. What the structure is
     * actually good at — wide cache-line-friendly nodes (locality exploitation),
     * ordered scans and rank/select over large runs, and a disk-page-ready layout
     * (persistence weight, at a discount: D2 pages-to-disk is still held) — and what
     * it is not: a priority queue, or a win at small n where pointer BSTs have better
     * constants (ADR-008's ~10⁵-key caveat keeps the aspirational bias modest).
     */
    private double bPlusFitness() {
        double locality = clamp(
                (capabilityProfile.getLocalityExploitationWeight() * 0.16) +
                (workloadTraits.getLocalityPreference() * 0.06)
        );

        double orderedBulk = clamp(
                (capabilityProfile.getOrderedSearchWeight() * 0.14) +
                (workloadTraits.getOrderStatisticPreference() * 0.08) +
                (capabilityProfile.getRankSelectWeight() * 0.06)
        );

        double diskReady = clamp(
                (capabilityProfile.getPersistenceWeight() * 0.10) +
                ((1.0 - workloadTraits.getPriorityQueuePreference()) * 0.05)
        );

        double discipline = clamp(
                (balanceTraits.getBalancePreference() * 0.06) +
                ((1.0 - balanceTraits.getFragmentationTolerance()) * 0.03)
        );

        double adaptation = adaptationMode == AdaptationMode.SPEED_FOCUSED ? 0.04 : 0.0;

        return clamp(locality + orderedBulk + diskReady + discipline + adaptation);
    }

    private double hybridFitness() {
        ScoreCard base = new ScoreCard(
                redBlackFitness(),
                avlFitness(),
                splayFitness(),
                fibonacciFitness(),
                vanEmdeBoasFitness(),
                persistentFitness(),
                0.0,
                bPlusFitness()
        );

        double spreadPenalty = clamp(base.range() * 0.25);
        double centrality = clamp(base.average() * 0.85);

        double flexibilityBonus = clamp(
                (capabilityProfile.getIntervalQueryWeight() * 0.06) +
                (capabilityProfile.getPersistenceWeight() * 0.04) +
                (capabilityProfile.getLocalityExploitationWeight() * 0.04) +
                (capabilityProfile.getMeldWeight() * 0.04)
        );

        double adaptation = adaptationMode == AdaptationMode.ECOLOGY_FOCUSED ? 0.04 : 0.0;

        return clamp(centrality - spreadPenalty + flexibilityBonus + adaptation);
    }

    // -------------------------------------------------
    // Validation / Object overrides
    // -------------------------------------------------

    public final void validate() {
        Objects.requireNonNull(genomeId, "genomeId cannot be null");
        Objects.requireNonNull(origin, "origin cannot be null");
        Objects.requireNonNull(preferredStructure, "preferredStructure cannot be null");
        Objects.requireNonNull(adaptationMode, "adaptationMode cannot be null");
        Objects.requireNonNull(balanceTraits, "balanceTraits cannot be null");
        Objects.requireNonNull(ecologyTraits, "ecologyTraits cannot be null");
        Objects.requireNonNull(workloadTraits, "workloadTraits cannot be null");
        Objects.requireNonNull(morphTraits, "morphTraits cannot be null");
        Objects.requireNonNull(capabilityProfile, "capabilityProfile cannot be null");

        if (generation < 0) {
            throw new IllegalStateException("generation cannot be negative");
        }
        if (createdAtEpochMillis <= 0) {
            throw new IllegalStateException("createdAtEpochMillis must be positive");
        }

        balanceTraits.validate();
        ecologyTraits.validate();
        workloadTraits.validate();
        morphTraits.validate();
        capabilityProfile.validate();

        lineageTag = normalizeLineageTag(lineageTag);
        notes = normalizeNotes(notes);
    }

    @Override
    public TreeGenome clone() {
        try {
            TreeGenome copy = (TreeGenome) super.clone();
            copy.balanceTraits = this.balanceTraits.copy();
            copy.ecologyTraits = this.ecologyTraits.copy();
            copy.workloadTraits = this.workloadTraits.copy();
            copy.morphTraits = this.morphTraits.copy();
            copy.capabilityProfile = this.capabilityProfile.copy();
            return copy;
        } catch (CloneNotSupportedException e) {
            throw new AssertionError("Clone should be supported", e);
        }
    }

    @Override
    public String toString() {
        return "TreeGenome{" +
                "genomeId=" + genomeId +
                ", parentAId=" + parentAId +
                ", parentBId=" + parentBId +
                ", generation=" + generation +
                ", createdAtEpochMillis=" + createdAtEpochMillis +
                ", origin=" + origin +
                ", preferredStructure=" + preferredStructure +
                ", adaptationMode=" + adaptationMode +
                ", balanceTraits=" + balanceTraits +
                ", ecologyTraits=" + ecologyTraits +
                ", workloadTraits=" + workloadTraits +
                ", morphTraits=" + morphTraits +
                ", capabilityProfile=" + capabilityProfile +
                ", lineageTag='" + lineageTag + '\'' +
                ", notes='" + notes + '\'' +
                '}';
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (!(obj instanceof TreeGenome other)) return false;

        return generation == other.generation
                && createdAtEpochMillis == other.createdAtEpochMillis
                && Objects.equals(genomeId, other.genomeId)
                && Objects.equals(parentAId, other.parentAId)
                && Objects.equals(parentBId, other.parentBId)
                && origin == other.origin
                && preferredStructure == other.preferredStructure
                && adaptationMode == other.adaptationMode
                && Objects.equals(balanceTraits, other.balanceTraits)
                && Objects.equals(ecologyTraits, other.ecologyTraits)
                && Objects.equals(workloadTraits, other.workloadTraits)
                && Objects.equals(morphTraits, other.morphTraits)
                && Objects.equals(capabilityProfile, other.capabilityProfile)
                && Objects.equals(lineageTag, other.lineageTag)
                && Objects.equals(notes, other.notes);
    }

    @Override
    public int hashCode() {
        return Objects.hash(
                genomeId,
                parentAId,
                parentBId,
                generation,
                createdAtEpochMillis,
                origin,
                preferredStructure,
                adaptationMode,
                balanceTraits,
                ecologyTraits,
                workloadTraits,
                morphTraits,
                capabilityProfile,
                lineageTag,
                notes
        );
    }

    // -------------------------------------------------
    // Presets
    // -------------------------------------------------

    public static TreeGenome redBlackGenome() {
        return builder()
                .origin(GenomeOrigin.SEEDED)
                .preferredStructure(StructureType.RED_BLACK)
                .adaptationMode(AdaptationMode.BALANCED)
                .balanceTraits(new BalanceTraits(0.75, 0.55, 0.50))
                .ecologyTraits(new EcologyTraits(0.60, 0.50))
                .workloadTraits(new WorkloadTraits(0.35, 0.75, 0.10))
                .morphTraits(new MorphTraits(0.04, 0.70))
                .capabilityProfile(CapabilityProfile.redBlackProfile())
                .lineageTag("RB-Lineage")
                .notes("Seeded Red-Black genome")
                .build();
    }

    public static TreeGenome avlGenome() {
        return builder()
                .origin(GenomeOrigin.SEEDED)
                .preferredStructure(StructureType.AVL)
                .adaptationMode(AdaptationMode.STABILITY_FOCUSED)
                .balanceTraits(new BalanceTraits(0.95, 0.30, 0.25))
                .ecologyTraits(new EcologyTraits(0.70, 0.45))
                .workloadTraits(new WorkloadTraits(0.25, 0.80, 0.05))
                .morphTraits(new MorphTraits(0.03, 0.55))
                .capabilityProfile(CapabilityProfile.avlProfile())
                .lineageTag("AVL-Lineage")
                .notes("Seeded AVL genome")
                .build();
    }

    public static TreeGenome splayGenome() {
        return builder()
                .origin(GenomeOrigin.SEEDED)
                .preferredStructure(StructureType.SPLAY)
                .adaptationMode(AdaptationMode.SPEED_FOCUSED)
                .balanceTraits(new BalanceTraits(0.40, 0.80, 0.65))
                .ecologyTraits(new EcologyTraits(0.55, 0.60))
                .workloadTraits(new WorkloadTraits(0.95, 0.55, 0.10))
                .morphTraits(new MorphTraits(0.08, 0.78))
                .capabilityProfile(CapabilityProfile.splayProfile())
                .lineageTag("SPLAY-Lineage")
                .notes("Seeded Splay genome")
                .build();
    }

    public static TreeGenome fibonacciGenome() {
        return builder()
                .origin(GenomeOrigin.SEEDED)
                .preferredStructure(StructureType.FIBONACCI_HEAP)
                .adaptationMode(AdaptationMode.AGGRESSIVE_MUTATION)
                .balanceTraits(new BalanceTraits(0.15, 0.85, 0.80))
                .ecologyTraits(new EcologyTraits(0.50, 0.70))
                .workloadTraits(new WorkloadTraits(0.40, 0.20, 0.98))
                .morphTraits(new MorphTraits(0.10, 0.82))
                .capabilityProfile(CapabilityProfile.fibonacciProfile())
                .lineageTag("FIB-Lineage")
                .notes("Seeded Fibonacci-heap genome")
                .build();
    }

    public static TreeGenome persistentGenome() {
        return builder()
                .origin(GenomeOrigin.SEEDED)
                .preferredStructure(StructureType.PERSISTENT_TREE)
                .adaptationMode(AdaptationMode.MEMORY_FOCUSED)
                .balanceTraits(new BalanceTraits(0.70, 0.45, 0.40))
                .ecologyTraits(new EcologyTraits(0.65, 0.45))
                .workloadTraits(new WorkloadTraits(0.30, 0.85, 0.10))
                .morphTraits(new MorphTraits(0.02, 0.60))
                .capabilityProfile(CapabilityProfile.persistentProfile())
                .lineageTag("PERSIST-Lineage")
                .notes("Seeded persistent-tree genome")
                .build();
    }

    public static TreeGenome hybridGenome() {
        return builder()
                .origin(GenomeOrigin.SEEDED)
                .preferredStructure(StructureType.HYBRID)
                .adaptationMode(AdaptationMode.ECOLOGY_FOCUSED)
                .balanceTraits(new BalanceTraits(0.78, 0.48, 0.42))
                .ecologyTraits(new EcologyTraits(0.72, 0.50))
                .workloadTraits(new WorkloadTraits(0.52, 0.74, 0.25))
                .morphTraits(new MorphTraits(0.06, 0.66))
                .capabilityProfile(CapabilityProfile.hybridProfile())
                .lineageTag("HYBRID-Lineage")
                .notes("Seeded hybrid genome")
                .build();
    }

    // -------------------------------------------------
    // Nested utility result classes
    // -------------------------------------------------

    public static class ScoreCard {
        private final double redBlack;
        private final double avl;
        private final double splay;
        private final double fibonacci;
        private final double vanEmdeBoas;
        private final double persistent;
        private final double hybrid;
        private final double bPlusTree;

        /** ADR-029: the card carries all eight declared structures (0.3.0 API change). */
        public ScoreCard(double redBlack,
                         double avl,
                         double splay,
                         double fibonacci,
                         double vanEmdeBoas,
                         double persistent,
                         double hybrid,
                         double bPlusTree) {
            this.redBlack = clamp(redBlack);
            this.avl = clamp(avl);
            this.splay = clamp(splay);
            this.fibonacci = clamp(fibonacci);
            this.vanEmdeBoas = clamp(vanEmdeBoas);
            this.persistent = clamp(persistent);
            this.hybrid = clamp(hybrid);
            this.bPlusTree = clamp(bPlusTree);
        }

        public StructureType bestStructure() {
            StructureType best = StructureType.RED_BLACK;
            double bestScore = redBlack;

            if (avl > bestScore) {
                best = StructureType.AVL;
                bestScore = avl;
            }
            if (splay > bestScore) {
                best = StructureType.SPLAY;
                bestScore = splay;
            }
            if (fibonacci > bestScore) {
                best = StructureType.FIBONACCI_HEAP;
                bestScore = fibonacci;
            }
            if (vanEmdeBoas > bestScore) {
                best = StructureType.VAN_EMDE_BOAS;
                bestScore = vanEmdeBoas;
            }
            if (persistent > bestScore) {
                best = StructureType.PERSISTENT_TREE;
                bestScore = persistent;
            }
            if (hybrid > bestScore) {
                best = StructureType.HYBRID;
                bestScore = hybrid;
            }
            if (bPlusTree > bestScore) {
                best = StructureType.B_PLUS_TREE;
            }

            return best;
        }

        public double scoreOf(StructureType structure) {
            return switch (structure) {
                case RED_BLACK -> redBlack;
                case AVL -> avl;
                case SPLAY -> splay;
                case FIBONACCI_HEAP -> fibonacci;
                case VAN_EMDE_BOAS -> vanEmdeBoas;
                case PERSISTENT_TREE -> persistent;
                case HYBRID -> hybrid;
                case B_PLUS_TREE -> bPlusTree;
            };
        }

        public double average() {
            return (redBlack + avl + splay + fibonacci + vanEmdeBoas + persistent + hybrid
                    + bPlusTree) / 8.0;
        }

        public double range() {
            double min = Math.min(Math.min(Math.min(redBlack, avl), Math.min(splay, fibonacci)),
                    Math.min(Math.min(vanEmdeBoas, persistent), Math.min(hybrid, bPlusTree)));
            double max = Math.max(Math.max(Math.max(redBlack, avl), Math.max(splay, fibonacci)),
                    Math.max(Math.max(vanEmdeBoas, persistent), Math.max(hybrid, bPlusTree)));
            return max - min;
        }

        @Override
        public String toString() {
            return "ScoreCard{" +
                    "RED_BLACK=" + format(redBlack) +
                    ", AVL=" + format(avl) +
                    ", SPLAY=" + format(splay) +
                    ", FIBONACCI_HEAP=" + format(fibonacci) +
                    ", VAN_EMDE_BOAS=" + format(vanEmdeBoas) +
                    ", PERSISTENT_TREE=" + format(persistent) +
                    ", HYBRID=" + format(hybrid) +
                    ", B_PLUS_TREE=" + format(bPlusTree) +
                    '}';
        }
    }

    // -------------------------------------------------
    // Nested trait classes
    // -------------------------------------------------

    public static class BalanceTraits {
        private double balancePreference;
        private double depthStressTolerance;
        private double fragmentationTolerance;

        public BalanceTraits(double balancePreference,
                             double depthStressTolerance,
                             double fragmentationTolerance) {
            this.balancePreference = clamp(balancePreference);
            this.depthStressTolerance = clamp(depthStressTolerance);
            this.fragmentationTolerance = clamp(fragmentationTolerance);
        }

        public static BalanceTraits average(BalanceTraits a, BalanceTraits b) {
            return new BalanceTraits(
                    avg(a.balancePreference, b.balancePreference),
                    avg(a.depthStressTolerance, b.depthStressTolerance),
                    avg(a.fragmentationTolerance, b.fragmentationTolerance)
            );
        }

        public BalanceTraits mutatedCopy() {
            return new BalanceTraits(
                    mutateTrait(balancePreference),
                    mutateTrait(depthStressTolerance),
                    mutateTrait(fragmentationTolerance)
            );
        }

        public double compatibilityScore(BalanceTraits other) {
            return clamp(
                    (closeness(balancePreference, other.balancePreference) * 0.40) +
                    (closeness(depthStressTolerance, other.depthStressTolerance) * 0.30) +
                    (closeness(fragmentationTolerance, other.fragmentationTolerance) * 0.30)
            );
        }

        public BalanceTraits copy() {
            return new BalanceTraits(balancePreference, depthStressTolerance, fragmentationTolerance);
        }

        public void validate() {
            balancePreference = clamp(balancePreference);
            depthStressTolerance = clamp(depthStressTolerance);
            fragmentationTolerance = clamp(fragmentationTolerance);
        }

        public double getBalancePreference() {
            return balancePreference;
        }

        public void setBalancePreference(double balancePreference) {
            this.balancePreference = clamp(balancePreference);
        }

        public double getDepthStressTolerance() {
            return depthStressTolerance;
        }

        public void setDepthStressTolerance(double depthStressTolerance) {
            this.depthStressTolerance = clamp(depthStressTolerance);
        }

        public double getFragmentationTolerance() {
            return fragmentationTolerance;
        }

        public void setFragmentationTolerance(double fragmentationTolerance) {
            this.fragmentationTolerance = clamp(fragmentationTolerance);
        }

        @Override
        public String toString() {
            return "BalanceTraits{" +
                    "balancePreference=" + balancePreference +
                    ", depthStressTolerance=" + depthStressTolerance +
                    ", fragmentationTolerance=" + fragmentationTolerance +
                    '}';
        }

        @Override
        public boolean equals(Object obj) {
            if (this == obj) return true;
            if (!(obj instanceof BalanceTraits other)) return false;
            return Double.compare(balancePreference, other.balancePreference) == 0
                    && Double.compare(depthStressTolerance, other.depthStressTolerance) == 0
                    && Double.compare(fragmentationTolerance, other.fragmentationTolerance) == 0;
        }

        @Override
        public int hashCode() {
            return Objects.hash(balancePreference, depthStressTolerance, fragmentationTolerance);
        }
    }

    public static class EcologyTraits {
        private double entropyPreference;
        private double duplicateTolerance;

        public EcologyTraits(double entropyPreference, double duplicateTolerance) {
            this.entropyPreference = clamp(entropyPreference);
            this.duplicateTolerance = clamp(duplicateTolerance);
        }

        public static EcologyTraits average(EcologyTraits a, EcologyTraits b) {
            return new EcologyTraits(
                    avg(a.entropyPreference, b.entropyPreference),
                    avg(a.duplicateTolerance, b.duplicateTolerance)
            );
        }

        public EcologyTraits mutatedCopy() {
            return new EcologyTraits(
                    mutateTrait(entropyPreference),
                    mutateTrait(duplicateTolerance)
            );
        }

        public double compatibilityScore(EcologyTraits other) {
            return clamp(
                    (closeness(entropyPreference, other.entropyPreference) * 0.60) +
                    (closeness(duplicateTolerance, other.duplicateTolerance) * 0.40)
            );
        }

        public EcologyTraits copy() {
            return new EcologyTraits(entropyPreference, duplicateTolerance);
        }

        public void validate() {
            entropyPreference = clamp(entropyPreference);
            duplicateTolerance = clamp(duplicateTolerance);
        }

        public double getEntropyPreference() {
            return entropyPreference;
        }

        public void setEntropyPreference(double entropyPreference) {
            this.entropyPreference = clamp(entropyPreference);
        }

        public double getDuplicateTolerance() {
            return duplicateTolerance;
        }

        public void setDuplicateTolerance(double duplicateTolerance) {
            this.duplicateTolerance = clamp(duplicateTolerance);
        }

        @Override
        public String toString() {
            return "EcologyTraits{" +
                    "entropyPreference=" + entropyPreference +
                    ", duplicateTolerance=" + duplicateTolerance +
                    '}';
        }

        @Override
        public boolean equals(Object obj) {
            if (this == obj) return true;
            if (!(obj instanceof EcologyTraits other)) return false;
            return Double.compare(entropyPreference, other.entropyPreference) == 0
                    && Double.compare(duplicateTolerance, other.duplicateTolerance) == 0;
        }

        @Override
        public int hashCode() {
            return Objects.hash(entropyPreference, duplicateTolerance);
        }
    }

    public static class WorkloadTraits {
        private double localityPreference;
        private double orderStatisticPreference;
        private double priorityQueuePreference;

        public WorkloadTraits(double localityPreference,
                              double orderStatisticPreference,
                              double priorityQueuePreference) {
            this.localityPreference = clamp(localityPreference);
            this.orderStatisticPreference = clamp(orderStatisticPreference);
            this.priorityQueuePreference = clamp(priorityQueuePreference);
        }

        public static WorkloadTraits average(WorkloadTraits a, WorkloadTraits b) {
            return new WorkloadTraits(
                    avg(a.localityPreference, b.localityPreference),
                    avg(a.orderStatisticPreference, b.orderStatisticPreference),
                    avg(a.priorityQueuePreference, b.priorityQueuePreference)
            );
        }

        public WorkloadTraits mutatedCopy() {
            return new WorkloadTraits(
                    mutateTrait(localityPreference),
                    mutateTrait(orderStatisticPreference),
                    mutateTrait(priorityQueuePreference)
            );
        }

        public double compatibilityScore(WorkloadTraits other) {
            return clamp(
                    (closeness(localityPreference, other.localityPreference) * 0.30) +
                    (closeness(orderStatisticPreference, other.orderStatisticPreference) * 0.35) +
                    (closeness(priorityQueuePreference, other.priorityQueuePreference) * 0.35)
            );
        }

        public WorkloadTraits copy() {
            return new WorkloadTraits(localityPreference, orderStatisticPreference, priorityQueuePreference);
        }

        public void validate() {
            localityPreference = clamp(localityPreference);
            orderStatisticPreference = clamp(orderStatisticPreference);
            priorityQueuePreference = clamp(priorityQueuePreference);
        }

        public double getLocalityPreference() {
            return localityPreference;
        }

        public void setLocalityPreference(double localityPreference) {
            this.localityPreference = clamp(localityPreference);
        }

        public double getOrderStatisticPreference() {
            return orderStatisticPreference;
        }

        public void setOrderStatisticPreference(double orderStatisticPreference) {
            this.orderStatisticPreference = clamp(orderStatisticPreference);
        }

        public double getPriorityQueuePreference() {
            return priorityQueuePreference;
        }

        public void setPriorityQueuePreference(double priorityQueuePreference) {
            this.priorityQueuePreference = clamp(priorityQueuePreference);
        }

        @Override
        public String toString() {
            return "WorkloadTraits{" +
                    "localityPreference=" + localityPreference +
                    ", orderStatisticPreference=" + orderStatisticPreference +
                    ", priorityQueuePreference=" + priorityQueuePreference +
                    '}';
        }

        @Override
        public boolean equals(Object obj) {
            if (this == obj) return true;
            if (!(obj instanceof WorkloadTraits other)) return false;
            return Double.compare(localityPreference, other.localityPreference) == 0
                    && Double.compare(orderStatisticPreference, other.orderStatisticPreference) == 0
                    && Double.compare(priorityQueuePreference, other.priorityQueuePreference) == 0;
        }

        @Override
        public int hashCode() {
            return Objects.hash(localityPreference, orderStatisticPreference, priorityQueuePreference);
        }
    }

    public static class MorphTraits {
        private double mutationRate;
        private double morphThreshold;

        public MorphTraits(double mutationRate, double morphThreshold) {
            this.mutationRate = clamp(mutationRate);
            this.morphThreshold = clamp(morphThreshold);
        }

        public static MorphTraits average(MorphTraits a, MorphTraits b) {
            return new MorphTraits(
                    avg(a.mutationRate, b.mutationRate),
                    avg(a.morphThreshold, b.morphThreshold)
            );
        }

        public MorphTraits mutatedCopy() {
            return new MorphTraits(
                    mutateTrait(mutationRate),
                    mutateTrait(morphThreshold)
            );
        }

        public double compatibilityScore(MorphTraits other) {
            return clamp(
                    (closeness(mutationRate, other.mutationRate) * 0.50) +
                    (closeness(morphThreshold, other.morphThreshold) * 0.50)
            );
        }

        public MorphTraits copy() {
            return new MorphTraits(mutationRate, morphThreshold);
        }

        public void validate() {
            mutationRate = clamp(mutationRate);
            morphThreshold = clamp(morphThreshold);
        }

        public double getMutationRate() {
            return mutationRate;
        }

        public void setMutationRate(double mutationRate) {
            this.mutationRate = clamp(mutationRate);
        }

        public double getMorphThreshold() {
            return morphThreshold;
        }

        public void setMorphThreshold(double morphThreshold) {
            this.morphThreshold = clamp(morphThreshold);
        }

        @Override
        public String toString() {
            return "MorphTraits{" +
                    "mutationRate=" + mutationRate +
                    ", morphThreshold=" + morphThreshold +
                    '}';
        }

        @Override
        public boolean equals(Object obj) {
            if (this == obj) return true;
            if (!(obj instanceof MorphTraits other)) return false;
            return Double.compare(mutationRate, other.mutationRate) == 0
                    && Double.compare(morphThreshold, other.morphThreshold) == 0;
        }

        @Override
        public int hashCode() {
            return Objects.hash(mutationRate, morphThreshold);
        }
    }

    public static class CapabilityProfile {
        private double orderedSearchWeight;
        private double predecessorSuccessorWeight;
        private double rankSelectWeight;
        private double intervalQueryWeight;
        private double meldWeight;
        private double decreaseKeyWeight;
        private double extractMinWeight;
        private double persistenceWeight;
        private double localityExploitationWeight;

        public CapabilityProfile(double orderedSearchWeight,
                                 double predecessorSuccessorWeight,
                                 double rankSelectWeight,
                                 double intervalQueryWeight,
                                 double meldWeight,
                                 double decreaseKeyWeight,
                                 double extractMinWeight,
                                 double persistenceWeight,
                                 double localityExploitationWeight) {
            this.orderedSearchWeight = clamp(orderedSearchWeight);
            this.predecessorSuccessorWeight = clamp(predecessorSuccessorWeight);
            this.rankSelectWeight = clamp(rankSelectWeight);
            this.intervalQueryWeight = clamp(intervalQueryWeight);
            this.meldWeight = clamp(meldWeight);
            this.decreaseKeyWeight = clamp(decreaseKeyWeight);
            this.extractMinWeight = clamp(extractMinWeight);
            this.persistenceWeight = clamp(persistenceWeight);
            this.localityExploitationWeight = clamp(localityExploitationWeight);
        }

        public static CapabilityProfile average(CapabilityProfile a, CapabilityProfile b) {
            return new CapabilityProfile(
                    avg(a.orderedSearchWeight, b.orderedSearchWeight),
                    avg(a.predecessorSuccessorWeight, b.predecessorSuccessorWeight),
                    avg(a.rankSelectWeight, b.rankSelectWeight),
                    avg(a.intervalQueryWeight, b.intervalQueryWeight),
                    avg(a.meldWeight, b.meldWeight),
                    avg(a.decreaseKeyWeight, b.decreaseKeyWeight),
                    avg(a.extractMinWeight, b.extractMinWeight),
                    avg(a.persistenceWeight, b.persistenceWeight),
                    avg(a.localityExploitationWeight, b.localityExploitationWeight)
            );
        }

        public CapabilityProfile mutatedCopy() {
            return new CapabilityProfile(
                    mutateTrait(orderedSearchWeight),
                    mutateTrait(predecessorSuccessorWeight),
                    mutateTrait(rankSelectWeight),
                    mutateTrait(intervalQueryWeight),
                    mutateTrait(meldWeight),
                    mutateTrait(decreaseKeyWeight),
                    mutateTrait(extractMinWeight),
                    mutateTrait(persistenceWeight),
                    mutateTrait(localityExploitationWeight)
            );
        }

        public double compatibilityScore(CapabilityProfile other) {
            return clamp(
                    (closeness(orderedSearchWeight, other.orderedSearchWeight) * 0.12) +
                    (closeness(predecessorSuccessorWeight, other.predecessorSuccessorWeight) * 0.10) +
                    (closeness(rankSelectWeight, other.rankSelectWeight) * 0.12) +
                    (closeness(intervalQueryWeight, other.intervalQueryWeight) * 0.10) +
                    (closeness(meldWeight, other.meldWeight) * 0.10) +
                    (closeness(decreaseKeyWeight, other.decreaseKeyWeight) * 0.10) +
                    (closeness(extractMinWeight, other.extractMinWeight) * 0.10) +
                    (closeness(persistenceWeight, other.persistenceWeight) * 0.13) +
                    (closeness(localityExploitationWeight, other.localityExploitationWeight) * 0.13)
            );
        }

        public CapabilityProfile copy() {
            return new CapabilityProfile(
                    orderedSearchWeight,
                    predecessorSuccessorWeight,
                    rankSelectWeight,
                    intervalQueryWeight,
                    meldWeight,
                    decreaseKeyWeight,
                    extractMinWeight,
                    persistenceWeight,
                    localityExploitationWeight
            );
        }

        public void validate() {
            orderedSearchWeight = clamp(orderedSearchWeight);
            predecessorSuccessorWeight = clamp(predecessorSuccessorWeight);
            rankSelectWeight = clamp(rankSelectWeight);
            intervalQueryWeight = clamp(intervalQueryWeight);
            meldWeight = clamp(meldWeight);
            decreaseKeyWeight = clamp(decreaseKeyWeight);
            extractMinWeight = clamp(extractMinWeight);
            persistenceWeight = clamp(persistenceWeight);
            localityExploitationWeight = clamp(localityExploitationWeight);
        }

        public static CapabilityProfile defaultSearchTreeProfile() {
            return new CapabilityProfile(0.85, 0.75, 0.70, 0.35, 0.05, 0.05, 0.10, 0.20, 0.35);
        }

        public static CapabilityProfile redBlackProfile() {
            return new CapabilityProfile(0.90, 0.82, 0.78, 0.45, 0.04, 0.03, 0.08, 0.18, 0.28);
        }

        public static CapabilityProfile avlProfile() {
            return new CapabilityProfile(0.94, 0.88, 0.84, 0.48, 0.03, 0.02, 0.06, 0.20, 0.22);
        }

        public static CapabilityProfile splayProfile() {
            return new CapabilityProfile(0.78, 0.70, 0.55, 0.28, 0.05, 0.04, 0.10, 0.12, 0.95);
        }

        public static CapabilityProfile fibonacciProfile() {
            return new CapabilityProfile(0.08, 0.05, 0.04, 0.02, 0.98, 0.98, 0.96, 0.05, 0.40);
        }

        public static CapabilityProfile persistentProfile() {
            return new CapabilityProfile(0.82, 0.76, 0.86, 0.40, 0.04, 0.03, 0.08, 0.98, 0.22);
        }

        public static CapabilityProfile hybridProfile() {
            return new CapabilityProfile(0.82, 0.76, 0.80, 0.55, 0.28, 0.26, 0.30, 0.42, 0.50);
        }

        public double getOrderedSearchWeight() {
            return orderedSearchWeight;
        }

        public void setOrderedSearchWeight(double orderedSearchWeight) {
            this.orderedSearchWeight = clamp(orderedSearchWeight);
        }

        public double getPredecessorSuccessorWeight() {
            return predecessorSuccessorWeight;
        }

        public void setPredecessorSuccessorWeight(double predecessorSuccessorWeight) {
            this.predecessorSuccessorWeight = clamp(predecessorSuccessorWeight);
        }

        public double getRankSelectWeight() {
            return rankSelectWeight;
        }

        public void setRankSelectWeight(double rankSelectWeight) {
            this.rankSelectWeight = clamp(rankSelectWeight);
        }

        public double getIntervalQueryWeight() {
            return intervalQueryWeight;
        }

        public void setIntervalQueryWeight(double intervalQueryWeight) {
            this.intervalQueryWeight = clamp(intervalQueryWeight);
        }

        public double getMeldWeight() {
            return meldWeight;
        }

        public void setMeldWeight(double meldWeight) {
            this.meldWeight = clamp(meldWeight);
        }

        public double getDecreaseKeyWeight() {
            return decreaseKeyWeight;
        }

        public void setDecreaseKeyWeight(double decreaseKeyWeight) {
            this.decreaseKeyWeight = clamp(decreaseKeyWeight);
        }

        public double getExtractMinWeight() {
            return extractMinWeight;
        }

        public void setExtractMinWeight(double extractMinWeight) {
            this.extractMinWeight = clamp(extractMinWeight);
        }

        public double getPersistenceWeight() {
            return persistenceWeight;
        }

        public void setPersistenceWeight(double persistenceWeight) {
            this.persistenceWeight = clamp(persistenceWeight);
        }

        public double getLocalityExploitationWeight() {
            return localityExploitationWeight;
        }

        public void setLocalityExploitationWeight(double localityExploitationWeight) {
            this.localityExploitationWeight = clamp(localityExploitationWeight);
        }

        @Override
        public String toString() {
            return "CapabilityProfile{" +
                    "orderedSearchWeight=" + orderedSearchWeight +
                    ", predecessorSuccessorWeight=" + predecessorSuccessorWeight +
                    ", rankSelectWeight=" + rankSelectWeight +
                    ", intervalQueryWeight=" + intervalQueryWeight +
                    ", meldWeight=" + meldWeight +
                    ", decreaseKeyWeight=" + decreaseKeyWeight +
                    ", extractMinWeight=" + extractMinWeight +
                    ", persistenceWeight=" + persistenceWeight +
                    ", localityExploitationWeight=" + localityExploitationWeight +
                    '}';
        }

        @Override
        public boolean equals(Object obj) {
            if (this == obj) return true;
            if (!(obj instanceof CapabilityProfile other)) return false;
            return Double.compare(orderedSearchWeight, other.orderedSearchWeight) == 0
                    && Double.compare(predecessorSuccessorWeight, other.predecessorSuccessorWeight) == 0
                    && Double.compare(rankSelectWeight, other.rankSelectWeight) == 0
                    && Double.compare(intervalQueryWeight, other.intervalQueryWeight) == 0
                    && Double.compare(meldWeight, other.meldWeight) == 0
                    && Double.compare(decreaseKeyWeight, other.decreaseKeyWeight) == 0
                    && Double.compare(extractMinWeight, other.extractMinWeight) == 0
                    && Double.compare(persistenceWeight, other.persistenceWeight) == 0
                    && Double.compare(localityExploitationWeight, other.localityExploitationWeight) == 0;
        }

        @Override
        public int hashCode() {
            return Objects.hash(
                    orderedSearchWeight,
                    predecessorSuccessorWeight,
                    rankSelectWeight,
                    intervalQueryWeight,
                    meldWeight,
                    decreaseKeyWeight,
                    extractMinWeight,
                    persistenceWeight,
                    localityExploitationWeight
            );
        }
    }

    // -------------------------------------------------
    // Builder
    // -------------------------------------------------

    public static class Builder {
        private UUID genomeId;
        private UUID parentAId;
        private UUID parentBId;
        private int generation = 0;
        private long createdAtEpochMillis = System.currentTimeMillis();
        private GenomeOrigin origin = GenomeOrigin.MANUAL;
        private StructureType preferredStructure = StructureType.RED_BLACK;
        private AdaptationMode adaptationMode = AdaptationMode.BALANCED;
        private BalanceTraits balanceTraits = new BalanceTraits(0.75, 0.50, 0.50);
        private EcologyTraits ecologyTraits = new EcologyTraits(0.60, 0.50);
        private WorkloadTraits workloadTraits = new WorkloadTraits(0.40, 0.70, 0.20);
        private MorphTraits morphTraits = new MorphTraits(0.05, 0.70);
        private CapabilityProfile capabilityProfile = CapabilityProfile.defaultSearchTreeProfile();
        private String lineageTag = "BuilderGenome";
        private String notes = "";

        public Builder genomeId(UUID genomeId) {
            this.genomeId = genomeId;
            return this;
        }

        public Builder parentAId(UUID parentAId) {
            this.parentAId = parentAId;
            return this;
        }

        public Builder parentBId(UUID parentBId) {
            this.parentBId = parentBId;
            return this;
        }

        public Builder generation(int generation) {
            this.generation = generation;
            return this;
        }

        public Builder createdAtEpochMillis(long createdAtEpochMillis) {
            this.createdAtEpochMillis = createdAtEpochMillis;
            return this;
        }

        public Builder origin(GenomeOrigin origin) {
            this.origin = origin;
            return this;
        }

        public Builder preferredStructure(StructureType preferredStructure) {
            this.preferredStructure = preferredStructure;
            return this;
        }

        public Builder adaptationMode(AdaptationMode adaptationMode) {
            this.adaptationMode = adaptationMode;
            return this;
        }

        public Builder balanceTraits(BalanceTraits balanceTraits) {
            this.balanceTraits = balanceTraits;
            return this;
        }

        public Builder ecologyTraits(EcologyTraits ecologyTraits) {
            this.ecologyTraits = ecologyTraits;
            return this;
        }

        public Builder workloadTraits(WorkloadTraits workloadTraits) {
            this.workloadTraits = workloadTraits;
            return this;
        }

        public Builder morphTraits(MorphTraits morphTraits) {
            this.morphTraits = morphTraits;
            return this;
        }

        public Builder capabilityProfile(CapabilityProfile capabilityProfile) {
            this.capabilityProfile = capabilityProfile;
            return this;
        }

        public Builder lineageTag(String lineageTag) {
            this.lineageTag = lineageTag;
            return this;
        }

        public Builder notes(String notes) {
            this.notes = notes;
            return this;
        }

        public TreeGenome build() {
            return new TreeGenome(
                    genomeId,
                    parentAId,
                    parentBId,
                    generation,
                    createdAtEpochMillis,
                    origin,
                    preferredStructure,
                    adaptationMode,
                    balanceTraits,
                    ecologyTraits,
                    workloadTraits,
                    morphTraits,
                    capabilityProfile,
                    lineageTag,
                    notes
            );
        }
    }

    // -------------------------------------------------
    // Helpers
    // -------------------------------------------------

    private static double clamp(double value) {
        if (value < MIN_TRAIT) return MIN_TRAIT;
        if (value > MAX_TRAIT) return MAX_TRAIT;
        return value;
    }

    private static double avg(double a, double b) {
        return (a + b) / 2.0;
    }

    private static double closeness(double a, double b) {
        return 1.0 - Math.abs(a - b);
    }

    private static double mutateTrait(double value) {
        double delta = (RNG.nextDouble() * 2.0 * DEFAULT_MUTATION_DELTA) - DEFAULT_MUTATION_DELTA;
        return clamp(value + delta);
    }

    private static String normalizeLineageTag(String lineageTag) {
        if (lineageTag == null || lineageTag.isBlank()) {
            return "UnnamedLineage";
        }
        return lineageTag.trim();
    }

    /** Cap for the free-text provenance note — see below. */
    private static final int MAX_NOTES_LENGTH = 512;

    /**
     * Trim and CAP the provenance note (bug audit 2026-08-12, G-F): every stagnation
     * mutation and morph appended " | Mutated from &lt;uuid&gt;", so a long-lived tree's
     * genome accumulated an O(ops) note (11.7k chars after 20k ops) with O(len) copy
     * cost per mutation. The tail is kept — the recent history is the useful part.
     */
    private static String normalizeNotes(String notes) {
        if (notes == null) return "";
        String trimmed = notes.trim();
        if (trimmed.length() <= MAX_NOTES_LENGTH) return trimmed;
        return "…" + trimmed.substring(trimmed.length() - MAX_NOTES_LENGTH);
    }

    private static <T> T randomEnum(T[] values) {
        return values[RNG.nextInt(values.length)];
    }

    private static String format(double value) {
        return String.format(Locale.US, "%.3f", value);
    }

    // -------------------------------------------------
    // Getters / Setters
    // -------------------------------------------------

    public UUID getGenomeId() {
        return genomeId;
    }

    public void setGenomeId(UUID genomeId) {
        this.genomeId = Objects.requireNonNull(genomeId, "genomeId cannot be null");
    }

    public UUID getParentAId() {
        return parentAId;
    }

    public void setParentAId(UUID parentAId) {
        this.parentAId = parentAId;
    }

    public UUID getParentBId() {
        return parentBId;
    }

    public void setParentBId(UUID parentBId) {
        this.parentBId = parentBId;
    }

    public int getGeneration() {
        return generation;
    }

    public void setGeneration(int generation) {
        this.generation = Math.max(0, generation);
    }

    public long getCreatedAtEpochMillis() {
        return createdAtEpochMillis;
    }

    public void setCreatedAtEpochMillis(long createdAtEpochMillis) {
        this.createdAtEpochMillis = Math.max(1L, createdAtEpochMillis);
    }

    public GenomeOrigin getOrigin() {
        return origin;
    }

    public void setOrigin(GenomeOrigin origin) {
        this.origin = Objects.requireNonNull(origin, "origin cannot be null");
    }

    public StructureType getPreferredStructure() {
        return preferredStructure;
    }

    public void setPreferredStructure(StructureType preferredStructure) {
        this.preferredStructure = Objects.requireNonNull(preferredStructure, "preferredStructure cannot be null");
    }

    public AdaptationMode getAdaptationMode() {
        return adaptationMode;
    }

    public void setAdaptationMode(AdaptationMode adaptationMode) {
        this.adaptationMode = Objects.requireNonNull(adaptationMode, "adaptationMode cannot be null");
    }

    public BalanceTraits getBalanceTraits() {
        return balanceTraits;
    }

    public void setBalanceTraits(BalanceTraits balanceTraits) {
        this.balanceTraits = Objects.requireNonNull(balanceTraits, "balanceTraits cannot be null");
    }

    public EcologyTraits getEcologyTraits() {
        return ecologyTraits;
    }

    public void setEcologyTraits(EcologyTraits ecologyTraits) {
        this.ecologyTraits = Objects.requireNonNull(ecologyTraits, "ecologyTraits cannot be null");
    }

    public WorkloadTraits getWorkloadTraits() {
        return workloadTraits;
    }

    public void setWorkloadTraits(WorkloadTraits workloadTraits) {
        this.workloadTraits = Objects.requireNonNull(workloadTraits, "workloadTraits cannot be null");
    }

    public MorphTraits getMorphTraits() {
        return morphTraits;
    }

    public void setMorphTraits(MorphTraits morphTraits) {
        this.morphTraits = Objects.requireNonNull(morphTraits, "morphTraits cannot be null");
    }

    public CapabilityProfile getCapabilityProfile() {
        return capabilityProfile;
    }

    public void setCapabilityProfile(CapabilityProfile capabilityProfile) {
        this.capabilityProfile = Objects.requireNonNull(capabilityProfile, "capabilityProfile cannot be null");
    }

    public String getLineageTag() {
        return lineageTag;
    }

    public void setLineageTag(String lineageTag) {
        this.lineageTag = normalizeLineageTag(lineageTag);
    }

    public String getNotes() {
        return notes;
    }

    public void setNotes(String notes) {
        this.notes = normalizeNotes(notes);
    }
}
