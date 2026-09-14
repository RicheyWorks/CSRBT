# -*- coding: utf-8 -*-
"""Field Entry Kit v1 — the shared large/colourful data-entry layer.

Single source of truth. Emitted inline into every page that uses it, because
every page in this kit must stay one self-contained file (artifact CSP, offline
in the field, printable). Bump VERSION on any change and re-emit consumers.
"""
VERSION = "1.6.0"

CSS = """
  /* ============ Field Entry Kit v%s ============
     Large-target, high-contrast entry controls. Sizing is driven by --tap
     rather than per-component numbers so one token retunes the whole kit for
     gloves, cold hands or a wall-mounted tablet. */
  :root {
    --tap: 60px;            /* primary control height  */
    --tap-sm: 48px;         /* secondary control height */
    --fek-r: 16px;
    /* These three moved for WCAG AA and the move was made in the pages, by
       hand, and never came back here -- because the CSS half of fek_emit was
       dead code and nobody could tell. Source and pages agreed only by
       ramp-1 moved here too: at its old teal, white label text on a selected
       button measured 3.94:1 and the .92-white sub-line 3.59:1, both under AA.
       No page had caught it because none defaulted to a ramp-1 option until the
       deployment log did. Every ramp is now checked against both, in
       verify_contrast_slice.
       The pre-fix ramp values are named in verify_contrast_slice,
       which greps for them literally across every page -- so they are not
       repeated here, because a comment naming them is itself a page carrying
       them, and the suite is right not to care why. */
    --ramp-0:#2B6C8F; --ramp-1:#2F7373; --ramp-2:#2C784C;
    --ramp-3:#8A6408; --ramp-4:#A94F26; --ramp-5:#B23A32;
    --fek-line:#C7C0AC;
  }
  .fek-lab { display:block; font:800 15px var(--body); color:var(--ink-2);
    letter-spacing:.01em; margin:0 0 6px; }
  .fek-lab .u { font:600 12.5px var(--mono); color:var(--muted); margin-left:6px; }
  .fek-help { font-size:13.5px; color:var(--muted); line-height:1.5; margin:6px 0 0; }
  .fek-row { margin:0 0 20px; }

  /* --- stepper: the workhorse numeric entry --- */
  .fek-step { display:flex; align-items:stretch; gap:0; border:2px solid var(--border);
    border-radius:var(--fek-r); overflow:hidden; background:var(--surface); max-width:340px; }
  .fek-step button { border:0; background:var(--surface-2); color:var(--ink);
    font:800 30px var(--body); line-height:1; width:calc(var(--tap) + 8px); min-height:var(--tap);
    cursor:pointer; touch-action:manipulation; transition:background .12s; }
  .fek-step button:hover { background:var(--soft); color:var(--s1); }
  .fek-step button:active { background:var(--s1); color:#fff; }
  .fek-step .val { flex:1; min-width:0; text-align:center; border:0; background:none;
    font:800 30px var(--head); color:var(--ink); font-variant-numeric:tabular-nums;
    -moz-appearance:textfield; padding:0 4px; }
  .fek-step .val::-webkit-outer-spin-button,
  .fek-step .val::-webkit-inner-spin-button { -webkit-appearance:none; margin:0; }
  .fek-step .val:focus { outline:none; background:var(--soft); }

  /* --- segmented ordinal dial with a colour ramp --- */
  .fek-dial { display:flex; flex-wrap:wrap; gap:8px; }
  .fek-dial button { flex:1 1 auto; min-width:72px; min-height:var(--tap);
    border:2px solid var(--border); border-radius:var(--fek-r); background:var(--surface);
    font:800 17px var(--body); color:var(--ink-2); cursor:pointer; touch-action:manipulation;
    display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px;
    padding:6px 8px; transition:transform .08s, border-color .12s, background .12s; }
  .fek-dial button small { font:600 11px var(--mono); color:var(--muted); letter-spacing:.02em; }
  .fek-dial button:active { transform:scale(.96); }
  .fek-dial button.on { color:#fff; border-color:transparent; }
  .fek-dial button.on small { color:rgba(255,255,255,.92); }
  .fek-dial button.on[data-r="0"]{background:var(--ramp-0);}
  .fek-dial button.on[data-r="1"]{background:var(--ramp-1);}
  .fek-dial button.on[data-r="2"]{background:var(--ramp-2);}
  .fek-dial button.on[data-r="3"]{background:var(--ramp-3);}
  .fek-dial button.on[data-r="4"]{background:var(--ramp-4);}
  .fek-dial button.on[data-r="5"]{background:var(--ramp-5);}

  /* --- field: a typed value from an instrument readout ---
     A stepper is the wrong control for a number you READ off a machine to three
     decimals: you would tap two thousand times to reach 1.842. This is a plain
     numeric entry sized like the rest of the kit, with the unit shown and the
     decimal keypad requested, and nothing that pretends the value is scrollable. */
  .fek-field { display:flex; align-items:stretch; gap:0; border:2px solid var(--border);
    border-radius:var(--fek-r); overflow:hidden; background:var(--surface); max-width:340px; }
  .fek-field input { flex:1; min-width:0; border:0; background:none; text-align:right;
    font:800 26px var(--head); color:var(--ink); font-variant-numeric:tabular-nums;
    -moz-appearance:textfield; padding:0 12px; min-height:var(--tap); }
  .fek-field input::-webkit-outer-spin-button,
  .fek-field input::-webkit-inner-spin-button { -webkit-appearance:none; margin:0; }
  .fek-field input:focus { outline:none; background:var(--soft); }
  .fek-field input::placeholder { color:var(--muted); font-weight:600; font-size:20px; }
  .fek-field .u { display:flex; align-items:center; padding:0 14px; background:var(--surface-2);
    font:700 13px var(--mono); color:var(--muted); border-left:2px solid var(--border); white-space:nowrap; }
  .fek-field.empty { border-style:dashed; }

  /* --- a box the browser could not parse (v1.4.0, ADR-151) ---
     Not the same state as empty, and it must not look like it. An empty box is
     "not recorded yet"; this one holds the reader's own characters and hands
     the page back the empty string, so without a state of its own the two are
     one thing on screen as well as in the value. */
  .fek-step.bad, .fek-field.bad { border-color:var(--ramp-5); border-style:solid; }
  .fek-bad { font:700 13.5px var(--body); color:var(--ramp-5); margin:6px 0 0; }
  input[type="number"].fek-badbox { border-color:var(--ramp-5) !important; }

  /* --- big toggle chips --- */
  .fek-chips { display:flex; flex-wrap:wrap; gap:9px; }
  .fek-chip { min-height:var(--tap-sm); border:2px solid var(--border); border-radius:999px;
    background:var(--surface); font:800 15.5px var(--body); color:var(--ink-2);
    padding:0 20px; cursor:pointer; touch-action:manipulation; display:inline-flex;
    align-items:center; gap:8px; transition:transform .08s, border-color .12s, background .12s; }
  .fek-chip:active { transform:scale(.96); }
  .fek-chip.on { border-color:var(--s1); background:var(--soft); color:var(--s1-deep); }
  .fek-chip.on::before { content:"\\2713"; font-size:17px; }

  /* --- slider with a live bubble --- */
  .fek-slide { display:flex; align-items:center; gap:14px; }
  .fek-slide input[type=range] { flex:1; min-width:0; height:var(--tap-sm); -webkit-appearance:none;
    background:transparent; cursor:pointer; touch-action:manipulation; }
  .fek-slide input[type=range]::-webkit-slider-runnable-track { height:14px; border-radius:8px;
    background:linear-gradient(90deg,var(--ramp-0),var(--ramp-2),var(--ramp-3),var(--ramp-5)); }
  .fek-slide input[type=range]::-moz-range-track { height:14px; border-radius:8px;
    background:linear-gradient(90deg,var(--ramp-0),var(--ramp-2),var(--ramp-3),var(--ramp-5)); }
  .fek-slide input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:34px; height:34px;
    border-radius:50%%; background:#fff; border:3px solid var(--ink); margin-top:-10px;
    box-shadow:0 2px 6px rgba(35,40,31,.3); }
  .fek-slide input[type=range]::-moz-range-thumb { width:34px; height:34px; border-radius:50%%;
    background:#fff; border:3px solid var(--ink); box-shadow:0 2px 6px rgba(35,40,31,.3); }
  .fek-slide .bub { font:800 26px var(--head); font-variant-numeric:tabular-nums; color:var(--ink);
    min-width:86px; text-align:right; }
  .fek-slide .bub span { font:600 13px var(--mono); color:var(--muted); margin-left:3px; }

  /* --- big picker: replaces <select> for long lists --- */
  .fek-pick { border:2px solid var(--border); border-radius:var(--fek-r); background:var(--surface);
    overflow:hidden; }
  .fek-pick .search { width:100%%; border:0; border-bottom:2px solid var(--border);
    font:700 17px var(--body); padding:0 16px; min-height:var(--tap); background:var(--surface-2); }
  .fek-pick .search:focus { outline:none; background:var(--soft); }
  .fek-pick .opts { max-height:264px; overflow-y:auto; -webkit-overflow-scrolling:touch; }
  .fek-pick .opt { display:block; width:100%%; text-align:left; border:0; border-bottom:1px solid var(--border);
    background:none; font:700 16.5px var(--body); color:var(--ink); min-height:var(--tap-sm);
    padding:10px 16px; cursor:pointer; touch-action:manipulation; }
  .fek-pick .opt small { display:block; font:400 12.5px var(--mono); color:var(--muted); margin-top:2px; }
  .fek-pick .opt:hover { background:var(--soft); }
  .fek-pick .opt.on { background:var(--s1); color:#fff; }
  .fek-pick .opt.on small { color:rgba(255,255,255,.92); }
  .fek-pick .none { padding:16px; color:var(--muted); font-size:14px; }

  /* --- readout tiles, sized to be read at arm's length --- */
  .fek-tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(148px,1fr)); gap:11px; margin:14px 0 2px; }
  .fek-tile { border:2px solid var(--border); border-radius:var(--fek-r); padding:13px 15px; background:var(--surface); }
  .fek-tile .v { font:800 30px var(--head); font-variant-numeric:tabular-nums; line-height:1.05; color:var(--ink); }
  .fek-tile .l { font:700 12px var(--body); color:var(--muted); margin-top:4px; letter-spacing:.02em; }
  .fek-tile.good { border-color:var(--ramp-2); } .fek-tile.good .v { color:var(--ramp-2); }
  .fek-tile.warn { border-color:var(--ramp-3); } .fek-tile.warn .v { color:#8a6508; }
  .fek-tile.bad  { border-color:var(--ramp-5); } .fek-tile.bad  .v { color:var(--ramp-5); }
  .fek-tile.cold { border-color:var(--ramp-0); } .fek-tile.cold .v { color:var(--ramp-0); }

  /* --- banner: the verdict, big --- */
  .fek-banner { border-radius:var(--fek-r); padding:16px 19px; margin:14px 0; font-size:16px;
    line-height:1.55; border-left:7px solid var(--ramp-2); background:var(--soft); color:var(--ink-2); }
  .fek-banner b { font-family:var(--head); color:var(--ink); font-size:17.5px; display:block; margin-bottom:4px; }
  .fek-banner.warn { border-left-color:var(--ramp-3); background:var(--warn-bg); }
  .fek-banner.bad  { border-left-color:var(--ramp-5); background:var(--danger-bg); }
  .fek-banner.cold { border-left-color:var(--ramp-0); background:#E6EEF3; }

  /* --- photographs: the record carries the reference, not the image ---
     (v1.5.0, ADR-201). Sized for a gloved thumb like the rest of the kit, and
     the thumbnail is large enough to tell two bark shots apart at arm's
     length, which is the only reason it is on screen at all. */
  .fek-drop { border:2.5px dashed var(--fek-line); border-radius:var(--fek-r);
    background:var(--surface); padding:18px 16px; text-align:center;
    transition:border-color .12s, background .12s; }
  .fek-drop.on { border-color:var(--ramp-2); background:var(--soft); border-style:solid; }
  .fek-drop p { margin:0 0 10px; font-size:15px; color:var(--ink-2); }
  .fek-drop button { min-height:var(--tap); border:0; border-radius:var(--fek-r);
    background:var(--ramp-2); color:#fff; font:800 16px var(--body); padding:0 22px;
    cursor:pointer; touch-action:manipulation; }
  .fek-drop button:active { transform:scale(.97); }
  .fek-photos { display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr));
    gap:12px; margin-top:14px; }
  .fek-photo { border:2px solid var(--border); border-radius:var(--fek-r);
    background:var(--surface); overflow:hidden; }
  .fek-photo img { display:block; width:100%%; height:150px; object-fit:cover; background:var(--surface-2); }
  .fek-photo .m { padding:10px 12px 12px; }
  .fek-photo .m code { display:block; font:500 11.5px var(--mono); color:var(--muted);
    word-break:break-all; line-height:1.45; }
  .fek-photo .m input, .fek-photo .m textarea { width:100%%; margin-top:8px; border:1.5px solid var(--fek-line);
    border-radius:10px; padding:9px 10px; font:15px var(--body); background:var(--surface);
    color:var(--ink); min-height:44px; }
  .fek-photo .m textarea { min-height:62px; resize:vertical; }
  .fek-photo .rm { margin-top:8px; min-height:44px; width:100%%; border:1.5px solid var(--fek-line);
    border-radius:10px; background:none; color:var(--ink-2); font:700 14px var(--body); cursor:pointer; }
  .fek-photo .rm:hover { border-color:var(--ramp-5); color:var(--ramp-5); }
  .fek-await { margin:8px 0 0; padding:9px 11px; border:1.5px dashed var(--accent, #7A6A3A);
    border-radius:10px; background:var(--surface-2, #F3EEE0); }
  .fek-await b { color:var(--accent, #7A6A3A); }
  .fek-await ul { margin:6px 0 0; padding:0 0 0 18px; font-family:var(--mono, monospace);
    font-size:11.5px; color:var(--ink-2, #4B5344); line-height:1.6; }
  .fek-await .cap { color:var(--muted, #6B6B5E); }
  .fek-shot { font:700 13.5px var(--body); color:var(--ink-2); margin:10px 0 0; min-height:1.2em; }
  .fek-shot.bad { color:var(--ramp-5); }
  @media print { .fek-drop, .fek-photo .rm { display:none !important; }
                 .fek-photo img { height:auto; } }

  @media (max-width:420px){ :root { --tap:56px; --tap-sm:46px; } .fek-step .val { font-size:26px; } }
  @media print { .fek-step button, .fek-pick .search { display:none; } }
""" % VERSION

