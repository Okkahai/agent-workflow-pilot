"""Pure routing policy and attempt-provenance validators. Output is data, never authority.

Nothing here dispatches, polls, scrapes quota, authenticates or merges. A trusted
controller resolves identity, head, live capabilities and usage independently and
passes them in; every function compares the caller's expectation to the record
(never the record to itself). Single trusted writer, local filesystem only.
See docs/orchestration/routing.md for the callable interfaces.
"""
import argparse
import copy
import hashlib
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from agent_workflow_pilot import handoff, task_context
from agent_workflow_pilot.controller import checkpoint

POLICY_SCHEMA = 'agent-workflow-pilot.routing-policy/1'
ATTEMPTS_SCHEMA = 'agent-workflow-pilot.routing-attempts/1'
CATEGORIES = ('program', 'delivery', 'planning', 'architecture', 'standard', 'complex',
              'bugfix', 'mechanical', 'docs')
NO_SWITCH = ('program', 'delivery', 'mechanical', 'docs')  # never auto-switch
CAPABILITIES = ('child_tasks', 'cross_provider')
LEVELS3 = ('low', 'standard', 'high')
RISKS = ('none', 'low', 'high')
COSTS = ('low', 'medium', 'high')
WINDOWS = ('session', 'weekly')
BASES = ('measured', 'user_estimate', 'cached_display', 'unsupported')
STATES = ('intent', 'running', 'terminal')
OUTCOMES = ('complete', 'failed', 'cancelled', 'not_dispatched')
SKEW = timedelta(seconds=60)
HEX64 = frozenset('0123456789abcdef')


# ---------- small strict validators (accumulate problems, never echo values) ----------

def _fail(problems):
    if problems:
        raise ValueError('; '.join(problems))


def _slug(v, path, p):
    if not (isinstance(v, str) and handoff.SLUG.fullmatch(v)):
        p.append(f'{path}: must be a short slug')


def _repo(v, path, p):
    if not (isinstance(v, str) and handoff.REPO.fullmatch(v)):
        p.append(f'{path}: must look like owner/name')


def _txt(v, path, p, high=300):
    handoff._text(v, path, p, high=high)
    if isinstance(v, str) and not v.strip():
        p.append(f'{path}: blank')


def _enum(v, options, path, p):
    if not (isinstance(v, str) and v in options):
        p.append(f'{path}: must be one of {", ".join(options)}')


def _flag(v, path, p):
    if type(v) is not bool:
        p.append(f'{path}: must be a boolean')


def _count(v, path, p, lo=0, hi=10**9, none=False):
    if v is None and none:
        return
    if type(v) is not int or not lo <= v <= hi:
        p.append(f'{path}: must be an integer {lo}..{hi}')


def _pct(v, path, p):
    if type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 100:
        p.append(f'{path}: must be a number 0..100')


def _hex64(v, path, p):
    if not (isinstance(v, str) and len(v) == 64 and set(v) <= HEX64):
        p.append(f'{path}: must be a lowercase sha256')


def _when(v, path, p):
    try:
        stamp = datetime.fromisoformat(v)
        if stamp.utcoffset() is None:
            raise ValueError
        return stamp
    except (TypeError, ValueError):
        p.append(f'{path}: must be ISO-8601 with timezone')


def _list(v, path, p, high=20):
    if not isinstance(v, list) or len(v) > high:
        p.append(f'{path}: must be a list of at most {high}')
        return []
    return v


def _dup(seen, value):
    """Record a string id; True when already seen. Non-strings are reported elsewhere."""
    if not isinstance(value, str):
        return False
    if value in seen:
        return True
    seen.add(value)
    return False


def _closed(v, keys, path, p):
    return handoff._fields(v, set(keys), path, p)


def _sha_of(doc):
    return hashlib.sha256(task_context.canonical(doc)).hexdigest()


def scope_sha256(scope):
    """Hash of the approved scope/acceptance (any JSON value) the attempts must preserve."""
    return _sha_of(scope)


# ---------- policy ----------

