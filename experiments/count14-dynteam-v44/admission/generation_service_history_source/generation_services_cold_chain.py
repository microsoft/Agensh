#!/usr/bin/env python3
"""One explicit service+SYSTEM-history source command atop original cold entry.

Original generation T/financial, native and earlier commands stay unchanged.
No action occurs during import, factory verification, emitter or installation.
This command publishes metadata only; it is not writer/science/TERM authority.
"""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib
import importlib.util
import json
import stat

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
PARENT = CODE / 'formal100m-generation-financial-source-entry-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/generation_source_cold_chain_v3.py'
PARENT_SHA256 = '367ec09cad67ccb9a33196e860e15cc4d7c5c863c42abec216b84f29b6926b69'
SOURCE_NAME = 'generation_service_history_source_v3'
SOURCE_SHA256 = '00c0e1885e7222248b74bd0c22e72cc9c83a98fa386c8646f861e89fe683a6a1'
OP = 'PUBLISH_NORMAL_GENERATION_INERT_SERVICE_CONTROLS'
RETAINED_PARENT_NAMESPACE = None
RETAINED_PRIVATE_FACTORY = None
RETAINED_ORIGINAL_OWNER = None
RETAINED_ORIGINAL_LEDGER = None


def _pin(path, pin):
    s = path.lstat()
    if not (path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode)
            and s.st_nlink == 1 and not s.st_mode & 0o022
            and hashlib.sha256(path.read_bytes()).hexdigest() == pin):
        raise ValueError('GENERATION_SERVICE_ENTRY_EXACT_FROZEN_SOURCE_PIN')


def parent():
    _pin(PARENT, PARENT_SHA256)
    spec = importlib.util.spec_from_file_location('count14_generation_services_financial_parent', PARENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_api():
    path = HERE / (SOURCE_NAME + '.py')
    _pin(path, SOURCE_SHA256)
    module = importlib.import_module(SOURCE_NAME)
    if Path(module.__file__) != path:
        raise ValueError('GENERATION_SERVICE_ENTRY_EXACT_SOURCE_MODULE_NOT_ALIAS')
    module.verify_sources()
    return module


def verify_sources():
    old = parent().verify_sources()
    source = source_api()
    return dict(parent_sha256=PARENT_SHA256, parent=old, service_history_source_sha256=SOURCE_SHA256,
        source_path=str(Path(source.__file__)), exact_no_argument_command=OP,
        old_commands_and_original_owner_binders_unchanged=True)


def publish_services(owner):
    from bounded_metadata_ro import ReadBudget
    from services_source_cold_chain import registered
    from source_services_controls import capture_registered
    verify_sources()
    registered(owner)  # Original typed same owner/core/issuer and real retirement methods.
    source = source_api()
    budget = ReadBudget()
    cap = capture_registered(owner.core, read_budget=budget)
    service = source.publish_source(owner, source_cap=cap, read_budget=budget)
    history = source.publish_system_history(owner, source_cap=cap,
        service_reference=source.load_service_reference(service['path'], service['sha256']), read_budget=budget)
    return dict(schema='count14-generation-original-services-history-explicit-cold-command-v1',
        service_source_reference=service, system_history_source_reference=history,
        source_metadata_only=True, original_control_history_bytes_and_None_values_preserved=True,
        inert_only=True, safe_to_TERM=False, whole_runnable_ready=False,
        paid_activation_authorized=False, live_scheduler_or_sampler_restored=False)


def load_private_factory(*, tester_sources=None, tester_companion=None, approved_repair_sources=()):
    verify_sources()
    return parent().load_private_factory(tester_sources=tester_sources, tester_companion=tester_companion,
        approved_repair_sources=approved_repair_sources)


def verify_actual_formal_import_graph():
    old = parent().verify_actual_formal_import_graph()
    return dict(schema='count14-generation-services-original-cold-import-graph-v1', parent=old,
        source_pins=verify_sources(), original_owner_constructed=False,
        source_publication_automatic=False, safe_to_TERM=False, whole_runnable_ready=False,
        paid_activation_authorized=False)


def create_prefix_owner(bindings_path, bindings_sha256, *, code_root, factory_path, factory_manifest,
        tester_bindings_path=None, tester_bindings_sha256=None, approved_repair_sources=()):
    global RETAINED_PARENT_NAMESPACE, RETAINED_PRIVATE_FACTORY, RETAINED_ORIGINAL_OWNER, RETAINED_ORIGINAL_LEDGER
    if RETAINED_PARENT_NAMESPACE is not None:
        raise ValueError('GENERATION_SERVICE_ENTRY_ONE_RETAINED_ORIGINAL_OWNER_NO_REPLAY')
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
    module = parent().private_emitter(tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256)
    if module._idle_helper_path != PARENT:
        raise ValueError('GENERATION_SERVICE_ENTRY_EXACT_CURRENT_FINANCIAL_HELPER')
    module._idle_helper_path = Path(__file__)
    module._idle_pin_paths = tuple(dict.fromkeys((*module._idle_pin_paths,
        Path(__file__), HERE / (SOURCE_NAME + '.py'))))
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
        if type(row) is dict and row.get('op') == OP:
            if set(row) != {'op'}:
                raise ValueError('GENERATION_SERVICE_ENTRY_ONLY_EXACT_NO_ARGUMENT_OPCODE')
            owner = namespace['RETAINED_OWNER']
            if owner is None:
                raise ValueError('GENERATION_SERVICE_ENTRY_SAME_RETAINED_SOURCE_OWNER_REQUIRED')
            return publish_services(owner)
        return previous(row)
    namespace['command'] = command
    shared._generation_services_previous_command = previous
    shared._generation_services_opcode = OP
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
        print(json.dumps(dict(PUBLIC_code='GENERATION_SERVICE_SOURCE_COLD_CHAIN_ENTRY_REFUSED',
            exception_type=type(error).__name__, locations=frames,
            message_or_private_body_exported=False), sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
