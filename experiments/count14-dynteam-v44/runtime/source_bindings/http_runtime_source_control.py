"""Secret-free original HTTP constructor controls, exact live old source only.

The one private reader below is FRAMEWORK RUNTIME, not a coordinator CLI or
forensic tool: only original registered local-relay URL/bearer scalars are
selected, compared/used in memory and NEVER returned by the public capability.
Provider key, Docker Env, SDK/scientific/private-context/continuation bodies
are neither read nor hashed. New-owner typed proof reuses kernel/native/T and
retired-services, both births and the original three locks.
"""
from dataclasses import asdict,dataclass
from pathlib import Path
from types import FunctionType,CodeType
import copy
import hashlib
import importlib
import importlib.util
import math
import os
import re
import stat
import threading
import urllib.parse

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
from original_relay_core import OriginalRelayCore
from scientific_relay import ScientificRelay,ScientificUsage,Bounds,PrivateStates
from feasibility_relay import ChatTransport
from scientific_profile import SearchProfile
from native_scientific_http import NativeScientificHttpServer
from native_network_binding import NativeNetworkBinding
from native_beta_layout import native_aliases
from new_scope_profile import original_search_profile
from dynteam_relay_binding import install as install_affinity
from glm_session_header import HeaderOpener,REVISION
import kernel_control_source_supplement as K
import financial_runtime_source_control as F

SCHEMA='count14-http-runtime-public-source-controls-v1'
CONTROL='count14-original-http-public-constructor-controls-v1'
ISSUED='count14-http-runtime-source-ISSUED-v1'
LEAF='normal-http-runtime-source-control-v1'
OWN_LEAF='OWN-http-runtime-source-component-v1'
SELECTED_SHA='dc136c2df6e39d27b4ccb5b0c770675e85d523013933f97962a0005f7c2891f2'
PINS=dict(kernel_control_source_supplement='8fb3300c24ade2a62d3e59d134eb4d988b80166ee993be2b9ecd4c25dab9a54e',
 original_relay_core='89ac900e66caa67887504522c574c1870f7a8faf51542fe248ca7f35b1541556',
 scientific_relay='8b50d9de9106d5dd1314dec305189691cbcb7e7a2269fa6b54821f7c860d4c1e',
 feasibility_relay='1f8057eeea4e6ce921c870f0ead6f663b92171d8b76f01e1ebcb62c167e12add',
 scientific_profile='3388e76335752ad2e76231a93f798dc418c6a88f8be5c2cb6d5d0541dea9976c',
 new_scope_profile='06b3475f3a8f9bdfda13655b4186d2b5df80ff57e32ec5af4cd31bb183ed528a',
 native_network_binding='d0f12d65aa2d2bc3ae1a54e76371778b6766008fdb2b0f591ba421c1e0dc8f17',
 native_beta_layout='92a22647dc030a222f053b1ee6d6a0a0f673f617b49b234ca9382790a7be055a',
 native_cold_exports='732a86ad824403fef9a99c8193c34c68166ead1c937d2710187aa4ec3cfa2114',
 dynteam_relay_binding='613aeee228ec9ecf1fdc3d3c8aec7a9e606f604308dfae7adf3ba5295b889fb4',
 glm_session_header='00e3a17daef62bba2bdb17960b762ecb9e301ead6e93aa15e535b6ebe5264d40',
 native_scientific_http='eb08ff0d770f2609f24e568d4724e427dbde0b5327e7067d70759f0855e789d3')
_SEAL=object()
_CAPTURES={}
_PUBLICATIONS={}
_VERIFIED={}


def budget(value):
 M.need(type(value)is ReadBudget,'HTTP_SOURCE_FINITE_CONTROL_READ_BUDGET');value.check()


def verify_sources():
 for name,pin in PINS.items():
  p=Path(importlib.import_module(name).__file__)
  M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and hashlib.sha256(p.read_bytes()).hexdigest()==pin,
   'HTTP_SOURCE_EXACT_FROZEN_ORIGINAL_FRAMEWORK_PINS')
 K.verify_sources();return dict(PINS)


def _clone(fn,**bindings):
 out=FunctionType(fn.__code__,dict(fn.__globals__,**bindings),fn.__name__,fn.__defaults__,fn.__closure__)
 out.__kwdefaults__=fn.__kwdefaults__;return out


