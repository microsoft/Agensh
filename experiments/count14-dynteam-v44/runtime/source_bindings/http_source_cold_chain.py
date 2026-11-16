#!/usr/bin/env python3
"""Same frozen source/factory/emitter, plus one explicit HTTP-control opcode.

No second capture, owner, science constructor or dispatcher. The old source
must still be alive after original T, services, native and kernel publication.
"""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib
import importlib.util
import json

PARENT_SHA256 = 'daad48586a851408991dcfe86b7bfbc3e9d7e34a59b38e6ded2d84f86e0c1aa1'
SOURCE_SHA256 = '892dbacf932d2d6f5e5904cf8777631916d416f3338f016d95cc145ed87a3164'
OP = 'PUBLISH_NORMAL_INERT_HTTP_CONTROLS'
RETAINED_PARENT_NAMESPACE = None
RETAINED_PRIVATE_FACTORY = None
RETAINED_ORIGINAL_OWNER = None
RETAINED_ORIGINAL_LEDGER = None


def parent():
    path = Path(__file__).resolve().parents[1]/'formal100m-kernel-control-source-entry-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/kernel_source_cold_chain.py'
    if path.resolve()!=path or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=PARENT_SHA256:
        raise ValueError('HTTP_SOURCE_ENTRY_FIXED_ORIGINAL_KERNEL_CHAIN')
    spec = importlib.util.spec_from_file_location('count14_http_source_kernel_parent',path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def source_api():
    value = importlib.import_module('http_runtime_source_control')
    path = Path(value.__file__)
    expected = Path(__file__).resolve().parents[1]/'formal100m-http-runtime-source-control-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/http_runtime_source_control.py'
    if SOURCE_SHA256 is None or path!=expected or path.resolve()!=path or path.is_symlink() \
            or hashlib.sha256(path.read_bytes()).hexdigest()!=SOURCE_SHA256:
        raise ValueError('HTTP_SOURCE_ENTRY_FIXED_REAL_SOURCE_CONTROL_COMPONENT')
    value.verify_sources()
    return value


def verify_sources():
    parent().verify_sources()
    source_api()
    return dict(parent_sha256=PARENT_SHA256,http_source_sha256=SOURCE_SHA256,
                original_binders_and_commands_unchanged=True,new_opcode=OP)


def publish_http(owner):
    from bounded_metadata_ro import ReadBudget
    reference = source_api().publish_registered(owner,read_budget=ReadBudget())
    return dict(schema='count14-http-source-actual-cold-entry-publication-v1',
                http_control_source_reference=reference,source_metadata_only=True,
                inert_only=True,safe_to_TERM=False,paid_activation_authorized=False,
                whole_runnable_ready=False,new_dispatcher=False)


def load_private_factory(*args,**kwargs):
    verify_sources()
    return parent().load_private_factory(*args,**kwargs)


def verify_actual_formal_import_graph():
    proof=parent().verify_actual_formal_import_graph()
    return dict(schema='count14-http-native-kernel-source-actual-import-graph-v1',
                parent=proof,source_pins=verify_sources(),http_publication_explicit_only=True,
                original_owner_constructed=False,safe_to_TERM=False,
                paid_activation_authorized=False,whole_runnable_ready=False)


def create_prefix_owner(bindings_path,bindings_sha256,*,code_root,factory_path,
                        factory_manifest,tester_bindings_path=None,tester_bindings_sha256=None,
                        approved_repair_sources=()):
    global RETAINED_PARENT_NAMESPACE,RETAINED_PRIVATE_FACTORY,RETAINED_ORIGINAL_OWNER,RETAINED_ORIGINAL_LEDGER
    if RETAINED_PARENT_NAMESPACE is not None:
        raise ValueError('HTTP_SOURCE_ENTRY_ONE_RETAINED_ORIGINAL_OWNER_NO_REPLAY')
    verify_sources()
    value = parent()
    try:
        return value.create_prefix_owner(bindings_path,bindings_sha256,code_root=code_root,
            factory_path=factory_path,factory_manifest=factory_manifest,
            tester_bindings_path=tester_bindings_path,tester_bindings_sha256=tester_bindings_sha256,
            approved_repair_sources=tuple(approved_repair_sources))
    finally:
        RETAINED_PARENT_NAMESPACE = value.RETAINED_PARENT_NAMESPACE
        RETAINED_PRIVATE_FACTORY = value.RETAINED_PRIVATE_FACTORY
        RETAINED_ORIGINAL_OWNER = value.RETAINED_ORIGINAL_OWNER
        RETAINED_ORIGINAL_LEDGER = value.RETAINED_ORIGINAL_LEDGER


def private_emitter(*,tester_bindings_path=None,tester_bindings_sha256=None):
    original = parent()
    value = original.private_emitter(tester_bindings_path=tester_bindings_path,
                                      tester_bindings_sha256=tester_bindings_sha256)
    if value._idle_helper_path!=Path(original.__file__):
        raise ValueError('HTTP_SOURCE_ENTRY_EXACT_CURRENT_KERNEL_HELPER')
    value._idle_helper_path = Path(__file__).resolve()
    source_path = Path(__file__).resolve().parents[1]/'formal100m-http-runtime-source-control-wip-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/http_runtime_source_control.py'
    value._idle_pin_paths = tuple(dict.fromkeys((*value._idle_pin_paths,Path(__file__).resolve(),source_path)))
    return value


def emit(bindings_path,bindings_sha256,*,destination,tester_bindings_path=None,
         tester_bindings_sha256=None,new_bindings=None):
    module = parent()
    old = module.emit
    function = FunctionType(old.__code__,dict(vars(module),private_emitter=private_emitter),
                            old.__name__,old.__defaults__,old.__closure__)
    function.__kwdefaults__ = old.__kwdefaults__
    return function(bindings_path,bindings_sha256,destination=destination,
        tester_bindings_path=tester_bindings_path,tester_bindings_sha256=tester_bindings_sha256,
        new_bindings=new_bindings)


def private_namespace(original):
    shared = parent().private_namespace(original)
    namespace = vars(shared)
    previous = namespace['command']
    def command(row):
        if type(row) is dict and row.get('op')==OP:
            if set(row)!={'op'}:
                raise ValueError('HTTP_SOURCE_ENTRY_EXACT_NO_ARGUMENT_OPCODE')
            owner = namespace['RETAINED_OWNER']
            if owner is None:
                raise ValueError('HTTP_SOURCE_ENTRY_SAME_RETAINED_SOURCE_OWNER_REQUIRED')
            return publish_http(owner)
        return previous(row)
    namespace['command'] = command
    shared._http_source_previous_command = previous
    shared._http_source_opcode = OP
    return shared


def original_entry():
    return parent().original_entry()


def main(argv=None):
    try:
        return private_namespace(original_entry()).main(argv)
    except Exception as error:
        frames=[]
        tb=error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,
                               function=tb.tb_frame.f_code.co_name))
            tb=tb.tb_next
        print(json.dumps(dict(PUBLIC_code='HTTP_SOURCE_ACTUAL_COLD_CHAIN_ENTRY_REFUSED',
            exception_type=type(error).__name__,locations=frames,
            message_or_private_body_exported=False),sort_keys=True))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