def validate_policy(doc):
    """Validate the closed v1 policy; return its immutable sha256. Raises ValueError."""
    doc = handoff.parse(task_context.canonical(doc).decode())
    p = []
    keys = ('schema', 'version', 'providers', 'targets', 'roles', 'categories', 'capabilities',
            'forbidden', 'usage', 'snapshot_max_age_seconds', 'max_attempts')
    if not _closed(doc, keys, 'policy', p):
        _fail(p)
    if doc.get('schema') != POLICY_SCHEMA:
        p.append('schema: mismatch')
    if doc.get('version') != 1 or type(doc.get('version')) is not int:
        p.append('version: must be 1')
    _count(doc.get('snapshot_max_age_seconds'), 'snapshot_max_age_seconds', p, 1, 86400)
    _count(doc.get('max_attempts'), 'max_attempts', p, 1, 10)
    forbidden = doc.get('forbidden')
    if _closed(forbidden, ('efforts', 'model_substrings', 'options'), 'forbidden', p):
        for key in ('efforts', 'model_substrings', 'options'):
            for i, item in enumerate(_list(forbidden.get(key), 'forbidden.' + key, p)):
                _txt(item, f'forbidden.{key}[{i}]', p, 100)
    else:
        forbidden = {}
    ban = {k: tuple(v) if isinstance(v, list) else () for k, v in forbidden.items()}
    providers = doc.get('providers') if isinstance(doc.get('providers'), dict) else {}
    if not providers:
        p.append('providers: must be a non-empty object')
    for name, prov in providers.items():
        _slug(name, 'providers key', p)
        if _closed(prov, ('underlying', 'effort_option'), 'providers.' + str(name)[:40], p):
            _slug(prov.get('underlying'), 'providers.underlying', p)
            _txt(prov.get('effort_option'), 'providers.effort_option', p, 50)
            if prov.get('effort_option') in ban.get('options', ()):
                p.append('providers: forbidden option')
    targets = doc.get('targets') if isinstance(doc.get('targets'), dict) else {}
    if not targets:
        p.append('targets: must be a non-empty object')
    for name, tgt in targets.items():
        _slug(name, 'targets key', p)
        if not _closed(tgt, ('provider', 'model', 'effort'), 'targets.' + str(name)[:40], p):
            continue
        _txt(tgt.get('model'), 'targets.model', p, 100)
        _txt(tgt.get('effort'), 'targets.effort', p, 50)
        if not isinstance(tgt.get('provider'), str) or tgt['provider'] not in providers:
            p.append('targets.provider: unknown provider')
        if tgt.get('effort') in ban.get('efforts', ()):
            p.append('targets.effort: forbidden escalation')
        model = str(tgt.get('model')).lower()
        if any(str(s).lower() in model for s in ban.get('model_substrings', ())):
            p.append('targets.model: forbidden escalation')
    roles = doc.get('roles') if isinstance(doc.get('roles'), dict) else {}
    for name, role in roles.items():
        _slug(name, 'roles key', p)
        if not _closed(role, ('primary', 'alternates', 'auto_switch'), 'roles.' + str(name)[:40], p):
            continue
        alts = _list(role.get('alternates'), 'roles.alternates', p, 5)
        auto = _list(role.get('auto_switch'), 'roles.auto_switch', p, 5)
        names = [role.get('primary'), *alts]
        if (any(not isinstance(n, str) or n not in targets for n in names)
                or len(set(map(str, names))) != len(names)):
            p.append('roles: unknown or duplicate target')
        if not set(map(str, auto)) <= set(map(str, alts)):
            p.append('roles.auto_switch: must be a subset of alternates')
    _fail(p)  # later checks index into roles/targets; require them well-formed first
    categories = doc.get('categories')
    if _closed(categories, CATEGORIES, 'categories', p):
        for cat, role in categories.items():
            if not isinstance(role, str) or role not in roles:
                p.append('categories: unknown role')
            elif cat in NO_SWITCH and roles[role].get('auto_switch'):
                p.append(f'categories.{cat}: automatic switching is not allowed')
    caps = _list(doc.get('capabilities'), 'capabilities', p)
    if sorted(map(str, caps)) != sorted(CAPABILITIES):
        p.append(f'capabilities: must list exactly {", ".join(CAPABILITIES)}')
    usage = doc.get('usage')
    if _closed(usage, ('normal_above', 'conserve_min', 'fresh_seconds', 'reserve'), 'usage', p):
        for key in ('normal_above', 'conserve_min'):
            _pct(usage.get(key), 'usage.' + key, p)
        _count(usage.get('fresh_seconds'), 'usage.fresh_seconds', p, 1, 86400)
        if not p and not usage['conserve_min'] < usage['normal_above']:
            p.append('usage: conserve_min must be below normal_above')
        reserve = usage.get('reserve') if isinstance(usage.get('reserve'), dict) else None
        if reserve is None:
            p.append('usage.reserve: must be an object')
        for name, entry in (reserve or {}).items():
            if name not in providers:
                p.append('usage.reserve: unknown provider')
            elif _closed(entry, ('percent', 'enforced'), 'usage.reserve', p):
                _pct(entry.get('percent'), 'usage.reserve.percent', p)
                # No enforcement mechanism exists in T3/CLIs; a reserve can only be advisory.
                if entry.get('enforced') is not False:
                    p.append('usage.reserve.enforced: must be false (advisory only)')
    _fail(p)
    return _sha_of(doc)


def load_policy(path):
    """Read a bounded strict policy file; return (policy, sha256)."""
    policy = handoff.parse(task_context.bounded_source(path).decode('utf-8'))
    return policy, validate_policy(policy)


# ---------- usage ----------

