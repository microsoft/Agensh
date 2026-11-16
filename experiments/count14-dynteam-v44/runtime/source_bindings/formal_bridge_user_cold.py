"""New six-track formal graphs: approved management-bridge UID0 only.

Original gateway/no-reference/team/exec/source/SDK/Tester constructor chain
is retained. No existing root, container replacement, privilege/cap addition,
image USER change, model replay or financial formula/schema change.
Only the original scientific CLI/router remain UID10000. No team-size limit.
"""
from pathlib import Path
from types import FunctionType
import hashlib,importlib,importlib.util,os,stat

HERE=Path(__file__).resolve().parent
GATEWAY=('formal-newroot-gateway-cold-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1-msg237-locatorsuffix-v1-msg237-prefix22-v1/formal_gateway_cold.py',
         '98e00282e3d5c864e98ef318a43a366cce73d5f1e4fb914c984d88ad79d10231')
# The original emitter intentionally follows this exact no-reference chain.
PREVIOUS=('formal100m-no-reference-host-cold-v1-msg236-traceback-v1-msg236-initial13-v1-msg237-held20-v1-msg237-pathsuffix-v1-msg237-testersuffix-v1-msg237-prefix21-v1/formal_no_reference_host.py',
          '28bc028b3ee71ff22628b25df17a24eeb632a860b4c470eae9c659ac0c33450e')
ORIGINAL_GATEWAY_PINS={
    'original_gateway_overlay.py':'db4f0d57b72affc65ecabba86536e684e80d2f498b2077a44e7e9c61365f92e0',
    'original_gateway_config.py':'654978a76d1c156b2900190f4442f51d2af3f4c0b0dafe8a02e4d78a3add2a41'}
USER_SOURCES={
    'native_bridge_user_cold.py':'6b90f2702a59caee15bcce842d75eb9c897a5672d9f9b5fbb4600a327aef995d',
    'agent_bridge_user_layer.py':'de71f139e963673d45da418b6c30032b63399cb22a6eb695b0a544c372b9d3c5'}
_GATEWAY=None
_PREPARE_ATTEMPTED=False
RETAINED_NEW_OWNER=None
RETAINED_USER_BINDING=None


def need(ok,code):
    if not ok:raise ValueError(code)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def pin(path,expected):
    path=Path(path);s=path.lstat()
    need(path.resolve()==path and not path.is_symlink()and stat.S_ISREG(s.st_mode)and s.st_nlink==1 and
         s.st_uid in(0,os.geteuid())and not s.st_mode&0o022 and sha(path)==expected,
         'FORMAL_BRIDGE_USER_EXACT_NEW_FROZEN_SOURCE')
    return path
def load(path,expected,name):
    path=pin(path,expected);spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def gateway():
    global _GATEWAY
    path=pin(HERE.parent/GATEWAY[0],GATEWAY[1])
    if _GATEWAY is None:_GATEWAY=load(path,GATEWAY[1],'count14_formal_original_gateway_before_USER')
    return _GATEWAY


def users():
    # These are registered SOURCE import roots, never sys.path injection or a
    # forged module alias. An already-loaded different origin is rejected.
    for name,value in USER_SOURCES.items():pin(HERE/name,value)
    layer=importlib.import_module('agent_bridge_user_layer')
    need(Path(layer.__file__).resolve()==HERE/'agent_bridge_user_layer.py'and
         sha(layer.__file__)==USER_SOURCES['agent_bridge_user_layer.py'],
         'FORMAL_BRIDGE_USER_REGISTERED_LAYER_MODULE_ORIGIN')
    module=importlib.import_module('native_bridge_user_cold')
    need(Path(module.__file__).resolve()==HERE/'native_bridge_user_cold.py'and
         sha(module.__file__)==USER_SOURCES['native_bridge_user_cold.py'],
         'FORMAL_BRIDGE_USER_REGISTERED_RUNTIME_MODULE_ORIGIN')
    return module


def prepare_new_owner(**kwargs):
    global _PREPARE_ATTEMPTED,RETAINED_NEW_OWNER,RETAINED_USER_BINDING
    need(not _PREPARE_ATTEMPTED and RETAINED_NEW_OWNER is None and RETAINED_USER_BINDING is None,
         'FORMAL_BRIDGE_USER_NEW_ONCE_CONSTRUCTOR_RETAIN_PARTIAL_NO_RETRY')
    _PREPARE_ATTEMPTED=True
    g=gateway();u=users()
    need(g.PREVIOUS==PREVIOUS and g.ORIGINAL_GATEWAY_PINS==ORIGINAL_GATEWAY_PINS,
         'FORMAL_BRIDGE_USER_COMPLETE_ORIGINAL_GATEWAY_NOREf_CHAIN')
    owner=g.prepare_new_owner(**kwargs)
    RETAINED_NEW_OWNER=owner # retain original whole graph before USER side effects
    if owner.errors:return owner  # preserve original failed phase; no USER side effect
    binding=u.install(owner.core,control_home=owner.core.home)
    RETAINED_USER_BINDING=binding
    u.bind_new_bootstrap(owner)
    need(binding['phase']=='BOUND_FULL_ROSTER_NO_CONTAINER_ACTION'and
         len(binding['bindings'])==6 and not owner.bootstrap.records,
         'FORMAL_BRIDGE_USER_FULL_SIX_BOUND_BEFORE_FIRST_ORIGINAL_NATIVE_UP')
    return owner


def select_new_formal_factory(factory):
    g=gateway();selected=g.select_new_formal_factory(factory)
    previous=selected.private_original_constructor
    def constructor(bind_same_owner):
        helper=previous(bind_same_owner)
        current=helper._future_team_executable_prepare
        need(sha(current.__globals__['__file__'])==GATEWAY[1],
             'FORMAL_BRIDGE_USER_ONLY_EXACT_GATEWAY_CONSTRUCTOR_SEAM')
        helper._future_team_executable_prepare=prepare_new_owner
        return helper
    selected.private_original_constructor=constructor
    return selected


def select_new_source_module(module,level=0):
    g=gateway();fn=g.select_new_source_module
    selected=FunctionType(fn.__code__,dict(vars(g),select_new_formal_factory=select_new_formal_factory,
        select_new_source_module=select_new_source_module),fn.__name__,fn.__defaults__,fn.__closure__)
    selected.__kwdefaults__=fn.__kwdefaults__
    return selected(module,level)
