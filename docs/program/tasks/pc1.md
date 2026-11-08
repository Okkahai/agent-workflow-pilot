# Program selection and recovery

Approved docs/plans/program-coordinator-m1.md supersedes design pending decisions. Current native Builder delivery already dispatched by controller.

Scope: Program selection and recovery.
Acceptance: controller verifies the stated outcome against current native records and reviewed scope.
Ownership: src/agent_workflow_pilot/controller/program.py, tests/test_program.py, docs/program/
Routing: bounded implementation worker; independent review belongs to controller.
Risk: stale evidence must not promote completion.
Exclusions: permissions, services, dependencies, scheduler, merge and unrelated repositories.
Completion: verified merged target-branch implementation; draft/report-ready is insufficient.
Authorization: PC1 implementation and draft PR only; acceptance is the committed M1 plan, including focused negative tests and replay demonstration.
