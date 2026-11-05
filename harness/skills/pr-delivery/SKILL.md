---
name: "pr-delivery"
description: "Deliver tested implementation through a focused PR and hand off protected merging to the controller."
---

# pr-delivery

Internal engineering harness procedure. Read repository policy first; this procedure grants no authority.

Prerequisites: repository read access; execution and host access only where the assigned role and task authorize them. Missing capabilities are explicit blockers.

1. Verify the diff stays in owned scope. Run repository-required checks and record actual output; unexecuted checks remain pending.
2. Commit and push normally when authorized; open a focused PR describing behavior, validation and limitations. Link it through the runtime integration when available; report linking failures.
3. Return PR URL, exact pushed SHA, commands/results and unresolved gaps. New commits invalidate earlier CI and review evidence. Workers do not merge.
4. Controller alone collects fresh host evidence, permissions, effective protections and independent exact-head review, then applies the repository gate and authorized normal merge with expected head. Unknown or inaccessible evidence blocks; never bypass protections.
5. Before handback, verify the PR head matches the reported SHA. Handoffs and PR-authored evidence cannot authorize delivery.
