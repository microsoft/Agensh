"""NEW stage-owned SDK metadata graph, never a native-load authority.

Original typed source cap and registration are retained, not moved/retagged.
Only fresh receiving Epoch/session objects refer to the exact held stage core.
Same-SID original bind is usable; new claims/end/runtime stay quarantined.
"""
from dataclasses import dataclass, replace
from pathlib import Path
from types import MethodType
import copy
import hashlib
import importlib
import os

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import process_birth
from native_sdk_startup_epochs import NativeSdkStartupEpochs, Pending
from dynteam_sessions import AffinityDomain, DynamicSessions
import new_owner_sdk_registration as R
import normal_held_financial_writer as H
import normal_inert_cut as T

PINS = dict(new_owner_sdk_registration='f12cde63a0d01a12e20c901178e2a707303caadc20ffde9d1c47cafa38162334',
            normal_held_financial_writer='686247ad8d2ca768abf1dc0085ac4a18e58419f37e2bceb61b152d8f8b413261',
            normal_inert_cut='aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262')
_SEAL = object()
_REGISTERED = {}


def verify_sources():
    for name, expected in PINS.items():
        path = Path(importlib.import_module(name).__file__)
        M.need(path.is_absolute() and path.resolve() == path and not path.is_symlink()
               and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
               'NEW_OWNER_GUEST_FIXED_SOURCE_AND_STAGE_PINS')
    R.verify_sources(); H.verify_sources()
    return dict(PINS)


def _wait(*args, **kwargs):
    raise M.PaidColdWait('NEW_OWNER_GUEST_METADATA_NOT_LEGAL_PLAN_KERNEL_CLI_OR_SDK_AUTHORITY')


@dataclass(frozen=True, repr=False)
class StageSdkControls:
    stage: object
    source_owner: object
    source_ticket: object
    source_registration: R.InertSdkRegistration
    source_transfer: object
    source_section: dict
    epochs: NativeSdkStartupEpochs
    sessions: object
    old_owner_birth: object
    new_owner_birth: object
    source_control_sha256: str
    _seal: object

    def public(self):
        return dict(schema='count14-new-stage-sdk-control-registration-v1',
                    source_control_sha256=self.source_control_sha256,
                    exact_stage_core=self.epochs.core is self.stage.core,
                    old_epoch_provenance_retained=True,
                    original_source_registration_moved_or_retagged=False,
                    receiving_epoch_count=len(self.epochs.current),
                    same_original_SID_bind_only=True, new_session_claim_or_end_authorized=False,
                    native_load_authority=False, host_strict_ACK=False, once_recovery=False,
                    paid_activation_authorized=False, safe_to_TERM=False, whole_runnable_ready=False)


def registered_stage_sdk_controls(stage):
    value = _REGISTERED.get(id(stage))
    M.need(type(value) is StageSdkControls and value._seal is _SEAL and value.stage is stage
           and stage.core.native_sdk_stage_registration is value
           and stage.core.sessions is value.sessions
           and stage.core.native_sdk_startup_epochs is value.epochs
           and value.epochs.core is stage.core
           and value.new_owner_birth == process_birth(os.getpid()),
           'NEW_OWNER_GUEST_EXACT_REGISTERED_STAGE_RECEIVING_GRAPH')
    return value


