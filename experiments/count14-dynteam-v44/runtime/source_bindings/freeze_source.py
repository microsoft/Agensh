#!/usr/bin/env python3
"""Local static plan/freezer CLI; default plan only, never a production package."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from source_package import build_plan,freeze,pinned_json,EXCLUSIONS,exclusive,wire,sha


def main():
 p=argparse.ArgumentParser();p.add_argument('--code-root',required=True);p.add_argument('--archive',required=True)
 p.add_argument('--output-plan',required=True);p.add_argument('--approve-two-exact-own-exclusions',action='store_true')
 p.add_argument('--supplement',nargs=2,action='append',default=[]);p.add_argument('--include-source-tools',action='store_true')
 p.add_argument('--freeze-destination');a=p.parse_args()
 supplements=[]
 for path,pin in a.supplement:
  value=pinned_json(Path(path).resolve(),pin)
  if value.get('schema')!='count14-formal-source-supplements-v1':raise ValueError('SOURCE_EXPLICIT_SUPPLEMENT_SCHEMA')
  supplements.extend(value['roots'])
 if a.include_source_tools:
  d=Path(a.code_root).resolve();own=Path(__file__).resolve().parent
  names=('source_package.py','deploy_import_registry.py','freeze_source.py')
  entries={n:dict(sha256=sha((own/n).read_bytes()),bytes=(own/n).stat().st_size)for n in names}
  supplements.append(dict(relative_root=str(own.relative_to(d)),imports={n:e['sha256']for n,e in entries.items()},execution=entries))
 plan=build_plan(a.code_root,a.archive,explicit_exclusions=EXCLUSIONS if a.approve_two_exact_own_exclusions else(),supplements=supplements)
 out=Path(a.output_plan).resolve();exclusive(out,wire(plan))
 result=dict(PUBLIC_code='STATIC_SOURCE_PLAN_READY_NOT_DELIVERY',path=str(out),sha256=sha(wire(plan)),files=len(plan['files']),
  excluded_OWN_members=len(plan['exclusions']),native_assets_opaque=True,models=0,Dev4=False,formal_delivery=False)
 if a.freeze_destination:result['static_source']=freeze(plan,code_root=a.code_root,archive=a.archive,destination=a.freeze_destination)
 print(json.dumps(result,sort_keys=True));return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:
  frames,tb=[],error.__traceback__
  while tb:frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
  print(json.dumps(dict(PUBLIC_code='STATIC_SOURCE_FREEZE_REFUSED',exception_type=type(error).__name__,locations=frames),sort_keys=True));raise SystemExit(2)