def _self_pin():return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _selected_reader():
 root=Path(importlib.import_module('original_relay_core').__file__).resolve().parents[1]
 p=root/'original-v2-resource-observer-v1/selected_numeric.py'
 M.need(p.resolve()==p and not p.is_symlink()and hashlib.sha256(p.read_bytes()).hexdigest()==SELECTED_SHA,
  'HTTP_SOURCE_ORIGINAL_FIXED_SCALAR_SKIP_PARSER_PIN')
 spec=importlib.util.spec_from_file_location('HTTP_SOURCE_fixed_selected_parser',p)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module.SelectedJSON


def file_identity(path,*,own):
 """Stat only. In particular do not hash a private overlay/continuation DB."""
 p=Path(path);s=p.lstat()
 M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)and
  s.st_uid==s.st_gid==(os.geteuid()if own else 0)and s.st_nlink==1 and not s.st_mode&0o077,
  'HTTP_SOURCE_CANONICAL_ORIGINAL_PRIVATE_REGULAR_FILE_STAT_ONLY')
 return dict(path=str(p),device=s.st_dev,inode=s.st_ino,uid=s.st_uid,gid=s.st_gid,mode=stat.S_IMODE(s.st_mode),
  nlink=s.st_nlink,size=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)


def _directory(row,*,own):
 p=M.existing(row,directory=True)
 M.need(row['uid']==row['gid']==(os.geteuid()if own else 0)and row['mode']==0o700,
  'HTTP_SOURCE_ORIGINAL_PRIVATE_DIRECTORY_OWNER_MODE');return p


