# -*- coding: utf-8 -*-
"""What has not left this device.

Every sheet in this kit answers two questions and has never answered the third.
It says what you have typed. Since ADR-15x it says whether that survived the tab
closing -- KEEP, one browser on one device, "not a backup", and the page says so.
Nothing anywhere says whether any of it has ever LEFT.

That is the question a field worker actually has. A reader on a link that comes
and goes -- a satellite window between ridges, an hour of town wifi, a phone that
finds a bar on the drive out -- has one thing to decide and a few minutes to
decide it: what on this device is not anywhere else? Until now the answer came
out of memory, which is the same mechanism that loses mornings.

So the outbox. It is deliberately NOT a transport: a page opened from a card over
`file://` cannot speak to a dish, a modem or a server, and a component that
pretended to would be the exact lie this kit exists to refuse. It is a ledger.
It records, per declared export, the state of the sheet AT THE MOMENT that export
actually succeeded, and compares it to the state now.

Three properties it is built around, each of which is a way the obvious version
would be wrong:

  1. IT MARKS ON SUCCESS, NEVER ON CLICK. The hook is inside the clipboard
     promise's resolve path, not the button's listener. A ledger that recorded a
     copy the browser refused would tell you your morning is safe when it is on
     no device but this one.

  2. IT IS PER EXPORT, NOT PER SHEET. A sheet with four exports whose ledger held
     one stamp would go quiet about the Darwin Core the moment you copied the CSV
     -- under-reporting, which is the direction that loses data. Each declared
     export carries its own stamp.

  3. AN EXPORT IT DOES NOT KNOW IS AN ERROR, NOT A SHRUG. `sent("csv")` from a
     sheet that never declared `csv` turns the line red and names the string.
     That is what makes a mis-wired call site loud instead of silent, which is
     the failure mode ADR-201 found the hard way when a `typeof x === "function"`
     guard hid a wrong function name for the length of a field season.

One hash for the whole kit: FEK's CRC-32, over UTF-8 bytes this file encodes
itself. Not a second implementation -- if FEK is absent the outbox REFUSES and
says so rather than falling back to something that would agree with nobody.

    python3 tools/outbox_emit.py           # rewrite every consumer
    python3 tools/outbox_emit.py --check   # report drift, write nothing
"""
VERSION = "1.0.0"

CSS = """
  /* ============ Outbox (what has not left this device) v%s ============ */
  .outbox { background:var(--surface-2, #F3EEE0); border:1px solid var(--border, #E3DCC9);
    border-radius:12px; padding:10px 13px; margin:4px 0 2px; }
  .outbox .st { font-family:var(--mono, monospace); font-size:11.5px; color:var(--muted, #6B6B5E);
    line-height:1.5; margin:0; }
  .outbox .st b { color:var(--ink, #23281F); }
  .outbox ul.pend { margin:7px 0 0; padding:0 0 0 18px; font-family:var(--mono, monospace);
    font-size:11.5px; color:var(--ink-2, #4B5344); line-height:1.6; }
  .outbox ul.pend li::marker { color:var(--muted, #6B6B5E); }
  .outbox ul.pend .why { color:var(--muted, #6B6B5E); }
  .outbox .note { margin:7px 0 0; font-size:12px; color:var(--muted, #6B6B5E); line-height:1.5; }
  .outbox.hot { border-color:var(--accent, #7A6A3A); }
  .outbox.hot .st b { color:var(--accent, #7A6A3A); }
  .outbox.bad { border-color:var(--danger, #B23A32); background:var(--danger-bg, #F6E7E5); }
  .outbox.bad .st b { color:var(--danger, #B23A32); }
  @media print { .outbox { display:none !important; } }
""" % VERSION

