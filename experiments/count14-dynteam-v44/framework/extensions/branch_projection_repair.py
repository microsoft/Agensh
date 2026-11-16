"""Public Gitea title/name mapping + original never-started branch suffix.

No new Phase/account/session/source. A branch closed BEFORE its first request
may reopen the same exact zero-use account after a successful private projection.
No request/history/cost is changed; mainline never parked/closed/rewritten.
"""
from pathlib import Path
from types import MethodType
import ast,copy,inspect,json,threading,textwrap
from common import need,digest,hash_file,wire,publish
PROJECTION_SHA='9cec4260794691a4c47cd6a7c7bef6014a1cdde955fda029b09dd5c4e65dd552'
MANAGER_SHA='4e519788567abf58f59b335571e4142a408855c36a24c3f490d46360d4fefdf1'
VIEW='readonly-source-schema-v1'

def discussion_rows(c):
 # Schema names only; never inspect rows to choose protocol or query. Both
 # approved public spellings map to the SAME output key, no SELECT *.
 cols={r[1]for r in c.execute('PRAGMA table_info(issue)')}
 cc={r[1]for r in c.execute('PRAGMA table_info(comment)')}
 need({'id','repo_id','index','content'}<=cols,'BRANCH_PUBLIC_ISSUE_REQUIRED_COLUMNS')
 title=cols&{'name','title'};need(len(title)==1,'BRANCH_PUBLIC_ISSUE_TITLE_NAME_UNIQUE')
 need({'id','issue_id','type','content'}<=cc,'BRANCH_PUBLIC_COMMENT_REQUIRED_COLUMNS')
 field=next(iter(title))
 issues=[dict(r)for r in c.execute('SELECT id,repo_id,"index",'+field+' AS title,content FROM issue ORDER BY id')]
 comments=[dict(r)for r in c.execute('SELECT id,issue_id,type,content FROM comment ORDER BY id')]
 return issues,comments

def fix_gitea(module):
 original=module.gitea;need(hash_file(Path(inspect.getsourcefile(original)))['sha256']==PROJECTION_SHA,'BRANCH_ORIGINAL_PROJECTION_PIN')
 tree=ast.parse(textwrap.dedent(inspect.getsource(original)));fn=tree.body[0]
 tries=[n for n in fn.body if isinstance(n,ast.Try)];need(len(tries)==1,'BRANCH_ORIGINAL_SQL_TRY')
 target=tries[0];need(len(target.body)==2 and all(isinstance(n,ast.Assign)for n in target.body),'BRANCH_ORIGINAL_SQL_TWO_SELECTS')
 need([ast.unparse(n.targets[0])for n in target.body]==['issues','comments'],'BRANCH_ORIGINAL_DISCUSSION_FIELDS')
 need(ast.literal_eval(target.body[0].value.generators[0].iter.args[0])=='SELECT id,repo_id,"index",title,content FROM issue ORDER BY id','BRANCH_ORIGINAL_ISSUE_SELECT')
 target.body=ast.parse('issues,comments=_discussion_rows(c)').body
 ns=dict(original.__globals__);ns['_discussion_rows']=discussion_rows
 exec(compile(ast.fix_missing_locations(tree),str(Path(__file__))+':original-gitea-schema-adapter','exec'),ns)
 return ns['gitea']

