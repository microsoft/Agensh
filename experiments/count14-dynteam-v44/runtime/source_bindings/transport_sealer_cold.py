"""Last NEW cold binder; unchanged paid/SYSTEM poll first, explicit request only.

This seam does not provide whole-cut/TERM authority or opaque SDK recovery.
"""
from types import MethodType, ModuleType
from pathlib import Path
import hashlib
import importlib
from normal_transport_retirement import NormalTransportRetirement, need
from bounded_metadata_cold import install_on_sealer, verify_component_imports


def verify_sources():
    pins = dict(normal_transport_retirement='51774562e2c0f6d26b90f2b307ec265a1da11c06553c7965535cdbddd827f9c2',
        bounded_metadata_cold='a151c0c832b3ab7ac74b3f2dc642fecea846eaf4a186c7028475170a37d179d2',
        bounded_metadata_ro='621cd0db6da2d1e6422537f6ae2188ac8466627efe803d8b4d39f260bfb7c249')
    for name, pin in pins.items():
        path = Path(importlib.import_module(name).__file__)
        need(path.resolve() == path and not path.is_symlink()
             and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
             'NORMAL_TRANSPORT_CHAIN_UNCHANGED_QUALIFIED_ORIGINAL_AND_RO_SOURCES')
    return pins


def registered(owner):
    value = getattr(owner, 'normal_transport_retirement', None)
    proof = getattr(owner, '_normal_transport_sealer_chain', None)
    need(type(value) is NormalTransportRetirement and type(proof) is dict
         and proof.get('owner') is owner and proof.get('retirement') is value
         and proof.get('barrier') is value.barrier and value.owner is owner
         and owner.core is value.core and owner.core.normal_transport_retirement is value
         and owner.normal_cold_barrier is value.barrier,
         'NORMAL_TRANSPORT_CHAIN_EXACT_LAST_COLD_REGISTERED_COMPONENT')
    return value


def status(owner):
    value = registered(owner)
    return dict(schema='count14-normal-transport-current-cold-chain-WIP-v1',
        explicit_runtime_control_opcode_installed=True,
        fixed_source_component=value.public(), default_automatic_retirement=False,
        normal_candidate_is_authority=False, whole_cold_ready=False,
        safe_to_TERM=False, opaque_SDK_pending_restore_qualified=False)


def request(owner):
    value = registered(owner)
    value._current()
    need(not value.requested, 'NORMAL_TRANSPORT_CHAIN_EXPLICIT_REQUEST_ONCE')
    # Original idempotent barrier request only. Never request the candidate
    # producer or collect/enqueue/park/freeze/archive a second time here.
    value.barrier.request_barrier()
    value.request()
    return status(owner)


def poll(owner):
    value = registered(owner)
    value.poll()  # a non-requested poll cannot start retirement
    return status(owner)


def install_after_binder(cohort):
    """Called only AFTER every existing current binder completed successfully."""
    owner = cohort.owner
    need(owner.normal_cold_sealer is cohort.normal_cold_sealer
         and owner.normal_cold_barrier is cohort.normal_cold_barrier
         and owner.core is cohort.core and not hasattr(owner, '_normal_transport_sealer_chain'),
         'NORMAL_TRANSPORT_CHAIN_CURRENT_SEALER_AND_BARRIER_ALREADY_BOUND')
    install_on_sealer(owner.normal_cold_sealer)
    retirement = NormalTransportRetirement(cohort.normal_cold_barrier)
    current = owner.poll
    need(current.__self__ is owner, 'NORMAL_TRANSPORT_CHAIN_CURRENT_ORIGINAL_BOUND_OWNER_POLL')
    proof = dict(owner=owner, retirement=retirement, barrier=cohort.normal_cold_barrier,
                 preceding_poll=current)
    owner._normal_transport_sealer_chain = proof
    def owner_poll(bound, *args, **kwargs):
        need(bound is owner, 'NORMAL_TRANSPORT_CHAIN_SAME_ORIGINAL_OWNER_POLL')
        result = current(*args, **kwargs)
        # All original resource/SYSTEM/paid FINAL/science polls stay live.
        # The original candidate sealer is NOT requested automatically.
        if retirement.requested:
            retirement.poll()
        return result
    owner.poll = MethodType(owner_poll, owner)
    owner.request_normal_http_transport_retirement = MethodType(request, owner)
    owner.poll_normal_http_transport_retirement = MethodType(poll, owner)
    cohort.normal_transport_retirement = retirement
    return retirement


def install_private_factory_last(factory):
    verify_sources()
    need(isinstance(factory, ModuleType) and factory.create_prefix_owner.__globals__ is vars(factory)
         and not hasattr(factory, '_normal_transport_last_constructor')
         and hasattr(factory, '_normal_sealer_cold_proof')
         and all(vars(factory).get(k) is None for k in ('RETAINED_FACTORY_OWNER',
             'RETAINED_FACTORY_LEDGER', 'RETAINED_ORIGINAL_OWNER', 'RETAINED_ORIGINAL_LEDGER')),
         'NORMAL_TRANSPORT_CHAIN_NEW_UNRETAINED_CURRENT_FACTORY_ONLY')
    original = factory.private_original_constructor
    def constructor(bind_same_owner):
        helper = original(bind_same_owner)
        current = helper._formal_bind_same_owner
        def bind(owner, *, sources):
            cohort = current(owner, sources=sources)
            install_after_binder(cohort)
            return cohort
        helper._formal_bind_same_owner = bind
        return helper
    factory._normal_transport_last_constructor = original
    factory.private_original_constructor = constructor
    factory._normal_transport_chain_proof = dict(all_current_binders_and_sealer_complete_first=True,
        complete_original_owner_poll_before_transport_poll=True, request_is_explicit_only=True,
        original_NORMAL_candidate_requested_automatically=False, new_thread_or_dispatcher=False,
        whole_cold_ready=False, safe_to_TERM=False, opaque_SDK_pending_restore_qualified=False)
    factory._bounded_metadata_cold_component_proof = verify_component_imports()
    return factory
