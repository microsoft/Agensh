"""Original current emitter; new fixed final cold helper, same public schema."""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib.util

PIN='4672c8a3b73b0f712f220523f73f510ab7ba1cb8ceec8175578f5c09e8db6b40'


def parent():
    p=Path(__file__).resolve().parents[1]/'formal100m-complete-source-control-cold-wip-v3-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/complete_source_emit.py'
    if p.resolve()!=p or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=PIN:
        raise ValueError('NORMAL_INERT_SOURCE_CURRENT_COMPLETE_EMITTER_PIN')
    spec=importlib.util.spec_from_file_location('count14_normal_inert_source_parent_emit',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def private_emitter(*,tester_bindings_path=None,tester_bindings_sha256=None):
    module=parent().private_emitter(tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256)
    root=Path(__file__).resolve().parent
    if module._idle_helper_path!=root.parent/'formal100m-complete-source-control-cold-wip-v3-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/complete_source_factory.py':
        raise ValueError('NORMAL_INERT_SOURCE_EXACT_CURRENT_COMPLETE_HELPER')
    module._idle_helper_path=root/'normal_inert_source_factory.py'
    extra=[root.parent/'formal100m-normal-inert-cut-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/normal_inert_cut.py',
        root.parent/'formal100m-metadata-inert-pair-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/metadata_inert_pair.py']
    module._idle_pin_paths=tuple(dict.fromkeys((*module._idle_pin_paths,*sorted(root.glob('*.py')),*extra)))
    return module


def emit(bindings_path,bindings_sha256,*,destination,tester_bindings_path=None,
    tester_bindings_sha256=None,new_bindings=None):
    module=parent();original=module.emit
    fn=FunctionType(original.__code__,dict(vars(module),private_emitter=private_emitter),
        original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__=original.__kwdefaults__
    return fn(bindings_path,bindings_sha256,destination=destination,tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256,new_bindings=new_bindings)
