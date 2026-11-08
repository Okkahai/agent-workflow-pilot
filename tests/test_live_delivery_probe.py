"""Regression for recollecting checkpoint evidence after a delivery correction."""

import pytest

from agent_workflow_pilot.controller.checkpoint import apply, load, new, save


def test_live_delivery_probe_rejects_stale_evidence_after_new_head(tmp_path):
    old_head, new_head = 'a' * 40, 'b' * 40
    state = new('live-delivery-probe', ['fresh CI and review required'])
    state = apply(state, 'dispatch', 'dispatch', client_request_id='probe', completed_dependencies=[])
    state = apply(state, 'started', 'started', refs={'task': 'probe-task', 'thread': 'probe-thread'})
    state = apply(state, 'old-head', 'head', head=old_head)
    state = apply(state, 'old-ci', 'ci', head=old_head, ref='checks/old')
    state = apply(state, 'old-review', 'review', head=old_head, ref='reviews/old')
    assert state['lifecycle'] == 'complete'

    state = apply(state, 'new-head', 'head', head=new_head)
    path = tmp_path / 'checkpoint.json'
    save(path, state)
    state = load(path)
    assert state['head'] == new_head
    assert state['ci'] is None and state['review'] is None
    assert state['lifecycle'] == 'awaiting_ci'

    for action in ('ci', 'review'):
        # Replayed receipts must not restore evidence invalidated by the new head.
        assert apply(state, f'old-{action}', action, head=old_head,
                     ref='checks/old' if action == 'ci' else 'reviews/old') == state
        with pytest.raises(ValueError, match='stale evidence'):
            apply(state, f'stale-{action}', action, head=old_head, ref='stale')
        assert f'stale-{action}' not in state['events']
        assert state[action] is None
        state = apply(state, f'fresh-{action}', action, head=new_head, ref=f'fresh/{action}')

    assert state['lifecycle'] == 'complete'
    assert state['ci']['head'] == state['review']['head'] == new_head
