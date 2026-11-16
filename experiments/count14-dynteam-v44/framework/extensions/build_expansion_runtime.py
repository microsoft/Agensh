"""Exact public-source guard delta for cold100M+4/8, not a production launcher.

No existing frozen source is modified. Only specifically pinned public framework
modules are read. The new overlay preserves the original first-start ABI10/20;
100M is installed additively after native startup (or original50M park).
"""
from pathlib import Path
import argparse,ast,difflib,hashlib,json,os
from common import need,wire,hash_file,publish,strict
HERE=Path(__file__).resolve().parent
FILES=('manifest.py','native_scientific_owner.py','native_writer_fence.py',
       'v21_inputs.py','native_final_runtime.py','model_capacity.py','native_k3.py',
       'scientific_profile.py','r16_natural_contract.py','agensh_v2_natural.py','run_native_scientific6.py')
CP='(10000000,20000000,50000000,100000000)'

def replace(text,old,new,count=1):
 need(text.count(old)==count,'EXP100_EXACT_SOURCE_REPLACEMENT_COUNT')
 return text.replace(old,new)

def transform(name,s):
 original=s
 if name=='manifest.py':
  s=replace(s,"    for s,n in zip(m['settings'],(16,1)):",
   "    sizes=(4,8) if (m['root'],m['experiment_id'])==('/mnt/ptb-scratch2/ag30v2x48','agensh-v2-20261030-x48') or (m['root'],m['experiment_id'])==('/mnt/ptb-scratch2/ag30v2x48','agensh-v2-20261030-x48-fork16plus4') else (16,1)\n    for s,n in zip(m['settings'],sizes):")
 elif name=='native_scientific_owner.py':
  s=replace(s,"setting in ('Agensh-1','Agensh-16')\n             and len(team.roles)==(1 if setting=='Agensh-1' else 16)",
   "setting in ('Agensh-1','Agensh-4','Agensh-8','Agensh-16')\n             and len(team.roles)==int(setting.split('-')[1])")
 elif name=='native_writer_fence.py':
  s=replace(s,'len(roles) in (1,2,16)','len(roles) in (1,2,4,8,16)')
 elif name=='v21_inputs.py':
  s=replace(s,"setting in ('Agensh-16','Agensh-1')and len(d['roles'])==(16 if setting=='Agensh-16'else 1)",
   "setting in ('Agensh-1','Agensh-4','Agensh-8','Agensh-16')and len(d['roles'])==int(setting.split('-')[1])")
  s=replace(s,'(10000000,20000000)',CP,count=2)
 elif name=='native_final_runtime.py':
  s=replace(s,'[10000000,20000000]','[10000000,20000000,50000000,100000000]')
  s=replace(s,"('Agensh-16','Agensh-1')","('Agensh-1','Agensh-4','Agensh-8','Agensh-16')",count=2)
  s=replace(s,"proposals=16 if setting=='Agensh-16'else 1","proposals=int(setting.split('-')[1])")
 elif name=='model_capacity.py':
  s=replace(s,"('Agensh-16','Agensh-1')","('Agensh-1','Agensh-4','Agensh-8','Agensh-16')",count=2)
  s=replace(s,'(10000000,20000000)',CP)
 elif name=='native_k3.py':
  s=replace(s,'(10000000,20000000)',CP)
 elif name=='scientific_profile.py':
  s=replace(s,'(10000000,20000000)',CP)
 elif name=='run_native_scientific6.py':
  s=replace(s,"36+3*getattr(self,'_r16_natural_point_count',0)","getattr(self,'_authorized_regular_job_count',36)+3*getattr(self,'_r16_natural_point_count',0)")
 elif name=='agensh_v2_natural.py':
  s=replace(s,"policy['budget_tokens']==20000000","policy['budget_tokens'] in (20000000,100000000)")
  s=replace(s,"f['actual']>=20000000","f['actual']>=self.policy['budget_tokens']",count=2)
  s=replace(s,"p['target_tokens']==20000000","p['target_tokens']==self.policy['budget_tokens']")
  s=replace(s,"len(targets)==2 and targets==[10000000,20000000]","targets==[10000000,20000000] if self.policy['budget_tokens']==20000000 else targets in ([10000000,20000000,50000000,100000000],[10000000,16000000,20000000,50000000,100000000])")
  s=replace(s,"max(0,20000000-f['actual']-f['reserved'])","max(0,self.policy['budget_tokens']-f['actual']-f['reserved'])")
 elif name=='r16_natural_contract.py':
  s=replace(s,'actual<20000000','actual<100000000')
  s=replace(s,'(10000000,20000000)',CP)
 else:need(False,'EXP100_FIXED_PUBLIC_SOURCE_SET')
 need(s!=original,'EXP100_SOURCE_DELTA_REQUIRED');compile(s,name,'exec');return s

def build(source,destination):
 source=Path(source);dest=Path(destination)
 need(source.resolve()==source and source.is_dir(),'EXP100_CANONICAL_PUBLIC_BASELINE')
 pins=strict((HERE/'BASELINE_PINS.json').read_bytes())
 contents={}
 for name in FILES:
  p=source/name
  need(not p.is_symlink()and hash_file(p)==pins[name],'EXP100_PINNED_PUBLIC_BASELINE_MODULE')
  contents[name]=p.read_text()
 # Complete source validation before any output; no partial compatibility claim.
 generated={name:transform(name,text)for name,text in contents.items()}
 need(not dest.exists()and not dest.is_symlink(),'EXP100_FRESH_OVERLAY_DIRECTORY')
 dest.mkdir(mode=0o700,parents=False);diffs=dest/'diffs';diffs.mkdir(mode=0o700)
 for name,text in generated.items():
  publish(dest/name,text.encode(),mode=0o600)
  patch=''.join(difflib.unified_diff(contents[name].splitlines(True),text.splitlines(True),fromfile='original/'+name,tofile='100m/'+name))
  publish(diffs/(name+'.diff'),patch.encode(),mode=0o600)
 report={'schema':'agensh-v2-100m-exact-public-runtime-overlay-v1','original_source_pins':pins,
         'source_pins':{n:hash_file(dest/n)for n in generated},'old_frozen_sources_modified':False,
         'startup_budget_manifest_abi':'unchanged20M;100M-by-additive-authorization',
         'scientific_prompts_changed':False,'candidate_rule_changed':False,'rng_algorithm_changed':False,
         'processes_started':0,'models':0,'production_ready':False,
         'required_remaining':'same-session disk SEARCH takeover and qualified launcher integration'}
 publish(dest/'RUNTIME_DELTA.json',wire(report),mode=0o600);return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--destination',required=True);a=p.parse_args()
 print(json.dumps(build(a.source,a.destination),sort_keys=True))
if __name__=='__main__':main()