def read_registered_local_routes(saved,*,contract,read_budget):
 """Trusted runtime-only fixed original export reader, NEVER print return.

 Select only pre-registered agent environment local relay URL/API_KEY. Every
 unselected value is skipped without JSON decode/materialization. No provider
 credential or Docker environment API is used. Return is ephemeral private
 runtime input for original HTTP constructor, not source PUBLIC material.
 """
 budget(read_budget)
 M.need(type(saved)is dict and type(contract)is dict,'HTTP_SOURCE_FIXED_REGISTERED_ROUTE_METADATA_ONLY')
 matches=[r for r in contract['trajectories']if r['trajectory_id']==saved['trajectory']]
 M.need(len(matches)==1,'HTTP_SOURCE_ONE_REGISTERED_TRAJECTORY');row=matches[0]
 network=NativeNetworkBinding(**saved['network']);own=network.qualification_only
 network.checked(contract=contract,row=row,qualification_only=own)
 root=_directory(saved['registered_export_directory'],own=own)
 M.need(root==Path(row['root'])/'native-cold-exports'and saved['local_route_equivalence']is True,
  'HTTP_SOURCE_ONLY_ORIGINAL_REGISTERED_NATIVE_EXPORT_DIRECTORY')
 reference=saved['private_overlay'];path=root/'compose.private-overlay.json'
 M.need(reference==file_identity(path,own=own)and reference['mode']==0o400 and 0<reference['size']<=8*1024*1024,
  'HTTP_SOURCE_EXACT_ORIGINAL_GENERATED_ROOT0400_OVERLAY_INODE_NO_HASH')
 address=tuple(saved['listener_address'])
 M.need(len(address)==2 and address[0]==network.gateway and type(address[1])is int and 0<address[1]<=65535,
  'HTTP_SOURCE_EXACT_ORIGINAL_PRIVATE_LISTENER_ADDRESS')
 aliases=native_aliases(row['arm'])
 M.need(set(aliases)==set(row['roles']),'HTTP_SOURCE_FROZEN_ORIGINAL_ALL_ROLE_ALIASES')
 agents={v['agent_service']:role for role,v in aliases.items()}
 expected_services=set(agents)|{v['router_service']for v in aliases.values()}
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  M.need(file_identity(path,own=own)==reference and
   (os.fstat(fd).st_dev,os.fstat(fd).st_ino)==(reference['device'],reference['inode']),
   'HTTP_SOURCE_ORIGINAL_PRIVATE_EXPORT_OPEN_FD')
  parts=[];count=0
  while count<reference['size']:
   read_budget.check();part=os.read(fd,min(1024*1024,reference['size']-count))
   M.need(bool(part),'HTTP_SOURCE_COMPLETE_FIXED_EXPORT_BYTES');parts.append(part);count+=len(part)
  M.need(os.read(fd,1)==b''and file_identity(path,own=own)==reference and
   (os.fstat(fd).st_dev,os.fstat(fd).st_ino,os.fstat(fd).st_size)==
   (reference['device'],reference['inode'],reference['size']),'HTTP_SOURCE_PRIVATE_EXPORT_FD_STABLE')
 finally:os.close(fd)
 parser=_selected_reader()(b''.join(parts).decode('utf-8','strict'));selected={};service_names=set()
 def obj(callback):
  parser.char('{');seen=set();parser.ws();parser.depth+=1
  M.need(parser.depth<=64,'HTTP_SOURCE_BOUNDED_FIXED_EXPORT_NESTING')
  if parser.i<len(parser.text)and parser.text[parser.i]=='}':parser.i+=1;parser.depth-=1;return
  while True:
   read_budget.check();start=parser.i;parser.string_end();key=parser.decoder.decode(parser.text[start:parser.i])
   M.need(key not in seen and len(seen)<1024,'HTTP_SOURCE_NO_DUPLICATE_OR_EXCESS_CONTROL_KEYS');seen.add(key)
   parser.char(':');parser.ws();callback(key);parser.ws()
   M.need(parser.i<len(parser.text),'HTTP_SOURCE_COMPLETE_EXPORT_CONTROL_OBJECT')
   if parser.text[parser.i]=='}':parser.i+=1;parser.depth-=1;return
   parser.char(',');parser.ws()
 def scalar(limit):
  start=parser.i;parser.string_end();raw=parser.text[start:parser.i]
  M.need(len(raw)<=limit,'HTTP_SOURCE_BOUNDED_SELECTED_LOCAL_CONTROL_STRING')
  value=parser.decoder.decode(raw);M.need(type(value)is str,'HTTP_SOURCE_LOCAL_CONTROL_STRING');return value
 def service(name):
  M.need(name in expected_services,'HTTP_SOURCE_NO_UNREGISTERED_OR_EXTRA_NATIVE_SERVICE')
  service_names.add(name)
  if name not in agents:parser.skip();return
  fields={}
  def environment(key):
   if key in('COPILOT_PROVIDER_BASE_URL','COPILOT_PROVIDER_API_KEY'):fields[key]=scalar(4096 if key.endswith('URL')else 1024)
   else:parser.skip()
  def control(key):
   M.need(key in('environment','volumes','labels','command','healthcheck'),
    'HTTP_SOURCE_ORIGINAL_GENERATED_AGENT_SERVICE_SCHEMA')
   if key=='environment':obj(environment)
   else:parser.skip()
  obj(control)
  M.need(set(fields)=={'COPILOT_PROVIDER_BASE_URL','COPILOT_PROVIDER_API_KEY'},
   'HTTP_SOURCE_BOTH_ORIGINAL_LOCAL_RELAY_CONTROL_FIELDS_REQUIRED')
  M.need(fields['COPILOT_PROVIDER_BASE_URL']==f'http://{address[0]}:{address[1]}/v1'and
   re.fullmatch('[A-Za-z0-9_-]{32,512}',fields['COPILOT_PROVIDER_API_KEY'])is not None,
   'HTTP_SOURCE_LOCAL_RELAY_ADDRESS_AND_PRIVATE_BEARER_SHAPE')
  selected[agents[name]]=fields['COPILOT_PROVIDER_API_KEY']
 top=set()
 def field(key):
  M.need(key in('services','networks'),'HTTP_SOURCE_ORIGINAL_GENERATED_OVERLAY_SCHEMA')
  top.add(key)
  if key=='services':obj(service)
  else:parser.skip()
 obj(field);parser.ws()
 M.need(parser.i==len(parser.text)and top=={'services','networks'}and service_names==expected_services and
  set(selected)==set(aliases)and len(set(selected.values()))==len(aliases),
  'HTTP_SOURCE_EXACT_COMPLETE_ROLE_SERVICE_SCHEMA_AND_UNIQUE_LOCAL_ROUTES')
 M.need(file_identity(path,own=own)==reference,'HTTP_SOURCE_PRIVATE_EXPORT_STILL_SAME_AFTER_SCALAR_PROJECTION')
 read_budget.check()
 return address,{token:(row['trajectory_id'],role)for role,token in selected.items()}


