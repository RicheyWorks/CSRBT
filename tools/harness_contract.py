# -*- coding: utf-8 -*-
"""A provider-neutral automation contract for the kit: gateway, registry, plugins.

WHY A CONTRACT AND NOT A SCRIPT
    tools/harness.py and tools/swarm.py drive these pages by reaching straight
    into Playwright. That works for one caller written by the same hand as the
    kit. It is useless to anyone else: an accessibility auditor, a test runner,
    an MCP server, a model with a tool-calling loop. Each of those would have to
    re-derive what a control IS on these pages, and would re-derive it wrongly,
    because "a button" on a Field Entry Kit page is a .fek-dial option with
    radio semantics and a rebuild-on-change lifecycle.

    So the knowledge moves behind a typed boundary, and every client -- the
    swarm included -- goes through it. The swarm is not a privileged insider
    with a private route to the DOM. It is the contract's first client, and it
    exercises every action on forty pages, which is the only evidence worth
    having that the contract is usable.

        AI provider / MCP / test runner / accessibility tool / script
                            |
              stdio, REST, MCP, or another adapter
                            |
              HarnessGateway   (token + policy + replay safety)
                            |
              HarnessRegistry  (plugin discovery)
                            |
              HarnessPlugin implementations
                            |
              a CSRBT page in a browser, or another target

    The gateway and the plugin interface are the contract. A transport is an
    adapter over four operations -- manifest, discover, observe, execute -- and
    nothing else. tools/harness_stdio.py is the first one; it is 120 lines,
    which is the point.

SAFETY DEFAULTS
    Off unless switched on. No transport serves anything unless
    CSRBT_HARNESS_ENABLED is true, and every call needs a token of at least 24
    characters whether or not a transport thinks it is on a private machine.

    Risk is declared by the PLUGIN, never claimed by the caller:

      READ            allowed   discover plugins, observe control metadata
      NAVIGATE        allowed   change pane or page without changing a record
      SENSITIVE_READ  blocked   read entered values, or capture pixels
      DRAFT           blocked   enter a temporary field or selector value
      MUTATE          blocked   change persistent data (localStorage autosave)
      DESTRUCTIVE     blocked   generic activation whose effect cannot be known

    DESTRUCTIVE cannot be enabled without MUTATE. Generic button activation is
    classified DESTRUCTIVE deliberately: on these pages a selector may resolve
    to "Add row", to "Clear trial", or to "Copy CSV", and deciding which from
    the label is precisely the guess this contract exists to refuse. The swarm
    guesses from labels for its own oracle and is welcome to be wrong about a
    verdict; the gateway does not get to be wrong about permission.

    Observation is value-redacted by default: kind, selector, label, pane,
    visible, enabled, commandable -- never the contents of a field. Labels can
    still carry field data on a page that renders entries into a list, so the
    manifest says so and the token is the boundary.

REPLAY SAFETY
    Every command carries a caller-generated request_id. Replaying the same id
    with the same body returns the cached response with replayed=true and does
    not operate the page twice. Reusing that id with a different body is a
    conflict. The cache is bounded: 256 commands or 8 MiB of output.

    One deliberate divergence from the FlowersForever gateway this mirrors: a
    replay is authorised again before it is served. There, the cache is checked
    before the risk is authorised, so a response captured while
    SENSITIVE_READ was open can still be replayed after an operator closes it.
    Here the policy is re-applied to the cached response's risk, so tightening
    the policy takes effect on the next call rather than the next restart.
"""
import hashlib, hmac, json, os, re, time

PROTOCOL_VERSION = "1.7"   # 1.1 (ADR-114): bounds, patterns, examples in argument schemas
                           # 1.2 (ADR-120): snapshotMs on every execute response -- the snapshot, priced
                           # 1.3 (ADR-124): argumentPools may carry argument SETS, keyed by the action alone
                           # 1.6 (ADR-189): `stale` -- a refusal for an argument that was right when
                           #                the client read it and is not right now. It is not
                           #                invalid_argument (it was valid) and not not_found (the thing
                           #                exists); it means READ AGAIN, and only a code of its own says so.
                           # 1.4 (ADR-134): a target may publish actions that set the ENVIRONMENT a run
                           #                happens in -- the clock, the seed, the answer a dialog gets --
                           #                so a client can make a non-deterministic path reproducible
                           # 1.5 (ADR-141): an action's declared risk is a FLOOR. An action marked
                           #                mayRise is one whose real risk depends on what it was
                           #                pointed at, and the plugin RAISES it per call -- never
                           #                lowers it -- with a reason the response carries.
                           # 1.7 (ADR-191): every snapshot carries a `stamp`, observe() takes a
                           #                `since` stamp and answers with what CHANGED, and every
                           #                execute response carries the same diff against the last
                           #                snapshot this session was served. A plugin says what
                           #                identity means on its own snapshot (identity()); the
                           #                gateway does the diffing, so all three targets diff alike.
