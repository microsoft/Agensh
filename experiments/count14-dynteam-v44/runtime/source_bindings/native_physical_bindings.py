"""Real original registry/peer/CLI binding, retained-source INERT scope only.

No launcher, dispatcher, signal, SDK body, paid constructor or original guard
rewrite. Missing physical dependencies remain explicit, never manufactured.
"""
from dataclasses import dataclass
from pathlib import Path
from types import CodeType
import hashlib
import importlib
import os
import socket
import stat
import struct
import subprocess

from common import digest
from bounded_metadata_ro import ReadBudget
from native_peer_registry import NativePeerRegistry,ProcessBirth,process_birth
from native_container_retirement import NativeContainerRegistry,ContainerBinding,descendant_in_container
from native_docker_scope import ScopedDocker
from native_bridge_owner import NativeBridgeLifecycleOwner,direct_native_child
from native_session_control import NativeSessionControl,COMMIT
from smoke_racing_tools_kernel_custody import kernel_census
import new_owner_sdk_registration as R
import normal_inert_cut as T
import metadata_inert_pair as M

PINS=dict(new_owner_sdk_registration='f12cde63a0d01a12e20c901178e2a707303caadc20ffde9d1c47cafa38162334',
 normal_inert_cut='aac25e6b4f30c199a84d1ac7f5652283585f259f93a2d3f4a3e3134c9f203262',
 metadata_inert_pair='83b2662daef394a6c3bb9cbfa46fc15a49c4382df7db5c963ec89a1f61b853da',
 native_peer_registry='0986b61a7c71b6745442b9c71dfc67d79eebf960a50523ea1e2b5ee0f37d019d',
 native_container_retirement='9cba289507f8fe65da64b75d737595585e08a58241d1badda88effc9f43926a3',
 native_docker_scope='513db38eb3e30fe7e5d93ef09b698c8e75dca9a7054085bac74647f63320474f',
 native_bridge_owner='e3e2c6b41ee109a1483ee92e8820fda1ad3e186e82263968299bd848bedac346',
 native_session_control='cba05b39fb3231f5791ba7421bf2b6a8487d081df6016885ab7f291b326cd370',
 smoke_racing_tools_kernel_custody='5ff1cb87ca0cd1f09b6ef972edb3d4ab3c945618012ee10d8849468333f841ab')
SCHEMA='count14-retained-source-native-physical-INERT-bindings-v1'
_SEAL=object()
_REGISTERED={}


class PhysicalBindingWait(RuntimeError):pass


def need(ok,code):
    if not ok:raise PhysicalBindingWait(code)


def check(budget):
    need(type(budget)is ReadBudget,'NATIVE_PHYSICAL_EXACT_FINITE_METADATA_BUDGET');budget.check()


def verify_sources():
    for name,pin in PINS.items():
        module=importlib.import_module(name);p=Path(module.__file__)
        need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and
            hashlib.sha256(p.read_bytes()).hexdigest()==pin,'NATIVE_PHYSICAL_FIXED_ORIGINAL_AND_RECEIVER_PINS')
    for name,cls,methods in(('native_peer_registry',NativePeerRegistry,('register_from_launcher','validate')),
        ('native_container_retirement',NativeContainerRegistry,('register_from_launcher','validate')),
        ('native_bridge_owner',NativeBridgeLifecycleOwner,('__init__','handle')),
        ('native_docker_scope',ScopedDocker,('__init__','verify_files','verify_daemon','inspect','_project')),
        ('native_session_control',NativeSessionControl,('__init__','start'))):
        module=importlib.import_module(name);code=compile(Path(module.__file__).read_bytes(),module.__file__,'exec',dont_inherit=True)
        original=next(c for c in code.co_consts if isinstance(c,CodeType)and c.co_name==cls.__name__)
        codes={c.co_name:c for c in original.co_consts if isinstance(c,CodeType)}
        need(all(getattr(cls,n).__code__==codes[n]and getattr(cls,n).__globals__ is vars(module)for n in methods),
            'NATIVE_PHYSICAL_ORIGINAL_REGISTRATION_GUARDS_UNCHANGED')
    R.verify_sources();return dict(PINS)


def _live(birth):
    try:return type(birth)is ProcessBirth and process_birth(birth.pid)==birth
    except (OSError,ValueError,KeyError,IndexError):return False


