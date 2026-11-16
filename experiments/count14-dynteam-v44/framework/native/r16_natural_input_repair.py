"""One fixed same-owner suffix after approved-UNKNOWN FINAL input omission.

No collector/backup/freeze/request is replayed. Existing COMPLETED/claimed FINALs,
ledger records and controller identities remain authoritative. Failed derivatives
and prior producer attempts remain immutable forensic evidence.
"""
from pathlib import Path
import copy,importlib.util,json,os,stat,threading
from common import need,digest,wire,publish,hash_file,regular_fd,strict
from bridge import process_identity
from budget import SERVICES
from r16_nofile_continuation import (verify_shared_without_admission,
    verify_finished_unsent,archive_finished_unsent,clock_pins,request_prefix,
    sanitized_exception,OLD,NEW)
BASE=Path(__file__).resolve().parent
ALLOWED=frozenset(('SCIENTIFIC6_DRIVER_ADMISSION_SEALED_AFTER_FAILURE',
 'SCIENTIFIC6_DRIVER_FAILURE_RETAINED_NO_RETRY',
 'NATIVE_SCIENTIFIC_OWNER_FAILED_RETAIN_NO_RETRY'))
REPAIR='r16-natural-approved-unknown-input-suffix-v1'
PHYSICAL_RUN_SHA='a6d8677fa63cc576d1f15add14b6cebdb0b2e6337fdd5bebf51f23fc0c0fb2b3'


def install_builder(driver):
    """Rebind the retained method's imported alias, not just sys.modules."""
    import v21_inputs,native_scientific_owner
    spec=importlib.util.spec_from_file_location('_r16_approved_unknown_v21_inputs',BASE/'v21_inputs.py')
    vi=importlib.util.module_from_spec(spec);spec.loader.exec_module(vi)
    v21_inputs.build=vi.build
    # _point was already qualified in a separate module namespace on the SAME
    # original class. Updating the old module attribute alone misses that alias.
    native_scientific_owner.NativeScientificOwner._point.__globals__['build']=vi.build
    original=Path(driver.dispatcher.environment['R16_ORIGINAL_FINAL_ENTRY'])
    need(original.name=='run_native_final_child.py'
         and hash_file(original)['sha256']==driver.dispatcher.environment['R16_ORIGINAL_FINAL_ENTRY_SHA'],
         'NATURAL_REPAIR_ORIGINAL_CHILD_PIN')
    driver.dispatcher.entry=BASE/'r16_final_child.py'
    driver.dispatcher.entry_pin=hash_file(driver.dispatcher.entry)
    return vi.build


def parked(c):
    need(c.cut is not None and c.fence.cut is c.cut and c.fence.state=='PARKED'
         and c.stage is None,'NATURAL_REPAIR_EXACT_RETAINED_PARKED_CUT')
    c.fence._coverage()
    need(all(d.frozen()and d.read('cgroup.freeze').strip()=='1'for d in c.fence.domains),
         'NATURAL_REPAIR_ORIGINAL_WHOLE_TEAM_STILL_FROZEN')
    f=c.ledger.frontier(c.t)
    need(f['generation']==c.cut.cut['generation']and f['target']==c.cut.cut['target_tokens']
         and f['reserved']==f['unresolved']==f['active_operations']==0,
         'NATURAL_REPAIR_ORIGINAL_DRAINED_CUT_FRONTIER')
    return f


def verify_committed(c,pin):
    """Only already COMMITTED snapshot + completed original collection."""
    f=parked(c)
    need(f['state']=='COMMITTED_PARKED'and c.ref is not None,'NATURAL_REPAIR_COMMITTED_ONLY')
    c.cas.verify_snapshot(c.ref,expected=f)
    need(set(c.cut.receipts)==SERVICES,'NATURAL_REPAIR_ALL_ORIGINAL_BACKUPS_SEALED')
    need(not any(p['generation']==f['generation']for p in c.points),
         'NATURAL_REPAIR_NO_EXISTING_CURRENT_POINT_OR_JOBS')
    home=c.root/('point-natural-'+str(f['target']))
    need(home.is_dir()and (home/'v21').is_dir()and not(home/'POINT_QUEUED.json').exists(),
         'NATURAL_REPAIR_RETAIN_FAILED_ORIGINAL_DERIVATIVE')
    path=home/'collection/candidate-manifest.json'
    with regular_fd(path)as fd:
        s=os.fstat(fd)
        need(s.st_uid==os.geteuid()and stat.S_IMODE(s.st_mode)==0o400 and s.st_nlink==1,
             'NATURAL_REPAIR_ORIGINAL_COLLECTION_PRIVATE_SEAL')
    need(hash_file(path)==pin,'NATURAL_REPAIR_ORIGINAL_COLLECTION_FIXED_PIN')
    derivative=c.root/('point-natural-'+str(f['target'])+'-unknown-input-repair-v1')
    need(not derivative.exists()and not derivative.is_symlink(),'NATURAL_REPAIR_NEW_DERIVATIVE_ONLY_ONCE')
    return {'collection':path,'pin':dict(pin),'destination':derivative,'generation':f['generation']}


