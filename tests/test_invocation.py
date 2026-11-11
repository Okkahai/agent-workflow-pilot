"""B1: trusted controller invocation boundary. Disposable local fixtures only.

Windows and Linux are separate evidence: nothing here is portability proof for a platform
that did not run it. The runtime under test is an installed wheel in a throwaway venv; the
target is a non-Python Git fixture (spaces + parentheses). No network, no real remote, no
native dispatch. Misbehaving "stub" runtimes are harmless copies of the package with one
module replaced; they test the process machinery, never genuine untrusted code.
"""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from agent_workflow_pilot import task_context as tc
from agent_workflow_pilot.controller import checkpoint, identity as i, invocation as v, program as p
from test_identity import GOLD_CHECKPOINT, GOLD_FINGERPRINT, GIT_ENV, PLAN

REPO = Path(__file__).resolve().parents[1]
UV, GIT = shutil.which('uv'), shutil.which('git')
GIT_DIR = str(Path(GIT).parent)
HEAD = 'a' * 40
SCRIPTS = 'Scripts' if os.name == 'nt' else 'bin'


def sh(*argv, **kw):
    r = subprocess.run(argv, capture_output=True, text=True, **kw)
    assert r.returncode == 0, (argv, r.stdout, r.stderr)
    return r.stdout.strip()


def venv(path):
    sh(UV, 'venv', '--python', '3.12', '--no-python-downloads', str(path))
    return str(path / SCRIPTS / ('python.exe' if os.name == 'nt' else 'python'))


def package_dir(python):
    return sh(python, '-I', '-B', '-c', 'import agent_workflow_pilot as a,os;print(os.path.dirname(a.__file__))')


@pytest.fixture(scope='session')
def wheel(tmp_path_factory):
    out = tmp_path_factory.mktemp('wheel')
    sh(UV, 'build', '--wheel', '--no-python-downloads', '--python', '3.12', '--out-dir', str(out), str(REPO))
    return next(out.glob('*.whl'))


def install(base, wheel):
    py = venv(base)
    sh(UV, 'pip', 'install', '--no-deps', '--link-mode', 'copy', '--no-python-downloads', '--python', py, str(wheel))
    return py


def pin(py, **over):
    root = package_dir(py)
    fields = dict(python=py, minor='3.12', package_root=root, package_sha256=v.package_digest(root),
                  provenance='fixture-wheel:uv-build')
    fields.update(over)
    return v.Runtime(**fields)


@pytest.fixture(scope='session')
def runtime(tmp_path_factory, wheel):
    return pin(install(tmp_path_factory.mktemp('rt') / 'venv', wheel))


STUB_PROGRAM = '''
import json, os, subprocess, sys, time
from pathlib import Path
def main(argv=None):
    a = sys.argv[1:]
    plan = Path(a[a.index('--plan') + 1])
    mode = (plan.parent / 'stub-mode.txt').read_text().strip()
    ok = json.loads((plan.parent / 'stub-ok.json').read_text())     # genuine-shaped, written by the test
    state = Path(a[a.index('--expect') + 1]).parent.parent.parent
    (plan.parent / 'stub-pid.txt').write_text(str(os.getpid()))
    if mode == 'ok': print(json.dumps(ok)); return 0
    if mode == 'nonjson': print('not json'); return 0
    if mode == 'array': print('[]'); return 0
    if mode == 'dup': print('{"a":1,"a":2}'); return 0
    if mode == 'badutf8': sys.stdout.buffer.write(b'\\xff\\xfe{}'); return 0
    if mode == 'authorizes': ok['merge_authorized'] = True; print(json.dumps(ok)); return 0
    if mode == 'nonzero': print('program: boom', file=sys.stderr); return 3
    if mode == 'reject':
        print("program: bad value 'secret-value' in " + str(state) + " ref user-t1-1", file=sys.stderr); return 1
    if mode == 'flood_out':
        while True: sys.stdout.write('x' * 65536); sys.stdout.flush()
    if mode == 'flood_err':
        while True: sys.stderr.write('x' * 65536); sys.stderr.flush()
    if mode == 'sleep': time.sleep(60)
    if mode == 'rogue': (state / 'rogue.txt').write_text('x'); print(json.dumps(ok)); return 0
    if mode == 'holder':     # long-lived descendant inheriting the pipes; the TEST owns and kills it
        h = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])
        with open(plan.parent / 'stub-holders.txt', 'a') as f: f.write(str(h.pid) + '\\n')
        print(json.dumps(ok)); return 0
    return 9
if __name__ == '__main__': sys.exit(main())
'''
STUB_LIFECYCLE = '''
import json, sys, time
from pathlib import Path
def main(argv=None):
    a = sys.argv[1:]
    plan = Path(a[a.index('--plan') + 1])
    mode = (plan.parent / 'stub-mode.txt').read_text().strip()
    binding = Path(a[a.index('--binding') + 1])
    if mode.startswith('write'): binding.write_text('{"half": ')
    if mode == 'write_sleep': time.sleep(60)
    if mode == 'write_fail': print('lifecycle: failed after write', file=sys.stderr); return 1
    if mode == 'rogue': (binding.parent / 'rogue.txt').write_text('x')
    print(json.dumps(dict(action='reconcile_native_intent', intent='intent-1', dispatch=False)))
    return 0
if __name__ == '__main__': sys.exit(main())
'''


@pytest.fixture(scope='session')
def stub(tmp_path_factory, wheel):
    py = install(tmp_path_factory.mktemp('stub') / 'venv', wheel)
    pkg = Path(package_dir(py)) / 'controller'
    (pkg / 'program.py').write_text(STUB_PROGRAM, encoding='utf-8')
    (pkg / 'lifecycle.py').write_text(STUB_LIFECYCLE, encoding='utf-8')
    return pin(py)


# ----------------------------------------------------------------------------- world
def git(path, *args):
    r = subprocess.run(['git', '-C', str(path), *args], capture_output=True, text=True, env=GIT_ENV)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


