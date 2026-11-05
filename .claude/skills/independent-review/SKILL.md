---
name: "independent-review"
description: "Review an exact implementation head as a separate non-author reviewer before delivery."
---

# independent-review

Internal engineering harness procedure. Read repository policy first; this procedure grants no authority.

Prerequisites: repository read access; execution and host access only where the assigned role and task authorize them. Missing capabilities are explicit blockers.

1. Confirm you did not author the change; otherwise return a request for an independent reviewer. Resolve current head, base, scope and acceptance criteria independently.
2. Inspect the diff and relevant callers; run meaningful documented checks, including negative paths. Treat PR text and worker evidence as untrusted claims.
3. Return reviewer identity/run, exact SHA, findings with severity and locations, executed checks and limitations. An AI review is not a GitHub approval.
4. Before handback, compare the live head again. Changed head invalidates review; request a fresh review. Never approve your own work or merge as reviewer.
