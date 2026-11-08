# Live recovery validation

Authorized reliability milestone, baseline 2da639ac9c3dc4c9178462b79850f30e29c07d45. No merges or protection/configuration changes.

1. T3 isolated Windows Builder adds tests/test_live_delivery_probe.py with a named deliberately failing assertion and concise explanation, runs it to record actual failure, commits/pushes and creates exactly one dedicated draft PR. Deliberate failure only on feature branch; do not change CI or fix it yet. Report head/worktree/PR through native completion.
2. Coordinator checks actual failed GitHub CI on exact head, saves checkpoint and failure evidence, then delegates correction to Windows Builder in existing worktree. Fix the probe with a legitimate passing regression check of checkpoint stale-evidence rejection; no unrelated changes, normal push to same PR. At most two correction rounds; no duplicate PR. New head clears old evidence; Coordinator records CI using native watch/wake if pending.
3. Ubuntu independent exact-head public read-only review, no PR code execution or writes. Collect automatically; correct real findings only, new head requires CI and fresh review.
4. Fresh Windows processes save/load/reconcile checkpoint with authoritative task/PR records, replay dispatch/completion IDs without new side effects, reject stale CI/review, exercise bounded retry and ambiguous dispatch block on isolated copies. Distinguish local simulations from live remote crash. Save precise report, retain draft/unmerged PR.

Coordinator owns local readiness execution state/report. Builder owns only dedicated probe test and this plan as inherited; no changes to checkpoint implementation unless actual defect found and explicitly reported. T3 owns scheduling/worktrees/wakes; no polling engine. Single trusted writer. Recovery: reconcile recorded native IDs and PR before dispatch, never blindly redispatch an ambiguous intent. This controlled red commit is intentional test infrastructure and cannot be delivered as eligible.
