"""B1 trusted controller invocation boundary: named operations, fixed argv, bounded child.

Runs ONE existing controller module CLI per call in a fresh process:
`<trusted absolute python> -I -B -X utf8 -m <fixed module> <fixed subcommand> ...`,
shell=False, controller-chosen cwd, scrubbed environment (approved Git directory on PATH).

Trust limits (read before relying on it):
- Startup is already trusted. The interpreter, its base install, site-packages/.pth,
  sitecustomize, DLLs/extensions, existing bytecode, Git and the toolchain are controller
  trust assumptions. The pre-check (package content hash computed by reading files, plus a
  child identity report) only detects MISMATCHES before the operational CLI; importing the
  candidate to report its location does not authenticate an untrusted interpreter. -I/-B
  mitigate cwd/PYTHON*/bytecode-write influence; they are not a sandbox.
- Expectation/approval and ownership inputs are controller ASSERTIONS. This module checks
  consistency; it authenticates nobody and authorizes nothing (results carry
  authorizes=false, merge_authorized=false, dispatch=false). The `authority` callable must
  build the expectation freshly from independently current controller permission on every
  call; nothing is cached. A revocation inside one call's window is an accepted race.
- State directories and the writer lock are bookkeeping, not OS isolation. A timeout or
  kill does not prove "no effects" or tree-wide termination (best-effort tree kill only);
  stateful ambiguity keeps the lock and state for manual reconciliation. Never auto-repaired.
No provisioning, publishing, rollback, dispatch, merge or free-form argv exists here.
"""
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from agent_workflow_pilot import graph, handoff, task_context
from agent_workflow_pilot.controller import checkpoint, identity, program

OUT_LIMIT = handoff.MAX_BYTES
ERR_LIMIT = 16 * 1024
HEX64 = re.compile(r'[0-9a-f]{64}')
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
MINOR = re.compile(r'3\.\d{1,2}')
LOCK, OWNER, CALLS = '.writer.lock', '.owner.json', '.calls'
RESERVED = {LOCK, OWNER, CALLS}
# name -> (module, subcommand, required args, optional args, stateful)
OPS = {
    'program.check': ('program', 'check', {'plan'}, set(), False),
    'program.next': ('program', 'next', {'plan'}, {'observations'}, False),
    'program.resume': ('program', 'resume', {'plan', 'binding'}, {'observations'}, False),
    'identity.check': ('identity', 'check', {'plan', 'task'}, set(), False),
    'identity.verify': ('identity', 'verify', {'plan', 'binding'}, set(), False),
    'task_context.validate': ('task_context', None, {'file', 'plan', 'current_head', 'task_id', 'repo'}, set(), False),
    'lifecycle.prepare': ('lifecycle', 'prepare', {'plan', 'binding', 'delivery', 'observations', 'scope', 'task',
                                                   'acceptance', 'intent'}, set(), True),
    'lifecycle.attach': ('lifecycle', 'attach', {'plan', 'binding', 'observations', 'scope', 'refs'}, set(), True),
    'lifecycle.reconcile': ('lifecycle', 'reconcile', {'plan', 'binding', 'observations', 'scope', 'native', 'head'},
                            set(), False),
}
# Rejected on purpose (exact blockers in docs/program/invocation.md).
UNSUPPORTED = ('program.record', 'identity.bind', 'continuation.advance', 'onboard', 'routing', 'gate')


class InvocationError(Exception):
    """Sanitized, bounded failure. `ambiguous`: stateful outcome unknown; state/lock retained."""
    def __init__(self, kind, message, ambiguous=False):
        super().__init__(f'{kind}: {message}')
        self.kind, self.ambiguous = kind, ambiguous


@dataclass(frozen=True)
class Runtime:
    """Controller-provisioned runtime pin. provenance is a reference, never verified here."""
    python: str          # absolute interpreter path
    minor: str           # e.g. '3.12'
    package_root: str    # absolute directory of the installed agent_workflow_pilot package
    package_sha256: str  # package_digest() of that directory
    provenance: str      # installation provenance reference


@dataclass(frozen=True)
class Project:
    project_id: str
    checkout: str    # approved target checkout root (absolute)
    common_dir: str  # approved Git common dir (absolute)
    state_dir: str   # controller-owned, outside the checkout (absolute, existing)
    writer: str      # exclusive-writer assertion (controller attempt id)


