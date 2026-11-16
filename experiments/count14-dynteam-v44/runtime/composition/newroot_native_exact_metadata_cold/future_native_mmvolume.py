"""Fresh native new-root MM anonymous volume, exact per-track full-backup root.

Only metadata projections. No adoption/current-root fallback, file body reads,
Docker/process mutation, root exclusions, CAS/special-file policy or finance.
Caller supplies the original strictly-pinned newroot metadata.scope function.
"""
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
import json
import stat
import subprocess
import threading

FORMAL='9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
RACING='3902509c2b0daf9dea0d7421e26cf7dd29e878aebd6cdd4699615e31bd7fc937'
DESTINATION='/mattermost/client/plugins'
VOLUME_FORMAT='{"name":{{json .Name}},"driver":{{json .Driver}},"scope":{{json .Scope}},"labels":{{json .Labels}},"options":{{json .Options}},"created_at":{{json .CreatedAt}},"mountpoint":{{json .Mountpoint}}}'
_REGISTRIES={}
_LOCK=threading.RLock()


def need(ok):
    if not ok:raise ValueError('FRESH_NATIVE_SAME_CORE_PER_TRACK_MM_FULL_BACKUP_REQUIRED')


def _hex(v):return type(v)is str and len(v)==64 and all(c in '0123456789abcdef'for c in v)
def _route(r):return(str(r.cli),r.cli_sha256,str(r.socket_path),r.daemon_id,str(r.data_root),r.qualification_only)


def directory_identity(source):
    p=Path(source);need(p.is_absolute()and p.resolve()==p and not p.is_symlink())
    s=p.lstat();need(stat.S_ISDIR(s.st_mode))
    return(s.st_dev,s.st_ino,s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))


def _admitted(core,scope_guard):
    from common import digest
    need(callable(scope_guard)and scope_guard(core)is True)
    need(core.rows=={r['trajectory_id']:r for r in core.contract['trajectories']})
    if not core.qualification_only:need(digest(core.contract)in(FORMAL,RACING))
    return True


def canonical_mounts(mounts):
    """Full JSON rows, no dropped fields or duplicate collapse."""
    from common import wire
    need(type(mounts)is list and all(type(m)is dict for m in mounts))
    return sorted(mounts,key=wire)


def same_snapshot(left,right):
    from common import wire
    need(type(left)is dict and type(right)is dict and 'mounts'in left and 'mounts'in right)
    return (wire({k:v for k,v in left.items()if k!='mounts'})==wire({k:v for k,v in right.items()if k!='mounts'})and
            [wire(m)for m in canonical_mounts(left['mounts'])]==[wire(m)for m in canonical_mounts(right['mounts'])])


def _native_record(core,t):
    from native_cold_bootstrap import NativeColdBootstrap
    from native_peer_registry import ProcessBirth
    boot=core.cold_bootstrap
    need(type(boot)is NativeColdBootstrap and boot.core is core and t in core.rows)
    record=boot.records[t]
    need(type(record)is dict and 'adopted_existing_infra_not_fresh_UP'not in record and
         'adopted_infra_launch_provenance'not in record)
    births=record['control_births']  # original missing key still fails, never fallback
    need(type(births)is list and bool(births)and all(type(v)is dict and
         set(v)==set(ProcessBirth.__dataclass_fields__)and type(ProcessBirth(**v))is ProcessBirth for v in births))
    return record


@dataclass(frozen=True)
class VolumeEntry:
    trajectory:str
    row_payload:bytes
    contract_sha256:str
    cid:str
    image_id:str
    birth:object
    launch:object
    native_record:object
    control_births_payload:bytes
    source:Path
    source_identity:tuple
    volume_payload:bytes
    route_value:tuple
    socket_identity:tuple


