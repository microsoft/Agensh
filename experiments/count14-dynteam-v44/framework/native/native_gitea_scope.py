"""Fixed native Gitea scope: original61 declarations/original26 allowed tools.

The native backend is not replaced. Bootstrap topology/actors and private output
workspace confinement are trusted owner inputs, not worker-selected URLs/paths.
Only physically completed output registers opaque resource IDs in the SAME
Ledger transaction as MCP completion; body/text/credentials are never journaled.
"""
from pathlib import Path
import json,os,re,stat,urllib.parse
from common import need,Refused,digest,ident,sha,wire,trajectory_id,parts
from native_mcp_policy import FixedScopeGuard,ScopeRejected,McpPolicy
from native_mcp_inputs import load_native_tools
from native_mattermost_scope import original_denials
SCHEMA='agensh-native-gitea-scope-v1'
WRITE={'create_commit_status','create_organization','issue_write','package_write','project_write','pull_request_review_write','pull_request_write','rename_branch'}
NAMES={'actions_run_read','attachment_read','compare_commits','create_commit_status','create_organization','get_commit_status','get_me','get_user_orgs','issue_read','issue_write','list_issues','list_my_repos','list_org_repos','list_pull_requests','package_read','package_write','project_read','project_write','pull_request_read','pull_request_review_write','pull_request_write','rename_branch','search_issues','search_org_teams','search_repos','search_users'}
KINDS={name:'GIT_WRITE'if name in WRITE else'GIT_READ'for name in NAMES}
def positive(value):return type(value)is int and value>0

def object_id(value):need(positive(value),'GITEA_SCOPE_POSITIVE_ID');return str(value)
def scope_need(ok,code):
 if not ok:raise ScopeRejected(code)
def ref(value):
 scope_need(type(value)is str and 0<len(value)<=255 and not any(c.isspace()or ord(c)<32 for c in value)and not any(x in value for x in ('..','@{','//','\\',':','^','~','?','*','['))and not value.startswith(('/','-','.'))and not value.endswith(('/','.','.lock')),'GITEA_SCOPE_REF')
 return value

def sequence(value,*keys):
 if type(value)is list:return value
 need(type(value)is dict,'GITEA_SCOPE_NATIVE_LIST')
 for key in keys:
  if key in value:need(type(value[key])is list,'GITEA_SCOPE_NATIVE_LIST');return value[key]
 need(False,'GITEA_SCOPE_NATIVE_LIST')

def native_json(response):
 result=response.get('result');need(type(result)is dict and not result.get('isError'),'GITEA_SCOPE_NATIVE_RESULT')
 if 'structuredContent'in result:return result['structuredContent']
 content=result.get('content');need(type(content)is list and len(content)==1 and type(content[0])is dict and content[0].get('type')=='text'and type(content[0].get('text'))is str,'GITEA_SCOPE_NATIVE_JSON')
 from common import strict
 return strict(content[0]['text'])

