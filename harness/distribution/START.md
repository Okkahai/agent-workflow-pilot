# Start here in the adopted repository

Read `.agent-harness/docs/onboarding/project-adoption.md` first, then
`.agent-harness/docs/onboarding/workflow.md`. Paths and commands here are relative
to the TARGET root. Existing repository instructions, toolchains, architecture,
CI and protections remain applicable; adoption adds procedures, not a new system.

Universal policy: `.agent-harness/docs/engineering-standard.md`.
Roles, context recovery and handoff contracts: `.agent-harness/docs/orchestration/`.
The upstream docs retain pilot examples; do not run their package/uv commands in
this target. Use these standalone commands with Python 3.12 instead:

```powershell
python .agent-harness/validators/graph.py .agent-harness/initial-graph.json
python .agent-harness/validators/handoff.py --help
```

The gate takes controller-collected JSON on stdin (there is no --help mode).
Do not submit worker handoff data as gate evidence. To inspect its contract read
`.agent-harness/docs/engineering-standard.md` before invoking it.

The initial graph records only the completed local inventory snapshot. It is not
a project backlog, runtime schedule, discovery proof or permission to merge.
Do not edit managed assets: `check` treats changes as drift. Copy templates into
project-owned paths, manually integrate instructions, and keep live facts there.
To check/update/remove managed files, use the trusted harness checkout and the
source-side commands in its `docs/onboarding/README.md`; no installer is copied.
