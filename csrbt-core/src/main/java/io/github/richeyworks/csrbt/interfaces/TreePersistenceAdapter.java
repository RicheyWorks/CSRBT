package io.github.richeyworks.csrbt.interfaces;

import io.github.richeyworks.csrbt.TreeContext;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.util.Objects;

/**
 * The persistence seam: named snapshots in, named snapshots out.
 *
 * <h2>Failure signaling (ADR-025)</h2>
 *
 * <p>{@link #saveSnapshot} returns {@code void} and is documented as best-effort: an implementation
 * that cannot write the snapshot reports it however it reports anything else (the built-in
 * {@code FilePersistenceAdapter} logs at ERROR) and returns normally. That is the published 0.2.0
 * contract and it does not change — a caller that never checked a save is not suddenly given an
 * exception to handle, and every existing implementor keeps compiling.</p>
 *
 * <p>{@link #trySaveSnapshot} is the same save with an <b>answer</b>: a {@link SaveResult} saying
 * whether the snapshot reached durable storage, and why not when it did not. It is a
 * {@code default} method, so it is additive in both directions — existing callers are untouched and
 * existing implementors inherit a version that delegates to their {@code saveSnapshot} and honestly
 * reports {@link SaveStatus#UNREPORTED}, because an implementation that returns {@code void} by
 * definition cannot say more than that. Overriding it is how an adapter opts in to reporting.</p>
 */
public interface TreePersistenceAdapter {

    /**
     * Persist a named snapshot to durable storage, best-effort: a failure is reported through the
     * implementation's own channel (a log, typically) and this method returns normally.
     *
     * <p>Callers that need to know whether the snapshot is durable should call
     * {@link #trySaveSnapshot} instead — same work, same failure modes, plus an answer.</p>
     */
    void saveSnapshot(String name, TreeContext snapshot);

    /**
     * Persist a named snapshot and report the outcome (ADR-025).
     *
     * <p>The default implementation calls {@link #saveSnapshot} and returns
     * {@link SaveStatus#UNREPORTED} — the honest answer for an adapter that has not opted in, since
     * a {@code void} save cannot distinguish success from failure. It is <em>not</em>
     * {@link SaveStatus#SAVED}: a signal that lies when it does not know is worse than no signal,
     * which is the whole reason this method exists.</p>
     *
     * <p>Argument validation is unchanged: a malformed snapshot name or a null argument still
     * throws, because those are caller defects, deterministic, and not retryable — the result
     * object is for <em>environmental</em> failures (a full disk, a revoked permission, an I/O
     * error mid-write, a commit that could not be published) which a caller can actually act on.</p>
     *
     * @return the outcome; never {@code null}
     */
    default SaveResult trySaveSnapshot(String name, TreeContext snapshot) {
        saveSnapshot(name, snapshot);
        return SaveResult.unreported(name);
    }

    /**
     * Retrieve a previously saved snapshot by name.
     * Returns null if not found.
     *
     * <p>{@code null} is also what a snapshot that <em>was</em> found but could not be used looks
     * like — see {@link #tryLoadSnapshot} for the version that says which.</p>
     */
    TreeContext loadSnapshot(String name);

    /**
     * Retrieve a previously saved snapshot and report the outcome (ADR-026).
     *
     * <p>The read-side twin of {@link #trySaveSnapshot}, and the answer to the question a bare
     * {@code null} cannot: was there no snapshot ({@link LoadStatus#ABSENT} — start fresh), was
     * there one that is not usable ({@link LoadStatus#MALFORMED} — do not start fresh, and do not
     * overwrite it), or could the file not be read at all ({@link LoadStatus#FAILED} — retry, or
     * fail over; the snapshot may be perfectly good).</p>
     *
     * <p>The default implementation calls {@link #loadSnapshot} and reports {@link
     * LoadStatus#LOADED} for a non-null return, {@link LoadStatus#UNREPORTED} for {@code null}.
     * That asymmetry with {@code trySaveSnapshot}'s default is deliberate and is the honest
     * reading of each: a {@code void} save says nothing at all, whereas a load that hands back a
     * context has demonstrably loaded one. Only the {@code null} is ambiguous, so only the
     * {@code null} is unreported. Overriding this is how an adapter opts in to naming the
     * reason.</p>
     *
     * <p>Argument validation is unchanged: a malformed snapshot name still throws, because that is
     * a caller defect — deterministic, not retryable, and fixed by changing code rather than by
     * changing the disk.</p>
     *
     * @return the outcome; never {@code null}
     */
    default LoadResult<TreeContext> tryLoadSnapshot(String name) {
        TreeContext loaded = loadSnapshot(name);
        return loaded != null ? LoadResult.loaded(name, loaded) : LoadResult.unreported(name);
    }

