from copy import deepcopy
from pathlib import Path
import json
import pytest
from agent_workflow_pilot.controller import program as p, checkpoint as c

ROOT=Path('docs/program')

def plan(): return p.load(ROOT/'roadmap.json')

def test_real_selection_and_order():
    a=plan(); result=p.select(a,ROOT)
    assert result['task']=='pc1'
    a['tasks'].reverse()
    assert p.select(a,ROOT)==result
    assert result['tasks']['pr14']['state']=='blocked'
    assert not result['merge_authorized']

@pytest.mark.parametrize('change', ['duplicate','missing','self','cycle','ownership','spec','authorization'])
def test_invalid_plan(change):
    a=plan(); t=a['tasks'][0]
    if change=='duplicate': a['tasks'].append(deepcopy(t))
    if change=='missing': t['depends_on']=['absent']
    if change=='self': t['depends_on']=[t['id']]
    if change=='cycle': t['depends_on']=['m1-gap']
    if change=='ownership': t['owns']=['docs/program/']
    if change=='spec': t['spec']='tasks/missing.md'
    if change=='authorization': t['approved']='yes'
    with pytest.raises(ValueError): p.select(a,ROOT)

def evidence():
    return dict(state='delivered',head='a'*40,verified_head='a'*40,ref='controller:verified',children_terminal=True,draft=False,merged=True,merge_commit='b'*40,target_tip='c'*40,ancestor_verified=True)

def test_ancestry_not_tip_equality():
    assert p.completion(plan()['tasks'][0],evidence())

@pytest.mark.parametrize('field,value',[('draft',True),('merged',False),('ancestor_verified',False),('children_terminal',False),('verified_head','d'*40),('head','short'),('state','complete')])
def test_completion_rejects(field,value):
    e=evidence(); e[field]=value
    with pytest.raises(ValueError): p.completion(plan()['tasks'][0],e)

def test_artifact():
    t=dict(plan()['tasks'][0],kind='artifact')
    e={k:v for k,v in evidence().items() if k in {'state','head','verified_head','ref','children_terminal'}}
    e.update(accepted=True,independent=True)
    assert p.completion(t,e)
    e['independent']=False
    with pytest.raises(ValueError): p.completion(t,e)

def test_resume_immutable_and_stale(tmp_path):
    a=plan(); delivery=tmp_path/'delivery.json'; binding=tmp_path/'program.json'
    s=c.new('pc1',['approved M1 acceptance'])
    s=c.apply(s,'intent','dispatch',client_request_id='original-intent',completed_dependencies=[])
    c.save(delivery,s)
    r=p.record(binding,a,ROOT,'pc1',delivery)
    assert r['tasks']['pc1']['state']=='blocked'
    assert p.record(binding,a,ROOT,'pc1',delivery)==r
    s=c.apply(s,'native','started',refs={'task':'existing-task','thread':'existing-thread'})
    c.save(delivery,s)
    assert p.select(a,ROOT,active=p.load(binding))['tasks']['pc1']['state']=='running'
    assert c.load(delivery)['intent']=='original-intent'
    with pytest.raises(ValueError): p.record(binding,a,ROOT,'pr14',delivery)
    a['revision']='changed'
    with pytest.raises(ValueError): p.select(a,ROOT,active=p.load(binding))

def test_stale_observations():
    with pytest.raises(ValueError): p.select(plan(),ROOT,{'plan_hash':'old','tasks':{}})

def test_dependencies_and_authorization():
    a=plan(); gap=next(t for t in a['tasks'] if t['id']=='m1-gap')
    gap.update(approved=True,decision=True,priority=-1)
    assert p.select(a,ROOT)['task']=='pc1'
    obs=dict(plan_hash=p.fingerprint(a,ROOT),tasks={'m1-core':evidence()})
    assert p.select(a,ROOT,obs)['task']=='m1-gap'
    gap['decision']=False
    assert p.select(a,ROOT)['task']=='pc1'

def test_cli(capsys):
    assert p.main(['next'])==0
    assert 'pc1' in capsys.readouterr().out
    assert p.main(['resume'])==1


@pytest.mark.parametrize('raw', [{}, [], False, '', 0])
def test_malformed_empty_observations_rejected(raw, tmp_path):
    with pytest.raises(ValueError):
        p.select(plan(), ROOT, raw)
    path = tmp_path / 'observations.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    assert p.main(['next', '--observations', str(path)]) == 1


