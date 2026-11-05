"""Real local validation/CLI checks; no live T3 or GitHub state is mocked as proof."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from agent_workflow_pilot.graph import GraphError, load_graph, readiness, render_markdown, validate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'docs/orchestration/graph.json'


def plan():
    return load_graph(FIXTURE)


def test_fixture_readiness_and_checked_view():
    graph = plan()
    states = readiness(graph)
    assert states['builder-a']['ready'] and states['builder-b']['ready']
    assert states['review']['blockers'] == [
        'dependency builder-a: planned', 'dependency builder-b: planned']
    assert not states['delivery']['ready']
    assert render_markdown(graph).encode() == FIXTURE.with_suffix('.md').read_bytes()


def test_completion_and_stale_propagation():
    graph = plan()
    for node in graph['nodes'][:2]:
        node['status'] = 'complete'
    assert readiness(graph)['review']['ready']
    graph['nodes'][0]['status'] = 'stale'
    assert 'dependency builder-a: stale' in readiness(graph)['delivery']['blockers']
    graph['nodes'][2]['status'] = 'complete'
    with pytest.raises(GraphError, match='complete requires'):
        validate(graph)


@pytest.mark.parametrize('value', [None, [], {}, {'version': 1},
    {'version': True, 'kind': 'planned', 'nodes': []},
    {'version': 1, 'kind': 'live', 'nodes': []}])
def test_malformed_root(value):
    with pytest.raises(GraphError):
        validate(value)


@pytest.mark.parametrize('field,value', [
    ('id', []), ('id', 'Bad ID'), ('title', ''), ('title', 'a\nb'),
    ('status', {}), ('status', 'running'), ('depends_on', 'review'),
    ('depends_on', [None]), ('owns', {}), ('owns', [1]),
    ('depends_on', ['review', 'review']), ('owns', ['a', 'a'])])
def test_malformed_node(field, value):
    graph = plan()
    graph['nodes'][0][field] = value
    with pytest.raises(GraphError):
        validate(graph)


@pytest.mark.parametrize('change,match', [
    ('duplicate', 'duplicate node'), ('missing', 'missing dependency'),
    ('self', 'self dependency'), ('cycle', 'cyclic dependencies'),
    ('superseded', 'impossible dependency'), ('complete', 'complete requires'),
    ('extra', 'expected exactly')])
def test_invalid_dependencies(change, match):
    graph = plan()
    a, b, review, delivery = graph['nodes']
    if change == 'duplicate':
        graph['nodes'].append(copy.deepcopy(a))
    elif change == 'missing':
        a['depends_on'] = ['absent']
    elif change == 'self':
        a['depends_on'] = [a['id']]
    elif change == 'cycle':
        a['depends_on'] = [delivery['id']]
    elif change == 'superseded':
        a['status'] = 'superseded'
    elif change == 'complete':
        delivery['status'] = 'complete'
    else:
        a['ready'] = True
    with pytest.raises(GraphError, match=match):
        validate(graph)


@pytest.mark.parametrize('left,right', [('src/', 'src/file.py'),
    ('src', 'src/sub/file.py'), ('SRC/A.py', 'src/a.py'),
    ('src/sub/file', 'src/'), ('a', 'a')])
def test_concurrent_overlap(left, right):
    graph = plan()
    graph['nodes'][0]['owns'] = [left]
    graph['nodes'][1]['owns'] = [right]
    with pytest.raises(GraphError, match='ownership overlap'):
        validate(graph)
    graph['nodes'][1]['depends_on'] = ['builder-a']
    assert validate(graph) is graph


@pytest.mark.parametrize('path', ['../x', '/tmp/x', 'C:/x', 'a\\b', './a',
    'a//b', 'a/../b', '*', '', 'a./b', 'NUL.txt', 'a/COM1', 'a b'])
def test_unsafe_path(path):
    graph = plan()
    graph['nodes'][0]['owns'] = [path]
    with pytest.raises(GraphError, match='path'):
        validate(graph)


def test_prefix_siblings_are_disjoint_and_order_is_irrelevant():
    graph = plan()
    graph['nodes'][0]['owns'] = ['src/a']
    graph['nodes'][1]['owns'] = ['src/ab']
    rendered = render_markdown(graph)
    graph['nodes'].reverse()
    for node in graph['nodes']:
        node['depends_on'].reverse()
        node['owns'].reverse()
    assert render_markdown(graph) == rendered


def test_unknown_fields_and_path_aliases():
    graph = plan()
    graph['unexpected'] = 1
    with pytest.raises(GraphError):
        validate(graph)
    del graph['unexpected']
    graph['nodes'][0]['owns'] = ['src', 'SRC/']
    with pytest.raises(GraphError, match='aliased'):
        validate(graph)


def test_superseded_is_not_ready():
    graph = plan()
    graph['nodes'].append(dict(id='old', title='Retired work', status='superseded',
                               depends_on=[], owns=['src/']))
    assert readiness(graph)['old'] == {'ready': False, 'blockers': ['status: superseded']}


@pytest.mark.parametrize('raw', ['{"version":1,"version":1}',
    '{"x":NaN}', '{"x":Infinity}', '{',
    '{"nodes":[{"id":"a","id":"b"}]}'])
def test_strict_json(tmp_path, raw):
    path = tmp_path / 'graph.json'
    path.write_text(raw)
    with pytest.raises(ValueError):
        load_graph(path)


def cli(*args):
    return subprocess.run([sys.executable, '-m', 'agent_workflow_pilot.graph',
                           *map(str, args)], capture_output=True)


def test_cli_write_check_and_failure(tmp_path):
    output = tmp_path / 'graph.md'
    result = cli(FIXTURE, '--output', output)
    assert result.returncode == 0, result.stderr
    assert cli(FIXTURE, '--check', output).returncode == 0
    assert cli(FIXTURE).stdout == output.read_bytes()
    output.write_bytes(b'stale')
    result = cli(FIXTURE, '--check', output)
    assert result.returncode == 1 and b'differs' in result.stderr
    assert output.read_bytes() == b'stale'
    assert cli(tmp_path / 'missing.json').returncode == 1
    invalid = tmp_path / 'invalid.json'
    invalid.write_text(json.dumps([]))
    result = cli(invalid, '--output', output)
    assert result.returncode == 1 and b'Traceback' not in result.stderr
    assert output.read_bytes() == b'stale'
    assert cli(FIXTURE, '--check', output, '--output', output).returncode == 2


def test_title_cannot_inject_markdown():
    graph = plan()
    graph['nodes'][0]['title'] = '<script>|[link](url)'
    rendered = render_markdown(graph)
    assert '<script>' not in rendered and '[link]' not in rendered
    assert '&#124;' in rendered


def test_output_cannot_overwrite_canonical_graph(tmp_path):
    graph = tmp_path / 'graph.json'
    graph.write_bytes(FIXTURE.read_bytes())
    original = graph.read_bytes()
    result = cli(graph, '--output', graph)
    assert result.returncode == 1
    assert graph.read_bytes() == original
