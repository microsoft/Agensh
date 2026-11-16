"""Exactly two isolated launch modes. Neither accepts arbitrary roots.

Dry mode is its own process and generated contract module, never a global
monkeypatch of a live production owner. Short fixed namespace obeys IFNAMSIZ.
"""
from pathlib import Path
import hashlib,importlib.util,threading
from common import need,hash_file,publish,wire,strict
import build_x48_host as BASE
NEW_ROOT='/mnt/ptb-scratch2/ag30v2x48'
NEW_EID='agensh-v2-20261030-x48'
HERE=Path(__file__).resolve().parent
DRY_ROOT='/mnt/ptb-scratch2/ag30x48g'
DRY_EID='agensh-v2-20261030-x48-dry4'
PROFILES={'production':(NEW_ROOT,NEW_EID),'zero-model':(DRY_ROOT,DRY_EID)}
CONTRACT_SHA='7d8522ae0e3bf4d5754c4fb79d6f5286c0f1cbf48dcba403b676a2a92812856d'
LOCK=threading.Lock()

def selected(mode):
 need(mode in PROFILES,'FRESH48_FIXED_DEPLOYMENT_MODE')
 return PROFILES[mode]

def public_scope(mode,port_base):
 root,eid=selected(mode)
 return {'schema':'agensh-v2-public-host-scope-input-v1','manifest':{'root':root,'experiment_id':eid},
         'deployment':{'port_base':port_base}}

def binding(public,mode):
 root,eid=selected(mode)
 need(type(public)is dict and set(public)=={'schema','manifest','deployment'}and
   public['schema']=='agensh-v2-public-host-scope-input-v1'and
   public['manifest']=={'root':root,'experiment_id':eid},'FRESH48_EXACT_MODE_ROOT_EID')
 d=public['deployment'];need(type(d)is dict and set(d)=={'port_base'},'FRESH48_PORT_FIELDS')
 port=d['port_base'];need(type(port)is int and 1024<=port<=65518,'FRESH48_PORT18_BOUND')
 for w in(4,8):
  for b in(1,2,3):need(len(f'{Path(root).name}s{w}b{b}b')<=15,'FRESH48_KERNEL_IFNAMSIZ')
 suffix=''if mode=='production'else'-dry4'
 return {'ROOT':root,'BACKEND_PREFIX':str(BASE.PARENT/('v2-20261030-x48'+suffix)),
 'REPOSITORY':'main-v2-x48'+suffix,'PROJECT_PREFIX':'agensh-comparison-v2-20261030-x48'+suffix,
 'NAMESPACE':Path(root).name,'PORT_BASE':port,'MANIFEST_SCOPE_SHA256':hashlib.sha256(wire(public['manifest'])).hexdigest()}

def host(renderer,destination,public,*,mode):
 binding(public,mode)
 # Fresh imported private renderer module. No change to BASE.scope or sys.modules
 # of a live owner. Its source pin/roster guards remain the frozen P original.
 path=Path(BASE.__file__);spec=importlib.util.spec_from_file_location('fresh48_fixed_scope_renderer',path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.scope=lambda p:binding(p,mode)
 with LOCK:result=module.build(renderer,destination,public)
 need(result['scope']==binding(public,mode),'FRESH48_RENDERER_EXACT_SELECTED_SCOPE')
 return result

def contract(destination,*,mode):
 """One fixed module per process. Production source bytes unchanged."""
 root,eid=selected(mode);p=Path(BASE.HERE/'expansion100_contract.py')
 need(hash_file(p)['sha256']==CONTRACT_SHA,'FRESH48_PINNED_AUTHORIZATION_SOURCE')
 raw=p.read_text()
 if mode=='zero-model':
  for old,new in((f"NEW_ROOT={NEW_ROOT!r}",f"NEW_ROOT={root!r}"),(f"NEW_EID={NEW_EID!r}",f"NEW_EID={eid!r}")):
   need(raw.count(old)==1,'FRESH48_EXACT_TWO_DRY_SCOPE_LITERALS');raw=raw.replace(old,new)
 compile(raw,'expansion100_contract.py','exec')
 dest=Path(destination);need(not dest.exists()and not dest.is_symlink(),'FRESH48_NEW_MODE_MODULE_DIRECTORY')
 dest.mkdir(mode=0o700);publish(dest/'expansion100_contract.py',raw.encode(),mode=0o600)
 receipt={'schema':'agensh-v2-fresh48-fixed-mode-contract-v1','mode':mode,'root':root,'experiment_id':eid,
  'source_sha256':CONTRACT_SHA,'installed_sha256':hash_file(dest/'expansion100_contract.py')['sha256'],
  'arbitrary_root_accepted':False,'models':0,'production_contract_changed':False}
 publish(dest/'FIXED_MODE.json',wire(receipt));return receipt