def retained_collection(c,plan):
    """Private framework metadata only; never export candidates or histories."""
    path=plan['collection'];need(hash_file(path)==plan['pin'],'NATURAL_REPAIR_COLLECTION_CHANGED')
    with regular_fd(path)as fd:
        with os.fdopen(os.dup(fd),'rb')as inp:raw=inp.read()
    need(hash_file(path)==plan['pin'],'NATURAL_REPAIR_COLLECTION_CHANGED')
    m=strict(raw)
    need(wire(m)==raw and m['schema']=='count14-agensh-candidates-v1'
         and m['trajectory']==c.t and m['generation']==plan['generation']
         and m['snapshot_sha256']==c.ref['sha256']
         and m['unique_candidates']==len(m['candidates']),
         'NATURAL_REPAIR_ORIGINAL_COLLECTION_IDENTITY')
    return {'manifest':m,'receipt':{'schema':'count14-agensh-candidate-receipt-v1',
        'manifest_sha256':plan['pin']['sha256'],'unique_candidates':m['unique_candidates'],
        'candidate_occurrences':m['counts'].get('candidate_occurrences',0),
        'snapshot_sha256':c.ref['sha256'],'native_final_executed':False}}


def complete_retained_point(c,plan,builder):
    """Original failed build -> NEW derivative -> original enqueue exactly once."""
    c._shared();f=c.ledger.frontier(c.t)
    need(f['generation']==plan['generation']and f['state']=='COMMITTED_PARKED',
         'NATURAL_REPAIR_SNAPSHOT_FRONTIER_CHANGED')
    collection=retained_collection(c,plan);home=plan['destination'];home.mkdir(mode=0o700)
    inputs=builder(c.cas,c.ref,collection,home/'v21',expected=f,setting=c.setting)
    ids=c.queue.enqueue(home/'v21',policy_sha256=inputs['input_policy_sha256'],trajectory=c.t,setting=c.setting)
    need(len(ids)==len(set(ids))==3,'NATURAL_REPAIR_EXACT_ORIGINAL_K3_QUEUE')
    nm=copy.deepcopy(c._r16_natural_stop)
    point={'generation':f['generation'],'target_tokens':f['target'],
        'snapshot':copy.deepcopy(c.ref),'input_policy_sha256':inputs['input_policy_sha256'],
        'jobs':ids,'final_completed':False,'point_kind':'NATURAL_STOP','natural_stop':nm,
        'report_label':'自然停止点 @ 实际 token','budget_accounting':{
            'actual_budget_tokens':f['actual'],'measured_search_tokens':f['measured_actual'],
            'unknown_reservation_charge':f['unknown_reservation_charge']},
        'input_repair':{'kind':REPAIR,'original_collection':plan['pin'],
                        'original_failed_derivative_retained':True,'recapture_or_recollect':False}}
    publish(home/'POINT_QUEUED.json',wire(point),mode=0o400)
    c.points.append(point);c._event('NATIVE_SCIENTIFIC_POINT_K3_QUEUED',point)
    c.state='POINT_QUEUED'
    return point


