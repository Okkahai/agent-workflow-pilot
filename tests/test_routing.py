"""Routing policy, attempt provenance and review validation. All fixtures are mocked policy
inputs or real local files; none is live T3/provider behavior."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from agent_workflow_pilot import routing, task_context as tc
from agent_workflow_pilot.controller import checkpoint, program

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / 'harness/policies/routing-v1.json'
POLICY = json.loads(POLICY_PATH.read_text())
HEAD, HEAD2 = 'a' * 40, 'b' * 40
NOW = '2026-11-09T12:00:00+00:00'
PR = 'https://github.com/owner/repo/pull/1'
BRANCH = 'agent/routing'
H_PLAN, H_CTX = '1' * 64, '2' * 64
SCOPE = routing.scope_sha256(['approved scope', 'acceptance'])
EFFORTS = ['low', 'medium', 'high', 'max']


def snapshot(**broken):
    prov = lambda *models: dict(enabled=True, child_tasks=True, cross_provider=True,
                                models={m: dict(efforts=list(EFFORTS)) for m in models})
    snap = dict(observed_at=NOW, source_ref='fixture:capabilities', providers=dict(
        codex=prov('gpt-6.1-sol', 'gpt-6.1-terra'),
        claudeAgent=prov('claude-sonnet-5-5', 'claude-haiku-5-5'), grok=dict(enabled=False)))
    for dotted, value in broken.items():
        node = snap
        *path, last = dotted.split('__')
        for part in path:
            node = node[part]
        if value is DELETE:
            del node[last]
        else:
            node[last] = value
    return snap


DELETE = object()


def classification(category='standard', **over):
    return dict(category=category, complexity='standard', architecture_risk='low',
                security_risk='none', required_capabilities=['child_tasks'], context='fixture',
                budget=dict(max_attempts=2), verification_cost='medium') | over


def request(category='standard', usage=(), snap=None, **over):
    return dict(project='proj-a', repo='owner/repo', task='dynamic-routing', attempt='att-1',
                head=HEAD, now=NOW, classification=classification(category),
                snapshot=snap or snapshot(), usage=list(usage),
                metrics=dict(tokens=None, elapsed_seconds=None, attempts=None)) | over


def obs(provider, window, pct, **over):
    return dict(provider=provider, project='proj-a', window=window, remaining_percent=pct,
                observed_at=NOW, source_ref='fixture:measured', basis='measured') | over


def both(provider, session, weekly=None):
    return [obs(provider, 'session', session), obs(provider, 'weekly', session if weekly is None else weekly)]


def target(decision):
    return decision['route']['target'] if decision['decision'] == 'route' else None


# ---------- policy ----------

def test_policy_valid_and_stable():
    sha = routing.validate_policy(POLICY)
    assert sha == routing.load_policy(POLICY_PATH)[1] == routing.validate_policy(copy.deepcopy(POLICY))


def test_policy_has_no_project_ids_or_paths():
    text = POLICY_PATH.read_text()
    for banned in ('Okkahai', 'm1-', 'm2-', 'C:\\', '/home', 'environmentId'):
        assert banned not in text


def mutate(fn):
    doc = copy.deepcopy(POLICY)
    fn(doc)
    return doc


@pytest.mark.parametrize('fn', [
    lambda d: d['targets']['sonnet'].update(model='claude-opus-5-5'),
    lambda d: d['targets']['sol'].update(model='gpt-6-astra'),
    lambda d: d['targets']['sonnet'].update(effort='high'),
    lambda d: d['targets']['sol'].update(effort='max'),
    lambda d: d['providers']['codex'].update(effort_option='serviceTier'),
    lambda d: d['usage']['reserve']['claudeAgent'].update(enforced=True),
    lambda d: d['roles']['program_delivery'].update(alternates=['sonnet'], auto_switch=['sonnet']),
    lambda d: d['roles']['docs'].update(auto_switch=['haiku']),
    lambda d: d['roles']['docs'].update(alternates=['haiku', 'haiku']),
    lambda d: d['roles']['planning_builder'].update(auto_switch=['haiku']),
    lambda d: d['targets']['sol'].update(provider='missing'),
    lambda d: d['categories'].pop('docs'),
    lambda d: d['categories'].update(docs='nope'),
    lambda d: d['usage'].update(conserve_min=40),
    lambda d: d.update(schema='x'),
    lambda d: d.update(version=True),
    lambda d: d.update(extra=1),
    lambda d: d.update(max_attempts='3'),
    lambda d: d['capabilities'].append('network'),
])
def test_policy_rejects(fn):
    with pytest.raises(ValueError):
        routing.validate_policy(mutate(fn))


def test_policy_version_is_content_addressed():
    assert routing.validate_policy(mutate(lambda d: d['usage'].update(fresh_seconds=901))) \
        != routing.validate_policy(POLICY)


# ---------- decide: roles, options, capability matching ----------

@pytest.mark.parametrize('category,name,provider,model,options', [
    ('program', 'sol', 'codex', 'gpt-6.1-sol', {'reasoningEffort': 'medium'}),
    ('delivery', 'sol', 'codex', 'gpt-6.1-sol', {'reasoningEffort': 'medium'}),
    ('planning', 'sonnet', 'claudeAgent', 'claude-sonnet-5-5', {'effort': 'medium'}),
    ('architecture', 'sonnet', 'claudeAgent', 'claude-sonnet-5-5', {'effort': 'medium'}),
    ('standard', 'sonnet', 'claudeAgent', 'claude-sonnet-5-5', {'effort': 'medium'}),
    ('complex', 'sonnet', 'claudeAgent', 'claude-sonnet-5-5', {'effort': 'medium'}),
    ('bugfix', 'sol', 'codex', 'gpt-6.1-sol', {'reasoningEffort': 'medium'}),
    ('mechanical', 'terra', 'codex', 'gpt-6.1-terra', {'reasoningEffort': 'low'}),
    ('docs', 'terra', 'codex', 'gpt-6.1-terra', {'reasoningEffort': 'low'}),
])
def test_primary_route(category, name, provider, model, options):
    d = routing.decide(POLICY, request(category))
    assert d['decision'] == 'route' and d['fallback'] is None and d['authorizes'] is False
    assert d['route'] == dict(target=name, provider=provider, model=model,
                              effort=options.popitem()[1], options=d['route']['options'])
    assert d['route']['options'] == {('reasoningEffort' if provider == 'codex' else 'effort'): d['route']['effort']}


def test_deterministic_and_input_not_mutated():
    req = request()
    before = copy.deepcopy(req)
    assert routing.decide(POLICY, req) == routing.decide(POLICY, copy.deepcopy(req))
    assert req == before


def test_risk_complexity_budget_never_change_cost():
    hot = request(classification=classification('complex', complexity='high',
                  architecture_risk='high', security_risk='high', verification_cost='high'))
    d = routing.decide(POLICY, hot)
    assert d['route']['effort'] == 'medium' and d['route']['target'] == 'sonnet'


@pytest.mark.parametrize('broken,category,expected', [
    ({'providers__claudeAgent__models__claude-sonnet-5-5': DELETE}, 'standard', 'sol'),
    ({'providers__claudeAgent__enabled': False}, 'standard', 'sol'),
    ({'providers__claudeAgent__models__claude-sonnet-5-5__efforts': ['low', 'high']}, 'complex', 'sol'),
    ({'providers__claudeAgent__child_tasks': False}, 'standard', 'sol'),
    ({'providers__codex__models__gpt-6.1-sol': DELETE}, 'bugfix', 'sonnet'),
    ({'providers__codex__enabled': False}, 'bugfix', 'sonnet'),
])
def test_sonnet_sol_automatic_fallback(broken, category, expected):
    d = routing.decide(POLICY, request(category, snap=snapshot(**broken)))
    assert d['decision'] == 'route' and target(d) == expected
    assert d['fallback']['requires'] and d['fallback']['reasons']


def test_fallback_target_must_also_match_ids():
    snap = snapshot(**{'providers__claudeAgent__enabled': False,
                       'providers__codex__models__gpt-6.1-sol__efforts': ['low']})
    d = routing.decide(POLICY, request('standard', snap=snap))
    assert d['decision'] == 'stop' and 'effort_missing' in d['reasons']


@pytest.mark.parametrize('category,broken', [
    ('program', {'providers__codex__models__gpt-6.1-sol': DELETE}),
    ('delivery', {'providers__codex__enabled': False}),
    ('mechanical', {'providers__codex__models__gpt-6.1-terra': DELETE}),
])
def test_no_switch_roles_stop(category, broken):
    d = routing.decide(POLICY, request(category, snap=snapshot(**broken)))
    assert d['decision'] == 'stop' and d['reasons']


def test_docs_haiku_is_candidate_not_automatic():
    d = routing.decide(POLICY, request('docs', snap=snapshot(
        **{'providers__codex__models__gpt-6.1-terra': DELETE})))
    assert d['decision'] == 'candidate' and 'route' not in d
    assert [c['target'] for c in d['candidates']] == ['haiku'] and d['requires'] == 'caller choice'


def test_missing_provider_and_required_capability():
    snap = snapshot(**{'providers__codex__cross_provider': False})
    d = routing.decide(POLICY, request('program', snap=snap,
                       classification=classification('program', required_capabilities=['cross_provider'])))
    assert d['decision'] == 'stop' and 'capability_missing:cross_provider' in d['reasons']
    snap = snapshot(**{'providers__codex': DELETE})
    assert 'provider_missing' in routing.decide(POLICY, request('program', snap=snap))['reasons']


def test_no_forbidden_escalation_ever_offered():
    snap = snapshot(**{'providers__codex': DELETE, 'providers__claudeAgent': DELETE})
    d = routing.decide(POLICY, request('complex', snap=snap))
    assert d['decision'] == 'stop' and 'route' not in d and 'candidates' not in d


def test_stale_and_future_snapshots_stop():
    for stamp in ('2026-11-09T10:59:59+00:00', '2026-11-09T12:02:00+00:00'):
        d = routing.decide(POLICY, request(snap=snapshot(observed_at=stamp)))
        assert d['decision'] == 'stop' and d['reasons'] == ['stale_capabilities']
    assert routing.decide(POLICY, request(snap=snapshot(observed_at='2026-11-09T11:00:00+00:00')))['decision'] == 'route'


@pytest.mark.parametrize('over', [
    {'classification': classification(category='emergency')},
    {'classification': classification(effort='high')},
    {'classification': classification(complexity='extreme')},
    {'classification': classification(required_capabilities=['network'])},
    {'classification': classification(required_capabilities=['child_tasks', 'child_tasks'])},
    {'classification': classification(budget=dict(max_attempts=True))},
    {'classification': classification(budget=dict(max_attempts=99))},
    {'classification': classification(context='')},
    {'project': 'bad project'}, {'repo': 'noslash'}, {'task': ''}, {'attempt': 7},
    {'head': 'abc'}, {'now': '2026-11-09T12:00:00'}, {'now': 5},
    {'metrics': dict(tokens=-1, elapsed_seconds=None, attempts=None)},
    {'metrics': dict(tokens=True, elapsed_seconds=None, attempts=None)},
    {'approved': True}, {'usage': 'none'},
])
def test_invalid_request_rejected(over):
    with pytest.raises(ValueError):
        routing.decide(POLICY, request() | over)


def test_missing_request_field_rejected():
    req = request()
    del req['attempt']
    with pytest.raises(ValueError):
        routing.decide(POLICY, req)


def test_bad_snapshot_types():
    for snap in (snapshot(providers__codex__enabled='yes'), snapshot(providers__codex__models='x'),
                 snapshot(providers__codex__models__x=dict(efforts='low')), snapshot(observed_at='x')):
        with pytest.raises(ValueError):
            routing.decide(POLICY, request(snap=snap))


# ---------- usage ----------

def level(pct, provider='claudeAgent', window='session'):
    return routing.decide(POLICY, request(usage=[obs(provider, window, pct)]))['usage'][provider]


@pytest.mark.parametrize('pct,expected', [
    (100, 'normal'), (35.01, 'normal'), (35, 'conserve'), (20, 'conserve'), (15, 'conserve'),
    (14.99, 'restrict'), (1, 'restrict'), (0, 'exhausted'),
])
def test_threshold_edges(pct, expected):
    assert level(pct)['level'] == expected


def test_unknown_stays_unknown_and_partial_is_flagged():
    d = routing.decide(POLICY, request())
    assert all(v['level'] == 'unknown' and v['worst'] is None and not v['complete'] for v in d['usage'].values())
    one = level(80)
    assert one['level'] == 'normal' and one['complete'] is False and 'partial_window_knowledge' in one['advisory']


def test_worst_known_window_wins_and_complete_flag():
    u = routing.decide(POLICY, request(usage=both('claudeAgent', 90, 30)))['usage']['claudeAgent']
    assert u['level'] == 'conserve' and u['worst'] == 30 and u['complete'] is True
    assert routing.decide(POLICY, request(usage=both('claudeAgent', 90, 0)))['usage']['claudeAgent']['level'] == 'exhausted'


@pytest.mark.parametrize('over,reason', [
    ({'basis': 'user_estimate'}, 'not_measured'), ({'basis': 'cached_display'}, 'not_measured'),
    ({'basis': 'unsupported', 'remaining_percent': None}, 'not_measured'),
    ({'project': 'proj-b'}, 'wrong_project'),
    ({'observed_at': '2026-11-09T11:44:59+00:00'}, 'stale'),
    ({'observed_at': '2026-11-09T12:05:00+00:00'}, 'stale'),
])
def test_untrusted_telemetry_cannot_masquerade(over, reason):
    u = routing.decide(POLICY, request(usage=[obs('claudeAgent', 'session', 0) | over]))['usage']['claudeAgent']
    assert u['level'] == 'unknown' and u['windows']['session'] is None
    assert f'session:{reason}' in u['untrusted']


def test_ambiguous_duplicate_window_is_unknown():
    u = routing.decide(POLICY, request(usage=[obs('claudeAgent', 'session', 90), obs('claudeAgent', 'session', 5)]))
    assert u['usage']['claudeAgent']['level'] == 'unknown' and 'session:ambiguous' in u['usage']['claudeAgent']['untrusted']


@pytest.mark.parametrize('bad', [
    obs('claudeAgent', 'session', True), obs('claudeAgent', 'session', '50'),
    obs('claudeAgent', 'session', 101), obs('claudeAgent', 'session', -1),
    obs('claudeAgent', 'session', None), obs('claudeAgent', 'daily', 50),
    obs('grok', 'session', 50), obs('claudeAgent', 'session', 50, source_ref=''),
    obs('claudeAgent', 'session', 50, observed_at='yesterday'),
    obs('claudeAgent', 'session', 50) | {'dollars': 3},
])
def test_invalid_observation_rejected(bad):
    with pytest.raises(ValueError):
        routing.decide(POLICY, request(usage=[bad]))


def test_reserve_is_advisory_only():
    d = routing.decide(POLICY, request(usage=both('claudeAgent', 20)))
    assert 'reserve_advisory_not_enforced' in d['usage']['claudeAgent']['advisory']
    assert d['decision'] == 'route' and target(d) == 'sonnet'
    assert 'reserve_advisory_not_enforced' not in routing.decide(
        POLICY, request(usage=both('claudeAgent', 21)))['usage']['claudeAgent']['advisory']
    assert not routing.decide(POLICY, request(usage=both('codex', 5)))['usage']['codex']['advisory'] == ['reserve']


def test_exhausted_primary_switches_provider_but_unknown_never_does():
    d = routing.decide(POLICY, request(usage=both('claudeAgent', 0)))
    assert target(d) == 'sol' and d['fallback']['reasons'] == ['usage_exhausted']
    assert target(routing.decide(POLICY, request())) == 'sonnet'
    d = routing.decide(POLICY, request(usage=both('claudeAgent', 0) + both('codex', 0)))
    assert d['decision'] == 'stop' and d['reasons'] == ['usage_exhausted']


def test_restricted_blocks_only_heavy_new_work():
    low = request(usage=both('claudeAgent', 10))
    assert target(routing.decide(POLICY, low)) == 'sonnet'
    heavy = low | {'classification': classification(complexity='high')}
    d = routing.decide(POLICY, heavy)
    assert target(d) == 'sol' and d['fallback']['reasons'] == ['usage_restricted_heavy_work']
    both_low = heavy | {'usage': both('claudeAgent', 10) + both('codex', 10)}
    assert routing.decide(POLICY, both_low)['decision'] == 'stop'


def test_program_role_exhausted_stops_without_switch():
    d = routing.decide(POLICY, request('program', usage=both('codex', 0)))
    assert d['decision'] == 'stop' and d['reasons'] == ['usage_exhausted']


def test_metrics_are_separate_from_quota():
    d = routing.decide(POLICY, request(metrics=dict(tokens=10**9, elapsed_seconds=5000, attempts=3)))
    assert d['metrics']['tokens'] == 10**9 and d['usage']['claudeAgent']['level'] == 'unknown'


# ---------- attempts ----------

def expected(**over):
    return dict(project='proj-a', repo='owner/repo', task='dynamic-routing', plan_hash=H_PLAN,
                context_hash=H_CTX, scope_sha256=SCOPE, retry_budget=2, head=HEAD, branch=BRANCH,
                worktree='C:/wt/task', pr=PR) | over


def fresh(**over):
    e = expected()
    return routing.new_record(POLICY, project=e['project'], repo=e['repo'], task=e['task'],
                              plan_hash=e['plan_hash'], context_hash=e['context_hash'],
                              scope_sha256=e['scope_sha256'], retry_budget=2, checkpoint_key='task-key',
                              workspace=dict(branch=BRANCH, worktree='C:/wt/task', pr=PR)) | over


def cp(head=HEAD, pr=PR, branch=BRANCH, key='task-key', budget=2):
    s = checkpoint.new(key, ['pytest'], retry_budget=budget)
    s = checkpoint.apply(s, 'e1', 'dispatch', client_request_id='req', completed_dependencies=[])
    s = checkpoint.apply(s, 'e2', 'started', refs={'task': 't', 'thread': 'th', 'branch': branch, 'pr': pr})
    return checkpoint.apply(s, 'e3', 'head', head=head)


def step(rec, event, action, data, exp=None, state=None):
    return routing.apply(rec, POLICY, exp or expected(), event, action, data, state or cp())


def intent(rec, n, target='sonnet', role='planning_builder', **kw):
    return step(rec, f'i{n}', 'intent', dict(attempt=f'att-{n}', role=role, target=target,
                                             client_request_id=f'req-{n}'), **kw)


def started(rec, n, route=None, **kw):
    a = rec['attempts'][-1]
    return step(rec, f's{n}', 'started', dict(attempt=f'att-{n}',
                native=dict(task=f'task-{n}', thread=f'thread-{n}'), returned=route or a['route']), **kw)


def finish(rec, n, outcome='complete', children=(), **kw):
    return step(rec, f't{n}', 'terminal', dict(attempt=f'att-{n}', outcome=outcome, writer='none',
                                               children=list(children)), **kw)


def run(rec, n, target='sonnet', role='planning_builder', route=None):
    rec, out = intent(rec, n, target, role)
    assert out['dispatch_allowed'] is True
    rec, _ = started(rec, n, route)
    return finish(rec, n)[0]


def test_first_intent_started_terminal_flow():
    rec, out = intent(fresh(), 1)
    assert out == dict(dispatch_allowed=True, replay=False, authorizes=False)
    assert rec['attempts'][0]['state'] == 'intent' and rec['attempts'][0]['writer'] == 'unknown'
    rec, out = started(rec, 1)
    assert out['dispatch_allowed'] is False and rec['attempts'][0]['route_match'] is True
    rec, _ = finish(rec, 1)
    a = rec['attempts'][0]
    assert a['state'] == 'terminal' and a['writer'] == 'none' and a['children'] == []


def test_replay_never_grants_dispatch_and_changes_nothing():
    rec, _ = intent(fresh(), 1)
    again, out = intent(rec, 1)
    assert again == rec and out == dict(dispatch_allowed=False, replay=True, authorizes=False)
    with pytest.raises(ValueError, match='reused'):
        step(rec, 'i1', 'intent', dict(attempt='att-2', role='planning_builder', target='sol',
                                       client_request_id='x'))


def test_duplicate_ids_rejected():
    rec = run(fresh(), 1)
    with pytest.raises(ValueError):  # same attempt id, new event
        step(rec, 'other', 'intent', dict(attempt='att-1', role='planning_builder', target='sonnet',
                                          client_request_id='new'))
    with pytest.raises(ValueError):  # same clientRequestId, new attempt id
        step(rec, 'other', 'intent', dict(attempt='att-9', role='planning_builder', target='sonnet',
                                          client_request_id='req-1'))
    again, _ = intent(rec, 2)
    with pytest.raises(ValueError, match='duplicate native'):
        step(again, 'sx', 'started', dict(attempt='att-2', native=dict(task='task-1', thread='thread-9'),
                                          returned=again['attempts'][-1]['route']))


def test_active_attempt_holds_slot_for_every_state():
    rec, _ = intent(fresh(), 1)
    with pytest.raises(ValueError, match='not terminal'):
        intent(rec, 2, 'sol')
    rec, _ = started(rec, 1)
    with pytest.raises(ValueError, match='not terminal'):
        intent(rec, 2, 'sol')


@pytest.mark.parametrize('data', [
    dict(outcome='complete', writer='active', children=[]),
    dict(outcome='complete', writer='unknown', children=[]),
    dict(outcome='complete', writer='none', children=[dict(id='c1', state='running')]),
    dict(outcome='complete', writer='none', children=None),
    dict(outcome='not_dispatched', writer='none', children=[]),
    dict(outcome='bogus', writer='none', children=[]),
])
def test_ambiguous_writer_or_children_cannot_terminate(data):
    rec, _ = started(intent(fresh(), 1)[0], 1)
    with pytest.raises(ValueError):
        step(rec, 't1', 'terminal', dict(attempt='att-1') | data)


def test_terminal_before_started_and_unknown_attempt():
    rec, _ = intent(fresh(), 1)
    with pytest.raises(ValueError, match='reconcile'):
        finish(rec, 1)
    with pytest.raises(ValueError):
        step(rec, 'x', 'started', dict(attempt='att-7', native=dict(task='a', thread='b'),
                                       returned=rec['attempts'][0]['route']))
    with pytest.raises(ValueError):
        step(rec, 'x', 'bogus', dict(attempt='att-1'))
    with pytest.raises(ValueError):
        step(rec, 'x', 'started', dict(attempt='att-1'))


def test_release_unreconciled_intent_only():
    rec, _ = intent(fresh(), 1)
    rec, _ = step(rec, 'r1', 'release', dict(attempt='att-1'))
    assert rec['attempts'][0]['outcome'] == 'not_dispatched'
    rec, _ = intent(rec, 2, 'sol')
    rec, _ = started(rec, 2)
    with pytest.raises(ValueError):
        step(rec, 'r2', 'release', dict(attempt='att-2'))


def test_route_mismatch_is_recorded_and_blocks_review_readiness():
    wrong = dict(provider='codex', model='gpt-6.1-sol', effort='medium')
    rec, _ = intent(fresh(), 1)
    rec, _ = started(rec, 1, wrong)
    assert rec['attempts'][0]['route_match'] is False
    assert any('route' in h for h in routing.recover(rec, POLICY, expected(), cp())['holds'])
    rec, _ = finish(rec, 1)
    out = routing.validate_reviews(rec, POLICY, expected(), [])
    assert out['ready'] is False and any('returned route' in x for x in out['problems'])


def test_safe_sonnet_to_sol_switch_preserves_identity_scope_and_budget():
    rec = run(fresh(), 1)
    rec, out = intent(rec, 2, 'sol')
    assert out['dispatch_allowed'] and rec['attempts'][1]['predecessor'] == 'att-1'
    assert (rec['project'], rec['repo'], rec['task'], rec['scope_sha256'], rec['retry_budget']) == \
        ('proj-a', 'owner/repo', 'dynamic-routing', SCOPE, 2)
    assert rec['attempts'][1]['route'] == dict(provider='codex', model='gpt-6.1-sol', effort='medium')


def test_safe_sol_to_sonnet_switch_for_bugfix_and_same_target_retry():
    rec = run(fresh(), 1, 'sol', 'scoped_bugfix')
    rec, _ = intent(rec, 2, 'sonnet', 'scoped_bugfix')
    rec = finish(started(rec, 2)[0], 2)[0]
    assert routing.recover(rec, POLICY, expected(), cp())['slot'] == 'free'
    rec, _ = intent(rec, 3, 'sonnet', 'scoped_bugfix')  # same-target correction retry


@pytest.mark.parametrize('first,role,second', [
    ('terra', 'mechanical', 'sol'), ('terra', 'docs', 'haiku'), ('sol', 'program_delivery', 'sonnet'),
    ('sonnet', 'planning_builder', 'terra'), ('sonnet', 'planning_builder', 'haiku'),
])
def test_only_sonnet_sol_implementation_switch_is_automatic(first, role, second):
    rec = run(fresh(), 1, first, role)
    with pytest.raises(ValueError, match='switch'):
        intent(rec, 2, second, role)


def test_role_change_cannot_launder_a_switch():
    rec = run(fresh(), 1, 'sonnet', 'planning_builder')
    with pytest.raises(ValueError, match='role'):
        intent(rec, 2, 'sol', 'scoped_bugfix')


@pytest.mark.parametrize('kw,match', [
    (dict(state=cp(head=HEAD2)), 'stale head'),
    (dict(state=cp(pr='https://github.com/owner/repo/pull/2')), 'pr differs'),
    (dict(state=cp(branch='other')), 'branch differs'),
    (dict(state=cp(key='other-task')), 'different task'),
    (dict(state=cp(budget=3)), 'retry budget'),
    (dict(exp=expected(head=HEAD2)), 'stale head'),
    (dict(exp=expected(pr=None)), 'workspace.pr'),
])
def test_switch_requires_fresh_matching_repo_state(kw, match):
    rec = run(fresh(), 1)
    with pytest.raises(ValueError, match=match):
        intent(rec, 2, 'sol', **kw)


def test_blocked_checkpoint_and_exhausted_corrections_hold_slot():
    s = cp()
    s = checkpoint.apply(s, 'c1', 'correction', reason='r')
    s = checkpoint.apply(s, 'c2', 'dispatch', client_request_id='q', completed_dependencies=[])
    s = checkpoint.apply(s, 'c3', 'started', refs={'task': 't', 'thread': 'th'})
    s = checkpoint.apply(s, 'c4', 'head', head=HEAD)
    s = checkpoint.apply(s, 'c5', 'correction', reason='r')
    s = checkpoint.apply(s, 'c6', 'dispatch', client_request_id='q2', completed_dependencies=[])
    s = checkpoint.apply(s, 'c7', 'started', refs={'task': 't', 'thread': 'th'})
    s = checkpoint.apply(s, 'c8', 'head', head=HEAD)
    s = checkpoint.apply(s, 'c9', 'correction', reason='last')
    assert s['lifecycle'] == 'blocked'
    with pytest.raises(ValueError, match='blocked'):
        intent(run(fresh(), 1), 2, 'sol', state=s)


def test_changed_head_clears_ci_review_and_stale_checkpoint_blocks_switch():
    s = cp()
    s = checkpoint.apply(s, 'ci', 'ci', head=HEAD, ref='ci-1')
    s = checkpoint.apply(s, 'rv', 'review', head=HEAD, ref='rv-1')
    s = checkpoint.apply(s, 'h2', 'head', head=HEAD2)
    assert s['ci'] is None and s['review'] is None and s['lifecycle'] == 'awaiting_ci'
    rec = run(fresh(), 1)
    with pytest.raises(ValueError, match='stale head'):  # fresh head observed, checkpoint behind
        intent(rec, 2, 'sol', exp=expected(head=HEAD2))
    intent(rec, 2, 'sol', exp=expected(head=HEAD2), state=s)  # reconciled checkpoint at new head


def test_max_attempts_policy_limit():
    rec = run(run(run(fresh(), 1), 2, 'sol'), 3)
    with pytest.raises(ValueError, match='maximum'):
        intent(rec, 4, 'sol')


def test_intent_requires_checkpoint():
    with pytest.raises(ValueError, match='checkpoint'):
        routing.apply(fresh(), POLICY, expected(), 'i1', 'intent', dict(
            attempt='att-1', role='planning_builder', target='sonnet', client_request_id='r'))


@pytest.mark.parametrize('over', [
    dict(project='proj-b'), dict(repo='other/repo'), dict(task='other-task'),
    dict(plan_hash='3' * 64), dict(context_hash='3' * 64), dict(scope_sha256='3' * 64),
    dict(retry_budget=1), dict(branch='other'), dict(worktree='C:/wt/other'), dict(pr=None),
])
def test_cross_project_stale_and_mismatched_records_fail_closed(over):
    for action_rec in (fresh(), run(fresh(), 1)):
        with pytest.raises(ValueError):
            step(action_rec, 'z1', 'release', dict(attempt='att-1'), exp=expected(**over))
        with pytest.raises(ValueError):
            routing.recover(action_rec, POLICY, expected(**over), cp())
        with pytest.raises(ValueError):
            routing.validate_reviews(action_rec, POLICY, expected(**over), [])


def test_expectation_is_closed_and_typed():
    for bad in (expected() | {'extra': 1}, expected(retry_budget='2'), expected(head='abc'),
                {k: v for k, v in expected().items() if k != 'repo'}):
        with pytest.raises(ValueError):
            routing.recover(fresh(), POLICY, bad, cp())


def test_record_tampering_and_policy_version_change_detected():
    rec = run(fresh(), 1)
    for fn in (lambda r: r['attempts'][0].update(route=dict(provider='codex', model='x', effort='low')),
               lambda r: r['attempts'][0].update(seq=2),
               lambda r: r['attempts'][0].update(state='running', outcome='complete'),
               lambda r: r['attempts'][0].update(predecessor='att-0'),
               lambda r: r['attempts'][0].update(children=[dict(id='c', state='running')]),
               lambda r: r.update(policy_sha256='4' * 64), lambda r: r.update(schema='x'),
               lambda r: r.update(extra=1), lambda r: r['attempts'].append(copy.deepcopy(r['attempts'][0]))):
        bad = copy.deepcopy(rec)
        fn(bad)
        with pytest.raises(ValueError):
            routing.validate_record(bad, POLICY)
    with pytest.raises(ValueError, match='policy'):
        routing.validate_record(rec, mutate(lambda d: d['usage'].update(fresh_seconds=901)))


def test_recover_reports_held_and_free_slots_without_dispatching():
    rec, _ = intent(fresh(), 1)
    out = routing.recover(rec, POLICY, expected(), cp())
    assert out['slot'] == 'held' and out['dispatch_allowed'] is False and out['authorizes'] is False
    rec, _ = started(rec, 1)
    assert routing.recover(rec, POLICY, expected(), cp())['slot'] == 'held'
    assert routing.recover(finish(rec, 1)[0], POLICY, expected(), cp())['slot'] == 'free'
    stale = routing.recover(finish(rec, 1)[0], POLICY, expected(), cp(head=HEAD2))
    assert stale['slot'] == 'held' and any('stale head' in h for h in stale['holds'])
    with pytest.raises(ValueError, match='context_hash'):
        routing.recover(rec, POLICY, expected(), cp(), context_hash='9' * 64)


# ---------- review validation ----------

def review(provider='codex', n=1, **over):
    return dict(provider=provider, model='m', effort='medium', native_task=f'rev-{n}', project='proj-a',
                repo='owner/repo', task='dynamic-routing', head=HEAD, authored=False, findings=[],
                evidence_ref='fixture:review') | over


def claude_authored():
    return run(fresh(), 1)


def mixed():
    return run(run(fresh(), 1, 'sonnet'), 2, 'sol')


def test_claude_author_needs_codex_reviewer():
    out = routing.validate_reviews(claude_authored(), POLICY, expected(), [review('codex')])
    assert out['ready'] is True and out['authorizes'] is False and out['coverage'] == {'openai': 'rev-1'}


def test_same_provider_review_does_not_count():
    out = routing.validate_reviews(claude_authored(), POLICY, expected(), [review('claudeAgent')])
    assert out['ready'] is False and any('opposite-provider' in p for p in out['problems'])
    assert routing.validate_reviews(claude_authored(), POLICY, expected(), [])['ready'] is False


def test_different_codex_model_is_not_cross_provider():
    rec = run(fresh(), 1, 'sol', 'scoped_bugfix')
    out = routing.validate_reviews(rec, POLICY, expected(), [review('codex', model='gpt-6.1-terra')])
    assert out['ready'] is False
    assert routing.validate_reviews(rec, POLICY, expected(), [review('claudeAgent')])['ready'] is True


def test_mixed_authorship_needs_both_provider_coverages():
    rec = mixed()
    one = routing.validate_reviews(rec, POLICY, expected(), [review('codex')])
    assert one['ready'] is False and one['authors'] == ['anthropic', 'openai']
    other = routing.validate_reviews(rec, POLICY, expected(), [review('claudeAgent', 2)])
    assert other['ready'] is False
    full = routing.validate_reviews(rec, POLICY, expected(), [review('codex'), review('claudeAgent', 2)])
    assert full['ready'] is True and full['coverage'] == {'openai': 'rev-1', 'anthropic': 'rev-2'}


def test_provider_alias_cannot_fake_underlying_identity():
    policy = mutate(lambda d: d['providers'].update(
        codex2={'underlying': 'openai', 'effort_option': 'reasoningEffort'}))
    rec = routing.new_record(policy, project='proj-a', repo='owner/repo', task='dynamic-routing',
                             plan_hash=H_PLAN, context_hash=H_CTX, scope_sha256=SCOPE, retry_budget=2,
                             checkpoint_key='task-key', workspace=dict(branch=BRANCH, worktree='C:/wt/task', pr=PR))
    rec, _ = routing.apply(rec, policy, expected(), 'i1', 'intent', dict(
        attempt='att-1', role='scoped_bugfix', target='sol', client_request_id='r1'), cp())
    rec, _ = routing.apply(rec, policy, expected(), 's1', 'started', dict(
        attempt='att-1', native=dict(task='t1', thread='th1'), returned=rec['attempts'][0]['route']), cp())
    rec, _ = routing.apply(rec, policy, expected(), 't1', 'terminal', dict(
        attempt='att-1', outcome='complete', writer='none', children=[]), cp())
    assert routing.validate_reviews(rec, policy, expected(), [review('codex2')])['ready'] is False
    assert routing.validate_reviews(rec, policy, expected(), [review('claudeAgent')])['ready'] is True
    assert routing.validate_reviews(rec, policy, expected(), [review('unknown-instance')])['ready'] is False


@pytest.mark.parametrize('over,match', [
    (dict(head=HEAD2), 'stale'), (dict(project='proj-b'), 'different project'),
    (dict(repo='other/repo'), 'different project'), (dict(task='other'), 'different project'),
    (dict(authored=True), 'author'), (dict(native_task='task-1'), 'author'),
    (dict(native_task='thread-1'), 'author'), (dict(findings=['P1 open bug']), 'findings'),
    (dict(evidence_ref=''), 'evidence_ref'), (dict(authored='no'), 'authored'),
    (dict(model=''), 'model'),
])
def test_review_rejections(over, match):
    out = routing.validate_reviews(claude_authored(), POLICY, expected(), [review('codex') | over])
    assert out['ready'] is False and any(match in p for p in out['problems'])


def test_review_requires_authored_attempt_and_closed_shape():
    with pytest.raises(ValueError, match='no authored'):
        routing.validate_reviews(fresh(), POLICY, expected(), [review()])
    out = routing.validate_reviews(claude_authored(), POLICY, expected(), [review() | {'approved': True}])
    assert out['ready'] is False


# ---------- fresh-process CLI ----------

def cli(*args, stdin=None):
    run_ = subprocess.run([sys.executable, '-m', 'agent_workflow_pilot.routing', *args],
                          input=stdin, capture_output=True, text=True, timeout=30)
    return run_.returncode, json.loads(run_.stdout)


def test_cli_decide_policy_and_errors():
    code, out = cli('policy', str(POLICY_PATH))
    assert code == 0 and out['policy_sha256'] == routing.validate_policy(POLICY)
    code, out = cli('decide', '--policy', str(POLICY_PATH), stdin=json.dumps(request('bugfix')))
    assert code == 0 and out['route']['target'] == 'sol' and out['authorizes'] is False
    assert out == routing.decide(POLICY, request('bugfix'))
    code, out = cli('decide', '--policy', str(POLICY_PATH), stdin='{"project": 1}')
    assert code == 1 and out['ok'] is False and out['dispatch_allowed'] is False
    code, out = cli('decide', '--policy', str(POLICY_PATH), stdin='{"a":1,"a":2}')
    assert code == 1


def test_cli_persistence_replay_switch_and_review_across_fresh_processes(tmp_path):
    rec_path, exp_path, cp_path = tmp_path / 'rec.json', tmp_path / 'exp.json', tmp_path / 'cp.json'
    exp_path.write_text(json.dumps(expected()))
    checkpoint.save(cp_path, cp())
    common = ['--policy', str(POLICY_PATH), '--expected', str(exp_path), '--checkpoint', str(cp_path)]
    e = expected()
    init = dict(project=e['project'], repo=e['repo'], task=e['task'], plan_hash=H_PLAN, context_hash=H_CTX,
                scope_sha256=SCOPE, retry_budget=2, checkpoint_key='task-key',
                workspace=dict(branch=BRANCH, worktree='C:/wt/task', pr=PR))
    assert cli('init', str(rec_path), '--policy', str(POLICY_PATH), stdin=json.dumps(init))[0] == 0
    assert cli('init', str(rec_path), '--policy', str(POLICY_PATH), stdin=json.dumps(init))[0] == 1

    def apply_(event, action, data):
        return cli('apply', str(rec_path), *common, stdin=json.dumps(dict(event_id=event, action=action, data=data)))

    first = dict(attempt='att-1', role='planning_builder', target='sonnet', client_request_id='req-1')
    code, out = apply_('i1', 'intent', first)
    assert code == 0 and out['dispatch_allowed'] is True
    saved = rec_path.read_bytes()
    code, out = apply_('i1', 'intent', first)  # fresh-process replay: no new dispatch
    assert code == 0 and out['dispatch_allowed'] is False and out['replay'] is True
    assert rec_path.read_bytes() == saved
    code, out = cli('recover', str(rec_path), *common)
    assert out['slot'] == 'held' and out['latest']['state'] == 'intent'
    route = dict(provider='claudeAgent', model='claude-sonnet-5-5', effort='medium')
    assert apply_('s1', 'started', dict(attempt='att-1', native=dict(task='t1', thread='h1'), returned=route))[0] == 0
    assert apply_('t1', 'terminal', dict(attempt='att-1', outcome='complete', writer='none', children=[]))[0] == 0
    assert cli('recover', str(rec_path), *common)[1]['slot'] == 'free'
    code, out = apply_('i2', 'intent', dict(attempt='att-2', role='planning_builder', target='sol',
                                             client_request_id='req-2'))
    assert code == 0 and out['dispatch_allowed'] is True
    assert json.loads(rec_path.read_text())['attempts'][1]['predecessor'] == 'att-1'
    code, out = apply_('i3', 'intent', dict(attempt='att-3', role='planning_builder', target='sonnet',
                                             client_request_id='req-3'))
    assert code == 1 and 'not terminal' in out['error'] and out['dispatch_allowed'] is False
    # stale expectation from a different process fails closed
    exp_path.write_text(json.dumps(expected(project='proj-b')))
    assert cli('recover', str(rec_path), *common)[0] == 1
    exp_path.write_text(json.dumps(expected()))
    code, out = cli('reviews', str(rec_path), *common, stdin=json.dumps([review('codex')]))
    assert code == 1 and out['ready'] is False  # attempt 2 (Sol) is still unreconciled


def test_cli_recover_reuses_real_m1_context_and_detects_stale_context(tmp_path):
    plan = program.load(ROOT / 'docs/program/roadmap.json')
    task = next(t for t in plan['tasks'] if t['id'] == 'dynamic-routing')
    ref = tc.reference(ROOT, 'docs/program/tasks/dynamic-routing.md')
    claim = json.loads((ROOT / 'docs/orchestration/handoffs/example.json').read_text())
    claim.update(task_id='dynamic-routing', head=HEAD)
    for row in claim['tests'] + claim['evidence']:
        row['head'] = HEAD
    doc = dict(schema=tc.SCHEMA, task_id='dynamic-routing', repo=claim['repo'], head=HEAD,
               plan_hash=program.fingerprint(plan, ROOT / 'docs/program'), spec=ref, objective='o',
               scope=['s'], exclusions=['x'], acceptance=['a'], depends_on=task['depends_on'],
               owns=task['owns'], owner='o', routing='r', risks=['r'], decisions=['d'], context=[ref],
               next_action='n', handoff=claim)
    digest = tc.reconstruct(doc, ROOT, ROOT / 'docs/program/roadmap.json', current_head=HEAD,
                            task_id='dynamic-routing', repo=claim['repo'])['context_hash']
    ctx = tmp_path / 'ctx.json'
    ctx.write_bytes(tc.canonical(doc))
    rec = fresh(repo=claim['repo'], context_hash=digest)
    rec_path, exp_path, cp_path = tmp_path / 'rec.json', tmp_path / 'exp.json', tmp_path / 'cp.json'
    routing.save(rec_path, rec)
    checkpoint.save(cp_path, cp())
    exp_path.write_text(json.dumps(expected(repo=claim['repo'], context_hash=digest)))
    args = ['recover', str(rec_path), '--policy', str(POLICY_PATH), '--expected', str(exp_path),
            '--checkpoint', str(cp_path), '--context', str(ctx), '--root', str(ROOT),
            '--plan', 'docs/program/roadmap.json']
    code, out = cli(*args)
    assert code == 0 and out['slot'] == 'free' and out['authorizes'] is False
    doc['next_action'] = 'changed'
    ctx.write_bytes(tc.canonical(doc))
    code, out = cli(*args)
    assert code == 1 and 'context_hash' in out['error']
    doc['plan_hash'] = '0' * 64
    ctx.write_bytes(tc.canonical(doc))
    assert cli(*args)[0] == 1


def test_save_is_atomic_and_leaves_no_temp(tmp_path):
    routing.save(tmp_path / 'r.json', fresh())
    assert [p.name for p in tmp_path.iterdir()] == ['r.json']
    assert routing.validate_record(json.loads((tmp_path / 'r.json').read_text()), POLICY)


# ---------- hostile scalar types never escape as non-ValueError ----------

def _scalar_mutations(doc, path=()):
    yield path
    children = doc.items() if isinstance(doc, dict) else enumerate(doc) if isinstance(doc, list) else ()
    for key, value in children:
        yield from _scalar_mutations(value, path + (key,))


@pytest.mark.parametrize('label,base,call', [
    ('request', request(usage=both('claudeAgent', 50)), lambda d: routing.decide(POLICY, d)),
    ('policy', POLICY, routing.validate_policy),
    ('record', run(fresh(), 1), lambda d: routing.validate_record(d, POLICY)),
    ('expected', expected(), lambda d: routing.recover(run(fresh(), 1), POLICY, d, cp())),
    ('checkpoint', cp(), lambda d: routing.recover(run(fresh(), 1), POLICY, expected(), d)),
    ('reviews', [review()], lambda d: routing.validate_reviews(run(fresh(), 1), POLICY, expected(), d)),
])
def test_hostile_types_raise_only_value_error(label, base, call):
    for path in _scalar_mutations(base):
        for value in (None, 1, True, 1.5, '', 'x', [], {}, [[]], {'a': []}):
            doc = copy.deepcopy(base)
            if path:
                node = doc
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = value
            else:
                doc = value
            try:
                call(doc)
            except ValueError:
                pass