ALT = copy.deepcopy(PLAN)
ALT['tasks'][0]['milestone'], ALT['tasks'][1]['milestone'] = 'Alpha-1', 'Billing_API'


class World:
    def __init__(self, tmp, plan, runtime, name='project'):
        self.runtime = runtime
        self.root = tmp / 'work area' / 'App Fixture (non-py)' if name == 'project' else tmp / name
        (self.root / 'ops' / 'tasks').mkdir(parents=True)
        self.plan = self.root / 'ops' / 'roadmap.json'
        self.plan.write_text(json.dumps(plan))
        (self.root / 'ops' / 'tasks' / 't1.md').write_bytes(b'spec one\n')
        (self.root / 'ops' / 'tasks' / 't2.md').write_bytes(b'spec two\n')
        (self.root / 'package.json').write_text('{"name": "app"}')
        git(self.root, 'init', '-q', '-b', 'main')
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-qm', 'base')
        git(self.root, 'remote', 'add', 'origin', 'https://github.com/acme/app-fixture.git')
        self.state = tmp / f'controller state ({name})'
        self.state.mkdir()
        self.project_id, self.writer, self.calls, self.mutate = 'proj-b1', 'attempt-1', 0, None
        self.frozen = None

    @property
    def project(self):
        return v.Project(self.project_id, str(self.root), str(self.root / '.git'), str(self.state), self.writer)

    def expectation(self):
        plan, base = p.load(self.plan), self.plan.parent
        repo = dict(host='github.com', name='acme/app-fixture')
        approvals = {t: dict(ref=f'user-{t}-1', source='user_decision', designated=False, project_id='proj-b1',
                             repository=repo, task=t, scope=['t1', 't2'], plan_hash=p.fingerprint(plan, base),
                             operation='implement', status='valid', revision=1,
                             spec_sha256=hashlib.sha256((base / 'tasks' / f'{t}.md').read_bytes()).hexdigest())
                     for t in ('t1', 't2')}
        e = dict(schema=i.EXPECT_SCHEMA, project_id='proj-b1', repository=repo, checkouts=[str(self.root)],
                 common_dir=str(self.root / '.git'), approvals=approvals)
        if self.mutate:
            self.mutate(e)
        return e

    def authority(self):
        self.calls += 1
        return self.frozen if self.frozen is not None else self.expectation()

    def obs(self, **tasks):
        try:
            digest = p.fingerprint(p.load(self.plan), self.plan.parent)
        except (ValueError, OSError):
            digest = '0' * 64
        return dict(plan_hash=digest, tasks=tasks)

    def args(self, op, **over):
        plan = str(self.plan)
        a = dict(
            **{'program.check': dict(plan=plan), 'program.next': dict(plan=plan),
               'program.resume': dict(plan=plan, binding='b.json'),
               'task_context.validate': dict(plan='ops/roadmap.json', file=plan, current_head=HEAD, task_id='t1',
                                             repo='o/r'),
               'identity.check': dict(plan=plan, task='t1'),
               'identity.verify': dict(plan=plan, binding='b.json'),
               'lifecycle.prepare': dict(plan=plan, binding='b.json', delivery='d.json', observations=self.obs(),
                                         scope=['t1'], task='t1', acceptance=['acc'], intent='intent-1'),
               'lifecycle.attach': dict(plan=plan, binding='b.json', observations=self.obs(), scope=['t1'],
                                        refs=dict(task='n-task', thread='n-thread')),
               'lifecycle.reconcile': dict(plan=plan, binding='b.json', observations=self.obs(), scope=['t1'],
                                           native=dict(task='n-task', thread='n-thread', status='completed',
                                                       children_terminal=True, ref='native-ref-1'), head=HEAD)}[op])
        a.update(over)
        return {k: x for k, x in a.items() if x is not None}

    def run(self, op, runtime=None, project=None, cwd=None, timeout=30.0, **over):
        return v.invoke(runtime or self.runtime, project or self.project, op, self.args(op, **over),
                        authority=self.authority, git_dir=GIT_DIR, cwd=cwd, timeout=timeout)

    def fail(self, op, kind, **kw):
        with pytest.raises(v.InvocationError) as e:
            self.run(op, **kw)
        assert e.value.kind == kind, str(e.value)
        return e.value

    def prepare(self, **kw):
        return self.run('lifecycle.prepare', **kw)

    def files(self):
        return {q.name: q.read_bytes() for q in self.state.iterdir() if q.is_file() and not q.name.startswith('.')}


@pytest.fixture
def world(tmp_path, runtime):
    return World(tmp_path, ALT, runtime)


@pytest.fixture
def swarm(tmp_path, stub):
    w = World(tmp_path, ALT, stub)
    w.mode = lambda m: (w.root / 'ops' / 'stub-mode.txt').write_text(m)
    doc = p.load(w.plan)
    (w.root / 'ops' / 'stub-ok.json').write_text(json.dumps(dict(
        plan_hash=p.fingerprint(doc, w.plan.parent), task=None, explanation='x', merge_authorized=False,
        tasks={t['id']: dict(state='eligible', explanation=['eligible']) for t in doc['tasks']})))
    return w


def tree(path):
    return {str(q.relative_to(path)): hashlib.sha256(q.read_bytes()).hexdigest()
            for q in sorted(Path(path).rglob('*')) if q.is_file()}


def alive(pid):
    if os.name == 'nt':
        return str(pid) in subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], capture_output=True, text=True).stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


# ----------------------------------------------------------------------------- positives
def test_installed_wheel_identity_matches_source(runtime):
    assert runtime.package_sha256 == v.package_digest(REPO / 'src' / 'agent_workflow_pilot')


