"""Per-parent source/start and per-point settlement containment.

Reuse exact original producer loops and ALL input/budget/identity guards. Never
reconstruct a source, restart a worker, replay requests, or modify mainline code.
"""
from pathlib import Path
from types import MethodType
import ast,copy,inspect,textwrap,traceback
from common import need,hash_file
from trajectory_isolation import shared_control_reason
SOURCE_SHA='4e519788567abf58f59b335571e4142a408855c36a24c3f490d46360d4fefdf1'
FINANCIAL_CODES=frozenset({'UPSTREAM_TOKEN_BOUND_VIOLATION','LOCAL_PROMPT_RESERVATION_EXCEEDED_USAGE_RETAINED','ACCOUNTED_PROTOCOL_ERROR','UPPER_BOUND_BREACH_USAGE_RETAINED','SEARCH_ADMISSION_STORAGE_FAILURE_NO_RETRY'})

def retain(manager,parent,error,where):
 state=manager._fork_manager_isolation
 need(parent in manager.driver.records,'FORK_LOCAL_ORIGINAL_PARENT_ONLY')
 # This check uses actual controls/UNKNOWN stop tables, not parent.failed's
 # derived peer hold. No original control or financial fault is ever cleared.
 global_stop=shared_control_reason(manager.l)
 unsafe=bool(global_stop)or getattr(error,'code',None)in FINANCIAL_CODES
 row={'stage':where,'exception_type':type(error).__name__,
      'frames':[{'file':v.filename,'line':v.lineno,'function':v.name}
                for v in traceback.extract_tb(error.__traceback__)],
      'messages_locals_omitted':True,'automatic_retry':False,
      'mainline_methods_or_accounts_modified':False,'global_model_or_billing_stop':unsafe}
 state['faults'][parent]=row
 manager.last_error=type(error).__name__
 record=manager.records.get(parent)
 # Preserve original worker failure path, including every pre-existing
 # accounting guard and branch admission closure. No extra child is started.
 if record is not None:
  state['original_fail'](parent,record,error)
  unsafe=unsafe or manager.needs_caretaker
 if unsafe:
  manager.needs_caretaker=True
  if global_stop is None:
   with manager.driver.ledger.tx():
    manager.driver.ledger.db.execute("UPDATE model_control SET paused=1,epoch=epoch+1,reason='AGGREGATE_BRANCH_MODEL_OR_BILLING_INCIDENT' WHERE singleton=1")
    manager.driver.ledger.event('GLOBAL','AGGREGATE_BRANCH_MODEL_OR_BILLING_INCIDENT',
        {'error_type':type(error).__name__,'branch_parent':parent})
 row['global_model_or_billing_stop']=unsafe
 with manager.l.tx():
  manager.l.event(parent,'AGGREGATE_PARENT_LOCAL_LOOP_FAILURE_RETAINED',row)
 # Actual global incidents propagate to the original manager run catch. Pure
 # source/attach/point errors are retained once and siblings keep progressing.
 if unsafe:raise error

def _compile(original,where):
 path=Path(inspect.getsourcefile(original))
 need(path.name=='aggregate_install.py'and hash_file(path)['sha256']==SOURCE_SHA,
      'FORK_ISOLATION_EXACT_ORIGINAL_MANAGER_SOURCE')
 tree=ast.parse(textwrap.dedent(inspect.getsource(original)));fn=tree.body[0]
 need(isinstance(fn,ast.FunctionDef),'FORK_ISOLATION_ORIGINAL_METHOD')
 if where=='source-start':
  need(fn.name=='step'and len(fn.body)==1 and isinstance(fn.body[0],ast.With),
       'FORK_ISOLATION_ORIGINAL_STEP_LOCK')
  loops=[x for x in fn.body[0].body if isinstance(x,ast.For)]
  need(len(loops)==1 and ast.unparse(loops[0].target)=='(parent, original)',
       'FORK_ISOLATION_ORIGINAL_SOURCE_LOOP');loop=loops[0]
 elif where=='point-settle':
  need(fn.name=='settle'and len(fn.body)==1 and isinstance(fn.body[0],ast.For),
       'FORK_ISOLATION_ORIGINAL_SETTLE_LOOP');loop=fn.body[0]
  need(ast.unparse(loop.target)=='(parent, r)','FORK_ISOLATION_ORIGINAL_POINT_TARGET')
 else:
  need(where=='bind-gate'and fn.name=='bind_main_gates'and len(fn.body)==1 and isinstance(fn.body[0],ast.For),
       'FORK_ISOLATION_ORIGINAL_BIND_LOOP');loop=fn.body[0]
  need(ast.unparse(loop.target)=='r'and ast.unparse(loop.iter)=='list(self.driver.records.values())',
       'FORK_ISOLATION_ORIGINAL_GATE_VALUES')
  loop.target=ast.Tuple(elts=[ast.Name('parent',ast.Store()),ast.Name('r',ast.Store())],ctx=ast.Store())
  loop.iter=ast.parse('list(self.driver.records.items())',mode='eval').body
 skip=ast.parse("if parent in self._fork_manager_isolation['faults']: continue").body[0]
 handler=ast.ExceptHandler(type=ast.Name('BaseException',ast.Load()),name='error',
   body=ast.parse(f"_retain(self,parent,error,{where!r})").body)
 loop.body=[skip,ast.Try(body=loop.body,handlers=[handler],orelse=[],finalbody=[])]
 ns=dict(original.__globals__);ns['_retain']=retain
 exec(compile(ast.fix_missing_locations(tree),'<per-parent-original-aggregate-manager>','exec'),ns)
 return ns[fn.name]

def install(manager):
 from aggregate_install import Manager
 need(type(manager)is Manager and not hasattr(manager,'_fork_manager_isolation'),
      'FORK_MANAGER_ISOLATION_ONCE_ORIGINAL_INSTANCE')
 methods={name:getattr(manager,name)for name in('step','settle','bind_main_gates')}
 fixed={name:_compile(fn,where)for(name,fn),where in zip(methods.items(),('source-start','point-settle','bind-gate'))}
 original_status=manager.status
 def status(self):
  value=original_status()
  value['parent_loop_faults']=copy.deepcopy(self._fork_manager_isolation['faults'])
  value['local_loop_isolation']=True
  return value
 with manager.lock:
  manager._fork_manager_isolation={'faults':{},'original_methods':methods,
                                  'original_fail':manager.fail,'original_status':original_status}
  for name,fn in fixed.items():setattr(manager,name,MethodType(fn,manager))
  manager.status=MethodType(status,manager)
 return {'schema':'agensh-fork-manager-parent-loop-isolation-v1','source_sha256':SOURCE_SHA,
         'mainline_methods_patched':False,'source_checks_unchanged':True,
         'worker_fail_guards_unchanged':True,'records_restarted':0,'requests_replayed':0,
         'loops':['bind-main-gate','source-start','point-settle']}
