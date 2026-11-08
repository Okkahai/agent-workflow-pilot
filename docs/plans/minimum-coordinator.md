# Minimum Coordinator autonomous delivery MVP

Authorized 2026-11-08. Baseline main 1225c72d9d69fdd3b4856e4f6a58e6dc0fb5b4b5. No merge authorization. User requests autonomous execution, including planning, implementation, draft PR and independent remote review.

## Design and ownership

Use native T3 delegation/worktrees/completion wakeups and PR watching. Do not build a scheduler, daemon, credentials store or competing task tracker. Existing graph is a sample, not a roadmap. This is the current bounded milestone following the read-only collector; no external project adoption or multi-coordinator architecture.

Windows Builder owns a minimal stdlib recovery-state component under src/agent_workflow_pilot/controller, its tests and focused runbook documentation. Coordinator owns local live execution checkpoint and readiness evidence. Reuse existing validators, atomic JSON conventions and policy gate where useful; keep handoffs untrusted and gate separate. No new dependencies or CI/protection changes.

Persist a stable task key, acceptance/dependencies, lifecycle, retry budget/blockers and references to native environment/provider/task/thread/branch/PR/head/CI/review records. T3/GitHub remain authoritative; references/checkpoints are not evidence authentication or merge authorization. Support duplicate/replayed events idempotently, reject stale SHA evidence, clear evidence on new head, bound correction retries, distinguish blocked/complete/awaiting authorization. Single trusted writer is sufficient; explicitly document crash windows around remote side effects and recovery reconciliation rather than promising exactly-once remote execution.

## Steps and acceptance

1. Inventory and synchronization (Coordinator): preserve existing local PR12 records; synchronize main; inspect native capabilities and real planning/readiness files.
2. Implementation (isolated Windows Builder): smallest useful lifecycle/checkpoint helper and CLI if helpful, tests for transitions/idempotence/stale evidence/retries/resume and atomic persistence; operational T3 recipe for build -> CI wake -> remote exact-head review -> correction -> readiness. Run uv run --locked pytest. Commit/push normally, create one draft PR. Return exact SHA, PR, worktree and checks automatically. No merge or child delegates.
3. Real run (Coordinator): independently verify PR/head/CI/protections, use native watch for pending CI, delegate Ubuntu public read-only exact-head analysis (no PR code execution), receive result automatically; new head invalidates CI/review. Corrections go to Windows worktree, at most two correction rounds before escalation. Save actual IDs and outcomes.
4. Delivery: draft PR remains draft/unmerged. Persistent report names verified execution, synthetic unit-test coverage and untested recovery/correction paths separately. No background continuation claim beyond native tool contracts.

## Recovery

Stable run identity minimum-coordinator-mvp-20261108. Before launching, record dispatch intent and clientRequestId. On interruption read checkpoint then native task/thread and GitHub branch/PR; reuse existing artifacts, never blindly launch a second task/PR. Ambiguous dispatch is blocked pending reconciliation. Completion means report ready; merge always awaits explicit authorization.
