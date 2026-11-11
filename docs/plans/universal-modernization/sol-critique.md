**Revise the proposal before treating it as an implementation specification.** Its overall direction is sound, but checkout identity, approval provenance, migration compatibility and several acceptance criteria remain incomplete.

This is a fresh nonauthor, read-only critique. I inspected committed source using `git show e7791174e3a5ed46f4834d8d0dc5b076f7e19d00:PATH`, local delivery artifacts and primary upstream sources. I ran no project code, imports or tests; made no writes; launched no delegates; changed no runtime settings.

## 1. Blocking and important proposal corrections

### Identity must distinguish project, repository and checkout

**Important design blocker:** `root_id = sha256(project + "\0" + repository)` identifies a logical pair. Every checkout of that pair receives the same value. It cannot detect an unexpected sibling directory, copied state or a worker redirecting execution to another checkout.

The existing portability handoff explicitly requires independently resolved remote/repository/root expectations and warns that passing record values back as expectations is circular. Committed `program.record()` currently binds an absolute delivery path; `continuation.advance()` persists resolved paths in its journal and replay payload. Replacing those paths with a logical hash does not preserve their binding semantics.

Use three distinct concepts:

| Concept | Correct meaning | Required validation |
|---|---|---|
| Stable project identity | Controller-assigned identity that survives relocation | Compare against trusted project registration |
| Repository identity | Repository origin and host namespace; GitHub `owner/name` is one adapter | Independently resolve expected repository; reject unapproved origin changes |
| Checkout binding | Controller-approved association with a particular runtime checkout/worktree | Resolve actual root and worktree association; compare against controller-owned binding |

A path is a locator, not authorization. A repository remote is evidence, not independently sufficient authority. A worker-provided project file cannot establish either expectation.

Multiple legitimate worktrees must be allowed through explicit checkout bindings. Relocation should create a reviewed rebinding record linked to the previous locator; it must not silently change stable project identity or make old absolute references point somewhere new.

For arbitrary repositories, the universal contract should not mandate GitHub’s `owner/name` syntax globally. Preserve the existing GitHub validators in their adapter. General repository identity needs a host-qualified namespace or equivalent opaque identity.

### Approval provenance must admit explicit user decisions

**Important design blocker:** “approval only from the host default branch” is too restrictive.

Committed `program.select()` consumes trusted controller assertions and gates `approved`, `decision`, dependencies and scope. It does not authenticate those assertions. `docs/engineering-standard.md` separately assigns authorization and protected delivery to the controller.

A current user can authorize a bounded unmerged task. That approval need not already exist on main. Conversely, a worker changing `approved:true` in a PR does not authorize itself.

Correct contract wording:

> Selection requires a controller-verified approval reference bound to project, repository, task, approved scope and relevant plan/spec identity. Accepted sources include an explicit current user decision and an independently designated trusted policy reference. Worker-authored approval fields are claims until reconciled against that source.

Record the source reference, what it authorizes, and whether it has been superseded or revoked. Implementation authorization, adoption authorization and merge authorization remain separate. Contract publication itself grants none of them.

### Migration and rollback currently promise too much

**Important design blocker:** “new fields are additive, readers tolerant; revert to restore v1 behavior” conflicts with the actual closed schemas.

`program.validate()` accepts exactly version 1 and closed fields. `program.select()` expects the old binding shape. Checkpoint v1 is also closed. An old binary will not automatically read a new binding or roadmap.

The safe compatibility promise is directional:

> A new implementation may explicitly support historical v1 inputs. An old implementation is not promised to understand new records or safely operate after a new writer has advanced state.

Keep archived v1 records immutable and readable. They do not acquire cross-project authority merely because a shim can parse them. Authority requires an explicit controller binding to independently verified project/repository/checkout expectations.

Rollback must never mean deleting the state root. That can erase dispatch uncertainty, retry consumption, native lineage and replay receipts. Roll back installed assets separately from execution state. If an older binary cannot consume the active record, preserve it and stop, or use a separately specified backward conversion that preserves history and authority boundaries.

Keep four version concepts separate:

