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
     */
    TreeContext loadSnapshot(String name);

    /**
     * List all saved snapshot names.
     */
    java.util.List<String> listSnapshots();

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
}
