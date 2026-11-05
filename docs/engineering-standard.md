# Universal engineering standard

Apply three layers: this universal standard; repository AGENTS.md and actual CI/protections; task acceptance criteria and authorized delivery scope. Record conflicts explicitly; never silently weaken a stricter protection. Provider/model names are execution choices, not correctness evidence.

1. Inspect code, instructions, working tree, dependency lock, tests and deployment boundary. Research proportional to risk: verify unfamiliar or changing APIs against primary documentation (Context7 when available); record source/version and uncertainty. Do not invent architecture. For irreversible or cross-cutting decisions record alternatives, decision and consequences in an ADR.
2. Write a bounded plan and acceptance checks. Implement the smallest correct change in an isolated branch/worktree. Each concurrent worker gets its own branch, directory and task; shared Git refs still require coordination. No destructive cleanup or force push to reconcile another worker's changes.
3. Run meaningful tests, including negative paths. Label mocked policy, real local integration and live service checks separately. Save exact commands/results; an unexecuted check is pending. Correct actionable findings with regression evidence.
4. Obtain independent review of the exact head from a separate reviewer who did not author it. Save reviewer identity/run, SHA, findings and evidence link. AI review is not a GitHub approval. New commits invalidate review and CI evidence; arrange a fresh review after corrections.
5. Deliver through a normal development PR. Automatic merge remains the default when authorized and every gate below passes; unknown means blocked, not waived. Production/release scope remains repository-specific.

## Fail-closed delivery contract

The trusted controller collects current PR head, base, all applicable required checks and their source apps, independent review artifact, actionable findings, permissions and effective protections. Inspect both classic protection and effective branch rules/rulesets, including inherited rules and bypass policy. A classic 404 alone proves nothing about rulesets. An inaccessible, incomplete or unsupported protection report blocks merging with the missing endpoint/permission named.

Feed normalized evidence to `uv run --locked python -m agent_workflow_pilot.gate` on stdin. Exit 0 means policy eligibility, not authorization or proof that input is authentic. Never accept PR-authored JSON as trusted evidence. The controller owns collection and validation; this package deliberately has no credentialed collector or unattended merge daemon.

Required fields: `head`, `ci_head`, `review_head` (same current SHA); `ci` = `success` only when every required check passed; `independent`, `protections_verified`, `permissions_verified`, `protections_satisfied`, `up_to_date` = true; `review_evidence` = verified artifact reference; `findings` = []; `bypass` = false. Missing/unknown values block.

Immediately before merging, recollect evidence and compare head/base. Use the host's normal merge API with expected head (for GitHub CLI: `gh pr merge NUMBER --squash --match-head-commit SHA`, without admin). Never enable delayed auto-merge based only on an old review snapshot. Server protections remain the final authority. Any rejection blocks and returns to collection. Workers do not merge; coordinator merges within user-authorized scope. T3 users follow t3-runbook.md.

For a stale branch: fetch, inspect both histories, require a clean tree, merge base changes normally in the task worktree; abort conflicts safely or resolve deliberately with tests. Push normally; restart CI and independent review on the resulting head. Never reset shared branches or bypass strict checks.