- Contract semantic version: normative guarantees and compatibility obligations.
- Record schema version: accepted serialized shape.
- Routing policy identity: schema/version plus immutable content hash.
- Distribution version: pinned source and asset manifest.

Changing accepted records needs explicit compatibility analysis. Changing normative contract meaning may require a contract version change even when JSON shapes stay identical. “All additive contract changes remain /1” is underspecified.

Retain the existing v1 fingerprint algorithm. Do not switch an active task into a new hash domain simply because a wrapper gains identity. A future domain change needs an explicit predecessor mapping and fresh authority reconciliation.

### Two source findings need correction; several others need narrower wording

**A7 is unsupported and should be removed.** `lifecycle.main()` selects `reconcile` for `reconcile`, `resume` and `reevaluate`, and supplies the same loaded argument dictionary. These are aliases. Sonnet identified no argument shape that succeeds for `reconcile` but fails for either alias. Existing local resume and delivered-reconciliation artifacts support the intended behavior. There is no basis for a “remove or implement dead commands” PR.

**A4 is a convention, not inherently a defect.** Program specs resolve relative to the roadmap directory. `task_context.reconstruct()` explicitly computes the same spec location using `plan_path.parent`, while requiring the plan to remain inside the supplied root. This is coherent. Document the two bases—roadmap-relative specs and root-relative context references—and test them when invocation changes.

**A9 is an unverified invocation seam.** Absolute package imports require an installed/importable harness package; they do not prove invocation must use the harness checkout as cwd.

**A15 is verified.** Committed README says “No application behavior yet” immediately before documenting calculator behavior. Correcting that sentence is reasonable documentation maintenance.

**U8’s subprocess ban should be rejected.** A read-only host collector or CLI adapter can legitimately use subprocesses. The relevant prohibition is a competing scheduler or unauthorized dispatch/merge path. An import ban tests syntax rather than that behavior.

**U12 must separate required evidence from advisory telemetry.** In `routing.usage_state()`, unknown remains unknown. `_blockers()` does not block ordinary routing solely because quota is unknown; `decide()` explicitly states unknown usage never triggers a switch. Missing required merge evidence blocks merging. Unknown subscription telemetry remains advisory.

### Delivery status must use the reconciled evidence

I independently read GitHub metadata confirming:

- PR18 merged as `fcfec45082208261e2992fca5501bc24d23bc5ce`.
- PR20 merged as `e7791174e3a5ed46f4834d8d0dc5b076f7e19d00`, from head `86fefa42d3f3b40f225e6456dcf6b66b274c8a0a`.
- That merge commit’s sole parent is the PR18 merge.

Local PR18/PR20 delivery addenda, native review artifacts and `final-review-coverage.json` support bounded completion and distinct opposite-provider review coverage. Their execution results remain recorded evidence; I did not rerun them or independently fetch every historical CI log.

The committed register still says final mixed-head reviews are open. That statement needs dated reconciliation. It does not invalidate the delivered routing milestone.

Likewise, historical `m*-core approved:false` values must not be interpreted as proof their implementation is undone. The local resumed Program decision explicitly reports `m1-core` as delivered despite those authorization flags. Completion evidence and permission to execute again are different dimensions.

## 2. Corrected contract and bounded migration recommendation

### Proposed inert contract text

The Coordinator can persist the corrected contract now as the research deliverable. It should say:

> Universal Contract v1 is a versioned reference specification for a shared harness operating against project-owned configuration and controller-bound execution state. It grants no implementation, adoption, dispatch, roadmap or merge authorization. It is not automatically loaded into provider instructions or installed into targets. Proposed requirements are distinguished from demonstrated behavior.

The acceptance mapping should preserve these groups:

| Invariant | Existing foundation | Acceptance still required |
|---|---|---|
| Arbitrary repository/stack; shared core | Standalone distributed validators; pure routing interfaces | Shared harness invocation against independent target cwd without adding harness dependencies to the target application |
| Project-defined roadmap | Existing deterministic selector and dependency validation | Arbitrary bounded milestone identifiers; unchanged historical v1 behavior |
| Distinct identities | Routing project/repo/task/attempt checks | Identity-bound Program/Delivery seam plus independently validated checkout binding |
| Cross-project rejection | Routing/context negative checks | Reject exchanged bindings, observations, contexts, reviews and state across projects, including identical task names and commit values |
| Bounded existing M1 context | `bounded_source`, reconstruction and `authorizes=False` | Preserve size/source/hash checks and existing formats; no replacement context subsystem |
| Native T3 execution | Intent/attachment/reconciliation and serial continuation | Thin adapter uses native operations and returned identity; ambiguous dispatch remains held |
| Mandatory opposite-provider review | `validate_reviews()` and actual mixed-head reviews | Exact head, nonauthor, underlying-provider coverage and distinct verified native review identities |
| One writer and replay | Checkpoint receipts, immutable binding, continuation journal | No redispatch on replay; conflicting payload rejected; historical attempts and retry consumption survive migration |
| Authorization/protected delivery | Existing fail-closed gate and engineering standard | Trusted approval-reference reconciliation; fresh host evidence and expected-head normal merge |
| Versioned distribution/trust | Full-SHA pins and manifest hashes | Supported compatibility matrix, explicit publisher trust decision and drift/upgrade/rollback behavior |

These are acceptance requirements, not claims they all pass today.

A trust annotation in a manifest cannot authenticate the publisher or establish that the controller approved it. The controller must independently verify the chosen origin/pin against its trust decision. Cryptographic signing can remain outside this cycle.

### First implementation recommendation

**Recommend one identity-bound Program binding adapter PR, followed by a separate arbitrary-milestone PR.** Do not combine identity, relocation, roadmap v2, distribution and approval machinery into Sonnet’s A2.

Bound the first PR as follows:

| Area | Exact scope |
|---|---|
| Behavior | Introduce an explicitly versioned identity-binding envelope referencing the unchanged immutable v1 Program binding and delivery checkpoint |
| Inputs | Independently supplied project/repository/checkout expectation and controller approval reference |
| Integration | Validate the envelope before the existing Program/Delivery adapter consumes the referenced state |
| Historical compatibility | Read archived v1 records without rewriting them; unbound historical state cannot authorize cross-project operation |
| Checks | Wrong project/repo/checkout rejected; identical plan bytes across projects rejected; worker record cannot supply its own expectation; conflicting replay rejected; existing state bytes/retries/receipts unchanged |

Expected files are a small binding helper, its narrow Program/Delivery integration, focused tests and compatibility documentation. Final filenames should follow the implementation plan; no need to prescribe a broad `ProjectContext` framework.

Explicit exclusions: no roadmap schema change, milestone generalization, relocation support, external-state-root selection, checkpoint/context replacement, native dispatch, installer changes, new scheduler, review hardening sweep or automatic migration.

This is a prerequisite recommendation, **not implementation authorization**. Its acceptance includes existing compatibility tests and `uv run --locked pytest` when implementation is authorized.

Choosing an external state root is unnecessary before defining identity. External storage may reduce accidental worker edits, but filesystem location alone is not a trust boundary. The minimal adapter should accept a controller-owned configured location and enforce binding; it should not introduce another state authority.

### Corrected A–E sequence

| Stage | Small PR boundaries | Acceptance / rollback |
|---|---|---|
| A | Identity-binding adapter; separate arbitrary-milestone change | Binding negatives and v1 compatibility; preserve state if reverting code |
| B | Shared invocation adapter; separate distribution-manifest extension | Target cwd/runtime separation, legacy install checks and asset rollback |
| C | Explicit project registration and checkout/worktree binding | Unexpected origin/root rejected; relocation only through explicit rebinding |
| D | Separately authorized two-project integration | Different-stack projects, exchanged-evidence negatives, native delivery-readiness cycles |
| E | Individually scoped recovery, parallelism, memory and UX work | Each gap’s own acceptance; no umbrella authorization |

A docs-only PR is a valid persistence vehicle for the current analysis, but adding tests makes it implementation. Deliver the corrected contract/register proposal in this research cycle; do not make another research approval a prerequisite for receiving the requested analysis.

## 3. Gap completeness amendments

