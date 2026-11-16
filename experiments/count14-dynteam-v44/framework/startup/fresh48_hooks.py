"""Fresh 4/8-only native launch hooks. No new scientific controller/CLI loop.

Install BEFORE first launch in the new owner. First-start publication, SDK/CLI,
whole-team inventory/freeze/backup, model bytes, candidate rule and FINAL remain
native. New policy only: 100M targets; one nonblocking16M source; latest clocks,
header/rejections and per-track failure isolation. Not a complete launcher alone.
"""
import os as _count14_os  # endpoints/keys come from environment; see CONFIGURATION.md
from pathlib import Path
from types import MethodType
import copy,hashlib,inspect,json
from common import need,digest,wire,publish
from expansion100_contract import check,group,append_new_targets
from fresh48_session import CliSessions,before_admission


def diagnostic_targets(ledger,manifest,t):
 policy=check(manifest)
 need(group(manifest)=='new-4-8'and t in policy['trajectories'],'FRESH48_DIAGNOSTIC_SCOPE')
 # Native controller constructor has ALREADY verified original10/20 startup
 # identity. Nothing scientific is released; no request may have been accepted.
 with ledger.tx():
  a=ledger.account(t);old=json.loads(a['targets'])
  need(a['generation']==1 and a['stage']==0 and a['actual']==0 and a['state']=='RUNNING'
       and not ledger.db.execute('SELECT 1 FROM requests WHERE trajectory=?',(t,)).fetchone(),
       'FRESH48_DIAGNOSTIC_BEFORE_FIRST_MODEL')
  need(old==[10_000_000,20_000_000],'FRESH48_ORIGINAL_CONSTRUCTOR_TARGETS')
  ledger.db.execute('UPDATE accounts SET targets=? WHERE trajectory=?',('[10000000,16000000,20000000]',t))
  ledger.event(t,'USER100M_NEW48_DIAGNOSTIC16M_SNAPSHOT_REGISTERED',{
    'authorization_sha256':digest(policy),'target_tokens':16_000_000,'K':0,
    'mainline_must_continue_without_branch_wait':True,'branch_budget_separate':4_000_000})
 return append_new_targets(ledger,manifest,t)


def bind_diagnostic(owner):
 """Keep the ORIGINAL step/release path: no handoff park, no branch wait."""
 from aggregate_source import save,read,NAME
 need(not hasattr(owner,'_fresh48_diagnostic'),'FRESH48_DIAGNOSTIC_BIND_ONCE')
 oldstep,oldpoint=owner.step,owner._point
 def step(_):
  with _.lock:
   if _.state=='COMMITTED'and _.cut is not None and _.cut.cut['target_tokens']==16_000_000:
    save(_) # Atomic immutable source; mainline never depends on branch readiness.
  return oldstep()
 def point(_):
  if _.ledger.frontier(_.t)['target']!=16_000_000:return oldpoint()
  source=read(_.cas,_.root/NAME,parent=_.t,manifest_sha=_.pins['manifest'])
  f=_.ledger.frontier(_.t)
  need(f['state']=='COMMITTED_PARKED'and source['snapshot']==_.ref,'FRESH48_EXACT_SEALED_DIAGNOSTIC_SOURCE')
  value={'generation':f['generation'],'target_tokens':16_000_000,'actual_search_tokens':f['actual'],
    'point_kind':'AGGREGATE_FORK_SOURCE_DIAGNOSTIC','snapshot':copy.deepcopy(_.ref),
    'source_sha256':digest(source),'K':0,'jobs':[],'automatic_next_stage':True,
    'mainline_waits_for_branch':False,'branch_budget_separate':True}
  home=_.root/'point-16000000-diagnostic';home.mkdir(mode=0o700)
  publish(home/'POINT_SNAPSHOTTED.json',wire(value),mode=0o400);_.points.append(value)
  _._event('USER100M_NEW48_DIAGNOSTIC16M_SNAPSHOT_SAVED_CONTINUE',value)
  return value
 owner.step=MethodType(step,owner);owner._point=MethodType(point,owner);owner._fresh48_diagnostic=True


def isolate_driver(driver,record):
 need(not hasattr(driver,'_fresh48_local_faults'),'FRESH48_LOCAL_FAULT_INSTALL_ONCE')
 driver._fresh48_local_faults={}
 def fault(_,t):
  need(t in _.records,'FRESH48_LOCAL_FAULT_REGISTERED_TRACK')
  if t not in _._fresh48_local_faults:
   _._fresh48_local_faults[t]='SCIENTIFIC6_TRAJECTORY_FAILURE_RETAINED'
   _.records[t]['phase']='TRAJECTORY_LOCAL_FAULT_RETAINED'
   _.ledger.latch_fault(t,'SCIENTIFIC6_TRAJECTORY_FAILURE_RETAINED')
   record('USER100M_NEW48_TRAJECTORY_LOCAL_FAULT',{'trajectory':t,'global_fault':False,
           'other_publishers_or_pollers_stopped':False,'requests_replayed':0})
  launch=_.records[t].get('launch')
  if launch is not None:launch.gate.notify()
 # driver.failed remains reserved for real relay/accounting stops in the outer
 # authority; no local controller/K3/source/attach path sets it.
 driver._fault=MethodType(fault,driver)
 return driver


