# -*- coding: utf-8 -*-
"""Best-effort local persistence for the field pages, and honesty about it.

Before this existed, one page in the kit saved anything: Pheno Tracker, with a
`try{ localStorage.setItem(...) }catch(e){}` that swallowed every failure. A
full quota, a private window, or storage disabled by policy all produced the
same result -- nothing saved, nothing said. A user who had watched the page
work for an hour had every reason to believe their data was safe. That is the
exact failure this kit was built to refuse, sitting inside the kit.

So KEEP does three things that a bare setItem does not:

  1. It probes storage at wire time and says up front when this browser is not
     keeping anything, rather than at the moment of loss.
  2. It surfaces a failed write instead of swallowing it.
  3. It states, in the page, what browser storage is: one browser on one
     device, gone when site data is cleared. It is recovery from a closed tab.
     It is NOT a backup, and the page says so where the user can read it rather
     than in a comment.

The durable path stays what it always was -- the exports. KEEP is what stops
you losing a morning's work to a phone call.

    python3 tools/keep_emit.py           # rewrite every consumer
    python3 tools/keep_emit.py --check   # report drift, write nothing
"""
VERSION = "1.4.0"

CSS = """
  /* ============ Keep (local autosave) v%s ============ */
  .keep { display:flex; flex-wrap:wrap; align-items:center; gap:10px;
    background:var(--surface-2, #F3EEE0); border:1px solid var(--border, #E3DCC9);
    border-radius:12px; padding:10px 13px; margin:12px 0 2px; }
  .keep .st { font-family:var(--mono, monospace); font-size:11.5px; color:var(--muted, #6B6B5E);
    line-height:1.5; flex:1 1 220px; min-width:0; }
  .keep .st b { color:var(--ink, #23281F); }
  .keep.bad { border-color:var(--danger, #B23A32); background:var(--danger-bg, #F6E7E5); }
  .keep.bad .st b { color:var(--danger, #B23A32); }
  .keep button { border:1.5px solid var(--border, #E3DCC9); background:none; border-radius:10px;
    padding:0 14px; min-height:var(--tap, 44px); font:700 13px var(--body, sans-serif);
    color:var(--ink-2, #4B5344); cursor:pointer; touch-action:manipulation; }
  .keep button:hover { border-color:var(--danger, #B23A32); color:var(--danger, #B23A32); }
  .keep .note { flex:1 1 100%%; font-size:12px; color:var(--muted, #6B6B5E); line-height:1.5; }
  @media print { .keep { display:none !important; } }
""" % VERSION