def test_read_only_operations_and_write_sets(world):
    before = dict(target=tree(world.root), runtime=tree(Path(world.runtime.package_root).parent),
                  src=sorted(str(q) for q in (REPO / 'src').rglob('*') if q.is_file()))
    r = world.run('program.check')
    assert r['result']['plan_hash'] and r['result']['merge_authorized'] is False
    assert r['read_only'] and r['state_changes'] == [] and r['dispatch'] is False and r['authorizes'] is False
    assert world.run('program.next')['result']['task'] == 't1'
    assert world.run('identity.check', task='t2')['result']['approval']['ref'] == 'user-t2-1'
    # A2 labels accepted; legacy-mode fixture plans use arbitrary milestones.
    assert {t['milestone'] for t in p.load(world.plan)['tasks']} == {'Alpha-1', 'Billing_API'}
    after = dict(target=tree(world.root), runtime=tree(Path(world.runtime.package_root).parent),
                 src=sorted(str(q) for q in (REPO / 'src').rglob('*') if q.is_file()))
    assert before == after          # target, installed runtime (incl. bytecode listing) and source unchanged
    assert world.files() == {}      # read-only: no controller state either
    assert world.calls == 3         # expectation rebuilt for every operation, never cached


@pytest.mark.parametrize('kind', ['default', 'target', 'shadow', 'python_bearing'])
def test_cwd_classes(world, tmp_path, kind):
    cwd = {'default': None, 'target': str(world.root)}.get(kind)
    if kind in ('shadow', 'python_bearing'):
        d = tmp_path / kind
        (d / 'agent_workflow_pilot').mkdir(parents=True)
        (d / 'agent_workflow_pilot' / '__init__.py').write_text(f"open({str(tmp_path / 'HIJACKED')!r}, 'w').write('x')")
        (d / 'json.py').write_text('raise SystemExit(7)')
        (d / 'pyproject.toml').write_text('[project]\nname="x"\nversion="0"\n')
        cwd = str(d)
    assert world.run('program.check', cwd=cwd)['result']['merge_authorized'] is False
    assert not (tmp_path / 'HIJACKED').exists()


@pytest.mark.parametrize('cwd', ['relative', 'missing'])
def test_bad_cwd(world, tmp_path, cwd):
    world.fail('program.check', 'invalid_request', cwd='rel' if cwd == 'relative' else str(tmp_path / 'nope'))


def test_stateful_flow_replay_and_golden_bytes(tmp_path, runtime):
    w = World(tmp_path, PLAN, runtime)
    r = w.prepare()
    assert r['result'] == dict(action='reconcile_native_intent', intent='intent-1', dispatch=False)
    assert r['dispatch'] is False and r['read_only'] is False
    assert sorted(r['state_changes']) == ['b.json', 'b.json.identity.json', 'd.json']
    # Legacy v1 bytes/fingerprints unchanged when produced through the boundary.
    assert json.loads((w.state / 'b.json').read_text()) == dict(
        delivery=str((w.state / 'd.json').resolve()), plan_hash=GOLD_FINGERPRINT, task='t1')
    assert json.dumps(json.loads((w.state / 'd.json').read_text()), sort_keys=True) == GOLD_CHECKPOINT
    snapshot = w.files()
    again = w.prepare()                           # replay: identical result, no new grant, no write
    assert again['result'] == r['result'] and again['state_changes'] == [] and w.files() == snapshot
    assert not (w.state / v.LOCK).exists()
    assert w.run('identity.verify')['result']['binding_sha256'] == hashlib.sha256(snapshot['b.json']).hexdigest()
    assert w.run('program.resume')['result']['task'] == 't1'
    attached = w.run('lifecycle.attach')
    assert attached['state_changes'] == ['d.json'] and attached['result']['lifecycle'] == 'building'
    state = checkpoint.load(w.state / 'd.json')
    assert (state['retries'], state['retry_budget'], state['intent']) == (0, 2, 'intent-1')
    kept = w.files()
    assert w.run('lifecycle.attach')['state_changes'] == [] and w.files() == kept   # receipt replay
    rec = w.run('lifecycle.reconcile', observations=w.obs(t1=dict(
        state='report_ready', head=HEAD, verified_head=HEAD, ref='controller-ref', children_terminal=True,
        draft=True, merged=False, merge_commit=None, target_tip='b' * 40, ancestor_verified=False)))
    assert rec['result']['action'] == 'awaiting_authorization' and rec['result']['merge_authorized'] is False
    assert rec['state_changes'] == [] and w.files() == kept


def test_stateful_write_set_only_designated_state(world):
    before, installed = tree(world.root), tree(Path(world.runtime.package_root).parent)
    world.prepare()
    world.run('lifecycle.attach')
    assert tree(world.root) == before                      # target checkout never written
    assert tree(Path(world.runtime.package_root).parent) == installed   # runtime incl. bytecode listing unchanged
    assert git(world.root, 'status', '--porcelain') == ''
    assert sorted(world.files()) == ['b.json', 'b.json.identity.json', 'd.json']


def context_args(world):
    ref = tc.reference(world.root, 'ops/tasks/t1.md')
    handoff = json.loads((REPO / 'docs/orchestration/handoffs/example.json').read_text())
    handoff.update(task_id='t1', head=HEAD)
    for row in handoff['tests'] + handoff['evidence']:
        row['head'] = HEAD
    doc = dict(schema=tc.SCHEMA, task_id='t1', repo=handoff['repo'], head=HEAD,
               plan_hash=p.fingerprint(p.load(world.plan), world.plan.parent), spec=ref, objective='o',
               scope=['s'], exclusions=['merge'], acceptance=['a'], depends_on=[], owns=['src/a/'], owner='w',
               routing='r', risks=['x'], decisions=['d'], context=[ref], next_action='n', handoff=handoff)
    (world.state / 'ctx.json').write_text(json.dumps(doc))
    return dict(file=str(world.state / 'ctx.json'), plan='ops/roadmap.json', current_head=HEAD, task_id='t1',
                repo=handoff['repo'])


