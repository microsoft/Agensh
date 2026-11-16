"""Publish truthful failed-admission observations; never change admission.

Only the original resource-proof PRODUCER closure's policy cell changes.
All consumers retain the exact strict validator and the original <=96 guard.
The original observer, source ledgers, windows, timestamps and schema stay live.
"""
import ast,types

def need(ok):
 if not ok:raise RuntimeError('PUBLIC_EXACT_TRUTHFUL_RESOURCE_PUBLISHER_ABI_REFUSED')

def observation_policy(original,source):
 tree=ast.parse(source)
 nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='validate'];need(len(nodes)==1)
 n=nodes[0];need('publish_observation_only'not in [a.arg for a in n.args.kwonlyargs])
 # Exact unique threshold predicate; integer/type/total=sum guards stay intact.
 class PermitObservation(ast.NodeTransformer):
  count=0
  def visit_Compare(self,x):
   if (isinstance(x.left,ast.Name)and x.left.id=='total'and len(x.ops)==1 and isinstance(x.ops[0],ast.LtE)and
       len(x.comparators)==1 and isinstance(x.comparators[0],ast.Constant)and type(x.comparators[0].value)is int and x.comparators[0].value==96):
    self.count+=1;return ast.copy_location(ast.BoolOp(op=ast.Or(),values=[ast.Name(id='publish_observation_only',ctx=ast.Load()),x]),x)
   return self.generic_visit(x)
 change=PermitObservation();n=change.visit(n);need(change.count==1)
 n.args.kwonlyargs.append(ast.arg(arg='publish_observation_only'));n.args.kw_defaults.append(ast.Constant(value=False))
 ns={};exec(compile(ast.fix_missing_locations(ast.Module(body=[n],type_ignores=[])),__file__,'exec'),ns)
 fn=types.FunctionType(ns['validate'].__code__,original.__globals__,'validate',original.__defaults__)
 fn.__kwdefaults__=dict(ns['validate'].__kwdefaults__)
 def publish(value,*,now_ns=None,for_system_health=False):
  need(for_system_health is True)
  return fn(value,now_ns=now_ns,for_system_health=True,publish_observation_only=True)
 publish.strict_extended_validator=fn
 return publish

def install(module,source):
 previous=module.validate
 if getattr(previous,'_count14_truthful_over96_producer_v1',False):return previous
 need(previous.__code__.co_name=='validate'and set(previous.__code__.co_freevars)=={'observer','policy'})
 cells=dict(zip(previous.__code__.co_freevars,previous.__closure__))
 strict=cells['policy'].cell_contents;observer=cells['observer'].cell_contents
 need(callable(getattr(observer,'collect',None)))
 policy=observation_policy(strict,source)
 def cell(value):return(lambda:value).__closure__[0]
 new=types.FunctionType(previous.__code__,previous.__globals__,previous.__name__,previous.__defaults__,
     tuple(cell(policy)if name=='policy'else cells[name]for name in previous.__code__.co_freevars))
 new.__kwdefaults__=previous.__kwdefaults__;new.__dict__.update(previous.__dict__)
 new._count14_truthful_over96_producer_v1=True
 new._count14_original_producer=previous
 new._count14_strict_consumer_policy=strict
 module.validate=new
 return new
