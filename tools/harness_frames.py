# -*- coding: utf-8 -*-
"""The wire, before it is a message: bytes in, one strict JSON value out (ADR-221).

Every door in this kit read its frames with `for line in sys.stdin` and
`json.loads(line)`, and each half of that is a decision nobody made.

`for line in sys.stdin` lets the MACHINE decide what the bytes mean. On a
UTF-8 locale with strict errors, one malformed byte raises inside the iterator
and the door is gone -- before it has answered the frames in front of the bad
one, because the decoder reads ahead. On a Windows code page nothing raises and
everything is wrong: a host that sends `Bear Creek — café` as UTF-8, which is
what MCP requires of it, is heard as `Bear Creek â€” cafÃ©`, and that is what
the door then types into the page. On a POSIX locale the bytes are smuggled
through as lone surrogates and surface somewhere else. Three machines, three
behaviours, and the tests passed on all of them because the tests sent ASCII.

`json.loads` decides the rest, and it is a lenient reader: a key given twice
keeps the LAST one silently, so `{"action":"ok","action":"clear-all"}` is one
command to a logger that reads the first and another to the door; `NaN` and
`Infinity` are accepted though they are not JSON; a hundred thousand open
brackets raise RecursionError, which is not a ValueError and went straight
through the MCP door's `except ValueError` and out of the process.

So the door reads BYTES, decodes them itself, strictly, as UTF-8, one bounded
line at a time, and parses them strictly. A frame that fails any of that is
REFUSED AND THE NEXT ONE IS READ: nothing a client can send ends the loop.

The shape of this file is the FlowersForever harness's `McpFrameReader`, which
learned the same thing from the same kind of evidence (two malformed-frame
cases that killed its reader). What differs is that this one serves three
transports, so it is a module and not a class inside one of them.

    for msg, err in frames(sys.stdin):
        if err is not None:
            answer(err.code, err.message)      # and carry on
            continue
        handle(msg)
"""
import json

# One frame. The HTTP door has refused a body over 1 MiB since ADR-192 and the
# two pipe doors had no bound at all: a 32 MiB line was read whole, parsed, and
# answered. The same number, so a command that fits one door fits them all.
FRAME_CAP = 1 << 20
_DRAIN = 1 << 16
BOM = b"\xef\xbb\xbf"

CODES = ("too_large", "not_utf8", "not_json", "duplicate_key", "not_finite")


class FrameError(Exception):
    """A frame that is not a message. `code` is one of CODES."""

    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code, self.message = code, message


def _pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise FrameError("duplicate_key",
                             "the key %r appears twice in one object: a reader that keeps the "
                             "first and a reader that keeps the last would be given two "
                             "different messages, so this is not one" % k[:60])
        out[k] = v
    return out


def _constant(name):
    raise FrameError("not_finite", "%s is not JSON, and no argument of this contract is "
                                   "anything but a finite number" % name)


def _float(text):
    v = float(text)
    if v != v or v in (float("inf"), float("-inf")):
        raise FrameError("not_finite", "%s does not fit a finite number" % text[:40])
    return v


def loads(data):
    """bytes (or str) -> one JSON value, strictly. Raises FrameError."""
    if isinstance(data, (bytes, bytearray)):
        data = bytes(data)
        if data.startswith(BOM):
            # PowerShell puts one on a pipe. It is not part of the message and it
            # is not an error a person piping a file in could do anything about.
            data = data[len(BOM):]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise FrameError("not_utf8", "byte 0x%02x at offset %d is not UTF-8; this door reads "
                                         "UTF-8 and nothing else, whatever the machine's code "
                                         "page is" % (data[e.start], e.start))
    else:
        text = data
        try:
            text.encode("utf-8")
        except UnicodeEncodeError as e:
            raise FrameError("not_utf8", "the text carries a lone surrogate at offset %d: bytes "
                                         "that were not UTF-8, smuggled through a lenient "
                                         "decoder" % e.start)
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant,
                          parse_float=_float)
    except FrameError:
        raise
    except RecursionError:
        raise FrameError("not_json", "nested too deeply to be a message")
    except ValueError as e:
        raise FrameError("not_json", "not JSON: %s" % str(e)[:120])


def frames(stream, cap=FRAME_CAP):
    """Yield (message, None) or (None, FrameError) for every non-empty line.

    `stream` is a byte stream, or a text stream with a `.buffer` (sys.stdin), or
    -- for the suites, which hand these doors a StringIO -- a plain text stream.
    Reading is bounded: a line longer than `cap` is drained in small pieces and
    refused as one frame, so neither memory nor the rest of the session is what
    an oversized line costs."""
    src = getattr(stream, "buffer", stream)
    while True:
        line = src.readline(cap + 2)
        if not line:
            return
        nl = b"\n" if isinstance(line, (bytes, bytearray)) else "\n"
        if len(line) > cap and not line.endswith(nl):
            n = len(line)
            while True:
                more = src.readline(_DRAIN)
                n += len(more)
                if not more or more.endswith(nl):
                    break
            yield None, FrameError("too_large", "a frame of %d bytes is over this door's %d; it "
                                                "was read to its end and dropped, and the next "
                                                "frame is read as usual" % (n, cap))
            continue
        line = line.strip()
        if not line:
            continue
        if len(line) > cap:
            yield None, FrameError("too_large", "a frame of %d bytes is over this door's %d; it "
                                                "was dropped, and the next frame is read as "
                                                "usual" % (len(line), cap))
            continue
        try:
            yield loads(line), None
        except FrameError as e:
            yield None, e
