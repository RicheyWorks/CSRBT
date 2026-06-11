package io.github.richeyworks.csrbt.persistence;

/**
 * Pluggable key (de)serializer for the snapshot text format (ADR-002 step 5).
 *
 * <p>The {@link FilePersistenceAdapter} flat format is key-agnostic except at two points —
 * emitting a key and parsing one — and this contract is what fills that hole for an arbitrary
 * key type {@code K}. {@link #serialize} renders a key as a single token; {@link #deserialize}
 * parses a token produced by {@code serialize}.</p>
 *
 * <p><b>Token contract.</b> The format separates nodes with {@code ';'}, splits a node on
 * {@code ','} (into {@code DATA,COLOR[,TAG]}), marks a NIL child with {@code '#'}, and treats an
 * empty token as NIL. A serialized key token therefore <em>must not</em> contain {@code ','} or
 * {@code ';'}, must not equal {@code "#"}, and must not be empty. ({@code '|'} is a header
 * delimiter only and never appears on the node line.) The numeric built-ins satisfy this for
 * free; {@link #string()} percent-encodes the reserved characters so any non-empty string is
 * safe.</p>
 */
public interface KeySerializer<K> {

    /** Render {@code key} as one delimiter-safe token (see the token contract above). */
    String serialize(K key);

    /** Parse a token produced by {@link #serialize}. */
    K deserialize(String token);

    /**
     * Built-in for {@code Integer} keys — the historical int snapshot format. Using this with
     * the int adapter path reproduces every byte of the legacy {@code .rbt} files.
     */
    KeySerializer<Integer> INTEGER = new KeySerializer<Integer>() {
        @Override public String  serialize(Integer key)  { return Integer.toString(key); }
        @Override public Integer deserialize(String tok)  { return Integer.valueOf(tok.trim()); }
    };

    /** Built-in for {@code Long} keys. */
    KeySerializer<Long> LONG = new KeySerializer<Long>() {
        @Override public String serialize(Long key)  { return Long.toString(key); }
        @Override public Long   deserialize(String tok) { return Long.valueOf(tok.trim()); }
    };

    /**
     * Serializer for arbitrary <em>non-empty</em> {@code String} keys. Reserved format
     * characters are percent-encoded so adversarial keys (containing {@code ',' ';' '#'})
     * round-trip intact.
     */
    static KeySerializer<String> string() {
        return StringKeySerializer.INSTANCE;
    }
}
