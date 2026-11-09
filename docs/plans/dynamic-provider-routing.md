# Dynamic multi-provider routing implementation plan

> For agentic workers: execute this bounded approved plan using repository task-planning, handoff and pr-delivery procedures. Coordinator owns native orchestration, acceptance and merge boundaries.

**Goal:** Add a minimal reusable routing policy and attempt-provenance validator to the existing Program/Delivery Coordinator. No replacement runtime or full portability migration.

**Authorization/spec:** User's 2026-11-09 Dynamic Multi-Provider Routing instruction, plus Master Recovery sections II/V/VI/IX/X/XI. Current instruction supersedes historical model defaults and historical PR18 status. Only this task is approved; no merge, PR14 change or original gap expansion.

**Baseline:** main `fcfec45082208261e2992fca5501bc24d23bc5ce`, PR18 merged/postmerge CI506 passed. PC1/2/3 and M1 delivered; bindings archived/logically retired. One existing Coordinator, Program and Delivery as logical roles.

## Design and boundaries

Small stdlib-only pure routing module plus explicit versioned JSON policy. Caller supplies independently resolved project/repository/task/current head, approved task classification, live capabilities and bounded usage observations. Output is a machine-readable target/stop reason, NEVER execution, authority or a merge decision. No network, credential collector, quotas scraper, scheduler, service, memory DB or provider SDK.

Use existing strict JSON/text/path/SHA validators, checkpoint persistence/replay conventions and M1 `task_context.reconstruct`. Keep handoff/context/checkpoint v1 schemas unchanged. A small routing sidecar references the existing delivery checkpoint and native artifacts; it does not copy full T3/GitHub results. Identity comprises separate project/repository/logical task/execution attempt values; compare against caller expectations on every operation, never record-to-itself. Explicit current head + plan/spec/context hash mismatch blocks. Reconstruct M1 context at recovery/dispatch boundaries; new routing record must not become a second context format.

Canonical policy belongs under `harness/policies/routing-v1.json`; caller supplies the path/object, not pilot globals. `docs/orchestration/model-routing.md` explains the new approved defaults and supersedes historical Astra/same-provider text. Local prior policy and audit are preserved at root and under docs/readiness/dynamic-routing; reference their provenance, do not copy obsolete defaults as active policy. No general onboarding/asset-map migration now.

Policy roles: program/delivery Codex Sol Medium with no auto switch; planning/architecture and standard/complex Builder Sonnet Medium, approved Sol Medium alternative; scoped bugfix Builder Sol Medium, approved Sonnet Medium alternative; mechanical/docs Terra Low, docs Haiku Low alternative. Capability-match IDs and provider-specific effort descriptors. Only Sonnet/Sol implementation switching is automatically authorized. Other missing targets stop or return an explicit approved candidate requiring caller choice; no Opus/Astra/high/max/fast escalation.

Classifications must be closed/validated and explain category, complexity, architecture/security risks, required capabilities, project/task context, budget and verification cost. Do not infer scope approval from classification or a pilot milestone ID. Risk/complexity cannot secretly upgrade cost or waive safeguards.

Usage windows: trusted current session AND weekly observations, source refs, freshness and project/provider association. Use worst known limit; preserve unknown windows as unknown and do not overstate complete quota knowledge. >35 normal; 15..35 conservation; <15 restrict heavy new work; 0 exhausted. Approx20% Claude reserve is advisory unless enforceable. Unsupported/stale/user-estimated telemetry cannot masquerade as measured quotas. Real installed T3 schema exposes no quota-reading tool; CLI /usage and /status are interactive displays, not permission to scrape private APIs. Tokens/elapsed time/attempt counts are separate attributable metrics, not subscription percentages/dollars or savings proof.

Safe attempt protocol: persist intent atomically before native call; reconcile returned IDs; replay never grants new dispatch. Before switching Sonnet/Sol, checkpoint and require terminal original task AND children, fresh matching repo/branch/worktree/PR/head, unchanged approved task/scope and retry budget, known predecessor/provenance. Unknown dispatch/writer/children or exhausted corrections holds the slot. Head change clears CI/review through existing checkpoint. Preserve partial work and original PR; no reset/force push/new PR. Single trusted writer/local filesystem only; no exactly-once or crash guarantee.

Review validation: each code-author provider needs independent opposite-provider coverage at current exact head with native reviewer task identity, no authorship, findings, evidence refs and provider/model/options. Mixed authorship needs both provider coverages. Different Codex model is not cross-provider. Missing provider/coverage or stale head blocks final readiness. Provider instance aliases cannot fake different underlying provider identity. Existing fail-closed delivery gate remains required; routing helper never merges.

## Ownership and tasks

### 1. Implement policy/classification/validation (Claude Sonnet Medium)

Owned: `src/agent_workflow_pilot/routing.py`, `tests/test_routing.py`, `harness/policies/routing-v1.json`, `docs/orchestration/model-routing.md`, `docs/orchestration/routing.md`, `docs/adr/0003-dynamic-routing.md`, `docs/readiness/routing-gap-register.md`, `docs/program/tasks/dynamic-routing.md`. New helper files only if needed to keep interfaces maintainable; avoid unrelated refactors. Coordinator owns roadmap/plan and local execution evidence; existing program/checkpoint/handoff/task-context code changes only when small compatible reuse is necessary and regression-justified.

