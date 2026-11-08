"""Single-writer local recovery checkpoint. Never evidence or merge authority."""
import copy
import json
import os
from pathlib import Path
import tempfile

from agent_workflow_pilot.handoff import SHA, parse

STATES = {'planned', 'dispatching', 'building', 'awaiting_ci', 'awaiting_review',
          'correcting', 'blocked', 'complete', 'awaiting_authorization'}
REFS = {'environment', 'provider', 'task', 'thread', 'branch', 'pr'}


def new(task_key, acceptance, dependencies=(), retry_budget=2):
    state = dict(version=1, task_key=task_key, acceptance=list(acceptance),
                 dependencies=list(dependencies), retry_budget=retry_budget,
                 retries=0, lifecycle='planned', blocker=None, refs={}, head=None,
                 ci=None, review=None, intent=None, events={})
    return validate(state)


def validate(s):
    fields = {'version', 'task_key', 'acceptance', 'dependencies', 'retry_budget',
              'retries', 'lifecycle', 'blocker', 'refs', 'head', 'ci', 'review',
              'intent', 'events'}
    if not isinstance(s, dict) or set(s) != fields:
        raise ValueError('invalid checkpoint fields')
    def text(v):
        return isinstance(v, str) and bool(v.strip())
    if type(s['version']) is not int or s['version'] != 1 or not text(s['task_key']):
        raise ValueError('invalid identity/version')
    for key in ('acceptance', 'dependencies'):
        if not isinstance(s[key], list) or any(not text(v) for v in s[key]):
            raise ValueError('invalid task contract')
    if not s['acceptance'] or s['task_key'] in s['dependencies']:
        raise ValueError('empty acceptance or self dependency')
    if any(type(s[k]) is not int or s[k] < 0 for k in ('retry_budget', 'retries')):
        raise ValueError('invalid retry counts')
    if s['retries'] > s['retry_budget'] or s['lifecycle'] not in STATES:
        raise ValueError('invalid lifecycle/budget')
    if not isinstance(s['refs'], dict) or set(s['refs']) - REFS or any(not text(v) for v in s['refs'].values()):
        raise ValueError('invalid native references')
    if s['head'] is not None and (not isinstance(s['head'], str) or not SHA.fullmatch(s['head'])):
        raise ValueError('invalid head')
    for key in ('ci', 'review'):
        evidence = s[key]
        if evidence is not None and (not isinstance(evidence, dict) or set(evidence) != {'head', 'ref'} or
                                     not s['head'] or evidence['head'] != s['head'] or not text(evidence['ref'])):
            raise ValueError('invalid or stale evidence reference')
    if s['blocker'] is not None and not text(s['blocker']):
        raise ValueError('invalid blocker')
    if (s['lifecycle'] == 'blocked') != (s['blocker'] is not None):
        raise ValueError('blocked state requires reason')
    if (s['intent'] is not None or s['lifecycle'] == 'dispatching') and not text(s['intent']):
        raise ValueError('invalid clientRequestId')
    if not isinstance(s['events'], dict) or any(not text(k) or not text(v) for k, v in s['events'].items()):
        raise ValueError('invalid replay receipts')
    if s['lifecycle'] in {'awaiting_ci', 'awaiting_review', 'complete', 'awaiting_authorization'} and not s['head']:
        raise ValueError('head required')
    if s['lifecycle'] in {'awaiting_review', 'complete', 'awaiting_authorization'} and not s['ci']:
        raise ValueError('CI reference required')
    if s['lifecycle'] in {'complete', 'awaiting_authorization'} and not s['review']:
        raise ValueError('review reference required')
    return s


def apply(state, event_id, action, **data):
    """Pure transition from trusted controller input; receipts deduplicate local events.

    Reconciliation always discards evidence; native records must be read again.
    No function dispatches, watches, authenticates evidence or merges.
    """
    validate(state)
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError('event ID required')
    receipt = json.dumps([action, data], sort_keys=True, allow_nan=False)
    if event_id in state['events']:
        if state['events'][event_id] != receipt:
            raise ValueError('event ID reused with different payload')
        return copy.deepcopy(state)
    s = copy.deepcopy(state)
    phase = s['lifecycle']
    allowed = {
        'dispatch': ({'planned', 'correcting'}, {'client_request_id', 'completed_dependencies'}),
        'started': ({'dispatching'}, {'refs'}),
        'head': ({'building', 'awaiting_ci', 'awaiting_review', 'complete', 'awaiting_authorization'}, {'head'}),
        'ci': ({'awaiting_ci'}, {'head', 'ref'}),
        'review': ({'awaiting_review'}, {'head', 'ref'}),
        'correction': ({'awaiting_ci', 'awaiting_review'}, {'reason'}),
        'block': (STATES, {'reason'}),
        'reconcile': (STATES, {'refs', 'head'}),
        'report': ({'complete'}, set()),
    }
    if action not in allowed or phase not in allowed[action][0] or set(data) != allowed[action][1]:
        raise ValueError('invalid transition or payload')
    if action == 'dispatch':
        if not isinstance(data['completed_dependencies'], list) or not set(s['dependencies']) <= set(data['completed_dependencies']):
            raise ValueError('dependencies incomplete')
        s.update(intent=data['client_request_id'], lifecycle='dispatching')
    elif action == 'started':
        if not {'task', 'thread'} <= data['refs'].keys():
            raise ValueError('native task/thread required')
        s['refs'].update(data['refs'])
        s['lifecycle'] = 'building'
    elif action in {'head', 'reconcile'}:
        if not isinstance(data['head'], str) or not SHA.fullmatch(data['head']):
            raise ValueError('full head required')
        if action == 'reconcile':
            s['refs'] = data['refs']
        if action == 'reconcile' or phase == 'building' or data['head'] != s['head']:
            s.update(head=data['head'], ci=None, review=None, blocker=None, lifecycle='awaiting_ci')
    elif action in {'ci', 'review'}:
        if data['head'] != s['head']:
            raise ValueError('stale evidence')
        s[action] = data
        s['lifecycle'] = 'awaiting_review' if action == 'ci' else 'complete'
    elif action == 'correction':
        if not isinstance(data['reason'], str) or not data['reason'].strip():
            raise ValueError('correction reason required')
        s.update(ci=None, review=None)
        if s['retries'] == s['retry_budget']:
            s.update(lifecycle='blocked', blocker='correction budget exhausted: ' + data['reason'])
        else:
            s['retries'] += 1
            s['lifecycle'] = 'correcting'
    elif action == 'block':
        s.update(lifecycle='blocked', blocker=data['reason'], ci=None, review=None)
    else:
        s['lifecycle'] = 'awaiting_authorization'
    s['events'][event_id] = receipt
    return validate(s)


def save(path, state):
    """Atomic replacement on one trusted local filesystem, one writer only."""
    payload = json.dumps(validate(state), sort_keys=True, indent=2)
    parse(payload)  # Same bounded strict JSON reader used on resume.
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload.encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load(path):
    with open(path, encoding='utf-8') as stream:
        return validate(parse(stream.read(65537)))
