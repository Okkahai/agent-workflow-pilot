# Routing: policy, attempts and review validation

`agent_workflow_pilot.routing` is one stdlib module of pure functions plus a small stdin JSON CLI. It turns facts a trusted controller already resolved into machine-readable decisions and checks. It performs no network, provider SDK, credential or quota collection, scheduling or merging, and every result carries `authorizes: false`. Validity is not authority. Policy and rationale: [model-routing.md](model-routing.md); decision record: docs/adr/0003-dynamic-routing.md.

Contracts are closed: unknown fields, wrong scalar types (booleans are not numbers), blank text, bad SHAs and oversized or duplicate-key JSON are rejected with a `ValueError` that names fields, not values. Strict parsing reuses `handoff.parse` and the bounded readers in `task_context`. The M1 handoff/1, task-context/1 and checkpoint v1 formats are unchanged and are reused, not replaced.

## Identity and fail-closed binding

Four values are separate everywhere: `project` (slug), `repo` (`owner/name`), `task` (logical task slug, equals the roadmap task and survives provider switches) and `attempt` (one execution try). On every operation the caller passes an independent **expectation** and the record is compared against it, never against itself: project, repo, task, `plan_hash`, `context_hash`, `scope_sha256`, `retry_budget`, current `head`, `branch`, `worktree`, `pr` (string or null). Any mismatch, including another project's record, a stale plan or context hash, a changed scope or retry budget, or a changed policy version, raises. The expectation must come from the host (current PR head, checkout), not from the record or an agent's claim.

## Policy (`harness/policies/routing-v1.json`)

Closed, versioned, content-addressed (`validate_policy` returns the sha256 of its canonical form). Sections: `providers` (instance name to underlying provider and effort option name), `targets` (name to provider, model, effort), `roles` (primary, alternates, `auto_switch`), `categories` (closed list: program, delivery, planning, architecture, standard, complex, bugfix, mechanical, docs), `capabilities`, `forbidden` (efforts, model substrings, options), `usage` (thresholds, freshness, advisory reserve), `snapshot_max_age_seconds`, `max_attempts`. It contains no project IDs, pilot milestones, native environment IDs or absolute paths; the caller supplies the path or object. Invalid by construction: a forbidden effort/model/option, enforced reserve, automatic switching for program, delivery, mechanical or docs, unknown or duplicate targets, auto-switch outside the alternates.

## API

All callables are in `agent_workflow_pilot.routing`.

| Callable | Purpose |
| --- | --- |
| `validate_policy(doc) -> sha256`, `load_policy(path) -> (doc, sha256)` | Validate the policy. |
| `decide(policy, request) -> decision` | Route, candidate or stop. |
| `usage_state(policy, project, now, observations)` | Per-provider level from trusted observations (used by `decide`). |
| `scope_sha256(scope) -> sha256` | Hash of the approved scope/acceptance the attempts must preserve. |
| `new_record(policy, *, project, repo, task, plan_hash, context_hash, scope_sha256, retry_budget, checkpoint_key, workspace)` | Create the attempts sidecar. `workspace` is `{branch, worktree, pr}`. |
| `validate_record(rec, policy)` | Closed structural and invariant validation. |
| `apply(rec, policy, expected, event_id, action, data, cp=None) -> (record, outcome)` | Pure transition. `cp` is the loaded delivery checkpoint (required for `intent`). |
| `recover(rec, policy, expected, cp, *, context_hash=None)` | Fresh-process state: slot `free` or `held`, with reasons. Never dispatches. |
| `validate_reviews(rec, policy, expected, reviews)` | Final-review coverage check. |
| `save(path, rec)` | Atomic replace (temp file, fsync, `os.replace`), one trusted writer, local filesystem. |

### `decide(policy, request)`

`request` fields (all required): `project`, `repo`, `task`, `attempt`, `head` (40-hex), `now` (ISO-8601 with timezone), `classification`, `snapshot`, `usage`, `metrics`.

- `classification`: `category`, `complexity` (`low|standard|high`), `architecture_risk`, `security_risk` (`none|low|high`), `required_capabilities` (subset of `child_tasks`, `cross_provider`), `context` (text), `budget` (`{max_attempts}`), `verification_cost` (`low|medium|high`). It is explanatory and filtering input. It never approves scope and never changes the target or effort.
- `snapshot`: `{observed_at, source_ref, providers: {name: {enabled, child_tasks, cross_provider, models: {id: {efforts: [...]}}}}}` taken from the live `orchestrator_capabilities` result. Older than `snapshot_max_age_seconds` or from the future: `stop` with `stale_capabilities`.
- `usage`: list of `{provider, project, window: session|weekly, remaining_percent, observed_at, source_ref, basis: measured|user_estimate|cached_display|unsupported}`. Only fresh `measured` readings for the same project and provider are trusted.
- `metrics`: `{tokens, elapsed_seconds, attempts}`, each non-negative int or null; echoed, never used as quota.