def _inner(function,name):
 values=[c for c in function.__code__.co_consts if type(c)is CodeType and c.co_name==name]
 M.need(len(values)==1,'HTTP_SOURCE_EXACT_ORIGINAL_NESTED_FRAMEWORK_FUNCTION');return values[0]


def _cell(function,name):
 M.need(type(function)is FunctionType and name in function.__code__.co_freevars,
  'HTTP_SOURCE_EXACT_ORIGINAL_PUBLIC_TRANSPORT_CLOSURE')
 return function.__closure__[function.__code__.co_freevars.index(name)].cell_contents


def _validate(controls):
 M.need(type(controls)is dict and set(controls)=={'schema','OWN','source_owner_birth','contract_sha256','catalogues',
  'profile','trajectories','private_route_payload_or_bearer_exported','scientific_body_or_continuation_database_read_or_hash',
  'same_listener_and_local_bearer_required','models_or_tools_clear_asserted'}and controls['schema']==CONTROL and
  type(controls['OWN'])is bool and controls['private_route_payload_or_bearer_exported']is
  controls['scientific_body_or_continuation_database_read_or_hash']is controls['models_or_tools_clear_asserted']is False and
  controls['same_listener_and_local_bearer_required']is True,'HTTP_SOURCE_EXACT_SECRET_FREE_CONTROL_SCHEMA')
 M.birth(controls['source_owner_birth']);M.sha(controls['contract_sha256'])
 profile=controls['profile']
 M.need(type(profile)is dict and set(profile)=={'policy','sha256'}and set(profile['policy'])==SearchProfile.FIELDS and
  M.digest(profile['policy'])==profile['sha256'],'HTTP_SOURCE_ORIGINAL_PUBLIC_MODEL_POLICY_ONLY')
 seen=set()
 for row in controls['trajectories']:
  M.need(type(row)is dict and set(row)=={'trajectory','network','continuation_directory','continuation_database',
   'model','max_output','max_states','max_inflight','global_allocated_cap','bounds','transport',
   'listener_address','listener_identity_sha256','registered_export_directory','private_overlay',
   'local_route_equivalence','header'},'HTTP_SOURCE_EXACT_PUBLIC_CONSTRUCTOR_ROW')
  t=row['trajectory'];M.need(t in controls['catalogues']and t not in seen,'HTTP_SOURCE_EXACT_UNIQUE_TRAJECTORIES');seen.add(t)
  M.need(row['model']==profile['policy']['model']and
   (row['max_output']is None or type(row['max_output'])is int and row['max_output']>0)and
   row['max_states']==100000 and row['max_inflight']==13 and row['global_allocated_cap']==96 and
   row['local_route_equivalence']is True,'HTTP_SOURCE_ORIGINAL_MODEL_OUTPUT_AND_CAPACITY_CONTROLS')
  b=row['bounds'];M.need(set(b)=={'proof','sha256'},'HTTP_SOURCE_ORIGINAL_BOUNDS_CONTROL')
  bound=Bounds(b['proof'],b['sha256']);M.need(bound.matches_model(row['model'])and
   ((bound.context_limit is not None and row['max_output']is None)or
    (bound.context_limit is None and type(row['max_output'])is int and
     row['max_output']<=b['proof']['maximum_output_tokens'])),
   'HTTP_SOURCE_BOUNDS_AND_MAXIMUM_OUTPUT_MATCH')
  transport=row['transport'];M.need(set(transport)=={'url','auth_style','timeout'}and
   type(transport['url'])is str and transport['url'].endswith('/v1/chat/completions')and
   transport['auth_style']=='bearer'and type(transport['timeout'])in(int,float)and
   math.isfinite(transport['timeout'])and 0<transport['timeout']<=86400,'HTTP_SOURCE_PUBLIC_ORIGINAL_CHAT_TRANSPORT_CONFIG')
  u=urllib.parse.urlsplit(transport['url']);M.need(u.scheme in('http','https')and u.hostname and
   not u.username and not u.password and not u.query and not u.fragment,'HTTP_SOURCE_TRANSPORT_URL_WITHOUT_SECRET_FIELDS')
  M.need(row['header']==dict(revision=REVISION,affinity_installed=True,key_path_exported=False),
   'HTTP_SOURCE_ORIGINAL_ROTATING_KEY_AND_SESSION_HEADER_INSTALLED')
  M.sha(row['listener_identity_sha256'])
 M.need(seen==set(controls['catalogues']),'HTTP_SOURCE_ALL_ORIGINAL_TRAJECTORIES_REQUIRED');return controls


