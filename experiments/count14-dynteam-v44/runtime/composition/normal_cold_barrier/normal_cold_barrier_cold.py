"""Last fresh private-factory constructor seam; no existing entry opcode."""
from types import ModuleType
from normal_cold_barrier import install_after_current_formal_binder, need


def after_current_binder(current):
    def bind(owner, *, sources):
        cohort = current(owner, sources=sources)  # all CURRENT original binders first
        install_after_current_formal_binder(cohort)
        return cohort
    return bind


def install_private_factory_last(factory):
    """Caller supplies the new final private factory, before first construction."""
    need(isinstance(factory, ModuleType) and factory.create_prefix_owner.__globals__ is vars(factory)
         and not hasattr(factory, '_normal_cold_barrier_last_constructor')
         and all(vars(factory).get(k) is None for k in ('RETAINED_FACTORY_OWNER',
             'RETAINED_FACTORY_LEDGER', 'RETAINED_ORIGINAL_OWNER', 'RETAINED_ORIGINAL_LEDGER')),
         'NORMAL_BARRIER_ONLY_NEW_UNRETAINED_FINAL_PRIVATE_FACTORY')
    current = factory.private_original_constructor
    def constructor(bind_same_owner):
        helper = current(bind_same_owner)
        helper._formal_bind_same_owner = after_current_binder(helper._formal_bind_same_owner)
        return helper
    factory._normal_cold_barrier_last_constructor = current
    factory.private_original_constructor = constructor
    return factory