JS = """
/* ---- Outbox v%s : what has not left this device ---- */
var OUT = (function(){
  function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g,function(c){
    return c==="&"?"&amp;":c==="<"?"&lt;":c===">"?"&gt;":c==='"'?"&quot;":"&#39;"; }); }

  /* UTF-8 by hand rather than TextEncoder, because the two would be two code
     paths and only one of them would ever be exercised -- and because what is
     hashed has to be the same bytes on the phone in the field as on the laptop
     that checks it. Surrogate pairs are joined: a filename or a note holding an
     emoji must hash as the character it is, not as two halves. */
  function utf8(s){
    var out = [], i, c, c2, u;
    for (i = 0; i < s.length; i++) {
      c = s.charCodeAt(i);
      if (c < 0x80) { out.push(c); continue; }
      if (c < 0x800) { out.push(0xC0 | (c >> 6), 0x80 | (c & 63)); continue; }
      if (c >= 0xD800 && c <= 0xDBFF && i + 1 < s.length
          && (c2 = s.charCodeAt(i + 1)) >= 0xDC00 && c2 <= 0xDFFF) {
        u = 0x10000 + ((c - 0xD800) << 10) + (c2 - 0xDC00); i++;
        out.push(0xF0 | (u >> 18), 0x80 | ((u >> 12) & 63),
                 0x80 | ((u >> 6) & 63), 0x80 | (u & 63));
        continue;
      }
      out.push(0xE0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    }
    return out;
  }

  /* ONE hash for the kit. FEK's, because the photographs already carry CRC-32
     and a sheet whose two checksums disagreed would be a sheet nobody could
     reconcile. No fallback: a second implementation here would drift silently,
     and an outbox that hashed with something nothing else uses would report
     "unchanged" for the wrong reason. */
  function hash(o){
    if (typeof FEK === "undefined" || !FEK || typeof FEK.crc32 !== "function") return null;
    return FEK.crc32(utf8(JSON.stringify(o)));
  }

  function usable(){
    try {
      var k = "__out_probe__";
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

  function kb(n){
    if(!n) return "0 bytes";
    return n < 1024 ? (n + " bytes") : ((n/1024).toFixed(n < 10240 ? 1 : 0) + " kB");
  }

  /* One outbox per page, and the module-level sent() finds it. A page's copy
     helper is defined long before the outbox is wired, so it cannot close over
     a handle; guarding the call with `typeof` is exactly how ADR-201 lost an
     export writer for a season. Instead a send that arrives before wiring is
     REMEMBERED and reported by wire(), which turns a wiring-order mistake into
     a red line instead of a silence. */
  var LIVE = null, EARLY = [];

  function wire(o){
    o = o || {};
    var key = o.key, host = typeof o.mount === "string" ? document.getElementById(o.mount) : o.mount;
    var keep = o.keep, defs = o.exports || [], fmt = o.format == null ? 1 : o.format;
    var ok = usable(), lastErr = null, sends = {}, timer = null;

    function def(id){ var i; for(i=0;i<defs.length;i++) if(defs[i].id === id) return defs[i]; return null; }

    /* The sheet's state comes from KEEP's snapshot and from nowhere else. Two
       descriptions of "what is on this page" would be two things to keep in
       step, and the one the outbox used would be the one nobody tested. */
    function state(){
      if(!keep || typeof keep.snapshot !== "function") return undefined;
      try { return keep.snapshot(); } catch(e){ return undefined; }
    }
    function nowCrc(){
      var st = state();
      if(st === undefined) return null;
      if(st === null) return "";
      return hash(st);
    }

    function load(){
      if(!ok) return;
      try {
        var raw = window.localStorage.getItem(key);
        if(!raw) return;
        var p = JSON.parse(raw);
        if(!p || p.format !== fmt || !p.sends) return;
        var id;
        /* Only ids this sheet still declares. An export that was renamed or
           removed leaves a stamp that can never go stale and would sit in the
           ledger claiming a copy of something that no longer exists. */
        for(id in p.sends) if(p.sends.hasOwnProperty(id) && def(id)) sends[id] = p.sends[id];
      } catch(e){}
    }
    function save(){
      if(!ok) return;
      try { window.localStorage.setItem(key, JSON.stringify({format:fmt, sends:sends})); }
      catch(e){
        lastErr = (e && e.name === "QuotaExceededError")
          ? "this browser's storage is full, so the outbox will forget what has gone when the tab closes"
          : "this browser refused to keep the outbox, so it will forget what has gone when the tab closes";
      }
    }

    /* THE SHEET AS IT CAME OUT OF THE BOX IS NOT WORK.
       Three of these pages fill a date in for you, so "the snapshot is not
       null" is not the same question as "is there anything here to send", and
       an outbox that opened saying four exports were overdue on a sheet nobody
       had touched would be ignored by the second morning. So the baseline is
       the state at wire time -- UNLESS the autosave just restored something,
       in which case every export is genuinely outstanding and saying so is the
       entire point. */
    var base = null;

    function status(){
      var crc = nowCrc(), rows = [], i, d, s;
      for(i=0;i<defs.length;i++){
        d = defs[i]; s = sends[d.id];
        rows.push({ id:d.id, label:d.label, records:(d.records !== false),
                    sent:!!s, at:(s?s.at:0), bytes:(s?s.bytes:0),
                    stale: !!s && crc !== null && crc !== "" && s.crc !== crc });
      }
      var never = [], stale = [], last = 0, lastLabel = "", carry = [];
      var blank = (crc === "") || (base !== null && crc === base);
      for(i=0;i<rows.length;i++){
        if(rows[i].at > last){ last = rows[i].at; lastLabel = rows[i].label; }
        /* A copy that does not carry the sheet's records is DECLARED -- so that
           no call site can hand out bytes this ledger has never heard of -- but
           it is not counted. An outbox that nagged you to re-copy an AI prompt
           every time you added a stem would be an outbox nobody reads, and an
           outbox nobody reads is worse than none, because the page still looks
           like it is keeping track. */
        if(!rows[i].records) continue;
        carry.push(rows[i]);
        if(blank) continue;
        if(!rows[i].sent) never.push(rows[i]);
        else if(rows[i].stale) stale.push(rows[i]);
      }
      return { crc:crc, empty:blank, unreadable:(crc === null), rows:rows,
               carry:carry, never:never, stale:stale, pending:never.length + stale.length,
               last:last, lastLabel:lastLabel, err:lastErr, storing:ok };
    }

    function sent(id, bytes){
      var d = def(id);
      if(!d){
        lastErr = 'an export this sheet does not declare: "' + String(id) + '". '
                + 'Something left this device and the outbox cannot tell you what';
        paint(); return false;
      }
      var crc = nowCrc();
      if(crc === null){
        lastErr = "the outbox could not read this sheet, so it has NOT marked "
                + d.label + " as gone";
        paint(); return false;
      }
      sends[id] = { crc:crc, at:Date.now(), bytes:(bytes|0) };
      lastErr = null;
      save(); paint();
      return true;
    }

    function paint(){
      if(!host) return;
      var st = status(), msg, tone = "";
      if(st.unreadable){
        tone = " bad";
        msg = "<b>The outbox cannot read this sheet.</b> It is not tracking what has left, so "
            + "treat nothing here as sent.";
      } else if(st.err){
        tone = " bad";
        msg = "<b>" + esc(st.err) + ".</b>";
      } else if(st.empty){
        msg = "Nothing on this sheet yet. The outbox starts counting when you do.";
      } else if(st.pending === 0){
        msg = "<b>Everything here has left this device.</b> Last export "
            + esc(when(st.last)) + (st.lastLabel ? " \\u2014 " + esc(st.lastLabel) : "") + ".";
      } else {
        tone = " hot";
        msg = "<b>" + st.pending + " of " + st.carry.length + " export"
            + (st.carry.length === 1 ? "" : "s") + " on this sheet " + (st.pending === 1 ? "has" : "have")
            + " not left this device</b>"
            + (st.last ? " \\u2014 last export " + esc(when(st.last)) + "." : " at all.");
      }
      var li = "", i, r;
      for(i=0;i<st.carry.length;i++){
        r = st.carry[i];
        if(!r.sent) li += "<li>" + esc(r.label) + " <span class=\\"why\\">never</span></li>";
        else if(r.stale) li += "<li>" + esc(r.label) + " <span class=\\"why\\">changed since "
                             + esc(when(r.at)) + "</span></li>";
      }
      host.className = "outbox noprint" + tone;
      host.innerHTML =
        '<p class="st" role="status" aria-live="polite">' + msg + '</p>'
        + (li ? '<ul class="pend">' + li + '</ul>' : '')
        + '<p class="note"><b>This is a ledger, not a transport.</b> A page opened from a card '
        + 'cannot send anything by itself \\u2014 what it can do is tell you exactly what is on '
        + 'this device and nowhere else, so a few minutes of signal go on the right bytes.'
        + (st.storing ? "" : " Storage is unavailable here, so this list starts again when the tab closes.")
        + '</p>';
    }

    /* Repaint on anything that could have changed the sheet, debounced. No page
       wiring: a page that gained a control would otherwise have to remember to
       tell the outbox, and the one it forgot would be the one that went stale
       quietly. */
    function touch(){
      if(timer) clearTimeout(timer);
      timer = setTimeout(function(){ timer = null; paint(); }, o.debounce == null ? 400 : o.debounce);
    }
    try {
      ["input", "change", "click"].forEach(function(ev){
        document.addEventListener(ev, touch, true); });
    } catch(e){}

    load();
    base = (keep && typeof keep.restored === "function" && keep.restored()) ? null : nowCrc();
    var h = { sent:sent, status:status, paint:paint, touch:touch,
              usable:function(){ return ok; }, error:function(){ return lastErr; } };
    LIVE = h;
    if(EARLY.length){
      /* An export that happened before the outbox existed is a wiring-order
         fault, and it is reported rather than replayed: the stamp it would have
         taken is the state at a moment that has already gone. */
      lastErr = "an export left this device before the outbox was wired ("
              + EARLY.map(function(e){ return String(e[0]); }).join(", ") + ")";
      EARLY = [];
    }
    paint();
    return h;
  }

  return { version:"%s", wire:wire, utf8:utf8, hash:hash,
           sent:function(id, bytes){
             if(!LIVE){ EARLY.push([id, bytes]); return false; }
             return LIVE.sent(id, bytes);
           },
           status:function(){ return LIVE ? LIVE.status() : null; } };
})();
""" % (VERSION, VERSION)
