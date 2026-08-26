# -*- coding: utf-8 -*-
"""Greenhouse engine: psychrometrics, light integrals, energy and yield economics.

Four calculations, one module, because they all read from the same log and the
interesting numbers are the ones that cross between them -- grams per kilowatt
hour is a light question and an energy question and a yield question at once.

WHAT IS COMPUTED, AND FROM WHOSE DEFINITION

  VPD      Buck (1981), the equation NOAA and most controllers use:
             es(T) = 0.61121 * exp((18.678 - T/234.5) * (T / (257.14 + T)))  kPa
           Leaf VPD, not air VPD -- the two differ and a lot of published
           target bands do not say which they mean. See vpd() for the argument.

  DLI      DLI = PPFD * hours * 0.0036   mol/m2/d
           An integral, not a formula: 1 umol/m2/s for 1 s is 1e-6 mol, and
           3600 s/h gives the 0.0036. Computed by trapezoid over the log when
           PPFD varies, so a dimming schedule integrates correctly.

  kWh      Trapezoid over the power log. A controller that samples unevenly --
           and they all do -- makes a rectangle sum wrong by however much the
           interval drifted. The trapezoid is right for any spacing.

  g/W      TWO different numbers with the same name, and the kit reports both:
             g/W   = yield / rated fixture watts       -- the industry figure
             g/kWh = yield / energy actually consumed  -- the honest one
           A fixture run at 60% for half the cycle has the same g/W as one run
           flat out and roughly triple the g/kWh. Anyone comparing g/W across
           two rooms with different duty cycles is comparing nothing.

WHAT IS REFUSED

  Lumens -> PPFD has no fixed conversion. Lumens weight a spectrum by the human
  photopic curve, which peaks at 555 nm where chlorophyll is nearly blind; PPFD
  counts photons 400-700 nm flat. The ratio between them is a property of the
  SPECTRUM, so the factor differs by a factor of three across common horticultural
  fixtures. The engine will convert if you give it a factor, it names the factor
  it used, and it refuses to pick one for you. See lumensToPPFD().

    python3 tools/gh_emit.py           # rewrite every consumer
    python3 tools/gh_emit.py --check   # report drift, write nothing
"""
VERSION = "1.0.0"

CSS = """
  /* ============ Greenhouse engine v__GHVER__ ============ */
  .gh-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px;
    margin:12px 0 2px; }
  .gh-stat { border:2px solid var(--border); border-radius:14px; padding:12px 14px;
    background:var(--surface); }
  .gh-stat .v { font:800 26px var(--head); font-variant-numeric:tabular-nums; line-height:1.05;
    color:var(--ink); }
  .gh-stat .v small { font:600 13px var(--mono); color:var(--muted); margin-left:3px; }
  .gh-stat .l { font:700 11.5px var(--body); color:var(--muted); margin-top:4px; line-height:1.35; }
  .gh-stat .d { font:600 11px var(--mono); margin-top:3px; }
  .gh-stat.good { border-color:var(--ramp-2); } .gh-stat.good .v { color:var(--ramp-2); }
  .gh-stat.warn { border-color:var(--ramp-3); } .gh-stat.warn .v { color:#8a6508; }
  .gh-stat.bad  { border-color:var(--ramp-5); } .gh-stat.bad  .v { color:var(--ramp-5); }
  .gh-stat.cold { border-color:var(--ramp-0); } .gh-stat.cold .v { color:var(--ramp-0); }
  .gh-stat.none .v { color:var(--muted); font-size:20px; }

  .gh-chart { display:block; width:100%; height:auto; background:var(--surface);
    border:1px solid var(--border); border-radius:12px; margin-top:10px; }
  .gh-chart text { font-family:var(--mono); }

  .gh-src { display:grid; gap:9px; margin-top:8px; }
  .gh-srow { border:1.5px solid var(--border); border-radius:13px; padding:11px 13px;
    background:var(--surface); }
  .gh-srow .hd { display:flex; align-items:center; justify-content:space-between; gap:9px;
    flex-wrap:wrap; }
  .gh-srow .nm { font-family:var(--head); font-weight:700; font-size:15px; }
  .gh-srow .st { font:700 10.5px var(--mono); letter-spacing:.05em; text-transform:uppercase;
    border-radius:999px; padding:3px 9px; border:1px solid var(--border); white-space:nowrap; }
  .gh-srow .st.ready { border-color:var(--ramp-2); color:var(--ramp-2); background:var(--soft); }
  .gh-srow .st.off   { border-color:var(--border); color:var(--muted); }
  .gh-srow .st.live  { border-color:var(--ramp-0); color:var(--ramp-0); background:#E6EEF3; }
  .gh-srow .wh { font-size:12.5px; color:var(--muted); line-height:1.5; margin-top:6px; }
  .gh-srow.unavailable { opacity:.72; }
  /* ============ /Greenhouse engine v__GHVER__ ============ */
"""