def usage_state(policy, project, now, observations):
    """Per-provider level from trusted current observations; unknown stays unknown."""
    cfg = policy['usage']
    out = {name: dict(level='unknown', worst=None, windows=dict.fromkeys(WINDOWS), complete=False,
                      untrusted=[], advisory=[]) for name in policy['providers']}
    p = []
    trusted = {}
    for i, obs in enumerate(_list(observations, 'usage', p, 50)):
        path = f'usage[{i}]'
        if not _closed(obs, ('provider', 'project', 'window', 'remaining_percent', 'observed_at',
                             'source_ref', 'basis'), path, p):
            continue
        _enum(obs.get('provider'), tuple(policy['providers']), path + '.provider', p)
        _slug(obs.get('project'), path + '.project', p)
        _enum(obs.get('window'), WINDOWS, path + '.window', p)
        _enum(obs.get('basis'), BASES, path + '.basis', p)
        _txt(obs.get('source_ref'), path + '.source_ref', p)
        stamp = _when(obs.get('observed_at'), path + '.observed_at', p)
        if obs.get('basis') == 'measured':
            _pct(obs.get('remaining_percent'), path + '.remaining_percent', p)
        elif obs.get('remaining_percent') is not None:
            _pct(obs.get('remaining_percent'), path + '.remaining_percent', p)
        if p:
            continue
        why = None
        if obs['basis'] != 'measured':
            why = 'not_measured'
        elif obs['project'] != project:
            why = 'wrong_project'
        elif stamp > now + SKEW or now - stamp > timedelta(seconds=cfg['fresh_seconds']):
            why = 'stale'
        if why:
            out[obs['provider']]['untrusted'].append(f"{obs['window']}:{why}")
        else:
            trusted.setdefault((obs['provider'], obs['window']), []).append(obs['remaining_percent'])
    _fail(p)
    for (name, window), values in trusted.items():
        if len(values) > 1:  # two trusted readings for one window: ambiguous, treat as unknown
            out[name]['untrusted'].append(f'{window}:ambiguous')
        else:
            out[name]['windows'][window] = values[0]
    for name, state in out.items():
        known = [v for v in state['windows'].values() if v is not None]
        state['complete'] = len(known) == len(WINDOWS)
        if not known:
            continue
        worst = state['worst'] = min(known)
        state['level'] = ('exhausted' if worst <= 0 else 'restrict' if worst < cfg['conserve_min']
                          else 'conserve' if worst <= cfg['normal_above'] else 'normal')
        if not state['complete']:
            state['advisory'].append('partial_window_knowledge')
        reserve = cfg['reserve'].get(name)
        if reserve and worst <= reserve['percent']:
            state['advisory'].append('reserve_advisory_not_enforced')
    return out


# ---------- decide ----------

REQUEST = ('project', 'repo', 'task', 'attempt', 'head', 'now', 'classification', 'snapshot',
           'usage', 'metrics')
CLASSIFICATION = ('category', 'complexity', 'architecture_risk', 'security_risk',
                  'required_capabilities', 'context', 'budget', 'verification_cost')


def _snapshot(snap, policy, now, p):
    keys = ('observed_at', 'source_ref', 'providers')
    if not _closed(snap, keys, 'snapshot', p):
        return None
    stamp = _when(snap.get('observed_at'), 'snapshot.observed_at', p)
    _txt(snap.get('source_ref'), 'snapshot.source_ref', p)
    provs = snap.get('providers')
    if not isinstance(provs, dict):
        p.append('snapshot.providers: must be an object')
        return None
    for name, prov in provs.items():
        if name not in policy['providers']:
            continue  # other advertised providers are irrelevant to this policy
        if not _closed(prov, ('enabled', 'child_tasks', 'cross_provider', 'models'),
                       'snapshot.providers.' + str(name)[:40], p):
            continue
        for key in ('enabled', *CAPABILITIES):
            _flag(prov.get(key), 'snapshot.' + key, p)
        models = prov.get('models')
        if not isinstance(models, dict):
            p.append('snapshot.models: must be an object')
            continue
        for model, entry in models.items():
            if _closed(entry, ('efforts',), 'snapshot.models', p):
                for effort in _list(entry.get('efforts'), 'snapshot.efforts', p, 20):
                    _txt(effort, 'snapshot.efforts', p, 50)
    return stamp


def _classification(cls, policy, p):
    if not _closed(cls, CLASSIFICATION, 'classification', p):
        return False
    _enum(cls.get('category'), CATEGORIES, 'classification.category', p)
    _enum(cls.get('complexity'), LEVELS3, 'classification.complexity', p)
    _enum(cls.get('architecture_risk'), RISKS, 'classification.architecture_risk', p)
    _enum(cls.get('security_risk'), RISKS, 'classification.security_risk', p)
    _enum(cls.get('verification_cost'), COSTS, 'classification.verification_cost', p)
    _txt(cls.get('context'), 'classification.context', p, 500)
    caps = _list(cls.get('required_capabilities'), 'classification.required_capabilities', p, 5)
    for cap in caps:
        _enum(cap, CAPABILITIES, 'classification.required_capabilities', p)
    if len(set(map(str, caps))) != len(caps):
        p.append('classification.required_capabilities: duplicate')
    budget = cls.get('budget')
    if _closed(budget, ('max_attempts',), 'classification.budget', p):
        _count(budget.get('max_attempts'), 'classification.budget.max_attempts', p,
               1, policy['max_attempts'])
    return not p


