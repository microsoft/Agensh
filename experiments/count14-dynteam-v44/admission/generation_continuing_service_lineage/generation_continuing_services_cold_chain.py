#!/usr/bin/env python3
"""Explicit registered continuing-service lineage command atop the original cold entry.

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
PARENT = CODE / 'formal100m-generation-service-history-source-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/generation_services_cold_chain.py'
PARENT_SHA256 = '05e4f7eafabd4b880603b26e08abcf119a872c3af77b416f05da35bac765cd8b'
SOURCE_NAME = 'generation_continuing_service_source'
SOURCE_SHA256 = 'cd9f04bf4f02de38dec4132f6c67c1ec797241bbf2e169f52a8e14ec8f7fc3f0'
OP = 'PUBLISH_NORMAL_GENERATION_CONTINUING_SERVICE_CONTROLS'
EXTRA_SOURCE_FILES = (
    'generation_continuing_service_source.py',
    'held_resource_lineage_source.py', 'held_resource_lineage_decoder.py',
    'resource_epoch_continuing_producer_v6.py', 'resource_epoch_transition_v3.py',
    'resource_epoch_archive_v2.py', 'own_held_stage_pair_v3.py',
)
RETAINED_PARENT_NAMESPACE = None
RETAINED_PRIVATE_FACTORY = None
RETAINED_ORIGINAL_OWNER = None
RETAINED_ORIGINAL_LEDGER = None


def _pin(path, pin):
    s = path.lstat()
    if not (path.is_absolute() and path.resolve() == path and stat.S_ISREG(s.st_mode)
            and s.st_nlink == 1 and not s.st_mode & 0o022
            and hashlib.sha256(path.read_bytes()).hexdigest() == pin):
        raise ValueError('GENERATION_CONTINUING_ENTRY_EXACT_FROZEN_SOURCE_PIN')


def parent():
    _pin(PARENT, PARENT_SHA256)
    spec = importlib.util.spec_from_file_location('count14_generation_continuing_services_parent', PARENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_api():
    path = HERE / (SOURCE_NAME + '.py')
    _pin(path, SOURCE_SHA256)
    module = importlib.import_module(SOURCE_NAME)
    if Path(module.__file__) != path:
        raise ValueError('GENERATION_CONTINUING_ENTRY_EXACT_SOURCE_MODULE_NOT_ALIAS')
    module.verify_sources()
    return module


def verify_sources():
    old = parent().verify_sources()
    source = source_api()
    return dict(parent_sha256=PARENT_SHA256, parent=old, service_history_source_sha256=SOURCE_SHA256,
        source_path=str(Path(source.__file__)), exact_no_argument_command=OP,
        old_commands_and_original_owner_binders_unchanged=True)


def publish_services(owner):
    verify_sources()
    return source_api().publish_for_owner(owner)


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
        raise ValueError('GENERATION_CONTINUING_ENTRY_ONE_RETAINED_ORIGINAL_OWNER_NO_REPLAY')
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
        raise ValueError('GENERATION_CONTINUING_ENTRY_EXACT_CURRENT_FINANCIAL_HELPER')
    module._idle_helper_path = Path(__file__)
    module._idle_pin_paths = tuple(dict.fromkeys((*module._idle_pin_paths,
        Path(__file__), *(HERE / name for name in EXTRA_SOURCE_FILES))))
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
                raise ValueError('GENERATION_CONTINUING_ENTRY_ONLY_EXACT_NO_ARGUMENT_OPCODE')
            owner = namespace['RETAINED_OWNER']
            if owner is None:
                raise ValueError('GENERATION_CONTINUING_ENTRY_SAME_RETAINED_SOURCE_OWNER_REQUIRED')
            return publish_services(owner)
        return previous(row)
    namespace['command'] = command
    shared._generation_continuing_services_previous_command = previous
    shared._generation_continuing_services_opcode = OP
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
