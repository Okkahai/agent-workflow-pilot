"""Local CLI simulations; no live T3 dispatch, quota outage or crash guarantee."""
import copy
import json


from agent_workflow_pilot import routing, task_context as tc
from agent_workflow_pilot.controller import checkpoint, program
from test_routing import (ROOT, POLICY, POLICY_PATH, HEAD, HEAD2, cli, cp, expected,
                          fresh, request, snapshot, review)


def test_planning_fallback_requires_choice_but_implementation_can_switch():
    unavailable = snapshot(providers__claudeAgent__enabled=False)
    for category in ('planning', 'architecture'):
        code, out = cli('decide', '--policy', str(POLICY_PATH),
                        stdin=json.dumps(request(category, snap=unavailable)))
        assert code == 0
        assert out['decision'] == 'candidate'
    assert routing.decide(POLICY, request('standard', snap=unavailable))['decision'] == 'route'


def test_refresh_requires_reconstructed_current_context_preserves_history(tmp_path):
    plan_path = ROOT / 'docs/program/roadmap.json'
    plan = program.load(plan_path)
    task = next(t for t in plan['tasks'] if t['id'] == 'dynamic-routing')
    ref = tc.reference(ROOT, 'docs/program/tasks/dynamic-routing.md')
    claim = json.loads((ROOT / 'docs/orchestration/handoffs/example.json').read_text())
    claim.update(task_id='dynamic-routing', head=HEAD2)
    for row in claim['tests'] + claim['evidence']:
        row['head'] = HEAD2
    context = dict(schema=tc.SCHEMA, task_id='dynamic-routing', repo=claim['repo'], head=HEAD2,
                   plan_hash=program.fingerprint(plan, plan_path.parent), spec=ref,
                   objective='Conformance simulation', scope=['routing'], exclusions=['live calls'],
                   acceptance=['fresh reconstruction'], depends_on=task['depends_on'], owns=task['owns'],
                   owner='implementation worker', routing='codex Sol medium', risks=['local simulation'],
                   decisions=['preserve history'], context=[ref], next_action='independent review', handoff=claim)
    digest = tc.reconstruct(context, ROOT, plan_path, current_head=HEAD2,
                            task_id='dynamic-routing', repo=claim['repo'])['context_hash']
    old_context = copy.deepcopy(context)
    old_context['head'] = old_context['handoff']['head'] = HEAD
    for row in old_context['handoff']['tests'] + old_context['handoff']['evidence']:
        row['head'] = HEAD
    old_hash = tc.reconstruct(old_context, ROOT, plan_path, current_head=HEAD,
                              task_id='dynamic-routing', repo=claim['repo'])['context_hash']
    old_expected = expected(repo=claim['repo'], plan_hash=context['plan_hash'], context_hash=old_hash)
    rec = routing.new_record(POLICY, **{k: old_expected[k] for k in
        ('project', 'repo', 'task', 'plan_hash', 'context_hash', 'scope_sha256', 'retry_budget')},
        checkpoint_key='task-key', workspace={k: old_expected[k] for k in ('branch', 'worktree', 'pr')})
    for eid, action, data in [
        ('intent', 'intent', dict(attempt='att-1', role='planning_builder', target='sonnet', client_request_id='req-1')),
        ('start', 'started', dict(attempt='att-1', native=dict(task='native-1', thread='thread-1'),
                                returned=dict(provider='claudeAgent', model='claude-sonnet-5-5', effort='medium'))),
        ('end', 'terminal', dict(attempt='att-1', outcome='complete', writer='none', children=[]))]:
        rec, _ = routing.apply(rec, POLICY, old_expected, eid, action, data, cp())
    old_attempts = copy.deepcopy(rec['attempts'])
    path, exp, state, ctx = [tmp_path / n for n in ('rec.json', 'expected.json', 'cp.json', 'ctx.json')]
    routing.save(path, rec)
    e = expected(repo=claim['repo'], head=HEAD2, plan_hash=context['plan_hash'], context_hash=digest)
    exp.write_text(json.dumps(e))
    ctx.write_bytes(tc.canonical(context))
    checkpoint.save(state, cp())
    args = ['refresh', str(path), '--policy', str(POLICY_PATH), '--expected', str(exp),
            '--checkpoint', str(state), '--context', str(ctx), '--root', str(ROOT),
            '--plan', 'docs/program/roadmap.json']
    # A new expectation cannot launder a stale checkpoint.
    before = path.read_bytes()
    assert cli(*args)[0] == 1
    assert path.read_bytes() == before
    checkpoint.save(state, checkpoint.apply(cp(), 'new-head', 'head', head=HEAD2))
    code, out = cli(*args)
    assert code == 0, out
    saved = json.loads(path.read_text())
    assert saved['attempts'] == old_attempts
    assert saved['events'] == rec['events']
    assert saved['context_hash'] == digest
    common = ['--policy', str(POLICY_PATH), '--expected', str(exp), '--checkpoint', str(state)]
    assert cli('recover', str(path), *common, '--context', str(ctx), '--root', str(ROOT),
               '--plan', 'docs/program/roadmap.json')[1]['slot'] == 'free'
    ctx.write_bytes(tc.canonical(context | {'head': HEAD}))
    assert cli(*args)[0] == 1
    assert json.loads(path.read_text()) == saved


