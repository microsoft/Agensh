#!/usr/bin/env python3
"""Original actual native cold chain, explicit generation T and financial ports.

No automatic publication or caller paths/owners/tickets/health booleans. Old
commands and retained-owner semantics are unchanged. Metadata publication is
not writer, runnable, TERM, science release or whole delivery authority.
"""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib
import importlib.util
import json
import stat

HERE = Path(__file__).resolve().parent
CODE = HERE.parent  # Same package-root constraint as the ORIGINAL emitter.
PARENT = CODE / 'formal100m-native-control-source-entry-cold-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/native_source_cold_chain.py'
PARENT_SHA256 = '27fd9b4eb32c432c56924ea9bf2ae4dfcec31af3bca09e8a403bcf02812a5cdd'
PINS = {
    'generation_inert_cut': ('generation_inert_cut.py',
        '0d23b664bf8dcfae949c11877fd3a6160d134b1a3a1bcc7f00bd2c660e0d73c5'),
    'generation_financial_runtime_source_v2': ('generation_financial_runtime_source_v2.py',
        'd30309aa7c29b6c61b550d9f3a463f0e33913d70bd96c2e1528d9c98e0bdc162'),
    'generation_registered_issuer_v3': ('generation_registered_issuer_v3.py',
        '24e92596ec3b66362c8736625293a3299b712488edeab1b688ce1cd721e97755'),
}
OPS = ('ISSUE_NORMAL_GENERATION_INERT_SOURCE_TICKET',
       'PUBLISH_NORMAL_GENERATION_INERT_FINANCIAL_CONTROLS')
RETAINED_PARENT_NAMESPACE = None
RETAINED_PRIVATE_FACTORY = None
RETAINED_ORIGINAL_OWNER = None
RETAINED_ORIGINAL_LEDGER = None


def _pin(path, pin):
    s = path.lstat()
    if not (path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode)
            and s.st_nlink == 1 and not s.st_mode & 0o022
            and hashlib.sha256(path.read_bytes()).hexdigest() == pin):
        raise ValueError('GENERATION_ENTRY_EXACT_FROZEN_SOURCE_PIN')


