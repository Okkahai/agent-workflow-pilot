# Model routing

Status: policy and protocol, observed 2026-11-05. Routing is an execution choice, not correctness evidence (engineering-standard.md). No benchmark has been run; quality claims below are hypotheses until the deferred protocol produces data.

## Rule

Route from the model IDs the controller actually sees advertised in the current session via `orchestrator_capabilities`. Never route from memory, from a table in this file, or from a name that sounds similar. If a wanted ID is not advertised, say so and stop or ask; do not silently substitute (t3-runbook.md). IDs below are a dated observation, not a registry.

## Observed advertisement (2026-11-05)

Source: `orchestrator_capabilities({})` in this session. Parent inherited `claude-sonnet-5-5`, effort `medium`, runtime `full-access`.

| Provider instance | Advertised model IDs | Effort options | Child tasks |
| --- | --- | --- | --- |
| codex | `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6.1-terra`, `gpt-6-luna` (+4 omitted) | `reasoningEffort` low..max (`ultra` on all but luna), `serviceTier` default/priority | yes, incl. cross-provider |
| claudeAgent | `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-fable-5-1`, `claude-haiku-5-5` (+9 omitted) | `effort` low..max, plus `ultracode` (opus, fable) and `ultrathink`; opus has `fastMode` | yes, incl. cross-provider |
| grok, cursor, opencode, antigravity, fx, kiro, muse, pi | listed with models or none | n/a | no: provider instance disabled |

`omittedModels` shows the short list is incomplete; `search` can reveal more. Advertised is not tested: no run of any ID is recorded here.

## Routing by role (hypotheses, not measured)

| Role | Selection principle | Constraint |
| --- | --- | --- |
| Coordinator | User-configured preference or a choice supported by measured evidence; exercise judgment on protections and delivery | Alone merges. Not the author of the head it reviews |
| Implementer | Select a capable advertised model for bounded work with explicit file ownership; treat unmeasured cost and quality comparisons as hypotheses | One writer per branch and directory |
| Reviewer | A different provider instance or model from the author when advertised; read-only; fresh task per head | Independent of the author, not merely a different prompt. Same-model review is recorded as weaker independence |
| Mechanical edits | Avoid delegation or use a user-preferred capable model | Must have a runnable check |

Raise effort before changing models when a task fails for reasoning depth; change model when it fails for capability or tool use. Record effort with the model ID in every handoff so results are attributable.

## Coordinator-led control plane

One coordinator thread owns plan, delegation, evidence collection, gate, and merge. T3 already provides the scheduler primitives: `delegate_task` async with completion wake, `task_cancel`, PR watch/wake. See docs/adr/0002-control-plane.md for the decision. Do not build a second scheduler, queue, polling loop or merge daemon in this repository; do not poll (`task_status`, sleep). Child tasks hand back a typed handoff (docs/orchestration/handoff.md) and never merge or spawn agents.

## Deferred benchmark protocol

Not executed. Run only when a decision depends on it and the user authorizes the usage budget.

1. Fix a task set of 5 or more small repository tasks with known acceptance checks (e.g. calculator and statistics fixes). Record repo SHA per task.
2. Candidate arms: model ID plus effort, taken from the live advertisement on the run day. Same prompt, same tools, fresh worktree per run, 3 or more runs per arm to expose variance.
3. Blind scoring: a separate grader sees diffs without model names. Metrics: acceptance checks passed, review findings, test failures after merge of the diff, wall-clock time, and usage drawn from the subscription window (not dollars).
4. Report per completed task (including retries), with pass counts and spread, not a single mean. A cheaper arm that needs retries counts retry cost.
5. Save raw results and exact commands under docs/evidence.md or a dated file. Conclusions expire when IDs change; rerun after a model change.
6. Cross-provider equivalence stays an untested contract until step 5 produces data.

## Limits

- Observed advertisement may change within a day. Re-call before the first delegation of each thread.
- No capability ranking is asserted here; names such as Sol, Astra, Terra, Luna carry no verified meaning.
- Provider settings beyond what `target.options` exposes were not tested.