JS = """
/* ---- Keep v%s : local autosave, and honesty about what that is ---- */
var KEEP = (function(){
  /* The handle the last wire() returned, so a reader outside the page's closure
     can ask the page what it is holding (v1.3.0, ADR-209). */
  var LIVE = null;
  function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g,function(c){
    return c==="&"?"&amp;":c==="<"?"&lt;":c===">"?"&gt;":c==='"'?"&quot;":"&#39;"; }); }

  /* Probe rather than assume. Safari in private mode used to throw on the
     first write; storage can also be disabled by enterprise policy or by the
     user, and in a sandboxed frame the accessor itself throws. All three look
     identical to a page that only wraps setItem in a try. */
  function usable(){
    try {
      var k = "__keep_probe__";
      window.localStorage.setItem(k, "1");
      window.localStorage.removeItem(k);
      return true;
    } catch(e){ return false; }
  }

  function when(ts){
    if(!ts) return "";
    try {
      var d = new Date(ts), now = new Date();
      var same = d.toDateString() === now.toDateString();
      var hm = ("0"+d.getHours()).slice(-2) + ":" + ("0"+d.getMinutes()).slice(-2);
      return same ? ("today " + hm) : (d.toISOString().slice(0,10) + " " + hm);
    } catch(e){ return ""; }
  }

  function wire(o){
    o = o || {};
    var key = o.key, host = typeof o.mount === "string" ? document.getElementById(o.mount) : o.mount;
    var fmt = o.format == null ? 1 : o.format;
    var ok = usable(), lastErr = null, savedAt = null, restoredFrom = null, timer = null;
    var noun = o.noun || "your work";

    function read(){
      if(!ok) return null;
      try {
        var raw = window.localStorage.getItem(key);
        if(!raw) return null;
        var p = JSON.parse(raw);
        /* A format stamp, so a page that changes its state shape does not
           restore a shape it can no longer read and fail in a way the user
           reads as data loss. */
        if(!p || p.format !== fmt) return null;
        return p;
      } catch(e){ return null; }
    }

    function write(){
      timer = null;
      if(!ok) return;
      var body;
      try { body = o.snapshot(); } catch(e){ lastErr = "could not read the page state"; paint(); return; }
      if(body == null){
        try { window.localStorage.removeItem(key); }catch(e){}
        savedAt = null; lastErr = null; paint(); return;
      }
      try {
        window.localStorage.setItem(key, JSON.stringify({ format:fmt, at:Date.now(), body:body }));
        savedAt = Date.now(); lastErr = null;
      } catch(e){
        /* Do not swallow this. A quota failure that says nothing is worse than
           no autosave at all, because it teaches the user to trust it. */
        lastErr = (e && e.name === "QuotaExceededError")
          ? "this browser's storage is full" : "this browser refused the write";
      }
      paint();
    }

    function touch(){
      if(!ok) return;
      if(timer) clearTimeout(timer);
      timer = setTimeout(write, o.debounce == null ? 500 : o.debounce);
    }

    function flush(){ if(timer){ clearTimeout(timer); } write(); }

    function forget(){
      /* Cancel the pending write first. Without this the debounced save from
         the edit that preceded the click -- or from the click itself, on a
         page that listens for clicks -- lands a few hundred milliseconds later
         and puts the copy straight back, which makes the button look like it
         did nothing. */
      if(timer){ clearTimeout(timer); timer = null; }
      try { window.localStorage.removeItem(key); }catch(e){}
      savedAt = null; restoredFrom = null; lastErr = null; paint();
      if(o.onforget) o.onforget();
    }

    function paint(){
      if(!host) return;
      /* noprint: this is screen chrome -- a status line about a browser and a
         button -- and the print audit is right to count anything else that
         vanishes on paper as content lost. */
      host.className = "keep noprint" + ((!ok || lastErr) ? " bad" : "");
      var msg;
      if(!ok){
        msg = "<b>This browser is not keeping anything.</b> Storage is unavailable here &mdash; a "
            + "private window, or site data switched off. Nothing is being saved, so export before "
            + "you close the tab.";
      } else if(lastErr){
        msg = "<b>Autosave failed &mdash; " + esc(lastErr) + ".</b> What is on screen is not saved. "
            + "Export it now.";
      } else if(savedAt){
        msg = "Saved on this device <b>" + esc(when(savedAt)) + "</b>"
            + (restoredFrom ? " &middot; restored from " + esc(when(restoredFrom)) : "") + ".";
      } else if(restoredFrom){
        msg = "Restored " + esc(noun) + " from <b>" + esc(when(restoredFrom)) + "</b> on this device.";
      } else {
        msg = "Autosave is on. " + esc(noun.charAt(0).toUpperCase() + noun.slice(1))
            + " will still be here if you close the tab.";
      }
      /* THE BUTTON IS BUILT ONCE (v1.2.0, ADR-207).
         This wrote the whole strip with innerHTML on every repaint, so the
         forget button was DESTROYED AND RE-CREATED whenever the autosave
         changed state -- and the autosave changes state on every save. A
         control that does not survive a repaint cannot be stamped, addressed
         or kept in focus across one: audit_focus reported it as "mounted after
         the last stamp and could not be measured", intermittently, on whichever
         page happened to save while the sweep was looking. Only the words
         change now. */
      if(!host.firstChild){
        var st = document.createElement("p"); st.className = "st";
        var btn = document.createElement("button");
        btn.type = "button"; btn.setAttribute("data-keep-forget", "");
        btn.textContent = "Forget this device's copy";
        btn.addEventListener("click", function(){
          forget();
          if(o.ontoast) o.ontoast("Saved copy removed from this device");
        });
        var note = document.createElement("p"); note.className = "note";
        note.innerHTML = '<b>This is not a backup.</b> It is one browser on one device, and it goes '
          + 'when site data is cleared, in a private window, or on any other machine. It exists so a '
          + 'phone call does not cost you a morning. The exports are the durable copy.';
        host.appendChild(st); host.appendChild(btn); host.appendChild(note);
      }
      host.firstChild.innerHTML = msg;
    }

    var got = read();
    if(got){
      var accepted = false;
      try { accepted = o.restore(got.body) !== false; } catch(e){ accepted = false; }
      if(accepted){ restoredFrom = got.at; }
    }
    paint();
    /* A PHOTOGRAPH IS AN EDIT (v1.1.0, ADR-206). FEK.photos fires `fek-change`
       when frames are added, removed or captioned; nothing else does, because
       a hidden file input and a drop produce neither `input` nor `change`. A
       page that had to remember to wire this is a page that would forget. */
    try {
      document.addEventListener("fek-change", function(){ touch(); }, true);
    } catch(e){}
    /* A tab closing mid-debounce is exactly the case this exists for. */
    try {
      window.addEventListener("pagehide", function(){ if(timer) flush(); });
      document.addEventListener("visibilitychange", function(){
        if(document.visibilityState === "hidden" && timer) flush(); });
    } catch(e){}

    var h = { touch:touch, flush:flush, forget:forget, usable:function(){ return ok; },
             restored:function(){ return restoredFrom; }, savedAt:function(){ return savedAt; },
             error:function(){ return lastErr; },
             /* v1.1.0 (ADR-203). The page already describes its own state once,
                here, for the autosave. The outbox needs the same description to
                say whether it has left the device -- and a SECOND description
                would be a second thing to keep in step, so the one that is
                already exercised by every restore is the one it gets. Read
                through this handle rather than by the page passing its snapshot
                twice, because two references can be wired to two functions and
                only one of them would ever be tested. */
             snapshot:function(){ return o.snapshot(); } };
    /* v1.3.0 (ADR-209). The live handle, reachable from outside the page's own
       closure. A page wires KEEP inside an IIFE and keeps the handle in a local,
       so the description of its state that the autosave and the outbox both
       already read was reachable from nowhere else -- and an audit asking "how
       much did that tap take" had to count rows on the screen instead. Rows on
       the screen are not records: a plate shown once in a list and once in a
       results table is one record counted twice, and a rule built on that cries
       wolf on a row remover while under-reading a delete that cascades.
       One description, read by everything that needs it (ADR-141). */
    LIVE = h;
    return h;
  }

  /* ---- generic form capture ----
     Every page in the kit keeps its typed state in elements with ids -- real
     inputs for text and dates, hidden write-through fields for the FEK
     widgets. Capturing them by walking the DOM means a page that gains a field
     does not also have to remember to add it to a list, which is how a
     hand-maintained list of fields quietly stops covering the newest one. */
  function formSnapshot(){
    var out = {}, i, els = document.querySelectorAll("input[id], textarea[id]");
    for(i=0;i<els.length;i++){
      var e = els[i];
      if(e.type === "file" || e.type === "button" || e.type === "submit") continue;
      out[e.id] = (e.type === "checkbox" || e.type === "radio") ? (e.checked ? "1" : "") : e.value;
    }
    /* v1.4.0 (ADR-210). ...AND EVERY FEK CONTROL THAT DECLARES A FIELD BUT HAS
       NO ELEMENT BEHIND IT. Walking the DOM finds a page's typed state only
       where the page also remembered to write it into a hidden input; a
       component that declared `field:"selN"` and nothing else was invisible
       here, and its value came back as the widget's default over correct data.
       Only the ones the DOM walk did not already find, so every page that has
       been keeping its state through hidden inputs keeps writing exactly the
       blob it wrote yesterday. */
    try {
      if (typeof FEK !== "undefined" && FEK && typeof FEK.values === "function") {
        var fv = FEK.values(), fk;
        for (fk in fv) if (fv.hasOwnProperty(fk) && !out.hasOwnProperty(fk)
                           && fv[fk] != null && fv[fk] !== "") out[fk] = fv[fk];
      }
    } catch (e) { }
    return out;
  }
  /* Restoring the hidden field is only half the job: the widget above it still
     shows its construction default, and a correct value under a wrong-looking
     dial is worse than no restore at all. FEK.setField (v1.3.0) puts the value
     back through the widget for every component that declared its field. */
  function formRestore(map){
    if(!map) return 0;
    var n = 0, id;
    for(id in map){
      if(!map.hasOwnProperty(id)) continue;
      var e = document.getElementById(id);
      if(!e){
        /* v1.4.0: a field with no element behind it is a FEK control that
           declared one; put the value back through the widget's own set(). */
        if(typeof FEK !== "undefined" && FEK.setField && FEK.setField(id, map[id])) n++;
        continue;
      }
      if(e.type === "checkbox" || e.type === "radio") e.checked = !!map[id];
      else e.value = map[id];
      if(typeof FEK !== "undefined" && FEK.setField){
        var v = map[id];
        if(e.type === "number" || /^-?\d+(\.\d+)?$/.test(String(v))) {
          FEK.setField(id, v === "" ? null : parseFloat(v));
        } else {
          FEK.setField(id, v === "" ? null : v);
        }
      }
      n++;
    }
    return n;
  }

  return { version:"%s", wire:wire, usable:usable, live:function(){ return LIVE; },
           formSnapshot:formSnapshot, formRestore:formRestore };
})();
""" % (VERSION, VERSION)
