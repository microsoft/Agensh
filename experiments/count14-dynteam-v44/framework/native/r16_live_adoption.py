"""OPS-only same-interpreter adoption. No SSH, process attach or owner reopen.

Only public framework AST/retained object references are used internally. Never
emit traceback locals, exception messages, transport contents or credentials.
"""
from pathlib import Path
import ast,copy,dis,hashlib,importlib.util,inspect,sys,threading,types
from common import need,digest
BASE=Path(__file__).resolve().parent
OLD_BUDGET_SHA='5b80a790b2559ddd2fd11e06dcc6ee1641a10d8a12a01206cef92b80f13b76a7'
R16_RID='resp_9e1f2378c8f64ba6db383193ebe0230f'
R16_SUFFIX='/Agensh-1/block-3/seed-2619738241'
POLICY_METHODS=('_unknown_schema','enable_unknown_reservation_policy','unknown_policy_enabled',
 'unknown_charged','unknown_statistics','_unknown_thresholds','admission_fault',
 'charge_unknown_at_reservation','_charge_unknown_at_reservation','frontier',
 'reserve','unknown','settle','ack','global_logical_unresolved')
CASCADE_CODES=frozenset(('SCIENTIFIC6_DRIVER_FAILURE_RETAINED_NO_RETRY',
 'SCIENTIFIC6_DRIVER_ADMISSION_SEALED_AFTER_FAILURE','TEAM_OWNER_STARTUP_FAILED_RETAIN_CUSTODY_NO_RETRY',
 'NATIVE_SCIENTIFIC_OWNER_FAILED_RETAIN_NO_RETRY'))
def _load(name,file):
 spec=importlib.util.spec_from_file_location(name,BASE/file);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def install_ledger(ledger):
 """Preserve exact Ledger class/object/SQLite/condition/flock identity."""
 cls=type(ledger);need(cls.__name__=='Ledger','R16_ORIGINAL_LEDGER_CLASS')
 origin=Path(inspect.getsourcefile(cls));pin=hashlib.sha256(origin.read_bytes()).hexdigest()
 candidate=hashlib.sha256((BASE/'budget.py').read_bytes()).hexdigest()
 need(pin in (OLD_BUDGET_SHA,candidate),'R16_EXACT_ORIGINAL_OR_QUALIFIED_LEDGER_SOURCE')
 new=_load('_r16_qualified_budget','budget.py')
 with ledger.mutex:
  for name in POLICY_METHODS:setattr(cls,name,getattr(new.Ledger,name))
  ledger.enable_unknown_reservation_policy()
 return {'schema':'r16-same-owner-ledger-policy-installed-v1','ledger_class_identity_preserved':True,
         'ledger_reopened':False,'original_source_sha256':pin,'qualified_source_sha256':candidate}

def _position(tb):
 for instruction in dis.get_instructions(tb.tb_frame.f_code,show_caches=True):
  if instruction.offset==tb.tb_lasti:
   p=instruction.positions;return p.lineno or tb.tb_lineno,p.col_offset or 0
 return tb.tb_lineno,0

def _contains(node,line,col):
 start=(getattr(node,'lineno',0),getattr(node,'col_offset',0))
 end=(getattr(node,'end_lineno',0),getattr(node,'end_col_offset',0))
 return start<=(line,col)<end

def _suffix(statements,line,col,*,skip):
 for i,node in enumerate(statements):
  if not _contains(node,line,col):continue
  tail=copy.deepcopy(statements[i+1:])
  if isinstance(node,ast.Try):
   need(any(_contains(n,line,col)for n in node.body),'R16_FAILURE_MUST_BE_IN_TRY_BODY')
   first=copy.deepcopy(node);first.body=_suffix(node.body,line,col,skip=skip)
   if not first.body:first.body=[ast.Pass()]
   return [first]+tail
  if isinstance(node,ast.For):
   need(isinstance(node.target,ast.Name),'R16_CONTINUATION_FIXED_SIMPLE_ROSTER')
   # Finish CURRENT iteration using retained locals. Only subsequent iterations
   # execute original loop prefix/constructor/prime operations.
   first=_suffix(node.body,line,col,skip=skip);rest=copy.deepcopy(node)
   sequence=ast.Call(ast.Name('tuple',ast.Load()),[copy.deepcopy(node.iter)],[])
   offset=ast.BinOp(ast.Call(ast.Attribute(copy.deepcopy(sequence),'index',ast.Load()),[ast.Name(node.target.id,ast.Load())],[]),ast.Add(),ast.Constant(1))
   rest.iter=ast.Subscript(sequence,ast.Slice(lower=offset),ast.Load())
   return first+[rest]+tail
  need(not isinstance(node,(ast.If,ast.With,ast.While)),'R16_UNQUALIFIED_CONTINUATION_CONTROL_FLOW')
  return ([]if skip else[copy.deepcopy(node)])+tail
 raise RuntimeError('R16_EXACT_PUBLIC_FAILURE_STATEMENT_NOT_FOUND')

