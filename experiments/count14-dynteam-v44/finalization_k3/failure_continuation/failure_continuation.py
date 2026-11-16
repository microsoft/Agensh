"""Compile-only cold continuation on ONE original FINAL dispatcher.

No install, constructor, new dispatcher, carrier DDL, exemption or model exists
here. Original proof/allocation/PARTIAL functions remain intact except the one
post-disposition exhausted exception becomes an explicit policy control result.
"""
from types import SimpleNamespace
import ast
import copy
from common import need,digest
from formal_ast import reversible,globals_clone
from native_final_dispatch import NativeFinalDispatcher
import native_replicate_attempts as original_attempts
import final_attempts


def compile_dispose(after_partial):
    """Private clone. Callback is invoked AFTER original durable disposition.

    This is a compilation primitive, NOT a production callback acceptance port.
    Only compile_new_dispatcher_poll supplies the exact typed host controller.
    """
    class End(ast.NodeTransformer):
        def __init__(self,edits):self.edits=edits
        def visit_Expr(self,node):
            c=node.value
            if (isinstance(c,ast.Call) and isinstance(c.func,ast.Name) and c.func.id=='need'
                and len(c.args)==2 and isinstance(c.args[1],ast.Constant)
                and c.args[1].value=='FINAL_REPLICATE_TWO_REPLACEMENTS_EXHAUSTED'):
                return self.edits.replace(node,ast.parse('_after_partial(dispatcher,record,new)').body[0],
                    'only_already_persisted_exhaustion_control')
            return self.generic_visit(node)
    return reversible(original_attempts.dispose,End,
        expected={'only_already_persisted_exhaustion_control':1},bindings={'_after_partial':after_partial})


def partial_aware_selection(dispatcher,point,*,effective_rows=final_attempts.effective_rows):
    # Absence of a valid third K is not an n3 audit failure and not a score.
    # Independent actual-n producer still must supply legitimate terminal proof.
    q=dispatcher.queue
    if effective_rows is final_attempts.effective_rows:
        with q.mutex:effective=effective_rows(q)
    else:
        # Typed allowance reader verifies its PUBLIC controls before taking its
        # own q mutex. Never perform that file I/O under this scientific lock.
        effective=effective_rows(q)
    point_ids=set(point['jobs'])
    if any(j['id'] in point_ids and j['state']=='PARTIAL' for j in effective):
        return None
    return original_attempts.selected(dispatcher,point)


class FailureContinuationControl:
    def __init__(self,dispatcher,control):
        from allowance_control import FormalAllowanceControl
        need(type(dispatcher)is NativeFinalDispatcher and type(control)is FormalAllowanceControl
            and dispatcher.ledger is control.core.ledger and dispatcher.queue is control.core.queue
            and not dispatcher.children and not dispatcher.points and not dispatcher.faulted,
            'FAILURE_CONTINUATION_ONLY_NEW_EMPTY_ORIGINAL_DISPATCHER_SAME_TYPED_COLD_CONTROL')
        control.fresh()
        self.dispatcher,self.control=dispatcher,control
        self.observations={}

    def after_partial(self,dispatcher,record,new):
        need(dispatcher is self.dispatcher and record.get('partial')is True,
            'FAILURE_CONTINUATION_ORIGINAL_DISPOSITION_MUST_FINISH_FIRST')
        job=record['job'];q=dispatcher.queue
        # Native dispose has already used its complete original financial proof.
        # Do not infer settlement/physical release from an exception or return.
        with q.mutex:
            raw=q._job(job['id'])
            partial=q.db.execute('SELECT metadata FROM replicate_partials WHERE job_id=?',(job['id'],)).fetchone()
        need(raw['state']=='CHILD_EXITED_HOLD' and partial is not None
            and record['terminal'] is not None and record['child'] is not None
            and record['child'].returncode is not None,
            'FAILURE_CONTINUATION_RETAIN_GENUINE_WAIT_AND_APPEND_ONLY_PARTIAL')
        if new is not None:
            with q.mutex:nxt=q._job(new)
            need(nxt['point']==job['point'] and nxt['replicate']==job['replicate']
                and nxt['attempt']==job.get('attempt',1)+1 and nxt['attempt']<=3
                and nxt['state']=='QUEUED',
                'FAILURE_CONTINUATION_ORIGINAL_NEXT_ORDINAL_NOT_REQUEST_REPLAY')
            state='ORIGINAL_INDEPENDENT_NEXT_ALREADY_QUEUED'
            plan=None
        else:
            plan=self.control.plan(job['point'],job['replicate'])
            decision=plan['decision'];nxt=decision['next_attempt']
            if decision['terminal']:
                need(nxt is None and decision['action']=='TERMINAL_ALLOWANCE_EXHAUSTED',
                    'FAILURE_CONTINUATION_ONLY_ORIGINAL_POLICY_TERMINAL')
                state='POLICY_TERMINAL_READY_FOR_INDEPENDENT_ACTUAL_N_PRODUCER'
            elif type(nxt)is int and nxt>=4:
                # NOT permission to install/provision/claim carrier raw4/5.
                state='WAIT_ALLOWANCE_RAW4' if nxt==4 else 'WAIT_ALLOWANCE_REVIEWED_ABOVE4'
            else:
                need(False,'FAILURE_CONTINUATION_INCONSISTENT_PERSISTED_POLICY_HOLD')
        self.observations[job['id']]=dict(schema='count14-formal-failure-continuation-proposal-v1',
            job_id=job['id'],point_id=job['point'],replicate_id=job['replicate'],
            original_claim=job['claim'],terminal_sha256=digest(record['terminal']),
            state=state,replacement_job_id=new,policy_plan=copy.deepcopy(plan),
            fees_or_UNKNOWN_or_physical_slots_changed=False,requests_replayed=0,
            carrier_installed=False,official_score_produced=False)
        return self.observations[job['id']]


def compile_new_dispatcher_poll(dispatcher,control):
    """Return a cold body + retained context; NEVER attach/hot patch it here.

    ROOT may place this in a separately reviewed prospective scope.dispatcher
    wrapper, before first dispatch_one. No old fault latch is reset or consumed.
    """
    context=FailureContinuationControl(dispatcher,control)
    dispose=compile_dispose(context.after_partial)
    def selected(dispatch,point):
        return partial_aware_selection(dispatch,point,effective_rows=control.effective_rows)
    private=SimpleNamespace(**dict(vars(original_attempts),dispose=dispose,selected=selected))
    function=dispatcher._poll.__func__
    body=globals_clone(function,replicate_attempts=private)
    need(body.__code__ is function.__code__,
        'FAILURE_CONTINUATION_POLL_REAP_AUTHORITY_AUDIT_BODY_CODE_IDENTICAL')
    return SimpleNamespace(body=body,control=context,original_poll=function,
        original_dispose_AST_inverse=dispose._formal_inverse_AST_proof,
        production_installed=False,dispatcher_constructed=False,carrier_installed=False)