Use **`docs/readiness/routing-gap-register.md`**, preserving existing links and IDs. Retain Master Recovery IX as the historical priority source and delivery reports as dated evidence. Keep the P3 JSON as retained provenance, with one canonical current status per ID.

Every row needs: **component, evidence, desired behavior, risk/priority, dependencies, intended stage, acceptance, authorization and non-goals**. Add status and owner/trigger where useful. A global “nothing authorized” banner is helpful but insufficient when some rows describe delivered work and others remain proposals.

The following are the required row contents, condensed for transfer.

### Identity and continuity rows

| ID | Component/evidence; desired behavior | Risk, dependencies, stage | Acceptance; authorization; non-goals |
|---|---|---|---|
| PORT-01 | Installer/invocation and portability handoff; complete shared workflow for arbitrary-stack targets | P0; PORT-02/03 and B–C; D | Two independent different-stack delivery-readiness cycles; future scope unapproved; no customer adoption |
| PORT-02 | `program.validate`, persisted paths; project-defined milestones and explicit path conventions | P0; identity/path contract; A–C | Non-M milestones accepted, historical fixtures preserved, explicit rebinding behavior; unapproved; no roadmap approval changes |
| PORT-03 | Program binding/checkpoint seam; independent project/repo/checkout validation | P0; trusted expectations; A then D | Exchange identical-looking A/B records and reject; legitimate worktrees explicitly bound; unapproved; no sandbox claim |
| CTX-01 | M1 reconstruction plus approval provenance; bounded trusted reconstruction | P0; PORT-03; A/D | Wrong repo/head/source/approval rejected; explicit user approval accepted when properly bound; unapproved extension; no second context format |
| CONT-01 | Master Recovery IX and committed stale register; one reconciled current view | P0; evidence reconciliation; current documentation plus later checks | All stable IDs retained, statuses sourced, no competing register; research text authorized only; no operational state rewrite |

### Routing, recovery and completed scope

| ID | Component/evidence; desired behavior | Risk, dependencies, stage | Acceptance; authorization; non-goals |
|---|---|---|---|
| ROUTE-01 | Routing module/policy and actual Builder records; preserve bounded implementation | Delivered for bounded scope; capability drift ongoing | Reconcile delivered evidence; no redispatch; no provider-equivalence claim |
| ROUTE-02 | Review validator and final native reviews; exact-head opposite-provider coverage | Delivered bounded scope with retained P3 limitation | Distinct verified reviewers and required coverage; no new execution authority; no formal GitHub-approval claim |
| ROUTE-03 | `usage_state`, installed capability snapshot; honest advisory telemetry | P1; supported trusted telemetry if available; event-triggered | Unknown/stale/estimated data cannot fabricate measured quota or trigger a switch; unapproved automation; no scraping |
| FALL-01 | Planned terminal Sonnet→Sol switch; preserve lineage during real interruption | P1; bounded interruption scenario, identity binding; E | Reconcile uncertain outcome without duplicate writer/PR or retry reset; unapproved; no exactly-once promise |
| M1-GAP | PR18 merge and recovery artifacts; preserve delivered bounded M1 | Delivered; migration regression obligation | Existing reconstruction/compatibility remains valid; no new work authorized; no replacement memory system |

### Original M2–M5 and later capabilities

| ID | Component/evidence; desired behavior | Risk, dependencies, stage | Acceptance; authorization; non-goals |
|---|---|---|---|
| M2-GAP | `skills.py` discovery limitation; actual Codex native skill use | P1; fresh catalog and native run; separately scoped | Record installed skill revision, discovery, invocation and resulting use; **unauthorized**; no inference from directory presence |
| M3-GAP | `docs/program/tasks/m3-gap.md`; decision-driven MCP/tool comparison | P2; named real decision and metric; optional separate scope | Successful scoped calls and measured outcomes with limitations; **unauthorized**; no generic benchmark campaign |
| M4-GAP | Onboarding assets and portability handoff; trusted adopter lifecycle | P0/P1; B/C and explicit adopter approval | Pin/origin trust, dry-run/init/check/upgrade/rollback and independent project smoke; **unauthorized**; no registry/signing mandate |
| M5-GAP | Recovery/readiness task scope; interruption, CI wake and security boundaries | P1; identity and host-evidence contract; E | Interrupted/reconciled event, stale/duplicate wake rejection, missing rights/protections block; **unauthorized**; no unattended-production claim |
| PAR-01 | Ownership and serial continuation contracts; bounded two-Builder integration | P1; isolated serial workflow; E | Disjoint ownership, conflict refusal and integration checks; unapproved; no general scheduler |

