"""Trusted all-role stop-point capture, immutable CAS; explicit L1, not L2.

Only the trusted runtime calls these APIs. Public receipts contain object
hashes/sizes, never captured file paths or data. No live database copies: callers
must provide native consistent backups after all required service ACKs.
"""
from pathlib import Path
from decimal import Decimal
from contextlib import contextmanager
import gzip,hashlib,json,os,stat,tarfile,uuid
from common import need,private_dir,stamp,parts,hash_file,sha,wire,digest,publish,sync_dir,regular_fd,strict,integer
SHARED=frozenset(('gitea_repo','gitea_database','collaboration','relay_continuation','usage_journal','bridge_journal','candidate_manifest'))
class CAS:
    def __init__(self,home):
        self.home=private_dir(home,create=True);self.objects=private_dir(self.home/'objects',create=True);self.stage=private_dir(self.home/'staging',create=True);self.refs=private_dir(self.home/'snapshots',create=True)
    def temporary(self):return self.stage/(uuid.uuid4().hex+'.partial')
    def store(self,p):
        p=Path(p);need(p.parent==self.stage,'PRIVATE_CAS_STAGING');r=hash_file(p);dest=self.objects/r['sha256']
        os.chmod(p,0o400)
        with regular_fd(p) as fd:os.fsync(fd)
        try:os.link(p,dest,follow_symlinks=False)
        except FileExistsError:need(hash_file(dest)==r,'CAS_OBJECT_CONFLICT')
        sync_dir(self.objects);p.unlink();sync_dir(self.stage);return r
    def resolve(self,r):
        need(type(r)is dict and set(r)=={'size','sha256'},'OBJECT_REF');sha(r['sha256']);p=self.objects/r['sha256'];need(hash_file(p)==r,'CAS_OBJECT_CHANGED');return p
    def store_bytes(self,b):
        p=self.temporary();publish(p,b);return self.store(p)
    def capture_tree(self,source,*,member_cap=1000000,file_cap=2**30,total_cap=256*2**30,runtime_sockets=None):
        source=Path(source);need(source.resolve()==source and source.is_absolute(),'CANONICAL_CAPTURE_ROOT')
        policy={} if runtime_sockets is None else runtime_sockets
        need(type(policy)is dict,'CAPTURE_RUNTIME_SOCKET_POLICY')
        for path,identity in policy.items():
            need(type(path)is str and Path(path).is_absolute() and Path(path).resolve()==Path(path)
                 and type(identity)is tuple and len(identity)==6 and all(type(v)is int for v in identity),'CAPTURE_RUNTIME_SOCKET_BINDING')
        skipped=[]
        rootfd=os.open(source,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);rootstat=os.fstat(rootfd);before_path=stamp(source.lstat())
        temp=self.temporary();counts={'entries':0,'regular_bytes':0,'regular':0,'directories':0,'symbolic':0,'hardlinks':0};seen={}
        def info(name,s):
            t=tarfile.TarInfo(name);t.mode=stat.S_IMODE(s.st_mode);t.uid=s.st_uid;t.gid=s.st_gid;t.mtime=s.st_mtime_ns//10**9;t.pax_headers={'mtime':str(Decimal(s.st_mtime_ns)/Decimal(10**9))};return t
        def walk(fd,prefix,tar):
            ds=os.fstat(fd)
            for name in sorted(os.listdir(fd)):
                parts(name);s=os.stat(name,dir_fd=fd,follow_symlinks=False);rel=prefix+name;counts['entries']+=1;need(counts['entries']<=member_cap,'CAPTURE_MEMBER_CAP');t=info(rel,s)
                if stat.S_ISDIR(s.st_mode):
                    child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                    try:
                        need(stamp(s)==stamp(os.fstat(child)),'CAPTURE_DIRECTORY_CHANGED');t.type=tarfile.DIRTYPE;tar.addfile(t);counts['directories']+=1;walk(child,rel+'/',tar)
                    finally:os.close(child)
                elif stat.S_ISLNK(s.st_mode):
                    t.type=tarfile.SYMTYPE;t.linkname=os.readlink(name,dir_fd=fd);need('\x00'not in t.linkname,'CAPTURE_LINK_NUL');tar.addfile(t);counts['symbolic']+=1
                elif stat.S_ISREG(s.st_mode):
                    key=(s.st_dev,s.st_ino);child=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
                    try:
                        need(stamp(s)==stamp(os.fstat(child)),'CAPTURE_FILE_CHANGED')
                        if key in seen:t.type=tarfile.LNKTYPE;t.linkname=seen[key];tar.addfile(t);counts['hardlinks']+=1
                        else:
                            need(s.st_size<=file_cap and counts['regular_bytes']+s.st_size<=total_cap,'CAPTURE_BYTE_CAP');t.type=tarfile.REGTYPE;t.size=s.st_size
                            with os.fdopen(os.dup(child),'rb') as inp:tar.addfile(t,inp)
                            seen[key]=rel;counts['regular_bytes']+=s.st_size;counts['regular']+=1
                        need(stamp(s)==stamp(os.fstat(child)),'CAPTURE_FILE_CHANGED')
                    finally:os.close(child)
                elif stat.S_ISSOCK(s.st_mode):
                    # No wildcard or generic special-file exclusion. Only exact
                    # host-registered IPC endpoints can be omitted from disk
                    # bytes; their physical identity is retained in the object.
                    identity=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_mtime_ns)
                    need(policy.get(str(source/rel))==identity,'CAPTURE_SPECIAL_FILE_REQUIRES_EXPLICIT_POLICY')
                    skipped.append({'registered_runtime_socket':rel,'identity':list(identity)})
                else:need(False,'CAPTURE_SPECIAL_FILE_REQUIRES_EXPLICIT_POLICY')
                need(stamp(s)==stamp(os.stat(name,dir_fd=fd,follow_symlinks=False)),'CAPTURE_PATH_CHANGED')
            need(stamp(ds)==stamp(os.fstat(fd)),'CAPTURE_DIRECTORY_CHANGED')
        try:
            with temp.open('xb') as out:
                os.chmod(temp,0o600)
                with gzip.GzipFile(fileobj=out,mode='wb',mtime=0,filename='') as gz:
                    with tarfile.open(fileobj=gz,mode='w|',format=tarfile.PAX_FORMAT) as tar:walk(rootfd,'',tar)
                out.flush();os.fsync(out.fileno())
            need(stamp(rootstat)==stamp(os.fstat(rootfd)) and before_path==stamp(source.lstat()),'CAPTURE_ROOT_CHANGED')
            result={'archive':self.store(temp),'root_metadata':{'mode':stat.S_IMODE(rootstat.st_mode),'mtime_ns':rootstat.st_mtime_ns},'census':counts}
            if skipped:result['runtime_socket_exclusions']=skipped
            return result
        finally:os.close(rootfd)
    def verify_snapshot(self,ref,*,expected=None):
        raw=self.resolve(ref).read_bytes();d=strict(raw)
        fields={'schema','trajectory','generation','target_tokens','actual_search_tokens','shortfall','reserved','unresolved','active_operations','ledger_frontier','pins','roles','shared','durable_ledger','parent','restore','automatic_next_stage'}
        need(type(d)is dict and set(d)==fields and d['schema']=='count14-agensh-snapshot-v1','SNAPSHOT_SCHEMA')
        need(type(d['trajectory'])is str and 0<len(d['trajectory'])<=512,'SNAPSHOT_TRAJECTORY')
        for k in ('generation','target_tokens','actual_search_tokens','shortfall','reserved','unresolved','active_operations','ledger_frontier'):integer(d[k],'SNAPSHOT_'+k.upper())
        from r16_natural_contract import natural
        nm=natural(d)
        need(d['generation']>0 and (d['target_tokens']>0 or nm is not None) and d['actual_search_tokens']+d['shortfall']==d['target_tokens'],'SNAPSHOT_BUDGET')
        need(d['reserved']==d['unresolved']==d['active_operations']==0,'SNAPSHOT_NOT_QUIESCENT')
        need(type(d['pins'])is dict and {'manifest','protocol','source','task_description'}<=set(d['pins']),'SNAPSHOT_PINS')
        for value in d['pins'].values():sha(value)
        need(type(d['roles'])is dict and 1<=len(d['roles'])<=16 and set(d['roles'])=={f'worker-{i:02d}'for i in range(len(d['roles']))},'SNAPSHOT_ROLE_ROSTER')
        need(type(d['shared'])is dict and set(d['shared'])==SHARED,'SNAPSHOT_SHARED_ROSTER')
        for role in d['roles'].values():
            need(type(role)is dict and set(role)=={'workspace','session'},'SNAPSHOT_ROLE_COMPONENTS')
            for obj in role.values():self.resolve(obj['archive'])
        for obj in d['shared'].values():self.resolve(obj['archive'])
        self.resolve(d['durable_ledger'])
        if 'native_writer_fence' in d['pins']:
            from native_writer_fence import verify_sealed_writer_proof
            verify_sealed_writer_proof(self,d)
        need(d['restore']=={'level':'L1','cold_continuation_supported':False} and d['restore']['cold_continuation_supported']is False and d['automatic_next_stage']is False,'SNAPSHOT_CAPABILITIES')
        if d['parent']is not None:self.resolve(d['parent'])
        if expected is not None:
            mapping={'trajectory':'trajectory','generation':'generation','target_tokens':'target','actual_search_tokens':'actual','shortfall':'shortfall'}
            need(all(d[k]==expected[v]for k,v in mapping.items()) and d['pins']['manifest']==expected['manifest_sha256'] and set(d['roles'])==set(expected['roles']),'SNAPSHOT_EXPECTED_IDENTITY')
        return d

