"""One fixed original-owner suffix: claim-lock fix + per-replicate replacement.

Does not replay an old child, rerun a physical backup, re-post old messages,
reopen a ledger, replace a scientific identity, or use wrapped driver.run().
"""
from pathlib import Path
import copy,importlib.util,json,os,threading,sys
from contextlib import ExitStack
from common import need,digest,wire,publish,hash_file,private_dir,strict,sync_dir
from bridge import process_identity
from budget import SERVICES
from r16_nofile_continuation import (verify_shared_without_admission,verify_finished_unsent,
    archive_finished_unsent,clock_pins,request_prefix,NEW,OLD)
from r16_natural_input_repair import parked,finish_backup,tick_loop,failure
BASE=Path(__file__).resolve().parent
ALLOWED=frozenset(('SCIENTIFIC6_DRIVER_ADMISSION_SEALED_AFTER_FAILURE',
 'SCIENTIFIC6_DRIVER_FAILURE_RETAINED_NO_RETRY','NATIVE_SCIENTIFIC_OWNER_FAILED_RETAIN_NO_RETRY',
 'NATIVE_FINAL_CHILD_FAILED_NO_RETRY'))
FAILED='1d5f43c51ab5d7cad9e4707c8ec510db0ff26dd8bb23b42d83431108f3eec3bd'
BRIDGE_PINS={'candidate_manifest/INPUTS.json':{'size':2081,'sha256':'88d5fb4ca4cdf8634fe01f92ea06f9567efaeb99498747ea3778d49f23e57c7e'},
 'bridge_journal/INVENTORY.json':{'size':2104,'sha256':'28106974f83678d17e631734189d52a18311cf65485d17bf3c33eaea65c51238'},
 'bridge_journal/bridge.sqlite':{'size':7028736,'sha256':'9bf589b11a513cb0e5a04247811f9b8464aff3196f0713a803b947236984adaf'}}


def install(driver):
    """Methods, not new object instances; old dual locks/DB/Popen remain owned."""
    def load(name):
        spec=importlib.util.spec_from_file_location('_r16_final_rpc_qualified_'+name,BASE/(name+'.py'))
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    import final_queue,final_binding,native_final_dispatch,native_k3
    q=load('final_queue');fb=load('final_binding');nk=load('native_k3');nd=load('native_final_dispatch')
    for name in ('_job','claim','attach','reap','complete','frontier'):
        setattr(final_queue.FinalQueue,name,getattr(q.FinalQueue,name))
    q.attempts.initialize(driver.queue)
    for name in ('__init__','bind_request'):setattr(final_binding.FinalBinding,name,getattr(fb.FinalBinding,name))
    native_k3.audit_three=nk.audit_three;nd.audit_three=nk.audit_three
    # New method function globals retain qualified modules even though the
    # original class object is shared by existing authorities/dispatchers.
    for name in ('dispatch_one','_poll'):setattr(native_final_dispatch.NativeFinalDispatcher,name,getattr(nd.NativeFinalDispatcher,name))
    original=Path(driver.dispatcher.environment['R16_ORIGINAL_FINAL_ENTRY'])
    need(original.name=='run_native_final_child.py' and hash_file(original)['sha256']==driver.dispatcher.environment['R16_ORIGINAL_FINAL_ENTRY_SHA'],'FINAL_RPC_REPAIR_ORIGINAL_CHILD_PIN')
    driver.dispatcher.entry=BASE/'r16_final_child.py';driver.dispatcher.entry_pin=hash_file(driver.dispatcher.entry)
    old=driver.dispatcher.environment.get('PYTHONPATH','')
    driver.dispatcher.environment['PYTHONPATH']=str(BASE)+(os.pathsep+old if old else '')


