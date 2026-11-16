"""OPS-only named control action on retained R16 objects. No attach/signals.

All preflight reads are fixed framework identities/metadata, never scientific
bodies. Five original tracks retain their accounts, cuts and objects. The one
explicitly authorized replacement gets an appended SYSTEM record and new account.
"""
from pathlib import Path
import ast,copy,hashlib,importlib.util,inspect,json,os,resource,sys,threading,traceback
from common import need,digest,wire,hash_file,strict,regular_fd,stamp
from bridge import process_identity
from r16_attempt_identity import resolve_row,EXPERIMENT,OLD_SUFFIX,ATTEMPT_SUFFIX,ATTEMPT_ID
BASE=Path(__file__).resolve().parent
OLD=EXPERIMENT+OLD_SUFFIX
NEW=OLD+ATTEMPT_SUFFIX
ALLOWED=frozenset(('SCIENTIFIC6_DRIVER_ADMISSION_SEALED_AFTER_FAILURE',
 'SCIENTIFIC6_DRIVER_FAILURE_RETAINED_NO_RETRY','NATIVE_SCIENTIFIC_OWNER_FAILED_RETAIN_NO_RETRY',
 'SCIENTIFIC_HTTP_REQUEST_BINDING_UNKNOWN'))


def owner_fd_floor():
    soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
    need(hard>=65536,'R16_NOFILE_HARD_LIMIT_TOO_LOW')
    if soft<65536:resource.setrlimit(resource.RLIMIT_NOFILE,(65536,hard))
    return {'soft':resource.getrlimit(resource.RLIMIT_NOFILE)[0],'hard':hard}


def sanitized_exception(exc):
    # No str(exc), source lines, frame locals, or repr of any user object.
    frames=[];tb=exc.__traceback__
    while tb is not None:
        code=tb.tb_frame.f_code
        frames.append({'file':code.co_filename,'line':tb.tb_lineno,'function':code.co_name})
        tb=tb.tb_next
    return {'exception_type':type(exc).__name__,'frames':frames}


def request_prefix(ledger):
    with ledger.mutex:
        return digest([list(r)for r in ledger.db.execute('SELECT * FROM requests ORDER BY id')])


def retire_old_account(ledger):
    """Append-only cost allocation; NEVER reset actual/RNG or update requests."""
    with ledger.tx():
        a=ledger.account(OLD)
        need(a['actual']==339871 and a['generation']==1 and a['stage']==0,
             'R16_EXACT_RETIRED_ATTEMPT_339871')
        need(ledger.db.execute("SELECT COUNT(*)FROM requests WHERE trajectory=? AND state!='SETTLED'",(OLD,)).fetchone()[0]==0,
             'R16_OLD_ATTEMPT_ALL_REQUESTS_SETTLED')
        need(ledger.db.execute('SELECT COUNT(*)FROM snapshots WHERE trajectory=?',(OLD,)).fetchone()[0]==0,
             'R16_OLD_ATTEMPT_HAS_NO_POINT')
        need(ledger.db.execute("SELECT COUNT(*)FROM operations WHERE trajectory=? AND state='ACTIVE'",(OLD,)).fetchone()[0]==0,
             'R16_OLD_ATTEMPT_NO_ACTIVE_OPERATION')
        prior=ledger.db.execute("SELECT metadata FROM events WHERE trajectory=? AND kind='SYSTEM_TOOLING_FAULT_ATTEMPT_RETIRED'",(OLD,)).fetchall()
        metadata={'attempt_id':'original','system_consumption_tokens':339871,'experiment_tokens':0,
            'replacement_attempt_id':ATTEMPT_ID,'replacement_trajectory':NEW,'from_zero':True,
            'same_seed':4287909351,'same_block':1,'requests_rewritten':False,'replay':False}
        if prior:
            need(len(prior)==1 and strict(prior[0][0])==metadata and a['state']=='RETIRED_SYSTEM',
                 'R16_RETIRED_ATTEMPT_SETTLEMENT_CHANGED')
            return False
        ledger.event(OLD,'SYSTEM_TOOLING_FAULT_ATTEMPT_RETIRED',metadata)
        # Account admission state only; original actual and every request remain.
        ledger.db.execute("UPDATE accounts SET state='RETIRED_SYSTEM' WHERE trajectory=?",(OLD,))
        return True