def test_task_context_validation(world):
    ok = context_args(world)
    for bad in (dict(current_head='b' * 40), dict(plan='../x.json'), dict(plan=str(world.plan)),
                dict(file=str(world.root.parent / 'outside.json')), dict(task_id='zz'), dict(repo=''),
                dict(plan='ops/missing.json')):
        with pytest.raises(v.InvocationError):
            world.run('task_context.validate', **{**ok, **bad})
    result = world.run('task_context.validate', **ok)
    assert result['result']['authorizes'] is False and result['state_changes'] == []
    assert world.run('task_context.validate', **ok)['result'] == result['result']



# ----------------------------------------------------------------------------- allowlist / inputs
@pytest.mark.parametrize('op', ['continuation.advance', 'identity.bind', 'program.record', 'onboard',
                                'routing', 'gate', 'python -c print(1)', 'program.check; calc', '', None])
def test_unsupported_and_unknown_operations(world, op):
    with pytest.raises(v.InvocationError) as e:
        v.invoke(world.runtime, world.project, op, dict(plan=str(world.plan)), authority=world.authority,
                 git_dir=GIT_DIR)
    assert e.value.kind == 'unsupported' and world.calls == 0 and not (world.state / v.LOCK).exists()


@pytest.mark.parametrize('extra', [dict(extra='--help'), dict(python='evil'), dict(module='os'), dict(argv=['x']),
                                   dict(cwd='C:/'), dict(env={'A': 'B'}), dict(expect='x.json'), dict(mode='legacy')])
def test_free_arguments_and_overrides_rejected(world, extra):
    with pytest.raises(v.InvocationError) as e:
        v.invoke(world.runtime, world.project, 'program.check', {**world.args('program.check'), **extra},
                 authority=world.authority, git_dir=GIT_DIR)
    assert e.value.kind == 'invalid_request' and world.calls == 0


@pytest.mark.parametrize('op,drop', [('program.check', 'plan'), ('identity.check', 'task'),
                                     ('lifecycle.prepare', 'intent'), ('lifecycle.attach', 'refs')])
def test_missing_arguments(world, op, drop):
    with pytest.raises(v.InvocationError) as e:
        v.invoke(world.runtime, world.project, op, {k: x for k, x in world.args(op).items() if k != drop},
                 authority=world.authority, git_dir=GIT_DIR)
    assert e.value.kind == 'invalid_request'


def test_non_dict_args(world):
    with pytest.raises(v.InvocationError):
        v.invoke(world.runtime, world.project, 'program.check', ['--plan'], authority=world.authority, git_dir=GIT_DIR)


def test_plan_path_domains(world, tmp_path, runtime):
    other = World(tmp_path / 'o', ALT, runtime, name='other')
    world.fail('program.check', 'invalid_request', plan=str(other.plan))                  # other checkout
    world.fail('program.check', 'invalid_request', plan='ops/roadmap.json')                # relative
    world.fail('program.check', 'invalid_request', plan=str(world.root / 'ops' / '..' / '..' / 'x.json'))
    world.fail('program.check', 'invalid_request', plan=str(world.root / 'package.json'))  # not a roadmap
    (world.root / 'ops' / 'bad.json').write_text(json.dumps(dict(ALT, tasks=[dict(ALT['tasks'][0], python='evil')])))
    world.fail('program.check', 'invalid_request', plan=str(world.root / 'ops' / 'bad.json'))  # worker runtime field
    (world.root / 'ops' / 'tasks' / 't1.md').unlink()
    world.fail('program.check', 'invalid_request')                                          # missing spec
    assert world.calls == 0


@pytest.mark.parametrize('name', ['../b.json', 'sub/b.json', '/abs.json', 'C:\\x.json', '..', '.writer.lock',
                                  '.calls', 'b.json.identity.json', 'x' * 80, 'a b.json'])
def test_state_name_redirects(world, name):
    with pytest.raises(v.InvocationError) as e:
        world.prepare(binding=name)
    assert e.value.kind == 'invalid_request' and world.calls == 0 and world.files() == {}


def test_prepare_argument_shapes(world):
    for bad in (dict(delivery='b.json'), dict(task='t2'), dict(scope=[]), dict(scope=['t1', 't1']),
                dict(scope=['nope']), dict(acceptance=[]), dict(acceptance=[1]), dict(intent=' '),
                dict(observations=dict(plan_hash='x', tasks={})), dict(observations=dict(tasks={}))):
        world.fail('lifecycle.prepare', 'invalid_request', **bad)
    assert world.files() == {} and not (world.state / v.LOCK).exists()


def test_attach_reconcile_argument_shapes(world):
    world.prepare()
    for bad in (dict(refs={}), dict(refs=dict(bogus='x')), dict(refs=dict(task='')), dict(refs=['a'])):
        world.fail('lifecycle.attach', 'invalid_request', **bad)
    n = dict(task='n-task', thread='n-thread', status='completed', children_terminal=True, ref='r')
    for bad in (dict(native={**n, 'children_terminal': 'yes'}), dict(native={**n, 'extra': 1}),
                dict(native={k: x for k, x in n.items() if k != 'ref'}), dict(head='abc'), dict(head=None)):
        world.fail('lifecycle.reconcile', 'invalid_request', **bad)


def test_state_dir_must_be_separate_from_checkout(world):
    inside = world.root / 'state'
    inside.mkdir()
    for state in (inside, world.root, world.root.parent):
        world.fail('program.check', 'invalid_request', project=v.Project(
            'proj-b1', str(world.root), str(world.root / '.git'), str(state), 'attempt-1'))


@pytest.mark.parametrize('field,value', [('project_id', 'Bad Id!'), ('writer', ''), ('checkout', 'rel'),
                                         ('common_dir', 'rel'), ('state_dir', 'rel')])
def test_project_validation(world, field, value):
    d = dict(project_id='proj-b1', checkout=str(world.root), common_dir=str(world.root / '.git'),
             state_dir=str(world.state), writer='w')
    d[field] = value
    world.fail('program.check', 'invalid_request', project=v.Project(**d))


def test_symlink_state_file_rejected(world):
    world.prepare()
    link = world.state / 'link.json'
    try:
        link.symlink_to(world.state / 'b.json')
    except OSError:
        pytest.skip('symlink creation needs privilege on this host (not verified here)')
    world.fail('identity.verify', 'state', binding='link.json')


