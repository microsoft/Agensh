"""Pinned original metadata kernels only; no install, DB, job or model action."""
import ast
from pathlib import Path
from types import SimpleNamespace
from common import need,digest,sha,strict

PINS={'policy':'3cf620d829f7c6cfc71bda1d2664ad8f5ab51be4aa0a436a3ac75f662ca1f9a8',
 'selection':'acbc49b9c2822264db3722c54e553c8aaf6b4ccd424ed940bc056582f4503dad',
 'durable':'0278c7ac9ac77704f1467e8d1d22d0f048149355d4c3e80a4f64d3c0fa9a8c0c',
 'raw4':'5b8c7f5c5b1b9d9424d7a42f2ab79a54b7c3dcf3ba44260e0809e53633c4ca22'}


def load_kernels(paths):
    """Explicit PUBLIC code paths; verify bytes before compiling original defs.

    No original module global is patched. Only original metadata policy,
    persisted proof reader, durable wait and raw4 queue install body are loaded.
    The raw4 installer is RETURNED, never executed by this loader.
    """
    import hashlib,re
    need(type(paths)is dict and set(paths)==set(PINS),'FORMAL_ALLOWANCE_EXACT_KERNEL_PATHS')
    source={}
    for name,p in paths.items():
        p=Path(p);need(p.is_absolute()and p.resolve()==p and p.is_file(),'FORMAL_ALLOWANCE_PUBLIC_SOURCE_PATH')
        raw=p.read_bytes();need(hashlib.sha256(raw).hexdigest()==PINS[name],'FORMAL_ALLOWANCE_ORIGINAL_KERNEL_PIN')
        source[name]=raw.decode()
    policy={};exec(compile(source['policy'],str(paths['policy']),'exec'),policy)
    space=dict(need=need,digest=digest,strict=strict,re=re)
    def original_defs(key,names):
        tree=ast.parse(source[key]);nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in names]
        need({n.name for n in nodes}==set(names),'FORMAL_ALLOWANCE_ORIGINAL_FUNCTION_SET')
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(paths[key]),'exec'),space)
    original_defs('durable',('ended','durable_wait'))
    original_defs('selection',('_point_rows','_failed_proof'))
    original_defs('raw4',('install_queue',))
    return SimpleNamespace(policy=SimpleNamespace(**policy),point_rows=space['_point_rows'],
        failed_proof=space['_failed_proof'],durable_wait=space['durable_wait'],
        raw4_install=space['install_queue'],source_paths={k:str(v)for k,v in paths.items()},
        source_sha256=dict(PINS),unedited_original_function_AST=True)
