"""Cold-rebuild the SAME public budget-clock binding/directory, not a new CLI.

Creator identity in frozen bindings is preserved. The new host custodian is
recorded honestly; old sequence and pause totals cannot go backwards. No thaw,
lease nonce, budget/generation transition, session read or request replay here.
"""
from pathlib import Path
from types import MethodType
import copy,json,os,stat,threading,time
from common import need,digest
from bridge import process_identity
from admission_gate import AdmissionGate
from native_budget_park import NativeBudgetParkProjection,SCHEMA,BINDING,VALID_FOR_NS
from r16_resume_budget_clocks import _public
from r16_cohort_clock_publisher_v4 import sample_cohort_atomic
from r16_checkpoint_clock_rearm import SCHEMA as REARM

def restore(gate,t,directory,*,bindings,ready_pins,exclusive_owner,old_publishers_ended):
 need(type(gate)is AdmissionGate,'DISK_CLOCK_ORIGINAL_NATIVE_GATE_TYPE')
 need(exclusive_owner()is True and old_publishers_ended()is True,'DISK_CLOCK_EXCLUSIVE_SUCCESSOR_OLD_PUBLISHERS_ENDED')
 directory=Path(directory);s=directory.lstat()
 need(directory.resolve()==directory and stat.S_ISDIR(s.st_mode)and s.st_uid==os.geteuid()
      and not s.st_mode&0o022,'DISK_CLOCK_ORIGINAL_TRUSTED_DIRECTORY')
 ledger=gate.ledger;f=ledger.frontier(t);roles=list(f['roles'])
 need(f['state']=='COMMITTED_PARKED'and f['target']==50_000_000 and
      f['unresolved']==f['reserved']==f['active_operations']==0,'DISK_CLOCK_ORIGINAL_50M_DRAINED_PARK')
 need(set(bindings)==set(ready_pins)==set(roles),'DISK_CLOCK_ORIGINAL_FULL_ROLE_ROSTER')
 new_owner=process_identity(os.getpid());sequence=0;totals={};creators=set()
 # Validate EVERY original readonly leaf before touching the in-memory gate.
 for role in roles:
  b=bindings[role]
  need(type(b)is dict and set(b)=={'schema','trajectory','role','manifest_sha256','owner'}and
   b['schema']==BINDING and b['trajectory']==t and b['role']==role and b['manifest_sha256']==f['manifest_sha256'],
   'DISK_CLOCK_EXACT_ORIGINAL_CREATOR_BINDING')
  need(type(b['owner'])is dict and set(b['owner'])=={'pid','start_ticks','boot_id'}and
       b['owner']!=new_owner,'DISK_CLOCK_NEW_CUSTODIAN_NOT_OLD_CREATOR')
  pin=digest(b);need(ready_pins[role]==pin,'DISK_CLOCK_ORIGINAL_CLOCK_READY_PIN')
  creators.add(digest(b['owner']));v=_public(directory/(role+'.json'))
  need(v['schema']==SCHEMA and v['binding_sha256']==pin and type(v['sequence'])is int and v['sequence']>0
       and type(v['generation'])is int and 0<v['generation']<=f['generation']
       and v['valid_for_ns']==str(VALID_FOR_NS),'DISK_CLOCK_ORIGINAL_LEAF_IDENTITY_AND_WIRE10S')
  total=v['total_paused_ns'];need(type(total)is str and total.isdigit(),'DISK_CLOCK_PRIOR_PAUSE_TOTAL')
  totals[role]=int(total);sequence=max(sequence,v['sequence'])
  nonce=directory/(role+'.json.rearm')
  if nonce.exists()or nonce.is_symlink():
   n=_public(nonce)
   need(set(n)=={'schema','binding_sha256','sequence','generation'}and n['schema']==REARM and n['binding_sha256']==pin
        and type(n['sequence'])is int and n['sequence']>0 and type(n['generation'])is int
        and 0<n['generation']<=f['generation'],'DISK_CLOCK_PRIOR_REARM_PIN')
   sequence=max(sequence,n['sequence'])
 need(len(creators)==1,'DISK_CLOCK_ONE_ORIGINAL_PUBLISHER_IDENTITY')
 with gate.condition:
  need(not gate.waiters and not gate.closed,'DISK_CLOCK_NO_OLD_UNADMITTED_FRAME_TRANSFER')
  for role in roles:
   old=gate._budget_pause.get((t,role))
   need(old is None or old=={'total_ns':totals[role],'since_ns':None},'DISK_CLOCK_NO_LIVE_COUNTER_RESET')
  for role in roles:gate._budget_pause[(t,role)]={'total_ns':totals[role],'since_ns':None}
 p=NativeBudgetParkProjection.__new__(NativeBudgetParkProjection)
 p.gate=gate;p.ledger=ledger;p.t=t;p.directory=directory;p.roles=roles;p.owner=new_owner
 p.bindings=copy.deepcopy(bindings);p.directory_identity=(s.st_dev,s.st_ino)
 p.stop_event=threading.Event();p.thread=None;p.sequence=sequence;p.closed=False;p.lock=threading.RLock()
 p.sample=MethodType(sample_cohort_atomic,p)
 p._current();need(exclusive_owner()is True and old_publishers_ended()is True,'DISK_CLOCK_FRONTIER_CHANGED_DURING_RESTORE')
 with ledger.tx():ledger.event(t,'USER100M_CLOCK_DISK_CUSTODY_ADOPTED',{
  'new_owner':new_owner,'original_binding_roster_sha256':digest(bindings),'previous_sequence':sequence,
  'pause_totals_preserved':True,'wire_lease_ns':10_000_000_000,'reader_lease_ns':120_000_000_000,
  'original_creator_binding_unchanged':True,'cgroups_thawed':False,'requests_replayed':0,
  'new_python_projection_object':True,'old_live_object_not_claimed':True})
 return p

def start_supervised(p,record):
 """A per-trajectory publisher survives its own transient write failures.

 Does NOT clear scientific faults or issue lease-only rearm. Those remain the
 explicit same-binding host release path's responsibility after native advance.
 Logging is a metadata-only callback, outside gate locks; failed logging cannot
 kill publisher or peers. No global owner failure is raised from this loop.
 """
 need(type(p)is NativeBudgetParkProjection and p.thread is None and not p.closed
      and not p.stop_event.is_set(),'DISK_CLOCK_ONE_COLD_PUBLISHER')
 def notify(kind,data):
  try:record(kind,data)
  except BaseException:pass
 def run():
  failed=False
  while not p.stop_event.wait(.5):
   try:
    p.sample()
    if failed:notify('CLOCK_REFRESH_RECOVERED',{'trajectory':p.t,'sequence':p.sequence,'lease_nonce_issued':False})
    failed=False
   except BaseException as e:
    notify('CLOCK_REFRESH_LOCAL_WARNING',{'trajectory':p.t,'exception_type':type(e).__name__,
           'messages_locals_omitted':True,'global_fault':False});failed=True
 p.thread=threading.Thread(target=run,name='exp100-clock-'+digest(p.t)[:12],daemon=True);p.thread.start();return p.thread
