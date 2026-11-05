# Planned graph contract (version 1)

`graph.json` is the canonical authored JSON source; `graph.md` is a deterministic derived view. The checked-in example depicts two parallel disjoint builders, independent review, then controller delivery. It is illustrative, never a live status report. Canonical here means one source of truth, not RFC 8785 byte canonicalization.

## Exact structure

The root has exactly `version` (integer 1, not boolean), `kind` (string `planned`), and `nodes` (nonempty array). Each node has exactly:

| Field | Contract |
| --- | --- |
| `id` | Unique lowercase slug matching `[a-z][a-z0-9_-]*` |
| `title` | Nonblank text without ASCII control characters; rendered as escaped text |
| `status` | `planned`, `complete`, `stale`, or `superseded` |
| `depends_on` | Array of unique existing node IDs; all are required |
| `owns` | Array of exclusive repository-relative paths; empty for read-only work |

Unknown fields, duplicate JSON keys (at any depth), nonstandard JSON constants, duplicate IDs/list entries, missing/self/cyclic dependencies and impossible completion claims fail validation. A complete node requires every ancestor complete. An active node (anything except superseded) cannot depend directly or transitively on superseded work. Cycles remain invalid even among retired nodes. No inferred roles or role-specific scheduling rules exist.

## Ownership

Paths use portable ASCII components containing letters, digits, dots, underscores and hyphens, separated by `/`, with an optional trailing `/`. Absolute paths, drives, backslashes, glob patterns, empty/dot/parent components, trailing dots and Windows reserved device names are rejected. Components compare case-insensitively. Each path conservatively claims its entire subtree, with or without a trailing slash: `src` overlaps `src/a.py`; `src/a` does not overlap `src/ab`. Aliased duplicate claims within a node are rejected.

Two non-superseded nodes are potentially concurrent unless one is a transitive prerequisite of the other. Potentially concurrent nodes must have disjoint claims, regardless of claimed completion. Ordered nodes may reuse paths. Reviewers claiming no writes use `owns: []`. This is lexical plan validation, not filesystem locking: symlinks, hardlinks, alternate filesystem aliases, undeclared writes and changes in separate checkouts require controller enforcement. Ownership is scoped to the same logical repository.

## Readiness, blockers and invalidation

`readiness(graph)` returns entries sorted by ID with `ready` and an ordered `blockers` list. Only planned nodes whose entire dependency closure is complete are ready. Other statuses produce a status blocker; every non-complete ancestor produces a dependency blocker sorted by ID. Completion is a human/controller assertion, not verified evidence.

When a relevant head, input or acceptance criterion changes, the controller marks affected work `stale`, including previously complete descendants. Stale work cannot satisfy dependencies and is not automatically runnable. To redo it, explicitly revise the plan and reset it to planned. To replace work, mark it superseded, add a new unique ID and rewire all active dependents before validating; no automatic replacement inference occurs. Update affected completion assertions as well. The validator rejects contradictory snapshots; it does not perform transitions or persist runtime state.

This component does not schedule T3, inspect PRs, grant merge eligibility, or replace `agent_workflow_pilot.gate`. Independent exact-head review and fresh protected-delivery evidence remain controller responsibilities.

## Commands and exit codes

Run from the repository root with Python 3.12 and locked dependencies:

```powershell
uv run --locked python -m agent_workflow_pilot.graph docs/orchestration/graph.json
uv run --locked python -m agent_workflow_pilot.graph docs/orchestration/graph.json --output docs/orchestration/graph.md
uv run --locked python -m agent_workflow_pilot.graph docs/orchestration/graph.json --check docs/orchestration/graph.md
uv run --locked pytest
```

Default output is UTF-8 Markdown on stdout. `--output` writes UTF-8 without BOM and LF endings. `--check` compares exact bytes without writing; a missing or outdated view fails. Validation always precedes writing. Success is 0, invalid input/read/write/check failure is 1, argument misuse is 2. Nodes and displayed lists sort lexically, so source ordering does not affect rendering. JSON source formatting is unconstrained; Markdown is the reproducible artifact. No dependencies beyond the Python standard library are added.
