# Routing gap register

Dated 2026-11-09, scope: dynamic provider routing milestone (plan: docs/plans/dynamic-provider-routing.md). Evidence classes: **local-test** (pytest on mocked policy inputs or local files), **doc**, **open** (nothing demonstrated), **live** (real native T3/provider run, recorded by the Coordinator, not claimed here). Routing does not close the portability or original gaps.

| ID | Status | Evidence / next |
| --- | --- | --- |
| ROUTE-01 dynamic routing coded | partial: local-test | `routing.py`, `routing-v1.json`, `tests/test_routing.py`. Live capability decisions and bounded live tasks are open; the Coordinator must run them. |
| ROUTE-02 cross-provider review, mixed authorship | partial: local-test | `validate_reviews` with Claude to Codex, Codex to Claude, mixed, stale head, alias, cross-project cases. Final mixed-head reviews by real non-author reviewers are open. |
| ROUTE-03 subscription telemetry | advisory only | No trusted quota API in the installed T3 schema. Unknown stays unknown; reserve is advisory; thresholds apply only to supplied measured readings. Revisit if a supported quota API appears. |
| FALL-01 provider switch, attempt identity | partial: local-test | Intent before call, replay no dispatch, one writer, children/writer ambiguity, scope/budget/head freshness, checkpoint head change. Live Sonnet/Sol switch and reuse of an existing isolated checkout without full-history injection: open; report the limit if T3 cannot do it. |
| QA-01 evidence class separation | partial | Tests and docs label mocked, local-file and live evidence; the final readiness report must keep that labelling. |
| DOC-01 docs drift | partial: doc | model-routing.md rewritten, routing.md and ADR 0003 added. No CI check yet that docs mention current policy values or links stay valid. |
| CONT-01 single current architecture/readiness register | open | This register and the gap list below are the only current record; no CI drift test. |
| PORT-01 control plane on a second real project | open | Never executed outside the pilot. Needs an independent repository run. |
| PORT-02 pilot M1 to M5 names, paths, repo coupling | open | Routing core is free of milestone IDs and paths (`test_policy_has_no_project_ids_or_paths`). The rest of the pilot (roadmap enums, `owns` paths, onboarding asset map) is unchanged. Also open: local evidence storage layout, onboarding distributes skills and validators but not the controller, shared installation packaging and import paths, immutable policy-version migration tooling, checkpoint sidecar compatibility on a checkpoint version bump. |
| PORT-03 cross-repo evidence isolation | partial: local-test | Routing records, reviews and telemetry reject other project/repo/task evidence. Not tested across two real repositories with different stacks and root IDs. |

## Original M1-M5 gaps

Unchanged by this milestone and not selected: M1 gap is delivered at main fcfec45; `m2-gap` to `m5-gap` and `pr14` remain historical references or future scope that need fresh reviewed scope and authorization (docs/program/tasks/*). No claim is made that routing satisfies any of them.

## Known limits of this change

- Single trusted writer, local filesystem, no exactly-once or crash guarantee.
- Ubuntu link unreachable at observation time: no Ubuntu isolation claim.
- Quota percentages are caller-supplied; the module cannot verify their origin.
- Review and fallback demonstrations on real providers are Coordinator work after this PR.