def _blockers(tgt, snap, usage, caps, heavy):
    prov = snap['providers'].get(tgt['provider'])
    why = []
    if prov is None:
        why.append('provider_missing')
    elif not prov['enabled']:
        why.append('provider_disabled')
    else:
        model = prov['models'].get(tgt['model'])
        if model is None:
            why.append('model_missing')
        elif tgt['effort'] not in model['efforts']:
            why.append('effort_missing')
        why += ['capability_missing:' + c for c in caps if not prov[c]]
    level = usage[tgt['provider']]['level']
    if level == 'exhausted':
        why.append('usage_exhausted')
    elif level == 'restrict' and heavy:
        why.append('usage_restricted_heavy_work')
    return why


def _route(policy, name):
    tgt = policy['targets'][name]
    effort_option = policy['providers'][tgt['provider']]['effort_option']
    return dict(target=name, provider=tgt['provider'], model=tgt['model'], effort=tgt['effort'],
                options={effort_option: tgt['effort']})


def decide(policy, request):
    """Return a routing decision (route / candidate / stop). Never executes or authorizes.

    A route is the policy primary, or an automatically authorized Sonnet/Sol fallback
    that still needs `switch` checks in `apply`. A candidate is an approved alternate
    that requires the caller's explicit choice. Unknown usage never triggers a switch.
    """
    sha = validate_policy(policy)
    request = handoff.parse(task_context.canonical(request).decode())
    p = []
    if not _closed(request, REQUEST, 'request', p):
        _fail(p)
    _slug(request.get('project'), 'project', p)
    _repo(request.get('repo'), 'repo', p)
    _slug(request.get('task'), 'task', p)
    _slug(request.get('attempt'), 'attempt', p)
    handoff._sha(request.get('head'), 'head', p)
    now = _when(request.get('now'), 'now', p)
    cls = request.get('classification')
    _classification(cls, policy, p)
    stamp = _snapshot(request.get('snapshot'), policy, now, p) if now else None
    metrics = request.get('metrics')
    if _closed(metrics, ('tokens', 'elapsed_seconds', 'attempts'), 'metrics', p):
        for key in ('tokens', 'elapsed_seconds', 'attempts'):
            _count(metrics.get(key), 'metrics.' + key, p, none=True)
    _fail(p)
    base = dict(authorizes=False, policy_sha256=sha,
                identity={k: request[k] for k in ('project', 'repo', 'task', 'attempt', 'head')},
                metrics=metrics, scope_approval='not inferred from classification')
    usage = usage_state(policy, request['project'], now, request['usage'])
    base['usage'] = usage
    if stamp > now + SKEW or now - stamp > timedelta(seconds=policy['snapshot_max_age_seconds']):
        return dict(base, decision='stop', reasons=['stale_capabilities'])
    role = policy['roles'][policy['categories'][cls['category']]]
    heavy = (cls['complexity'] == 'high' or 'high' in (cls['architecture_risk'], cls['security_risk'])
             or cls['verification_cost'] == 'high')
    caps = cls['required_capabilities']
    blocked = {n: _blockers(policy['targets'][n], request['snapshot'], usage, caps, heavy)
               for n in (role['primary'], *role['alternates'])}
    base['blocked'] = {n: why for n, why in blocked.items() if why}
    if not blocked[role['primary']]:
        return dict(base, decision='route', route=_route(policy, role['primary']), fallback=None)
    candidates = [n for n in role['alternates'] if not blocked[n]]
    auto = [n for n in candidates if n in role['auto_switch']
            and request['classification']['category'] in ('standard', 'complex', 'bugfix')]
    if auto:
        return dict(base, decision='route', route=_route(policy, auto[0]),
                    fallback=dict(from_target=role['primary'], reasons=blocked[role['primary']],
                                  requires='apply intent checks'))
    if candidates:
        return dict(base, decision='candidate', candidates=[_route(policy, n) for n in candidates],
                    reasons=blocked[role['primary']], requires='caller choice')
    return dict(base, decision='stop', reasons=sorted({r for v in blocked.values() for r in v}))


# ---------- attempt provenance ----------

BIND = ('project', 'repo', 'task', 'plan_hash', 'context_hash', 'scope_sha256', 'retry_budget',
        'head', 'branch', 'worktree', 'pr')
RECORD = ('schema', 'project', 'repo', 'task', 'policy_sha256', 'plan_hash', 'context_hash',
          'scope_sha256', 'retry_budget', 'checkpoint_key', 'workspace', 'attempts', 'events')
ATTEMPT = ('id', 'seq', 'role', 'target', 'route', 'client_request_id', 'state', 'native',
           'returned', 'route_match', 'writer', 'children', 'outcome', 'predecessor', 'head')


def new_record(policy, *, project, repo, task, plan_hash, context_hash, scope_sha256,
               retry_budget, checkpoint_key, workspace):
    """Create the routing sidecar for one logical task. References the delivery checkpoint."""
    rec = dict(schema=ATTEMPTS_SCHEMA, project=project, repo=repo, task=task,
               policy_sha256=validate_policy(policy), plan_hash=plan_hash,
               context_hash=context_hash, scope_sha256=scope_sha256, retry_budget=retry_budget,
               checkpoint_key=checkpoint_key, workspace=dict(workspace), attempts=[], events={})
    return validate_record(rec, policy)


