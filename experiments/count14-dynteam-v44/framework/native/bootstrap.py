"""Trusted source-only bootstrap. Run on authorised inputs, never by workers.

The baseline-approved exact member index is pinned before reading an archive.
No task reformulation, existing workspace import, evaluator mount or code exec.
Only Git itself runs on synthetic/approved files with hooks/config disabled.
"""
from pathlib import Path,PurePosixPath
from decimal import Decimal
import hashlib,io,os,posixpath,shutil,stat,subprocess,tarfile,uuid
from common import need,parts,sha,strict,digest,wire,hash_file,publish,stamp,Refused
FORBIDDEN=frozenset(('.git','evaluator-private','private-context.json','count14_candidates','pocs','model-output','trajectory-history'))
KINDS=frozenset(('file','directory','symlink','hardlink'))

def validate_input(index,expected_index_sha):
    need(digest(index)==sha(expected_index_sha),'BASELINE_INPUT_INDEX_PIN')
    need(type(index)is dict and set(index)=={'schema','artifact_kind','source_sha256','task_description_sha256','members'},'INPUT_INDEX_FIELDS')
    need(index['schema']=='count14-approved-source-input-v1' and index['artifact_kind']=='SOURCE_ONLY_NO_EVALUATOR_HISTORY_OR_CANDIDATES','SOURCE_ONLY_ABI')
    sha(index['source_sha256']);sha(index['task_description_sha256']);need(type(index['members'])is list and len(index['members'])<=1000000,'INPUT_MEMBER_CAP')
    seen={}
    for r in index['members']:
        need(type(r)is dict and {'path','kind','mode','mtime_ns'}<=r.keys(),'INPUT_MEMBER_FIELDS');p=parts(r['path']);need(not FORBIDDEN.intersection(p),'PRIVATE_OR_HISTORY_INPUT_FORBIDDEN')
        need(r['path']not in seen,'DUPLICATE_INPUT_PATH');need(r['kind']in KINDS,'INPUT_MEMBER_KIND')
        need(type(r['mode'])is int and 0<=r['mode']<=0o777,'INPUT_UNSAFE_MODE');need(type(r['mtime_ns'])is int and 0<=r['mtime_ns']<=2**63-1,'INPUT_MTIME')
        fields={'path','kind','mode','mtime_ns'}
        if r['kind']=='file':fields|={'size','sha256'};sha(r['sha256']);need(type(r['size'])is int and 0<=r['size']<=2**30,'INPUT_FILE_SIZE')
        if r['kind']in ('symlink','hardlink'):
            fields|={'target'};need(type(r['target'])is str and '\x00'not in r['target'] and '\\'not in r['target'],'INPUT_LINK')
            resolved=posixpath.normpath(posixpath.join(posixpath.dirname(r['path']),r['target']) if r['kind']=='symlink' else r['target'])
            parts(resolved)
        need(set(r)==fields,'INPUT_MEMBER_FIELDS');seen[r['path']]=r
    for p,r in seen.items():
        parents=PurePosixPath(p).parents
        for q in parents:
            if str(q)in seen:need(seen[str(q)]['kind']=='directory','INPUT_PARENT_NOT_DIRECTORY')
        if r['kind']in ('symlink','hardlink'):
            target=posixpath.normpath(posixpath.join(posixpath.dirname(p),r['target']) if r['kind']=='symlink' else r['target'])
            need(target in seen and seen[target]['kind']in ('file','directory'),'INPUT_LINK_NOT_APPROVED_TARGET')
            if r['kind']=='hardlink':need(seen[target]['kind']=='file','INPUT_HARDLINK_REGULAR')
    return seen

def extract_source(archive,index,index_sha,destination):
    members=validate_input(index,index_sha);archive=Path(archive);need(hash_file(archive)['sha256']==index['source_sha256'],'SOURCE_BUNDLE_PIN')
    destination=Path(destination);need(destination.is_absolute() and destination.resolve()==destination and not destination.exists(),'ABSENT_SOURCE_DESTINATION');destination.mkdir(mode=0o700)
    seen=set();links=[];directories=[];total=0
    with tarfile.open(archive,'r|*',errorlevel=2) as t:
        for m in t:
            t.members.clear();parts(m.name);need(m.name in members and m.name not in seen,'ARCHIVE_NOT_EXACT_APPROVED_INPUT');seen.add(m.name);r=members[m.name]
            kind='file'if m.isreg() else 'directory'if m.isdir() else 'symlink'if m.issym() else 'hardlink'if m.islnk() else None
            need(kind==r['kind'] and m.mode==r['mode'] and int(Decimal(m.pax_headers.get("mtime",str(m.mtime)))*10**9)==r['mtime_ns'],'ARCHIVE_METADATA_PIN')
            p=destination.joinpath(*parts(m.name));p.parent.mkdir(parents=True,exist_ok=True)
            if kind=='directory':p.mkdir(exist_ok=True);directories.append((p,r));continue
            if kind in ('symlink','hardlink'):need(m.linkname==r['target'],'ARCHIVE_LINK_PIN');links.append((p,r));continue
            need(m.size==r['size'] and total+m.size<=64*2**30,'SOURCE_TOTAL_SIZE');h=hashlib.sha256();n=0
            with t.extractfile(m) as inp,p.open('xb') as out:
                for b in iter(lambda:inp.read(1024*1024),b''):n+=len(b);need(n<=m.size,'SOURCE_MEMBER_GREW');h.update(b);out.write(b)
                out.flush();os.fsync(out.fileno())
            need(n==r['size'] and h.hexdigest()==r['sha256'],'SOURCE_MEMBER_PIN');total+=n;p.chmod(r['mode']);os.utime(p,ns=(r['mtime_ns'],r['mtime_ns']))
    need(seen==set(members),'SOURCE_MEMBER_MISSING')
    for p,r in links:
        if r['kind']=='symlink':p.symlink_to(r['target']);os.utime(p,ns=(r['mtime_ns'],r['mtime_ns']),follow_symlinks=False)
        else:os.link(destination.joinpath(*parts(r['target'])),p,follow_symlinks=False)
    for p,r in sorted(directories,key=lambda x:len(x[0].parts),reverse=True):p.chmod(r['mode']);os.utime(p,ns=(r['mtime_ns'],r['mtime_ns']))
    need(hash_file(archive)['sha256']==index['source_sha256'],'SOURCE_BUNDLE_CHANGED')
    return {'source_sha256':index['source_sha256'],'approved_input_index_sha256':index_sha,'file_count':sum(r['kind']=='file' for r in members.values()),'member_count':len(members),'regular_bytes':total}

