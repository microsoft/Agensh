"""Latest authorized SEARCH rejection/UNKNOWN policy; AUX remains point-local.

No retrospective row/account edit or UNKNOWN release. Window checks use public
request event metadata. All blocking model/RPC/controller work is outside locks.
"""
from types import MethodType
import time
from common import need,digest,strict

def search_window(ledgers,now_ns):
 lower=now_ns-600*10**9;sent=set();bad=set()
 for l in ledgers:
  with l.mutex:
   for r in l.db.execute("SELECT kind,metadata FROM events WHERE at_ns>=?AND kind IN('SENT','UNKNOWN_EXECUTION')",(lower,)):
    m=strict(r[1]);key=(id(l),m['request_id'])
    if r[0]=='SENT':sent.add(key)
    else:
     rejected=l.db.execute('SELECT 1 FROM upstream_rejections WHERE request_id=?',(m['request_id'],)).fetchone()
     if rejected is None:bad.add(key)
 return {'window_seconds':600,'sent_SEARCH_requests':len(sent),'unknown_SEARCH_requests':len(bad&sent),
  'stop':bool(sent)and len(bad&sent)*5>len(sent),'AUX_in_SEARCH_threshold':False}

def financial_state(ledgers,started_ns):
 from a4_final_fault_gate import FINANCIAL_PREFIXES
 for l in ledgers:
  with l.mutex:
   if l.db.execute("SELECT 1 FROM accounts WHERE state='FAULT' LIMIT 1").fetchone():return {'proof':'ACCOUNT_BUDGET_FAULT'}
   for trajectory,code in l.memory_faults.items():
    if trajectory=='GLOBAL'or code.startswith(FINANCIAL_PREFIXES):return {'proof':'RELAY_OR_BILLING_LATCH','trajectory':trajectory,'code':code}
   for raw, in l.db.execute("SELECT metadata FROM events WHERE kind='UNKNOWN_EXECUTION'AND at_ns>=?",(started_ns,)):
    m=strict(raw);code=m.get('code','')
    prefix='UPSTREAM_HTTP_'
    if code.startswith(prefix)and code[len(prefix):].isdigit():
     status=int(code[len(prefix):])
     if 400<=status<500 and status!=429:return {'proof':'UNAUTHORIZED_UPSTREAM_4XX','http_status':status,'request_id':m['request_id']}
 return None

def install(c):
 from rejection_ledger import Projection,final_projection,REPEAT
 from rejection_transport import Monitor
 need(not hasattr(c,'_user100_rejection_projection'),'DISK_SEARCH_POLICY_INSTALL_ONCE')
 ledgers=tuple(d.ledger for d in c.ds.values())
 p=Projection();p.install(ledgers,c.peer);final_projection(p)
 c._user100_rejection_projection=p;c._user100_retry_monitor=Monitor(ledgers)
 # Instance only. Peer closures already hold the original same mutex. They
 # continue reading the append-only effective stops and physical reservations.
 def thresholds(l,t):
  if not l.unknown_policy_enabled():return
  stats=l.unknown_statistics(t);window=search_window(ledgers,time.time_ns());stops=[]
  if stats['trajectory_consecutive_unknown']>=3:stops.append((t,'UNKNOWN_CONSECUTIVE_3_STOP'))
  if window['stop']:stops.append(('GLOBAL','UNKNOWN_GLOBAL_RECENT10M_RATIO_GT20_STOP'))
  for scope,code in stops:
   if l.db.execute('SELECT 1 FROM upstream_effective_unknown_stops WHERE scope=?',(scope,)).fetchone():continue
   seq=l.event(scope,'UNKNOWN_POLICY_STOP',{'code':code,**stats,**window})
   table=REPEAT if l.db.execute('SELECT 1 FROM unknown_stops WHERE scope=?',(scope,)).fetchone()else'unknown_stops'
   l.db.execute('INSERT INTO '+table+' VALUES(?,?,?)',(scope,code,seq))
 for l in ledgers:l._unknown_thresholds=MethodType(thresholds,l)
 # Old .tick's rolling ratio was AUX-only but fed the global SEARCH hold. Keep
 # AUX dispatch held for its own ratio without poisoning main/branch SEARCH.
 original_status=c.status
 def status(_):
  value=original_status();value.update(schema='agensh-v2-user100m-search-custodian-status-v1',
   SEARCH_started=sum(bool(r.get('release_started'))for r in _.user100_search.records.values())if hasattr(_,'user100_search')else 0,
   SEARCH_objects_prepared=sum(r.get('controller')is not None for r in _.user100_search.records.values())if hasattr(_,'user100_search')else 0,
   SEARCH_cold_reconstructed=True,AUX_threshold_hold=getattr(_,'user100_aux_hold',False))
  if hasattr(_,'user100_search'):value['SEARCH_tracks']=_.user100_search.status()
  return value
 def tick(_):
  from disk_capacity import global_recent_unknown_ratio
  h,memory=_.resource_health()
  money=financial_state(ledgers,_.started_ns)
  if money is not None:
   if not _.financial_stop:_.record('USER100M_RELAY_OR_BILLING_STOP',money)
   _.financial_stop=True
  search=search_window(ledgers,time.time_ns());retry=_._user100_retry_monitor.ratio()
  aux=global_recent_unknown_ratio(_.ds.values(),started_ns=_.started_ns,now_ns=time.time_ns())
  if search['stop']or retry['stop']:_.upstream_stop=True
  _.user100_aux_hold=bool(aux['stop'])
  _.hold=_.operator_hold or _.financial_stop or _.upstream_stop or bool(h['health_failed'])
  for name,d in _.ds.items():
   try:
    for event in d.poll()['local_holds']:_.record('POINT_POLL_WARNING',{'domain':name,**event,'messages_locals_omitted':True,'global_fault':False})
   except BaseException as e:_.local_error(name,'DISPATCHER_POLL',e)
  if _.hold or memory<64*2**30 or _.peer.physical()>_.peer.global_cap:return
  evidence={'current_owner_authorized':True,'gateway_health_sha256':h['receipt_sha256']or digest(h),
   'allocation_sha256':digest({'free':memory,'physical':_.peer.physical(),'cap':_.peer.global_cap,'final_cap':_.slots.cap})}
  for d in _.ds.values():
   if d.ledger.db.execute('SELECT paused FROM model_control WHERE singleton=1').fetchone()[0]:d.capacity.release(owner_evidence=evidence)
  if _.user100_aux_hold:return
  for name,d in _.ds.items():
   try:d.dispatch_one()
   except BaseException as e:_.local_error(name,'NEW_FINAL_DISPATCH',e)
 c.tick=MethodType(tick,c);c.status=MethodType(status,c)
 return {'SEARCH_unknown_same_track_stop':3,'SEARCH_recent_window_seconds':600,'SEARCH_unknown_ratio_stop_percent':20,
  'AUX_threshold_blocks_SEARCH':False,'original_rows_rewritten':0,'physical_UNKNOWN_slots_released':0}