def finish_backup(c,suffix):
    """Only a preflight-pinned unstarted producer suffix, NOT backup_ports()."""
    c._shared();c.cut.current({'DRAINING'})
    receipt=suffix(c,c.root/('backup-'+str(c.cut.cut['generation'])))
    c._shared();c.cut.current({'DRAINING'})
    need(type(receipt)is dict and set(receipt)=={'git_exports'},'NATURAL_REPAIR_BACKUP_SUFFIX_RETURN')
    need(type(receipt['git_exports'])is list and len(receipt['git_exports'])==len(c.refs)
         and {r.get('ref')for r in receipt['git_exports']}==set(c.refs),
         'NATURAL_REPAIR_ORIGINAL_GIT_EXPORTS_COMPLETE')
    need(set(c.cut.receipts)==SERVICES,'NATURAL_REPAIR_ALL_ORIGINAL_BACKUPS_REQUIRED')
    c.exports=copy.deepcopy(receipt['git_exports'])
    pins={**c.pins,'native_writer_fence':c.fence.receipt['sha256'],
          'gitea_exports':digest({'registered_refs':list(c.refs),'exports':c.exports})}
    nm=c._r16_natural_stop
    need(nm['generation']==c.cut.cut['generation'],'NATURAL_REPAIR_ORIGINAL_NATURAL_GENERATION')
    pins.update(natural_stop_policy=nm['policy_sha256'],natural_stop_point=digest(nm))
    c.ref=c.cut.capture(roles=c.roles,pins=pins,parent=c.parent)
    c.state='COMMITTED'


def failure(driver,t,exc):
    with driver.ledger.tx():driver.ledger.event(t,'R16_NATURAL_INPUT_REPAIR_FAILED',sanitized_exception(exc))
    driver._fault(t)


def tick_loop(driver,stop=None):
    # NEVER call instance.run(): OPS recorded_run republishes a prior result.
    while not driver.finished and not driver.failed:
        driver.tick()
        if stop is not None:
            if stop.wait(.25):return
        else:__import__('time').sleep(.25)


