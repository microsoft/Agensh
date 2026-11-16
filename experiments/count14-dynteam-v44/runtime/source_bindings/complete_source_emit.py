"""Original current emitter code; only final helper and fixed-source pins vary."""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib.util

PIN = '855b692706c74f726f118f27d4a3ef0d21f345ef9508566898b908c59a59dbea'


def parent():
    path = Path(__file__).resolve().parents[1]/'formal100m-normal-transport-sealer-chain-wip-v2-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/transport_sealer_emit.py'
    if path.resolve() != path or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != PIN:
        raise ValueError('COMPLETE_SOURCE_CURRENT_TRANSPORT_EMITTER_PIN')
    spec = importlib.util.spec_from_file_location('count14_complete_source_parent_emitter', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def private_emitter(*, tester_bindings_path=None, tester_bindings_sha256=None):
    module = parent().private_emitter(tester_bindings_path=tester_bindings_path,
                                    tester_bindings_sha256=tester_bindings_sha256)
    own = Path(__file__).resolve().parent
    if module._idle_helper_path != own.parent/'formal100m-normal-transport-sealer-chain-wip-v2-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/transport_sealer_factory.py':
        raise ValueError('COMPLETE_SOURCE_EXACT_CURRENT_PARENT_HELPER')
    module._idle_helper_path = own/'complete_source_factory.py'
    extra = []
    for leaf in ('formal100m-clock-controls-cold-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1',
                 'formal100m-native-sdk-epoch-control-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1',
                 'formal100m-native-sdk-epoch-control-wip-v2-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1',
                 'formal100m-paid-final-source-capture-wip-v3-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1'):
        extra.extend(sorted((own.parent/leaf).glob('*.py')))
    module._idle_pin_paths = tuple(dict.fromkeys((*module._idle_pin_paths,
        *sorted(own.glob('*.py')), *extra)))
    return module


def emit(bindings_path, bindings_sha256, *, destination, tester_bindings_path=None,
         tester_bindings_sha256=None, new_bindings=None):
    module = parent(); original = module.emit
    fn = FunctionType(original.__code__, dict(vars(module), private_emitter=private_emitter),
        original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn(bindings_path, bindings_sha256, destination=destination,
        tester_bindings_path=tester_bindings_path, tester_bindings_sha256=tester_bindings_sha256,
        new_bindings=new_bindings)