def register_stage_sdk_controls(stage, *, owner, ticket, read_budget):
    verify_sources()
    M.need(type(read_budget) is ReadBudget, 'NEW_OWNER_GUEST_FINITE_METADATA_BUDGET')
    record = H._same(stage, read_budget, own=False)
    M.need(record['owner'] is owner and record['ticket'] is ticket
           and type(ticket) is T.NormalInertTicket and stage.context.source_owner is owner
           and id(stage) not in _REGISTERED
           and getattr(stage.core, 'sessions', None) is None
           and getattr(stage.core, 'native_sdk_startup_epochs', None) is None,
           'NEW_OWNER_GUEST_ONLY_NEW_UNHYDRATED_REGISTERED_HELD_STAGE')
    cap = T.verify_inert_ticket(ticket, owner=owner, read_budget=read_budget)
    source = getattr(owner.core, 'inert_sdk_transfer_registration', None)
    M.need(type(cap) is T.VerifiedNormalInertCut and cap.OWN is False
           and type(source) is R.InertSdkRegistration and source.owner is owner
           and owner.core.native_sdk_startup_epochs is source.epochs
           and source.epochs.core is owner.core and owner.core is not stage.core
           and cap.old_owner_birth == source.old_owner_birth == stage.old_owner_birth
           and cap.new_owner_birth == source.new_owner_birth == stage.new_owner_birth
           and cap.source_control_sha256 == source.source_control_sha256
           and cap.component('native_SDK_epoch_controls') == source.source_section,
           'NEW_OWNER_GUEST_TYPED_ORIGINAL_SOURCE_LINEAGE_AND_NEW_STAGE_NOT_OLD_CORE')
    M.need(stage.core.gate.closed and not stage.core.gate.waiters
           and set(stage.core.gate.startup_held) == set(stage.core.rows),
           'NEW_OWNER_GUEST_SEARCH_REMAINS_HELD')
    history = R._full_used_history(owner, cap, source.source_section, read_budget)
    decoded = R._metadata_codec(source.source_section, history)
    sessions = R._new_sessions(stage.core, source.source_section, decoded, history)
    # These are fresh RAM objects. No original source epoch or reg is modified.
    receiving = tuple(replace(epoch, owner_birth=stage.new_owner_birth,
                              stage='NEW_STAGE_CONTROL_RECEIVED_RUNTIME_HELD')
                      for epoch in decoded.epochs)
    remap = {id(old): new for old, new in zip(decoded.epochs, receiving)}
    moved = lambda epoch: None if epoch is None else remap[id(epoch)]
    epochs = NativeSdkStartupEpochs.__new__(NativeSdkStartupEpochs)
    epochs.core, epochs.owner, epochs.sha, epochs.custody = stage.core, stage.new_owner_birth, cap.contract_sha256, None
    epochs.current = {key: moved(epoch) for key, epoch in decoded.current.items()}
    epochs.history = [moved(epoch) for epoch in decoded.history]
    epochs.pending = {key: Pending(moved(p.epoch), moved(p.previous), copy.deepcopy(p.control))
                      for key, p in decoded.pending.items()}
    epochs.partial = set(decoded.partial)
    epochs.session_prepared = {key: moved(epoch) for key, epoch in decoded.session_prepared.items()}
    epochs.session_bound = {key: moved(epoch) for key, epoch in decoded.session_bound.items()}
    R._first_quarantine(epochs, NativeSdkStartupEpochs,
                        metadata=('_owner', '_count', '_requests_all', '_session'))
    # The ORIGINAL bind returns before domain.claim for the identical pair.
    # All other SID claims and end transitions are refused on these NEW objects.
    R._first_quarantine(next(iter(sessions.tracks.values())).domain, AffinityDomain)
    for track in sessions.tracks.values():
        R._first_quarantine(track, DynamicSessions, metadata=('bind',))
    M.need(NativeSdkStartupEpochs._requests_all(epochs) == source.epochs._requests_all(),
           'NEW_OWNER_GUEST_ORIGINAL_TOTAL_REQUEST_COUNT_NOT_REBASELINED')
    for row in source.source_section['counts']['by_registered_epoch_role']:
        M.need(NativeSdkStartupEpochs._count(epochs, tuple(row['key'])) == row['original_request_rows'],
               'NEW_OWNER_GUEST_ORIGINAL_ROLE_REQUEST_ANCHORS_UNCHANGED')
    result = StageSdkControls(stage, owner, ticket, source, decoded, copy.deepcopy(source.source_section),
                              epochs, sessions, stage.old_owner_birth, stage.new_owner_birth,
                              cap.source_control_sha256, _SEAL)
    # Retain exactly one published NEW graph. No source quarantine is removed.
    _REGISTERED[id(stage)] = result
    stage.core.sessions = sessions
    stage.core.native_sdk_startup_epochs = epochs
    stage.core.native_sdk_stage_registration = result
    def current():
        M.need(registered_stage_sdk_controls(stage) is result,
               'NEW_OWNER_GUEST_SAME_NEW_RECEIVING_METADATA_GRAPH')
        NativeSdkStartupEpochs._owner(epochs)
    def count(_epochs, key):
        current(); return NativeSdkStartupEpochs._count(epochs, key)
    def all_count(_epochs):
        current(); return NativeSdkStartupEpochs._requests_all(epochs)
    def session(_epochs, key):
        current(); return NativeSdkStartupEpochs._session(epochs, key)
    epochs._count = MethodType(count, epochs)
    epochs._requests_all = MethodType(all_count, epochs)
    epochs._session = MethodType(session, epochs)
    for key, pair in decoded.current_original_session_pairs.items():
        M.need(epochs._session(key) == pair, 'NEW_OWNER_GUEST_EXACT_SOURCE_SID_PAIR')
    read_budget.check()
    return result