def test_truthful_unmerged_observation_does_not_block_independent_task():
    a = plan()
    e = evidence()
    e.update(state='report_ready', draft=True, merged=False,
             merge_commit=None, ancestor_verified=False)
    obs = dict(plan_hash=p.fingerprint(a, ROOT), tasks={'pr14': e})
    result = p.select(a, ROOT, obs)
    assert result['task'] == 'pc1'
    assert result['tasks']['pr14']['state'] == 'report_ready'
    assert not p.completion(next(t for t in a['tasks'] if t['id']=='pr14'), e)
    e['state'] = 'delivered'
    with pytest.raises(ValueError):
        p.select(a, ROOT, obs)


# ---- A2: arbitrary milestone identifiers --------------------------------------------------
# Captured by running b013c82 (pre-A2) on its roadmap + specs; serialization must not move.
BASELINE_ROADMAP_FINGERPRINT = '3f15c9e5eef65e0fb95064f2be4c5576da2f6ef0856cb6d02eb1c9c1a32da069'
BASELINE_REVISION = 'a1-approved-2026-11-09'


def with_milestone(value, index=0):
    a = plan(); a['tasks'][index]['milestone'] = value
    return a


def test_baseline_fingerprint_unchanged_for_unchanged_inputs():
    a = plan()
    a['tasks'] = [t for t in a['tasks'] if t['id'] != 'a2']
    a['revision'] = BASELINE_REVISION
    assert p.fingerprint(a, ROOT) == BASELINE_ROADMAP_FINGERPRINT


@pytest.mark.parametrize('name', ['M1', 'M5', 'alpha', 'phase-2', 'phase_2', 'Q3-launch', 'a', 'M1x', 'X' * 64,
                                  'a-b_c-d'])
def test_valid_milestone_names(name):
    a = with_milestone(name)
    assert p.validate(a, ROOT) is a


def test_mixed_and_shared_milestones_select_unchanged():
    a = plan()
    for t, name in zip(a['tasks'], ['alpha', 'M2', 'alpha', 'beta-1', 'M1'] * 6):
        t['milestone'] = name
    assert p.select(a, ROOT)['task'] == 'pc1'
    assert not p.select(a, ROOT)['merge_authorized']


@pytest.mark.parametrize('name', ['', ' ', 'M1 ', ' M1', 'M 1', 'M1\n', '\tM1', 'M1\x00', 'M\x1b1', '1M', '-M1', '_M1',
                                  'M1-', 'M1_', 'M1.2', 'M1/x', '../M1', 'a\b', 'M1:x', 'M$1', 'MÉ', 'Μ1', 'M１',
                                  'M1‮', 'X' * 65, 'X' * 1000, None, 1, 1.0, True, [], ['M1'], {}, b'M1'])
def test_invalid_milestone_names_rejected_by_validate(name):
    with pytest.raises(ValueError):
        p.validate(with_milestone(name), ROOT)
    with pytest.raises(ValueError):
        p.select(with_milestone(name), ROOT)


def test_case_and_bytes_preserved():
    assert p.fingerprint(with_milestone('m1'), ROOT) != p.fingerprint(plan(), ROOT)
    assert p.fingerprint(with_milestone('M1'), ROOT) == p.fingerprint(plan(), ROOT)


def test_changed_milestone_invalidates_old_observations_and_bindings(tmp_path):
    a = plan()
    obs = dict(plan_hash=p.fingerprint(a, ROOT), tasks={})
    assert p.select(a, ROOT, obs)['task'] == 'pc1'
    renamed = with_milestone('alpha')
    with pytest.raises(ValueError):
        p.select(renamed, ROOT, obs)
    delivery = tmp_path / 'delivery.json'
    binding = tmp_path / 'binding.json'
    st = c.apply(c.new('pc1', ['acc']), 'intent', 'dispatch', client_request_id='i1', completed_dependencies=[])
    c.save(delivery, st)
    p.record(binding, a, ROOT, 'pc1', delivery)
    assert p.select(a, ROOT, active=p.load(binding))['tasks']['pc1']['state'] == 'blocked'  # dispatching
    with pytest.raises(ValueError):
        p.select(renamed, ROOT, active=p.load(binding))


def test_milestone_never_authorizes():
    a = plan()
    for t in a['tasks']:
        t['milestone'] = 'approved-merge'
    res = p.select(a, ROOT)
    assert res['task'] == 'pc1' and not res['merge_authorized']
    assert res['tasks']['pr14']['state'] == 'blocked'
    assert res['tasks']['a2']['state'] == 'blocked'  # depends on a1, not freshly observed delivered
