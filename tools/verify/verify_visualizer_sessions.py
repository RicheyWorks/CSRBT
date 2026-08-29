# -*- coding: utf-8 -*-
"""Do the replayable sessions still show what the visualizer says they show?

ADR-052 bound `docs/ecology-lab.html` to the engine through
`ecology-lab-session.json`. Four more recorded artifacts ship in `docs/` and
were left unbound because no *published* page references them:

    docs/arena-session.json          docs/arena-search-session.json
    docs/viability-map.json          docs/visualizer-contract.json

They are not orphans. `demo/visualizer.html` is their reader: it names all four
in its footer, describes what each one shows, and invites you to drop them in.
Nothing checked any of those descriptions against the files, and one of them was
wrong -- the footer called arena-session "the real controller morphing
RB -> Splay -> RB" when the recorded arc is RedBlack -> Hybrid -> Splay ->
Hybrid and never returns to red-black. A reader who loaded the file to see the
described thing would have seen a different thing, with the page's own cards
naming the strategies it did not mention.

WHAT IS CHECKED, AND WHY IT NEEDS NO ENGINE

ADR-052's link A ("the engine still emits this") needs a compiled engine and
reports UNVERIFIED where it cannot run. Everything here is checkable from the
shipped bytes alone, because a tree export carries its own invariants:

    size    every node's size is 1 + size(left) + size(right)
    depth   the root is at 1 and every child is one deeper than its parent
    height  the state's height is the deepest node in it
    order   the in-order key walk is strictly increasing

Those four hold across 52 recorded states and 5576 nodes today. A hand-edited
state, a truncated file, or an exporter that drifted would break at least one --
and unlike a byte hash they say WHICH state and WHICH node, and they keep
passing when the engine legitimately produces a different tree.

Run:  python3 tools/verify/verify_visualizer_sessions.py
"""
import io, json, os, re, sys
import _kit

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DOCS = os.path.join(ROOT, "docs")
PAGE = os.path.join(ROOT, "demo", "visualizer.html")
CONTRACT = "visualizer-contract.json"
SESSIONS = ["arena-session.json", "arena-search-session.json"]

ok = bad = 0
def ck(name, cond, got=""):
    global ok, bad
    if cond: ok += 1; print("PASS  " + name)
    else:    bad += 1; print("FAIL  %s   got: %r" % (name, got))


def load(name):
    return json.load(io.open(os.path.join(DOCS, name), encoding="utf-8"))


