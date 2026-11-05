"""Provider-neutral policy over trusted, freshly collected delivery evidence.

This is not an authorization service or a GitHub evidence collector.
"""
import json
import sys


def blockers(evidence):
    """Return actionable reasons to withhold normal protected merge."""
    if not isinstance(evidence, dict):
        return ['Evidence must be an object; recollect from trusted sources.']
    reasons = []
    head = evidence.get('head')
    if not isinstance(head, str) or not head.strip():
        reasons.append('Resolve the current PR head.')
    for kind in ('ci', 'review'):
        if not head or evidence.get(kind + '_head') != head:
            reasons.append(f'Recollect {kind} evidence for the current head.')
    if evidence.get('ci') != 'success':
        reasons.append('Wait for every applicable CI check to pass.')
    for field in ('independent', 'protections_verified', 'permissions_verified',
                  'protections_satisfied', 'up_to_date'):
        if evidence.get(field) is not True:
            reasons.append(f'Verify {field}; unknown or false blocks delivery.')
    if not isinstance(evidence.get('review_evidence'), str) or not evidence['review_evidence'].strip():
        reasons.append('Attach independently produced review evidence.')
    if evidence.get('findings') != []:
        reasons.append('Correct actionable findings and obtain fresh review.')
    if evidence.get('bypass') is not False:
        reasons.append('Disable bypass; use normal protected merge only.')
    return reasons


def main():
    try:
        reasons = blockers(json.load(sys.stdin))
    except (ValueError, OSError) as error:
        reasons = [f'Cannot read evidence: {error}']
    print(json.dumps({'eligible': not reasons, 'blockers': reasons}))
    return int(bool(reasons))


if __name__ == '__main__':
    sys.exit(main())