def _socket_identity(control,home,*,own):
    need(type(control)is NativeSessionControl and control.path==Path(home)/'native-control.sock'and
        control.path.parent.resolve()==control.path.parent and not control.path.is_symlink()and
        (own or control.started),'NATIVE_PHYSICAL_ACTUAL_ORIGINAL_CONTROL_HANDLE_NOT_CALLER_PEERCRED')
    listener=control.server.socket;st=control.path.lstat();fd=os.fstat(listener.fileno())
    need(type(listener)is socket.socket and listener.family==socket.AF_UNIX and
        listener.getsockname()==str(control.path)and stat.S_ISSOCK(st.st_mode)and stat.S_ISSOCK(fd.st_mode)and
        listener.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)==1,
        'NATIVE_PHYSICAL_ORIGINAL_LIVE_LISTENER_AND_EXISTING_SOCKET_INODES')
    return st.st_dev,st.st_ino,st.st_uid,st.st_gid,stat.S_IMODE(st.st_mode),fd.st_dev,fd.st_ino


def _peer_channel(registry,key,birth,control,channel,home,*,own):
    before=_socket_identity(control,home,own=own)
    need(type(channel)is socket.socket and channel.family==socket.AF_UNIX and
        channel.getsockname()==str(control.path)and stat.S_ISSOCK(os.fstat(channel.fileno()).st_mode),
        'NATIVE_PHYSICAL_RETAIN_ACTUAL_ACCEPTED_ORIGINAL_UDS_SOCKET')
    peer=struct.unpack('3i',channel.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
    t,role,purpose=key
    need(purpose in('bridge','router')and peer==(birth.pid,birth.uid,birth.gid)and
        registry.validate(dict(schema='count14-native-bridge-lifecycle-v1'if purpose=='bridge'else
            'count14-dynteam-native-session-ready-v1',source_commit=COMMIT,trajectory_id=t,role_slot=role),peer),
        'NATIVE_PHYSICAL_KERNEL_SO_PEERCRED_EXACT_REGISTERED_SOURCE_BIRTH')
    need(_socket_identity(control,home,own=own)==before,'NATIVE_PHYSICAL_CONTROL_SOCKET_INODE_STABLE')
    return before


def _register_peer(registry,key,birth,budget):
    check(budget)
    need(type(registry)is NativePeerRegistry and registry.source_commit==COMMIT and _live(birth),
        'NATIVE_PHYSICAL_ORIGINAL_TRUSTED_LAUNCHER_BIRTH_STILL_LIVE')
    # Expected identity is fixed-source control, NEVER a sender's claimed PID.
    # No new-owner parenthood is required by this original registration API.
    registry.register_from_launcher(*key[:2],birth,expected_birth=birth,purpose=key[2])
    check(budget)


@dataclass(frozen=True,repr=False)
class LiveCliBinding:
    key:tuple
    source_cli:object
    source_epoch:object
    receiving_epoch:object
    receiving_owner_birth:ProcessBirth
    bridge_birth:ProcessBirth
    physical_child:ProcessBirth
    receiving_cli_record:dict
    channel:socket.socket
    control_socket_identity:tuple
    installed_original_bridge_owner:bool


@dataclass(repr=False)
class NativePhysicalBindings:
    owner:object
    sdk_registration:R.InertSdkRegistration
    peers:NativePeerRegistry
    containers:object
    control:object
    bridge_owner:object
    source_peer_births:dict
    live_cli_bindings:dict
    domain_fds:dict
    unresolved:list
    receiving_owner_birth:ProcessBirth
    _seal:object

    def public(self):
        return dict(schema=SCHEMA,registered_original_peer_bindings=len(self.peers._peers),
            registered_original_container_bindings=0 if self.containers is None else len(self.containers.records),
            registered_live_CLI_bindings=len(self.live_cli_bindings),unresolved=[dict(key=list(k),code=c)for k,c in self.unresolved],
            source_control_sha256=self.sdk_registration.source_control_sha256,
            receiving_owner_birth_sha256=digest(R.C._birth(self.receiving_owner_birth)),
            original_source_CLI_Python_identity_claimed=False,source_Epochs_and_CLI_provenance_preserved=True,
            actual_SDK_load=False,strict_path_runtime_bound=False,host_strict_ACK=False,once_collaboration_recovery=False,
            runtime_ready=False,safe_to_TERM=False,paid_activation=False)

    def context_for_original_loader(self,key,*,read_budget):
        """Return REAL live bindings, not execution authority or a fabricated handle.

        The future NEW-owner strict control must retain this new receiving CLI
        object as its own same-process identity. Old same-owner plans stay old.
        """
        check(read_budget)
        need(self._seal is _SEAL and _REGISTERED.get(id(self.owner))is self and
            self.owner.core.inert_native_physical_bindings is self and
            process_birth(os.getpid())==self.receiving_owner_birth,'NATIVE_PHYSICAL_SAME_REGISTERED_RECEIVING_PROCESS')
        cli=self.live_cli_bindings.get(key)
        need(cli is not None and cli.installed_original_bridge_owner and self.containers is not None and
            all((*key,c)in self.containers.records for c in('agent','router')),
            'NATIVE_PHYSICAL_ORIGINAL_LOADER_CONTEXT_MISSING_REAL_BINDINGS')
        need(self.bridge_owner.clis.get(key)is cli.receiving_cli_record and _live(cli.physical_child),
            'NATIVE_PHYSICAL_SAME_NEW_RECEIVING_CLI_RECORD_AND_LIVE_CHILD')
        _peer_channel(self.peers,(*key,'bridge'),cli.bridge_birth,self.control,cli.channel,self.owner.core.home,own=False)
        for component in('agent','router'):
            record=self.containers.records[*key,component]
            self.containers.validate(record,self.containers.docker.inspect(record.cid),running=True)
            retained=next(v for v in self.sdk_registration.retained_containers if v.key==(*key,component))
            fd=_domain(retained.source_component,read_budget)
            try:
                held=os.fstat(self.domain_fds[*key,component]);fresh=os.fstat(fd)
                need((held.st_dev,held.st_ino)==(fresh.st_dev,fresh.st_ino),'NATIVE_PHYSICAL_HELD_SAME_CGROUP_DOMAIN_FD')
            finally:os.close(fd)
            check(read_budget)
        return cli,self.peers,self.containers,self.control


def _domain(component,budget):
    check(budget);census=kernel_census(component.init_birth,deadline_seconds=.5);check(budget)
    need((census.domain,census.domain_device,census.domain_inode)==(component.domain,component.device,component.inode),
        'NATIVE_PHYSICAL_ORIGINAL_EXACT_CGROUP_DOMAIN_DEVICE_INODE')
    # Identity binding is NOT a fresh tool-clear/startup baseline. Original
    # racing-game control births are not all serialized in Component.controls;
    # never impose a new birthscope or absorb census members into that tuple.
    path=Path('/sys/fs/cgroup')/census.domain.lstrip('/')
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    if (os.fstat(fd).st_dev,os.fstat(fd).st_ino)!=(component.device,component.inode):
        os.close(fd);raise PhysicalBindingWait('NATIVE_PHYSICAL_DOMAIN_INODE_CHANGED')
    return fd


def register_inert_native_physical_bindings(owner,*,ticket,docker=None,control=None,channels=None,bridge_owner=None,read_budget):
    """Production: bind only actual retained-source births. No replacement launch."""
    verify_sources();check(read_budget)
    cap=T.verify_inert_ticket(ticket,owner=owner,read_budget=read_budget)
    need(type(cap)is T.VerifiedNormalInertCut and cap.OWN is False,'NATIVE_PHYSICAL_PRODUCTION_FIXED_TICKET_ONLY')
    core=owner.core;reg=getattr(core,'inert_sdk_transfer_registration',None)
    need(type(reg)is R.InertSdkRegistration and reg.owner is owner and
        core.native_sdk_startup_epochs is reg.epochs and reg.source_control_sha256==cap.source_control_sha256 and
        reg.new_owner_birth==cap.new_owner_birth==process_birth(os.getpid()) and reg.old_owner_birth==cap.old_owner_birth and
        cap.component('native_SDK_epoch_controls')==reg.source_section and
        getattr(core,'peers',None)is None and getattr(core,'native_containers',None)is None and
        id(owner)not in _REGISTERED and not hasattr(core,'inert_native_physical_bindings'),
        'NATIVE_PHYSICAL_NEW_SAME_TYPED_SDK_GRAPH_ONLY_NO_REPLACEMENT_OR_SECOND_REGISTRATION')
    need(docker is None or type(docker)is ScopedDocker and docker.route.qualification_only is False,
        'NATIVE_PHYSICAL_ONLY_REAL_PRIVATE_SCOPED_DOCKER_OR_EXPLICIT_MISSING')
    need(docker is None or not any(n in vars(docker)for n in('verify_files','verify_daemon','inspect','_project')),
        'NATIVE_PHYSICAL_NO_CALLER_DOCKER_METHOD_SUBSTITUTION')
    need(control is None or core.control is control and type(control)is NativeSessionControl,
        'NATIVE_PHYSICAL_CONTROL_FROM_REAL_SAME_CORE_FACTORY')
    need(bridge_owner is None or core.bridge_owner is bridge_owner and type(bridge_owner)is NativeBridgeLifecycleOwner and
        bridge_owner.core is core and not bridge_owner.clis and not bridge_owner.logical,
        'NATIVE_PHYSICAL_ORIGINAL_SAME_CORE_NEW_BRIDGE_OWNER_NO_OLD_CLI_IDENTITY')
    need(channels is None or type(channels)is dict,'NATIVE_PHYSICAL_ACTUAL_CHANNEL_MAP_NOT_CALLBACK')
    peers=NativePeerRegistry(source_commit=COMMIT,allowed_bindings=[(t,r)for t,row in core.rows.items()for r in row['roles']])
    result=NativePhysicalBindings(owner,reg,peers,None,control,bridge_owner,{}, {},{},[],reg.new_owner_birth,_SEAL)
    # Hold the genuine new RAM registration even on a later partial observation.
    _REGISTERED[id(owner)]=result;core.peers=peers;core.inert_native_physical_bindings=result
    if not cap.has_component('native_peer_birth_controls'):
        result.unresolved.append(((),'MISSING_ORIGINAL_TRUSTED_LAUNCHER_PEER_CONTROLS'));return result
    for row in cap.component('native_peer_birth_controls'):
        key=row['trajectory'],row['role'],row['purpose'];birth=R._birth(row['birth'])
        need(key not in result.source_peer_births and key[:2]in peers.allowed and key[2]in('bridge','router','launcher'),
            'NATIVE_PHYSICAL_UNAMBIGUOUS_ORIGINAL_ROLE_PURPOSE_PEER_PROVENANCE')
        result.source_peer_births[key]=birth
        if not _live(birth):result.unresolved.append((key,'ORIGINAL_PEER_BIRTH_NO_LONGER_LIVE'));continue
        _register_peer(peers,key,birth,read_budget)
    if docker is None:result.unresolved.append(((),'MISSING_ACTUAL_PRIVATE_SCOPED_DOCKER'))
    else:
        docker.verify_files();docker.verify_daemon();images={}
        for retained in reg.retained_containers:
            c=retained.source_component
            need(c.component not in images or images[c.component]==c.image_id,'NATIVE_PHYSICAL_ORIGINAL_IMAGE_PIN_CONSISTENCY')
            images[c.component]=c.image_id
        need(set(images)=={'agent','router'},'NATIVE_PHYSICAL_ORIGINAL_COMPLETE_AGENT_ROUTER_IMAGE_PINS')
        result.containers=NativeContainerRegistry(core,docker,image_ids=images);core.native_containers=result.containers
        for retained in reg.retained_containers:
            key=retained.key;c=retained.source_component;purpose='bridge'if c.component=='agent'else'router'
            peer=peers._peers.get((*key[:2],purpose))
            if peer is None or not _live(c.init_birth):
                result.unresolved.append((key,'MISSING_ORIGINAL_LIVE_CONTAINER_INIT_OR_PEER'));continue
            binding=ContainerBinding(*key,c.cid,c.image_id,c.init_birth,peer)
            need(descendant_in_container(c.init_birth,peer),'NATIVE_PHYSICAL_RETAINED_SOURCE_PEER_IN_EXACT_ORIGINAL_CONTAINER')
            domain_fd=_domain(c,read_budget);result.domain_fds[key]=domain_fd
            result.containers.register_from_launcher(binding);check(read_budget)
    channels={}if channels is None else channels
    for source in reg.source_transfer.clis:
        key=source.key;bridge=peers._peers.get((*key,'bridge'));epoch=reg.source_transfer.current.get(key)
        if source.archived:continue # Never revive an ended logical CLI.
        if bridge is None or control is None or (*key,'bridge')not in channels:
            result.unresolved.append((key,'MISSING_LIVE_ORIGINAL_BRIDGE_CONTROL_CHANNEL'));continue
        if not _live(source.birth):result.unresolved.append((key,'ORIGINAL_CLI_BIRTH_NO_LONGER_LIVE'));continue
        need(epoch is not None and epoch.child==source.birth and epoch.token==source.token,
            'NATIVE_PHYSICAL_EXACT_RETAINED_ORIGINAL_CLI_EPOCH_TOKEN')
        channel=channels[*key,'bridge'];identity=_peer_channel(peers,(*key,'bridge'),bridge,control,channel,core.home,own=False)
        child=direct_native_child(bridge.pid,source.token[1],source.token[2],expected_uid=source.birth.uid)
        need(child==source.birth,'NATIVE_PHYSICAL_ORIGINAL_BRIDGE_DIRECT_CHILD_NOT_NEW_OWNER_PARENT')
        record=dict(token=source.token,birth=child,raw_birth=source.raw_birth,archived=False,end_lease=source.end_lease)
        installed=bridge_owner is not None and source.end_lease is None
        if source.end_lease is not None:
            result.unresolved.append((key,'MISSING_RESTORED_ORIGINAL_MEMBERSHIP_FENCE_LEASE'))
        if installed:
            need(child.uid==bridge_owner.uid,'NATIVE_PHYSICAL_ORIGINAL_BRIDGE_CHILD_UID')
            bridge_owner.clis[key]=record;bridge_owner.logical[key]=source.raw_birth
        result.live_cli_bindings[key]=LiveCliBinding(key,source,epoch,reg.epochs.current[key],reg.new_owner_birth,
            bridge,child,record,channel,identity,installed)
        if bridge_owner is None:result.unresolved.append((key,'MISSING_ACTUAL_ORIGINAL_SAME_CORE_BRIDGE_OWNER'))
    check(read_budget);return result


def register_OWN_live_peer_cli_component(*,home,trajectory,role,launcher_child,control,accepted_channel,expected_cli_birth,token,read_budget):
    """Explicit OWN actual kernel/component port, NOT a production ticket flow.

    This qualifies shared original peer/UDS/direct-child code only. It supplies
    no original paid source lineage, Docker/container, kernel-custody or SDK ACK.
    """
    verify_sources();check(read_budget);home=Path(home)
    need(home.is_absolute()and home.resolve()==home and home.is_dir()and home.name.startswith('OWN-')and
        home.stat().st_uid==os.geteuid()and not home.stat().st_mode&0o077 and trajectory.startswith('OWN-'),
        'NATIVE_PHYSICAL_EXPLICIT_OWN_REAL_PRIVATE_SANDBOX_ONLY')
    need(type(launcher_child)is subprocess.Popen and launcher_child._child_created and launcher_child.poll()is None,
        'NATIVE_PHYSICAL_OWN_ACTUAL_LIVE_POPEN_HANDLE_ONLY')
    birth=process_birth(launcher_child.pid);key=trajectory,role
    peers=NativePeerRegistry(source_commit=COMMIT,allowed_bindings=[key])
    _register_peer(peers,(*key,'bridge'),birth,read_budget)
    identity=_peer_channel(peers,(*key,'bridge'),birth,control,accepted_channel,home,own=True)
    need(type(expected_cli_birth)is ProcessBirth and type(token)is tuple and token[0]==key and
        token[2]==expected_cli_birth.start_ticks,'NATIVE_PHYSICAL_OWN_DECLARED_REAL_CHILD_CONTROL_ONLY')
    child=direct_native_child(birth.pid,token[1],token[2],expected_uid=expected_cli_birth.uid)
    need(child==expected_cli_birth,'NATIVE_PHYSICAL_OWN_ACTUAL_ORIGINAL_DIRECT_CHILD_METHOD')
    check(read_budget)
    return peers,child,identity
