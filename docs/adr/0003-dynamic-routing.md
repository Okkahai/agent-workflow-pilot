# ADR 0003: bounded dynamic provider routing as a pure validator

Status: accepted for this pilot, 2026-11-09. Builds on ADR 0001 (policy core separate from adapters) and ADR 0002 (coordinator-led control plane, no duplicated scheduler). Spec: docs/plans/dynamic-provider-routing.md.

## Context

The user approved explicit routing defaults across Codex (Sol, Terra) and Claude (Sonnet, Haiku), automatic Sonnet/Sol fallback, and cross-provider final review. T3 already provides async delegation, cancellation, PR watch, and explicit provider/model/effort targets. It exposes no quota-reading tool; Claude `/usage` and Codex `/status` are interactive displays. Existing M1 contracts (handoff, task-context, checkpoint) already carry recovery state.

## Decision

1. Add one stdlib module and one versioned JSON policy. The module validates and decides; it never executes, polls, schedules, scrapes quota or merges. The caller (Coordinator) resolves identity, head, live capabilities and usage independently and performs every native call.
2. Persist a small attempts sidecar that references the existing delivery checkpoint, task-context hash and native IDs. Do not change handoff, task-context or checkpoint schemas and do not create a second context format.
3. Intent is persisted before a native call. Replay never grants dispatch. Ambiguous writer, children or dispatch hold the slot. Only Sonnet and Sol implementation switching is automatic.
4. Final readiness requires opposite-underlying-provider, non-author, exact-head review for each author provider; the existing gate stays required.
5. Unknown subscription capacity stays unknown. Thresholds apply only to genuine current measured telemetry; the Claude reserve is advisory. Tokens and elapsed time are separate metrics.
6. The universal policy holds provider/model/effort facts only; project and pilot specifics live in project state.

## Alternatives considered

- Extend the checkpoint with routing fields: breaks checkpoint v1 compatibility and widens an existing core. Rejected for a sidecar.
- A routing daemon or quota scraper: duplicates T3, needs credentials, relies on unsupported private APIs. Rejected.
- Hard-code model names in code: IDs change per session and per project. Rejected for a policy file checked against the live snapshot.
- Allow high effort or Opus when blocked: silent cost escalation. Rejected; a human may decide outside the router.
- Treat different models of one provider as independent review: shares the provider and its failure modes. Rejected.

## Consequences

- Single trusted writer and a local filesystem only; no exactly-once or crash guarantee. A crash between intent and native call needs controller reconciliation.
- Safety depends on the Coordinator supplying honest expectations; hashes and records prove consistency, not authenticity.
- A policy edit creates a new `policy_sha256` and requires an explicit migration; old records fail closed.
- Live provider behavior (including whether T3 can reuse an isolated checkout without full-history injection) is not established by this change; tests are mocked or local-file and labelled so.
- Portability work (PORT-01 to 03, CONT-01) is deferred and tracked in docs/readiness/routing-gap-register.md.
