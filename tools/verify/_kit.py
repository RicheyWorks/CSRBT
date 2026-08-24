# -*- coding: utf-8 -*-
"""Shared helpers for the CSRBT verification suites.

The Field Entry Kit replaced the kit's bare <select>/<input> controls with
composed widgets that write through to hidden fields. That means a suite can no
longer drive a control with select_option() or fill() -- it has to do what a
finger does. These helpers do that, in one place, so a future FEK change is one
edit here rather than one per suite.
"""
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DOCS_DIR = os.path.join(ROOT, "docs") + os.sep
TOOLS_DIR = os.path.join(ROOT, "tools") + os.sep


def url(name):
    """file:// URL for a page in docs/, whatever the checkout is called."""
    return "file://" + os.path.join(ROOT, "docs", name).replace(os.sep, "/")


def offline(pg):
    """The container has no DNS; an un-aborted webfont request stalls load."""
    pg.route("**://fonts.googleapis.com/**", lambda r: r.abort())
    pg.route("**://fonts.gstatic.com/**", lambda r: r.abort())


def pick(pg, root, name):
    """Type into a FEK picker's filter and click the first match."""
    pg.evaluate("""([r,n])=>{const s=document.querySelector(r+' .search');
      if(!s) throw new Error('no picker search under '+r);
      s.value=n; s.dispatchEvent(new Event('input',{bubbles:true}));}""", [root, name])
    pg.wait_for_timeout(140)
    pg.evaluate("""(r)=>{const o=document.querySelector(r+' .opt');
      if(!o) throw new Error('no match under '+r); o.click();}""", root)
    pg.wait_for_timeout(160)


def setstep(pg, root, idx, val):
    """Set the nth FEK stepper under root, firing the input event readers expect."""
    pg.evaluate("""([r,i,v])=>{const s=[...document.querySelectorAll(r+' .fek-step .val')];
      if(!s[i]) throw new Error('no stepper '+i+' under '+r);
      s[i].value=String(v); s[i].dispatchEvent(new Event('input',{bubbles:true}));}""",
                [root, idx, val])
    pg.wait_for_timeout(130)


def hidden(pg, elid):
    """Read a hidden write-through field by id."""
    return pg.evaluate("(i)=>{const e=document.getElementById(i); return e?e.value:null;}", elid)


def options(pg, root):
    """Labels currently offered by a FEK picker."""
    return pg.evaluate("(r)=>[...document.querySelectorAll(r+' .opt')].map(o=>o.textContent.trim())", root)


def push(pg, elid, value):
    """Write a value into a FEK hidden write-through field exactly as the widget
    does -- set .value, then fire input AND change, because different readers on
    these pages listen for different ones.

    Driving the hidden field rather than the widget is a deliberate division of
    labour, not a shortcut: verify_cs proves the widget writes through to the
    field, so a suite about the science downstream of the field does not need to
    prove it a second time, and does not break when the widget is restyled.
    """
    pg.evaluate("""([i,v])=>{const e=document.getElementById(i);
      if(!e) throw new Error('no field #'+i);
      e.value=String(v);
      e.dispatchEvent(new Event('input',{bubbles:true}));
      e.dispatchEvent(new Event('change',{bubbles:true}));}""", [elid, value])
    pg.wait_for_timeout(120)
