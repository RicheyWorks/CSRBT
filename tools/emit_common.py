# -*- coding: utf-8 -*-
"""One rule the regenerators all got wrong the same way.

Every emitter in this kit finds its generated block, replaces it, and stops. On
a page carrying the block TWICE that is not a rewrite, it is a rewrite of the
first half; and `--check` then reports the tree clean, because the copy it looked
at was correct.

That is not hypothetical either. `survey-design.html` carried the Keep
stylesheet four times, and `keep_emit.py --check` said "0 consumers would
change" for as long as anyone had been running it. Four identical copies render
identically -- which is why it survived a contrast audit, a print audit and an
offline audit unnoticed. They stop being identical the first time keep.CSS
changes: copy one is updated, copies two to four are not, and the LAST rule wins
in CSS. The page renders the stale stylesheet and every regenerator reports
success. The failure this whole layer exists to prevent, arriving through the
layer itself.

Found by reading a published artifact, not by any tool. It is a tool now.
"""


def dedupe(src, opener, span_fn):
    """Leave exactly one copy of a generated block; return (src, removed).

    `opener` is a compiled regex matching the START of one block; `span_fn` is
    the emitter's own span finder, taking (src, from_) and returning (a, b) or
    None. Extras are removed from the END, so the survivor is the first one --
    the copy every emitter's rewrite already targets, so nothing else has to
    change.

    A span it cannot resolve stops the loop rather than guessing: leaving a
    duplicate that --check will report beats deleting bytes on a hunch.
    """
    removed = 0
    while len(opener.findall(src)) > 1:
        last = [m.start() for m in opener.finditer(src)][-1]
        span = span_fn(src, last)
        if not span:
            break
        # Exactly ONE newline, not lstrip. A span runs from the start of its
        # banner line to the end of its last rule, so the newline that ends
        # that rule is the block's; anything past it is the blank line the
        # author put there, and eating it makes the removal one byte short of
        # reversible -- which is how the canary in verify_emitters failed on
        # correct work.
        rest = src[span[1]:]
        if rest.startswith("\n"):
            rest = rest[1:]
        src = src[:span[0]] + rest
        removed += 1
    return src, removed
