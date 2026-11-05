# Milestone 4 implementation plan and evidence

Owned: `src/agent_workflow_pilot/onboard.py`, `tests/test_onboard.py`,
`docs/onboarding/**`, `harness/distribution/**`. Base:
`95ac90027e7ce57c262fad467d7fbe8d4df9de0e`.

1. Implement committed-pin asset selection, explicit target validation and conflict
   preflight. Acceptance: no source working-tree assets or unrelated target files copied.
2. Implement ownership hashes, check, deliberate upgrades and rollback snapshots.
   Acceptance: disposable Git tests cover drift, collisions, redirects, interrupted
   writes, idempotence, dry-run and upgrade/rollback between real commits.
3. Document trust boundary and limitations, run `uv run --locked pytest`, open a
   focused PR. Controller supplies independent review and merges; no child agents.

Research: Context7 `/python/cpython` query on 2026-11-05 confirmed `lstat`,
Windows reparse attributes and `os.replace`. Its snippets referenced CPython main,
not a version-pinned 3.12 documentation set; actual execution uses Python 3.12.14.
No third-party runtime dependency or library API is introduced.

Validation: `uv run --locked pytest` on Windows, CPython 3.12.14:
**354 passed, 1 skipped in 32.63s**. The skipped test requires symlink creation
privileges. These are real local disposable Git integration tests, not live host
or provider discovery evidence. No target project was adopted. Controller review
and CI on the pushed exact head remain pending.