def public_continuation(tb,*,skip=False,expected_name):
 """Compile suffix of a fixed public frame, never private wrapper source."""
 frame=tb.tb_frame;need(frame.f_code.co_name==expected_name,'R16_PUBLIC_FAILURE_FRAME_NAME')
 path=Path(frame.f_code.co_filename);need(path.name in ('native_team_owner.py','run_native_scientific6.py','test_r16_live_adoption.py'),'R16_PUBLIC_SOURCE_ALLOWLIST')
 tree=ast.parse(path.read_text());functions=[n for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)and n.name==expected_name and n.lineno==frame.f_code.co_firstlineno]
 need(len(functions)==1,'R16_EXACT_PUBLIC_FUNCTION_SOURCE')
 line,col=_position(tb);body=_suffix(functions[0].body,line,col,skip=skip)
 local=dict(frame.f_locals);need(all(k.isidentifier()for k in local),'R16_FRAME_LOCAL_NAMES')
 args=ast.arguments(posonlyargs=[],args=[ast.arg(k)for k in local],kwonlyargs=[],kw_defaults=[],defaults=[])
 fn=ast.FunctionDef(name='_resume_public_suffix',args=args,body=body or[ast.Pass()],decorator_list=[])
 module=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]));space=dict(frame.f_globals)
 exec(compile(module,'<R16-public-suffix:'+expected_name+'>','exec'),space)
 return lambda:space['_resume_public_suffix'](**local)

def retained_start_continuations(driver,failure):
 need(getattr(failure,'code',None)=='MCP_ACCOUNT_NOT_ADMITTING','R16_EXACT_STARTUP_CASCADE_EXCEPTION')
 frames={};tb=failure.__traceback__
 while tb is not None:
  name=tb.tb_frame.f_code.co_name;file=Path(tb.tb_frame.f_code.co_filename).name
  if (file,name)in(('native_team_owner.py','start'),('run_native_scientific6.py','launch_one')):frames[(file,name)]=tb
  tb=tb.tb_next
 need(len(frames)==2,'R16_ORIGINAL_STARTUP_TRACEBACK_REQUIRED')
 team_tb=frames[('native_team_owner.py','start')];driver_tb=frames[('run_native_scientific6.py','launch_one')]
 need(driver_tb.tb_frame.f_locals['self'] is driver,'R16_ORIGINAL_DRIVER_REFERENCE')
 team=team_tb.tb_frame.f_locals['self'];record=driver.records[team.t]
 need(record['team']is team and record['launch'].attached is False and record['launch'].started is False and record['launch'].released is False,'R16_PARTIAL_HELD_ONLY')
 need(not team.listeners and len(team.configs)<len(team.roles),'R16_PARTIAL_NO_LISTENERS_NO_RELEASE')
 # The failed NativeMcpSession constructor rejected BEFORE registration/spawn.
 role=team_tb.tb_frame.f_locals['role'];purpose=team_tb.tb_frame.f_locals['purpose']
 need((role,purpose)not in team.sessions,'R16_FAILED_SESSION_MUST_NOT_EXIST_NO_RESPAWN')
 first=public_continuation(team_tb,expected_name='start');second=public_continuation(driver_tb,skip=True,expected_name='launch_one')
 return team.t,first,second

def restart_controller(driver,t):
 record=driver.records[t];launch=record['launch'];controller=launch.controller
 need(not record['thread'].is_alive()and not controller.step_in_progress and not launch.stop.is_set(),'R16_CONTROLLER_NO_REENTRY')
 record.pop('terminal',None)
 def run():
  try:
   status=launch.run();record['terminal']=status
   if status['owner_state']=='FAULT':driver._fault(t)
  except BaseException:driver._fault(t)
 thread=threading.Thread(target=run,name='science-adopt-'+digest(t)[:12],daemon=False)
 record['thread']=thread;thread.start();return thread

def _install_runtime_methods(driver):
    # Keep every original class identity used by the exact-type guards. Only
    # methods change; source files, graph pins and original objects stay retained.
    snapshot=_load('_r16_qualified_snapshot','snapshot.py')
    whole=_load('_r16_qualified_whole_team','native_whole_team.py')
    relay=_load('_r16_qualified_scientific_relay','scientific_relay.py')
    driver_module=_load('_r16_qualified_driver','run_native_scientific6.py')
    type(driver.cas).capture_tree=snapshot.CAS.capture_tree
    import native_whole_team,scientific_relay
    native_whole_team.NativeWholeTeamPhysicalBackup.run=whole.NativeWholeTeamPhysicalBackup.run
    scientific_relay.ScientificUsage.record=relay.ScientificUsage.record
    type(driver).tick=driver_module.ScientificSixDriver.tick