# ----------------------------------------------------------------------------- runtime identity
def test_runtime_pin_negatives(world, runtime, tmp_path):
    py, root, sha = runtime.python, runtime.package_root, runtime.package_sha256
    bad = {
        'relative python': v.Runtime('python', '3.12', root, sha, 'p'),
        'missing python': v.Runtime(str(tmp_path / 'nope.exe'), '3.12', root, sha, 'p'),
        'relative root': v.Runtime(py, '3.12', 'site-packages', sha, 'p'),
        'missing root': v.Runtime(py, '3.12', str(tmp_path / 'nope'), sha, 'p'),
        'minor too old': v.Runtime(py, '3.11', root, sha, 'p'),
        'minor malformed': v.Runtime(py, '3', root, sha, 'p'),
        'minor mismatch': v.Runtime(py, '3.13', root, sha, 'p'),
        'wrong hash': v.Runtime(py, '3.12', root, '0' * 64, 'p'),
        'malformed hash': v.Runtime(py, '3.12', root, 'xyz', 'p'),
        'blank provenance': v.Runtime(py, '3.12', root, sha, ' '),
        'not a runtime': object(),
        # same bytes (pin matches) but the child imports the installed copy elsewhere: location mismatch
        'package root elsewhere': v.Runtime(py, '3.12', str(REPO / 'src' / 'agent_workflow_pilot'), sha, 'p'),
    }
    for label, rt in bad.items():
        try:
            world.run('program.check', runtime=rt)
        except v.InvocationError as e:
            assert e.kind == 'runtime', label
        else:
            pytest.fail('accepted: ' + label)
    assert world.files() == {}


def test_interpreter_without_package_detected(world, tmp_path, runtime):
    bare = venv(tmp_path / 'bare')
    world.fail('program.check', 'runtime', runtime=v.Runtime(bare, '3.12', runtime.package_root,
                                                               runtime.package_sha256, 'bare'))


def test_startup_code_detection_vs_prevention(world, tmp_path, wheel):
    """Classification: package tampering is DETECTED before launch; startup code is NOT PREVENTED."""
    py = install(tmp_path / 'startup' / 'venv', wheel)
    site = Path(package_dir(py)).parent
    marker = site / 'startup-ran.txt'
    (site / 'sitecustomize.py').write_text(f'open({str(marker)!r}, "w").write("ran")')
    good = pin(py)
    assert world.run('program.check', runtime=good)['result']['merge_authorized'] is False
    assert marker.exists()            # harmless startup fixture ran: sitecustomize is a trust assumption
    marker.unlink()
    (Path(good.package_root) / 'graph.py').write_text('# tampered\n', encoding='utf-8')
    world.fail('program.check', 'runtime', runtime=good)
    assert not marker.exists()        # mismatch detected from file bytes before any launch


# ----------------------------------------------------------------------------- authority
@pytest.mark.parametrize('how', ['raises', 'none', 'not_dict', 'bad_schema'])
def test_authority_unavailable_or_invalid(world, how):
    def authority():
        if how == 'raises':
            raise RuntimeError('permission service down')
        return {'none': None, 'not_dict': [], 'bad_schema': {'schema': 'x'}}[how]
    with pytest.raises(v.InvocationError) as e:
        v.invoke(world.runtime, world.project, 'identity.check', world.args('identity.check'), authority=authority,
                 git_dir=GIT_DIR)
    assert e.value.kind == 'authority'


def test_authority_not_callable(world):
    with pytest.raises(v.InvocationError) as e:
        v.invoke(world.runtime, world.project, 'identity.check', world.args('identity.check'),
                 authority=world.expectation(), git_dir=GIT_DIR)
    assert e.value.kind == 'authority'


@pytest.mark.parametrize('status', ['revoked', 'superseded'])
def test_revocation_blocks_next_fresh_operation(world, status):
    assert world.run('identity.check')['result']['authorizes'] is False
    world.mutate = lambda e: e['approvals']['t1'].update(status=status)
    assert 'valid controller approval' in str(world.fail('identity.check', 'authority'))
    world.fail('lifecycle.prepare', 'authority')
    assert world.files() == {}


@pytest.mark.parametrize('change', ['missing', 'scope', 'project', 'operation', 'other_task'])
def test_approval_shapes_block(world, change):
    def mutate(e):
        r = e['approvals']['t1']
        if change == 'missing':
            del e['approvals']['t1']
        elif change == 'scope':
            r['scope'] = ['t2']
        elif change == 'project':
            r['project_id'] = 'proj-other'
        elif change == 'operation':
            r['operation'] = 'merge'
        else:
            r['task'] = 't2'
    world.mutate = mutate
    world.fail('identity.check', 'authority')


def test_scope_needs_every_task_approved_not_roadmap_flags(world):
    world.mutate = lambda e: e['approvals'].pop('t2')
    assert all(t['approved'] for t in p.load(world.plan)['tasks'])      # roadmap booleans alone are insufficient
    world.fail('lifecycle.prepare', 'authority', scope=['t1', 't2'])
    assert world.files() == {}


@pytest.mark.parametrize('field,value', [('project_id', 'proj-other'), ('checkouts', ['/elsewhere/x']),
                                         ('common_dir', '/elsewhere/.git')])
def test_cross_project_root_and_common_dir_blocked(world, field, value):
    world.mutate = lambda e: e.update({field: value})
    world.fail('program.check', 'authority')


@pytest.mark.parametrize('how', ['host', 'repo_name', 'origin_changed', 'no_origin', 'other_host_origin'])
def test_host_and_repo_identity_enforced_by_child(world, how):
    if how == 'host':
        world.mutate = lambda e: e.update(repository=dict(host='git.example.invalid', name='acme/app-fixture'))
    elif how == 'repo_name':
        world.mutate = lambda e: e.update(repository=dict(host='github.com', name='acme/other'))
    elif how == 'origin_changed':
        git(world.root, 'remote', 'set-url', 'origin', 'https://github.com/acme/renamed.git')
    elif how == 'no_origin':
        git(world.root, 'remote', 'remove', 'origin')
    else:
        git(world.root, 'remote', 'set-url', 'origin', 'https://git.example.invalid/acme/app-fixture.git')
    world.fail('identity.check', 'operation')


