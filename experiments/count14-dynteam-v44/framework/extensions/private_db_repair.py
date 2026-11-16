"""Private physical-DB restore only; aggregate-visible unpack remains unchanged.

Only MySQL's conventional non-data socket symlink is OMITTED (never followed
or materialized). All other original archive guards remain bytecode-derived.
Existing completed sealed worker/Gitea view is verified/reused, not reprojected.
"""
from pathlib import Path,PurePosixPath
from types import FunctionType,MethodType
import ast,hashlib,inspect,json,os,tarfile,textwrap,threading,stat,sys
from common import need,digest,hash_file,wire,publish,parts
PROJECTION_SHA='9cec4260794691a4c47cd6a7c7bef6014a1cdde955fda029b09dd5c4e65dd552'
MANAGER_SHA='4e519788567abf58f59b335571e4142a408855c36a24c3f490d46360d4fefdf1'
SOCKET_TARGETS=frozenset(('/var/run/mysqld/mysqld.sock','/run/mysqld/mysqld.sock','/tmp/mysql.sock'))

def socket_link(m):
 return m.issym() and PurePosixPath(m.name).name in ('mysql.sock','mysqld.sock') and m.linkname in SOCKET_TARGETS and m.size==0

def private_unpack(module):
 original=module.unpack
 need(hash_file(Path(inspect.getsourcefile(original)))['sha256']==PROJECTION_SHA,'DB_REPAIR_ORIGINAL_UNPACK_PIN')
 tree=ast.parse(textwrap.dedent(inspect.getsource(original)));fn=tree.body[0];changed=0
 for n in ast.walk(fn):
  if isinstance(n,ast.If) and ast.unparse(n.test)=='m.issym()':
   need(len(n.body)==1 and ast.unparse(n.body[0]).startswith("pending.append((p, 'symbolic',"),'DB_REPAIR_ORIGINAL_SYMLINK_BRANCH')
   old=n.body;n.body=[ast.If(test=ast.parse('_socket(m)',mode='eval').body,body=ast.parse("need(not p.exists() and not p.is_symlink(),'DB_REPAIR_SOCKET_CANNOT_BE_DATA_PARENT');inert_names.add(m.name.rstrip('/'));inert.append(digest({'name':m.name,'target':m.linkname,'kind':'private-mysql-nondata-socket-link'}))").body,orelse=old)];changed+=1
 need(changed==1,'DB_REPAIR_ONE_PRIVATE_SYMLINK_CLASSIFIER')
 fn.body[1:1]=ast.parse('inert=[];inert_names=set()').body
 loops=[n for n in ast.walk(fn)if isinstance(n,ast.For)and ast.unparse(n.target)=='m'];need(len(loops)==1,'DB_REPAIR_ORIGINAL_ONE_TAR_LOOP')
 loops[0].body.insert(0,ast.parse("need(not any(m.name.rstrip('/').startswith(x+'/') for x in inert_names),'DB_REPAIR_NO_INERT_SOCKET_PARENT')").body[0])
 # Preserve original output fields; append public inert count/hash, no link text.
 ret=fn.body[-1];need(isinstance(ret,ast.Return) and isinstance(ret.value,ast.Dict),'DB_REPAIR_ORIGINAL_UNPACK_RETURN')
 ret.value.keys += [ast.Constant('inert_socket_links'),ast.Constant('inert_socket_metadata_sha256')]
 ret.value.values += [ast.parse('len(inert)',mode='eval').body,ast.parse('digest(inert)',mode='eval').body]
 ns=dict(original.__globals__);ns['_socket']=socket_link
 exec(compile(ast.fix_missing_locations(tree),str(Path(__file__))+':private-db-only-unpack','exec'),ns)
 return ns['unpack']

