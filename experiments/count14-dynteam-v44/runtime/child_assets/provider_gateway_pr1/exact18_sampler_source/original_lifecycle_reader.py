"""Fresh exact18 original lifecycle projection; never read request/ledger bodies.

Expected identities are from the actual OPS PUBLIC read, not current-state
truth. Each call reopens the original registered queue RO and checks original
source pins/code/no-reentry and live execution births afresh. No owner244 pin.
"""
from pathlib import Path
import ast,hashlib,inspect,json,os,sqlite3,stat,time

BINDINGS_PIN='f050c4ade30cc757ac316369b9cfaea8a201aa8db5df654280f9812e912d157d'
RUNTIME_PIN='84789e5e6627a7fdeb79e35600c079fe5bf89aee84b214fa4c8301fba29c60b0'
SOURCES={'k3_jobs_v514.py':'b93bcd1682d23f5596be51da8a5d33ad7711131eebe8007278bfdc61bf0bc8ee',
 'checkpoint_jobs.py':'c038347918c8d8d2adfaf227648630033048763a178c1d105cce7e99dba76331',
 'finalization_engine_v1094.py':'e3415e57bf68de8155fa08f1ad0a0e0af13eb77428f9aec1b61a39634df40145'}

def need(ok,code):
 if not ok:raise ValueError(code)
def identity(p):
 p=Path(p);s=p.lstat()
 need(p.is_absolute()and p.resolve()==p and not p.is_symlink(),'LIFECYCLE_CANONICAL_EXACT_SOURCE')
 return dict(path=str(p),device=s.st_dev,inode=s.st_ino,uid=s.st_uid,gid=s.st_gid,mode=oct(stat.S_IMODE(s.st_mode)))
