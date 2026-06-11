package io.github.richeyworks.csrbt.event;

/**
 * Receiver for {@link TreeEvent}s (ADR-009 P3). Register with
 * {@code OrderedSet.setEventListener} / {@code EnsembleOrderedSet.setEventListener};
 * {@code null} unregisters.
 *
 * <p><b>Contract:</b> listeners are invoked synchronously on the mutating thread, while the
 * set's internal locks are held — exactly like the log lines they mirror. A listener must be
 * fast, must not throw, and must never call back into the set (reentry can deadlock).
 * Queueing for another thread is the listener's job if it needs to do real work.</p>
 */
@FunctionalInterface
public interface TreeEventListener<K> {

    void onEvent(TreeEvent<K> event);
}