def _route_triple(v, path, p):
    if _closed(v, ('provider', 'model', 'effort'), path, p):
        for key in v:
            _txt(v[key], f'{path}.{key}', p, 100)


def validate_record(rec, policy):
    """Validate a sidecar against its own policy version. Raises ValueError."""
    sha = validate_policy(policy)
    p = []
    if not _closed(rec, RECORD, 'record', p):
        _fail(p)
    if rec.get('schema') != ATTEMPTS_SCHEMA:
        p.append('schema: mismatch')
    _slug(rec.get('project'), 'project', p)
    _repo(rec.get('repo'), 'repo', p)
    _slug(rec.get('task'), 'task', p)
    for key in ('plan_hash', 'context_hash', 'scope_sha256', 'policy_sha256'):
        _hex64(rec.get(key), key, p)
    if rec.get('policy_sha256') != sha:
        p.append('policy_sha256: policy version changed; migrate explicitly')
    _count(rec.get('retry_budget'), 'retry_budget', p, 0, 10)
    _txt(rec.get('checkpoint_key'), 'checkpoint_key', p, 100)
    ws = rec.get('workspace')
    if _closed(ws, ('branch', 'worktree', 'pr'), 'workspace', p):
        _txt(ws.get('branch'), 'workspace.branch', p, 100)
        _txt(ws.get('worktree'), 'workspace.worktree', p, 300)
        if ws.get('pr') is not None:
            _txt(ws.get('pr'), 'workspace.pr', p, 300)
    events = rec.get('events')
    if not isinstance(events, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                           for k, v in events.items()):
        p.append('events: invalid receipts')
    attempts = _list(rec.get('attempts'), 'attempts', p, policy['max_attempts'])
    seen = {k: set() for k in ('id', 'client_request_id', 'task', 'thread')}
    active = 0
    for i, a in enumerate(attempts):
        path = f'attempts[{i}]'
        if not _closed(a, ATTEMPT, path, p):
            continue
        _slug(a.get('id'), path + '.id', p)
        _count(a.get('seq'), path + '.seq', p, 1, 100)
        if a.get('seq') != i + 1:
            p.append(path + '.seq: must be sequential')
        _enum(a.get('state'), STATES, path + '.state', p)
        _enum(a.get('role'), tuple(policy['roles']), path + '.role', p)
        _enum(a.get('target'), tuple(policy['targets']), path + '.target', p)
        if isinstance(a.get('role'), str) and a['role'] in policy['roles']:
            role = policy['roles'][a['role']]
            if a.get('target') not in (role['primary'], *role['alternates']):
                p.append(path + '.target: not allowed for role')
        _txt(a.get('client_request_id'), path + '.client_request_id', p, 100)
        handoff._sha(a.get('head'), path + '.head', p)
        if isinstance(a.get('target'), str) and a['target'] in policy['targets'] and a.get('route') != {
                k: policy['targets'][a['target']][k] for k in ('provider', 'model', 'effort')}:
            p.append(path + '.route: differs from policy target')
        _enum(a.get('writer'), ('unknown', 'active', 'none'), path + '.writer', p)
        if a.get('outcome') is not None:
            _enum(a.get('outcome'), OUTCOMES, path + '.outcome', p)
        if a.get('predecessor') != (attempts[i - 1].get('id') if i and isinstance(attempts[i - 1], dict) else None):
            p.append(path + '.predecessor: must name the previous attempt')
        if a.get('native') is not None and _closed(a['native'], ('task', 'thread'), path + '.native', p):
            for k in ('task', 'thread'):
                _txt(a['native'].get(k), f'{path}.native.{k}', p, 200)
                if _dup(seen[k], a['native'].get(k)):
                    p.append(path + '.native: duplicate native id across attempts')
        if a.get('returned') is not None:
            _route_triple(a['returned'], path + '.returned', p)
        if a.get('children') is not None:
            for child in _list(a['children'], path + '.children', p, 20):
                if _closed(child, ('id', 'state'), path + '.children', p):
                    _txt(child.get('id'), path + '.children.id', p, 200)
                    _enum(child.get('state'), ('running', 'terminal'), path + '.children.state', p)
        for k in ('id', 'client_request_id'):
            if _dup(seen[k], a.get(k)):
                p.append(f'{path}.{k}: duplicate')
        if a.get('state') == 'terminal':
            if not a.get('outcome') or a.get('writer') != 'none' or a.get('children') is None:
                p.append(path + ': terminal requires outcome, writer none and known children')
            kids = a['children'] if isinstance(a.get('children'), list) else []
            if any(not isinstance(c, dict) or c.get('state') != 'terminal' for c in kids):
                p.append(path + ': terminal with live children')
        else:
            active += 1
            if a.get('outcome') is not None:
                p.append(path + ': outcome only on terminal attempts')
        if a.get('state') == 'running' and not a.get('native'):
            p.append(path + ': running requires native ids')
    if active > 1 or (active and attempts and attempts[-1].get('state') == 'terminal'):
        p.append('attempts: more than one non-terminal attempt')
    _fail(p)
    return rec


