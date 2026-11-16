"""Exact 4/8 runtime roster completion on immutable original source.

Uses the already-qualified expansion component delta. Adds only the three
missing original roster guards (team actors, native stage, K3 setting). No
budget/metering/network/scope/prompt/candidate rule is broadened. This builds
sources; it is not by itself a launcher or a SEARCH resumption.
"""
from pathlib import Path
import difflib,hashlib,json
from common import need,hash_file,publish,wire,strict
import build_expansion_runtime as BASE
HERE=Path(__file__).resolve().parent
EXTRA=('native_team_owner.py','native_stage_binding.py')

def transform(name,raw):
 if name in BASE.FILES:result=BASE.transform(name,raw)
 else:result=raw
 if name in EXTRA:
  old='len(roles)in(1,2,16)';need(result.count(old)==1,'FRESH48_ONE_EXACT_ORIGINAL_ROSTER_LITERAL')
  result=result.replace(old,'len(roles)in(1,2,4,8,16)')
 if name=='native_k3.py':
  old="setting in ('Agensh-16','Agensh-1')";need(result.count(old)==1,'FRESH48_ONE_EXACT_K3_SETTING_LITERAL')
  result=result.replace(old,"setting in ('Agensh-1','Agensh-4','Agensh-8','Agensh-16')")
 compile(result,name,'exec');return result

def build(source,destination,*,mode='production'):
 from fresh48_scope import selected,NEW_ROOT,NEW_EID
 mode_root,mode_eid=selected(mode)
 source=Path(source);dest=Path(destination);need(source.is_absolute()and source.resolve()==source,'FRESH48_CANONICAL_FROZEN_BASELINE')
 pins={**strict((BASE.HERE/'BASELINE_PINS.json').read_bytes()),**strict((HERE/'ADDITIONAL_BASELINE_PINS.json').read_bytes())}
 need(set(pins)==set(BASE.FILES)|set(EXTRA),'FRESH48_EXACT13_NATIVE_MODULES')
 output={};original={}
 for name,pin in pins.items():
  p=source/name;need(hash_file(p)==pin and not p.is_symlink(),'FRESH48_EXACT_NATIVE_SOURCE_PIN')
  original[name]=p.read_text();output[name]=transform(name,original[name])
  if name=='manifest.py'and mode=='zero-model':
   need(output[name].count(NEW_ROOT)==2 and output[name].count(NEW_EID)==2,'FRESH48_EXACT_DRY_MANIFEST_ROOT_PAIR')
   output[name]=output[name].replace(NEW_ROOT,mode_root).replace(NEW_EID,mode_eid)
   compile(output[name],name,'exec')
 assets=strict((HERE/'K3_ASSET_PINS.json').read_bytes());asset_bytes={}
 need(set(assets)=={'NATIVE_K3_ORIGIN.json','native_evaluation_consistency.py','native_k3_original.py'},'FRESH48_EXACT_ORIGINAL_K3_ASSETS')
 for name,pin in assets.items():
  p=source/name;need(hash_file(p)==pin and not p.is_symlink(),'FRESH48_EXACT_K3_ASSET_PIN');asset_bytes[name]=p.read_bytes()
 need(not dest.exists()and not dest.is_symlink(),'FRESH48_NEW_RUNTIME_OVERLAY');dest.mkdir(mode=0o700)
 for name,raw in asset_bytes.items():publish(dest/name,raw,mode=0o600)
 diff=dest/'diffs';diff.mkdir(mode=0o700)
 for name,text in output.items():
  publish(dest/name,text.encode(),mode=0o600)
  publish(diff/(name+'.diff'),''.join(difflib.unified_diff(original[name].splitlines(True),text.splitlines(True),fromfile='original/'+name,tofile='fresh48/'+name)).encode(),mode=0o600)
 result={'schema':'agensh-v2-fresh48-exact-runtime-overlay-v1','mode':mode,'scope_root':mode_root,'source_pins':pins,'installed_pins':{n:hash_file(dest/n)for n in output},'native_modules':len(output),'k3_asset_pins':assets,'old_frozen_source_modified':False,'launcher_ready':False,'model_calls':0}
 publish(dest/'RUNTIME_OVERLAY.json',wire(result));return result
