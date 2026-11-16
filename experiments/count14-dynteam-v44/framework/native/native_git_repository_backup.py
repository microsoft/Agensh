"""Original Gitea repo CAS + exact preregistered native git-archive exports.

Read-only trusted host producer; no Git history candidate expansion, worker URL,
credential, local hooks, network, retry, signal, source or candidate inspection.
Native application async drain is STILL the cold owner's independent obligation.
This component's source guards do not assert that a backend has no pending job.
"""
from pathlib import Path
import copy,os,re,shutil,stat,subprocess,threading,uuid
from common import need,digest,sha,hash_file,private_dir,publish,sync_dir,wire,strict,Refused
from bridge import process_identity
from native_gitea import NativeGitea,binding_identity
from native_service_cut import NativeServiceCut

COMPONENT='gitea'
OBJECT='gitea_repo'

def backup_protocol():
    root=Path(__file__).resolve().parent
    return {'schema':'agensh-original-native-git-repository-backup-protocol-v1',
            'implementations':{n:hash_file(root/n)['sha256']for n in
                ('native_git_repository_backup.py','native_gitea.py','snapshot.py','common.py')},
            'repository':'complete-original-bare-tree-through-original-no-follow-CAS',
            'exports':'original-git-archive-tar.gz-at-exact-registered-ref-commit',
            'selection':'unchanged-original-collector-only-after-COMMITTED',
            'source_and_refs_reverified_before_publication':True,
            'application_async_drain_not_proven_by_this_component':True}

def repository_binding(root,instance_sha256):
    sha(instance_sha256);p=Path(root);st=p.lstat()
    need(p.is_absolute()and p.resolve()==p and stat.S_ISDIR(st.st_mode),
         'GIT_BACKUP_ORIGINAL_CANONICAL_BARE_ROOT')
    # Native bare layout only. No linked worktree, alternate object database or
    # graft pointing outside the exact original service repository is admitted.
    for name in ('HEAD','config'):
        s=(p/name).lstat();need(stat.S_ISREG(s.st_mode)and s.st_nlink==1,
                             'GIT_BACKUP_ORIGINAL_BARE_LAYOUT')
    for name in ('objects','refs'):
        s=(p/name).lstat();need(stat.S_ISDIR(s.st_mode),'GIT_BACKUP_ORIGINAL_BARE_LAYOUT')
    need(all(not(p/name).exists()and not(p/name).is_symlink()for name in
        ('commondir','gitdir','shallow','info/grafts','objects/info/alternates','objects/info/http-alternates')),
         'GIT_BACKUP_NO_EXTERNAL_OBJECT_OR_GRAFT_ROOT')
    return {'schema':'agensh-original-gitea-repository-root-binding-v1',
            'instance_sha256':instance_sha256,'device':st.st_dev,'inode':st.st_ino,
            'uid':st.st_uid,'gid':st.st_gid,'path':str(p)}

