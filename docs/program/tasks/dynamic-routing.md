# Dynamic multi-provider routing (approved bounded task)

User authorized 2026-11-09. Scope/acceptance/ownership: `docs/plans/dynamic-provider-routing.md`. Depends on merged PC3 and original M1 gap; these are delivered at authoritative main fcfec45082208261e2992fca5501bc24d23bc5ce.

Implement minimal reusable routing policy, task/capability/budget validation, safe Sonnet/Sol attempt provenance and cross-provider final-review checks. Reuse existing T3 native execution and checkpoint/M1 context contracts. Explicit project/repository/task/attempt separation; no pilot globals in reusable core. Unknown budget stays unknown. No new scheduler, service, settings/permissions or full portability migration.

Acceptance: closed deterministic contracts; all positive/negative cases in the approved plan; PC1–PC3/M1 compatibility; focused draft PR with CI and final exact-head non-author cross-provider review coverage; bounded live provider directions/switch where supported with honest limits; real typed context handoff and fresh-process recovery; canonical policy and portability/gap handoff. Code remains report_ready until separately authorized and verified merge. No other M1–M5 gap or PR14 action authorized.
