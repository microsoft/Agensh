"""Fail-closed kernel custody for new native smoke roots; no tool result API.

This is NOT a generic shell runner. A live paid CLI additionally needs the real
ordered ACP prompt/tool counters to be complete and zero, AND no process births
outside its pre-forward, zero-model native startup baseline. Missing provenance
retains the original writer; a whole-domain checkpoint may freeze it instead.
Only fixed cgroup/proc control metadata and original model-row COUNT are read.
No cmdline, process stack, locals, credentials, tool command/output or log.
"""
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import ctypes
import os
import stat
import time

from common import need
from native_peer_registry import ProcessBirth, process_birth


@dataclass(frozen=True)
class KernelCensus:
    domain: str
    domain_device: int
    domain_inode: int
    members: tuple
    directories: tuple


def _cgroup2(fd):
    value=(ctypes.c_long*32)()
    libc=ctypes.CDLL(None,use_errno=True)
    need(libc.fstatfs(fd,ctypes.byref(value))==0 and value[0]==0x63677270,
         'DYNTEAM_TOOL_CUSTODY_REAL_CGROUP2_REQUIRED')


def _bounded(path,limit):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        raw=os.read(fd,limit+1)
        need(len(raw)<=limit,'DYNTEAM_TOOL_CUSTODY_FIXED_METADATA_BOUND')
        return raw
    finally:os.close(fd)


def _relative(birth):
    need(type(birth) is ProcessBirth and process_birth(birth.pid)==birth,
         'DYNTEAM_TOOL_CUSTODY_EXACT_LIVE_BIRTH')
    raw=_bounded(Path('/proc',str(birth.pid),'cgroup'),16384)
    values=[line[3:].decode('ascii') for line in raw.splitlines() if line.startswith(b'0::')]
    need(len(values)==1,'DYNTEAM_TOOL_CUSTODY_ONE_UNIFIED_DOMAIN')
    path=PurePosixPath(values[0])
    need(path.is_absolute() and '..' not in path.parts and str(path)==values[0] and
         str(path)!='/' and process_birth(birth.pid)==birth,
         'DYNTEAM_TOOL_CUSTODY_CGROUP_PATH_AND_BIRTH_STABLE')
    return path


