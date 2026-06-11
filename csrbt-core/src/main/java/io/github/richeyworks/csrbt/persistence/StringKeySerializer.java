package io.github.richeyworks.csrbt.persistence;

/**
 * {@link KeySerializer} for arbitrary non-empty {@code String} keys.
 *
 * <p>The snapshot text format reserves a small set of structural characters (see
 * {@link KeySerializer}). This serializer percent-encodes them so any non-empty string
 * round-trips, including keys that themselves contain delimiters:</p>
 *
 * <pre>
 *   '%' -&gt; %25   (encoded first, so decoding is unambiguous)
 *   ',' -&gt; %2C
 *   ';' -&gt; %3B
 *   '#' -&gt; %23
 *   '|' -&gt; %7C
 * </pre>
 *
 * <p>Only those ASCII characters are ever encoded, so decoding is a plain two-hex {@code %XX}
 * scan and non-ASCII characters pass through untouched. The empty string is rejected because the
 * format treats an empty token as a NIL marker.</p>
 */
final class StringKeySerializer implements KeySerializer<String> {

    static final StringKeySerializer INSTANCE = new StringKeySerializer();

    private StringKeySerializer() {}

    @Override
    public String serialize(String key) {
        if (key == null) {
            throw new IllegalArgumentException("key must not be null");
        }
        if (key.isEmpty()) {
            throw new IllegalArgumentException(
                    "empty-string keys are not supported by the snapshot format");
        }
        StringBuilder b = new StringBuilder(key.length() + 8);
        for (int i = 0; i < key.length(); i++) {
            char c = key.charAt(i);
            switch (c) {
                case '%': b.append("%25"); break;
                case ',': b.append("%2C"); break;
                case ';': b.append("%3B"); break;
                case '#': b.append("%23"); break;
                case '|': b.append("%7C"); break;
                default:  b.append(c);
            }
        }
        return b.toString();
    }

    @Override
    public String deserialize(String token) {
        if (token == null) {
            throw new IllegalArgumentException("token must not be null");
        }
        if (token.indexOf('%') < 0) {
            return token;                       // fast path: nothing was escaped
        }
        StringBuilder b = new StringBuilder(token.length());
        for (int i = 0; i < token.length(); i++) {
            char c = token.charAt(i);
            if (c == '%') {
                if (i + 2 >= token.length()) {
                    throw new IllegalArgumentException("truncated %-escape in token: " + token);
                }
                int hi = Character.digit(token.charAt(i + 1), 16);
                int lo = Character.digit(token.charAt(i + 2), 16);
                if (hi < 0 || lo < 0) {
                    throw new IllegalArgumentException("invalid %-escape in token: " + token);
                }
                b.append((char) ((hi << 4) + lo));
                i += 2;
            } else {
                b.append(c);
            }
        }
        return b.toString();
    }
}
