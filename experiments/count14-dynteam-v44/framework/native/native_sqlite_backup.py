"""Actual Gitea SQLite online backup -> same-cut NativeServiceCut/CAS/ACK.

Not a hot-file copy and not a source-table/log reader. The trusted owner provides
an already-closed, fully drained application write boundary. This port creates
an independent complete SQLite backup and verifies it before any service ACK.
It does NOT implement MySQL/Mattermost backup, process freezing or the writer
boundary. No model/candidate/task/evaluator data or error text is disclosed.
"""
from pathlib import Path, PurePosixPath
from contextlib import closing
import os, sqlite3, stat
from common import need, Refused, digest, hash_file, private_dir, regular_fd, sync_dir, wire, parts
from native_service_cut import NativeServiceCut

COMPONENT = 'gitea_database'
OBJECT = 'gitea_database'
OUTPUT = 'gitea.sqlite'

def backup_protocol():
    return {'schema':'agensh-gitea-sqlite-native-backup-v1',
            'implementation_sha256':hash_file(Path(__file__))['sha256'],
            'sqlite_version':sqlite3.sqlite_version,
            'source':'native-readonly-connection-with-live-WAL',
            'copy':'sqlite3.Connection.backup',
            'destination':'independent-private-SQLite-database-delete-journal',
            'validation':'quick_check-before-fsync-before-service-ACK',
            'requires':'same-cut-application-admission-closed-and-drained',
            'replay':'none-after-started'}

def source_binding(root, relative_database, instance_sha256):
    """Trusted bootstrap/OPS pins actual native DB inode, not worker JSON.

    `root` is the owner's private enclosing experiment directory. Native data
    below it may belong to its backend UID; none is made public or chmod'ed.
    No database contents are read. Pin the returned metadata before backup.
    """
    root=private_dir(root);rel=PurePosixPath(*parts(relative_database))
    path=root.joinpath(*rel.parts)
    need(path.resolve()==path and path.is_relative_to(root),'SQLITE_BACKUP_CANONICAL_SOURCE')
    # Reject special files BEFORE open as well: O_RDONLY on a FIFO could block
    # forever before regular_fd's post-open type check. Backend paths are under
    # the host's private root; worker/agent never controls these ancestors.
    pre=path.lstat()
    need(stat.S_ISREG(pre.st_mode)and pre.st_nlink==1,'SQLITE_BACKUP_SOURCE_SINGLE_REGULAR')
    with regular_fd(path)as fd:
        st=os.fstat(fd)
        need((st.st_dev,st.st_ino)==(pre.st_dev,pre.st_ino),'SQLITE_BACKUP_SOURCE_OPEN_RACE')
        need(stat.S_ISREG(st.st_mode)and st.st_nlink==1,'SQLITE_BACKUP_SOURCE_SINGLE_REGULAR')
    # Only metadata/instance identity: WAL-state bytes are captured by SQLite,
    # not approximated by a source-file hash, mtime or quiet-file interval.
    from common import sha
    sha(instance_sha256)
    return {'schema':'agensh-native-sqlite-source-binding-v1','root':str(root),
            'database':str(rel),'instance_sha256':instance_sha256,
            'device':st.st_dev,'inode':st.st_ino,'uid':st.st_uid,'gid':st.st_gid}

