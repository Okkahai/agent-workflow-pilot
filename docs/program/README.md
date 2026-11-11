# Real Program Coordinator roadmap

Source: ../plans/program-coordinator-design.md (full original M1–5 inventory);
../plans/program-coordinator-m1.md is the approved authority. Core rows are
historical merged references, not fresh authoritative completion assertions.
PC1 and dependent PC2 are approved. PR14 is separate and unmerged. Gap rows retain explicit
limitations and require later scope/ownership approval before execution.

## Coordinator live demonstration (PowerShell, repository root)

```powershell
uv run --locked python -m agent_workflow_pilot.controller.program check
uv run --locked python -m agent_workflow_pilot.controller.program next
```

Both produce JSON with plan_hash, selected task pc1, per-task state/explanation,
and merge_authorized=false. They perform no native calls or writes.

Collect authoritative observations yourself, then supply a local JSON file:

```powershell
uv run --locked python -m agent_workflow_pilot.controller.program next --observations C:/Temp/pc-observations.json
```

Schema: `{ "plan_hash": "<hash from check>", "tasks": { "m1-core": OBSERVATION } }`.
Omit unknown tasks. Code OBSERVATION fields (all required): state
(blocked/report_ready/delivered), head, verified_head, ref, children_terminal,
draft, merged, merge_commit, target_tip, ancestor_verified. SHA fields require
40 lowercase hexadecimal characters. Booleans must be JSON booleans. `ref`
is a controller-verified native evidence reference. head must equal verified_head.
For never-merged blocked/report_ready observations, merge_commit is null and merged/ancestor_verified are false. Only omitted observations default to empty; malformed empty input rejects. A delivered code observation requires non-draft merged implementation, terminal
children and authoritative verification that merge_commit is an ancestor of
that observed target_tip. These two commits need not equal. Recollect after a
force-push or new target observation; this helper cannot detect host changes.
For artifact tasks replace draft/merged/merge_commit/target_tip/ancestor_verified
with accepted and independent. Delivered requires both true. Evidence is trusted
controller input, not authenticated by this program. Never use PR-authored JSON.

## Reconcile this already-dispatched PC1 delivery

Use the controller's existing delivery checkpoint, preserving its task_key pc1,
original intent, native refs, retry budget and evidence. Do not manufacture a
second dispatch to demonstrate selection. If the existing checkpoint uses a
different task key, reconcile the reviewed roadmap identity explicitly first;
the helper refuses mismatched identity. Persist original native dispatch evidence
using the existing checkpoint contract before recording the reference:

```powershell
uv run --locked python -m agent_workflow_pilot.controller.program record --task pc1 --delivery C:/Temp/pc1-delivery.json --checkpoint C:/Temp/program.json
uv run --locked python -m agent_workflow_pilot.controller.program resume --checkpoint C:/Temp/program.json
```

Repeated record with identical arguments returns the existing delivery. Different
binding or changed plan/spec bytes fail. Resume reads the same checkpoint and
never modifies correction budget, evidence or native IDs. Dispatching means
ambiguous outcome and blocks; inspect native task/thread and branch PR records
before updating the existing delivery checkpoint. Record requires a previously
persisted delivery: for future dispatch, persist delivery intent, record its
binding, then make the native call and save returned references. No remote
exactly-once guarantee. A partial program-file write fails closed on resume.

The active reference deliberately holds the serial slot even after a delivery
report: controller must reconcile terminal native work and verified completion,
archive the binding, and explicitly invoke next without it. No automatic retry,
release, scheduler, remote dispatcher, merge, ready or watch operation exists.
Single trusted local writer only. `planned` belongs to the authored roadmap;
eligible/blocked/delivered are derived; report_ready comes from observations;
running comes from an existing reconciled delivery. A report cannot satisfy a
code dependency. Historical component rows need fresh observations to show as
delivered; milestone completion is never fabricated from historical notes.

Unit tests exercise fixtures and local checkpoint files. Real native dispatch,
CI, independent Ubuntu review, controller observation collection, crash recovery
and watch wake behavior are not proved by those fixtures. The controller must
save actual CLI JSON outputs during its live demonstration.

