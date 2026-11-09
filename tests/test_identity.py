"""A1: external project identity/approval binding. Disposable local fixtures only.

Nothing here contacts GitHub; origin URLs are just local config strings.
"""
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agent_workflow_pilot.controller import continuation as x, identity as i, lifecycle as l, program as p

GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@example.invalid',
               GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@example.invalid',
               GIT_AUTHOR_DATE='2026-01-01T00:00:00Z', GIT_COMMITTER_DATE='2026-01-01T00:00:00Z')
PLAN = {'version': 1, 'revision': 'r1', 'tasks': [
    dict(id='t1', title='One', milestone='M1', kind='code', approved=True, decision=True, priority=0,
         depends_on=[], owns=['src/a/'], spec='tasks/t1.md'),
    dict(id='t2', title='Two', milestone='M1', kind='code', approved=True, decision=True, priority=1,
         depends_on=['t1'], owns=['src/b/'], spec='tasks/t2.md')]}
# Captured from the pre-A1 code: legacy v1 semantics must not move.
GOLD_FINGERPRINT = '989c46239c2cfb97676ffdcf50c5400ddc1a3418ad6ebfb6cf5efd4d57f273ef'
GOLD_CHECKPOINT = ('{"acceptance": ["acc"], "blocker": null, "ci": null, "dependencies": [], "events": {"prepare": '
                   '"[\\"dispatch\\", {\\"client_request_id\\": \\"intent-1\\", \\"completed_dependencies\\": []}]"}, '
                   '"head": null, "intent": "intent-1", "lifecycle": "dispatching", "refs": {}, "retries": 0, '
                   '"retry_budget": 2, "review": null, "task_key": "t1", "version": 1}')


def git(path, *args):
    r = subprocess.run(['git', '-C', str(path), *args], capture_output=True, text=True, env=GIT_ENV)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def world(tmp_path, name='alpha', owner='acme', remote=True):
    root = tmp_path / name
    (root / 'docs' / 'program' / 'tasks').mkdir(parents=True)
    (root / 'docs' / 'program' / 'roadmap.json').write_text(json.dumps(PLAN))
    (root / 'docs' / 'program' / 'tasks' / 't1.md').write_bytes(b'spec one\n')
    (root / 'docs' / 'program' / 'tasks' / 't2.md').write_bytes(b'spec two\n')
    git(root, 'init', '-q', '-b', 'main')
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'base')
    if remote:
        git(root, 'remote', 'add', 'origin', f'https://github.com/{owner}/{name}.git')
    return root


def planpath(root):
    return Path(root) / 'docs' / 'program' / 'roadmap.json'


def approval(root, task, **over):
    plan, base = p.load(planpath(root)), planpath(root).parent
    rec = dict(ref=f'user-{task}-1', source='user_decision', designated=False, project_id='proj-a',
               repository=dict(host='github.com', name='acme/' + Path(root).name), task=task, scope=['t1', 't2'],
               plan_hash=p.fingerprint(plan, base), operation='implement', status='valid', revision=1,
               spec_sha256=hashlib.sha256((base / ('tasks/%s.md' % task)).read_bytes()).hexdigest())
    rec.update(over)
    return rec


def expectation(root, **over):
    root = Path(root)
    e = dict(schema=i.EXPECT_SCHEMA, project_id='proj-a', repository=dict(host='github.com', name='acme/' + root.name),
             checkouts=[str(root)], common_dir=str(root / '.git'),
             approvals={t: approval(root, t) for t in ('t1', 't2')})
    e.update(over)
    return e


def prepared(tmp_path, root, tag='a'):
    """Legacy PC2 prepare: returns (plan, base, binding, delivery, observations)."""
    plan, base = p.load(planpath(root)), planpath(root).parent
    obs = dict(plan_hash=p.fingerprint(plan, base), tasks={})
    b, d = tmp_path / f'{tag}-binding.json', tmp_path / f'{tag}-delivery.json'
    l.prepare(plan, base, b, d, obs, ['t1'], 't1', ['acc'], 'intent-1')
    return plan, base, b, d, obs


# ---------------------------------------------------------------- legacy bytes
def test_legacy_v1_bytes_and_fingerprint_unchanged(tmp_path):
    root = world(tmp_path)
    plan, base, b, d, _ = prepared(tmp_path, root)
    assert p.fingerprint(plan, base) == GOLD_FINGERPRINT
    assert json.loads(b.read_text()) == dict(delivery=str(d.resolve()), plan_hash=GOLD_FINGERPRINT, task='t1')
    assert json.dumps(json.loads(d.read_text()), sort_keys=True) == GOLD_CHECKPOINT
    before = (b.read_bytes(), d.read_bytes())
    i.bind(expectation(root), plan, planpath(root), b)
    assert (b.read_bytes(), d.read_bytes()) == before  # adapter only references; never rewrites


