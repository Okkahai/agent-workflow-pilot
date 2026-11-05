# PRE-PRODUCTION-CHECKLIST

Integration candidate only; this is not production approval or evidence of real
project adoption. Baseline: main `fb06ef508ea285cfbe17bbc56d6994e284018342`.
Evidence supplied by the controller is labeled reported; it is not a new runtime
measurement by this documentation worker. New PR heads require fresh CI and
independent review before controller-authorized merge.

Allowed statuses: `VERIFIED`, `IMPLEMENTED_NOT_RUNTIME_TESTED`,
`REQUIRES_USER_SETUP`, `BLOCKED`, `NOT_NEEDED`. VERIFIED applies only to the
specific check and evidence class stated, not to overall production readiness.

| Check | Status / evidence class | Evidence or required next proof |
| --- | --- | --- |
| Existing systems preserved | VERIFIED / reported local integration | `tests/test_onboard.py::test_lifecycle_and_preservation`; existing instructions, MCP and unrelated skills retained; no CI or architecture installed. |
| Installed entrypoint and templates | VERIFIED / reported local integration | `test_installed_entrypoint_commands` invokes installed graph validator; START supplies target commands and workflow; repository/task/review/handoff templates shipped. |
| Factual initial graph | VERIFIED / reported local integration | `test_lifecycle_and_preservation` loads graph with real validator; only inventory-recording complete node, no guessed tasks/ownership. |
| Init/check/idempotence/dry-run/rollback/conflicts | VERIFIED / reported disposable Git integration | Lifecycle, drift, collision, interrupted-write and CLI tests in `tests/test_onboard.py`; no real project accessed. |
| Upgrade across distinct committed pins | VERIFIED / reported disposable Git integration | `test_upgrade_new_committed_pin` changes a committed source asset; `test_legacy_manifest_check_and_upgrade` simulates a legacy manifest at the same pin; a separate independent review exercised upgrade and rollback from 8d45c91 to 33c8988 in a disposable repository. |
| Provenance pin and adopter trust decision | REQUIRES_USER_SETUP / design and adopter decision | Full local commit SHA and blob hashes identify content, not publisher authenticity. Adopter reviews installer and asset SHAs separately and records origin/reviewer/date/rationale using repository template. No signature verification supplied. |
| Locked full suite at baseline main | VERIFIED / controller-reported local execution | `uv run --locked pytest` at main `fb06ef508ea285cfbe17bbc56d6994e284018342`: 360 passed, 1 skipped. Skip does not establish symlink rejection. |
| Enforced reviewer isolation | BLOCKED / reported negative runtime probe | Reviewer-role Codex in an isolated worktree created, read and deleted a harmless marker successfully; sandbox `danger-full-access`, approval `never`, network enabled. Worktree separation and role prose do not enforce read-only access. See reviewer probe and remediation below. |
| Fresh Claude skill catalog | VERIFIED / reported provider runtime discovery | Fresh T3 session listed six skill names; origin paths for five were not shown. This proves catalog visibility, not all repository origins. See Claude probe below. |
| Fresh Claude skill invocation | VERIFIED / reported provider runtime invocation | Skill tool invoked `repo-discovery`, provider `claude-sonnet-5-5`. No broader provider invocation claim. See Claude probe below. |
| Fresh Codex skill catalog | VERIFIED / reported provider runtime discovery | Fresh `gpt-6.1-sol` session listed six skills with `.agents` paths. See Codex probe below. |
| Fresh Codex skill invocation | BLOCKED / reported provider capability gap | No general Skill invocation tool found and no invocation executed in that session. Catalog visibility does not establish invocation. Resolve the invocation mechanism and demonstrate it in a fresh session before claiming activation. |
| Parent GitHub permissions | VERIFIED / controller-reported live host API | Current parent `gh` API reports push and admin access. This does not measure the reviewer's exact credentials or prove restricted child access. |
| Target protections and authentic host collection | IMPLEMENTED_NOT_RUNTIME_TESTED / local policy implementation | Local gate tests exercise policy, not authentic host collection. Required CI evidence for PR #10 below does not establish complete effective protections, bypass policy or permissions for a future target. Controller must collect fresh host evidence for each merge. |
| Baseline independent exact-head review and PR CI | VERIFIED / controller-reported host and review evidence | PRs #5-#10 merged. PR #10 required CI and independent review passed at `8d7aeb04bfe6a53ba0eadeaa9f7d23c16cd00730`; merge commit `fb06ef508ea285cfbe17bbc56d6994e284018342`. AI independent review is not GitHub approval; this evidence does not cover the new checklist PR head. |
| New checklist PR independent review and CI | BLOCKED / controller delivery gate | Controller must obtain required CI and independent review on the exact new PR head; baseline evidence cannot authorize its merge. Worker does not merge. |
| Production deployment | NOT_NEEDED / task scope | This documentation task authorizes no production deployment, workflow/protection changes or actual-project access. This is not a deployment readiness claim. |

