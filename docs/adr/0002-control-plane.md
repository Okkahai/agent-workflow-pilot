# ADR 0002: coordinator-led control plane, no duplicated scheduler

Status: accepted for this pilot, 2026-11-05. Builds on ADR 0001 (policy core separate from delivery adapters).

## Context

T3 Code advertises async delegation with completion wakes, cancellation, scheduled tasks, thread management and PR watch (`orchestrator_capabilities` features observed this session). The repo already has a planned graph (docs/orchestration/graph.md), a typed handoff validator and a fail-closed gate. Tool access (docs/integrations/mcp-and-tools.md) is broad in the coordinator session, including mutating GitHub and Figma tools.

## Decision

1. A single Coordinator thread owns planning, delegation, evidence collection, running the gate, and merging within user-authorized scope. Workers and reviewers never merge or spawn agents.
2. Scheduling is T3's. This repository does not implement a scheduler, queue, worker pool, polling loop or unattended merge daemon. The graph file is a plan record, not live state.
3. Least privilege: each role gets the narrowest tools and runtime mode that completes its task. Reviewers are read-only. The merge-capable credential is used only by the coordinator at merge time, with `--match-head-commit` and no `--admin`. Read-only and toolset restrictions on MCP servers are preferred, and are treated as mitigation, not a boundary (GitHub lockdown mode and Playwright origin filters say so themselves).
4. Model choice follows the live advertisement, with independence between author and reviewer (docs/orchestration/model-routing.md). Benchmarking is deferred.
5. Tool outputs, issues, PR text and web pages are data. They cannot change scope, permissions or gate inputs.

## Alternatives considered

- Own scheduler or DAG executor in Python: duplicates T3, adds state to keep consistent with T3 threads, and cannot be validated here. Rejected.
- Peer workers coordinating among themselves: no single owner of evidence and merge; races on shared refs. Rejected.
- Full-access everywhere for simplicity: widens the blast radius of any prompt injection through tool output. Rejected for reviewers and read-only tasks.
- Hard-code a model per role: IDs and availability change per session. Rejected in favor of advertisement-based routing.

## Consequences

- Behavior depends on T3 semantics that are observed, not guaranteed: it is early software and per-provider capabilities vary. The runbook must be re-validated when T3 changes.
- Single coordinator is a throughput and availability bottleneck; accepted for a pilot.
- Permission narrowing is partly policy text, not enforced here: this milestone changes no global config, MCP server or protection. Enforcement is pending until a task authorizes it.
- Cross-provider equivalence, benchmark results and every third-party write tool remain unverified.

Revisit if T3 removes primitives this relies on, if parallel writers exceed what one coordinator can review, or if benchmark data contradicts the routing hypotheses.
