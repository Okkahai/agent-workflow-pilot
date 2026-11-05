# Adopt into an existing project

This document is also installed at
`.agent-harness/docs/onboarding/project-adoption.md`. In the target, start at
`.agent-harness/START.md`. No real project was accessed to develop this workflow.

1. Obtain authorization for the specific target. Read its instructions and existing
   systems first. Do not replace architecture, package management, CI, protections,
   root instructions, MCP settings or deployment. Record unknowns rather than
   selecting a replacement system. Installation itself reads only Git identity
   and root-instruction presence, not architecture or task intent.
2. From a separate trusted harness checkout, follow its onboarding README with an
   explicit target and reviewed full commit pin. Inspect dry-run, then init/check.
   Review BOTH executable installer checkout and asset pin: they can differ.
   Record source origin, full SHAs, reviewer, date and rationale in the repository
   facts template. Pinning is an explicit human/controller trust decision, not a
   signature or security certification. Never select a mutable branch by default.
3. In the target, read START. Copy the repository, task, review and handoff templates
   from `.agent-harness/docs/onboarding/templates/` to project-owned documentation
   locations. Fill from inspected evidence; keep unknown fields explicit. These
   are editable copies; managed templates remain unchanged. Example handoff is
   illustrative and requires replacement of every identity/head/evidence field.
4. Manually merge the following block into existing instructions only after review:

```markdown
Read .agent-harness/START.md for installed paths and standalone validator commands.
Follow .agent-harness/docs/engineering-standard.md plus repository-specific rules.
Read .agent-harness/docs/orchestration/roles.md and context-pack.md in that folder.
Use existing project toolchains, architecture, checks and delivery controls.
The controller collects fresh protections, permissions and independent head review.
Workers return scoped PRs, exact SHA, executed checks and explicit limitations.
```

5. Follow `.agent-harness/docs/onboarding/workflow.md` for one authorized task.
   Snapshot inventory and initial graph are historical observations, not current
   repository facts. The graph's sole complete node means recording inventory
   completed, not that discovery, implementation or delivery completed. Create a
   separate project-owned graph only from the authorized task's facts and accepted
   plan. No product tasks, ownership, stack or build commands are guessed.

An installed skill copy is packaging evidence only. Fresh provider discovery and
an enforced read-only reviewer sandbox need separate runtime evidence. Until then,
label both unverified. Procedures do not install or enforce either capability.
