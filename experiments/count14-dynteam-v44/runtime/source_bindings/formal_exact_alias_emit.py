"""ONE generated-source constant over CURRENT full-used outer emitter.

No new loader/science loop. The original exact alias hook/bridge/PUBLIC bytes
are cold-bound before the current outer import graph can import the sampler.
"""
from pathlib import Path
from types import FunctionType
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
import stat

PARENT_SHA256 = '8c227571768267d2ce6c5591de370379e5f3c9c0add65efe42d6353d7eb96768'
HOOK_SHA256 = '3973d537a4989f931230e1a3ab430da73155c37c11d722af448ecd9a40c188d6'
CONSTRUCTOR_SHA256 = '71de11f1bb3f778b9d4afc7ce965d18fd4f7ed9dcf49bcb6fdbf622cea9dd29f'
SOURCES = ('exact_alias_cold_hook.py', 'path_bridge.py', 'formal_exact_alias_emit.py',
           'qualify_formal_exact_alias.py', 'test_formal_exact_alias_OWN.py',
           'private_config_cold_hook.py', 'exact_private_config_projection_v1.py')
ANCHOR = 'guard.verify_framework_imports(@REGISTRY@,@REGISTRY_SHA@,code_root=Path(@CODE_ROOT@))\n'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def pinned(path, expected):
    path = Path(path)
    s = path.lstat()
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
         stat.S_ISREG(s.st_mode) and not s.st_mode & 0o022 and s.st_uid in (0, os.geteuid()) and
         s.st_nlink == 1 and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
         'FORMAL_EXACT_ALIAS_FIXED_REGULAR_CODE_PIN')
    return path


