import pytest
from agent_workflow_pilot.gate import blockers


def valid():
    return dict(head='abc', ci_head='abc', ci='success', review_head='abc',
                independent=True, review_evidence='review artifact', findings=[],
                protections_verified=True, permissions_verified=True,
                protections_satisfied=True, up_to_date=True, bypass=False)


@pytest.mark.parametrize('field,value', [
    ('ci', 'failure'), ('ci', 'pending'), ('ci_head', 'old'),
    ('review_head', 'old'), ('independent', False), ('review_evidence', ''),
    ('findings', ['fix missing validation']), ('protections_verified', False),
    ('permissions_verified', False), ('protections_satisfied', False),
    ('up_to_date', False), ('bypass', True), ('head', '')])
def test_blocks_unsafe_merge(field, value):
    evidence = valid()
    evidence[field] = value
    assert blockers(evidence)


def test_missing_evidence_blocks():
    assert blockers({})


def test_corrected_findings_require_fresh_review():
    evidence = valid()
    evidence.update(head='fixed', ci_head='fixed', findings=[])
    assert blockers(evidence)
    evidence['review_head'] = 'fixed'
    assert blockers(evidence) == []
