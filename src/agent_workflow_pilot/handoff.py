"""Machine-checkable, bounded, inert handoff records between agent roles.

A valid handoff is structurally well-formed data and nothing more. It is not
authenticated, not evidence a gate may trust, and carries no authorization:
approval, merge eligibility and permissions are decided elsewhere (see gate.py
and docs/engineering-standard.md). Text fields are never executed, evaluated,
templated or followed; problem messages name fields, never echo their values.
"""
import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime

SCHEMA = 'agent-workflow-pilot.handoff/1'
ROLES = ('coordinator', 'implementer', 'reviewer')
RESULTS = ('pass', 'fail', 'pending', 'not_run')
MAX_BYTES = 64 * 1024
MAX_ITEMS = 20
SHA = re.compile(r'[0-9a-f]{40}')
SLUG = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
REPO = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}')
# Keys that would smuggle authorization semantics; rejected by name for a clear message.
FORBIDDEN = frozenset({'approved', 'approval', 'authorized', 'authorization', 'authorised',
                       'eligible', 'merge', 'mergeable', 'permission', 'permissions',
                       'bypass', 'trusted', 'verified', 'run', 'exec'})

TOP = {'schema', 'task_id', 'repo', 'branch', 'base', 'head', 'from_role', 'receiving_role',
       'summary', 'tests', 'evidence', 'provenance', 'unknowns'}
TEST = {'command', 'result', 'head', 'detail'}
EVID = {'kind', 'ref', 'head'}
PROV = {'author', 'runtime', 'created_at', 'basis'}


def _pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise ValueError('duplicate key')
        out[key] = value
    return out


def _reject_constant(_):
    raise ValueError('non-finite number')


def parse(raw):
    """Parse bounded JSON text strictly (no duplicate keys, NaN or Infinity)."""
    if len(raw.encode('utf-8', 'surrogatepass')) > MAX_BYTES:
        raise ValueError(f'input exceeds {MAX_BYTES} bytes')
    try:
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except RecursionError:
        raise ValueError('nesting too deep') from None


def _text(value, path, problems, low=1, high=200, multiline=False):
    if not isinstance(value, str):
        problems.append(f'{path}: must be a string')
        return
    if not low <= len(value) <= high:
        problems.append(f'{path}: length must be {low}..{high}')
    for ch in value:
        cat = unicodedata.category(ch)
        if cat in ('Cs', 'Cn') or (cat in ('Cc', 'Cf', 'Zl', 'Zp')
                                   and not (multiline and ch in '\n\t')):
            problems.append(f'{path}: contains control, format or invalid characters')
            return


def _fields(obj, allowed, path, problems):
    if not isinstance(obj, dict):
        problems.append(f'{path}: must be an object')
        return False
    for key in obj:
        if not isinstance(key, str):
            problems.append(f'{path}: non-string key')
        elif key.lower() in FORBIDDEN:
            problems.append(f'{path}: field carries authorization semantics; not allowed')
        elif key not in allowed:
            problems.append(f'{path}: unknown field')
    for key in sorted(allowed - obj.keys()):
        problems.append(f'{path}.{key}: missing')
    return True


def _sha(value, path, problems):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        problems.append(f'{path}: must be a full 40-char lowercase hex SHA')


def _items(value, path, problems, minimum):
    if not isinstance(value, list):
        problems.append(f'{path}: must be a list')
        return []
    if not minimum <= len(value) <= MAX_ITEMS:
        problems.append(f'{path}: must hold {minimum}..{MAX_ITEMS} entries')
        return value[:MAX_ITEMS]
    return value


def _same_head(entry, path, head, problems):
    _sha(entry.get('head'), path + '.head', problems)
    if isinstance(entry.get('head'), str) and SHA.fullmatch(entry['head']) and entry['head'] != head:
        problems.append(f'{path}.head: stale or mismatched against handoff head')