def _continue_parked_backup(controller):
    """Original cut and completed native exports retained. No producer replay.

    Only the failed read-only physical copy gets a NEW destination; its partial
    original is forensic, never treated as complete. No model/tool/Git business
    request from the completed prefix is sent again.
    """
    c=controller;cut=c.cut;ports=c.backup_ports
    ports.registration.frozen(c.fence);cut.current({'DRAINING'})
    need(set(cut.receipts)=={'gitea','gitea_database'} and cut.binding is None,
         'R16_EXACT_ORIGINAL_TWO_BACKUP_RECEIPTS_REQUIRED')
    need(cut.cut_sha in ports.git.captures and cut.cut_sha in ports.gitea_database.captures,
         'R16_ORIGINAL_BACKUP_HANDLES_REQUIRED')
    need(cut.cut_sha not in ports.collaboration.captures,'R16_FAILED_COPY_NOT_COMMITTED')
    git=ports.git.captures[cut.cut_sha]
    need(not ports.git.children,'R16_ORIGINAL_GIT_CHILDREN_MUST_ALREADY_BE_REAPED')
    dest=c.root/('backup-'+str(cut.cut['generation'])+'-r16-authorized-readonly-continuation')
    need(not dest.exists()and not dest.is_symlink(),'R16_COPY_CONTINUATION_ONCE_NO_CLOBBER')
    dest.mkdir(mode=0o700)
    ports.collaboration.run(cut,dest/'collaboration-physical')
    ports.relay.run(cut,dest/'relay',roles=ports.roles)
    ports.bridge.run(cut,dest/'bridge',git_exports=git['git_exports'])
    ports.registration.frozen(c.fence);c._shared();cut.current({'DRAINING'})
    from budget import SERVICES
    need(set(cut.receipts)==SERVICES,'R16_ORIGINAL_ALL_NATIVE_BACKUPS_REQUIRED')
    c.exports=copy.deepcopy(git['git_exports'])
    pins={**c.pins,'native_writer_fence':c.fence.receipt['sha256'],
          'gitea_exports':digest({'registered_refs':list(c.refs),'exports':c.exports})}
    c.ref=cut.capture(roles=c.roles,pins=pins,parent=c.parent);c.state='COMMITTED'

def _prepare_controller(driver,t):
    r=driver.records[t];c=r['launch'].controller
    need(r['thread']is threading.current_thread()and not c.step_in_progress and not r['launch'].stop.is_set(),
         'R16_ORIGINAL_CONTROLLER_MUST_NOT_BE_REENTERED')
    need(c.state=='FAULT','R16_RETAINED_CONTROLLER_STATE')
    if c.cut is None:
        need(c.fence.state=='REGISTERED','R16_UNSTARTED_CUT_ONLY')
        c.state='RUNNING';return
    need(c.cut.binding is None and c.ledger.frontier(t)['state']=='DRAINING',
         'R16_ORIGINAL_UNCOMMITTED_DRAINING_CUT')
    if c.fence.state=='PARK_INCOMPLETE':
        need(not c.cut.receipts and c.fence.cut is c.cut,'R16_ORIGINAL_PARTIAL_PARK_NOT_BACKUP')
        # Observe ORIGINAL domains, not a second park request or new migration.
        c.fence._coverage()
        need(all(d.frozen()and d.read('cgroup.freeze').strip()=='1'for d in c.fence.domains),
             'R16_ORIGINAL_ALL_DOMAINS_STILL_FROZEN')
        c.fence.state='PARK_REQUESTED'
        need(c.fence.poll_park(),'R16_ORIGINAL_PARK_PROOF_NOT_READY')
        c.state='PARKED';return
    need(c.fence.state=='PARKED','R16_ORIGINAL_PARKED_BACKUP_ONLY')
    c.state='BACKUP_STARTED';_continue_parked_backup(c)