def test_stale_expectation_after_a2_milestone_change(world):
    world.frozen = world.expectation()          # approval collected before the plan changed
    world.run('identity.check')
    plan = json.loads(world.plan.read_text())
    plan['tasks'][0]['milestone'] = 'Gamma-9'   # milestone edit changes the plan hash (A2)
    world.plan.write_text(json.dumps(plan))
    world.fail('identity.check', 'operation')
    world.fail('lifecycle.prepare', 'operation')
    assert world.files() == {} and not (world.state / v.LOCK).exists()   # clean rejection: nothing written


def test_wrong_project_identical_plan_rejected(world, tmp_path, runtime):
    world.prepare()
    twin = World(tmp_path / 't', ALT, runtime, name='twin')
    for name in ('b.json', 'b.json.identity.json', 'd.json'):
        shutil.copy(world.state / name, twin.state / name)
    twin.fail('identity.verify', 'state')            # delivery path references the other project's state


def test_authority_called_once_per_launching_operation(world):
    for _ in range(3):
        world.run('program.check')
    assert world.calls == 3


# ----------------------------------------------------------------------------- state fail-closed
def test_missing_binding_or_envelope_blocks_without_repair(world):
    world.fail('identity.verify', 'state')
    world.fail('lifecycle.attach', 'state')
    world.prepare()
    marker = world.state / 'b.json.identity.json'
    kept = marker.read_bytes()
    marker.unlink()
    for op in ('identity.verify', 'program.resume', 'lifecycle.attach', 'lifecycle.reconcile', 'lifecycle.prepare'):
        world.fail(op, 'state')
    assert not marker.exists()                      # prepare replay did not recreate the envelope
    marker.write_bytes(kept)
    (world.state / 'b.json').unlink()
    world.fail('lifecycle.prepare', 'state')        # envelope without binding
    assert not (world.state / 'b.json').exists()


@pytest.mark.parametrize('cut', [0, 1, 20, -1])
def test_torn_envelope_blocks_and_is_retained(world, cut):
    world.prepare()
    marker = world.state / 'b.json.identity.json'
    data = marker.read_bytes()
    torn = data[:cut] if cut >= 0 else data[:-1]
    marker.write_bytes(torn)
    for op in ('identity.verify', 'program.resume', 'lifecycle.attach', 'lifecycle.prepare'):
        world.fail(op, 'state')
    assert marker.read_bytes() == torn


def test_nested_delivery_escape_and_tampered_checkpoint_blocked(world):
    world.prepare()
    b = world.state / 'b.json'
    binding = json.loads(b.read_text())
    outside = world.root / 'ops' / 'delivery-copy.json'
    shutil.copy(world.state / 'd.json', outside)
    b.write_text(json.dumps(dict(binding, delivery=str(outside))))
    for op in ('identity.verify', 'lifecycle.attach', 'program.resume'):
        world.fail(op, 'state')
    b.write_text(json.dumps(binding))
    good = (world.state / 'd.json').read_bytes()
    (world.state / 'd.json').write_text('{"half": ')
    world.fail('lifecycle.attach', 'state')
    (world.state / 'd.json').write_bytes(good)
    assert world.run('lifecycle.attach')['result']['lifecycle'] == 'building'


def test_conflicting_replay_and_consumed_state_rejected_cleanly(world):
    world.prepare()
    world.fail('lifecycle.prepare', 'operation', intent='intent-2')
    world.fail('lifecycle.prepare', 'operation', acceptance=['different'])
    world.run('lifecycle.attach')
    kept = world.files()
    world.fail('lifecycle.attach', 'operation', refs=dict(task='other', thread='n-thread'))
    assert world.files() == kept and not (world.state / v.LOCK).exists()   # no reset, no lock, same bytes
    assert world.run('identity.verify')['result']['task'] == 't1'


def test_owner_and_writer_assertions(world):
    world.prepare()
    for project in (v.Project('proj-b1', str(world.root), str(world.root / '.git'), str(world.state), 'attempt-2'),
                    v.Project('proj-zzz', str(world.root), str(world.root / '.git'), str(world.state), 'attempt-1')):
        assert 'another project or writer' in str(world.fail('identity.verify', 'state', project=project))


def test_existing_lock_blocks_everything_and_is_not_removed(world):
    world.prepare()
    lock = world.state / v.LOCK
    lock.write_text('{"state": "ambiguous"}')
    for op in ('program.check', 'identity.verify', 'lifecycle.attach', 'lifecycle.prepare'):
        assert 'lock' in str(world.fail(op, 'state'))
    assert lock.read_text() == '{"state": "ambiguous"}'


def test_per_call_files_are_cleaned_after_clean_outcomes(world):
    world.run('program.check')
    world.fail('identity.check', 'operation', task='t9') if False else None
    assert list((world.state / v.CALLS).iterdir()) == []


# ----------------------------------------------------------------------------- process machinery
@pytest.mark.parametrize('mode,kind,needle', [
    ('nonjson', 'output', 'JSON'), ('array', 'output', 'object'), ('dup', 'output', 'JSON'),
    ('badutf8', 'output', 'JSON'), ('authorizes', 'output', 'schema'), ('nonzero', 'process', 'exit 3'),
    ('reject', 'operation', 'exit 1'), ('unknown-mode', 'process', 'exit 9')])
def test_output_and_exit_contracts(swarm, mode, kind, needle):
    swarm.mode(mode)
    err = swarm.fail('program.check', kind)
    assert needle in str(err)
    assert not err.ambiguous and not (swarm.state / v.LOCK).exists()


