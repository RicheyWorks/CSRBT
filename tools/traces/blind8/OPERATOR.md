# OPERATOR.md — how to drive the door

You are operating a web science page you have never seen, through one door and
nothing else. You have a **brief** (a goal, the values to enter, and counts of
what it will be graded on) and this file. You do NOT have the page's source,
the task, or the grader. Work only through the console below.

## The console

    python3 tools/blind_console.py --session op --target page \
            --page <PAGE>.html --rungs SENSITIVE_READ,DRAFT,MUTATE,DESTRUCTIVE \
            --moves moves.json --trace <TRACE>

The FIRST call needs `--target page --page <PAGE>.html --rungs ... --trace <path>`
and starts a door that stays alive. EVERY LATER call needs only
`--session op --moves next.json` — same door, same page, the store remembers
everything you entered, and a stamp you read in one call is still the door's
baseline in the next. Close with `--session op --end` when the goal is done.

`moves.json` is a JSON list. Each move is one of:

    {"list": true}                                  list the tools (do this first)
    {"read": "harness://csrbt-page/snapshot"}       read the whole page state
    {"observe": "csrbt-page"}                        the snapshot, with a fresh stamp
    {"observe": "csrbt-page", "since": "<stamp>"}    only WHAT CHANGED since that stamp
                                                     (any of the last 8 snapshot stamps this
                                                     session was served — a stamp you read
                                                     BEFORE a batch of acts is a baseline too)
    {"call": "<tool>", "arguments": {...}}           do something to the page

Every move's whole answer is printed as JSON, in order. Plan the next move from
what the door actually answered — that is all a real host has too.

## Discovery

Call `{"list": true}` for the tools (each carries `_meta` with its plugin id,
action and risk). `{"read": "harness://csrbt-page/snapshot"}` once gives the
whole page: every control with an `address`, the pick pools, the boxes, the
figures, the rules. It is large; read it ONCE, note the stamp it carries, and
`observe` with `since` from then on to see only what your last move changed.

## Addressing a control

A tool's `selector` argument takes an address. Prefer, in order:

    "#someId"              the control's id
    "@Visible label"       its visible label (or "@Host/label" when a label repeats)
    "kind:index"           a positional address from the snapshot (stamped)

`read-report` figures and boxes are read from the snapshot; `read-control`
gives one control's current value and address.

## Two things you may say about a call (use them)

A `call` move may carry either or both:

    {"call": "csrbt_page__activate", "arguments": {"selector": "@Undo"},
     "if_stamp": "<a stamp you just read>"}

    {"call": "csrbt_page__set_text", "arguments": {"selector": "#x", "text": "5"},
     "expires_at": "2026-09-18T23:00:00+00:00"}

- **`if_stamp`** — a SNAPSHOT stamp (see the two kinds below). The door acts
  ONLY IF THE TARGET IS STILL THAT; if the page moved under you it refuses
  `stale`, naming the stamp it was bound to and the stamp the target has now,
  instead of acting on a page that changed since you looked. Use it to guard an
  irreversible act (an Undo, a Clear) against a page that moved between your
  read and your press.
- **`expires_at`** — an ISO-8601 instant with an offset (`...+00:00`). At or
  after it the command is refused `stale` rather than run late.

Neither is part of the command's identity; a retry with a fresh deadline is the
same request. A move naming neither is a plain call.

## Two kinds of stamp — the first character says which

    s + 12 hex   a SNAPSHOT stamp: on every snapshot/observe answer and on every
                 call's response as `stamp`. `observe ... since` and `if_stamp`
                 take THIS one.
    r + 12 hex   a REPORT stamp: on every `read-report` answer at `output.stamp`
                 (the answer's TOP-LEVEL `stamp` is the snapshot's, as on every
                 response). `read-report`'s own `since` argument takes THIS one.

Both doors hold the last 8 stamps they served as baselines: `since` any of
them and you get the change since THAT look. So after a batch of acts, ask
`observe since=<the stamp you read before the batch>` to see everything the
batch changed in one answer.

Hand a door the other kind and it says so by name (observe / read-report answer
the whole document and tell you which kind they were given; `if_stamp` refuses
`invalid_argument` and runs nothing).

## The refusal vocabulary

- `invalid_argument` — the call itself is wrong; fix it.
- `not_found` — no such control/tool by that address; look again.
- `stale` — it was right when you read it, not now; read again and decide again.
- `forbidden` — the action's risk is above the rungs you were granted.

## What to do

Enter every value the brief lists, into the control it names, reading the page
back to confirm each figure the brief implies is right. When the brief's RUNGS
line names DESTRUCTIVE, the goal includes an irreversible step (an Undo, a
Clear, a remove) — do it, and guard it with `if_stamp` from the read you based
it on. Stop when the goal is met. Keep `--trace` on for every call.
