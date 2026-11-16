"""Exact last cold seam; original poll/binders first, no extra runtime loop."""
from types import MethodType,ModuleType
from normal_cold_barrier import install_after_current_formal_binder
from normal_cold_sealer import NormalColdCandidateSealer,need


def install_after_binder(cohort):
    if not hasattr(cohort,'normal_cold_barrier'):
        install_after_current_formal_binder(cohort)
    owner=cohort.owner
    sealer=NormalColdCandidateSealer(owner)
    current=owner.poll
    need(current.__self__ is owner,'NORMAL_SEALER_FINAL_ORIGINAL_BOUND_OWNER_POLL')
    def poll(bound,*args,**kwargs):
        need(bound is owner,'NORMAL_SEALER_SAME_BOUND_OWNER_POLL')
        result=current(*args,**kwargs) # complete original metadata/science/health/FINAL poll first
        if sealer.requested:sealer.poll_once()
        return result
    owner.poll=MethodType(poll,owner)
    cohort.normal_cold_sealer=owner.normal_cold_sealer=cohort.core.normal_cold_sealer=sealer
    owner.request_normal_cold_candidate=MethodType(lambda own:sealer.request(),owner)
    owner.poll_normal_cold_candidate=MethodType(lambda own:sealer.poll_once(),owner)
    return sealer


def install_private_factory_last(factory):
    need(isinstance(factory,ModuleType)and factory.create_prefix_owner.__globals__ is vars(factory)and
         not hasattr(factory,'_normal_sealer_last_constructor')and
         all(vars(factory).get(k)is None for k in ('RETAINED_FACTORY_OWNER','RETAINED_FACTORY_LEDGER',
             'RETAINED_ORIGINAL_OWNER','RETAINED_ORIGINAL_LEDGER')),
         'NORMAL_SEALER_ONLY_NEW_FINAL_UNRETAINED_COLD_FACTORY')
    original=factory.private_original_constructor
    def constructor(bind_same_owner):
        helper=original(bind_same_owner)
        current=helper._formal_bind_same_owner
        def bind(owner,*,sources):
            cohort=current(owner,sources=sources)
            # Optional exact PR1 source selection is registered on this NEW
            # private helper before owner construction. Complete inner binder
            # first; actual prepare selection next; unchanged barrier/sealer last.
            source_selector=getattr(helper,'_msg238_PR1_before_normal_barrier',None)
            if source_selector is not None:
                need(type(source_selector)is __import__('types').FunctionType,
                     'NORMAL_SEALER_PRIVATE_NEW_PROVIDER_SOURCE_FUNCTION')
                source_selector(cohort)
            install_after_binder(cohort)
            return cohort
        helper._formal_bind_same_owner=bind
        return helper
    factory._normal_sealer_last_constructor=original
    factory.private_original_constructor=constructor
    factory._normal_sealer_cold_proof=dict(all_current_binders_complete_before_sealer=True,
        original_owner_poll_complete_before_observation=True,new_thread_or_dispatcher=False,
        exact_registered_production_only=True,normal_handoff_authoritative=False,actual_cold_ready=False)
    return factory