def _controls(core,*,read_budget,own):
 budget(read_budget);K.N._unlocked(core);verify_sources()
 M.need(type(core)is OriginalRelayCore and core.qualification_only is own and
  type(core.profile)is SearchProfile and core.profile._dynteam_contract_sha256==M.digest(core.contract)and
  set(core.engines)==set(core.servers)==set(core.native_networks)==set(core.tokens)==set(core.rows),
  'HTTP_SOURCE_REAL_ORIGINAL_COMPLETE_ENGINE_SERVER_NETWORK_GRAPH')
 p=core.profile;M.need(set(p.policy)==SearchProfile.FIELDS and M.digest(p.policy)==p.sha,
  'HTTP_SOURCE_ONLY_ORIGINAL_PUBLIC_MODEL_POLICY')
 original_search_profile(core.contract,p.policy,original_policy_sha256=p.sha)
 exports=core.cold_native_exports
 M.need(type(exports)is dict and exports['state']=='EXPORTED_HELD_NOT_DOCKER_OR_SCIENTIFIC_PREPARED'and
  set(exports['trajectories'])==set(core.rows)and exports['root']==str(core.home/'cold-native-exports'),
  'HTTP_SOURCE_ORIGINAL_REGISTERED_EXPORT_GRAPH_NOT_CALLER_PATH')
 _directory(M.descriptor(core.home/'cold-native-exports'),own=own)
 rows=[]
 for t,row in sorted(core.rows.items()):
  read_budget.check();engine=core.engines[t];server=core.servers[t];network=core.native_networks[t]
  M.need(type(engine)is ScientificRelay and engine.budget is core.ledger and
   type(engine.ledger)is ScientificUsage and engine.ledger.ledger is core.ledger and
   engine.profile is engine.ledger.profile is p and engine.ledger.admission_gate is core.gate and
   engine.ledger.global_cap==96 and engine.ledger.tool_parents is None and engine.tool_terminal_port is None and
   engine.request_limit is None and type(engine.capacity)is threading.BoundedSemaphore and
   engine.capacity._initial_value==13 and engine.max_states==100000 and engine.model==p.policy['model'],
   'HTTP_SOURCE_EXACT_ORIGINAL_ENGINE_USAGE_PROFILE_GATE_AND_INITIAL_CAPACITY')
  M.need(type(server)is NativeScientificHttpServer and server.engine is engine and server.ledger is core.ledger and
   server.gate is core.gate and engine.native_http_custodian is server and
   server.registered==frozenset((t,role)for role in row['roles'])and server.closed is True and
   server.network_closed is True and server.listener_stopped is True,
   'HTTP_SOURCE_EXACT_REGISTERED_OLD_RETIRED_HTTP_CUSTODIAN_NO_BEARER_EXPORT')
  network.checked(contract=core.contract,row=row,qualification_only=own)
  usage=engine.ledger;bounds=usage.bounds
  M.need(type(bounds)is Bounds and set(bounds.proof)in(Bounds.FIELDS,Bounds.CONFIGURED_FIELDS,Bounds.CONTEXT_FIELDS)and
   M.digest(bounds.proof)==bounds.sha,'HTTP_SOURCE_EXACT_ORIGINAL_PUBLIC_RESERVATION_BOUNDS')
  Bounds(bounds.proof,bounds.sha)
  M.need(engine.transport.__code__==_inner(ScientificRelay.__init__,'trusted_transport')and
   engine.transport.__globals__ is ScientificRelay.__init__.__globals__ and _cell(engine.transport,'usage')is usage,
   'HTTP_SOURCE_ORIGINAL_TRANSPORT_BODY_AND_USAGE_CLOSURE_UNCHANGED')
  raw=_cell(engine.transport,'transport') # Do not inspect any other closure value or raw.token.
  M.need(type(raw)is ChatTransport and raw.auth_style=='bearer'and type(raw.opener)is HeaderOpener and
   raw.opener.url==raw.url and getattr(engine,'_dynteam_affinity_installed',None)is True and
   engine._fresh48_session_guard is core.sessions and
   engine.run.__func__.__code__==_inner(install_affinity,'request_bound_run'),
   'HTTP_SOURCE_ORIGINAL_RAW_TRANSPORT_ROTATING_HEADER_AND_SESSION_AFFINITY')
  directory=Path(engine.private_home)
  M.need(type(engine.continuations)is PrivateStates and engine.states is engine.continuations and
   directory==core.home/'continuations'/M.digest(t),'HTTP_SOURCE_EXACT_ORIGINAL_CONTINUATION_DIRECTORY_ONLY')
  _directory(M.descriptor(directory),own=own)
  database=file_identity(directory/'continuations.sqlite',own=own)
  M.need(database['mode']==0o600,'HTTP_SOURCE_ORIGINAL_CONTINUATION_DB_STAT_NOT_CONTENT')
  export=exports['trajectories'][t];export_dir=Path(export['directory'])
  aliases=native_aliases(row['arm'])
  M.need(export_dir==Path(row['root'])/'native-cold-exports'and export['native_roles']==len(row['roles'])and
   set(export['role_exports'])==set(aliases)and all(
    export['role_exports'][role]['agent_control_directory']==str(export_dir/'native-agent-control-exports'/role)and
    export['role_exports'][role]['router_control_directory']==str(export_dir/'native-private-exports'/role)
    for role in aliases),
   'HTTP_SOURCE_EXACT_REGISTERED_ORIGINAL_EXPORT_RECORD')
  saved=dict(trajectory=t,network=asdict(network),continuation_directory=M.descriptor(directory),
   continuation_database=database,model=engine.model,max_output=engine.max_output,max_states=engine.max_states,
   max_inflight=engine.capacity._initial_value,global_allocated_cap=usage.global_cap,
   bounds=dict(proof=copy.deepcopy(bounds.proof),sha256=bounds.sha),
   transport=dict(url=raw.url,auth_style=raw.auth_style,timeout=raw.timeout),
   listener_address=list(server.server_address),listener_identity_sha256=server.listener_identity_sha256,
   registered_export_directory=M.descriptor(export_dir),private_overlay=file_identity(export_dir/'compose.private-overlay.json',own=own),
   local_route_equivalence=True,header=dict(revision=REVISION,affinity_installed=True,key_path_exported=False))
  address,identities=read_registered_local_routes(saved,contract=core.contract,read_budget=read_budget)
  M.need(address==server.server_address and identities==core.tokens[t],
   'HTTP_SOURCE_REGISTERED_PRIVATE_LOCAL_ROUTES_EQUAL_ORIGINAL_RAM_TOKENS_AND_LISTENER')
  rows.append(saved) # No token/Env/private overlay body or hash enters this PUBLIC value.
 controls=dict(schema=CONTROL,OWN=own,source_owner_birth=asdict(process_birth(os.getpid())),
  contract_sha256=M.digest(core.contract),catalogues={t:list(r['roles'])for t,r in core.rows.items()},
  profile=dict(policy=copy.deepcopy(p.policy),sha256=p.sha),trajectories=rows,
  private_route_payload_or_bearer_exported=False,scientific_body_or_continuation_database_read_or_hash=False,
  same_listener_and_local_bearer_required=True,models_or_tools_clear_asserted=False)
 return _validate(controls)


