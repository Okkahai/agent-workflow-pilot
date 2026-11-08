import json
import subprocess
import sys
import pytest
from agent_workflow_pilot.controller import continuation as x, lifecycle as l, program as p
from test_program import plan, ROOT, evidence


def artifact(char='d'):
    return dict(state='delivered', head=char*64, verified_head=char*64,
                ref='pinned:artifact', children_terminal=True, accepted=True, independent=True)


def setup(tmp_path):
    a=plan()
    obs=dict(plan_hash=p.fingerprint(a,ROOT), tasks={'pc1':evidence(),'pc2':evidence()})
    scope=['pc3-a','pc3-b']
    binding=tmp_path/'a.json'
    l.prepare(a,ROOT,binding,tmp_path/'a-delivery.json',obs,scope,'pc3-a',['inventory'],'a-intent')
    refs=dict(task='native-a',thread='thread-a')
    l.attach(a,ROOT,binding,obs,scope,refs)
    obs['tasks']['pc3-a']=artifact()
    args=dict(journal=str(tmp_path/'journal.json'),binding=str(binding),scope=scope,event='a-to-b',
              native=dict(**refs,status='completed',children_terminal=True,ref='native-record'),head='d'*64,
              successor=dict(binding=str(tmp_path/'b.json'),delivery=str(tmp_path/'b-delivery.json'),
                             task='pc3-b',acceptance=['priorities'],intent='b-intent'))
    return a,obs,args


def test_serial_replay_stop(tmp_path):
    a,obs,args=setup(tmp_path)
    result=x.advance(a,ROOT,observations=obs,**args)
    assert result['dispatch'] and result['task']=='pc3-b'
    assert not x.advance(a,ROOT,observations=obs,**args)['dispatch']
    with pytest.raises(ValueError): x.advance(a,ROOT,observations=obs,**dict(args,event='different'))
    refs=dict(task='native-b',thread='thread-b')
    l.attach(a,ROOT,result['binding'],obs,args['scope'],refs)
    obs['tasks']['pc3-b']=artifact('e')
    stop=dict(args,binding=result['binding'],event='b-stop',successor=None,head='e'*64,
              native=dict(**refs,status='completed',children_terminal=True,ref='b-record'))
    assert x.advance(a,ROOT,observations=obs,**stop)['action']=='stop'
    assert p.load(args['journal'])['active'] is None
    assert not x.advance(a,ROOT,observations=obs,**stop)['dispatch']


@pytest.mark.parametrize('change',['unaccepted','independent','stale','plan','scope','approval','native','children','code'])
def test_rejections(tmp_path,change):
    a,obs,args=setup(tmp_path)
    if change=='unaccepted': obs['tasks']['pc3-a']['accepted']=False
    if change=='independent': obs['tasks']['pc3-a']['independent']=False
    if change=='stale': args['head']='f'*64
    if change=='plan': a['revision']='changed'
    if change=='scope': args['scope']=[]
    if change=='approval': next(t for t in a['tasks'] if t['id']=='pc3-b')['approved']=False
    if change=='code': obs['tasks']['pc2'].update(state='report_ready',merged=False,ancestor_verified=False,merge_commit=None,draft=True)
    if change=='native': args['native']['status']='unknown'
    if change=='children': args['native']['children_terminal']=False
    if change in ('native','children'):
        assert not x.advance(a,ROOT,observations=obs,**args)['dispatch']
    else:
        with pytest.raises(ValueError): x.advance(a,ROOT,observations=obs,**args)
    assert not (tmp_path/'b.json').exists()