def test_stub_ok_baseline(swarm):
    swarm.mode('ok')
    assert swarm.run('program.check')['result']['merge_authorized'] is False


def test_diagnostics_are_sanitized_and_bounded(swarm):
    swarm.mode('reject')
    msg = str(swarm.fail('program.check', 'operation'))
    for leak in ('secret-value', str(swarm.state), str(swarm.root), 'user-t1-1'):
        assert leak not in msg
    assert len(msg) < 300


@pytest.mark.parametrize('mode', ['flood_out', 'flood_err'])
def test_stream_flood_bounded_and_cleaned(swarm, mode):
    swarm.mode(mode)
    start = time.monotonic()
    err = swarm.fail('program.check', 'process', timeout=20)
    assert 'output_limit' in str(err) and time.monotonic() - start < 15
    pid = int((swarm.root / 'ops' / 'stub-pid.txt').read_text())
    time.sleep(1)
    assert not alive(pid)


def test_timeout_kills_and_returns_promptly(swarm):
    swarm.mode('sleep')
    start = time.monotonic()
    err = swarm.fail('program.check', 'process', timeout=2)
    assert 'timeout' in str(err) and time.monotonic() - start < 14
    pid = int((swarm.root / 'ops' / 'stub-pid.txt').read_text())
    time.sleep(1)
    assert not alive(pid)                           # best-effort tree kill observed here; not a guarantee
    assert not (swarm.state / v.LOCK).exists()      # read-only timeout with unchanged state is not ambiguous


def holders(swarm):
    f = swarm.root / 'ops' / 'stub-holders.txt'
    return [int(x) for x in f.read_text().split()] if f.exists() else []


def reap_holders(swarm):
    """Fixture-owned cleanup of ONLY the pids the stub recorded; always runs."""
    for pid in holders(swarm):
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True)
        else:
            try:
                os.kill(pid, 9)
            except OSError:
                pass


def handle_count():
    if os.name == 'nt':
        import ctypes
        n = ctypes.c_ulong()
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        assert k.GetProcessHandleCount(k.GetCurrentProcess(), ctypes.byref(n))
        return n.value
    return len(os.listdir('/proc/self/fd' if os.path.isdir('/proc/self/fd') else '/dev/fd'))


def test_inherited_pipe_does_not_hang_cleanup(swarm):
    swarm.mode('holder')
    try:
        start = time.monotonic()
        err = swarm.fail('program.check', 'process', timeout=20)
        assert 'pipe_held' in str(err) and time.monotonic() - start < 12
    finally:
        reap_holders(swarm)


def test_persistent_pipe_holder_does_not_accumulate_readers_or_handles(swarm):
    """B1-P2-02: a descendant that keeps the inherited pipes open after the direct child exits."""
    swarm.mode('holder')
    try:
        swarm.fail('program.check', 'process', timeout=20)           # warm-up: lazy imports, first handles
        threads, handles = threading.active_count(), handle_count()
        for _ in range(4):
            assert 'pipe_held' in str(swarm.fail('program.check', 'process', timeout=20))
        assert len(holders(swarm)) == 5                              # five real holders were created
        assert threading.active_count() <= threads, 'reader threads accumulated'
        assert handle_count() <= handles + 2, 'process handles accumulated'
    finally:
        reap_holders(swarm)


def test_unauthorized_write_by_read_only_operation_is_ambiguous(swarm):
    swarm.mode('rogue')
    err = swarm.fail('program.check', 'state')
    assert err.ambiguous and (swarm.state / 'rogue.txt').exists() and (swarm.state / v.LOCK).exists()
    assert 'lock' in str(swarm.fail('program.check', 'state'))          # blocked until manual reconciliation


@pytest.mark.parametrize('mode', ['write_sleep', 'write_fail', 'rogue'])
def test_stateful_ambiguity_retains_state_and_blocks(swarm, mode):
    swarm.mode(mode)
    kind = {'write_sleep': 'process', 'write_fail': 'operation', 'rogue': 'state'}[mode]
    err = swarm.fail('lifecycle.prepare', kind, timeout=3)
    assert err.ambiguous and (swarm.state / v.LOCK).exists()
    if mode != 'rogue':
        assert (swarm.state / 'b.json').read_text() == '{"half": '        # partial state retained, not repaired
    before = swarm.files()
    swarm.fail('lifecycle.prepare', 'state')                               # replay is blocked, never blind-retried
    swarm.fail('lifecycle.attach', 'state')
    assert swarm.files() == before


def test_stateful_timeout_does_not_claim_isolation(swarm):
    swarm.mode('write_sleep')
    assert 'effects unknown' in str(swarm.fail('lifecycle.prepare', 'process', timeout=2))


def test_exclusive_writer_lock_released_after_clean_stateful_call(world):
    world.prepare()
    assert not (world.state / v.LOCK).exists()
    assert json.loads((world.state / v.OWNER).read_text()) == dict(project_id='proj-b1', writer='attempt-1')


@pytest.mark.parametrize('timeout', [0, -1, 601, '5', None, True])
def test_timeout_bounds(world, timeout):
    world.fail('program.check', 'invalid_request', timeout=timeout)


def test_git_directory_must_hold_git(world, tmp_path):
    for d in (str(tmp_path), 'rel'):
        with pytest.raises(v.InvocationError) as e:
            v.invoke(world.runtime, world.project, 'program.check', world.args('program.check'),
                     authority=world.authority, git_dir=d)
        assert e.value.kind == 'runtime'


# ----------------------------------------------------------------------------- B1-P2-01 result schemas
REPORT = dict(state='report_ready', head=HEAD, verified_head=HEAD, ref='controller-ref', children_terminal=True,
              draft=True, merged=False, merge_commit=None, target_tip='b' * 40, ancestor_verified=False)


def ready(world, op):
    """Untampered setup for `op`; returns the extra run() arguments."""
    if op in ('identity.verify', 'program.resume', 'lifecycle.attach', 'lifecycle.reconcile'):
        world.prepare()
    if op == 'lifecycle.reconcile':
        world.run('lifecycle.attach')
        return dict(observations=world.obs(t1=REPORT))
    return context_args(world) if op == 'task_context.validate' else {}


