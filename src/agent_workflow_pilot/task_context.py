"""Bounded task/context recovery data. Validity never grants authority."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from agent_workflow_pilot import graph, handoff
from agent_workflow_pilot.controller import program

SCHEMA = 'agent-workflow-pilot.task-context/1'
parse = handoff.parse
FIELDS = {'schema', 'task_id', 'repo', 'head', 'plan_hash', 'spec', 'objective',
          'scope', 'exclusions', 'acceptance', 'depends_on', 'owns', 'owner',
          'routing', 'risks', 'decisions', 'context', 'next_action', 'handoff'}


def canonical(doc):
    """Canonical UTF-8 bytes; preserves meaningful list order."""
    return json.dumps(doc, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def read(path):
    with Path(path).open(encoding='utf-8') as stream:
        return parse(stream.read(handoff.MAX_BYTES + 1))


def reference(root, path):
    """Hash a bounded local source; never execute or fetch referenced content."""
    graph._path(path)
    if path.endswith('/'):
        raise ValueError('reference must name a file')
    root = Path(root).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ValueError('escaping reference')
    with target.open('rb') as stream:
        content = stream.read(handoff.MAX_BYTES + 1)
    if len(content) > handoff.MAX_BYTES:
        raise ValueError('reference exceeds size limit')
    return dict(path=path, sha256=hashlib.sha256(content).hexdigest())


def reconstruct(doc, root, plan_path, *, current_head, task_id, repo):
    """Revalidate sources and independent identity on every reload; return inert pack.

    Caller must resolve current_head/task_id/repo independently. Hashes establish
    consistency, never origin, authorization, dependency completion or live state.
    """
    # Apply the same size/depth/strict JSON boundary to API and CLI callers.
    doc = parse(canonical(doc).decode())
    problems = []
    if not handoff._fields(doc, FIELDS, 'context', problems):
        raise ValueError('; '.join(problems))
    for key in ('objective', 'owner', 'routing', 'next_action'):
        handoff._text(doc.get(key), key, problems, high=1000)
        if isinstance(doc.get(key), str) and not doc[key].strip():
            problems.append(key + ': blank')
    for key in ('scope', 'exclusions', 'acceptance', 'risks', 'decisions'):
        for entry in handoff._items(doc.get(key), key, problems, 1):
            handoff._text(entry, key, problems, high=1000)
            if isinstance(entry, str) and not entry.strip():
                problems.append(key + ': blank')
    handoff._sha(current_head, 'current_head', problems)
    if doc.get('schema') != SCHEMA:
        problems.append('schema: mismatch')
    for key, expected in (('head', current_head), ('task_id', task_id), ('repo', repo)):
        if doc.get(key) != expected:
            problems.append(key + ': independent identity mismatch')
    claim = doc.get('handoff')
    problems.extend(handoff.problems_for(claim, current_head))
    if isinstance(claim, dict):
        for key in ('head', 'task_id', 'repo'):
            if claim.get(key) != doc.get(key):
                problems.append('handoff: identity mismatch')
    if problems:
        raise ValueError('; '.join(problems))
    root = Path(root).resolve()
    plan_path = Path(plan_path).resolve()
    if not plan_path.is_relative_to(root):
        raise ValueError('plan outside root')
    plan = read(plan_path)
    digest = program.fingerprint(plan, plan_path.parent)
    if doc['plan_hash'] != digest:
        raise ValueError('stale plan fingerprint')
    task = next((t for t in plan['tasks'] if t['id'] == task_id), None)
    if task is None:
        raise ValueError('unknown task')
    for key in ('depends_on', 'owns'):
        if doc[key] != task[key]:
            raise ValueError(key + ': roadmap mismatch')
    expected_spec = (plan_path.parent / task['spec']).resolve().relative_to(root).as_posix()
    refs = handoff._items(doc['context'], 'context', problems, 1)
    seen = set()
    for ref in [doc['spec'], *refs]:
        if not handoff._fields(ref, {'path', 'sha256'}, 'reference', problems):
            continue
        if problems:
            break
        if reference(root, ref['path']) != ref:
            problems.append('stale source reference')
    for ref in refs:
        if isinstance(ref, dict) and isinstance(ref.get('path'), str):
            if ref['path'] in seen:
                problems.append('duplicate context reference')
            seen.add(ref['path'])
    if not isinstance(doc['spec'], dict) or doc['spec'].get('path') != expected_spec:
        problems.append('spec: roadmap mismatch')
    if problems:
        raise ValueError('; '.join(problems))
    return dict(authorizes=False, context_hash=hashlib.sha256(canonical(doc)).hexdigest(),
                context=doc)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file')
    p.add_argument('--root', required=True)
    p.add_argument('--plan', required=True, help='repository-relative roadmap path')
    p.add_argument('--current-head', required=True)
    p.add_argument('--task-id', required=True)
    p.add_argument('--repo', required=True)
    a = p.parse_args(argv)
    try:
        graph._path(a.plan)
        result = reconstruct(read(a.file), a.root, Path(a.root) / a.plan,
                             current_head=a.current_head, task_id=a.task_id, repo=a.repo)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError, RecursionError, TypeError) as error:
        # Do not echo untrusted content or filesystem names.
        print(json.dumps(dict(authorizes=False, valid=False, error=type(error).__name__)))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
