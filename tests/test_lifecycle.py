from copy import deepcopy
import pytest
from agent_workflow_pilot.controller import lifecycle as l, program as p, checkpoint as c
from test_program import plan, evidence, ROOT


def setup(tmp_path):
    a = plan()
    obs = dict(plan_hash=p.fingerprint(a, ROOT), tasks={'pc1': evidence()})
    binding, delivery = tmp_path/'binding.json', tmp_path/'delivery.json'
    args = (a, ROOT, binding)
    kw = dict(observations=obs, scope=['pc2'])
    l.prepare(*args, **kw, delivery=delivery, task='pc2', acceptance=['approved PC2 plan'], intent='existing-intent')
    refs = dict(task='native-task', thread='native-thread')
    l.attach(*args, **kw, refs=refs)
    e = evidence()
    e.update(state='report_ready', draft=True, merged=False, merge_commit=None, ancestor_verified=False)
    obs['tasks']['pc2'] = e
    native = dict(**refs, status='completed', children_terminal=True, ref='controller-native-record')
    return args, kw, native, delivery


def test_same_delivery_resume(tmp_path):
    args, kw, native, delivery = setup(tmp_path)
    before = c.load(delivery)
    for _ in range(2):
        result = l.reconcile(*args, **kw, native=native, head='a'*40)
        assert result['action']=='awaiting_authorization'
        assert result['slot']=='held'
        assert not result['merge_authorized']
    assert c.load(delivery)==before
    kw['observations']['tasks']['pc2']=evidence()
    assert l.reconcile(*args, **kw, native=native, head='a'*40)['slot']=='retired'


@pytest.mark.parametrize('status', ['running','failed','interrupted','unknown'])
def test_non_success_holds(tmp_path,status):
    args,kw,native,_=setup(tmp_path)
    native['status']=status
    assert l.reconcile(*args,**kw,native=native,head='a'*40)['action']=='blocked'


@pytest.mark.parametrize('change', ['head','plan','scope','identity','decision'])
def test_rejects(tmp_path,change):
    args,kw,native,_=setup(tmp_path)
    head='a'*40
    if change=='head': head='b'*40
    if change=='plan': args[0]['revision']='stale'
    if change=='scope': kw['scope']=[]
    if change=='identity': native['task']='other'
    if change=='decision': next(t for t in args[0]['tasks'] if t['id']=='pc2')['decision']=False
    with pytest.raises(ValueError): l.reconcile(*args,**kw,native=native,head=head)


def test_attach_replay_conflict_and_children(tmp_path):
    args,kw,native,delivery=setup(tmp_path)
    refs={k:native[k] for k in ('task','thread')}
    assert l.attach(*args,**kw,refs=refs)==c.load(delivery)
    with pytest.raises(ValueError): l.attach(*args,**kw,refs=dict(refs,task='conflict'))
    native['children_terminal']=False
    assert l.reconcile(*args,**kw,native=native,head='a'*40)['slot']=='held'


def test_prepare_replay_budget(tmp_path):
    args,kw,native,delivery=setup(tmp_path)
    del kw['observations']['tasks']['pc2']
    before=c.load(delivery)
    result=l.prepare(*args,**kw,delivery=delivery,task='pc2',acceptance=before['acceptance'],intent=before['intent'])
    assert not result['dispatch']
    assert c.load(delivery)==before
    with pytest.raises(ValueError): l.prepare(*args,**kw,delivery=delivery,task='pc2',acceptance=['changed'],intent=before['intent'])
    state=c.apply(before,'head','head',head='a'*40)
    state['retries']=state['retry_budget']
    state=c.apply(state,'budget','block',reason='budget exhausted')
    c.save(delivery,state)
    kw['observations']['tasks']['pc2']=evidence()
    assert l.reconcile(*args,**kw,native=native,head='a'*40)['action']=='blocked'


def test_unattached_intent_cannot_reconcile_terminal(tmp_path):
    a=plan()
    obs=dict(plan_hash=p.fingerprint(a,ROOT),tasks={'pc1':evidence()})
    binding,delivery=tmp_path/'binding.json',tmp_path/'delivery.json'
    l.prepare(a,ROOT,binding,delivery,obs,['pc2'],'pc2',['approved PC2'],'intent')
    obs['tasks']['pc2']=evidence()
    native=dict(task=None,thread=None,status='completed',children_terminal=True,ref='record')
    with pytest.raises(ValueError,match='native identity'):
        l.reconcile(a,ROOT,binding,obs,['pc2'],native,'a'*40)
    assert c.load(delivery)['lifecycle']=='dispatching'


def test_reevaluation_selects_best_eligible_in_scope(tmp_path):
    a=plan()
    template=next(t for t in a['tasks'] if t['id']=='pc2')
    for ident,priority in [('outside',-2),('inside',-1)]:
        a['tasks'].append(dict(deepcopy(template),id=ident,title=ident,priority=priority,
                               depends_on=['pc2'],owns=[]))
    obs=dict(plan_hash=p.fingerprint(a,ROOT),tasks={'pc1':evidence()})
    binding,delivery=tmp_path/'binding.json',tmp_path/'delivery.json'
    l.prepare(a,ROOT,binding,delivery,obs,['pc2','inside'],'pc2',['approved'],'intent')
    refs=dict(task='task',thread='thread')
    l.attach(a,ROOT,binding,obs,['pc2','inside'],refs)
    obs['tasks']['pc2']=evidence()
    result=l.reconcile(a,ROOT,binding,obs,['pc2','inside'],dict(**refs,status='completed',children_terminal=True,ref='record'),'a'*40)
    assert result['action']=='continue' and result['task']=='inside'
    prepared=l.prepare(a,ROOT,tmp_path/'inside-binding.json',tmp_path/'inside-delivery.json',
                       obs,['pc2','inside'],result['task'],['approved successor'],'inside-intent')
    assert not prepared['dispatch']
    assert c.load(tmp_path/'inside-delivery.json')['task_key']=='inside'
