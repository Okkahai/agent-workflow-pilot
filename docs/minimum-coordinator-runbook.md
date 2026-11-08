# Minimum Coordinator operational runbook

This milestone follows the read-only collector; the sample graph is not a project
roadmap. Read the actual task plan and readiness checklist before execution.
No readiness records are updated by the implementation helper.

## Checkpoint contract

`controller.checkpoint` offers `new`, pure `apply`, `save` and `load` functions.
A single trusted Coordinator owns a local checkpoint outside committed evidence.
Initialize with a stable task key, acceptance strings, dependency task keys and
retry budget (two for this MVP). Persist every returned transition before its
associated remote action. State is a recovery hint, never authentic evidence or
merge authorization. No scheduler, credentials, remote client or daemon is added.

Lifecycle: planned -> dispatching -> building -> awaiting_ci -> awaiting_review
-> complete -> awaiting_authorization. Complete means report ready only.
Correction increments the bounded counter and returns through dispatch/build;
exhaustion blocks. `block` records any unknown or inaccessible prerequisite.

Use stable native event IDs with `apply(state, event_id, action, **payload)`.
Identical replay is a no-op; ID reuse with different payload rejects. Receipts
contain transition payloads only, not tool transcripts. The strict checkpoint
limit is 64 KiB; exceeding it blocks save. Do not prune receipts during a run.
Refs accept environment/provider/task/thread/branch/PR identifiers or URLs.
CI and review contain only exact head and durable artifact reference. These are
trusted-controller assertions, not validation of remote authenticity or findings.
Never feed PR-authored checkpoint data to a delivery gate.

## Native execution recipe

1. Discover native capabilities as described in [T3 runbook](t3-runbook.md).
   Create the task contract with key `minimum-coordinator-mvp-20261108`.
   Apply `dispatch` with `client_request_id` and a list of freshly reconciled
   `completed_dependencies`; save before native delegation. T3 creates the Windows
   worktree. Record returned native IDs using `started(refs=...)`, save, and follow
   the tool's returned `next` contract for completion wake. Never poll or add a
   scheduler. Worker returns tests, draft PR and full pushed SHA; link immediately.
2. On build completion independently resolve GitHub PR and branch head; apply
   `head(head=...)`. Collect current host CI and required-check policy. The existing
   read-only collector's `observed_ci` does not establish required checks or merge
   eligibility. Unknown checks block; pending CI uses native PR watch and ends the
   Coordinator turn. On wake recollect; record `ci(head=..., ref=...)` only after
   the required exact-head checks pass. Worker never watches CI.
3. Delegate a fresh Ubuntu review using the linked environment and exact public
   PR SHA, plan and acceptance criteria. Review is read-only public analysis: no
   PR code execution, write credentials or claims of enforced isolation from role
   prose. Follow native completion wake. Verify reviewer identity, reviewed SHA,
   artifact and absence of actionable findings before `review(head=..., ref=...)`.
4. CI failure or actionable findings uses `correction(reason=...)`; save before
   dispatching the correction to the Windows worktree. At most two rounds, then
   escalation. A changed head clears CI/review; new CI and a new independent review
   task are mandatory. Never reuse an earlier review merely because tests pass.
5. `report` moves complete to awaiting_authorization. Keep this PR draft/unmerged.
   Coordinator records actual native IDs and distinguishes live execution from
   synthetic coverage and untested recovery. Unwatch before final handback.
   Any future authorized merge separately requires fresh host/protection/permission
   evidence and the policy gate; no checkpoint transition authorizes it.

## Resume and remote ambiguity

Load and validate checkpoint, then read referenced T3 task/thread and GitHub
branch/PR records before taking action. Search for an existing branch PR before
creating one. Save dispatch intent/clientRequestId first; a crash after remote
acceptance but before saving the returned ID is ambiguous. Never blindly resend
or assume a clientRequestId provides exactly-once execution. Block until native
records identify the existing action or establish it did not occur. A missing or
corrupt checkpoint is not permission to start a replacement task.

`reconcile(refs=..., head=...)` is for a trusted operator who has resolved existing
remote build/PR identity. It clears both evidence references, preserves retry
consumption and returns to CI collection even if head is unchanged. It cannot
recover an unlaunched build: resolve that dispatch manually from authoritative
records before choosing a fresh run. Unknown remote state remains blocked.
Atomic same-directory replace protects against partial JSON writes and failed
replacement retains the old file. File flush/fsync does not promise directory
power-loss durability, multi-writer coordination, network filesystem guarantees
or an atomic transaction with remote services. Resume always reconciles remote
state. Tests simulate interruption; no live crash or Ubuntu review is claimed by
these tests.
