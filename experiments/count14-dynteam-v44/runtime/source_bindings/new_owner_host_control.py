"""NEW-owner original metadata control graph. Never SDK/paid/whole authority.

Original classes, handler, peer credentials, publisher and anonymous journal
methods remain unchanged. The only path exception is a sealed birth/contract
subhome under the SAME owner home; the old socket inode is retained. No fresh
spawn counter, fresh SID domain, original SDK baseline or caller-True custody.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MethodType
import ast
import copy
import hashlib
import importlib
import inspect
import json
import os
import socket
import stat
import textwrap

from common import digest, need, wire
from bounded_metadata_ro import ReadBudget, readonly
from native_peer_registry import NativePeerRegistry, process_birth
from native_session_control import NativeSessionControl, NativeSessionInbox, COMMIT
from native_metadata_publisher import NativeMetadataPublisher
from anonymous_roster_journal import AnonymousRosterJournal, snapshot
from dynteam_metadata import catalogue
from original_relay_core import OriginalRelayCore
from native_bridge_owner import NativeBridgeLifecycleOwner
from native_archive_guard import NativeArchiveGuard
from smoke_racing_tools_kernel_custody import NativeKernelToolCustody
import normal_held_financial_writer as H
import normal_inert_cut as T
import new_owner_sdk_guest_control as G

PINS = dict(native_control_whitelist_source='9cbf5f9efe1719578c19b1749f19fc411561b9613c2430388272e226f2e7ea4f',native_control_source_supplement='6a05b79f670257c49d29edca6f924c5144fe68ed28517e10b1c6ba250115b049',native_session_control='cba05b39fb3231f5791ba7421bf2b6a8487d081df6016885ab7f291b326cd370',
 native_metadata_publisher='a0e2fe4a193a25333424c7c4c723714bb1f2aa6b7b352c811421f59ffa9e4bdb',
 native_peer_registry='0986b61a7c71b6745442b9c71dfc67d79eebf960a50523ea1e2b5ee0f37d019d',
 anonymous_roster_journal='853a333ead7beb01229412f96d00a1947803b8ad3e8f5599ce93b5d2d02652e4',
 original_relay_core='89ac900e66caa67887504522c574c1870f7a8faf51542fe248ca7f35b1541556',
 native_bridge_owner='e3e2c6b41ee109a1483ee92e8820fda1ad3e186e82263968299bd848bedac346',
 native_archive_guard='75d4de0bf891c88e0b00714b564572b4426f5d1ce1938993ed5fbfb8b3219f7e',
 native_physical_bindings='73ca2f006cfeb0ee9434c0ab0c380c1e59fa136514a199d90030461089fd2c40',
 smoke_racing_tools_kernel_custody='5ff1cb87ca0cd1f09b6ef972edb3d4ab3c945618012ee10d8849468333f841ab',
 normal_held_financial_writer='686247ad8d2ca768abf1dc0085ac4a18e58419f37e2bceb61b152d8f8b413261')
_SEAL=object()
_SOCKETS={}
_GRAPHS={}


def verify_sources():
 for name,pin in PINS.items():
  path=Path(importlib.import_module(name).__file__)
  need(path.is_absolute()and path.resolve()==path and not path.is_symlink()and
   hashlib.sha256(path.read_bytes()).hexdigest()==pin,'NEW_HOST_EXACT_ORIGINAL_SOURCE_PINS')
 H.verify_sources();G.verify_sources()
 return dict(PINS)


def _identity(path):
 path=Path(path);s=path.lstat()
 need(path.is_absolute()and path.resolve()==path and not path.is_symlink(),
  'NEW_HOST_CANONICAL_CONTROL_NODE')
 return dict(path=str(path),device=s.st_dev,inode=s.st_ino,uid=s.st_uid,gid=s.st_gid,mode=stat.S_IMODE(s.st_mode))


def _unlocked(core):
 need(not core.ledger.mutex._is_owned()and not core.queue.mutex._is_owned(),
  'NEW_HOST_NO_METADATA_IO_WHILE_HOLDING_FINANCIAL_OR_QUEUE_LOCK')


def _save_new(path,body):
 raw=wire(body)
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
 with os.fdopen(fd,'wb')as out:out.write(raw);out.flush();os.fsync(out.fileno())
 return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True,repr=False)
class NewOwnerSocketProof:
 core:object
 owner_birth:object
 contract_sha256:str
 home_identity:dict
 directory_identity:dict
 path:Path
 receipt:Path
 receipt_identity:dict
 receipt_sha256:str
 old_socket_identity:object
 OWN:bool
 _seal:object


def create_control_subhome(core,*,read_budget,OWN=False):
 """O_EXCL exact birth-scoped control leaf. No old socket unlink/chmod."""
 need(type(read_budget)is ReadBudget,'NEW_HOST_FINITE_CONTROL_READ_BUDGET');read_budget.check();_unlocked(core)
 need(type(core)is OriginalRelayCore and type(OWN)is bool and core.qualification_only is OWN and
  id(core)not in _SOCKETS,'NEW_HOST_EXACT_NEW_CORE_SINGLE_CONTROL_SUBHOME')
 home=Path(core.home);home_id=_identity(home)
 need(home.is_dir()and home_id['uid']==os.geteuid()and home_id['mode']==0o700 and
  (not OWN or any(p.startswith('OWN-')for p in home.parts)),
  'NEW_HOST_SAME_PRIVATE_ORIGINAL_OWNER_HOME_NOT_NEW_SCIENTIFIC_ROOT')
 birth=process_birth(os.getpid());contract=digest(core.contract)
 key=digest(dict(owner_birth=asdict(birth),contract_sha256=contract))[:16]
 base=home/'c'
 if not base.exists():base.mkdir(mode=0o700)
 base_id=_identity(base)
 need(base.is_dir()and base_id['uid']==os.geteuid()and base_id['mode']==0o700,
  'NEW_HOST_EXACT_OWNED_PRIVATE_CONTROL_CONTAINER')
 directory=base/key;directory.mkdir(mode=0o700) # no reuse, chmod, replacement or recursive action
 directory_id=_identity(directory);path=directory/'native-control.sock'
 need(len(os.fsencode(path))<108,'NEW_HOST_UNIX_SOCKET_PATH_KERNEL_LENGTH')
 old=home/'native-control.sock'
 old_id=None if not old.exists()else _identity(old)
 receipt=directory/'NEW_OWNER_CONTROL_PUBLIC.json'
 body=dict(schema='count14-new-owner-control-subhome-proof-v1',OWN=OWN,
  owner_birth=asdict(birth),contract_sha256=contract,original_owner_home=home_id,
  new_control_directory=directory_id,control_socket=str(path),old_socket_identity=old_id,
  original_scientific_roots_ledger_SIDs_unchanged=True,SDK_or_paid_authority=False)
 pin=_save_new(receipt,body)
 for node in(directory,base):
  fd=os.open(node,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  try:os.fsync(fd)
  finally:os.close(fd)
 proof=NewOwnerSocketProof(core,birth,contract,home_id,directory_id,path,receipt,_identity(receipt),pin,old_id,OWN,_SEAL)
 _SOCKETS[id(core)]=proof
 return proof


def verify_control_subhome(proof,core,*,read_budget):
 read_budget.check();_unlocked(core)
 need(type(proof)is NewOwnerSocketProof and proof._seal is _SEAL and proof.core is core and
  _SOCKETS.get(id(core))is proof and proof.owner_birth==process_birth(os.getpid())and
  proof.contract_sha256==digest(core.contract)and _identity(core.home)==proof.home_identity and
  _identity(proof.path.parent)==proof.directory_identity and
  _identity(proof.receipt)==proof.receipt_identity and
  hashlib.sha256(proof.receipt.read_bytes()).hexdigest()==proof.receipt_sha256,
  'NEW_HOST_EXACT_REGISTERED_FULL_BIRTH_CONTRACT_AND_CONTROL_DIRECTORY_PROOF')
 old=Path(core.home)/'native-control.sock'
 need((None if not old.exists()else _identity(old))==proof.old_socket_identity,
  'NEW_HOST_OLD_CONTROL_SOCKET_INODE_RETAINED_NOT_UNLINKED_OR_REBOUND')
 return proof


def _socket_path_guard(core,path,proof):
 """Private clone of ONE original socket-path guard. Reverse AST must match."""
 fn=ast.parse(textwrap.dedent(inspect.getsource(OriginalRelayCore.bind_native_control))).body[0]
 matches=[]
 for node in ast.walk(fn):
  if isinstance(node,ast.Expr)and isinstance(node.value,ast.Call)and any(
   isinstance(v,ast.Constant)and v.value=='DYNTEAM_EXACT_NEW_OWNER_CONTROL_SOCKET'for v in node.value.args):matches.append(node)
 need(len(matches)==1,'NEW_HOST_ONE_ORIGINAL_HARDCODED_SOCKET_GUARD')
 original=copy.deepcopy(matches[0]);modified=copy.deepcopy(original)
 compare=modified.value.args[0]
 need(isinstance(compare,ast.Compare)and len(compare.comparators)==1 and
  ast.unparse(compare.comparators[0])=="self.home / 'native-control.sock'",'NEW_HOST_EXACT_ORIGINAL_SOCKET_PATH_AST')
 before=copy.deepcopy(compare.comparators[0]);compare.comparators[0]=ast.Name(id='_exact_path',ctx=ast.Load())
 reverse=copy.deepcopy(modified);reverse.value.args[0].comparators[0]=before
 need(ast.dump(reverse,include_attributes=False)==ast.dump(original,include_attributes=False),
  'NEW_HOST_PATH_ONLY_REVERSE_AST_ALL_ORIGINAL_GUARDS_UNCHANGED')
 wrapper=ast.FunctionDef(name='_original_socket_path_guard',args=ast.arguments(posonlyargs=[],
  args=[ast.arg(arg=n)for n in('self','socket_path','_exact_path')],kwonlyargs=[],kw_defaults=[],defaults=[]),
  body=[modified],decorator_list=[])
 namespace={};globals_=dict(OriginalRelayCore.bind_native_control.__globals__)
 exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[])),__file__+':path_only_original_guard','exec'),globals_,namespace)
 namespace['_original_socket_path_guard'](core,path,proof.path)


def _journals(core,source,*,read_budget,OWN=False):
 need(type(source)is dict and set(source)==set(core.rows),'NEW_HOST_ALL_ORIGINAL_ANONYMOUS_JOURNAL_CONTROLS')
 result={}
 try:
  for t,row in core.rows.items():
   _unlocked(core);read_budget.check();saved=source[t]
   path=Path(row['root'])/'metadata/DYNTEAM_ROSTER_PUBLIC_METADATA.sqlite'
   need(_identity(path)==saved['identity']and set(saved['anonymous_projection']['roles'])==set(row['roles'])and
    saved['anonymous_projection']['roles']==catalogue(racing_players=7 if row['arm']=='DYNTEAM_RACING'else 0)and
    saved['anonymous_projection']['complete_history']is True,
    'NEW_HOST_ORIGINAL_JOURNAL_PATH_INODE_CATALOGUE_LIFECYCLE_NOT_EMPTY_RESTART')
   with readonly(path,read_budget,lambda:_unlocked(core))as ro:
    latest=ro.execute('SELECT id,state_sha256 FROM roster_batches ORDER BY id DESC LIMIT 1').fetchone()
   need((None if latest is None else latest['id'])==saved['latest_id']and
    (None if latest is None else latest['state_sha256'])==saved['latest_state_sha256']and
    (latest is not None or saved['initial_empty_projection_verified']is True),
    'NEW_HOST_ORIGINAL_JOURNAL_DURABLE_TIP_NOT_CHANGED')
   journal=AnonymousRosterJournal(path,block=row['block'],arm=row['arm'],qualification_only=OWN,lifecycle_complete=True)
   result[t]=journal
   need(snapshot(journal.projection)==saved['anonymous_projection'],
    'NEW_HOST_RESTORED_ORIGINAL_ANONYMOUS_STATE_EQUAL_NO_RETROSPECTIVE_BIRTHS')
  return result
 except BaseException:
  for journal in result.values():journal.close() # new anonymous metadata handles only
  raise


def _archive_bindings(core):
 from native_layout import native_names
 from native_beta_layout import native_aliases
 result={}
 for t,row in core.rows.items():
  profile,org=native_names(t);root=Path(row['root'])/'native-data'/profile
  for role,alias in native_aliases(row['arm']).items():
   account=org+'-'+alias['native_short']
   result[t,role]=dict(archive_root=str(root/'trajectories'/account),
    native_turn_metadata=str(root/'acp'/account/'current-turn.json'),owner_uid=os.geteuid())
 return result


def _runtime_wait(*args,**kwargs):
 raise RuntimeError('NEW_HOST_SOURCE_SPAWN_OR_SDK_RUNTIME_PROOF_MISSING_RETAIN_NO_RESET')


@dataclass(repr=False)
class NewOwnerHostControlGraph:
 stage:object
 core:object
 registration:object
 epochs:object
 sessions:object
 control:object
 publisher:object
 peers:object
 journals:dict
 kernel_custody:object
 socket_proof:object
 bridge_owner:object
 unresolved:list
 _seal:object

 def poll_metadata_once(self,*,read_budget):
  need(registered_stage_host_graph(self.stage)is self,'NEW_HOST_SINGLE_CURRENT_OWNER_METADATA_PUBLISHER')
  verify_control_subhome(self.socket_proof,self.core,read_budget=read_budget)
  return self.publisher.poll_once() # original owner loop, no extra dispatcher

 def public(self):
  return dict(schema='count14-new-owner-original-host-control-graph-v1',same_stage_core=True,
   new_control_socket=str(self.socket_proof.path),control_proof_sha256=self.socket_proof.receipt_sha256,
   original_native_control_started=bool(self.control and self.control.started),
   original_anonymous_journal_count=len(self.journals),registered_original_peers=len(self.peers._peers),
   source_spawn_counters_restored=False,unresolved=list(self.unresolved),
   new_SID_claim_or_SDK_runtime_authorized=False,actual_SDK_load=False,host_strict_ACK=False,
   once_recovery=False,paid_activation_authorized=False,safe_to_TERM=False,whole_runnable_ready=False)


def registered_stage_host_graph(stage):
 value=_GRAPHS.get(id(stage))
 need(type(value)is NewOwnerHostControlGraph and value._seal is _SEAL and value.stage is stage and
  value.core is stage.core and stage.core.native_new_owner_host_control is value and
  G.registered_stage_sdk_controls(stage)is value.registration and
  stage.core.sessions is value.sessions and stage.core.native_sdk_startup_epochs is value.epochs and
  stage.core.inbox is value.publisher.inbox and stage.core.publisher is value.publisher and
  stage.core.journals is value.journals and stage.core.peers is value.peers and
  stage.new_owner_birth==process_birth(os.getpid()),'NEW_HOST_EXACT_REGISTERED_SAME_CORE_GRAPH')
 return value


def prepare_registered_host_control(stage,*,owner,ticket,read_budget):
 """Restore control RAM, then start ONE original listener. All science HELD."""
 verify_sources();record=H._same(stage,read_budget,own=False);_unlocked(stage.core)
 need(record['owner']is owner and record['ticket']is ticket and id(stage)not in _GRAPHS and
  stage.core.gate.closed and not stage.core.gate.waiters and
  set(stage.core.gate.startup_held)==set(stage.core.rows),
  'NEW_HOST_EXACT_ORIGINAL_T_AND_NEW_UNPUBLISHED_HELD_FINANCIAL_GRAPH')
 cap=T.verify_inert_ticket(ticket,owner=owner,read_budget=read_budget)
 registration=G.registered_stage_sdk_controls(stage);core=stage.core
 need(registration.source_owner is owner and registration.source_ticket is ticket and
  registration.old_owner_birth==stage.old_owner_birth and registration.new_owner_birth==stage.new_owner_birth and
  registration.source_control_sha256==cap.source_control_sha256 and
  record['services'].snapshot()['physical_service_retirement']['native_control_listener_and_handlers_ended']is True and
  not getattr(core,'control',None)and not hasattr(core,'native_new_owner_host_control'),
  'NEW_HOST_SOURCE_LISTENER_PHYSICALLY_RETIRED_TYPED_LINEAGE_NOT_INERT_AUTHORITY')
 pre=cap._body['source_controls'];proof=create_control_subhome(core,read_budget=read_budget)
 bindings={(t,r):row['block']for t,row in core.rows.items()for r in row['roles']}
 peers=NativePeerRegistry(source_commit=COMMIT,allowed_bindings=bindings)
 inbox=NativeSessionInbox();journals=_journals(core,pre['anonymous_journals'],read_budget=read_budget)
 core.original_projection=MethodType(OriginalRelayCore.original_projection,core)
 publisher=NativeMetadataPublisher(inbox=inbox,sessions=registration.sessions,journals=journals,
  bindings=bindings,original_control_projection=core.original_projection)
 # This is a separate, expressly cold restoration, NOT original fresh bind().
 # Its epochs remain quarantined. No paid baseline is reset or inferred clear.
 custody=NativeKernelToolCustody();custody.core=core;custody.sdk_startup_epochs=registration.epochs
 registration.epochs.custody=custody;publisher.native_kernel_tool_custody=custody
 core.native_kernel_tool_custody=custody
 core.inbox,core.journals,core.publisher,core.peers=inbox,journals,publisher,peers
 def physical(t,role):
  return dict(models_clear=core.original_projection(t,role)[1],tools_clear=custody(t,role))
 core.native_physical_projection=physical
 bridge=NativeBridgeLifecycleOwner(core,child_uid=10000,original_physical_projection=physical,
  archive_guard=NativeArchiveGuard(_archive_bindings(core)))
 core.bridge_owner=bridge
 unresolved=['SOURCE_NATIVE_SPAWN_COUNTERS_NOT_CAPTURED_RUNTIME_WAIT',
  'ORIGINAL_SDK_NATIVE_LOAD_STRICT_ACK_ONCE_NOT_YET_QUALIFIED']
 graph=NewOwnerHostControlGraph(stage,core,registration,registration.epochs,registration.sessions,None,
  publisher,peers,journals,custody,proof,bridge,unresolved,_SEAL)
 _GRAPHS[id(stage)]=graph;core.native_new_owner_host_control=graph # retain genuine partial on any later WAIT
 for row in pre['native_peer_birth_controls']:
  birth=G.R._birth(row['birth']);read_budget.check()
  try:live=process_birth(birth.pid)==birth
  except (OSError,ValueError,KeyError,IndexError):live=False
  if live:peers.register_from_launcher(row['trajectory'],row['role'],birth,expected_birth=birth,purpose=row['purpose'])
  else:unresolved.append('ORIGINAL_SOURCE_PEER_NO_LONGER_LIVE')
 for source in registration.source_transfer.clis:
  need(source.end_lease is None,'NEW_HOST_WAIT_ORIGINAL_MEMBERSHIP_LEASE_NOT_GUESSED')
  bridge.clis[source.key]=dict(token=source.token,birth=source.birth,raw_birth=source.raw_birth,
   archived=source.archived,end_lease=None)
  if source.archived:bridge.finished.add(source.token)
  elif source.key in core.roles.births:bridge.logical[source.key]=source.raw_birth
 # No source spawn state => not even a fresh NativeSpawnOwner constructor.
 core.spawn_owner=None;core.pending_native_launches={}
 core.validate_native_peer=MethodType(OriginalRelayCore.validate_native_peer,core)
 _socket_path_guard(core,proof.path,proof)
 control=NativeSessionControl(proof.path,peer_validator=core.validate_native_peer,receiver=inbox.receive,
  socket_uid=10000,socket_gid=10000)
 graph.control=core.control=control
 from new_owner_sdk_plan_control import NewOwnerGuestPlanControl
 graph.guest_plan_control=NewOwnerGuestPlanControl(graph) # fixed new-only handler; plans still require genuine SDK/kernel proof
 control.start()
 registered_stage_host_graph(stage);return graph


def bind_registered_host_native_containers(graph,*,docker,native_reference,read_budget):
 """Original live source container/peer graph, no container/CLI launch."""
 from native_docker_scope import ScopedDocker
 from native_container_retirement import NativeContainerRegistry,ContainerBinding,descendant_in_container
 import native_physical_bindings as P
 need(registered_stage_host_graph(graph.stage)is graph and type(docker)is ScopedDocker and
  docker.route.qualification_only is False and not hasattr(graph.core,'native_containers'),
  'NEW_HOST_REAL_NEW_SAME_CORE_ORIGINAL_PRIVATE_DOCKER_BINDING_ONLY')
 verify_control_subhome(graph.socket_proof,graph.core,read_budget=read_budget)
 import native_control_source_supplement as N
 import native_control_whitelist_source as W
 native_cap=N.verify_reference(native_reference,owner=graph.registration.source_owner,ticket=graph.registration.source_ticket,read_budget=read_budget)
 docker.verify_files();docker.verify_daemon()
 retained=graph.registration.source_registration.retained_containers;images={}
 for row in retained:
  c=row.source_component
  need(c.component not in images or images[c.component]==c.image_id,'NEW_HOST_SAME_PINNED_SOURCE_IMAGES')
  images[c.component]=c.image_id
 need(set(images)=={'agent','router'},'NEW_HOST_BOTH_ORIGINAL_AGENT_AND_ROUTER_IMAGE_PINS')
 registry=NativeContainerRegistry(graph.core,docker,image_ids=images);graph.core.native_containers=registry
 W.bind_registered_receiver(graph,registry,capability=native_cap,read_budget=read_budget)
 graph.domain_fds={};graph.source_containers_registered=set()
 for row in retained:
  _unlocked(graph.core);read_budget.check();c=row.source_component
  key=row.key;purpose='bridge'if c.component=='agent'else'router'
  peer=graph.peers._peers.get((*key[:2],purpose))
  if peer is None:
   graph.unresolved.append('ORIGINAL_CONTAINER_LIVE_SOURCE_PEER_UNAVAILABLE');continue
  need(process_birth(c.init_birth.pid)==c.init_birth and descendant_in_container(c.init_birth,peer),
   'NEW_HOST_ORIGINAL_REAL_CONTAINER_INIT_AND_PEER_DESCENDANT')
  binding=ContainerBinding(*key,c.cid,c.image_id,c.init_birth,peer)
  registry.register_from_launcher(binding) # original daemon labels/image/init/namespace guards
  graph.domain_fds[key]=P._domain(c,read_budget) # actual original cgroup device/inode FD
  graph.source_containers_registered.add(key)
 return registry