# ---------------------------------------------------------------- positives
def test_correct_binding_is_inert_and_deterministic(tmp_path):
    root = world(tmp_path)
    plan, _, b, _, _ = prepared(tmp_path, root)
    env = i.bind(expectation(root), plan, planpath(root), b)
    assert env['schema'] == i.SCHEMA and 'approved' not in env
    report = i.verify(expectation(root), plan, planpath(root), b)
    assert report['authorizes'] is False and report['merge_authorized'] is False
    assert report['task'] == 't1' and report['approval']['source'] == 'user_decision'
    assert i.verify(expectation(root), plan, planpath(root), b) == report
    assert i.bind(expectation(root), plan, planpath(root), b) == env  # replay idempotent


def test_approved_sibling_worktree_and_unapproved_one(tmp_path):
    root = world(tmp_path)
    wt = tmp_path / 'alpha-wt'
    git(root, 'worktree', 'add', '-q', '-b', 'wt', str(wt))
    plan, _, b, _, _ = prepared(tmp_path, root)
    i.bind(expectation(root), plan, planpath(root), b)
    exp = expectation(root, checkouts=[str(root), str(wt)])
    assert i.verify(exp, plan, planpath(wt), b)['checkout']['root']
    with pytest.raises(ValueError, match='checkout'):
        i.verify(expectation(root), plan, planpath(wt), b)  # sibling worktree not approved


# ---------------------------------------------------------------- identity negatives
def _bound(tmp_path, **kw):
    root = world(tmp_path, **kw)
    plan, _, b, _, _ = prepared(tmp_path, root)
    i.bind(expectation(root), plan, planpath(root), b)
    return root, plan, b


@pytest.mark.parametrize('field,value', [
    ('project_id', 'proj-b'),
    ('repository', dict(host='github.com', name='acme/other')),
    ('checkouts', ['/somewhere/else']),
    ('common_dir', '/somewhere/else/.git'),
])
def test_wrong_expectation_rejected(tmp_path, field, value):
    root, plan, b = _bound(tmp_path)
    with pytest.raises(ValueError):
        i.verify(expectation(root, **{field: value}), plan, planpath(root), b)


def test_identical_projects_do_not_cross(tmp_path):
    a, b_ = world(tmp_path, 'alpha'), world(tmp_path, 'beta')
    assert git(a, 'rev-parse', 'HEAD') == git(b_, 'rev-parse', 'HEAD')  # same tree, same task names, same SHA
    plan, _, binding, _, _ = prepared(tmp_path, a)
    i.bind(expectation(a), plan, planpath(a), binding)
    # beta's controller expectation (own project/repo/root) rejects alpha's envelope
    beta = expectation(b_, project_id='proj-b')
    with pytest.raises(ValueError):
        i.verify(beta, plan, planpath(b_), binding)
    # alpha's expectation rejects being run from beta's identical checkout
    with pytest.raises(ValueError, match='checkout'):
        i.verify(expectation(a), plan, planpath(b_), binding)


def test_origin_change_and_sibling_clone_rejected(tmp_path):
    root, plan, b = _bound(tmp_path)
    clone = tmp_path / 'clone'
    subprocess.run(['git', 'clone', '-q', str(root), str(clone)], check=True, env=GIT_ENV)
    git(clone, 'remote', 'set-url', 'origin', 'https://github.com/acme/alpha.git')
    with pytest.raises(ValueError, match='checkout'):
        i.verify(expectation(root), plan, planpath(clone), b)  # same origin, other root/common dir
    git(root, 'remote', 'set-url', 'origin', 'https://github.com/evil/alpha.git')
    with pytest.raises(ValueError, match='origin'):
        i.verify(expectation(root), plan, planpath(root), b)


def test_self_authenticating_inputs_rejected(tmp_path):
    root, plan, b = _bound(tmp_path)
    envelope = json.loads((Path(str(b) + i.MARKER)).read_text())
    with pytest.raises(ValueError):
        i.verify(envelope, plan, planpath(root), b)  # envelope offered as the expectation
    with pytest.raises(ValueError):
        i.verify(None, plan, planpath(root), b)  # missing independent expectation
    env = tmp_path / 'env.json'
    env.write_text(json.dumps(expectation(root)))
    r = subprocess.run([sys.executable, '-m', 'agent_workflow_pilot.controller.identity', 'verify', '--plan',
                        str(planpath(root)), '--binding', str(b), '--expect', str(Path(str(b) + i.MARKER))],
                       capture_output=True, text=True)
    assert r.returncode == 1


