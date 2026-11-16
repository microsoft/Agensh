"""One new private registry: truthful optional StopSignal default acceptance.

The raw ScopedDocker projection remains None if the optional field is absent.
No invented empty string, image/config change, signal, container or fee action.
Explicit non-default signals still follow the unchanged original rejection.
This component is not a same-process repair entry or deployment authority.
"""
from pathlib import Path
from types import MethodType
import ast
import copy
import hashlib
import inspect
import os
import textwrap

SOURCE_SHA = '9cba289507f8fe65da64b75d737595585e08a58241d1badda88effc9f43926a3'
SMOKE_SHA = 'a009fcb9880fe694db540c6c9d8742d5e77ba1ce2314ee3b9018517f42f58e1e'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def compile_validate(module):
    path = Path(module.__file__)
    need(path.resolve() == path and not path.is_symlink() and
         hashlib.sha256(path.read_bytes()).hexdigest() == SOURCE_SHA,
         'OPTIONAL_NATIVE_STOPSIGNAL_EXACT_ORIGINAL_VALIDATOR_SOURCE')
    original = module.NativeContainerRegistry.validate
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    before = copy.deepcopy(tree)
    target = ast.parse("snapshot['stop_signal'] in ('', 'SIGTERM', '15')", mode='eval').body
    selected = ast.parse("snapshot['stop_signal'] is None or snapshot['stop_signal'] in ('', 'SIGTERM', '15')", mode='eval').body
    sites = []
    class Select(ast.NodeTransformer):
        def generic_visit(self, node):
            if ast.dump(node, include_attributes=False) == ast.dump(target, include_attributes=False):
                sites.append(node)
                return copy.deepcopy(selected)
            return super().generic_visit(node)
    tree = Select().visit(tree)
    need(len(sites) == 1, 'OPTIONAL_NATIVE_STOPSIGNAL_ONE_EXACT_ORIGINAL_BOOLEAN_SITE')
    inverse = copy.deepcopy(tree)
    class Reverse(ast.NodeTransformer):
        def generic_visit(self, node):
            if ast.dump(node, include_attributes=False) == ast.dump(selected, include_attributes=False):
                return copy.deepcopy(target)
            return super().generic_visit(node)
    inverse = Reverse().visit(inverse)
    need(ast.dump(inverse, include_attributes=False) == ast.dump(before, include_attributes=False),
         'OPTIONAL_NATIVE_STOPSIGNAL_ALL_OTHER_SCOPE_IMAGE_MOUNT_KERNEL_STATE_GUARDS_UNCHANGED')
    ns = {}
    exec(compile(ast.fix_missing_locations(tree), __file__ + ':one-private-optional-field-predicate', 'exec'), original.__globals__, ns)
    return ns[original.__name__], dict(schema='count14-native-optional-default-stop-signal-private-validator-v1',
        original_source_sha256=SOURCE_SHA, inverse_original_AST=True, boolean_sites=1,
        raw_missing_optional_value_remains_null=True, explicit_nondefault_signals_not_admitted=True,
        all_original_scope_image_mount_running_state_kernel_PID_namespace_guards_preserved=True,
        original_class_method_module_or_active_graph_modified=False, models_or_container_or_financial_actions=0)


def bind_new_registry(core, *, stage, financial, core_restore, fresh_guard):
    """Only a genuine new cold graph, before first boot-plan/peer adoption."""
    from common import digest
    from original_relay_core import OriginalRelayCore
    import native_container_retirement as module
    need(type(core) is OriginalRelayCore and not core.ledger.mutex._is_owned() and
         financial.current_stage(stage, read_budget=financial.ReadBudget()) is stage and
         core_restore.current_core(stage, read_budget=financial.ReadBudget()) is core and
         core.pre_request_financial_stage is stage and core.ledger is stage.ledger and
         not core.closed and not core.scientific_activation_qualified and
         set(core.gate.startup_held) == set(core.rows) and not core.peers._peers and
         callable(fresh_guard) and fresh_guard() is True,
         'OPTIONAL_NATIVE_STOPSIGNAL_GENUINE_SAME_NEW_EXCLUSIVE_STAGE_CORE_HELD')
    need(core.contract['mode'] == 'smoke' and
         (core.qualification_only and os.uname().nodename != 'H100DEV4' or
          not core.qualification_only and digest(core.contract) == SMOKE_SHA),
         'OPTIONAL_NATIVE_STOPSIGNAL_ONLY_EXACT_OWN_EXPERIMENT_SMOKE_NOT_OTHER_PROJECT')
    registry = core.native_containers
    need(type(registry) is module.NativeContainerRegistry and registry.core is core and
         not registry.records and not registry.boot_plans and 'validate' not in vars(registry),
         'OPTIONAL_NATIVE_STOPSIGNAL_ONE_NEW_EMPTY_GENUINE_REGISTRY_NO_LIVE_PATCH_OR_RETRY')
    with core.ledger.mutex:
        need(core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0] == 0 and
             core.ledger.db.execute('SELECT COUNT(*) FROM unknown_charges').fetchone()[0] == 0,
             'OPTIONAL_NATIVE_STOPSIGNAL_NO_REQUEST_OR_UNKNOWN_POLICY_EXCEPTION')
    function, proof = compile_validate(module)
    registry.validate = MethodType(function, registry)
    return proof