def bridge_plan(c,pins=BRIDGE_PINS):
    f=parked(c);p=c.backup_ports.bridge;cut=c.cut
    need(f['state']=='DRAINING' and c.ref is None and set(cut.receipts)==SERVICES-{'bridge'},'FINAL_RPC_REPAIR_EXACT_FOUR_SEALED')
    need(cut.cut_sha not in p.captures,'FINAL_RPC_REPAIR_BRIDGE_NOT_ALREADY_CAPTURED')
    dest=c.root/('backup-'+str(cut.cut['generation']))/'bridge'
    need(dest.is_dir()and not(dest/'RECEIPT.json').exists(),'FINAL_RPC_REPAIR_ORIGINAL_BRIDGE_PARTIAL')
    for name,pin in pins.items():need(hash_file(dest/name)==pin,'FINAL_RPC_REPAIR_BRIDGE_FIXED_ARTIFACT_PIN')
    inventory=strict((dest/'bridge_journal/INVENTORY.json').read_bytes())
    inputs=strict((dest/'candidate_manifest/INPUTS.json').read_bytes())
    need(wire(inventory)==(dest/'bridge_journal/INVENTORY.json').read_bytes()and wire(inputs)==(dest/'candidate_manifest/INPUTS.json').read_bytes(),'FINAL_RPC_REPAIR_CANONICAL_ORIGINAL_ARTIFACTS')
    need(inventory['cut_sha256']==inputs['cut_sha256']==cut.cut_sha and inventory['instance_sha256']==p.instance_sha,'FINAL_RPC_REPAIR_BRIDGE_ORIGINAL_SCOPE')
    frozen=inventory['writer_fence_receipt']
    need(inputs['writer_fence_receipt']==frozen and inputs['gitea_service_receipt']==cut.receipts['gitea'] and inputs['gitea_repo_object']==cut.packed['gitea_repo'],'FINAL_RPC_REPAIR_ORIGINAL_INPUTS_SHARED_BINDINGS')
    exports=c.backup_ports.git.captures[cut.cut_sha]['git_exports']
    need(inputs['git_exports']==exports,'FINAL_RPC_REPAIR_ORIGINAL_EXPORTS')
    for kind in ('NATIVE_BRIDGE_BACKUP_STARTED','NATIVE_BRIDGE_BACKUP_FAILED'):
        n=sum(strict(r[0]).get('cut_sha256')==cut.cut_sha for r in c.ledger.db.execute('SELECT metadata FROM events WHERE trajectory=?AND kind=?',(c.t,kind)))
        need(n==1,'FINAL_RPC_REPAIR_ONE_STARTED_ONE_FAILED_BRIDGE')
    return {'destination':dest,'inventory':inventory,'inputs':inputs,'pins':pins,'exports':exports}


def seal_bridge(c,plan):
    p=c.backup_ports.bridge;cut=c.cut;dest=plan['destination'];inventory=plan['inventory'];inputs=plan['inputs']
    # No backup/copy invoked. Only the original already-materialized artifacts
    # can qualify the unstarted receipt/seal/capture suffix.
    need(bridge_plan(c,plan['pins'])==plan,'FINAL_RPC_REPAIR_BRIDGE_PLAN_CHANGED')
    frozen,current=p._current(cut,{'DRAINING'})
    need(frozen==inventory['writer_fence_receipt'] and current==inventory['state'],'FINAL_RPC_REPAIR_ORIGINAL_FROZEN_STATE_CHANGED')
    exports_sha=p._exports(cut,plan['exports']);need(exports_sha==inputs['gitea_exports_sha256'],'FINAL_RPC_REPAIR_EXPORT_DIGEST')
    receipt={'schema':'agensh-original-bridge-consistent-backup-receipt-v1','cut_sha256':cut.cut_sha,
        'instance_sha256':p.instance_sha,'backup_protocol_sha256':p.protocol_sha,
        'writer_fence_receipt':frozen,'bridge_database':plan['pins']['bridge_journal/bridge.sqlite'],
        'inventory_sha256':digest(inventory),'candidate_INPUT_sha256':digest(inputs),
        'gitea_exports_sha256':exports_sha,'other_backend_async_or_shell_terminal_not_claimed':True}
    publish(dest/'RECEIPT.json',wire(receipt));sync_dir(dest)
    native=cut.cas.store_bytes(wire(receipt))
    _,after=p._current(cut,{'DRAINING'});need(after==current,'FINAL_RPC_REPAIR_BRIDGE_CURRENT_CHANGED')
    sources={name:dest/name for name in ('candidate_manifest','bridge_journal')}
    ref=cut.record_native_backup('bridge',sources,{'cut_sha256':cut.cut_sha,'instance_sha256':p.instance_sha,
        'backup_protocol_sha256':p.protocol_sha,'receipt_sha256':native['sha256']})
    p.captures[cut.cut_sha]={'inputs':copy.deepcopy(inputs),'state':current,'native_receipt':native,'service_receipt':ref}
    with c.ledger.tx():c.ledger.event(c.t,'R16_ORIGINAL_BRIDGE_RECEIPT_SEAL_SUFFIX',{
        'cut_sha256':cut.cut_sha,'original_artifacts':plan['pins'],'new_backup_or_copy':False,
        'original_failed_attempt_retained':True,'native_receipt_sha256':native['sha256']})
    return {'git_exports':plan['exports']}


