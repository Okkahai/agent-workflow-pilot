"""Single-writer serial continuation; never invokes a native runtime."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from agent_workflow_pilot.controller import identity, program as p, lifecycle as l


def _save(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        f.write(json.dumps(value, sort_keys=True).encode())
        f.flush()
        os.fsync(f.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def advance(plan, root, journal, binding, observations, scope, event,
            native, head, successor=None, project=None):
    """Retire current binding and prepare successor. Replay never grants dispatch.

    successor: {binding, delivery, task, acceptance, intent}, or null at stop.
    Paths must be stable absolute paths. One trusted writer per journal.
    """
    if not isinstance(scope, list) or not scope or len(set(scope)) != len(scope):
        raise ValueError('explicit nonempty unique scope required')
    if not isinstance(event, str) or not event.strip():
        raise ValueError('event required')
    binding = str(Path(binding).resolve())
    project = identity.assert_project(binding, project, plan, root)
    current_binding = p.load(binding)
    if str(Path(journal).resolve()) in (binding, current_binding['delivery']):
        raise ValueError('journal must be separate from binding/delivery')
    digest = p.fingerprint(plan, root)
    p.select(plan, root, observations, scope=scope)
    request = dict(binding=binding, scope=sorted(scope), native=native, head=head,
                   successor=successor)
    receipt = json.dumps(request, sort_keys=True)
    state = p.load(journal) if Path(journal).exists() else dict(
        plan_hash=digest, scope=sorted(scope), active=binding, events={})
    if state['plan_hash'] != digest or state['scope'] != sorted(scope):
        raise ValueError('stale journal plan/scope')
    if event in state['events']:
        old = state['events'][event]
        if old['request'] != receipt:
            raise ValueError('conflicting replay')
        checked = l.reconcile(plan, root, binding, observations, scope, native, head, project)
        if checked['slot'] != 'retired':
            return dict(checked, dispatch=False)
        return dict(old['result'], dispatch=False, replay=True)
    if state['active'] != binding:
        raise ValueError('binding is not the active serial slot')
    result = l.reconcile(plan, root, binding, observations, scope, native, head, project)
    if result['slot'] != 'retired':
        return dict(result, dispatch=False)
    recovering = 'pending' in state
    if recovering and state['pending'] != [event, receipt]:
        raise ValueError('ambiguous pending transition; reconcile original event')
    dispatch = False
    next_binding = None
    if result['task']:
        if successor is None or successor['task'] != result['task']:
            raise ValueError('selected successor contract required')
        p.graph._fields(successor, ('binding','delivery','task','acceptance','intent'), 'successor')
        next_binding = str(Path(successor['binding']).resolve())
        delivery = str(Path(successor['delivery']).resolve())
        current = current_binding
        used_intents = {l.c.load(current['delivery'])['intent']}
        used_intents.update(v['result']['intent'] for v in state['events'].values())
        used_intents.update(v['retired_intent'] for v in state['events'].values())
        if successor['intent'] in used_intents:
            raise ValueError('successor requires distinct intent')
        if len({next_binding, delivery, binding, current['delivery'], str(Path(journal).resolve())}) != 5:
            raise ValueError('successor must have distinct paths')
        retired = [v['binding'] for v in state['events'].values()]
        if next_binding in retired:
            raise ValueError('cannot reuse retired binding')
        if project is not None:
            identity.check_task(project.expectation, plan, Path(root) / project.plan_path.name,
                                successor['task'])
        # An orphan from an interrupted preparation is ambiguous: recover identity,
        # but never issue a new dispatch grant.
        dispatch = not recovering and not Path(next_binding).exists() and not Path(delivery).exists()
        state['pending'] = [event, receipt]
        _save(journal, state)
        l.prepare(plan, root, next_binding, delivery, observations, scope,
                  successor['task'], successor['acceptance'], successor['intent'])
        if project is not None:
            identity.bind(project.expectation, plan, Path(root) / project.plan_path.name, next_binding)
    elif successor is not None:
        raise ValueError('no successor authorized')
    result.update(dispatch=dispatch, binding=next_binding,
                  intent=successor['intent'] if successor else None, replay=False)
    state.pop('pending', None)
    state['active'] = next_binding
    state['events'][event] = dict(request=receipt, result=result, binding=binding,
                                 retired_intent=l.c.load(current_binding['delivery'])['intent'])
    _save(journal, state)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', default='docs/program/roadmap.json')
    parser.add_argument('--observations', required=True)
    parser.add_argument('--input', required=True)
    identity.add_arguments(parser)
    a = parser.parse_args(argv)
    try:
        plan, args = p.load(a.plan), p.load(a.input)
        expect, proof = identity.enter(a.mode, a.expect, plan, a.plan, args.get('binding'))
        if expect is not None:
            args['project'] = proof
        result = advance(plan, Path(a.plan).parent, observations=p.load(a.observations), **args)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(f'continuation: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