JS = """
/* ---------- Greenhouse engine v__GHVER__ ---------- */
var GH = (function(){
  "use strict";

  /* ================= psychrometrics ================= */

  /* Buck (1981) saturation vapour pressure over water, kPa, T in degrees C.
     Chosen over Tetens and over Magnus because it is what NOAA publishes and
     what most grow controllers implement, so a number computed here matches
     the number on the controller's own screen. Buck is within 0.05% of the
     reference formulation from -20 to +50 C, which is the whole range that
     matters here and then some. */
  function svp(t){
    return 0.61121 * Math.exp((18.678 - t/234.5) * (t / (257.14 + t)));
  }

  /* Vapour pressure deficit, kPa.

     THERE ARE TWO VPDs AND THE PUBLISHED TARGET BANDS RARELY SAY WHICH.

       air VPD  = es(T_air)  - es(T_air) * RH/100
       leaf VPD = es(T_leaf) - es(T_air) * RH/100

     A leaf transpiring under a lamp sits BELOW air temperature -- typically
     1-3 C below with airflow, less in still air, and it can sit above air
     temperature under a very hot fixture with no movement. A cooler leaf has a
     lower saturation pressure, so a LARGER offset gives a LOWER VPD.

     Because es() is exponential the size of that shift is not small. Swept
     across 18-32 C and 40-85% RH, a 2 C offset moves VPD by 0.25 to 0.51 kPa
     -- median 0.36. The vegetative band is 0.4 kPa wide. So the offset alone
     is worth between 61 and 128 percent of the whole band: at the top of that range
     it is wider than the band it is being compared against. This is not a
     rounding difference, it is the difference between "in band" and not, and
     a target band quoted without its leaf assumption is not a number.

     This returns LEAF VPD, and takes the offset explicitly rather than
     assuming one. Pass 0 and you get air VPD. The page states which it shows. */
  function vpd(tAir, rh, leafOffset){
    if(tAir==null || rh==null) return null;
    var off = (leafOffset==null) ? 0 : leafOffset;
    var tLeaf = tAir - off;
    var avp = svp(tAir) * (rh/100);
    return svp(tLeaf) - avp;
  }

  /* Dew point by inverting Buck numerically. A closed-form inverse of Buck
     does not exist; bisection over a bracket that covers every terrestrial
     condition converges to well under 0.01 C in 50 steps and cannot diverge. */
  function dewPoint(tAir, rh){
    if(tAir==null || rh==null || rh<=0) return null;
    var target = svp(tAir) * (rh/100);
    var lo=-80, hi=tAir;
    for(var i=0;i<60;i++){
      var mid=(lo+hi)/2;
      if(svp(mid) < target) lo=mid; else hi=mid;
    }
    return (lo+hi)/2;
  }

  /* Absolute humidity, g/m3 -- the number that tells you what your dehumidifier
     actually has to remove. RH alone does not, because the same RH at two
     temperatures is two different amounts of water. */
  function absHumidity(tAir, rh){
    if(tAir==null || rh==null) return null;
    var e = svp(tAir) * (rh/100) * 1000;         /* Pa */
    return 2.16679 * e / (tAir + 273.15);        /* g/m3 */
  }

  /* Target bands, kPa, LEAF VPD. These are the ranges in common circulation
     among growers and equipment makers; they are not a controlled result and
     the page says so. Stage boundaries are soft. */
  var BANDS = [
    {id:"clone",  label:"clones / seedlings", lo:0.4, hi:0.8},
    {id:"veg",    label:"vegetative",         lo:0.8, hi:1.2},
    {id:"early",  label:"early flower",       lo:1.0, hi:1.4},
    {id:"late",   label:"late flower",        lo:1.2, hi:1.6}
  ];
  function band(id){
    for(var i=0;i<BANDS.length;i++) if(BANDS[i].id===id) return BANDS[i];
    return BANDS[1];
  }
  function inBand(v, b){ return v!=null && v>=b.lo && v<=b.hi; }

  /* ================= light ================= */

  /* DLI, mol/m2/d, from a constant PPFD held for `hours`.
       1 umol/m2/s * 3600 s/h * h / 1e6 = PPFD * h * 0.0036 */
  function dli(ppfd, hours){
    if(ppfd==null || hours==null) return null;
    return ppfd * hours * 0.0036;
  }

  /* DLI from a LOG of PPFD samples -- the integral rather than the formula.
     A dimming ramp, a cloudy afternoon or a two-stage photoperiod all make the
     constant-PPFD version wrong, and by more than people expect. Trapezoid,
     because controller sample spacing is never uniform. */
  function dliFromLog(rows, tKey, ppfdKey){
    var pts = rows.filter(function(r){ return r[tKey]!=null && r[ppfdKey]!=null; })
                  .sort(function(a,b){ return a[tKey]-b[tKey]; });
    if(pts.length<2) return null;
    var umol = 0;                       /* umol/m2 accumulated */
    for(var i=1;i<pts.length;i++){
      var dt = (pts[i][tKey] - pts[i-1][tKey]) / 1000;   /* ms -> s */
      umol += (pts[i][ppfdKey] + pts[i-1][ppfdKey]) / 2 * dt;
    }
    var days = (pts[pts.length-1][tKey] - pts[0][tKey]) / 86400000;
    if(days<=0) return null;
    return (umol / 1e6) / days;
  }

  /* Lumens to PPFD. THE ENGINE WILL NOT PICK THE FACTOR FOR YOU.

     Lumens are photons weighted by the human photopic response, which peaks at
     555 nm -- green, where a leaf reflects most and absorbs least. PPFD counts
     every photon from 400-700 nm equally. The ratio between the two is a
     property of the fixture's SPECTRUM and nothing else, and across the lamps
     people actually own it spans roughly 15 to 70 lux per umol/m2/s.

     Handing back a number from a default factor would be inventing three
     significant figures out of a guess. This returns the conversion WITH the
     factor used, so the number never travels without it. */
  function lumensToPPFD(lux, luxPerUmol){
    if(lux==null || luxPerUmol==null || luxPerUmol<=0)
      return {value:null, factor:luxPerUmol||null,
              note:"no conversion: lux to PPFD depends entirely on the fixture spectrum, "+
                   "and no default is defensible"};
    return {value: lux/luxPerUmol, factor: luxPerUmol,
            note:"converted at "+luxPerUmol+" lux per umol/m2/s -- a property of YOUR fixture's "+
                 "spectrum, not a constant"};
  }
  /* Rough published factors, offered as a starting point and labelled as one. */
  var LUX_FACTORS = [
    {id:"sun",   label:"daylight / sun",        f:54},
    {id:"hps",   label:"HPS",                   f:82},
    {id:"mh",    label:"metal halide",          f:71},
    {id:"cmh",   label:"CMH / LEC 3100K",       f:64},
    {id:"led3k", label:"white LED ~3000K",      f:62},
    {id:"led4k", label:"white LED ~4000K",      f:65},
    {id:"led5k", label:"white LED ~5000K",      f:69},
    {id:"blur",  label:"blurple LED (red/blue)",f:24}
  ];

  /* ================= energy ================= */

  /* Energy in kWh by trapezoid over a power log. Uneven spacing is the norm --
     a controller that logs "every 5 minutes" drops samples under load -- and a
     rectangle sum silently attributes the gap to whichever endpoint it used.
     Returns null rather than 0 for a log too short to integrate: zero is an
     answer, and "I cannot answer" is not zero. */
  function kWh(rows, tKey, wKey){
    var pts = rows.filter(function(r){ return r[tKey]!=null && r[wKey]!=null; })
                  .sort(function(a,b){ return a[tKey]-b[tKey]; });
    if(pts.length<2) return null;
    var wh = 0;
    for(var i=1;i<pts.length;i++){
      var dtH = (pts[i][tKey] - pts[i-1][tKey]) / 3600000;   /* ms -> h */
      wh += (pts[i][wKey] + pts[i-1][wKey]) / 2 * dtH;
    }
    return wh/1000;
  }

  /* The simple case: a fixture at a fixed draw on a timer. */
  function kWhFromSchedule(watts, hoursPerDay, days){
    if(watts==null||hoursPerDay==null||days==null) return null;
    return watts * hoursPerDay * days / 1000;
  }

  function cost(kwh, ratePerKWh){
    if(kwh==null||ratePerKWh==null) return null;
    return kwh * ratePerKWh;
  }

  /* ================= yield economics ================= */

  /* Both g/W figures, with the difference stated rather than buried.
     ratedW  -- what the fixture is sold as
     kwh     -- what the meter actually saw over the whole cycle
     days    -- cycle length, needed to turn kWh back into an average draw */
  function economics(grams, ratedW, kwh, days, ratePerKWh){
    var out = {grams:grams, ratedW:ratedW, kwh:kwh, days:days,
               gPerW:null, gPerKWh:null, costTotal:null, costPerGram:null,
               avgW:null, dutyVsRated:null};
    if(grams==null) return out;
    if(ratedW) out.gPerW = grams/ratedW;
    if(kwh)    out.gPerKWh = grams/kwh;
    if(kwh!=null && days) out.avgW = kwh*1000/(days*24);
    if(out.avgW!=null && ratedW) out.dutyVsRated = out.avgW/ratedW;
    if(kwh!=null && ratePerKWh!=null){
      out.costTotal = kwh*ratePerKWh;
      if(grams>0) out.costPerGram = out.costTotal/grams;
    }
    return out;
  }

  /* ================= trend ================= */

  /* Ordinary least squares on (x,y). Returns slope, intercept, r2 and n.
     The slope is the derivative the trend question is actually asking for --
     "is my VPD drifting" is dVPD/dt, and eyeballing a chart answers it badly.
     r2 is returned alongside because a slope from a cloud of points is a
     number with no meaning, and reporting one without the other is how a
     trend line becomes a claim it cannot support. */
  function ols(xs, ys){
    var n=0, sx=0, sy=0, sxx=0, sxy=0, syy=0;
    for(var i=0;i<xs.length;i++){
      if(xs[i]==null||ys[i]==null||!isFinite(xs[i])||!isFinite(ys[i])) continue;
      n++; sx+=xs[i]; sy+=ys[i]; sxx+=xs[i]*xs[i]; sxy+=xs[i]*ys[i]; syy+=ys[i]*ys[i];
    }
    if(n<3) return {n:n, slope:null, intercept:null, r2:null,
                    why:"fewer than three usable points"};
    var d = n*sxx - sx*sx;
    if(Math.abs(d) < 1e-12) return {n:n, slope:null, intercept:null, r2:null,
                                    why:"every x is the same -- no slope exists"};
    var slope = (n*sxy - sx*sy)/d;
    var intercept = (sy - slope*sx)/n;
    var ssTot = syy - sy*sy/n;
    var ssRes = 0;
    for(var j=0;j<xs.length;j++){
      if(xs[j]==null||ys[j]==null||!isFinite(xs[j])||!isFinite(ys[j])) continue;
      var e = ys[j] - (intercept + slope*xs[j]);
      ssRes += e*e;
    }
    var r2 = ssTot>1e-12 ? 1 - ssRes/ssTot : null;
    return {n:n, slope:slope, intercept:intercept, r2:r2, why:null};
  }

  /* Fraction of LOGGED TIME outside a band, by trapezoid on the indicator --
     not the fraction of samples, which is a different question whenever
     sampling is uneven. Ten samples in one bad hour and one sample per good
     hour would read as 50% of samples and about 4% of time. */
  function timeOutside(rows, tKey, vKey, lo, hi){
    var pts = rows.filter(function(r){ return r[tKey]!=null && r[vKey]!=null; })
                  .sort(function(a,b){ return a[tKey]-b[tKey]; });
    if(pts.length<2) return null;
    var out=0, tot=0;
    for(var i=1;i<pts.length;i++){
      var dt = pts[i][tKey]-pts[i-1][tKey];
      if(dt<=0) continue;
      var a = (pts[i-1][vKey]<lo || pts[i-1][vKey]>hi) ? 1 : 0;
      var b = (pts[i][vKey]<lo   || pts[i][vKey]>hi)   ? 1 : 0;
      out += (a+b)/2*dt; tot += dt;
    }
    return tot>0 ? out/tot : null;
  }

  /* ================= ingest plugins ================= */

  /* A registry rather than one hard-wired path, because no two growers have
     the same kit. A source declares what it is, whether it can run HERE (in
     this browser, on this page, right now), and how to read. A source that
     cannot run says so with a reason -- it does not silently return nothing,
     which is how a dashboard ends up confidently displaying an empty room. */
  var sources = [];
  function register(src){
    if(!src || !src.id) throw new Error("a source needs an id");
    if(typeof src.read !== "function") throw new Error(src.id+": needs a read()");
    var s = {
      id: src.id,
      name: src.name || src.id,
      kind: src.kind || "file",          /* file | poll | serial | manual | demo */
      note: src.note || "",
      needs: src.needs || "",
      available: typeof src.available === "function"
                 ? src.available
                 : function(){ return {ok:true, why:""}; },
      read: src.read
    };
    sources = sources.filter(function(x){ return x.id !== s.id; });
    sources.push(s);
    return s;
  }
  function list(){
    return sources.map(function(s){
      var a;
      try { a = s.available(); } catch(e){ a = {ok:false, why:"probe threw: "+e.message}; }
      return {id:s.id, name:s.name, kind:s.kind, note:s.note, needs:s.needs,
              ok:!!(a&&a.ok), why:(a&&a.why)||""};
    });
  }
  function get(id){
    for(var i=0;i<sources.length;i++) if(sources[i].id===id) return sources[i];
    return null;
  }
  function clear(){ sources = []; }

  /* ================= reading rows ================= */

  /* Column aliases. Every controller names things differently and nobody is
     going to rename their CSV headers by hand. Matching is case- and
     punctuation-insensitive on the whole header, then on a contained word. */
  var ALIASES = {
    t:    ["time","timestamp","datetime","date","ts","recorded","logged at"],
    temp: ["temp","temperature","air temp","tempc","temp c","temp f","t","tair"],
    rh:   ["rh","humidity","relative humidity","hum","rh%"],
    ppfd: ["ppfd","par","umol","photon flux","ppf"],
    lux:  ["lux","lumens","illuminance","light"],
    w:    ["w","watts","power","load","draw","p"],
    co2:  ["co2","carbon dioxide","ppm"],
    leaf: ["leaf","leaf temp","leaftemp","canopy temp"]
  };
  function norm(s){ return String(s==null?"":s).toLowerCase().replace(/[^a-z0-9%]+/g," ").trim(); }
  function mapHeaders(headers){
    var map = {}, used = {};
    Object.keys(ALIASES).forEach(function(field){
      for(var i=0;i<headers.length;i++){
        if(used[i]) continue;
        var h = norm(headers[i]);
        if(ALIASES[field].indexOf(h) >= 0){ map[field]=i; used[i]=1; return; }
      }
      for(var j=0;j<headers.length;j++){
        if(used[j]) continue;
        var hh = " "+norm(headers[j])+" ";
        for(var k=0;k<ALIASES[field].length;k++){
          if(hh.indexOf(" "+ALIASES[field][k]+" ") >= 0){ map[field]=j; used[j]=1; return; }
        }
      }
    });
    return map;
  }

  /* A CSV parser that handles quoted fields, because controller exports put
     commas inside timestamps and a split(",") silently shifts every column
     after the first quoted one. */
  function parseCSV(text){
    var rows=[], row=[], cur="", q=false;
    for(var i=0;i<text.length;i++){
      var c=text[i];
      if(q){
        if(c==='"'){ if(text[i+1]==='"'){ cur+='"'; i++; } else q=false; }
        else cur+=c;
      } else if(c==='"'){ q=true; }
      else if(c===","){ row.push(cur); cur=""; }
      else if(c==="\\n"){ row.push(cur); cur=""; rows.push(row); row=[]; }
      else if(c==="\\r"){ /* skip */ }
      else cur+=c;
    }
    if(cur!=="" || row.length){ row.push(cur); rows.push(row); }
    return rows.filter(function(r){ return r.length>1 || (r[0]||"").trim()!==""; });
  }

  function num(v){
    if(v==null) return null;
    var s=String(v).replace(/[^\\d.eE+-]/g,"");
    if(s==="" ) return null;
    var n=parseFloat(s);
    return isFinite(n) ? n : null;
  }
  function stamp(v){
    if(v==null || v==="") return null;
    var n = Number(v);
    /* A bare number is an epoch. Seconds and milliseconds are told apart by
       magnitude: anything under 1e11 as a timestamp would be 1973 in ms. */
    if(isFinite(n) && String(v).trim()!==""&& /^[\\d.]+$/.test(String(v).trim()))
      return n < 1e11 ? n*1000 : n;
    var d = Date.parse(String(v).replace(" ","T"));
    if(!isNaN(d)) return d;
    d = Date.parse(String(v));
    return isNaN(d) ? null : d;
  }

  /* Turn a parsed CSV into engine rows. Reports what it could NOT map, because
     a silently dropped column is a chart that is quietly missing a variable. */
  function rowsFromCSV(text, opts){
    opts = opts || {};
    var grid = parseCSV(text);
    if(grid.length<2) return {rows:[], map:{}, headers:[], unmapped:[],
                              why:"fewer than two lines -- no header plus data"};
    var headers = grid[0].map(function(h){ return String(h).trim(); });
    var map = mapHeaders(headers);
    var fahrenheit = !!opts.fahrenheit;
    var rows = [];
    for(var i=1;i<grid.length;i++){
      var g=grid[i], r={};
      if(map.t   != null) r.t    = stamp(g[map.t]);
      if(map.temp!= null){ var tv=num(g[map.temp]);
        r.temp = (tv!=null && fahrenheit) ? (tv-32)*5/9 : tv; }
      if(map.leaf!= null){ var lv=num(g[map.leaf]);
        r.leaf = (lv!=null && fahrenheit) ? (lv-32)*5/9 : lv; }
      if(map.rh  != null) r.rh   = num(g[map.rh]);
      if(map.ppfd!= null) r.ppfd = num(g[map.ppfd]);
      if(map.lux != null) r.lux  = num(g[map.lux]);
      if(map.w   != null) r.w    = num(g[map.w]);
      if(map.co2 != null) r.co2  = num(g[map.co2]);
      if(r.t==null) continue;
      rows.push(r);
    }
    var mappedIdx = {};
    Object.keys(map).forEach(function(k){ mappedIdx[map[k]]=1; });
    var unmapped = headers.filter(function(h,i){ return !mappedIdx[i]; });
    return {rows:rows, map:map, headers:headers, unmapped:unmapped,
            why: rows.length ? null : "no row carried a readable timestamp"};
  }

  /* ================= summary ================= */

  function summarise(rows, opts){
    opts = opts || {};
    var off  = opts.leafOffset==null ? 2 : opts.leafOffset;
    var b    = band(opts.stage || "veg");
    var withV = rows.map(function(r){
      var o = {};
      for(var k in r) if(Object.prototype.hasOwnProperty.call(r,k)) o[k]=r[k];
      /* A measured leaf temperature beats an assumed offset every time. */
      o.vpd = (o.leaf!=null && o.rh!=null)
              ? svp(o.leaf) - svp(o.temp)*(o.rh/100)
              : vpd(o.temp, o.rh, off);
      o.dew = dewPoint(o.temp, o.rh);
      o.ah  = absHumidity(o.temp, o.rh);
      return o;
    });
    var vs = withV.map(function(r){ return r.vpd; }).filter(function(v){ return v!=null; });
    var ts = withV.map(function(r){ return r.t; });
    var span = (ts.length>1) ? (Math.max.apply(null,ts)-Math.min.apply(null,ts)) : 0;
    return {
      rows: withV,
      n: withV.length,
      spanDays: span/86400000,
      band: b,
      leafOffsetUsed: off,
      measuredLeaf: withV.some(function(r){ return r.leaf!=null; }),
      vpdMean: vs.length ? vs.reduce(function(a,c){return a+c;},0)/vs.length : null,
      vpdMin: vs.length ? Math.min.apply(null,vs) : null,
      vpdMax: vs.length ? Math.max.apply(null,vs) : null,
      outsideBand: timeOutside(withV, "t", "vpd", b.lo, b.hi),
      kwh: kWh(withV, "t", "w"),
      dli: dliFromLog(withV, "t", "ppfd"),
      trendVPD: ols(withV.map(function(r){ return r.t/86400000; }),
                    withV.map(function(r){ return r.vpd; }))
    };
  }

  return { version:"__GHVER__",
           svp:svp, vpd:vpd, dewPoint:dewPoint, absHumidity:absHumidity,
           BANDS:BANDS, band:band, inBand:inBand,
           dli:dli, dliFromLog:dliFromLog, lumensToPPFD:lumensToPPFD, LUX_FACTORS:LUX_FACTORS,
           kWh:kWh, kWhFromSchedule:kWhFromSchedule, cost:cost, economics:economics,
           ols:ols, timeOutside:timeOutside,
           register:register, list:list, get:get, clear:clear,
           parseCSV:parseCSV, mapHeaders:mapHeaders, rowsFromCSV:rowsFromCSV,
           summarise:summarise };
})();
/* ---------- /Greenhouse engine v__GHVER__ ---------- */
"""


def render_css():
    """CSS with the version stamped in.

    This used to be %-formatting, which broke the moment the module carried
    prose about percentages -- "40-85% RH" in a docstring and "width:100%" in a
    rule are both format directives to Python, and escaping them by regex
    double-escaped the ones already escaped. A token nothing else can look like
    has no such failure mode.
    """
    return CSS.replace("__GHVER__", VERSION)


def render_js():
    return JS.replace("__GHVER__", VERSION)
