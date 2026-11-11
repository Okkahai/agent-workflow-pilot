"""Single-writer Program/Delivery bridge. Inputs must be collected by the controller."""
import argparse
import json
from pathlib import Path
import sys
from agent_workflow_pilot.controller import checkpoint as c, identity, program as p


def bound(plan, root, binding, observations, scope, project=None):
    identity.assert_project(binding, project, plan, root)
    active = p.load(binding)
    p.select(plan, root, observations, active, scope=scope)
    if active['task'] not in scope:
        raise ValueError('task outside approved execution scope')
    task = next(t for t in plan['tasks'] if t['id'] == active['task'])
    return active, task, c.load(active['delivery'])


def prepare(plan, root, binding, delivery, observations, scope, task, acceptance, intent):
    """Persist intent and binding BEFORE caller invokes its native tool. Never dispatch."""
    selected = p.select(plan, root, observations, scope=scope)
    if selected['task'] != task or task not in scope:
        raise ValueError('task not eligible in approved scope')
    spec = next(t for t in plan['tasks'] if t['id'] == task)
    state = c.new(task, acceptance, spec['depends_on'])
    state = c.apply(state, 'prepare', 'dispatch', client_request_id=intent,
                    completed_dependencies=spec['depends_on'])
    if Path(delivery).exists():
        old = c.load(delivery)
        if any(old[k] != state[k] for k in ('task_key', 'acceptance', 'dependencies', 'intent')):
            raise ValueError('conflicting existing delivery')
    else:
        if Path(binding).exists():
            raise ValueError('active binding already exists')
        c.save(delivery, state)
    p.record(binding, plan, root, task, delivery, observations, scope=scope)
    return dict(action='reconcile_native_intent', intent=intent, dispatch=False)


def attach(plan, root, binding, observations, scope, refs, project=None):
    active, task, state = bound(plan, root, binding, observations, scope, project)
    if any(k in state['refs'] and state['refs'][k] != v for k,v in refs.items()):
        raise ValueError('conflicting native identity')
    state = c.apply(state, 'native-attachment', 'started', refs=refs)
    c.save(active['delivery'], state)
    return state


def reconcile(plan, root, binding, observations, scope, native, head, project=None):
    """Read fresh native and host evidence, never worker assertions. No merge authority."""
    active, task, state = bound(plan, root, binding, observations, scope, project)
    p.graph._fields(native, ('task', 'thread', 'status', 'children_terminal', 'ref'), 'native')
    if any(not isinstance(value, str) or not value.strip()
           for k in ('task', 'thread') for value in (native[k], state['refs'].get(k))):
        raise ValueError('nonempty persisted and supplied native identity required')
    if any(native[k] != state['refs'].get(k) for k in ('task', 'thread')):
        raise ValueError('native identity mismatch')
    if not isinstance(native['ref'], str) or not native['ref'].strip():
        raise ValueError('native evidence reference required')
    if type(native['children_terminal']) is not bool:
        raise ValueError('native terminal boolean required')
    if not isinstance(head, str) or not (p.re.fullmatch(r'[0-9a-f]{64}', head) if task['kind'] == 'artifact' and len(head) == 64 else p.SHA.fullmatch(head)):
        raise ValueError('current full head required')
    evidence = observations['tasks'].get(task['id'])
    if evidence is not None and evidence['head'] != head:
        raise ValueError('stale host head')
    if native['status'] != 'completed' or not native['children_terminal']:
        return dict(action='blocked', slot='held', reason='native work not successfully terminal', merge_authorized=False)
    if state['retries'] >= state['retry_budget'] and state['lifecycle'] in ('blocked','correcting'):
        return dict(action='blocked', slot='held', reason='correction budget exhausted', merge_authorized=False)
    if evidence is None or not evidence['children_terminal']:
        return dict(action='blocked', slot='held', reason='missing terminal host observation', merge_authorized=False)
    delivered = p.completion(task, evidence)
    if delivered:
        # Retain immutable binding on disk as an archive; reevaluation logically retires it.
        result = p.select(plan, root, observations, scope=scope)
        candidate = result['task']
        return dict(action='continue' if candidate else 'stop', task=candidate,
                    slot='retired', merge_authorized=False)
    return dict(action='awaiting_authorization' if evidence['state']=='report_ready' else 'blocked',
                state=evidence['state'], slot='held', reason='merge boundary; report is not delivery',
                merge_authorized=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','attach','reconcile','reevaluate','resume'))
    parser.add_argument('--plan', default='docs/program/roadmap.json')
    parser.add_argument('--binding', required=True)
    parser.add_argument('--observations', required=True)
    parser.add_argument('--input', required=True, help='trusted controller JSON arguments, including scope')
    identity.add_arguments(parser)
    a = parser.parse_args(argv)
    try:
        args = p.load(a.input)
        plan = p.load(a.plan)
        creating = a.command == 'prepare'
        expect, proof = identity.enter(a.mode, a.expect, plan, a.plan, a.binding, args.get('task') if creating else None)
        fn = prepare if creating else attach if a.command=='attach' else reconcile
        if proof is not None:
            args['project'] = proof
        result = fn(plan, Path(a.plan).parent, a.binding, observations=p.load(a.observations), **args)
        if creating and expect is not None:
            identity.bind(expect, plan, a.plan, a.binding)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(f'lifecycle: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
