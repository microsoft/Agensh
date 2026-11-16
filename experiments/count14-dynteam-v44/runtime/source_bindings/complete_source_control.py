"""Fixed registered framework controls, not a whole-owner transfer authority.

Extends the original candidate only. Uses the original financial/frontier code
through the already-qualified bounded RO views. No model, original transaction,
native SDK load, peer registration or new dispatcher is invoked here.
"""
from pathlib import Path
from types import FunctionType, MethodType
import hashlib
import importlib

import normal_cold_sealer as S
import bounded_metadata_ro as R
import transport_sealer_cold as T

NAMES = frozenset((
    'normal_cold_sealer', 'bounded_metadata_ro', 'transport_sealer_cold',
    'clock_controls_cold', 'native_sdk_epoch_control', 'native_sdk_epoch_control_v2', 'paid_final_source_capture',
))


COMPONENTS = {'bounded_metadata_ro': {'path': 'formal100m-normal-sealer-ro-deadline-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/bounded_metadata_ro.py', 'sha256': '621cd0db6da2d1e6422537f6ae2188ac8466627efe803d8b4d39f260bfb7c249'}, 'clock_controls_cold': {'path': 'formal100m-clock-controls-cold-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/clock_controls_cold.py', 'sha256': '395a5ad1edaf8f622f5a88d87a2cffb2bef22003bcdcb28a08b03dc9835baa29'}, 'native_sdk_epoch_control': {'path': 'formal100m-native-sdk-epoch-control-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/native_sdk_epoch_control.py', 'sha256': '6a813f5a8726c1d60a54411da8f7a0e477ec9f96a52022235db24b0f3a39bd44'}, 'native_sdk_epoch_control_v2': {'path': 'formal100m-native-sdk-epoch-control-wip-v2-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/native_sdk_epoch_control_v2.py', 'sha256': '2f7ab34a1a1a89b39bba94ee0c8801b0cac48d811b95dc51e5961b755e9bb417'}, 'normal_cold_sealer': {'path': 'formal100m-normal-cold-sealer-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/normal_cold_sealer.py', 'sha256': 'dd33e7a7a336c872086b3769f70e112942a466a18f52d099ce188ebe1e129e68'}, 'paid_final_source_capture': {'path': 'formal100m-paid-final-source-capture-wip-v3-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/paid_final_source_capture.py', 'sha256': 'ed981d7d293e2a6a0d7f8c35f01fda697d570ae563a681b613cb8b3c0f5b5e64'}, 'transport_sealer_cold': {'path': 'formal100m-normal-transport-sealer-chain-wip-v2-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/transport_sealer_cold.py', 'sha256': 'ce56d30c15d839084640bfb85e22e54d542ee1a0c63d68bbe67af12604713e88'}}

def verify_sources():
    S.need(set(COMPONENTS) == NAMES, 'COMPLETE_SOURCE_EXACT_FIXED_COMPONENT_SET')
    for name, row in COMPONENTS.items():
        source = Path(importlib.import_module(name).__file__)
        relative = Path(row['path'])
        S.need(source.is_absolute() and source.resolve() == source and not source.is_symlink()
               and not relative.is_absolute() and '..' not in relative.parts
               and source == Path(__file__).resolve().parents[1]/relative
               and hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256'],
               'COMPLETE_SOURCE_COMPONENT_SOURCE_PIN')
    S.verify_sources(); R.verify_sources(); T.verify_sources()
    return COMPONENTS


def verify_component_imports():
    verify_sources()
    return dict(fixed_original_finance_frontier_account_and_journal_code=True,
        private_RO_timeout0_VM_deadline=True,
        registered_clock_SDK_epoch_FINAL_control_capture_components=True,
        source_control_observation_not_owner_transfer=True,
        live_connection_or_schema_modified=False, multi_epoch_producer=False,
        actual_six_registered_capture_qualified=False, whole_seal_or_cold_ready=False)


