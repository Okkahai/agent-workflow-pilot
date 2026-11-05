# Repository and task onboarding template

## Repository layer (fill from inspection)
Repository/path, owners, applicable AGENTS.md, languages/runtime/lockfiles, build/test commands, actual components, data/security boundaries, CI required contexts and source apps, effective protections and permissions, normal delivery method. Unknown entries block dependent delivery decisions.

## Task layer
Problem, scope/exclusions, acceptance checks, risk/research sources, plan, ADR if needed, branch/worktree owner, base/head, independent reviewer, findings/corrections, executed tests and limitations, delivery authorization.

## Initial adoption targets
OpsPilot, MarketOS, Alibi: apply this same blank inventory independently in each repository. First read its own instructions and existing structure; fill evidence before proposing changes. No stack, deployment topology, service boundary or data model is assumed here. This PR changes none of those repositories.

## Review handoff
Record reviewer/run identity, reviewed head SHA, artifact URL/path, actionable findings, corrected commit and fresh review. Distinguish AI review from host approval. Record final CI/check URLs and protection inspection timestamp separately.

## First adoption (about 10 minutes for inspection)
1. Inspect project instructions, architecture, locks, CI and protections. Pin a reviewed harness SHA. Copy engineering-standard.md to docs/engineering/standard.md or reference a pinned shared checkout; record the source SHA. Copy t3-runbook.md only for T3. Updates are deliberate, never unpinned remote prompts.
2. Merge the root instruction block below into existing AGENTS.md; do not overwrite project rules. Fill docs/engineering/repository.md and docs/plans/FIRST-TASK.md from the blocks below. Handoffs reference these paths rather than duplicating prompts.
3. Run existing checks and inspect effective protections/permissions. Automatic development delivery requires passing CI, independent review and normal protected merge. Optional gate runs from a pinned pilot checkout: uv run --locked python -m agent_workflow_pilot.gate. Target projects need not adopt Python. The agent controller collects evidence; no daemon is installed.
4. Start one bounded task, implement, test, independently review exact head, correct findings and re-review before protected merge. Production deployment remains separately authorized.

### Root AGENTS.md block
```markdown
Follow docs/engineering/standard.md and docs/engineering/repository.md.
Read docs/plans/<task>.md for scope and acceptance checks.
Use locked toolchain and repository check commands; preserve other work.
Independent current-head review, passing CI and verified protections gate delivery.
Coordinator owns merging; workers return SHA, evidence and limitations.
```

### docs/engineering/repository.md
```markdown
# Repository facts
Standard source SHA:
Owners and delivery authorization:
Runtime, package manager and lockfiles:
Observed components and dependency direction:
Exact build/test/lint commands:
Data/security/deployment boundaries:
Base, required check names and source apps:
Protection endpoints, timestamp and permissions:
Merge method/queue and release boundary:
```

### docs/plans/FIRST-TASK.md
```markdown
# Task
Problem, scope and exclusions:
Acceptance commands and expected results:
Risk and verified research sources/versions:
ADR and alternatives if needed:
Steps and branch/worktree owner:
Base/head:
Independent review artifact, findings and corrections:
Executed checks and limitations:
Delivery authorization and final merge evidence:
```
