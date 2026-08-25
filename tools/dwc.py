# -*- coding: utf-8 -*-
"""Darwin Core export, emitted inline into the instruments that record occurrences.

The kit collected the substance of a Darwin Core record from the first day -- a
name, a place, a date, a person, a count -- and wrote every one of them under its
own column headings. That is the difference between a thesis dataset that can be
deposited and one that has to be hand-mapped by whoever inherits it.

This emits Simple Darwin Core: one flat table, one row per occurrence, column
headers that are the term names themselves. Not a full archive -- no meta.xml, no
EML -- because a student with a flat file of correct terms is 90% of the way there
and a student with a half-built archive is not.

Two decisions worth stating, both from GBIF's own guidance:

  occurrenceID is a UUID, not a triplet. GBIF explicitly discourages encoding
  institution and collection codes into the identifier, because those change and
  the occurrence does not. institutionCode / collectionCode / catalogNumber are
  still emitted -- as the pointer to the physical voucher, which is what they are.

  coordinateUncertaintyInMeters is computed, and it is never zero. Zero is not a
  valid value for this term; unknown is an empty cell. It is also not GPS
  accuracy -- it is the radius of the smallest circle containing the whole
  location, so the plot's own extent goes in it before any instrument error does.
"""

VERSION = "1.2.0"

CSS = """
  /* ============ Darwin Core export v%s ============ */
  .dwc-box { background:var(--surface-2, #F3EEE0); border:1px solid var(--border, #E3DCC9);
    border-radius:14px; padding:16px; margin:14px 0; }
  .dwc-box .dwc-h { font-family:var(--head, Georgia, serif); font-weight:600; font-size:16.5px;
    margin:0 0 4px; }
  .dwc-box .dwc-p { font-size:13.5px; color:var(--muted, #6B6B5E); line-height:1.55; margin:0 0 12px; }
  /* The controls themselves are FEK components -- there is no bespoke input
     styling here on purpose, because a second styling system is how the 44px
     rule regressed twice before. */
  .dwc-box .fek-row { margin-bottom:10px; }
  .dwc-box .fek-row:last-of-type { margin-bottom:0; }
  .dwc-out { font-family:var(--mono, monospace); font-size:12px; color:var(--muted, #6B6B5E);
    margin-top:12px; line-height:1.6; }
  .dwc-out b { color:var(--ink, #23281F); }
  .dwc-warn { color:var(--danger, #B23A32); }
""" % VERSION

