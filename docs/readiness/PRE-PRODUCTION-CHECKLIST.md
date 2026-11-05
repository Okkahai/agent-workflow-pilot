# PRE-PRODUCTION-CHECKLIST

Integration candidate only; this is not production approval or evidence of real
project adoption. Base: `8d45c91`. Implementation candidate:
`497c44a5241bee9c17945ff8e80b3a9b07bafc52`. Evidence below is self-reported local
execution; controller must independently verify the final PR head.

| Check | Status / evidence class | Evidence or required next proof |
| --- | --- | --- |
| Existing systems preserved | PASS / local integration | `tests/test_onboard.py::test_lifecycle_and_preservation`; existing instructions, MCP and unrelated skills retained; no CI or architecture installed. |
| Installed entrypoint and templates | PASS / local integration | `test_installed_entrypoint_commands` invokes installed graph validator; START supplies target commands and workflow; repository/task/review/handoff templates shipped. |
| Factual initial graph | PASS / local integration | `test_lifecycle_and_preservation` loads graph with real validator; only inventory-recording complete node, no guessed tasks/ownership. |
| Init/check/idempotence/dry-run/rollback/conflicts | PASS / disposable Git | Lifecycle, drift, collision, interrupted-write and CLI tests in `tests/test_onboard.py`; no real project accessed. |
| Upgrade across distinct committed pins | PASS / disposable Git | `test_upgrade_new_committed_pin` changes a committed source asset; `test_legacy_manifest_check_and_upgrade` checks base-pin install, upgrade and rollback. |
| Provenance pin | EXPLICIT TRUST DECISION REQUIRED / design | Full local commit SHA and blob hashes identify content, not publisher authenticity. Adopter reviews installer and asset SHAs separately and records origin/reviewer/date/rationale using repository template. No signature verification supplied. |
| Locked full suite | See execution record below / local | `uv run --locked pytest` on Windows, CPython 3.12.14. Symlink privilege case may skip; it is not a pass. |
| Enforced reviewer sandbox | UNVERIFIED / runtime | Read-only role contract is prose; no demonstrated OS/tool enforcement. Requires independent runtime enforcement test. |
| Fresh provider skill discovery | UNVERIFIED / runtime | Files packaged for providers; no fresh Codex/Claude discovery/selection/activation session executed. |
| Live host/tool/MCP/protection checks | NOT RUN / live | No target host protections, permissions, provider execution or real adoption tested. Local gate tests are policy checks, not authentic host collection. |
| Independent exact-head review and PR CI | PENDING / controller | Controller resolves final head and arranges non-author review; GitHub checks must be verified on that head. No worker merge. |
| Production deployment | NOT AUTHORIZED / release | No deployment, workflow/protection changes or actual-project access performed. |

## Execution record

Initial local run at `cda9992`: `uv run --locked pytest` → 358 passed,
1 skipped in 52.38s. Expanded run at `497c44a5241bee9c17945ff8e80b3a9b07bafc52`:
`uv run --locked pytest`: **360 passed, 1 skipped in 67.29s**. CI on 68b9d09 failed 1 test because the base commit was unavailable in a shallow checkout; the legacy manifest test was adjusted and the local suite then passed 360 tests with 1 skipped.
Final PR-head validation is recorded in the PR/handback. A skipped Windows symlink test does not establish
symlink rejection on this machine.

## Operational limits

Single-writer trusted local filesystem; no concurrent race sandbox. Hash manifests
and rollback journals are unauthenticated. Per-file replacement is not a durable
multi-file transaction. Preserve/inspect recovery journal before deliberate
upgrade; changed managed or newly collided files block writes. Legacy inventory
snapshots are preserved during upgrade; their `graph: null` is historical, while
new initial graph is installed separately. Mutable project facts belong outside
managed assets. No background controller or scheduler is installed.
