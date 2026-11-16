"""One unique CURRENT original entry/companion emitter; private SDK helper."""
from pathlib import Path
from types import FunctionType
import hashlib,importlib.util
PIN='56fcdba3b7373b00754ce1d461329d6c4eb5035a9b17e351bb003a498160e741'


def parent():
    p=Path(__file__).resolve().parents[1]/'formal100m-natural-point-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_natural_emit.py'
    if p.resolve()!=p or p.is_symlink()or hashlib.sha256(p.read_bytes()).hexdigest()!=PIN:raise ValueError('SDK_RESTORE_CURRENT_NATURAL_EMITTER_PIN')
    spec=importlib.util.spec_from_file_location('count14_sdk_private_natural_emit',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def private_emitter(*,tester_bindings_path=None,tester_bindings_sha256=None):
    m=parent().private_emitter(tester_bindings_path=tester_bindings_path,tester_bindings_sha256=tester_bindings_sha256)
    own=Path(__file__).resolve().parent;m._idle_helper_path=own/'formal_sdk_factory.py'
    m._idle_pin_paths=tuple(dict.fromkeys((*m._idle_pin_paths,*sorted(own.glob('*.py')))))
    return m


def emit(bindings_path,bindings_sha256,*,destination,tester_bindings_path=None,tester_bindings_sha256=None):
    m=parent();original=m.emit;space=dict(vars(m),private_emitter=private_emitter)
    fn=FunctionType(original.__code__,space,original.__name__,original.__defaults__,original.__closure__)
    fn.__kwdefaults__=original.__kwdefaults__
    return fn(bindings_path,bindings_sha256,destination=destination,tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256)