    /**
     * List all saved snapshot names.
     *
     * <p>An empty list is also what an unreadable snapshot directory looks like — see
     * {@link #tryListSnapshots} for the version that says which.</p>
     */
    java.util.List<String> listSnapshots();

    /**
     * List all saved snapshot names and report the outcome (ADR-026).
     *
     * <p>{@link #listSnapshots} returns {@code []} both for "there are no snapshots" and for "the
     * directory could not be read", which are different facts about the world. This reports
     * {@link LoadStatus#LOADED} with the (possibly empty) list when the directory was read, and
     * {@link LoadStatus#FAILED} carrying the {@code IOException} when it was not.</p>
     *
     * <p>The default implementation infers what it honestly can from {@link #listSnapshots}: a
     * non-empty list was certainly read, an empty one might not have been.</p>
     *
     * @return the outcome; never {@code null}
     */
    default LoadResult<java.util.List<String>> tryListSnapshots() {
        java.util.List<String> names = listSnapshots();
        return names != null && !names.isEmpty()
                ? LoadResult.loaded(ALL_SNAPSHOTS, names)
                : LoadResult.unreported(ALL_SNAPSHOTS);
    }

    /**
     * The {@link LoadResult#name()} a listing carries, since it asks about the whole snapshot
     * directory rather than one named snapshot (ADR-026).
     */
    String ALL_SNAPSHOTS = "*";

    /**
     * Delete a named snapshot.
     */
    boolean deleteSnapshot(String name);

    /**
     * What a save is known to have done (ADR-025).
     *
     * <p>There is deliberately no {@code PARTIAL}: a save stages to a sibling temporary file and
     * publishes it with an atomic rename (consolidation D-3, hardened by sixth-pass fix S6-05), so
     * a target is either the complete new snapshot or the complete previous one — never a blend.
     * A state no implementation can reach is a state every caller has to handle for nothing.</p>
     */
    enum SaveStatus {
        /** The snapshot reached durable storage and is loadable. */
        SAVED,
        /** The snapshot did not reach storage; any previous snapshot of this name is intact. */
        FAILED,
        /** The adapter does not report outcomes — it may have saved, it may not. */
        UNREPORTED
    }

    /**
     * The outcome of one {@link #trySaveSnapshot} call — a value, not a process: store it, log it,
     * branch on it (ADR-025).
     *
     * <p>Why a result object rather than a {@code boolean}: the two failures a caller treats
     * differently are "the volume is full / the mount went away", which is worth retrying or
     * failing over to another location, and "this configuration can never write here", which is
     * worth surfacing to an operator. A bare {@code false} cannot tell them apart, and the whole
     * argument for the signal is that the caller can do something with it.</p>
     *
     * @param name   the snapshot name that was attempted
     * @param status what is known to have happened
     * @param detail a one-line, human-readable explanation (never {@code null})
     * @param cause  the I/O failure behind a {@link SaveStatus#FAILED}, else {@code null}
     */
    record SaveResult(String name, SaveStatus status, String detail, IOException cause) {

        public SaveResult {
            Objects.requireNonNull(name, "name cannot be null");
            Objects.requireNonNull(status, "status cannot be null");
            Objects.requireNonNull(detail, "detail cannot be null");
            if ((status == SaveStatus.FAILED) != (cause != null)) {
                throw new IllegalArgumentException(
                        "a FAILED result carries its cause and no other status may: " + status);
            }
        }

        /** The snapshot is durable. */
        public static SaveResult saved(String name) {
            return new SaveResult(name, SaveStatus.SAVED, "saved", null);
        }

