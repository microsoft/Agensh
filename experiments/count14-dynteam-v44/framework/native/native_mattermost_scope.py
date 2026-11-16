"""Fixed per-trajectory native Mattermost authorization, not a replacement tool.

No HTTP, credentials, user content logging, model calls or service administration.
The trusted bootstrap supplies the binding; NativeMcpSession still runs the real
pinned native MCP backend. Only physically completed native output may add opaque
resource identities, in the SAME Ledger transaction as operation completion.
"""
import json,re,urllib.parse
from pathlib import Path
from common import need,Refused,digest,ident,sha,wire,trajectory_id,private_dir
from native_mcp_policy import FixedScopeGuard,ScopeRejected,McpPolicy
from native_mcp_inputs import load_native_tools
from native_mcp_overlay import PUBLIC,BASE

SCHEMA='agensh-native-mattermost-scope-v1'
KINDS={
 'create_direct_channel':'CHAT_WRITE','get_channel':'CHAT_READ',
 'list_my_channels':'CHAT_READ','mark_channel_viewed':'CHAT_WRITE',
 'get_channel_messages':'CHAT_READ','post_message':'CHAT_WRITE',
 'search_messages':'CHAT_READ','add_reaction':'CHAT_WRITE','get_thread':'CHAT_READ',
 'get_me':'CHAT_READ','get_user':'CHAT_READ','get_user_by_username':'CHAT_READ',
 'search_users':'CHAT_READ',
}
def object_id(value):
 need(type(value)is str and re.fullmatch('[a-z0-9]{26}',value)is not None,'MM_SCOPE_OBJECT_ID');return value

def original_denials():
 pins={r['path']:r['sha256']for r in json.loads((BASE/'NATIVE_PUBLIC105_CONSUMED.json').read_text())['sources']}
 from common import hash_file
 path=PUBLIC/'agent/config/copilot-deny-tools.json'
 need(hash_file(path)['sha256']==pins['agent/config/copilot-deny-tools.json'],'MM_SCOPE_NATIVE_DENIALS_PIN')
 return json.loads(path.read_text())