def verify_worker(module,archive,ref,dest):
 """Opaque byte comparison, no output/body/log. Original safe tar names only."""
 need(hash_file(archive)==ref and dest.is_dir() and not dest.is_symlink(),'DB_REPAIR_REUSED_WORKER_SOURCE_PIN')
 n=files=total=0;seen=set()
 with tarfile.open(archive,'r|gz',tarinfo=module.Header,errorlevel=2)as tar:
  for m in tar:
   n+=1;tar.members.clear();need(n<=module.MAX_ENTRIES,'DB_REPAIR_WORKER_ENTRY_CAP')
   name=m.name.rstrip('/');p=dest.joinpath(*parts(name));need(name not in seen,'DB_REPAIR_WORKER_DUPLICATE');seen.add(name)
   for parent in p.parents:
    if parent==dest:break
    need(not parent.is_symlink(),'DB_REPAIR_WORKER_NO_LINK_PARENT')
   need(module.special_kind(m) in (None,'hardlink'),'DB_REPAIR_WORKER_NO_SPECIAL')
   if m.isdir():need(p.is_dir() and not p.is_symlink(),'DB_REPAIR_REUSED_DIRECTORY')
   elif m.issym():
    need(not PurePosixPath(m.linkname).is_absolute() and (p.parent/m.linkname).resolve().is_relative_to(dest.resolve()),'DB_REPAIR_REUSED_LINK_GUARD')
    need(p.is_symlink() and os.readlink(p)==m.linkname,'DB_REPAIR_REUSED_SYMBOLIC_LINK')
   elif m.islnk():
    q=dest.joinpath(*parts(m.linkname));need(q.is_file() and not q.is_symlink() and p.is_file() and not p.is_symlink() and os.path.samefile(p,q),'DB_REPAIR_REUSED_HARDLINK')
   else:
    need(m.type in (tarfile.REGTYPE,tarfile.AREGTYPE) and m.size<=module.MAX_MEMBER,'DB_REPAIR_REUSED_REGULAR_CAP')
    st=p.lstat();need(stat.S_ISREG(st.st_mode) and st.st_size==m.size,'DB_REPAIR_REUSED_REGULAR_SIZE')
    total+=m.size;files+=1;need(total<=module.MAX_TREE,'DB_REPAIR_WORKER_TOTAL_CAP')
    a=hashlib.sha256();b=hashlib.sha256();count=0
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb')as disk,tar.extractfile(m)as source:
     for chunk in iter(lambda:source.read(1024*1024),b''):count+=len(chunk);a.update(chunk)
     for chunk in iter(lambda:disk.read(1024*1024),b''):b.update(chunk)
    need(count==m.size and a.digest()==b.digest(),'DB_REPAIR_REUSED_WORKER_OPAQUE_SHA')
 need(hash_file(archive)==ref,'DB_REPAIR_REUSED_ARCHIVE_CHANGED')
 return {'files':files,'entries':n,'regular_bytes':total,'archive':ref,'reused_and_opaque_verified':True}

def physical(module,cas,component,home):
 """Private-only new clone for failed partial roots; original partial retained."""
 home=Path(home);ref=component['archive'];archive=cas.resolve(ref);outer=home/'physical-outer'
 if not outer.exists():module.unpack(archive,ref,outer)
 else:
  # Outer is a simple opaque set of ordinary archives+metadata, not a DB tree.
  verify_worker(module,archive,ref,outer)
 meta=json.loads((outer/'PHYSICAL_ROOTS.json').read_bytes())
 need(meta['schema']=='agensh-whole-team-physical-backup-v1' and meta['whole_team_frozen'] is True,'AGGREGATE_FROZEN_PHYSICAL_SOURCE')
 expected={'PHYSICAL_ROOTS.json'};roots=[];inert=[];unpack_db=private_unpack(module)
 new=home/'private-db-socket-repair-v1';new.mkdir(mode=0o700)
 for row in meta['roots']:
  name=row['service']+'--'+row['name']+'.tar.gz';need('/'not in name and name not in expected,'AGGREGATE_PHYSICAL_ROOT_NAME');expected.add(name)
  pin=row['object']['archive'];p=outer/name;old=home/('root-'+digest(row)[:16])
  if row['service']=='backend-mysql':
   d=new/('root-'+digest(row)[:16]);receipt=unpack_db(p,pin,d);inert.append({'archive':pin,**{k:receipt[k]for k in ('inert_socket_links','inert_socket_metadata_sha256')}})
  elif old.exists():verify_worker(module,p,pin,old);d=old
  else:d=new/('root-'+digest(row)[:16]);module.unpack(p,pin,d)
  roots.append((row['service'],row['name'],d))
 need({p.name for p in outer.iterdir()}==expected,'AGGREGATE_PHYSICAL_ALL_ROOTS')
 publish(new/'PRIVATE_RESTORE_RECEIPT.json',wire({'schema':'private-mysql-inert-socket-restore-v1','source':ref,'roots':inert,'visible_unpack_guard_unchanged':True,'socket_target_text_omitted':True}),mode=0o400)
 return roots

