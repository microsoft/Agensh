"""One prospective fixed PUBLIC producer cold hook after allowance bind.

No new owner/core/queue/capacity/control/controller/dispatcher, no carrier or
repair grant, no automatic fee exemption. ORIGINAL objects remain the objects.
"""
from pathlib import Path
from types import MethodType
from common import need,hash_file
from formal_allowance_cold import FormalAllowanceColdHooks
from fixed_public_code_producer import install_fixed_public_code_producer,FixedPublicCodeProducer

PRODUCER_SHA='61cb73eb4a70097529d95f1011a86b4676bdbc09038f2c59a71037c8b656526c'


class FormalFixedCodeColdHooks:
    def __init__(self,cohort):
        from native_formal_cohort import NativeFormalCohort
        from allowance_control import FormalAllowanceControl
        need(type(cohort)is NativeFormalCohort and not cohort.activation_attempted and cohort.final is None
            and cohort.source_ports is None and not hasattr(cohort,'formal_fixed_public_code_cold_hook'),
            'FIXED_CODE_FACTORY_COLD_BEFORE_FIRST_COHORT_PREPARE_ONLY')
        hooks=getattr(cohort,'formal_allowance_cold_hooks',None)
        need(type(hooks)is FormalAllowanceColdHooks and hooks.cohort is cohort and hooks.core is cohort.core
            and hooks.owner is cohort.owner and type(hooks.control)is FormalAllowanceControl
            and cohort.core.formal_allowance_control is hooks.control and not hooks.dispatchers
            and hooks.controller is None and set(cohort.core.gate.startup_held)==set(cohort.tracks),
            'FIXED_CODE_FACTORY_EXISTING_EXACT_SAME_OWNER_CONTROL_ALLOWANCE_HOOKS')
        hooks.control.fresh()
        import fixed_public_code_producer
        need(hash_file(Path(fixed_public_code_producer.__file__).resolve())['sha256']==PRODUCER_SHA,
            'FIXED_CODE_FACTORY_EXACT_FROZEN_PRODUCER_SOURCE')
        self.cohort,self.hooks,self.control=cohort,hooks,hooks.control
        self.producers=[];self.original_bind_new_dispatcher=hooks.bind_new_dispatcher
        def bind(own,result):
            need(own is hooks and not self.producers,
                'FIXED_CODE_FACTORY_ONE_FRESH_SHARED_DISPATCHER_ONLY')
            value=self.original_bind_new_dispatcher(result) # ORIGINAL same-d failurepoll first
            need(value is result and result.queue is self.control.core.queue and
                result.ledger is self.control.core.ledger,
                'FIXED_CODE_FACTORY_NEVER_REPLACE_DISPATCHER_OR_ORIGINAL_FINANCIAL_PORTS')
            producer=install_fixed_public_code_producer(result,self.control)
            self.producers.append(producer)
            need(type(producer)is FixedPublicCodeProducer and producer.dispatcher is result and
                producer.control is self.control,
                'FIXED_CODE_FACTORY_SAME_EXACT_OBJECTS_AFTER_ORIGINAL_INSTALL')
            return result
        hooks.bind_new_dispatcher=MethodType(bind,hooks)
        cohort.formal_fixed_public_code_cold_hook=self

    def public(self):
        return dict(schema='count14-formal-fixed-public-code-cold-hook-wip-v1',
            prospective_hook_registered=True,actual_producers_created=len(self.producers),
            producer_source_sha256=PRODUCER_SHA,automatic_tool_exemptions=0,
            carrier_install_authorized=False,model_calls=0,actual_Dev4_or_formal_qualified=False)


def install(cohort):
    return FormalFixedCodeColdHooks(cohort)
