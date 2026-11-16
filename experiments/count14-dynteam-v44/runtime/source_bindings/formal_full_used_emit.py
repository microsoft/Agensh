"""Original current emitter; only an independent WIP outer helper is selected."""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib.util

PIN = '0b91d0828266424258ca90939e35c938bffb4268dc6982bff639375f12a7cc04'


def parent():
    p = Path(__file__).resolve().parents[1] / 'formal100m-queue-approved-cold-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/approved_queue_emit.py'
    if p.resolve() != p or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != PIN:
        raise ValueError('FULL_USED_CURRENT_APPROVED_SDK4_EMITTER_SOURCE_PIN')
    spec = importlib.util.spec_from_file_location('count14_full_used_private_approved_emitter', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def private_emitter(*, tester_bindings_path=None, tester_bindings_sha256=None):
    m = parent().private_emitter(tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256)
    own = Path(__file__).resolve().parent
    m._idle_helper_path = own / 'formal_full_used_factory.py'
    m._idle_pin_paths = tuple(dict.fromkeys((*m._idle_pin_paths, *sorted(own.glob('*.py')))))
    return m


def emit(bindings_path, bindings_sha256, *, destination, tester_bindings_path=None, tester_bindings_sha256=None):
    m = parent()
    original = m.emit
    fn = FunctionType(original.__code__, dict(vars(m), private_emitter=private_emitter),
        original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn(bindings_path, bindings_sha256, destination=destination,
        tester_bindings_path=tester_bindings_path, tester_bindings_sha256=tester_bindings_sha256)