class GiteaScope(FixedScopeGuard):
 requires_native_text_integrity=True
 def __init__(self,ledger,binding,expected_sha256,*,sandbox=None,sdk_identity=None):
  self.sandbox=sandbox;self.sdk_identity=sdk_identity
  need(type(binding)is dict and set(binding)=={'schema','trajectory','service_instance_sha256','bootstrap_receipt_sha256','service_origin','organization','repository','role_users','service_users','teams','workspace_roots'},'GITEA_SCOPE_BINDING_FIELDS')
  need(binding['schema']==SCHEMA and digest(binding)==sha(expected_sha256),'GITEA_SCOPE_BINDING_PIN');trajectory_id(binding['trajectory']);sha(binding['service_instance_sha256']);sha(binding['bootstrap_receipt_sha256'])
  url=urllib.parse.urlsplit(binding['service_origin']);need(url.scheme in('http','https')and url.hostname and url.username is None and url.password is None and url.path in('','/')and not url.query and not url.fragment,'GITEA_SCOPE_FIXED_ORIGIN')
  self.ledger=ledger;self.binding=json.loads(wire(binding));self.pin=digest(binding);self.trajectory=binding['trajectory'];self.origin=binding['service_origin'].rstrip('/');self.roles={};self.agents={};self.users={};self.usernames={};self.workspaces={}
  org=binding['organization'];repo=binding['repository'];need(type(org)is dict and set(org)=={'id','name'}and type(repo)is dict and set(repo)=={'id','name'},'GITEA_SCOPE_REPOSITORY_IDENTITY');object_id(org['id']);object_id(repo['id']);ident(org['name']);ident(repo['name']);self.org=org;self.repo=repo
  roles=set(json.loads(ledger.account(self.trajectory)['roles']));need(type(binding['role_users'])is dict and set(binding['role_users'])==roles and type(binding['workspace_roots'])is dict and set(binding['workspace_roots'])==roles,'GITEA_SCOPE_EXACT_REGISTERED_ROSTER')
  for role,user in binding['role_users'].items():
   ident(role);need(type(user)is dict and set(user)=={'id','username','agent'},'GITEA_SCOPE_ROLE_USER');ident(user['agent']);need(user['agent']not in self.agents.values(),'GITEA_SCOPE_AGENT_DUPLICATE');self.user(user);self.roles[role]=user['id'];self.agents[role]=user['agent']
   workspace=binding['workspace_roots'][role];need(type(workspace)is dict and set(workspace)=={'path','uid','device','inode'},'GITEA_SCOPE_WORKSPACE_IDENTITY');p=Path(workspace['path']);need(p.is_absolute()and p.resolve()==p and p.is_dir()and not p.is_symlink(),'GITEA_SCOPE_WORKSPACE_CANONICAL');s=p.stat();need((s.st_uid,s.st_dev,s.st_ino)==(workspace['uid'],workspace['device'],workspace['inode']),'GITEA_SCOPE_WORKSPACE_PIN');self.workspaces[role]=p
  need(type(binding['service_users'])is list and type(binding['teams'])is list,'GITEA_SCOPE_BOOTSTRAP_RESOURCES')
  for user in binding['service_users']:self.user(user)
  self.teams={}
  for team in binding['teams']:
   need(type(team)is dict and set(team)=={'id','name'}and positive(team['id'])and team['id']not in self.teams,'GITEA_SCOPE_TEAM_IDENTITY');ident(team['name']);self.teams[team['id']]=team['name']
  need(len(self.users)<=64 and len(self.teams)<=64 and len(set(self.workspaces.values()))==len(roles),'GITEA_SCOPE_RESOURCE_BOUND')
  with ledger.tx():
   ledger.db.execute('CREATE TABLE IF NOT EXISTS gitea_scope_bindings(trajectory TEXT PRIMARY KEY,pin TEXT NOT NULL,binding TEXT NOT NULL)');ledger.db.execute('CREATE TABLE IF NOT EXISTS gitea_scope_resources(scope TEXT NOT NULL,kind TEXT NOT NULL,id TEXT NOT NULL,parent TEXT NOT NULL,metadata TEXT NOT NULL,PRIMARY KEY(scope,kind,id))')
   for table in ('gitea_scope_bindings','gitea_scope_resources'):
    for action in('UPDATE','DELETE'):ledger.db.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'append only native scope'); END")
   row=ledger.db.execute('SELECT pin FROM gitea_scope_bindings WHERE trajectory=?',(self.trajectory,)).fetchone()
   if row is None:ledger.db.execute('INSERT INTO gitea_scope_bindings VALUES(?,?,?)',(self.trajectory,self.pin,wire(binding).decode()));ledger.event(self.trajectory,'GITEA_SCOPE_BOUND',{'binding_sha256':self.pin,'service_instance_sha256':binding['service_instance_sha256'],'bootstrap_receipt_sha256':binding['bootstrap_receipt_sha256'],'roles':sorted(roles)})
   else:need(row['pin']==self.pin,'GITEA_SCOPE_SERVICE_REBIND_NO_REPLAY')
 def user(self,user):
  need(type(user)is dict and set(user)in({'id','username'},{'id','username','agent'}),'GITEA_SCOPE_USER_IDENTITY');object_id(user['id']);ident(user['username']);need(user['id']not in self.users and user['username']not in self.usernames,'GITEA_SCOPE_PRINCIPAL_DUPLICATE');self.users[user['id']]=user['username'];self.usernames[user['username']]=user['id']
 def add(self,kind,oid,parent,metadata=None):
  need(self.ledger.db.in_transaction,'GITEA_SCOPE_RESOURCE_REQUIRES_TRANSACTION');oid=str(oid);parent=str(parent);need(0<len(oid)<=256 and 0<len(parent)<=256,'GITEA_SCOPE_RESOURCE_ID');raw=wire(metadata or{}).decode()
  row=self.ledger.db.execute('SELECT parent,metadata FROM gitea_scope_resources WHERE scope=? AND kind=? AND id=?',(self.pin,kind,oid)).fetchone()
  if row is not None:need(row['parent']==parent and row['metadata']==raw,'GITEA_SCOPE_RESOURCE_IDENTITY_CHANGED');return
  need(self.ledger.db.execute('SELECT COUNT(*)FROM gitea_scope_resources WHERE scope=?',(self.pin,)).fetchone()[0]<100000,'GITEA_SCOPE_RESOURCE_COUNT_BOUND');self.ledger.db.execute('INSERT INTO gitea_scope_resources VALUES(?,?,?,?,?)',(self.pin,kind,oid,parent,raw));self.ledger.event(self.trajectory,'GITEA_SCOPE_RESOURCE_REGISTERED',{'binding_sha256':self.pin,'kind':kind,'id':oid,'parent':parent,'identity_sha256':digest(metadata or{})})
 def get(self,kind,oid):
  row=self.ledger.db.execute('SELECT parent,metadata FROM gitea_scope_resources WHERE scope=? AND kind=? AND id=?',(self.pin,kind,str(oid))).fetchone();scope_need(row is not None,'GITEA_SCOPE_RESOURCE_NOT_OBSERVED');return row['parent'],json.loads(row['metadata'])
 def bind(self,identity,tools,rules):
  need(identity.role in self.roles,'GITEA_SCOPE_POLICY_IDENTITY')
  need(identity.uid==self.binding['workspace_roots'][identity.role]['uid'],'GITEA_SCOPE_WORKSPACE_PEER_UID')
  need(identity.trajectory==self.trajectory and identity.purpose=='gitea'and identity.role in self.roles and identity.agent==self.agents[identity.role],'GITEA_SCOPE_POLICY_IDENTITY');need(tools==load_native_tools('gitea')and set(rules)==NAMES,'GITEA_SCOPE_FULL_NATIVE_POLICY')
  for name,rule in rules.items():need(rule=={'kind':KINDS[name],'scope_fields':{},'native_self_scope_qualified':True},'GITEA_SCOPE_POLICY_RULE')
 def backend(self,identity,command,environment,cwd):
  need(environment.get('GITEA_HOST','').rstrip('/')==self.origin and environment.get('AGENT_NAME')==self.agents[identity.role],'GITEA_SCOPE_FIXED_BACKEND_ACTOR');token=environment.get('GITEA_ACCESS_TOKEN');need(type(token)is str and token and not any(c in token for c in '\x00\r\n'),'GITEA_SCOPE_PRIVATE_TOKEN')
  # The owner's backend builder verifies the original binary/overlay and mounts
  # ONLY this bound workspace writable. A free-form command is never qualified.
  from native_gitea_backend import verify_command
  verify_command(command,self.workspaces[identity.role],environment,sandbox=self.sandbox,sdk_identity=self.sdk_identity)
 def ready(self,identity):
  try:return self.get('AUTH',self.roles[identity.role])[1]=={'role':identity.role}
  except ScopeRejected:return False
 def known_org(self,name):
  if name==self.org['name']:return True
  try:self.get('ORG_NAME',name);return True
  except ScopeRejected:return False
 def org_id(self,name):return self.org['id']if name==self.org['name']else int(self.get('ORG_NAME',name)[0])
 def category(self,identity,args):
  if args.get('org'):return'org:'+str(self.org_id(args['org']))
  if args.get('repo'):return'repo:'+str(self.repo['id'])
  return'user:'+str(self.roles[identity.role])
 def known(self,kind,value,parent=None):
  scope_need(positive(value),'GITEA_SCOPE_NUMERIC_ID');actual,_=self.get(kind,value);scope_need(parent is None or actual==str(parent),'GITEA_SCOPE_RESOURCE_PARENT');return actual
 def before(self,identity,name,args):
  scope_need(name=='get_me'or self.ready(identity),'GITEA_SCOPE_NATIVE_ACTOR_NOT_PRIMED');scope_need(name in NAMES,'GITEA_SCOPE_NATIVE_TOOL')
  domain_tool=name.startswith(('package_','project_'))or name in('list_org_repos','search_org_teams')
  for field,value in(('owner',self.org['name']),('related_owner',self.org['name']),('repo',self.repo['name']),('related_repo',self.repo['name']),('org',self.org['name'])):
   if field in args:
    dynamic=domain_tool and field in('owner','org')and not args.get('repo')and not args.get('related_repo')
    if dynamic:
     candidate=args[field];registered=candidate==self.org['name']or(field=='owner'and candidate in self.usernames)or(hasattr(self,'known_org')and self.known_org(candidate))
     scope_need(registered,'GITEA_SCOPE_FIXED_REPOSITORY')
    else:scope_need(args[field]==value,'GITEA_SCOPE_FIXED_REPOSITORY')
  if name=='create_organization':scope_need(type(args.get('username'))is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]{0,127}',args['username'])is not None,'GITEA_SCOPE_NATIVE_ORG_NAME')
  if name=='list_org_repos':scope_need(args.get('org')==self.org['name']or hasattr(self,'known_org')and self.known_org(args.get('org')),'GITEA_SCOPE_FIXED_ORG')
  if name=='search_issues':scope_need(args.get('owner')==self.org['name'],'GITEA_SCOPE_SEARCH_OWNER_REQUIRED')
  if name=='search_repos':scope_need(args.get('ownerID')==self.org['id'],'GITEA_SCOPE_SEARCH_OWNER_REQUIRED')
  method=args.get('method')
  required={
   'actions_run_read':{'get_workflow':['workflow_id'],'get_run':['run_id'],'list_run_jobs':['run_id'],'list_run_artifacts':['run_id'],'get_job':['job_id'],'get_job_log_preview':['job_id'],'download_job_log':['job_id'],'get_artifact':['artifact_id'],'download_artifact':['artifact_id']},
   'issue_read':{'get_comment':['comment_id']},
   'issue_write':{'create':['title'],'add_comment':['issue_number','body'],'edit_comment':['body'],'remove_label':['issue_number','label_id'],'add_dependency':['issue_number','related_issue_number'],'remove_dependency':['issue_number','related_issue_number']},
   'pull_request_read':{'get_by_branches':['base','head'],'get_by_commit':['sha'],'get_review':['pull_number','review_id'],'get_review_comments':['pull_number','review_id']},
   'pull_request_write':{'create':['base','head','title']},
   'pull_request_review_write':{'submit':['pull_number','review_id','state'],'delete':['pull_number','review_id'],'dismiss':['pull_number','review_id','message'],'reply_comment':['pull_number','comment_id','body'],'resolve_thread':['comment_id'],'unresolve_thread':['comment_id']},
   'project_read':{'get':['project_id'],'list_columns':['project_id'],'list_column_issues':['column_id']},
   'project_write':{'create':['title'],'update':['project_id'],'delete':['project_id'],'create_column':['project_id','title'],'update_column':['project_id','column_id'],'delete_column':['project_id','column_id'],'move_columns':['project_id','column_ids'],'set_default_column':['project_id','column_id'],'add_issue':['project_id','column_id','issue_id'],'remove_issue':['project_id','column_id','issue_id'],'move_issue':['project_id','column_id','issue_id']},
   'package_read':{'list_versions':['type','name'],'get':['type','name','version']},'package_write':{'delete':['type','name','version']},
  }
  fields=required.get(name,{}).get(method,[])
  if name=='issue_read'and method not in('get_comment','get_assignee_candidates'):fields=fields+['issue_number']
  if name=='issue_write'and method not in('create','edit_comment'):fields=fields+['issue_number']
  if name=='pull_request_read'and method not in('get_by_branches','get_by_commit','get_reviewer_candidates'):fields=fields+['pull_number']
  if name=='pull_request_write'and method!='create':fields=fields+['pull_number']
  if name=='pull_request_review_write'and method=='create':fields=fields+['pull_number']
  for field in fields:scope_need(field in args and bool(args[field]),'GITEA_SCOPE_CONDITIONAL_ARGUMENT_REQUIRED')
  if name=='issue_write'and method=='edit_comment':scope_need(bool(args.get('comment_id')or args.get('commentID')),'GITEA_SCOPE_CONDITIONAL_ARGUMENT_REQUIRED')
  if name=='issue_write'and method in('add_labels','replace_labels'):scope_need('labels'in args,'GITEA_SCOPE_CONDITIONAL_ARGUMENT_REQUIRED')
  if name=='attachment_read':
   scope_need(bool(args.get('issue_number')or args.get('comment_id'))or method=='download'and bool(args.get('attachment_uuid')),'GITEA_SCOPE_ATTACHMENT_PARENT_REQUIRED')
   if method in('get','download')and not args.get('attachment_uuid'):scope_need(bool(args.get('attachment_id')),'GITEA_SCOPE_CONDITIONAL_ARGUMENT_REQUIRED')
  if name=='pull_request_write'and method in('add_reviewers','remove_reviewers'):scope_need(bool(args.get('reviewers')or args.get('team_reviewers')),'GITEA_SCOPE_CONDITIONAL_ARGUMENT_REQUIRED')
  if name in('issue_write','pull_request_write'):
   for label in args.get('labels',[]):self.known('LABEL',label,self.repo['id'])
  if args.get('workflow_id'):scope_need(re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,255}',args['workflow_id'])is not None and'..'not in args['workflow_id'],'GITEA_SCOPE_WORKFLOW_COMPONENT')
  for key in('base','head','branch','new_name','ref','sha','commit_id','head_commit_id','head_sha'):
   if key in args and args[key]:ref(args[key])
  for key in('assignees','reviewers'):
   for user in args.get(key,[]):scope_need(user in self.usernames,'GITEA_SCOPE_REGISTERED_ACTOR_ONLY')
  for key in('assignee','created_by','assigned_by','mentioned_by'):
   if args.get(key):scope_need(args[key]in self.usernames,'GITEA_SCOPE_REGISTERED_ACTOR_ONLY')
  for team in args.get('team_reviewers',[]):scope_need(team in self.teams.values(),'GITEA_SCOPE_REGISTERED_TEAM_ONLY')
  for key in('name','type','version'):
   if name.startswith('package_')and key in args:scope_need(type(args[key])is str and 0<len(args[key])<=4096 and not any(ord(c)<32 or ord(c)==127 for c in args[key]),'GITEA_SCOPE_PACKAGE_COMPONENT')
  # Optional native output paths stay in exactly one worker's private sandbox.
  # Even a symlink race cannot reach another mount or host root in that jail.
  if args.get('output_path'):
   value=args['output_path'];scope_need(type(value)is str and not value.startswith('/')or type(value)is str and value.startswith('/work/'),'GITEA_SCOPE_WORKSPACE_OUTPUT_PATH')
   relative=value[len('/work/'):]if value.startswith('/work/')else value
   try:parts(relative)
   except Refused:raise ScopeRejected('GITEA_SCOPE_WORKSPACE_OUTPUT_PATH')from None
   path=self.workspaces[identity.role]
   for segment in relative.split('/'):
    path=path/segment;scope_need(not path.is_symlink(),'GITEA_SCOPE_OUTPUT_SYMLINK')
  for field in('issue_number','related_issue_number'):
   if args.get(field):self.known('ISSUE_NUMBER',args[field],self.repo['id'])
  if args.get('issue_id'):self.known('ISSUE_ID',args['issue_id'],self.repo['id'])
  if args.get('pull_number'):self.known('PULL',args['pull_number'],self.repo['id'])
  for field in('comment_id','commentID'):
   if args.get(field):self.known('REVIEW_COMMENT'if name=='pull_request_review_write'else'COMMENT',args[field],args.get('pull_number')if name=='pull_request_review_write'else args.get('issue_number'))
  if args.get('comment_id')and args.get('commentID'):scope_need(args['comment_id']==args['commentID'],'GITEA_SCOPE_COMMENT_ALIAS_CONFLICT')
  if args.get('review_id'):self.known('REVIEW',args['review_id'],args.get('pull_number'))
  for field,kind in(('label_id','LABEL'),('milestone','MILESTONE'),('run_id','RUN'),('job_id','JOB'),('artifact_id','ARTIFACT'),('attachment_id','ATTACHMENT_ID')):
   if args.get(field):self.known(kind,args[field])
  if args.get('attachment_uuid'):self.get('ATTACHMENT_UUID',args['attachment_uuid'])
  if args.get('project_id'):self.known('PROJECT',args['project_id'],self.category(identity,args))
  for column in list(args.get('column_ids',[]))+([args['column_id']]if args.get('column_id')else[]):self.known('COLUMN',column,args.get('project_id'))
 def check_user(self,value,expected=None):
  if type(value)is str:
   need(expected is None and value in self.usernames,'GITEA_SCOPE_NATIVE_USER');return self.usernames[value]
  need(type(value)is dict and positive(value.get('id'))and self.users.get(value['id'])==value.get('login')and(expected is None or value['id']==expected),'GITEA_SCOPE_NATIVE_USER');return value['id']
 def check_repo(self,value):need(type(value)is dict and value.get('id')==self.repo['id']and value.get('name',self.repo['name'])==self.repo['name']and value.get('full_name',self.org['name']+'/'+self.repo['name'])==self.org['name']+'/'+self.repo['name'],'GITEA_SCOPE_NATIVE_REPOSITORY')
 def pull(self,value):
  # Original pinned Go MCP v1.11.0 publishes a PR projection, NOT Issue/API
  # objects: only PR number; author/labels/milestone are names. A PR database ID
  # must never be fabricated or registered as an underlying Issue database ID.
  need(type(value)is dict and 'id'not in value,'GITEA_SCOPE_NATIVE_PULL_PROJECTION')
  number=object_id(value.get('number'))
  need(type(value.get('user'))is str,'GITEA_SCOPE_NATIVE_PULL_AUTHOR')
  self.check_user(value['user'])
  labels=value.get('labels')
  need(labels is None or type(labels)is list and all(type(v)is str for v in labels),
       'GITEA_SCOPE_NATIVE_PULL_LABEL_NAMES')
  need(value.get('milestone')is None or type(value['milestone'])is str,
       'GITEA_SCOPE_NATIVE_PULL_MILESTONE_NAME')
  if 'repository'in value:self.check_repo(value['repository'])
  self.add('ISSUE_NUMBER',number,self.repo['id'])
  self.add('PULL',number,self.repo['id'])
 def issue(self,value,*,pull=False):
  if pull:return self.pull(value)
  need(type(value)is dict,'GITEA_SCOPE_NATIVE_ISSUE');iid=object_id(value.get('id'));number=object_id(value.get('number'));self.add('ISSUE_NUMBER',number,self.repo['id']);self.add('ISSUE_ID',iid,self.repo['id'],{'number':int(number)})
  if 'repository'in value:self.check_repo(value['repository'])
  if pull or value.get('pull_request'):self.add('PULL',number,self.repo['id'])
  for label in value.get('labels')or[]:self.add('LABEL',object_id(label.get('id')),self.repo['id'])
  if value.get('milestone'):self.add('MILESTONE',object_id(value['milestone'].get('id')),self.repo['id'])
  for key in('user','assignee','merged_by'):
   if value.get(key):self.check_user(value[key])
  for user in value.get('assignees')or[]:self.check_user(user)
 def comment(self,value,kind,parent):
  need(type(value)is dict,'GITEA_SCOPE_NATIVE_COMMENT');self.add(kind,object_id(value.get('id')),parent)
  if value.get('user'):self.check_user(value['user'])
 def complete(self,identity,request,response):
  if request['method']!='tools/call':return
  name=request['params']['name'];args=request['params']['arguments'];method=args.get('method')
  # Methods without learned identifiers still used the original confined native
  # backend; do not reparse arbitrary textual success as a replacement protocol.
  if name in('compare_commits','create_commit_status','get_commit_status','rename_branch','package_read','package_write'):return
  if name=='issue_write'and method in('update','edit_comment','remove_label','clear_labels','add_dependency','remove_dependency'):return
  if name=='pull_request_write'and method!='create':return
  if name=='project_write'and method in('update','update_column'):return
  if name=='actions_run_read'and method in('get_job_log_preview','download_job_log','download_artifact'):return
  if name=='attachment_read'and method=='download':return
  if name=='pull_request_read'and method in('get_diff','get_files','get_commits','get_status'):return
  if name=='project_write'and method in('delete','delete_column','move_columns','set_default_column','add_issue','remove_issue','move_issue'):return
  if name=='pull_request_review_write'and method in('delete','dismiss','reply_comment','resolve_thread','unresolve_thread'):return
  value=native_json(response)
  if name=='get_me':
   self.check_user(value,self.roles[identity.role]);need(value.get('is_admin')is False,'GITEA_SCOPE_WORKER_ADMIN_FORBIDDEN');self.add('AUTH',value['id'],self.org['id'],{'role':identity.role})
  elif name=='create_organization':
   need(type(value)is dict,'GITEA_SCOPE_NATIVE_ORG');oid=object_id(value.get('id'));name=value.get('username',value.get('name'))
   need(name==args['username']and oid!=str(self.org['id'])and name!=self.org['name']and name not in self.usernames,'GITEA_SCOPE_NATIVE_ORG')
   self.add('ORG_ID',oid,self.pin,{'name':name});self.add('ORG_NAME',name,oid)
  elif name=='get_user_orgs':
   for org in sequence(value,'organizations','data'):
    name=org.get('username',org.get('name'))if type(org)is dict else None
    need(self.known_org(name)and org.get('id')==self.org_id(name),'GITEA_SCOPE_NATIVE_ORG')
  elif name in('list_my_repos','list_org_repos','search_repos'):
   for repo in sequence(value,'data','repositories'):self.check_repo(repo)
  elif name=='search_users':
   for user in sequence(value,'data','users'):self.check_user(user)
  elif name=='search_org_teams':
   for team in sequence(value,'data','teams'):need(type(team)is dict and self.teams.get(team.get('id'))==team.get('name'),'GITEA_SCOPE_NATIVE_TEAM')
  elif name in('list_issues','search_issues','list_pull_requests'):
   for issue in sequence(value,'issues','data','pull_requests'):self.issue(issue,pull=name=='list_pull_requests')
  elif name in('issue_read','issue_write'):
   if method in('get','create','update','add_dependency','remove_dependency'):self.issue(value)
   elif method in('get_comments',):
    for comment in sequence(value,'comments','data'):self.comment(comment,'COMMENT',args['issue_number'])
   elif method in('get_comment','add_comment','edit_comment'):self.comment(value,'COMMENT',args.get('issue_number')or self.get('COMMENT',args.get('comment_id')or args.get('commentID'))[0])
   elif method=='get_assignee_candidates':
    for user in sequence(value,'data','users'):self.check_user(user)
   elif method in('get_labels','add_labels','replace_labels'):
    for label in sequence(value,'labels','data'):self.add('LABEL',object_id(label.get('id')),self.repo['id'])
   elif method in('get_blocked_by','get_blocking'):
    for issue in sequence(value,'issues','data'):self.issue(issue)
  elif name in('pull_request_read','pull_request_write'):
   if name=='pull_request_write'or method in('get','get_by_branches','get_by_commit'):self.issue(value,pull=True)
   elif method in('get_reviews','get_review'):
    for review in([value]if method=='get_review'else sequence(value,'reviews','data')):self.add('REVIEW',object_id(review.get('id')),args['pull_number'])
   elif method in('get_review_comments','get_comments'):
    for comment in sequence(value,'comments','data'):self.comment(comment,'REVIEW_COMMENT'if method=='get_review_comments'else'COMMENT',args['pull_number'])
   elif method=='get_reviewer_candidates':
    for user in sequence(value,'users','data'):self.check_user(user)
  elif name=='pull_request_review_write':self.add('REVIEW',object_id(value.get('id')),args['pull_number'])
  elif name.startswith('project_'):
   category=self.category(identity,args)
   if method in('list','get','create','update'):
    for project in(sequence(value,'projects','data')if method=='list'else[value]):self.add('PROJECT',object_id(project.get('id')),category)
   elif method in('list_columns','create_column','update_column'):
    for column in(sequence(value,'columns','data')if method=='list_columns'else[value]):self.add('COLUMN',object_id(column.get('id')),args['project_id'])
   elif method=='list_column_issues':
    for issue in sequence(value,'issues','data'):self.issue(issue)
  elif name=='actions_run_read':
   kinds={'list_workflows':('WORKFLOW','workflows'),'get_workflow':('WORKFLOW',None),'list_runs':('RUN','workflow_runs'),'get_run':('RUN',None),'list_jobs':('JOB','jobs'),'list_run_jobs':('JOB','jobs'),'get_job':('JOB',None),'list_artifacts':('ARTIFACT','artifacts'),'list_run_artifacts':('ARTIFACT','artifacts'),'get_artifact':('ARTIFACT',None)};kind,key=kinds[method]
   for item in(sequence(value,key,'data')if key else[value]):self.add(kind,object_id(item.get('id')),self.repo['id'])
  elif name=='attachment_read':
   parent=args.get('issue_number')or(self.get('COMMENT',args['comment_id'])[0]if args.get('comment_id')else self.get('ATTACHMENT_ID',args['attachment_id'])[0])
   for item in(sequence(value,'attachments','data')if method=='list'else[value]):
    aid=object_id(item.get('id'));self.add('ATTACHMENT_ID',aid,parent);uid=item.get('uuid');need(type(uid)is str and re.fullmatch('[a-fA-F0-9-]{16,64}',uid)is not None,'GITEA_SCOPE_ATTACHMENT_UUID');self.add('ATTACHMENT_UUID',uid,aid)
  else:need(False,'GITEA_SCOPE_NATIVE_COMPLETION_UNIMPLEMENTED')
 def checkpoint_state(self):
  with self.ledger.mutex:
   rows=self.ledger.db.execute('SELECT kind,id,parent,metadata FROM gitea_scope_resources WHERE scope=?ORDER BY kind,id',(self.pin,)).fetchall();return {'schema':'agensh-native-gitea-scope-checkpoint-v1','binding_sha256':self.pin,'resources':[{'kind':r['kind'],'id':r['id'],'parent':r['parent'],'metadata':json.loads(r['metadata'])}for r in rows]}