REPLAY_CACHE_LIMIT = 256
REPLAY_CACHE_BYTE_LIMIT = 8 * 1024 * 1024
# ADR-191: how many entries of one list, in one bucket of one diff, are named
# before the diff says it stopped naming them. A diff is a saving over the
# snapshot or it is nothing, and an unbounded one on a page that rebuilt every
# control would be larger than the snapshot it was meant to replace.
DIFF_CAP = 40
# The separator for a path INTO a snapshot. Not "." -- the page's argument pool
# names contain dots ("choose-option.value", "set-text.selector"), so a dotted
# path could not say whether it meant a pool called "choose-option.value" or a
# field "value" inside a pool called "choose-option".
PATH_SEP = "/"
TOKEN_MIN = 24
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,29}$")
TOOL_NAME_MAX = 64
TOOL_NAME_OK = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Ordered least to most consequential. The order is not decorative: DESTRUCTIVE
# requires MUTATE, and the manifest publishes the ladder so an adapter can show
# an operator what it is being asked for.
RISKS = ("READ", "NAVIGATE", "SENSITIVE_READ", "DRAFT", "MUTATE", "DESTRUCTIVE")
DEFAULT_POLICY = {"READ": True, "NAVIGATE": True, "SENSITIVE_READ": False,
                  "DRAFT": False, "MUTATE": False, "DESTRUCTIVE": False}

VALUE_TYPES = ("string", "integer", "number", "boolean", "array")
_JSON_TYPE = {"string": str, "integer": int, "number": (int, float),
              "boolean": bool, "array": list}


def _is_scalar(v):
    return v is None or isinstance(v, (str, int, float, bool))


def _key_of(entry, fields):
    """The identity of one entry of a keyed list: the first field it HAS.

    A list of scalars is keyed by the scalar ("self"). A list of objects is
    keyed by the first named field that is present and not null, so a page
    control is its address when it has one and its selector when it does not
    -- the same fallback the address grammar itself makes (ADR-188)."""
    if fields == "self":
        return entry if _is_scalar(entry) else None
    if not isinstance(entry, dict):
        return None
    for f in fields:
        v = entry.get(f)
        if v is not None and _is_scalar(v):
            return v
    return None


def _walk(node, path, noise, out):
    """Flatten a snapshot to (path -> value), stopping at keyed lists.

    A keyed list is left WHOLE at its own path, because the diff handles it
    entry by entry. Everything else lands as a scalar path (compared value by
    value) or, for a list this snapshot did not claim to have identity in, as
    one opaque value at its path -- compared by length rather than by content,
    because a list nobody keyed cannot be diffed without inventing an identity
    for its entries, and inventing one is how a reordered list reads as
    everything changing."""
    if path in noise:
        return
    if isinstance(node, dict):
        for k in node:
            _walk(node[k], (path + PATH_SEP + k) if path else k, noise, out)
        return
    out[path] = node


def _paths(snap, noise):
    out = {}
    _walk(snap, "", noise, out)
    return out


def stamp_of(snap, spec=None):
    """A short digest of everything in a snapshot that a reader could notice.

    Its whole job is to answer "has anything moved since I last looked" in a
    handful of bytes. Paths the plugin declared NOISE are left out -- a replica
    lag in milliseconds and a thread count move on their own, and a stamp that
    moved with them would report change on every call and mean nothing. The
    stamp itself is not a version of the page (`version`, ADR-188, is that);
    it is a version of the OBSERVATION, and it moves when a value does."""
    spec = spec or {}
    noise = set(spec.get("noise") or ())
    if not isinstance(snap, dict):
        return None
    paths = _paths(snap, noise)
    # A KEYED LIST IS A SET, FOR STAMPING PURPOSES. These pages rebuild their
    # controls on nearly every act, in whatever order the rebuild happened to
    # produce, and a stamp that moved with the order would report "changed"
    # about a page where nothing changed -- and would contradict the empty diff
    # the same two snapshots produce. Sorted by the same identity the diff
    # uses, so the stamp and the diff can never disagree about whether
    # something moved.
    keys = spec.get("keys") or {}
    for p in keys:
        v = paths.get(p)
        if isinstance(v, list):
            paths[p] = sorted(v, key=lambda e: json.dumps(
                [_key_of(e, keys[p]), e], sort_keys=True, default=str))
    body = json.dumps([[k, paths[k]] for k in sorted(paths)],
                      sort_keys=True, default=str, ensure_ascii=False)
    h = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    return "s" + h


def diff_of(before, after, spec=None, cap=DIFF_CAP):
    """What changed between two snapshots of the same target.

    The gateway computes this, not the plugin, so the page, the organism and
    the lab all diff alike and one suite holds all three. What the PLUGIN
    supplies is the only thing the gateway cannot know: what identity means on
    its own snapshot -- which lists are keyed, and by what -- and which paths
    are noise. Everything else follows.

        fields    a value that moved, at its path: {"size": [4, 5]}
        gained    a path that was not there before, with its value
        lost      a path that is not there now
        appeared  a whole new entry of a keyed list, so a client can act on it
                  without re-reading the snapshot
        vanished  the KEY of an entry that is gone -- not its body, which the
                  client already had and which is no longer true of anything
        altered   a key, and the fields of that entry that moved
        counts    a list nobody keyed: how long it was and how long it is. Not
                  its contents: a list with no declared identity cannot be
                  diffed entry by entry without inventing one.
        capped    where a bucket stopped naming entries, and how many there were
        noise     the paths that were NOT compared, named rather than dropped

    Order is not change. A keyed list is compared as a mapping from key to
    entry, so a page that rebuilt its controls in a different order -- which
    these pages do on every act -- reports the handful that actually moved."""
    spec = spec or {}
    keys = spec.get("keys") or {}
    noise = set(spec.get("noise") or ())
    d = {"fields": {}, "gained": {}, "lost": [], "appeared": {}, "vanished": {},
         "altered": {}, "counts": {}, "capped": [], "noise": sorted(noise)}
    if not isinstance(before, dict) or not isinstance(after, dict):
        return d
    pb, pa = _paths(before, noise), _paths(after, noise)
    for p in sorted(set(pb) | set(pa)):
        in_b, in_a = p in pb, p in pa
        vb, va = pb.get(p), pa.get(p)
        spec_k = keys.get(p)
        if isinstance(vb, list) or isinstance(va, list):
            if not in_b or not in_a:
                (d["gained"].__setitem__(p, _brief(va)) if in_a else d["lost"].append(p))
                continue
            if spec_k is None:
                if len(vb) != len(va) or vb != va:
                    d["counts"][p] = [len(vb), len(va)]
                continue
            _diff_list(p, vb, va, spec_k, cap, d)
            continue
        if in_b and not in_a:
            d["lost"].append(p)
        elif in_a and not in_b:
            d["gained"][p] = _brief(va)
        elif vb != va:
            d["fields"][p] = [_brief(vb), _brief(va)]
    return d


