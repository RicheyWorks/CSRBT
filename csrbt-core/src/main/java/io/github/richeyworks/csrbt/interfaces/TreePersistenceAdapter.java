package io.github.richeyworks.csrbt.interfaces;

import io.github.richeyworks.csrbt.TreeContext;

public interface TreePersistenceAdapter {

    /**
     * Persist a named snapshot to durable storage.
     */
    void saveSnapshot(String name, TreeContext snapshot);

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
}
