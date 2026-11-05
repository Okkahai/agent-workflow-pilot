# Repository and task onboarding template

## Repository layer (fill from inspection)
Repository/path, owners, applicable AGENTS.md, languages/runtime/lockfiles, build/test commands, actual components, data/security boundaries, CI required contexts and source apps, effective protections and permissions, normal delivery method. Unknown entries block dependent delivery decisions.

## Task layer
Problem, scope/exclusions, acceptance checks, risk/research sources, plan, ADR if needed, branch/worktree owner, base/head, independent reviewer, findings/corrections, executed tests and limitations, delivery authorization.

## Initial adoption targets
OpsPilot, MarketOS, Alibi: apply this same blank inventory independently in each repository. First read its own instructions and existing structure; fill evidence before proposing changes. No stack, deployment topology, service boundary or data model is assumed here. This PR changes none of those repositories.

## Review handoff
Record reviewer/run identity, reviewed head SHA, artifact URL/path, actionable findings, corrected commit and fresh review. Distinguish AI review from host approval. Record final CI/check URLs and protection inspection timestamp separately.