def compile_gitea_policy(identity,guard):
 need(isinstance(guard,GiteaScope),'GITEA_SCOPE_TRUSTED_GUARD');return McpPolicy(identity,native_tools=load_native_tools('gitea'),deny_names=original_denials(),rules={name:{'kind':kind,'scope_fields':{},'native_self_scope_qualified':True}for name,kind in KINDS.items()},scope_guard=guard)

def prime_gitea(session):
 guard=session.policy.scope_guard;need(isinstance(guard,GiteaScope)and not guard.ready(session.identity),'GITEA_SCOPE_PRIME_ONCE_NO_REPLAY')
 request={'jsonrpc':'2.0','id':'owner-init','method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'count14-native-owner','version':'1'}}}
 response=session.call(request)
 session.call({'jsonrpc':'2.0','method':'notifications/initialized'})
 session.call({'jsonrpc':'2.0','id':'owner-tools','method':'tools/list','params':{}})
 session.call({'jsonrpc':'2.0','id':'owner-actor','method':'tools/call','params':{'name':'get_me','arguments':{}}})
 need(guard.ready(session.identity),'GITEA_SCOPE_PRIME_NOT_CLOSED');session.bind_worker_initialize(request,response)
 return {'schema':'agensh-native-gitea-prime-v1','binding_sha256':guard.pin,'process_scope':session.scope,'role':session.identity.role,'policy_sha256':session.policy.sha,'worker_admission_released':False,'worker_initialize':'exact verified native prime reply, no duplicate native initialize'}
