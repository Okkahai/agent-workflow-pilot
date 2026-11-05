"""Portable, pinned harness installer. Run from the trusted harness checkout."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ('repo-discovery', 'research-first', 'task-planning', 'handoff',
          'independent-review', 'pr-delivery')
DOCS = ('engineering-standard.md', 'orchestration/roles.md',
        'orchestration/skills.md', 'orchestration/graph-schema.md',
        'orchestration/handoff.md', 'orchestration/context-pack.md',
        'orchestration/model-routing.md', 't3-runbook.md',
        'templates/onboarding.md', 'onboarding/project-adoption.md',
        'onboarding/workflow.md', 'onboarding/templates/repository.md',
        'onboarding/templates/task.md', 'onboarding/templates/review.md',
        'onboarding/templates/handoff.json', 'orchestration/handoffs/README.md',
        'orchestration/handoffs/example.json')
STATE = '.agent-harness/manifest.json'
JOURNAL = '.agent-harness/rollback.json'
INVENTORY = '.agent-harness/inventory.json'
GRAPH = '.agent-harness/initial-graph.json'
START = '.agent-harness/START.md'


def git(root, *args):
    return subprocess.run(['git', '--no-replace-objects', '-C', str(root), *args], check=True,
                          capture_output=True).stdout.strip()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def safe(root, name):
    """Reject redirects, hardlinks, case aliases and non-regular leaves."""
    path = root
    for part in Path(name).parts:
        if part in ('.', '..') or ':' in part:
            raise ValueError('unsafe path')
        if path.exists():
            aliases = [p.name for p in path.iterdir() if p.name.casefold() == part.casefold()]
            if aliases and aliases != [part]:
                raise ValueError('case alias: ' + name)
        path = path / part
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode) or
                getattr(info, 'st_file_attributes', 0) & 1024 or
                (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)):
            raise ValueError('filesystem redirect: ' + name)
        if not (stat.S_ISREG(info.st_mode) if path == root / name else stat.S_ISDIR(info.st_mode)):
            raise ValueError('unexpected file type: ' + name)
    return path


def read(root, name):
    p = safe(root, name)
    return p.read_bytes() if p.exists() else None


def write(root, name, data):
    p = safe(root, name)
    if data is None:
        p.unlink(missing_ok=True)
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=p.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        safe(root, name)
        os.replace(temporary, p)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def mapping():
    files = {'.agent-harness/docs/' + d: 'docs/' + d for d in DOCS}
    for module in ('graph', 'handoff', 'gate'):
        files[f'.agent-harness/validators/{module}.py'] = f'src/agent_workflow_pilot/{module}.py'
    for skill in SKILLS:
        for prefix in ('.agent-harness/skills', '.agents/skills', '.claude/skills'):
            files[f'{prefix}/{skill}/SKILL.md'] = f'harness/skills/{skill}/SKILL.md'
    files[START] = 'harness/distribution/START.md'
    return files


def bundle(pin):
    if not re.fullmatch('[0-9a-f]{40}', pin):
        raise ValueError('pin must be a full lowercase committed SHA')
    if git(ROOT, 'rev-parse', '--verify', pin + '^{commit}').decode() != pin:
        raise ValueError('pin is not a commit')
    files = {}
    for dest, source in mapping().items():
        mode = git(ROOT, 'ls-tree', pin, '--', source).split(b' ', 1)[0]
        if mode != b'100644':
            raise ValueError('missing or non-regular canonical asset: ' + source)
        files[dest] = subprocess.run(['git', '--no-replace-objects', '-C', str(ROOT), 'show', f'{pin}:{source}'],
                                     check=True, capture_output=True).stdout
    return files


def target(path):
    path = Path(os.path.abspath(path))
    # Inspect every ancestor before resolving, including Windows junctions.
    for p in [*reversed(path.parents), path]:
        info = p.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
            raise ValueError('redirected target')
    if Path(os.fsdecode(git(path, 'rev-parse', '--show-toplevel'))).resolve() != path.resolve():
        raise ValueError('target must be a repository root')
    common = git(path, 'rev-parse', '--path-format=absolute', '--git-common-dir')
    if common == git(ROOT, 'rev-parse', '--path-format=absolute', '--git-common-dir'):
        raise ValueError('pilot repository is forbidden')
    remote = git(path, 'config', '--get-regexp', 'remote.*.url') if git(path, 'remote') else b''
    if b'agent-workflow-pilot' in remote.lower():
        raise ValueError('pilot remote is forbidden')
    return path


def manifest(raw):
    doc = json.loads(raw)
    if not isinstance(doc, dict) or not isinstance(doc.get('files'), dict):
        raise ValueError('invalid ownership manifest')
    if (set(doc) != {'version', 'pin', 'files'} or doc['version'] != 1 or
            not isinstance(doc['pin'], str) or
            not re.fullmatch('[0-9a-f]{40}', doc['pin']) or
            set(doc['files']) not in (set(mapping()) | {INVENTORY, GRAPH},
                {name for name in mapping() if name != START and
                 not name.startswith('.agent-harness/docs/onboarding/') and
                 not name.startswith('.agent-harness/docs/orchestration/handoffs/')} | {INVENTORY}) or
            any(not isinstance(h, str) or not re.fullmatch('[0-9a-f]{64}', h)
                for h in doc['files'].values())):
        raise ValueError('invalid ownership manifest')
    return doc


def run(command, path, pin=None, dry_run=False):
    root = target(path)
    raw = read(root, STATE)
    old = manifest(raw) if raw else None
    allowed = set(mapping()) | {INVENTORY, GRAPH, STATE}
    if command == 'rollback':
        journal = json.loads(read(root, JOURNAL) or b'null')
        if not isinstance(journal, dict) or set(journal) != {'before', 'after'}:
            raise ValueError('no valid rollback snapshot')
        if (not isinstance(journal['before'], dict) or not isinstance(journal['after'], dict) or
                set(journal['before']) != set(journal['after']) or
                not set(journal['before']).issubset(allowed) or STATE not in journal['before']):
            raise ValueError('invalid rollback paths')
        changes = {}
        for name in sorted(journal['before']):
            before = journal['before'][name]
            changes[name] = None if before is None else base64.b64decode(before, validate=True)
            current = read(root, name)
            actual = None if current is None else digest(current)
            # Interrupted operations may be at either side; nothing else is overwritten.
            if actual not in (journal['after'][name], None if changes[name] is None else digest(changes[name])):
                raise ValueError('rollback conflict: ' + name)
        if not dry_run:
            for name, value in changes.items():
                write(root, name, value)
            write(root, JOURNAL, None)
        return {'operation': command, 'dry_run': dry_run}
    if old:
        for name, expected in old['files'].items():
            current = read(root, name)
            if current is None or digest(current) != expected:
                raise ValueError('owned file drift: ' + name)
    if command == 'check':
        if not old:
            raise ValueError('not initialized')
        expected = bundle(old['pin'])
        if any(name not in expected or digest(expected[name]) != value
               for name, value in old['files'].items() if name not in (INVENTORY, GRAPH)):
            raise ValueError('manifest differs from committed source')
        return {'operation': command, 'pin': old['pin'], 'drift': []}
    if command == 'upgrade' and not old:
        raise ValueError('upgrade requires initialization')
    files = bundle(pin)
    if old:
        files[INVENTORY] = read(root, INVENTORY)
    else:
        files[INVENTORY] = encode({
            'observed': {'git_root': str(root), 'head': git(root, 'rev-parse', 'HEAD').decode(),
                         'root_AGENTS_present': os.path.lexists(root / 'AGENTS.md')},
            'unknowns': ['owners', 'stack', 'build/test commands', 'architecture',
                         'CI/protections/permissions', 'MCP runtime availability'],
            'graph': GRAPH, 'graph_status': 'inventory observation only; no project tasks inferred'})
    files[GRAPH] = (read(root, GRAPH) if old and GRAPH in old['files'] else encode({
        'version': 1, 'kind': 'planned', 'nodes': [{
            'id': 'record-inventory', 'title': 'Record local Git inventory snapshot',
            'status': 'complete', 'depends_on': [], 'owns': []}]}))
    state = encode({'version': 1, 'pin': pin,
                    'files': {k: digest(v) for k, v in files.items()}})
    files[STATE] = state
    before = {name: read(root, name) for name in files}
    for name, value in before.items():
        if value is not None and (not old or name not in set(old['files']) | {STATE}):
            raise ValueError('unowned collision: ' + name)
    changed = [name for name in files if before[name] != files[name]]
    if old and command == 'init' and old['pin'] != pin:
        raise ValueError('use upgrade to change pin')
    if changed and read(root, JOURNAL) is not None:
        raise ValueError('rollback snapshot exists; archive it deliberately before another upgrade')
    if changed and not dry_run:
        snapshot = {'before': {k: None if v is None else base64.b64encode(v).decode()
                               for k, v in before.items()},
                    'after': {k: digest(v) for k, v in files.items()}}
        write(root, JOURNAL, encode(snapshot))
        for name in sorted(files):
            write(root, name, files[name])
    return {'operation': command, 'pin': pin, 'dry_run': dry_run, 'changed': sorted(changed)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init', 'check', 'upgrade', 'rollback'))
    parser.add_argument('--target', required=True, type=Path)
    parser.add_argument('--pin')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    if args.command in ('init', 'upgrade') and not args.pin:
        parser.error('--pin is required for init and upgrade')
    try:
        print(json.dumps(run(args.command, args.target, args.pin, args.dry_run)))
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as error:
        print(json.dumps({'error': str(error), 'recovery': 'inspect drift; use rollback after a partial write'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
