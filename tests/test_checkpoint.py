import pytest
from agent_workflow_pilot.controller.checkpoint import apply, new, save, load

A, B = 'a' * 40, 'b' * 40


def building():
    s = new('task', ['tests pass'], ['dependency'])
    s = apply(s, 'dispatch', 'dispatch', client_request_id='request-1', completed_dependencies=['dependency'])
    return apply(s, 'started', 'started', refs={'task': 'native-task', 'thread': 'native-thread'})


def test_lifecycle_replay_and_new_head(tmp_path):
    s = building()
    s = apply(s, 'head', 'head', head=A)
    s = apply(s, 'ci', 'ci', head=A, ref='github/check/1')
    s = apply(s, 'review', 'review', head=A, ref='t3/review/1')
    assert s['lifecycle'] == 'complete'
    s = apply(s, 'report', 'report')
    assert s['lifecycle'] == 'awaiting_authorization'
    path = tmp_path / 'checkpoint.json'
    save(path, s)
    assert load(path) == s
    assert apply(load(path), 'ci', 'ci', head=A, ref='github/check/1') == s
    with pytest.raises(ValueError, match='reused'):
        apply(s, 'ci', 'ci', head=B, ref='github/check/1')
    s = apply(s, 'new-head', 'head', head=B)
    assert s['ci'] is None and s['review'] is None
    assert s['lifecycle'] == 'awaiting_ci'
    with pytest.raises(ValueError, match='stale'):
        apply(s, 'old-ci', 'ci', head=A, ref='old')
    s = apply(s, 'new-ci', 'ci', head=B, ref='new')
    with pytest.raises(ValueError, match='stale'):
        apply(s, 'old-review', 'review', head=A, ref='old')


def test_dependencies_and_transition_fail_closed():
    s = new('task', ['test'], ['dep'])
    with pytest.raises(ValueError, match='dependencies'):
        apply(s, 'd', 'dispatch', client_request_id='r', completed_dependencies=[])
    with pytest.raises(ValueError, match='transition'):
        apply(s, 'r', 'report')
    assert s['events'] == {}


def test_bounded_corrections_and_replay():
    s = apply(building(), 'h0', 'head', head=A)
    for i in range(2):
        s = apply(s, f'c{i}', 'correction', reason='failed CI')
        assert apply(s, f'c{i}', 'correction', reason='failed CI') == s
        s = apply(s, f'd{i}', 'dispatch', client_request_id=f'r{i}', completed_dependencies=['dependency'])
        s = apply(s, f's{i}', 'started', refs={'task': f't{i}', 'thread': f'th{i}'})
        s = apply(s, f'h{i+1}', 'head', head=B if i == 0 else A)
    s = apply(s, 'exhaust', 'correction', reason='findings')
    assert s['retries'] == 2 and s['lifecycle'] == 'blocked'
    s = apply(s, 'recover', 'reconcile', refs={'pr': 'github/pr/1'}, head=B)
    assert s['retries'] == 2 and s['ci'] is None
    assert apply(s, 'still-exhausted', 'correction', reason='failure')['lifecycle'] == 'blocked'


def test_crash_recovery_requires_recollection(tmp_path, monkeypatch):
    s = building()
    path = tmp_path / 'state.json'
    save(path, s)
    def fail(*args):
        raise OSError('replace interrupted')
    monkeypatch.setattr('agent_workflow_pilot.controller.checkpoint.os.replace', fail)
    with pytest.raises(OSError):
        save(path, apply(s, 'h', 'head', head=A))
    assert load(path) == s
    assert list(tmp_path.iterdir()) == [path]
    s = apply(s, 'ambiguous', 'block', reason='dispatch outcome unknown')
    assert s['lifecycle'] == 'blocked'
    s = apply(s, 'reconciled', 'reconcile', refs={'task': 'existing', 'pr': 'existing-pr'}, head=A)
    assert s['lifecycle'] == 'awaiting_ci' and s['review'] is None


@pytest.mark.parametrize('raw', ['{}', '{"version":1,"version":1}', 'NaN'])
def test_corrupt_resume(tmp_path, raw):
    path = tmp_path / 'state.json'
    path.write_text(raw)
    with pytest.raises(ValueError):
        load(path)


def test_same_head_correction_recollects():
    s = apply(building(), 'h', 'head', head=A)
    s = apply(s, 'c', 'correction', reason='transient failure')
    s = apply(s, 'd', 'dispatch', client_request_id='retry', completed_dependencies=['dependency'])
    s = apply(s, 's', 'started', refs={'task': 'retry', 'thread': 'retry'})
    s = apply(s, 'h2', 'head', head=A)
    assert s['lifecycle'] == 'awaiting_ci'