def _diff_list(path, vb, va, fields, cap, d):
    """One keyed list, compared as a mapping. Entries with no identity at all
    are counted rather than named: a client cannot act on an entry it has no
    way to name again, and pretending otherwise would be the diff inventing a
    key the target never published."""
    mb, na = {}, 0
    for e in vb:
        k = _key_of(e, fields)
        if k is not None:
            mb[k] = e
    ma = {}
    for e in va:
        k = _key_of(e, fields)
        if k is None:
            na += 1
        else:
            ma[k] = e
    app = [ma[k] for k in ma if k not in mb]
    gone = [k for k in mb if k not in ma]
    alt = {}
    for k in ma:
        if k not in mb:
            continue
        a, b = ma[k], mb[k]
        if a == b:
            continue
        if not isinstance(a, dict) or not isinstance(b, dict):
            alt[k] = {"value": [_brief(b), _brief(a)]}
            continue
        moved = {}
        for f in sorted(set(a) | set(b)):
            if a.get(f) != b.get(f):
                moved[f] = [_brief(b.get(f)), _brief(a.get(f))]
        if moved:
            alt[k] = moved
    if app:
        d["appeared"][path] = _cap(app, cap, path + ".appeared", len(app), d)
    if gone:
        d["vanished"][path] = _cap(sorted(gone, key=str), cap, path + ".vanished", len(gone), d)
    if alt:
        ks = sorted(alt, key=str)
        kept = _cap(ks, cap, path + ".altered", len(ks), d)
        d["altered"][path] = dict((k, alt[k]) for k in kept)
    if na:
        d["counts"][path + ".unnamed"] = [0, na]


def _cap(seq, cap, where, total, d):
    if total > cap:
        d["capped"].append({"where": where, "named": cap, "of": total})
        return list(seq)[:cap]
    return list(seq)


def _brief(v):
    """A value, small enough to sit in a diff. A diff that carried a page's
    whole box text on each side would cost more than the snapshot it saves."""
    if isinstance(v, str) and len(v) > 200:
        return v[:200] + "…"
    if isinstance(v, (list, tuple)):
        return {"list": len(v)}
    if isinstance(v, dict):
        return {"object": len(v)}
    return v


class HarnessError(Exception):
    """Every refusal a client can be given, with a code a transport can map."""

    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code = code
        self.message = message

    def as_dict(self):
        return {"ok": False, "code": self.code, "message": self.message}


def _err(code):
    def make(msg):
        return HarnessError(code, msg)
    return make


Unauthorized = _err("unauthorized")
Forbidden = _err("forbidden")
NotFound = _err("not_found")
InvalidArgument = _err("invalid_argument")
Conflict = _err("conflict")
# ADR-189: the client's argument was right when it was read and is not right
# now -- a positional selector from a snapshot the page has since rebuilt. The
# fix is to read again, which is neither what invalid_argument says (the
# argument was well formed and true) nor what not_found says (the control is
# there; the caller's name for it is what expired).
Stale = _err("stale")
Unavailable = _err("unavailable")
Failed = _err("failed")


# ---------------------------------------------------------------------------
# Typed description of what a plugin can do
# ---------------------------------------------------------------------------