JS = """
/* ---- Darwin Core v%s : Simple DwC, one flat table ---- */
var DWC = (function(){
  function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g,function(c){
    return c==="&"?"&amp;":c==="<"?"&lt;":c===">"?"&gt;":c==='"'?"&quot;":"&#39;"; }); }

  /* RFC 4122 v4. crypto.getRandomValues where it exists; Math.random is a
     documented fallback rather than a silent one, because an ID that is only
     probably unique should say so. */
  var weak = false;
  function uuid(){
    var b = new Uint8Array(16), i;
    if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(b);
    else { weak = true; for(i=0;i<16;i++) b[i] = Math.floor(Math.random()*256); }
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    var h = []; for(i=0;i<16;i++) h.push((b[i]+0x100).toString(16).slice(1));
    return h.slice(0,4).join("")+"-"+h.slice(4,6).join("")+"-"+h.slice(6,8).join("")
         +"-"+h.slice(8,10).join("")+"-"+h.slice(10,16).join("");
  }
  function idsAreWeak(){ return weak; }

  function cell(v){ v = (v==null?"":String(v));
    return /[",\\n\\r]/.test(v) ? '"'+v.replace(/"/g,'""')+'"' : v; }
  function csv(rows){ return rows.map(function(r){ return r.map(cell).join(","); }).join("\\n"); }

  /* Decimal places actually typed. A coordinate written to two places carries
     about half a kilometre of latitude in it, whatever the GPS said. */
  function places(s){
    var m = String(s==null?"":s).match(/\\.(\\d+)$/);
    return m ? m[1].length : 0;
  }

  /* The point-radius method: the radius of the smallest circle containing the
     WHOLE location. Contributions are summed, which is the conservative reading
     and the one Chapman & Wieczorek describe for the simple case.
       extentM   the sampled area itself -- a 10x10 m quadrat at its centre is
                 already 7.07 m before any instrument error
       gpsM      what the receiver claimed; 30 m is GBIF's stand-in for "a GPS
                 under good conditions, accuracy not recorded"
       datum     "unknown" adds up to 5359 m globally. That is not a rounding
                 error; it is why the term exists.
     Returns null when nothing is known -- the caller must then write an EMPTY
     cell. Zero is not a valid value for this term. */
  function hasCoord(v){ return v != null && String(v).trim() !== "" && isFinite(+v); }
  function uncertainty(o){
    o = o || {};
    /* No coordinate, no uncertainty about it. An earlier version treated an
       empty field as "zero decimal places" and reported 55 km of precision
       error for a plot nobody had located yet -- a number that is not wrong so
       much as meaningless. */
    if (!hasCoord(o.latText) || !hasCoord(o.lonText)) return null;
    var lat = (o.lat==null ? 0 : +o.lat), parts = [];
    if (o.extentM > 0) parts.push(+o.extentM);
    if (o.gpsM > 0)    parts.push(+o.gpsM);
    var dp = Math.min(places(o.latText), places(o.lonText));
    if (dp >= 0) {
      var degLat = 110540, degLon = 111320 * Math.cos(lat * Math.PI/180);
      var half = 0.5 * Math.pow(10, -dp);
      var m = Math.max(half*degLat, half*Math.abs(degLon));
      if (m > 0.5) parts.push(m);
    }
    if (o.datum === "unknown") parts.push(5359);
    if (!parts.length) return null;
    var total = 0; for (var i=0;i<parts.length;i++) total += parts[i];
    return Math.max(1, Math.round(total));
  }

  /* A square plot georeferenced at its centre; a circular one at its centre. */
  function extentSquare(sideM){ return sideM > 0 ? (sideM * Math.SQRT2 / 2) : 0; }
  function extentCircle(radiusM){ return radiusM > 0 ? radiusM : 0; }

  /* Simple Darwin Core. Order follows GBIF's own tables: the terms it calls
     required first, then strongly recommended, then the voucher pointer. */
  var TERMS = ["occurrenceID","basisOfRecord","scientificName","eventDate","recordedBy",
    "decimalLatitude","decimalLongitude","geodeticDatum","coordinateUncertaintyInMeters",
    "locality","locationID","eventID","habitat","taxonRank","kingdom","vernacularName",
    "organismQuantity","organismQuantityType","occurrenceStatus","samplingProtocol",
    "sampleSizeValue","sampleSizeUnit","verbatimElevation","identifiedBy",
    "institutionCode","collectionCode","catalogNumber","associatedTaxa","associatedSequences",
    "occurrenceRemarks","informationWithheld","dataGeneralizations"];

  function table(records){
    var rows = [TERMS.slice()];
    records.forEach(function(r){
      rows.push(TERMS.map(function(t){ return r[t]==null ? "" : r[t]; }));
    });
    return csv(rows);
  }

  /* The provenance a coordinate needs before it means anything. Mounted by the
     page next to its own site fields rather than replacing them. */
  function coordControls(hostId, o){
    o = o || {};
    var h = typeof hostId === "string" ? document.getElementById(hostId) : hostId;
    if (!h) return null;
    /* The kit decided in ADR-031 that entry is one component layer, not one per
       page. A bare <select> here would have been the fifteenth hand-rolled
       control and would have quietly opted out of the 44px rule, the focus
       ring, and the contrast palette that the audits check. Three suites
       already assert "no legacy select on this page"; they were right. */
    if (typeof FEK === "undefined") {
      h.innerHTML = '<p class="dwc-p">Coordinate controls need the Field Entry Kit.</p>';
      return null;
    }
    var datum = "WGS84", gps = 0;
    h.className = "dwc-box";
    var head = document.createElement("div");
    head.innerHTML =
      '<p class="dwc-h">Where, exactly?</p>' +
      '<p class="dwc-p">A coordinate without a datum and an uncertainty is a number, not a ' +
      'location. Both are filled into the Darwin Core export below; neither is guessed.</p>';
    var dDial = FEK.dial({
      label: "geodetic datum", clearable: false, value: "WGS84",
      options: [
        { value:"WGS84",   label:"WGS84",   sub:"what a phone gives you", ramp:0 },
        { value:"NAD83",   label:"NAD83",   sub:"US survey datum",        ramp:1 },
        { value:"ETRS89",  label:"ETRS89",  sub:"European",              ramp:2 },
        { value:"unknown", label:"unknown", sub:"adds 5359 m",           ramp:5 }
      ],
      onchange: function(v){ datum = v || "WGS84"; if(o.onchange) o.onchange(); }
    });
    /* nullable, and it matters: a GPS accuracy of 0 m is not a thing anyone
       has ever measured, so an empty stepper means "not recorded" and adds
       nothing, rather than asserting perfect fix. */
    var gStep = FEK.step({
      label: "gps accuracy", unit: "m", min: 0, max: 10000, step: 1,
      nullable: true, start: 5,
      help: "Blank means not recorded. It is left out of the total rather than counted as zero.",
      onchange: function(v){ gps = (v == null ? 0 : v); if(o.onchange) o.onchange(); }
    });
    var out = document.createElement("p");
    out.className = "dwc-out"; out.id = "dwcOut";
    h.innerHTML = "";
    h.appendChild(head);
    h.appendChild(dDial.el);
    h.appendChild(gStep.el);
    h.appendChild(out);
    return {
      datum: function(){ return datum; },
      gps:   function(){ return gps; },
      setDatum: function(v){ datum = v || "WGS84"; dDial.set(datum); },
      setGps:   function(v){ gStep.set(v == null ? null : +v, true); gps = (v == null ? 0 : +v); },
      report: function(u, extentM, note){
        if (u == null) {
          out.innerHTML = 'coordinateUncertaintyInMeters will be written <b>empty</b> &mdash; ' +
            'there is no coordinate yet, or nothing about it is known. Empty means unknown; ' +
            '<b>zero would be a lie</b>, and is not a valid value for this term.';
          return;
        }
        out.innerHTML = 'coordinateUncertaintyInMeters = <b>' + u + ' m</b>' +
          (extentM ? ' &mdash; of which ' + Math.round(extentM) + ' m is the plot itself, before any instrument error' : '') +
          (note ? '. ' + esc(note) : '');
      }
    };
  }

  return { version:"%s", uuid:uuid, idsAreWeak:idsAreWeak, csv:csv, cell:cell,
           uncertainty:uncertainty, extentSquare:extentSquare, extentCircle:extentCircle,
           TERMS:TERMS, table:table, coordControls:coordControls, esc:esc, places:places,
           hasCoord:hasCoord };
})();
""" % (VERSION, VERSION)
