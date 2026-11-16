"""Same-interpreter local failures stay local; model/financial guards stay global.

No network/credential/Gitea/usage/custody guard is removed. No request is retried.
The original OPS canary tick is left installed, including its unique tick0.
"""
import ast,copy,functools,inspect,threading,textwrap
from types import MethodType
from common import need,digest,hash_file
from pathlib import Path

LOCAL_CODES=frozenset(('SCIENTIFIC6_DRIVER_FAILURE_RETAINED_NO_RETRY',
 'SCIENTIFIC6_DRIVER_ADMISSION_SEALED_AFTER_FAILURE','NATIVE_SCIENTIFIC_OWNER_FAILED_RETAIN_NO_RETRY',
 'TEAM_OWNER_STARTUP_FAILED_RETAIN_CUSTODY_NO_RETRY','NATIVE_RELAY_BACKUP_INCOMPLETE_NO_RETRY',
 'WHOLE_TEAM_PHYSICAL_BACKUP_FAILED_NO_RETRY','NATIVE_BRIDGE_BACKUP_STARTUP_BINDING_UNKNOWN_NO_RETRY',
 'NATIVE_BRIDGE_BACKUP_INCOMPLETE_NO_RETRY','NATIVE_GIT_BACKUP_CHILD_UNKNOWN_RETAIN_NO_RETRY',
 'NATIVE_GIT_BACKUP_TERMINAL_STORAGE_UNKNOWN','NATIVE_GIT_REPOSITORY_BACKUP_INCOMPLETE_NO_RETRY',
 'NATIVE_WRITER_PARK_INCOMPLETE_RETAIN_NO_RETRY','NATIVE_WRITER_PARK_PROOF_INCOMPLETE_RETAIN_NO_RETRY',
 'NATIVE_WRITER_RELEASE_INCOMPLETE_RETAIN_NO_RETRY','NATIVE_WRITER_RELEASE_PROOF_INCOMPLETE_RETAIN_NO_RETRY',
 'NATIVE_SCIENCE_RETIREMENT_FAILED_NO_RETRY','NATIVE_SCIENCE_RETIREMENT_PROOF_FAILED_NO_RETRY',
 'NATIVE_WRITER_RETIREMENT_THAW_INCOMPLETE_NO_RETRY','NATIVE_WRITER_RETIREMENT_PROOF_INCOMPLETE_NO_RETRY',
 'NATIVE_FINAL_DISPATCH_INCOMPLETE_NO_RETRY','NATIVE_FINAL_AUDIT_FAILED_NO_RETRY'))

def shared_control_reason(ledger):
 """Actual model_control/UNKNOWN stops, not peer's derived parent.failed hold.

A fresh branch's NEW_CURRENT_OWNER_REQUIRES_RELEASE hold is branch-local and
never stops main. All other real pauses and both ledgers' UNKNOWN stops remain.
No wrapper is temporarily replaced, and driver.failed is never toggled to test.
 """
 peer=getattr(ledger,'_aggregate_capacity_peer',None)
 ledgers=peer.ledgers if peer is not None else (ledger,)
 with ledger.mutex:
  for own in ledgers:
   control=own.db.execute('SELECT paused,reason FROM model_control WHERE singleton=1').fetchone()
   is_new_branch=peer is not None and own is peer.branch and control and control['reason']=='NEW_CURRENT_OWNER_REQUIRES_RELEASE'
   if control and control['paused'] and not is_new_branch:return 'EXISTING_RELAY_OR_BILLING_MODEL_PAUSE'
   if own.db.execute('SELECT 1 FROM unknown_stops LIMIT 1').fetchone():return 'EXISTING_SEARCH_UNKNOWN_STOP'
 return None

def global_reason(ledger):
 with ledger.mutex:
  actual=shared_control_reason(ledger)
  if actual:return actual
  codes=[v for v in ledger.memory_faults.values()if v not in LOCAL_CODES]
  return codes[0]if codes else None

def _event(ledger,t,kind,fields):
 with ledger.tx():ledger.event(t,kind,fields)

def _local_driver_fault(self,t):
 reason=global_reason(self.ledger)
 if reason:return self._isolation.original_driver_fault(t)
 need(t in self.rows,'ISOLATION_REGISTERED_TRAJECTORY')
 self._isolation.trajectories.add(t)
 self.ledger.latch_fault(t,'SCIENTIFIC6_DRIVER_FAILURE_RETAINED_NO_RETRY')
 _event(self.ledger,t,'TRAJECTORY_LOCAL_FAULT_RETAINED',{'scope':'trajectory','global_admission_sealed':False,
  'requests_replayed':0,'handles_retained':True})
 # Crucially never writes driver.failed/state, nor another trajectory's latch.

