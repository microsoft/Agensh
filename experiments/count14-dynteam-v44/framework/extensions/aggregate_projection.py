"""Runtime-only opaque materialization from the sealed16M CAS, never live roots.

Private bodies remain private. Developer/tests use only synthetic fixtures.
The worker receives neither physical DBs nor user/session/API tokens. Gitea
projection reuses the already-qualified frozen recollector's safe Git parser.
"""
from pathlib import Path,PurePosixPath
from decimal import Decimal
import gzip,hashlib,importlib.util,sys,io,json,os,shutil,sqlite3,stat,subprocess,tarfile,time
from common import need,hash_file,wire,publish,digest,parts
from native_inert_archive import Header,special_kind
MAX_TREE=256*2**30;MAX_MEMBER=2**30;MAX_ENTRIES=1_000_000

def unpack(archive,ref,dest):
 """Nofollow tar materializer. Preserve original nanosecond mtime, no devices."""
 archive=Path(archive);dest=Path(dest);need(hash_file(archive)==ref,'AGGREGATE_READONLY_ARCHIVE_PIN')
 dest.mkdir(mode=0o755,parents=True,exist_ok=False);seen={};pending=[];n=0;total=0
 def path(name):
  ps=parts(name);p=dest.joinpath(*ps)
  for parent in p.parents:
   if parent==dest:break
   need(not parent.is_symlink(),'AGGREGATE_ARCHIVE_SYMLINK_PARENT')
  return p
 with tarfile.open(archive,'r|gz',tarinfo=Header,errorlevel=2)as tar:
  for m in tar:
   n+=1;tar.members.clear();need(n<=MAX_ENTRIES,'AGGREGATE_TREE_MEMBER_CAP')
   name=m.name.rstrip('/');p=path(name);need(name not in seen,'AGGREGATE_TREE_DUPLICATE_PATH');seen[name]=m.type
   need(special_kind(m)in(None,'hardlink'),'AGGREGATE_TREE_NO_SPECIAL')
   p.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
   if m.isdir():p.mkdir(mode=0o755,exist_ok=True)
   elif m.issym():pending.append((p,'symbolic',m.linkname,m))
   elif m.islnk():pending.append((p,'hard',m.linkname,m))
   else:
    need(m.type in(tarfile.REGTYPE,tarfile.AREGTYPE)and m.size<=MAX_MEMBER,'AGGREGATE_TREE_REGULAR_FILE_CAP')
    total+=m.size;need(total<=MAX_TREE,'AGGREGATE_TREE_TOTAL_CAP')
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,(0o555 if m.mode&0o111 else 0o444));count=0
    try:
     with os.fdopen(fd,'wb',closefd=False)as out,tar.extractfile(m)as inp:
      for b in iter(lambda:inp.read(1024*1024),b''):count+=len(b);need(count<=m.size,'AGGREGATE_TREE_GREW');out.write(b)
    finally:os.close(fd)
    need(count==m.size,'AGGREGATE_TREE_TRUNCATED');mt=int(Decimal(m.pax_headers.get('mtime',str(m.mtime)))*10**9);os.utime(p,ns=(mt,mt),follow_symlinks=False)
 for p,kind,link,m in pending:
  if kind=='hard':
   q=path(link);need(q.is_file()and not q.is_symlink(),'AGGREGATE_HARDLINK_REGULAR_TARGET');os.link(q,p,follow_symlinks=False)
  else:
   # Links can point only within their own frozen tree. Never expose a host path.
   need(not PurePosixPath(link).is_absolute(),'AGGREGATE_NO_ABSOLUTE_HOST_LINK')
   need((p.parent/link).resolve().is_relative_to(dest.resolve()),'AGGREGATE_LINK_ESCAPES_FROZEN_TREE');os.symlink(link,p)
 need(hash_file(archive)==ref,'AGGREGATE_READONLY_ARCHIVE_CHANGED')
 return {'files':sum(x in(tarfile.REGTYPE,tarfile.AREGTYPE)for x in seen.values()),'entries':n,'regular_bytes':total,'archive':ref}

def physical_roots(cas,component,home):
 """Only sealed physical archives; restore to OWN private clone, never originals."""
 ref=component['archive'];archive=cas.resolve(ref);outer=Path(home)/'physical-outer';unpack(archive,ref,outer)
 meta=json.loads((outer/'PHYSICAL_ROOTS.json').read_bytes())
 need(meta['schema']=='agensh-whole-team-physical-backup-v1'and meta['whole_team_frozen'] is True,'AGGREGATE_FROZEN_PHYSICAL_SOURCE')
 roots=[];expected={'PHYSICAL_ROOTS.json'}
 for row in meta['roots']:
  name=row['service']+'--'+row['name']+'.tar.gz';need('/'not in name and name not in expected,'AGGREGATE_PHYSICAL_ROOT_NAME');expected.add(name)
  p=outer/name;ref=row['object']['archive'];d=Path(home)/('root-'+digest(row)[:16]);unpack(p,ref,d)
  roots.append((row['service'],row['name'],d))
 need({p.name for p in outer.iterdir()}==expected,'AGGREGATE_PHYSICAL_ALL_ROOTS')
 return roots