def verify_shared_without_admission(controller):
    """All original _shared binding assertions, except already-known fault flag.

    This is preflight only. The actual scientific loop still uses unmodified
    _shared INCLUDING its admission guard after authorized exact fault clear.
    """
    from native_scientific_owner import NativeScientificOwner
    need(type(controller)is NativeScientificOwner,'R16_ORIGINAL_CONTROLLER_TYPE')
    fn=NativeScientificOwner._shared
    tree=ast.parse(inspect.getsource(fn).strip())
    node=tree.body[0];first=node.body[0]
    need(ast.unparse(first)=="need(not self.ledger.admission_fault(self.t), 'SCIENCE_OWNER_SHARED_FAULT')",
         'R16_ORIGINAL_SHARED_ADMISSION_STATEMENT')
    node.body=node.body[1:];node.name='_verify_shared_without_admission'
    namespace=dict(fn.__globals__)
    exec(compile(ast.fix_missing_locations(tree),'<R16-fixed-framework-binding-preflight>','exec'),namespace)
    namespace[node.name](controller)


def verify_finished_unsent(server):
    """Retained UNSENT rejection is forensic evidence, not remote execution."""
    server.current()
    need(not server.lifecycle_storage_unknown and not server.requests and not server.accepted_sockets,
         'R16_HTTP_ALL_HANDLERS_MUST_FINISH')
    plan=[]
    for key,req in server.retained.items():
        need(req.server is server and req.ledger is server.ledger and req.handle==key
             and req.identity in server.registered and req.finished
             and req.outcome=='PROTOCOL_REJECTED' and req.rid is None and req.request_sha is None
             and not req.stream_opened and type(req.bytes_written)is int and req.bytes_written>=0
             and req.failure_metadata_unknown and not req.delivery_unknown
             and req.connection.fileno()==-1
             and (req.heartbeat_thread is None or not req.heartbeat_thread.is_alive()),
             'R16_ONLY_FINISHED_CLOSED_UNSENT_REJECTION_CAN_ARCHIVE')
        plan.append((key,req))
    return plan


def archive_finished_unsent(server,plan):
    with server.registry_lock:
        need(verify_finished_unsent(server)==plan,'R16_HTTP_RETAINED_CHANGED')
        archive=getattr(server,'_r16_forensic_unsent',None)
        if archive is None:archive={};server._r16_forensic_unsent=archive
        for key,req in plan:
            need(key not in archive,'R16_HTTP_FORENSIC_ARCHIVE_NO_REPLACE')
            with server.ledger.tx():server.ledger.event(req.identity[0],'R16_FINISHED_UNSENT_HTTP_FORENSIC_ARCHIVED',{
                'handle':key,'request_id':None,'outcome':req.outcome,'original_object_retained':True,
                'closed_socket':True,'remote_execution':False,'new_charge':0,'replay':False,
                'protocol_rejection_response_bytes':req.bytes_written})
            archive[key]=req;del server.retained[key]


def verify_controller_suffix(c):
    """Validate state evidence; no new generation, backup, point or thaw write."""
    verify_shared_without_admission(c)
    f=c.ledger.frontier(c.t)
    need(f['state']=='RUNNING' and f['reserved']==0 and f['unresolved']==0
         and f['active_operations']==0,'R16_EXISTING_TRACK_LOGICALLY_DRAINED_RUNNING')
    c.fence._coverage()
    need(all(not d.frozen()and d.read('cgroup.freeze').strip()=='0'for d in c.fence.domains),
         'R16_ALL_ORIGINAL_DOMAINS_ALREADY_RUNNING')
    if c.cut is None:
        need(c.stage is None and c.ref is None and c.fence.state=='REGISTERED',
             'R16_NO_CUT_ORIGINAL_REGISTERED_FENCE')
        return 'RUNNING'
    stage=c.stage;fence=c.fence
    need(stage is not None and stage.team is c.team and stage.team_attempted and stage.team_released
         and stage.old==c.cut.cut['generation'] and stage.new==stage.old+1==f['generation']
         and stage.ref==c.ref['sha256'] and fence.cut is c.cut
         and fence.state=='RELEASE_INCOMPLETE','R16_ONLY_ALREADY_RELEASED_ORIGINAL_STAGE_SUFFIX')
    rows=c.team._stage_registry
    expected={(x.kind,x.role,x.purpose)if x.kind=='MCP'else('GIT',x.role)for x in rows}
    need(stage.changed==expected and len(expected)==4*len(c.team.roles),'R16_ALL_ORIGINAL_PORTS_PREPARED')
    for row in rows:
        p=row.port;b=p.identity if row.kind=='MCP'else p.binding
        need(b.generation==stage.new and b.trajectory==c.t,'R16_ORIGINAL_PORT_SUCCESSOR_GENERATION')
    snapshots=c.ledger.db.execute('SELECT *FROM snapshots WHERE trajectory=? AND generation=?',
        (c.t,stage.old)).fetchall()
    need(len(snapshots)==1 and snapshots[0]['ref_sha']==stage.ref,'R16_ORIGINAL_COMMITTED_POINT_REQUIRED')
    need(len(c.points)==1 and c.points[0]['generation']==stage.old
         and c.points[0]['snapshot']==c.ref and len(c.points[0]['jobs'])==3,
         'R16_ORIGINAL_POINT_AND_K3_RETAINED')
    for job in c.points[0]['jobs']:
        need(c.queue.db.execute('SELECT state FROM jobs WHERE id=?',(job,)).fetchone()[0]=='COMPLETE',
             'R16_ORIGINAL_K3_ALREADY_COMPLETE')
    return 'RELEASING'


