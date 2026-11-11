# A2 — Arbitrary milestone identifiers

Approved 2026-11-10 by the current user instruction, only through draft-delivery readiness.
Baseline main: b013c82c2773607ea320709920dfe6680f14ff39. A1 is delivered; PR14 is excluded.

## Scope and ownership

One isolated Builder owns controller/program.py, tests/test_program.py, narrowly necessary
tests/test_identity.py coverage, docs/program/README.md, docs/program/roadmap.json,
docs/program/tasks/a2.md, this plan, and the PORT-02 status in the canonical gap register.
Read the actual Universal Contract, corrected migration proposal and Sol critique first.
Preserve all 26 gap IDs and the three accepted A1 P3 limitations.

Replace only the M1–M5 allowlist with a bounded ASCII identifier grammar. Prefer a
letter-led identifier with letters/digits and narrowly allowed internal hyphens/underscores,
maximum 64 characters. Decide and document the exact grammar after inspecting existing
validators. No normalization, paths, whitespace, controls, Unicode ambiguity or schema v2.
Milestones are metadata, never authority. Fingerprint code and canonical serialization
must remain unchanged. Do not rewrite historical state, retry counts, receipts or task IDs.

## Acceptance and negative matrix

1. M1–M5 and independent-project names, mixed names and shared milestones validate.
2. Empty/non-string/oversized/path/control/Unicode/invalid punctuation fail through validate.
3. Pin baseline fingerprints and historical fixtures; no hashes change for unchanged inputs.
4. Changed milestone invalidates observations, binding hashes and A1 approval expectations.
5. Selection/DAG/replay/PC1–PC3/M1/routing/A1 remain compatible; valid names never approve
   an unapproved task or grant dispatch/merge authority. Rollback preserves uncertain state.

## Delivery

Register a2 only, approved for implementation, depending on verified delivered a1.
No other roadmap approvals change. Run focused tests first, then uv run --locked pytest.
Record actual counts and skips, fresh-process compatibility evidence and final head.
Create/link one Draft PR, no ready/merge. Independent opposite-provider exact-head review
and required CI are controller work. Correction budget: 2; no duplicate task/PR/writer.

No A3/B/C/D/E, adoption, registry, distribution, routing changes or A1 P3 fixes.
Preserve local Coordinator routing audit/policy changes outside this PR.