class ArgumentSpec(object):
    """One argument, typed, and -- since ADR-114 -- bounded well enough that a
    client holding nothing but the manifest can form a valid call.

    minimum/maximum apply to integer and number arguments; pattern applies to a
    string argument, or to each item of an array of strings; examples are
    values a client may use verbatim. An argument with a pattern MUST carry
    examples, and every example must satisfy its own pattern, because the
    manifest is the only thing a schema-driven client reads and a pattern with
    no example is a lock with no key (organism_walk reported exactly that on the
    batch-op strings before this rule existed)."""

    def __init__(self, name, type, description, required=False, items=None,
                 enum=None, minimum=None, maximum=None, pattern=None, examples=None):
        if type not in VALUE_TYPES:
            raise ValueError("unknown value type %r" % type)
        if type == "array" and items not in VALUE_TYPES:
            # An adapter that cannot tell a list of row numbers from a list of
            # menu labels will build the wrong tool schema, so an array must
            # publish what it is an array OF.
            raise ValueError("array argument %r must declare items type" % name)
        if (minimum is not None or maximum is not None) and type not in ("integer", "number"):
            raise ValueError("argument %r: bounds need a numeric type" % name)
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("argument %r: minimum %r > maximum %r" % (name, minimum, maximum))
        if pattern is not None:
            if not (type == "string" or (type == "array" and items == "string")):
                raise ValueError("argument %r: a pattern needs a string, or an array of strings" % name)
            if not examples:
                raise ValueError("argument %r: a pattern without examples is a lock with no key" % name)
            rx = re.compile(pattern)
            for ex in examples:
                if not isinstance(ex, str) or not rx.fullmatch(ex):
                    raise ValueError("argument %r: example %r fails its own pattern" % (name, ex))
        if enum is not None and examples:
            for ex in examples:
                if ex not in enum:
                    raise ValueError("argument %r: example %r is not in its enum" % (name, ex))
        self.name, self.type, self.description = name, type, description
        self.required, self.items, self.enum = required, items, enum
        self.minimum, self.maximum, self.pattern = minimum, maximum, pattern
        self.examples = list(examples) if examples else None
        self._rx = re.compile(pattern) if pattern else None

    def schema(self):
        s = {"type": self.type, "description": self.description}
        if self.type == "array":
            s["items"] = {"type": self.items}
            if self.pattern:
                s["items"]["pattern"] = self.pattern
            if self.enum:
                s["items"]["enum"] = list(self.enum)     # an enum on an array is per item
        elif self.pattern:
            s["pattern"] = self.pattern
        if self.enum and self.type != "array":
            s["enum"] = list(self.enum)
        if self.minimum is not None:
            s["minimum"] = self.minimum
        if self.maximum is not None:
            s["maximum"] = self.maximum
        if self.examples:
            s["examples"] = list(self.examples)
        return s

    def validate(self, value, action):
        want = _JSON_TYPE[self.type]
        if self.type == "integer" and isinstance(value, bool):
            raise InvalidArgument("%s: %s must be an integer" % (action, self.name))
        if self.type == "number" and isinstance(value, bool):
            raise InvalidArgument("%s: %s must be a number" % (action, self.name))
        if not isinstance(value, want):
            raise InvalidArgument("%s: %s must be %s, got %s"
                                  % (action, self.name, self.type,
                                     type(value).__name__))
        if self.type == "array":
            for v in value:
                if not isinstance(v, _JSON_TYPE[self.items]):
                    raise InvalidArgument("%s: %s must be an array of %s"
                                          % (action, self.name, self.items))
                if self._rx and not self._rx.fullmatch(v):
                    raise InvalidArgument("%s: %s item %r does not match %s"
                                          % (action, self.name, v[:40], self.pattern))
        if self.enum:
            each = value if self.type == "array" else [value]
            for v in each:
                if v not in self.enum:
                    raise InvalidArgument("%s: %s must be one of %s"
                                          % (action, self.name, ", ".join(self.enum)))
        if self.minimum is not None and value < self.minimum:
            raise InvalidArgument("%s: %s must be >= %s, got %s"
                                  % (action, self.name, self.minimum, value))
        if self.maximum is not None and value > self.maximum:
            raise InvalidArgument("%s: %s must be <= %s, got %s"
                                  % (action, self.name, self.maximum, value))
        if self._rx and self.type == "string" and not self._rx.fullmatch(value):
            raise InvalidArgument("%s: %s does not match %s"
                                  % (action, self.name, self.pattern))


class ActionSpec(object):
    def __init__(self, name, description, risk, arguments=(), may_rise=False):
        if not SLUG.match(name):
            raise ValueError("action name %r is not a slug of 1-30 chars" % name)
        if risk not in RISKS:
            raise ValueError("unknown risk %r" % risk)
        self.name, self.description, self.risk = name, description, risk
        self.arguments = list(arguments)
        # ADR-141: THE DECLARED RISK IS A FLOOR, NOT A VERDICT, for an action
        # whose real risk depends on what it is pointed at. `activate` on these
        # pages may resolve to "Add stem" or to "Clear trial"; declaring it
        # DESTRUCTIVE for the second made the first unreachable, and a
        # supervised session that can fill every field and commit none of them
        # cannot enter data at all -- which is what four blind operators
        # independently found. An action that says may_rise is one the plugin
        # re-reads per call; the gateway authorises whatever comes back, and
        # only ever upward.
        self.may_rise = bool(may_rise)

    def input_schema(self):
        return {"type": "object",
                "properties": dict((a.name, a.schema()) for a in self.arguments),
                "required": [a.name for a in self.arguments if a.required],
                "additionalProperties": False}

    def as_dict(self):
        return {"name": self.name, "description": self.description,
                "risk": self.risk, "mayRise": self.may_rise,
                "arguments": [{"name": a.name, "type": a.type,
                               "description": a.description,
                               "required": a.required,
                               "items": a.items, "enum": a.enum,
                               "minimum": a.minimum, "maximum": a.maximum,
                               "pattern": a.pattern, "examples": a.examples}
                              for a in self.arguments]}