def clock_pins(driver,t,record):
    from native_budget_park import NativeBudgetParkProjection,BINDING
    from r16_resume_budget_clocks import _public
    launch=record['launch'];c=launch.controller;p=c.projection
    need(type(p)is NativeBudgetParkProjection and p is c.projection and p.t==t
         and p.gate is launch.gate and p.ledger is driver.ledger
         and p.directory==c.root/'budget-clock' and not p.closed and not p.stop_event.is_set(),
         'R16_EXACT_ORIGINAL_OPEN_CLOCK_PROJECTION')
    need(p.owner==process_identity(os.getpid()),'R16_ORIGINAL_CLOCK_OWNER_PID_START_BOOT')
    need(set(p.roles)==set(record['row']['roles'])==set(p.bindings),'R16_ORIGINAL_CLOCK_ROLE_ROSTER')
    pins={}
    for role in p.roles:
        binding=p.bindings[role]
        need(binding=={'schema':BINDING,'trajectory':t,'role':role,
            'manifest_sha256':digest(driver.manifest),'owner':p.owner},'R16_ORIGINAL_CLOCK_BINDING')
        startup=launch.startup_bindings[role]
        ready=_public(Path(startup['directory'])/'CLOCK_READY.json')
        need(ready.get('schema')=='agensh-original-router-clock-release-v1'
             and ready.get('binding_sha256')==startup['binding_sha256']
             and ready.get('budget_pause_binding_sha256')==digest(binding)
             and ready.get('budget_pause_file')==startup['clock_container_file']
             and ready.get('budget_pause_owner_uid')==startup['owner_uid'],
             'R16_ORIGINAL_ROUTER_CLOCK_READY_PIN')
        pins[role]=digest(binding)
    return pins


def rearm_suffix(c,kind):
    # Called ONLY after all full preflights and exact authorized fault clear.
    c._shared()
    if kind=='RELEASING':
        need(c.fence.state=='RELEASE_INCOMPLETE','R16_RELEASE_SUFFIX_ONCE')
        c.fence.state='RELEASE_REQUESTED'  # original poll only, NO resume/thaw.
    else:need(kind=='RUNNING'and c.cut is None,'R16_EXACT_NO_CUT_RUNNING_SUFFIX')
    c.state=kind


