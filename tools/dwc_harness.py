# -*- coding: utf-8 -*-
"""Build the Darwin Core unit harness -- a bare page with DWC loaded and nothing else.

Generated from tools/dwc.py on every run, for the same reason the FEK harness is:
a suite that loads a copy from a scratch directory tests whatever version was
lying around when that copy was made.
"""
import io, os, sys, tempfile, importlib.util

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_spec = importlib.util.spec_from_file_location("dwc", os.path.join(ROOT, "tools", "dwc.py"))
dwc = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(dwc)

html = """<!doctype html><html><head><meta charset="utf-8"><title>dwc harness</title>
<style>:root{--tap:44px}body{font-family:system-ui,sans-serif;padding:16px}
""" + dwc.CSS + """</style></head><body>
<div id="coords"></div>
<script>""" + dwc.JS + """
window.CC = DWC.coordControls("coords", {});
</script></body></html>"""


def build(outdir=None):
    d = outdir or tempfile.mkdtemp(prefix="dwc_harness_")
    p = os.path.join(d, "dwc_harness.html")
    io.open(p, "w", encoding="utf-8").write(html)
    return p


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else None))
