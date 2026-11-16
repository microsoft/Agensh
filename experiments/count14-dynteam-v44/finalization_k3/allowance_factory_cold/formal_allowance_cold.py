"""Same-owner cold allowance/control + single-dispatcher failure continuation.

No existing owner/controller is touched, no production carrier is installed,
no fault is cleared, no request replay or public-cause exemption is invented.
"""
from pathlib import Path
from types import MethodType
from common import need,digest
from formal_ast import globals_clone
from allowance_control import FormalAllowanceControl
from allowance_original import load_kernels,PINS
from allowance_native import create_allowance_final_controller
from failure_continuation import compile_new_dispatcher_poll


def ensure_formal_allowance_control(owner,*,original_kernel_paths=None,approved_repair_sources=()):
    """One exact control before cohort bind; actual-n source reuses it.

    Paths may be equivalent new-code copies, but all four ORIGINAL code pins
    and approved repair-source descriptors must agree. No second ctor is used.
    """
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    need(type(owner)is NativeColdOwner and type(owner.core)is OriginalRelayCore and not owner.errors,
        'ALLOWANCE_COLD_EXACT_PREPARED_ORIGINAL_OWNER')
    core=owner.core
    need(not core.qualification_only and not core.closed and
        set(core.gate.startup_held)==set(core.rows) and not core.scientific_activation_qualified,
        'ALLOWANCE_COLD_ONLY_BEFORE_ANY_SCIENTIFIC_ACTIVATION')
    if original_kernel_paths is None:
        from formal_actualn_cold import original_kernel_paths as registered_paths
        original_kernel_paths=registered_paths()
    approved_repair_sources=tuple(approved_repair_sources)
    kernels=load_kernels(original_kernel_paths)
    need(kernels.source_sha256==PINS,'ALLOWANCE_COLD_PINNED_ORIGINAL_POLICY_AND_PROOF_KERNELS')
    prior=getattr(core,'formal_allowance_control',None)
    approved={str(Path(path)):pin for path,pin in approved_repair_sources}
    if prior is not None:
        need(type(prior)is FormalAllowanceControl and prior.owner is owner and prior.core is core
            and prior.kernels.source_sha256==kernels.source_sha256 and prior.approved==approved,
            'ALLOWANCE_COLD_REUSE_ONLY_SAME_OWNER_POLICY_AND_APPROVAL_SET')
        prior.fresh();return prior
    return FormalAllowanceControl(owner,original_kernel_paths=original_kernel_paths,
        approved_repair_sources=approved_repair_sources)


class FormalAllowanceColdHooks:
    def __init__(self,owner,cohort,*,original_kernel_paths=None,approved_repair_sources=()):
        from native_formal_cohort import NativeFormalCohort
        from native_cold_owner import NativeColdOwner
        need(type(owner)is NativeColdOwner and type(cohort)is NativeFormalCohort and cohort.owner is owner
            and owner.scientific_smoke is cohort and cohort.core is owner.core and not owner.errors
            and not cohort.activation_attempted and cohort.final is None and cohort.source_ports is None
            and not hasattr(cohort,'formal_allowance_cold_hooks') and
            hasattr(cohort,'formal_tester_cold_sources') and
            all(row['state']=='BOUND_AWAIT_ORIGINAL_SOURCE' and row['tester']is None and row['host']is None
                for row in cohort.tracks.values()),
            'ALLOWANCE_COLD_BIND_ONLY_SAME_NEW_UNPREPARED_COHORT_AFTER_TESTER_INSTALL_PLAN')
        self.owner,self.cohort,self.core=owner,cohort,owner.core
        self.control=ensure_formal_allowance_control(owner,original_kernel_paths=original_kernel_paths,
            approved_repair_sources=approved_repair_sources)
        self.controller=None;self.dispatchers=[]
        original=cohort._prepare_one.__func__
        need('create_formal_final_controller' in original.__globals__ and
            not hasattr(cohort,'_allowance_original_prepare_one'),
            'ALLOWANCE_COLD_ONE_EXISTING_CONTROLLER_FACTORY_LOOKUP')
        self.original_prepare_one=original
        function=globals_clone(original,create_formal_final_controller=self.controller_factory)
        need(function.__code__ is original.__code__,
            'ALLOWANCE_COLD_CURRENT_TESTER_PREPARE_BODY_CODE_IDENTICAL')
        cohort._allowance_original_prepare_one=original
        cohort._prepare_one=MethodType(function,cohort)
        cohort.formal_allowance_cold_hooks=self

    def controller_factory(self,core,config_path,config_sha256):
        need(core is self.core and self.controller is None and self.cohort.final is None,
            'ALLOWANCE_COLD_EXACT_ORIGINAL_CONTROLLER_CONSTRUCTION_ONCE')
        # Original existing factory creates ONE controller, not an additional one.
        controller=create_allowance_final_controller(self.owner,config_path,config_sha256,control=self.control)
        self.controller=controller # retain before fallible cold hook composition
        original=controller._prepare.__func__
        scope_factory=original.__globals__['SmokeFinalRuntimeScope']
        def scope(*args,**kwargs):
            value=scope_factory(*args,**kwargs)
            original_dispatcher=value.dispatcher
            def dispatcher(this,*args,**kwargs):
                need(not self.dispatchers,'ALLOWANCE_COLD_ONE_ORIGINAL_SHARED_DISPATCHER_ONLY')
                result=original_dispatcher(*args,**kwargs)
                return self.bind_new_dispatcher(result)
            value.dispatcher=MethodType(dispatcher,value)
            return value
        function=globals_clone(original,SmokeFinalRuntimeScope=scope)
        need(function.__code__ is original.__code__,
            'ALLOWANCE_COLD_ORIGINAL_ALLOWANCE_CONTROLLER_PREPARE_CODE_IDENTICAL')
        controller._prepare=MethodType(function,controller)
        controller.formal_allowance_cold_hooks=self
        return controller

    def bind_new_dispatcher(self,result):
        # Explicit cold post-construction seam for ROOT's prospective fixed-code
        # producer: chain this method, then install on SAME result/control before
        # any dispatch_one. No arbitrary callback is accepted by this module.
        need(not self.dispatchers,'ALLOWANCE_COLD_ONE_ORIGINAL_SHARED_DISPATCHER_ONLY')
        self.dispatchers.append(result) # retain before compilation/bind
        qualified=compile_new_dispatcher_poll(result,self.control)
        result._poll=MethodType(qualified.body,result)
        result.formal_failure_continuation=qualified.control
        qualified.production_installed=True # SAME new instance, before any dispatch
        result.formal_failure_continuation_cold_binding=qualified
        return result

    def public(self):
        return dict(schema='count14-formal100m-allowance-cold-same-owner-hook-wip-v1',
            control_registered=type(self.control)is FormalAllowanceControl,
            original_policy_sha256=self.control.kernels.source_sha256['policy'],
            controller_created=self.controller is not None,original_dispatchers_created=len(self.dispatchers),
            third_failed_original_attempt='WAIT_ALLOWANCE_RAW4_NOT_TERMINAL',
            carrier_production_install_authorized=False,cause_producer_installed=False,
            automatic_tool_exemption=False,fees_or_REQUESTS_or_UNKNOWN_changed=False,
            actual_Dev4_or_formal_qualification=False)


def install_formal_allowance_cold_hooks(owner,cohort,*,original_kernel_paths=None,approved_repair_sources=()):
    return FormalAllowanceColdHooks(owner,cohort,original_kernel_paths=original_kernel_paths,
        approved_repair_sources=approved_repair_sources)
