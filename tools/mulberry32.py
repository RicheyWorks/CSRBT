# -*- coding: utf-8 -*-
"""mulberry32, the generator the kit's pages seed themselves with.

Two callers need to agree about it and neither may read the other's answer:
the determinism shim (`tools/harness.py`'s DETERMINISM) replaces a page's
`Math.random` with this generator so a run is reproducible, and an oracle
recomputes what the page must then print. This module is that oracle's half --
a port, not a wrapper, because a wrapper around the page's own JavaScript would
agree with it by construction and prove nothing.

It lived in a scratch file through ADR-129, which is how a port becomes two
ports that drift. It is a module now, with a suite.

    >>> r = Mulberry32(42)
    >>> round(r.random(), 6)
    0.001251
"""


class Mulberry32(object):
    """The generator, bit for bit as JavaScript computes it.

    JavaScript's operators are the whole specification here: `>>> 0` is an
    unsigned 32-bit truncation, `Math.imul` is a signed 32-bit multiply that
    wraps, and `^` and `>>>` are 32-bit. Python's integers are unbounded, so
    every step masks back to 32 bits explicitly -- an unmasked intermediate is
    the one way this port can be wrong while looking right.
    """

    M32 = 0xFFFFFFFF

    def __init__(self, seed):
        self.state = int(seed) & self.M32

    @classmethod
    def _imul(cls, a, b):
        """Math.imul: multiply as 32-bit signed, wrapping."""
        r = (a * b) & cls.M32
        return r

    def next_u32(self):
        self.state = (self.state + 0x6D2B79F5) & self.M32
        t = self.state
        t = self._imul(t ^ (t >> 15), t | 1) & self.M32
        t ^= (t + self._imul(t ^ (t >> 7), t | 61)) & self.M32
        t &= self.M32
        return (t ^ (t >> 14)) & self.M32

    def random(self):
        """The float in [0, 1) that Math.random() returns."""
        return self.next_u32() / 4294967296.0

    def take(self, n):
        return [self.random() for _ in range(n)]

    def int_below(self, n):
        """The page's usual idiom: Math.floor(Math.random() * n)."""
        return int(self.random() * n)


def stream(seed, n):
    """The first n values of the seeded stream, as a page would draw them."""
    return Mulberry32(seed).take(n)
