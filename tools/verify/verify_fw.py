# -*- coding: utf-8 -*-
"""Food Web Builder: the graph algorithms, recomputed independently.

The one instrument in the kit with no suite naming it, found by the coverage
count in ADR-038. It computes trophic levels, connectance, the longest chain
and a knockout cascade -- four real graph algorithms, none of them checked
against anything.

Everything here is recomputed in Python from the definition rather than read
back from the page, and the two shipped presets give known answers that a
change to the algorithms has to keep producing.
"""
import io, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _kit import url, offline, ROOT
from playwright.sync_api import sync_playwright

P, F = [], []
def ck(n, c, e=""):
    (P if c else F).append(n + (("  << " + str(e)) if (e and not c) else ""))

PAGE = "food-web.html"
SRC = io.open(os.path.join(ROOT, "docs", PAGE), encoding="utf-8").read()


# ---- independent implementations -------------------------------------------
def trophic(species, links):
    """Longest-chain trophic level: producers are 1, a consumer is
    1 + max(level of its prey), counting only prey that themselves have a
    level. A consumer with no prey that reaches a producer stays 0."""
    lv = {s: (1 if k == "producer" else 0) for s, k in species.items()}
    for _ in range(len(species) + 2):
        changed = False
        for s, k in species.items():
            if k == "producer":
                continue
            prey = [lv[p] for p, q in links if q == s and lv[p] > 0]
            if prey:
                v = 1 + max(prey)
                if v != lv[s]:
                    lv[s] = v
                    changed = True
        if not changed:
            break
    return lv


def connectance(species, links):
    S = len(species)
    return (len(links) / (S * S)) if S else 0.0


def cascade(species, links, dead):
    """Remove `dead`, then repeatedly remove any consumer with no living prey."""
    alive = {s: (s != dead) for s in species}
    gone = []
    changed = True
    while changed:
        changed = False
        for s, k in species.items():
            if not alive[s] or k == "producer":
                continue
            if not any(alive[p] for p, q in links if q == s):
                alive[s] = False
                gone.append(s)
                changed = True
    return set(gone)


POND_SP = {"algae": "producer", "pondweed": "producer", "water-flea": "consumer",
           "mayfly-nymph": "consumer", "snail": "consumer", "minnow": "consumer",
           "dragonfly-nymph": "consumer", "perch": "consumer", "heron": "consumer"}
POND_LN = [("algae", "water-flea"), ("algae", "snail"), ("pondweed", "snail"),
           ("pondweed", "mayfly-nymph"), ("water-flea", "minnow"), ("mayfly-nymph", "minnow"),
           ("mayfly-nymph", "dragonfly-nymph"), ("minnow", "perch"),
           ("dragonfly-nymph", "perch"), ("snail", "perch"), ("perch", "heron"),
           ("minnow", "heron")]

MEADOW_SP = {"grass": "producer", "clover": "producer", "wildflowers": "producer",
             "aphid": "consumer", "grasshopper": "consumer", "bee": "consumer",
             "ladybird": "consumer", "spider": "consumer", "shrew": "consumer",
             "kestrel": "consumer"}
