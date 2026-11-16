"""Restore only verified ordered-control counters on the exact new HELD graph.

This does not call fresh bind(), restore a baseline, unquarantine any SDK
method or assert physical clearance. The original epochs.project(), model/HTTP
checks and actual cgroup census must still qualify normal runtime separately.
"""
from dataclasses import asdict,dataclass
from pathlib import Path
import copy
import hashlib
import importlib
import threading

import paid_cold_material as M
from native_peer_registry import process_birth
from smoke_racing_tools_kernel_custody import NativeKernelToolCustody
from smoke_racing_tools_cold_control_builder import consume_control_snapshot
import kernel_control_source_supplement as S

HOST_SHA256='dadf6ce97da5a7f57d239ac7f4bbbdd397308745c36fa9575d48c524c6ecfb85'
_SEAL=object()
_RESTORED={}


def host_api():
 value=importlib.import_module('new_owner_host_control');p=Path(value.__file__)
 expected=Path(__file__).resolve().parents[1]/'formal100m-new-owner-host-control-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/new_owner_host_control.py'
 M.need(p==expected and p.resolve()==p and not p.is_symlink()and hashlib.sha256(p.read_bytes()).hexdigest()==HOST_SHA256,
  'KERNEL_RESTORE_EXACT_FROZEN_HOST_GRAPH');return value


def _install_original_numeric_controls(custody,controls):
 """New RAM map only; input must already have the typed production proof."""
 S._validate(controls)
 M.need(type(custody)is NativeKernelToolCustody and custody.core is not None and
  not hasattr(custody,'native_control_snapshots'),'KERNEL_RESTORE_NO_EXISTING_SNAPSHOT_OVERWRITE_OR_REBASELINE')
 # Feed the exact original fixed consumer. No hand-built clear/zero snapshot.
 for row in controls['snapshots']:
  consume_control_snapshot(custody,*row['key'],M.birth(row['child']),copy.deepcopy(row['value']))
 if not controls['snapshots']:
  # A genuinely captured empty map is distinct from a missing source map.
  custody.native_control_snapshots={}
 return custody.native_control_snapshots


@dataclass(frozen=True,repr=False)
class RestoredKernelControlMetadata:
 graph:object
 capability:S.VerifiedKernelControls
 snapshots:dict
 thread:int
 _seal:object
 def public(self):
  return dict(schema='count14-kernel-ordered-control-metadata-restored-v1',
   source_snapshot_count=len(self.snapshots),same_stage_original_kernel_object=True,
   original_checked_control_and_consumer_used=True,original_sequence_and_pending_counts_preserved=True,
   fresh_bind_or_baseline_called=False,SDK_runtime_methods_unquarantined=False,
   physical_kernel_HTTP_or_model_clearance_asserted=False,actual_kernel_project_qualified=False,
   models=0,safe_to_TERM=False,paid_activation_authorized=False,whole_runnable_ready=False)


def current_kernel_controls(graph):
 S.N._unlocked(graph.core);H=host_api();value=_RESTORED.get(id(graph))
 M.need(H.registered_stage_host_graph(graph.stage)is graph and type(value)is RestoredKernelControlMetadata and
  value._seal is _SEAL and value.graph is graph and value.capability.new_owner_birth==process_birth(__import__('os').getpid())and
  graph.kernel_custody.native_control_snapshots is value.snapshots,
  'KERNEL_RESTORE_SAME_REGISTERED_CURRENT_HELD_GRAPH');return value


def restore_registered_kernel_controls(graph,*,reference,native_reference,read_budget):
 S.budget(read_budget);S.verify_sources();H=host_api();S.N._unlocked(graph.core)
 M.need(H.registered_stage_host_graph(graph.stage)is graph and id(graph)not in _RESTORED and
  graph.core.gate.closed and not graph.core.gate.waiters and
  set(graph.core.gate.startup_held)==set(graph.core.rows)and not graph.guest_plan_control.plans,
  'KERNEL_RESTORE_EXACT_NEW_HELD_GRAPH_BEFORE_ANY_GUEST_PLAN')
 reg=graph.registration;core=graph.core;custody=graph.kernel_custody
 M.need(type(custody)is NativeKernelToolCustody and custody.core is core and
  core.native_kernel_tool_custody is custody and graph.publisher.native_kernel_tool_custody is custody and
  custody.sdk_startup_epochs is reg.epochs and reg.epochs.custody is custody and
  not hasattr(custody,'native_control_snapshots'),
  'KERNEL_RESTORE_ORIGINAL_SAME_STAGE_KERNEL_RELATIONSHIPS_NO_METADATA_CLEAR_CLAIM')
 H.verify_control_subhome(graph.socket_proof,core,read_budget=read_budget)
 cap=S.verify_reference(reference,native_reference=native_reference,owner=reg.source_owner,
  ticket=reg.source_ticket,read_budget=read_budget)
 M.need(type(cap)is S.VerifiedKernelControls and cap.old_owner_birth==reg.old_owner_birth and
  cap.new_owner_birth==reg.new_owner_birth==graph.stage.new_owner_birth and
  tuple(cap.lock_fds)==tuple(graph.stage.context.lock_fds)and cap.contract_sha256==M.digest(core.contract),
  'KERNEL_RESTORE_TYPED_ORIGINAL_SOURCE_AND_STAGE_BIRTH_LOCK_LINEAGE')
 controls=cap.snapshot()
 expected=[S.epoch_anchor(epoch)for _,epoch in sorted(reg.source_transfer.current.items())]
 M.need([r['epoch']for r in controls['current_epoch_presence']]==expected and
  set(reg.epochs.current)==set(reg.source_transfer.current),
  'KERNEL_RESTORE_SOURCE_CURRENT_EPOCH_AND_COUNT_ANCHORS_NOT_REBASELINED')
 for key,epoch in reg.epochs.current.items():
  source=reg.source_transfer.current[key]
  M.need(epoch.owner_birth==reg.new_owner_birth and source.owner_birth==reg.old_owner_birth and
   S.epoch_anchor(epoch)==S.epoch_anchor(source),
   'KERNEL_RESTORE_SOURCE_CHILD_ORDINAL_REQUEST_ANCHOR_TOKEN_AND_ARCHIVED_UNCHANGED')
 snapshots=_install_original_numeric_controls(custody,controls)
 value=RestoredKernelControlMetadata(graph,cap,snapshots,threading.get_ident(),_SEAL)
 _RESTORED[id(graph)]=value;current_kernel_controls(graph);read_budget.check();return value