class PluginDescriptor(object):
    def __init__(self, id, title, description, version, actions):
        if not SLUG.match(id):
            raise ValueError("plugin id %r is not a slug of 1-30 chars" % id)
        seen = set()
        for a in actions:
            if a.name in seen:
                raise ValueError("plugin %s declares action %s twice" % (id, a.name))
            seen.add(a.name)
            t = tool_name(id, a.name)
            if not TOOL_NAME_OK.match(t) or len(t) > TOOL_NAME_MAX:
                raise ValueError("tool name %r is not provider-safe" % t)
        self.id, self.title, self.description = id, title, description
        self.version, self.actions = version, list(actions)

    def action(self, name):
        for a in self.actions:
            if a.name == name:
                return a
        raise NotFound("plugin %s has no action %r" % (self.id, name))

    def as_dict(self):
        return {"id": self.id, "title": self.title, "description": self.description,
                "version": self.version,
                "actions": [a.as_dict() for a in self.actions]}


def tool_name(plugin_id, action):
    return "%s__%s" % (plugin_id.replace("-", "_"), action.replace("-", "_"))


class Plugin(object):
    """What a target implements. Three methods, no transport, no policy."""

    def descriptor(self):
        raise NotImplementedError

    def observe(self, sensitive=False):
        """A snapshot. Field VALUES appear only when sensitive is true, and the
        gateway is the only thing that may pass it."""
        raise NotImplementedError

    def execute(self, action, arguments):
        """Return (ok, message, output). Raise HarnessError to refuse."""
        raise NotImplementedError

    def identity(self, snapshot=None):
        """ADR-191: what identity means on THIS target's snapshot.

            {"keys":  {"controls": ["address", "selector"], "panes": "self"},
             "noise": ["jvm", "replicaLagMs"]}

        `keys` names the lists that have identity, by path from the snapshot's
        root (PATH_SEP-joined), each with the fields that identify an entry --
        first one present wins -- or "self" for a list of scalars. A list not
        named here is compared by length, because a list with no declared
        identity cannot be diffed entry by entry without inventing one.

        `noise` names paths that move on their own -- a lag, a thread count, a
        wall clock -- which are left out of the stamp AND out of the diff, and
        NAMED in it, so a reader can see what was not compared rather than
        conclude it did not change.

        A plugin that says nothing gets a stamp over its whole snapshot and a
        diff of scalars and counts, which is correct and merely coarse."""
        return {}

    def risk_for(self, action, arguments):
        """ADR-141: the risk of THIS call, for an action that declared may_rise.

        Return (risk, why) or None. The gateway takes it only if it is HIGHER
        than the declared risk -- a plugin may raise its own ceiling and may
        never lower it, because a plugin that could talk its way down the ladder
        would be the policy asking the target for permission.

        It must fail CLOSED: a call whose subject cannot be identified is the
        dangerous case, not the safe one, and gets the highest risk the action
        can carry rather than the lowest."""
        return None


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class Policy(object):
    """Off by default, read from the environment, and never from the caller."""

    def __init__(self, token=None, allow=None, enabled=None):
        self.enabled = (os.environ.get("CSRBT_HARNESS_ENABLED", "").lower() == "true"
                        if enabled is None else bool(enabled))
        self.token = token if token is not None else os.environ.get("CSRBT_HARNESS_TOKEN", "")
        p = dict(DEFAULT_POLICY)
        for r in RISKS:
            v = os.environ.get("CSRBT_HARNESS_ALLOW_" + r)
            if v is not None:
                p[r] = v.lower() == "true"
        if allow:
            for r in allow:
                if r not in RISKS:
                    raise ValueError("unknown risk %r" % r)
                p[r] = bool(allow[r])
        # A generic activation that may change nothing or may delete a record is
        # not something to hand out on its own.
        if p["DESTRUCTIVE"] and not p["MUTATE"]:
            raise ValueError("DESTRUCTIVE cannot be allowed without MUTATE")
        self.allow = p

    def authenticate(self, token):
        if not self.token or len(self.token) < TOKEN_MIN:
            raise Unauthorized("harness token is unset or shorter than %d characters"
                               % TOKEN_MIN)
        if not isinstance(token, str) or not hmac.compare_digest(token, self.token):
            raise Unauthorized("harness token rejected")

    def authorize(self, risk):
        if not self.allow.get(risk):
            raise Forbidden("%s is not enabled for this session" % risk)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class Registry(object):
    """The plugins a session may drive -- and, since ADR-137, a set that can
    CHANGE while the session is open.

    A registry that could only be built and then read made the transports'
    `listChanged: false` true by construction: there was nothing that could
    change a list. `retire()` and a `register()` after construction are what
    make the notification worth sending, and `watch()` is how a transport
    hears about it. Anything that changes which tools a manifest names calls
    every watcher with the kind of change ("tools" for a policy-shaped change,
    "plugins" when the set of targets itself moved -- a plugin's tools AND its
    snapshot resource arrive or leave together)."""

    def __init__(self, plugins=()):
        self._by_id = {}
        self._watchers = []
        for p in plugins:
            self.register(p, quiet=True)          # construction is not a change

    def watch(self, fn):
        """Call fn(kind) whenever the set of plugins changes. Returns fn so a
        caller can unwatch it."""
        self._watchers.append(fn)
        return fn

    def unwatch(self, fn):
        if fn in self._watchers:
            self._watchers.remove(fn)

    def _announce(self, kind):
        # A watcher that raises must not take the registry down with it: the
        # change HAPPENED, and a transport that cannot cope with hearing so is
        # the transport's problem.
        for fn in list(self._watchers):
            try:
                fn(kind)
            except Exception:
                pass

    def register(self, plugin, quiet=False):
        d = plugin.descriptor()
        if d.id in self._by_id:
            # A ValueError, not a Conflict: nothing a HOST does reaches here
            # with a duplicate -- csrbt-session checks the ids it is about to
            # add against the ones already served and refuses with `conflict`
            # first. Getting here is a programming mistake, and has been since
            # ADR-102.
            raise ValueError("duplicate plugin id %r" % d.id)
        self._by_id[d.id] = plugin
        if not quiet:
            self._announce("plugins")
        return self

    def retire(self, plugin_id):
        """Take a plugin out of the session. Its tools stop being listed and
        its snapshot stops being a resource; the caller owns closing it."""
        if plugin_id not in self._by_id:
            raise NotFound("unknown harness plugin %r" % plugin_id)
        plugin = self._by_id.pop(plugin_id)
        self._announce("plugins")
        return plugin

    def descriptors(self):
        return [self._by_id[k].descriptor() for k in sorted(self._by_id)]

    def find(self, plugin_id):
        if plugin_id not in self._by_id:
            raise NotFound("unknown harness plugin %r" % plugin_id)
        return self._by_id[plugin_id]


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

