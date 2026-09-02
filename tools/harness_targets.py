# -*- coding: utf-8 -*-
"""Standing up what a transport fronts (ADR-115).

Two transports now serve the same gateway -- stdio (ADR-102) and MCP (ADR-115)
-- and both need the same thing before they can serve anything: a policy that
is switched on, a token long enough, and a registry holding the targets the
operator named. That is not transport work, so it lives here once. A transport
maps four operations and decides nothing; this file decides what stands
behind them, and it is the only place that knows a target's name.

    policy = require_policy()            # None, and a line on stderr, if off
    plugins, closers = stand_up("organism", seed=42)   # or "lab", "page", "both", "all"
    gateway = Gateway(Registry(plugins), policy)
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "verify"))
from harness_contract import HarnessError, Policy, TOKEN_MIN

TARGETS = ("page", "organism", "lab", "both", "all", "fixture")
WANTS = {"page": ("page",), "organism": ("organism",), "lab": ("lab",),
         "both": ("organism", "page"), "all": ("organism", "lab", "page"),
         "fixture": ("fixture",)}       # ADR-119: the robot's own test target; never in "all"


def require_policy(err=None):
    """The policy from the environment, or None with the reason written."""
    err = err or sys.stderr
    policy = Policy()
    if not policy.enabled:
        err.write("harness is off. Set CSRBT_HARNESS_ENABLED=true to enable it for "
                  "this supervised session.\n")
        return None
    if not policy.token or len(policy.token) < TOKEN_MIN:
        err.write("CSRBT_HARNESS_TOKEN must be at least %d characters.\n" % TOKEN_MIN)
        return None
    return policy


def stand_up(target, page="ecology.html", seed=42, headed=False, err=None):
    """The plugins for a target, and the closers to run when the transport
    ends (in order). Raises SystemExit(2) with the reason on stderr when a
    target cannot come up, because a transport that serves a half-built
    registry is answering for something that is not there."""
    err = err or sys.stderr
    if target not in TARGETS:
        raise ValueError("target must be one of %s" % ", ".join(TARGETS))
    plugins, closers = [], []
    wants = WANTS[target]
    if "organism" in wants:
        from harness_plugin_organism import OrganismPlugin
        org = OrganismPlugin(seed=seed)
        try:
            org.observe()          # stand it up now, so a missing build fails here
        except HarnessError as e:
            err.write(e.message + "\n")
            raise SystemExit(2)
        if not org.console or not org.console.alive():
            err.write("organism did not come up\n")
            raise SystemExit(2)
        plugins.append(org)
        closers.append(org.close)
    if "fixture" in wants:
        from harness_plugin_fixture import FixturePlugin
        plugins.append(FixturePlugin())
    if "lab" in wants:
        from harness_plugin_lab import LabPlugin
        lab = LabPlugin()
        try:
            lab.observe()
        except HarnessError as e:
            err.write(e.message + "\n")
            raise SystemExit(2)
        if not lab.console or not lab.console.alive():
            err.write("lab console did not come up\n")
            raise SystemExit(2)
        plugins.append(lab)
        closers.append(lab.close)
    if "page" in wants:
        import _kit
        import harness as H
        from playwright.sync_api import sync_playwright
        from harness_plugin_page import PagePlugin
        pw = sync_playwright().start()
        b = pw.chromium.launch(headless=not headed)
        ctx = b.new_context(viewport=H.VIEWPORT)
        ctx.set_offline(True)
        ctx.add_init_script(H.STUBS)
        try:
            from swarm import CATCH
            ctx.add_init_script(CATCH)
        except Exception:
            pass
        pg = ctx.new_page()
        pg.goto(_kit.url(page), wait_until="domcontentloaded")
        pg.wait_for_timeout(300)
        # The swarm's widened kinds (ADR-101: checkboxes, drop zones, every text
        # input type) are the discovery a client should get; the harness's own
        # list is the published ledger's and stays narrower on purpose.
        try:
            from swarm import SWARM_KINDS
        except Exception:
            SWARM_KINDS = None
        plugins.append(PagePlugin(pg, page, kinds=SWARM_KINDS))
        closers.append(ctx.close)
        closers.append(b.close)
        closers.append(pw.stop)
    return plugins, closers


def tear_down(closers):
    for c in closers:
        try:
            c()
        except Exception:
            pass
