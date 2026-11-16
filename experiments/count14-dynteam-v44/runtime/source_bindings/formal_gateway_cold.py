"""NEW formal six-root cold constructor, original gateway layer/config actions.

No existing owner, container repair/removal, daemon/network setting or model
request is touched. Reuses the actual R7 gateway fix before first native UP.
Not a production delivery/activation authority or permission to create roots.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_HOSTNAME = _count14_os.environ.get('COUNT14_HOSTNAME', 'count14-host')
from pathlib import Path
from types import FunctionType,MethodType,SimpleNamespace
import ast,hashlib,importlib.util,inspect,json,os,shlex,stat,textwrap,time
HERE=Path(__file__).resolve().parent
ORIGINAL_GATEWAY_PINS={'original_gateway_overlay.py': 'db4f0d57b72affc65ecabba86536e684e80d2f498b2077a44e7e9c61365f92e0', 'original_gateway_config.py': '654978a76d1c156b2900190f4442f51d2af3f4c0b0dafe8a02e4d78a3add2a41'}
PREVIOUS=('formal100m-no-reference-host-cold-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_no_reference_host.py',
 '28bc028b3ee71ff22628b25df17a24eeb632a860b4c470eae9c659ac0c33450e')
SCOPE_SHA='8aed2cbcf62da6961b8d609a2c89ab961d9f72f7bca0a6b70da32e2d848b62e4'
_REGISTRY={};RETAINED_NEW_OWNER=None;_PREPARE_ATTEMPTED=False

def need(ok,code):
 if not ok:raise ValueError(code)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,pin,name):
 p=Path(p);s=p.lstat()
 need(p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and
  s.st_uid in(0,os.geteuid())and not s.st_mode&0o022 and sha(p)==pin,'FORMAL_GATEWAY_EXACT_FROZEN_REGULAR_DEPENDENCY')
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def components():
 # Pin exact reusable source bytes inside this new component footprint. No
 # operational dependency on an old installed R7 package/action entry point.
 return (load(HERE/'original_gateway_overlay.py',ORIGINAL_GATEWAY_PINS['original_gateway_overlay.py'],
              'count14_formal_original_gateway_layer'),
         load(HERE/'original_gateway_config.py',ORIGINAL_GATEWAY_PINS['original_gateway_config.py'],
              'count14_formal_original_config_comparison'))


def select_compare(compare,graph):
 # Only metadata HOME differs in a wholly new formal graph. Original R7 uses
 # a cold-successor control leaf absent from a fresh constructor. Keep the
 # original subprocess/config/single-field reverse diff and all fresh gates.
 tree=ast.parse(textwrap.dedent(inspect.getsource(compare)))
 original=ast.dump(tree,include_attributes=False);hits=0
 for node in ast.walk(tree):
  if isinstance(node,ast.Attribute)and isinstance(node.value,ast.Name)and node.value.id=='core'and node.attr=='pre_request_control_home':
   node.attr='home';hits+=1
 need(hits==1,'FORMAL_GATEWAY_EXACT_ONE_ORIGINAL_CONFIG_METADATA_HOME_SITE')
 reverse=ast.parse(ast.unparse(tree));back=0
 for node in ast.walk(reverse):
  if isinstance(node,ast.Attribute)and isinstance(node.value,ast.Name)and node.value.id=='core'and node.attr=='home':
   node.attr='pre_request_control_home';back+=1
 need(back==1 and ast.dump(reverse,include_attributes=False)==original,
  'FORMAL_GATEWAY_CONFIG_ALL_OTHER_ORIGINAL_STATEMENTS_UNCHANGED')
 namespace=dict(compare.__globals__,held=graph)
 exec(compile(ast.fix_missing_locations(tree),'formal-config-original-single-metadata-home-selector','exec'),namespace)
 return namespace[compare.__name__]


def scope(core):
 import formal_scope as F
 need(sha(F.__file__)==SCOPE_SHA,'FORMAL_GATEWAY_ORIGINAL_CONTRACT_VALIDATOR_PIN')
 if core.qualification_only:
  need(os.uname().nodename!=(_C14_HOSTNAME),'FORMAL_GATEWAY_NO_OWN_PATH_ON_PRODUCTION')
  from common import digest
  fn=F.validate_contract
  own=FunctionType(fn.__code__,dict(fn.__globals__,PUBLIC_CONTRACT_CANONICAL_SHA256=digest(core.contract)),fn.__name__)
  own(core.contract,digest(core.contract)) # explicit OWN root/ID remapping, same full six/cuts/caps validators
 else:
  from common import digest
  F.validate_contract(core.contract,digest(core.contract))

def held(owner):
 from native_cold_owner import NativeColdOwner
 from original_relay_core import OriginalRelayCore
 from native_cold_bootstrap import NativeColdBootstrap
 from native_peer_registry import process_birth
 need(type(owner)is NativeColdOwner and not owner.errors and type(owner.core)is OriginalRelayCore and
  type(owner.bootstrap)is NativeColdBootstrap and owner.bootstrap.core is owner.core and
  owner.ledger is owner.core.ledger,'FORMAL_GATEWAY_ONE_GENUINE_NEW_ORIGINAL_OWNER_CORE_BOOTSTRAP')
 core=owner.core;scope(core)
 need(not core.closed and not core.scientific_activation_qualified and set(core.gate.startup_held)==set(core.rows)and
  set(core.native_networks)==set(core.rows)and not core.ledger.mutex._is_owned(),
  'FORMAL_GATEWAY_ALL_SIX_HELD_SAME_NETWORKS_NO_NATIVE_PEERS_OR_SCIENTIFIC_PREFIX')
 with core.ledger.mutex:
  for table in('requests','unknown_charges','aux_scopes','aux_permits','snapshots','acks','unknown_stops'):
   need(core.ledger.db.execute('SELECT COUNT(*)FROM '+table).fetchone()[0]==0,
    'FORMAL_GATEWAY_BEFORE_FIRST_MODEL_UNKNOWN_CHECKPOINT_OR_FINAL')
  need(core.ledger.db.execute('SELECT paused FROM model_control WHERE singleton=1').fetchone()[0]==1 and
   not core.ledger.memory_faults,'FORMAL_GATEWAY_MODELS_PAUSED_NO_FAULT_CLEAR')
 r=_REGISTRY.get(id(owner))
 if r is not None:
  need(r['owner']is owner and r['birth']==process_birth(os.getpid()),'FORMAL_GATEWAY_SAME_REGISTERED_REAL_BIRTH')
 for t,row in core.rows.items():
  core.native_networks[t].checked(contract=core.contract,row=row,qualification_only=core.qualification_only)
  need(core.servers[t].server_address[0]==core.native_networks[t].gateway,
   'FORMAL_GATEWAY_SAME_EXISTING_RELAY_NETWORK_GATEWAY')
 return True

def write_receipt(record,name,value):
 p=record['owner'].core.home/name
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
 with os.fdopen(fd,'wb')as f:
  f.write((json.dumps(value,sort_keys=True)+'\n').encode());f.flush();os.fsync(f.fileno())

def exact_native_gateway_replacement_baseline(core, trajectory, compose):
 """Replace the already-checked duplicate alias layer, not any config guard.

 The native exporter already concretizes the sentinel.  A second gateway
 layer needs the true sentinel baseline for the original two-config proof.
 Keep the old file/descriptor; only substitute its exact -f operand pair on
 this wholly new held constructor, before any bootstrap/container action.
 """
 from native_cold_exports import _checked_native_gateway_companion
 from native_beta_layout import native_aliases
 export=core.cold_native_exports['trajectories'][trajectory]
 path=_checked_native_gateway_companion(core,trajectory,export)
 descriptor=export['native_gateway_override']
 aliases=native_aliases(core.rows[trajectory]['arm'])
 names={alias[key]for alias in aliases.values()for key in('agent_service','router_service')}
 need(set(descriptor['existing_hosts'])==names and
      all(type(hosts)is dict and hosts=={'host.docker.internal':'host-gateway'}
          for hosts in descriptor['existing_hosts'].values()),
      'FORMAL_GATEWAY_REPLACEMENT_EXACT_ALL_ORIGINAL_SINGLE_SENTINEL_HOSTS')
 need(type(compose)is tuple and all(type(value)is str for value in compose)and
      compose.count('compose')==compose.count('--project-name')==1 and compose.count(str(path))==1,
      'FORMAL_GATEWAY_REPLACEMENT_EXACT_ONCE_ORIGINAL_NATIVE_COMPANION')
 at=compose.index(str(path))
 need(at>compose.index('compose')and at<compose.index('--project-name')and compose[at-1]=='-f',
      'FORMAL_GATEWAY_REPLACEMENT_ONLY_EXACT_FILE_OPERAND_PAIR')
 before=compose[:at-1]+compose[at+1:]
 need(str(path)not in before and before[:at-1]+('-f',str(path))+before[at-1:]==compose,
      'FORMAL_GATEWAY_REPLACEMENT_COMPLETE_COMMAND_INVERSE')
 # _checked_native_gateway_companion validates canonical path, typed network,
 # exact source bytes+SHA and before/after identity.  No file is changed.
 return before


def install_new(owner):
 """Only a brand-new six-held constructor, not a cold successor/old repair."""
 from native_peer_registry import process_birth
 held(owner)
 need(id(owner)not in _REGISTRY and not owner.bootstrap.records and
  not getattr(owner.core,'source_bootstraps',{}) and not hasattr(owner,'scientific_smoke') and
  not owner.core.native_containers.records and not owner.core.native_containers.boot_plans and not owner.core.peers._peers,
  'FORMAL_GATEWAY_NEW_UNSTARTED_FORMAL_OWNER_ONLY_NOT_CURRENT240_OR_PARTIAL_ADOPTION')
 core=owner.core;G,C=components()
 record=dict(owner=owner,birth=process_birth(os.getpid()),phase='NEW_GATEWAY_LAYERS_PARTIAL',
  failures=[],spawns={},layer_proofs={})
 _REGISTRY[id(owner)]=record # retain partial before first new private file
 try:
  for t,row in core.rows.items():
   host=core.native_host_environment['trajectories'][t];network=core.native_networks[t]
   need('current240_gateway_overlay'not in host and
    host['launcher_env']['COUNT14_NATIVE_COMPOSE_COMMAND']==shlex.join(host['compose']),
    'FORMAL_GATEWAY_NEW_BOTH_NATIVE_COMPOSE_CONSUMERS_UNMODIFIED')
   home=Path(row['root'])/'native-explicit-gateway';need(not home.exists()and not home.is_symlink(),
    'FORMAL_GATEWAY_ONE_NEW_PRIVATE_LEAF_NO_REUSE_OR_DELETE')
   home.mkdir(mode=0o700)
   path=G.write_new_overlay(home/'compose.explicit-host-gateway.private.yaml',contract=core.contract,row=row,
    network=network,relay_address=core.servers[t].server_address,qualification_only=core.qualification_only,owner_uid=os.geteuid())
   before=exact_native_gateway_replacement_baseline(core,t,host['compose'])
   after=G.append_layer(before,path=path,network=network)
   host['compose']=after
   host['launcher_env']=dict(host['launcher_env'],COUNT14_NATIVE_COMPOSE_COMMAND=shlex.join(after))
   host['current240_gateway_overlay']=dict(path=str(path),original_compose=before,selected_compose=after,
    current_owner_birth=record['birth'])
  original=owner.bootstrap._spawn
  compare=C.verify_actual_compose
  def graph(core_,t):
   need(core_ is core and t in core.rows,'FORMAL_GATEWAY_ONLY_THIS_EXACT_NEW_GRAPH')
   return held(owner)
  selected=select_compare(compare,graph)
  def spawn(bootstrap,raw,argv,env,*,cwd):
   need(bootstrap is owner.bootstrap and bootstrap.records.get(raw['trajectory'])is raw and
    raw['child'] is None and raw['failure_type'] is None,'FORMAL_GATEWAY_ORIGINAL_SAME_ONCE_BOOTSTRAP_RECORD')
   t=raw['trajectory'];held(owner);key=(t,raw['phase'])
   need(key not in record['spawns'],'FORMAL_GATEWAY_NO_AUTORETRY_OF_PARTIAL_CONFIG_OR_UP')
   record['spawns'][key]='CONFIG_CHECK_PENDING'
   try:
    proof=selected(core,t,fresh_guard=lambda:held(owner))
    record['layer_proofs'][key]=proof
    from common import digest
    write_receipt(record,'HOST_GATEWAY_CONFIG_'+digest([t,raw['phase']])+'_PUBLIC.json',
     dict(schema='count14-formal-native-host-gateway-config-control-v1',trajectory=t,phase=raw['phase'],
      both_original_native_compose_consumers_equal=True,actual_original_config_diff_single_extra_hosts_only=True,
      config_expansion_exported_or_hashed=False,normal_original_spawn_next_not_yet_done=True))
    record['spawns'][key]='ORIGINAL_SPAWN_PENDING'
    value=original(raw,argv,env,cwd=cwd) # same command/body/normal Popen/resource guards
    record['spawns'][key]='ORIGINAL_SPAWN_ENTERED'
    return value
   except BaseException as e:
    record['spawns'][key]='PARTIAL_RETAINED_NO_RETRY';record['failures'].append(type(e).__name__);raise
  owner.bootstrap._spawn=MethodType(spawn,owner.bootstrap)
  record['phase']='SIX_GATEWAY_LAYERS_BOUND_ORIGINAL_CONFIG_BEFORE_EACH_BOOTSTRAP_UP'
  return dict(schema='count14-formal-newroot-gateway-layer-bound-v1',trajectories=len(core.rows),
   native_alias_instances=sum(2*len(r['roles'])for r in core.rows.values()),models=0,
   original_bootstrap_spawn_body_and_commands_unmodified=True,actual_host_config_and_UP_not_yet_executed=True)
 except BaseException as e:
  record['failures'].append(type(e).__name__);raise

def prepare_new_owner(**kwargs):
 global RETAINED_NEW_OWNER,_PREPARE_ATTEMPTED
 need(not _PREPARE_ATTEMPTED and RETAINED_NEW_OWNER is None,'FORMAL_GATEWAY_ONE_ORIGINAL_NEW_CONSTRUCTOR_NO_RETRY')
 _PREPARE_ATTEMPTED=True
 previous=load(HERE.parent/PREVIOUS[0],PREVIOUS[1],'count14_formal_original_no_reference_team_exec_constructor')
 owner=previous.prepare_new_owner(**kwargs);RETAINED_NEW_OWNER=owner
 if owner.errors:return owner  # original partial custody, never mask its error with held()
 install_new(owner)
 return owner


def select_new_formal_factory(factory):
 """Keep the complete current no-reference/source/SDK/Tester binder chain."""
 old=load(HERE.parent/PREVIOUS[0],PREVIOUS[1],'count14_formal_original_no_reference_factory')
 selected=old.select_new_formal_factory(factory)
 previous=selected.private_original_constructor
 def constructor(bind_same_owner):
  helper=previous(bind_same_owner)
  need(sha(helper._future_team_executable_prepare.__globals__['__file__'])==PREVIOUS[1],
   'FORMAL_GATEWAY_EXACT_CURRENT_NOREf_TEAM_EXEC_PREPARE_REQUIRED')
  helper._future_team_executable_prepare=prepare_new_owner
  return helper
 selected.private_original_constructor=constructor
 return selected


def select_new_source_module(module,level=0):
 old=load(HERE.parent/PREVIOUS[0],PREVIOUS[1],'count14_formal_original_no_reference_source_selector')
 fn=old.select_new_source_module
 selected=FunctionType(fn.__code__,dict(vars(old),select_new_formal_factory=select_new_formal_factory,
  select_new_source_module=select_new_source_module),fn.__name__,fn.__defaults__,fn.__closure__)
 selected.__kwdefaults__=fn.__kwdefaults__
 return selected(module,level)