def _bind(rec, expected, policy):
    """Compare caller-resolved expectations with the record; never the record to itself."""
    p = []
    if not _closed(expected, BIND, 'expected', p):
        _fail(p)
    _slug(expected.get('project'), 'expected.project', p)
    _repo(expected.get('repo'), 'expected.repo', p)
    _slug(expected.get('task'), 'expected.task', p)
    for key in ('plan_hash', 'context_hash', 'scope_sha256'):
        _hex64(expected.get(key), 'expected.' + key, p)
    _count(expected.get('retry_budget'), 'expected.retry_budget', p, 0, 10)
    handoff._sha(expected.get('head'), 'expected.head', p)
    for key in ('branch', 'worktree'):
        _txt(expected.get(key), 'expected.' + key, p)
    if expected.get('pr') is not None:
        _txt(expected.get('pr'), 'expected.pr', p)
    _fail(p)
    validate_record(rec, policy)
    for key in ('project', 'repo', 'task', 'plan_hash', 'context_hash', 'scope_sha256', 'retry_budget'):
        if rec[key] != expected[key]:
            p.append(f'{key}: differs from independent expectation (cross-project or stale record)')
    for key in ('branch', 'worktree', 'pr'):
        if rec['workspace'][key] != expected[key]:
            p.append(f'workspace.{key}: differs from independent expectation')
    _fail(p)


def _switch_problems(rec, policy, expected, cp, role, target):
    p = []
    try:
        checkpoint.validate(cp)
    except (ValueError, TypeError):
        return ['checkpoint: invalid']
    if cp['task_key'] != rec['checkpoint_key']:
        p.append('checkpoint: belongs to a different task')
    if cp['retry_budget'] != rec['retry_budget']:
        p.append('checkpoint: retry budget changed')
    if cp['lifecycle'] == 'blocked':
        p.append('checkpoint: blocked (correction budget exhausted or unresolved) holds the slot')
    spec = policy['roles'][role]
    if target not in (spec['primary'], *spec['alternates']):
        p.append('target: not allowed for role')
    last = rec['attempts'][-1] if rec['attempts'] else None
    if last is None:
        return p
    if cp['head'] != expected['head']:
        p.append('checkpoint: stale head; reconcile before a new attempt')
    for ref, key in (('branch', 'branch'), ('pr', 'pr')):
        if cp['refs'].get(ref) != expected[key]:
            p.append(f'checkpoint: {ref} differs from fresh observation')
    if last['state'] != 'terminal':
        p.append('predecessor: not terminal; slot is held')
    if last['writer'] != 'none' or last['children'] is None:
        p.append('predecessor: writer or children unknown; slot is held')
    allowed = {spec['primary'], *spec['auto_switch']}
    if last['target'] != target and not {last['target'], target} <= allowed:
        p.append('switch: not an automatically authorized fallback for this role')
    if last['role'] != role:
        p.append('switch: task role changed')
    return p


def apply(rec, policy, expected, event_id, action, data, cp=None):
    """Pure transition: returns (new_record, outcome). Raises ValueError on any refusal.

    Actions: intent {attempt, role, target, client_request_id}; started {attempt, native,
    returned}; terminal {attempt, outcome, writer, children}; release {attempt} (intent that
    verifiably never reached native dispatch). Replay of an identical event never grants
    dispatch. Caller persists the new record before issuing any native call.
    """
    _bind(rec, expected, policy)
    if not isinstance(event_id, str) or not handoff.SLUG.fullmatch(event_id):
        raise ValueError('event ID required')
    receipt = json.dumps([action, data], sort_keys=True, allow_nan=False)
    if event_id in rec['events']:
        if rec['events'][event_id] != receipt:
            raise ValueError('event ID reused with different payload')
        return copy.deepcopy(rec), dict(dispatch_allowed=False, replay=True, authorizes=False)
    new = copy.deepcopy(rec)
    if not isinstance(data, dict):
        raise ValueError('data: must be an object')
    keys = dict(intent={'attempt', 'role', 'target', 'client_request_id'},
                started={'attempt', 'native', 'returned'},
                terminal={'attempt', 'outcome', 'writer', 'children'}, release={'attempt'})
    if action not in keys or set(data) != keys[action]:
        raise ValueError('invalid action or payload')
    p = []
    _slug(data['attempt'], 'attempt', p)
    _fail(p)
    mine = [a for a in new['attempts'] if a['id'] == data['attempt']]
    outcome = dict(dispatch_allowed=False, replay=False, authorizes=False)
    if action == 'intent':
        if mine or any(a['client_request_id'] == data['client_request_id'] for a in new['attempts']):
            raise ValueError('duplicate attempt or clientRequestId')
        _enum(data['role'], tuple(policy['roles']), 'role', p)
        _enum(data['target'], tuple(policy['targets']), 'target', p)
        _fail(p)
        if cp is None:
            raise ValueError('checkpoint required')
        problems = _switch_problems(new, policy, expected, cp, data['role'], data['target'])
        if len(new['attempts']) >= policy['max_attempts']:
            problems.append('attempts: policy maximum reached')
        _fail(problems)
        tgt = policy['targets'][data['target']]
        new['attempts'].append(dict(
            id=data['attempt'], seq=len(new['attempts']) + 1, role=data['role'], target=data['target'],
            route={k: tgt[k] for k in ('provider', 'model', 'effort')},
            client_request_id=data['client_request_id'], state='intent', native=None, returned=None,
            route_match=None, writer='unknown', children=None, outcome=None,
            predecessor=new['attempts'][-1]['id'] if new['attempts'] else None,
            head=expected['head']))
        outcome['dispatch_allowed'] = True
    else:
        if len(mine) != 1 or new['attempts'][-1] is not mine[0]:
            raise ValueError('unknown attempt or not the latest attempt')
        a = mine[0]
        if action == 'started':
            if a['state'] != 'intent':
                raise ValueError('attempt already reconciled')
            _closed(data['native'], ('task', 'thread'), 'native', p)
            _route_triple(data['returned'], 'returned', p)
            _fail(p)
            a.update(state='running', native=data['native'], returned=data['returned'],
                     writer='active', route_match=data['returned'] == a['route'])
        elif action == 'release':
            if a['state'] != 'intent':
                raise ValueError('only an unreconciled intent can be released')
            a.update(state='terminal', outcome='not_dispatched', writer='none', children=[])
        else:
            if a['state'] == 'terminal':
                raise ValueError('attempt already terminal')
            if a['state'] == 'intent':
                raise ValueError('reconcile native ids (started/release) first')
            _enum(data['outcome'], tuple(o for o in OUTCOMES if o != 'not_dispatched'), 'outcome', p)
            if data['writer'] != 'none':
                p.append('writer: must be none before terminal')
            kids = _list(data['children'], 'children', p)
            for kid in kids:
                if _closed(kid, ('id', 'state'), 'children', p) and kid.get('state') != 'terminal':
                    p.append('children: live child holds the slot')
            _fail(p)
            a.update(state='terminal', outcome=data['outcome'], writer='none', children=kids)
    new['events'][event_id] = receipt
    return validate_record(new, policy), outcome


