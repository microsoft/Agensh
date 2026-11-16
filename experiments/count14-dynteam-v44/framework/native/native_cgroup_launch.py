"""Trusted OWN pre-exec cgroup FD handoff, not a Docker/config/PID mover.

This joins only the newly-created shim itself, BEFORE the outermost original
Node/SDK command. No Python preexec_fn in a multithreaded owner. No signals,
controller writes, respawn or implicit timeout retry. Failed joins retain the
original Popen custody. OPS must independently qualify actual kernel containment.
"""
from pathlib import Path, PurePosixPath
import hashlib
import os
import selectors
import stat
import threading
import time
from common import need, Refused, digest, sha
from bridge import process_identity
from native_writer_fence import _cgroup2_filesystem, process_cgroup_v2

SCHEMA = 'agensh-native-sdk-domain-launch-v1'


def _integer(value):
    return type(value) is int and value >= 0


def _trust(st, *, directory=False):
    need((stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode))
         and st.st_uid in (0, os.geteuid()) and st.st_uid != 10000
         and not st.st_mode & 0o022, 'CGROUP_LAUNCH_TRUSTED_HOST_FILE')


class NativeCgroupLaunch:
    """Reusable for ONE role's three native SDKs, never worker-controlled.

    The binding/provenance hash comes from the original OWN capsule bootstrap.
    Constructor duplicates, but does not take ownership of, the supplied FD.
    Receipt ownership is per child. Calling close never moves or kills anything.
    """
    def __init__(self, *, directory_fd, binding, expected_binding_sha256,
                 shim, expected_shim_sha256, handshake_seconds=10):
        need(type(binding) is dict and set(binding) == {
            'schema','directory','relative','device','inode','owner_uid','provenance_sha256'}
             and binding['schema'] == SCHEMA, 'CGROUP_LAUNCH_BINDING_FIELDS')
        sha(expected_binding_sha256);sha(expected_shim_sha256);sha(binding['provenance_sha256'])
        need(digest(binding) == expected_binding_sha256, 'CGROUP_LAUNCH_ORIGINAL_DOMAIN_PIN')
        need(all(_integer(binding[k]) for k in ('device','inode','owner_uid'))
             and binding['inode'] > 0, 'CGROUP_LAUNCH_BINDING_INTEGER')
        need(type(handshake_seconds) in (int,float) and 0 < handshake_seconds <= 30,
             'CGROUP_LAUNCH_BOUNDED_HANDSHAKE')
        need(type(binding['directory']) is str and type(binding['relative']) is str, 'CGROUP_LAUNCH_PATH_TYPES')
        root = Path('/sys/fs/cgroup');p = Path(binding['directory']);rel = PurePosixPath(binding['relative'])
        need(type(binding['directory']) is str and type(binding['relative']) is str
             and p.is_absolute() and p.resolve() == p and p != root and p.is_relative_to(root)
             and str(p) == binding['directory'] and not p.is_symlink()
             and str(PurePosixPath('/') / p.relative_to(root).as_posix()) == str(rel)
             and str(rel) == binding['relative'] and '..' not in rel.parts,
             'CGROUP_LAUNCH_OWN_CANONICAL_PATH')
        need(type(directory_fd) is int and directory_fd >= 3, 'CGROUP_LAUNCH_DIRECTORY_FD')
        self.lock=threading.RLock();self.fd=os.dup(directory_fd);self.closed=False
        self.binding=dict(binding);self.binding_sha=expected_binding_sha256
        self.path=p;self.relative=rel;self.shim=Path(shim);self.shim_sha=expected_shim_sha256
        self.handshake_seconds=handshake_seconds
        try:
            self.current()
            fd=self._open_shim()
            os.close(fd)
        except BaseException:
            self.close();raise

    def current(self):
        need(not self.closed, 'CGROUP_LAUNCH_CLOSED')
        st=os.fstat(self.fd);p=self.path.lstat();_trust(st,directory=True)
        need(_cgroup2_filesystem(self.fd), 'CGROUP_LAUNCH_REAL_CGROUP2')
        need((st.st_dev,st.st_ino,st.st_uid) == (
            self.binding['device'],self.binding['inode'],self.binding['owner_uid'])
             and (p.st_dev,p.st_ino)==(st.st_dev,st.st_ino)
             and self.path.resolve()==self.path and not self.path.is_symlink(),
             'CGROUP_LAUNCH_DIRECTORY_CHANGED')
        owner=process_cgroup_v2(process_identity(os.getpid()))
        need(not owner.is_relative_to(self.relative), 'CGROUP_LAUNCH_CONTROL_OWNER_INSIDE')
        for name,wanted in (('cgroup.type',b'domain'),('cgroup.freeze',b'0')):
            fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=self.fd)
            try:
                st=os.fstat(fd);_trust(st)
                raw=os.read(fd,8193)
                need(len(raw)<=8192 and raw.strip()==wanted,
                     'CGROUP_LAUNCH_RUNNING_NONTHREADED_DOMAIN')
            finally:os.close(fd)

    def _open_shim(self):
        need(self.shim.is_absolute() and self.shim.resolve()==self.shim
             and not self.shim.is_symlink(), 'CGROUP_LAUNCH_PINNED_SHIM_PATH')
        fd=os.open(self.shim,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            st=os.fstat(fd);_trust(st)
            need(st.st_nlink==1 and st.st_mode&0o111 and st.st_size<=2**20,
                 'CGROUP_LAUNCH_PINNED_SHIM_MODE')
            data=os.read(fd,2**20+1)
            after=os.fstat(fd)
            need(len(data)==st.st_size and (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)==(
                after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
                 and hashlib.sha256(data).hexdigest()==self.shim_sha,
                 'CGROUP_LAUNCH_PINNED_SHIM_BYTES')
            return fd
        except BaseException:
            os.close(fd);raise

    def prepare(self,command,environment):
        # A loader-injected library would execute before our trusted main().
        need(not any(k.startswith('LD_') or k in ('GLIBC_TUNABLES','GCONV_PATH',
             'LOCPATH','MALLOC_TRACE') for k in environment), 'CGROUP_LAUNCH_NO_LOADER_INJECTION')
        need(type(command)is list and command and all(type(x)is str and x and '\0'not in x for x in command)
             and Path(command[0]).is_absolute(), 'CGROUP_LAUNCH_ORIGINAL_COMMAND')
        with self.lock:
            self.current()
            fds=[]
            try:
                dfd=os.dup(self.fd);fds.append(dfd)
                pfd=os.open('cgroup.procs',os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=dfd);fds.append(pfd)
                p=os.fstat(pfd);_trust(p)
                need(p.st_dev==self.binding['device'], 'CGROUP_LAUNCH_PROCS_DEVICE')
                xfd=self._open_shim();fds.append(xfd)
                rfd,wfd=os.pipe2(os.O_CLOEXEC);fds.extend((rfd,wfd))
                afd,ackfd=os.pipe2(os.O_CLOEXEC);fds.extend((afd,ackfd))
                return PreparedCgroupLaunch(self,command,dfd,pfd,xfd,rfd,wfd,afd,ackfd,p.st_ino)
            except BaseException:
                for fd in fds:os.close(fd)
                raise

    def close(self):
        with self.lock:
            if not self.closed:os.close(self.fd);self.closed=True


class PreparedCgroupLaunch:
    """One child only; ack is closed without release on every failed startup."""
    def __init__(self,spec,command,dfd,pfd,xfd,rfd,wfd,afd,ackfd,pino):
        self.spec=spec;self.fds={dfd,pfd,xfd,rfd,wfd,afd,ackfd}
        self.rfd=rfd;self.wfd=wfd;self.afd=afd;self.ackfd=ackfd
        self.procs_inode=pino;self.receipt=None;self.released=False
        self.pass_fds=(dfd,pfd,xfd,wfd,afd)
        self.command=[f'/proc/self/fd/{xfd}',str(dfd),str(pfd),str(wfd),str(afd),str(xfd),
                      str(spec.binding['device']),str(spec.binding['inode']),str(pino),
                      str(spec.binding['owner_uid']),str(spec.relative),'--',*command]

    def _close(self,fd):
        if fd in self.fds:os.close(fd);self.fds.remove(fd)

    def child_started(self):
        # A parent-held ACK read end must not hide shim failure as successful write.
        for fd in self.pass_fds:self._close(fd)

    def verify(self,child,identity):
        need(self.receipt is None and not self.released, 'CGROUP_LAUNCH_SINGLE_RECEIPT')
        end=time.monotonic()+self.spec.handshake_seconds;data=b''
        with selectors.DefaultSelector() as selector:
            selector.register(self.rfd,selectors.EVENT_READ)
            while not data.endswith(b'\n'):
                remaining=end-time.monotonic()
                need(remaining>0 and selector.select(remaining), 'CGROUP_LAUNCH_RECEIPT_TIMEOUT_CUSTODY_RETAINED')
                chunk=os.read(self.rfd,513-len(data))
                need(chunk and len(data)+len(chunk)<=512, 'CGROUP_LAUNCH_RECEIPT_MISSING_OR_BOUND')
                data+=chunk
        fields=data.rstrip(b'\n').split(b' ')
        need(len(fields)==6 and fields[0]==b'AGENSH_CGROUP_PREEXEC_V1'
             and data.count(b'\n')==1 and all(x.isdigit() for x in fields[1:]),
             'CGROUP_LAUNCH_RECEIPT_FORMAT')
        values=tuple(int(x) for x in fields[1:])
        need(identity==process_identity(child.pid) and values==(
            identity['pid'],identity['start_ticks'],self.spec.binding['device'],
            self.spec.binding['inode'],self.procs_inode), 'CGROUP_LAUNCH_RECEIPT_PROCESS_BINDING')
        with self.spec.lock:self.spec.current()
        need(process_cgroup_v2(identity)==self.spec.relative and child.poll() is None,
             'CGROUP_LAUNCH_ACTUAL_MEMBERSHIP_BEFORE_EXEC')
        body={'schema':'agensh-native-sdk-preexec-receipt-v1',
              'domain_binding_sha256':self.spec.binding_sha,'shim_sha256':self.spec.shim_sha,
              'process':dict(identity),'relative':str(self.spec.relative),
              'device':self.spec.binding['device'],'inode':self.spec.binding['inode'],
              'procs_inode':self.procs_inode,'original_command_not_yet_executed':True}
        self.receipt={**body,'sha256':digest(body)}
        return dict(self.receipt)

    def release(self):
        need(self.receipt is not None and not self.released, 'CGROUP_LAUNCH_VERIFIED_BEFORE_RELEASE')
        need(os.write(self.ackfd,b'1')==1, 'CGROUP_LAUNCH_ACK_CUSTODY_UNKNOWN')
        self.released=True;self.close()

    def close(self):
        # Closing the ACK without writing is a refusal, never a command retry.
        for fd in tuple(self.fds):self._close(fd)