def parent():
    _pin(PARENT, PARENT_SHA256)
    spec = importlib.util.spec_from_file_location('count14_generation_original_native_entry', PARENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def api(name):
    relative, pin = PINS[name]
    expected = (HERE / relative).resolve()
    _pin(expected, pin)
    module = importlib.import_module(name)
    if Path(module.__file__) != expected:
        raise ValueError('GENERATION_ENTRY_EXACT_CANONICAL_MODULE_NOT_ALIAS')
    module.verify_sources()
    return module


def verify_sources():
    original = parent()
    old = original.verify_sources()
    modules = {name: api(name) for name in PINS}
    return dict(parent_sha256=PARENT_SHA256, parent=old,
        modules={name: str(Path(module.__file__)) for name, module in modules.items()},
        explicit_no_argument_commands=list(OPS), original_binders_commands_and_owner_unchanged=True)


def issue_generation(owner):
    from bounded_metadata_ro import ReadBudget
    from normal_inert_source_cold import registered
    verify_sources()
    issuer = registered(owner)  # Original typed same owner/core/source/birth/thread.
    ticket = api('generation_registered_issuer_v3').issue_registered(issuer, read_budget=ReadBudget())
    return dict(schema='count14-generation-original-T-explicit-cold-command-v1',
        source_ticket=dict(path=ticket.path, sha256=ticket.sha256), source_metadata_only=True,
        original_services_post_clock_port_retained=True, inert_only=True,
        safe_to_TERM=False, whole_runnable_ready=False, paid_activation_authorized=False)


def publish_generation_financial(owner):
    from bounded_metadata_ro import ReadBudget
    from normal_inert_source_cold import registered
    verify_sources()
    registered(owner)  # No caller-supplied ticket, path, source dict or callback.
    reference = api('generation_financial_runtime_source_v2').publish_registered(owner, read_budget=ReadBudget())
    return dict(schema='count14-generation-original-financial-explicit-cold-command-v1',
        financial_source_reference=reference, source_metadata_only=True, inert_only=True,
        original_fixed_leaf_files_unmodified=True, safe_to_TERM=False,
        whole_runnable_ready=False, paid_activation_authorized=False)


def load_private_factory(*, tester_sources=None, tester_companion=None, approved_repair_sources=()):
    verify_sources()
    return parent().load_private_factory(tester_sources=tester_sources, tester_companion=tester_companion,
        approved_repair_sources=approved_repair_sources)


def verify_actual_formal_import_graph():
    old = parent().verify_actual_formal_import_graph()
    return dict(schema='count14-generation-explicit-original-cold-import-graph-v1', parent=old,
        source_pins=verify_sources(), original_owner_constructed=False,
        source_publication_automatic=False, safe_to_TERM=False, whole_runnable_ready=False,
        paid_activation_authorized=False)


def create_prefix_owner(bindings_path, bindings_sha256, *, code_root, factory_path, factory_manifest,
        tester_bindings_path=None, tester_bindings_sha256=None, approved_repair_sources=()):
    global RETAINED_PARENT_NAMESPACE, RETAINED_PRIVATE_FACTORY, RETAINED_ORIGINAL_OWNER, RETAINED_ORIGINAL_LEDGER
    if RETAINED_PARENT_NAMESPACE is not None:
        raise ValueError('GENERATION_ENTRY_ONE_RETAINED_ORIGINAL_OWNER_NO_REPLAY')
    verify_sources()
    module = parent()
    try:
        return module.create_prefix_owner(bindings_path, bindings_sha256, code_root=code_root,
            factory_path=factory_path, factory_manifest=factory_manifest,
            tester_bindings_path=tester_bindings_path, tester_bindings_sha256=tester_bindings_sha256,
            approved_repair_sources=tuple(approved_repair_sources))
    finally:
        RETAINED_PARENT_NAMESPACE = module.RETAINED_PARENT_NAMESPACE
        RETAINED_PRIVATE_FACTORY = module.RETAINED_PRIVATE_FACTORY
        RETAINED_ORIGINAL_OWNER = module.RETAINED_ORIGINAL_OWNER
        RETAINED_ORIGINAL_LEDGER = module.RETAINED_ORIGINAL_LEDGER


def private_emitter(*, tester_bindings_path=None, tester_bindings_sha256=None):
    verify_sources()
    original = parent()
    module = original.private_emitter(tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256)
    if module._idle_helper_path != PARENT:
        raise ValueError('GENERATION_ENTRY_EXACT_CURRENT_NATIVE_HELPER')
    module._idle_helper_path = Path(__file__)
    extra = [Path(__file__), *((HERE / relative).resolve() for relative, _ in PINS.values())]
    module._idle_pin_paths = tuple(dict.fromkeys((*module._idle_pin_paths, *extra)))
    return module


def emit(bindings_path, bindings_sha256, *, destination, tester_bindings_path=None,
        tester_bindings_sha256=None, new_bindings=None):
    module = parent()
    original = module.emit
    fn = FunctionType(original.__code__, dict(vars(module), private_emitter=private_emitter),
        original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn(bindings_path, bindings_sha256, destination=destination,
        tester_bindings_path=tester_bindings_path, tester_bindings_sha256=tester_bindings_sha256,
        new_bindings=new_bindings)


def private_namespace(original):
    shared = parent().private_namespace(original)
    namespace = vars(shared)
    previous = namespace['command']
    def command(row):
        if type(row) is dict and row.get('op') in OPS:
            if set(row) != {'op'}:
                raise ValueError('GENERATION_ENTRY_ONLY_EXACT_NO_ARGUMENT_OPCODE')
            owner = namespace['RETAINED_OWNER']
            if owner is None:
                raise ValueError('GENERATION_ENTRY_SAME_RETAINED_SOURCE_OWNER_REQUIRED')
            return issue_generation(owner) if row['op'] == OPS[0] else publish_generation_financial(owner)
        return previous(row)
    namespace['command'] = command
    shared._generation_source_previous_command = previous
    shared._generation_source_ops = OPS
    return shared


def original_entry():
    return parent().original_entry()


def main(argv=None):
    try:
        return private_namespace(original_entry()).main(argv)
    except Exception as error:
        frames, tb = [], error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                function=tb.tb_frame.f_code.co_name))
            tb = tb.tb_next
        print(json.dumps(dict(PUBLIC_code='GENERATION_SOURCE_COLD_CHAIN_ENTRY_REFUSED',
            exception_type=type(error).__name__, locations=frames,
            message_or_private_body_exported=False), sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