def refresh(rec, policy, expected, cp, context, root, plan_path):
    """Refresh current context after a commit, retaining historic attempts/receipts.

    Requires independently reconstructed M1 sources and a reconciled checkpoint;
    never releases a writer or authorizes dispatch.
    """
    previous = dict(expected, plan_hash=rec['plan_hash'], context_hash=rec['context_hash'])
    _bind(rec, previous, policy)
    last = rec['attempts'][-1] if rec['attempts'] else None
    if last is None or last['state'] != 'terminal' or last['head'] == expected['head']:
        raise ValueError('refresh: requires terminal predecessor and a changed head')
    _fail(_switch_problems(rec, policy, previous, cp, last['role'], last['target']))
    rebuilt = task_context.reconstruct(context, root, plan_path, current_head=expected['head'],
                                      task_id=expected['task'], repo=expected['repo'])
    if rebuilt['context_hash'] != expected['context_hash'] or context['plan_hash'] != expected['plan_hash']:
        raise ValueError('refresh: reconstructed hashes differ from expectation')
    new = copy.deepcopy(rec)
    new.update(plan_hash=expected['plan_hash'], context_hash=expected['context_hash'])
    _bind(new, expected, policy)
    return new


def recover(rec, policy, expected, cp, *, context_hash=None):
    """Fresh-process summary. Never dispatches; the slot is free only when provably so."""
    _bind(rec, expected, policy)
    last = rec['attempts'][-1] if rec['attempts'] else None
    holds = []
    if context_hash is not None and context_hash != rec['context_hash']:
        raise ValueError('context_hash: reconstructed context differs from the record')
    if last and last['state'] != 'terminal':
        holds.append(f"attempt {last['id']} is {last['state']}; reconcile native task before any new dispatch")
    if last and last['route_match'] is False:
        holds.append('returned route differs from requested route')
    if last and last['state'] != 'terminal':
        problems = []
    else:
        problems = _switch_problems(rec, policy, expected, cp, last['role'], last['target']) if last else []
    return dict(authorizes=False, dispatch_allowed=False, attempts=len(rec['attempts']),
                latest=last and {k: last[k] for k in ('id', 'state', 'target', 'outcome', 'writer')},
                slot='held' if holds or problems else 'free', holds=holds + problems)


# ---------- final review validation ----------

REVIEW = ('provider', 'model', 'effort', 'native_task', 'project', 'repo', 'task', 'head',
          'authored', 'findings', 'evidence_ref')


