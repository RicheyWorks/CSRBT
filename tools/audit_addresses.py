# -*- coding: utf-8 -*-
"""Whether a control's name outlives pressing it (ADR-239).

ADR-188 gave every control an ADDRESS -- the page's own name for it, `@forage`,
`@rCov/4`, `#tAdd` -- because an index renumbers the moment the page rebuilds and
four blind operators had spent their trials counting buttons. The address is
checked, when it is published, to resolve back to its control. It was never
checked a moment later. This audit presses each control the way an operator
does and asks the one question the scheme exists to answer: DOES THE NAME I WAS
JUST GIVEN STILL NAME THE THING I JUST PRESSED?

    HELD      the old address resolves, through the door's own resolver, to
              the control that was pressed (the same node, or its rebuilt
              successor under the same host and the same name)
    GONE      the control left the page -- a delete, a picker collapsing to its
              pick, a key moving to its next couplet. Nothing to name.
    RENAMED   the control is still there and its name is not: the label
              carried a value the press changed. The field notebook's tally
              card read `species-a0`, and one tap made it `species-a1` -- an
              address that lasts exactly one press, on the page's primary
              data-entry control. The worklist.
    SHADOWED  the old address now resolves to a DIFFERENT control while the
              pressed one is still on the page. Worse than stale: a caller
              acting on it presses the wrong thing and is told ok.

"Still there" is decided by the node itself where the page kept it (the pressed
element is marked before the press), and by the rebuilt control at the same
host whose label differs from the old one only in its digits where the page
re-rendered it -- which is exactly the shape of a label that carries a count.
A rebuilt list whose labels changed in their words (a key's next couplet) is
GONE, not RENAMED: those are different controls, and the bias is toward not
crying wolf.

Every activate-kind control with an address (an id or a name -- a stamped
index is not an address a page owns) is pressed once, in one session per page,
in document order, and controls a press brings into being (a quadrat's
steppers after "+ Add quadrat") join the walk. An id cannot carry a count, but
pressing it is how the controls behind it come into being, and an id can be
shadowed as well as a name can. The press goes
through the door (`PagePlugin.execute`) and so does the reading
(`PagePlugin._resolve`), so this measures what a client gets, not what a
private reading of the DOM would say.

    python3 tools/audit_addresses.py                 # every page; exit 1 on any RENAMED or SHADOWED
    python3 tools/audit_addresses.py --page field-notebook.html
    python3 tools/audit_addresses.py --json
"""
import argparse, glob, io, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "verify"))
sys.path.insert(0, HERE)
import harness_plugin_page as PP     # noqa: E402

LEDGER = os.path.join(HERE, "address_ledger.json")
KINDS = tuple(PP.POOL_KINDS["activate"])     # what the door's activate acts on, not a second list
CAP = 400                 # presses per page; no page of the kit comes near it
BAD = ("renamed", "shadowed")

MARK = r"""(sel) => {
  document.querySelectorAll('[data-audit-mark]').forEach(e => e.removeAttribute('data-audit-mark'));
  const e = document.querySelector('[data-h="' + sel + '"]');
  if (e) e.setAttribute('data-audit-mark', '1');
  return !!e; }"""

# After the press: where is the pressed node, what is it called now, and which
# control sits where the old address now points.
AFTER = "([sel]) => {" + PP.LABEL_FN + PP.ADDR_FN + r"""
  const rows = _rows(), idx = _index(rows), v = _version(rows);
  const m = document.querySelector('[data-audit-mark]');
  const kept = !!(m && m.isConnected);
  const mr = kept ? rows.filter(x => x.e === m)[0] : null;
  const at = sel ? rows.filter(x => x.selector === sel)[0] : null;
  return { kept: kept,
           label: kept ? _label(m) : null,
           address: mr ? _address(mr, idx, v) : null,
           resolvedIsMark: !!(at && kept && at.e === m),
           resolvedLabel: at ? at.label : null, resolvedHost: at ? at.host : null,
           resolvedId: at ? at.id : null,
           hosts: rows.map(x => [x.host, x.label, _address(x, idx, v)]) };
}"""


def digitless(s):
    return re.sub(r"\d+", "#", s or "")


def classify(before, resolved, after):
    """One press -> (verdict, the name it has now or None).

    `before` is the control as the snapshot published it; `resolved` is the
    selector the old address resolves to after the press (None when it
    resolves to nothing); `after` is AFTER's reading."""
    host, label = before.get("host"), before.get("label")
    if resolved is not None:
        if after["kept"]:
            if after["resolvedIsMark"]:
                return "held", None
            return "shadowed", after.get("address")
        # rebuilt: the successor is the control carrying the same id, or under
        # the same host with the same name -- which is what the resolver found.
        # An id is the page saying "this is the same control" across a rebuild
        # (the phenology tracker's next-plant button is rebuilt reading the
        # next plant's number, and is still #pNext).
        if before.get("id") and (before.get("address") or "") == "#" + before["id"] \
                and after.get("resolvedId") == before["id"]:
            return "held", None
        if after.get("resolvedHost") == host and after.get("resolvedLabel") == label:
            return "held", None
        return "shadowed", None
    if after["kept"]:
        return "renamed", after.get("address") or after.get("label")
    # rebuilt and not found by name: a successor whose label differs from the
    # old one only in its digits is the same control carrying a new count
    for h, l, addr in after.get("hosts") or ():
        if h == host and l != label and digitless(l) == digitless(label) and re.search(r"\d", label or ""):
            return "renamed", addr
    return "gone", None


