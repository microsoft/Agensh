"""Cold-only P.frozen_observer closure; exact original 51-alias bridge only.

Factory import validates code/PUBLIC bytes and installs a closure, never looks
at any actual alias/target. Each future ORIGINAL private observer assembly runs
the ORIGINAL bridge validation. No counts, SQL,25s guards or registry are changed.
"""
from pathlib import Path
from types import CodeType, ModuleType
import hashlib
import importlib
import importlib.util
import json
import os
import stat
import sys

PROJECTIONS_SHA256 = '66ece9e044bdde4b0742941ae390a16c9eaaf18f38c61d342224007b86fbdf26'
CONSTRUCTOR_SHA256 = '71de11f1bb3f778b9d4afc7ce965d18fd4f7ed9dcf49bcb6fdbf622cea9dd29f'
BRIDGE_SHA256 = 'fa906e97a1608054563e26d6fedef93d12bb9d24392c914eab11dc01f6dae511'
BINDINGS_SHA256 = '166a57fd72452c4315f51a9aead1238074863b8e8c3a904e5a7bf9a5b771e8da'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def pinned(path, pin, maximum=131072):
    path = Path(path)
    s = path.lstat()
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink() and
         stat.S_ISREG(s.st_mode) and s.st_uid in (0, os.geteuid()) and
         not s.st_mode & 0o022 and s.st_nlink == 1 and s.st_size <= maximum,
         'EXACT_ALIAS_FROZEN_REGULAR_PUBLIC_CODE_ONLY')
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == pin, 'EXACT_ALIAS_FIXED_CODE_OR_PUBLIC_RAW_PIN')
    return raw


def alias_mapping(raw):
    value = json.loads(raw)
    need(value['only_path_control_metadata'] is True and
         value['private_body_logs_PKL_read_or_hash'] is False and
         type(value['scientific_writes_or_models']) is int and value['scientific_writes_or_models'] == 0,
         'EXACT_ALIAS_ORIGINAL_PUBLIC_CONTROL_NOT_SCIENTIFIC_DATA')
    rows = value['all_canonical_guard_mismatches']
    need(type(rows) is list and len(rows) == 51, 'EXACT_ALIAS_ORIGINAL_FIFTY_ONE_ONLY')
    aliases = {}
    for row in rows:
        need(set(row) == {'field','is_final_symlink','logical_exists','logical_path',
                         'resolved_on_S2','resolved_path'} and row['field'] == 'scale_request_roots' and
             row['is_final_symlink'] is row['logical_exists'] is row['resolved_on_S2'] is True,
             'EXACT_ALIAS_ORIGINAL_PATH_BINDING_FIELDS')
        a, b = Path(row['logical_path']), Path(row['resolved_path'])
        # PURE lexical control checks only. is_symlink/resolve/target metadata
        # are intentionally deferred to B.install on each newly assembled O.
        need(a.is_absolute() and b.is_absolute() and '..' not in a.parts+b.parts and
             a.name == b.name == 'requests' and a.parent.name == b.parent.name and
             str(a) == row['logical_path'] and str(b) == row['resolved_path'] and
             str(a) not in aliases, 'EXACT_ALIAS_FINITE_EXACT_SAME_ROLE_MAPPING')
        aliases[str(a)] = str(b)
    need(len(aliases) == 51, 'EXACT_ALIAS_NO_DUPLICATE_OR_PREFIX_WHITELIST')
    return aliases


def require_cold(constructor):
    need(isinstance(constructor, ModuleType) and
         vars(constructor).get('RETAINED_FACTORY_OWNER') is None and
         vars(constructor).get('RETAINED_FACTORY_LEDGER') is None,
         'EXACT_ALIAS_NO_RETAINED_CONSTRUCTOR_OWNER_OR_LEDGER')
    need('native_resource_sampler' not in sys.modules,
         'EXACT_ALIAS_INSTALL_BEFORE_SAMPLER_FROM_IMPORT_NOT_HOT_PATCH')
    names = ('RETAINED_OWNER','RETAINED_FACTORY_OWNER','RETAINED_FACTORY_LEDGER',
             'RETAINED_FORMAL_OWNER','RETAINED_FORMAL_LEDGER','RETAINED_ORIGINAL_OWNER','RETAINED_ORIGINAL_LEDGER')
    for module in list(sys.modules.values()):
        if isinstance(module, ModuleType):
            need(not any(vars(module).get(k) is not None for k in names),
                 'EXACT_ALIAS_NO_EXISTING_PAID_OR_RETAINED_OWNER_HOT_INSTALL')


def install(constructor, *, code_root):
    require_cold(constructor)
    code_root = Path(code_root)
    need(code_root.is_absolute() and code_root.resolve() == code_root and
         Path(constructor.__file__) == code_root/'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/smoke_bootstrap_task_factory.py',
         'EXACT_ALIAS_ORIGINAL_SAME_CODE_CONSTRUCTOR')
    pinned(constructor.__file__, CONSTRUCTOR_SHA256)
    P = importlib.import_module('native_resource_projections')
    path = code_root/'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/native_resource_projections.py'
    need(Path(P.__file__) == path and not hasattr(P, '_count14_exact_alias_cold_factory_v1'),
         'EXACT_ALIAS_EXACT_ORIGINAL_NEW_PROJECTIONS_MODULE')
    raw = pinned(path, PROJECTIONS_SHA256)
    compiled = compile(raw, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    functions = [v for v in compiled.co_consts if isinstance(v, CodeType) and v.co_name == 'frozen_observer']
    need(len(functions) == 1 and P.frozen_observer.__globals__ is vars(P) and
         P.frozen_observer.__code__ == functions[0], 'EXACT_ALIAS_UNMODIFIED_ORIGINAL_FACTORY_CODE_OBJECT')
    root = Path(__file__).resolve().parent
    config_path = root/'private_config_cold_hook.py'
    pinned(config_path, 'bc226f9791ebda3ce6d074f73aaeab9076175ab80dab4c11435cbd0b70108461')
    config_spec = importlib.util.spec_from_file_location('count14_owner_child_private_config_cold', config_path)
    config_hook = importlib.util.module_from_spec(config_spec)
    config_spec.loader.exec_module(config_hook)
    # Already proved cold above; both hooks precede import graph / sampler imports.
    config_hook.install(constructor, code_root=code_root)
    bridge_path = root/'path_bridge.py'
    pinned(bridge_path, BRIDGE_SHA256)
    aliases = alias_mapping(pinned(root/'ALIAS_BINDINGS_PUBLIC.json', BINDINGS_SHA256))
    spec = importlib.util.spec_from_file_location('count14_smoke_exact_original_path_bridge', bridge_path)
    B = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B)
    old_factory = P.frozen_observer
    proof = dict(schema='count14-smoke-exact-alias-cold-factory-hook-v1', alias_count=51,
        bridge_sha256=BRIDGE_SHA256, bindings_sha256=BINDINGS_SHA256,
        original_projections_sha256=PROJECTIONS_SHA256, private_assemblies_wrapped=0,
        actual_alias_target_metadata_checked_at_factory_import=False, counts_or_counts_freshness_claimed=False)
    def frozen_observer():
        O, performance = old_factory() # full original assembly, patches/SQL intact
        B.install(O, aliases) # ORIGINAL exact51 target/symlink guard, no relaxation
        proof['private_assemblies_wrapped'] += 1
        return O, performance
    P.frozen_observer = frozen_observer
    P._count14_exact_alias_cold_factory_v1 = proof
    P._count14_exact_alias_cold_bridge = B # source-pinned module, not an old observer
    return dict(proof)