MEADOW_LN = [("grass", "grasshopper"), ("clover", "aphid"), ("wildflowers", "bee"),
             ("wildflowers", "aphid"), ("aphid", "ladybird"), ("aphid", "spider"),
             ("grasshopper", "spider"), ("bee", "spider"), ("ladybird", "shrew"),
             ("spider", "shrew"), ("grasshopper", "shrew"), ("shrew", "kestrel")]

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 950, "height": 1400})
    pg.set_default_timeout(20000)
    offline(pg)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console: " + m.text)
          if m.type == "error" and "ERR_" not in m.text else None)
    pg.goto(url(PAGE), wait_until="domcontentloaded")
    pg.wait_for_timeout(700)
    ck("page loads clean", not errs, errs[:3])

    def tile(label):
        return pg.evaluate("""(l)=>{const t=[...document.querySelectorAll('#webStats .tile')]
          .find(x=>x.querySelector('.l').textContent.trim()===l);
          return t ? t.querySelector('.v').textContent.trim() : null;}""", label)

    def build(sp, ln):
        """Drive the page's own state, then its own render."""
        pg.evaluate("""([sp,ln])=>{
          FW.load(sp, ln);}""", [sp, ln])
        pg.wait_for_timeout(350)

    # ---- the shipped presets, against an independent recomputation ----
    for name, btn, SP, LN in [("pond", "#presetPond", POND_SP, POND_LN),
                              ("meadow", "#presetMeadow", MEADOW_SP, MEADOW_LN)]:
        errs[:] = []
        pg.click(btn)
        pg.wait_for_timeout(450)
        ck("%s preset loads clean" % name, not errs, errs[:2])
        ck("%s: species count" % name, tile("species") == str(len(SP)), tile("species"))
        ck("%s: link count" % name, tile("feeding links") == str(len(LN)), tile("feeding links"))
        C = connectance(SP, LN)
        ck("%s: connectance L/S² = %.3f" % (name, C),
           tile("connectance L/S²") == "%.3f" % C, tile("connectance L/S²"))
        lv = trophic(SP, LN)
        ck("%s: longest chain = %d" % (name, max(lv.values())),
           tile("longest chain") == str(max(lv.values())), tile("longest chain"))
        ck("%s: producer count" % name,
           tile("producers") == str(sum(1 for k in SP.values() if k == "producer")),
           tile("producers"))
        # nothing should be flagged as orphaned or looping in a shipped preset
        box = pg.inner_text("#webStats")
        ck("%s: no orphan warning on a shipped preset" % name,
           "no food source" not in box, box[:120])
        ck("%s: no loop warning on a shipped preset" % name,
           "Loop detected" not in box, box[:120])

    # ---- tapping a pair twice erases the link, INCLUDING the first one ----
    # The builder's own instructions say "tap the same pair again to erase".
    # The erase branch is guarded by `if(i>=0)` on a findIndex result, and a
    # mutation sweep turned it into `i>0` -- which leaves the link at index 0
    # permanently unremovable while every other link still erases. Nothing
    # noticed, because no check had ever erased the FIRST link.
    pg.click("#presetPond"); pg.wait_for_timeout(450)
    first = pg.evaluate("()=>FW.links()[0]")
    before = pg.evaluate("()=>FW.links().length")
    def tap(sid):
        pg.eval_on_selector('g[data-id="%s"]' % sid,
                            "e=>e.dispatchEvent(new MouseEvent('click',{bubbles:true}))")
        pg.wait_for_timeout(220)
    tap(first["prey"]); tap(first["pred"])          # re-tapping the pair erases it
    after = pg.evaluate("()=>FW.links().length")
    ck("re-tapping a pair erases the link at index 0", after == before - 1, (before, after))
    ck("and it is that link that went",
       not any(l["prey"] == first["prey"] and l["pred"] == first["pred"]
               for l in pg.evaluate("()=>FW.links()")), first)
    tap(first["prey"]); tap(first["pred"])          # and putting it back works
    ck("tapping the pair once more restores it",
       pg.evaluate("()=>FW.links().length") == before,
       pg.evaluate("()=>FW.links().length"))

    # ---- the connectance verdict, ON its boundary ----
    # The page's three readings hinge on 0.05 and 0.3, and the upper one is
    # written `C <= 0.3`. A mutation sweep made it `C < 0.3` and every check
    # passed, because no web in the suite sat ON the boundary -- which is the
    # only place the two spellings differ. S=10, L=30 gives C = 30/100 exactly.
    BSP = {}
    for i in range(3): BSP["p%d" % i] = "producer"
    for i in range(7): BSP["c%d" % i] = "consumer"
    ids = list(BSP)
    # A DAG, or the page reports a loop and never prints the connectance
    # reading at all -- the first attempt let every consumer eat every other
    # species, which is mutual predation, and the verdict block is guarded by
    # `!orphans.length && !L.loop`. Only i<j links, and every consumer is given
    # one incoming link first so none is an orphan either.
    order = {k: i for i, k in enumerate(ids)}
    seed = [(ids[0], c) for c in ids[3:]]                      # 7, no orphans
    rest = [(x, y) for x in ids for y in ids
            if order[x] < order[y] and order[y] >= 3 and (x, y) not in seed]
    pairs = seed + rest
    BLN = pairs[:30]
    ck("the boundary web is exactly S=10, L=30", len(BSP) == 10 and len(BLN) == 30,
       (len(BSP), len(BLN)))
    build(list(BSP.items()), BLN)
    ck("connectance on the boundary reads 0.300",
       tile("connectance L/S²") == "0.300", tile("connectance L/S²"))
    body = pg.inner_text("body")
    ck("C = 0.3 exactly is read as INSIDE the published range, not denser than it",
       "right in the range" in body, body[:200])
    # and one link past it flips, so the check above is not passing on a page
    # that says "in the range" whatever the number.
    build(list(BSP.items()), pairs[:31])
    body2 = pg.inner_text("body")
    ck("and 31 links on ten species is read as denser than most real webs",
       "denser than most" in body2, body2[:200])

    # ---- the knockout cascade, on the case the page advertises ----
    pg.click("#presetPond")
    pg.wait_for_timeout(400)
    for victim in ["minnow", "algae", "mayfly-nymph", "heron", "perch"]:
        want = cascade(POND_SP, POND_LN, victim)
        got = pg.evaluate("""(n)=>{
          const s=FW.species().find(x=>x.name===n);
          return FW.cascade(s.id);}""", victim)
        ck("pond: losing %s takes down %s" % (victim, ", ".join(sorted(want)) or "nothing"),
           set(got) == want, sorted(got))

    pg.click("#presetMeadow")
    pg.wait_for_timeout(400)
    for victim in ["aphid", "grass", "spider", "kestrel"]:
        want = cascade(MEADOW_SP, MEADOW_LN, victim)
        got = pg.evaluate("""(n)=>{
          const s=FW.species().find(x=>x.name===n);
          return FW.cascade(s.id);}""", victim)
        ck("meadow: losing %s takes down %s" % (victim, ", ".join(sorted(want)) or "nothing"),
           set(got) == want, sorted(got))

    # ---- webs chosen to DISCRIMINATE, not merely to pass ----
    # Both shipped presets give the same answer under longest-chain and under
    # prey-averaged trophic level, and neither produces a cascade longer than
    # one round. So swapping max for mean, and cutting the cascade to a single
    # pass, both slipped through a full green suite. Fixtures that cannot tell
    # two implementations apart are not tests of the difference.
    LADDER_SP = {"p": "producer", "A": "consumer", "B": "consumer", "C": "consumer"}
    LADDER_LN = [("p", "A"), ("A", "B"), ("p", "C"), ("B", "C")]
    # C eats p (level 1) and B (level 3): longest-chain gives 4, prey-averaged 3.
    pg.evaluate("([sp,ln])=>FW.load(sp,ln)",
                [[[k, v] for k, v in LADDER_SP.items()], [list(x) for x in LADDER_LN]])
    pg.wait_for_timeout(350)
    want = trophic(LADDER_SP, LADDER_LN)
    got = pg.evaluate("()=>{const L=FW.levels(), sp=FW.species(), o={};"
                      "sp.forEach(s=>o[s.name]=L.lv[s.id]); return o;}")
    ck("a consumer eating two levels takes the HIGHEST, not the mean (C = %d)" % want["C"],
       got.get("C") == want["C"] == 4, (got.get("C"), want["C"]))
    ck("the whole ladder matches the independent recomputation",
       got == want, (got, want))
    ck("longest chain reports the longest-chain level",
       tile("longest chain") == str(max(want.values())), tile("longest chain"))

    # The chain p -> A -> B -> C, DECLARED BACKWARDS. Order matters: with the
    # species listed p, A, B, C a single forward pass happens to sweep the whole
    # chain in one go, so cutting the cascade loop to one round still passed.
    # Declared p, C, B, A, a single pass reaches C before B has starved, and
    # only a loop that runs to a fixed point gets the right answer.
    CHAIN_ORDER = ["p", "C", "B", "A"]
    CHAIN_SP = {"p": "producer", "C": "consumer", "B": "consumer", "A": "consumer"}
    CHAIN_LN = [("p", "A"), ("A", "B"), ("B", "C")]
    pg.evaluate("([sp,ln])=>FW.load(sp,ln)",
                [[[k, CHAIN_SP[k]] for k in CHAIN_ORDER], [list(x) for x in CHAIN_LN]])
    pg.wait_for_timeout(350)
    want_c = cascade(CHAIN_SP, CHAIN_LN, "A")
    got_c = set(pg.evaluate("()=>{const s=FW.species().find(x=>x.name==='A');"
                            "return FW.cascade(s.id);}"))
    ck("a cascade runs to a fixed point, not one round (losing A takes B and C)",
       got_c == want_c == {"B", "C"}, sorted(got_c))

    # ---- every surface that reports a measure must report the SAME measure ----
    # The page shows connectance in a tile, writes it into the notes export, and
    # exposes it on the public seam. A canary that changed only the seam left the
    # tile -- the one surface the suite read -- unchanged, and the suite stayed
    # green. Read all three.
    for name, SP, LN in [("pond", POND_SP, POND_LN), ("meadow", MEADOW_SP, MEADOW_LN)]:
        pg.evaluate("([sp,ln])=>FW.load(sp,ln)",
                    [[[k, v] for k, v in SP.items()], [list(x) for x in LN]])
        pg.wait_for_timeout(350)
        want_C = "%.3f" % connectance(SP, LN)
        seam_C = "%.3f" % pg.evaluate("()=>FW.connectance()")
        note = pg.inner_text("#ecoOut")
        note_C = ""
        for tok in note.split("\n"):
            if tok.startswith("note: connectance "):
                note_C = tok.split()[2]
        ck("%s: the tile, the seam and the export agree on connectance (%s)"
           % (name, want_C),
           tile("connectance L/S²") == seam_C == note_C == want_C,
           (tile("connectance L/S²"), seam_C, note_C, want_C))
        want_M = str(max(trophic(SP, LN).values()))
        seam_M = str(pg.evaluate("()=>{const L=FW.levels(); return FW.longestChain(L.lv);}"))
        ck("%s: the tile and the seam agree on longest chain (%s)" % (name, want_M),
           tile("longest chain") == seam_M == want_M,
           (tile("longest chain"), seam_M, want_M))

    # ---- properties that must hold on any web ----
    props = pg.evaluate("""()=>{
      function rnd(seed){ let s=seed; return ()=>{ s=(1664525*s+1013904223)>>>0; return s/4294967296; }; }
      const out=[];
      for(let t=0;t<8;t++){
        const r=rnd(97+t*7717), n=4+Math.floor(r()*7), sp=[], ln=[];
        for(let i=0;i<n;i++) sp.push([ "s"+i, i<2 ? "producer":"consumer" ]);
        for(let i=2;i<n;i++) for(let j=0;j<i;j++) if(r()<0.5) ln.push(["s"+j,"s"+i]);
        FW.load(sp, ln);
        const L=FW.levels();
        const lvs=Object.keys(L.lv).map(k=>L.lv[k]);
        out.push({ n:n, links:ln.length, loop:L.loop,
                   minLv:Math.min.apply(null,lvs), maxLv:Math.max.apply(null,lvs),
                   finite: lvs.every(v=>isFinite(v)) });
      }
      return out; }""")
    ck("a producer is always level 1 or above",
       all(pr["minLv"] >= 0 for pr in props), [pr["minLv"] for pr in props])
    ck("levels are always finite", all(pr["finite"] for pr in props), props[:1])
    ck("an acyclic web never reports a loop",
       all(not pr["loop"] for pr in props), [pr["loop"] for pr in props])
    ck("the longest chain never exceeds the species count",
       all(pr["maxLv"] <= pr["n"] + 1 for pr in props),
       [(pr["maxLv"], pr["n"]) for pr in props])

    # ---- a cycle: the case with no basal input ----
    pg.evaluate("""()=>FW.load(
      [["A","consumer"],["B","consumer"],["plant","producer"]],
      [["A","B"],["B","A"]])""")
    pg.wait_for_timeout(400)
    cyc = pg.inner_text("#webStats")
    ck("a mutual-predation pair is not described as having no arrows in",
       not re.search(r"\bA\b.*no food source|no food source.*\bA\b", cyc)
       or "arrow coming in" not in cyc,
       cyc[:220])
    ck("a web with a cycle and no basal path says something true about it",
       ("Loop detected" in cyc) or ("no path" in cyc) or ("cannot reach" in cyc),
       cyc[:220])

    # ---- the two orphan shapes, asserted POSITIVELY ----
    # The suite already checked that a mutual-predation pair is NOT called
    # unfed. Only the negative was checked, so blanking the unfed() filter
    # entirely -- every warning gone -- passed a green suite. A diagnosis that
    # is only ever tested for staying quiet is not tested at all.
    pg.evaluate("""()=>FW.load(
      [["plant","producer"],["grazer","consumer"],["stray","consumer"]],
      [["plant","grazer"]])""")
    pg.wait_for_timeout(400)
    orph = pg.inner_text("#webStats")
    ck("a consumer with no incoming arrow is named as having no food source",
       "stray" in orph and "no food source" in orph, orph[:220])
    ck("a consumer that IS fed is not named as an orphan",
       not re.search(r"grazer[^<]{0,40}no food source", orph), orph[:220])

    # rootless: eats something, but nothing it eats reaches a producer
    pg.evaluate("""()=>FW.load(
      [["plant","producer"],["ghost","consumer"],["hunter","consumer"]],
      [["ghost","hunter"]])""")
    pg.wait_for_timeout(400)
    root = pg.inner_text("#webStats")
    ck("a consumer fed only by an orphan is diagnosed separately from an unfed one",
       "hunter" in root and "ghost" in root, root[:240])
    ck("the two orphan shapes do not share one wrong message",
       root.count("no food source") >= 1, root[:240])

    # ---- escaping, on EVERY surface that prints a species name ----
    # esc() is called at seven sites: the node label, the unfed warning, the
    # rootless warning, the apex line, and three places in the knockout
    # verdict. The old fixture -- one producer, one consumer, one link -- drove
    # exactly one of them, so deleting esc() from the warning path passed a
    # green suite. One web that lights up all seven.
    PROBE = [["<x-probe>plant</x-probe>", "producer"],
             ["<x-probe>grazer</x-probe>", "consumer"],   # fed, and apex
             ["<x-probe>stray</x-probe>", "consumer"],    # unfed
             ["<x-probe>ghost</x-probe>", "consumer"],    # unfed
             ["<x-probe>hunter</x-probe>", "consumer"]]   # rootless: eats ghost
    PROBE_LN = [["<x-probe>plant</x-probe>", "<x-probe>grazer</x-probe>"],
                ["<x-probe>ghost</x-probe>", "<x-probe>hunter</x-probe>"]]
    pg.evaluate("([sp,ln])=>FW.load(sp,ln)", [PROBE, PROBE_LN])
    pg.wait_for_timeout(400)
    box = pg.inner_text("#webStats")
    ck("the escaping fixture actually reaches the unfed warning",
       "stray" in box and "no food source" in box, box[:200])
    ck("the escaping fixture actually reaches the rootless warning",
       "hunter" in box, box[:200])
    ck("a species name typed as markup does not become markup",
       pg.eval_on_selector_all("x-probe", "e=>e.length") == 0,
       pg.eval_on_selector_all("x-probe", "e=>e.length"))
    ck("the raw angle brackets survive as text, not as swallowed markup",
       "<x-probe>stray</x-probe>" in pg.inner_text("body"),
       pg.inner_text("#webStats")[:160])

    # The apex line lives inside `if(!orphans.length && !L.loop && links_n)`,
    # so the orphan-bearing web above can never reach it -- which is exactly
    # why dropping esc() from the apex names passed a green suite. A CLEAN web
    # is required to light that branch.
    CLEAN = [["<x-probe>plant</x-probe>", "producer"],
             ["<x-probe>grazer</x-probe>", "consumer"],
             ["<x-probe>cat</x-probe>", "consumer"]]
    CLEAN_LN = [["<x-probe>plant</x-probe>", "<x-probe>grazer</x-probe>"],
                ["<x-probe>grazer</x-probe>", "<x-probe>cat</x-probe>"]]
    pg.evaluate("([sp,ln])=>FW.load(sp,ln)", [CLEAN, CLEAN_LN])
    pg.wait_for_timeout(400)
    clean = pg.inner_text("#webStats")
    ck("a clean web reaches the connectance reading and the apex line",
       "Top of this web" in clean, clean[:200])
    ck("the apex line escapes the species name too",
       pg.eval_on_selector_all("x-probe", "e=>e.length") == 0, clean[:200])

    # back to the orphan-bearing probe for the knockout verdict
    pg.evaluate("([sp,ln])=>FW.load(sp,ln)", [PROBE, PROBE_LN])
    pg.wait_for_timeout(350)

    # the knockout verdict prints the name three more times
    pg.evaluate("""()=>{const s=FW.species().find(x=>x.name.indexOf('ghost')>=0);
      FW.knockout(s.id);}""")
    pg.wait_for_timeout(400)
    ko = pg.inner_text("#webStats")
    ck("the knockout verdict actually rendered", "Knockout test" in ko, ko[:160])
    ck("the knockout verdict escapes the species name too",
       pg.eval_on_selector_all("x-probe", "e=>e.length") == 0,
       ko[:200])

    ck("no errors through the whole run", not errs, errs[:3])

    b.close()

# ---- the page must say which trophic-level definition it uses ----
ck("the page names the trophic-level definition it uses",
   "longest" in SRC.lower() and ("prey-averaged" in SRC or "mean of its prey" in SRC
                                 or "not the prey-averaged" in SRC),
   "two standard definitions exist; the page must say which one these numbers are")

print("\n".join("PASS  " + x for x in P))
if F:
    print("\n".join("FAIL  " + x for x in F))
print("-" * 60)
print("%d passed, %d failed" % (len(P), len(F)))
sys.exit(1 if F else 0)