def tamper(monkeypatch, mutate):
    """Rewrite only the operational CLI's stdout (never the identity probe) after it really ran."""
    real = v._run

    def run(argv, cwd, env, timeout):
        code, out, err, problem = real(argv, cwd, env, timeout)
        if '-m' in argv and not argv[argv.index('-m') + 1].endswith('invocation'):
            doc = json.loads(out)
            out = json.dumps(mutate(doc) or doc).encode()
        return code, out, err, problem
    monkeypatch.setattr(v, '_run', run)


def setkey(**kw):
    return lambda r: r.update(kw)


def setin(key, **kw):
    return lambda r: r[key].update(kw)


def drop(key):
    return lambda r: r.pop(key)


def task(**kw):
    return lambda r: r['tasks']['t1'].update(kw)


IDENTITY = [
    ('null_identity', setkey(project_id=None, repository=None, task=None)), ('null_approval', setkey(approval=None)),
    ('null_checkout', setkey(checkout=None)), ('approval_extra', setin('approval', x=1)),
    ('approval_ref', setin('approval', ref='user-t9-9')), ('approval_status', setin('approval', status='revoked')),
    ('approval_bool_revision', setin('approval', revision=True)), ('approval_missing', lambda r: r['approval'].pop('ref')),
    ('repository', setkey(repository=dict(host='github.com', name='evil/other'))),
    ('project', setkey(project_id='proj-other')), ('task', setkey(task='t2')), ('extra', setkey(extra=1)),
    ('checkout_root', setin('checkout', root='/elsewhere')), ('checkout_origin', setin('checkout', origin=None)),
    ('authorizes', setkey(authorizes=True)), ('merge', setkey(merge_authorized=1)),
]
PROGRAM = [
    ('entry_scalar', lambda r: r['tasks'].update(t1=5)), ('entry_none', lambda r: r['tasks'].update(t2=None)),
    ('entry_no_explanation', lambda r: r['tasks']['t1'].pop('explanation')), ('entry_extra', task(x=1)),
    ('entry_state', task(state='bogus')), ('entry_explanation_str', task(explanation='x')),
    ('entry_explanation_items', task(explanation=[1])), ('entry_explanation_empty', task(explanation=[])),
    ('extra_task', lambda r: r['tasks'].update(zz=dict(state='eligible', explanation=['eligible']))),
    ('missing_task', lambda r: r['tasks'].pop('t2')), ('tasks_list', setkey(tasks=[])),
    ('plan_hash', setkey(plan_hash='0' * 64)), ('task_unknown', setkey(task='zz')),
    ('explanation_type', setkey(explanation=['x'])), ('extra', setkey(extra=1)), ('authority', setkey(merge_authorized=None)),
]
CASES = (
    [('identity.check', n, f) for n, f in IDENTITY]
    + [('identity.verify', n, f) for n, f in IDENTITY + [('sha', setkey(binding_sha256='0' * 64)),
                                                         ('sha_missing', drop('binding_sha256'))]]
    + [(op, n, f) for op in ('program.check', 'program.next', 'program.resume') for n, f in PROGRAM]
    + [('task_context.validate', n, f) for n, f in [
        ('context_null', setkey(context=None)), ('context_empty', setkey(context={})),
        ('context_head', setin('context', head='b' * 40)), ('context_task', setin('context', task_id='t2')),
        ('context_extra', setin('context', zz=1)), ('context_field', lambda r: r['context'].pop('objective')),
        ('hash', setkey(context_hash='0' * 64)), ('hash_type', setkey(context_hash=1)), ('extra', setkey(extra=1)),
        ('authorizes', setkey(authorizes=None))]]
    + [('lifecycle.prepare', n, f) for n, f in [
        ('intent', setkey(intent='other')), ('action', setkey(action='blocked')), ('extra', setkey(extra=1)),
        ('dispatch', setkey(dispatch=0)), ('missing', drop('intent'))]]
    + [('lifecycle.attach', n, f) for n, f in [
        ('task_key', setkey(task_key='t2')), ('refs', setkey(refs={})), ('refs_value', setin('refs', task='other')),
        ('lifecycle', setkey(lifecycle='planned')), ('extra', setkey(extra=1)), ('events', setkey(events=None))]]
    + [('lifecycle.reconcile', n, f) for n, f in [
        ('slot', setkey(slot='free')), ('action', setkey(action='go')), ('reason', setkey(reason=5)),
        ('extra', setkey(extra=1)), ('state', setkey(state='bogus')), ('no_state', drop('state')),
        ('merge', setkey(merge_authorized=True)), ('task', setkey(task='t1')),
        ('variant', lambda r: r.update(action='continue', slot='retired', task=5))]])


@pytest.mark.parametrize('op,name,mutate', CASES, ids=[f'{o}-{n}' for o, n, _ in CASES])
def test_malformed_nested_results_are_output_errors(world, monkeypatch, op, name, mutate):
    extra = ready(world, op)
    tamper(monkeypatch, mutate)
    world.fail(op, 'output', **extra)


@pytest.mark.parametrize('op', ['program.check', 'program.next', 'program.resume', 'identity.check',
                                'identity.verify', 'task_context.validate', 'lifecycle.prepare',
                                'lifecycle.attach', 'lifecycle.reconcile'])
def test_genuine_results_pass_the_closed_schemas(world, op):
    assert world.run(op, **ready(world, op))['operation'] == op


def test_reconcile_continue_and_stop_variants_validate(world):
    world.prepare()
    world.run('lifecycle.attach')
    done = dict(REPORT, state='delivered', draft=False, merged=True, merge_commit='c' * 40, ancestor_verified=True)
    r = world.run('lifecycle.reconcile', observations=world.obs(t1=done))['result']
    assert r['slot'] == 'retired' and r['action'] in ('continue', 'stop') and r['merge_authorized'] is False