def test_persist_before_mock_execution_safe_switch_and_final_reviews(tmp_path):
    path, exp, state = [tmp_path / n for n in ('attempts.json', 'expected.json', 'cp.json')]
    routing.save(path, fresh())
    exp.write_text(json.dumps(expected()))
    checkpoint.save(state, cp())
    common = ['--policy', str(POLICY_PATH), '--expected', str(exp), '--checkpoint', str(state)]

    def event(name, action, **data):
        return cli('apply', str(path), *common,
                   stdin=json.dumps(dict(event_id=name, action=action, data=data)))

    def mock_native(attempt, provider, model):
        # The mock sees the persisted intent, as a native adapter must.
        persisted = json.loads(path.read_text())['attempts'][-1]
        assert persisted['id'] == attempt and persisted['state'] == 'intent'
        return event('start-' + attempt, 'started', attempt=attempt,
                     native=dict(task='native-' + attempt, thread='thread-' + attempt),
                     returned=dict(provider=provider, model=model, effort='medium'))

    first = dict(attempt='sonnet-1', role='planning_builder', target='sonnet', client_request_id='req-1')
    code, out = event('intent-1', 'intent', **first)
    assert code == 0 and out['dispatch_allowed'], out
    before = path.read_bytes()
    assert event('intent-1', 'intent', **first)[1]['dispatch_allowed'] is False
    assert path.read_bytes() == before
    assert mock_native('sonnet-1', 'claudeAgent', 'claude-sonnet-5-5')[0] == 0
    second = dict(attempt='sol-2', role='planning_builder', target='sol', client_request_id='req-2')
    assert event('intent-2', 'intent', **second)[0] == 1
    assert event('terminal-1', 'terminal', attempt='sonnet-1', outcome='complete', writer='none',
                 children=[dict(id='child-1', state='running')])[0] == 1
    assert event('terminal-1', 'terminal', attempt='sonnet-1', outcome='complete', writer='none',
                 children=[dict(id='child-1', state='terminal')])[0] == 0
    assert event('intent-2', 'intent', **second)[1]['dispatch_allowed'] is True
    assert mock_native('sol-2', 'codex', 'gpt-6.1-sol')[0] == 0
    assert event('terminal-2', 'terminal', attempt='sol-2', outcome='complete', writer='none', children=[])[0] == 0
    rec = json.loads(path.read_text())
    assert rec['retry_budget'] == 2 and rec['scope_sha256'] == expected()['scope_sha256']
    assert rec['attempts'][1]['predecessor'] == 'sonnet-1'
    reviews = [review('codex'), review('claudeAgent', 2)]
    assert cli('reviews', str(path), *common, stdin=json.dumps(reviews))[1]['ready'] is True
    for field, value in [('head', HEAD2), ('project', 'other-project'), ('native_task', 'native-sol-2')]:
        bad = copy.deepcopy(reviews)
        bad[0][field] = value
        assert cli('reviews', str(path), *common, stdin=json.dumps(bad))[1]['ready'] is False
    exp.write_text(json.dumps(expected(retry_budget=3)))
    assert cli('recover', str(path), *common)[0] == 1
