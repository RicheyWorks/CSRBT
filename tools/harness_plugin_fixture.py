# -*- coding: utf-8 -*-
"""The csrbt-fixture plugin: a target built to be walked, so the robot can be
broken on purpose (ADR-119).

tools/harness_walk.py is the instrument every "operable from the manifest"
claim rests on, and until this file nobody had broken it to see whether its
suite noticed. Breaking it against the organism is slow (a JVM per walk)
and partly random (which arguments a seed forms). This target is neither:
every action lands in a KNOWN bucket, every time, so a mutant that misfiles
one shows up as a wrong count, deterministically, in a walk that takes
under two seconds.

    ok           READ        always ok                                -> driven
    refuse       READ        always invalid_argument                  -> refused
    decline      NAVIGATE    always ok:false with no code             -> declined
    crash        MUTATE      raises, message names a Crash; the
                             snapshot says a plan is armed             -> chaos
    boom         MUTATE      raises, no Crash in the message           -> failed
    pooled       DRAFT       accepts only the slot the LATEST snapshot
                             publishes in "pooled.slot", and rotates it
                             on every call -- a robot that does not read
                             each response's pools is refused           -> driven
    empty-pool   DRAFT       its scoped pool is published empty, always,
                             and it refuses whatever it is handed          -> unreachable
    reached      DRAFT       its scoped pool is ALSO published empty, but
                             the schema's example gets through -- so it is
                             driven, and must not be called unreachable      -> driven
    unformable   READ        a string with no enum and no examples      -> unschemable
    array        DRAFT       records the lengths it was handed, so the
                             suite can see that one came first           -> driven
    broken       MUTATE      flips the snapshot's `consistent` flag, so
                             the fixture's cross-check reports a break
    die          DESTRUCTIVE (only with CSRBT_FIXTURE_DIE=1) the target
                             goes away: observe says not ready, every
                             execute is unavailable

It is served only by `--target fixture`; no production manifest lists it.
It holds no data and touches no disk.
"""
import os

from harness_contract import (ActionSpec, ArgumentSpec, Plugin, PluginDescriptor,
                              InvalidArgument, Unavailable)


class FixturePlugin(Plugin):
    ID = "csrbt-fixture"
    SLOTS = ["s0", "s1", "s2"]

    def __init__(self, can_die=None):
        self.calls = {}
        self.slot = 0
        self.consistent = True
        self.dead = False
        self.array_lengths = []
        can_die = (os.environ.get("CSRBT_FIXTURE_DIE") == "1") if can_die is None else can_die
        actions = [
            ActionSpec("ok", "Always succeeds.", "READ", []),
            ActionSpec("refuse", "Always refuses with invalid_argument, whatever n is.", "READ",
                       [ArgumentSpec("n", "integer", "Any small integer.", required=True,
                                     minimum=0, maximum=9)]),
            ActionSpec("decline", "Always answers no, with no code.", "NAVIGATE", []),
            ActionSpec("crash", "Always raises; the message names a Crash and the snapshot "
                                "says a plan is armed.", "MUTATE", []),
            ActionSpec("boom", "Always raises, with no Crash in the message.", "MUTATE", []),
            ActionSpec("pooled", "Accepts only the slot the latest snapshot's pool names; "
                                 "the slot rotates on every call.", "DRAFT",
                       [ArgumentSpec("slot", "string", "A slot name.", required=True,
                                     examples=["never-valid"])]),
            ActionSpec("empty-pool", "Its scoped pool is always empty.", "DRAFT",
                       [ArgumentSpec("thing", "string", "Anything.", required=True,
                                     examples=["z"])]),
            ActionSpec("reached", "Its scoped pool is empty too, but its example is accepted.", "DRAFT",
                       [ArgumentSpec("thing", "string", "Anything.", required=True,
                                     examples=["z"])]),
            ActionSpec("unformable", "Takes a string the manifest gives no way to form.", "READ",
                       [ArgumentSpec("text", "string", "Free text, no examples.", required=True)]),
            ActionSpec("array", "Records the lengths of the arrays it is handed.", "DRAFT",
                       [ArgumentSpec("items", "array", "Some items.", required=True,
                                     items="string", examples=["p", "q", "r"])]),
            ActionSpec("broken", "Flips the snapshot's consistent flag.", "MUTATE", []),
        ]
        if can_die:
            actions.append(ActionSpec("die", "The target goes away.", "DESTRUCTIVE", []))
        self._desc = PluginDescriptor(
            self.ID, "CSRBT fixture",
            "A target built to be walked: every action lands in a known bucket, so the "
            "robot can be broken on purpose and its suite required to notice.",
            "1.0", actions)

    def descriptor(self):
        return self._desc

    def observe(self, sensitive=False):
        if self.dead:
            return {"ready": False, "why": "the fixture died, as asked"}
        return {"ready": True, "target": "fixture", "sensitive": bool(sensitive),
                "chaos": "armed", "consistent": self.consistent,
                "calls": dict(self.calls), "arrayLengths": list(self.array_lengths),
                "argumentPools": {"pooled.slot": [self.SLOTS[self.slot]],
                                  "empty-pool.thing": [], "reached.thing": []}}

    def execute(self, action, args):
        if self.dead:
            raise Unavailable("the fixture died, as asked")
        self.calls[action] = self.calls.get(action, 0) + 1
        if action == "ok":
            return True, "ok", {}
        if action == "refuse":
            raise InvalidArgument("refused, as always (n=%s)" % args.get("n"))
        if action == "decline":
            return False, "no", {}
        if action == "crash":
            raise RuntimeError("Crash: the fixture's armed plan fired")
        if action == "boom":
            raise RuntimeError("boom: no plan, just a raise")
        if action == "pooled":
            want = self.SLOTS[self.slot]
            self.slot = (self.slot + 1) % len(self.SLOTS)
            if args.get("slot") != want:
                raise InvalidArgument("slot %r is not the current slot %r" % (args.get("slot"), want))
            return True, "slot %s" % want, {"slot": want}
        if action == "empty-pool":
            raise InvalidArgument("nothing to act on: the pool is empty, whatever %r is" % args.get("thing"))
        if action == "reached":
            return True, "reached with %r" % args.get("thing"), {}
        if action == "unformable":
            return True, "formed, somehow", {}
        if action == "array":
            self.array_lengths.append(len(args.get("items") or []))
            return True, "%d item(s)" % len(args.get("items") or []), {}
        if action == "broken":
            self.consistent = False
            return True, "broke it", {}
        if action == "die":
            self.dead = True
            return True, "dying", {}
        raise InvalidArgument("unknown action %r" % action)