def projector(module):
 original=module.project
 need(hash_file(Path(inspect.getsourcefile(original)))['sha256']==PROJECTION_SHA,'DB_REPAIR_ORIGINAL_PROJECT_PIN')
 ns=dict(original.__globals__);ns['physical_roots']=lambda cas,component,home:physical(module,cas,component,home)
 fresh=FunctionType(original.__code__,ns,original.__name__,original.__defaults__,original.__closure__)
 def project(cas,ref,expected,home,*,recollector,mysql_export):
  home=Path(home)
  if not home.exists():return fresh(cas,ref,expected,home,recollector=recollector,mysql_export=mysql_export)
  snapshot=cas.verify_snapshot(ref,expected=expected);need(snapshot['target_tokens']==16_000_000,'AGGREGATE_ONLY_SEALED16M')
  need(not(home/'PROJECTION.json').exists(),'DB_REPAIR_NO_COMPLETED_PROJECTION_REEXECUTION')
  view=home/'view';round_=view/'proposals/round-0001';workers={}
  # Finished original stages are immutable/private and have never been mounted.
  for role,row in sorted(snapshot['roles'].items()):
   pin=row['workspace']['archive'];workers[role]=verify_worker(module,cas.resolve(pin),pin,round_/role)
  need(set(p.name for p in round_.iterdir())==set(workers)|{'gitea'},'DB_REPAIR_ONLY_COMPLETED_PREDB_VIEW')
  for p in [view,*view.rglob('*')]:
   if p.is_symlink():need(not PurePosixPath(os.readlink(p)).is_absolute() and p.resolve().is_relative_to(view.resolve()),'DB_REPAIR_REUSED_VISIBLE_LINK_GUARD')
  d=round_/'gitea/discussions.json';need(d.is_file() and not d.is_symlink(),'DB_REPAIR_COMPLETED_GITEA_DISCUSSION_STAGE')
  # Private runtime reads only previously generated discussion projection; never
  # emits its bodies. Workers/Git/parser/export are NOT invoked a second time.
  g=json.loads(d.read_bytes());need(set(g)=={'repositories','issues','comments','merged_pull_requests'},'DB_REPAIR_ORIGINAL_GITEA_OUTPUT_SCHEMA')
  git={'repositories':len(g['repositories']),'issues':len(g['issues']),'comments':len(g['comments']),'archive':snapshot['shared']['gitea_database']['archive'],'reused_original_completed_projection':True}
  private=home/'collaboration-private';need(private.is_dir() and not private.is_symlink(),'DB_REPAIR_ORIGINAL_PRIVATE_DB_STAGE')
  roots=physical(module,cas,snapshot['shared']['collaboration'],private)
  mm=mysql_export(roots,private,round_/'team-discussion.jsonl')
  (view/'output/pocs').mkdir(mode=0o755,parents=True);(view/'output/progress.md').touch(mode=0o444)
  receipt={'schema':'agensh-late-aggregate-readonly-view-v1','snapshot':ref,'worker_roster':sorted(workers),'workers':workers,'gitea':git,'collaboration':mm,'sources':'sealed16M-only','view_has_no_physical_databases_or_credentials':True,'proposal_round':'round-0001','private_db_repair':'inert-socket-only'}
  publish(home/'PROJECTION.json',wire(receipt),mode=0o400);return view,receipt
 return project

def schema_repair():
 prior=sys.modules.get('a4_original_branch_projection_repair_v1') or sys.modules.get('branch_projection_repair')
 need(prior is not None and hash_file(Path(prior.__file__))['sha256']=='805a5b7838776e6f34b1c0d5e72645a386eace125a41da62c731a8d44c918a94','DB_REPAIR_INSTALLED_SCHEMA_MODULE_PIN')
 return prior

def continuation(manager_module,project,prior=None):
 prior=prior or schema_repair()
 need(hash_file(Path(inspect.getsourcefile(manager_module.Manager.run_one)))['sha256']==MANAGER_SHA,'DB_REPAIR_ORIGINAL_MANAGER_PIN')
 # The old schema suffix hardcoded a NEW view, whereas here we reuse the exact
 # finished view chosen during qualification. Only that original call arg moves.
 original=manager_module.Manager.run_one
 tree=ast.parse(textwrap.dedent(inspect.getsource(original)));root=tree.body[0]
 i=next(i for i,n in enumerate(root.body)if isinstance(n,ast.Assign)and isinstance(n.value,ast.Call)and ast.unparse(n.value.func)=='Phase')
 root.body[i:i+2]=ast.parse("phase=record['phase']").body
 i=next(i for i,n in enumerate(root.body)if isinstance(n,ast.Assign)and isinstance(n.value,ast.Call)and ast.unparse(n.value.func)=='project')
 root.body[i].value.args[3]=ast.parse("record['_db_projection_home']",mode='eval').body
 root.body.insert(i+1,ast.parse('_reopen(phase,record)').body[0])
 ns=dict(original.__globals__);ns.update(project=project,_reopen=prior.reopen_zero_request)
 exec(compile(ast.fix_missing_locations(tree),str(Path(__file__))+':original-agent-unexecuted-suffix','exec'),ns)
 return ns['run_one']

