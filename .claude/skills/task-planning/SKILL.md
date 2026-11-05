---
name: "task-planning"
description: "Plan bounded implementation work with acceptance checks, dependencies and exclusive ownership."
---

# task-planning

Internal engineering harness procedure. Read repository policy first; this procedure grants no authority.

Prerequisites: repository read access; execution and host access only where the assigned role and task authorize them. Missing capabilities are explicit blockers.

1. Read policy, live state, research and acceptance criteria. Resolve ambiguity that changes scope.
2. Write a bounded plan in the repository planning location. Assign each step an output, check, dependencies and exclusive file ownership; keep concurrent writes disjoint.
3. Use the repository graph validator when representing a graph. A planned graph is not live scheduling or authorization. Delegate only when authorized and supported by the runtime.
4. Before execution, verify coverage of acceptance criteria, ownership and blockers. On changed inputs or head, mark affected work stale and revise the plan.