def test_crash_and_fresh_process(tmp_path,monkeypatch):
    a,obs,args=setup(tmp_path)
    original=x._save
    def fail_final(path,value):
        if 'pending' not in value: raise OSError('simulated crash')
        original(path,value)
    monkeypatch.setattr(x,'_save',fail_final)
    with pytest.raises(OSError): x.advance(a,ROOT,observations=obs,**args)
    monkeypatch.setattr(x,'_save',original)
    obsfile=tmp_path/'obs.json'; infile=tmp_path/'input.json'
    obsfile.write_text(json.dumps(obs)); infile.write_text(json.dumps(args))
    run=subprocess.run([sys.executable,'-m','agent_workflow_pilot.controller.continuation',
                        '--observations',str(obsfile),'--input',str(infile)],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    assert json.loads(run.stdout)['dispatch'] is False
    assert p.load(args['journal'])['active']==args['successor']['binding']

def test_deterministic_scope_and_budget(tmp_path):
    a,obs,args=setup(tmp_path)
    template=next(t for t in a['tasks'] if t['id']=='pc3-b')
    a['tasks'].append(dict(template,id='outside',priority=-10))
    a['tasks'].reverse()
    obs['plan_hash']=p.fingerprint(a,ROOT)
    # Rebind the fixture to this plan before any continuation exists.
    binding=p.load(args['binding']); binding['plan_hash']=obs['plan_hash']
    from pathlib import Path
    Path(args['binding']).write_text(json.dumps(binding))
    assert p.select(a,ROOT,obs,scope=args['scope'])['task']=='pc3-b'
    state=l.c.load(binding['delivery'])
    state['retries']=state['retry_budget']
    state=l.c.apply(state,'exhausted','block',reason='correction budget exhausted')
    l.c.save(binding['delivery'],state)
    assert x.advance(a,ROOT,observations=obs,**args)['slot']=='held'


def test_replay_stale_and_conflicting_intent(tmp_path):
    a,obs,args=setup(tmp_path)
    original=args['successor']['intent']
    args['successor']['intent']='a-intent'
    with pytest.raises(ValueError,match='distinct intent'):
        x.advance(a,ROOT,observations=obs,**args)
    args['successor']['intent']=original
    x.advance(a,ROOT,observations=obs,**args)
    changed=dict(args,successor=dict(args['successor'],intent='other'))
    with pytest.raises(ValueError,match='conflicting replay'):
        x.advance(a,ROOT,observations=obs,**changed)
    obs['tasks']['pc3-a']['verified_head']='f'*64
    with pytest.raises(ValueError): x.advance(a,ROOT,observations=obs,**args)

@pytest.mark.parametrize('field', ['task', 'thread'])
def test_native_identity_conflict(tmp_path, field):
    a, obs, args = setup(tmp_path)
    args['native'][field] = 'different-native-identity'
    with pytest.raises(ValueError, match='identity mismatch'):
        x.advance(a, ROOT, observations=obs, **args)
    assert not (tmp_path/'journal.json').exists()


def test_missing_decision(tmp_path):
    a, obs, args = setup(tmp_path)
    next(t for t in a['tasks'] if t['id']=='pc3-b')['decision'] = False
    obs['plan_hash'] = p.fingerprint(a, ROOT)
    with pytest.raises(ValueError):
        x.advance(a, ROOT, observations=obs, **args)
    assert not (tmp_path/'b.json').exists()


def test_three_task_chain_rejects_initial_retired_intent(tmp_path):
    a,obs,args=setup(tmp_path)
    template=next(t for t in a['tasks'] if t['id']=='pc3-b')
    a['tasks'].append(dict(template,id='pc3-c',depends_on=['pc3-b']))
    args['scope'].append('pc3-c')
    obs['plan_hash']=p.fingerprint(a,ROOT)
    from pathlib import Path
    binding=p.load(args['binding']); binding['plan_hash']=obs['plan_hash']
    Path(args['binding']).write_text(json.dumps(binding))
    result=x.advance(a,ROOT,observations=obs,**args)
    refs=dict(task='native-b',thread='thread-b')
    l.attach(a,ROOT,result['binding'],obs,args['scope'],refs)
    obs['tasks']['pc3-b']=artifact('e')
    onward=dict(args,binding=result['binding'],event='b-to-c',head='e'*64,
                native=dict(**refs,status='completed',children_terminal=True,ref='b-record'),
                successor=dict(binding=str(tmp_path/'c.json'),delivery=str(tmp_path/'c-delivery.json'),
                               task='pc3-c',acceptance=['third'],intent='a-intent'))
    with pytest.raises(ValueError,match='distinct intent'):
        x.advance(a,ROOT,observations=obs,**onward)
    assert not (tmp_path/'c.json').exists()
    onward['successor']['intent']='c-intent'
    assert x.advance(a,ROOT,observations=obs,**onward)['dispatch']