class NativeSqliteBackup:
    def __init__(self,cut,root,relative_database,*,expected_source_binding_sha256,expected_protocol_sha256):
        need(isinstance(cut,NativeServiceCut),'SQLITE_BACKUP_TRUSTED_NATIVE_CUT')
        cut.current({'DRAINING'})
        domain=cut.graph[COMPONENT]
        need(domain['objects']==[OBJECT],'SQLITE_BACKUP_EXACT_DATABASE_OBJECT')
        self.protocol=backup_protocol();self.protocol_sha=digest(self.protocol)
        need(self.protocol_sha==expected_protocol_sha256==domain['backup_protocol_sha256'],
             'SQLITE_BACKUP_FROZEN_NATIVE_PROTOCOL')
        self.binding=source_binding(root,relative_database,domain['instance_sha256'])
        need(digest(self.binding)==expected_source_binding_sha256,'SQLITE_BACKUP_FROZEN_SOURCE_INSTANCE')
        self.cut,self.ledger,self.t=cut,cut.ledger,cut.t
        self.root=Path(root);self.relative_database=relative_database
        self.source=self.root.joinpath(*PurePosixPath(relative_database).parts)
        self.binding_sha=digest(self.binding)

    def _current(self):
        self.cut.current({'DRAINING'})
        need(source_binding(self.root,self.relative_database,self.binding['instance_sha256'])==self.binding,
             'SQLITE_BACKUP_SOURCE_INODE_OR_INSTANCE_CHANGED')

    def _started(self):
        rows=self.ledger.db.execute("SELECT metadata FROM events WHERE trajectory=? AND kind='NATIVE_SQLITE_BACKUP_STARTED'",(self.t,))
        from common import strict
        return any(strict(r[0])['cut_sha256']==self.cut.cut_sha for r in rows)

    def run(self,destination):
        """One actual backup. On failure preserve partial files, latch, no retry.

        `destination` must be a fresh private directory outside the native source
        directory. The original DB/WAL are not copied, modified or checkpointed.
        SQLite may take its ordinary read locks/SHM locks on the live database.
        """
        self._current()
        dest=Path(destination)
        need(dest.is_absolute() and dest.resolve()==dest
             and not self.source.is_relative_to(dest) and not dest.is_relative_to(self.source.parent),
             'SQLITE_BACKUP_NEW_INDEPENDENT_DESTINATION')
        # Validate before mkdir: rejecting a source-relative destination must
        # not create directories inside the live native service data tree.
        dest=private_dir(dest,create=True)
        need(not any(dest.iterdir()),'SQLITE_BACKUP_NEW_INDEPENDENT_DESTINATION')
        # Allocate once under the same original durable owner. A new Python port
        # object cannot rerun this cut after failure/interruption or even success.
        with self.ledger.tx():
            self._current()
            need(COMPONENT not in self.cut.receipts and not self._started(),'SQLITE_BACKUP_ONE_NATIVE_ATTEMPT')
            self.ledger.event(self.t,'NATIVE_SQLITE_BACKUP_STARTED',
                              {'cut_sha256':self.cut.cut_sha,'source_binding_sha256':self.binding_sha,
                               'backup_protocol_sha256':self.protocol_sha})
        output=dest/OUTPUT;progress={'calls':0,'remaining':None,'total':None}
        try:
            fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            os.close(fd)
            def advanced(status,remaining,total):
                self._current()
                progress.update(calls=progress['calls']+1,remaining=remaining,total=total)
            # Keep the originally pinned source inode open until the protocol is
            # finished; identity is rechecked before and during SQLite's copy.
            with regular_fd(self.source)as source_fd:
                st=os.fstat(source_fd)
                need((st.st_dev,st.st_ino)==(self.binding['device'],self.binding['inode']),
                     'SQLITE_BACKUP_SOURCE_OPEN_IDENTITY')
                with closing(sqlite3.connect(self.source.as_uri()+'?mode=ro',uri=True))as src:
                    src.execute('PRAGMA query_only=ON');src.execute('PRAGMA trusted_schema=OFF')
                    with closing(sqlite3.connect(output))as dst:
                        dst.execute('PRAGMA trusted_schema=OFF')
                        src.backup(dst,pages=128,progress=advanced)
                        need(progress['calls']>0 and progress['remaining']==0,'SQLITE_BACKUP_NATIVE_NOT_COMPLETE')
                        # This affects the independent destination ONLY; do not
                        # checkpoint/change the native source journal mode.
                        need(dst.execute('PRAGMA journal_mode=DELETE').fetchone()==('delete',),
                             'SQLITE_BACKUP_DESTINATION_JOURNAL')
                        need(dst.execute('PRAGMA quick_check').fetchall()==[('ok',)],
                             'SQLITE_BACKUP_INTEGRITY_CHECK')
                        pages=dst.execute('PRAGMA page_count').fetchone()[0]
                        page_size=dst.execute('PRAGMA page_size').fetchone()[0]
                self._current()
            need(set(p.name for p in dest.iterdir())=={OUTPUT},'SQLITE_BACKUP_NO_SIDECAR_DEPENDENCY')
            with regular_fd(output)as fd:
                os.fchmod(fd,0o400);os.fsync(fd)
            sync_dir(dest)
            pin=hash_file(output)
            receipt={'schema':'agensh-native-sqlite-backup-receipt-v1','cut_sha256':self.cut.cut_sha,
                     'source_binding':self.binding,'backup_protocol':self.protocol,
                     'output':pin,'pages':pages,'page_size':page_size,
                     'native_backup_finished':True,'integrity_check':'ok',
                     'source_journal_checkpoint_requested':False}
            native_receipt=self.cut.cas.store_bytes(wire(receipt));self._current()
            evidence={'cut_sha256':self.cut.cut_sha,'instance_sha256':self.binding['instance_sha256'],
                      'backup_protocol_sha256':self.protocol_sha,'receipt_sha256':native_receipt['sha256']}
            reference=self.cut.record_native_backup(COMPONENT,{OBJECT:dest},evidence)
            return {'source_binding_sha256':self.binding_sha,'native_receipt':native_receipt,
                    'service_receipt':reference,'destination':dest}
        except BaseException as exc:
            # Never expose SQLite messages, file paths, rows, locals or payloads.
            self.ledger.latch_fault(self.t,'NATIVE_SQLITE_BACKUP_INCOMPLETE_NO_RETRY')
            try:
                with self.ledger.tx():
                    self.ledger.event(self.t,'NATIVE_SQLITE_BACKUP_FAILED',
                                      {'cut_sha256':self.cut.cut_sha,'exception_type':type(exc).__name__,
                                       'code':'NATIVE_SQLITE_BACKUP_INCOMPLETE_NO_RETRY'})
            except Exception:pass # memory fault above remains fail-closed
            raise Refused('NATIVE_SQLITE_BACKUP_INCOMPLETE_NO_RETRY')from None
