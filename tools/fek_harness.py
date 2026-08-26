# -*- coding: utf-8 -*-
"""Build the FEK unit harness -- a bare page carrying one of every control.

verify_fek.py used to load a copy of this from /tmp, so the FEK unit suite tested
whatever version happened to be lying around in the container that last built it.
On a fresh clone it would not have loaded at all, and in this container it went
on asserting 1.1.0 after the component had moved to 1.2.0. Generated fresh from
tools/fek.py on every run instead.
"""
import io, os, sys, tempfile, importlib.util

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_spec = importlib.util.spec_from_file_location("fek", os.path.join(ROOT, "tools", "fek.py"))
fek = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(fek)
html = """<!doctype html><html><head><meta charset="utf-8"><style>
:root{--page:#F5F1E6;--surface:#FFFDF7;--surface-2:#F3EEE0;--ink:#23281F;--ink-2:#4B5344;
--muted:#8B8B7B;--border:#E3DCC9;--s1:#2E7D4F;--s1-deep:#236240;--soft:#E9F0E7;--warn-bg:#F6EAD8;
--danger:#B23A32;--danger-bg:#F6E7E5;--head:Georgia,serif;--body:system-ui,sans-serif;--mono:monospace;}
body{font-family:var(--body);background:var(--page);padding:20px;max-width:520px;margin:0 auto}
""" + fek.CSS + """</style></head><body>
<div id="h1"></div><div id="h2"></div><div id="h3"></div><div id="h4"></div><div id="h5"></div>
<div id="h6"></div><div id="h7"></div><div id="h8"></div>
<script>""" + fek.JS + """
window.LOG=[];
window.A=FEK.step({label:"nullable stepper",unit:"cm",nullable:true,min:0,max:50,step:0.5,dec:1,start:5,
  onchange:function(v){LOG.push(["A",v]);}});
window.B=FEK.step({label:"plain stepper",unit:"m",value:10,min:0,max:100,step:1,dec:0,
  onchange:function(v){LOG.push(["B",v]);}});
window.C=FEK.field({label:"absorbance",unit:"AU",dec:3,step:0.001,min:0,max:4,
  onchange:function(v){LOG.push(["C",v]);}});
window.D=FEK.slider({label:"nullable slider",unit:"%",nullable:true,min:0,max:100,step:5,
  onchange:function(v){LOG.push(["D",v]);}});
window.E=FEK.step({label:"nullable but zeroed",nullable:true,value:0,min:0,max:10,step:1,dec:0,
  onchange:function(v){LOG.push(["E",v]);}});
/* The field registry had NO fixture at all, so nothing in the suite ever
   touched it -- a mutation sweep found reg() and setField() both untested,
   and they are what KEEP's restore path depends on to put a saved value back
   THROUGH the widget rather than only into a hidden input. */
window.G=FEK.step({label:"registered stepper",field:"sElev",unit:"m",value:0,min:-100,max:9000,
  step:10,dec:0,onchange:function(v){LOG.push(["G",v]);}});
window.H=FEK.dial({label:"registered dial",field:"sCover",clearable:true,
  options:[{value:"a",label:"none"},{value:"b",label:"some"},{value:"c",label:"lots"}],
  onchange:function(v){LOG.push(["H",v]);}});
/* Five options, no explicit ramp: the default index is
   min(5, round(i*5/(n-1))) and the off-by-one in that denominator is exactly
   what a mutation exposed. */
window.I=FEK.dial({label:"ramped dial",clearable:false,
  options:[{value:"1",label:"one"},{value:"2",label:"two"},{value:"3",label:"three"},
           {value:"4",label:"four"},{value:"5",label:"five"}]});
FEK.mount("h1",[A]); FEK.mount("h2",[B]); FEK.mount("h3",[C]); FEK.mount("h4",[D]); FEK.mount("h5",[E]);
FEK.mount("h6",[G]); FEK.mount("h7",[H]); FEK.mount("h8",[I]);
</script></body></html>"""


def build(outdir=None):
    """Write the harness somewhere temporary and return its path."""
    d = outdir or tempfile.mkdtemp(prefix="fek_harness_")
    p = os.path.join(d, "fek_harness.html")
    io.open(p, "w", encoding="utf-8").write(html)
    return p


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else None))
