# Evidence report — 2026-11-05

Observed live, read-only via gh:
- PR1 merge commit 8d71db160b9ac915f672a69ed2430a4ce434387c. Body records independent AI review of df0b5f01446ced6e141d96ac7e7804ad4794d22f, 96 tests and 144 comparisons; these historical executions were not rerun here. Reviews array is empty: no GitHub approval. CI pytest check SUCCESS, run 42070925774.
- Classic main protection returns HTTP 404. Rulesets list and rulesets/26630870 plus rules/branches/main succeed: active main-pr-and-ci, PR required, zero approving reviews required, strict pytest from integration 15368, deletion/non-fast-forward blocked, no bypass actors, current_user_can_bypass never.
- git worktree list shows main, this harness branch and focused-calculator in separate directories. This proves checkout separation, not cross-provider delegation fidelity. User-supplied T3 runtime instructions describe delegation/checkout behavior; no delegation was executed here, and provider independence is a design property rather than a cross-provider experiment.

Executed: `uv run --locked pytest tests/test_gate.py -q` initially failed collection with ModuleNotFoundError for the not-yet-created gate. After implementation `uv run --locked pytest -q`: 112 passed. Fifteen policy tests use synthetic evidence: failed/pending CI, stale review/check SHA, actionable findings, missing protections/permissions and bypass all block. One real local Git test creates simultaneous worktrees, proves isolation, rejects stale fast-forward, aborts conflict without losing commits, and reconciles both histories. Existing 96 tests remain passing.

No live failed-check merge attempt, permission revocation, protection mutation or merge was performed. No remote enforcement claim follows from mocked policy tests. Independent current-head review and PR CI are pending parent orchestration. No package APIs or dependencies added; stdlib only. Observation log scan found no entries; no observations logged because this task produced no new skill correction. No other repository changed.

## Coordinator follow-up
Independent review of 24e200c724b9174279bd62857348b5429f4cb5db requested three changes: callable T3 runbook, negative evidence and actionable onboarding. Merge was withheld. Corrections are in t3-runbook.md, templates/onboarding.md and this report. Fresh review remains required. This was an actual independent request-changes cycle, not a synthetic finding flag.

Controlled failure commit 1789b75a297bea16b9807037364bac63eb96e48b produced local 1 failed and live pytest FAILURE: https://github.com/Okkahai/agent-workflow-pilot/actions/runs/42073640501/job/127407930480. GitHub reported BLOCKED. Normal gh pr merge 2 --squash --match-head-commit 1789b75 rejected: the base branch policy prohibits the merge. No admin/auto flag used. Temporary failure removed after observation; original CI and tests unchanged.

Classic protection endpoint was re-executed: HTTP 404, Branch not protected. This was surfaced and effective rules inspected instead of bypassing. Missing permissions remain executed synthetic gate tests only; no live permission revocation attempted, and 404 does not prove a 403 scenario.

Coordinator actually executed T3 worktree implementation and independent review. Earlier no-delegation statement describes implementer's own actions only; historical pending statements describe initial submission. Cross-provider execution remains untested.