        /** The snapshot was not written; the previous snapshot of this name (if any) is intact. */
        public static SaveResult failed(String name, IOException cause) {
            Objects.requireNonNull(cause, "a failed save must carry its cause");
            return new SaveResult(name, SaveStatus.FAILED,
                    cause.getClass().getSimpleName() + ": " + cause.getMessage(), cause);
        }

        /** The adapter does not report outcomes (the {@code void}-only default). */
        public static SaveResult unreported(String name) {
            return new SaveResult(name, SaveStatus.UNREPORTED,
                    "adapter does not report save outcomes", null);
        }

        /** True only when the snapshot is known to be durable. */
        public boolean saved() { return status == SaveStatus.SAVED; }

        /** True only when the save is known to have failed. */
        public boolean failed() { return status == SaveStatus.FAILED; }

        /**
         * Escalate a known failure to an exception, for callers that would rather not branch —
         * the "unchecked exception" option, opt-in at the call site instead of imposed on every
         * caller of a published API.
         *
         * @return {@code this} when the save did not fail
         * @throws UncheckedIOException when it did
         */
        public SaveResult orThrow() {
            if (status == SaveStatus.FAILED) {
                throw new UncheckedIOException("snapshot '" + name + "' was not saved: " + detail, cause);
            }
            return this;
        }

        @Override
        public String toString() {
            return "SaveResult[" + name + " " + status + ": " + detail + "]";
        }
    }

    /**
     * What a load is known to have done (ADR-026).
     *
     * <p>The states are the ones a caller <em>acts</em> on, which is the only test a signal has to
     * pass. {@link #ABSENT} is the single case in which "there is no checkpoint, start fresh" is
     * the right move; the published {@code null} return meant it and eight other things at once.
     * {@link #MALFORMED} and {@link #FAILED} are kept apart for exactly the reason ADR-025 kept
     * "the volume is full, retry" apart from "this configuration can never work": one is worth
     * retrying and one is worth telling an operator about.</p>
     */
    enum LoadStatus {
        /** The snapshot was read and passed every gate; the value is present. */
        LOADED,
        /** There is no snapshot of that name. Nothing is wrong. */
        ABSENT,
        /**
         * The snapshot exists and is not usable — a truncated or tampered file, a header that does
         * not parse, a tree that failed the structural gate. Deterministic: rereading it produces
         * the same answer. The file is left on disk exactly as it was found.
         */
        MALFORMED,
        /** An {@code IOException} prevented reading. The snapshot itself may be perfectly good. */
        FAILED,
        /** The adapter does not report load outcomes — it may have been absent, it may not. */
        UNREPORTED
    }

    /**
     * The outcome of one {@code tryLoad…} call — a value, not a process: store it, log it, branch
     * on it (ADR-026).
     *
     * <p>Why a result object rather than the published {@code null}: the read side decides
     * <em>what state the caller runs on</em>. Falling back to an empty set is correct when there is
     * no snapshot and is silent data loss when the snapshot is merely unreadable, and a bare
     * {@code null} cannot tell those apart. Two compact-constructor invariants make the states
     * unfakeable — a {@link LoadStatus#LOADED} result carries its value and no other status may, a
     * {@link LoadStatus#FAILED} result carries its cause and no other status may — so the signal
     * can never be a bare boolean in disguise.</p>
     *
     * @param <T>    what was being loaded — a {@code TreeContext}, an {@code OrderedSet}, a
     *               {@code PersistentTreeEngine}, an {@code EnsembleOrderedSet}, or the name list
     * @param name   the snapshot name that was asked for, or {@link #ALL_SNAPSHOTS} for a listing
     * @param status what is known to have happened
     * @param detail a one-line, human-readable explanation (never {@code null})
     * @param value  what was loaded on {@link LoadStatus#LOADED}, else {@code null}
     * @param cause  the I/O failure behind a {@link LoadStatus#FAILED}, else {@code null}
     */
    record LoadResult<T>(String name, LoadStatus status, T value, String detail, IOException cause) {

