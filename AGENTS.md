# Repository instructions

Follow docs/engineering-standard.md. This repository is the engineering harness pilot and a small Python calculator package, not an application architecture template.
Use Python 3.12, uv locked dependencies, and `uv run --locked pytest`.
Do not weaken .github/workflows/ci.yml or GitHub protections. Keep provider-specific runtime instructions outside universal policy.
Independent review and merge are controller responsibilities; the implementation worker creates a focused PR and hands back head SHA and evidence.
