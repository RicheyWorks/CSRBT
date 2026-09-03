# -*- coding: utf-8 -*-
"""The csrbt-session plugin: the session's own control surface (ADR-137).

Every other plugin in this harness fronts a TARGET -- a JVM, a browser page,
a fixture. This one fronts the SESSION: it is how a host asks for a target it
did not start with, and how it gives one back.

    targets   READ      which targets can be attached, and which are attached
    attach    NAVIGATE  stand a target up and put it in this session's registry
    detach    NAVIGATE  take a target out of the registry and close it

Why it exists. ADR-115 declared `listChanged: false` on both transports and
ADR-121 held it there, for the honest reason that nothing could change a
list: a registry was built once and only read. That made the capability true
and useless at the same time. This plugin is the thing that can change it --
and the notification is not decoration, because a client that CACHES the tool
list (the robot's McpWire keeps a (pluginId, action) -> tool name map, and the
MCP server keeps its own) is wrong the moment a target arrives, and has no
way to know unless it is told.

What it does NOT do. It cannot attach a target twice, it cannot attach
itself, and it cannot detach a target it did not attach -- the targets a
session was started with are the operator's, not the host's. Standing a
target up is NAVIGATE, not MUTATE: attaching changes nothing about any record
in any target; it changes what this session can reach. Detaching runs the
target's own closers, so a browser attached and detached leaves no process.

It is registered only when a transport is asked for it (`--attachable`), and
a transport that does not register it says `listChanged: false` and means it.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from harness_contract import (ActionSpec, ArgumentSpec, Conflict, Failed,
                              InvalidArgument, NotFound, Plugin, PluginDescriptor)
import harness_targets as TG

# The targets a host may ask for by name. "both" and "all" are the operator's
# command-line words for a set; a host attaches one target at a time, so they
# are not offered here.
ATTACHABLE = ("page", "organism", "lab", "fixture")


class SessionPlugin(Plugin):
    ID = "csrbt-session"

    def __init__(self, registry, page="ecology.html", seed=42, headed=False, stand_up=None):
        self.registry = registry
        self.page, self.seed, self.headed = page, seed, headed
        self._stand_up = stand_up or TG.stand_up
        # target -> (plugin ids it registered, closers to run on detach). Only
        # what THIS plugin attached; the session's own targets are not in here
        # and cannot be detached.
        self.attached = {}

    # -- contract -----------------------------------------------------------
    def descriptor(self):
        return PluginDescriptor(
            id=self.ID, title="the session itself",
            description="Attach and detach targets while the session is open. "
                        "Attaching or detaching changes which tools this session lists, "
                        "and the transport says so.",
            version="1.0",
            actions=[
                ActionSpec("targets", "Which targets can be attached, and which are attached now.",
                           "READ"),
                ActionSpec("attach", "Stand a target up and add it to this session. Its tools and "
                                     "its snapshot resource appear; the tool list has changed.",
                           "NAVIGATE",
                           [ArgumentSpec("target", "string", "The target to attach.",
                                         required=True, enum=list(ATTACHABLE),
                                         examples=["fixture", "page"]),
                            ArgumentSpec("page", "string", "For target=page: the kit page to open.",
                                         required=False, examples=["collection-sheet.html"])]),
                ActionSpec("detach", "Close a target this session attached and take it out. Its "
                                     "tools and its snapshot resource go away.",
                           "NAVIGATE",
                           [ArgumentSpec("target", "string", "The target to detach.",
                                         required=True, enum=list(ATTACHABLE),
                                         examples=["fixture"])]),
            ])

    def observe(self, sensitive=False):
        live = sorted(d.id for d in self.registry.descriptors())
        return {"ready": True, "target": "session",
                "attachable": list(ATTACHABLE),
                "attached": sorted(self.attached),
                "plugins": live, "pluginCount": len(live),
                # what a host would have to re-read after a change, named so a
                # trace can show it did
                "lists": {"tools": "tools/list", "resources": "resources/list"}}

    def execute(self, action, arguments):
        if action == "targets":
            live = sorted(d.id for d in self.registry.descriptors())
            return True, "%d attachable, %d attached" % (len(ATTACHABLE), len(self.attached)), {
                "attachable": list(ATTACHABLE),
                "attached": sorted(self.attached),
                "plugins": live,
                "detachable": sorted(self.attached)}
        if action == "attach":
            return self._attach(arguments)
        if action == "detach":
            return self._detach(arguments)
        raise NotFound("csrbt-session has no action %r" % action)

    # -- the two that change the list ---------------------------------------
    def _attach(self, arguments):
        target = arguments.get("target")
        if target not in ATTACHABLE:
            raise InvalidArgument("target must be one of %s" % ", ".join(ATTACHABLE))
        if target in self.attached:
            raise Conflict("%s is already attached to this session" % target)
        # A target the session was STARTED with is not this plugin's to manage.
        # Standing a second one up would collide on the plugin id anyway; saying
        # so as a conflict is better than letting register() say it.
        live = set(d.id for d in self.registry.descriptors())
        page = arguments.get("page") or self.page
        try:
            plugins, closers = self._stand_up(target, page=page, seed=self.seed,
                                              headed=self.headed, err=_Sink())
        except SystemExit as e:
            raise Failed("%s could not be stood up (exit %s)" % (target, e.code))
        except Exception as e:
            raise Failed("%s could not be stood up: %s" % (target, str(e)[:160]))
        ids = [p.descriptor().id for p in plugins]
        clash = [i for i in ids if i in live]
        if clash:
            TG.tear_down(closers)
            raise Conflict("this session already serves %s" % ", ".join(clash))
        added = []
        try:
            for p in plugins:
                self.registry.register(p)          # one announcement per plugin
                added.append(p.descriptor().id)
        except Exception:
            for i in reversed(added):
                try:
                    self.registry.retire(i)
                except Exception:
                    pass
            TG.tear_down(closers)
            raise
        self.attached[target] = (ids, closers)
        return True, "%s attached; %d tool list(s) changed" % (target, len(ids)), {
            "target": target, "plugins": ids, "attached": sorted(self.attached),
            "reread": ["tools/list", "resources/list"]}

    def _detach(self, arguments):
        target = arguments.get("target")
        if target not in ATTACHABLE:
            raise InvalidArgument("target must be one of %s" % ", ".join(ATTACHABLE))
        if target not in self.attached:
            raise NotFound("%s was not attached by this session (attached: %s)"
                           % (target, ", ".join(sorted(self.attached)) or "none"))
        ids, closers = self.attached.pop(target)
        gone = []
        for i in ids:
            try:
                self.registry.retire(i)
                gone.append(i)
            except NotFound:
                pass
        TG.tear_down(closers)
        return True, "%s detached; %d plugin(s) gone" % (target, len(gone)), {
            "target": target, "plugins": gone, "attached": sorted(self.attached),
            "reread": ["tools/list", "resources/list"]}

    def close(self):
        """Detach everything this plugin attached, in reverse order."""
        for target in list(self.attached)[::-1]:
            try:
                self._detach({"target": target})
            except Exception:
                pass


class _Sink(object):
    """stand_up writes the reason a target could not come up to `err`; here that
    reason belongs in the refusal, not on the transport's stderr."""

    def __init__(self):
        self.text = ""

    def write(self, s):
        self.text += s
