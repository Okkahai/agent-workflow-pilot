# Rich planning and context contract

Approved scope: docs/plans/m1-gap-completion.md. Implement the bounded
machine-validated task/context envelope beside the existing engines.

Acceptance: strict positive/negative regressions, deterministic fresh-process
recovery with independently supplied identity, full `uv run --locked pytest`,
focused draft PR and actual final-head Builder handoff for Coordinator validation.

Ownership: src/agent_workflow_pilot/task_context.py, tests/test_task_context.py,
docs/orchestration/task-context/; this task specification is updated under the
approved plan. Mapping and recovery contract: docs/orchestration/task-context/README.md.

Dependencies: m1-core (roadmap design dependency; completion independently checked).
Routing: Windows Builder codex/gpt-6.1-sol medium. No fallback or subdelegation.
Independent Ubuntu exact-head review remains the Coordinator's responsibility.
Risk: stale or self-reported evidence must never promote completion.
Decision: reuse graph paths/DAG, handoff strict parsing/validators and program
fingerprinting; preserve existing closed schemas and lifecycle engine.
Exclusions: other gaps, PR14, installers, skill assets, settings, permissions,
services, dependencies, protections, CI edits, merge and ready transitions.
Next action after draft delivery: Coordinator independently resolves host head,
validates the actual returned envelope, reconstructs it in a fresh process and
obtains independent exact-head review. This document grants no merge authority.
