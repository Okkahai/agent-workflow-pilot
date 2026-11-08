"""Read-only GitHub PR evidence collection via an authenticated gh CLI.

Observed checks do not establish the required checks: protection collection and
independent review are outside this milestone. Consequently eligibility blocks.
"""
import argparse
import json
import re
import subprocess
import sys

from agent_workflow_pilot.gate import blockers

REPO = re.compile(r'[A-Za-z0-9_](?:[A-Za-z0-9_.-]{0,98})/[A-Za-z0-9_](?:[A-Za-z0-9_.-]{0,99})\Z')
SHA = re.compile(r'[0-9a-f]{40}\Z')


def github_api(path):
    completed = subprocess.run(['gh', 'api', '--paginate', '--slurp', path],
                               capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError('GitHub API request failed: ' + path)
    try:
        return json.loads(completed.stdout)
    except ValueError as error:
        raise RuntimeError('GitHub API returned invalid JSON: ' + path) from error


def _pr(value, number):
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if not isinstance(value, dict):
        raise ValueError('Malformed PR response')
    head, base = value.get('head'), value.get('base')
    if (value.get('number') != number or value.get('state') not in ('open', 'closed')
            or type(value.get('draft')) is not bool or not isinstance(head, dict)
            or not isinstance(base, dict) or not isinstance(head.get('sha'), str)
            or not SHA.fullmatch(head['sha']) or not isinstance(base.get('sha'), str)
            or not SHA.fullmatch(base['sha']) or not isinstance(base.get('ref'), str)
            or not base['ref']):
        raise ValueError('Incomplete or malformed PR metadata')
    return {'number': number, 'state': value['state'], 'draft': value['draft'],
            'head_sha': head['sha'], 'base_sha': base['sha'], 'base_branch': base['ref']}


def _checks(pages, key, sha):
    if not isinstance(pages, list) or not pages:
        raise ValueError('Incomplete check response')
    items = []
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get(key), list):
            raise ValueError('Malformed check response')
        for item in page[key]:
            if not isinstance(item, dict):
                raise ValueError('Malformed check item')
            if key == 'check_runs':
                if item.get('head_sha') != sha or not isinstance(item.get('name'), str):
                    raise ValueError('Malformed or stale check run')
                status, conclusion = item.get('status'), item.get('conclusion')
                if status == 'completed':
                    state = 'success' if conclusion == 'success' else 'failure'
                elif status in ('queued', 'in_progress', 'pending', 'waiting', 'requested'):
                    state = 'pending'
                else:
                    raise ValueError('Unknown check status')
                items.append({'name': item['name'], 'state': state, 'source': 'check_run'})
            else:
                state = item.get('state')
                if state not in ('success', 'failure', 'error', 'pending') or not isinstance(item.get('context'), str):
                    raise ValueError('Malformed commit status')
                items.append({'name': item['context'], 'state': 'failure' if state == 'error' else state, 'source': 'status'})
    return items


def collect(repository, number, api=github_api):
    evidence = {'head': None, 'ci_head': None, 'ci': 'unknown', 'review_head': None,
                'independent': None, 'review_evidence': None, 'findings': None,
                'protections_verified': None, 'permissions_verified': None,
                'protections_satisfied': None, 'up_to_date': None, 'bypass': None}
    report = {'repository': repository, 'pr': None, 'provenance': {'source': 'gh api',
              'required_checks': 'unverified', 'review': 'unverified',
              'protections': 'unverified', 'permissions': 'unverified'},
              'checks': [], 'observed_ci': 'unknown', 'evidence': evidence, 'errors': []}
    try:
        if not isinstance(repository, str) or not REPO.fullmatch(repository) or type(number) is not int or number < 1:
            raise ValueError('Repository must be OWNER/REPO and PR number a positive integer')
        prefix = f'repos/{repository}'
        first = _pr(api(f'{prefix}/pulls/{number}'), number)
        report['pr'] = first
        sha = first['head_sha']
        checks = _checks(api(f'{prefix}/commits/{sha}/check-runs'), 'check_runs', sha)
        checks += _checks(api(f'{prefix}/commits/{sha}/status'), 'statuses', sha)
        last = _pr(api(f'{prefix}/pulls/{number}'), number)
        if first != last:
            raise ValueError('PR identity changed during collection; recollect evidence')
        report['checks'] = checks
        states = {item['state'] for item in checks}
        report['observed_ci'] = ('failure' if 'failure' in states else 'pending' if 'pending' in states
                                 else 'success' if states == {'success'} else 'unknown')
        evidence['head'] = sha
        evidence['ci_head'] = sha
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as error:
        report['errors'].append(str(error))
    report['blockers'] = blockers(evidence)
    report['blockers'].extend(report['errors'])
    report['eligible'] = not report['blockers']
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', help='GitHub OWNER/REPO')
    parser.add_argument('pr', help='pull request number')
    args = parser.parse_args(argv)
    try:
        number = int(args.pr)
    except ValueError:
        number = 0
    report = collect(args.repository, number)
    print(json.dumps(report, indent=2))
    return 0 if report['eligible'] else 1


if __name__ == '__main__':
    sys.exit(main())
