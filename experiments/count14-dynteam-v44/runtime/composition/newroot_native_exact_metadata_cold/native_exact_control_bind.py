"""Approved a892: exact original SDK control bind, never an owner-root allowlist.

Private new registry only. Whitelist is snapshotted from this genuine core's
original complete export BEFORE native actions, plus the 5199 retained router
document. No route body/credentials are read. Sources and actual mounted
parents are checked again at the real kernel birth. Original stopped checks
remain: an absent process can use only its own earlier live verification.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_HOSTNAME = _count14_os.environ.get('COUNT14_HOSTNAME', 'count14-host')
from pathlib import Path
from types import MappingProxyType, MethodType
from dataclasses import dataclass
import ast,copy,inspect,os,stat,textwrap
from common import need,digest
from native_peer_registry import process_birth
from native_container_retirement import alive
import native_container_retirement as original
from native_beta_layout import native_aliases
from native_optional_stop_signal_validator import compile_validate as optional_validate

APPROVED_PLAN='a89263734bc48884bac7d3fe68e60606e819398a5e6be38484c11d26bd10ee15'
CONTRACTS=frozenset(('a009fcb9880fe694db540c6c9d8742d5e77ba1ce2314ee3b9018517f42f58e1e',
 '3902509c2b0daf9dea0d7421e26cf7dd29e878aebd6cdd4699615e31bd7fc937',
 '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'))
DESTINATION='/run/count14-dynteam'
CLOCK='/run/count14-budget-clock'


def identity(path):
    s=Path(path).stat()
    need(stat.S_ISDIR(s.st_mode),'EXACT_NATIVE_CONTROL_DIRECTORY_TYPE')
    return (s.st_dev,s.st_ino,s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))


def mounted_path(birth,destination):
    return Path('/proc')/str(birth.pid)/'root'/destination.lstrip('/')


@dataclass(frozen=True)
class Entry:
    source: Path
    directory_identity: tuple
    cid: str | None
    birth: object | None


class FrozenControls:
    def __init__(self,core,*,retained=None):
        from original_relay_core import OriginalRelayCore
        need(type(core)is OriginalRelayCore and not core.closed and not core.scientific_activation_qualified and
             set(core.gate.startup_held)==set(core.rows)and not core.peers._peers and
             (digest(core.contract)in CONTRACTS or core.qualification_only and os.uname().nodename!=(_C14_HOSTNAME)),
             'EXACT_NATIVE_CONTROL_ONLY_GENUINE_HELD_APPROVED_CONTRACT_CORE')
        registry=core.native_containers
        need(type(registry)is original.NativeContainerRegistry and registry.core is core and
             not registry.records and not registry.boot_plans and not registry.bootstrap_busy and
             'validate'not in vars(registry),'EXACT_NATIVE_CONTROL_ONE_COLD_EMPTY_REGISTRY_NO_HOT_PATCH')
        exports=core.cold_native_exports
        need(exports['state']=='EXPORTED_HELD_NOT_DOCKER_OR_SCIENTIFIC_PREPARED' and
             set(exports['trajectories'])==set(core.rows), 'EXACT_NATIVE_CONTROL_GENUINE_COMPLETE_SAME_CORE_EXPORTS')
        entries={};read_only={};clocks=set();source_socket=core.control.path.stat()
        for t,row in core.rows.items():
            value=exports['trajectories'][t];directory=Path(value['directory'])
            allowed=[Path(row['root'])/'native-cold-exports']
            if hasattr(core,'pre_request_control_home'):
                allowed.append(core.pre_request_control_home/'trajectory-exports'/digest(t))
            roles=native_aliases(row['arm'])
            need(directory in allowed and directory.is_absolute()and directory.resolve()==directory and
                 set(roles)==set(row['roles'])==set(value['role_exports'])and
                 value['native_roles']==len(roles), 'EXACT_NATIVE_CONTROL_ORIGINAL_EXPORT_LAYOUT_FULL_FROZEN_ROLE_CATALOGUE')
            clock=Path(core.clocks[t].directory)
            need(clock.is_absolute()and clock.resolve()==clock and clock.is_dir(),
                 'EXACT_NATIVE_CONTROL_REGISTERED_CLOCK_DIRECTORY')
            clocks.add(clock)
            for role in roles:
                v=value['role_exports'][role]
                need(set(v)=={'agent_control_directory','router_control_directory','clock_directory',
                             'clock_binding_sha256','clock_owner_uid'}and Path(v['clock_directory'])==clock,
                     'EXACT_NATIVE_CONTROL_ORIGINAL_ROLE_EXPORT_FIELDS_AND_CLOCK')
                for component,key,parent,mode in (('agent','agent_control_directory','native-agent-control-exports',0o755),
                                                  ('router','router_control_directory','native-private-exports',0o700)):
                    source=Path(v[key]);expected=directory/parent/role
                    need(source==expected and source.is_absolute()and source.resolve()==source and not source.is_symlink(),
                         'EXACT_NATIVE_CONTROL_NOT_CALLER_PATH_PREFIX_OR_PARENT_ALLOWLIST')
                    pin=identity(source);uid=os.geteuid()if component=='agent'or core.qualification_only else 10000
                    need(pin[2:]==(uid,uid,mode),'EXACT_NATIVE_CONTROL_ORIGINAL_SOURCE_DIRECTORY_UID_GID_MODE')
                    linked=(source/'native-control.sock').lstat()
                    need(stat.S_ISSOCK(linked.st_mode)and (linked.st_dev,linked.st_ino)==(source_socket.st_dev,source_socket.st_ino),
                         'EXACT_NATIVE_CONTROL_SAME_CORE_ORIGINAL_SDK_SOCKET_EXPORT')
                    entry=Entry(source,pin,None,None)
                    # Original agent control bind is RO, including all racing
                    # helpers. Only original routers receive the RW exception.
                    (entries if component=='router'else read_only)[t,role,component]=entry
        old={}
        if retained is not None:
            from current186_router_controls import RetainedRouterControls
            need(type(retained)is RetainedRouterControls,'EXACT_NATIVE_CONTROL_TYPED_RETAINED_ROUTER_REGISTRATION')
            d=retained.document
            # No free-form production document: constructor read pinned5199.
            if not core.qualification_only:
                from current186_router_controls import registered
                need(d==registered(),'EXACT_NATIVE_CONTROL_ONLY5199_ORIGINAL_RETAINED_DOCUMENT')
            need(digest(core.contract)==d['contract_sha256']and d['baseline']in core.rows and
                 set(d['routers'])=={'tester-00','checker-00','worker-00'},
                 'EXACT_NATIVE_CONTROL_SAME_CURRENT_CONTRACT_BASELINE_THREE_ROUTERS')
            from native_peer_registry import ProcessBirth
            for role,v in d['routers'].items():
                source=Path(v['control_directory']);pin=v['control_parent'];birth=ProcessBirth(**v['init_birth'])
                need(source.is_absolute()and source.resolve()==source and not source.is_symlink()and
                     identity(source)==tuple(pin[k]for k in('device','inode','uid','gid','mode')),
                     'EXACT_NATIVE_CONTROL_RETAINED5199_SOURCE_INODE_UID_GID_MODE')
                old[d['baseline'],role,'router',v['cid']]=Entry(source,identity(source),v['cid'],birth)
            clocks.add(Path(d['clock_directory']))
        self.core=core;self.registry=registry;self.contract_sha=digest(core.contract)
        self.entries=MappingProxyType(entries);self.read_only=MappingProxyType(read_only)
        self.retained=MappingProxyType(old);self.clocks=frozenset(clocks);self.live_verified={}

    def readonly_clocks(self,binding,snapshot):
        need(self.registry.core is self.core and digest(self.core.contract)==self.contract_sha,
             'EXACT_NATIVE_CONTROL_ORIGINAL_SAME_CONTRACT_NOT_REPLACED')
        for m in snapshot['mounts']:
            need(type(m)is dict and type(m.get('RW'))is bool,'EXACT_NATIVE_CONTROL_MOUNT_FIELDS')
            if m['RW']:
                need(m.get('Destination')!=CLOCK and Path(m.get('Source',''))not in self.clocks,
                     'EXACT_NATIVE_CONTROL_CLOCK_ALWAYS_READONLY')
                if m.get('Destination')==DESTINATION:
                    need(binding.component=='router','EXACT_NATIVE_CONTROL_ORIGINAL_AGENT_BIND_STAYS_READONLY')

    def exact(self,registry,binding,snapshot,mount,path,*,running):
        key=(binding.trajectory,binding.role,binding.component)
        need(registry is self.registry and binding.role in self.core.rows[binding.trajectory]['roles']and
             binding.component in('router','agent'), 'EXACT_NATIVE_CONTROL_SAME_CORE_ROLE_COMPONENT')
        v=self.retained.get((*key,binding.cid)) or self.entries.get(key)
        need(v is not None and path==v.source and mount.get('Destination')==DESTINATION and
             mount.get('Type')=='bind'and mount.get('RW')is True and
             sum(m.get('Destination')==DESTINATION for m in snapshot['mounts'])==1 and
             sum(m.get('Source')==str(path)and m.get('RW')is True for m in snapshot['mounts'])==1 and
             path.is_absolute()and path.resolve()==path and not path.is_symlink()and
             identity(path)==v.directory_identity,
             'EXACT_NATIVE_CONTROL_UNIQUE_REGISTERED_SOURCE_DESTINATION_AND_FROZEN_IDENTITY')
        if v.cid is not None:
            need(binding.cid==v.cid and binding.init_birth==v.birth,
                 'EXACT_NATIVE_CONTROL_RETAINED_CID_FULL_BIRTH_MUST_MATCH5199')
        token=(*key,binding.cid,binding.image_id,binding.init_birth)
        if running:
            need(snapshot['pid']==binding.init_birth.pid and process_birth(binding.init_birth.pid)==binding.init_birth,
                 'EXACT_NATIVE_CONTROL_ACTUAL_KERNEL_BIRTH_BEFORE_MOUNT')
            need(identity(mounted_path(binding.init_birth,DESTINATION))==v.directory_identity and
                 process_birth(binding.init_birth.pid)==binding.init_birth,
                 'EXACT_NATIVE_CONTROL_ACTUAL_MOUNTED_PARENT_INODE_AND_FULL_BIRTH')
            self.live_verified[token]=v
        else:
            need(self.live_verified.get(token)==v and not alive(binding.init_birth)and not alive(binding.peer_birth),
                 'EXACT_NATIVE_CONTROL_STOPPED_ONLY_PREVIOUSLY_LIVE_VERIFIED_SAME_CID_BIRTH')
        return True


def compile_validate(whitelist):
    # Preserve the truthful None correction. Change ONLY under-row in its AST.
    fn,proof=optional_validate(original)
    source=ast.parse(textwrap.dedent(inspect.getsource(original.NativeContainerRegistry.validate)))
    before=copy.deepcopy(source)
    target=ast.parse('path.is_relative_to(root)',mode='eval').body
    selected=ast.parse('path.is_relative_to(root) or _exact(self,binding,snapshot,mount,path,running=running)',mode='eval').body
    optional=ast.parse("snapshot['stop_signal'] in ('', 'SIGTERM', '15')",mode='eval').body
    truthful=ast.parse("snapshot['stop_signal'] is None or snapshot['stop_signal'] in ('', 'SIGTERM', '15')",mode='eval').body
    pairs=((target,selected),(optional,truthful));counts=[0,0]
    class Change(ast.NodeTransformer):
        def visit(self,n):
            for i,(a,b)in enumerate(pairs):
                if ast.dump(n,include_attributes=False)==ast.dump(a,include_attributes=False):counts[i]+=1;return copy.deepcopy(b)
            return super().visit(n)
    source=Change().visit(source)
    class Reverse(ast.NodeTransformer):
        def visit(self,n):
            for a,b in pairs:
                if ast.dump(n,include_attributes=False)==ast.dump(b,include_attributes=False):return copy.deepcopy(a)
            return super().visit(n)
    need(counts==[1,1]and ast.dump(Reverse().visit(copy.deepcopy(source)),include_attributes=False)==ast.dump(before,include_attributes=False),
         'EXACT_NATIVE_CONTROL_ONLY_OPTIONAL_NONE_AND_SINGLE_UNDER_ROW_PREDICATE_CHANGED')
    ns={};exec(compile(ast.fix_missing_locations(source),__file__+':original-full-validator-exact-control-only','exec'),
        dict(fn.__globals__,_exact=whitelist.exact),ns)
    body=ns['validate']
    def validate(registry,binding,snapshot,*,running):
        whitelist.readonly_clocks(binding,snapshot)
        return body(registry,binding,snapshot,running=running)
    return validate,dict(proof,approved_exact_bind_plan_sha256=APPROVED_PLAN,
        under_row_inverse_original_AST=True,exact_router_RW_entries=len(whitelist.entries),
        original_agent_RO_entries=len(whitelist.read_only),retained5199_exact_CID_entries=len(whitelist.retained),
        clock_RW_refused=True,all_other_original_validator_actions_and_guards_preserved=True,
        frozen_new_core_whitelist_not_parent_or_ROOT_allowlist=True)


def bind_new_registry(core,*,stage,financial,core_restore,fresh_guard,retained):
    # The original Stage binder validates genuine registry/Stage/core/held/0
    # request. Run its checks via private compile port WITHOUT installing first.
    from native_optional_stop_signal_validator import bind_new_registry as optional_bind
    from types import FunctionType
    whitelist=FrozenControls(core,retained=retained)
    fn,proof=compile_validate(whitelist)
    binder=FunctionType(optional_bind.__code__,dict(optional_bind.__globals__,
        compile_validate=lambda m:(fn,proof)),optional_bind.__name__,optional_bind.__defaults__,optional_bind.__closure__)
    binder.__kwdefaults__=optional_bind.__kwdefaults__
    return binder(core,stage=stage,financial=financial,core_restore=core_restore,fresh_guard=fresh_guard)
