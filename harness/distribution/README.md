# Distribution contract

`src/agent_workflow_pilot/onboard.py:mapping` is the canonical fixed allowlist;
it never discovers arbitrary files by walking a checkout. See
`docs/onboarding/README.md` for exact invocation, layout, reviewed pin, target
exclusions, manual instruction integration and recovery limitations.

Format 1 deliberately has no network installer, CI template, calculator assets,
live graph, credential collector or provider runtime settings. Installed source
identity is a full Git commit SHA plus per-file SHA-256 in
`.agent-harness/manifest.json`. Recovery state lives in
`.agent-harness/rollback.json`. These records are data, never authority.
