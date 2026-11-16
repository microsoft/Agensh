"""One domain everywhere; original policy/disposition precedes raw>=4 once.

No new dispatcher, request replay, allowance, automatic exemption or fee/UNKNOWN
mutation. CURRENT natural/fixed-producer/failure/header/child code is preserved.
"""
from pathlib import Path
from types import MethodType,SimpleNamespace
import ast,copy
from common import need,digest,hash_file
from formal_ast import reversible,globals_clone
from queue_control import CarrierQueueDomain,AUTH,JOBS,original_replacement_id
from approved_queue_reader import ApprovedCarrierReader
import queue_native,native_replicate_attempts


def approved_native_ports(reader=None):
    return globals_clone(queue_native.native_ports,FormalAllowanceReader=ApprovedCarrierReader)(reader)


def bind_natural_point_guard(domain):
    from formal_natural_cold import registered_control_point
    def point_guard(own,point,row):
        return registered_control_point(own.control,point,row)
    class Guard(ast.NodeTransformer):
        def __init__(self,e):self.e=e
        def visit_Compare(self,n):
            if ast.unparse(n)=="point == digest(dict(trajectory=descriptor['trajectory'], target=descriptor['target']))":
                return self.e.replace(n,ast.parse('_approved_point(self,point,descriptor)',mode='eval').body,
                    'regular_or_actual_committed_first_natural_point')
            return self.generic_visit(n)
    fn=reversible(CarrierQueueDomain._capture_locked,Guard,
        expected={'regular_or_actual_committed_first_natural_point':1},bindings={'_approved_point':point_guard})
    domain._capture_locked=MethodType(fn,domain)
    return fn


def register_proven_next(domain,record):
    """Only AFTER genuine original PARTIAL; observe an already registered slot."""
    need(type(domain)is CarrierQueueDomain and domain.installed and record.get('partial')is True,
         'APPROVED_CARRIER_ONLY_AFTER_ORIGINAL_DURABLE_DISPOSITION')
    domain.fresh();job=record['job'];q=domain.q
    with q.mutex:
        raw=q._job(job['id']);partial=q.db.execute('SELECT metadata FROM replicate_partials WHERE job_id=?',(job['id'],)).fetchone()
    need(raw['state']=='CHILD_EXITED_HOLD'and partial is not None and record['terminal']is not None and
         record['child']is not None and record['child'].returncode is not None,
         'APPROVED_CARRIER_GENUINE_WAIT_AND_ORIGINAL_PARTIAL_PROOF_NOT_BOOL')
    prior=record.get('approved_carrier_successor')
    if prior is not None:
        with q.mutex:
            row=q._job(prior);domain._registration_locked(row)
        need(row['point']==job['point']and row['replicate']==job['replicate'],
             'APPROVED_CARRIER_REPEAT_ONLY_OBSERVES_EXACT_EXISTING_SUCCESSOR')
        return prior
    plan=domain.plan(job['point'],job['replicate']);decision=plan['decision'];nxt=decision['next_attempt']
    if decision['terminal']:return None
    if type(nxt)is not int or nxt<4:return None # original1..3 path owns that branch
    jid=domain.register_next(plan) # exactly original policy + exact current proof
    record['approved_carrier_successor']=jid
    return jid


def bind_after_disposition(dispatcher,domain):
    context=dispatcher.formal_failure_continuation
    need(context.dispatcher is dispatcher and context.control is domain.control and
         not dispatcher.children and not dispatcher.points,'APPROVED_CARRIER_CURRENT_SAME_EMPTY_FAILURE_CONTEXT')
    current=dispatcher._poll.__func__;old=current.__globals__['replicate_attempts']
    dispose=old.dispose
    previous=dispose.__globals__['_after_partial']
    def after(own,record,new):
        result=previous(own,record,new) # original genuine proof + durable PARTIAL first
        if new is None:
            jid=register_proven_next(domain,record)
            if jid is not None:
                # Public observation only; original replacement_job_id and
                # historical disposition/PARTIAL are NOT overwritten.
                result=dict(result,approved_carrier_successor=jid,carrier_installed=True,
                    state='ORIGINAL_POLICY_AUTHORIZED_INDEPENDENT_CARRIER_REGISTERED')
        context.observations[record['job']['id']]=result
        return result
    actual_dispose=globals_clone(dispose,_after_partial=after)
    original_selected=globals_clone(native_replicate_attempts.selected,final_attempts=domain.attempts)
    def selected(own,point):
        effective=domain.effective_rows(own.queue)
        if any(j['id']in set(point['jobs'])and j['state']=='PARTIAL'for j in effective):return None
        return original_selected(own,point)
    private=SimpleNamespace(**dict(vars(old),dispose=actual_dispose,selected=selected))
    fn=globals_clone(current,replicate_attempts=private)
    need(fn.__code__ is current.__code__,'APPROVED_CARRIER_CURRENT_NATURAL_FAILURE_POLL_CODE_IDENTICAL')
    dispatcher._poll=MethodType(fn,dispatcher)
    dispatcher.formal_approved_carrier_domain=domain


