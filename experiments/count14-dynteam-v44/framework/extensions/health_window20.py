"""Three consecutive completed probe failures within the last 20 minutes only.

A pending probe, stale/missing/unreadable data or one failure is WARNING only.
No network calls, retries, source rewriting, weakened accounting or 5xx gate.
"""
from pathlib import Path
from types import MethodType
from datetime import datetime
import math,time
from common import need,strict,ident,digest
WINDOW_SECONDS=1200
WINDOW=WINDOW_SECONDS*10**9
PROBE_PERIOD_SECONDS=300
HEALTH='UPSTREAM_HEALTH_PROBE_FAILED_STOP'
def external_status(path,*,now_ns=None):
 now_ns=time.time_ns()if now_ns is None else now_ns
 try:
  raw=Path(path).read_bytes();need(len(raw)<=4*1024*1024,'HEALTH_V1_PUBLIC_EVENTS_BOUND')
  intents={};results={}
  for line in raw.splitlines():
   if not line:continue
   e=strict(line);need(type(e)is dict,'HEALTH_V1_EVENT_OBJECT')
   need(e.get('schema')=='agensh-glm-outage-system-health-v1'and e.get('model')=='VLLM-GATEWAY-GLM-5.3-FP8','HEALTH_V1_MODEL')
   need(e.get('included_in_search_budget')is False and e.get('included_in_AUX')is False and e.get('request_retries')==0,'HEALTH_V1_SYSTEM_ONLY')
   rid=ident(e['request_id']);kind=e['kind']
   if kind=='HEALTH_PROBE_INTENT':need(rid not in intents,'HEALTH_V1_DISTINCT_INTENT');intents[rid]=e
   elif kind=='HEALTH_PROBE_RESULT':
    need(rid not in results and e.get('response_body_saved')is False,'HEALTH_V1_DISTINCT_RESULT_NO_BODY');results[rid]=e
   else:need(False,'HEALTH_V1_FIXED_EVENTS')
  need(set(results)<=set(intents),'HEALTH_V1_ORIGINAL_INTENTS')
  rows=[];pending=0
  for rid,intent in intents.items():
   if rid not in results:pending+=1;continue
   r=results[rid];need(r['sequence']==intent['sequence']and r['max_output_tokens']==8,'HEALTH_V1_ORIGINAL_SEQUENCE')
   def ns(v):
    dt=datetime.fromisoformat(v);need(dt.tzinfo is not None,'HEALTH_V1_UTC');return int(dt.timestamp()*10**9)
   start,end=ns(r['started_at']),ns(r['completed_at']);elapsed=r['elapsed_seconds'];status=r['http_status']
   need(type(elapsed)in(int,float)and math.isfinite(elapsed)and elapsed>=0 and 0<=start<=end<=now_ns,'HEALTH_V1_VALID_TERMINAL_TIME')
   need(status is None or type(status)is int and 100<=status<=599,'HEALTH_V1_STATUS')
   # The original stream=false monitor and pre-response HTTP/IO failures do
   # not emit done. Both original monitors do emit an explicit healthy bool.
   need(type(r.get('healthy'))is bool,'HEALTH_V2_ORIGINAL_MONITOR_HEALTH_FLAG')
   need('done'not in r or type(r['done'])is bool,'HEALTH_V2_OPTIONAL_STREAM_DONE_FLAG')
   rows.append({'id':rid,'started_at_ns':start,'finished_at_ns':end,
     'success':r['healthy']is True and status==200 and elapsed<=60 and end-start<=60*10**9})
  last=rows[-3:];fresh=bool(last)and now_ns-last[-1]['finished_at_ns']<=WINDOW
  failed=len(last)==3 and all(not r['success']and 0<=now_ns-r['finished_at_ns']<=WINDOW for r in last)
  healthy=bool(last)and fresh and last[-1]['success']
  reason='THREE_COMPLETED_FAILURES_WITHIN_1200S'if failed else ('HEALTHY_COMPLETED_PROBE'if healthy else('NO_COMPLETED_PROBES'if not last else('STALE_PUBLIC_PROBES'if not fresh else'SUBTHRESHOLD_FAILURE_WARNING')))
  return {'normal':not failed,'health_failed':failed,'warning':not failed and (not healthy or pending>0),
    'reason':reason,'pending_probe_count':pending,'probe_ids':[r['id']for r in last],
    'last_finished_at_ns':last[-1]['finished_at_ns']if last else None,'receipt_sha256':digest({'source_sha256':__import__('hashlib').sha256(raw).hexdigest(),'completed':last,'pending_count':pending}),
    'window_seconds':WINDOW_SECONDS,'completed_failure_threshold':3}
 except (OSError,ValueError,TypeError,KeyError,IndexError,OverflowError,__import__('common').Refused):
  return {'normal':True,'health_failed':False,'warning':True,'reason':'PUBLIC_HEALTH_UNAVAILABLE_WARNING',
    'pending_probe_count':None,'probe_ids':[],'last_finished_at_ns':None,'receipt_sha256':None,
    'window_seconds':WINDOW_SECONDS,'completed_failure_threshold':3}


