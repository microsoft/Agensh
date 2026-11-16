"""Last new-cold source issuer, default inert and explicit single issuance.

This adds no owner/operator/dispatcher and does not request/repeat any barrier,
park, checkpoint, transport retirement, source capture, TERM or model action.
It only consumes the already-finished original candidate and transport steps.
"""
from pathlib import Path
from types import MethodType, ModuleType
import hashlib
import importlib

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget

TICKET_SOURCE_SHA256='aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262'
SOURCE_CONTROL_SHA256='67ccae6cd502738934aa942fa1ea078c1a030d2d53ffe258fdc763151f81332b'


def verify_sources():
    pins=dict(normal_inert_cut=TICKET_SOURCE_SHA256,complete_source_control=SOURCE_CONTROL_SHA256)
    for name,pin in pins.items():
        p=Path(importlib.import_module(name).__file__)
        M.need(len(pin)==64 and p.is_absolute() and p.resolve()==p and not p.is_symlink() and
            hashlib.sha256(p.read_bytes()).hexdigest()==pin,'NORMAL_INERT_SOURCE_COLD_FIXED_COMPONENT_PINS')
    from normal_inert_cut import verify_source_components
    verify_source_components()
    return pins


def registered(owner):
    from normal_inert_cut import NormalInertIssuer
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    M.need(type(owner) is NativeColdOwner and type(owner.core) is OriginalRelayCore and
        type(getattr(owner,'normal_inert_cut_issuer',None)) is NormalInertIssuer and
        owner.normal_inert_cut_issuer.owner is owner and owner.normal_inert_cut_issuer.core is owner.core,
        'NORMAL_INERT_SOURCE_COLD_SAME_REGISTERED_OWNER_ISSUER')
    value=owner.normal_inert_cut_issuer;value._current();return value


def status(owner):
    value=registered(owner)
    return dict(schema='count14-normal-INERT-source-cold-status-v1',
        source_issuer_registered=True,source_ticket_issued=value.ticket is not None,
        inert_only=True,paid_activation_authorized=False,whole_runnable_ready=False,safe_to_TERM=False,
        candidate_transport_or_scientific_actions_requested_automatically=False)


def issue(owner):
    value=registered(owner)
    ticket=value.issue(read_budget=ReadBudget())
    return dict(status(owner),source_ticket=dict(path=ticket.path,sha256=ticket.sha256))


def install_after_binder(cohort):
    from normal_inert_cut import NormalInertIssuer
    verify_sources()
    issuer=NormalInertIssuer(cohort.owner)
    M.need(cohort.owner.core is cohort.core and issuer.source is cohort.normal_cold_sealer,
        'NORMAL_INERT_SOURCE_COLD_AFTER_ORIGINAL_ALL_BINDERS')
    cohort.normal_inert_cut_issuer=issuer
    cohort.owner.issue_normal_inert_source_ticket=MethodType(issue,cohort.owner)
    cohort.owner.normal_inert_source_status=MethodType(status,cohort.owner)
    return issuer


def install_private_factory_last(factory):
    verify_sources()
    M.need(isinstance(factory,ModuleType) and factory.create_prefix_owner.__globals__ is vars(factory) and
        not hasattr(factory,'_normal_inert_source_last_constructor') and
        hasattr(factory,'_complete_source_control_cold_proof') and
        all(vars(factory).get(k) is None for k in ('RETAINED_FACTORY_OWNER','RETAINED_FACTORY_LEDGER',
            'RETAINED_ORIGINAL_OWNER','RETAINED_ORIGINAL_LEDGER')),
        'NORMAL_INERT_SOURCE_COLD_NEW_UNRETAINED_CURRENT_FACTORY_ONLY')
    preceding=factory.private_original_constructor
    def constructor(bind_same_owner):
        helper=preceding(bind_same_owner);current=helper._formal_bind_same_owner
        def bind(owner,*,sources):
            cohort=current(owner,sources=sources)
            install_after_binder(cohort)
            return cohort
        helper._formal_bind_same_owner=bind
        return helper
    factory._normal_inert_source_last_constructor=preceding
    factory.private_original_constructor=constructor
    factory._normal_inert_source_cold_proof=dict(
        original_all_binders_complete_source_and_retirement_first=True,
        source_ticket_issuance_explicit_only=True,existing_source_durable_reference_only=True,
        source_pre_and_post_retirement_observations_independent=True,
        new_thread_or_dispatcher=False,safe_to_TERM=False,paid_activation_authorized=False,
        whole_runnable_ready=False,actual_six_source_qualified=False)
    return factory
