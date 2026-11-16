"""Original MySQL logical consistent backup -> same-cut CAS/service ACK.

Host-only original instance, fixed UNIX endpoint, original mysqldump with its
native global read lock. No SQL table reads, credential/SQL/error text disclosure,
DB hot-file copy, process kill, dump replay, shared-host config or model calls.
SQL-only mode never ACKs; composite mode also seals five native volume roots.
OWN tests do not qualify actual production async drain or full collaboration.
"""
from pathlib import Path
import os
import re
import stat
import threading
import uuid
from common import need, Refused, digest, wire, strict, private_dir, hash_file, regular_fd, sync_dir, parts
from bridge import process_identity
from native_mysql_runtime import NativeMysqlRuntime
from native_service_cut import NativeServiceCut
import subprocess

COMPONENT='collaboration'
OBJECT='collaboration'
OUTPUT='mysql-all-databases.sql'
IDENTITY_SQL='SELECT @@server_uuid,@@version'
DUMP_FLAGS=['--all-databases','--lock-all-tables','--routines','--events','--triggers',
            '--hex-blob','--set-gtid-purged=OFF','--no-tablespaces','--flush-privileges',
            '--skip-dump-date','--skip-comments']


def native_compose_pin():
    from native_mcp_overlay import BASE, PUBLIC
    meta=strict((BASE/'NATIVE_PUBLIC105_CONSUMED.json').read_bytes())
    row=next(r for r in meta['sources']if r['path']=='tools/gen-compose-prod.py')
    pin=hash_file(PUBLIC/row['path'])
    need(pin=={'size':row['bytes'],'sha256':row['sha256']},'MYSQL_BACKUP_ORIGINAL_NATIVE_COMPOSE')
    return {'path':row['path'],**pin}


def backup_protocol(runtime):
    need(type(runtime)is NativeMysqlRuntime,'MYSQL_BACKUP_ORIGINAL_RUNTIME_OBJECT')
    return {'schema':'agensh-native-mysql-logical-consistent-backup-v1',
            'implementation_sha256':hash_file(Path(__file__))['sha256'],
            'runtime':runtime.verify(),'dump_flags':list(DUMP_FLAGS),'native_compose':native_compose_pin(),
            'consistency':'native-mysqldump-lock-all-tables-global-read-lock',
            'native_account_metadata':'all-databases-plus-flush-privileges',
            'requires':'same-cut-application-admission-closed-and-scientific-async-drained',
            'no_hot_file_copy':True,'replay':'none-after-started',
            'coverage':'all-native-databases-and-five-persistent-collaboration-volumes',
            'persistent_volumes':list(VOLUMES)}


def source_binding(root,relative_socket,*,user,server_uuid,version,instance_sha256):
    from common import sha, ident
    root=private_dir(root);rel=Path(*parts(relative_socket));path=root/rel
    need(path.resolve()==path and not path.is_symlink(),'MYSQL_BACKUP_CANONICAL_SOCKET')
    st=path.lstat();parent=path.parent.stat();r=root.stat()
    need(stat.S_ISSOCK(st.st_mode) and st.st_nlink==1,'MYSQL_BACKUP_NATIVE_UNIX_SOCKET')
    ident(user);sha(instance_sha256)
    need(type(server_uuid)is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',server_uuid)
         and version=='8.4.10','MYSQL_BACKUP_REGISTERED_NATIVE_VERSION_UUID')
    return {'schema':'agensh-native-mysql-source-binding-v1','root':str(root),
            'socket':str(rel),'instance_sha256':instance_sha256,'user':user,
            'server_uuid':server_uuid,'version':version,
            'root_device':r.st_dev,'root_inode':r.st_ino,
            'parent_device':parent.st_dev,'parent_inode':parent.st_ino,
            'socket_device':st.st_dev,'socket_inode':st.st_ino,'socket_uid':st.st_uid,'socket_gid':st.st_gid}


