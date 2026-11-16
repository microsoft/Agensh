"""Install the exact declared-config projection only in a new cold module.

No route observation here. Real proof is collected by every original call,
including owner sampling and each finite sampler child's fresh import.
"""
from pathlib import Path
from types import ModuleType
import hashlib
import importlib
import importlib.util
import os
import stat
import sys

CONSTRUCTOR_SHA256 = '71de11f1bb3f778b9d4afc7ce965d18fd4f7ed9dcf49bcb6fdbf622cea9dd29f'
PROJECTION_SHA256 = '66ece9e044bdde4b0742941ae390a16c9eaaf18f38c61d342224007b86fbdf26'
HELPER_SHA256 = 'c170564e5407913e06e37136c1b04e38de475146ff9e115aab24a123dda51bff'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def pinned(path, pin):
    path = Path(path)
    s = path.lstat()
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink()
         and stat.S_ISREG(s.st_mode) and s.st_uid in (0, os.geteuid())
         and not s.st_mode & 0o022 and s.st_nlink == 1
         and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
         'CONFIG_COLD_EXACT_FROZEN_REGULAR_READONLY_CODE_PIN')
    return path


def require_cold():
    need('native_resource_sampler' not in sys.modules,
         'CONFIG_COLD_BEFORE_SAMPLER_CONSUMER_IMPORT_NOT_HOT')
    names = ('RETAINED_OWNER', 'RETAINED_FACTORY_OWNER', 'RETAINED_FACTORY_LEDGER',
             'RETAINED_FORMAL_OWNER', 'RETAINED_FORMAL_LEDGER',
             'RETAINED_ORIGINAL_OWNER', 'RETAINED_ORIGINAL_LEDGER')
    for module in list(sys.modules.values()):
        if isinstance(module, ModuleType):
            need(not any(vars(module).get(k) is not None for k in names),
                 'CONFIG_COLD_NO_EXISTING_RETAINED_OWNER_OR_LEDGER')


def install(constructor, *, code_root):
    require_cold()
    code = Path(code_root)
    need(isinstance(constructor, ModuleType) and code.is_absolute()
         and code.resolve() == code and Path(constructor.__file__) ==
         code / 'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/smoke_bootstrap_task_factory.py',
         'CONFIG_COLD_EXACT_ORIGINAL_CONSTRUCTOR_AND_CODE_ROOT')
    pinned(constructor.__file__, CONSTRUCTOR_SHA256)
    P = importlib.import_module('native_resource_projections')
    need(Path(P.__file__) == code / 'runtime-v1-msg237-held20-v1-msg237-prefix21-v1/native_resource_projections.py'
         and not hasattr(P, '_count14_exact_private_config_cold_v1'),
         'CONFIG_COLD_ONE_NEW_ORIGINAL_PROJECTION_MODULE')
    pinned(P.__file__, PROJECTION_SHA256)
    path = pinned(Path(__file__).with_name('exact_private_config_projection_v1.py'), HELPER_SHA256)
    spec = importlib.util.spec_from_file_location('count14_exact_private_config_source', path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    private = helper.install_new_cold_module(P)
    P._count14_exact_private_config_cold_v1 = dict(
        helper_sha256=HELPER_SHA256, original_projection_sha256=PROJECTION_SHA256,
        single_branch_inverse_AST=private._single_branch_inverse_AST,
        before_sampler_import=True, actual_route_checked_at_import=False,
        unknown_routes_original_guards=True, exact_SEARCH_and_EVAL_declared_config_only=True, managed_child_claimed=False)
    return dict(P._count14_exact_private_config_cold_v1)