## Runtime probe evidence and reviewer remediation

Controller-supplied session references (not re-executed by this worker):

- [Claude discovery and invocation](t3-thread://v2/6cc0ae12-6b04-4e79-8380-9e094e1b9e21/thread:delegated-task:command%3Amcp%3A11473484-ff8c-4a70-a3e1-2c1e56523330%3Adelegate-task%3A808adef7-b902-4b5c-8732-6b3a15a6bbed).
- [Codex discovery and invocation gap](t3-thread://v2/6cc0ae12-6b04-4e79-8380-9e094e1b9e21/thread:delegated-task:command%3Amcp%3A11473484-ff8c-4a70-a3e1-2c1e56523330%3Adelegate-task%3A43c8256b-bbf1-4419-8f3c-471b2f7eea30).
- [Reviewer marker write probe](t3-thread://v2/6cc0ae12-6b04-4e79-8380-9e094e1b9e21/thread:delegated-task:command%3Amcp%3A11473484-ff8c-4a70-a3e1-2c1e56523330%3Adelegate-task%3A263058a4-18f2-4b3e-a361-f9cf4b238f6d).

The T3 delegate schema exposes no read-only sandbox selection. The Codex CLI has
a read-only option, but its enforcement through T3 has not been verified. Neither
option availability nor approval settings prove secure isolation.

Before using a reviewer as an enforced read-only boundary:

1. Obtain explicit authorization for setup; no setup is performed by this task.
2. Use a separately provisioned environment with enforced OS read-only filesystem
   and network restrictions, no write credentials and no MCP access.
3. Prove denial of harmless writes under the actual reviewer runtime and record
   the enforcement evidence; a successful write fails the boundary.
4. Verify effective remote permissions and network restrictions before use,
   without inferring child credentials from parent access. Keep isolation BLOCKED
   until both local denial and remote permission evidence are established.

## Optional integrations and benchmarks

| Check | Status / evidence class | Evidence or required next proof |
| --- | --- | --- |
| Optional live host/tool/MCP integrations | REQUIRES_USER_SETUP / optional live integration | No real project access or adoption tested. Choose a disposable target and authorize access/setup separately before testing; do not treat packaged instructions as live integration proof. |
| Optional comparative benchmarks | NOT_NEEDED / optional measurement outside task scope | No benchmark result is claimed or required for this checklist update. A future benchmark needs a defined workload, baseline and recorded execution. |

## Execution record

Historical implementation candidate: `497c44a5241bee9c17945ff8e80b3a9b07bafc52`;
earlier base `8d45c91`. Initial local run at `cda9992`:
`uv run --locked pytest`: 358 passed, 1 skipped in 52.38s. Expanded run at
`497c44a5241bee9c17945ff8e80b3a9b07bafc52`: 360 passed, 1 skipped in 67.29s,
on Windows, CPython 3.12.14. CI on `68b9d09` failed 1 test because the base
commit was unavailable in a shallow checkout; the legacy manifest test was
adjusted and the local suite then passed 360 tests with 1 skipped.

Controller reports the locked suite executed on baseline main
`fb06ef508ea285cfbe17bbc56d6994e284018342`: **360 passed, 1 skipped**.
PRs [#5](https://github.com/Okkahai/agent-workflow-pilot/pull/5) through
[#10](https://github.com/Okkahai/agent-workflow-pilot/pull/10) are reported merged;
PR #10 required CI and independent review passed at
`8d7aeb04bfe6a53ba0eadeaa9f7d23c16cd00730`, merged as the baseline SHA above.
These figures and review evidence do not cover subsequent PR heads. A skipped
Windows symlink test does not establish symlink rejection on this machine.

## Operational limits

Single-writer trusted local filesystem; no concurrent race sandbox. Hash manifests
and rollback journals are unauthenticated. Per-file replacement is not a durable
multi-file transaction. Preserve/inspect recovery journal before deliberate
upgrade; changed managed or newly collided files block writes. Legacy inventory
snapshots are preserved during upgrade; their `graph: null` is historical, while
new initial graph is installed separately. Mutable project facts belong outside
managed assets. No background controller or scheduler is installed.