def suffix(c):
    verify_shared_without_admission(c);f=c.ledger.frontier(c.t)
    need(c.state=='FAULT' and not c.step_in_progress and f['reserved']==f['unresolved']==f['active_operations']==0,'FINAL_RPC_REPAIR_CONTROLLER_QUIESCENT')
    c.fence._coverage()
    if c.t==NEW:return 'BRIDGE_SEAL_SUFFIX',bridge_plan(c)
    need(f['state']=='RUNNING' and all(not d.frozen()and d.read('cgroup.freeze').strip()=='0' for d in c.fence.domains),'FINAL_RPC_REPAIR_ALREADY_RUNNING_DOMAINS')
    if c.cut is None:
        need(c.ref is c.stage is None and c.fence.state=='REGISTERED','FINAL_RPC_REPAIR_NO_CUT_ORIGINAL_REGISTERED')
        return 'RUNNING',None
    need(c.fence.state=='RELEASE_REQUESTED' and c.ref is not None and c.stage is not None
         and c.stage.team_attempted and c.stage.team_released and c.stage.new==f['generation']
         and c.stage.old==c.cut.cut['generation'] and set(c.cut.receipts)==SERVICES,'FINAL_RPC_REPAIR_RELEASE_POLL_ONLY')
    return 'RELEASING',None