def reference_path(cas,frontier):
    return cas.refs/f"{digest(frontier['trajectory'])}-g{frontier['generation']}-b{frontier['target']}.json"

def finish_published_capture(cas,ledger,trajectory):
    """Recover commit only, not search or a second capture, after owner loss.

    A missing/partial staging object does not authorize this. Only the original
    atomically published same-identity reference plus every immutable object and
    the original CAPTURING frontier permits completing the durable ledger side.
    """
    f=ledger.frontier(trajectory);need(f['state']in ('CAPTURING','COMMITTED_PARKED'),'RECOVERY_NOT_CAPTURING')
    path=reference_path(cas,f);ref=strict(path.read_bytes());cas.verify_snapshot(ref,expected=f)
    if f['state']=='COMMITTED_PARKED':
        row=ledger.db.execute('SELECT ref_sha FROM snapshots WHERE trajectory=? AND generation=?',(trajectory,f['generation'])).fetchone()
        need(row is not None and row[0]==ref['sha256'],'PUBLISHED_COMMIT_CONFLICT')
    else:ledger.commit(trajectory,f['generation'],ref['sha256'])
    return ref

def capture(cas,ledger,trajectory,*,roles,shared,pins,parent=None,publication_guard=None):
    need(publication_guard is None or callable(publication_guard),'CAPTURE_TRUSTED_PUBLICATION_GUARD')
    # Fail before begin_capture/CAS writes: a generic callable, plain cut or
    # absent registry cannot discharge retained original kernel writer custody.
    from native_cli_callback_custody import registered_custody
    port=registered_custody(ledger,trajectory)
    if port is not None:
        from native_service_cut import NativeServiceCut
        cut=getattr(publication_guard,'__self__',None)
        need(type(cut)is NativeServiceCut and getattr(publication_guard,'__func__',None)is NativeServiceCut.guard
             and cut.ledger is ledger and cut.cas is cas and cut.t==trajectory,
             'CAPTURE_CALLBACK_CUSTODY_ORIGINAL_SERVICE_GUARD_REQUIRED')
        port.verify_capture(cut,roles,pins)
    f=ledger.frontier(trajectory)
    need(set(roles)==set(f['roles']) and all(set(r)=={'workspace','session'} for r in roles.values()),'CAPTURE_ALL_REQUIRED_ROLES')
    need(set(shared)==SHARED,'CAPTURE_ALL_SHARED_OBJECTS')
    for v in pins.values():sha(v)
    need(pins.get('manifest')==f['manifest_sha256'] and {'manifest','protocol','source','task_description'}<=pins.keys(),'SNAPSHOT_PINS')
    f=ledger.begin_capture(trajectory)
    r={role:{kind:cas.capture_tree(source) for kind,source in paths.items()} for role,paths in sorted(roles.items())}
    s={kind:cas.capture_tree(source) for kind,source in sorted(shared.items())}
    backup=cas.temporary();ledger.backup(backup);durable=cas.store(backup)
    d={'schema':'count14-agensh-snapshot-v1','trajectory':trajectory,'generation':f['generation'],'target_tokens':f['target'],'actual_search_tokens':f['actual'],'shortfall':f['shortfall'],'reserved':f['reserved'],'unresolved':f['unresolved'],'active_operations':f['active_operations'],'ledger_frontier':f['sequence'],'pins':pins,'roles':r,'shared':s,'durable_ledger':durable,'parent':parent,'restore':{'level':'L1','cold_continuation_supported':False},'automatic_next_stage':False}
    if publication_guard is not None:
        original=digest(d);publication_guard(d);need(digest(d)==original,'CAPTURE_GUARD_MUST_NOT_MUTATE_SNAPSHOT')
    ref=cas.store_bytes(wire(d));cas.verify_snapshot(ref,expected=f)
    # This no-clobber reference, not staging existence, is the commit point.
    publish(reference_path(cas,f),wire(ref))
    ledger.commit(trajectory,f['generation'],ref['sha256']);return ref
