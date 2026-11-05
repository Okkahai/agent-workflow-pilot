# Engineering harness plan

1. Inspect repository, PR1, classic protection and applicable rulesets.
2. Add provider-independent standard, evidence contract and fail-closed decision gate; exercise negative cases and real isolated Git repositories.
3. Run locked pytest, record evidence, push focused PR. Parent independently reviews current head and merges only after all gates pass.

Ruling: no automatic merge side effect in this implementation task; reusable gate emits eligibility only. Delivery controller performs a fresh evidence collection and normal SHA-bound merge. No new dependencies or CI changes.