def capture_extended(sealer, read_budget):
    """No caller capture callbacks. All three ports are fixed pinned functions."""
    from clock_controls_cold import capture_registered as clocks
    from native_sdk_epoch_control_v2 import capture_registered as epochs
    from paid_final_source_capture import capture_registered as final
    S.need(type(read_budget) is R.ReadBudget,
           'COMPLETE_SOURCE_ORIGINAL_BOUNDED_READ_BUDGET')
    sealer._current(); read_budget.check()
    original = S.capture_registered_metadata
    namespace = dict(original.__globals__,
        financial_controls=lambda core, approved: R.financial_controls(core, approved, read_budget),
        journal_controls=lambda core: R.journal_controls(core, read_budget))
    fn = FunctionType(original.__code__, namespace, original.__name__,
        original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    result = fn(sealer)
    for name, capture in (('normal_clock_controls', clocks),
                          ('native_SDK_epoch_controls', epochs),
                          ('paid_FINAL_controls', final)):
        read_budget.check()
        S.need(name not in result, 'COMPLETE_SOURCE_NO_ORIGINAL_FIELD_OVERWRITE')
        result[name] = capture(sealer.owner, read_budget=read_budget)
        read_budget.check()
    sealer._current()
    result['extended_source_control_scope'] = dict(
        schema='count14-complete-normal-source-controls-CANDIDATE-v1',
        source_metadata_only=True, cross_database_atomic_snapshot=False,
        new_owner_SDK_session_import_qualified=False,
        paid_normal_activation_qualified=False,
        normal_handoff_authoritative=False, safe_to_TERM=False,
        whole_paid_restore_qualified=False, actual_cold_ready=False)
    return result


def install_on_sealer(sealer):
    verify_sources()
    S.need(type(sealer) is S.NormalColdCandidateSealer,
           'COMPLETE_SOURCE_EXACT_ORIGINAL_NEW_COLD_SEALER')
    sealer._current()
    S.need(not sealer.requested and not sealer.publication_started
           and not sealer.cohort.activation_attempted
           and not sealer.core.scientific_activation_qualified
           and not hasattr(sealer, '_bounded_metadata_cold_proof'),
           'COMPLETE_SOURCE_FIRST_UNACTIVATED_UNPUBLISHED_COLD_ONLY')
    original = sealer.poll_once
    S.need(original.__func__ is S.NormalColdCandidateSealer.poll_once,
           'COMPLETE_SOURCE_ORIGINAL_CANDIDATE_POLL_NOT_PREPATCHED')
    def poll(bound):
        S.need(bound is sealer, 'COMPLETE_SOURCE_SAME_ORIGINAL_SEALER_INSTANCE')
        budget = None
        def capture_view(current):
            nonlocal budget
            if budget is None:
                # The original normal barrier runs first, unchanged. This
                # deadline bounds new metadata SQL/VM, not barrier or FS I/O.
                budget = R.ReadBudget(25)
            return capture_extended(current, budget)
        fn = FunctionType(original.__func__.__code__,
            dict(original.__func__.__globals__, capture_registered_metadata=capture_view),
            original.__func__.__name__, original.__func__.__defaults__,
            original.__func__.__closure__)
        fn.__kwdefaults__ = original.__func__.__kwdefaults__
        return fn(bound)
    sealer.poll_once = MethodType(poll, sealer)
    proof = verify_component_imports()
    sealer._bounded_metadata_cold_proof = proof
    sealer._complete_source_control_cold_proof = proof
    return dict(proof)


def install_private_factory_last(factory):
    """Same original transport binder code; only a fixed cold metadata seam."""
    verify_sources()
    namespace = dict(vars(T), install_on_sealer=install_on_sealer,
        verify_sources=verify_sources, verify_component_imports=verify_component_imports)
    old = T.install_after_binder
    bind = FunctionType(old.__code__, namespace, old.__name__,
        old.__defaults__, old.__closure__)
    bind.__kwdefaults__ = old.__kwdefaults__
    namespace['install_after_binder'] = bind
    old = T.install_private_factory_last
    installer = FunctionType(old.__code__, namespace, old.__name__,
        old.__defaults__, old.__closure__)
    installer.__kwdefaults__ = old.__kwdefaults__
    result = installer(factory)
    result._complete_source_control_cold_proof = verify_component_imports()
    return result