def physical_suffix_plan(c,pin):
    """Verify ALL original opaque copies; never re-run copy of live roots."""
    from native_whole_team import NativeWholeTeamBackupPorts
    p=c.backup_ports;f=parked(c);cut=c.cut
    need(type(p)is NativeWholeTeamBackupPorts and p is c.backup_callable
         and p.registration is c.fence.whole_team and p.registration.owner is c.team
         and p.graph==c.graph and p.graph_sha==c.graph_sha,
         'NATURAL_REPAIR_ORIGINAL_FULL_BACKUP_PORTS')
    need(f['state']=='DRAINING'and c.ref is None
         and set(cut.receipts)=={'gitea','gitea_database'},
         'NATURAL_REPAIR_EXACT_TWO_ORIGINAL_SEALED_COMPONENTS')
    p.registration.frozen(c.fence)
    need(cut.cut_sha in p.git.captures and cut.cut_sha in p.gitea_database.captures
         and p.git.captures[cut.cut_sha]['service_receipt']==cut.receipts['gitea']
         and p.gitea_database.captures[cut.cut_sha]['service_receipt']==cut.receipts['gitea_database']
         and cut.cut_sha not in p.collaboration.captures and cut.cut_sha not in p.bridge.captures,
         'NATURAL_REPAIR_RETAIN_ORIGINAL_PRODUCER_CAPTURES')
    dest=c.root/('backup-'+str(cut.cut['generation']))
    need(not(dest/'relay').exists()and not(dest/'relay').is_symlink()
         and not(dest/'bridge').exists()and not(dest/'bridge').is_symlink(),
         'NATURAL_REPAIR_RELAY_BRIDGE_MUST_NOT_HAVE_STARTED')
    for kind in ('NATIVE_RELAY_BACKUP_STARTED','NATIVE_BRIDGE_BACKUP_STARTED'):
        rows=c.ledger.db.execute('SELECT metadata FROM events WHERE trajectory=?AND kind=?',(c.t,kind))
        need(not any(strict(r[0]).get('cut_sha256')==cut.cut_sha for r in rows),
             'NATURAL_REPAIR_NO_PRIOR_RELAY_OR_BRIDGE_ATTEMPT')
    root=dest/'collaboration-physical/collaboration';manifest=root/'PHYSICAL_ROOTS.json'
    with regular_fd(manifest)as fd:
        s=os.fstat(fd)
        need(s.st_uid==os.geteuid()and stat.S_IMODE(s.st_mode)==0o600 and s.st_nlink==1,
             'NATURAL_REPAIR_PHYSICAL_MANIFEST_ORIGINAL_PRIVATE')
        with os.fdopen(os.dup(fd),'rb')as inp:raw=inp.read()
    need(hash_file(manifest)==pin,'NATURAL_REPAIR_PHYSICAL_MANIFEST_PIN')
    m=strict(raw);registration=p.registration
    need(wire(m)==raw and set(m)=={'schema','cut_sha256','inventory_sha256','whole_team_frozen','roots','live_sql_rpc','runtime_socket_policy','actual_copy_implementation_sha256'}
         and m['schema']=='agensh-whole-team-physical-backup-v1'
         and m['cut_sha256']==cut.cut_sha and m['inventory_sha256']==registration.inventory_sha
         and m['whole_team_frozen']is True and m['live_sql_rpc']is False
         and m['runtime_socket_policy']=='REGISTERED_NATIVE_MCP_GIT_AND_ACP_AGENT_SOCK_ONLY'
         and m['actual_copy_implementation_sha256']==PHYSICAL_RUN_SHA
         and hash_file(Path(type(p.collaboration).run.__globals__['__file__']))['sha256']==PHYSICAL_RUN_SHA,
         'NATURAL_REPAIR_ORIGINAL_PHYSICAL_MANIFEST_IDENTITY')
    expected={(service,name)for service in p.collaboration.names
              for name in registration.services[service]['roots']}
    actual=[];files={'PHYSICAL_ROOTS.json'}
    need(type(m['roots'])is list,'NATURAL_REPAIR_ORIGINAL_PHYSICAL_ROOT_LIST')
    for row in m['roots']:
        need(type(row)is dict and set(row)=={'service','name','root_binding_sha256','object'},
             'NATURAL_REPAIR_ORIGINAL_ROOT_FIELDS')
        key=(row['service'],row['name']);need(key in expected,'NATURAL_REPAIR_UNREGISTERED_PHYSICAL_ROOT')
        actual.append(key);binding=registration.services[key[0]]['roots'][key[1]]
        need(row['root_binding_sha256']==digest(binding),'NATURAL_REPAIR_PHYSICAL_ROOT_PIN')
        archive=row['object']['archive'];original=cut.cas.resolve(archive)
        target=root/(key[0]+'--'+key[1]+'.tar.gz');files.add(target.name)
        with regular_fd(target)as fd:
            s=os.fstat(fd)
            need(s.st_uid==os.geteuid()and stat.S_IMODE(s.st_mode)==0o400 and s.st_nlink==1,
                 'NATURAL_REPAIR_ORIGINAL_ARCHIVE_PRIVATE_SEAL')
        need(hash_file(target)==archive and hash_file(original)==archive,
             'NATURAL_REPAIR_ORIGINAL_PHYSICAL_ARCHIVE_BYTES')
    need(len(actual)==len(set(actual))and set(actual)==expected
         and {x.name for x in root.iterdir()}==files,
         'NATURAL_REPAIR_COMPLETE_EXACT_ORIGINAL_PHYSICAL_ROOTS')
    p.registration.frozen(c.fence)
    cut.cas.resolve(pin)  # Original producer stored this before refused seal.
    return {'pin':dict(pin),'manifest':manifest,'root':root,'count':len(expected),'cut_sha256':cut.cut_sha}


def seal_original_physical_suffix(c,plan):
    """record_native_backup was refused at its FIRST guard before sealing."""
    p=c.backup_ports;cut=c.cut
    current=physical_suffix_plan(c,plan['pin'])
    need(current==plan,'NATURAL_REPAIR_PHYSICAL_SUFFIX_PLAN_CHANGED')
    # Original producer already stored exactly this canonical native receipt
    # before its refused record_native_backup() call. Resolve, do not recopy.
    native=dict(plan['pin']);cut.cas.resolve(native)
    result=cut.record_native_backup('collaboration',{'collaboration':plan['root']},{
        'cut_sha256':cut.cut_sha,'instance_sha256':p.collaboration.graph_domain['instance_sha256'],
        'backup_protocol_sha256':p.collaboration.graph_domain['backup_protocol_sha256'],
        'receipt_sha256':native['sha256']})
    need(cut.cut_sha not in p.collaboration.captures,'NATURAL_REPAIR_PHYSICAL_CAPTURE_ONCE')
    p.collaboration.captures[cut.cut_sha]={'service_receipt':result,'native_receipt':native}
    with c.ledger.tx():c.ledger.event(c.t,'R16_ORIGINAL_PHYSICAL_COPY_SEAL_SUFFIX',{
        'cut_sha256':cut.cut_sha,'original_manifest':plan['pin'],'roots':plan['count'],
        'new_physical_copy':False,'original_frozen_team_unchanged':True})
    dest=c.root/('backup-'+str(cut.cut['generation']))
    git=p.git.captures[cut.cut_sha]
    # These are their FIRST calls for this cut, using the SAME original ports.
    p.relay.run(cut,dest/'relay',roles=p.roles)
    p.bridge.run(cut,dest/'bridge',git_exports=git['git_exports'])
    p.registration.frozen(c.fence)
    return {'git_exports':git['git_exports']}