def install(driver):
 import aggregate_projection as P,aggregate_install as A,aggregate_source as S
 prior=schema_repair()
 need(not hasattr(driver,'_a4_private_db_repair'),'DB_REPAIR_INSTALL_ONCE')
 m=driver.late_aggregate_fork_manager
 need(not driver.failed and not m.needs_caretaker and hasattr(driver,'_a4_branch_projection_repair'),'DB_REPAIR_ORIGINAL_SCHEMA_FIXED_OWNER')
 fixed=projector(P);tail=continuation(A,fixed,prior);fail=prior.failure_suffix(A)
 # Preserve both forensic markers if the new suffix itself fails.
 fail.__globals__['publish']=lambda path,*a,**kw:publish(Path(path).with_name('PRIVATE_DB_REPAIR_FAILURE_RETAINED.json'),*a,**kw)
 retained=[]
 with m.lock:
  for parent,r in m.records.items():
   if r['state']!='FAULT_RETAINED':continue
   phase=r.get('phase');need(phase is not None and r['error_type']=='Refused','DB_REPAIR_ONLY_PROVEN_PREMODEL_REFUSAL')
   need(r['thread']is not None and not r['thread'].is_alive(),'DB_REPAIR_ORIGINAL_THREAD_TERMINAL')
   need(phase.source==r['source'] and phase.id==r['branch_id'] and phase.parent==parent and phase.ref==r['source']['snapshot'],'DB_REPAIR_ORIGINAL_PHASE_SOURCE')
   need(phase.relay is None and phase.sealed is None and not r.get('agent') and not r.get('sandbox'),'DB_REPAIR_NEVER_STARTED_AGENT')
   f=m.l.frontier(phase.id)
   need(f['state']=='DRAINING' and all(f[k]==0 for k in ('actual','reserved','unresolved','active_operations')),'DB_REPAIR_ORIGINAL_ZERO_ACCOUNT')
   need(m.l.db.execute('SELECT COUNT(*)FROM requests WHERE trajectory=?',(phase.id,)).fetchone()[0]==0,'DB_REPAIR_NO_REPLAY')
   homes=[r['home']/name for name in ('readonly-source','readonly-source-schema-v1')]
   homes=[h for h in homes if (h/'view/proposals/round-0001/gitea/discussions.json').is_file() and not(h/'PROJECTION.json').exists() and (h/'collaboration-private/physical-outer/PHYSICAL_ROOTS.json').is_file()]
   need(len(homes)==1,'DB_REPAIR_UNIQUE_COMPLETED_WORKER_GITEA_VIEW')
   S.validate(driver.records[parent]['launch'].controller.cas,r['source'],parent=parent,manifest_sha=digest(driver.manifest))
   retained.append((parent,r,homes[0]))
  need(retained,'DB_REPAIR_RETAINED_PREMODEL_BRANCHES_REQUIRED')
  # Future branches use same original project with PRIVATE physical adapter only.
  A.project=fixed;P.project=fixed
  state={'threads':[],'original_project_source_sha256':PROJECTION_SHA};driver._a4_private_db_repair=state
  for parent,r,home in retained:
   r.setdefault('_db_retired_threads',[]).append(r['thread']);r['_db_projection_home']=home;r['state']='PRIVATE_DB_REPAIR';r['error_type']=None
   def run(parent=parent,r=r):
    try:tail(m,parent,r)
    except BaseException as e:fail(m,parent,r,e)
   th=threading.Thread(target=run,name='same-branch-private-db-'+digest(parent)[:12],daemon=False);r['thread']=th;state['threads'].append(th);th.start()
 return {'schema':'a4-private-db-repair-v1','same_phase_account_source':True,'reused_worker_gitea_views':len(retained),'visible_archive_guard_changed':False,'mainline_state_modified':False,'requests_replayed':0,'branch_search':'REQUIRES_REAL_NEW_SETTLEMENTS'}