def install(driver,manager,monitor,record):
 from native_scientific_launch import NativeScientificLaunch as L
 from native_writer_fence import NativeWriterFence
 from native_budget_park import NativeBudgetParkProjection
 from disk_clock import start_supervised,sample_cohort_atomic
 from r16_checkpoint_clock_rearm import request_release_with_checkpoint_rearm,ORIGINAL_RELEASE_SHA256
 from glm_session_header import install_search
 from rejection_transport import install as retry
 from aggregate_phase import Phase
 policy=check(driver.manifest)
 need(group(driver.manifest)=='new-4-8'and set(driver.rows)==set(policy['trajectories']),
      'FRESH48_NEW_EXACT_AUTHORIZED_SIX')
 need(driver.shared_started and not driver.records and manager.driver is driver and manager.peer.main is driver.ledger,
      'FRESH48_HOOK_BEFORE_FIRST_LAUNCH_WITH_ORIGINAL_SHARED_PEER')
 need(not hasattr(L,'_fresh48_hooks'),'FRESH48_NEW_OWNER_HOOKS_ONCE')
 key=Path(driver.upstream['token_file'])
 need(key==Path(driver.manifest['root'])/_count14_os.environ.get('COUNT14_GLM_KEY_RELPATH', 'config/glm-provider-key'),'FRESH48_NEW_PRIVATE_PROVIDER_KEY_PATH')
 raw=L.__dict__['prepare_transport'];original=raw.__func__;attach0=L.attach
 phasebind=Phase.bind
 def prepare(cls,**kw):
  need(kw['ledger']is driver.ledger and kw['manifest']==driver.manifest and kw['trajectory']in driver.rows,
       'FRESH48_SINGLE_NEW_ROOT_TRANSPORT')
  x=original(cls,**kw);manager.peer.bind_gate(x.gate)
  row=driver.rows[x.t];layout=Path(row['root'])
  sessions=CliSessions(x.t,{r:layout/'host-workers'/r/'home'for r in row['roles']},record)
  before_admission(x.relay,sessions)
  overlay=install_search(x.relay,sessions,key_path=key);retry(x.relay,overlay,monitor)
  x._fresh48_header=overlay;return x
 def attach(self,**kw):
  value=attach0(self,**kw)
  from fresh48_session_home import bind_runtime_homes
  bind_runtime_homes(self.relay._fresh48_session_guard,kw['roles'],Path(driver.rows[self.t]['root']),self.gate)
  need(self.ledger is driver.ledger and self.t in driver.rows,'FRESH48_ATTACHED_ORIGINAL_NEW_TEAM')
  diagnostic_targets(self.ledger,driver.manifest,self.t)
  ctrl=self.controller;ctrl.team._r16_budget_pause_projection=ctrl.projection;bind_diagnostic(ctrl)
  record('USER100M_NEW48_NATIVE_ATTACHED_BEFORE_RELEASE',{'trajectory':self.t,
    'regular_checkpoints':[10_000_000,20_000_000,50_000_000,100_000_000],
    'diagnostic16M':True,'no_branch_handoff_park':True,'SEARCH_released':False})
  return value
 def bind(self,transport):
  need(self.driver is driver and self.l is manager.l,'FRESH48_BRANCH_SAME_SEPARATE_LEDGER')
  value=phasebind(self,transport)
  # This is the original host-driven single aggregate agent, not a CLI.
  # Identity uses only its registered phase+sealed-source SHA metadata.
  sessions={(self.id,'worker-00'):'aggregate-phase:'+self.ref['sha256']}
  overlay=install_search(self.relay,sessions,key_path=key);retry(self.relay,overlay,monitor)
  self._fresh48_header=overlay;return value
 release=NativeWriterFence.request_release
 need(release is request_release_with_checkpoint_rearm or
      hashlib.sha256(inspect.getsource(release).encode()).hexdigest()==ORIGINAL_RELEASE_SHA256,
      'FRESH48_EXACT_NATIVE_REARM_RELEASE_SOURCE')
 NativeWriterFence.request_release=request_release_with_checkpoint_rearm
 NativeBudgetParkProjection.sample=sample_cohort_atomic
 NativeBudgetParkProjection.start=lambda p:start_supervised(p,record)
 L.prepare_transport=classmethod(prepare);L.attach=attach;L._fresh48_hooks=True;Phase.bind=bind
 isolate_driver(driver,record)
 driver._authorized_regular_job_count=72
 return {'schema':'agensh-v2-fresh48-native-launch-hooks-v1','models':0,
   'original_cli_and_scientific_loop':True,'local_fault_isolation':True,'wire_lease_seconds':10,
   'reader_lease_seconds':120,'requires_qualified_reader_mount':True,'same_session_affinity':True,
   'diagnostic16M_mainline_wait_for_branch':False}
