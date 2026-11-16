"""Append-only explicit HTTP rejection dispositions; all other custody unchanged.

Original request/UNKNOWN/charge/stop/event rows remain untouched. Mutable account
actual is the net budget projection of its retained charge plus explicit reversal.
Read-only views expose effective status/charges/stops to original ledger guards.
"""
import ast,copy,inspect,re,types
from common import need,digest,wire,strict
REJECT='upstream_rejections'
RESOLVE='upstream_stop_resolutions'
REPEAT='upstream_stop_retriggers'

def schema(l):
 with l.tx():
  l.db.execute(f'CREATE TABLE IF NOT EXISTS {REJECT}(request_id TEXT PRIMARY KEY REFERENCES requests(id),http_status INTEGER NOT NULL,reversed_tokens INTEGER NOT NULL,event_seq INTEGER NOT NULL UNIQUE REFERENCES events(seq),metadata TEXT NOT NULL)')
  l.db.execute(f'CREATE TABLE IF NOT EXISTS {RESOLVE}(event_seq INTEGER PRIMARY KEY REFERENCES events(seq),scope TEXT NOT NULL,receipt_seq INTEGER NOT NULL UNIQUE REFERENCES events(seq))')
  l.db.execute(f'CREATE TABLE IF NOT EXISTS {REPEAT}(scope TEXT NOT NULL,code TEXT NOT NULL,event_seq INTEGER PRIMARY KEY REFERENCES events(seq))')
  for t in (REJECT,RESOLVE,REPEAT):
   for action in ('UPDATE','DELETE'):l.db.execute(f"CREATE TRIGGER IF NOT EXISTS no_{action.lower()}_{t} BEFORE {action} ON {t} BEGIN SELECT RAISE(ABORT,'append only'); END")
  l.db.execute(f'''CREATE VIEW IF NOT EXISTS upstream_effective_requests AS SELECT id,trajectory,role,generation,CASE WHEN EXISTS(SELECT 1 FROM {REJECT} u WHERE u.request_id=requests.id) THEN 'UPSTREAM_REJECTED' ELSE state END AS state,upper_bound,proof_sha,input,output,receipt_sha FROM requests''')
  l.db.execute(f'CREATE VIEW IF NOT EXISTS upstream_effective_unknown_charges AS SELECT * FROM unknown_charges WHERE NOT EXISTS(SELECT 1 FROM {REJECT} u WHERE u.request_id=unknown_charges.request_id)')
  l.db.execute(f'CREATE VIEW IF NOT EXISTS upstream_effective_unknown_stops AS SELECT * FROM unknown_stops WHERE NOT EXISTS(SELECT 1 FROM {RESOLVE} u WHERE u.event_seq=unknown_stops.event_seq) UNION ALL SELECT * FROM {REPEAT} WHERE NOT EXISTS(SELECT 1 FROM {RESOLVE} u WHERE u.event_seq={REPEAT}.event_seq)')

def reject(l,rid,status,proof):
 need(status in (429,503)and type(proof)is dict,'EXPLICIT_UPSTREAM_REJECTION_REQUIRED')
 with l.tx():
  r=l.db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
  need(r is not None and r['state']in('SENT','UNKNOWN')and r['input']is None and r['output']is None and r['receipt_sha']is None,'REJECTION_ORIGINAL_UNACCOUNTED_SEND_ONLY')
  old=l.db.execute(f'SELECT metadata FROM {REJECT} WHERE request_id=?',(rid,)).fetchone()
  if old:
   m=strict(old[0].encode());need(m['http_status']==status and m['proof']==proof,'REJECTION_SAME_RECEIPT_REQUIRED');return m
  charge=l.db.execute('SELECT upper_bound,settlement_seq FROM unknown_charges WHERE request_id=?',(rid,)).fetchone()
  amount=0 if charge is None else charge['upper_bound']
  need(amount in(0,r['upper_bound']),'REJECTION_EXACT_ORIGINAL_UPPER')
  m={'schema':'agensh-explicit-upstream-rejection-v1','request_id':rid,'trajectory':r['trajectory'],'http_status':status,'effective_search_tokens':0,'reversed_tokens':amount,'original_state':r['state'],'original_charge_seq':None if charge is None else charge['settlement_seq'],'proof':proof,'usage_available':False,'original_rows_rewritten':False,'requests_replayed':0}
  seq=l.event(r['trajectory'],'UPSTREAM_REJECTED_'+str(status),m)
  l.db.execute(f'INSERT INTO {REJECT} VALUES(?,?,?,?,?)',(rid,status,amount,seq,wire(m).decode()))
  if amount:
   need(l.account(r['trajectory'])['actual']>=amount,'REJECTION_REVERSAL_NET_NONNEGATIVE')
   l.db.execute('UPDATE accounts SET actual=actual-? WHERE trajectory=?',(amount,r['trajectory']))
   l.event(r['trajectory'],'UPSTREAM_REJECTION_RESERVATION_REVERSAL',{'request_id':rid,'search_budget_delta':-amount,'rejection_seq':seq,'provider_usage':None})
  return m

