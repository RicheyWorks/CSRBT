# Traces — provenance

Each `<task-id>.jsonl` here is what an operator did through the MCP door
(`tools/harness_mcp.py --trace`), one JSON line per `tools/call` and per
`resources/read`, with the gateway's whole response. They are graded
against `tools/tasks/<task-id>.json` by `harness_tasks.py --grade-trace`.

**These six were produced on 2026-09-02 by the assistant of the session that
built ADR-126 (Claude), acting as the operator**: for each task it was given
the task's `goal` sentence and the server's `tools/list` and `resources/list`,
planned its own calls, and drove the door over JSON-RPC. It was not given the
task's steps, and its arguments differ from theirs (other keys, another lag,
eight shuffled keys where the task writes five, the page's first text control
found from the snapshot's pool rather than named). It is not a blind trial —
the same session had written the tasks earlier that day — and the ADR says so.
It is the first trace of a model operating the organism, the lab and a page
from the goal alone, and the grader's first real customer.

To add a trace: run the server with `--trace tools/traces/<task-id>.jsonl`,
operate, then `python3 tools/harness_tasks.py --grade-trace all`.