class NativeGitRepositoryBackup:
    def __init__(self,publication,repository_root,*,registered_refs,
                 expected_repository_binding_sha256,expected_publication_pin):
        need(type(publication)is NativeGitea,'GIT_BACKUP_ORIGINAL_PUBLICATION_PORT')
        self.pub=publication;self.ledger=publication.ledger;self.t=publication.binding.trajectory
        self.original_publication_binding=(publication.origin,publication.binding_sha)
        need(getattr(publication,'repository_backup',None)is None,'GIT_BACKUP_FIRST_START_BIND_ONCE')
        origin,bsha=binding_identity(publication.binding)
        need(origin==publication.origin and bsha==publication.binding_sha,'GIT_BACKUP_ORIGINAL_PUBLICATION_BINDING')
        self.root=Path(repository_root)
        need(self.root.name==publication.binding.repository+'.git'and
             self.root.parent.name==publication.binding.organization,'GIT_BACKUP_ORIGINAL_ORG_REPOSITORY')
        self.binding=repository_binding(self.root,publication.binding.service_instance_sha256)
        self.binding_sha=sha(expected_repository_binding_sha256)
        need(digest(self.binding)==self.binding_sha,'GIT_BACKUP_ORIGINAL_ROOT_PIN')
        need(type(registered_refs)is tuple and registered_refs and len(set(registered_refs))==len(registered_refs)
             and all(type(r)is str and re.fullmatch(r'refs/[A-Za-z0-9_./-]+',r)and
                     not any(x in r for x in ('..','//','/.'))and not r.endswith(('/', '.lock', '.'))
                     for r in registered_refs),'GIT_BACKUP_PREREGISTERED_REF_SET')
        self.refs=registered_refs;self.pin=copy.deepcopy(expected_publication_pin)
        self.publication_path=publication.home/'gitea-publication.json'
        need(hash_file(self.publication_path)==self.pin,'GIT_BACKUP_ORIGINAL_PUBLICATION_RECEIPT')
        self.publication_sha=digest(strict(self.publication_path.read_bytes()))
        self.publication_operation=publication.operation
        with self.ledger.mutex:
            op=self.ledger.db.execute('SELECT * FROM operations WHERE id=?',(publication.operation,)).fetchone()
            f=self.ledger.frontier(self.t)
            need(op is not None and op['trajectory']==self.t and op['kind']=='GIT_WRITE'and op['state']=='COMPLETE'
                 and f['state']=='RUNNING'and f['generation']==1
                 and self.ledger.db.execute('SELECT COUNT(*)FROM requests WHERE trajectory=?',(self.t,)).fetchone()[0]==0,
                 'GIT_BACKUP_FIRST_START_AFTER_NATIVE_PUBLICATION_BEFORE_MODEL')
            proof=[strict(r[0])for r in self.ledger.db.execute("SELECT metadata FROM events WHERE trajectory=?AND kind='GITEA_PUBLICATION_VERIFIED'",(self.t,))]
            need(len(proof)==1 and proof[0].get('operation_id')==publication.operation
                 and proof[0].get('receipt_sha256')==self.publication_sha,'GIT_BACKUP_NATIVE_PUBLICATION_EVENT')
        self.git=publication.git;self.git_sha=publication.git_sha;self.process=process_identity(os.getpid())
        self.protocol=backup_protocol();self.protocol_sha=digest(self.protocol)
        self.graph_domain={'instance_sha256':publication.binding.service_instance_sha256,
                           'backup_protocol_sha256':self.protocol_sha,'objects':[OBJECT]}
        self.lock=threading.RLock();self.children={};self.captures={}
        publication.repository_backup=self
    def _current(self,cut,states={'DRAINING'}):
        need(type(cut)is NativeServiceCut and cut.ledger is self.ledger and cut.t==self.t,
             'GIT_BACKUP_ORIGINAL_SAME_CUT')
        cut.current(states)
        need(self.pub.repository_backup is self and process_identity(os.getpid())==self.process
             and self.pub.operation==self.publication_operation
             and binding_identity(self.pub.binding)==(self.pub.origin,self.pub.binding_sha)==self.original_publication_binding
             and self.pub.git==self.git and self.pub.git_sha==self.git_sha
             and repository_binding(self.root,self.pub.binding.service_instance_sha256)==self.binding
             and hash_file(self.publication_path)==self.pin and hash_file(self.git)['sha256']==self.git_sha
             and backup_protocol()==self.protocol and cut.graph[COMPONENT]==self.graph_domain,
             'GIT_BACKUP_ORIGINAL_BINDING_CHANGED')
        if cut.writer_fence is not None:
            fence=cut.writer_fence
            fence.verify_capture(cut,{r:{'workspace':fence.owner.gb['workspace_roots'][r]['path']}for r in fence.owner.roles})
    def _event(self,kind,value):
        with self.ledger.tx():self.ledger.event(self.t,kind,value)
    def _command(self,args,*,output=None):
        scope='native-git-backup-'+uuid.uuid4().hex;child=None
        # All args here are fixed host choices/ref names/validated object ids.
        # No credential/network, user config, replace refs, hooks or lazy fetch.
        command=[str(self.git),'--no-optional-locks','-c','core.hooksPath=/dev/null',
                 '-c','core.fsmonitor=false','-c','credential.helper=','-c','protocol.allow=never',
                 '--git-dir='+str(self.root),*args]
        env={'PATH':'/usr/bin:/bin','HOME':str(self.pub.home),'LANG':'C','LC_ALL':'C',
             'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_TERMINAL_PROMPT':'0',
             'GIT_NO_REPLACE_OBJECTS':'1','GIT_OPTIONAL_LOCKS':'0','GIT_NO_LAZY_FETCH':'1'}
        self.ledger.retain_native_service(scope,self)
        def terminal():
            code=child.wait()
            self._event('NATIVE_GIT_BACKUP_CHILD_TERMINAL',{'scope':scope,'pid':child.pid,
                        'exit_code':code if code>=0 else None,'signal':-code if code<0 else None})
            self.children.pop(scope,None);self.ledger.release_native_service(scope);return code
        try:
            self._event('NATIVE_GIT_BACKUP_CHILD_ALLOCATING',{'scope':scope,'arguments_sha256':digest(args),'git_executable_sha256':self.git_sha})
            child=subprocess.Popen(command,env=env,cwd=self.root,stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE if output is None else output,stderr=subprocess.DEVNULL)
            self.children[scope]=child # own BEFORE fallible identity/metadata
            self._event('NATIVE_GIT_BACKUP_CHILD_STARTED',{'scope':scope,**process_identity(child.pid)})
            data=bytearray();overflow=False
            if output is None:
                for block in iter(lambda:child.stdout.read(65536),b''):
                    if len(data)+len(block)>2**20:overflow=True
                    if not overflow:data.extend(block)
                child.stdout.close()
            code=terminal();need(not overflow,'GIT_BACKUP_METADATA_BOUND')
            need(code==0,'GIT_BACKUP_NATIVE_COMMAND_NONZERO');return bytes(data)
        except BaseException:
            self.ledger.latch_fault(self.t,'NATIVE_GIT_BACKUP_CHILD_UNKNOWN_RETAIN_NO_RETRY')
            if child is None:self.ledger.release_native_service(scope)
            elif scope in self.children:
                def drain():
                    try:
                        if child.stdout is not None and not child.stdout.closed:
                            for _ in iter(lambda:child.stdout.read(65536),b''):pass
                            child.stdout.close()
                        terminal()
                    except BaseException:self.ledger.latch_fault(self.t,'NATIVE_GIT_BACKUP_TERMINAL_STORAGE_UNKNOWN')
                thread=threading.Thread(target=drain,name='native-git-backup-custodian',daemon=False)
                try:thread.start()
                except BaseException:drain()
            raise
    def _refs(self):
        values={}
        for ref in self.refs:
            raw=self._command(['rev-parse','--verify',ref+'^{commit}'])
            need(re.fullmatch(b'[0-9a-f]{40}\n|[0-9a-f]{64}\n',raw)is not None,'GIT_BACKUP_EXACT_COMMIT_OBJECT')
            values[ref]=raw.decode().strip()
        return values
    def run(self,cut,destination):
        with self.lock:
            self._current(cut)
            need(not self.children,'GIT_BACKUP_PRIOR_CHILD_CUSTODY')
            dest=Path(destination)
            need(dest.is_absolute()and dest.resolve()==dest and not dest.exists()
                 and not dest.is_relative_to(self.root)and not self.root.is_relative_to(dest),
                 'GIT_BACKUP_FRESH_INDEPENDENT_DESTINATION')
            with self.ledger.tx():
                need(COMPONENT not in cut.receipts and not any(strict(r[0]).get('cut_sha256')==cut.cut_sha
                    for r in self.ledger.db.execute("SELECT metadata FROM events WHERE trajectory=?AND kind='NATIVE_GIT_REPOSITORY_BACKUP_STARTED'",(self.t,))),
                    'GIT_BACKUP_ONE_DURABLE_CUT_ATTEMPT')
                cut.bind_gitea_backup(self)
                self.ledger.event(self.t,'NATIVE_GIT_REPOSITORY_BACKUP_STARTED',{'cut_sha256':cut.cut_sha,'root_binding_sha256':self.binding_sha,'protocol_sha256':self.protocol_sha})
            try:
                dest=private_dir(dest,create=True);source=cut.cas.capture_tree(self.root)
                # Include the opaque complete repository blob INSIDE the shared
                # object too, so normal snapshot closure/transfer doesn't depend
                # on interpreting an application manifest's nested CAS pointer.
                repository_archive=dest/'repository.tar.gz'
                shutil.copyfile(cut.cas.resolve(source['archive']),repository_archive)
                with repository_archive.open('rb')as f:os.fsync(f.fileno())
                repository_archive.chmod(0o400)
                need(hash_file(repository_archive)==source['archive'],'GIT_BACKUP_REPOSITORY_COPY_PIN')
                refs=self._refs();exports=[];out=private_dir(dest/'exports',create=True)
                for i,ref in enumerate(self.refs):
                    self._current(cut);p=out/(str(i)+'.tar.gz')
                    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                    try:
                        self._command(['archive','--format=tar.gz',refs[ref]],output=fd);os.fsync(fd);os.fchmod(fd,0o400)
                    finally:os.close(fd)
                    staged=cut.cas.temporary();shutil.copyfile(p,staged)
                    archive=cut.cas.store(staged);need(hash_file(p)==archive,'GIT_BACKUP_EXPORT_COPY_PIN')
                    exports.append({'ref':ref,'commit':refs[ref],'archive':archive})
                sync_dir(out);self._current(cut)
                need(self._refs()==refs and cut.cas.capture_tree(self.root)==source,'GIT_BACKUP_SOURCE_CHANGED_DURING_EXPORT')
                # Preserve actual original complete repository archive/census and
                # native exports as immutable CAS objects; no history selection.
                manifest={'schema':'agensh-original-native-gitea-repo-backup-manifest-v1',
                          'cut_sha256':cut.cut_sha,'root_binding_sha256':self.binding_sha,
                          'publication_receipt_pin':self.pin,'source_repository':source,
                          'registered_refs':list(self.refs),'exports':exports,'protocol':self.protocol}
                publish(dest/'MANIFEST.json',wire(manifest),mode=0o400);sync_dir(dest)
                receipt=cut.cas.store_bytes(wire(manifest))
                result={'source':source,'refs':refs,'git_exports':exports,'native_receipt':receipt,
                        'destination':dest,'manifest':manifest}
                self.captures[cut.cut_sha]=result
                evidence={'cut_sha256':cut.cut_sha,'instance_sha256':self.graph_domain['instance_sha256'],
                          'backup_protocol_sha256':self.protocol_sha,'receipt_sha256':receipt['sha256']}
                result['service_receipt']=cut.record_native_backup(COMPONENT,{OBJECT:dest},evidence)
                return result
            except BaseException as e:
                self.ledger.latch_fault(self.t,'NATIVE_GIT_REPOSITORY_BACKUP_INCOMPLETE_NO_RETRY')
                try:self._event('NATIVE_GIT_REPOSITORY_BACKUP_FAILED',{'cut_sha256':cut.cut_sha,'exception_type':type(e).__name__})
                except BaseException:pass
                raise Refused('NATIVE_GIT_REPOSITORY_BACKUP_INCOMPLETE_NO_RETRY')from None
    def verify_capture(self,cut,draft):
        with self.lock:
            self._current(cut,{'CAPTURING'})
            need(not self.children and cut.cut_sha in self.captures,'GIT_BACKUP_ORIGINAL_CAPTURE_REQUIRED')
            row=self.captures[cut.cut_sha]
            need(cut.gitea_backup is self and cut.receipts[COMPONENT]==row['service_receipt']
                 and cut.cas.capture_tree(self.root)==row['source']and self._refs()==row['refs'],
                 'GIT_BACKUP_ORIGINAL_SOURCE_CHANGED_BEFORE_PUBLICATION')
            need(draft['pins'].get('gitea_exports')==digest({'registered_refs':list(self.refs),'exports':row['git_exports']}),
                 'GIT_BACKUP_DRAFT_EXACT_ORIGINAL_EXPORTS')
            need(strict(cut.cas.resolve(row['native_receipt']).read_bytes())==row['manifest'],
                 'GIT_BACKUP_ORIGINAL_NATIVE_RECEIPT_CHANGED')
            cut.cas.resolve(row['source']['archive'])
            for export in row['git_exports']:cut.cas.resolve(export['archive'])