def parent():
    # Preserve the CURRENT emitter's original source guard. Its adjacent WIP
    # sources are not a frozen execution tree; do not invent a new mode gate.
    path = Path(__file__).resolve().parents[1] / 'formal100m-full-used-domain-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_full_used_emit.py'
    need(path.resolve() == path and not path.is_symlink() and
         hashlib.sha256(path.read_bytes()).hexdigest() == PARENT_SHA256,
         'FORMAL_EXACT_ALIAS_CURRENT_FULL_USED_EMITTER_SOURCE_PIN')
    spec = importlib.util.spec_from_file_location('count14_exact_alias_private_current_full_used_emit', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cloned_emit(original, hook_path):
    hook_path = pinned(hook_path, HOOK_SHA256)
    block = '''_alias_hook_path=Path(@EXACT_HOOK@)
_alias_hook_stat=_alias_hook_path.lstat()
if not (_alias_hook_path.resolve()==_alias_hook_path and not _alias_hook_path.is_symlink() and
        __import__('stat').S_ISREG(_alias_hook_stat.st_mode) and not _alias_hook_stat.st_mode&0o022 and
        _alias_hook_stat.st_uid in (0,__import__('os').geteuid()) and _alias_hook_stat.st_nlink==1 and
        hashlib.sha256(_alias_hook_path.read_bytes()).hexdigest()==@EXACT_HOOK_SHA@):
    raise ValueError('FORMAL_EXACT_ALIAS_GENERATED_FROZEN_HOOK_PIN')
_alias_spec=importlib.util.spec_from_file_location('count14_formal_exact_alias_cold_hook',_alias_hook_path)
_alias_hook=importlib.util.module_from_spec(_alias_spec)
_alias_spec.loader.exec_module(_alias_hook)
# The ORIGINAL guard above stays at aggregate/runtime-v1. The actual registered
# P is in this existing F subtree; use its REAL same-byte constructor, not a
# forged __file__, alternate registry, baseline loader, or weakened hook guard.
_alias_code_root=Path(@CODE_ROOT@)/'racing-complete-cold-tree-v4-msg237-held20-v1-msg237-prefix21-v1'
_alias_constructor_path=_alias_code_root/'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/smoke_bootstrap_task_factory.py'
_alias_hook.pinned(_alias_constructor_path,_alias_hook.CONSTRUCTOR_SHA256)
_alias_constructor_spec=importlib.util.spec_from_file_location('count14_formal_exact_alias_private_F_constructor',_alias_constructor_path)
_alias_constructor=importlib.util.module_from_spec(_alias_constructor_spec)
_alias_constructor_spec.loader.exec_module(_alias_constructor)
_alias_hook.install(_alias_constructor,code_root=_alias_code_root)
'''.replace('@EXACT_HOOK@', repr(str(hook_path))).replace('@EXACT_HOOK_SHA@', repr(HOOK_SHA256))
    constants = original.__code__.co_consts
    matches = [(i, v) for i, v in enumerate(constants) if type(v) is str and
        v.startswith('# Prospective formal SAME-owner factory: import never creates owner.\n')]
    need(len(matches) == 1, 'FORMAL_EXACT_ALIAS_ONE_CURRENT_GENERATED_SOURCE_CONSTANT')
    index, before = matches[0]
    following = "spec=importlib.util.spec_from_file_location('count14_actual_formal_cold_factory',HELPER)\n"
    need(before.count(ANCHOR) == 1 and ANCHOR + following in before and
         before.count('module.verify_actual_formal_import_graph()\n') == 1,
         'FORMAL_EXACT_ALIAS_ONLY_AFTER_REGISTRY_BEFORE_CURRENT_OUTER_IMPORT')
    after = before.replace(ANCHOR, ANCHOR + block, 1)
    need(after.replace(block, '', 1) == before and after.count(block) == 1,
         'FORMAL_EXACT_ALIAS_ONE_CONSTANT_EXACT_INVERSE')
    def parsed(value):
        for token in ('ORIGINAL', 'ORIGINAL_SHA', 'HELPER', 'HELPER_SHA', 'REGISTRY',
                      'REGISTRY_SHA', 'CODE_ROOT', 'BINDINGS', 'BINDINGS_SHA', 'MANIFEST'):
            value = value.replace('@' + token + '@', repr('OWN-' + token))
        return ast.parse(value)
    need(ast.dump(parsed(after.replace(block, '', 1)), include_attributes=False) ==
         ast.dump(parsed(before), include_attributes=False), 'FORMAL_EXACT_ALIAS_INVERSE_AST_CURRENT')
    changed = list(constants)
    changed[index] = after
    code = original.__code__.replace(co_consts=tuple(changed))
    need(code.co_code == original.__code__.co_code and code.replace(co_consts=constants) == original.__code__,
         'FORMAL_EXACT_ALIAS_CURRENT_EMIT_BYTECODE_AND_ONE_CONST_INVERSE')
    fn = FunctionType(code, original.__globals__, original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    return fn, dict(one_generated_source_const_changed=True, inverse_const_and_AST_current=True,
        current_emit_bytecode_unchanged=True, hook_path=str(hook_path), hook_sha256=HOOK_SHA256,
        hook_before_current_outer_import_graph=True, real_F_constructor_no_file_forgery=True)


def private_emitter(*, tester_bindings_path=None, tester_bindings_sha256=None):
    module = parent().private_emitter(tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256)
    own = Path(__file__).resolve().parent
    need(module._idle_helper_path == own.parent / 'formal100m-full-used-domain-wip-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_full_used_factory.py',
         'FORMAL_EXACT_ALIAS_CURRENT_FULL_USED_LOADER_NOT_BASELINE_OR_NEW_LOADER')
    module.emit, module._formal_exact_alias_proof = cloned_emit(module.emit, own / 'exact_alias_cold_hook.py')
    module._idle_pin_paths = tuple(dict.fromkeys((*module._idle_pin_paths, *(own / n for n in SOURCES))))
    return module


def rebind_self_manifest(value, actual_manifest):
    need(type(value['resource_sampler']) is dict and 'factory_manifest' in value['resource_sampler'],
         'FORMAL_EXACT_ALIAS_ORIGINAL_SAMPLER_SELF_FIELD_REQUIRED')
    before, after = copy.deepcopy(value), copy.deepcopy(value)
    after['resource_sampler']['factory_manifest'] = str(actual_manifest)
    restored = copy.deepcopy(after)
    restored['resource_sampler']['factory_manifest'] = before['resource_sampler']['factory_manifest']
    need(restored == before, 'FORMAL_EXACT_ALIAS_ONLY_SELF_MANIFEST_FIELD_CHANGED')
    return after


def emit(bindings_path, bindings_sha256, *, destination, tester_bindings_path=None,
         tester_bindings_sha256=None, new_bindings=None):
    root = Path(__file__).resolve().parents[1]
    helper_path = pinned(root / 'racing-complete-cold-tree-v4-msg237-held20-v1-msg237-prefix21-v1/runtime-v1/smoke_bootstrap_task_factory.py',
        CONSTRUCTOR_SHA256)
    spec = importlib.util.spec_from_file_location('count14_formal_exact_alias_public_guard', helper_path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    value = guard.public(bindings_path, bindings_sha256)
    dest = Path(destination)
    need(Path(value['code_root']) == root and dest.is_absolute() and dest.parent.resolve() == dest.parent and
         dest.is_relative_to(root) and not dest.exists(), 'FORMAL_EXACT_ALIAS_ORIGINAL_DEST_IN_CODE_AND_ABSENT')
    actual_manifest = dest / 'FACTORY_PUBLIC.json'
    updated = rebind_self_manifest(value, actual_manifest)
    changed = updated != value
    used_path, used_sha = str(bindings_path), bindings_sha256
    if changed:
        need(new_bindings is not None, 'FORMAL_EXACT_ALIAS_DIFFERENT_DEST_REQUIRES_FIRST_NEW_BINDINGS_COPY')
        output = Path(new_bindings)
        need(output.is_absolute() and output.parent.resolve() == output.parent and output.is_relative_to(root) and
             output.name.endswith('PUBLIC.json') and not output.exists() and not output.is_symlink() and
             output != Path(bindings_path), 'FORMAL_EXACT_ALIAS_NEW_SELF_BINDINGS_NO_REPLACE_OR_OLD_EDIT')
        raw = (json.dumps(updated, sort_keys=True, allow_nan=False) + '\n').encode()
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        with os.fdopen(fd, 'wb') as out:
            out.write(raw); out.flush(); os.fsync(out.fileno())
        used_path, used_sha = str(output), hashlib.sha256(raw).hexdigest()
    else:
        need(new_bindings is None, 'FORMAL_EXACT_ALIAS_MATCHING_SELF_USES_ORIGINAL_BINDINGS_BYTES')
    module = parent()
    original = module.emit
    fn = FunctionType(original.__code__, dict(vars(module), private_emitter=private_emitter),
        original.__name__, original.__defaults__, original.__closure__)
    fn.__kwdefaults__ = original.__kwdefaults__
    result = fn(used_path, used_sha, destination=dest, tester_bindings_path=tester_bindings_path,
        tester_bindings_sha256=tester_bindings_sha256)
    need(guard.public(used_path, used_sha)['resource_sampler']['factory_manifest'] == str(actual_manifest),
         'FORMAL_EXACT_ALIAS_OWNER_AND_SAMPLER_SAME_ACTUAL_MANIFEST')
    result['formal_exact_alias_cold_suffix'] = dict(current_full_used_emitter_sha256=PARENT_SHA256,
        frozen_hook_sha256=HOOK_SHA256, one_generated_source_constant_only=True,
        current_full_used_outer_loader_preserved=True, original_bindings_path=str(bindings_path),
        original_bindings_sha256=bindings_sha256, bindings_used_path=used_path, bindings_used_sha256=used_sha,
        only_self_manifest_field_rebound=changed, actual_alias_target_metadata_checked=False,
        owner_constructor_or_sampler_collection_called=False, formal_delivery=False)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bindings', required=True); p.add_argument('--bindings-sha256', required=True)
    p.add_argument('--destination', required=True); p.add_argument('--tester-bindings')
    p.add_argument('--tester-bindings-sha256'); p.add_argument('--new-bindings')
    a = p.parse_args(argv)
    try:
        print(json.dumps(emit(a.bindings, a.bindings_sha256, destination=a.destination,
            tester_bindings_path=a.tester_bindings, tester_bindings_sha256=a.tester_bindings_sha256,
            new_bindings=a.new_bindings), sort_keys=True)); return 0
    except Exception as error:
        frames, tb = [], error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename, line=tb.tb_lineno,
                function=tb.tb_frame.f_code.co_name)); tb = tb.tb_next
        print(json.dumps(dict(PUBLIC_code='FORMAL_EXACT_ALIAS_FIRST_COLD_EMISSION_RETAINED_NO_RETRY',
            exception_type=type(error).__name__, locations=frames, models=0), sort_keys=True)); return 2


if __name__ == '__main__':
    raise SystemExit(main())
