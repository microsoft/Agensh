"""OPS-only R16 tail: resume DEAD original budget-clock publishers, same owner.

No model/task/reconnect, no projection construction, no resets or gate/fault
clear. Existing published control metadata is the only file content read here.
"""
from pathlib import Path
import os,stat,threading
from native_budget_park import NativeBudgetParkProjection,SCHEMA,BINDING
from common import need,digest,strict,regular_fd,stamp,hash_file

def _public(path,limit=4096):
    path=Path(path)
    with regular_fd(path)as fd:
        before=os.fstat(fd)
        need(before.st_uid==os.geteuid()and before.st_nlink==1 and stat.S_IMODE(before.st_mode)==0o444,
             'R16_CLOCK_OWNED_READONLY_METADATA')
        raw=os.read(fd,limit+1);need(len(raw)<=limit,'R16_CLOCK_METADATA_BOUND')
        need(stamp(before)==stamp(os.fstat(fd))==stamp(path.lstat()),'R16_CLOCK_METADATA_CHANGED')
    return strict(raw)

def resume_projection(projection,*,expected_bindings,expected_directory):
    """Resume an already-started original producer; atomic/idempotent per object.

    expected_bindings are ORIGINAL CLOCK_READY pins checked by the driver-level
    entry, not worker assertions. Closed/stopped/unstarted/faulted producers are
    never reopened. Old thread remains retained on this same projection.
    """
    p=projection;need(type(p)is NativeBudgetParkProjection,'R16_CLOCK_ORIGINAL_PROJECTION_TYPE')
    with p.lock:
        p._current()
        need(not p.stop_event.is_set()and not p.closed,'R16_CLOCK_STOPPED_NOT_RESUMABLE')
        need(p.directory==Path(expected_directory),'R16_CLOCK_ORIGINAL_DIRECTORY_BINDING')
        need(type(expected_bindings)is dict and set(expected_bindings)==set(p.roles)==set(p.bindings),
             'R16_CLOCK_EXACT_ROLE_BINDINGS')
        for role in p.roles:
            need(digest(p.bindings[role])==expected_bindings[role],'R16_CLOCK_ORIGINAL_BINDING_PIN')
        old=p.thread;need(type(old)is threading.Thread and old.ident is not None,'R16_CLOCK_NOT_AN_ORIGINAL_STARTED_PUBLISHER')
        if old.is_alive():
            return {'trajectory':p.t,'status':'ALREADY_LIVE','roles':len(p.roles),
                    'sequence':p.sequence,'new_publisher':False}
        # Validate all OLD public files BEFORE replacing any; sequence is not
        # reset, so existing native readers can observe a strictly newer sample.
        sequence=p.sequence;need(type(sequence)is int and sequence>0,'R16_CLOCK_ORIGINAL_SEQUENCE')
        for role in p.roles:
            value=_public(p.directory/(role+'.json'))
            need(type(value)is dict and value.get('schema')==SCHEMA
                 and value.get('binding_sha256')==expected_bindings[role],
                 'R16_CLOCK_PUBLISHED_BINDING_MISMATCH')
            n=value.get('sequence');need(type(n)is int and 0<n<=sequence,'R16_CLOCK_SEQUENCE_WOULD_ROLL_BACK')
        p.sample()  # Original code: same gate counters, current generation,0444.
        need(p.sequence>sequence,'R16_CLOCK_FRESH_MONOTONIC_SAMPLE_REQUIRED')
        retained=getattr(p,'_r16_retired_publisher_threads',None)
        if retained is None:retained=[];p._r16_retired_publisher_threads=retained
        retained.append(old)
        # Original start() is used verbatim; only its first-start pointer guard
        # is rearmed after proving the old thread dead. No Event/binding reset.
        p.thread=None
        try:p.start()
        except BaseException:
            if p.thread is None:p.thread=old
            p.ledger.latch_fault(p.t,'R16_CLOCK_RESUME_FAILED_RETAINED')
            raise
        need(p.thread is not old and p.thread.is_alive(),'R16_CLOCK_ORIGINAL_LOOP_NOT_RUNNING')
        with p.ledger.tx():p.ledger.event(p.t,'R16_ORIGINAL_BUDGET_CLOCK_PUBLISHER_RESUMED',
            {'prior_sequence':sequence,'first_resumed_sequence':p.sequence,'roles':len(p.roles),
             'binding_roster_sha256':digest(expected_bindings),'original_projection_retained':True,
             'original_owner_and_directory_retained':True,'old_thread_retained':True,
             'new_projection_or_task_or_model':False,
             'resume_implementation_sha256':hash_file(Path(__file__))['sha256']})
        return {'trajectory':p.t,'status':'RESUMED_ORIGINAL_PROJECTION','roles':len(p.roles),
                'previous_sequence':sequence,'sequence':p.sequence,'new_publisher':True}

def resume_driver_publishers(driver):
    """Same retained ScientificSixDriver only. Leave sixth startup untouched."""
    from run_native_scientific6 import ScientificSixDriver
    need(type(driver)is ScientificSixDriver and driver.shared_started
         and not driver.failed and not driver.finished,'R16_CLOCK_LIVE_ORIGINAL_DRIVER')
    ledger=driver.ledger;manifest_sha=digest(driver.manifest);rows=[]
    # Preflight pins for the entire applicable set before starting any producer.
    plans=[]
    for t,record in driver.records.items():
        launch=record.get('launch');controller=getattr(launch,'controller',None)
        if controller is None or record.get('phase')!='ORIGINAL_TASK_RELEASED':
            rows.append({'trajectory':t,'status':'NO_PROJECTION_YET_NATIVE_STARTUP_UNTOUCHED','new_publisher':False});continue
        p=controller.projection
        need(type(p)is NativeBudgetParkProjection and p is launch.controller.projection
             and p.gate is launch.gate and p.ledger is ledger and p.t==t,
             'R16_CLOCK_ORIGINAL_DRIVER_GATE_LEDGER_BINDING')
        need(not ledger.admission_fault(t),'R16_CLOCK_NEW_FAULT_MUST_NOT_CLEAR')
        need(set(p.roles)==set(record['row']['roles']),'R16_CLOCK_ORIGINAL_ROLE_ROSTER')
        pins={}
        for role in p.roles:
            binding=p.bindings[role]
            need(binding=={'schema':BINDING,'trajectory':t,'role':role,
                'manifest_sha256':manifest_sha,'owner':p.owner},'R16_CLOCK_ORIGINAL_MANIFEST_OWNER_BINDING')
            startup=launch.startup_bindings[role]
            ready=_public(Path(startup['directory'])/'CLOCK_READY.json')
            need(ready.get('schema')=='agensh-original-router-clock-release-v1'
                 and ready.get('binding_sha256')==startup['binding_sha256']
                 and ready.get('budget_pause_binding_sha256')==digest(binding)
                 and ready.get('budget_pause_file')==startup['clock_container_file']
                 and ready.get('budget_pause_owner_uid')==startup['owner_uid'],
                 'R16_CLOCK_ORIGINAL_ROUTER_RELEASE_PIN')
            pins[role]=digest(binding)
        plans.append((p,pins,controller.root/'budget-clock'))
    for p,pins,directory in plans:
        rows.append(resume_projection(p,expected_bindings=pins,expected_directory=directory))
    return {'schema':'r16-same-owner-original-budget-publishers-resume-v1',
            'rows':rows,'resumed':sum(r['new_publisher']for r in rows),
            'same_owner':True,'new_projection_or_ledger_or_task':False,'model_calls':0}