def install(driver,*,failure=None,unknown_request=R16_RID,run=False):
    """OPS calls in the SAME owning interpreter. No model rehearsal/restart.

    run=False: install + append idempotent approved charge, no gate/fault clear.
    run=True: additionally resume original controller objects/cuts and exact
    never-released sixth startup suffix asynchronously. Call once, no retry.
    """
    need(getattr(driver,'shared_started',False)and not driver.finished,'R16_EXISTING_DRIVER_NOT_FINISHED')
    prior=getattr(driver,'_r16_adoption_receipt',None)
    if run and prior is not None:return {**prior,'already_started':True}
    if failure is None:failure=sys.exception()
    plan=retained_start_continuations(driver,failure)if run else None
    ledger=driver.ledger;receipt=install_ledger(ledger)
    with ledger.mutex:
        r=ledger.db.execute('SELECT *FROM requests WHERE id=?',(unknown_request,)).fetchone()
        need(r is not None and r['trajectory'].endswith(R16_SUFFIX)and r['upper_bound']==266240,
             'R16_EXACT_USER_APPROVED_UNKNOWN')
    receipt.update(request_id=unknown_request,charged_now=ledger.charge_unknown_at_reservation(unknown_request),
        trajectory=r['trajectory'],budget_actual=ledger.frontier(r['trajectory'])['actual'],physical_slot_retained=True)
    if not run:return receipt
    need(driver.failed and not driver.pending and len(driver.records)==6,'R16_RETAINED_SIX_EXISTING_RECORDS')
    need(ledger.db.execute("SELECT COUNT(*)FROM requests WHERE state IN ('RESERVED','SENT')").fetchone()[0]==0,
         'R16_ORIGINAL_ACCEPTED_REQUESTS_MUST_SETTLE')
    allowed=CASCADE_CODES|{'WHOLE_TEAM_PHYSICAL_BACKUP_FAILED_NO_RETRY'}
    need(set(ledger.memory_faults)<=set(driver.records)and all(v in allowed for v in ledger.memory_faults.values()),
         'R16_UNRELATED_SECURITY_OR_ACCOUNTING_FAULT_MUST_NOT_CLEAR')
    need(ledger.db.execute('SELECT COUNT(*)FROM unknown_stops').fetchone()[0]==0,'R16_UNKNOWN_STOP_THRESHOLD_CROSSED')
    for t,record in driver.records.items():
        if t==plan[0]:continue
        c=record['launch'].controller
        need(not record['thread'].is_alive()and c.state=='FAULT'and not c.step_in_progress,
             'R16_ALL_ORIGINAL_CONTROLLER_HANDLES_RETAINED_DEAD')
    _install_runtime_methods(driver)
    with ledger.tx():
        old=dict(ledger.memory_faults)
        # Charge did not claim remote completion. It only closes this logical
        # budget reservation so that this track may admit its NEXT request.
        if ledger.account(r['trajectory'])['state']=='DRAINING':
            c=driver.records[r['trajectory']]['launch'].controller
            need(c.cut is None,'R16_UNKNOWN_TRACK_NO_STARTED_CUT')
            ledger.db.execute("UPDATE accounts SET state='RUNNING' WHERE trajectory=?",(r['trajectory'],))
        ledger.event(r['trajectory'],'R16_SAME_OWNER_AUTHORIZED_ADOPTION',{'request_id':unknown_request,
            'cleared_retained_codes':old,'request_history_unchanged':True,'ledger_reopened':False,
            'new_owner_or_root':False,'original_checkpoints_preserved':True,
            'qualified_patch':{f:hashlib.sha256((BASE/f).read_bytes()).hexdigest()for f in
                ('budget.py','snapshot.py','native_whole_team.py','scientific_relay.py','run_native_scientific6.py','r16_live_adoption.py')}})
    with ledger.capacity_changed:
        need(ledger.memory_faults==old,'R16_FAULT_CHANGED_DURING_INSTALL')
        ledger.memory_faults.clear();ledger.capacity_changed.notify_all()
    driver.failed=False;driver.state='RUNNING'
    receipt.update(adoption_started=True,new_root=False,original_handles_retained=True)
    driver._r16_adoption_receipt=receipt
    def failure_record(exc):
        with ledger.tx():ledger.event('GLOBAL','R16_SAME_OWNER_ADOPTION_FAILED',
            {'exception_type':type(exc).__name__,'code':getattr(exc,'code','R16_ADOPTION_EXCEPTION')})
    # Resume each original controller independently. Slow frozen physical copies
    # must not prevent other tracks or FINAL poll from making progress.
    for t,record in driver.records.items():
        if t==plan[0]:continue
        record.pop('terminal',None)
        def resume_controller(t=t,record=record):
            try:
                _prepare_controller(driver,t)
                status=record['launch'].run();record['terminal']=status
                if status['owner_state']=='FAULT':driver._fault(t)
            except BaseException as exc:failure_record(exc);driver._fault(t)
        thread=threading.Thread(target=resume_controller,name='science-adopt-'+digest(t)[:12],daemon=False)
        record['thread']=thread;thread.start()
    def resume_sixth():
        try:plan[1]();plan[2]()
        except BaseException as exc:failure_record(exc);driver._fault(plan[0])
    partial_thread=threading.Thread(target=resume_sixth,name='r16-partial-native-start-continuation',daemon=False)
    driver._r16_partial_thread=partial_thread;partial_thread.start()
    def poll():
        try:driver.run()
        except BaseException as exc:failure_record(exc);driver._fault(plan[0])
    poll_thread=threading.Thread(target=poll,name='r16-same-owner-driver-poll',daemon=False)
    driver._r16_poll_thread=poll_thread;poll_thread.start()
    return receipt
