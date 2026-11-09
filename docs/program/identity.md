# A1 project identity and approval binding — implemented draft

Status: A1 is `report_ready`, draft and unmerged. The implementation at `b6fe40b1c460c8e4de1e5f01139ac342a916b66a` passed required CI and both independent cross-provider reviews. Exact-head evidence must be renewed for every subsequent revision; publication does not grant ready or merge authorization. Proposed architecture lives in `docs/plans/universal-modernization/`; this file records what was built. Code: `src/agent_workflow_pilot/controller/identity.py`; tests: `tests/test_identity.py`.

## What it is

One small versioned adapter at Program/Delivery entry points. It does not authenticate anyone and authorizes nothing: every report has `authorizes=false`, `merge_authorized=false`. It checks that a **controller-supplied expectation** agrees with an **independently observed Git checkout** and with an **identity envelope** stored beside an unchanged legacy binding.

| Concept | Where it lives | Notes |
| --- | --- | --- |
| project id | expectation + envelope | opaque slug; not a path |
| repository identity | `{host, name}` | any host is *representable*; only `github.com` origins are *verifiable* |
| checkout / worktree / common dir / origin | observed with bounded `git rev-parse`/`config` reads | compared by file identity (`samefile`), never by hash or string |
| task | binding + envelope | logical key (`program.py` ids) |
| native attempt | checkpoint `refs` only | unchanged; not copied into the envelope |
| approval | expectation `approvals[task]` | evidence record, referenced by `approval_ref` |

## Modes (CLI: program, lifecycle, continuation)

- `--mode legacy` (default): exactly the old behaviour and bytes. **Not multi-project safe.** It refuses a binding that has an identity envelope (`<binding>.identity.json`), so a legacy entrypoint cannot accidentally consume project-bound state. It rejects `--expect`.
- `--mode project --expect FILE`: the expectation is validated, the checkout observed and the envelope verified **before** the binding, observations or checkpoint are read. Missing `--expect`, missing envelope, or any mismatch exits 1. Creating commands (`program record`, `lifecycle prepare`, successor in `continuation`) check checkout and approval first, then write the envelope after success. A crash in between leaves a binding with no envelope, which project mode refuses until `identity bind` is run.
- Python API: `lifecycle.attach/reconcile` and `continuation.advance` revalidate the current operational root, binding bytes, checkout/origin and current controller approval using `project=<identity.verify(...) result>`. The result holds revalidation context, not reusable authority; ordinary construction or a JSON dict cannot stand in for it. Direct continuation checks successor approval before journal/successor writes and creates the successor envelope before returning a dispatch grant. CLI and API use that same operation.
- `python -m agent_workflow_pilot.controller.identity check|bind|verify --plan --expect [--binding] [--task]`.

## Files

Expectation `agent-workflow-pilot.identity-expectation/1` (controller-owned, **never** inside the repo a worker edits): `project_id`, `repository`, `checkouts` (absolute approved roots incl. approved worktrees), `common_dir`, `approvals` keyed by task. Approval record (closed): `ref, source (user_decision|trusted_policy), designated, project_id, repository, task, scope, plan_hash, spec_sha256, operation ("implement" only), status (valid|revoked|superseded), revision`. Envelope `agent-workflow-pilot.identity/1` (closed): `project_id, repository, task, plan_hash, spec_sha256, binding_sha256, approval_ref`. An envelope can never be passed as an expectation (schema check). Extra fields such as `approved` are rejected.

## Trust limits (read before relying on it)

Three accepted nonblocking limitations are tracked in the existing canonical
`docs/readiness/routing-gap-register.md` as A1-P3-01, A1-P3-02 and A1-P3-03.
For every Python API operation, reload independently current controller approval
evidence and obtain a fresh verification result. A long-lived proof retains an
in-memory expectation reference and does not detect later revocation on disk;
CLI calls reload each invocation. Interrupted non-atomic envelope writes fail
closed: preserve partial markers, legacy state and uncertainty for reviewed
manual recovery, never reset state to resume. Custom-observer successor checks
currently use the default observer; custom-observer continuation is not a
supported operational guarantee. These findings are tracked, not fixed here.

- Python cannot tell who wrote a file. The expectation and approval evidence are trusted *assertions*; the controller must keep them where workers cannot write. Roadmap `approved`/`decision` flags and PR flags remain necessary but are never sufficient in project mode.
- Origin is the local `remote.origin.url`; it is not fetched or compared with the network and a local config edit is not detected beyond the expectation.
- Implementation approval is never merge approval; `operation` must be `implement`.
- No project registry, relocation/rebind, arbitrary milestones, installer change, routing/gate change or new state machine. Moved roots are rejected, not migrated.
- Legacy v1 binding/checkpoint/context/handoff/routing/receipt formats, fingerprints, retries and native IDs are unchanged (golden-byte test). Rollback = stop using project mode; state is retained, nothing is deleted or reset. Old binaries are not promised to read envelopes and legacy mode refuses bound state.

## Supported vs blocked hosts

| Case | Result |
| --- | --- |
| GitHub-origin checkout, Windows 11, case alias, directory junction to the approved root | tested, accepted |
| Junction/path to a different repository, unapproved sibling worktree, sibling clone, changed origin | rejected |
| Approved extra worktree | accepted (explicit `checkouts`) |
| Symlink alias | accepted if the OS allows creating one; skipped on this host (privilege) — **not verified here** |
| Non-GitHub host, remote-less checkout, bare/non-Git path | explicit block (`unsupported:` / error); no portability claim |
| POSIX/Ubuntu, 8.3 short names, network shares | not tested here |

Use disposable fixtures only; no real target repository was adopted.