def load_recollector(path,expected_sha):
 p=Path(path);need(hash_file(p)['sha256']==expected_sha,'AGGREGATE_FROZEN_RECOLLECTOR_PIN')
 spec=importlib.util.spec_from_file_location('late_aggregate_original_recollector',p);m=importlib.util.module_from_spec(spec)
 before=list(sys.path)
 try:spec.loader.exec_module(m);m.check_rule()
 finally:sys.path[:]=before
 return m

def gitea(cas,snapshot,home,view,recollector):
 ref=snapshot['shared']['gitea_database']['archive'];private=Path(home)/'gitea-private';private.mkdir(mode=0o700)
 frozen=recollector.FrozenGitea(cas.resolve(ref),ref,private,MAX_ENTRIES);frozen.unpack();repos,prs=frozen.metadata()
 out=Path(view)/'gitea';out.mkdir(mode=0o755);identities=[]
 for row in repos:
  matches=[k for k in frozen.roots if tuple(k.split('/')[-2:])==(row['owner_lower'],row['lower_name']+'.git')]
  need(len(matches)==1,'AGGREGATE_ALL_GITEA_REPOSITORIES')
  dest=out/(str(row['id'])+'-'+row['owner_lower']+'-'+row['lower_name']);dest.mkdir(mode=0o755)
  git=recollector.FrozenGit(frozen.roots[matches[0]],row['object_format_name'])
  # Recreated safe config, no original config/hooks/credentials/alternates.
  shutil.copytree(git.root,dest/'repository.git',symlinks=False)
  if not row['is_empty']:
   commit=git.commit('refs/heads/'+row['default_branch'],'AGGREGATE_DEFAULT_REF')
   archive=private/('tree-'+str(row['id'])+'.tar.gz')
   with archive.open('xb')as fd:
    child=subprocess.run(git.command+['archive','--format=tar.gz',commit],stdout=fd,stderr=subprocess.DEVNULL,env=recollector.GIT_ENV)
   need(child.returncode==0,'AGGREGATE_GIT_READONLY_TREE_EXPORT');unpack(archive,hash_file(archive),dest/'tree')
  identities.append({'repository_id':row['id'],'path':str(dest.relative_to(Path(view))), 'default_branch':row['default_branch'],'all_refs_and_objects':True})
 c=sqlite3.connect(':memory:');c.deserialize(frozen.dbraw);c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON')
 try:
  # Whitelisted discussion fields only; not users/access_token/sessions/config.
  issues=[dict(r)for r in c.execute('SELECT id,repo_id,"index",title,content FROM issue ORDER BY id')]
  comments=[dict(r)for r in c.execute('SELECT id,issue_id,type,content FROM comment ORDER BY id')]
 finally:c.close()
 publish(out/'discussions.json',wire({'repositories':identities,'issues':issues,'comments':comments,'merged_pull_requests':prs}),mode=0o444)
 return {'repositories':len(repos),'issues':len(issues),'comments':len(comments),'archive':ref}

