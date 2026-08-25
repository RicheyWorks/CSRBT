# -*- coding: utf-8 -*-
"""Field Entry Kit v1 — the shared large/colourful data-entry layer.

Single source of truth. Emitted inline into every page that uses it, because
every page in this kit must stay one self-contained file (artifact CSP, offline
in the field, printable). Bump VERSION on any change and re-emit consumers.
"""
VERSION = "1.3.0"

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

  /* ---- field registry (v1.3.0) ----
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
      if(nullable && inp.value===""){ v=null; box.classList.add("empty");
        if(o.onchange) o.onchange(null); return; }
      var x=parseFloat(inp.value);
      if(isFinite(x)){ v=clamp(x); box.classList.remove("empty"); if(o.onchange) o.onchange(v); } });
    inp.addEventListener("blur",render);
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
      if(inp.value===""){ v=null; paint(); if(o.onchange) o.onchange(null); return; }
      var n=parseFloat(inp.value);
      if(isFinite(n)){ v=Math.min(max,Math.max(min,n)); paint(); if(o.onchange) o.onchange(v); } });
    inp.addEventListener("blur",function(){
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
  function mount(host,parts){
    var h=typeof host==="string"?document.getElementById(host):host;
    h.innerHTML=""; parts.forEach(function(p){ h.appendChild(p.el||p); }); return h;
  }
  /* Exported because a page building a component LABEL -- which stays HTML by
     design -- still has to escape the data inside it. A private copy of an
     escaper in one page was how the last one got lost when the kit was
     re-emitted over it. */
  return { version:"%s", esc:escv, setField:setField, fields:fields, step:step, field:field, dial:dial, chips:chips, slider:slider,
           picker:picker, tiles:tiles, banner:banner, mount:mount, buzz:buzz };
})();
""" % (VERSION, VERSION)
