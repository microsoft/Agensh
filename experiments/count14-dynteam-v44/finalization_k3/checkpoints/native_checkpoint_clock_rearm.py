"""Original current clock/counters -> authenticated checkpoint watchdog rearm.

New cold source only. Never called on an already-running old owner as repair.
Does not restore/reset/estimate an active-clock SOURCE or financial pause total.
Native readers consume the existing schema, ONLY after the original writer cut
and all native domains are proven frozen, immediately before original thaw.
"""
from pathlib import Path
import json,os,stat
from common import need,digest
from native_budget_park import NativeBudgetParkProjection
from native_writer_fence import NativeWriterFence
from r16_checkpoint_clock_rearm import SCHEMA,_atomic_public
from r16_resume_budget_clocks import _public

def rearm_before_native_thaw(writer,*,final_retirement):
 from native_dynamic_writer import DynamicCutWriter
 from native_dynamic_checkpoint import DynamicCheckpointPorts
 from original_relay_core import OriginalRelayCore
 from types import MethodType
 need(type(writer.core)is OriginalRelayCore and type(final_retirement)is bool,
      'DYNTEAM_CLOCK_REARM_ORIGINAL_TYPED_DYNAMIC_WRITER')
 core=writer.core;ledger=writer.ledger;t=writer.t;fence=writer.writer_fence
 port=core.smoke_checkpoint_ports[t];begin=port._begin_cut
 need(type(port)is DynamicCheckpointPorts and port.core is core and port.t==t and
      type(begin)is MethodType and begin.__self__ is port and
      begin.__func__.__code__ is DynamicCheckpointPorts._begin_cut.__code__,
      'DYNTEAM_CLOCK_REARM_ORIGINAL_CHECKPOINT_CONSTRUCTOR_CODETYPE')
 selected=begin.__func__.__globals__['DynamicCutWriter']
 # Exact same cold-selected class consumed by the ORIGINAL constructor. The
 # approved MM/control bind compiler creates a private writer class; insisting
 # on the old global class would reject that genuine source-proven inventory.
 # No caller-supplied type flag, fallback facade or live class patch is used.
 need(type(selected)is type and type(writer)is selected and
      selected.__name__==DynamicCutWriter.__name__ and
      selected.__module__==DynamicCutWriter.__module__,
      'DYNTEAM_CLOCK_REARM_EXACT_COLD_SELECTED_ORIGINAL_WRITER_CLASS')
 need(not ledger.mutex._is_owned(),'DYNTEAM_CLOCK_REARM_NO_FILESYSTEM_IO_UNDER_SCIENCE_LOCK')
 need(type(fence)is NativeWriterFence and fence.owner is writer and fence.ledger is ledger and
      fence.t==t and fence.state=='PARKED'and fence.whole_team is writer.whole_team and
      core.ledger is ledger and core.smoke_checkpoint_ports[t].writer is writer,
      'DYNTEAM_CLOCK_REARM_SAME_ORIGINAL_NATIVE_FROZEN_CUT')
 projection=core.clocks[t]
 need(type(projection)is NativeBudgetParkProjection and projection.gate is core.gate and
      projection.ledger is ledger and projection.t==t and
      set(projection.roles)==set(core.rows[t]['roles']),
      'DYNTEAM_CLOCK_REARM_SAME_ORIGINAL_PUBLISHER_ROSTER_COUNTERS')
 fence._coverage()
 need(all(d.frozen()and d.read('cgroup.freeze').strip()=='1'for d in fence.domains),
      'DYNTEAM_CLOCK_REARM_ALL_NATIVE_DOMAINS_STILL_FROZEN')
 fence.verify_capture(writer.cut,writer.role_sources)
 snapshot=core.cas.verify_snapshot(writer.reference)
 need(snapshot['trajectory']==t and snapshot['generation']==writer.generation and
      snapshot['pins']['native_writer_fence']==fence.receipt['sha256'],
      'DYNTEAM_CLOCK_REARM_ORIGINAL_SEALED_SNAPSHOT_FENCE')
 with ledger.mutex:
  frontier=ledger.frontier(t);account=ledger.account(t)
  committed=ledger.db.execute('SELECT ref_sha FROM snapshots WHERE trajectory=?AND generation=?',(t,writer.generation)).fetchone()
  need(committed is not None and committed[0]==writer.reference['sha256'],
       'DYNTEAM_CLOCK_REARM_EXACT_ORIGINAL_COMMITTED_REFERENCE')
  if final_retirement:
   need(core.gate.closed and frontier['state']=='COMMITTED_PARKED'and
        frontier['generation']==writer.generation and
        account['stage']+1==len(json.loads(account['targets']))and
        frontier['unresolved']==frontier['reserved']==frontier['active_operations']==0,
        'DYNTEAM_CLOCK_REARM_FINAL_MODELS_CLOSED_NO_SUCCESSOR')
  else:
   need(not core.gate.closed and frontier['state']=='RUNNING'and
        frontier['generation']==writer.generation+1,
        'DYNTEAM_CLOCK_REARM_ORIGINAL_RESUMED_NATIVE_SUCCESSOR')
  generation=frontier['generation']
 kind='DYNTEAM_NATIVE_FINAL_RETIREMENT_CLOCK_REARM_AUTHORIZED'if final_retirement else'DYNTEAM_NATIVE_CHECKPOINT_CLOCK_REARM_AUTHORIZED'
 with projection.lock:
  projection._current();projection.sample();sequence=projection.sequence
  values={r:dict(schema=SCHEMA,binding_sha256=digest(projection.bindings[r]),sequence=sequence,generation=generation)for r in projection.roles}
  for role,value in values.items():
   path=projection.directory/(role+'.json.rearm')
   if path.exists()or path.is_symlink():
    info=path.lstat();need(stat.S_ISREG(info.st_mode)and info.st_uid==os.geteuid()and
        info.st_nlink==1 and stat.S_IMODE(info.st_mode)==0o444,
        'DYNTEAM_CLOCK_REARM_PREVIOUS_LEAF_IDENTITY')
    previous=_public(path)
    need(set(previous)==set(value)and previous['schema']==SCHEMA and
         previous['binding_sha256']==value['binding_sha256']and
         type(previous['sequence'])is int and previous['sequence']<sequence and
         type(previous['generation'])is int and 0<previous['generation']<=generation and
         (final_retirement or previous['generation']<generation),
         'DYNTEAM_CLOCK_REARM_MONOTONIC_AUTHORIZATION_NOT_COUNTER_RESET')
  # Each original writer has exactly one successor thaw OR final retirement.
  # Preserve intent on failure; no retry or reuse of a partially issued marker.
  need(not getattr(writer,'_native_clock_thaw_rearm_started',False),
       'DYNTEAM_CLOCK_REARM_ONCE_PER_ORIGINAL_CUT_NO_RETRY')
  writer._native_clock_thaw_rearm_started=True
  for role,value in values.items():_atomic_public(projection.directory/(role+'.json.rearm'),value)
  with ledger.tx():
   ledger.event(t,kind,dict(generation=generation,authorization_sequence=sequence,
       minimum_fresh_status_sequence=projection.sequence+1,roles=len(values),
       cut_sha256=writer.cut.cut_sha,snapshot_sha256=writer.reference['sha256'],
       binding_roster_sha256=digest({r:v['binding_sha256']for r,v in values.items()}),
       all_native_domains_frozen_before_original_thaw=True,
       final_model_admission_reopened=False if final_retirement else None,
       active_clock_SOURCE_or_budget_pause_counter_reset=False,
       wire_lease_ns_unchanged=10_000_000_000,requests_or_sessions_modified=False))
  # No durable commit or fabricated clock is placed after this final genuine
  # sample and before original caller's native thaw.
  projection.sample()
 return dict(generation=generation,sequence=sequence,roles=len(values),final_retirement=final_retirement)
