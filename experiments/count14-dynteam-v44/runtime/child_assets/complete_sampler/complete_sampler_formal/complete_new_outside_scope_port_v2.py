"""One private finite-cache lexical port over original outside projection.
All original collection, SQL,25s,600s,unknown and health-None logic remains.
Caller applies this AFTER existing exact18/provider source selectors.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
from types import FunctionType
import ast,copy,hashlib,inspect,textwrap
PROJECTION_PIN='66ece9e044bdde4b0742941ae390a16c9eaaf18f38c61d342224007b86fbdf26'
EXACT_ARMS={
 '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391':Path((_C14_SCRATCH + '/ct14-dynteam-formal-msg237-20261110-v33/u')),
 '9f176e2fedfa407678bc3b7d1fe6ed6a89a8782e0dbc0ddd6337f0ae3fd5e4de':Path((_C14_SCRATCH + '/ct14-dynteam-racing-smoke-msg232-20261109-v1/u')),
 '3902509c2b0daf9dea0d7421e26cf7dd29e878aebd6cdd4699615e31bd7fc937':Path((_C14_SCRATCH + '/ct14-dtr-smoke-20261105/u')),
}

def exact_cache(directory,contract_sha256):
 if contract_sha256 not in EXACT_ARMS:return False
 p=Path(directory);arm=EXACT_ARMS[contract_sha256]
 if not p.is_absolute()or '..'in p.parts:return False
 return p==arm/'owner/resources/reader-cache' or(p.parent==arm/'outside-resource-cache'and p.name not in('','.','..'))

def select(original,*,retained_combine):
 assert type(original)is FunctionType and original.__name__=='registered_outside_projection'
 source=Path(original.__code__.co_filename)
 assert source.resolve()==source and hashlib.sha256(source.read_bytes()).hexdigest()==PROJECTION_PIN
 before=ast.parse(textwrap.dedent(inspect.getsource(original)));tree=copy.deepcopy(before)
 target=ast.parse("directory.parts[3].startswith('count14-dynteam')",mode='eval').body
 replacement=ast.BoolOp(op=ast.Or(),values=[copy.deepcopy(target),ast.Call(func=ast.Name(id='_exact_new_arm_cache',ctx=ast.Load()),args=[ast.Name(id='directory',ctx=ast.Load()),ast.Name(id='contract_sha256',ctx=ast.Load())],keywords=[])])
 class Port(ast.NodeTransformer):
  def __init__(self,a,b):self.a=a;self.b=b;self.hits=0
  def generic_visit(self,n):
   if ast.dump(n,include_attributes=False)==ast.dump(self.a,include_attributes=False):self.hits+=1;return ast.copy_location(copy.deepcopy(self.b),n)
   return super().generic_visit(n)
 forward=Port(target,replacement);tree=forward.visit(tree);assert forward.hits==1
 inverse=Port(replacement,target);restored=inverse.visit(copy.deepcopy(tree));assert inverse.hits==1 and ast.dump(restored,include_attributes=False)==ast.dump(before,include_attributes=False)
 returns=[n for n in ast.walk(tree)if isinstance(n,ast.Return)and isinstance(n.value,ast.Tuple)and [getattr(x,'id',None)for x in n.value.elts]==['own','health']]
 assert len(returns)==1
 returns[0].value=ast.Call(func=ast.Name(id='_combine_retained_system',ctx=ast.Load()),args=[ast.Name(id=x,ctx=ast.Load())for x in('own','health','O','value')],keywords=[])
 reverse2=copy.deepcopy(tree)
 ret=[n for n in ast.walk(reverse2)if isinstance(n,ast.Return)and isinstance(n.value,ast.Call)and isinstance(n.value.func,ast.Name)and n.value.func.id=='_combine_retained_system']
 assert len(ret)==1
 ret[0].value=ast.Tuple(elts=[ast.Name(id=x,ctx=ast.Load())for x in('own','health')],ctx=ast.Load())
 inverse2=Port(replacement,target);reverse2=inverse2.visit(reverse2)
 assert inverse2.hits==1 and ast.dump(reverse2,include_attributes=False)==ast.dump(before,include_attributes=False)
 scope=dict(original.__globals__,_exact_new_arm_cache=exact_cache,_combine_retained_system=retained_combine);out={}
 exec(compile(ast.fix_missing_locations(tree),str(source)+':exact-two-new-arm-cache-only','exec'),scope,out)
 return out[original.__name__],dict(original_entire_projection_inverse_AST_cache_and_declared_retained_tail=True,all_original_source_SQL_25s_health_None_collection_and_same_private_observer_preserved=True,no_old_cache_or_prefix_expansion=True,only_two_registered_contract_cache_trees=True)