def reopen_zero_request(phase,record):
 l=phase.l;t=phase.id
 need(phase.relay is None and phase.sealed is None,'BRANCH_SUFFIX_NEVER_BOUND_OR_SEALED')
 need(not record.get('sandbox')and not record.get('agent'),'BRANCH_SUFFIX_NEVER_STARTED_AGENT')
 with l.tx():
  f=l.frontier(t)
  need(f['state']=='DRAINING'and f['generation']==1 and f['stage']==0 and f['target']==4_000_000,'BRANCH_SUFFIX_ORIGINAL_FIRST_PHASE')
  need(not any(f[k]for k in('actual','reserved','unresolved','active_operations')),'BRANCH_SUFFIX_ZERO_USE_ONLY')
  need(l.db.execute('SELECT COUNT(*)FROM requests WHERE trajectory=?',(t,)).fetchone()[0]==0,'BRANCH_SUFFIX_ZERO_REQUESTS_NO_REPLAY')
  need(l.admission_fault(t)is None and not l.model_paused()and not phase.driver.failed,'BRANCH_SUFFIX_NO_FINANCIAL_FAULT')
  row=l.db.execute("SELECT metadata FROM events WHERE trajectory=? AND kind='ADMISSION_CLOSED'ORDER BY seq DESC LIMIT 1",(t,)).fetchone()
  need(row is not None and json.loads(row[0]).get('reason')=='LATE_AGGREGATE_BRANCH_FAILURE_RETAINED','BRANCH_SUFFIX_OWN_PROJECTION_CLOSE_ONLY')
  l.db.execute("UPDATE accounts SET state='RUNNING' WHERE trajectory=? AND state='DRAINING'",(t,))
  l.event(t,'AGGREGATE_PREREQUEST_PROJECTION_REPAIR_REOPENED',{'source_sha256':digest(record['source']),'requests_existing':0,'actual_existing':0,'same_phase':True,'same_account':True,'mainline_state_modified':False,'replay':False})
 phase.gate.notify()

def suffix(manager_module):
 original=manager_module.Manager.run_one
 need(hash_file(Path(inspect.getsourcefile(original)))['sha256']==MANAGER_SHA,'BRANCH_ORIGINAL_MANAGER_PIN')
 tree=ast.parse(textwrap.dedent(inspect.getsource(original)));fn=tree.body[0]
 # Leave all original source/materialization/sandbox/tool/model/budget/final
 # code unchanged, except reuse Phase, new private view, and zero-use rearm.
 need(len(fn.body)>4,'BRANCH_ORIGINAL_RUN_ONE_STRUCTURE')
 phase_nodes=[i for i,n in enumerate(fn.body)if isinstance(n,ast.Assign)and isinstance(n.value,ast.Call)and ast.unparse(n.value.func)=='Phase']
 need(len(phase_nodes)==1,'BRANCH_ORIGINAL_ONE_PHASE_CONSTRUCTOR');i=phase_nodes[0]
 need(ast.unparse(fn.body[i+1])=="record['phase'] = phase",'BRANCH_ORIGINAL_PHASE_RECORD')
 fn.body[i:i+2]=ast.parse("phase=record['phase']").body
 projected_nodes=[i for i,n in enumerate(fn.body)if isinstance(n,ast.Assign)and isinstance(n.value,ast.Call)and ast.unparse(n.value.func)=='project']
 need(len(projected_nodes)==1,'BRANCH_ORIGINAL_ONE_PROJECT_CALL');i=projected_nodes[0];projected=fn.body[i]
 need(ast.unparse(projected.value.args[3])=="home / 'readonly-source'",'BRANCH_ORIGINAL_PRIVATE_SOURCE_HOME')
 projected.value.args[3]=ast.parse('home/'+repr(VIEW),mode='eval').body
 fn.body.insert(i+1,ast.parse('_reopen(phase,record)').body[0])
 ns=dict(original.__globals__);ns['_reopen']=reopen_zero_request
 exec(compile(ast.fix_missing_locations(tree),str(Path(__file__))+':original-branch-unexecuted-suffix','exec'),ns)
 return ns['run_one']

def failure_suffix(manager_module):
 original=manager_module.Manager.fail
 need(hash_file(Path(inspect.getsourcefile(original)))['sha256']==MANAGER_SHA,'BRANCH_ORIGINAL_FAIL_PIN')
 tree=ast.parse(textwrap.dedent(inspect.getsource(original)));changed=0
 for n in ast.walk(tree):
  if isinstance(n,ast.Constant)and n.value=='FAULT_RETAINED.json':n.value='SCHEMA_REPAIR_FAILURE_RETAINED.json';changed+=1
 need(changed==1,'BRANCH_ORIGINAL_FAIL_MARKER_ONLY')
 ns=dict(original.__globals__);exec(compile(ast.fix_missing_locations(tree),str(Path(__file__))+':original-fail-new-marker-only','exec'),ns)
 return ns['fail']