def resolve(l,scope,*,cause_requests):
 with l.tx():
  row=l.db.execute('SELECT code,event_seq FROM upstream_effective_unknown_stops WHERE scope=?',(scope,)).fetchone()
  need(row is not None and row['code']=='UNKNOWN_CONSECUTIVE_3_STOP','REJECTION_EXACT_TRAJECTORY_STOP')
  tail=l.db.execute("SELECT metadata FROM events WHERE trajectory=? AND kind='UNKNOWN_EXECUTION'AND seq<=?ORDER BY seq DESC LIMIT 3",(scope,row['event_seq'])).fetchall()
  need(len(tail)==3 and {strict(r[0].encode())['request_id']for r in tail}==set(cause_requests),'REJECTION_STOP_EXACT_CAUSAL_THREE')
  need(all(l.db.execute(f'SELECT 1 FROM {REJECT} WHERE request_id=?AND http_status=429',(rid,)).fetchone()for rid in cause_requests),'REJECTION_STOP_ONLY_EXPLICIT429')
  seq=l.event(scope,'UPSTREAM_REJECTION_UNKNOWN_STOP_RESOLVED',{'original_stop_seq':row['event_seq'],'original_code':row['code'],'cause_requests':sorted(cause_requests),'original_stop_retained':True})
  l.db.execute(f'INSERT INTO {RESOLVE} VALUES(?,?,?)',(row['event_seq'],scope,seq));return seq

def thresholds(self,t):
 if not self.unknown_policy_enabled():return
 stats=self.unknown_statistics(t);stops=[]
 if stats['trajectory_consecutive_unknown']>=3:stops.append((t,'UNKNOWN_CONSECUTIVE_3_STOP'))
 if stats['sent_requests']>=200 and stats['unknown_requests']*100>stats['sent_requests']:stops.append(('GLOBAL','UNKNOWN_GLOBAL_RATIO_GT_1_PERCENT_STOP'))
 for scope,code in stops:
  if self.db.execute('SELECT 1 FROM upstream_effective_unknown_stops WHERE scope=?',(scope,)).fetchone():continue
  seq=self.event(scope,'UNKNOWN_POLICY_STOP',{'code':code,**stats})
  table=REPEAT if self.db.execute('SELECT 1 FROM unknown_stops WHERE scope=?',(scope,)).fetchone()else'unknown_stops'
  self.db.execute('INSERT INTO '+table+' VALUES(?,?,?)',(scope,code,seq))

def statistics(self,t):
 with self.mutex:
  total=self.db.execute("SELECT COUNT(*)FROM upstream_effective_requests WHERE state IN('SENT','SETTLED','UNKNOWN')").fetchone()[0]
  unknown=self.db.execute("SELECT COUNT(*)FROM upstream_effective_requests WHERE state='UNKNOWN'").fetchone()[0]
  # Explicit rejection is a non-UNKNOWN terminal for streak purposes, not a
  # fabricated SETTLED/model response. Historical raw events stay unchanged.
  rows=self.db.execute("SELECT kind,metadata FROM events WHERE trajectory=?AND kind IN('SETTLED','UNKNOWN_EXECUTION','UPSTREAM_REJECTED_429','UPSTREAM_REJECTED_503')ORDER BY seq DESC",(t,))
  streak=0
  for kind,meta in rows:
   if kind!='UNKNOWN_EXECUTION':break
   rid=strict(meta.encode())['request_id']
   if self.db.execute(f'SELECT 1 FROM {REJECT} WHERE request_id=?',(rid,)).fetchone():break
   streak+=1
   if streak==3:break
  return {'sent_requests':total,'unknown_requests':unknown,'trajectory_consecutive_unknown':streak}

# Only SELECT references change; original INSERT/UPDATE/assertions stay intact.
# Code-object substitution also reaches original bound methods cached by peer.
def select_sql(s):
 if not isinstance(s,str)or not s.lstrip().upper().startswith('SELECT '):return s
 for old,new in (('requests','upstream_effective_requests'),('unknown_charges','upstream_effective_unknown_charges'),('unknown_stops','upstream_effective_unknown_stops')):
  s=re.sub(r'\b(FROM|JOIN)\s+'+old+r'\b',lambda m:m[1]+' '+new,s,flags=re.I)
  s=s.replace(old+'.','upstream_effective_'+old+'.')
 return s

def changed_code(code):
 return code.replace(co_consts=tuple(changed_code(c)if isinstance(c,types.CodeType)else select_sql(c)for c in code.co_consts))

