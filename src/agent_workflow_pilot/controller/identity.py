"""Versioned external project identity/approval binding adapter (A1).

Inert: every report carries authorizes=false and merge_authorized=false. The adapter
only checks that a controller-supplied EXPECTATION (never read from the envelope it
checks) agrees with (a) an independently observed Git checkout and (b) a stored
identity ENVELOPE that references an unchanged legacy v1 Program binding by SHA-256.

Trust limit: a Python process cannot tell who wrote its inputs. The expectation file
and approval evidence are trusted *assertions* of the controller, kept where workers
cannot edit them; this module checks consistency, it does not authenticate people,
hosts or Git configuration. Legacy v1 binding/checkpoint formats are never rewritten.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from agent_workflow_pilot import graph
from agent_workflow_pilot.handoff import REPO, SLUG, parse
from agent_workflow_pilot.controller import checkpoint, program as p

SCHEMA = 'agent-workflow-pilot.identity/1'
EXPECT_SCHEMA = 'agent-workflow-pilot.identity-expectation/1'
MARKER = '.identity.json'          # envelope lives next to its binding: <binding>.identity.json
SOURCES = ('user_decision', 'trusted_policy')
HEX64 = re.compile(r'[0-9a-f]{64}')
HOST = re.compile(r'[a-z0-9][a-z0-9.-]{0,98}')
GITHUB = 'github.com'              # the only host whose origin this module can verify
ORIGIN = re.compile(r'(?:https://(?:[^/@]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)'
                    r'([A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*?)(?:\.git)?/?')


class Unsupported(ValueError):
    """Explicit block: a host/checkout shape this module cannot verify (not a silent pass)."""


class Verified(dict):
    """Result of verify(); only this type unlocks project-bound legacy entry points."""
    binding = None


def _text(v, name, high=200):
    if not isinstance(v, str) or not 1 <= len(v) <= high or not v.isprintable():
        raise ValueError(f'invalid {name}')
    return v


def _hex(v, name):
    if not isinstance(v, str) or not HEX64.fullmatch(v):
        raise ValueError(f'invalid {name}')
    return v


def _repo(v):
    graph._fields(v, ('host', 'name'), 'repository')
    if not isinstance(v['host'], str) or not HOST.fullmatch(v['host']):
        raise ValueError('invalid repository host')
    _text(v['name'], 'repository name')
    if v['host'] == GITHUB and not REPO.fullmatch(v['name']):
        raise ValueError('invalid GitHub repository name')
    return v


def _same_repo(a, b):
    fold = (lambda s: s.casefold()) if a['host'] == GITHUB else (lambda s: s)
    return a['host'] == b['host'] and fold(a['name']) == fold(b['name'])


def _marker(binding):
    return Path(str(Path(binding).resolve()) + MARKER)


def load(path):
    with open(path, encoding='utf-8') as stream:
        return parse(stream.read(65537))


# ------------------------------------------------------------------ expectation
APPROVAL = ('ref', 'source', 'designated', 'project_id', 'repository', 'task', 'scope', 'plan_hash',
            'spec_sha256', 'operation', 'status', 'revision')


def _approval_shape(task, r):
    graph._fields(r, APPROVAL, 'approval')
    _text(r['ref'], 'approval ref')
    if r['source'] not in SOURCES or type(r['designated']) is not bool or r['designated'] != (r['source'] == 'trusted_policy'):
        raise ValueError('invalid approval source (policy must be controller-designated, user decision must not claim it)')
    if not isinstance(r['project_id'], str) or not SLUG.fullmatch(r['project_id']):
        raise ValueError('invalid approval project')
    _repo(r['repository'])
    if r['task'] != task or not isinstance(r['scope'], list) or not r['scope'] or any(not isinstance(s, str) for s in r['scope']):
        raise ValueError('invalid approval task/scope')
    _hex(r['plan_hash'], 'approval plan hash')
    _hex(r['spec_sha256'], 'approval spec hash')
    if r['operation'] != 'implement' or r['status'] not in ('valid', 'revoked', 'superseded') or \
            type(r['revision']) is not int or r['revision'] < 1:
        raise ValueError('invalid approval operation/status (implementation approval is never merge approval)')


def expectation(value):
    """Validate a controller-supplied expectation. An envelope or None can never pass."""
    if value is None:
        raise ValueError('independent controller expectation required')
    graph._fields(value, ('schema', 'project_id', 'repository', 'checkouts', 'common_dir', 'approvals'), 'expectation')
    if value['schema'] != EXPECT_SCHEMA:
        raise ValueError('not an identity expectation')
    if not isinstance(value['project_id'], str) or not SLUG.fullmatch(value['project_id']):
        raise ValueError('invalid project id')
    _repo(value['repository'])
    paths = value['checkouts']
    if not isinstance(paths, list) or not paths or any(not isinstance(c, str) or not os.path.isabs(c) for c in paths):
        raise ValueError('approved checkouts must be absolute paths')
    if not isinstance(value['common_dir'], str) or not os.path.isabs(value['common_dir']):
        raise ValueError('common directory must be an absolute path')
    if not isinstance(value['approvals'], dict):
        raise ValueError('approvals must be an object keyed by task')
    for task, record in value['approvals'].items():
        _approval_shape(task, record)
    return value


# ------------------------------------------------------------------ observation
def _git(path, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0')
    try:
        r = subprocess.run(['git', '-C', str(path), *args], capture_output=True, timeout=10, env=env,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        raise Unsupported('unsupported: git unavailable or timed out') from None
    if len(r.stdout) > 4096:
        raise ValueError('git observation too large')
    return r.returncode, r.stdout.decode('utf-8', 'replace').strip()


def _same(a, b):
    try:
        return os.path.samefile(a, b)   # file identity: Windows case, 8.3, junction and symlink aliases
    except OSError:
        return False


def observe(path):
    """Bounded read-only Git observation of the checkout containing `path`."""
    if not Path(path).is_dir():
        raise ValueError('checkout path is not a directory')
    code, out = _git(path, 'rev-parse', '--path-format=absolute', '--show-toplevel', '--git-common-dir', '--git-dir')
    lines = out.split('\n')
    if code or len(lines) != 3:
        raise ValueError('not an observable non-bare Git checkout')
    code, url = _git(path, 'config', '--get', 'remote.origin.url')
    if code:
        raise Unsupported('unsupported: remote-less checkout cannot be verified')
    match = ORIGIN.fullmatch(url)
    if not match:
        raise Unsupported('unsupported: only github.com origins are verifiable')
    return dict(root=os.path.realpath(lines[0]), common_dir=os.path.realpath(lines[1]),
                origin=dict(host=GITHUB, name=match.group(1)))


def _checkout(expect, plan_path, observe=observe):
    if expect['repository']['host'] != GITHUB:
        raise Unsupported('unsupported: only github.com repositories are verifiable')
    seen = observe(Path(plan_path).resolve().parent)
    if not any(_same(seen['root'], c) for c in expect['checkouts']) or not _same(seen['common_dir'], expect['common_dir']):
        raise ValueError('checkout root/common directory is not an approved checkout or worktree')
    if not _same_repo(seen['origin'], expect['repository']):
        raise ValueError('origin does not match expected repository')
    return seen


# ------------------------------------------------------------------ checks
def _facts(plan, plan_path, task):
    base = Path(plan_path).parent
    spec = next((t['spec'] for t in plan['tasks'] if t['id'] == task), None)
    if spec is None:
        raise ValueError('unknown task')
    return p.fingerprint(plan, base), hashlib.sha256((base / spec).read_bytes()).hexdigest()


def check_task(expect, plan, plan_path, task, observe=observe):
    """Checkout + approval for a task; needs no envelope (used before a binding exists)."""
    expect = expectation(expect)
    seen = _checkout(expect, plan_path, observe)
    plan_hash, spec_hash = _facts(plan, plan_path, task)
    r = expect['approvals'].get(task)
    if r is None:
        raise ValueError('no controller approval evidence for task')
    if r['status'] != 'valid' or r['project_id'] != expect['project_id'] or task not in r['scope'] \
            or not _same_repo(r['repository'], expect['repository']) \
            or r['plan_hash'] != plan_hash or r['spec_sha256'] != spec_hash:
        raise ValueError('approval is revoked, superseded, stale or bound to another project/repository/scope')
    return Verified(authorizes=False, merge_authorized=False, project_id=expect['project_id'],
                    repository=expect['repository'], task=task,
                    approval=dict(ref=r['ref'], source=r['source'], status=r['status'], revision=r['revision']),
                    checkout=seen)


def check_checkout(expect, plan_path, observe=observe):
    return _checkout(expectation(expect), plan_path, observe)


def _binding_ref(plan, plan_path, binding):
    raw = Path(binding).read_bytes()
    value = parse(raw.decode('utf-8'))
    graph._fields(value, ('plan_hash', 'task', 'delivery'), 'binding')
    if value['plan_hash'] != p.fingerprint(plan, Path(plan_path).parent):
        raise ValueError('binding is stale for this plan')
    if checkpoint.load(value['delivery'])['task_key'] != value['task']:
        raise ValueError('binding/delivery identity mismatch')
    return value['task'], hashlib.sha256(raw).hexdigest()


def bind(expect, plan, plan_path, binding, observe=observe):
    """Write the immutable envelope for an existing, well-formed legacy binding."""
    task, digest = _binding_ref(plan, plan_path, binding)
    report = check_task(expect, plan, plan_path, task, observe)
    plan_hash, spec_hash = _facts(plan, plan_path, task)
    envelope = dict(schema=SCHEMA, project_id=report['project_id'], repository=report['repository'], task=task,
                    plan_hash=plan_hash, spec_sha256=spec_hash, binding_sha256=digest,
                    approval_ref=report['approval']['ref'])
    marker = _marker(binding)
    try:
        with open(marker, 'x', encoding='utf-8') as stream:
            json.dump(envelope, stream, sort_keys=True)
    except FileExistsError:
        if load(marker) != envelope:
            raise ValueError('immutable identity envelope differs') from None
    return envelope


def verify(expect, plan, plan_path, binding, observe=observe):
    """Check envelope against independent expectation and observation BEFORE state use."""
    expect = expectation(expect)
    try:
        env = load(_marker(binding))
    except FileNotFoundError:
        raise ValueError('missing identity envelope for project-scoped binding') from None
    graph._fields(env, ('schema', 'project_id', 'repository', 'task', 'plan_hash', 'spec_sha256',
                        'binding_sha256', 'approval_ref'), 'envelope')
    if env['schema'] != SCHEMA:
        raise ValueError('unsupported identity envelope schema')
    _repo(env['repository'])
    if env['project_id'] != expect['project_id'] or not _same_repo(env['repository'], expect['repository']):
        raise ValueError('envelope project/repository differs from controller expectation')
    if hashlib.sha256(Path(binding).read_bytes()).hexdigest() != _hex(env['binding_sha256'], 'binding hash'):
        raise ValueError('binding bytes differ from identity envelope')
    report = check_task(expect, plan, plan_path, env['task'], observe)
    plan_hash, spec_hash = _facts(plan, plan_path, env['task'])
    if (env['plan_hash'], env['spec_sha256']) != (plan_hash, spec_hash):
        raise ValueError('envelope is stale for plan/spec')
    if env['approval_ref'] != report['approval']['ref']:
        raise ValueError('envelope approval reference differs from controller evidence')
    if _binding_ref(plan, plan_path, binding)[0] != env['task']:
        raise ValueError('binding task differs from envelope')
    out = Verified(report, binding_sha256=env['binding_sha256'])
    out.binding = str(Path(binding).resolve())
    return out


# ------------------------------------------------------------------ entry-point guard
def assert_project(binding, project):
    """Legacy entry points call this: project-bound state needs a Verified proof for that binding."""
    if _marker(binding).exists() and not (isinstance(project, Verified) and project.binding == str(Path(binding).resolve())):
        raise ValueError('project-bound state requires project-mode verification')


def add_arguments(parser):
    parser.add_argument('--mode', choices=('legacy', 'project'), default='legacy',
                        help='legacy: single-project pilot semantics (not multi-project safe); '
                             'project: verify --expect identity/approval first, fail closed')
    parser.add_argument('--expect', help='controller-owned identity expectation JSON (project mode only)')


def enter(mode, expect_path, plan, plan_path, binding=None, task=None):
    """Run first in every CLI. Returns (expectation|None, proof|None). Raises before state is read."""
    if mode == 'legacy':
        if expect_path:
            raise ValueError('--expect requires --mode project')
        if binding is not None:
            assert_project(binding, None)
        return None, None
    if not expect_path:
        raise ValueError('project mode requires --expect')
    expect = expectation(load(expect_path))
    if task is not None:
        check_task(expect, plan, plan_path, task)
        return expect, None
    if binding is None:
        check_checkout(expect, plan_path)
        return expect, None
    return expect, verify(expect, plan, plan_path, binding)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'bind', 'verify'))
    parser.add_argument('--plan', default='docs/program/roadmap.json')
    parser.add_argument('--expect', required=True)
    parser.add_argument('--binding')
    parser.add_argument('--task')
    a = parser.parse_args(argv)
    try:
        plan, expect = p.load(a.plan), load(a.expect)
        if a.command == 'check':
            if not a.task:
                raise ValueError('check requires --task')
            result = check_task(expect, plan, a.plan, a.task)
        elif not a.binding:
            raise ValueError(a.command + ' requires --binding')
        else:
            result = (bind if a.command == 'bind' else verify)(expect, plan, a.plan, a.binding)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(f'identity: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