def test_envelope_tampering_and_laundering(tmp_path):
    root, plan, b = _bound(tmp_path)
    marker = Path(str(b) + i.MARKER)
    good = json.loads(marker.read_text())
    for edit in ({'project_id': 'proj-b'}, {'task': 't2'}, {'plan_hash': 'f' * 64}, {'binding_sha256': 'f' * 64},
                 {'approval_ref': 'other'}, {'approved': True}, {'schema': 'x'}):
        marker.write_text(json.dumps(dict(good, **edit)))
        with pytest.raises(ValueError):
            i.verify(expectation(root), plan, planpath(root), b)
    marker.write_text(json.dumps(good))
    b.write_text(json.dumps(dict(json.loads(b.read_text()), task='t2')))  # legacy bytes edited after binding
    with pytest.raises(ValueError, match='binding'):
        i.verify(expectation(root), plan, planpath(root), b)


def test_malformed_legacy_binding_not_laundered(tmp_path):
    root = world(tmp_path)
    plan = p.load(planpath(root))
    b = tmp_path / 'bad.json'
    for bad in ('{"task": "t1"}', 'not json', json.dumps(dict(plan_hash='0' * 64, task='t1', delivery=str(tmp_path / 'none')))):
        b.write_text(bad)
        with pytest.raises((ValueError, OSError)):
            i.bind(expectation(root), plan, planpath(root), b)
        assert not Path(str(b) + i.MARKER).exists()


# ---------------------------------------------------------------- approval
@pytest.mark.parametrize('over', [
    dict(status='revoked'), dict(status='superseded'), dict(plan_hash='e' * 64), dict(spec_sha256='e' * 64),
    dict(project_id='proj-b'), dict(repository=dict(host='github.com', name='acme/other')), dict(task='t2'),
    dict(scope=['t2']), dict(operation='merge'), dict(source='pr_flag'), dict(source='trusted_policy', designated=False),
    dict(ref=''), dict(approved=True),
])
def test_approval_rejections(tmp_path, over):
    root, plan, b = _bound(tmp_path)
    exp = expectation(root)
    exp['approvals']['t1'] = dict(exp['approvals']['t1'], **over)
    with pytest.raises(ValueError):
        i.verify(exp, plan, planpath(root), b)


def test_approval_ref_mismatch_missing_and_flags_alone(tmp_path):
    root, plan, b = _bound(tmp_path)
    exp = expectation(root)
    exp['approvals']['t1']['ref'] = 'another-user-decision'  # envelope names a different reference
    with pytest.raises(ValueError, match='approval'):
        i.verify(exp, plan, planpath(root), b)
    exp = expectation(root, approvals={})  # roadmap says approved=true, controller supplied no evidence
    with pytest.raises(ValueError, match='approval'):
        i.verify(exp, plan, planpath(root), b)
    with pytest.raises(ValueError, match='approval'):
        i.check_task(exp, plan, planpath(root), 't1')


def test_designated_policy_accepted_but_never_merge(tmp_path):
    root, plan, b = _bound(tmp_path)
    exp = expectation(root)
    exp['approvals']['t1'] = dict(exp['approvals']['t1'], source='trusted_policy', designated=True)
    marker = Path(str(b) + i.MARKER)
    marker.unlink()
    i.bind(exp, plan, planpath(root), b)
    r = i.verify(exp, plan, planpath(root), b)
    assert r['approval']['source'] == 'trusted_policy' and r['merge_authorized'] is False


def test_stale_plan_invalidates_approval(tmp_path):
    root, plan, b = _bound(tmp_path)
    changed = copy.deepcopy(plan)
    changed['revision'] = 'r2'
    with pytest.raises(ValueError):
        i.verify(expectation(root), changed, planpath(root), b)


# ---------------------------------------------------------------- unsupported hosts
def test_unsupported_hosts_block_explicitly(tmp_path):
    root, plan, b = _bound(tmp_path)
    exp = expectation(root, repository=dict(host='gitlab.example', name='acme/alpha'))
    exp['approvals'] = {t: dict(r, repository=exp['repository']) for t, r in exp['approvals'].items()}
    with pytest.raises(i.Unsupported, match='unsupported'):
        i.check_task(exp, plan, planpath(root), 't1')  # representable, not verifiable
    git(root, 'remote', 'remove', 'origin')
    with pytest.raises(i.Unsupported, match='remote'):
        i.verify(expectation(root), plan, planpath(root), b)
    git(root, 'remote', 'add', 'origin', 'https://gitlab.example/acme/alpha.git')
    with pytest.raises(i.Unsupported, match='unsupported'):
        i.verify(expectation(root), plan, planpath(root), b)
    plain = tmp_path / 'plain'
    plain.mkdir()
    with pytest.raises(ValueError):
        i.observe(plain)


