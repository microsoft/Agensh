"""Trusted content-blind candidate collector from committed immutable snapshots.

Original FINAL predicate/caps/inert header parser are reused. The one declared
adapter mapping is count14_candidates/ -> pocs/. No live worktree, model output,
Git history search, scoring, or content interpretation is performed here.
The returned manifest with private provenance is itself private; publish only
its hash/counts. This is not the native FINAL executor or its scope authority.
"""
from pathlib import Path
from decimal import Decimal,InvalidOperation
import collections,gzip,hashlib,os,re,tarfile
from common import need,integer,sha,parts,wire,publish,hash_file,digest
from snapshot import CAS
from native_inert_archive import Header,special_kind,Stop as HeaderStop
from native_candidate_policy import candidate,MAX_FILE,MAX_TOTAL


def mapped_parts(path):
    p=parts(path.rstrip('/'))
    if p[0]=='count14_candidates':p=('pocs',*p[1:])
    return p


def collect(cas,snapshot_ref,destination,*,expected,member_cap,git_exports=(),registered_refs=()):
    """git_exports are trusted, frozen native git-archive objects, never live refs.

    A git export receipt binds the exact preregistered ref and commit object.
    Native publication/backup must create these under the same capture fence;
    this function does not turn arbitrary extra archives into snapshot inputs.
    """
    integer(member_cap,'BOUND_NATIVE_MEMBER_CAP',1);need(member_cap<=10_000_000,'BOUND_NATIVE_MEMBER_CAP')
    d=cas.verify_snapshot(snapshot_ref,expected=expected)
    destination=Path(destination);need(destination.is_absolute() and destination.resolve()==destination and not destination.exists(),'ABSENT_PRIVATE_COLLECTION');destination.mkdir(mode=0o700)
    rows={};counts=collections.Counter();total=0;sources=[]
    for role,component in sorted(d['roles'].items()):sources.append({'kind':'worker','origin':role,'archive':component['workspace']['archive']})
    if git_exports or registered_refs:
        need(d['pins'].get('gitea_exports')==digest({'registered_refs':list(registered_refs),'exports':list(git_exports)}),'GIT_EXPORTS_NOT_PINNED_IN_SNAPSHOT')
    seen_refs=set()
    for export in git_exports:
        need(type(export)is dict and set(export)=={'ref','commit','archive'},'GIT_EXPORT_FIELDS')
        need(export['ref']in registered_refs and export['ref']not in seen_refs,'GIT_REF_NOT_PREREGISTERED_OR_DUPLICATE')
        need(type(export['commit'])is str and re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}',export['commit']),'GIT_COMMIT_PIN')
        seen_refs.add(export['ref']);sources.append({'kind':'gitea_ref','origin':export['ref'],'commit':export['commit'],'archive':export['archive']})
    need(seen_refs==set(registered_refs),'ALL_REGISTERED_REFS_REQUIRED')
    for source in sources:
        archive=cas.resolve(source['archive']);seen=set();entries=0
        try:
            # A separate complete gzip pass verifies EOF/CRC even after tar EOF.
            with gzip.open(archive,'rb')as stream:
                for _ in iter(lambda:stream.read(1024*1024),b''):pass
            with tarfile.open(archive,'r|gz',tarinfo=Header,errorlevel=2)as tar:
                for member in tar:
                    entries+=1;tar.members.clear();need(entries<=member_cap,'CANDIDATE_MEMBER_CAP')
                    kind=special_kind(member)
                    if kind is not None:counts['skipped_'+kind]+=1;continue
                    if member.issym():counts['skipped_symbolic']+=1;continue
                    p=mapped_parts(member.name)
                    if member.isdir()or not candidate(p):continue
                    need(member.type in (tarfile.REGTYPE,tarfile.AREGTYPE),'CANDIDATE_ORDINARY_ONLY')
                    relative='/'.join(p);need(relative not in seen,'CANDIDATE_DUPLICATE_MEMBER');seen.add(relative)
                    need(0<=member.size<=MAX_FILE and total+member.size<=MAX_TOTAL,'NATIVE_CANDIDATE_BYTE_CAP')
                    try:
                        # PAX decimal avoids float truncation across K branches.
                        mt=Decimal(member.pax_headers.get('mtime',str(member.mtime)));need(mt.is_finite(),'CANDIDATE_MTIME');mtime=int(mt*10**9)
                    except (InvalidOperation,ValueError,OverflowError):need(False,'CANDIDATE_MTIME')
                    temporary=cas.temporary();n=0;h=hashlib.sha256()
                    with tar.extractfile(member)as inp,temporary.open('xb')as out:
                        for block in iter(lambda:inp.read(1024*1024),b''):
                            n+=len(block);need(n<=member.size,'CANDIDATE_MEMBER_GREW');h.update(block);out.write(block)
                        out.flush();os.fsync(out.fileno())
                    need(n==member.size,'CANDIDATE_TRUNCATED');total+=n;obj=cas.store(temporary);need(obj=={'size':n,'sha256':h.hexdigest()},'CANDIDATE_SNAPSHOT_SHA')
                    origin={k:v for k,v in source.items()if k!='archive'};origin.update(original_path=member.name,native_path=relative,mtime_ns=mtime,archive_sha256=source['archive']['sha256'])
                    row=rows.setdefault(obj['sha256'],{'object':obj,'origins':[]})
                    if origin not in row['origins']:row['origins'].append(origin)
                    counts['candidate_occurrences']+=1
        except (tarfile.TarError,HeaderStop,EOFError):need(False,'NATIVE_CANDIDATE_ARCHIVE_REFUSED')
        need(hash_file(archive)==source['archive'],'CANDIDATE_ARCHIVE_CHANGED')
    result=[]
    for key,row in sorted(rows.items()):
        row['origins'].sort(key=lambda r:(r['kind'],r['origin'],r['original_path'],r['mtime_ns']));row['mtime_ns']=max(x['mtime_ns']for x in row['origins']);result.append(row)
    manifest={'schema':'count14-agensh-candidates-v1','snapshot_sha256':snapshot_ref['sha256'],'trajectory':d['trajectory'],'generation':d['generation'],'pins':d['pins'],'member_cap':member_cap,'no_live_sources':True,'source_kind':'frozen-workers-and-preregistered-gitea-exports','native_export_mapping':'count14_candidates->pocs','candidates':result,'unique_candidates':len(result),'imported_bytes':total,'counts':dict(counts)}
    raw=wire(manifest);publish(destination/'candidate-manifest.json',raw,mode=0o400)
    return {'manifest':manifest,'receipt':{'schema':'count14-agensh-candidate-receipt-v1','manifest_sha256':hashlib.sha256(raw).hexdigest(),'unique_candidates':len(result),'candidate_occurrences':counts['candidate_occurrences'],'snapshot_sha256':snapshot_ref['sha256'],'native_final_executed':False}}