@dataclass(frozen=True,repr=False)
class CapturedHttpControls:
 core:object
 OWN:bool
 controls:dict
 _seal:object
 def snapshot(self):
  M.need(self._seal is _SEAL and _CAPTURES.get(id(self.core))is self,'HTTP_SOURCE_REGISTERED_CAPTURE')
  return copy.deepcopy(self.controls)


def _capture(core,*,read_budget,own):
 M.need(id(core)not in _CAPTURES,'HTTP_SOURCE_ONE_LIVE_SOURCE_CAPTURE')
 before=_controls(core,read_budget=read_budget,own=own)
 M.need(_controls(core,read_budget=read_budget,own=own)==before,'HTTP_SOURCE_PUBLIC_RUNTIME_CONTROLS_CHANGED_WAIT')
 value=CapturedHttpControls(core,own,before,_SEAL);_CAPTURES[id(core)]=value;return value


def capture_OWN_components(core,*,read_budget):return _capture(core,read_budget=read_budget,own=True)


class HttpSourceReference:
 __slots__=('_path','_pin','_seal')
 def __init__(self,*a,**k):raise M.PaidColdWait('HTTP_SOURCE_FIXED_REFERENCE_LOADER_ONLY')
 def __setattr__(self,n,v):
  M.need(not hasattr(self,'_seal'),'HTTP_SOURCE_IMMUTABLE_REFERENCE');object.__setattr__(self,n,v)
 @property
 def path(self):return self._path
 @property
 def sha256(self):return self._pin


