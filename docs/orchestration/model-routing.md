# Model routing

Status: user-approved defaults, observed 2026-11-09. Machine-readable source of truth: `harness/policies/routing-v1.json` (validated and applied by `agent_workflow_pilot.routing`, see [routing.md](routing.md)). This page explains the policy. It supersedes the 2026-11-05 text (Astra defaults, same-model review as "weaker independence", no fallback) and the 2026-11-08 local override. Both are kept only as dated evidence (see Provenance). Routing is an execution choice, never correctness evidence (engineering-standard.md).

## Rule

Route from the capabilities the controller actually sees advertised in the current session (`orchestrator_capabilities`) and from the installed `delegate_task` schema, never from memory or from this table. Every model ID and effort value is checked against that live snapshot before use; a missing ID, effort or capability means stop or an explicit approved candidate, never a silent substitute (t3-runbook.md). A policy edit changes `policy_sha256`; recorded attempts keep the version they started under and migrating is explicit.

## Approved defaults (policy v1)

| Role (categories) | Primary | Approved alternative | Automatic switch |
| --- | --- | --- | --- |
| Program and delivery coordination (`program`, `delivery`) | Codex `gpt-6.1-sol`, `reasoningEffort=medium` | none | no |
| Planning, architecture, standard and complex Builder (`planning`, `architecture`, `standard`, `complex`) | Claude `claude-sonnet-5-5`, `effort=medium` | Sol medium | yes, Sonnet and Sol only |
| Scoped bugfix Builder (`bugfix`) | Sol medium | Sonnet medium | yes, Sonnet and Sol only |
| Mechanical (`mechanical`) | Codex `gpt-6.1-terra`, `reasoningEffort=low` | none | no |
| Docs (`docs`) | Terra low | Claude `claude-haiku-5-5`, `effort=low` | no: candidate only, caller chooses |

Provider-specific effort descriptors differ (`reasoningEffort` for Codex, `effort` for Claude); the router emits the exact `target.options` entry for the chosen provider. Sol is the Codex model for Coordinator work; Terra is its cheaper tier; Sonnet and Haiku are Claude tiers. These names carry no benchmark claim.

## Escalation and independence rules

- No automatic expensive escalation: no Opus, Astra, Fable, no `high`, `xhigh`, `max`, `ultra`, `ultrathink`, `ultracode`, no `fastMode` or `serviceTier`. The policy validator rejects such a policy. Task complexity, architecture or security risk, and verification cost can only mark work as heavy (relevant while usage is restricted); they never upgrade the model or effort, and never waive a safeguard. A human may choose to escalate outside this router.
- Only Sonnet and Sol implementation switching is pre-authorized, and only through the checked attempt protocol (routing.md). Other missing targets stop, or surface an approved candidate that the caller must choose.
- Final review must come from a different underlying provider than each code-author provider. Same-provider review, including a different Codex model reviewing Codex work, is not independent and does not satisfy final readiness. Mixed authorship needs both coverages. Reviewers are read-only, fresh per exact head, and never authors.

## Usage and quota

Telemetry is optional, caller-supplied, current and attributable (provider, project, window, source reference, timestamp). The installed T3 schema exposes no quota-reading tool. Claude Code `/usage` and `/status` and Codex `/status` are interactive displays and may be cached; they do not authorize scraping private APIs. Therefore nothing is assumed:

| Worst known remaining | Level | Effect |
| --- | --- | --- |
| above 35 | normal | none |
| 15 to 35 inclusive | conserve | advisory; routing proceeds |
| below 15 | restrict | heavy new work is not routed to that provider |
| 0 | exhausted | provider is not routed to |
| no trusted current reading | unknown | stays unknown; never triggers a switch |

Both session and weekly windows are tracked; the worst known value wins; a single known window is flagged as partial knowledge. User estimates, cached displays, unsupported readings, stale or other-project readings and ambiguous duplicates are recorded as untrusted and count as unknown. The roughly 20% Claude reserve is advisory (`enforced` must be false in the policy) because no mechanism can enforce it. Tokens, elapsed time and attempt counts are separate attributable metrics, not percentages, dollars or proof of savings.

## Coordinator-led control plane

One coordinator thread owns plan, delegation, evidence collection, gate and merge. T3 provides the scheduler primitives (async `delegate_task`, `task_cancel`, PR watch); see docs/adr/0002-control-plane.md and docs/adr/0003-dynamic-routing.md. The router is a pure validator: it does not execute, poll, schedule, collect credentials or merge. Child tasks return a typed handoff (handoff.md) and never merge or spawn agents. Reuse of an isolated checkout requires a supported native mechanism; if T3 cannot reuse it without injecting the full prior history, report that limit rather than inventing support.

## Provenance and limits

- Prior local policy and audit (2026-11-08 user routing override, Coordinator Sol medium, Astra for implementation) are preserved byte-identical by the Coordinator under `docs/readiness/dynamic-routing/` (`model-routing-before.md`, `model-routing-audit-before.json`) outside this branch. They are dated evidence only, not active defaults.
- Capability facts are a dated observation (2026-11-09): codex Sol/Terra and claudeAgent Sonnet/Haiku available with child and cross-provider tasks; Codex CLI 0.167.0, Claude Code 2.1.319. Source of truth is always the live schema; official docs are linked in routing.md.
- Quality and cost comparisons between models remain unmeasured hypotheses. The deferred benchmark protocol is not part of this change; run it only when a decision depends on it and the user authorizes the usage budget.
- Advertised is not tested: no live run of any ID is claimed here beyond what the Coordinator records separately.