class Projection:
 def __init__(self):self.saved=[];self.old_pending=None
 def change(self,fn,code,ns=None):
  self.saved.append((fn,fn.__code__));fn.__code__=code
  if ns:fn.__globals__.update(ns)
 def install(self,ledgers,peer=None):
  import budget,aggregate_capacity,a4_final_fault_gate
  for l in ledgers:schema(l)
  for name,fn in vars(budget.Ledger).items():
   if not isinstance(fn,types.FunctionType)or name in('__init__','_unknown_schema'):continue
   if name=='unknown_statistics':self.change(fn,statistics.__code__,{'REJECT':REJECT,'strict':strict})
   elif name=='_unknown_thresholds':self.change(fn,thresholds.__code__,{'REPEAT':REPEAT})
   else:
    code=changed_code(fn.__code__)
    if code!=fn.__code__:self.change(fn,code)
  self.old_pending=budget.LOGICAL_PENDING
  budget.LOGICAL_PENDING=budget.LOGICAL_PENDING.replace('requests.id','upstream_effective_requests.id')+f' AND NOT EXISTS(SELECT 1 FROM {REJECT} ur WHERE ur.request_id=upstream_effective_requests.id)'
  # Existing peer.logical/fault closures are already live; mutate their exact
  # SELECT constants as well, preserving closure identities/capacity semantics.
  if peer is not None:
   for l in ledgers:
    for fn in(l.global_logical_unresolved,l.admission_fault):self.change(fn,changed_code(fn.__code__))
   self.change(aggregate_capacity.CapacityPeer.search,changed_code(aggregate_capacity.CapacityPeer.search.__code__))
  # A trajectory UNKNOWN stop must not be reclassified as a GLOBAL financial
  # incident. GLOBAL ratio stop, paused control and all other proofs retained.
  fn=a4_final_fault_gate.evidence;code=changed_code(fn.__code__)
  code=code.replace(co_consts=tuple(c.replace('FROM upstream_effective_unknown_stops LIMIT 1',"FROM upstream_effective_unknown_stops WHERE scope='GLOBAL' LIMIT 1")if isinstance(c,str)else c for c in code.co_consts))
  self.change(fn,code)
  return self
 def restore_own_test(self):
  import budget
  for fn,code in reversed(self.saved):fn.__code__=code
  if self.old_pending is not None:budget.LOGICAL_PENDING=self.old_pending


def approved_rejection(db,t,rid,upper,inp,out,receipt):
 exists=db.execute("SELECT 1 FROM sqlite_master WHERE name=?",(REJECT,)).fetchone()
 if not exists:return False
 row=db.execute(f'SELECT * FROM {REJECT} WHERE request_id=?',(rid,)).fetchone()
 if row is None:return False
 # Row factory is not assumed in the FINAL immutable connection.
 _,status,amount,seq,raw=tuple(row);m=strict(raw.encode())
 need(status in(429,503)and amount in(0,upper)and inp is None and out is None and receipt is None,'FINAL_EXPLICIT_REJECTION_NO_USAGE')
 event=db.execute('SELECT trajectory,kind,metadata FROM events WHERE seq=?',(seq,)).fetchone()
 need(event is not None and tuple(event)==(t,'UPSTREAM_REJECTED_'+str(status),raw)and m['schema']=='agensh-explicit-upstream-rejection-v1'and m['request_id']==rid and m['trajectory']==t and m['effective_search_tokens']==0 and m['reversed_tokens']==amount and m['http_status']==status,'FINAL_EXPLICIT_REJECTION_RECEIPT')
 charge=db.execute('SELECT upper_bound,settlement_seq FROM unknown_charges WHERE request_id=?',(rid,)).fetchone()
 need((charge is None and amount==0 and m['original_charge_seq']is None)or(charge is not None and tuple(charge)==(amount,m['original_charge_seq'])),'FINAL_EXPLICIT_REJECTION_EXACT_REVERSAL')
 return True

def final_projection(projection):
 import v21_inputs,aux_allowance
 fn=v21_inputs.build;node=ast.parse(inspect.getsource(fn)).body[0]
 candidates=[n for n in ast.walk(node)if isinstance(n,ast.For)and isinstance(n.target,ast.Tuple)and ast.unparse(n.target)=='(rid, role, state, upper, inp, out, receipt_sha)']
 need(len(candidates)==1,'REJECTION_EXACT_FINAL_METADATA_LOOP')
 loop=candidates[0]
 loop.body.insert(1,ast.parse("if _a4_approved_rejection(ledger_db,d['trajectory'],rid,upper,inp,out,receipt_sha): continue").body[0])
 ns={**fn.__globals__,'_a4_approved_rejection':approved_rejection};exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),fn.__code__.co_filename+':explicit-rejection','exec'),ns)
 fixed=ns['build'].__code__
 # Preserve the already-authorized50M literal-only ABI if installed.
 baseline=compile(ast.fix_missing_locations(ast.Module(body=[ast.parse(inspect.getsource(fn)).body[0]],type_ignores=[])),fn.__code__.co_filename,'exec')
 has50=any(isinstance(c,tuple)and c==(10000000,20000000,50000000)for c in fn.__code__.co_consts)
 if has50:fixed,n=aux_allowance._constant(fixed,(10000000,20000000),(10000000,20000000,50000000));need(n==1,'REJECTION_KEEP50M_ABI')
 projection.change(fn,fixed,{'_a4_approved_rejection':approved_rejection})
