# GitHub evidence collector, milestone 1

Run `uv run --locked python -m agent_workflow_pilot.controller.github OWNER/REPO PR_NUMBER` using a trusted controller checkout and an authenticated `gh` installation. The command makes read-only GitHub API requests, emits JSON, and exits 1 when eligibility is blocked. It reads PR metadata before and after collecting check runs and commit statuses; changed metadata, incomplete responses, or API failures block the result.

The `checks` and `observed_ci` fields describe returned observations only. They do not establish which checks are required or whether their source apps are trusted. The gate's `ci` remains unknown; review, findings, protections, permissions, up-to-date status, and bypass are unverified. This milestone cannot produce an eligible decision. Do not execute a collector from an untrusted PR checkout or use its output as authorization to merge. Collect fresh evidence independently before any delivery decision.

The adapter is separate from the pure policy engine, preserving ADR 0001. It has no merge operation and does not modify GitHub settings.

Collection validates `total_count` across all returned pages, rejects missing or duplicate check-run IDs, and verifies every combined-status page's SHA. The check-suite endpoint is also counted: more than 1,000 suites makes the check-run listing incomplete under GitHub's documented limit. The check-run endpoint uses GitHub's default `latest` filter; this is an observation of that filtered set, not proof of required checks. These sequential requests are not an atomic GitHub snapshot; changing checks can require recollection even if PR metadata is unchanged.

References: https://docs.github.com/en/rest/checks/runs#list-check-runs-for-a-git-reference and https://docs.github.com/en/rest/commits/statuses#get-the-combined-status-for-a-specific-reference.
