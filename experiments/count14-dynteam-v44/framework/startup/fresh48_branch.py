"""Private sealed16M builder, stable after runtime rejection code projection.

Reads only pinned public framework source. Do not depend on inspect.getsource(V.build)
once the already-authorized SQL projection changes co_filename to a synthetic
filename. Original ordinary FINAL V.build remains untouched by this helper.
"""
from pathlib import Path
import ast,copy
from common import need
import v21_inputs as V

def original16_builder():
 tree=ast.parse(Path(V.__file__).read_text());functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='build']
 need(len(functions)==1,'FRESH48_ONE_PUBLIC_ORIGINAL_V21_BUILDER');f=copy.deepcopy(functions[0])
 matches=[n for n in ast.walk(f)if isinstance(n,ast.Compare)and ast.unparse(n.left)=="d['target_tokens']"and
   len(n.ops)==1 and isinstance(n.ops[0],ast.In)and len(n.comparators)==1 and
   ast.unparse(n.comparators[0])in('(10000000, 20000000)','(10000000, 20000000, 50000000, 100000000)')]
 need(len(matches)==1,'FRESH48_ONE_PRIVATE16_TARGET_BOUNDARY')
 matches[0].ops=[ast.Eq()];matches[0].comparators=[ast.Constant(16_000_000)]
 ns=dict(V.__dict__)
 if callable(ns.get('_a4_approved_rejection')):
  # Same qualified projection as rejection_ledger.final_projection, not a
  # relaxed new candidate/budget rule. Only explicit proven upstream rejection.
  loops=[n for n in ast.walk(f)if isinstance(n,ast.For)and isinstance(n.target,ast.Tuple)and
         ast.unparse(n.target)=='(rid, role, state, upper, inp, out, receipt_sha)']
  need(len(loops)==1,'FRESH48_ONE_ORIGINAL_REJECTION_METADATA_LOOP')
  loops[0].body.insert(1,ast.parse("if _a4_approved_rejection(ledger_db,d['trajectory'],rid,upper,inp,out,receipt_sha): continue").body[0])
 exec(compile(ast.fix_missing_locations(ast.Module(body=[f],type_ignores=[])),str(Path(__file__))+':private-original16-builder','exec'),ns)
 return ns['build']

def install():
 import aggregate_final as A
 need(A.original16_builder.__module__ in('aggregate_final','aggregate100_compat'),'FRESH48_ORIGINAL_BRANCH_HELPER_ONLY')
 A.original16_builder=original16_builder
 return {'original_regular_builder_changed':False,'private_source_target':16_000_000,
  'same_authorized_rejection_projection_if_installed':True,'models':0}