class NativeMattermostVolumes:
    def __init__(self,core,scope_guard):
        from original_relay_core import OriginalRelayCore
        from native_container_retirement import NativeContainerRegistry
        from native_docker_scope import ScopedDocker,DockerRoute
        need(type(core)is OriginalRelayCore and not core.closed and _admitted(core,scope_guard)is True and
             type(core.native_containers)is NativeContainerRegistry and core.native_containers.core is core and
             type(core.native_containers.docker)is ScopedDocker and type(core.native_containers.docker.route)is DockerRoute)
        self.core,self.scope_guard=core,scope_guard
        self.registry=core.native_containers;self.docker=self.registry.docker;self.route=self.docker.route
        self._entries={};self.entries=MappingProxyType(self._entries)
        self._states={};self.states=MappingProxyType(self._states)
        self._names={};self._lock=threading.RLock()

    def _same(self):
        from original_relay_core import OriginalRelayCore
        from native_container_retirement import NativeContainerRegistry
        from native_docker_scope import ScopedDocker,DockerRoute
        need(_REGISTRIES.get(id(self.core))is self and type(self.core)is OriginalRelayCore and
             _admitted(self.core,self.scope_guard)is True and not self.core.closed and
             type(self.registry)is NativeContainerRegistry and self.core.native_containers is self.registry and
             self.registry.core is self.core and self.registry.docker is self.docker and
             type(self.docker)is ScopedDocker and self.docker.route is self.route and type(self.route)is DockerRoute)

    def _launch(self,writer,launch,snapshot):
        from common import digest
        from native_peer_registry import ProcessBirth,process_birth
        self._same();core=self.core;t=writer.t
        record=_native_record(core,t)
        need(writer.core is core and writer.row==core.rows[t]and type(launch)is dict and
             set(launch)=={'cid','image_id','init_birth'}and type(launch['init_birth'])is ProcessBirth and
             core.cold_bootstrap.infra_birth_records[t,'mattermost']is launch and
             snapshot['labels']==dict(root=core.rows[t]['root'],trajectory=digest(t),contract=digest(core.contract),
                 role='infra-mattermost',component='infra')and snapshot['running']is True and
             all(snapshot[k]is False for k in('paused','restarting','dead'))and
             _hex(launch['cid'])and launch['image_id']==core.native_host_environment['trajectories'][t]['image_ids']['mattermost']and
             (launch['init_birth'].uid,launch['init_birth'].gid)==(2000,2000)and
             (snapshot['id'],snapshot['image'],snapshot['pid'])==(launch['cid'],launch['image_id'],launch['init_birth'].pid)and
             process_birth(snapshot['pid'])==launch['init_birth'])
        return record

    def _volume(self,name):
        self._same();need(_hex(name));self.docker.verify_daemon()
        v=self.docker._project('volume','inspect','--format',VOLUME_FORMAT,name)
        need(type(v)is dict and set(v)=={'name','driver','scope','labels','options','created_at','mountpoint'}and
             v['name']==name and v['driver']=='local'and v['scope']=='local'and
             v['labels']=={'com.docker.volume.anonymous':''}and v['options']is None and
             type(v['created_at'])is str and bool(v['created_at']))
        p=self.route.data_root/'volumes'/name/'_data'
        need(v['mountpoint']==str(p));directory_identity(p)
        self.docker.verify_daemon()
        r=subprocess.run(self.docker.argv('ps','-aq','--no-trunc','--filter','volume='+name),
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},cwd='/',timeout=2.5)
        need(r.returncode==0 and len(r.stdout)<=4096)
        refs=r.stdout.decode('ascii').splitlines();need(len(refs)==1 and _hex(refs[0]))
        self.docker.verify_daemon();return v,refs

    def _mount(self,snapshot):
        need(type(snapshot['mounts'])is list)
        matches=[m for m in snapshot['mounts']if type(m)is dict and m.get('Destination')==DESTINATION]
        need(len(matches)==1);m=matches[0]
        need(m.get('Type')=='volume'and m.get('RW')is True and m.get('Driver')=='local'and _hex(m.get('Name')))
        return m

    def _make(self,writer,launch,snapshot):
        from common import wire,digest
        record=self._launch(writer,launch,snapshot);m=self._mount(snapshot)
        v,refs=self._volume(m['Name']);p=Path(v['mountpoint']);identity=directory_identity(p)
        need(m.get('Source')==str(p)and refs==[launch['cid']]and identity[2:]==(2000,2000,0o755))
        entry=VolumeEntry(writer.t,wire(self.core.rows[writer.t]),digest(self.core.contract),launch['cid'],launch['image_id'],
            launch['init_birth'],launch,record,wire(record['control_births']),p,identity,wire(v),_route(self.route),tuple(self.docker._socket_identity))
        self._validate(writer,launch,snapshot,entry)
        return entry

    def _validate(self,writer,launch,snapshot,entry):
        from common import wire,digest
        record=self._launch(writer,launch,snapshot);m=self._mount(snapshot)
        need(writer.t==entry.trajectory and record is entry.native_record and wire(record['control_births'])==entry.control_births_payload and
             wire(self.core.rows[writer.t])==entry.row_payload and digest(self.core.contract)==entry.contract_sha256 and
             launch is entry.launch and (launch['cid'],launch['image_id'],launch['init_birth'])==(entry.cid,entry.image_id,entry.birth)and
             m.get('Source')==str(entry.source)and m['Name']==json.loads(entry.volume_payload)['name']and
             _route(self.route)==entry.route_value and tuple(self.docker._socket_identity)==entry.socket_identity)
        v,refs=self._volume(m['Name'])
        need(wire(v)==entry.volume_payload and refs==[entry.cid]and directory_identity(entry.source)==entry.source_identity)
        fresh=self.docker.inspect(entry.cid)
        need(same_snapshot(fresh,snapshot)and self._launch(writer,launch,fresh)is record and
             directory_identity(entry.source)==entry.source_identity and tuple(self.docker._socket_identity)==entry.socket_identity)
        return True

    def snapshot(self,writer,launch,snapshot):
        self._same();t=writer.t
        with self._lock:
            state=self._states.get(t)
            if state is not None:
                need(state=='COMPLETE'and t in self._entries);entry=self._entries[t]
            else:self._states[t]='REGISTERING';entry=None
        if entry is not None:return self._validate(writer,launch,snapshot,entry)
        try:
            entry=self._make(writer,launch,snapshot)
            name=json.loads(entry.volume_payload)['name']
            with self._lock:
                need(self._states[t]=='REGISTERING'and name not in self._names and t not in self._entries)
                self._entries[t]=entry;self._names[name]=t;self._states[t]='COMPLETE'
            return True
        except BaseException:
            with self._lock:self._states[t]='FAILED'
            raise

    def exact(self,writer,launch,snapshot,mount,source):
        self._same()
        with self._lock:
            need(self._states.get(writer.t)=='COMPLETE'and writer.t in self._entries);entry=self._entries[writer.t]
        need(source==entry.source and type(mount)is dict and mount==self._mount(snapshot))
        return self._validate(writer,launch,snapshot,entry)


def registry_for(core,scope_guard):
    with _LOCK:
        value=_REGISTRIES.get(id(core))
        if value is None:
            value=NativeMattermostVolumes(core,scope_guard);_REGISTRIES[id(core)]=value
        need(type(value)is NativeMattermostVolumes and value.core is core and value.scope_guard is scope_guard)
    value._same();return value


def launch_selector(core,*,scope_guard):
    """Binding is cold/lazy: no bootstrap, records, Docker or registry yet."""
    need(_admitted(core,scope_guard)is True)
    def selected(writer,name,launch,snapshot,original_binding):
        need(writer.core is core and _admitted(core,scope_guard)is True)
        record=_native_record(core,writer.t)
        need(type(original_binding)is dict and original_binding==dict(kind='ORIGINAL_ZERO_MODEL_INFRA_BOOTSTRAP',
             control_births=record['control_births']))
        if name=='mattermost':need(registry_for(core,scope_guard).snapshot(writer,launch,snapshot)is True)
        return original_binding
    return selected
