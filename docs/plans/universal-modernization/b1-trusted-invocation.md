# B1 — Trusted Controller Invocation Boundary

Approved by current user instruction 2026-11-11, through one Draft PR only.
Baseline main: 0beeb7e6aeeb27763c5a6c5bd21b51fb1e97d950.
Read actual mandatory architecture sources and local B0 report/critique/evidence first.
The Coordinator's local B0 artifacts are outside committed source and must not be overwritten.

## Architecture, ownership and scope

One small stdlib production module controller/invocation.py, tests/test_invocation.py,
minimal compatibility docs docs/program/invocation.md, this plan, task b1 spec/roadmap entry,
and existing canonical gap register status. No other production-module refactor expected.
One isolated Builder; correction budget2. Implementation approval never authorizes merge.

Dedicated pre-provisioned trusted Python3.12 runtime; explicit absolute interpreter,
expected package location and selected content identity, installation provenance reference.
Controller already trusts startup/base/interpreter/access before launch. An isolated child
identity response only detects mismatches before operational CLI, not before startup code.
No arbitrary untrusted interpreter verifier, OS sandbox or immutable-runtime claim.

Use named operations and fixed argv schemas, shell=False, -I -B, neutral approved cwd,
controlled Git path/environment preserving required Windows values. No caller module,
Python code, executable override or free argument tail. No worker-authored runtime policy.

Initial operation set: program check/next/resume; identity check/verify; task_context
validation; lifecycle prepare/attach/reconcile only if all nested paths/write targets and
authority expectations can be constrained with existing contracts. Reject unsupported
operations explicitly. Program record duplicates prepare and can remain unsupported;
identity bind/repair, continuation/successor dispatch grants, onboarding, routing mutation,
runtime provisioning and native dispatch/merge are excluded. If an operation cannot be
safely supported without legacy changes, reject and document its exact blocker.

For each supported operation specify required/optional inputs, trusted origins, read/write
sets, output schema, errors and replay semantics. Strictly validate nested delivery/checkpoint,
plan/spec, binding/envelope, journal/input/observation and reference paths before launching
stateful calls. Controller owns separate per-project state and exclusive writer assertions;
directories and assertions are not OS isolation or authentication. Missing ownership/current
approval blocks. Expectation must be freshly constructed from independently current authority
each operation. Do not cache Verified. Existing roadmap flags alone are insufficient.

## Path and process contract

Explicit target checkout/common-dir, filesystem plan inside checkout, specs relative to
plan.parent. task_context uses explicit root plus repository-relative plan. No pilot defaults,
external roadmap, state relocation/rebind, custom observer or automatic envelope recovery.
Stateful writes only designated controller state; partial/ambiguous state retained and blocked.

Use bounded reads DURING stdout/stderr collection, explicit timeout, encoding/exit/strict JSON
and operation-result validation. Kill/wait/pipe/thread cleanup on errors including Windows;
do not wait indefinitely for inherited pipes. Bound/sanitize diagnostic messages; never echo
approval contents, secrets or uncontrolled worker output into logs. Output success is not
authority. Timeout/write interruption does not prove no effects or tree-wide termination.

## Acceptance

1. Disposable installed wheel/runtime against non-Python Git fixture, paths with spaces and
   parentheses, neutral/target/hostile/Python-bearing cwd. No target dependency installation.
2. Runtime missing/relative/wrong minor/package/root/pin; harmless startup fixtures only,
   classification of detection vs prevention. No genuine untrusted runtime execution.
3. Allowlist/input/nested path/output schema/nonzero/encoding/timeout/stream overflow tests,
   bounded collection and cleanup. Wrong root/repo/common-dir/host and path redirects reject.
4. Fresh/missing/stale/revoked/superseded/cross-project approvals, changed A2 milestone/hash,
   absent/truncated envelope, consumed intent and ambiguous state fail closed without reset.
5. Supported stateful calls use designated state; replay preserves receipts/retries. Observe
   source/runtime/target/state/bytecode writes and explicitly unmeasured caches. No dispatch.
6. Existing Program/identity/continuation/checkpoint/live-recovery/context/onboarding and full
   uv run --locked pytest pass. Pin historical fingerprints; legacy bytes remain unchanged.
7. Independent opposite-provider exact-head review and required CI. Windows and Linux evidence
   separately labeled, skips never passes. Runtime rollback remains unverified unless tested.

## Documentation and delivery boundaries

Update PORT-01/02/03 only to demonstrated partial scope; preserve31 historical IDs and all
accepted A1/A2/PR14 limits. Track INV-DEFAULT-PLAN hazard with evidence/owner/severity/trigger/
stage/acceptance/non-goals; supported invocation prevents it, public legacy defaults unchanged.
Document official Python subprocess/startup/Windows and uv/T3 source URLs/date/version.

No B2 mapping/manifest/legacy-path-set or installed-wheel-onboard fixes; source/asset checkout
remains separately pinned. No C/D/E, adoption, package registry, runtime upgrades/rollback,
automatic authority service, scheduler/daemon or new checkpoint formats.
Draft/report_ready is not delivered. No Ready transition or merge. Retain original task,
worktree, PR, native refs and retry budget across corrections. Stop on essential scope blocker.
