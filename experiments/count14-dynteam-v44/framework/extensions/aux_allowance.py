"""One excused failure ONLY for the seven exact jobs containing approved15.

Old rows/tables stay intact. Attempt4 has an additive table, unique RNG, scope
checks everywhere; all other replicates retain the original max2 replacements.
"""
from pathlib import Path
import ast,copy,inspect,textwrap,types
from common import need,digest,wire,strict,hash_file
import final_attempts as A
TABLE='aux_stall_exempt_replacement_jobs'
def _constant(code,old,new):
 values=[];count=0
 for v in code.co_consts:
  if isinstance(v,types.CodeType):v,n=_constant(v,old,new);count+=n
  elif type(v)is type(old)and v==old:v=new;count+=1
  values.append(v)
 return code.replace(co_consts=tuple(values)),count
ALLOWED=set()

def allowed(point,k,attempt):
 return type(attempt)is int and (attempt in(1,2,3)or attempt==4 and (point,k)in ALLOWED)
def maximum(q,j):return 4 if (j['point'],j['replicate'])in ALLOWED else 3
def job_table(q,nxt):return TABLE if nxt==4 else 'replacement_jobs'
def set_authorization(auth):
 need(auth['schema']=='a4-user-aux-stall15-v1'and len(auth['rows'])==15 and auth['total_upper_bound']==3023011,'AUX_ALLOWANCE_FIXED15_AUTH')
 need(len({r['request_id']for r in auth['rows']})==15 and sum(r['charged_tokens']for r in auth['rows'])==3023011,'AUX_ALLOWANCE_DISTINCT15_SUM')
 need(all(r['attempt']==1 and r['replicate_id']in(1,2,3)for r in auth['rows']),'AUX_ALLOWANCE_ONLY_ORIGINAL_ATTEMPT1')
 pairs={(r['point_id'],r['replicate_id'])for r in auth['rows']};need(len(pairs)==7,'AUX_ALLOWANCE_SEVEN_EXACT_REPLICATES')
 ALLOWED.update(pairs)

def _same(a,b):
 attrs=('co_code','co_argcount','co_posonlyargcount','co_kwonlyargcount','co_nlocals','co_flags','co_names','co_varnames','co_freevars','co_cellvars')
 return all(getattr(a,k)==getattr(b,k)for k in attrs)and len(a.co_consts)==len(b.co_consts)and all(_same(x,y)if isinstance(x,types.CodeType)and isinstance(y,types.CodeType)else type(x)is type(y)and x==y for x,y in zip(a.co_consts,b.co_consts))
def _node(module,name,cls=None):
 source=Path(module.__file__).read_text();tree=ast.parse(source)
 body=next(x for x in tree.body if isinstance(x,ast.ClassDef)and x.name==cls).body if cls else tree.body
 node=copy.deepcopy(next(x for x in body if isinstance(x,ast.FunctionDef)and x.name==name))
 node._a4_imports=[copy.deepcopy(x)for x in tree.body if isinstance(x,(ast.Import,ast.ImportFrom))]
 return node
def _compile(node,ns):
 space=dict(ns)
 if node.name=='__init__':
  cls=ast.ClassDef(name='FinalBinding',bases=[],keywords=[],body=[node],decorator_list=[],type_params=[])
  exec(compile(ast.fix_missing_locations(ast.Module(body=getattr(node,'_a4_imports',[])+[cls],type_ignores=[])),str(Path(__file__))+':scoped-allowance','exec'),space)
  return space['FinalBinding'].__init__
 exec(compile(ast.fix_missing_locations(ast.Module(body=getattr(node,'_a4_imports',[])+[node],type_ignores=[])),str(Path(__file__))+':scoped-allowance','exec'),space)
 return space[node.name]
def _replace_test(node,code,replacement):
 matches=[x for x in ast.walk(node)if isinstance(x,ast.Call)and ast.unparse(x.func)=='need'and len(x.args)>1 and isinstance(x.args[1],ast.Constant)and x.args[1].value==code]
 need(len(matches)==1,'AUX_ALLOWANCE_EXACT_SINGLE_GUARD_'+code);matches[0].args[0]=ast.parse(replacement,mode='eval').body