Do not rename M4-GAP as merely a “PORT-01 sub” row. Its stable identity and publisher-trust acceptance must remain independently visible.

| ID | Component/evidence; desired behavior | Risk, dependencies, stage | Acceptance; authorization; non-goals |
|---|---|---|---|
| MEM-01 | Master Recovery IX; versioned project facts and ADR index | P2; identity/trust; E | Reviewed fact with source/revision/project identity; stale/cross-project fact rejected; memory cannot authorize execution; unapproved; Obsidian optional |
| DOC-01 | README and DOC-P3-03 evidence; operational documentation agrees with behavior | P1; current baseline; each relevant PR | Specific links/status/behavior checked; implementation checks separately authorized; no wording-mirroring test |
| QA-01 | Delivery artifacts and evidence classes; traceable claim classification | P1; continuous | Each material claim names source/class/date/head/limits; research reconciliation allowed; no simulated-as-live evidence |
| UX-01 | Master Recovery IX; understandable adoption flow | P2; demonstrated portable workflow; after D | Documented entry command, actionable failure output and cross-platform user scenario; unapproved; no hidden approval automation |

### Preserve all four accepted P3 rows

| ID | Evidence and desired behavior | Trigger/stage and acceptance |
|---|---|---|
| ROUTE-P3-01 | `validate_reviews`; reject repeated native review identity across normalized entries | Before expanded/imported review consumption; same-ID cross-provider negative |
| ROUTE-P3-02 | `validate_record`; derive route equality and require native identity for real terminal outcomes | Before editable/imported state or broader writer trust; tampering negatives |
| DOC-P3-03 | Shared routing table; distinguish caller-choice planning from automatic implementation continuation | Before operational reuse of that table; inspect wording against actual decisions |
| RECOVERY-P3-04 | Empty-attempt refresh refusal; document safe predispatch recovery | Before supporting that scenario; preserve uncertainty/history, demonstrate no duplicate dispatch |

All remain **P3, open, accepted as nonblocking for PR20**, with future remediation unauthorized. Preserve ledger owners and source artifacts. No new gap ID is needed for these corrections; any additional ID must be explicitly marked proposed.

## 4. Primary-source research addendum

Retrieved **2026-11-09** through read-only GitHub API and official documentation. These are source inspections, not installation or execution benchmarks.

### Framework revisions and bounded findings