def kernel_census(init_birth,*,deadline_seconds=.5):
    """Finite snapshot of the exact native container's recursive cgroup domain.

    PID sets are private in-memory proof only. New/exited/raced processes or
    changed subgroups reject the observation, never synthesize an empty set.
    Caller must own no ledger/scientific lock. No domain is created/migrated.
    """
    need(type(deadline_seconds) in (int,float) and 0<deadline_seconds<=1,
         'DYNTEAM_TOOL_CUSTODY_FINITE_CONTROL_DEADLINE')
    end=time.monotonic()+deadline_seconds
    relative=_relative(init_birth);root=Path('/sys/fs/cgroup')
    need(root.resolve()==root,'DYNTEAM_TOOL_CUSTODY_CANONICAL_KERNEL_ROOT')
    domain=root/str(relative).lstrip('/')
    need(domain.resolve()==domain and domain.is_dir(),'DYNTEAM_TOOL_CUSTODY_CANONICAL_DOMAIN')
    fd=os.open(domain,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        _cgroup2(fd);identity=os.fstat(fd)
        def scan():
            pending=[domain];directories=[];pids=set()
            while pending:
                need(time.monotonic()<end and len(directories)<256,
                     'DYNTEAM_TOOL_CUSTODY_FINITE_DOMAIN_SCAN')
                path=pending.pop();current=path.lstat()
                need(stat.S_ISDIR(current.st_mode) and not path.is_symlink() and path.resolve()==path,
                     'DYNTEAM_TOOL_CUSTODY_NO_DOMAIN_ALIAS')
                directories.append((str(path),current.st_dev,current.st_ino))
                raw=_bounded(path/'cgroup.procs',65536)
                rows=raw.splitlines()
                need(all(x.isdigit() and int(x)>0 for x in rows),
                     'DYNTEAM_TOOL_CUSTODY_KERNEL_PID_FIELDS')
                pids.update(map(int,rows))
                need(len(pids)<=4096,'DYNTEAM_TOOL_CUSTODY_PROCESS_BOUND')
                with os.scandir(path) as entries:
                    for entry in entries:
                        if entry.is_symlink():
                            raise RuntimeError('DYNTEAM_TOOL_CUSTODY_NO_KERNEL_SYMLINKS')
                        if entry.is_dir(follow_symlinks=False):pending.append(Path(entry.path))
            return tuple(sorted(directories)),tuple(sorted(pids))
        directories,pids=scan()
        members=[]
        for pid in pids:
            need(time.monotonic()<end,'DYNTEAM_TOOL_CUSTODY_FINITE_PROCESS_SCAN')
            members.append(process_birth(pid))
        members=tuple(members)
        need(init_birth in members and all(time.monotonic()<end and _relative(b).is_relative_to(relative) for b in members),
             'DYNTEAM_TOOL_CUSTODY_ALL_MEMBERS_IN_EXACT_CONTAINER_DOMAIN')
        again,again_pids=scan()
        need((again,again_pids)==(directories,pids) and process_birth(init_birth.pid)==init_birth and
             (domain.stat().st_dev,domain.stat().st_ino)==(identity.st_dev,identity.st_ino) and
             all(time.monotonic()<end and process_birth(b.pid)==b for b in members),
             'DYNTEAM_TOOL_CUSTODY_DOMAIN_MEMBERS_AND_BIRTHS_STABLE')
        return KernelCensus(str(relative),identity.st_dev,identity.st_ino,members,directories)
    finally:os.close(fd)


def _control_chain(descendant,ancestor):
    """Known framework process ancestry only, never a global /proc census."""
    result=[];current=descendant
    for _ in range(32):
        result.append(current)
        if current==ancestor:return tuple(result)
        raw=_bounded(Path('/proc',str(current.pid),'stat'),16384)
        parent=int(raw[raw.rfind(b')')+2:].split()[1])
        need(parent>1,'DYNTEAM_TOOL_CUSTODY_FRAMEWORK_PARENT_CHAIN')
        current=process_birth(parent)
    raise RuntimeError('DYNTEAM_TOOL_CUSTODY_PARENT_CHAIN_BOUND')


class NativeKernelToolCustody:
    """Deferred SAME-owner callable for the original physical-tools seam.

    True means exact domains contain only proven native startup-control births
    and (for paid live CLI) real complete/zero ordered prompt/tool counters.
    A later background writer is never silently absorbed into that baseline.
    Missing control evidence stays held; full-domain checkpoint can retain it.
    """
    def __init__(self):self.core=None;self.candidates={};self.observations={}

    def bind(self,core):
        from original_relay_core import OriginalRelayCore
        need(self.core is None and type(core) is OriginalRelayCore and
             not core.qualification_only and core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0,
             'DYNTEAM_TOOL_CUSTODY_ONLY_NEW_REAL_SAME_CORE')
        self.core=core;core.native_kernel_tool_custody=self
        core.publisher.native_kernel_tool_custody=self
        return self

    def observe_cli_birth(self,t,role,birth,*,row=None):
        epochs=getattr(self,'sdk_startup_epochs',None)
        if epochs is not None:return epochs.prepare_birth(t,role,birth,row)
        from smoke_racing_tools_fresh_baseline import capture_cli_startup
        baseline=capture_cli_startup(self,t,role,birth)
        self.candidates[t,role]=birth
        return baseline

    def observe_first_native_session(self,t,role,*,row=None):
        epochs=getattr(self,'sdk_startup_epochs',None)
        if epochs is not None:return epochs.prepare_session(t,role,row)
        from smoke_racing_tools_fresh_baseline import capture_first_session_startup
        return capture_first_session_startup(self,t,role)

    def commit_native_session(self,t,role,row):
        epochs=getattr(self,'sdk_startup_epochs',None)
        if epochs is not None:return epochs.commit_session(t,role,row)
        return None

    def _legacy_strict_cli_candidate(self,t,role,birth):
        need(self.core is not None and type(birth) is ProcessBirth and
             (t,role) in self.core.roles.held and process_birth(birth.pid)==birth,
             'DYNTEAM_TOOL_CUSTODY_KNOWN_DIRECT_NATIVE_CLI_BIRTH')
        with self.core.ledger.mutex:
            count=self.core.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=? AND role=?',(t,role)).fetchone()[0]
        # Never use a fresh baseline to erase old paid tool custody.
        need(count==0,'DYNTEAM_TOOL_CUSTODY_NO_PAID_ROLE_REBASELINE')
        self.candidates[t,role]=birth

    def __call__(self,t,role):
        core=self.core
        if core is None:return False
        need(not core.ledger.mutex._is_owned(),'DYNTEAM_TOOL_CUSTODY_IO_OUTSIDE_SCIENCE_LOCK')
        try:
            need(t in core.rows and role in core.rows[t]['roles'],'DYNTEAM_TOOL_CUSTODY_REGISTERED_ROLE')
            epochs=getattr(self,'sdk_startup_epochs',None)
            if epochs is not None:
                result=epochs.project(t,role)
                if result is not None:return result
            from smoke_racing_tools_fresh_baseline import project_startup_bound_tools
            native=project_startup_bound_tools(self,t,role)
            if native is not None:return native
            registry=core.native_containers
            with core.ledger.mutex:
                paid=core.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=? AND role=?',(t,role)).fetchone()[0]
            cli=core.bridge_owner.clis.get((t,role))
            child=self.candidates.get((t,role)) if cli is None else cli['birth']
            if child is not None:
                try:child_live=process_birth(child.pid)==child
                except FileNotFoundError:child_live=False
                if paid and child_live:return False
            else:child_live=False
            censuses=[]
            for component in ('agent','router'):
                key=t,role,component
                binding=registry.records.get(key)
                plan=registry.boot_plans.get(key) if binding is None else None
                need(binding is not None or plan is not None,'DYNTEAM_TOOL_CUSTODY_MISSING_REAL_BOOT_BINDING')
                selected=binding if binding is not None else plan
                snapshot=registry.docker.inspect(selected.cid)
                need(snapshot['running'] and snapshot['pid']==selected.init_birth.pid and
                     process_birth(selected.init_birth.pid)==selected.init_birth,
                     'DYNTEAM_TOOL_CUSTODY_EXACT_SCOPE_INIT_STILL_LIVE')
                if binding is not None:registry.validate(binding,snapshot,running=True)
                else:
                    need(snapshot['image']==selected.image_id,'DYNTEAM_TOOL_CUSTODY_BOOT_IMAGE_PIN')
                census=kernel_census(selected.init_birth)
                allowed={selected.init_birth}
                if binding is not None:allowed.update(_control_chain(binding.peer_birth,binding.init_birth))
                if component=='agent' and child_live:
                    need(not paid and binding is not None,'DYNTEAM_TOOL_CUSTODY_PREMODEL_EXACT_CLI_ONLY')
                    chain=_control_chain(child,binding.peer_birth)
                    need(len(chain)==2,'DYNTEAM_TOOL_CUSTODY_ORIGINAL_DIRECT_CLI_CHILD_ONLY')
                    allowed.update(chain)
                need(set(census.members)<=allowed,'DYNTEAM_TOOL_CUSTODY_NONCONTROL_PROCESS_RETAINS_DOMAIN')
                censuses.append((selected.cid,census))
            self.observations[t,role]=dict(all_domains_stable=True,noncontrol_process_count=0,
                live_paid_cli=False,domain_count=len(censuses))
            return True
        except Exception:
            # Missing/late/raced control proof is never an empty/healthy result.
            self.observations[t,role]=dict(all_domains_stable=False,physical_tools_clear=False)
            return False