        public LoadResult {
            Objects.requireNonNull(name, "name cannot be null");
            Objects.requireNonNull(status, "status cannot be null");
            Objects.requireNonNull(detail, "detail cannot be null");
            if ((status == LoadStatus.LOADED) != (value != null)) {
                throw new IllegalArgumentException(
                        "a LOADED result carries its value and no other status may: " + status);
            }
            if ((status == LoadStatus.FAILED) != (cause != null)) {
                throw new IllegalArgumentException(
                        "a FAILED result carries its cause and no other status may: " + status);
            }
        }

        /** The snapshot was read and validated. */
        public static <T> LoadResult<T> loaded(String name, T value) {
            Objects.requireNonNull(value, "a loaded result must carry what it loaded");
            return new LoadResult<>(name, LoadStatus.LOADED, value, "loaded", null);
        }

        /** There is no snapshot of that name — the one case where starting fresh is right. */
        public static <T> LoadResult<T> absent(String name) {
            return new LoadResult<>(name, LoadStatus.ABSENT, null, "no snapshot of that name", null);
        }

        /**
         * The snapshot exists and cannot be used; the file is untouched.
         *
         * @param why which gate rejected it, in enough detail to act on
         */
        public static <T> LoadResult<T> malformed(String name, String why) {
            Objects.requireNonNull(why, "a malformed result must say what is wrong");
            return new LoadResult<>(name, LoadStatus.MALFORMED, null, why, null);
        }

        /** An I/O failure prevented the read. */
        public static <T> LoadResult<T> failed(String name, IOException cause) {
            Objects.requireNonNull(cause, "a failed load must carry its cause");
            return new LoadResult<>(name, LoadStatus.FAILED, null,
                    cause.getClass().getSimpleName() + ": " + cause.getMessage(), cause);
        }

        /** The adapter does not report load outcomes (the {@code null}-only default). */
        public static <T> LoadResult<T> unreported(String name) {
            return new LoadResult<>(name, LoadStatus.UNREPORTED, null,
                    "adapter does not report load outcomes", null);
        }

        /** True only when the value is present. */
        public boolean loaded() { return status == LoadStatus.LOADED; }

        /** True only when there is known to be no snapshot of this name. */
        public boolean absent() { return status == LoadStatus.ABSENT; }

        /** True only when the snapshot was found and rejected. */
        public boolean malformed() { return status == LoadStatus.MALFORMED; }

        /** True only when the read is known to have failed. */
        public boolean failed() { return status == LoadStatus.FAILED; }

        /**
         * The loaded value, or {@code fallback} for every other status — the one-liner for the
         * "fall back, rebuild" caller.
         *
         * @param fallback what to use when nothing was loaded; may be {@code null}
         * @return the value on {@link LoadStatus#LOADED}, else {@code fallback}
         */
        public T orElse(T fallback) {
            return status == LoadStatus.LOADED ? value : fallback;
        }

        /**
         * Escalate a known non-answer to an exception, for callers that would rather not branch —
         * the "unchecked exception" option, opt-in at the call site instead of imposed on every
         * caller of a published API.
         *
         * <p>{@link LoadStatus#MALFORMED} escalates alongside {@link LoadStatus#FAILED}: both mean
         * the caller does not have the data and something is wrong. {@link LoadStatus#ABSENT} does
         * not — "there is no snapshot" is an answer the caller asked for and can act on. A
         * MALFORMED result has no {@code cause} to carry (nothing threw; the file simply is not a
         * snapshot), so one is synthesized from the detail rather than inventing a second exception
         * type for callers to catch.</p>
         *
         * @return {@code this} when the load did not fail
         * @throws UncheckedIOException when it did
         */
        public LoadResult<T> orThrow() {
            if (status == LoadStatus.FAILED) {
                throw new UncheckedIOException("snapshot '" + name + "' could not be read: " + detail, cause);
            }
            if (status == LoadStatus.MALFORMED) {
                throw new UncheckedIOException("snapshot '" + name + "' is not usable: " + detail,
                        new IOException(detail));
            }
            return this;
        }

        @Override
        public String toString() {
            return "LoadResult[" + name + " " + status + ": " + detail + "]";
        }
    }
}