class NativeMysqlEndpoint:
    """Trusted owner input only. Credentials never enter argv/hash/log/disk.

    Future native compose must place its backup UDS under the experiment-owned
    private MySQL volume, reachable only by trusted owner. No TCP publication or
    worker SQL capability. Parent-dir FD preserves exact pathname resolution.
    """
    def __init__(self,root,relative_socket,*,user,password,server_uuid,version,instance_sha256,
                 expected_binding_sha256):
        self.binding=source_binding(root,relative_socket,user=user,server_uuid=server_uuid,version=version,
                                    instance_sha256=instance_sha256)
        need(digest(self.binding)==expected_binding_sha256,'MYSQL_BACKUP_ORIGINAL_ENDPOINT_PIN')
        need(type(password)is str and '\0'not in password and len(password.encode())<=4096,
             'MYSQL_BACKUP_PRIVATE_PASSWORD')
        self.root=Path(root);self.relative_socket=relative_socket;self.password=password
        self.binding_sha=expected_binding_sha256

    def current(self):
        b=self.binding
        need(source_binding(self.root,self.relative_socket,user=b['user'],server_uuid=b['server_uuid'],
             version=b['version'],instance_sha256=b['instance_sha256'])==b,
             'MYSQL_BACKUP_ENDPOINT_INODE_OR_INSTANCE_CHANGED')

    def options(self):
        self.current();path=self.root/self.relative_socket
        dfd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        mfd=None
        try:
            st=os.fstat(dfd)
            need((st.st_dev,st.st_ino)==(self.binding['parent_device'],self.binding['parent_inode']),
                 'MYSQL_BACKUP_SOCKET_PARENT_OPEN_RACE')
            # Fixed [client] password only; no user-selectable host/plugin/options.
            escapes={'\\':'\\\\','"':'\\"','\n':'\\n','\r':'\\r','\t':'\\t','\b':'\\b'}
            password=''.join(escapes.get(c,c)for c in self.password)
            content=('[client]\npassword="'+password+'"\n').encode()
            mfd=os.memfd_create('agensh-private-mysql-options',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
            need(os.write(mfd,content)==len(content),'MYSQL_BACKUP_PRIVATE_OPTIONS_WRITE')
            os.fchmod(mfd,0o400);os.lseek(mfd,0,os.SEEK_SET)
            import fcntl
            fcntl.fcntl(mfd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL)
            args=[f'--defaults-file=/proc/self/fd/{mfd}','--no-login-paths','--protocol=SOCKET',
                  f'--socket=/proc/self/fd/{dfd}/'+path.name,'--user='+self.binding['user'],
                  '--ssl-mode=DISABLED']
            return args,(dfd,mfd)
        except BaseException:
            os.close(dfd)
            if mfd is not None:os.close(mfd)
            raise


class NativeMysqlCommand:
    """Retain exact native Popen before fallible STARTED metadata. No timeout kill."""
    def __init__(self,ledger,trajectory,runtime,endpoint,home):
        self.ledger,self.t,self.runtime,self.endpoint=ledger,trajectory,runtime,endpoint
        self.home=private_dir(home);self.children={};self.lock=threading.RLock()

    def _terminal(self,scope,child,identity,code):
        meta={**identity,'exit_code':code if code>=0 else None,'signal':-code if code<0 else None}
        with self.ledger.tx():self.ledger.event(self.t,'NATIVE_MYSQL_CHILD_TERMINAL',{'scope':scope,**meta})
        with self.lock:self.children.pop(scope,None)
        self.ledger.release_native_service(scope)
        return meta

    def _retain(self,scope,child,identity):
        def drain():
            try:
                if child.stdout and not child.stdout.closed:
                    while child.stdout.read(65536):pass
                    child.stdout.close()
                code=child.wait()
                self._terminal(scope,child,identity,code)
            except BaseException:
                # Strong references stay in self.children and ledger custody.
                self.ledger.latch_fault(self.t,'NATIVE_MYSQL_TERMINAL_CUSTODY_UNKNOWN')
        thread=threading.Thread(target=drain,name='native-mysql-custodian',daemon=False)
        try:thread.start()
        except BaseException:drain()

    def run(self,name,args,*,output_fd=None,input_fd=None):
        self.endpoint.current();options,fds=self.endpoint.options();scope='mysql-'+uuid.uuid4().hex
        child=None;identity=None;retained=False
        try:
            command=self.runtime.command(name,options+args)
            with self.ledger.tx():self.ledger.event(self.t,'NATIVE_MYSQL_CHILD_ALLOCATING',
                {'scope':scope,'native_command':name,'endpoint_binding_sha256':self.endpoint.binding_sha,
                 'runtime_pin_sha256':self.runtime.pin_sha})
            self.ledger.retain_native_service(scope,self)
            env={'PATH':'/usr/bin:/bin','HOME':str(self.home),'LC_ALL':'C','TZ':'UTC','OPENSSL_CONF':'/dev/null'}
            child=subprocess.Popen(command,stdin=subprocess.DEVNULL if input_fd is None else input_fd,
                stdout=subprocess.PIPE if output_fd is None else output_fd,stderr=subprocess.DEVNULL,
                env=env,pass_fds=fds)
            # Own first, before proc/SQLite allocation can fail. No guessed PID.
            with self.lock:self.children[scope]=child
            identity=process_identity(child.pid)
            with self.ledger.tx():self.ledger.event(self.t,'NATIVE_MYSQL_CHILD_STARTED',{'scope':scope,**identity})
            data=b''
            if child.stdout is not None:
                while True:
                    block=child.stdout.read(65536)
                    if not block:break
                    need(len(data)+len(block)<=65536,'MYSQL_BACKUP_METADATA_BOUND')
                    data+=block
                child.stdout.close()
            code=child.wait();terminal=self._terminal(scope,child,identity,code)
            need(code==0,'MYSQL_BACKUP_NATIVE_COMMAND_NONZERO')
            self.endpoint.current();return data,terminal
        except BaseException:
            self.ledger.latch_fault(self.t,'NATIVE_MYSQL_COMMAND_CUSTODY_OR_RESULT_UNKNOWN')
            if child is not None:
                with self.lock:retained=scope in self.children
                if retained:
                    if identity is None:
                        try:identity=process_identity(child.pid)
                        except BaseException:identity={'pid':child.pid,'start_ticks':None,'boot_id':None}
                    self._retain(scope,child,identity)
            else:
                # If no native process exists, don't manufacture process custody.
                with self.ledger.mutex:allocated=scope in self.ledger.native_services
                if allocated:self.ledger.release_native_service(scope)
            raise
        finally:
            for fd in fds:os.close(fd)


class NativeMysqlBackup:
    """One SQL subprotocol only. Final collaboration ACK needs volume composition."""
    def __init__(self,cut,runtime,endpoint,*,expected_protocol_sha256):
        need(type(cut)is NativeServiceCut and type(runtime)is NativeMysqlRuntime
             and type(endpoint)is NativeMysqlEndpoint,'MYSQL_BACKUP_TRUSTED_OBJECTS')
        cut.current({'DRAINING'});domain=cut.graph[COMPONENT]
        need(domain['objects']==[OBJECT],'MYSQL_BACKUP_COLLABORATION_OBJECT')
        self.protocol=backup_protocol(runtime);self.protocol_sha=digest(self.protocol)
        need(expected_protocol_sha256==self.protocol_sha==domain['backup_protocol_sha256'],
             'MYSQL_BACKUP_FROZEN_PROTOCOL')
        need(endpoint.binding['instance_sha256']==domain['instance_sha256'],'MYSQL_BACKUP_NATIVE_INSTANCE')
        self.cut,self.ledger,self.t,self.runtime,self.endpoint=cut,cut.ledger,cut.t,runtime,endpoint

    def current(self):
        self.cut.current({'DRAINING'});self.endpoint.current()
        need(backup_protocol(self.runtime)==self.protocol,'MYSQL_BACKUP_FROZEN_PROTOCOL_CHANGED')

    def run_sql(self,destination):
        """Actual SQL dump, retained separately; NOT an incomplete service ACK."""
        self.current();dest=Path(destination)
        need(dest.is_absolute()and dest.resolve()==dest and not dest.is_relative_to(self.endpoint.root)
             and not self.endpoint.root.is_relative_to(dest),'MYSQL_BACKUP_INDEPENDENT_DESTINATION')
        dest=private_dir(dest,create=True);need(not any(dest.iterdir()),'MYSQL_BACKUP_FRESH_DESTINATION')
        with self.ledger.tx():
            self.current();rows=self.ledger.db.execute("SELECT metadata FROM events WHERE trajectory=? AND kind='NATIVE_MYSQL_BACKUP_STARTED'",(self.t,))
            need(not any(strict(r[0])['cut_sha256']==self.cut.cut_sha for r in rows),
                 'MYSQL_BACKUP_ONE_NATIVE_ATTEMPT')
            self.ledger.event(self.t,'NATIVE_MYSQL_BACKUP_STARTED',
                {'cut_sha256':self.cut.cut_sha,'endpoint_binding_sha256':self.endpoint.binding_sha,
                 'backup_protocol_sha256':self.protocol_sha})
        output=dest/OUTPUT;executor=NativeMysqlCommand(self.ledger,self.t,self.runtime,self.endpoint,self.ledger.home)
        self.executor=executor
        stage='IDENTITY_CHECK'
        try:
            identity,check=executor.run('mysql',['--batch','--raw','--skip-column-names','--execute='+IDENTITY_SQL])
            expected=(self.endpoint.binding['server_uuid']+'\t'+self.endpoint.binding['version']+'\n').encode()
            need(identity==expected,'MYSQL_BACKUP_NATIVE_SERVER_UUID_OR_VERSION_MISMATCH')
            self.current()
            stage='NATIVE_DUMP'
            fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            try:
                _,terminal=executor.run('mysqldump',list(self.protocol['dump_flags']),output_fd=fd)
                self.current();need(os.fstat(fd).st_size>0,'MYSQL_BACKUP_EMPTY_NATIVE_DUMP')
                os.fchmod(fd,0o400);os.fsync(fd)
            finally:os.close(fd)
            stage='SEAL_SQL'
            sync_dir(dest);pin=hash_file(output)
            receipt={'schema':'agensh-native-mysql-sql-backup-receipt-v1',
                'cut_sha256':self.cut.cut_sha,'source_binding_sha256':self.endpoint.binding_sha,
                'instance_sha256':self.endpoint.binding['instance_sha256'],
                'backup_protocol_sha256':self.protocol_sha,'runtime_pin_sha256':self.runtime.pin_sha,
                'server_identity_checked':True,'identity_child_terminal':check,
                'dump_child_terminal':terminal,'output':pin,'native_dump_finished':True,
                'service_ACK_emitted':False,'other_collaboration_volumes_still_required':True}
            ref=self.cut.cas.store_bytes(wire(receipt));self.current()
            with self.ledger.tx():self.ledger.event(self.t,'NATIVE_MYSQL_SQL_BACKUP_SEALED',
                {'cut_sha256':self.cut.cut_sha,'receipt_sha256':ref['sha256'],'output_sha256':pin['sha256']})
            return {'native_receipt':ref,'output':output,'destination':dest,'output_pin':pin}
        except BaseException as error:
            self.ledger.latch_fault(self.t,'NATIVE_MYSQL_BACKUP_INCOMPLETE_NO_RETRY')
            try:
                with self.ledger.tx():self.ledger.event(self.t,'NATIVE_MYSQL_BACKUP_FAILED',
                    {'cut_sha256':self.cut.cut_sha,'exception_type':type(error).__name__,'stage':stage,'automatically_retried':False})
            except BaseException:pass
            raise Refused('NATIVE_MYSQL_BACKUP_INCOMPLETE_NO_RETRY')from None

# Exact persistent non-SQL collaboration volumes in the pinned native compose.
# No worker-selected names; router/board state itself is in the all-database dump.
VOLUMES=('board_lifecycle','mattermost_config','mattermost_data','mattermost_logs','mattermost_plugins')


def collaboration_volume_binding(root,volumes,instance_sha256):
    from common import sha
    root=private_dir(root);sha(instance_sha256)
    need(type(volumes)is dict and set(volumes)==set(VOLUMES),'MYSQL_BACKUP_FULL_NATIVE_VOLUME_ROSTER')
    bound={}
    for name in VOLUMES:
        rel=Path(*parts(volumes[name]));p=root/rel
        need(p.resolve()==p and not p.is_symlink(),'MYSQL_BACKUP_NATIVE_VOLUME_CANONICAL')
        st=p.lstat();need(stat.S_ISDIR(st.st_mode),'MYSQL_BACKUP_NATIVE_VOLUME_DIRECTORY')
        bound[name]={'relative':str(rel),'device':st.st_dev,'inode':st.st_ino,'uid':st.st_uid,'gid':st.st_gid}
    paths=[root/row['relative']for row in bound.values()]
    need(len(set(paths))==len(paths)and all(a==b or not a.is_relative_to(b)for a in paths for b in paths),
         'MYSQL_BACKUP_VOLUMES_DISTINCT_NONNESTED')
    return {'schema':'agensh-native-collaboration-volume-binding-v1','root':str(root),
            'instance_sha256':instance_sha256,'volumes':bound}


class NativeCollaborationBackup:
    """SQL + every native persistent volume, one actual same-cut service ACK.

    Application/scientifically meaningful async work must already be drained by
    the trusted owner. Native SQL uses global lock; volume capture uses original
    no-follow/race-checking CAS (not a hot SQL file copy). Background race refuses
    rather than relabeling an inconsistent archive. Full native composition still
    requires production service/CLI qualification, not just OWN fixture PASS.
    """
    def __init__(self,cut,runtime,endpoint,volume_root,volumes,*,expected_protocol_sha256,
                 expected_volume_binding_sha256):
        self.sql=NativeMysqlBackup(cut,runtime,endpoint,expected_protocol_sha256=expected_protocol_sha256)
        self.cut,self.ledger,self.t=cut,cut.ledger,cut.t
        self.binding=collaboration_volume_binding(volume_root,volumes,endpoint.binding['instance_sha256'])
        need(digest(self.binding)==expected_volume_binding_sha256,'MYSQL_BACKUP_ORIGINAL_VOLUME_BINDING')
        self.root=Path(volume_root);self.volumes=dict(volumes);self.binding_sha=expected_volume_binding_sha256

    def current(self):
        self.sql.current()
        need(collaboration_volume_binding(self.root,self.volumes,self.sql.endpoint.binding['instance_sha256'])==self.binding,
             'MYSQL_BACKUP_NATIVE_VOLUME_INODE_CHANGED')

    def run(self,destination):
        self.current();dest=Path(destination)
        need(dest.is_absolute()and dest.resolve()==dest and not dest.is_relative_to(self.root)
             and not self.root.is_relative_to(dest),'MYSQL_BACKUP_INDEPENDENT_VOLUME_DESTINATION')
        dest=private_dir(dest,create=True);need(not any(dest.iterdir()),'MYSQL_BACKUP_FRESH_VOLUME_DESTINATION')
        try:
            result=self.sql.run_sql(dest/'mysql')
            # Copy only opaque sealed archives; never inspect SQL/table/file rows.
            archive_dir=private_dir(dest/'volumes',create=True);sealed={}
            import shutil
            for name in VOLUMES:
                self.current();source=self.root/self.binding['volumes'][name]['relative']
                entry=self.cut.cas.capture_tree(source);self.current()
                blob=self.cut.cas.resolve(entry['archive']);out=archive_dir/(name+'.tar.gz')
                with regular_fd(blob)as source_fd:
                    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                    try:
                        with os.fdopen(os.dup(source_fd),'rb')as inp,os.fdopen(os.dup(fd),'wb')as output:
                            shutil.copyfileobj(inp,output,1024*1024);output.flush()
                        os.fsync(fd);os.fchmod(fd,0o400)
                    finally:os.close(fd)
                need(hash_file(out)==entry['archive'],'MYSQL_BACKUP_OPAQUE_VOLUME_COPY_PIN')
                sealed[name]=entry
            sync_dir(archive_dir)
            manifest={'schema':'agensh-native-collaboration-backup-manifest-v1',
                      'cut_sha256':self.cut.cut_sha,'volume_binding_sha256':self.binding_sha,
                      'mysql_receipt':result['native_receipt'],'mysql_output':result['output_pin'],
                      'volumes':sealed,'same_cut':True,'cold_search_continuation_supported':False}
            from common import publish
            publish(dest/'manifest.json',wire(manifest),mode=0o400);sync_dir(dest)
            self.current();need(hash_file(result['output'])==result['output_pin'],'MYSQL_BACKUP_SQL_CHANGED_AFTER_NATIVE_SUCCESS')
            native_receipt=self.cut.cas.store_bytes(wire(manifest))
            evidence={'cut_sha256':self.cut.cut_sha,'instance_sha256':self.sql.endpoint.binding['instance_sha256'],
                      'backup_protocol_sha256':self.sql.protocol_sha,'receipt_sha256':native_receipt['sha256']}
            reference=self.cut.record_native_backup(COMPONENT,{OBJECT:dest},evidence)
            return {'native_receipt':native_receipt,'service_receipt':reference,'destination':dest,
                    'sql':result,'volumes':sealed}
        except BaseException as error:
            self.ledger.latch_fault(self.t,'NATIVE_COLLABORATION_BACKUP_INCOMPLETE_NO_RETRY')
            try:
                with self.ledger.tx():self.ledger.event(self.t,'NATIVE_COLLABORATION_BACKUP_FAILED',
                    {'cut_sha256':self.cut.cut_sha,'exception_type':type(error).__name__,'automatically_retried':False})
            except BaseException:pass
            raise Refused('NATIVE_COLLABORATION_BACKUP_INCOMPLETE_NO_RETRY')from None
