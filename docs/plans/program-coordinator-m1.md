# Approved Program Coordinator Milestone 1

User authorization 2026-11-08: implement minimal roadmap/selection/recovery layer, draft PR, CI, independent Ubuntu review and corrections; no ready/merge authorization. Full proposal: program-coordinator-design.md. This task supersedes its pending-decision language: single thread with Program/Delivery logical roles; code dependencies require verified merged target-branch implementation; research/design may use independently verified artifacts; approved task execution automatic, merge separate.

Baseline main 2da639ac9c3dc4c9178462b79850f30e29c07d45. PR14 is separate open draft at d37b00877895eca3036639c5ddcb73ee09112de2; do not modify or treat as merged. No dependency on PR14 code.

## Bounded ownership and output

One Windows Builder in T3 isolated worktree owns new controller/program.py, tests/test_program.py, docs/program/{roadmap.json,README.md,tasks/*} and focused runbook docs. Keep existing graph/handoff/checkpoint/gate contracts unless a demonstrated defect requires minimal compatible change. No dependencies, scheduler, services, config, permissions, CI changes or unrelated repos. Coordinator owns local readiness state/evidence.

Use graph validation through a projection for cycle/reference/ownership checks; keep actual roadmap separate from sample graph. Store reviewed scope/acceptance/approval/priority/task identity once and references to native T3/GitHub evidence, not transcripts. Evidence input is trusted-controller-collected assertions, never PR-authored truth or automatic host authentication. Explicitly reject malformed, inconsistent, stale, draft or unmerged code completion evidence. Do not assume current main must equal an older merged commit: specify authoritative ancestry/verification semantics.

Roadmap should cover actual original Milestones 1–5, merged component references and explicit outstanding gaps, PC1 approval and PR14 pending delivery. No fabricated milestone completion or newly approved gaps. Pure deterministic selector returns task/state/explanation or blockers; one serial active task, stable priority/ID. States planned/eligible/running/blocked/report_ready/delivered must be consistent and derived where appropriate. All remaining unapproved work stays authorization-blocked.

Persist plan revision/hash, active task and immutable delivery/native refs before side effects; replay/resume returns existing task and never dispatches duplicate work. Ambiguous outcome blocks; no exactly-once remote claim. Existing delivery checkpoint preserves correction budget/evidence. No tool dispatch from selector. Human-readable explanation accompanies machine-readable JSON check/next output; CLI read-only selection by default.

## Acceptance and live demonstration

1. Validate real versioned roadmap/task specs; duplicate/missing/self/cyclic edges, invalid states/evidence, ownership overlap fail. Tests positive/negative, deterministic permutation ordering, independent blocked tasks, merged vs draft/unmerged/research evidence, stale plan and SHA, authorization, replay/resume.
2. Explain current original milestone components and remaining Milestones 2–5 gaps; no sample graph masquerades as roadmap.
3. Run uv run --locked pytest, inspect scope/diff, commit/push normal and create exactly one focused draft PR after checking branch PR existence. Link via T3, return head/worktree/tests/CLI examples automatically. No merge, ready, watches or delegates from Builder.
4. Coordinator verifies CI and fresh exact-head Ubuntu read-only review; corrections max two. Execute real-roadmap selection/checkpoint resume demonstration and save its JSON outputs. Initial PC1 Program-to-Delivery task handoff is a real native Builder dispatch with persisted intent, not retroactively claimed as selection by code that did not exist. Once helper exists, reconcile that active delivery and demonstrate it resumes instead of creating another. If demonstrating another approved runnable task is necessary, use only a legitimate bounded task within PC1; no dummy work or unapproved future milestone.
5. Final evidence distinguishes unit fixtures, actual native execution and untested remote crashes/watch paths. No new milestones automatically authorized.