def patch_attempt_partial(fn,*,unknown=False,terminal_predicate=None):
 # Read original public source, not a virtual-code filename. Existing exit0
 # qualification is retained explicitly in the UNKNOWN-only body.
 import aux_unknown_replacement as policy
 module=policy if unknown else A
 node=_node(module,'partial_and_replace')
 if unknown:
  need(terminal_predicate is not None,'AUX_ALLOWANCE_EXIT0_POLICY_REQUIRED')
  _replace_test(node,'AUX_PARTIAL_REAL_FAILED_TERMINAL','_allowance_terminal_ok(terminal,p)')
 tests=[x for x in ast.walk(node)if isinstance(x,ast.If)and ast.unparse(x.test)=='attempt >= 3'];need(len(tests)==1,'AUX_ALLOWANCE_ONE_MAX2_TEST')
 tests[0].test=ast.parse('_allowance_maximum(q,j)'if unknown else'_allowance_maximum(q,job)',mode='eval').body
 tests[0].test=ast.Compare(left=ast.Name('attempt',ast.Load()),ops=[ast.GtE()],comparators=[tests[0].test])
 # Exact original two SQL statements; use the additive attempt4 table only.
 replacements=0
 for call in [x for x in ast.walk(node)if isinstance(x,ast.Call)and ast.unparse(x.func)=='q.db.execute']:
  if not call.args or not isinstance(call.args[0],ast.Constant)or type(call.args[0].value)is not str:continue
  sql=call.args[0].value
  if sql.startswith('SELECT ')and 'FROM replacement_jobs WHERE id=?'in sql:
   prefix,suffix=sql.split('replacement_jobs');call.args[0]=ast.parse(repr(prefix)+'+_allowance_table(q,nxt)+'+repr(suffix),mode='eval').body;replacements+=1
  elif sql.startswith('INSERT INTO replacement_jobs '):
   prefix,suffix=sql.split('replacement_jobs');call.args[0]=ast.parse(repr(prefix)+'+_allowance_table(q,nxt)+'+repr(suffix),mode='eval').body;replacements+=1
 need(replacements==2,'AUX_ALLOWANCE_EXACT_TWO_REPLACEMENT_SQL')
 ns=dict(fn.__globals__);ns.update(_allowance_maximum=maximum,_allowance_table=job_table,_allowance_terminal_ok=terminal_predicate)
 return _compile(node,ns)

def _audit_allowed(trajectory,target,natural,k,attempt):
 key={'trajectory':trajectory,'target':target}
 if natural is not None:key.update(point_kind='NATURAL_STOP',policy_sha256=natural['policy_sha256'])
 return allowed(digest(key),k,attempt)

