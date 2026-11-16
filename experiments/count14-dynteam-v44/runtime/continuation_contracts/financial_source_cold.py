"""Explicit metadata-only financial sidecar, after the original INERT issuer.

No source action is run by installation. The existing original ticket must
already have been issued and its HTTP transport normally retired. This seam
does not issue that ticket, poll a barrier, retire anything or grant a writer.
"""
from pathlib import Path
from types import MethodType, ModuleType
import hashlib
import importlib

SOURCE_SHA256 = '5d7aedc421df71583d55ec6ffc32cd80389c1f944ed93c3dcad99b433d38f906'
PARENT_SHA256 = 'addd82d80c31d83a661cafc3d7a9dd9fbc8942f0cb6526b6d1e9621330ba094a'


def verify_sources():
    import paid_cold_material as M
    pins = dict(financial_runtime_source_control=SOURCE_SHA256,
                normal_inert_source_cold=PARENT_SHA256)
    for name, pin in pins.items():
        path = Path(importlib.import_module(name).__file__)
        M.need(type(pin) is str and len(pin) == 64 and path.is_absolute()
               and path.resolve() == path and not path.is_symlink()
               and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
               'FINANCIAL_SOURCE_COLD_FIXED_COMPONENT_PINS')
    from financial_runtime_source_control import verify_sources as verify_finance
    from normal_inert_source_cold import verify_sources as verify_parent
    verify_finance(); verify_parent()
    return pins


def publish(owner):
    from bounded_metadata_ro import ReadBudget
    from financial_runtime_source_control import publish_registered
    from normal_inert_source_cold import registered
    verify_sources()
    registered(owner)  # Original exact same-owner issuer, not a caller callback.
    reference = publish_registered(owner, read_budget=ReadBudget())
    return dict(schema='count14-financial-source-cold-publication-status-v1',
                financial_source_reference=reference, original_INERT_ticket_unmodified=True,
                inert_only=True, source_metadata_only=True, new_dispatcher=False,
                safe_to_TERM=False, whole_runnable_ready=False,
                paid_activation_authorized=False)


def install_after_binder(cohort):
    import paid_cold_material as M
    from normal_inert_source_cold import registered
    verify_sources()
    value = registered(cohort.owner)
    M.need(value.source is cohort.normal_cold_sealer and cohort.owner.core is cohort.core
           and not hasattr(cohort.owner, 'publish_normal_inert_financial_controls'),
           'FINANCIAL_SOURCE_COLD_AFTER_ORIGINAL_ISSUER_ONCE')
    cohort.owner.publish_normal_inert_financial_controls = MethodType(publish, cohort.owner)
    return value


def install_private_factory_last(factory):
    import paid_cold_material as M
    verify_sources()
    M.need(isinstance(factory, ModuleType)
           and factory.create_prefix_owner.__globals__ is vars(factory)
           and hasattr(factory, '_normal_inert_source_cold_proof')
           and not hasattr(factory, '_financial_source_cold_last_constructor')
           and all(vars(factory).get(k) is None for k in (
               'RETAINED_FACTORY_OWNER', 'RETAINED_FACTORY_LEDGER',
               'RETAINED_ORIGINAL_OWNER', 'RETAINED_ORIGINAL_LEDGER')),
           'FINANCIAL_SOURCE_COLD_NEW_UNRETAINED_CURRENT_FACTORY_ONLY')
    previous = factory.private_original_constructor

    def constructor(bind_same_owner):
        helper = previous(bind_same_owner)
        current = helper._formal_bind_same_owner

        def bind(owner, *, sources):
            cohort = current(owner, sources=sources)
            install_after_binder(cohort)
            return cohort

        helper._formal_bind_same_owner = bind
        return helper

    factory._financial_source_cold_last_constructor = previous
    factory.private_original_constructor = constructor
    factory._financial_source_cold_proof = dict(
        original_source_issuer_and_all_binders_first=True,
        publication_explicit_only=True, original_ticket_or_candidate_rewritten=False,
        barrier_capture_retirement_or_TERM_automatically_requested=False,
        new_thread_or_dispatcher=False, safe_to_TERM=False,
        paid_activation_authorized=False, whole_runnable_ready=False,
        actual_production_six_runtime_qualified=False)
    return factory
