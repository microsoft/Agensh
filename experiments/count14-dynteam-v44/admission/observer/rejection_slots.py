"""Original exact429/503 physical terminal projection in the SAME RO snapshot.

No raw request/fee/event/unknown/state is changed. Missing proof keeps a slot.
Original UNKNOWN502 releases and final health SQL corrections stay unchanged.
"""
import ast,types
KEY='_count14_observer_original_rejection_slots_v2'
SQL="""SELECT COUNT(DISTINCT r.id)FROM requests r
JOIN upstream_rejections u ON u.request_id=r.id
JOIN events e ON e.seq=u.event_seq
JOIN upstream_effective_requests v ON v.id=r.id
LEFT JOIN unknown_charges c ON c.request_id=r.id
WHERE r.state IN('SENT','UNKNOWN')AND r.input IS NULL AND r.output IS NULL AND r.receipt_sha IS NULL
AND u.http_status IN(429,503)AND u.reversed_tokens IN(0,r.upper_bound)AND v.state='UPSTREAM_REJECTED'
AND e.kind='UPSTREAM_REJECTED_'||u.http_status AND e.trajectory=r.trajectory AND e.metadata=u.metadata
AND json_extract(u.metadata,'$.schema')='agensh-explicit-upstream-rejection-v1'
AND json_extract(u.metadata,'$.request_id')=r.id AND json_extract(u.metadata,'$.trajectory')=r.trajectory
AND json_extract(u.metadata,'$.http_status')=u.http_status AND json_extract(u.metadata,'$.effective_search_tokens')=0
AND json_extract(u.metadata,'$.original_state')=r.state AND json_extract(u.metadata,'$.reversed_tokens')=u.reversed_tokens
AND((r.state='SENT'AND c.request_id IS NULL AND u.reversed_tokens=0 AND json_extract(u.metadata,'$.original_charge_seq')IS NULL)
OR(r.state='UNKNOWN'AND c.request_id IS NOT NULL AND c.upper_bound=u.reversed_tokens AND c.upper_bound=r.upper_bound
AND json_extract(u.metadata,'$.original_charge_seq')=c.settlement_seq))
AND NOT(r.state='UNKNOWN'AND EXISTS(SELECT 1 FROM events ue WHERE ue.kind='UNKNOWN_EXECUTION'
AND json_extract(ue.metadata,'$.request_id')=r.id AND json_extract(ue.metadata,'$.code')='UPSTREAM_HTTP_502')
AND EXISTS(SELECT 1 FROM events he WHERE he.kind='SCIENTIFIC_HTTP_HANDLER_FINISHED'AND json_extract(he.metadata,'$.request_id')=r.id))"""

def count(db):
 objects=dict(db.execute("SELECT name,type FROM sqlite_master WHERE name IN('upstream_rejections','upstream_effective_requests')"))
 if objects!={'upstream_rejections':'table','upstream_effective_requests':'view'}:return 0
 required={'requests':{'id','trajectory','state','input','output','receipt_sha','upper_bound'},
           'upstream_rejections':{'request_id','http_status','reversed_tokens','event_seq','metadata'},
           'events':{'seq','kind','trajectory','metadata'},
           'unknown_charges':{'request_id','upper_bound','settlement_seq'}}
 for name,columns in required.items():
  if not columns<={r[1]for r in db.execute('PRAGMA table_info('+name+')')}:return 0
 return db.execute(SQL).fetchone()[0]

def install(observer,source):
 old=observer.native
 if getattr(old,'_count14_original_rejection_slots_v2',False):return old
 def need(ok):
  if not ok:raise RuntimeError('PUBLIC_ORIGINAL_REJECTION_SLOT_OBSERVER_ABI_REFUSED')
 tree=ast.parse(source);nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='native'];need(len(nodes)==1)
 fn=nodes[0]
 with_db=[n for n in ast.walk(fn)if isinstance(n,ast.With)and any(isinstance(i.optional_vars,ast.Name)and i.optional_vars.id=='db'for i in n.items)]
 need(len(with_db)==1)
 # Keep already-installed AUX terminal health SQL literal, not the old source's
 # intermediate-POSSIBLE bug. Every prior SQL literal has a matching signature.
 aux=[c for c in old.__code__.co_consts if type(c)is str and "WITH t AS(SELECT json_extract(metadata,'$.permit_id')"in c]
 need(len(aux)==1)
 class RetainPriorSQL(ast.NodeTransformer):
  changed=0
  def visit_Constant(self,n):
   if type(n.value)is str and "WITH t AS(SELECT json_extract(metadata,'$.permit_id')"in n.value:
    self.changed+=1;return ast.copy_location(ast.Constant(value=aux[0]),n)
   return n
 prior=RetainPriorSQL();fn=prior.visit(fn);need(prior.changed==1)
 with_db[0].body.append(ast.Assign(targets=[ast.Name(id='rejected',ctx=ast.Store())],
    value=ast.Call(func=ast.Name(id=KEY,ctx=ast.Load()),args=[ast.Name(id='db',ctx=ast.Load())],keywords=[])))
 returns=[n for n in fn.body if isinstance(n,ast.Return)];need(len(returns)==1 and isinstance(returns[0].value,ast.Call))
 call=returns[0].value;inflight=[k for k in call.keywords if k.arg=='inflight'];need(len(inflight)==1)
 need(ast.dump(inflight[0].value,include_attributes=False)==ast.dump(ast.parse('raw-released',mode='eval').body,include_attributes=False))
 inflight[0].value=ast.parse('raw-released-rejected',mode='eval').body
 call.keywords.append(ast.keyword(arg='explicit_original_429_503_slots_excluded',value=ast.Name(id='rejected',ctx=ast.Load())))
 fn.body.insert(fn.body.index(returns[0]),ast.Expr(value=ast.Call(func=ast.Name(id='need',ctx=ast.Load()),
   args=[ast.parse('0<=released+rejected<=raw',mode='eval').body],keywords=[])))
 namespace={};exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),__file__,'exec'),namespace)
 need(KEY not in old.__globals__);old.__globals__[KEY]=count
 new=types.FunctionType(namespace['native'].__code__,old.__globals__,'native',old.__defaults__)
 new.__kwdefaults__=old.__kwdefaults__;new.__dict__.update(old.__dict__)
 new._count14_original_rejection_slots_v2=True;new._count14_previous_rejection_native=old
 # All pre-existing SQL constants stay present (including the installed AUX fix).
 prior_sql=[c for c in old.__code__.co_consts if type(c)is str and('SELECT 'in c or 'PRAGMA 'in c or c=='BEGIN')]
 need(all(c in new.__code__.co_consts for c in prior_sql))
 observer.native=new;return new