def _bad(message, kind='invalid_request'):
    raise InvocationError(kind, message)


def _abs(value, what, kind='invalid_request'):
    if not isinstance(value, str) or not value or '\x00' in value or not os.path.isabs(value):
        _bad(f'{what} must be an absolute path', kind)
    return value


def _real(value):
    return Path(os.path.realpath(value))


def _text(value, what, high=200):
    if not isinstance(value, str) or not value.strip() or len(value) > high or not value.isprintable():
        _bad(f'invalid {what}')
    return value


def package_digest(root):
    """Content identity of the package (*.py + py.typed, sorted path+bytes). Reads files only."""
    root = Path(root)
    h = hashlib.sha256()
    for f in sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                    and (p.suffix == '.py' or p.name == 'py.typed')):
        h.update(f.relative_to(root).as_posix().encode() + b'\0' + f.read_bytes() + b'\0')
    return h.hexdigest()


# --------------------------------------------------------------------------- process
def _kill(proc):
    try:
        if os.name == 'nt':
            exe = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'taskkill.exe'
            subprocess.run([str(exe), '/PID', str(proc.pid), '/T', '/F'], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        else:
            os.killpg(proc.pid, 9)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def _drain(streams, sinks, limits):
    """One nonblocking pass over the open pipes. Returns True when a limit was exceeded.

    EOF (empty read) and BlockingIOError/None (no data yet) are the only benign outcomes. Any other
    OSError/ValueError is a COLLECTION FAILURE and propagates: it must never look like EOF."""
    over = False
    for s in list(streams):
        try:
            chunk = s.read(65536)
        except BlockingIOError:
            continue
        if chunk is None:
            continue
        if not chunk:
            streams.discard(s)
            continue
        room = limits[s] - len(sinks[s])
        sinks[s].extend(chunk[:room])
        over = over or len(chunk) > room
    return over


def _run(argv, cwd, env, timeout):
    """Bounded collection by NONBLOCKING POLLING in the caller's thread; returns (code, stdout, stderr, problem).

    problem is None, 'timeout', 'output_limit', 'pipe_held' (a descendant kept a pipe open after the
    direct child exited), 'read_error' / 'setup_error' (pipe configuration or collection failed: the
    capture is incomplete and is never accepted) or 'unreaped'. No reader threads exist, so nothing
    can outlive the call; both pipe ends are always closed here (os.set_blocking supports pipes on Windows since Python 3.12).
    Best-effort tree kill only: after the direct child is gone a Windows descendant cannot be found by
    PID tree, so a surviving holder is NOT guaranteed to be stopped. No tree-isolation claim.
    """
    try:
        proc = subprocess.Popen(argv, shell=False, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                                start_new_session=(os.name != 'nt'))
    except (OSError, ValueError):
        raise InvocationError('process', 'could not start runtime') from None
    streams = {proc.stdout, proc.stderr}
    sinks = {proc.stdout: bytearray(), proc.stderr: bytearray()}
    limits = {proc.stdout: OUT_LIMIT, proc.stderr: ERR_LIMIT}
    problem = None
    try:
        try:
            for s in streams:
                os.set_blocking(s.fileno(), False)
        except (OSError, ValueError):
            problem = 'setup_error'
        start = time.monotonic()
        deadline, exited = start + timeout, None
        while problem is None:
            try:
                if _drain(streams, sinks, limits):
                    problem = 'output_limit'
            except Exception:                  # collection failure is NOT EOF: incomplete capture, never success
                problem = 'read_error'
            now = time.monotonic()
            if problem is None and proc.poll() is None and now >= deadline:
                problem = 'timeout'
            if problem is None and proc.poll() is not None:
                exited = exited or now
                if not streams:
                    break
                if now - exited >= 2:      # grace for the last bytes, then a descendant is holding a pipe
                    problem = 'pipe_held'
            if problem:
                break
            time.sleep(0.01)
        if problem:
            _kill(proc)                    # best effort; also for pipe_held (works where the group persists)
    finally:
        if proc.poll() is None:            # any exit path (including unexpected errors): bounded kill, wait, close
            _kill(proc)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            problem = problem or 'unreaped'
        for s in (proc.stdout, proc.stderr):
            try:
                s.close()
            except (OSError, ValueError):
                pass
    return proc.returncode, bytes(sinks[proc.stdout]), bytes(sinks[proc.stderr]), problem


def _env(git_dir, tmp):
    env = {'PATH': git_dir, 'TEMP': tmp, 'TMP': tmp, 'TMPDIR': tmp}
    if os.name == 'nt':
        root = os.environ.get('SystemRoot')
        if not root:
            _bad('SystemRoot is required on Windows', 'runtime')
        env['SystemRoot'] = root
    return env


def _argv(runtime, module, tail):
    name = 'agent_workflow_pilot.task_context' if module == 'task_context' else f'agent_workflow_pilot.controller.{module}'
    return [runtime.python, '-I', '-B', '-X', 'utf8', '-m', name, *tail]


def _json(raw, what):
    try:
        value = handoff.parse(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise InvocationError('output', f'{what} is not strict bounded UTF-8 JSON') from None
    if not isinstance(value, dict):
        raise InvocationError('output', f'{what} is not an object')
    return value


# --------------------------------------------------------------------------- runtime
def check_runtime(runtime, git_dir, cwd, timeout=15.0):
    try:
        return _check_runtime(runtime, git_dir, cwd, timeout)
    except InvocationError as error:
        if error.kind == 'invalid_request':      # every malformed pin field is a runtime failure
            raise InvocationError('runtime', str(error).split(': ', 1)[-1]) from None
        raise


def _check_runtime(runtime, git_dir, cwd, timeout):
    """Detect mismatches (not authenticate) BEFORE the operational CLI. Returns identity facts."""
    if not isinstance(runtime, Runtime):
        _bad('runtime must be a Runtime', 'runtime')
    py, root = _abs(runtime.python, 'runtime python', 'runtime'), _abs(runtime.package_root, 'package root', 'runtime')
    if not Path(py).is_file() or not Path(root).is_dir():
        _bad('runtime interpreter or package root missing', 'runtime')
    if not isinstance(runtime.minor, str) or not MINOR.fullmatch(runtime.minor) or int(runtime.minor[2:]) < 12:
        _bad('runtime minor must be 3.12 or newer', 'runtime')
    if not isinstance(runtime.package_sha256, str) or not HEX64.fullmatch(runtime.package_sha256):
        _bad('invalid package pin', 'runtime')
    _text(runtime.provenance, 'provenance reference')
    if package_digest(root) != runtime.package_sha256:
        _bad('package content differs from pin', 'runtime')
    code, out, _, problem = _run(_argv(runtime, 'invocation', []), cwd, _env(git_dir, cwd), timeout)
    if problem or code != 0:
        _bad('runtime identity probe failed', 'runtime')
    seen = _json(out, 'identity report')
    version, package = seen.get('version'), seen.get('package')
    if (set(seen) != {'version', 'package'} or not isinstance(version, list) or len(version) != 3
            or any(type(v) is not int for v in version) or not isinstance(package, str)):
        _bad('malformed identity report', 'runtime')
    if f'{version[0]}.{version[1]}' != runtime.minor:
        _bad('runtime minor differs from pin', 'runtime')
    try:
        same = os.path.samefile(package, root)
    except OSError:
        same = False
    if not same:
        _bad('package imported from a location other than the pinned root', 'runtime')
    return dict(version='.'.join(map(str, version)), package_sha256=runtime.package_sha256,
                provenance=runtime.provenance)


# --------------------------------------------------------------------------- project/state
def _project(project):
    if not isinstance(project, Project):
        _bad('project must be a Project')
    if not isinstance(project.project_id, str) or not handoff.SLUG.fullmatch(project.project_id):
        _bad('invalid project id')
    _text(project.writer, 'writer assertion')
    paths = {k: _real(_abs(getattr(project, k), k)) for k in ('checkout', 'common_dir', 'state_dir')}
    for k in ('checkout', 'state_dir'):
        if not paths[k].is_dir():
            _bad(f'{k} is not a directory')
    a, b = paths['checkout'], paths['state_dir']
    if a == b or a.is_relative_to(b) or b.is_relative_to(a):
        _bad('state directory must be outside (and not contain) the approved checkout')
    return paths


def _state_name(project_paths, name):
    if not isinstance(name, str) or not NAME.fullmatch(name) or name in RESERVED or name.endswith(identity.MARKER):
        _bad('invalid state file name')
    path = project_paths['state_dir'] / name
    if path.is_symlink():
        _bad('state file must not be a link', 'state')
    return path


def _claim_owner(project, paths):
    owner = paths['state_dir'] / OWNER
    want = dict(project_id=project.project_id, writer=project.writer)
    try:
        with open(owner, 'x', encoding='utf-8') as f:
            json.dump(want, f, sort_keys=True)
    except FileExistsError:
        try:
            have = json.loads(owner.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            have = None
        if have != want:
            raise InvocationError('state', 'state directory belongs to another project or writer') from None


def _snapshot(state_dir):
    snap = {}
    for p in sorted(state_dir.iterdir()):
        if p.name in RESERVED:
            continue
        snap[p.name] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() and not p.is_symlink() else 'non-file'
    return snap


def _changed(before, after):
    return {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}


def _check_pair(paths, binding, stateful_create, task=None, delivery=None):
    """Existing binding+envelope pair must be complete and well-formed; never repaired."""
    b = _state_name(paths, binding)
    m = Path(str(b) + identity.MARKER)
    if m.is_symlink():
        _bad('envelope must not be a link', 'state')
    if stateful_create and not b.exists() and not m.exists():
        return
    if not b.exists() or not m.exists():
        _bad('binding/envelope pair incomplete; manual reconciliation required (no repair)', 'state')
    try:
        env = identity.load(m)
        graph._fields(env, ('schema', 'project_id', 'repository', 'task', 'plan_hash', 'spec_sha256',
                            'binding_sha256', 'approval_ref'), 'envelope')
        value = program.load(b)
        graph._fields(value, ('plan_hash', 'task', 'delivery'), 'binding')
        d = _real(value['delivery'])
        if d.parent != paths['state_dir'] or not d.is_file() or d.is_symlink():
            _bad('binding delivery must be a regular file in the controller state directory', 'state')
        if checkpoint.load(d)['task_key'] != value['task'] or env['task'] != value['task']:
            _bad('binding/delivery/envelope identity mismatch', 'state')
        if delivery is not None and d != _state_name(paths, delivery):
            _bad('existing binding references a different delivery', 'state')
    except InvocationError:
        raise
    except (ValueError, OSError, KeyError, TypeError):
        raise InvocationError('state', 'binding, delivery or identity envelope is missing, torn or invalid; '
                                       'manual reconciliation required (no repair)') from None
    return d


# --------------------------------------------------------------------------- authority
def _authority(project, paths, authority, tasks):
    if not callable(authority):
        _bad('an authority callable is required', 'authority')
    try:
        exp = identity.expectation(copy.deepcopy(authority()))   # constructed fresh, every call
    except Exception:   # the authority source is arbitrary controller code; any failure blocks
        raise InvocationError('authority', 'current controller expectation missing or invalid') from None
    ok = exp['project_id'] == project.project_id and identity._same(paths['common_dir'], exp['common_dir']) \
        and any(identity._same(paths['checkout'], c) for c in exp['checkouts'])
    if not ok:
        raise InvocationError('authority', 'expectation is not for this project, checkout or common directory')
    for task in tasks:
        r = exp['approvals'].get(task)
        if r is None or r['status'] != 'valid' or task not in r['scope'] or r['project_id'] != project.project_id:
            raise InvocationError('authority', f'no current valid controller approval for task {task!r}'[:100])
    return exp


# --------------------------------------------------------------------------- inputs
def _plan(paths, plan):
    real = _real(_abs(plan, 'plan'))
    if real.suffix != '.json' or not real.is_file() or not real.is_relative_to(paths['checkout']):
        _bad('plan must be a JSON file inside the approved checkout')
    try:
        doc = program.load(real)
        program.validate(doc, real.parent)
    except (ValueError, OSError, TypeError, KeyError):
        raise InvocationError('invalid_request', 'plan or task specification invalid') from None
    return doc


def _scope(doc, scope):
    ids = {t['id'] for t in doc['tasks']}
    if not isinstance(scope, list) or not scope or len(set(scope)) != len(scope) or len(scope) > 20 \
            or any(not isinstance(s, str) or s not in ids for s in scope):
        _bad('scope must be a unique nonempty list of roadmap task ids')
    return scope


def _list(value, what):
    if not isinstance(value, list) or not 1 <= len(value) <= 20:
        _bad(f'{what} must be a short nonempty list')
    return [_text(v, what, 1000) for v in value]


def _observations(value):
    if not isinstance(value, dict) or set(value) != {'plan_hash', 'tasks'} or not isinstance(value['tasks'], dict) \
            or not isinstance(value['plan_hash'], str) or not HEX64.fullmatch(value['plan_hash']):
        _bad('observations must be {plan_hash, tasks}')
    return value


def _head(value):
    if not isinstance(value, str) or not (handoff.SHA.fullmatch(value) or HEX64.fullmatch(value)):
        _bad('full head required')
    return value


def _within(paths, file):
    real = _real(_abs(file, 'file'))
    if not real.is_file() or not any(real.is_relative_to(paths[k]) for k in ('checkout', 'state_dir')):
        _bad('context file must be a file inside the checkout or controller state directory')
    return real


def _build(op, a, paths, doc, call):
    """Validate operation arguments; returns (argv tail, tasks needing approval, bindings, writes)."""
    plan = None if op == 'task_context.validate' else str(_real(a['plan']))
    proj = ['--mode', 'project', '--expect', str(call / 'expect.json')]
    obs = []
    if a.get('observations') is not None:
        (call / 'obs.json').write_text(json.dumps(_observations(a['observations']), sort_keys=True), encoding='utf-8')
        obs = ['--observations', str(call / 'obs.json')]
    elif op.startswith('lifecycle.'):
        _bad('observations required')
    if op == 'program.check':
        return ['--plan', plan, *proj], [], None, set()
    if op == 'program.next':
        return ['--plan', plan, *obs, *proj], [], None, set()
    if op == 'identity.check':
        if a['task'] not in {t['id'] for t in doc['tasks']}:
            _bad('unknown task')
        return ['--plan', plan, '--expect', str(call / 'expect.json'), '--task', a['task']], [a['task']], None, set()
    if op == 'identity.verify':
        _check_pair(paths, a['binding'], False)
        b = _state_name(paths, a['binding'])
        return ['--plan', plan, '--expect', str(call / 'expect.json'), '--binding', str(b)], [], b.name, set()
    if op == 'program.resume':
        _check_pair(paths, a['binding'], False)
        b = _state_name(paths, a['binding'])
        return ['--plan', plan, '--checkpoint', str(b), *obs, *proj], [], b.name, set()
    if op == 'task_context.validate':
        graph._path(a['plan'])
        if a['plan'].endswith('/'):
            _bad('plan must name a file')
        task = a['task_id']
        if task not in {t['id'] for t in doc['tasks']}:
            _bad('unknown task')
        _text(a['repo'], 'repo')
        return [str(_within(paths, a['file'])), '--root', str(paths['checkout']), '--plan', a['plan'],
                '--current-head', _head(a['current_head']), '--task-id', task, '--repo', a['repo']], [], None, set()
    scope = _scope(doc, a['scope'])
    b = _state_name(paths, a['binding'])
    args, writes, tasks = {'scope': scope}, set(), list(scope)
    if op == 'lifecycle.prepare':
        d = _state_name(paths, a['delivery'])
        if d == b or a['task'] not in scope:
            _bad('delivery must differ from binding and task must be in scope')
        _check_pair(paths, a['binding'], True, delivery=a['delivery'])
        args.update(delivery=str(d), task=a['task'], acceptance=_list(a['acceptance'], 'acceptance'),
                    intent=_text(a['intent'], 'intent'))
        writes = {b.name, d.name, b.name + identity.MARKER}
    else:
        d = _check_pair(paths, a['binding'], False)
        if op == 'lifecycle.attach':
            refs = a['refs']
            if not isinstance(refs, dict) or not refs or set(refs) - checkpoint.REFS:
                _bad('refs must be a nonempty object with known native reference keys')
            args['refs'] = {k: _text(v, 'native reference') for k, v in refs.items()}
            writes = {d.name}
        else:
            n = a['native']
            graph._fields(n, ('task', 'thread', 'status', 'children_terminal', 'ref'), 'native')
            if type(n['children_terminal']) is not bool:
                _bad('native terminal boolean required')
            args.update(native={k: n[k] if k == 'children_terminal' else _text(n[k], 'native ' + k) for k in n},
                        head=_head(a['head']))
    (call / 'input.json').write_text(json.dumps(args, sort_keys=True), encoding='utf-8')
    return ['--plan', plan, '--binding', str(b), '--observations', str(call / 'obs.json'),
            '--input', str(call / 'input.json'), *proj], tasks, b.name, writes


# --------------------------------------------------------------------------- results
# Closed, operation-specific shapes bound to the controller's own request. Child output is DATA: a
# well-formed result never grants anything (authority-shaped fields must be literally false) and is
# only compared with what the controller itself asked for and observed. Existing strict validators
# (identity._repo, checkpoint.validate, handoff.problems_for) are reused, never loosened.
STATES = {'eligible', 'blocked', 'running', 'report_ready', 'delivered'}
ID_KEYS = {'authorizes', 'merge_authorized', 'project_id', 'repository', 'task', 'approval', 'checkout'}


def _need(ok):
    if not ok:
        raise ValueError('result schema')


def _str(value, high=1000):
    return isinstance(value, str) and 0 < len(value) <= high


def _keys(r, keys):
    _need(isinstance(r, dict) and set(r) == keys)


def _program(r, c):
    """The child's selection must EQUAL the deterministic selection recomputed here from the same
    validated plan, observations and (for resume) binding. A valid-looking id is not enough."""
    active = program.load(c['binding']) if c['op'] == 'program.resume' else None
    _need(r == program.select(c['doc'], Path(c['plan_path']).parent, copy.deepcopy(c['args'].get('observations')),
                              active))


def _identity(r, c):
    verify = c['op'] == 'identity.verify'
    _keys(r, ID_KEYS | ({'binding_sha256'} if verify else set()))
    exp, task = c['exp'], c['task']
    approval = exp['approvals'][task]
    _need(r['project_id'] == exp['project_id'] and r['task'] == task)
    identity._repo(r['repository'])
    _need(identity._same_repo(r['repository'], exp['repository']))
    a = r['approval']
    _keys(a, {'ref', 'source', 'status', 'revision'})
    _need(a == dict(ref=approval['ref'], source=approval['source'], status='valid', revision=approval['revision'])
          and type(a['revision']) is int)
    seen = r['checkout']
    _keys(seen, {'root', 'common_dir', 'origin'})
    identity._repo(seen['origin'])
    _need(identity._same_repo(seen['origin'], exp['repository'])
          and identity._same(seen['root'], c['paths']['checkout'])
          and identity._same(seen['common_dir'], c['paths']['common_dir']))
    if verify:
        _need(r['binding_sha256'] == hashlib.sha256(c['binding'].read_bytes()).hexdigest())


def _context(r, c):
    """Re-run the real task_context.reconstruct (sources, hashes, handoff identity, roadmap relationships)
    against the controller's OWN expected root/plan/head/task/repo; recomputing context_hash cannot bypass it.
    The result must also be the context the controller asked about (the input file), byte-for-byte as data."""
    _keys(r, {'authorizes', 'context_hash', 'context'})
    a = c['args']
    again = task_context.reconstruct(task_context.read(c['file']), c['paths']['checkout'], c['plan_path'],
                                     current_head=a['current_head'], task_id=a['task_id'], repo=a['repo'])
    _need(r['context'] == again['context'] and r['context_hash'] == again['context_hash']
          and type(r['context_hash']) is str and again['authorizes'] is False)


def _prepare(r, c):
    _keys(r, {'action', 'intent', 'dispatch'})
    _need(r['action'] == 'reconcile_native_intent' and r['intent'] == c['args']['intent'])


def _attach(r, c):
    checkpoint.validate(r)
    _need(r == checkpoint.load(c['delivery']) and r['task_key'] == c['task'] and r['lifecycle'] == 'building')
    _need(all(r['refs'].get(k) == v for k, v in c['args']['refs'].items()))


def _reconcile(r, c):
    _need(isinstance(r, dict) and r.get('slot') in ('held', 'retired'))
    evidence = c['args']['observations']['tasks'].get(c['task'])
    if r['slot'] == 'retired':      # delivered: next selection (or stop) from the same observations
        _keys(r, {'action', 'task', 'slot', 'merge_authorized'})
        _need(isinstance(evidence, dict) and evidence.get('state') == 'delivered')
        nxt = program.select(c['doc'], Path(c['plan_path']).parent, copy.deepcopy(c['args']['observations']),
                             scope=c['args']['scope'])['task']
        _need(r['task'] == nxt and r['action'] == ('continue' if nxt else 'stop'))
    elif 'state' in r:
        _keys(r, {'action', 'state', 'slot', 'reason', 'merge_authorized'})
        _need(isinstance(evidence, dict) and r['state'] == evidence.get('state') and _str(r['reason']))
        _need(r['action'] == ('awaiting_authorization' if r['state'] == 'report_ready' else 'blocked'))
    else:
        _keys(r, {'action', 'slot', 'reason', 'merge_authorized'})
        _need(r['action'] == 'blocked' and r['slot'] == 'held' and _str(r['reason']))


_RESULTS = {'program': _program, 'identity': _identity, 'task_context': _context, 'lifecycle.prepare': _prepare,
            'lifecycle.attach': _attach, 'lifecycle.reconcile': _reconcile}


def _result_context(op, args, doc, exp, paths, plan_path, bname):
    c = dict(op=op, args=args, doc=doc, exp=exp, paths=paths, plan_path=plan_path, binding=None, delivery=None,
             ids={t['id'] for t in doc['tasks']}, plan_hash=program.fingerprint(doc, Path(plan_path).parent),
             task=args.get('task') or args.get('task_id'), file=args.get('file'))
    if bname:
        c['binding'] = paths['state_dir'] / bname
        if op != 'lifecycle.prepare':
            value = program.load(c['binding'])
            c['task'], c['delivery'] = value['task'], Path(value['delivery'])
    return c


def _validate_result(op, r, build):
    """`build` is a zero-argument callable producing the request context (kept lazy so any failure is 'output')."""
    try:
        (_RESULTS.get(op) or _RESULTS[op.split('.')[0]])(r, build())
        # Output success is never authority: authority-shaped fields must be literally false when present.
        _need(all(r[k] is False for k in ('authorizes', 'merge_authorized', 'dispatch') if k in r))
    except (ValueError, TypeError, KeyError, AttributeError, OSError, StopIteration, RecursionError):
        _bad('operation result violates the fixed output schema', 'output')
    return r


_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def _diagnostic(err, redact):
    line = err.decode('utf-8', 'replace').strip().split('\n')[0]
    for s in redact:
        if s:
            line = line.replace(s, '<redacted>')
    line = _QUOTED.sub("'…'", line)
    if re.fullmatch(r'(?:program|identity|lifecycle|task_context): [ -~]{1,160}', line[:200]):
        return line[:160]
    return 'unrecognized diagnostic'


# --------------------------------------------------------------------------- entry
def invoke(runtime, project, operation, args, *, authority, git_dir, cwd=None, timeout=30.0):
    """Run one named operation. Raises InvocationError (never partial success).

    Returns dict(operation, result, state_changes, read_only, runtime, authorizes=False,
    dispatch=False, merge_authorized=False). `authority()` must return the current
    controller expectation JSON object; it is called on every invocation.
    """
    if operation not in OPS:
        raise InvocationError('unsupported', 'unsupported operation' if operation not in UNSUPPORTED
                              else 'operation is explicitly unsupported by the B1 boundary')
    module, sub, required, optional, stateful = OPS[operation]
    if not isinstance(args, dict) or required - set(args) or set(args) - required - optional:
        _bad('arguments must be exactly the fixed schema for ' + operation)
    if type(timeout) not in (int, float) or not 0 < timeout <= 600:
        _bad('timeout must be 0-600 seconds')
    git_dir = _abs(git_dir, 'git directory', 'runtime')
    if not any((Path(git_dir) / n).is_file() for n in ('git.exe', 'git')):
        _bad('approved git directory has no git executable', 'runtime')
    paths = _project(project)
    state = paths['state_dir']
    call = state / CALLS / uuid.uuid4().hex
    call.mkdir(parents=True)
    (call / 'tmp').mkdir()
    ambiguous = held = False
    try:
        if cwd is None:
            (call / 'cwd').mkdir()
        run_cwd = str(call / 'cwd') if cwd is None else _abs(cwd, 'cwd')
        if not Path(run_cwd).is_dir():
            _bad('cwd must be an existing directory')
        _claim_owner(project, paths)
        lock = state / LOCK
        if lock.exists() or lock.is_symlink():
            raise InvocationError('state', 'writer lock present: active writer or ambiguous earlier outcome; '
                                           'manual reconciliation required')
        plan_arg = args['plan']
        if module == 'task_context':      # repository-relative here; joined to the approved checkout
            try:
                graph._path(plan_arg)
            except ValueError:
                _bad('plan must be a repository-relative path')
            plan_arg = str(paths['checkout'] / plan_arg)
        doc = _plan(paths, plan_arg)
        plan_path = str(_real(plan_arg))
        try:
            argv_tail, tasks, bname, writes = _build(operation, args, paths, doc, call)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise InvocationError('invalid_request', 'operation arguments are invalid') from None
        exp = _authority(project, paths, authority, tasks)
        (call / 'expect.json').write_text(json.dumps(exp, sort_keys=True), encoding='utf-8')
        facts = check_runtime(runtime, git_dir, run_cwd)
        before = _snapshot(state)
        if stateful:
            try:
                with open(lock, 'x', encoding='utf-8') as f:
                    json.dump(dict(writer=project.writer, operation=operation, state='running'), f)
            except FileExistsError:
                raise InvocationError('state', 'writer lock present') from None
            held = ambiguous = True    # ambiguous until the outcome is understood
        code, out, err, problem = _run(_argv(runtime, module, [*([sub] if sub else []), *argv_tail]), run_cwd,
                                       _env(git_dir, str(call / 'tmp')), timeout)
        changed = _changed(before, _snapshot(state))
        redact = [str(paths['state_dir']), str(paths['checkout']), str(call), git_dir] +                  [r['ref'] for r in exp['approvals'].values()]
        if changed - writes:
            ambiguous = True
            raise InvocationError('state', 'unexpected state change outside the operation write set; '
                                           'state retained', True)
        if problem:
            ambiguous = ambiguous or bool(changed)
            raise InvocationError('process', f'child {problem}' + ('; effects unknown, state retained' if ambiguous else ''),
                                  ambiguous)
        if code != 0:
            ambiguous = bool(changed)   # a stateful rejection that wrote nothing is clean
            message = 'task context rejected' if module == 'task_context' else f'exit {code}: ' + _diagnostic(err, redact)
            raise InvocationError('operation' if code == 1 else 'process', message, ambiguous)
        result = _validate_result(operation, _json(out, 'operation result'),
                                  lambda: _result_context(operation, args, doc, exp, paths, plan_path, bname))
        ambiguous = False
        return dict(operation=operation, result=result, state_changes=sorted(changed), read_only=not stateful,
                    runtime=facts, authorizes=False, dispatch=False, merge_authorized=False)
    finally:
        if ambiguous:
            _mark(state / LOCK, operation)
        elif held:
            _release(state / LOCK, project.writer)
        if not ambiguous:
            shutil.rmtree(call, ignore_errors=True)


def _mark(lock, operation):
    try:
        lock.write_text(json.dumps(dict(state='ambiguous', operation=operation)), encoding='utf-8')
    except OSError:
        pass


def _release(lock, writer):
    try:
        if json.loads(lock.read_text(encoding='utf-8')).get('writer') == writer:
            lock.unlink()
    except (OSError, ValueError):
        pass


def _report():
    import agent_workflow_pilot
    print(json.dumps(dict(version=list(sys.version_info[:3]),
                          package=os.path.dirname(os.path.realpath(agent_workflow_pilot.__file__)))))


if __name__ == '__main__':
    sys.exit(_report() or 0 if len(sys.argv) == 1 else 2)
