"""Frozen new-instance preparation selection; container preflight before Popen.

Baseline swaps only the adjacent original statements. Racing and formal add
an early ORIGINAL container-only preflight and preserve every post-Popen host
writer/helper/read-only-view guard. No current owner or class is patched.
"""
from pathlib import Path
from types import FunctionType
import ast,copy,hashlib,inspect,textwrap
PINS={
 'baseline':('native_baseline_smoke.py','NativeBaselineSmoke.prepare_tick','4363f23d9fb845b8536f68b0e5d54ab291146134230db4aadbecc30b44d9a12a'),
 'racing':('native_racing_smoke.py','NativeRacingSmoke.prepare_tick','72a302960d4e6783c1ee1d8cc87ee75073d067c8e68802375c44466b68ebaf27'),
 'formal':('native_formal_cohort.py','NativeFormalCohort._prepare_one','7a38d82988e3c60181ece17e541c4c86c644ce160dfedba66fe235d5d03b7723'),
}
_SELECTED={}
def need(ok):
 if not ok:raise ValueError('NEWROOT_ONLY_FROZEN_PRERELEASE_CONTAINER_PREFLIGHT_ORDER')
def same(a,b):return ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)
def locate(tree,statement):
 rows=[]
 for parent in ast.walk(tree):
  for field,values in ast.iter_fields(parent):
   if isinstance(values,list):
    for i,value in enumerate(values):
     if isinstance(value,ast.stmt)and same(value,statement):rows.append((values,i))
 return rows

def select(original,*,canonical,mode):
 need(mode in PINS and type(original)is type(canonical)is FunctionType and
      original.__code__ is canonical.__code__ and original.__defaults__==canonical.__defaults__ and
      original.__closure__==canonical.__closure__)
 filename,qualname,pin=PINS[mode];path=Path(inspect.getsourcefile(canonical))
 need(path.name==filename and canonical.__qualname__==qualname and hashlib.sha256(path.read_bytes()).hexdigest()==pin)
 before=ast.parse(textwrap.dedent(inspect.getsource(canonical)));tree=copy.deepcopy(before)
 start=ast.parse("if not row['launch'].try_start():\n    return"if mode=='formal'else'self.launch.start()').body[0]
 check=ast.parse("row['checkpoint'].preflight()"if mode=='formal'else'self.checkpoint.preflight()').body[0]
 matches=locate(tree,start);need(len(matches)==1);values,i=matches[0]
 if mode=='baseline':
  need(i+1<len(values)and same(values[i+1],check));values[i],values[i+1]=values[i+1],values[i]
 else:values.insert(i,copy.deepcopy(check))
 inverse=copy.deepcopy(tree);values,i=locate(inverse,start)[0];need(i>0 and same(values[i-1],check))
 if mode=='baseline':values[i-1],values[i]=values[i],values[i-1]
 else:del values[i-1]
 need(same(inverse,before))
 namespace=dict(original.__globals__);namespace.pop(canonical.__name__,None)
 exec(compile(ast.fix_missing_locations(tree),canonical.__code__.co_filename+':newroot-prerelease-container-order','exec'),namespace)
 selected=namespace[canonical.__name__];selected.__defaults__=original.__defaults__;selected.__kwdefaults__=original.__kwdefaults__
 proof=dict(schema='count14-newroot-container-preflight-before-launch-order-v1',mode=mode,source_sha256=pin,
  original_complete_function_inverse_AST=True,baseline_adjacent_swap=mode=='baseline',early_original_container_preflight_added=mode!='baseline',
  all_original_postlaunch_host_writer_helper_readonly_view_and_PREPARED_guards_retained=True,
  original_exception_and_partial_refusal_body_retained=True,new_owner_supervisor_container_or_science_actions=0)
 _SELECTED[id(selected)]=(selected,selected.__code__,canonical,mode,copy.deepcopy(proof),copy.deepcopy(tree))
 return selected,proof

def matches(value,*,canonical,mode):
 r=_SELECTED.get(id(value))
 return r is not None and r[0]is value and value.__code__ is r[1] and r[2]is canonical and r[3]==mode


def selected_tree(value,*,canonical,mode):
 """Only the exact previously registered unused selected body, not arbitrary AST."""
 need(matches(value,canonical=canonical,mode=mode))
 record=_SELECTED[id(value)]
 filename,qualname,pin=PINS[mode];path=Path(inspect.getsourcefile(canonical))
 need(path.name==filename and canonical.__qualname__==qualname and hashlib.sha256(path.read_bytes()).hexdigest()==pin)
 return copy.deepcopy(record[5]),copy.deepcopy(record[4])
