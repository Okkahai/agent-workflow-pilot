# Task/context envelope v1

`agent_workflow_pilot.task_context` adds a compact, closed JSON envelope beside
existing engines. No graph, program, checkpoint or handoff schema changes.
It reads local sources only; text and command strings stay inert. It neither
collects host state nor executes acceptance commands, schedules or grants authority.

## Original M1 field coverage

| Original requirement | Existing source / envelope field | Validation |
| --- | --- | --- |
| Identity and objective | roadmap task id/spec; task_id, repo, objective | independent task/repo/head arguments, nonblank bounded text |
| Scope and exclusions | approved brief/spec; scope, exclusions | required nonempty bounded text arrays; spec content hash |
| Acceptance | task brief; acceptance; handoff.tests | nonempty checks, existing handoff result/head validation |
| Dependencies and ownership | roadmap depends_on, owns; graph v1 | exact roadmap equality; program reuses graph DAG/path/overlap validation |
| Worker and routing | owner, routing | nonblank bounded text; explicit dispatch remains Coordinator responsibility |
| Risk and decisions | risks, decisions | nonempty bounded arrays; decisions are rationale, never approval |
| Evidence and revision | handoff v1; head, plan_hash, spec, context | handoff validator; program fingerprint; byte hashes of local references |
| Recovery and next action | context, next_action | bounded local references, fresh rehash, required next action, deterministic context_hash |
| Runtime/lifecycle references | checkpoint refs/CI/review and handoff evidence | checkpoint remains lifecycle owner; handoff evidence is self-reported, never collected or promoted here |

The envelope contains exactly: schema, task_id, repo, head, plan_hash, spec,
objective, scope, exclusions, acceptance, depends_on, owns, owner, routing, risks,
decisions, context, next_action, handoff. Schema is
`agent-workflow-pilot.task-context/1`. `handoff` is an unchanged complete handoff/1
record. `spec` and each `context` entry contain exactly `path` (portable repository
relative file path) and `sha256` (SHA256 of source bytes). No URLs, traversal,
Windows aliases or escaping filesystem redirects are followed. Context has 1..20
unique entries. The spec may also appear in context. Text arrays have 1..20 entries
of 1..1000 characters. Total envelope input is at most 64 KiB, strict JSON.

## Build and reload

Use `reference(root, path)` for source hashes and
`program.fingerprint(plan, plan_directory)` for plan_hash. This fingerprint binds
all roadmap task specifications; changing even another spec invalidates it.
Design/spec identity is distinct from the current implementation head: never put
the final commit SHA into a committed document that changes that SHA.

Save the final envelope outside committed source, after the final push. Call:

```powershell
$head = git rev-parse HEAD
uv run --locked python -m agent_workflow_pilot.task_context C:/Temp/m1-context.json --root . --plan docs/program/roadmap.json --current-head $head --task-id m1-gap --repo Okkahai/agent-workflow-pilot
```

Run the command again in a fresh process to reconstruct the same compact pack and
context_hash. API: `reconstruct(doc, root, plan_path, current_head=..., task_id=...,
repo=...)`. `canonical(doc)` returns deterministic UTF-8 bytes (object key order
ignored, list order preserved). CLI returns 0 with the reconstructed context or
1 with an inert error; argument misuse returns 2. It writes no files.

The Coordinator must independently obtain the expected repo, task and current
head (host PR head for delivery), compare checkout cleanliness/diff, and inspect
sources. Supplying a record's own head as expected head is circular. Hashes prove
consistency only. They do not prove source authenticity, tests, dependency
completion, live CI, review, permissions or authorization. Preserve unresolved
unknowns in handoff. Never replay next_action automatically. On stale data stop,
reconcile sources and obtain a new record; never use old claims to advance state.