def problems_for(doc, current_head=None, role=None):
    """Return a list of problems; empty means structurally valid, not authorized."""
    problems = []
    if not _fields(doc, TOP, 'handoff', problems):
        return problems
    if 'schema' in doc and doc['schema'] != SCHEMA:
        problems.append(f'schema: must be {SCHEMA}')
    for key in ('branch', 'base'):
        if key in doc:
            _text(doc[key], key, problems, high=100)
    if 'task_id' in doc and not (isinstance(doc['task_id'], str) and SLUG.fullmatch(doc['task_id'])):
        problems.append('task_id: must be a short slug')
    if 'repo' in doc and not (isinstance(doc['repo'], str) and REPO.fullmatch(doc['repo'])):
        problems.append('repo: must look like owner/name')
    head = doc.get('head')
    if 'head' in doc:
        _sha(head, 'head', problems)
    for key in ('from_role', 'receiving_role'):
        if key in doc and doc[key] not in ROLES:
            problems.append(f'{key}: must be one of {", ".join(ROLES)}')
    if doc.get('from_role') == doc.get('receiving_role') and doc.get('from_role') in ROLES:
        problems.append('receiving_role: must differ from from_role')
    if 'summary' in doc:
        _text(doc['summary'], 'summary', problems, high=2000, multiline=True)

    for i, test in enumerate(_items(doc.get('tests'), 'tests', problems, 1)):
        path = f'tests[{i}]'
        if _fields(test, TEST, path, problems):
            _text(test.get('command'), path + '.command', problems, high=300)
            if test.get('result') not in RESULTS:
                problems.append(f'{path}.result: must be one of {", ".join(RESULTS)}')
            _text(test.get('detail'), path + '.detail', problems, high=500)
            _same_head(test, path, head, problems)
    for i, item in enumerate(_items(doc.get('evidence'), 'evidence', problems, 1)):
        path = f'evidence[{i}]'
        if _fields(item, EVID, path, problems):
            _text(item.get('kind'), path + '.kind', problems, high=50)
            _text(item.get('ref'), path + '.ref', problems, high=300)
            _same_head(item, path, head, problems)

    prov = doc.get('provenance')
    if _fields(prov, PROV, 'provenance', problems):
        _text(prov.get('author'), 'provenance.author', problems, high=100)
        _text(prov.get('runtime'), 'provenance.runtime', problems, high=100)
        if prov.get('basis') != 'self-reported':
            problems.append('provenance.basis: must be "self-reported"')
        stamp = prov.get('created_at')
        try:
            if not isinstance(stamp, str) or datetime.fromisoformat(stamp).utcoffset() is None:
                raise ValueError
        except ValueError:
            problems.append('provenance.created_at: must be ISO-8601 with timezone')

    for i, item in enumerate(_items(doc.get('unknowns'), 'unknowns', problems, 0)):
        _text(item, f'unknowns[{i}]', problems, high=300)

    if current_head is not None:
        _sha(current_head, 'current_head', problems)
        if isinstance(head, str) and head != current_head:
            problems.append('head: stale; does not match the independently resolved current head')
    if role is not None and doc.get('receiving_role') != role:
        problems.append('receiving_role: handoff is not addressed to this role')
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description='Validate a handoff record (stdin or FILE). '
                                 'Validity is not authorization.')
    ap.add_argument('file', nargs='?', help='JSON file; default stdin')
    ap.add_argument('--current-head', help='full SHA freshly resolved from the host, not from the handoff')
    ap.add_argument('--role', choices=ROLES, help='role of the receiver performing this check')
    args = ap.parse_args(argv)
    try:
        if args.file:
            with open(args.file, encoding='utf-8') as fh:
                raw = fh.read(MAX_BYTES + 1)
        else:
            raw = sys.stdin.read(MAX_BYTES + 1)
        problems = problems_for(parse(raw), args.current_head, args.role)
    except (ValueError, OSError) as error:
        problems = [f'cannot read handoff: {type(error).__name__}']
    # authorizes is constant: a handoff can never grant approval or merge eligibility.
    print(json.dumps({'valid': not problems, 'authorizes': False, 'problems': problems}))
    return int(bool(problems))


if __name__ == '__main__':
    sys.exit(main())