def measure_page(plug, pg, name, reopen):
    """Press every name-addressed activate control once; one row per press."""
    rows, seen = [], set()
    for _ in range(CAP):
        s = plug.observe()
        if not s.get("ready"):
            break
        todo = [c for c in s["controls"]
                if c["kind"] in KINDS and (c.get("address") or "")[:1] in ("@", "#")
                and c["address"] not in seen]
        if not todo:
            break
        c = todo[0]
        seen.add(c["address"])
        pg.evaluate(MARK, c["selector"])
        try:
            plug.execute("activate", {"selector": c["selector"]})
        except Exception as e:
            rows.append({"address": c["address"], "verdict": "unpressed", "why": str(e)[:100]})
            continue
        if not pg.url.split("/")[-1].split("#")[0].split("?")[0] == name:
            rows.append({"address": c["address"], "verdict": "gone", "why": "navigated"})
            reopen()
            continue
        try:
            sel = plug._resolve(c["address"])
        except Exception:
            sel = None
        after = pg.evaluate(AFTER, [sel])
        v, now = classify(c, sel, after)
        row = {"address": c["address"], "verdict": v}
        if now:
            row["now"] = now
            seen.add(now)           # the same control under its new name is not a new control
        rows.append(row)
    return rows


def summarise(rows):
    out = {"pressed": len([r for r in rows if r["verdict"] != "unpressed"])}
    for k in ("held", "gone", "renamed", "shadowed", "unpressed"):
        out[k] = len([r for r in rows if r["verdict"] == k])
    for k in BAD:
        out[k + "_names"] = ["%s -> %s" % (r["address"], r.get("now") or "?")
                             for r in rows if r["verdict"] == k]
    return out


def docs_dir():
    return os.environ.get("CSRBT_DOCS_DIR") or os.path.join(ROOT, "docs")


def pages():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(docs_dir(), "*.html")))


def walk(names=None, docs=None):
    from playwright.sync_api import sync_playwright
    docs = docs or docs_dir()
    names = names or pages()
    out = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for name in names:
            ctx = b.new_context()
            pg = ctx.new_page()
            url = "file://" + os.path.join(docs, name).replace(os.sep, "/")

            def reopen():
                pg.goto(url, wait_until="domcontentloaded")
                pg.wait_for_timeout(300)
            try:
                reopen()
                plug = PP.PagePlugin(pg, name)
                rows = measure_page(plug, pg, name, reopen)
                out[name] = dict(summarise(rows), rows=rows)
            except Exception as e:
                out[name] = {"error": "%s: %s" % (type(e).__name__, str(e)[:160])}
            ctx.close()
        b.close()
    return out


def load():
    if os.path.isfile(LEDGER):
        try:
            return json.load(io.open(LEDGER, encoding="utf-8"))
        except ValueError:
            pass
    return {"_comment": "Written by tools/audit_addresses.py (ADR-239). Per page: the controls "
                        "pressed by their name, and whether that name still named them after the "
                        "press. RENAMED and SHADOWED are defects; the gate is zero.",
            "pages": {}}


def save(state):
    io.open(LEDGER, "w", encoding="utf-8").write(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def problems(got):
    return sorted(n for n, r in got.items() if r.get("error") or any(r.get(k) for k in BAD))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="one page")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-ledger", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()
    got = walk([a.page] if a.page else None)
    if a.json:
        print(json.dumps(got, indent=1, sort_keys=True, ensure_ascii=False))
        return 1 if problems(got) else 0
    if not a.no_ledger:
        state = load()
        led = state.setdefault("pages", {})
        for n, r in got.items():
            led[n] = dict((k, v) for k, v in r.items() if k != "rows")
            led[n]["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save(state)
    print("%-30s %7s %6s %6s %8s %8s   %s" % ("PAGE", "PRESSED", "HELD", "GONE", "RENAMED", "SHADOWED", ""))
    print("-" * 100)
    for n in sorted(got):
        r = got[n]
        if r.get("error"):
            print("%-30s %s" % (n, r["error"]))
            continue
        names = r["renamed_names"] + r["shadowed_names"]
        print("%-30s %7d %6d %6d %8d %8d   %s" % (n, r["pressed"], r["held"], r["gone"], r["renamed"],
                                               r["shadowed"], "; ".join(names[:3])[:60]))
    print("-" * 100)
    tot = lambda k: sum(r.get(k, 0) for r in got.values())
    bad = problems(got)
    print("%d page(s), %d press(es): %d held, %d gone, %d renamed, %d shadowed  (%.0fs)"
          % (len(got), tot("pressed"), tot("held"), tot("gone"), tot("renamed"), tot("shadowed"),
             time.time() - t0))
    if bad:
        print("A RENAMED control's address lasts one press; a SHADOWED one presses something else "
              "and answers ok. Give the control a name that is not its value.")
    print("%d/%d pages clear" % (len(got) - len(bad), len(got)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