def install_attempt_methods(driver):
    """Retain class identity. Only three named alias resolution paths change."""
    def load(name):
        spec=importlib.util.spec_from_file_location('_r16_attempt_qualified_'+name,BASE/(name+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    import scientific_profile,final_binding,native_scientific_launch
    profile=load('scientific_profile').SearchProfile
    for name in ('__init__','row','reserve_rng'):setattr(scientific_profile.SearchProfile,name,getattr(profile,name))
    final_binding.FinalBinding.__init__=load('final_binding').FinalBinding.__init__
    native_scientific_launch.NativeScientificLaunch.prepare_transport=classmethod(
        load('native_scientific_launch').NativeScientificLaunch.prepare_transport.__func__)
    # Children must also import the qualified alias resolver, never old copies.
    dispatcher=driver.dispatcher
    old=dispatcher.entry
    dispatcher.environment=dict(dispatcher.environment,
        R16_ORIGINAL_FINAL_ENTRY=str(old),R16_ORIGINAL_FINAL_ENTRY_SHA=hash_file(old)['sha256'])
    dispatcher.entry=BASE/'r16_final_child.py';dispatcher.entry_pin=hash_file(dispatcher.entry)


class AttemptHostMux:
    def __init__(self,original,replacement):self.original=original;self.replacement=replacement
    def __getattr__(self,name):
        need(name in ('admit','backend','workers','cli','inventory','ready','task'),'R16_NAMED_HOST_METHOD_ONLY')
        def call(*args,**kwargs):
            value=args[0]if args else None
            trajectory=value.get('trajectory_id')if type(value)is dict else getattr(value,'t',None)
            if trajectory is None:trajectory=getattr(getattr(value,'binding',None),'trajectory',None)
            target=self.replacement if trajectory==NEW else self.original
            return getattr(target,name)(*args,**kwargs)
        return call


def prepare_new_attempt(driver,replacement_host):
    """No constructor/process/model yet; same shared ledger/capacity/FINAL queue."""
    need(all(callable(getattr(replacement_host,n,None))for n in
        ('admit','backend','workers','cli','inventory','ready','task')),'R16_NEW_ATTEMPT_TRUSTED_HOST_PORTS')
    need(OLD in driver.records and NEW not in driver.records and NEW not in driver.rows
         and not driver.pending,'R16_NEW_ATTEMPT_EXACT_FIRSTSTART_ONCE')
    row=resolve_row(driver.manifest,NEW)
    need(not Path(row['root']).exists()and not Path(row['root']).is_symlink(),'R16_ATTEMPT_NEW_PRIVATE_ROOT')
    need(driver.ledger.db.execute('SELECT 1 FROM accounts WHERE trajectory=?',(NEW,)).fetchone()is None,
         'R16_ATTEMPT_NO_OLD_ACCOUNT_OR_RNG')
    old_record=driver.records[OLD]
    archive=getattr(driver,'_r16_retired_attempts',None)
    if archive is None:archive={};driver._r16_retired_attempts=archive
    need(OLD not in archive,'R16_OLD_RECORD_RETAINED_ONCE')
    retire_old_account(driver.ledger)
    archive[OLD]=old_record;del driver.records[OLD]
    driver.rows[NEW]=row;driver.pending.append(NEW)
    driver.host=AttemptHostMux(driver.host,replacement_host)
    driver._r16_attempt_mapping={OLD:{'old_attempt':'original','replacement':NEW,'attempt_id':ATTEMPT_ID,
        'same_seed':4287909351,'same_block':1,'system_consumption_tokens':339871}}
    return row


def _failure(driver,t,exc):
    with driver.ledger.tx():driver.ledger.event(t,'R16_NOFILE_CONTINUATION_FAILED',sanitized_exception(exc))
    driver._fault(t)


def continue_r16(driver,*,expected_owner,replacement_host,run=True):
    """One named non-diagnostic control action. OPS must own its invocation.

    Dry run validates only, except per-owner authorized FD floor. Production
    invocation requires old exact owner; no ledger reopen or process inspector.
    """
    from run_native_scientific6 import ScientificSixDriver
    need(type(driver)is ScientificSixDriver and driver.shared_started and driver.failed
         and not driver.finished and len(driver.records)==6 and not driver.pending,
         'R16_EXACT_RETAINED_SIX_DRIVER')
    need(process_identity(os.getpid())==expected_owner,'R16_EXACT_RETAINED_PROCESS_IDENTITY')
    need(driver.manifest['experiment_id']==EXPERIMENT and OLD in driver.records,'R16_EXACT_AUTHORIZED_EXPERIMENT')
    limits=owner_fd_floor();ledger=driver.ledger
    for name in ('_r16_poll_thread','_r16_partial_thread'):
        thread=getattr(driver,name,None);need(thread is None or not thread.is_alive(),'R16_OLD_CONTROL_THREAD_MUST_BE_DEAD')
    need(not getattr(driver,'_r16_nofile_continuation_started',False),'R16_NOFILE_CONTINUATION_NO_RETRY')
    with ledger.mutex:
        faults=dict(ledger.memory_faults)
        need(set(faults)==set(driver.records) and set(faults.values())<=ALLOWED,
             'R16_UNRELATED_FAULT_MUST_NOT_CLEAR')
        need(ledger.db.execute("SELECT COUNT(*)FROM requests WHERE state IN ('RESERVED','SENT')").fetchone()[0]==0,
             'R16_NO_ACTUALLY_INFLIGHT_REQUESTS')
        need(ledger.db.execute('SELECT COUNT(*)FROM unknown_stops').fetchone()[0]==0,
             'R16_UNKNOWN_THRESHOLD_MUST_NOT_CLEAR')
    plans=[]
    for t,r in driver.records.items():
        launch=r['launch'];c=launch.controller
        need(not r['thread'].is_alive()and c.state=='FAULT'and not c.step_in_progress
             and not launch.stop.is_set()and not c.projection.thread.is_alive(),
             'R16_ALL_RETAINED_SCIENTIFIC_THREADS_MUST_BE_DEAD')
        if t==OLD:continue # Authorized new identity; NEVER certify dead old team.
        with c.http.registry_lock:http_plan=verify_finished_unsent(c.http)
        clock_pins(driver,t,r)
        plans.append((t,r,verify_controller_suffix(c),http_plan))
    need(len(plans)==5,'R16_EXACT_FIVE_LIVE_ORIGINAL_TRACKS')
    if not run:return {'status':'PREFLIGHT_ONLY','plans':{t:k for t,r,k,h in plans},'limits':limits,'model_calls':0}
    driver._r16_nofile_continuation_started=True
    prefix=request_prefix(ledger)
    try:
        install_attempt_methods(driver)
        row=prepare_new_attempt(driver,replacement_host)
        for t,r,k,h in plans:archive_finished_unsent(r['launch'].http,h)
        with ledger.capacity_changed:
            need(ledger.memory_faults==faults,'R16_FAULTS_CHANGED_DURING_PREFLIGHT')
            with ledger.tx():ledger.event('GLOBAL','R16_NOFILE_FIVE_AND_AUTHORIZED_B1_ATTEMPT',{
                'cleared_exact_faults':faults,'retired_attempt':OLD,'new_attempt':NEW,
                'limits':limits,'original_requests_sha256':prefix,'original_ledger_objects_preserved':True,
                'original_10M_K3_preserved':True,'no_replay':True})
            for t,_,_,_ in plans:del ledger.memory_faults[t]
            # Old account remains sealed even though it is no longer active.
            ledger.memory_faults[OLD]='R16_RETIRED_ATTEMPT_SYSTEM_COST'
            for t,r,k,h in plans:rearm_suffix(r['launch'].controller,k)
            need(request_prefix(ledger)==prefix,'R16_ORIGINAL_REQUEST_ROWS_CHANGED')
            driver.failed=False;driver.state='RUNNING';ledger.capacity_changed.notify_all()
        from r16_resume_budget_clocks import resume_projection
        for t,r,k,h in plans:
            c=r['launch'].controller;p=c.projection
            # New b1 projection uses original class default; originals retain
            # the already qualified atomic sample method on their SAME object.
            pins=clock_pins(driver,t,r)
            resume_projection(p,expected_bindings=pins,expected_directory=c.root/'budget-clock')
        def resume_one(t,r):
            try:
                r.pop('terminal',None);status=r['launch'].run();r['terminal']=status
                if status['owner_state']=='FAULT':driver._fault(t)
            except BaseException as exc:_failure(driver,t,exc)
        for t,r,k,h in plans:
            old=r['thread'];r.setdefault('_r16_retained_old_threads',[]).append(old)
            thread=threading.Thread(target=resume_one,args=(t,r),name='r16-nofile-'+digest(t)[:12],daemon=False)
            r['thread']=thread;thread.start()
        def poll():
            try:driver.run()
            except BaseException as exc:_failure(driver,NEW,exc)
        thread=threading.Thread(target=poll,name='r16-nofile-same-owner-driver',daemon=False)
        driver._r16_nofile_poll_thread=thread;thread.start()
        return {'status':'R16_FIVE_CONTINUATION_NEW_B1_ATTEMPT_QUEUED','limits':limits,
            'original_five':5,'new_attempt':row,'old_system_consumption_tokens':339871,
            'original_requests_sha256':prefix,'new_root_allowance_used':False}
    except BaseException as exc:
        _failure(driver,OLD,exc);raise


def apply_r16(driver,*,expected_owner,replacement_host):
    """Initial OPS control call: install future non-debug control BEFORE repair."""
    need(process_identity(os.getpid())==expected_owner,'R16_EXACT_RETAINED_PROCESS_IDENTITY')
    owner_fd_floor()
    from r16_owner_control import install_owner_control
    control=install_owner_control(driver)
    result=continue_r16(driver,expected_owner=expected_owner,replacement_host=replacement_host)
    return {**result,'owner_control_socket':str(control.path),'fixed_commands':['apply-fix','status','drain']}