def stable(p):
 s=Path(p).lstat();return(s.st_dev,s.st_ino,s.st_uid,s.st_gid,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def source_read(p,pin,expected=None):
 p=Path(p);before=stable(p);meta=identity(p)
 need(stat.S_ISREG(before[4]) and before[5]==1 and before[6]<=2**20 and
      (expected is None or meta=={k:v for k,v in expected.items()if k!='sha256'}),
      'LIFECYCLE_EXACT_BOUNDED_PUBLIC_OR_FRAMEWORK_SOURCE')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  with os.fdopen(fd,'rb',closefd=False)as f:raw=f.read(2**20+1)
 finally:os.close(fd)
 need(len(raw)==before[6]and stable(p)==before and hashlib.sha256(raw).hexdigest()==pin,
      'LIFECYCLE_ORIGINAL_SOURCE_PIN_AND_STABILITY')
 return raw

def same_birth_active(pid,start):
 try:b=(Path('/proc')/str(pid)/'stat').read_bytes()
 except FileNotFoundError:return False
 f=b[b.rfind(b')')+2:].split()
 return int(f[19])==int(start)and f[0]not in(b'Z',b'X',b'x')

def numeric_identity(row):
 return {k:(int(v,8)if k=='mode'else v)for k,v in row.items()if k!='path'}

class OriginalLifecycle:
 def __init__(self,bindings_path,*,original_registry_path,original_registry_sha256):
  raw=source_read(bindings_path,BINDINGS_PIN);value=json.loads(raw)
  need(value['plan_sha256']=='7b754107d928b8e8597ad0c4171707127921fb4216847eb34a65f5bce29d0e69'and
       len(value['rows'])==18 and len(value['controllers'])==3,'LIFECYCLE_ACTUAL_FULL18_BINDINGS')
  self.rows={r['request_root']:r for r in value['rows']};need(len(self.rows)==18,'LIFECYCLE_NO_DUPLICATE_ROOT')
  self.controllers=value['controllers'];self.reg=Path(original_registry_path);self.reg_pin=original_registry_sha256
  self.reader_pin=hashlib.sha256(inspect.getsource(self.read_one).encode()).hexdigest()
  self.refs=dict(path=str(bindings_path),sha256=BINDINGS_PIN)

 def read_one(self,original_root):
  need(original_root in self.rows,'LIFECYCLE_EXACT18_ONLY');row=self.rows[original_root]
  registry=json.loads(source_read(self.reg,self.reg_pin))
  need(original_root in registry['scale_request_roots']and row['book_identity']['path']in registry['scale_reservation_books'],
       'LIFECYCLE_ROOT_AND_BOOK_ORIGINAL_REGISTERED_NOT_DELETED')
  candidates=[c for c in self.controllers if Path(original_root).is_relative_to(Path(c['native_directory_identity']['path']).parent.parent)]
  need(len(candidates)==1,'LIFECYCLE_ORIGINAL_TRAJECTORY_CONTROLLER_BINDING');controller=candidates[0]
  need(identity(controller['native_directory_identity']['path'])==controller['native_directory_identity'],
       'LIFECYCLE_REGISTERED_CONTROLLER_DIRECTORY')
  runtime=controller['runtime_pins'];need(runtime['sha256']==RUNTIME_PIN,'LIFECYCLE_ACTUAL_RUNTIME_BINDING_PIN')
  pins=json.loads(source_read(runtime['path'],RUNTIME_PIN))
  for ref in controller['original_sources']:
   name=Path(ref['path']).name;need(name in SOURCES and ref['sha256']==SOURCES[name]==pins[name],
        'LIFECYCLE_NO_UNREGISTERED_OR_OLD_FALLBACK_SOURCE')
   body=source_read(ref['path'],SOURCES[name],ref);t=ast.parse(body)
   funcs={n.name:ast.get_source_segment(body.decode(),n)for n in t.body if isinstance(n,ast.FunctionDef)}
   if name=='k3_jobs_v514.py':
    one=funcs['one'];refusal="if branch.exists() or result.exists():raise RuntimeError('Never replay an existing K run')"
    need(refusal in one and one.index(refusal)<one.index('finalize_checkpoint('),
         'LIFECYCLE_ORIGINAL_EXISTING_BRANCH_REFUSES_BEFORE_FINALIZE')
   if name=='checkpoint_jobs.py':need("WHERE state='PENDING'"in funcs['claim'],'LIFECYCLE_ORIGINAL_CLAIM_PENDING_ONLY')
  qi=controller['jobs_db_identity'];q=Path(qi['path']);need(identity(q)==qi,'LIFECYCLE_SAME_ORIGINAL_QUEUE_INODE')
  before=stable(q);db=sqlite3.connect(q.as_uri()+'?mode=ro&cache=private',uri=True,timeout=.2,isolation_level=None)
  deadline=time.monotonic()+3;db.execute('PRAGMA query_only=ON');db.execute('PRAGMA busy_timeout=200')
  db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
  try:
   db.execute('BEGIN');changes=db.total_changes
   counts=dict(db.execute('SELECT state,COUNT(*)FROM jobs GROUP BY state'))
   need(set(counts)<={'COMPLETE','PARTIAL'},'LIFECYCLE_ANY_ACTIVE_OR_PENDING_REFUSED')
   unended=db.execute('SELECT COUNT(*)FROM queue_executions_v524 WHERE ended_at IS NULL OR terminal IS NULL').fetchone()[0]
   need(unended==0,'LIFECYCLE_ANY_UNENDED_EXECUTION_REFUSED')
   job=row['original_job'];j=db.execute("SELECT id,state,json_extract(payload,'$.runtime_pins_sha256'),json_extract(payload,'$.label'),json_extract(payload,'$.replicate_index'),json_extract(payload,'$.attempt_ordinal')FROM jobs WHERE id=?AND json_extract(payload,'$.kind')='finalization_k3'",(job['id'],)).fetchall()
   expected=(job['id'],'COMPLETE',RUNTIME_PIN,job['label'],job['replicate'],job['attempt_ordinal'])
   need(j==[expected]and db.execute('SELECT COUNT(*)FROM pilot_registered_attempts_v1 WHERE job=?',(job['id'],)).fetchone()[0]==1,
        'LIFECYCLE_EXACT_ORIGINAL_JOB_REGISTRATION_AND_TERMINAL')
   executions=db.execute('SELECT owner_pid,owner_start,claimed_at,ended_at,terminal FROM queue_executions_v524 WHERE job=?',(job['id'],)).fetchall()
   need(len(executions)==1 and executions==[tuple(e)for e in row['original_execution_control_rows']] and
        all(e[3]is not None and e[4]in('COMPLETE','PARTIAL')and not same_birth_active(e[0],e[1])for e in executions),
        'LIFECYCLE_EXACT_EXECUTION_TERMINAL_NO_LIVE_BIRTH')
   need(db.total_changes==changes==0,'LIFECYCLE_READ_ONLY_CONTROL');db.execute('ROLLBACK')
  finally:db.close()
  need(stable(q)==before,'LIFECYCLE_QUEUE_STABLE_DURING_FRESH_READ')
  need(identity(row['branch_identity']['path'])==row['branch_identity']and identity(row['book_identity']['path'])==row['book_identity'],
       'LIFECYCLE_EXACT_REGISTERED_PARENT_BOOK_IDENTITY')
  # This is a digest of selected public job/lifecycle controls, not ledger,
  # request values or scientific contents. Observation timestamp is not hashed.
  selected=dict(queue=qi,job=j,executions=executions,all_job_state_counts=counts,unended=unended,runtime=RUNTIME_PIN)
  control_pin=hashlib.sha256(json.dumps(selected,sort_keys=True).encode()).hexdigest()
  return dict(root=original_root,lifecycle_reader_sha256=self.reader_pin,observed_ns=time.time_ns(),
       original_active_jobs=0,original_pending_jobs=0,original_no_reentry=True,actual_original_lifecycle_bound=True,
       lifecycle_reference=dict(path=str(q),sha256=control_pin),registered_parent_identity=numeric_identity(row['branch_identity']),
       registered_book_identity=numeric_identity(row['book_identity']))