class MattermostScope(FixedScopeGuard):
 def __init__(self,ledger,binding,expected_sha256,*,sandbox=None,sdk_identity=None):
  self.sandbox=sandbox;self.sdk_identity=sdk_identity
  need(type(binding)is dict and set(binding)=={'schema','trajectory','service_instance_sha256','bootstrap_receipt_sha256','service_origin','team_id','role_users','service_users','channels'},'MM_SCOPE_BINDING_FIELDS')
  need(binding['schema']==SCHEMA and digest(binding)==sha(expected_sha256),'MM_SCOPE_BINDING_PIN')
  trajectory_id(binding['trajectory']);sha(binding['service_instance_sha256']);sha(binding['bootstrap_receipt_sha256']);object_id(binding['team_id'])
  url=urllib.parse.urlsplit(binding['service_origin'])
  need(url.scheme in('http','https')and url.hostname and url.username is None and url.password is None and url.path in('','/')and not url.query and not url.fragment,'MM_SCOPE_FIXED_SERVICE_ORIGIN')
  self.origin=binding['service_origin'].rstrip('/')
  self.ledger=ledger;self.binding=json.loads(wire(binding));self.pin=digest(binding);self.trajectory=binding['trajectory'];self.team=binding['team_id']
  need(type(binding['role_users'])is dict and set(binding['role_users'])==set(json.loads(ledger.account(self.trajectory)['roles'])),'MM_SCOPE_EXACT_REGISTERED_ROSTER')
  need(type(binding['service_users'])is dict and type(binding['channels'])is list,'MM_SCOPE_BOOTSTRAP_RESOURCES')
  self.users={};self.names={};self.roles={};self.agents={}
  for role,user in binding['role_users'].items():
   ident(role);need(type(user)is dict and set(user)=={'id','username','agent'},'MM_SCOPE_ROLE_USER')
   ident(user['agent']);self._user(user['id'],user['username'])
   need(user['agent']not in self.agents.values(),'MM_SCOPE_NATIVE_AGENT_DUPLICATE')
   self.roles[role]=user['id'];self.agents[role]=user['agent']
  for uid,name in binding['service_users'].items():self._user(uid,name)
  need(len(self.users)<=64,'MM_SCOPE_PRINCIPAL_BOUND')
  with ledger.tx():
   ledger.db.execute('CREATE TABLE IF NOT EXISTS mm_scope_bindings(trajectory TEXT PRIMARY KEY,pin TEXT NOT NULL,binding TEXT NOT NULL)')
   ledger.db.execute('CREATE TABLE IF NOT EXISTS mm_scope_resources(scope TEXT NOT NULL,kind TEXT NOT NULL,id TEXT NOT NULL,parent TEXT NOT NULL,metadata TEXT NOT NULL,PRIMARY KEY(scope,kind,id))')
   for table in ('mm_scope_bindings','mm_scope_resources'):
    for action in ('UPDATE','DELETE'):
     ledger.db.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'append only native scope'); END")
   row=ledger.db.execute('SELECT pin FROM mm_scope_bindings WHERE trajectory=?',(self.trajectory,)).fetchone()
   if row is None:
    ledger.db.execute('INSERT INTO mm_scope_bindings VALUES(?,?,?)',(self.trajectory,self.pin,wire(binding).decode()))
    ledger.event(self.trajectory,'MM_SCOPE_BOUND',{'binding_sha256':self.pin,'service_instance_sha256':binding['service_instance_sha256'],'bootstrap_receipt_sha256':binding['bootstrap_receipt_sha256'],'roles':sorted(self.roles)})
   else:need(row['pin']==self.pin,'MM_SCOPE_SERVICE_REBIND_NO_REPLAY')
   for channel in binding['channels']:
    need(type(channel)is dict and set(channel)=={'id','team_id','type'},'MM_SCOPE_INITIAL_CHANNEL')
    self.channel(channel,bootstrap=True)
 def _user(self,uid,name):
  object_id(uid);need(type(name)is str and re.fullmatch('[a-zA-Z][a-zA-Z0-9._-]*',name)is not None and len(name)<=128,'MM_SCOPE_USERNAME')
  need(uid not in self.users and name not in self.names,'MM_SCOPE_PRINCIPAL_DUPLICATE')
  self.users[uid]=name;self.names[name]=uid
 def bind(self,identity,tools,rules):
  need(identity.trajectory==self.trajectory and identity.purpose=='mattermost'and identity.role in self.roles and identity.agent==self.agents[identity.role],'MM_SCOPE_POLICY_IDENTITY')
  need(tools==load_native_tools('mattermost')and set(rules)==set(KINDS),'MM_SCOPE_FULL_NATIVE_POLICY_REQUIRED')
  for name,rule in rules.items():need(rule=={'kind':KINDS[name],'scope_fields':{},'native_self_scope_qualified':True},'MM_SCOPE_POLICY_RULE_CHANGED')
 def backend(self,identity,command,environment,cwd):
  # The native0.5.1 client otherwise retries5xx/429 even for accepted POSTs.
  # Existing native configuration disables that without changing its source.
  need(environment.get('AGENT_NAME')==self.agents[identity.role],'MM_SCOPE_NATIVE_BACKEND_ACTOR')
  need(environment.get('MATTERMOST_MAX_RETRIES')=='0','MM_SCOPE_NATIVE_RETRIES_MUST_BE_ZERO')
  need(environment.get('MATTERMOST_AUTH_MODE')=='static_token'and environment.get('MATTERMOST_URL','').rstrip('/')==self.origin,'MM_SCOPE_NATIVE_FIXED_BACKEND')
  token=environment.get('MATTERMOST_TOKEN')
  need(type(token)is str and bool(token)and not any(c in token for c in '\x00\r\n'),'MM_SCOPE_NATIVE_PRIVATE_TOKEN')
  home=private_dir(cwd)
  need(not(home/'.env').exists()and not(home/'.env').is_symlink(),'MM_SCOPE_NO_AMBIENT_DOTENV')
  from native_mattermost_backend import ImageRuntime
  ImageRuntime.supplied().verify_command(command,home,environment,sandbox=self.sandbox,sdk_identity=self.sdk_identity)
 def ready(self,identity):
  try:return self.get('AUTH',self.roles[identity.role])[1]=={'role':identity.role}
  except ScopeRejected:return False
 def get(self,kind,oid):
  object_id(oid)
  with self.ledger.mutex:
   row=self.ledger.db.execute('SELECT parent,metadata FROM mm_scope_resources WHERE scope=? AND kind=? AND id=?',(self.pin,kind,oid)).fetchone()
  if row is None:raise ScopeRejected('MCP_FIXED_SCOPE_RESOURCE_NOT_REGISTERED')
  return row['parent'],json.loads(row['metadata'])
 def add(self,kind,oid,parent,metadata):
  # Called only within bootstrap or physical-completion Ledger transaction.
  need(self.ledger.db.in_transaction,'MM_SCOPE_RESOURCE_REQUIRES_LEDGER_TRANSACTION')
  object_id(oid);object_id(parent)
  row=self.ledger.db.execute('SELECT parent,metadata FROM mm_scope_resources WHERE scope=? AND kind=? AND id=?',(self.pin,kind,oid)).fetchone();raw=wire(metadata).decode()
  if row is not None:need(row['parent']==parent and row['metadata']==raw,'MM_SCOPE_RESOURCE_IDENTITY_CHANGED');return
  self.ledger.db.execute('INSERT INTO mm_scope_resources VALUES(?,?,?,?,?)',(self.pin,kind,oid,parent,raw))
  self.ledger.event(self.trajectory,'MM_SCOPE_RESOURCE_REGISTERED',{'binding_sha256':self.pin,'kind':kind,'id':oid,'parent':parent,'identity_sha256':digest(metadata)})
 def channel(self,value,*,bootstrap=False,direct_pair=None):
  need(type(value)is dict,'MM_SCOPE_CHANNEL_OUTPUT');cid=object_id(value.get('id'));team=value.get('team_id');kind=value.get('type')
  if kind in('O','P'):
   need(team==self.team,'MM_SCOPE_CHANNEL_CROSS_TEAM');self.add('CHANNEL',cid,self.team,{'type':kind})
  else:
   need(not bootstrap and kind=='D'and team==''and direct_pair is not None,'MM_SCOPE_DIRECT_CHANNEL_NOT_PROVEN')
   pair=sorted(direct_pair);need(value.get('name')=='__'.join(pair),'MM_SCOPE_DIRECT_PEER_IDENTITY')
   self.add('CHANNEL',cid,self.team,{'type':'D','peers':pair})
  return cid
 def user_output(self,value,expected=None):
  need(type(value)is dict,'MM_SCOPE_USER_OUTPUT');uid=object_id(value.get('id'))
  need(uid in self.users and value.get('username')==self.users[uid]and(expected is None or uid==expected),'MM_SCOPE_USER_CROSS_PRINCIPAL')
  return uid
 def post(self,value,expected_channel=None,expected_user=None):
  need(type(value)is dict,'MM_SCOPE_POST_OUTPUT');pid=object_id(value.get('id'));cid=object_id(value.get('channel_id'));self.get('CHANNEL',cid)
  need((expected_channel is None or cid==expected_channel)and value.get('user_id')in self.users and(expected_user is None or value.get('user_id')==expected_user),'MM_SCOPE_POST_CROSS_CHANNEL_OR_USER')
  files=value.get('file_ids',[]);need(type(files)is list and len(files)<=1000,'MM_SCOPE_FILE_OUTPUT_BOUND')
  self.add('POST',pid,cid,{'user_id':value['user_id']})
  for fid in files:self.add('FILE',fid,cid,{})
  return pid
 def visible_channel(self,cid,uid):
  _,meta=self.get('CHANNEL',cid)
  if meta['type']=='D'and uid not in meta['peers']:raise ScopeRejected('MCP_FIXED_SCOPE_DIRECT_MEMBERSHIP')
  return meta
 def before(self,identity,name,args):
  uid=self.roles[identity.role]
  if name!='get_me'and not self.ready(identity):raise ScopeRejected('MCP_FIXED_SCOPE_NATIVE_IDENTITY_NOT_PRIMED')
  def equal(key,wanted):
   if args.get(key)!=wanted:raise ScopeRejected('MCP_FIXED_SCOPE_ARGUMENT')
  if name in('get_channel','mark_channel_viewed','get_channel_messages','post_message'):
   self.visible_channel(args['channel_id'],uid)
  elif name in('list_my_channels','search_messages','search_users'):equal('team_id',self.team)
  elif name in('get_thread','add_reaction'):self.visible_channel(self.get('POST',args['post_id'])[0],uid)
  elif name=='get_user':
   if args['user_id']not in self.users:raise ScopeRejected('MCP_FIXED_SCOPE_PRINCIPAL')
  elif name=='get_user_by_username':
   if args['username']not in self.names:raise ScopeRejected('MCP_FIXED_SCOPE_PRINCIPAL')
  elif name=='create_direct_channel':
   pair=[args['user_id_1'],args['user_id_2']]
   if len(set(pair))!=2 or uid not in pair or not set(pair)<=set(self.roles.values()):raise ScopeRejected('MCP_FIXED_SCOPE_DIRECT_PEERS')
  elif name!='get_me':raise ScopeRejected('MCP_FIXED_SCOPE_TOOL')
  if name=='post_message':
   root=args.get('root_id')
   if root and self.get('POST',root)[0]!=args['channel_id']:raise ScopeRejected('MCP_FIXED_SCOPE_ROOT_CHANNEL')
   for fid in args.get('file_ids')or[]:
    if self.get('FILE',fid)[0]!=args['channel_id']:raise ScopeRejected('MCP_FIXED_SCOPE_FILE_CHANNEL')
 def complete(self,identity,request,response):
  if request['method']!='tools/call':return
  name=request['params']['name'];args=request['params']['arguments'];uid=self.roles[identity.role]
  result=response['result'];need(type(result)is dict,'MM_SCOPE_NATIVE_RESULT')
  if name=='mark_channel_viewed':return
  value=result.get('structuredContent');need(type(value)is dict,'MM_SCOPE_STRUCTURED_NATIVE_OUTPUT_REQUIRED')
  if name=='create_direct_channel':self.channel(value,direct_pair=[args['user_id_1'],args['user_id_2']])
  elif name=='get_channel':
   cid=object_id(value.get('id'));need(cid==args['channel_id'],'MM_SCOPE_CHANNEL_RESPONSE_ID')
   known=self.get('CHANNEL',cid)[1]
   if known['type']=='D':self.channel(value,direct_pair=known['peers'])
   else:self.channel(value)
  elif name=='list_my_channels':
   values=value.get('result');need(type(values)is list and len(values)<=10000,'MM_SCOPE_CHANNEL_LIST_OUTPUT')
   for channel in values:
    need(type(channel)is dict,'MM_SCOPE_CHANNEL_OUTPUT')
    if channel.get('type')=='D':self.channel(channel,direct_pair=self.get('CHANNEL',channel.get('id'))[1].get('peers'))
    else:self.channel(channel)
    self.visible_channel(channel['id'],uid)
  elif name in('get_channel_messages','search_messages','get_thread'):
   posts=value.get('posts');order=value.get('order');need(type(posts)is dict and len(posts)<=10000 and type(order)is list and len(order)<=len(posts)and set(order)<=set(posts),'MM_SCOPE_POST_LIST_OUTPUT')
   expected=args.get('channel_id')
   if name=='get_thread':expected=self.get('POST',args['post_id'])[0]
   for pid,post in posts.items():
    need(type(post)is dict and pid==post.get('id'),'MM_SCOPE_POST_MAP_ID');self.post(post,expected);self.visible_channel(post['channel_id'],uid)
  elif name=='post_message':self.post(value,args['channel_id'],uid)
  elif name=='add_reaction':need(value.get('post_id')==args['post_id']and value.get('user_id')==uid and value.get('emoji_name')==args['emoji_name'],'MM_SCOPE_REACTION_IDENTITY')
  elif name=='get_me':
   self.user_output(value,uid);need(type(value.get('roles'))is str and 'system_admin'not in value['roles'].split(),'MM_SCOPE_WORKER_ADMIN_FORBIDDEN')
   self.add('AUTH',uid,self.team,{'role':identity.role})
  elif name=='get_user':self.user_output(value,args['user_id'])
  elif name=='get_user_by_username':self.user_output(value,self.names[args['username']])
  elif name=='search_users':
   values=value.get('result');need(type(values)is list and len(values)<=len(self.users),'MM_SCOPE_USER_LIST_OUTPUT')
   for user in values:self.user_output(user)
  else:need(False,'MM_SCOPE_NATIVE_TOOL_UNIMPLEMENTED')
 def checkpoint_state(self):
  with self.ledger.mutex:
   rows=self.ledger.db.execute('SELECT kind,id,parent,metadata FROM mm_scope_resources WHERE scope=? ORDER BY kind,id',(self.pin,)).fetchall()
   return {'schema':'agensh-native-mm-scope-checkpoint-v1','binding_sha256':self.pin,'resources':[{'kind':r['kind'],'id':r['id'],'parent':r['parent'],'metadata':json.loads(r['metadata'])}for r in rows]}

