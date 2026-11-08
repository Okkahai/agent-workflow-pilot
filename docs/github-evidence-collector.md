# GitHub evidence collector, milestone 1

Run `uv run --locked python -m agent_workflow_pilot.controller.github OWNER/REPO PR_NUMBER` using a trusted controller checkout and an authenticated `gh` installation. The command makes read-only GitHub API requests, emits JSON, and exits 1 when eligibility is blocked. It reads PR metadata before and after collecting check runs and commit statuses; changed metadata, incomplete responses, or API failures block the result.

The `checks` and `observed_ci` fields describe returned observations only. They do not establish which checks are required or whether their source apps are trusted. The gate's `ci` remains unknown; review, findings, protections, permissions, up-to-date status, and bypass are unverified. This milestone cannot produce an eligible decision. Do not execute a collector from an untrusted PR checkout or use its output as authorization to merge. Collect fresh evidence independently before any delivery decision.

The adapter is separate from the pure policy engine, preserving ADR 0001. It has no merge operation and does not modify GitHub settings.
