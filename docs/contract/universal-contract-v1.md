# Universal Harness Contract — proposed v1.0

Status: REVIEWABLE PROPOSAL, 2026-11-09, against main `e7791174e3a5ed46f4834d8d0dc5b076f7e19d00`. This specification grants no implementation, adoption, dispatch, policy migration or merge authority. It is an on-demand reference, not an automatically loaded instruction file. Existing formats remain unchanged. Audit and migration: `docs/plans/universal-modernization/migration-proposal.md`. Proposed consolidated register: `docs/readiness/routing-gap-register.md`.

## Invariants and acceptance obligations

| ID | Normative requirement | Existing foundation / required acceptance |
| --- | --- | --- |
| UC-01 | Arbitrary independent repositories and application stacks; target applications need not install the harness toolchain | Standalone validators exist; shared controller invocation against a non-Python target cwd remains unverified. Stage B invocation tests and D different-stack cycles required. |
| UC-02 | Shared version-pinned code, skills and policy; per-project configuration, roadmap, approvals, checkpoints, evidence and usage | Validate configured state ownership and never write the shared installation during target execution. State location alone is not a security boundary. |
| UC-03 | Project, repository, logical task and execution attempt have distinct identities | Routing checks exist. Extend Program/Delivery binding with independently supplied identity expectations; identical task/plan/SHA values in another project must fail. |
| UC-04 | Stable project identity is not a checkout locator | Controller-owned registration binds a host-qualified repository identity and approved checkout/worktrees. Independently resolve actual root/origin/worktree; reject unexpected sibling roots and origin changes. A hash of project+repo cannot validate a root. Relocation requires explicit rebinding, retaining predecessor history. |
| UC-05 | Each project defines its own milestones, roadmap/spec locations and acceptance commands | Selector/DAG reuse; future bounded milestone identifiers must accept non-M1–M5 names while preserving historical records. Specs are roadmap-directory-relative; context references are project-root-relative. |
| UC-06 | No project A record authorizes project B | Negative tests exchange binding, observations, context, quota, reviews and checkpoints, including identical task names, plan bytes and SHAs. Provider summaries cannot supply their own trusted expectations. |
| UC-07 | Existing bounded, reconstructible M1 handoff/context contract remains authoritative for transferred context | Reconstruct against independently resolved identity/head/source hashes and limits; stale/missing/special sources rejected, text stays inert, fresh processes agree. No replacement context or full-transcript injection. |
| UC-08 | T3 native execution remains the orchestration layer | Thin adapter only: persist intent, invoke supported native primitive, reconcile returned IDs. No second scheduler, daemon, queue or merge service. Legitimate CLI/collector subprocess use is not prohibited. |
| UC-09 | Provider-independent task contracts and mandatory opposite-provider independent exact-head review | Explicit runtime-advertised provider/model/options, non-author reviewers, mixed-provider coverage and distinct verified native reviewer identities. Same-provider model changes do not satisfy cross-provider independence. |
| UC-10 | One writer by default; replay never grants another dispatch; ambiguous native state holds the slot | Preserve task identity, scope, native lineage, receipts and retry consumption. Test conflicting replay and overlapping writers; demonstrate returned native identities before claiming runtime behavior. No exactly-once promise. |
| UC-11 | Approval, selection, implementation/adoption and merge are separate boundaries | Controller verifies approval reference bound to project/repo/task/scope/plan/spec. Sources may be explicit current user authorization or designated trusted policy. PR-authored booleans alone are not permission. Supersession/revocation must be reconciled. |
| UC-12 | Required delivery evidence is fresh and fail-closed | Changed head invalidates final CI/review. Missing protections/permissions/required checks block merge. Normal protected expected-head merge only, separately authorized; no admin bypass or stale auto-merge. |
| UC-13 | Unknown quota stays unknown and advisory | Thresholds only for supported trustworthy current telemetry; session/weekly evidence separate from tokens and API-equivalent cost. No private quota scraping or invented reserve enforcement. |
| UC-14 | Compatibility is directional and explicit | New readers may support immutable historical v1 records; old binaries need not read new schemas. Unbound historical records cannot authorize cross-project actions. Preserve v1 fingerprint semantics and receipts; any hash-domain migration needs explicit predecessor reconciliation. |
| UC-15 | Distribution version/pin, record schema, policy content identity and normative contract version are separate | Full source pins/hashes prove content identity, not publisher trust. Verify origin/pin against controller trust decision; test legacy upgrade/drift/asset rollback. Reverting binaries never deletes uncertain execution state. |
| UC-16 | Evidence and documentation remain scoped and honest | Claims carry source/class/date/revision/limits. Mocked/local/native/host evidence distinguished. No isolation, production resilience or whole-workflow portability claim without acceptance. Secrets excluded; no automatic memory authority. |

## Version and migration rules

Contract semantic version changes when normative guarantees/compatibility change. Serialized shapes use their own explicit schema versions. Policy version and content hash are immutable identities. Distribution uses a pinned revision and asset manifest.

Do not silently rewrite v1 roadmap/binding/checkpoint/context records. Archive original bytes; new identity envelopes reference historical records. Readability is not authorization. A new reader must reconcile trusted project/repository/checkout and approval references before consuming legacy state operationally. No implicit relocation, retry reset or event-receipt deletion.

Asset rollback and execution-state recovery are separate. If reverted code cannot read current state, retain it and stop; only an explicitly specified lossless backward conversion may resume it. Do not delete state roots to roll back.

## Current proof boundary

PC1–PC3, M1 and bounded dynamic routing are delivered. Program-level project isolation, arbitrary milestones, shared external invocation and two-project whole-workflow adoption remain absent or unverified. Windows cross-provider review does not prove Ubuntu isolation. Future implementation stages and all original M2–M5 gaps require authorization.