def continue_same_owner(driver,*,expected_owner,start=True):
    need(process_identity(os.getpid())==expected_owner,'FINAL_RPC_REPAIR_OWNER_PID_START_BOOT')
    need(driver.failed and not driver.finished and driver.shared_started and not driver.pending
         and len(driver.records)==6 and NEW in driver.records and OLD not in driver.records,
         'FINAL_RPC_REPAIR_RETAINED_SIX_NO_NEW_ROOT')
    need(not getattr(driver,'_r16_final_rpc_repair_started',False),'FINAL_RPC_REPAIR_SINGLE_USE')
    d=driver.dispatcher;l=driver.ledger;manager=driver._r16_natural_manager
    need(d.faulted and d.server.thread.is_alive() and d.server.path.exists() and len(manager.first)==6,
         'FINAL_RPC_REPAIR_RETAINED_SERVER_AND_MANAGER')
    for n in ('_r16_poll_thread','_r16_partial_thread','_r16_nofile_poll_thread','_r16_natural_input_repair_poll_thread'):
        thread=getattr(driver,n,None);need(thread is None or not thread.is_alive(),'FINAL_RPC_REPAIR_OLD_POLL_THREADS_DEAD')
    plans=[]
    with manager.lock,d.lock,ExitStack()as locks:
        for t,r in sorted(driver.records.items()):
            c=r['launch'].controller;locks.enter_context(c.lock)
            need(not r['thread'].is_alive() and not r['launch'].stop.is_set(),'FINAL_RPC_REPAIR_OLD_CONTROLLER_THREAD_DEAD')
            k,p=suffix(c);h=verify_finished_unsent(r['launch'].http);clocks=clock_pins(driver,t,r)
            plans.append((t,r,k,p,h,clocks))
        need(sorted(k for t,r,k,p,h,s in plans)==['BRIDGE_SEAL_SUFFIX','RELEASING','RUNNING','RUNNING','RUNNING','RUNNING'],'FINAL_RPC_REPAIR_EXACT_V3_SUFFIX_SET')
        original=d.children[FAILED];j=driver.queue._job(FAILED)
        need(j['state']=='CHILD_EXITED_HOLD' and original['terminal']['exit_code']==1 and original['job']['replicate']==3,
             'FINAL_RPC_REPAIR_ORIGINAL_FAILED_REPLICATE3')
        import native_replicate_attempts
        p=native_replicate_attempts.proof(d,original)
        need(p['native_aux_tokens']==147921 and p['native_request_count']==14
             and p['native_ledger_sha256']=='9e92c7be47e09b218705533c2a292f5d4faf08e4f2ed86429b10f675dfb06a26'
             and p['request_ids_sha256']=='59cb6235677d17702a48ab9ba1b3f0c6b3248136e3a8307cd580b24cfde55ec1',
             'FINAL_RPC_REPAIR_ORIGINAL_FAILED_FINANCIAL_PINS')
        faults=dict(l.memory_faults)
        need(all(faults.get(t)in ALLOWED for t in driver.records) and set(faults)==set(driver.records)|{OLD}
             and faults[OLD]=='R16_RETIRED_ATTEMPT_SYSTEM_COST','FINAL_RPC_REPAIR_ONLY_KNOWN_EXACT_FAULTS')
        if not start:return {'status':'PREFLIGHT_ONLY','plans':{t:k for t,r,k,p,h,s in plans},'failed_aux_system_tokens':147921,'new_requests':0}
        driver._r16_final_rpc_repair_started=True
        install(driver);prefix=request_prefix(l)
        for t,r,k,p,h,s in plans:archive_finished_unsent(r['launch'].http,h)
        with l.capacity_changed:
            need(l.memory_faults==faults,'FINAL_RPC_REPAIR_EXACT_FAULT_SET_CHANGED')
            with l.tx():l.event('GLOBAL','R16_FINAL_RPC_LOCK_AND_ONE_REPLICATE_SUFFIX',{
                'cleared_exact_faults':{t:faults[t]for t in driver.records},'request_rows_sha256':prefix,
                'original_handles_retained':True,'new_root':False,'request_replay':False,'plans':{t:k for t,r,k,p,h,s in plans}})
            for t,r,k,p,h,s in plans:
                del l.memory_faults[t];r['launch'].controller.state=k if k!='BRIDGE_SEAL_SUFFIX' else 'BACKUP_SUFFIX_STARTED'
            d.faulted=False;driver.failed=False;driver.state='RUNNING';l.capacity_changed.notify_all()
            need(request_prefix(l)==prefix,'FINAL_RPC_REPAIR_ORIGINAL_REQUEST_ROWS_CHANGED')
    try:
        # Reap and audit the original eleven successful children using original
        # Popen handles, dispose only failedK3. No new claim is dispatched here.
        d.poll()
        from r16_resume_budget_clocks import resume_projection
        for t,r,k,p,h,s in plans:resume_projection(r['launch'].controller.projection,expected_bindings=s,expected_directory=r['launch'].controller.root/'budget-clock')
        def resume_one(t,r,k,p):
            try:
                c=r['launch'].controller
                if k=='BRIDGE_SEAL_SUFFIX':
                    with c.lock:finish_backup(c,lambda owner,dest:seal_bridge(owner,p))
                r.pop('terminal',None);r['terminal']=r['launch'].run()
                if r['terminal']['owner_state']=='FAULT':driver._fault(t)
            except BaseException as e:failure(driver,t,e)
        for t,r,k,p,h,s in plans:
            r.setdefault('_r16_retained_old_threads',[]).append(r['thread'])
            thread=threading.Thread(target=resume_one,args=(t,r,k,p),name='r16-final-rpc-suffix-'+digest(t)[:12],daemon=False)
            r['thread']=thread;thread.start()
        if manager.thread is None or not manager.thread.is_alive():
            manager._r16_retained_old_threads=getattr(manager,'_r16_retained_old_threads',[])+[manager.thread]
            need(not manager.stop.is_set(),'FINAL_RPC_REPAIR_ORIGINAL_MANAGER_NOT_CANCELLED');manager.thread=None;manager.start()
        def poll():
            try:tick_loop(driver)
            except BaseException as e:failure(driver,NEW,e)
        driver._r16_final_rpc_repair_poll_thread=threading.Thread(target=poll,name='r16-final-rpc-original-tick',daemon=False)
        driver._r16_final_rpc_repair_poll_thread.start()
        return {'status':'R16_ORIGINAL_OWNER_SUFFIX_STARTED','same_owner':True,'replicate_id':3,'attempt':2,
                'original_children_retained':len(d.children),'failed_aux_system_tokens':147921,'new_root':False,'replay':False}
    except BaseException as e:failure(driver,NEW,e);raise