JS = """
/* ---- Field Entry Kit v%s : constructors return {el, get, set} ---- */
var FEK = (function(){
  function el(t,c,h){ var e=document.createElement(t); if(c) e.className=c;
    if(h!=null) e.innerHTML=h; return e; }
  /* Where the line falls, and why it falls there.
     A component's OWN label is written by whoever built the page and often
     carries deliberate markup -- "Pod parent <span class=\"u\">seed bearer</span>".
     That stays HTML. The label on an OPTION, a chip or a tile is data: a
     species you typed, a cross you recorded, a source you named. v1.1 passed
     those straight into innerHTML, so a plant named with a < became markup.
     Escaped here rather than at each call site, because a component whose
     safety depends on every caller remembering is a component that will bite
     somebody. Verified against the whole kit first: no option, chip or tile
     label anywhere passes markup on purpose. */
  /* No object literal here on purpose: the map form needs an escaped double
     quote as a key, and this file is a Python string emitting JavaScript, so
     that quote has to survive two layers of escaping. It did not, and every
     consumer got a syntax error that took FEK down with it. A chain of
     comparisons has nothing to escape. */
  function escv(s){ return String(s==null?"":s).replace(/[&<>"']/g,function(c){
    return c==="&"?"&amp;":c==="<"?"&lt;":c===">"?"&gt;":c==='"'?"&quot;":"&#39;"; }); }
  function buzz(m){ try{ if(navigator.vibrate) navigator.vibrate(m||8);}catch(e){} }

  /* ---- a rejected keystroke buffer is not an empty one (v1.4.0, ADR-151) ----
     `<input type=number>` has a value the page reads and a raw buffer the page
     cannot see, and when the browser cannot parse the buffer the value it
     hands over is the EMPTY STRING -- the same string a box nobody touched
     hands over. Both numeric components here treated that as "not recorded":
     the stepper and the field each reported null, the row went dashed-empty,
     and the reader's characters sat in a box the sheet had decided was blank.
     `validity.badInput` is the only thing that separates them, because it is
     about the buffer rather than the value. Fixed once, here, rather than in
     the seven pages that mount these components -- which is what this file is
     for. */
  function badBuffer(inp){ return !!(inp && inp.validity && inp.validity.badInput); }
  function badMark(wrap, box, inp, label, on){
    var line = wrap.__fekBad;
    if(on && !line){ line = wrap.__fekBad = el("p","fek-bad"); wrap.appendChild(line); }
    if(line) line.textContent = on
      ? ((label||"this box") + " holds something that is not a number")
      : "";
    if(box) box.classList.toggle("bad", !!on);
    if(on) inp.setAttribute("aria-invalid","true"); else inp.removeAttribute("aria-invalid");
    return on;
  }

  /* ---- field registry (v1.4.0) ----
     A component writes through to a hidden field via the page's own onchange.
     That is fine going out and useless coming back: nothing could put a
     restored value INTO the widget, so an autosaved session showed default
     dials over correct data -- a lie on screen, which is worse than no
     autosave. A component that declares `field:"sElev"` is registered here,
     and FEK.setField puts a value back through the widget's own set(). Purely
     additive: a component with no `field` behaves exactly as before. */
  var REG = {};
  function reg(o, h){ if(o && o.field) REG[o.field] = h; return h; }
  function setField(id, v){
    var h = REG[id];
    if(!h) return false;
    try { h.set(v); } catch(e){ return false; }
    return true;
  }
  function fields(){ var out=[]; for(var k in REG) if(REG.hasOwnProperty(k)) out.push(k); return out; }

  function step(o){
    o=o||{}; var min=(o.min==null?-Infinity:o.min), max=(o.max==null?Infinity:o.max);
    var stepv=o.step||1, dec=o.dec==null?(String(stepv).split(".")[1]||"").length:o.dec;
    var v=o.value==null?0:o.value;
    var wrap=el("div","fek-row"), lab=el("label","fek-lab",
      (o.label||"")+(o.unit?'<span class="u">'+o.unit+'</span>':""));
    var box=el("div","fek-step");
    var minus=el("button",null,"&minus;"), inp=el("input"), plus=el("button",null,"+");
    minus.type="button"; plus.type="button"; inp.type="number"; inp.className="val";
    inp.setAttribute("inputmode","decimal");
    if(o.label) inp.setAttribute("aria-label",o.label);
    /* nullable: the control can hold "not recorded", which is not the same as
       zero. Aspect 0 is north; a duff depth of 0 cm is an observation. An empty
       nullable stepper reports null and the first bump starts from o.start. */
    var nullable = !!o.nullable;
    if(nullable && o.value==null) v=null;
    function clamp(x){ return Math.min(max,Math.max(min,x)); }
    function render(){
      if(v==null){ inp.value=""; wrap.classList.add("is-empty"); box.classList.add("empty"); return; }
      wrap.classList.remove("is-empty"); box.classList.remove("empty");
      inp.value=(dec?v.toFixed(dec):String(v));
    }
    function set(x,quiet){
      if(nullable && (x==null || x==="" || (typeof x==="number" && !isFinite(x)))) v=null;
      else v=clamp(isFinite(x)?x:0);
      render(); if(!quiet&&o.onchange) o.onchange(v);
    }
    function bump(d){
      if(v==null) set(clamp(o.start==null?0:o.start));
      else set(+(v+d*stepv).toFixed(6));
      buzz();
    }
    function clear(){ if(nullable) set(null); }
    minus.addEventListener("click",function(){ bump(-1); });
    plus.addEventListener("click",function(){ bump(1); });
    var hold;
    function holdOn(d){ return function(){ clearInterval(hold);
      hold=setInterval(function(){ bump(d); },110); }; }
    function holdOff(){ clearInterval(hold); }
    minus.addEventListener("pointerdown",holdOn(-1)); plus.addEventListener("pointerdown",holdOn(1));
    ["pointerup","pointerleave","pointercancel"].forEach(function(ev){
      minus.addEventListener(ev,holdOff); plus.addEventListener(ev,holdOff); });
    inp.addEventListener("input",function(){
      if(badMark(wrap, box, inp, o.label, badBuffer(inp))){
        // A nullable stepper goes to "not recorded", the same as a cleared box,
        // because there is no number to hold either way -- what changes is that
        // the row now SAYS which of the two happened. A fixed stepper keeps the
        // value it had, and says so, rather than silently reading as unchanged.
        if(nullable && v!==null){ v=null; box.classList.add("empty"); if(o.onchange) o.onchange(null); }
        return; }
      if(nullable && inp.value===""){ v=null; box.classList.add("empty");
        if(o.onchange) o.onchange(null); return; }
      var x=parseFloat(inp.value);
      if(isFinite(x)){ v=clamp(x); box.classList.remove("empty"); if(o.onchange) o.onchange(v); } });
    // BLUR MUST NOT ERASE THE EVIDENCE. render() writes v back into the box, so
    // a blur over bad input would replace the reader's characters with the old
    // number and take the message down with them -- the page quietly deciding
    // it knew better. The buffer is still bad; leave it, and leave the line up.
    inp.addEventListener("blur",function(){ if(!badBuffer(inp)) render(); });
    box.appendChild(minus); box.appendChild(inp); box.appendChild(plus);
    wrap.appendChild(lab); wrap.appendChild(box);
    if(o.help) wrap.appendChild(el("p","fek-help",o.help));
    render();
    return reg(o, { el:wrap, get:function(){return v;}, set:function(x){set(x,true);},
             clear:clear, nullable:nullable });
  }

  /* field: a value typed from an instrument readout. No steppers — see the CSS note. */
  function field(o){
    o=o||{};
    var min=(o.min==null?-Infinity:o.min), max=(o.max==null?Infinity:o.max);
    var dec=(o.dec==null?3:o.dec), v=(o.value==null?null:o.value);
    var wrap=el("div","fek-row"), lab=el("label","fek-lab",
      (o.label||"")+(o.unit?'<span class="u">'+o.unit+'</span>':""));
    var box=el("div","fek-field"), inp=el("input");
    inp.type="number"; inp.setAttribute("inputmode","decimal");
    if(o.step!=null) inp.step=o.step;
    inp.placeholder = o.placeholder==null ? "—" : o.placeholder;
    if(o.label) inp.setAttribute("aria-label",o.label);
    function paint(){ box.classList.toggle("empty", v==null); }
    function set(x,quiet){
      if(x==null || x===""){ v=null; inp.value=""; }
      else { var n=parseFloat(x);
        v = isFinite(n) ? Math.min(max,Math.max(min,n)) : null;
        inp.value = (v==null?"":String(v)); }
      paint(); if(!quiet&&o.onchange) o.onchange(v);
    }
    inp.addEventListener("input",function(){
      if(badMark(wrap, box, inp, o.label, badBuffer(inp))){
        if(v!==null){ v=null; paint(); if(o.onchange) o.onchange(null); }
        return; }
      if(inp.value===""){ v=null; paint(); if(o.onchange) o.onchange(null); return; }
      var n=parseFloat(inp.value);
      if(isFinite(n)){ v=Math.min(max,Math.max(min,n)); paint(); if(o.onchange) o.onchange(v); } });
    inp.addEventListener("blur",function(){
      if(badBuffer(inp)) return;
      if(v!=null && isFinite(v)) inp.value = (dec==null?String(v):String(+v.toFixed(dec)));
      paint(); });
    box.appendChild(inp);
    if(o.unitBox!==false && o.unit) box.appendChild(el("div","u",o.unit));
    wrap.appendChild(lab); wrap.appendChild(box);
    if(o.help) wrap.appendChild(el("p","fek-help",o.help));
    set(v,true);
    return reg(o, { el:wrap, get:function(){return v;}, set:function(x){set(x,true);},
             clear:function(){ set(null,true); }, nullable:true });
  }

  function dial(o){
    o=o||{}; var opts=o.options||[], cur=o.value==null?null:o.value;
    var wrap=el("div","fek-row"), lab=el("label","fek-lab",o.label||"");
    var box=el("div","fek-dial"), btns=[];
    opts.forEach(function(op,i){
      var b=el("button",null,'<span>'+escv(op.label)+'</span>'+(op.sub?'<small>'+escv(op.sub)+'</small>':""));
      b.type="button";
      b.setAttribute("data-r", op.ramp==null ? String(Math.min(5,Math.round(i*5/Math.max(1,opts.length-1)))) : String(op.ramp));
      b.addEventListener("click",function(){
        cur = (cur===op.value && o.clearable!==false) ? null : op.value;
        paint(); buzz(); if(o.onchange) o.onchange(cur);
      });
      btns.push(b); box.appendChild(b);
    });
    function paint(){ btns.forEach(function(b,i){ b.classList.toggle("on", opts[i].value===cur); }); }
    paint();
    wrap.appendChild(lab); wrap.appendChild(box);
    if(o.help) wrap.appendChild(el("p","fek-help",o.help));
    return reg(o, { el:wrap, get:function(){return cur;},
             set:function(x){ cur=x; paint(); } });
  }

  function chips(o){
    o=o||{}; var opts=o.options||[], sel={};
    (o.value||[]).forEach(function(v){ sel[v]=1; });
    var wrap=el("div","fek-row"), lab=el("label","fek-lab",o.label||"");
    var box=el("div","fek-chips"), btns=[];
    opts.forEach(function(op){
      var b=el("button","fek-chip",escv(op.label)); b.type="button";
      b.addEventListener("click",function(){
        if(o.single){ sel={}; sel[op.value]=1; }
        else if(sel[op.value]) delete sel[op.value]; else sel[op.value]=1;
        paint(); buzz(); if(o.onchange) o.onchange(Object.keys(sel));
      });
      btns.push(b); box.appendChild(b);
    });
    function paint(){ btns.forEach(function(b,i){ b.classList.toggle("on",!!sel[opts[i].value]); }); }
    paint();
    wrap.appendChild(lab); wrap.appendChild(box);
    if(o.help) wrap.appendChild(el("p","fek-help",o.help));
    return reg(o, { el:wrap, get:function(){return Object.keys(sel);},
             set:function(a){ sel={}; (a||[]).forEach(function(v){sel[v]=1;}); paint(); } });
  }

  function slider(o){
    o=o||{};
    var nullable=!!o.nullable;
    var v = (nullable && o.value==null) ? null : (o.value==null?(o.min||0):o.value);
    var wrap=el("div","fek-row"), lab=el("label","fek-lab",o.label||"");
    var box=el("div","fek-slide"), r=el("input"), bub=el("div","bub");
    r.type="range"; r.min=o.min==null?0:o.min; r.max=o.max==null?100:o.max;
    r.step=o.step||1; r.value=v;
    if(o.label) r.setAttribute("aria-label",o.label);
    function paint(){
      if(v==null){ bub.innerHTML='<span style="opacity:.6">not recorded</span>'; return; }
      bub.innerHTML=(o.fmt?o.fmt(v):v)+(o.unit?'<span>'+o.unit+'</span>':"");
    }
    r.addEventListener("input",function(){ v=parseFloat(r.value); paint(); if(o.onchange) o.onchange(v); });
    if(nullable && v==null) r.value = (o.min==null?0:o.min);
    paint();
    box.appendChild(r); box.appendChild(bub);
    wrap.appendChild(lab); wrap.appendChild(box);
    if(o.help) wrap.appendChild(el("p","fek-help",o.help));
    return reg(o, { el:wrap, get:function(){return v;},
             set:function(x){ v=(nullable&&x==null)?null:x; if(x!=null) r.value=x; paint(); },
             clear:function(){ if(nullable){ v=null; paint(); } }, nullable:nullable });
  }

  function picker(o){
    o=o||{}; var opts=o.options||[], cur=o.value==null?null:o.value, q="";
    var wrap=el("div","fek-row"), lab=el("label","fek-lab",o.label||"");
    var box=el("div","fek-pick"), s=el("input","search"), list=el("div","opts");
    s.type="text"; s.placeholder=o.placeholder||"type to filter…";
    s.setAttribute("autocomplete","off");
    if(o.label) s.setAttribute("aria-label",o.label+" filter");
    function paint(){
      list.innerHTML="";
      var qq=q.toLowerCase();
      var shown=opts.filter(function(op){
        return !qq || (op.label+" "+(op.sub||"")).toLowerCase().indexOf(qq)>=0; });
      if(!shown.length){ list.appendChild(el("div","none","No match. Clear the filter to see all "+opts.length+".")); return; }
      shown.slice(0,200).forEach(function(op){
        var b=el("button","opt"+(op.value===cur?" on":""),
          escv(op.label)+(op.sub?'<small>'+escv(op.sub)+'</small>':""));
        b.type="button";
        b.addEventListener("click",function(){ cur=op.value; paint(); buzz(); if(o.onchange) o.onchange(cur); });
        list.appendChild(b);
      });
    }
    s.addEventListener("input",function(){ q=s.value; paint(); });
    box.appendChild(s); box.appendChild(list);
    wrap.appendChild(lab); wrap.appendChild(box);
    if(o.help) wrap.appendChild(el("p","fek-help",o.help));
    paint();
    return reg(o, { el:wrap, get:function(){return cur;}, set:function(x){ cur=x; paint(); } });
  }

  function tiles(list){
    var box=el("div","fek-tiles");
    (list||[]).forEach(function(t){
      box.appendChild(el("div","fek-tile"+(t.tone?" "+t.tone:""),
        '<div class="v">'+escv(t.v)+'</div><div class="l">'+escv(t.l)+'</div>'));
    });
    return box;
  }
  function banner(title,body,tone){
    return el("div","fek-banner"+(tone?" "+tone:""),"<b>"+title+"</b>"+body);
  }

  /* ==================== PHOTOGRAPHS (v1.5.0, ADR-201) ====================
     THE RECORD CARRIES THE REFERENCE, NOT THE IMAGE.

     One page in this kit took a photograph and twenty did not, on a kit that
     emits Darwin Core with `associatedMedia` left empty everywhere. A field
     record whose voucher is a sentence is a weaker record than one that names
     the frame.

     The image itself does not go into the record, for three reasons that all
     point the same way. A CSV cell cannot hold a JPEG. A base64 photograph
     inside a .eco export turns a 40 kB record into a 4 MB one, and the export
     is a thing people paste into a message. And a photograph's home is the
     camera roll or the card, where it already is -- Darwin Core asks
     `associatedMedia` for an IDENTIFIER of the media, not the media.

     So what the record carries is what lets a person -- or a script -- put the
     row and the file back together six months later:

         filename | bytes | captured | crc32

     CRC-32 AND NOT SHA-256, deliberately. `crypto.subtle` does not exist on a
     `file://` page, because a file URL is not a secure context, and this kit
     is opened off a card in the field as often as it is served over https as
     an artifact. A digest that is only available in one of those two is worse
     than a weaker one that is the same in both: the whole point is that the
     number written on the sheet in the field still matches the number computed
     back at the desk. This is an INTEGRITY check -- has this file changed, is
     this the same file -- and it is not, and must not be described as,
     cryptographic.

     CAPTURED IS THE FILE'S MTIME, NOT EXIF. `File.lastModified` is what a
     browser will give a page without parsing the JPEG, and for a frame straight
     off a camera it is the shutter. For a file that has been copied between
     cards, or round-tripped through a messaging app, it is the copy's time.
     The field is named `captured` because that is what it usually means, and
     the page says plainly that a copy carries the copy's time.

     THE IMAGES ARE NEVER UPLOADED and never leave the tab. They are object
     URLs revoked the moment a photograph is removed, so a session that adds and
     drops a hundred frames does not hold a hundred blobs. Closing the tab
     discards them, which is correct: the originals are where they belong. */
  var CRCT = (function(){
    var t = new Array(256), c, n, k;
    for (n = 0; n < 256; n++) {
      c = n;
      for (k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      t[n] = c >>> 0;
    }
    return t;
  })();
  function crc32(bytes){
    var c = 0xFFFFFFFF, i;
    for (i = 0; i < bytes.length; i++) c = CRCT[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
    c = (c ^ 0xFFFFFFFF) >>> 0;
    /* eight hex digits always: a crc of 0x0000A1B2 written as "a1b2" is a
       different string from the one the next reader computes, and a checksum
       you have to remember to pad is a checksum that will be compared wrong. */
    return ("0000000" + c.toString(16)).slice(-8);
  }
  function iso(ms){
    /* Local minutes, not UTC, because a field sheet is read where it was
       written. ISO-shaped so it sorts. */
    if (!ms) return "";
    var d = new Date(ms), p = function(n){ return (n < 10 ? "0" : "") + n; };
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate())
         + " " + p(d.getHours()) + ":" + p(d.getMinutes());
  }
  function photos(o){
    o = o || {};
    var list = [], max = (o.max == null ? 40 : o.max);
    var wrap = el("div", "fek-row"), lab = el("label", "fek-lab", o.label || "Photographs");
    var zone = el("div", "fek-drop");
    /* THE ZONE NEEDS A NAME OF ITS OWN. A drop listener leaves no mark a
       selector can find, and the control the page's own snapshot offers under
       this component's label is the hidden FILE INPUT -- so a task that says
       "drop these on the photographs" landed on the input and was refused as
       not a drop zone. The id is the address; a page that mounts this without
       one can still be driven through the file input, and cannot be driven by
       a drop. */
    zone.id = o.dropId || (o.field ? o.field + "Drop" : "");
    if (!zone.id) zone.removeAttribute("id");
    var inp = el("input");
    inp.type = "file"; inp.accept = o.accept || "image/*"; inp.multiple = true;
    inp.style.display = "none";
    if (o.label) inp.setAttribute("aria-label", o.label);
    var btn = el("button", null, "📷 Add photos");
    btn.type = "button";
    zone.appendChild(el("p", null, o.prompt ||
      "<b>Shoot the character, not the specimen.</b> Camera or gallery, or drop files here."));
    zone.appendChild(inp); zone.appendChild(btn);
    var grid = el("div", "fek-photos");
    /* Its own live region, by the rule ADR-199 put on every other message in
       this kit: an addition that is refused -- a PDF dropped on a photo zone,
       a frame too many -- is announced rather than silently ignored. */
    var shot = el("p", "fek-shot");
    shot.setAttribute("role", "status"); shot.setAttribute("aria-live", "polite");

    /* FRAMES THIS SHEET KNOWS ABOUT AND DOES NOT HOLD (v1.6.0, ADR-206).
       A page can restore what you typed. It cannot restore a photograph: a
       page cannot hand a File back to a file input, and this component has
       always refused to pretend otherwise. But a restored sheet that came back
       quietly WITHOUT its frames is worse than one that admits it, because the
       reader believes their morning is back. So the record survives the
       restore even though the bytes do not, the component says which frames
       are missing and names them, and it takes them back BY CHECKSUM: drop the
       same files in again and the label and note you typed -- the expensive
       part -- come back with them. */
    var await_ = [];
    var awaitBox = el("div", "fek-await");
    awaitBox.style.display = "none";

    function say(t, bad){ shot.textContent = t || ""; shot.classList.toggle("bad", !!bad); }
    function changed(){
      if (o.onchange) o.onchange(records());
      /* A REAL EVENT, BECAUSE A PHOTOGRAPH IS AN EDIT (v1.6.0, ADR-206).
         Adding a frame fires no input and no change -- the file input is
         hidden and a drop is neither -- so every autosave in this kit sat
         still while a reader photographed four stations, and a session that
         was ONLY photographs was saved by nothing. One bubbling event, so the
         page does not have to remember to wire it and a page added tomorrow
         is covered on the day it mounts the component. */
      try { wrap.dispatchEvent(new CustomEvent("fek-change", { bubbles: true })); }
      catch (e) {}
    }
    function records(){
      /* The awaited frames are IN the record. A photograph that was taken has
         an identifier whether or not this browser still holds the bytes, and
         an export that dropped it would lose the only link between the row and
         a file sitting on a camera. `have` says which is which. */
      return list.map(function(p){
        return { name: p.name, bytes: p.bytes, captured: p.captured, crc: p.crc,
                 label: p.label, note: p.note, have: true };
      }).concat(await_.map(function(p){
        return { name: p.name, bytes: p.bytes, captured: p.captured, crc: p.crc,
                 label: p.label, note: p.note, have: false };
      }));
    }
    function renderAwait(){
      if (!await_.length) { awaitBox.style.display = "none"; awaitBox.innerHTML = ""; return; }
      awaitBox.style.display = "";
      awaitBox.innerHTML = "<b>" + await_.length + " photograph"
        + (await_.length === 1 ? " is" : "s are") + " on this record and not on this device.</b> "
        + "A saved sheet keeps what you typed; it cannot keep an image. Add the same file"
        + (await_.length === 1 ? "" : "s") + " again and the caption you wrote comes back with "
        + (await_.length === 1 ? "it" : "them") + " \\u2014 matched by checksum, so it has to be "
        + "the same frame."
        + "<ul>" + await_.map(function(p){
            return "<li>" + escv(p.name) + " <span class=\\"cap\\">" + p.bytes + " bytes \\u00b7 crc "
                 + p.crc + (p.label ? " \u00b7 " + escv(p.label) : "") + "</span></li>";
          }).join("") + "</ul>";
    }
    function render(){
      grid.innerHTML = "";
      list.forEach(function(p, i){
        var d = el("div", "fek-photo");
        var im = el("img"); im.src = p.url;
        im.alt = p.label || ("photograph " + (i + 1) + " \u2014 " + p.name);
        var m = el("div", "m");
        m.appendChild(el("code", null,
          escv(p.name) + "<br>" + p.bytes + " bytes \u00b7 crc " + p.crc
          + (p.captured ? "<br>" + escv(p.captured) : "")));
        var lv = el("input"); lv.type = "text"; lv.value = p.label;
        lv.placeholder = o.labelPlaceholder || "voucher / specimen \u2116";
        lv.setAttribute("aria-label", "voucher for " + p.name);
        var nt = el("textarea"); nt.value = p.note;
        nt.placeholder = o.notePlaceholder || "What does this show?";
        nt.setAttribute("aria-label", "note on " + p.name);
        var rm = el("button", "rm", "Remove"); rm.type = "button";
        lv.addEventListener("input", function(){ p.label = lv.value; changed(); });
        nt.addEventListener("input", function(){ p.note = nt.value; changed(); });
        rm.addEventListener("click", function(){
          try { URL.revokeObjectURL(p.url); } catch (e) {}
          list.splice(list.indexOf(p), 1);
          render(); say("Removed " + p.name); changed(); buzz();
        });
        m.appendChild(lv); m.appendChild(nt); m.appendChild(rm);
        d.appendChild(im); d.appendChild(m);
        grid.appendChild(d);
      });
    }
    function add(files){
      var fs = Array.prototype.slice.call(files || []);
      if (!fs.length) return;
      var notImages = fs.filter(function(f){ return !/^image\//.test(f.type || ""); });
      fs = fs.filter(function(f){ return /^image\//.test(f.type || ""); });
      var room = Math.max(0, max - list.length), over = fs.length - room;
      if (over > 0) fs = fs.slice(0, room);
      var pending = fs.length, added = 0, back = 0;
      /* A refusal is SAID, not swallowed: the reader who dropped six files and
         got four has to be able to find out which two, and why. */
      function done(){
        if (pending) return;
        var parts = [];
        if (added) parts.push(added + " photograph" + (added === 1 ? "" : "s") + " added");
        if (back) parts.push(back + " matched by checksum, caption restored");
        if (notImages.length)
          parts.push(notImages.length + " not an image: "
                     + notImages.map(function(f){ return f.name; }).slice(0, 3).join(", "));
        if (over > 0) parts.push(over + " over the limit of " + max);
        say(parts.join(" \u2014 ") || "Nothing added", !added);
        if (added) { render(); renderAwait(); changed(); buzz(12); }
      }
      if (!pending) { done(); return; }
      fs.forEach(function(f){
        var rd = new FileReader();
        rd.onload = function(){
          var bytes = new Uint8Array(rd.result);
          var sum = crc32(bytes), lab = "", note = "", i;
          /* BY CHECKSUM, NOT BY NAME. A camera roll renames on export and two
             cards both start at DSC_0001; the checksum is the only thing that
             says this is the frame the caption was written about. */
          for (i = 0; i < await_.length; i++) {
            if (await_[i].crc === sum && await_[i].bytes === bytes.length) {
              lab = await_[i].label || ""; note = await_[i].note || "";
              await_.splice(i, 1); back++;
              break;
            }
          }
          list.push({ name: f.name || ("photo-" + (list.length + 1) + ".jpg"),
                      bytes: bytes.length, captured: iso(f.lastModified),
                      crc: sum, label: lab, note: note,
                      url: URL.createObjectURL(f) });
          added++; pending--; done();
        };
        rd.onerror = function(){ pending--; done(); };
        rd.readAsArrayBuffer(f);
      });
    }
    btn.addEventListener("click", function(){ inp.click(); });
    inp.addEventListener("change", function(){ add(inp.files); inp.value = ""; });
    ["dragenter", "dragover"].forEach(function(ev){
      zone.addEventListener(ev, function(e){ e.preventDefault(); zone.classList.add("on"); }); });
    ["dragleave", "dragend"].forEach(function(ev){
      zone.addEventListener(ev, function(){ zone.classList.remove("on"); }); });
    /* The harness stamps data-h-drop on anything that registers a drop
       listener, so this zone is drivable by the door with no page markup. */
    zone.addEventListener("drop", function(e){
      e.preventDefault(); zone.classList.remove("on");
      if (e.dataTransfer && e.dataTransfer.files) add(e.dataTransfer.files);
    });
    wrap.appendChild(lab); wrap.appendChild(zone); wrap.appendChild(shot);
    wrap.appendChild(awaitBox); wrap.appendChild(grid);
    if (o.help) wrap.appendChild(el("p", "fek-help", o.help));
    render();
    return reg(o, {
      el: wrap, get: records, count: function(){ return list.length; },
      /* set() is deliberately not a way to put images back: a page cannot
         hand a File to a file input, and a component that pretended to
         restore a photograph from a record would be restoring a caption. */
      set: function(){ return false; },
      /* ...and THIS is what an autosave gets instead (v1.6.0, ADR-206). The
         records come back, the bytes do not, and the component says so where
         the reader will see it rather than coming back quietly one frame
         short. Frames the sheet already holds are left alone -- a restore that
         listed a photograph you are looking at would be noise. */
      restore: function(recs){
        if (!recs || !recs.length) return 0;
        var held = {}, i;
        for (i = 0; i < list.length; i++) held[list[i].crc] = 1;
        await_ = recs.filter(function(r){
          return r && r.crc && !held[r.crc];
        }).map(function(r){
          return { name: r.name, bytes: r.bytes, captured: r.captured, crc: r.crc,
                   label: r.label || "", note: r.note || "" };
        });
        renderAwait();
        return await_.length;
      },
      awaiting: function(){ return await_.slice(); },
      clear: function(){
        list.forEach(function(p){ try { URL.revokeObjectURL(p.url); } catch (e) {} });
        list = []; await_ = []; render(); renderAwait(); say(""); changed();
      },
      /* `associatedMedia` the way Darwin Core asks for it: identifiers,
         concatenated and separated. The separator is " | " because a filename
         may hold a comma and a record that splits wrong is worse than one that
         is hard to read. */
      media: function(){
        /* Awaited frames are named too. A photograph that was taken has an
           identifier whether or not this browser still holds it, and a deposit
           that dropped it would break the only link between the row and a file
           on a camera. */
        return list.concat(await_).map(function(p){
          return p.name + " (crc32 " + p.crc + (p.captured ? ", " + p.captured : "") + ")";
        }).join(" | ");
      }
    });
  }
  /* ---- the same rule for a box FEK did not build (v1.4.0, ADR-151) ----
     The components above now say when a box holds something the browser could
     not read as a number. Every page that mounts them also carries number
     boxes of its OWN -- an elevation, an effort value, five camera settings --
     and those had the same silence for the same reason: `.value` comes back ""
     and the page reads a blank. One delegated listener rather than a wrapper
     per box, because the boxes a page builds LATER -- a row added, a pane
     rendered, a measurement grid opened -- have to be covered too, and a guard
     that only knew about the boxes present at load would go quiet exactly when
     the sheet gets long. Capture phase, so the note is up before the page's own
     handler decides what the box now means. */
  function boxName(inp){
    var a=inp.getAttribute("aria-label"); if(a && a.trim()) return a.trim();
    var l=inp.closest?inp.closest("label"):null;
    if(l){ var t="",i; for(i=0;i<l.childNodes.length;i++){ var n=l.childNodes[i];
             if(n.nodeType===3) t+=n.nodeValue; }
           t=t.replace(/\s+/g," ").trim(); if(t) return t; }
    if(inp.id){ var lb=document.querySelector('label[for="'+inp.id+'"]');
                if(lb) return lb.textContent.replace(/\s+/g," ").trim(); }
    var ph=inp.getAttribute("placeholder");
    return (ph && ph.trim()) ? ph.trim() : "this box";
  }
  function guardBox(inp){
    var bad = !!(inp.validity && inp.validity.badInput);
    var note = inp.__fekBadNote;
    if(bad && !note){
      note = inp.__fekBadNote = el("p","fek-bad");
      var after = (inp.closest ? inp.closest("label") : null) || inp;
      if(after.parentNode) after.parentNode.insertBefore(note, after.nextSibling);
    }
    if(note) note.textContent = bad ? (boxName(inp)+" holds something that is not a number") : "";
    inp.classList.toggle("fek-badbox", bad);
    if(bad) inp.setAttribute("aria-invalid","true"); else inp.removeAttribute("aria-invalid");
  }
  function guard(){
    document.addEventListener("input",function(ev){
      var inp=ev.target;
      if(!inp || inp.tagName!=="INPUT" || inp.type!=="number") return;
      // a component built here already says it, in its own row
      if(inp.closest && inp.closest(".fek-step, .fek-field")) return;
      guardBox(inp);
    }, true);
  }
  if(document.readyState==="loading")
    document.addEventListener("DOMContentLoaded",guard);
  else guard();

  function mount(host,parts){
    var h=typeof host==="string"?document.getElementById(host):host;
    h.innerHTML=""; parts.forEach(function(p){ h.appendChild(p.el||p); }); return h;
  }
  /* Exported because a page building a component LABEL -- which stays HTML by
     design -- still has to escape the data inside it. A private copy of an
     escaper in one page was how the last one got lost when the kit was
     re-emitted over it. */
  return { version:"%s", esc:escv, setField:setField, fields:fields, step:step, field:field, dial:dial, chips:chips, slider:slider,
           picker:picker, photos:photos, crc32:crc32, tiles:tiles, banner:banner, mount:mount, buzz:buzz, guard:guard };
})();
""" % (VERSION, VERSION)