def git(args,*,cwd,extra_env=None):
    env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':str(Path(cwd).parent),'LANG':'C','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_TERMINAL_PROMPT':'0','GIT_AUTHOR_NAME':'Agensh bootstrap','GIT_AUTHOR_EMAIL':'bootstrap@invalid','GIT_COMMITTER_NAME':'Agensh bootstrap','GIT_COMMITTER_EMAIL':'bootstrap@invalid','GIT_AUTHOR_DATE':'2000-01-01T00:00:00Z','GIT_COMMITTER_DATE':'2000-01-01T00:00:00Z'}
    if extra_env:env.update(extra_env)
    cmd=['git','-c','core.hooksPath=/dev/null','-c','protocol.file.allow=always','-c','protocol.ext.allow=never','-c','core.fsmonitor=false',*args]
    r=subprocess.run(cmd,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
    need(r.returncode==0,'BOOTSTRAP_GIT_FAILED');return r.stdout

def bootstrap(archive,description,index,index_sha,destination,roles):
    need(type(roles)is list and 1<=len(roles)<=16 and roles==[f'worker-{i:02d}' for i in range(len(roles))],'BOOTSTRAP_ROLES')
    destination=Path(destination);need(destination.is_absolute() and destination.resolve()==destination and not destination.exists(),'ABSENT_BOOTSTRAP_ROOT');destination.mkdir(mode=0o700)
    source=destination/'source';receipt=extract_source(archive,index,index_sha,source)
    need(hash_file(description)['sha256']==index['task_description_sha256'],'TASK_DESCRIPTION_PIN')
    # Private file copied byte-for-byte, no prompt concatenation or rewriting.
    task=destination/'task-description.bin';shutil.copyfile(description,task);task.chmod(0o400);need(hash_file(task)['sha256']==index['task_description_sha256'],'TASK_DESCRIPTION_COPY_PIN')
    git(['init','--template=','--initial-branch=main'],cwd=source);git(['add','--all','--force','--','.'],cwd=source);git(['commit','--allow-empty','-m','approved immutable bootstrap'],cwd=source)
    commit=git(['rev-parse','HEAD'],cwd=source).decode().strip();tree=git(['rev-parse','HEAD^{tree}'],cwd=source).decode().strip();git(['tag','count14-bootstrap'],cwd=source)
    repo=destination/'bootstrap.git';git(['init','--bare','--template=',str(repo)],cwd=destination);git(['push',str(repo),'HEAD:refs/heads/main','refs/tags/count14-bootstrap'],cwd=source)
    for role in roles:
        worker=destination/'workers'/role;worker.parent.mkdir(parents=True,exist_ok=True)
        # cp -a preserves within-tree links/mode/mtime; no writable inode is shared
        # between workers, unlike hardlink clones. Reflink is only a copy option.
        r=subprocess.run(['cp','-a','--reflink=auto','--',str(source),str(worker)],stdout=subprocess.PIPE,stderr=subprocess.PIPE);need(r.returncode==0,'WORKER_VIEW_COPY_FAILED')
        need(git(['rev-parse','HEAD'],cwd=worker).decode().strip()==commit,'WORKER_BOOTSTRAP_COMMIT')
        for name,entry in validate_input(index,index_sha).items():
            if entry['kind']=='file':
                p=worker.joinpath(*parts(name));need(hash_file(p)=={'size':entry['size'],'sha256':entry['sha256']},'WORKER_INITIAL_SOURCE_PIN');need(p.stat().st_ino!=source.joinpath(*parts(name)).stat().st_ino,'NO_WRITABLE_WORKER_HARDLINK_CLONE')
    receipt.update(schema='count14-agensh-bootstrap-v1',task_description_sha256=index['task_description_sha256'],bootstrap_commit=commit,bootstrap_tree=tree,roles=list(roles),task_bytes_unchanged=True,private_evaluator_or_history_imported=False,gitea_published=False)
    publish(destination/'bootstrap-receipt.json',wire(receipt));return receipt
