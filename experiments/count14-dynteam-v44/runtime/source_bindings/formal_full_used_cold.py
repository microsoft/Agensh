"""Fresh-only instance hooks BEFORE the first formal cohort constructor.

No financial writes, model hooks, class/global patch, new shared configuration,
snapshot capability promotion or whole-owner restore. Normal framework private
control under the existing new owner home is the only new runtime storage.
"""
from dataclasses import asdict
from pathlib import Path
from types import FunctionType, MethodType
import os

from formal_full_used_domain import FullUsedDomainProducer, digest, need, verify_session_source

PARENT_FACTORY_SHA256 = '68985fc4c4967ad6efd967a9b188c299bb6f2d690fdfa6cd10d548275436bc92'


def install_before_formal(owner):
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    from native_metadata_publisher import NativeMetadataPublisher
    from native_peer_registry import process_birth
    need(type(owner) is NativeColdOwner and type(owner.core) is OriginalRelayCore and
         not owner.errors and not hasattr(owner, 'scientific_smoke'),
         'FULL_USED_INSTALL_BEFORE_FIRST_FORMAL_CONSTRUCTOR')
    core = owner.core
    need(not core.qualification_only and not core.closed and
         core.contract['mode'] == 'production' and len(core.rows) == 6 and
         set(core.gate.startup_held) == set(core.rows) and
         not core.scientific_activation_qualified and not owner.bootstrap.records and
         type(core.publisher) is NativeMetadataPublisher and core.publisher.sessions is core.sessions and
         not hasattr(core, 'formal_full_used_domain'),
         'FULL_USED_EXACT_NEW_HELD_FORMAL_GRAPH_NO_NATIVE_SESSION')
    # Current original binder installs fresh SDK epochs itself, before creating
    # the formal cohort. Do not require/move/replay that not-yet-run constructor.
    if hasattr(core, 'native_sdk_startup_epochs'):
        from native_sdk_startup_epochs import NativeSdkStartupEpochs
        need(type(core.native_sdk_startup_epochs) is NativeSdkStartupEpochs and
             not core.native_sdk_startup_epochs.current, 'FULL_USED_NO_EXISTING_NATIVE_EPOCH')
    need(not core.ledger.mutex._is_owned(), 'FULL_USED_INSTALL_OUTSIDE_SCIENCE_LOCK')
    with core.ledger.mutex:
        need(core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0] == 0,
             'FULL_USED_INSTALL_NEVER_ADOPTS_PAID_HISTORY')
    control = FullUsedDomainProducer(core.sessions, core.home / 'full-affinity-domain-control-v1',
        science_mutex=core.ledger.mutex, source_binding=dict(
            contract_sha256=digest(core.contract), cohort_sha256=digest(sorted(core.rows)),
            owner_sha256=digest(asdict(process_birth(os.getpid()))),
            factory_parent_sha256=PARENT_FACTORY_SHA256))
    core.formal_full_used_domain = control
    return control


def bind_checkpoint(control, checkpoint):
    from native_dynamic_checkpoint import DynamicCheckpointPorts
    core = checkpoint.core
    need(type(checkpoint) is DynamicCheckpointPorts and core.formal_full_used_domain is control and
         core.sessions is control.sessions and checkpoint.state == 'BOUND_MODELS_HELD' and
         checkpoint.t in core.gate.startup_held and not hasattr(checkpoint, 'formal_full_used_domain'),
         'FULL_USED_ONLY_ORIGINAL_NEW_HELD_CHECKPOINT')
    original = checkpoint._bridge_control
    def bridge(bound):
        base = original() # original ledger/session locks released before our call
        writer = checkpoint.writer
        need(writer is not None and writer.cut is not None and
             checkpoint.state in ('PARKED', 'COMMITTED', 'COLLECTION_STARTED', 'POINT_QUEUED', 'FINAL_PARKED') and
             'full_shared_affinity_used_domain' not in base,
             'FULL_USED_ONLY_ORIGINAL_FROZEN_PER_TRACK_WRITER_CUT')
        sidecar = control.protected_for_cut(dict(cut_sha256=writer.cut.cut_sha,
            trajectory_sha256=digest(checkpoint.t), membership_sha256=digest(writer.membership_token)))
        # Original _bridge writes this to protected NATIVE_CONTROL -> opaque CAS.
        # No PUBLIC method/export receives the raw full_used list.
        return {**base, 'full_shared_affinity_used_domain': sidecar}
    checkpoint._bridge_control = MethodType(bridge, checkpoint)
    checkpoint.formal_full_used_domain = control
    return checkpoint


def finish_after_formal(cohort, control):
    from native_formal_cohort import NativeFormalCohort
    need(type(cohort) is NativeFormalCohort and cohort.core.formal_full_used_domain is control and
         cohort.core.sessions is control.sessions and not cohort.activation_attempted and
         cohort.final is None and not hasattr(cohort, 'formal_full_used_domain'),
         'FULL_USED_SAME_FIRST_FORMAL_COHORT_AFTER_CURRENT_PARENT_BINDER')
    current = cohort._prepare_one.__func__
    parent_host = current.__globals__['FormalHostWriters']
    def host(*args, **kwargs):
        value = parent_host(*args, **kwargs) # SDK4/natural/approved hooks run first
        bind_checkpoint(control, value.checkpoint)
        return value
    fn = FunctionType(current.__code__, dict(current.__globals__, FormalHostWriters=host),
        current.__name__, current.__defaults__, current.__closure__)
    fn.__kwdefaults__ = current.__kwdefaults__
    cohort._prepare_one = MethodType(fn, cohort)
    cohort.formal_full_used_domain = control
    return cohort


def before_after_binder(binder, before=install_before_formal, after=finish_after_formal):
    """One seam also exercised offline with explicit synthetic constructor ports."""
    def bind(owner, *, sources):
        control = before(owner)
        cohort = binder(owner, sources=sources)
        return after(cohort, control)
    return bind


def verify_component_imports():
    return dict(original_sessions_sha256=verify_session_source(),
        installs_before_formal_constructor=True, normal_claim_body_unchanged=True,
        current_approved_SDK4_natural_graph_preserved=True,
        raw_SID_only_in_protected_control=True, per_track_cut_is_not_whole_cohort=True,
        no_ledger_model_or_shared_configuration_change=True,
        whole_paid_restore_factory_implemented=False, actual_cold_qualified=False)
