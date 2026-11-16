"""New formal six graphs: optional metadata + a892 exact native control bind.

Retain original gateway/no-reference/team/exec/USER and all science conditions.
Private NEW empty registry only, no current smoke graph or shared source patch.
"""
from pathlib import Path
from types import FunctionType
import hashlib,importlib,importlib.util,os,stat
HERE=Path(__file__).resolve().parent
PREVIOUS=('formal-newroot-bridge-user-cold-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1-msg237-locatorsuffix-v1-msg237-prefix22-v1/formal_bridge_user_cold.py',
          '55612175644f8f7981d769ed4dda154f7070f6ce0cfc1ea536b129f635518035')
METADATA=('newroot-native-exact-metadata-cold-v2/newroot_native_metadata.py',
          'ae269051768a63c0d56cd2dfab256f2ed9c7b7a06e9ffa9011ef39947958f3bc')
_PREVIOUS=None
_PREPARE_ATTEMPTED=False
RETAINED_OWNER=RETAINED_METADATA_PROOF=None

def need(ok,code):
    if not ok:raise ValueError(code)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pin(reference):
    p=HERE.parent/reference[0];s=p.lstat()
    need(p.resolve()==p and not p.is_symlink()and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and
         s.st_uid in(0,os.geteuid())and not s.st_mode&0o022 and sha(p)==reference[1],
         'FORMAL_NATIVE_METADATA_EXACT_ORIGINAL_FROZEN_DEPENDENCY')
    return p

def previous():
    global _PREVIOUS
    p=pin(PREVIOUS)
    if _PREVIOUS is None:
        s=importlib.util.spec_from_file_location('count14_formal_original_bridge_USER_before_metadata',p)
        m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_PREVIOUS=m
    return _PREVIOUS

def metadata():
    p=pin(METADATA);m=importlib.import_module('newroot_native_metadata')
    need(Path(m.__file__).resolve()==p and sha(m.__file__)==METADATA[1],
         'FORMAL_NATIVE_METADATA_ONLY_ORIGINAL_REGISTERED_IMPORT_ROOT')
    return m

def prepare_new_owner(**kwargs):
    global _PREPARE_ATTEMPTED,RETAINED_OWNER,RETAINED_METADATA_PROOF
    need(not _PREPARE_ATTEMPTED and RETAINED_OWNER is None,
         'FORMAL_NATIVE_METADATA_ONE_NEW_COLD_CONSTRUCTOR_RETAIN_PARTIAL_NO_RETRY')
    p=previous();m=metadata();_PREPARE_ATTEMPTED=True
    owner=p.prepare_new_owner(**kwargs);RETAINED_OWNER=owner
    if owner.errors:return owner  # original factory/entry retains this exact partial
    RETAINED_METADATA_PROOF=m.bind_new_owner(owner)
    return owner

def select_new_formal_factory(factory):
    p=previous();selected=p.select_new_formal_factory(factory);old=selected.private_original_constructor
    def constructor(bind_same_owner):
        def bind_with_writer(owner,**kwargs):
            result=bind_same_owner(owner,**kwargs)
            metadata().require_checkpoint_consumers_bound(owner)
            return result
        helper=old(bind_with_writer);current=helper._future_team_executable_prepare
        need(sha(current.__globals__['__file__'])==PREVIOUS[1],
             'FORMAL_NATIVE_METADATA_EXACT_FULL_GATEWAY_USER_CONSTRUCTOR_SEAM')
        helper._future_team_executable_prepare=prepare_new_owner
        return helper
    selected.private_original_constructor=constructor
    return selected

def select_new_source_module(module,level=0):
    p=previous();fn=p.select_new_source_module
    selected=FunctionType(fn.__code__,dict(vars(p),select_new_formal_factory=select_new_formal_factory,
        select_new_source_module=select_new_source_module),fn.__name__,fn.__defaults__,fn.__closure__)
    selected.__kwdefaults__=fn.__kwdefaults__
    return selected(module,level)