def states(node, path=""):
    """Every exported tree state anywhere in a recorded session.

    Found by SHAPE (a dict carrying both "root" and "strategy") rather than by a
    list of paths, so a session that gains an event type is still covered. A
    path list would be a second copy of the format, free to drift from it."""
    if isinstance(node, dict):
        if "root" in node and "strategy" in node:
            yield path or "/", node
        for k, v in node.items():
            yield from states(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from states(v, path + "[%d]" % i)


def audit(state):
    """Every invariant a tree export carries, in ONE walk (ADR-039).

    Returns a list of complaints, each naming the state, the node and both
    numbers -- a boolean would tell you a 551 KB file is wrong and nothing
    more."""
    out, keys = [], []

    def walk(n, want_depth):
        if n is None:
            return 0
        if n.get("depth") != want_depth:
            out.append("node %s depth %r, expected %d" % (n.get("key"), n.get("depth"), want_depth))
        left = walk(n.get("left"), want_depth + 1)
        keys.append(n.get("key"))
        right = walk(n.get("right"), want_depth + 1)
        if n.get("size") != 1 + left + right:
            out.append("node %s size %r, subtree holds %d" % (n.get("key"), n.get("size"), 1 + left + right))
        return 1 + left + right

    total = walk(state.get("root"), 1)
    if total != state.get("size"):
        out.append("state size %r, tree holds %d" % (state.get("size"), total))

    depths = []
    def deep(n):
        if n is None: return
        depths.append(n.get("depth")); deep(n.get("left")); deep(n.get("right"))
    deep(state.get("root"))
    got_h = max(depths) if depths else 0
    if got_h != state.get("height"):
        out.append("state height %r, deepest node at %r" % (state.get("height"), got_h))

    try:
        nums = [int(k) for k in keys]
    except (TypeError, ValueError):
        out.append("a key is not an integer: %r" % (keys[:4],))
    else:
        if nums != sorted(nums):
            first = next(i for i in range(1, len(nums)) if nums[i] < nums[i - 1])
            out.append("in-order walk not increasing at %d (%d after %d)"
                       % (first, nums[first], nums[first - 1]))
    return out


# ---- 1. the contract, and the shape every state must have -----------------
CONTRACT_JSON = load(CONTRACT)
STATE_KEYS = set(CONTRACT_JSON) - {"root"}
ck("the contract parses and is itself a valid export",
   not audit(CONTRACT_JSON), audit(CONTRACT_JSON))
ck("the contract names the fields a state carries",
   STATE_KEYS >= {"type", "strategy", "size", "height", "meters"}, sorted(STATE_KEYS))

ALL = []
for s in SESSIONS:
    ALL += [(s, p, st) for p, st in states(load(s))]
ck("the recorded sessions hold states to check -- otherwise this is vacuous",
   len(ALL) > 40, len(ALL))
NODES = sum(1 for _, _, st in ALL for _ in re.finditer(r'"depth"', json.dumps(st)))
ck("and those states hold thousands of nodes, not a handful", NODES > 1000, NODES)

missing = [(f, p, sorted(STATE_KEYS - set(st))) for f, p, st in ALL if STATE_KEYS - set(st)]
ck("every recorded state carries the contract's fields", not missing, missing[:3])

# ---- 2. the invariants, on every shipped node -----------------------------
broken = [(f, p, audit(st)) for f, p, st in ALL if audit(st)]
ck("every recorded state satisfies size, depth, height and in-order",
   not broken, broken[:2])

# ---- 3. the detector is not vacuous --------------------------------------
# Six seeded faults, one per invariant plus the two that share a walk. A suite
# that only ever sees clean data is asserting that its inputs are clean.
GOOD = json.loads(json.dumps(CONTRACT_JSON))
def mutated(fn):
    m = json.loads(json.dumps(CONTRACT_JSON)); fn(m); return m
def setk(m, path, key, val):
    n = m["root"]
    for step in path: n = n[step]
    n[key] = val
# Each asserts WHICH invariant complained, not merely that something did. A
# first version checked only that audit() returned anything, and a mutation
# sweep disabled the depth rule with every fixture still green -- the depth
# mutant was being caught by the HEIGHT rule, which the same edit happened to
# trip. A catch that depends on a different check is not evidence for the check
# it is named after (ADR-039).
def says(m, word):
    return [c for c in audit(m) if word in c]

ck("a wrong node size is caught, BY the size rule",
   says(mutated(lambda m: setk(m, ["left"], "size", 99)), "size"),
   audit(mutated(lambda m: setk(m, ["left"], "size", 99))))
ck("a wrong node depth is caught, BY the depth rule",
   says(mutated(lambda m: setk(m, ["left"], "depth", 9)), "depth"),
   audit(mutated(lambda m: setk(m, ["left"], "depth", 9))))
ck("a wrong state size is caught, BY the state-size rule",
   says(mutated(lambda m: m.__setitem__("size", 6)), "state size"),
   audit(mutated(lambda m: m.__setitem__("size", 6))))
ck("a wrong state height is caught, BY the height rule",
   says(mutated(lambda m: m.__setitem__("height", 4)), "state height"),
   audit(mutated(lambda m: m.__setitem__("height", 4))))
ck("a key out of BST order is caught, BY the order rule",
   says(mutated(lambda m: setk(m, ["left", "left"], "key", "999")), "in-order"),
   audit(mutated(lambda m: setk(m, ["left", "left"], "key", "999"))))
ck("a lost subtree is caught", audit(mutated(lambda m: setk(m, ["left"], "right", None))))
ck("and the unmutated contract still passes", not audit(GOOD), audit(GOOD))

# ---- 4. what the page SAYS these files show ------------------------------
# The footer describes each artifact by name. The descriptions were prose that
# nothing read, and one of them had gone wrong.
SRC = io.open(PAGE, encoding="utf-8").read()
def sentence_for(fname):
    """The footer text from the file's name up to the next artifact or the end."""
    i = SRC.find(fname)
    if i < 0: return ""
    rest = SRC[i + len(fname): i + len(fname) + 400]
    cut = min([m.start() for m in re.finditer(r"docs/[\w-]+\.json", rest)] or [len(rest)])
    return _kit.prose_of(rest[:cut])

def arc(session):
    """The strategy sequence actually recorded, with repeats collapsed."""
    seq = []
    for _, st in states(session):
        s = re.sub(r"Strategy$", "", st.get("strategy", ""))
        if not seq or seq[-1] != s:
            seq.append(s)
    return seq

ARROW = re.compile(r"([A-Za-z][A-Za-z-]*)\s*(?:&rarr;|→|->)\s*")
def claimed(text):
    """The arrow chain in a description: 'RB -> Splay -> RB' -> [RB, Splay, RB]."""
    hits = ARROW.findall(text)
    if not hits: return []
    tail = ARROW.split(text)[-1].strip()
    m = re.match(r"[A-Za-z][A-Za-z-]*", tail)
    return hits + ([m.group(0)] if m else [])

def faithful(claim, actual):
    """Is the page's short chain an abbreviation of the recorded one?

    Same length, and each claimed token abbreviates the strategy in that slot.
    A page may write RB for RedBlack; it may not drop a strategy the reader's
    own cards will name, and it may not invent a return to one."""
    if len(claim) != len(actual): return False
    for c, a in zip(claim, actual):
        letters = "".join(ch for ch in a if ch.isupper()).lower()   # RedBlack -> rb
        if a.lower().startswith(c.lower()) or letters == c.lower():
            continue
        return False
    return True

ARENA = load("arena-session.json")
ACTUAL = arc(ARENA)
ck("arena-session records a morph arc worth describing", len(ACTUAL) >= 3, ACTUAL)
ck("the page's chain for arena-session matches the recorded arc",
   faithful(claimed(sentence_for("arena-session.json")), ACTUAL),
   (claimed(sentence_for("arena-session.json")), ACTUAL))

# faithful() in both directions, because a comparison that only ever says yes
# is the same as no comparison.
ck("an abbreviation is accepted", faithful(["RB", "Splay"], ["RedBlack", "Splay"]))
ck("a dropped strategy is refused", not faithful(["RB", "Splay"], ["RedBlack", "Hybrid", "Splay"]))
ck("an invented strategy is refused", not faithful(["RB", "Splay", "RB"], ["RedBlack", "Hybrid", "Splay"]))
ck("a wrong strategy in the right slot is refused",
   not faithful(["RB", "AVL"], ["RedBlack", "Splay"]))
# A claim that is a correct PREFIX of the arc and simply stops early. Every
# other refusal above still fires with the length test removed, because a
# mismatched pair happens to line up; this one does not, and a mutation sweep
# found it by deleting that test with all four fixtures green.
ck("a chain that stops before the arc does is refused",
   not faithful(["RB", "Hybrid"], ["RedBlack", "Hybrid", "Splay"]))
ck("and one that runs on past it is refused",
   not faithful(["RB", "Hybrid", "Splay"], ["RedBlack", "Hybrid"]))

# ---- 5. the other three descriptions -------------------------------------
SEARCH = load("arena-search-session.json")
EV = [e for e in SEARCH.get("events", [])]
def any_field(kind, field, test):
    return any(test(e.get(field)) for e in EV if e.get("type") == kind)
sent = sentence_for("arena-search-session.json")
ck("the page calls arena-search an evolution machine, and genomes are born in it",
   "born" in sent and any_field("Lineage", "child", lambda v: bool(v)), sent[:80])
ck("it says gate-killed, and a generation disqualifies one",
   "gate-killed" in sent and any_field("Diversity", "disqualified", lambda v: (v or 0) > 0), "")
ck("it says culled, and a generation culls one",
   "culled" in sent and any_field("Diversity", "culled", lambda v: (v or 0) > 0), "")
ck("it says promoted, and a morph is committed",
   "promoted" in sent and any_field("Morph", "committed", lambda v: v is True), "")

VM = load("viability-map.json")
vsent = sentence_for("viability-map.json")
axes = set(VM["cells"][0]) if VM.get("cells") else set()
ck("the page names the viability map's plane by its two axes, and the cells carry both",
   ("Δ" in vsent or "&Delta;" in vsent) and ("Γ" in vsent or "&Gamma;" in vsent)
   and {"delta", "ratio"} <= axes, (vsent[:60], sorted(axes)))
ck("and every cell records where the gate first broke",
   VM["cells"] and all("firstViolationOp" in c for c in VM["cells"]), "")

# ---- 6. the states embedded in the page itself ---------------------------
# The script comment claims three exports of the SAME 15 keys, before and after
# health-gated morphs. Both halves are checkable.
EMB = {}
for m in re.finditer(r'^(\w+):\s*(\{"type":"OrderedSet".*?)(?=,?\s*$)', SRC, re.M):
    try: EMB[m.group(1)] = json.loads(m.group(2).rstrip(","))
    except ValueError: pass
ck("the page's embedded states parse", len(EMB) >= 3, sorted(EMB))
ck("each embedded state is itself a valid export",
   not [k for k, v in EMB.items() if audit(v)],
   {k: audit(v) for k, v in EMB.items() if audit(v)})
def keyset(st):
    out = []
    def w(n):
        if not n: return
        w(n.get("left")); out.append(n["key"]); w(n.get("right"))
    w(st["root"]); return out
ck("and they are the SAME keys, which is what makes the animation a morph",
   len({tuple(keyset(v)) for v in EMB.values()}) == 1,
   {k: len(keyset(v)) for k, v in EMB.items()})
ck("the splay state is the spine the comment says it is (height == size)",
   "SPLAY" in EMB and EMB["SPLAY"]["height"] == EMB["SPLAY"]["size"],
   EMB.get("SPLAY", {}).get("height"))
ck("and the balanced one is shallower than it",
   "AVL" in EMB and EMB["AVL"]["height"] < EMB["SPLAY"]["height"],
   (EMB.get("AVL", {}).get("height"), EMB.get("SPLAY", {}).get("height")))

print("-" * 70)
print("%d passed, %d failed" % (ok, bad))
sys.exit(1 if bad else 0)
