"""Restore only separately verified original spawn/logical control metadata.

New stage graph only, still all startup-held. No source owner/Epoch/CLI retag,
paid runtime grant, SDK call, new SID, constructor reset or historical rewrite.
"""
from dataclasses import asdict,dataclass
from pathlib import Path
from types import CodeType
import ast
import copy
import hashlib
import importlib
import inspect
import os
import textwrap
import threading

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
from native_spawn_owner import NativeSpawnOwner
from native_spawn_protocol import NativeSpawnInbox
from native_bridge_protocol import NativeBridgeInbox
from native_phase_proof import NativePhaseProofInbox
from original_relay_core import OriginalRelayCore
from dynteam_membership_fence import Lease
import native_control_source_supplement as S
import native_infra_source_state as I

HOST_SHA256='dadf6ce97da5a7f57d239ac7f4bbbdd397308745c36fa9575d48c524c6ecfb85'
POLL_WRITER_GUARD_SHA256='378f1b0a94634ffe26cb690317c6ae35b91397a0ffe4b39101c4fc346ce8a629'
_SEAL=object()
_RESTORED={}


def host_api():
 module=importlib.import_module('new_owner_host_control');p=Path(module.__file__)
 expected=Path(__file__).resolve().parents[1]/'formal100m-new-owner-host-control-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/new_owner_host_control.py'
 M.need(p==expected and p.resolve()==p and not p.is_symlink()and
  hashlib.sha256(p.read_bytes()).hexdigest()==HOST_SHA256,'NATIVE_RESTORE_EXACT_FROZEN_NEW_HOST_GRAPH')
 return module


def poll_writer_api():
 module=importlib.import_module('native_poll_writer_guard');p=Path(module.__file__)
 expected=Path(__file__).resolve().parents[1]/'formal100m-native-poll-writer-order-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/native_poll_writer_guard.py'
 M.need(p==expected and p.resolve()==p and not p.is_symlink()and
  hashlib.sha256(p.read_bytes()).hexdigest()==POLL_WRITER_GUARD_SHA256,
  'NATIVE_RESTORE_EXACT_POLL_WRITER_ORDER_GUARD_SOURCE')
 return module


def _pure_components(core,controls):
 """Pure new RAM restore. Must be called only after typed production guards."""
 S._validate_controls(controls)
 M.need(controls['contract_sha256']==M.digest(core.contract)and
  controls['catalogues']=={t:list(r['roles'])for t,r in core.rows.items()},
  'NATIVE_RESTORE_EXACT_ORIGINAL_CONTRACT_AND_ROSTER_NOT_NEW_COUNTER_SCOPE')
 spawn=NativeSpawnOwner.__new__(NativeSpawnOwner);spawn.core=core
 spawn.next=copy.deepcopy(controls['original_spawn_public_control']['next_ordinals'])
 spawn.used={t:set(v)for t,v in controls['original_spawn_public_control']['used_slots'].items()}
 spawn.history={};spawn.operations={};spawn.retirement_jobs={}
 for row in controls['original_spawn_completed_operations']:
  spawn.operations[row['trajectory'],row['ordinal']]=dict(lease=Lease(**row['lease']),slot=row['slot'],reuse=row['reuse'],
   committed=row['committed'],birth_observed=row['birth_observed'],native_cli_token_sha256=row['native_cli_token_sha256'])
 # Source jobs all have real terminal proof; old child handles are NOT revived.
 spawn.source_terminal_retirement_controls=copy.deepcopy(controls['original_spawn_terminal_retirement_jobs'])
 logical={(r['trajectory'],r['role']):r['logical_birth_sha256']for r in controls['original_bridge_logical_map']}
 finished={S.unpack_token(v)for v in controls['original_bridge_finished_tokens']}
 M.need(spawn.checkpoint_control_state()==controls['original_spawn_public_control'],
  'NATIVE_RESTORE_ORIGINAL_COUNTER_API_EXACT_ROUNDTRIP_NO_NEXT1_OR_MISSING_EFFECTS')
 return spawn,logical,finished


