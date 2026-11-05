# Distribution contract

`onboard.py:mapping()` is the fixed committed-blob allowlist. Source invocation and
trust/recovery limits: `docs/onboarding/README.md`. Target entrypoint:
`.agent-harness/START.md`. Reusable adoption/workflow/templates are installed under
`.agent-harness/docs/onboarding/`. All linked handoff reference assets are included.

No network installer, CI, calculator, sample product graph, credential collector,
provider configuration or root instruction replacement is distributed. The initial
graph records only the completed local inventory snapshot. SHA identity and local
hashes are not authenticity or authorization. Existing format-1 installations may
upgrade deliberately; old asset pins missing the new allowlist cannot initialize
with this installer. Check and rollback of existing format-1 records remain supported.