class Isolation:
 def __init__(self,driver):
  self.driver=driver;self.original_driver_fault=driver._fault
  self.trajectories=set();self.points={};self.defer_finals=True
 def record(self,dispatcher,*,record=None,point=None,error=None,kind='LOCAL_FINAL_FAILURE'):
  if global_reason(dispatcher.ledger):
   dispatcher.faulted=True
   self.original_driver_fault(record['job']['trajectory']if record else 'GLOBAL')
   if error is not None:raise error
   return
  job=record['job']if record else None
  key=job['point']if job else next((k for k,v in dispatcher.points.items()if v is point),None)
  t=job['trajectory']if job else next((r['job']['trajectory']for r in dispatcher.children.values()if r['job']['point']==key),'AUX_CONTROL')
  if record is not None:record['isolated_fault']=True
  if point is not None:point['isolated_fault']=True
  self.points[key]={'kind':kind,'exception_type':type(error).__name__ if error else None}
  _event(dispatcher.ledger,t,'FINAL_POINT_LOCAL_FAULT_RETAINED',{'point_id':key,**self.points[key],
   'global_admission_sealed':False,'original_handles_claims_retained':True,'automatic_retry':False})

def _poll_replacement(original,isolation):
 """Keep the original protocol/audit code; isolate each row and each point."""
 source_file=Path(inspect.getsourcefile(original))
 need(source_file.name=='native_final_dispatch.py'and hash_file(source_file)['sha256']=='fadb72e2ced6228133066390c51d60f5fa168b7e09b0c42ce44733beff27e45d','ISOLATION_EXACT_PUBLIC_FINAL_POLL_SOURCE')
 tree=ast.parse(textwrap.dedent(inspect.getsource(original)));fn=tree.body[0]
 need(fn.name=='_poll','ISOLATION_ORIGINAL_FINAL_POLL')
 outer=fn.body[0];need(isinstance(outer,ast.With),'ISOLATION_FINAL_LOCK_BOUNDARY')
 loops=[n for n in outer.body if isinstance(n,ast.For)]
 need(len(loops)==2 and ast.unparse(loops[0].target)=='(key, record)'and ast.unparse(loops[1].target)=='point',
      'ISOLATION_TWO_EXACT_FINAL_POLL_LOOPS')
 for loop,name in zip(loops,('record','point')):
  skip=ast.parse(f"if {name}.get('isolated_fault'): continue").body[0]
  handler=ast.ExceptHandler(type=ast.Name('BaseException',ast.Load()),name='error',body=ast.parse(
   f"_isolation.record(self,{name}={name},error=error)").body)
  loop.body=[skip,ast.Try(body=loop.body,handlers=[handler],orelse=[],finalbody=[])]
 ns=dict(original.__globals__);ns['_isolation']=isolation
 exec(compile(ast.fix_missing_locations(tree),'<trajectory-isolated-original-final-poll>','exec'),ns)
 return ns[fn.name]

def install(driver):
 need(not hasattr(driver,'_isolation'),'ISOLATION_INSTALL_ONCE')
 i=Isolation(driver);driver._isolation=i;driver._fault=MethodType(_local_driver_fault,driver)
 dispatcher=driver.dispatcher;original_dispatch=dispatcher.dispatch_one;original_poll=dispatcher.poll
 original_inner=dispatcher._poll
 fixed=_poll_replacement(original_inner,i)
 dispatcher._poll=MethodType(fixed,dispatcher)
 def fault(_,t,kind):
  records=[r for r in dispatcher.children.values()if r['job']['trajectory']==t]
  i.record(dispatcher,record=records[-1]if records else None,kind=kind)
 dispatcher._fault=MethodType(fault,dispatcher)
 def poll(_):
  if i.defer_finals:return dispatcher.status()
  return original_poll()
 def dispatch(_):
  if i.defer_finals:return None
  try:return original_dispatch()
  except BaseException as e:
   if global_reason(driver.ledger):raise
   # original_dispatch has already retained the claim and called local _fault.
   return None
 dispatcher.poll=MethodType(poll,dispatcher);dispatcher.dispatch_one=MethodType(dispatch,dispatcher)
 # Tick's launch_one exception must not kill the global poller after local fault.
 original_launch=driver.launch_one
 def launch(_,t):
  try:return original_launch(t)
  except BaseException:
   if driver.failed or global_reason(driver.ledger):raise
   need(t in i.trajectories,'ISOLATION_LAUNCH_FAILURE_MUST_BE_RECORDED')
   return None
 driver.launch_one=MethodType(launch,driver)
 _event(driver.ledger,'GLOBAL','TRAJECTORY_ISOLATION_INSTALLED',{'global_faults':'RELAY_OR_BILLING_ONLY',
  'existing_driver_fault_not_cleared':True,'final_dispatch_deferred_until_search_restored':True,
  'canary_tick_unchanged':True,'requests_replayed':0})
 return i

def release_final_dispatch(driver):
 need(global_reason(driver.ledger)is None,'ISOLATION_NO_GLOBAL_INCIDENT_RELEASE')
 driver.dispatcher.faulted=False
 driver._isolation.defer_finals=False
 _event(driver.ledger,'GLOBAL','FINAL_DISPATCH_AFTER_SEARCH_RECOVERY',{'search_first':True})
