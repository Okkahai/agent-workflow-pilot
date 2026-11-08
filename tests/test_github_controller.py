import pytest
from agent_workflow_pilot.controller.github import collect

SHA = 'a' * 40
BASE = 'b' * 40

def pr(sha=SHA):
    return {'number': 7, 'state': 'open', 'draft': False,
            'head': {'sha': sha}, 'base': {'sha': BASE, 'ref': 'main'}}

def client(checks=None, statuses=None, last=None):
    calls = []
    def get(path):
        calls.append(path)
        if '/pulls/' in path:
            return (last or pr()) if sum('/pulls/' in x for x in calls) == 2 else pr()
        if path.endswith('/check-runs'):
            return checks if checks is not None else [{'check_runs': []}]
        return statuses if statuses is not None else [{'statuses': []}]
    return get

def test_valid_metadata_is_blocked_without_review_and_protections():
    result = collect('owner/repo', 7, client([{'check_runs': [{'name': 'test', 'status': 'completed', 'conclusion': 'success', 'head_sha': SHA}]}]))
    assert result['pr']['head_sha'] == SHA
    assert result['pr']['base_sha'] == BASE
    assert result['observed_ci'] == 'success'
    assert result['evidence']['ci'] == 'unknown'
    assert result['evidence']['independent'] is None
    assert not result['eligible'] and result['blockers']

@pytest.mark.parametrize('status,conclusion,expected', [('completed', 'failure', 'failure'), ('in_progress', None, 'pending')])
def test_unsuccessful_ci(status, conclusion, expected):
    checks = [{'check_runs': [{'name': 'test', 'status': status, 'conclusion': conclusion, 'head_sha': SHA}]}]
    assert collect('owner/repo', 7, client(checks))['observed_ci'] == expected

def test_missing_ci():
    assert collect('owner/repo', 7, client())['observed_ci'] == 'unknown'

def test_api_error_fails_closed():
    def fail(path): raise RuntimeError('unavailable')
    result = collect('owner/repo', 7, fail)
    assert not result['eligible'] and result['errors']

def test_head_changed():
    result = collect('owner/repo', 7, client(last=pr('c' * 40)))
    assert not result['eligible'] and result['evidence']['head'] is None
    assert result['errors']

@pytest.mark.parametrize('repo,number', [('bad', 7), ('owner/repo', 0), ('owner/repo', True), ('../repo', 7)])
def test_invalid_input(repo, number):
    result = collect(repo, number, client())
    assert not result['eligible'] and result['errors']

def test_incomplete_metadata():
    result = collect('owner/repo', 7, lambda path: {})
    assert not result['eligible'] and result['errors']
