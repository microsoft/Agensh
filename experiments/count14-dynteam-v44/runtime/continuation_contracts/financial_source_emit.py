"""Original emitter and schema, fixed financial source helper/code pins only."""
from pathlib import Path
from types import FunctionType
import hashlib
import importlib.util

PIN = 'cdd005497924e0018c3ed8755d6f4017dd8e718cd651a81ee3835a2a2600829d'


def parent():
    path = Path(__file__).resolve().parents[1] / 'formal100m-normal-inert-source-cold-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/normal_inert_source_emit.py'
    if path.resolve() != path or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != PIN:
        raise ValueError('FINANCIAL_SOURCE_CURRENT_ORIGINAL_EMITTER_PIN')
    spec = importlib.util.spec_from_file_location('count14_financial_source_parent_emit', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def private_emitter(*, tester_bindings_path=None, tester_bindings_sha256=None):
    module = parent().private_emitter(tester_bindings_path=tester_bindings_path,
                                     tester_bindings_sha256=tester_bindings_sha256)
    root = Path(__file__).resolve().parent
    if module._idle_helper_path != root.parent/'formal100m-normal-inert-source-cold-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/normal_inert_source_factory.py':
        raise ValueError('FINANCIAL_SOURCE_EXACT_CURRENT_ORIGINAL_HELPER')
    module._idle_helper_path = root/'financial_source_factory.py'
    extra = [*sorted(root.glob('*.py')),
             *sorted((root.parent/'formal100m-financial-runtime-source-control-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1').glob('*.py')),
             *sorted((root.parent/'formal100m-staged-financial-runtime-wip-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1').glob('*.py'))]
    module._idle_pin_paths = tuple(dict.fromkeys((*module._idle_pin_paths, *extra)))
    return module


def emit(bindings_path, bindings_sha256, *, destination, tester_bindings_path=None,
         tester_bindings_sha256=None, new_bindings=None):
    module = parent(); original = module.emit
    fn = FunctionType(original.__code__, dict(vars(module), private_emitter=private_emitter),
                      original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn(bindings_path, bindings_sha256, destination=destination,
              tester_bindings_path=tester_bindings_path,
              tester_bindings_sha256=tester_bindings_sha256, new_bindings=new_bindings)
