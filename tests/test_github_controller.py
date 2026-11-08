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
        if path.endswith('/check-suites'):
            return [{'total_count': 0, 'check_suites': []}]
        if path.endswith('/check-runs'):
            if checks is None:
                return [{'total_count': 0, 'check_runs': []}]
            return checks
        return statuses if statuses is not None else [{'sha': SHA, 'total_count': 0, 'statuses': []}]
    return get

def test_valid_metadata_is_blocked_without_review_and_protections():
    result = collect('owner/repo', 7, client([{'total_count': 1, 'check_runs': [{'id': 1, 'name': 'test', 'status': 'completed', 'conclusion': 'success', 'head_sha': SHA}]}]))
    assert result['pr']['head_sha'] == SHA
    assert result['pr']['base_sha'] == BASE
    assert result['observed_ci'] == 'success'
    assert result['evidence']['ci'] == 'unknown'
    assert result['evidence']['independent'] is None
    assert not result['eligible'] and result['blockers']

@pytest.mark.parametrize('status,conclusion,expected', [('completed', 'failure', 'failure'), ('in_progress', None, 'pending')])
def test_unsuccessful_ci(status, conclusion, expected):
    checks = [{'total_count': 1, 'check_runs': [{'id': 1, 'name': 'test', 'status': status, 'conclusion': conclusion, 'head_sha': SHA}]}]
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


def successful_run(ident=1):
    return {'id': ident, 'name': 'test', 'status': 'completed', 'conclusion': 'success', 'head_sha': SHA}


def test_truncated_check_runs_are_not_success():
    result = collect('owner/repo', 7, client([{'total_count': 2, 'check_runs': [successful_run()]}]))
    assert result['observed_ci'] == 'unknown' and result['errors'] and not result['eligible']


@pytest.mark.parametrize('count', [None, -1, True, '1'])
def test_bad_check_count(count):
    result = collect('owner/repo', 7, client([{'total_count': count, 'check_runs': [successful_run()]}]))
    assert result['observed_ci'] == 'unknown' and result['errors']


def test_paginated_check_runs():
    pages = [{'total_count': 2, 'check_runs': [successful_run(1)]},
             {'total_count': 2, 'check_runs': [successful_run(2)]}]
    result = collect('owner/repo', 7, client(pages))
    assert result['observed_ci'] == 'success' and len(result['checks']) == 2


def test_inconsistent_check_counts():
    pages = [{'total_count': 2, 'check_runs': [successful_run(1)]},
             {'total_count': 3, 'check_runs': [successful_run(2)]}]
    result = collect('owner/repo', 7, client(pages))
    assert result['observed_ci'] == 'unknown' and result['errors']


def test_truncated_check_page():
    pages = [{'total_count': 3, 'check_runs': [successful_run(1)]},
             {'total_count': 3, 'check_runs': [successful_run(2)]}]
    result = collect('owner/repo', 7, client(pages))
    assert result['observed_ci'] == 'unknown' and result['errors']


@pytest.mark.parametrize('sha', [None, 'bad', 'b' * 40])
def test_status_sha_must_match(sha):
    statuses = [{'sha': sha, 'total_count': 1, 'statuses': [{'context': 'ci', 'state': 'success'}]}]
    result = collect('owner/repo', 7, client(statuses=statuses))
    assert result['observed_ci'] == 'unknown' and result['errors']


def test_status_sha_checked_on_every_page():
    statuses = [{'sha': SHA, 'total_count': 2, 'statuses': [{'id': 1, 'context': 'a', 'state': 'success'}]},
                {'sha': BASE, 'total_count': 2, 'statuses': [{'id': 2, 'context': 'b', 'state': 'success'}]}]
    result = collect('owner/repo', 7, client(statuses=statuses))
    assert result['observed_ci'] == 'unknown' and result['errors']


def test_suite_limit_blocks_observation():
    base = client([{'total_count': 1, 'check_runs': [successful_run()]}])
    def api(path):
        if path.endswith('/check-suites'):
            return [{'total_count': 1001, 'check_suites': []}]
        return base(path)
    result = collect('owner/repo', 7, api)
    assert result['observed_ci'] == 'unknown' and result['errors'] and not result['eligible']


def test_matching_status_shas_on_multiple_pages():
    statuses = [{'sha': SHA, 'total_count': 2, 'statuses': [{'id': 1, 'context': 'a', 'state': 'success'}]},
                {'sha': SHA, 'total_count': 2, 'statuses': [{'id': 2, 'context': 'b', 'state': 'success'}]}]
    result = collect('owner/repo', 7, client(statuses=statuses))
    assert result['observed_ci'] == 'success' and not result['eligible']


def test_duplicate_check_run_ids_rejected():
    pages = [{'total_count': 2, 'check_runs': [successful_run()]},
             {'total_count': 2, 'check_runs': [successful_run()]}]
    result = collect('owner/repo', 7, client(pages))
    assert result['observed_ci'] == 'unknown' and result['errors']


def status_record(ident=1, context='ci', state='success'):
    return {'id': ident, 'context': context, 'state': state}


def status_pages(*records):
    return [{'sha': SHA, 'total_count': len(records), 'statuses': [record]} for record in records]


def test_duplicate_status_id_across_pages_blocks():
    result = collect('owner/repo', 7, client(statuses=status_pages(status_record(), status_record())))
    assert result['observed_ci'] == 'unknown' and not result['eligible']
    assert any('status' in error.lower() and 'id' in error.lower() for error in result['errors'])


def test_duplicate_status_id_with_contradictory_state_blocks():
    result = collect('owner/repo', 7, client(statuses=status_pages(status_record(), status_record(state='failure'))))
    assert result['observed_ci'] == 'unknown' and result['errors']


@pytest.mark.parametrize('ident', [None, 0, -1, True, '12', 1.2])
def test_invalid_status_identity_blocks(ident):
    result = collect('owner/repo', 7, client(statuses=status_pages(status_record(ident))))
    assert result['observed_ci'] == 'unknown' and result['errors'] and not result['eligible']


def test_distinct_status_ids_same_context_are_not_duplicates():
    result = collect('owner/repo', 7, client(statuses=status_pages(status_record(1), status_record(2))))
    assert result['observed_ci'] == 'success' and not result['errors'] and not result['eligible']


def test_distinct_status_updates_same_context_are_conservative():
    result = collect('owner/repo', 7, client(statuses=status_pages(status_record(1), status_record(2, state='failure'))))
    assert result['observed_ci'] == 'failure' and not result['errors']


def test_malformed_status_record_blocks():
    result = collect('owner/repo', 7, client(statuses=status_pages({'id': 1, 'context': 'ci', 'state': 'unknown'})))
    assert result['observed_ci'] == 'unknown' and result['errors']


def test_absent_status_id_blocks():
    result = collect('owner/repo', 7, client(statuses=status_pages({'context': 'ci', 'state': 'success'})))
    assert result['observed_ci'] == 'unknown' and result['errors'] and not result['eligible']