def install(d):
 """Hot-swap classification and health event metadata, never release admission.

 The existing gate.status closure resolves health_failure.external_status on each
 call. Keep that closure and its probe path; preserve the original warning set.
 No lock, RPC, model request, fee adjustment or controller action is performed.
 """
 import health_failure
 from incident_policy import GLOBAL_RATIO,tx
 policy=d._a4_upstream_incidents_v1;gate=d._a4_aux_health_gate_v1
 need(getattr(d,'_a4_health_failure_policy_final_v1',False)and not hasattr(d,'_a4_health_window20_v4'),'HEALTH20_FINAL_POLICY_ONCE')
 need(policy.health is gate and gate.status.__func__.__globals__ is vars(health_failure),'HEALTH20_ORIGINAL_DYNAMIC_STATUS')
 need(policy.evaluate.__func__.__globals__ is vars(health_failure)and policy.evaluate.__func__.__name__=='evaluate','HEALTH20_ORIGINAL_EVALUATE')
 state=d._a4_health_failure_policy_v1
 need(type(state)is dict and type(state.get('warnings'))is set,'HEALTH20_KEEP_ORIGINAL_WARNING_STATE')
 old_parser=health_failure.external_status;old_evaluate=policy.evaluate;old_status=gate.status;old_snapshot=policy.snapshot
 def evaluate(self):
  health=self.health.status();stats=self.snapshot()
  if health.get('warning'):
   key=(health['reason'],tuple(health['probe_ids']))
   if key not in state['warnings']:
    with tx(self.ledgers[0]):self.ledgers[0].event('GLOBAL','HEALTH_WARNING_NOT_ADMISSION_STOP',{'reason':health['reason'],'probe_ids':health['probe_ids'],'seal':False,'temporary':False})
    state['warnings'].add(key)
  if health.get('health_failed'):self.global_stop(HEALTH,{'window_seconds':WINDOW_SECONDS,'completed_failures':3,'probe_ids':health['probe_ids']})
  elif stats['stop']:self.global_stop(GLOBAL_RATIO,stats)
  return stats
 # Dynamic replacement preserves the existing source path and gate status. The
 # evaluator changes only health-stop window metadata; snapshot/ratio stay native.
 health_failure.external_status=external_status
 policy.evaluate=MethodType(evaluate,policy)
 d._a4_health_window20_v4={'old_parser':old_parser,'new_parser':external_status,'old_evaluate':old_evaluate,'new_evaluate':policy.evaluate,'warning_state':state}
 need(gate.status is old_status and policy.snapshot==old_snapshot and d._a4_health_failure_policy_v1 is state,'HEALTH20_KEEP_GATE_SNAPSHOT_WARNINGS')
 return {'schema':'a4-health-window20-v4','probe_period_seconds':PROBE_PERIOD_SECONDS,
   'three_completed_failures_within_seconds':WINDOW_SECONDS,'health_stop_metadata_window_seconds':WINDOW_SECONDS,
   'same_warning_dedup_state':True,'same_native_ratio_snapshot':True,'same_5xx_ratio_and_trajectory_thresholds':True,
   'admission_release':False,'sessions_restarted':0,'models_dispatched':0,'fees_changed':False,'requests_replayed':0,
   'health_public_status':gate.status()}