class OWNHttpReference(HttpSourceReference):__slots__=()


def _reference(path,pin,*,own):
 p=Path(path);M.need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and p.name=='SOURCE.json'and
  p.parent.name==(OWN_LEAF if own else LEAF),'HTTP_SOURCE_FIXED_ORIGINAL_REFERENCE_NAMESPACE')
 value=object.__new__(OWNHttpReference if own else HttpSourceReference)
 value._path,value._pin,value._seal=str(p),M.sha(pin),_SEAL;return value


def load_reference(path,sha256):return _reference(path,sha256,own=False)
def load_OWN_reference(path,sha256):return _reference(path,sha256,own=True)


def _plumbing(function):
 """Same fixed O_EXCL metadata codec body, new namespace/types/validator only."""
 return _clone(function,SCHEMA=SCHEMA,ISSUED=ISSUED,LEAF=LEAF,OWN_LEAF=OWN_LEAF,_SEAL=_SEAL,
  PINS=PINS,_self_pin=_self_pin,verify_sources=verify_sources,_validate=_validate,
  KernelSourceReference=HttpSourceReference,OWNKernelReference=OWNHttpReference)


def _complete(core,body,*,own,final_guard):return _plumbing(K._complete)(core,body,own=own,final_guard=final_guard)
def _read_complete(reference,home,*,read_budget,own):
 return _plumbing(K._read_complete)(reference,home,read_budget=read_budget,own=own)


def publish_registered(owner,*,read_budget):
 """Exact LIVE SOURCE after original kernel/native/T/services publication."""
 budget(read_budget);issuer,ticket_body,storage,locks,retirement=F._source(owner,read_budget)
 core=owner.core;K.N._unlocked(core);verify_sources();registered=K._PUBLICATIONS.get(id(owner))
 M.need(type(registered)is dict and registered.get('owner')is owner and registered.get('reference')is not None and
  id(owner)not in _PUBLICATIONS,'HTTP_SOURCE_EXISTING_SAME_LIVE_KERNEL_CONTROL_PUBLICATION_NO_RETRY')
 saved=registered['reference'];kernel=K.load_reference(saved['path'],saved['sha256'])
 original,_=K._read_complete(kernel,core.home,read_budget=read_budget,own=False)
 M.need(original['source_owner_birth']==asdict(process_birth(os.getpid()))and
  set(retirement['listeners'])=={s.listener_identity_sha256 for s in core.servers.values()}and
  set(owner.normal_transport_retirement.servers)==set(core.servers.values()),
  'HTTP_SOURCE_ORIGINAL_KERNEL_CHAIN_AND_TRUE_PHYSICALLY_RETIRED_HTTP_SET')
 captured=_capture(core,read_budget=read_budget,own=False);controls=captured.snapshot()
 db=F._db_controls(core.ledger.home/'ledger.sqlite',core.queue.home/'queue.sqlite',read_budget)
 M.need(db==original['current_fixed_db_controls'],'HTTP_SOURCE_FIXED_FINANCIAL_CONTROLS_UNCHANGED')
 body=dict(source_owner_birth=controls['source_owner_birth'],contract_sha256=M.digest(core.contract),
  controls=controls,controls_sha256=M.digest(controls),kernel_reference=dict(path=kernel.path,sha256=kernel.sha256),
  current_fixed_db_controls=db,production_source_binding=True)
 def final():
  again,tb,ss,ll,rr=F._source(owner,read_budget)
  M.need(again is issuer and tb==ticket_body and ss==storage and ll==locks and rr==retirement and
   _controls(core,read_budget=read_budget,own=False)==controls and
   K._read_complete(kernel,core.home,read_budget=read_budget,own=False)[0]==original and
   F._db_controls(core.ledger.home/'ledger.sqlite',core.queue.home/'queue.sqlite',read_budget)==db,
   'HTTP_SOURCE_ORIGINAL_RUNTIME_OR_T_KERNEL_FINANCIAL_CONTROLS_CHANGED_RETAIN_UNISSUED')
 _PUBLICATIONS[id(owner)]=dict(owner=owner,capture=captured)
 result=_complete(core,body,own=False,final_guard=final);_PUBLICATIONS[id(owner)]['reference']=copy.deepcopy(result)
 return result