def install(driver):
 import aggregate_projection as projection,aggregate_install as manager_module
 m=driver.late_aggregate_fork_manager
 need(not hasattr(driver,'_a4_branch_projection_repair'),'BRANCH_SCHEMA_INSTALL_ONCE')
 need(not driver.failed and not m.needs_caretaker,'BRANCH_SCHEMA_NO_GLOBAL_INCIDENT')
 need(isinstance(m,manager_module.Manager),'BRANCH_ORIGINAL_MANAGER_OBJECT')
 fixed=fix_gitea(projection);continuation=suffix(manager_module);fail=failure_suffix(manager_module)
 retained=[]
 with m.lock:
  for parent,r in list(m.records.items()):
   if r['state']!='FAULT_RETAINED' or r['error_type']!='OperationalError':continue
   phase=r.get('phase');need(phase is not None,'BRANCH_SUFFIX_RETAINED_PHASE')
   need(phase.source==r['source']and phase.ref==r['source']['snapshot']and phase.id==r['branch_id']and phase.parent==parent,'BRANCH_SUFFIX_EXACT_ORIGINAL_SOURCE_PHASE')
   need(r['thread']is not None and not r['thread'].is_alive(),'BRANCH_SUFFIX_ORIGINAL_THREAD_TERMINAL')
   need(phase.relay is None and phase.sealed is None and not r.get('agent')and not r.get('sandbox'),'BRANCH_SUFFIX_PREMODEL_ONLY')
   need(not(r['home']/'readonly-source/PROJECTION.json').exists(),'BRANCH_SUFFIX_ORIGINAL_PROJECTION_INCOMPLETE')
   need(not(r['home']/VIEW).exists(),'BRANCH_SUFFIX_NEW_PRIVATE_VIEW_ONLY')
   f=m.l.frontier(phase.id)
   need(f['actual']==f['reserved']==f['unresolved']==f['active_operations']==0 and f['state']=='DRAINING','BRANCH_SUFFIX_ORIGINAL_ZERO_ACCOUNT')
   need(m.l.db.execute('SELECT COUNT(*)FROM requests WHERE trajectory=?',(phase.id,)).fetchone()[0]==0,'BRANCH_SUFFIX_NO_REPLAY')
   owner=driver.records[parent]['launch'].controller
   __import__('aggregate_source').validate(owner.cas,r['source'],parent=parent,manifest_sha=digest(driver.manifest))
   retained.append((parent,r))
  need(retained,'BRANCH_SUFFIX_AT_LEAST_ONE_RETAINED_ZERO_BRANCH')
  previous=projection.gitea;projection.gitea=fixed
  driver._a4_branch_projection_repair={'previous_gitea':previous,'threads':[],'source':'same-original16M','no_mainline_state_changed':True}
  for parent,r in retained:
   old=r['thread'];r.setdefault('_schema_retired_threads',[]).append(old)
   r['state']='PROJECTION_REPAIR';r['error_type']=None
   def run(parent=parent,r=r):
    try:continuation(m,parent,r)
    except BaseException as e:fail(m,parent,r,e)
   th=threading.Thread(target=run,name='original-branch-schema-'+digest(parent)[:12],daemon=False)
   r['thread']=th;driver._a4_branch_projection_repair['threads'].append(th);th.start()
 return {'schema':'a4-original-branch-schema-repair-v1','retained_branch_count':len(retained),'same_phase_account_source':True,'prior_requests':0,'requests_replayed':0,'mainline_paused':False,'new_model_outcome':'NOT_YET_PROVEN'}
