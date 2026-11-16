"""Cold instance-only metadata seam, no original class/module hot modification."""
from types import FunctionType,MethodType
import normal_cold_sealer as S
from bounded_metadata_ro import ReadBudget,financial_controls,journal_controls,verify_sources


def verify_component_imports():
    verify_sources()
    return dict(fixed_original_finance_frontier_account_and_journal_code=True,
        private_RO_timeout0_VM_deadline=True,live_connection_or_schema_modified=False,
        multi_epoch_producer=False,whole_seal_or_cold_ready=False)


def install_on_sealer(sealer):
    verify_sources()
    S.need(type(sealer)is S.NormalColdCandidateSealer,'BOUNDED_RO_EXACT_NEW_NORMAL_SEALER')
    sealer._current()
    S.need(not sealer.requested and not sealer.publication_started and
        not sealer.cohort.activation_attempted and not sealer.core.scientific_activation_qualified and
        not hasattr(sealer,'_bounded_metadata_cold_proof'),
        'BOUNDED_RO_INSTALL_ONLY_FIRST_COLD_BEFORE_SCIENCE_OR_CAPTURE')
    original=sealer.poll_once
    S.need(original.__func__ is S.NormalColdCandidateSealer.poll_once,
        'BOUNDED_RO_ORIGINAL_NORMAL_SEALER_BOUND_POLL')
    capture=S.capture_registered_metadata
    def poll(bound):
        S.need(bound is sealer,'BOUNDED_RO_SAME_OWNER_SEALER_INSTANCE')
        budget=None
        def capture_view(current):
            nonlocal budget
            if budget is None:budget=ReadBudget(25) # AFTER unchanged original barrier.poll
            budget.check()
            namespace=dict(capture.__globals__,
                financial_controls=lambda core,approved:financial_controls(core,approved,budget),
                journal_controls=lambda core:journal_controls(core,budget))
            fn=FunctionType(capture.__code__,namespace,capture.__name__,capture.__defaults__,capture.__closure__)
            fn.__kwdefaults__=capture.__kwdefaults__
            result=fn(current);budget.check();return result
        fn=FunctionType(original.__func__.__code__,dict(original.__func__.__globals__,
            capture_registered_metadata=capture_view),original.__func__.__name__,
            original.__func__.__defaults__,original.__func__.__closure__)
        fn.__kwdefaults__=original.__func__.__kwdefaults__
        return fn(bound)
    sealer.poll_once=MethodType(poll,sealer)
    sealer._bounded_metadata_cold_proof=verify_component_imports()
    return dict(sealer._bounded_metadata_cold_proof)
