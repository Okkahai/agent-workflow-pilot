"""Deterministic program selection from trusted controller assertions; no dispatch."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys

from agent_workflow_pilot import graph
from agent_workflow_pilot.handoff import parse, SHA
from agent_workflow_pilot.controller import checkpoint, identity


def load(path):
    return parse(Path(path).read_text(encoding='utf-8'))


def validate(plan, root):
    graph._fields(plan, ('version', 'revision', 'tasks'), 'program')
    if type(plan['version']) is not int or plan['version'] != 1 or not isinstance(plan['revision'], str) or not plan['revision']:
        raise ValueError('invalid program version/revision')
    if not isinstance(plan['tasks'], list):
        raise ValueError('tasks must be an array')
    nodes = []
    for task in plan['tasks']:
        graph._fields(task, ('id', 'title', 'milestone', 'kind', 'approved', 'decision',
                            'priority', 'depends_on', 'owns', 'spec'), 'task')
        if task['kind'] not in ('code', 'artifact') or task['milestone'] not in ('M1','M2','M3','M4','M5'):
            raise ValueError('invalid kind/milestone')
        if type(task['approved']) is not bool or type(task['decision']) is not bool or type(task['priority']) is not int:
            raise ValueError('invalid authorization/priority')
        graph._path(task['spec'])
        spec = (Path(root) / task['spec']).resolve()
        if not spec.is_relative_to(Path(root).resolve()) or not spec.is_file():
            raise ValueError('missing or escaping task specification')
        nodes.append(dict(id=task['id'], title=task['title'], status='planned',
                          depends_on=task['depends_on'], owns=task['owns']))
    graph.validate(dict(version=1, kind='planned', nodes=nodes))
    return plan


def fingerprint(plan, root, read_spec=None):
    validate(plan, root)
    canonical = dict(plan, tasks=sorted(plan['tasks'], key=lambda t:t['id']))
    canonical['tasks'] = [dict(t, depends_on=sorted(t['depends_on']), owns=sorted(t['owns'])) for t in canonical['tasks']]
    payload = json.dumps(canonical, sort_keys=True).encode()
    for t in canonical['tasks']:
        path = Path(root) / t['spec']
        payload += path.read_bytes() if read_spec is None else read_spec(path)
    return hashlib.sha256(payload).hexdigest()


def completion(task, evidence):
    if evidence is None:
        return False
    common = {'state', 'head', 'verified_head', 'ref', 'children_terminal'}
    extra = {'draft', 'merged', 'merge_commit', 'target_tip', 'ancestor_verified'} if task['kind'] == 'code' else {'accepted', 'independent'}
    graph._fields(evidence, common | extra, 'observation')
    if evidence['state'] not in ('blocked', 'report_ready', 'delivered'):
        raise ValueError('invalid observation state')
    for field in {'head', 'verified_head'} | (set() if task['kind'] == 'artifact' else {'target_tip'}):
        if not isinstance(evidence[field], str) or not (re.fullmatch(r'[0-9a-f]{64}', evidence[field]) if task['kind'] == 'artifact' and len(evidence[field]) == 64 else SHA.fullmatch(evidence[field])):
            raise ValueError('full SHA required')
    if task['kind'] == 'code':
        merge = evidence['merge_commit']
        if merge is not None and (not isinstance(merge, str) or not SHA.fullmatch(merge)):
            raise ValueError('full merge SHA or null required')
        if merge is None and (evidence['merged'] or evidence['ancestor_verified'] or evidence['state']=='delivered'):
            raise ValueError('merge SHA required for merged/delivered evidence')
    if evidence['head'] != evidence['verified_head'] or not isinstance(evidence['ref'], str) or not evidence['ref'].strip():
        raise ValueError('stale evidence or missing reference')
    booleans = {'children_terminal'} | ({'draft','merged','ancestor_verified'} if task['kind'] == 'code' else {'accepted','independent'})
    if any(type(evidence[k]) is not bool for k in booleans):
        raise ValueError('observation booleans required')
    complete = evidence['children_terminal'] and (all(evidence[k] for k in ('merged','ancestor_verified')) and not evidence['draft'] if task['kind']=='code' else evidence['accepted'] and evidence['independent'])
    if evidence['state']=='delivered' and not complete:
        raise ValueError('inconsistent delivered evidence')
    return complete and evidence['state']=='delivered'


def select(plan, root, observations=None, active=None, scope=None):
    digest = fingerprint(plan, root)
    if observations is None:
        observations = {'plan_hash': digest, 'tasks': {}}
    graph._fields(observations, ('plan_hash','tasks'), 'observations')
    if observations['plan_hash'] != digest:
        raise ValueError('stale observation plan')
    tasks = {t['id']:t for t in plan['tasks']}
    if scope is not None and (not isinstance(scope, list) or
                              any(not isinstance(i, str) or i not in tasks for i in scope)):
        raise ValueError('invalid execution scope')
    if not isinstance(observations['tasks'], dict) or set(observations['tasks']) - tasks.keys():
        raise ValueError('unknown observation task')
    done = {i:completion(t, observations['tasks'].get(i)) for i,t in tasks.items()}
    for i, t in tasks.items():
        if done[i] and any(not done[d] for d in t['depends_on']):
            raise ValueError('delivered task has incomplete dependency')
    view = {}
    for i,t in sorted(tasks.items()):
        blockers = []
        if not t['approved']: blockers.append('awaiting_authorization')
        if not t['decision']: blockers.append('awaiting_decision')
        blockers += ['dependency: '+d for d in sorted(t['depends_on']) if not done[d]]
        e = observations['tasks'].get(i)
        state = 'delivered' if done[i] else 'blocked' if blockers else 'eligible'
        if e and not done[i]: state = e['state']; blockers.append('completion not verified')
        view[i] = dict(state=state, explanation=blockers or [state])
    selected = None
    if active is not None:
        graph._fields(active, ('plan_hash','task','delivery'), 'program checkpoint')
        if active['plan_hash'] != digest or active['task'] not in tasks:
            raise ValueError('stale checkpoint plan/task')
        if not tasks[active['task']]['approved'] or not tasks[active['task']]['decision']:
            raise ValueError('active task lacks authorization/decision')
        if scope is not None and active['task'] not in scope:
            raise ValueError('active task outside execution scope')
        delivery = checkpoint.load(active['delivery'])
        if delivery['task_key'] != active['task']:
            raise ValueError('delivery identity mismatch')
        selected = active['task']
        view[selected] = dict(state='blocked' if delivery['lifecycle'] in ('dispatching','blocked') else 'running', explanation=['resume existing delivery; reconcile native records; never redispatch'])
    else:
        eligible = [t for t in tasks.values() if view[t['id']]['state']=='eligible'
                    and (scope is None or t['id'] in scope)]
        if eligible: selected = min(eligible, key=lambda t:(t['priority'],t['id']))['id']
    return dict(plan_hash=digest, task=selected, tasks=view, explanation='resume' if active else 'selected' if selected else 'no authorized eligible task', merge_authorized=False)


def record(path, plan, root, task, delivery, observations=None, scope=None):
    """Bind an existing persisted delivery; exclusive creation makes replay immutable."""
    value = dict(plan_hash=fingerprint(plan, root), task=task, delivery=str(Path(delivery).resolve()))
    if Path(path).exists():
        if load(path) != value: raise ValueError('immutable delivery binding differs')
        return select(plan, root, observations, value, scope=scope)
    result = select(plan, root, observations, scope=scope)
    if result['task'] != task: raise ValueError('task is not selected/authorized')
    result = select(plan, root, observations, value, scope=scope)
    with open(path, 'x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('check','next','record','resume'))
    p.add_argument('--plan', default='docs/program/roadmap.json')
    p.add_argument('--observations')
    p.add_argument('--checkpoint')
    p.add_argument('--task')
    p.add_argument('--delivery')
    identity.add_arguments(p)
    a = p.parse_args(argv)
    try:
        plan = load(a.plan); root = Path(a.plan).parent
        expect, proof = identity.enter(a.mode, a.expect, plan, a.plan, a.checkpoint,
                                       a.task if a.command=='record' and a.checkpoint else None)
        obs = load(a.observations) if a.observations else None
        if a.command=='record':
            if not all((a.checkpoint,a.task,a.delivery)): raise ValueError('record requires checkpoint/task/delivery')
            result = record(a.checkpoint,plan,root,a.task,a.delivery,obs)
            if expect is not None: identity.bind(expect,plan,a.plan,a.checkpoint)
        else:
            if a.command=='resume' and not a.checkpoint: raise ValueError('resume requires checkpoint')
            result = select(plan,root,obs,load(a.checkpoint) if a.checkpoint else None)
            if expect is not None and result['task']: identity.check_task(expect,plan,a.plan,result['task'])
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (ValueError,OSError,TypeError,KeyError) as error:
        print(f'program: {error}',file=sys.stderr)
        return 1


if __name__=='__main__':
    sys.exit(main())