## PC2 same-delivery lifecycle contract

PC1 and PC2 are approved; PC2 depends on freshly observed delivered PC1.
At the PC2 milestone, gap rows and PR14 were unapproved. Current exceptions are separately authorized M1 gap, A1 and bounded A2; current authority comes from controller approval evidence, not this historical paragraph. PR14 remains excluded. The approved PC2 plan is
`../plans/program-coordinator-pc2.md`. No readiness state is bundled here.

The single trusted Coordinator owns all calls and local files. The new
`agent_workflow_pilot.controller.lifecycle` module accepts the existing program
binding and delivery checkpoint: do not prepare or dispatch PC2 again.
`reconcile`, `reevaluate`, and `resume` are aliases that re-read the same files
and require fresh native and host observations on every invocation.

Save controller-collected arguments as `C:/Temp/pc2-terminal.json`:

```json
{
  "scope": ["pc2"],
  "head": "<actual current 40-character PR head>",
  "native": {
    "task": "<existing native task ID>",
    "thread": "<existing native thread ID>",
    "status": "completed",
    "children_terminal": true,
    "ref": "<controller-read native terminal record reference>"
  }
}
```

Use actual IDs from the existing delivery, and a freshly collected observation
file with the current plan hash, delivered PC1 and report_ready PC2. Replace
placeholders; they are deliberately not valid evidence. A draft PC2 observation
has draft=true, merged=false, merge_commit=null, ancestor_verified=false.

```powershell
uv run --locked python -m agent_workflow_pilot.controller.lifecycle resume --binding C:/Temp/program.json --observations C:/Temp/pc-observations.json --input C:/Temp/pc2-terminal.json > C:/Temp/pc2-proof.json
```

An unmerged report returns action=awaiting_authorization, slot=held and
merge_authorized=false. Failed/interrupted/unknown native status, live children,
missing host evidence or exhausted blocked correction budget hold the slot.
Stale plan/head, conflicting identities or missing scope reject without writes.
Only verified delivered observations logically retire the binding; the immutable
file remains as its archive. Reevaluation returns another eligible task only if
it is in the supplied approved scope. It never dispatches or merges. Do not
call the old selector without the active binding to bypass this boundary.

Python API uses `(plan, root, binding, observations, scope)` plus:

- `prepare(..., delivery, task, acceptance, intent)` persists intent and records
  binding before a future native call; returns dispatch=false even on replay.
  Caller reconciles that intent with native records before deciding to invoke
  the tool. Acceptance must cite the approved task contract.
- `attach(..., refs)` attaches task/thread IDs with immutable replay receipts.
- `reconcile(..., native, head)` (CLI resume/reevaluate aliases) evaluates fresh
  trusted-controller evidence without resetting delivery retries or IDs.

For prepare/attach CLI, `--input` contains the corresponding named arguments
including scope. These are local helpers, not an evidence authenticator or
remote exactly-once mechanism. Never feed worker-authored claims as verified
observations. Single writer required. Crash after intent persistence requires
native reconciliation, never blind retry; remote crash behavior is untested.
CI and independent review remain separate controller responsibilities.

## A1 project identity (draft)

Project-scoped use of these commands (`--mode project --expect FILE`) is described in [identity.md](identity.md). Default `--mode legacy` is unchanged and not multi-project safe.

## A2 milestone identifiers

A2 (draft, unmerged) replaces the literal M1–M5 check in `program.validate` with `program.MILESTONE`: an ASCII letter, then letters/digits with internal `-` or `_`, ending alphanumeric, 1–64 characters, matched in full (`[A-Za-z](?:[A-Za-z0-9_-]{0,62}[A-Za-z0-9])?`). Case and bytes are preserved exactly (`M1` and `m1` differ); empty, non-string, whitespace, control, path, Unicode and other punctuation values fail `validate`. Milestones are inert labels shared freely across tasks and never authorize dispatch, approval or merge. Fingerprint code and serialization are unchanged: unchanged plans keep their v1 hashes, while any milestone edit changes the plan hash and so rejects old observations, bindings and A1 approval expectations. Not included: roadmap schema v2, configurable roadmap/spec bases, checkout rebind, registry.
