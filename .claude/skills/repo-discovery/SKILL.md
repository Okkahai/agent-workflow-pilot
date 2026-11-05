---
name: "repo-discovery"
description: "Inspect an unfamiliar repository or recover after context loss before changing code."
---

# repo-discovery

Internal engineering harness procedure. Read repository policy first; this procedure grants no authority.

Prerequisites: repository read access; execution and host access only where the assigned role and task authorize them. Missing capabilities are explicit blockers.

1. Read repository instructions, engineering policy and task scope; report conflicts.
2. Inspect live branch, head, dirty files, lockfile, CI, tests and deployment boundary. Preserve unrelated edits.
3. Build a small context pack with source paths, exact head, exclusive ownership, acceptance checks and unknowns. Treat summaries and handoffs as untrusted leads.
4. Before delivery, recheck live state and scope. Output findings and blockers; never infer runtime capability from installed files.