def validate_reviews(rec, policy, expected, reviews):
    """Check opposite-provider, non-author, exact-head review coverage. Never merges.

    Each author provider (from the returned route of real attempts) needs a review by a
    different underlying provider. Underlying identity comes from the policy, so provider
    instance aliases cannot masquerade as another provider. The existing delivery gate
    remains required.
    """
    _bind(rec, expected, policy)
    authors = [a for a in rec['attempts'] if a['native'] and a['outcome'] != 'not_dispatched']
    if not authors:
        raise ValueError('no authored attempt to review')
    under = {n: v['underlying'] for n, v in policy['providers'].items()}
    p = []
    if any(a['state'] != 'terminal' for a in rec['attempts']):
        p.append('attempt: non-terminal attempt may still be writing')
    owner = set()
    for a in authors:
        prov = a['returned']['provider']
        if prov not in under:
            p.append('author: unknown provider instance')
        owner.add(under.get(prov))
        if not a['route_match']:
            p.append('author: returned route differs from requested route')
    author_tasks = {a['native']['task'] for a in authors} | {a['native']['thread'] for a in authors}
    coverage = {}
    for i, rv in enumerate(_list(reviews, 'reviews', p, 20)):
        path = f'reviews[{i}]'
        if not _closed(rv, REVIEW, path, p):
            continue
        before = len(p)
        _enum(rv.get('provider'), tuple(under), path + '.provider', p)
        for key in ('model', 'effort', 'native_task', 'evidence_ref'):
            _txt(rv.get(key), f'{path}.{key}', p, 300)
        _flag(rv.get('authored'), path + '.authored', p)
        for f in _list(rv.get('findings'), path + '.findings', p, 20):
            _txt(f, path + '.findings', p, 500)
        handoff._sha(rv.get('head'), path + '.head', p)
        if len(p) != before:
            continue
        if (rv['project'], rv['repo'], rv['task']) != (expected['project'], expected['repo'], expected['task']):
            p.append(path + ': evidence belongs to a different project/repo/task')
        elif rv['head'] != expected['head']:
            p.append(path + ': stale; not the exact current head')
        elif rv['authored'] or rv['native_task'] in author_tasks:
            p.append(path + ': reviewer is an author')
        elif rv['findings']:
            p.append(path + ': open findings')
        else:
            coverage.setdefault(under[rv['provider']], rv['native_task'])
            continue
    for provider in sorted(owner - {None}):
        if not any(u != provider for u in coverage):
            p.append(f'missing opposite-provider review of {provider} authorship')
    return dict(authorizes=False, ready=not p, authors=sorted(owner - {None}), coverage=coverage,
                problems=p, note='delivery gate and protections remain required; never merges')


# ---------- persistence and CLI ----------

def save(path, rec):
    """Atomic replacement on one trusted local filesystem, one writer only."""
    payload = json.dumps(rec, sort_keys=True, indent=2)
    handoff.parse(payload)
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


def _read(path):
    return handoff.parse(task_context.bounded_source(path).decode('utf-8'))


def _stdin():
    return handoff.parse(sys.stdin.read(handoff.MAX_BYTES + 1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('policy').add_argument('policy')
    d = sub.add_parser('decide', help='stdin: request JSON; stdout: decision')
    d.add_argument('--policy', required=True)
    for name in ('init', 'apply', 'recover', 'reviews', 'refresh'):
        s = sub.add_parser(name)
        s.add_argument('record')
        s.add_argument('--policy', required=True)
        s.add_argument('--expected', help='independent expectation JSON file')
        s.add_argument('--checkpoint', help='delivery checkpoint JSON file')
    for name in ('recover', 'refresh'):
        r = sub.choices[name]
        r.add_argument('--context', help='existing M1 task-context envelope')
        r.add_argument('--root')
        r.add_argument('--plan')
    a = ap.parse_args(argv)
    try:
        policy, sha = load_policy(a.policy)
        if a.cmd == 'policy':
            out = dict(valid=True, policy_sha256=sha)
        elif a.cmd == 'decide':
            request = _stdin()
            request.setdefault('now', datetime.now().astimezone().isoformat())
            out = decide(policy, request)
        elif a.cmd == 'init':
            rec = new_record(policy, **_stdin())
            if Path(a.record).exists():
                raise ValueError('record already exists')
            save(a.record, rec)
            out = dict(ok=True, authorizes=False)
        else:
            rec, expected = _read(a.record), _read(a.expected)
            cp = _read(a.checkpoint) if a.checkpoint else None
            if a.cmd == 'refresh':
                new = refresh(rec, policy, expected, cp, _read(a.context), a.root, Path(a.root) / a.plan)
                save(a.record, new)
                out = dict(ok=True, authorizes=False, dispatch_allowed=False)
            elif a.cmd == 'apply':
                event = _stdin()
                new, outcome = apply(rec, policy, expected, event.get('event_id'),
                                     event.get('action'), event.get('data'), cp)
                save(a.record, new)
                out = dict(ok=True, **outcome)
            elif a.cmd == 'reviews':
                out = validate_reviews(rec, policy, expected, _stdin())
            else:
                digest = None
                if a.context:
                    digest = task_context.reconstruct(
                        _read(a.context), a.root, Path(a.root) / a.plan, current_head=expected['head'],
                        task_id=expected['task'], repo=expected['repo'])['context_hash']
                out = recover(rec, policy, expected, cp, context_hash=digest)
    except (ValueError, OSError, RecursionError, TypeError, KeyError,
            AttributeError) as error:
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(json.dumps(dict(ok=False, authorizes=False, dispatch_allowed=False, error=message)))
        return 1
    print(json.dumps(out, sort_keys=True))
    return int(out.get('ready') is False or out.get('valid') is False)


if __name__ == '__main__':
    sys.exit(main())