def _cli_controls(rows,core):
 return [dict(key=list(v.key),token=S._token(v.token,core.rows),birth=asdict(v.birth),
  logical_birth_sha256=v.raw_birth,archived=v.archived)for v in sorted(rows,key=lambda x:x.key)]


def _owner_poll_tail(core):
 """Exact original native-control return expression; no extra dispatcher."""
 fn=ast.parse(textwrap.dedent(inspect.getsource(OriginalRelayCore.poll_native_control_once))).body[0]
 tails=[n for n in fn.body if isinstance(n,ast.Return)]
 M.need(len(tails)==1,'NATIVE_RESTORE_EXACT_ORIGINAL_OWNER_LOOP_CONTROL_TAIL')
 wrapper=ast.FunctionDef(name='_original_native_control_tail',args=ast.arguments(posonlyargs=[],
  args=[ast.arg(arg='self')],kwonlyargs=[],kw_defaults=[],defaults=[]),body=copy.deepcopy(tails),decorator_list=[])
 namespace={};exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[])),
  __file__+':original_native_owner_control_tail','exec'),dict(OriginalRelayCore.poll_native_control_once.__globals__),namespace)
 return namespace['_original_native_control_tail'](core)


@dataclass(frozen=True,repr=False)
class RestoredNativeControlRuntime:
 graph:object
 capability:S.VerifiedNativeSourceControls
 spawn:NativeSpawnOwner
 logical:dict
 finished:set
 original_source_archived_flags:tuple
 thread:int
 _seal:object
 def poll_once(self,*,read_budget):
  S._unlocked(self.graph.core)
  current_native_controls(self.graph);S.budget(read_budget)
  M.need(threading.get_ident()==self.thread,'NATIVE_RESTORE_ONLY_ORIGINAL_OWNER_LOOP_THREAD')
  poll_writer_api().require_registered_poll_writer(self.graph,read_budget=read_budget)
  return _owner_poll_tail(self.graph.core)
 def public(self):
  return dict(schema='count14-native-spawn-logical-control-restored-v1',
   exact_original_spawn_counter_and_effects=True,source_logical_map_not_inferred_from_archived=True,
   restored_logical_roles=len(self.logical),restored_completed_effects=len(self.spawn.operations),
   old_source_owner_Epoch_and_archived_CLI_provenance_preserved=True,
   native_control_only=True,new_original_SDK_runtime_granted=False,paid_activation_authorized=False,
   safe_to_TERM=False,whole_runnable_ready=False)


def current_native_controls(graph):
 S._unlocked(graph.core)
 H=host_api();value=_RESTORED.get(id(graph))
 M.need(H.registered_stage_host_graph(graph.stage)is graph and type(value)is RestoredNativeControlRuntime and
  value._seal is _SEAL and value.graph is graph and graph.core.spawn_owner is value.spawn and
  graph.core.bridge_owner.logical is value.logical and graph.core.bridge_owner.finished is value.finished and
  value.capability.new_owner_birth==process_birth(os.getpid()),'NATIVE_RESTORE_SAME_REGISTERED_NEW_OWNER_CONTROL_GRAPH')
 return value