class _Done(object):
    __slots__ = ("body", "response", "risk", "nbytes")

    def __init__(self, body, response, risk, nbytes):
        self.body, self.response, self.risk, self.nbytes = body, response, risk, nbytes


class Gateway(object):
    """Token, policy, replay safety. The only thing a transport talks to."""

    def __init__(self, registry, policy):
        self.registry, self.policy = registry, policy
        self._done = {}          # cacheKey -> _Done, insertion-ordered
        self._bytes = 0
        self.audit = []          # (t, plugin, action, risk, outcome)
        # ADR-137: a transport subscribes here and hears every change to what a
        # session may drive. The gateway is what watches the registry, not the
        # transport, because the gateway is also what must FORGET a retired
        # plugin's replayable responses.
        self._subs = []
        self.changes = 0
        # ADR-191: the last snapshot this session was SERVED, per plugin, and
        # its stamp. It is the baseline every diff is taken against -- which is
        # why a diff is always "since you last looked" and never "since some
        # moment the door picked", and why a session that has never observed is
        # told it has no baseline rather than handed a diff against nothing.
        self._seen = {}
        registry.watch(self._changed)

    def subscribe(self, fn):
        """Call fn(kind) when the set of tools this session lists changes."""
        self._subs.append(fn)
        return fn

    def unsubscribe(self, fn):
        if fn in self._subs:
            self._subs.remove(fn)

    def _changed(self, kind):
        # A RETIRED PLUGIN'S REPLAY CACHE GOES WITH IT. The cache is keyed by
        # plugin id and request id; a plugin detached and attached again is a
        # NEW target that has done nothing, and serving it a previous
        # incarnation's response as `replayed: true` would be a lie about a
        # machine that no longer exists.
        live = set(d.id for d in self.registry.descriptors())
        for key in [k for k in self._done if k.split("\x00", 1)[0] not in live]:
            self._bytes -= self._done.pop(key).nbytes
        # And its baseline goes with it, for the same reason: a plugin detached
        # and attached again is a NEW target, and diffing what it says now
        # against what its predecessor said would report a machine's whole
        # state as having "changed" when in truth it was replaced.
        for pid in [k for k in self._seen if k not in live]:
            self._seen.pop(pid, None)
        self.changes += 1
        for fn in list(self._subs):
            try:
                fn(kind)
            except Exception:
                pass

    # -- the four operations ------------------------------------------------
    def manifest(self, token):
        self.policy.authenticate(token)
        self.policy.authorize("READ")
        plugins = self.registry.descriptors()
        tools = []
        for p in plugins:
            for a in p.actions:
                tools.append({
                    "name": tool_name(p.id, a.name),
                    "pluginId": p.id, "action": a.name,
                    "description": a.description, "risk": a.risk,
                    # allowed=false is an instruction to omit the tool for this
                    # session, not a hint. The gateway refuses it regardless.
                    "allowed": bool(self.policy.allow.get(a.risk)),
                    "inputSchema": a.input_schema()})
        return {"protocolVersion": PROTOCOL_VERSION,
                "replayCacheCommands": REPLAY_CACHE_LIMIT,
                "replayCacheBytes": REPLAY_CACHE_BYTE_LIMIT,
                # ADR-191: a client cannot discover a stamp it was never told
                # about. The manifest says the door keeps one look per target
                # and what to pass back, so `since` is part of the contract
                # rather than a trick learned by reading a response closely.
                "session": {"stamp": "every snapshot carries one; it moves when a value a "
                                     "reader could notice moves",
                            "since": "pass the last stamp to observe() to get the CHANGE "
                                     "instead of the snapshot; an unknown stamp gets the "
                                     "whole snapshot and says so",
                            "diff": "every execute response carries the same diff against "
                                    "the last snapshot this session was served",
                            "diffCap": DIFF_CAP},
                "strictArguments": True,
                "tokenMinLength": TOKEN_MIN,
                "risks": list(RISKS),
                "policy": dict(self.policy.allow),
                "redaction": "observe() omits entered values unless "
                             "SENSITIVE_READ is enabled; visible labels may still "
                             "carry data a user typed",
                "plugins": [p.as_dict() for p in plugins],
                "tools": tools}

    def discover(self, token):
        self.policy.authenticate(token)
        self.policy.authorize("READ")
        return [p.as_dict() for p in self.registry.descriptors()]

    def observe(self, token, plugin_id, since=None):
        """A snapshot, or -- given the stamp of the last one -- what CHANGED.

        ADR-187 watched four blind operators re-read a forty-kilobyte snapshot
        after every structural act, because the door had no way to say "two
        controls appeared and one value moved". This is that way. `since` is a
        stamp the door itself issued to THIS session; the answer is the diff
        and not the snapshot, which is the whole saving.

        It fails toward MORE information, never less. A stamp this session has
        no baseline for -- a stamp from another door, one lost when a plugin
        was detached, the first call of a session -- gets the whole snapshot
        and a line saying why, because a diff against a baseline the door does
        not hold would be a fabrication, and silence would be worse."""
        self.policy.authenticate(token)
        self.policy.authorize("READ")
        sensitive = bool(self.policy.allow.get("SENSITIVE_READ"))
        p = self.registry.find(plugin_id)
        snap, raw, st = self._stamped(p, p.observe(sensitive=sensitive))
        prev = self._seen.get(plugin_id)
        if isinstance(snap, dict):
            self._seen[plugin_id] = (st, raw)
        if not since:
            return snap
        if not isinstance(snap, dict):
            return snap
        head = {"protocolVersion": PROTOCOL_VERSION, "pluginId": plugin_id,
                "stamp": st, "since": since, "ready": snap.get("ready")}
        if prev is None or prev[0] != since:
            snap = dict(snap)
            snap["since"] = since
            snap["sinceUnknown"] = (
                "this session holds no snapshot stamped %r for %s, so there is nothing to "
                "compare against and the whole snapshot is here instead"
                % (since, plugin_id))
            return snap
        if st == since:
            head["changed"] = False
            head["diff"] = None
            return head
        head["changed"] = True
        head["diff"] = diff_of(prev[1], raw, self._spec(p, raw))
        return head

    def execute(self, token, plugin_id, command):
        self.policy.authenticate(token)
        rid = command.get("request_id") or command.get("requestId")
        name = command.get("action")
        args = command.get("arguments") or {}
        if not rid or not isinstance(rid, str):
            raise InvalidArgument("every command needs a caller-generated request_id")
        if not isinstance(args, dict):
            raise InvalidArgument("arguments must be an object")
        plugin = self.registry.find(plugin_id)
        key = plugin_id + "\x00" + rid
        body = json.dumps({"a": name, "g": args}, sort_keys=True)

        hit = self._done.get(key)
        if hit is not None:
            if hit.body != body:
                raise Conflict("request_id %r was already used for a different command"
                               % rid)
            # Re-authorised, not merely re-served: a payload captured while a
            # gate was open must not keep flowing after it is closed.
            self.policy.authorize(hit.risk)
            r = dict(hit.response)
            r["replayed"] = True
            return r

        spec = plugin.descriptor().action(name)
        self._validate(spec, args)
        risk, risk_why = self._risk_of(plugin, spec, args)
        try:
            self.policy.authorize(risk)
        except HarnessError as e:
            if e.code != "forbidden":
                raise
            # A call refused at a rung it was RAISED to must say so. "DESTRUCTIVE
            # is not enabled for this session" about an action the manifest calls
            # MUTATE reads as the door contradicting itself; the reason the
            # target gave is the whole of the difference.
            if risk_why:
                raise Forbidden("%s -- %s was raised from %s to %s because %s"
                                % (e.message, spec.name, spec.risk, risk, risk_why))
            raise
        t0 = time.time()
        try:
            ok, message, output = plugin.execute(spec.name, args)
        except HarnessError:
            self.audit.append((time.time(), plugin_id, name, risk, "refused"))
            raise
        except Exception as e:
            self.audit.append((time.time(), plugin_id, name, risk, "failed"))
            raise Failed("%s/%s raised: %s" % (plugin_id, name, str(e)[:200]))
        ms = int((time.time() - t0) * 1000)
        # The snapshot rides every response, and until ADR-120 nobody had said
        # what it costs. Priced here, per response: a client can read how much
        # of a round trip was the action and how much was the target being
        # asked about itself, and a ledger can hold it to a bound.
        t1 = time.time()
        # ADR-191: WHAT THIS ACT DID, beside what the target now is. The
        # baseline is the last snapshot this session was served -- the one the
        # client planned this call from -- so the diff answers the question the
        # client actually has ("did my call land, and what moved") rather than
        # handing back a second copy of the page and leaving it to compare.
        before = self._seen.get(plugin_id)
        snap, raw, st = self._stamped(plugin, plugin.observe(
            sensitive=bool(self.policy.allow.get("SENSITIVE_READ"))))
        if isinstance(snap, dict):
            self._seen[plugin_id] = (st, raw)
        if before is None:
            diff = {"since": None,
                    "why": "this session had not observed %s before this call, so there is "
                           "no baseline to diff against" % plugin_id}
        else:
            diff = diff_of(before[1], raw, self._spec(plugin, raw))
            diff["since"] = before[0]
            diff["changed"] = before[0] != st
        resp = {"protocolVersion": PROTOCOL_VERSION, "requestId": rid,
                "pluginId": plugin_id, "action": spec.name, "risk": risk,
                "declaredRisk": spec.risk, "riskWhy": risk_why,
                "ok": bool(ok), "replayed": False, "message": message,
                "output": output, "ms": ms,
                "snapshotMs": int((time.time() - t1) * 1000),
                "stamp": st, "diff": diff,
                "snapshot": snap}
        n = _bytes(output)
        self._done[key] = _Done(body, resp, risk, n)
        self._bytes += n
        self._trim()
        self.audit.append((time.time(), plugin_id, name, risk,
                           "ok" if ok else "no"))
        return resp

    # -- internals ----------------------------------------------------------
    @staticmethod
    def _spec(plugin, snap):
        """What identity means on this snapshot, asked of the plugin. A plugin
        that raises while answering is treated as one that said nothing: the
        diff goes coarse, which is a worse answer and not a wrong one."""
        try:
            spec = plugin.identity(snap)
        except Exception:
            return {}
        return spec if isinstance(spec, dict) else {}

    def _fit(self, plugin, snap):
        """A snapshot never advertises what this door would refuse (ADR-141).

        `argumentPools` are keyed by the action they are for -- "set-text.selector",
        "pick", "activate.selector" -- and until now every snapshot carried every
        pool, whatever the session was allowed to do. A blind operator was handed
        `activate.selector` with 65 selectors in it and no tool of that name in
        the list: the snapshot advertised what the door then denied, and the
        operator spent moves finding out which of the two was lying.

        The pools for an action this session may not call are withheld and
        NAMED, with the rung that withheld them, so the answer is "you may not
        do that, and here is what you would need" rather than a pool that
        silently goes nowhere. Pools that belong to no action -- selector, pane,
        page -- are facts about the target and are always published."""
        if not isinstance(snap, dict):
            return snap
        pools = snap.get("argumentPools")
        if not isinstance(pools, dict):
            return snap
        try:
            risk_of = dict((a.name, a.risk) for a in plugin.descriptor().actions)
        except Exception:
            return snap
        keep, gone = {}, {}
        for k in pools:
            act = k.split(".", 1)[0]
            r = risk_of.get(act)
            if r is not None and not self.policy.allow.get(r):
                gone[act] = r
            else:
                keep[k] = pools[k]
        if not gone:
            return snap
        snap = dict(snap)
        snap["argumentPools"] = keep
        snap["poolsWithheld"] = [{"action": a, "risk": gone[a],
                                  "why": "%s is not enabled for this session" % gone[a]}
                                 for a in sorted(gone)]
        return snap

    def _stamped(self, plugin, snap):
        """Fit, stamp, and hand back BOTH the served copy and the fitted one.

        The stamp covers the snapshot AS SERVED, so two sessions at different
        rungs get different stamps for the same page and a client cannot be
        handed `unchanged` about a snapshot it was never shown. It is added to
        the copy that leaves and NOT to the one kept as a baseline: a stamp is
        the gateway's own bookkeeping, and a baseline carrying it would make
        every diff report `stamp` as a field that changed -- the door telling
        a client that the answer to "what changed" is "the answer changed"."""
        snap = self._fit(plugin, snap)
        if not isinstance(snap, dict):
            return snap, snap, None
        st = stamp_of(snap, self._spec(plugin, snap))
        served = dict(snap)
        served["stamp"] = st
        return served, snap, st

    @staticmethod
    def _risk_of(plugin, spec, args):
        """The risk THIS call is authorised at, and why (ADR-141).

        Only an action that declared may_rise is asked, and only an answer
        further UP the ladder is taken. A plugin that raises on ignorance is
        doing the right thing; a plugin that raises when it should not costs a
        refusal, which is the safe direction. A plugin that throws while
        deciding is treated as ignorance."""
        if not getattr(spec, "may_rise", False):
            return spec.risk, None
        try:
            got = plugin.risk_for(spec.name, args)
        except HarnessError:
            raise
        except Exception:
            got = ("DESTRUCTIVE", "the target could not say what this call would touch")
        if not got:
            return spec.risk, None
        risk, why = got
        if risk not in RISKS:
            return spec.risk, None
        if RISKS.index(risk) <= RISKS.index(spec.risk):
            return spec.risk, None            # a plugin may raise, never lower
        return risk, why

    @staticmethod
    def _validate(spec, args):
        declared = set()
        for a in spec.arguments:
            declared.add(a.name)
            v = args.get(a.name)
            if a.required and v is None:
                raise InvalidArgument("action %r requires argument %r"
                                      % (spec.name, a.name))
            if v is not None:
                a.validate(v, spec.name)
        for k in args:
            if k not in declared:
                raise InvalidArgument("action %r does not accept argument %r"
                                      % (spec.name, k))

    def _trim(self):
        while self._done and (len(self._done) > REPLAY_CACHE_LIMIT
                              or (self._bytes > REPLAY_CACHE_BYTE_LIMIT
                                  and len(self._done) > 1)):
            k = next(iter(self._done))
            self._bytes -= self._done.pop(k).nbytes


def _bytes(v):
    if v is None:
        return 0
    if isinstance(v, str):
        return len(v.encode("utf-8"))
    if isinstance(v, dict):
        return sum(_bytes(k) + _bytes(x) for k, x in v.items())
    if isinstance(v, (list, tuple)):
        return sum(_bytes(x) for x in v)
    return 16