def install_guards(auth):
 """Trusted parent+fresh child. Preserve existing function/wrapper identities."""
 set_authorization(auth)
 import final_binding as B,native_k3 as K,run_native_final_child as C
 if getattr(A,'_a4_scoped_stall_allowance_guards',False):return
 init=inspect.unwrap(B.FinalBinding.__init__)
 planned=[]
 node=_node(B,'__init__','FinalBinding');expected=_compile(copy.deepcopy(node),init.__globals__)
 need(_same(init.__code__,expected.__code__),'AUX_ALLOWANCE_ORIGINAL_BINDING_EXECUTABLE')
 _replace_test(node,'FINAL_REPLICATE_ATTEMPT','_a4_allowance_allowed(point_id,replicate_index,replicate_attempt)')
 planned.append((init,_compile(node,{**init.__globals__,'_a4_allowance_allowed':allowed}),{'_a4_allowance_allowed':allowed}))
 fn=A.request_rng;node=_node(A,'request_rng');need(_same(fn.__code__,_compile(copy.deepcopy(node),fn.__globals__).__code__),'AUX_ALLOWANCE_ORIGINAL_RNG_EXECUTABLE')
 _replace_test(node,'FINAL_REPLACEMENT_ATTEMPT','attempt != 1 and _a4_allowance_allowed(point_id,replicate_id,attempt)')
 planned.append((fn,_compile(node,{**fn.__globals__,'_a4_allowance_allowed':allowed}),{'_a4_allowance_allowed':allowed}))
 fn=C.config_fields;node=_node(C,'config_fields');need(_same(fn.__code__,_compile(copy.deepcopy(node),fn.__globals__).__code__),'AUX_ALLOWANCE_ORIGINAL_CONFIG_EXECUTABLE')
 # Preserve exact field set; only the original attempt membership is expanded.
 members=[x for x in ast.walk(node)if isinstance(x,ast.Compare)and ast.unparse(x)=="config['replicate_attempt'] in (2, 3)"]
 need(len(members)==1,'AUX_ALLOWANCE_EXACT_CONFIG_ATTEMPT')
 target=members[0];target.left=ast.parse("_a4_allowance_allowed(config.get('point_id'),config.get('k'),config['replicate_attempt']) and config['replicate_attempt'] != 1",mode='eval').body;target.ops=[ast.Is()];target.comparators=[ast.Constant(True)]
 planned.append((fn,_compile(node,{**fn.__globals__,'_a4_allowance_allowed':allowed}),{'_a4_allowance_allowed':allowed}))
 fn=K.audit_three;node=_node(K,'audit_three');baseline=_compile(copy.deepcopy(node),fn.__globals__).__code__
 # Existing authorized50M ABI is a single literal-only executable difference.
 extended,n=_constant(baseline,(10000000,20000000),(10000000,20000000,50000000));need(n==1,'AUX_ALLOWANCE_EXACT_50M_BUDGET_LITERAL')
 is50=_same(fn.__code__,extended);need(is50 or _same(fn.__code__,baseline),'AUX_ALLOWANCE_ORIGINAL_OR_AUTHORIZED50M_AUDIT')
 _replace_test(node,'FINAL_K_ATTEMPT','_a4_audit_allowed(trajectory,target_tokens,natural_stop,k,attempt)')
 fixed=_compile(node,{**fn.__globals__,'_a4_audit_allowed':_audit_allowed})
 if is50:fixed.__code__,n=_constant(fixed.__code__,(10000000,20000000),(10000000,20000000,50000000));need(n==1,'AUX_ALLOWANCE_PRESERVE_50M')
 planned.append((fn,fixed,{'_a4_audit_allowed':_audit_allowed}))
 for fn,fixed,globals_patch in planned:
  fn.__globals__.update(globals_patch);fn.__code__=fixed.__code__
 A._a4_scoped_stall_allowance_guards=True

def install_queue(q):
 with q.tx():
  q.db.execute('CREATE TABLE IF NOT EXISTS '+TABLE+'(id TEXT PRIMARY KEY,point TEXT NOT NULL REFERENCES points,replicate INTEGER NOT NULL,state TEXT NOT NULL,claim TEXT,child TEXT,terminal TEXT,result TEXT,attempt INTEGER NOT NULL CHECK(attempt=4),original_job TEXT NOT NULL REFERENCES jobs,UNIQUE(point,replicate,attempt))')
 if getattr(A,'_a4_scoped_stall_allowance_tables',False):return
 table,job,rows=A.table,A.replacement_job,A.all_rows
 def exists(q):return q.db.execute("SELECT 1 FROM sqlite_master WHERE name=?",(TABLE,)).fetchone()is not None
 def is_extra(q,id):return exists(q)and q.db.execute('SELECT 1 FROM '+TABLE+' WHERE id=?',(id,)).fetchone()is not None
 def extended_table(q,id):return TABLE if is_extra(q,id)else table(q,id)
 def extended_job(q,id):
  if not is_extra(q,id):return job(q,id)
  return dict(q.db.execute('SELECT r.*,p.trajectory,p.setting,p.target,p.input_root,p.input_policy FROM '+TABLE+' r JOIN points p ON r.point=p.point WHERE r.id=?',(id,)).fetchone())
 def extended_rows(q):return rows(q)+([q._job(r[0])for r in q.db.execute('SELECT id FROM '+TABLE+' ORDER BY rowid')]if exists(q)else[])
 A.table=extended_table;A.replacement_job=extended_job;A.all_rows=extended_rows
 A._a4_scoped_stall_allowance_tables=True