def restore_registered_native_controls(graph,*,reference,read_budget):
 S._unlocked(graph.core)
 S.budget(read_budget);S.verify_sources();H=host_api()
 M.need(H.registered_stage_host_graph(graph.stage)is graph and id(graph)not in _RESTORED and
  graph.core.gate.closed and not graph.core.gate.waiters and
  set(graph.core.gate.startup_held)==set(graph.core.rows)and
  graph.core.spawn_owner is None and not graph.core.pending_native_launches and
  not graph.guest_plan_control.plans,
  'NATIVE_RESTORE_NEW_UNPUBLISHED_HELD_GRAPH_NO_SPAWN_OR_GUEST_ATTEMPT')
 H.verify_control_subhome(graph.socket_proof,graph.core,read_budget=read_budget)
 core=graph.core;reg=graph.registration
 cap=S.verify_reference(reference,owner=reg.source_owner,ticket=reg.source_ticket,read_budget=read_budget)
 M.need(type(cap)is S.VerifiedNativeSourceControls and cap.old_owner_birth==reg.old_owner_birth and
  cap.new_owner_birth==reg.new_owner_birth==graph.stage.new_owner_birth and
  tuple(cap.lock_fds)==tuple(graph.stage.context.lock_fds)and cap.contract_sha256==M.digest(core.contract),
  'NATIVE_RESTORE_ORIGINAL_TYPED_T_SERVICES_THREE_LOCKS_AND_BOTH_BIRTHS')
 controls=cap.snapshot()
 M.need(controls['original_bridge_cli_controls']==_cli_controls(reg.source_transfer.clis,core),
  'NATIVE_RESTORE_SOURCE_CLI_PROVENANCE_EXACT_OLD_ARCHIVED_AND_PHYSICAL_BIRTHS')
 expected={tuple(r['key']):r for r in controls['original_bridge_cli_controls']}
 for key,row in core.bridge_owner.clis.items():
  source=expected.get(key)
  M.need(source is not None and row['birth']==M.birth(source['birth'])and row['archived']is source['archived']and
   row['token']==S.unpack_token(source['token'])and row['raw_birth']==source['logical_birth_sha256']and row['end_lease']is None,
   'NATIVE_RESTORE_NEW_RECEIVING_CLI_RECORD_NOT_RETAGGED_OR_REPLACED')
 M.need(set(core.bridge_owner.clis)==set(expected),'NATIVE_RESTORE_ALL_ORIGINAL_CLI_RECORDS_RETAINED')
 spawn,logical,finished=_pure_components(core,controls)
 for key,raw in logical.items():
  anonymous=core.journals[key[0]].projection._identity(key[1],raw)
  M.need(core.roles.births.get(key)==anonymous and
   core.journals[key[0]].projection._live.get(key[1],{}).get('birth')==anonymous,
   'NATIVE_RESTORE_TRUE_SOURCE_LOGICAL_MAP_MATCHES_ORIGINAL_DURABLE_BIRTH_NOT_ARCHIVED')
 inbox=core.inbox
 M.need(inbox.lock.acquire(timeout=min(.2,read_budget.remaining())),'NATIVE_RESTORE_INBOX_CONTROL_LOCK_FINITE')
 try:M.need(not inbox.pending and inbox.unresolved==0,'NATIVE_RESTORE_NO_PENDING_RECEIPTS_DURING_NEW_CONTROL_INSTALL')
 finally:inbox.lock.release()
 new_spawn,new_bridge,new_phase=NativeSpawnInbox(),NativeBridgeInbox(),NativePhaseProofInbox()
 flags=tuple((key,row['archived'])for key,row in sorted(core.bridge_owner.clis.items()))
 # All original T/services/CLI/journal/inbox checks above precede this
 # source-derived RAM binding. Exact existing infra births are revalidated;
 # fresh bootstrap/layout constructors and late current-CID first binding are forbidden.
 I.bind_registered_receiver(graph,capability=cap,read_budget=read_budget)
 restored=RestoredNativeControlRuntime(graph,cap,spawn,logical,finished,flags,threading.get_ident(),_SEAL)
 # New core only. Source objects, paid epochs, financial rows and CLI flags do not change.
 core.spawn_owner=spawn;core.bridge_owner.logical=logical;core.bridge_owner.finished=finished
 core.spawn_inbox,core.bridge_inbox,core.phase_proof_inbox=new_spawn,new_bridge,new_phase
 core.control.server.spawn_receiver=new_spawn.receive
 core.control.server.lifecycle_receiver=new_bridge.receive
 core.control.server.phase_proof_receiver=new_phase.receive
 _RESTORED[id(graph)]=restored
 M.need(flags==tuple((key,row['archived'])for key,row in sorted(core.bridge_owner.clis.items())),
  'NATIVE_RESTORE_ORIGINAL_ARCHIVED_FLAGS_UNCHANGED')
 current_native_controls(graph);return restored