class VerifiedHttpRuntimeControls:
 __slots__=('_body','_controls','_reference','_seal','kernel_capability','source_owner','source_ticket',
  'old_owner_birth','new_owner_birth','contract_sha256','lock_fds')
 def __init__(self,*a,**k):raise M.PaidColdWait('HTTP_SOURCE_ONLY_TYPED_CROSS_BIRTH_VERIFIER')
 def __setattr__(self,n,v):
  M.need(not hasattr(self,'_seal'),'HTTP_SOURCE_IMMUTABLE_VERIFIED_CAP');object.__setattr__(self,n,v)
 def snapshot(self):
  M.need(self._seal is _SEAL and _VERIFIED.get(id(self))is self,'HTTP_SOURCE_EXACT_VERIFIED_CAP_SEAL')
  return copy.deepcopy(self._controls)


def verify_reference(reference,*,kernel_reference,native_reference,owner,ticket,read_budget):
 budget(read_budget);verify_sources()
 M.need(type(reference)is HttpSourceReference and reference._seal is _SEAL,
  'HTTP_SOURCE_TYPED_PRODUCTION_REFERENCE_NOT_OWN_OR_BOOL')
 kernel=K.verify_reference(kernel_reference,native_reference=native_reference,owner=owner,ticket=ticket,read_budget=read_budget)
 body,record=_read_complete(reference,owner.core.home,read_budget=read_budget,own=False)
 M.need(type(kernel)is K.VerifiedKernelControls and body['production_source_binding']is True and
  body['kernel_reference']==dict(path=kernel_reference.path,sha256=kernel_reference.sha256)and
  body['source_owner_birth']==asdict(kernel.old_owner_birth)and body['contract_sha256']==kernel.contract_sha256 and
  body['current_fixed_db_controls']==kernel._body['current_fixed_db_controls']and
  body['controls']['catalogues']=={t:list(r['roles'])for t,r in owner.core.rows.items()},
  'HTTP_SOURCE_EXACT_ORIGINAL_KERNEL_NATIVE_T_SERVICES_BOTH_BIRTHS_THREE_LOCKS_AND_FINANCIAL_BINDING')
 M.need(_read_complete(reference,owner.core.home,read_budget=read_budget,own=False)==(body,record),
  'HTTP_SOURCE_STABLE_ORIGINAL_SOURCE_AND_ISSUED')
 cap=object.__new__(VerifiedHttpRuntimeControls)
 cap._body,cap._controls,cap._reference=copy.deepcopy(body),copy.deepcopy(body['controls']),copy.deepcopy(record)
 cap.kernel_capability,cap.source_owner,cap.source_ticket=kernel,owner,ticket
 cap.old_owner_birth,cap.new_owner_birth=kernel.old_owner_birth,kernel.new_owner_birth
 cap.contract_sha256,cap.lock_fds=kernel.contract_sha256,tuple(kernel.lock_fds)
 cap._seal=_SEAL;_VERIFIED[id(cap)]=cap;return cap


def publish_OWN_component(capture,*,read_budget):
 budget(read_budget)
 M.need(type(capture)is CapturedHttpControls and capture.OWN is True and capture._seal is _SEAL and
  _CAPTURES.get(id(capture.core))is capture,'HTTP_SOURCE_OWN_CODEC_ONLY_NO_T_OR_CROSS_BIRTH')
 controls=capture.snapshot();core=capture.core
 return _complete(core,dict(source_owner_birth=controls['source_owner_birth'],contract_sha256=controls['contract_sha256'],
  controls=controls,controls_sha256=M.digest(controls),production_source_binding=False),own=True,
  final_guard=lambda:M.need(_controls(core,read_budget=read_budget,own=True)==controls,'HTTP_SOURCE_OWN_CHANGED'))


def read_OWN_component(reference,*,home,read_budget):
 body,_=_read_complete(reference,home,read_budget=read_budget,own=True)
 M.need(body['production_source_binding']is False,'HTTP_SOURCE_OWN_NOT_PRODUCTION_TRANSFER')
 return copy.deepcopy(body['controls'])