**Gas City — active, revision `6c095aace30bdeba90a837fb7ed6993d60ca157e`.** Metadata reports `archived:false`. I inspected [`cmd/gc/dolt_project_id.go`](https://github.com/gastownhall/gascity/blob/6c095aace30bdeba90a837fb7ed6993d60ca157e/cmd/gc/dolt_project_id.go). It explicitly models identity reconciliation, including refusal, repair, migration and generation decisions across metadata layers. This supports separating identity and reconciliation rather than equating identity with a path. It does not validate adopting Gas City’s storage/runtime architecture. **Optional reference idea; adopting a second control plane is rejected for this scope.**

**GSD — archived, revision `bdcaab2c752d9a33a1a1ca9acf3a3c81fb991815`.** Metadata confirms archival; README redirects to `open-gsd/gsd-core`. The inspected [`commands/gsd/new-project.md`](https://github.com/gsd-build/get-shit-done/blob/bdcaab2c752d9a33a1a1ca9acf3a3c81fb991815/commands/gsd/new-project.md) defines project/config/requirements/roadmap/state artifacts and delegates to workflow instructions. This proves a documented command structure, not successful execution or fresh-context reliability. The exact archive date asserted by Sonnet is not established by the current metadata. **Optional planning reference; successor behavior remains unknown.**

**OpenSpec — active, revision `0fa4a9705c20ef1c571fe3ded74435733e4b73a1`.** I inspected [`docs-lab/customize/project-config.md`](https://github.com/Fission-AI/OpenSpec/blob/0fa4a9705c20ef1c571fe3ded74435733e4b73a1/docs-lab/customize/project-config.md). It distinguishes globally injected context, artifact-specific rules and operation guidance. That is useful evidence for keeping the universal contract outside automatically injected project context. It does not establish controller authority or isolation. **Optional design reference; dependency adoption rejected this cycle.**

**BMAD — current official reference, revision not exposed by the retrieved page.** The [skills and agents reference](https://docs.bmad-method.org/reference/skills-and-agents/) documents per-skill installation and `.claude/skills` versus `.agents/skills` placement. That corroborates layout conventions, not native activation in this pilot. The inspected page does not establish Sonnet’s installer-cleanup claim; that needs installer source. **Optional layout reference; no need to adopt personas or execution loops.**

**Overstory — archived, revision `ff38f3f76f084abcc34f519bcaa69580f6e53cf1`.** Metadata and README confirm no longer maintained and point to Warren as a spiritual successor. I inspected [`docs/runtime-adapters.md`](https://github.com/jayminwest/overstory/blob/ff38f3f76f084abcc34f519bcaa69580f6e53cf1/docs/runtime-adapters.md): it describes an `AgentRuntime` seam for spawning, configuration, readiness and transcripts. Its adapter count is internally stale relative to its own diagram/README. Therefore avoid framework-count metrics. **Optional adapter-boundary reference; adoption rejected, Warren equivalence unknown.**

These queried repositories are specific variants. Their identities must not be conflated with forks, successors or similarly named GSD projects.

### T3 and provider behavior

I inspected T3’s [orchestrator documentation at revision `4f0b74e190261c8233ae52af17b0fd1734e99e50`](https://github.com/pingdotgg/t3code/blob/4f0b74e190261c8233ae52af17b0fd1734e99e50/docs/orchestration-v2/orchestrator-mcp-server.md). It distinguishes T3-created child threads from provider-native subagents; children receive the supplied brief rather than copied parent conversation. Explicit provider-instance targeting fails when unavailable. Stable request IDs support scoped durable retry semantics; that is not a blanket exactly-once external-execution guarantee.

The local `capabilities-2026-11-09.json` is historical advertised capability evidence. The Coordinator’s newer check is reported context, not a live check performed by this reviewer. Provider/model/effort choices must remain runtime-validated; do not replace advertisements with names copied into a universal contract.

Current [Codex subagent guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents) says children inherit parent permissions; read-only instructions do not create a separate sandbox. This reinforces the existing distinction between independent source review and OS-enforced isolation.

[Codex skills guidance](https://learn.chatgpt.com/docs/build-skills) describes progressive disclosure and a bounded initial catalog that may shorten or omit descriptions. [Claude Code skills guidance](https://code.claude.com/docs/en/skills) likewise documents a description budget and skill-body lifecycle. Thin instructions are justified; neither page proves this installation’s native invocation.

The [official pricing page](https://learn.chatgpt.com/docs/pricing) was retrieved, but no subscription-window consumption measurement or quota API was established. Dollar comparisons do not answer this user’s five-hour/seven-day budget question. Model/effort efficiency remains unmeasured here; no runtime change is recommended.

**Necessary:** native T3 reuse, live capability validation, bounded briefs, honest isolation/evidence labels. **Optional:** framework-inspired configuration seams. **Deferred:** measured efficiency, broader recovery and successor evaluation. **Rejected:** another scheduler, quota scraping and capability claims based on marketing counts.

## 5. Verdict

**Architecture proposal: revision required before implementation authorization.**

Retain the shared-core/project-state direction, inert contract, existing register, native T3 execution and staged migration. Correct identity, approval provenance, compatibility/rollback and evidence status; fill the missing acceptance fields; remove the false lifecycle defect and syntax-based guard proposals.

Observations written: none; this review explicitly prohibited writes.

**Next: Coordinator persists the corrected contract and consolidated register proposal, with the identity-binding adapter presented as a separately authorizable first PR.**