- [ ] Define/document closed policy, task, capability/budget, attempt and review reference contracts; stdlib functions and a small stdin JSON CLI for reproducible decisions/reload. Prefer one maintainable module, not a framework. Document exact callable interfaces in routing.md.
- [ ] Write/run positive and negative tests before implementation, then minimum implementation. Cover categories, all target roles/options, disabled/missing provider/model/effort, invalid scalar types, stale quota, unknown/exhausted windows, threshold edges, reserve limitations, required capabilities and forbidden escalation.
- [ ] Test attempt identity, preserved scope/budget, duplicate/replayed intent/native ID, child/writer ambiguity, current repo/branch/PR/head mismatch, stale checkpoint/context, safe fallback, changed-head invalidation and fresh-process persistence. No fixture may be reported as live T3 behavior.
- [ ] Test opposite-provider review, mixed authorship, actual non-author identities/underlying providers, findings and exact-head freshness; cross-project/task evidence contamination rejection. Keep existing PC1–3/M1 tests passing.
- [ ] Document immutable architectural invariants and regression mapping, portability boundaries/migration and known gap register. Link current official sources below; distinguish runtime schema from dated snippets.
- [ ] Full `uv run --locked pytest`, diff check, normal commit/push and ONE focused draft PR; link in T3. Return exact head/native route/worktree/results plus a real typed M1 context+handoff record outside committed source. Stop terminal with clean tree. No agents/watches/merge/ready action.

### 2. Bounded provider-switch conformance contribution (Coordinator-dispatched Codex Sol Medium)

Only after first Builder is terminal/no children and worktree/PR/head independently reconciled, persist a new attempt intent for the SAME logical task and PR. Reserve `tests/test_routing_conformance.py` for a useful Codex contribution exercising the actual routing CLI and persisted fallback/replay path through fresh processes. Use the documented implementation API; no artificial failure/quota exhaustion, no extra feature, no parallel writer. Continue verified existing isolated worktree using supported native mechanism; if the installed mechanism cannot safely reuse it without full-history injection, report that live limit and do not invent execution support. This planned terminal provider switch is not a real usage-outage demonstration. Any genuine defect correction remains inside budget2.

### 3. Final delivery validation (Coordinator)

Fresh CI for every changed head. Fresh independent Codex Sol review covers Claude contributions; fresh independent Claude Sonnet review covers Codex contributions, both on final mixed head, neither author. Sequential reviewers, source read-only; no Ubuntu isolation claim while link unreachable. No same-provider substitution if capacity/provider unavailable.

Real native evidence must show one active Builder at a time, actual advertised/requested/returned route, terminal original before switch, persisted intent and native IDs, unchanged logical delivery/PR/budget, new-head CI/review invalidation, automatic result collection. Exercise final CLI/context fresh-process reload, local replay/no dispatch, cross-project negative evidence checks; label simulations separately. Stop draft report_ready, NOT delivered/merged, and do not select original gaps.

## Portability handoff acceptance

Record remaining pilot M1–M5 enum/schema names, local evidence storage, onboarding that distributes skills/validators but not full controller, shared installation packaging/import paths, immutable policy version migration, checkpoint sidecar compatibility and future two independent repositories (different stacks/root/repo IDs) tests. Universal policy contains no Okkahai IDs, pilot milestones, native environment IDs or absolute paths. Project config/state owns those. Maintain PORT-01/02/03, CONT-01, ROUTE-01/02/03, FALL-01, QA-01, DOC-01 and original gaps with evidence/status; do not claim all closed by routing.

## Research evidence (observed 2026-11-09)

- Installed `orchestrator_capabilities` and `delegate_task` schema: codex Sol/Terra and claudeAgent Sonnet/Haiku available, child/cross-provider=true. Codex `reasoningEffort`, Claude `effort`, explicitly medium/low as appropriate. Snapshot: Coordinator docs/readiness/dynamic-routing/capabilities-2026-11-09.json. Native T3 has no advertised subscription telemetry method. CLI versions Codex0.167.0, Claude Code2.1.319. Ubuntu link unreachable; no config changes.
- Official T3: https://github.com/pingdotgg/t3code/blob/main/docs/orchestration-v2/orchestrator-mcp-server.md — explicit targets, native completion/cancellation; current installed schema takes precedence over outdated examples. Options validated by native provider. Fresh delegates receive task-only context.
- Official Claude: https://code.claude.com/docs/en/costs and https://code.claude.com/docs/en/skills — separate token accounting vs plan usage, progressive context. `/usage` may show cached bars; do not treat cached/private data as a fresh machine quota API.
- Official Codex: https://learn.chatgpt.com/docs/build-skills and https://learn.chatgpt.com/docs/agent-configuration/subagents and https://learn.chatgpt.com/docs/pricing — progressive Skills, explicit/inherited model configuration, variable limits and interactive `/status`; no assumption tokens equal quota.
- Context7 primary sources checked: /pingdotgg/t3code, /websites/code_claude, /openai/codex. No SDK dependency or new service needed.