Result: `decision` is `route` (policy primary, or an automatic Sonnet/Sol `fallback` when the primary is blocked), `candidate` (approved alternate requiring caller choice), or `stop` with `reasons`. A route carries `route = {target, provider, model, effort, options}` where `options` is ready for `delegate_task target.options` (`{"reasoningEffort": "medium"}` or `{"effort": "medium"}`). `blocked` lists per-target reasons: `provider_missing`, `provider_disabled`, `model_missing`, `effort_missing`, `capability_missing:*`, `usage_exhausted`, `usage_restricted_heavy_work`. A `route` with `fallback` is still not permission to start work: the caller must first record an `intent` through `apply`.

### Attempts sidecar and `apply`

The sidecar (`agent-workflow-pilot.routing-attempts/1`) holds identity, `policy_sha256`, `plan_hash`, `context_hash`, `scope_sha256`, `retry_budget`, the delivery `checkpoint_key`, the workspace, ordered `attempts` and event receipts. It references the existing checkpoint and native IDs only; it copies no transcripts or GitHub/T3 results. It is not a second context format: context stays an M1 task-context envelope, referenced by `context_hash`.

Actions (event IDs are slugs; an identical replay returns the saved record with `dispatch_allowed=false`; the same ID with another payload raises):

| Action | `data` | Effect |
| --- | --- | --- |
| `intent` | `attempt, role, target, client_request_id` | Persist intent **before** the native call. Only this call returns `dispatch_allowed=true`. |
| `started` | `attempt, native{task,thread}, returned{provider,model,effort}` | Reconcile returned native IDs and the actually returned route; `route_match` records any difference. Duplicate native IDs across attempts are rejected. |
| `terminal` | `attempt, outcome, writer="none", children[]` | Only with the writer gone and every child terminal. |
| `release` | `attempt` | Controller asserts a never-reconciled intent never reached native dispatch. |

Rules for `intent` (all must hold, else `ValueError`): the previous attempt is terminal with writer `none` and known, terminal children; unknown dispatch, writer or children hold the slot; checkpoint belongs to the same `checkpoint_key`, has the same retry budget and is not `blocked`; for a second or later attempt the checkpoint `head`, `refs.branch` and `refs.pr` equal the freshly observed values; the attempt count is below `max_attempts`; the role is unchanged; the target either equals the predecessor (correction) or both are in `{primary} + auto_switch` of the role. Therefore only Sonnet and Sol implementation switching is automatic. A changed head must be applied to the checkpoint first (`checkpoint.apply(..., 'head', head=...)` clears CI and review); a routing record cannot launder it. Partial work and the original PR are preserved: nothing resets, force pushes or opens a new PR. Replay and `recover` never grant dispatch. There is no exactly-once or crash guarantee: a crash after the intent write and before the native call leaves the slot held until the controller inspects native state and applies `started` or `release`.

### `validate_reviews`

`reviews` is a list of `{provider, model, effort, native_task, project, repo, task, head, authored, findings[], evidence_ref}`. Authors are the reconciled attempts; their provider is the **returned** route mapped through the policy `providers.*.underlying`. For each author provider there must be a review by a different underlying provider at the exact current head, same project/repo/task, `authored=false`, a native task that is not an author task or thread, non-blank evidence reference and no open findings. Mixed authorship therefore needs both coverages. Provider instance aliases cannot masquerade: identity comes from the policy, not the review. A non-terminal attempt, a route mismatch, stale head or cross-project evidence yields `ready=false` with `problems`. The result never merges; the existing fail-closed delivery gate (`gate.py`) is still required.

## CLI (fresh-process reload)

```powershell
uv run --locked python -m agent_workflow_pilot.routing policy harness/policies/routing-v1.json
Get-Content request.json | uv run --locked python -m agent_workflow_pilot.routing decide --policy harness/policies/routing-v1.json
Get-Content init.json    | uv run --locked python -m agent_workflow_pilot.routing init attempts.json --policy harness/policies/routing-v1.json
Get-Content event.json   | uv run --locked python -m agent_workflow_pilot.routing apply attempts.json --policy P --expected expected.json --checkpoint checkpoint.json
uv run --locked python -m agent_workflow_pilot.routing recover attempts.json --policy P --expected expected.json --checkpoint checkpoint.json [--context ctx.json --root . --plan docs/program/roadmap.json]
Get-Content reviews.json | uv run --locked python -m agent_workflow_pilot.routing reviews attempts.json --policy P --expected expected.json
```

