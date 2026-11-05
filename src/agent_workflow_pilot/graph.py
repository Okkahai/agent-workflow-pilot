"""Validate and render a planned graph; never collect live state or schedule work."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


class GraphError(ValueError):
    """The planning document cannot be interpreted safely."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GraphError(f'duplicate JSON key: {key!r}')
        result[key] = value
    return result


def load_graph(path):
    """Read strict JSON, rejecting duplicate keys and non-JSON constants."""
    def constant(value):
        raise GraphError(f'invalid JSON constant: {value}')
    graph = json.loads(Path(path).read_text(encoding='utf-8'),
                       object_pairs_hook=_object, parse_constant=constant)
    validate(graph)
    return graph


def _fields(value, fields, where):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise GraphError(f'{where}: expected exactly {", ".join(fields)}')


def _path(value):
    # Portable lexical paths: reject aliases rather than guess filesystem identity.
    if not isinstance(value, str) or not re.fullmatch(
            r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*/?', value):
        raise GraphError(f'invalid ownership path: {value!r}')
    parts = value.rstrip('/').split('/')
    reserved = {'con', 'prn', 'aux', 'nul'} | {
        f'{prefix}{n}' for prefix in ('com', 'lpt') for n in range(1, 10)}
    if any(p in {'.', '..'} or p.endswith('.') or
           p.split('.')[0].lower() in reserved for p in parts):
        raise GraphError(f'unsafe ownership path: {value!r}')
    return tuple(p.lower() for p in parts)


def validate(graph):
    """Raise GraphError for malformed or unsafe plans; return the original object."""
    _fields(graph, ('version', 'kind', 'nodes'), 'graph')
    if type(graph['version']) is not int or graph['version'] != 1:
        raise GraphError('version must be integer 1')
    if graph['kind'] != 'planned':
        raise GraphError('kind must be planned')
    nodes = graph['nodes']
    if not isinstance(nodes, list) or not nodes:
        raise GraphError('nodes must be a nonempty array')
    by_id = {}
    paths = {}
    for node in nodes:
        _fields(node, ('id', 'title', 'status', 'depends_on', 'owns'), 'node')
        ident = node['id']
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', ident):
            raise GraphError('id must be a lowercase slug')
        if ident in by_id:
            raise GraphError(f'duplicate node: {ident}')
        by_id[ident] = node
        if (not isinstance(node['title'], str) or not node['title'].strip()
                or any(ord(c) < 32 or ord(c) == 127 for c in node['title'])):
            raise GraphError(f'{ident}: title must be nonempty single-line text')
        if node['status'] not in ('planned', 'complete', 'stale', 'superseded'):
            raise GraphError(f'{ident}: invalid status')
        for field in ('depends_on', 'owns'):
            values = node[field]
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                raise GraphError(f'{ident}: {field} must be an array of strings')
            if len(set(values)) != len(values):
                raise GraphError(f'{ident}: duplicate {field}')
        paths[ident] = [_path(p) for p in node['owns']]
        if len(set(paths[ident])) != len(paths[ident]):
            raise GraphError(f'{ident}: aliased ownership paths')
    for ident, node in by_id.items():
        for dep in node['depends_on']:
            if dep not in by_id:
                raise GraphError(f'{ident}: missing dependency {dep!r}')
            if dep == ident:
                raise GraphError(f'{ident}: self dependency')
    # Iterative topological traversal avoids recursion limits on long valid chains.
    ancestors = {}
    remaining = set(by_id)
    while remaining:
        ready = sorted(i for i in remaining
                       if all(d in ancestors for d in by_id[i]['depends_on']))
        if not ready:
            raise GraphError('cyclic dependencies: ' + ', '.join(sorted(remaining)))
        for ident in ready:
            deps = by_id[ident]['depends_on']
            ancestors[ident] = set(deps).union(*(ancestors[d] for d in deps))
            remaining.remove(ident)
    for ident, node in by_id.items():
        for dep in sorted(ancestors[ident]):
            status = by_id[dep]['status']
            if node['status'] != 'superseded' and status == 'superseded':
                raise GraphError(f'{ident}: impossible dependency on superseded {dep}')
            if node['status'] == 'complete' and status != 'complete':
                raise GraphError(f'{ident}: complete requires complete ancestor {dep}')
    active = sorted(i for i in by_id if by_id[i]['status'] != 'superseded')
    for index, left in enumerate(active):
        for right in active[index + 1:]:
            if left in ancestors[right] or right in ancestors[left]:
                continue
            for a in paths[left]:
                for b in paths[right]:
                    if a[:len(b)] == b or b[:len(a)] == a:
                        raise GraphError(f'concurrent ownership overlap: {left}, {right}')
    return graph


def readiness(graph):
    """Return deterministic planning readiness and blockers, never execution authority."""
    validate(graph)
    by_id = {n['id']: n for n in graph['nodes']}
    result = {}
    for ident, node in sorted(by_id.items()):
        reasons = []
        if node['status'] != 'planned':
            reasons.append('status: ' + node['status'])
        pending = set(node['depends_on'])
        seen = set()
        while pending:
            dep = pending.pop()
            if dep in seen:
                continue
            seen.add(dep)
            pending.update(by_id[dep]['depends_on'])
        reasons.extend(f'dependency {d}: {by_id[d]["status"]}' for d in sorted(seen)
                       if by_id[d]['status'] != 'complete')
        result[ident] = {'ready': not reasons, 'blockers': reasons}
    return result


def _cell(text):
    # Escape HTML and Markdown syntax so titles cannot inject rendered content.
    return ''.join(c if c.isalnum() or c == ' ' else f'&#{ord(c)};' for c in text)


def render_markdown(graph):
    """Render a stable view independent of JSON key/node/list ordering."""
    states = readiness(graph)
    lines = ['# Planned orchestration graph', '',
             'Example plan only; not live T3 state, scheduling, or merge authorization.', '',
             '| Node | Title | Status | Dependencies | Exclusive ownership | Readiness / blockers |',
             '| --- | --- | --- | --- | --- | --- |']
    for node in sorted(graph['nodes'], key=lambda n: n['id']):
        state = states[node['id']]
        cells = [node['id'], node['title'], node['status'],
                 ', '.join(sorted(node['depends_on'])) or '(none)',
                 ', '.join(sorted(node['owns'])) or '(none)',
                 'ready' if state['ready'] else '; '.join(state['blockers'])]
        lines.append('| ' + ' | '.join(_cell(c) for c in cells) + ' |')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--output', type=Path, help='write derived Markdown (stdout by default)')
    parser.add_argument('--check', type=Path, help='check exact derived Markdown bytes; never write')
    args = parser.parse_args(argv)
    if args.output and args.check:
        parser.error('--output and --check are mutually exclusive')
    try:
        rendered = render_markdown(load_graph(args.graph))
        if args.check:
            if args.check.read_bytes() != rendered.encode('utf-8'):
                raise GraphError(f'derived Markdown differs: {args.check}')
        elif args.output:
            if args.output.resolve() == args.graph.resolve() or (
                args.output.exists() and os.path.samefile(args.output, args.graph)
            ):
                raise GraphError('output must differ from canonical graph')
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=args.output.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(rendered.encode('utf-8'))
                if args.output.exists():
                    os.chmod(temporary, stat.S_IMODE(args.output.stat().st_mode))
                os.replace(temporary, args.output)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        else:
            sys.stdout.buffer.write(rendered.encode('utf-8'))
    except (ValueError, OSError, RecursionError) as error:
        print(f'graph: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