def bind_control(control,domain):
    need(domain.control is control and domain.q is control.core.queue and domain.installed,
         'APPROVED_CARRIER_SAME_ORIGINAL_ALLOWANCE_CONTROL_AND_DOMAIN')
    old_authorize=control.authorize_claim
    control.all_rows=MethodType(lambda own,q:domain.all_rows(q),control)
    control.effective_rows=MethodType(lambda own,q:domain.effective_rows(q),control)
    control.plan=MethodType(lambda own,point,k:domain.plan(point,k),control)
    def authorize(own,job):
        if job.get('attempt',1)<=3:return old_authorize(job)
        with domain.q.mutex:need(domain.q._job(job['id'])==job,'APPROVED_CARRIER_CURRENT_CONFIG_SAME_ACTUAL_CLAIM')
        reader=ApprovedCarrierReader(domain.descriptor,domain.pin)
        receipt=reader.authorization(job['point'],job['replicate'],job['attempt'],
            trajectory=job['trajectory'],input_policy=job['input_policy'])
        need(receipt['claim']==job['claim'],'APPROVED_CARRIER_CONFIG_OBSERVES_EXISTING_CLAIM_NO_REPUBLISH')
        return receipt
    control.authorize_claim=MethodType(authorize,control)


def augment_scope(scope,domain):
    need(type(domain)is CarrierQueueDomain and domain.installed and not hasattr(scope,'approved_carrier_domain') and
         hasattr(scope,'formal_natural_sidecar')and hasattr(scope,'_formal_allowance_ports'),
         'APPROVED_CARRIER_AFTER_CURRENT_NATURAL_ALLOWANCE_SCOPE_ONLY')
    reader=ApprovedCarrierReader(domain.descriptor,domain.pin);ports=approved_native_ports(reader)
    current=scope.final_binding.__func__
    need('_allowance_binding_init'in current.__globals__ and '_allowance_bind_request'in current.__globals__,
         'APPROVED_CARRIER_CURRENT_QUALIFIED_ALLOWANCE_BINDING_GLOBALS')
    scope.final_binding=MethodType(globals_clone(current,_allowance_binding_init=ports.binding_init,
        _allowance_bind_request=ports.bind_request),scope)
    scope._formal_allowance_ports=ports;scope.approved_carrier_domain=domain
    old_queue=scope.bind_queue
    def queue(own,q):
        result=old_queue(q) # keep original natural enqueue/input/marker first
        need(q is domain.q,'APPROVED_CARRIER_ONE_SAME_REAL_QUEUE')
        domain._bind_private_original_ports(own.verify_input)
        return result
    scope.bind_queue=MethodType(queue,scope)
    previous=scope.dispatcher
    def dispatcher(own,*args,**kwargs):
        result=previous(*args,**kwargs) # full CURRENT failure/fixed/natural hooks
        need(result.queue is domain.q and result.ledger is domain.l and not result.children and not result.points,
             'APPROVED_CARRIER_ONLY_SAME_NEW_FINAL_DISPATCHER')
        bind_after_disposition(result,domain)
        result.environment.update(COUNT14_FORMAL_QUEUE_CONTROL_DOMAIN_PUBLIC=str(domain.descriptor),
            COUNT14_FORMAL_QUEUE_CONTROL_DOMAIN_SHA256=domain.pin,
            COUNT14_NATURAL_PARENT_CHILD=str(Path(__file__).resolve().parents[1]/'formal100m-allowance-queue-proposal-v1/queue_child.py'),
            COUNT14_NATURAL_PARENT_CHILD_SHA256='5c99227268367fb77ceb161968cfe9860733613906c8649ba773e4f759aadf66')
        result.entry=Path(__file__).with_name('approved_queue_child.py');result.entry_pin=hash_file(result.entry)
        return result
    scope.dispatcher=MethodType(dispatcher,scope)
    return scope