# ---------------------------------------------------------------- Windows filesystem semantics
def _junction(link, target):
    r = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True, text=True)
    if r.returncode:
        pytest.skip('junction creation unavailable: ' + r.stdout + r.stderr)


@pytest.mark.skipif(os.name != 'nt', reason='Windows path-case semantics')
def test_windows_case_alias_accepted(tmp_path):
    root, plan, b = _bound(tmp_path)
    swapped = Path(str(planpath(root)).swapcase())
    assert str(swapped) != str(planpath(root)) and swapped.exists()
    assert i.verify(expectation(root), plan, swapped, b)['authorizes'] is False


@pytest.mark.skipif(os.name != 'nt', reason='Windows junction semantics')
def test_windows_junction_alias_and_foreign_target(tmp_path):
    root, plan, b = _bound(tmp_path)
    alias = tmp_path / 'alias'
    _junction(alias, root)
    assert i.verify(expectation(root), plan, planpath(alias), b)['authorizes'] is False
    other = world(tmp_path, 'beta')
    foreign = tmp_path / 'foreign'
    _junction(foreign, other)
    with pytest.raises(ValueError, match='checkout'):
        i.verify(expectation(root), plan, planpath(foreign), b)


def test_symlink_alias_or_honest_skip(tmp_path):
    root, plan, b = _bound(tmp_path)
    alias = tmp_path / 'sym'
    try:
        os.symlink(root, alias, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('symlink creation needs privilege on this host; not verified here')
    assert i.verify(expectation(root), plan, planpath(alias), b)['authorizes'] is False


# ---------------------------------------------------------------- project-mode entry points
def _cli(module, *args, **kw):
    return subprocess.run([sys.executable, '-m', 'agent_workflow_pilot.controller.' + module, *map(str, args)],
                          capture_output=True, text=True, **kw)


def _project(tmp_path):
    """Project-mode PC2 prepare through the real CLI. Returns paths."""
    root = world(tmp_path)
    plan, base = p.load(planpath(root)), planpath(root).parent
    exp, obs = tmp_path / 'expect.json', tmp_path / 'obs.json'
    exp.write_text(json.dumps(expectation(root)))
    obs.write_text(json.dumps(dict(plan_hash=p.fingerprint(plan, base), tasks={})))
    inp = tmp_path / 'prep.json'
    inp.write_text(json.dumps(dict(delivery=str(tmp_path / 'd.json'), scope=['t1'], task='t1',
                                   acceptance=['acc'], intent='intent-1')))
    return root, exp, obs, inp, tmp_path / 'b.json'


def test_project_mode_requires_binding_and_blocks_legacy_bypass(tmp_path):
    root, exp, obs, inp, b = _project(tmp_path)
    common = ['--plan', planpath(root), '--binding', b, '--observations', obs, '--input', inp]
    assert _cli('lifecycle', 'prepare', *common, '--mode', 'project').returncode == 1  # no --expect
    assert not b.exists()
    ok = _cli('lifecycle', 'prepare', *common, '--mode', 'project', '--expect', exp)
    assert ok.returncode == 0, ok.stderr
    assert Path(str(b) + i.MARKER).exists()
    before = (b.read_bytes(), (tmp_path / 'd.json').read_bytes())
    att = tmp_path / 'att.json'
    att.write_text(json.dumps(dict(scope=['t1'], refs=dict(task='n1', thread='th1'))))
    args = ['--plan', planpath(root), '--binding', b, '--observations', obs, '--input', att]
    for bad in (['--mode', 'project'],  # missing expectation
                [],  # legacy entrypoint against project-bound state
                ['--mode', 'legacy']):
        r = _cli('lifecycle', 'attach', *args, *bad)
        assert r.returncode == 1, r.stdout
    assert (b.read_bytes(), (tmp_path / 'd.json').read_bytes()) == before  # nothing consumed or rewritten
    assert _cli('lifecycle', 'attach', *args, '--mode', 'project', '--expect', exp).returncode == 0
    # wrong controller expectation (another project) fails before state is consumed
    bad = tmp_path / 'bad-expect.json'
    bad.write_text(json.dumps(expectation(root, project_id='proj-b')))
    snapshot = (tmp_path / 'd.json').read_bytes()
    assert _cli('lifecycle', 'attach', *args, '--mode', 'project', '--expect', bad).returncode == 1
    assert (tmp_path / 'd.json').read_bytes() == snapshot


def test_program_cli_modes(tmp_path):
    root, exp, obs, inp, b = _project(tmp_path)
    prog = ['--plan', planpath(root), '--observations', obs]
    legacy = _cli('program', 'next', *prog)
    assert legacy.returncode == 0 and json.loads(legacy.stdout)['task'] == 't1'  # legacy mode unchanged
    assert _cli('program', 'next', *prog, '--mode', 'project').returncode == 1  # missing expectation
    proj = _cli('program', 'next', *prog, '--mode', 'project', '--expect', exp)
    assert proj.returncode == 0 and json.loads(proj.stdout)['task'] == 't1'
    noapproval = tmp_path / 'none.json'
    noapproval.write_text(json.dumps(expectation(root, approvals={})))
    assert _cli('program', 'next', *prog, '--mode', 'project', '--expect', noapproval).returncode == 1


def test_fresh_process_validation_is_deterministic(tmp_path):
    root, exp, obs, inp, b = _project(tmp_path)
    common = ['--plan', planpath(root), '--binding', b, '--observations', obs, '--input', inp]
    assert _cli('lifecycle', 'prepare', *common, '--mode', 'project', '--expect', exp).returncode == 0
    outs = [_cli('identity', 'verify', '--plan', planpath(root), '--binding', b, '--expect', exp) for _ in range(2)]
    assert all(o.returncode == 0 for o in outs) and outs[0].stdout == outs[1].stdout
    assert json.loads(outs[0].stdout)['authorizes'] is False


def test_continuation_replay_no_duplicate_dispatch_in_project_mode(tmp_path):
    root = world(tmp_path)
    plan, base = p.load(planpath(root)), planpath(root).parent
    exp = expectation(root)
    ev = dict(state='delivered', head='d' * 64, verified_head='d' * 64, ref='pinned:artifact', children_terminal=True,
              accepted=True, independent=True)
    plan_a = copy.deepcopy(plan)
    for t in plan_a['tasks']:
        t['kind'] = 'artifact'
    (planpath(root)).write_text(json.dumps(plan_a))
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'artifact')
    plan, base = p.load(planpath(root)), planpath(root).parent
    exp = expectation(root)
    obs = dict(plan_hash=p.fingerprint(plan, base), tasks={})
    b = tmp_path / 'a.json'
    l.prepare(plan, base, b, tmp_path / 'a-d.json', obs, ['t1', 't2'], 't1', ['acc'], 'a-intent')
    i.bind(exp, plan, planpath(root), b)
    refs = dict(task='n-a', thread='th-a')
    l.attach(plan, base, b, obs, ['t1', 't2'], refs, project=i.verify(exp, plan, planpath(root), b))
    obs['tasks']['t1'] = ev
    args = dict(journal=str(tmp_path / 'j.json'), binding=str(b), scope=['t1', 't2'], event='e1',
                native=dict(**refs, status='completed', children_terminal=True, ref='rec'), head='d' * 64,
                successor=dict(binding=str(tmp_path / 'b.json'), delivery=str(tmp_path / 'b-d.json'), task='t2',
                               acceptance=['acc'], intent='b-intent'))
    with pytest.raises(ValueError, match='project'):  # legacy API refuses a project-bound binding
        x.advance(plan, base, observations=obs, **args)
    proof = i.verify(exp, plan, planpath(root), b)
    first = x.advance(plan, base, observations=obs, project=proof, **args)
    assert first['dispatch'] is True
    again = x.advance(plan, base, observations=obs, project=proof, **args)
    assert again['dispatch'] is False and again['replay'] is True
    with pytest.raises(ValueError, match='project'):  # JSON-forged proof is not a verification result
        x.advance(plan, base, observations=obs, project=dict(proof), **args)


def test_rollback_keeps_state_and_never_migrates(tmp_path):
    root, exp, obs, inp, b = _project(tmp_path)
    common = ['--plan', planpath(root), '--binding', b, '--observations', obs, '--input', inp]
    assert _cli('lifecycle', 'prepare', *common, '--mode', 'project', '--expect', exp).returncode == 0
    snap = {f.name: f.read_bytes() for f in tmp_path.iterdir() if f.is_file()}
    # An older/legacy reader must stop on project-bound state, leaving every byte in place.
    assert _cli('lifecycle', 'prepare', *common).returncode == 1
    assert {f.name: f.read_bytes() for f in tmp_path.iterdir() if f.is_file()} == snap