def compile_mattermost_policy(identity,guard):
 need(isinstance(guard,MattermostScope),'MM_SCOPE_TRUSTED_GUARD_REQUIRED')
 return McpPolicy(identity,native_tools=load_native_tools('mattermost'),deny_names=original_denials(),rules={name:{'kind':kind,'scope_fields':{},'native_self_scope_qualified':True}for name,kind in KINDS.items()},scope_guard=guard)

def prime_mattermost(session):
 """Trusted owner only, before binding the worker listener or releasing SEARCH.

 No model call and no worker-selected parameters. It uses the same native
 process/notice chain and ledger custody as subsequent native business tools.
 Never retry a failed or uncertain prime; it is not a cold reconstruction path.
 """
 guard=session.policy.scope_guard
 need(isinstance(guard,MattermostScope),'MM_SCOPE_NATIVE_SESSION_REQUIRED')
 need(not guard.ready(session.identity),'MM_SCOPE_ALREADY_PRIMED_NO_REPLAY')
 session.call({'jsonrpc':'2.0','id':'host-initialize','method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'count14-native-owner','version':'1'}}})
 session.call({'jsonrpc':'2.0','method':'notifications/initialized'})
 session.call({'jsonrpc':'2.0','id':'host-tools','method':'tools/list','params':{}})
 session.call({'jsonrpc':'2.0','id':'host-identity','method':'tools/call','params':{'name':'get_me','arguments':{}}})
 need(guard.ready(session.identity),'MM_SCOPE_NATIVE_IDENTITY_PRIME_NOT_CLOSED')
 return {'schema':'agensh-native-mm-prime-v1','binding_sha256':guard.pin,'policy_sha256':session.policy.sha,'process_scope':session.scope,'role':session.identity.role,'worker_admission_released':False}
