"""Direct typed WIP factory; NO public-binding compiler or formal release yet.

OPS's future frozen factory calls this with the SAME original NativeColdOwner
kwargs and new aggregate FINAL descriptor. Not an alternate ledger/dispatcher.
Cold import pins must select the epoch-hooked copies BEFORE this module imports
any original owner/core class. This function never patches an imported module.
"""
import inspect
from pathlib import Path
from common import need

RETAINED_FORMAL_OWNER = None
RETAINED_FORMAL_LEDGER = None


def require_cold_sdk_epoch_hooks():
    from smoke_racing_tools_kernel_custody import NativeKernelToolCustody
    from native_bridge_owner import NativeBridgeLifecycleOwner
    from native_metadata_publisher import NativeMetadataPublisher
    # Structural checks complement (not replace) the future package SHA map.
    # Fail before core/ledger actions if someone supplied the old import graph.
    need(callable(getattr(NativeKernelToolCustody, 'commit_native_session', None)) and
         'epochs.prepare_birth' in inspect.getsource(NativeKernelToolCustody.observe_cli_birth) and
         'epochs.commit_birth' in inspect.getsource(NativeBridgeLifecycleOwner) and
         'custody.commit_native_session' in inspect.getsource(NativeMetadataPublisher),
         'FORMAL_REQUIRES_PINNED_NEW_INTERPRETER_COLD_SDK_EPOCH_HOOKS_NO_HOT_PATCH')


def create_formal_prefix_owner(*, owner_arguments, sources, game_sources, tester_execution_ports=None):
    global RETAINED_FORMAL_OWNER, RETAINED_FORMAL_LEDGER
    from native_cold_owner import NativeColdOwner
    from smoke_racing_tools_kernel_custody import NativeKernelToolCustody
    from native_sdk_startup_epochs import NativeSdkStartupEpochs
    from native_formal_cohort import bind_formal_cohort, FormalCohortSources
    from formal_scope import validate_contract
    from common import digest
    need(RETAINED_FORMAL_OWNER is None and RETAINED_FORMAL_LEDGER is None and
         type(owner_arguments) is dict and type(sources) is FormalCohortSources and
         'original_tool_physical_clear' not in owner_arguments,
         'FORMAL_UNIQUE_NEW_TYPED_FACTORY_NO_CALLER_REPLACEMENT_CUSTODY')
    require_cold_sdk_epoch_hooks()
    arguments = dict(owner_arguments)
    contract = arguments['core_arguments']['contract']
    validate_contract(contract, digest(contract))
    need(arguments['core_arguments']['home'] == Path(contract['arms'][0]['root']) / 'owner',
         'FORMAL_ORIGINAL_ARMS0_NEW_OWNER_HOME_SELECTOR')
    custody = NativeKernelToolCustody()
    arguments['original_tool_physical_clear'] = custody
    RETAINED_FORMAL_LEDGER = arguments['core_arguments']['ledger']
    owner = NativeColdOwner.prepare(**arguments)
    RETAINED_FORMAL_OWNER = owner
    if owner.errors:
        return owner  # original constructor's partial owner/ledger stay retained
    phase = 'BINDING_ORIGINAL_KERNEL_CUSTODY'
    try:
        custody.bind(owner.core)
        phase = 'BINDING_NORMAL_NATIVE_SDK_STARTUP_EPOCHS'
        NativeSdkStartupEpochs(custody)
        phase = 'BINDING_FORMAL_SAME_OWNER_COHORT'
        bind_formal_cohort(owner, sources=sources, game_sources=game_sources,
            tester_execution_ports=tester_execution_ports)
    except Exception as error:
        frames, tb = [], error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                               function=tb.tb_frame.f_code.co_name))
            tb = tb.tb_next
        owner.errors.append(dict(PUBLIC_code='FORMAL_FACTORY_PARTIAL_RETAINED_NO_RETRY',
            exception_type=type(error).__name__, phase=phase, locations=frames))
        owner.state = 'PARTIAL_RETAINED_MODELS_NOT_ACTIVATED'
    return owner
