"""One exact new4/8 host-sibling scope; no arbitrary root/network widening.

Uses the already-qualified v2 scope renderer and applies ONLY4/8 roster/port
rank changes. Prompt/runtime recovery overlays remain separately pinned inputs.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
import hashlib,importlib.util,json,threading
from common import need,hash_file,publish,wire,strict
from expansion100_contract import NEW_ROOT,NEW_EID
HERE=Path(__file__).resolve().parent
PARENT=Path((_C14_SCRATCH + '/agensh-comparison-20261026'))
LOCK=threading.Lock()

def scope(public):
 need(type(public)is dict and set(public)=={'schema','manifest','deployment'}and
      public['schema']=='agensh-v2-public-host-scope-input-v1','EXP48_PUBLIC_SCOPE_FIELDS')
 need(public['manifest']=={'root':NEW_ROOT,'experiment_id':NEW_EID},'EXP48_UNIQUE_REGISTERED_ROOT')
 d=public['deployment'];need(type(d)is dict and set(d)=={'port_base'},'EXP48_PUBLIC_DEPLOYMENT_FIELDS')
 port=d['port_base'];need(type(port)is int and 1024<=port<=65518,'EXP48_EIGHTEEN_DISTINCT_PORTS')
 root=Path(NEW_ROOT)
 for w in(4,8):
  for b in(1,2,3):need(len(f'{root.name}s{w}b{b}b')<=15,'EXP48_KERNEL_BRIDGE_NAME_BOUND')
 return {'ROOT':NEW_ROOT,'BACKEND_PREFIX':str(PARENT/'v2-20261030-x48'),'REPOSITORY':'main-v2-x48',
  'PROJECT_PREFIX':'agensh-comparison-v2-20261030-x48','NAMESPACE':root.name,'PORT_BASE':port,
  'MANIFEST_SCOPE_SHA256':hashlib.sha256(wire(public['manifest'])).hexdigest()}

def build(renderer,destination,public):
 renderer=Path(renderer);pins=strict((HERE/'HOST_RENDERER_PINS.json').read_bytes())
 for name,pin in pins.items():need(hash_file(renderer/name)==pin,'EXP48_PINNED_QUALIFIED_RENDERER')
 values=scope(public);spec=importlib.util.spec_from_file_location('exp48_own_pinned_renderer',renderer/'build_host_scope.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.binding=scope
 # A fresh imported module, not monkeypatching any running host or shared module.
 with LOCK:result=m.build(public,destination)
 dest=Path(destination);changes={
  'scientific_backend_config.py':[('workers in(1,16)','workers in(4,8)')],
  'scientific_native_host.py':[('n in(1,16)','n in(4,8)')],
  'prepare_scientific_backend_infra.py':[
   ('workers in(1,16)','workers in(4,8)'),
   ('{(16,1):0,(1,1):1,(16,2):2,(1,2):3,(16,3):4,(1,3):5}',
    '{(4,1):0,(8,1):1,(4,2):2,(8,2):3,(4,3):4,(8,3):5}')]
 }
 for name,edits in changes.items():
  p=dest/name;s=p.read_text()
  for old,new in edits:
   need(s.count(old)==1,'EXP48_EXACT_HOST_ROSTER_REPLACEMENT');s=s.replace(old,new)
  compile(s,name,'exec');p.write_bytes(s.encode());p.chmod(0o600)
 result['host_files']={n:hash_file(dest/n)['sha256']for n in result['host_files']}
 result.update(schema='agensh-v2-host-scope-build-v1',expansion_setting_pair=[4,8],models=0,
               whole_runtime_ready=False,required_remaining='same validated v2 prompt/runtime overlays plus full launcher rehearsal')
 report=m.audit({n:(dest/n).read_bytes()for n in result['host_files']})
 (dest/'FULL_HOST_SCOPE_AUDIT.json').write_bytes(wire(report)+b'\n')
 (dest/'HOST_SCOPE_BUILD.json').write_bytes(wire(result)+b'\n')
 return result