`init` stdin is the `new_record` keyword arguments; `apply` stdin is `{event_id, action, data}`; `reviews` stdin is the review list; `now` defaults to the process clock in `decide` only. `--context` reconstructs the existing M1 envelope with `task_context.reconstruct` (expected head, task and repo) and requires its `context_hash` to equal the record's, so a stale plan, spec or context blocks recovery. Exit 0 success; 1 refused or `ready=false` with `{"ok": false, "error": ..., "dispatch_allowed": false}`; 2 usage error. The CLI writes only the named record, atomically.

## Official sources and runtime schema

The installed schema wins over any snippet. Observed 2026-11-09: `orchestrator_capabilities` and `delegate_task` expose codex Sol/Terra and claudeAgent Sonnet/Haiku with child and cross-provider tasks; Codex `reasoningEffort`, Claude `effort`; no quota-reading tool; Codex CLI 0.167.0, Claude Code 2.1.319. Dated documentation consulted: T3 [orchestrator MCP server](https://github.com/pingdotgg/t3code/blob/main/docs/orchestration-v2/orchestrator-mcp-server.md) (explicit targets, native completion/cancellation, options validated natively, fresh delegates get task-only context); Claude Code [costs](https://code.claude.com/docs/en/costs) and [skills](https://code.claude.com/docs/en/skills) (token accounting is separate from plan usage; `/usage` may show cached bars); Codex [skills](https://learn.chatgpt.com/docs/build-skills), [subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) and [pricing](https://learn.chatgpt.com/docs/pricing) (explicit/inherited model configuration, variable limits, interactive `/status`).

## Immutable invariants and regression mapping

| Invariant | Enforced and tested by |
| --- | --- |
| Output never grants authority, dispatch or merge | `authorizes=false` in every result; `test_replay_never_grants_dispatch_and_changes_nothing`, CLI tests |
| Closed contracts, strict scalar types | `test_invalid_request_rejected`, `test_policy_rejects`, `test_hostile_types_raise_only_value_error` |
| No escalation beyond approved targets | `test_policy_rejects`, `test_risk_complexity_budget_never_change_cost`, `test_no_forbidden_escalation_ever_offered` |
| Unknown quota stays unknown | `test_unknown_stays_unknown_and_partial_is_flagged`, `test_untrusted_telemetry_cannot_masquerade`, `test_threshold_edges` |
| Separate project/repo/task/attempt identities, fail closed | `test_cross_project_stale_and_mismatched_records_fail_closed` |
| One writer; ambiguous dispatch/writer/children hold the slot | `test_active_attempt_holds_slot_for_every_state`, `test_ambiguous_writer_or_children_cannot_terminate` |
| Safe Sonnet/Sol switch only; scope and budget preserved | `test_safe_*`, `test_only_sonnet_sol_implementation_switch_is_automatic`, `test_switch_requires_fresh_matching_repo_state` |
| Head change clears CI/review through the checkpoint | `test_changed_head_clears_ci_review_and_stale_checkpoint_blocks_switch` |
| Cross-provider, non-author, exact-head review | `test_claude_author_needs_codex_reviewer`, `test_mixed_authorship_*`, `test_provider_alias_*`, `test_review_rejections` |
| Fresh-process reload and M1 context reuse | `test_cli_persistence_replay_switch_and_review_across_fresh_processes`, `test_cli_recover_reuses_real_m1_context_*` |

PC1-PC3 and M1 tests remain unchanged and passing. Fixtures in `tests/test_routing.py` are mocked policy inputs or real local files; none is live T3 or provider behavior.

## Portability boundaries and migration

Reusable core: `routing.py` plus the policy file. It needs no pilot globals, milestone IDs, paths or environment IDs; a project supplies its own policy file, expectation and state paths. Remaining pilot coupling, deferred and tracked in [routing-gap-register.md](../readiness/routing-gap-register.md): pilot M1 to M5 enum and schema names and the `roadmap.json` convention; local evidence storage layout; onboarding that distributes skills and validators but not the controller; installation packaging and import paths (`agent_workflow_pilot` is not yet a shared package); immutable policy-version migration (a changed policy requires an explicit new record, `policy_sha256` is checked); checkpoint sidecar compatibility (the sidecar only references checkpoint v1 and must be re-verified on any checkpoint version bump); and tests with two independent repositories of different stacks, roots and repo IDs. Not claimed: that routing closes any of these.