class MysqlDiscussionExport:
 """Read only Posts/Channels from a PRIVATE recovered copy using original image.
 Container has no network; skip grants only for this owned throwaway clone. Its
 data/temp/logs never enter the aggregate mount. No original config or password.
 """
 def __init__(self,docker,image):self.docker=list(docker);self.image=image
 def __call__(self,roots,home,destination):
  candidates=[]
  for service,name,root in roots:
   if service!='mattermost':
    for p in [root,*[x for x in root.iterdir()if x.is_dir()and not x.is_symlink()]]:
     if (p/'ibdata1').is_file():candidates.append(p)
  need(len(candidates)==1,'AGGREGATE_MYSQL_PRIVATE_DATA_ROOT')
  data=candidates[0]
  # Readonly extraction files are made writable only in this throwaway clone.
  for p in [data,*data.rglob('*')]:
   need(not p.is_symlink(),'AGGREGATE_MYSQL_NO_EXTERNAL_LINKS');p.chmod(0o700 if p.is_dir()else 0o600)
  name='ag-late-mm-'+digest(str(home))[:18]
  argv=self.docker+['run','-d','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
   '--user','0:0','--memory','2g','--pids-limit','256','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
   '--mount','type=bind,src='+str(data)+',dst=/var/lib/mysql','--entrypoint','mysqld',self.image,'--no-defaults','--user=root','--datadir=/var/lib/mysql','--socket=/tmp/late.sock','--pid-file=/tmp/late.pid',
   '--skip-networking','--skip-grant-tables','--mysqlx=0','--log-error=/tmp/mysql.err']
  started=False
  try:
   r=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL);need(r.returncode==0,'AGGREGATE_PRIVATE_MYSQL_START');started=True
   deadline=time.monotonic()+120
   base=self.docker+['exec',name,'mysql','--no-defaults','--protocol=socket','--socket=/tmp/late.sock','--user=root','--batch','--skip-column-names','--raw']
   while True:
    ping=subprocess.run(base+['-e','SELECT 1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    if ping.returncode==0:break
    need(time.monotonic()<deadline,'AGGREGATE_PRIVATE_MYSQL_RECOVERY_TIMEOUT');time.sleep(.25)
   # The runtime-created DB name is selected only by the two public table names.
   db=subprocess.run(base+['-e',"SELECT TABLE_SCHEMA FROM information_schema.tables WHERE TABLE_NAME IN ('Posts','Channels') GROUP BY TABLE_SCHEMA HAVING COUNT(*)=2"],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
   need(db.returncode==0,'AGGREGATE_MM_DATABASE_ENUMERATION');names=db.stdout.decode().splitlines();need(len(names)==1 and names[0].replace('_','').isalnum(),'AGGREGATE_MM_DATABASE_UNIQUE')
   sql="SELECT JSON_OBJECT('id',p.Id,'channel_id',p.ChannelId,'root_id',p.RootId,'create_at',p.CreateAt,'update_at',p.UpdateAt,'message',p.Message,'channel',c.Name,'channel_type',c.Type) FROM Posts p JOIN Channels c ON c.Id=p.ChannelId ORDER BY p.CreateAt,p.Id"
   with Path(destination).open('xb')as out:r=subprocess.run(base+[names[0],'-e',sql],stdout=out,stderr=subprocess.DEVNULL)
   need(r.returncode==0,'AGGREGATE_MM_DISCUSSION_EXPORT');Path(destination).chmod(0o444)
  finally:
   if started:
    r=subprocess.run(self.docker+['stop','--time','30',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    need(r.returncode==0,'AGGREGATE_PRIVATE_MYSQL_RETIRE')
  return {'source':'sealed-collaboration-physical-clone','file':hash_file(destination),'query':'Posts+Channels-public-discussion-fields-only'}

def project(cas,snapshot_ref,expected,home,*,recollector,mysql_export):
 snapshot=cas.verify_snapshot(snapshot_ref,expected=expected);need(snapshot['target_tokens']==16_000_000,'AGGREGATE_ONLY_SEALED16M')
 home=Path(home);home.mkdir(mode=0o700);view=home/'view';view.mkdir(mode=0o755)
 round_=view/'proposals'/'round-0001';round_.mkdir(mode=0o755,parents=True);workers={}
 for role,row in sorted(snapshot['roles'].items()):
  ref=row['workspace']['archive'];dest=round_/role;workers[role]=unpack(cas.resolve(ref),ref,dest)
  for name,target in [('progress.md','output/progress.md'),('pocs','output/pocs')]:
   if not (dest/name).exists()and(dest/target).exists():os.symlink(target,dest/name)
 # The prompt's /work/repo is a readonly view of the same original fixed source.
 first=round_/sorted(workers)[0]
 if (first/'repo').is_dir():os.symlink('proposals/round-0001/'+first.name+'/repo',view/'repo')
 else:os.symlink('proposals/round-0001/'+first.name,view/'repo')
 git=gitea(cas,snapshot,home,round_,recollector)
 private=home/'collaboration-private';private.mkdir(mode=0o700)
 roots=physical_roots(cas,snapshot['shared']['collaboration'],private)
 mm=mysql_export(roots,private,round_/'team-discussion.jsonl')
 (view/'output'/'pocs').mkdir(mode=0o755,parents=True);(view/'output'/'progress.md').touch(mode=0o444)
 receipt={'schema':'agensh-late-aggregate-readonly-view-v1','snapshot':snapshot_ref,'worker_roster':sorted(workers),'workers':workers,
  'gitea':git,'collaboration':mm,'sources':'sealed16M-only','view_has_no_physical_databases_or_credentials':True,'proposal_round':'round-0001'}
 publish(home/'PROJECTION.json',wire(receipt),mode=0o400)
 return view,receipt