def continue_same_owner(driver,*,expected_owner,collection_pins,physical_pins,start=True):
    """Preflight everything before exact known fault clear; never blind rearm."""
    need(process_identity(os.getpid())==expected_owner,'NATURAL_REPAIR_EXACT_OWNER_PID_START_BOOT')
    need(driver.failed and not driver.finished and driver.shared_started and not driver.pending,
         'NATURAL_REPAIR_RETAINED_DRIVER_NO_NEW_TRAJECTORY')
    need(not getattr(driver,'_r16_natural_input_repair_started',False),'NATURAL_REPAIR_ONCE_NO_RETRY')
    need(not driver.dispatcher.faulted,'NATURAL_REPAIR_ORIGINAL_FINAL_DISPATCHER_HEALTHY')
    manager=driver._r16_natural_manager
    need(manager.driver is driver and manager.thread.is_alive()and not manager.stop.is_set()
         and len(manager.first)==5 and all(v==0 for v in manager.posts.values()),
         'NATURAL_REPAIR_ORIGINAL_MONITOR_FIVE_FIRST_NO_POST')
    for name in ('_r16_poll_thread','_r16_partial_thread','_r16_nofile_poll_thread'):
        thread=getattr(driver,name,None)
        need(thread is None or not thread.is_alive(),'NATURAL_REPAIR_PRIOR_DRIVER_LOOP_DEAD')
    ledger=driver.ledger;plans=[]
    with driver.dispatcher.lock:
        from contextlib import ExitStack
        with ExitStack()as locks:
            need(len(driver.records)==6 and NEW in driver.records and OLD not in driver.records
                 and set(driver.records)==set(manager.tracks),
                 'NATURAL_REPAIR_ORIGINAL_SIX_RECORDS')
            for t,r in sorted(driver.records.items()):
                c=r['launch'].controller
                need(not r['thread'].is_alive()and c.state=='FAULT'and not c.step_in_progress
                     and not r['launch'].stop.is_set(),'NATURAL_REPAIR_OLD_CONTROLLERS_DEAD_NOT_ACTIVE')
                locks.enter_context(c.lock)
            with ledger.mutex:
                faults=dict(ledger.memory_faults)
                need(set(faults)==set(driver.records)|{OLD}
                     and faults[OLD]=='R16_RETIRED_ATTEMPT_SYSTEM_COST'
                     and all(faults[t]in ALLOWED for t in driver.records),
                     'NATURAL_REPAIR_UNRELATED_FAULT_MUST_NOT_CLEAR')
                need(ledger.db.execute("SELECT COUNT(*)FROM requests WHERE state IN ('RESERVED','SENT')").fetchone()[0]==0
                     and ledger.db.execute('SELECT COUNT(*)FROM unknown_stops').fetchone()[0]==0,
                     'NATURAL_REPAIR_INFLIGHT_OR_UNKNOWN_THRESHOLD_MUST_NOT_CLEAR')
            for t,r in sorted(driver.records.items()):
                c=r['launch'].controller;verify_shared_without_admission(c)
                with c.http.registry_lock:http=verify_finished_unsent(c.http)
                clocks=clock_pins(driver,t,r);f=ledger.frontier(t)
                if t in collection_pins:
                    plan=verify_committed(c,collection_pins[t]);kind='RETAINED_COLLECTION'
                elif t in physical_pins:
                    plan=physical_suffix_plan(c,physical_pins[t]);kind='PHYSICAL_SEAL_SUFFIX'
                else:
                    need(c.cut is None and c.ref is None and c.stage is None
                         and c.fence.state=='REGISTERED'and f['state']=='RUNNING'
                         and f['reserved']==f['unresolved']==f['active_operations']==0,
                         'NATURAL_REPAIR_EXACT_ALREADY_RUNNING_NO_CUT_SUFFIX')
                    c.fence._coverage()
                    need(all(not d.frozen()and d.read('cgroup.freeze').strip()=='0'for d in c.fence.domains),
                         'NATURAL_REPAIR_NO_CUT_ALL_ORIGINAL_DOMAINS_RUNNING')
                    plan=None;kind='RUNNING'
                plans.append((t,r,kind,plan,http,clocks))
            need(len(collection_pins)==1 and len(physical_pins)==3
                 and set(collection_pins)|set(physical_pins)<=set(driver.records),
                 'NATURAL_REPAIR_EXACT_ONE_INPUT_THREE_PHYSICAL_SUFFIXES')
            if not start:return {'status':'PREFLIGHT_ONLY','plans':{t:k for t,r,k,p,h,s in plans},'models':0}
            driver._r16_natural_input_repair_started=True
            builder=install_builder(driver);prefix=request_prefix(ledger)
            for t,r,k,p,h,s in plans:archive_finished_unsent(r['launch'].http,h)
            with ledger.capacity_changed:
                need(ledger.memory_faults==faults,'NATURAL_REPAIR_FAULTS_CHANGED_AFTER_PREFLIGHT')
                with ledger.tx():ledger.event('GLOBAL','R16_NATURAL_INPUT_REPAIR_SAME_OWNER',{
                    'kind':REPAIR,'cleared_exact_faults':{t:faults[t]for t in driver.records},
                    'original_request_rows_sha256':prefix,'plans':{t:k for t,r,k,p,h,s in plans},
                    'original_snapshots_points_children_retained':True,'new_charge':0,'replay':False})
                for t,r,k,p,h,s in plans:
                    del ledger.memory_faults[t]
                    r['launch'].controller.state={'RUNNING':'RUNNING','RETAINED_COLLECTION':'POINT_REPAIR_STARTED',
                                                  'PHYSICAL_SEAL_SUFFIX':'BACKUP_SUFFIX_STARTED'}[k]
                need(request_prefix(ledger)==prefix,'NATURAL_REPAIR_ORIGINAL_REQUEST_ROWS_CHANGED')
                driver.failed=False;driver.state='RUNNING';ledger.capacity_changed.notify_all()
    from r16_resume_budget_clocks import resume_projection
    try:
        for t,r,k,p,h,s in plans:
            c=r['launch'].controller
            resume_projection(c.projection,expected_bindings=s,expected_directory=c.root/'budget-clock')
        def resume_one(t,r,kind,plan):
            try:
                c=r['launch'].controller
                with c.lock:
                    if kind=='RETAINED_COLLECTION':complete_retained_point(c,plan,builder)
                    elif kind=='PHYSICAL_SEAL_SUFFIX':finish_backup(c,lambda owner,dest:seal_original_physical_suffix(owner,plan))
                r.pop('terminal',None);status=r['launch'].run();r['terminal']=status
                if status['owner_state']=='FAULT':driver._fault(t)
            except BaseException as exc:failure(driver,t,exc)
        for t,r,k,p,h,s in plans:
            r.setdefault('_r16_retained_old_threads',[]).append(r['thread'])
            thread=threading.Thread(target=resume_one,args=(t,r,k,p),name='r16-natural-suffix-'+digest(t)[:12],daemon=False)
            r['thread']=thread;thread.start()
        def poll():
            try:tick_loop(driver)
            except BaseException as exc:failure(driver,NEW,exc)
        driver._r16_natural_input_repair_poll_thread=threading.Thread(target=poll,name='r16-natural-suffix-original-tick',daemon=False)
        driver._r16_natural_input_repair_poll_thread.start()
        return {'status':'R16_ORIGINAL_SIX_EXACT_SUFFIX_QUEUED','kind':REPAIR,
                'plans':{t:k for t,r,k,p,h,s in plans},'original_natural_monitor_retained':True,
                'original_K3_children_retained':len(driver.dispatcher.children),'new_root':False,'new_charge':0,'request_replay':False}
    except BaseException as exc:failure(driver,NEW,exc);raise
