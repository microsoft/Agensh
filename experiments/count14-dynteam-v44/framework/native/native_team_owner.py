"""Trusted native team startup. No Docker/SSH/models or worker release here.

Use *after* original bootstrap + original task-channel owner (pbench_run.sh)
completed in an OPS-owned root. Readback is not inferred from DONE or warnings.
All service credentials stay here. Native CLI/ACP/router/prompt paths are not
replaced. OPS holds workers, supplies actual peer identity, mounts exact private
outputs, qualifies the namespace fence, and only then releases original CLI.
"""
from contextlib import ExitStack
from contextlib import nullcontext
from pathlib import Path
import http.client,json,os,secrets,shutil,stat,subprocess,urllib.parse
from common import need,Refused,wire,strict,digest,sha,ident,integer,private_dir,publish,regular_fd
from bridge import process_identity
from native_mcp_overlay import build_overlay
from native_mcp_inputs import load_native_tools
from native_mcp_policy import McpIdentity,McpPolicy,board_rules
from native_mcp_bridge import NativeMcpSession,McpServer
from native_mcp_config import build_worker_config,PURPOSES
from native_mattermost_scope import MattermostScope,compile_mattermost_policy,prime_mattermost,original_denials,SCHEMA as MM_SCHEMA,object_id as mm_id
from native_gitea_scope import GiteaScope,compile_gitea_policy,prime_gitea,SCHEMA as G_SCHEMA,object_id as g_id
from native_mattermost_backend import ImageRuntime
from native_gitea_backend import build_gitea_backend
from native_git_http import NativeGitHttpBinding,NativeGitHttp,NativeGitHttpServer

class FixedRest:
 """Only host-owned fixed origins, no redirects/proxy/ambient credentials/retry.
 Responses are transient. No response body, secrets or raw exceptions journaled.
 """
 def __init__(self,origin,token,scheme):
  u=urllib.parse.urlsplit(origin);need(u.scheme=='http'and u.hostname and u.path in('','/')and not u.username and not u.password and not u.query and not u.fragment,'TEAM_NATIVE_FIXED_HTTP_ORIGIN')
  need(type(token)is str and token and not any(c in token for c in '\r\n\0')and scheme in('token','Bearer'),'TEAM_NATIVE_PRIVATE_AUTHORITY');self.u=u;self.token=token;self.scheme=scheme
 def get(self,path):
  need(type(path)is str and path.startswith('/api/')and not any(c in path for c in('\r','\n','#','?')),'TEAM_NATIVE_FIXED_REST_PATH')
  c=http.client.HTTPConnection(self.u.hostname,self.u.port,timeout=15)
  try:
   c.request('GET',path,headers={'Authorization':self.scheme+' '+self.token});r=c.getresponse();body=r.read(2**20+1)
   need(r.status==200 and len(body)<=2**20,'TEAM_NATIVE_POSTFLIGHT_HTTP_NOT200');return strict(body)
  except Refused:raise
  except Exception:raise Refused('TEAM_NATIVE_POSTFLIGHT_CUSTODY_UNKNOWN_NO_RETRY')from None
  finally:c.close()

def component(value):
 ident(value);need(value not in('.','..'),'TEAM_NATIVE_COMPONENT');return urllib.parse.quote(value,safe='')

def actor_map(roles,organization):
 need(type(roles)is list and len(roles)in(1,2,16)and roles==[f'worker-{i:02}'for i in range(len(roles))],'TEAM_NATIVE_EXACT_CANONICAL_ROSTER');ident(organization)
 return {role:f'{organization}-worker{i+1}'for i,role in enumerate(roles)}

def postflight(trajectory,roles,*,service_instance_sha256,bootstrap_receipt_sha256,organization,repository,gitea_origin,mm_origin,gitea_admin_token,mm_admin_token,role_tokens,workspaces):
 """Read-only real channel/actor/repo readback; never a fabricated bootstrap.

 Exact role tokens/workspaces are owner supplied, never worker-authored. Original
 channel stage must have run with PBENCH_WORKERS_PER_TEAM explicitly 1/2/16.
 No POST, retries, channel membership repair or task/source inspection.
 """
 sha(service_instance_sha256);sha(bootstrap_receipt_sha256);actors=actor_map(roles,organization);org=component(organization);repo=component(repository)
 need(set(role_tokens)==set(actors)and set(workspaces)==set(actors),'TEAM_NATIVE_EXACT_REGISTERED_INPUT_ROSTER')
 g=FixedRest(gitea_origin,gitea_admin_token,'token');m=FixedRest(mm_origin,mm_admin_token,'Bearer')
 organization_value=g.get('/api/v1/orgs/'+org);repository_value=g.get('/api/v1/repos/'+org+'/'+repo)
 g_id(organization_value.get('id'));g_id(repository_value.get('id'))
 need(organization_value.get('username',organization_value.get('name'))==organization and repository_value.get('name')==repository and repository_value.get('full_name')==organization+'/'+repository and repository_value.get('owner',{}).get('id')==organization_value['id'],'TEAM_NATIVE_REPOSITORY_IDENTITY')
 team=m.get('/api/v4/teams/name/'+org);mm_id(team.get('id'));need(team.get('name')==organization and not team.get('delete_at',0),'TEAM_NATIVE_TEAM_IDENTITY')
 channel=m.get('/api/v4/teams/'+team['id']+'/channels/name/pbench-task');mm_id(channel.get('id'))
 need(channel.get('name')=='pbench-task'and channel.get('type')=='P'and channel.get('team_id')==team['id']and not channel.get('delete_at',0),'TEAM_NATIVE_TASK_CHANNEL_IDENTITY')
 g_admin=g.get('/api/v1/user');g_id(g_admin.get('id'));ident(g_admin.get('login'))
 m_admin=m.get('/api/v4/users/me');mm_id(m_admin.get('id'));ident(m_admin.get('username'))
 mm_users={};g_users={};workspace_roots={}
 for role,agent in actors.items():
  tokens=role_tokens[role];need(type(tokens)is dict and set(tokens)=={'gitea','mattermost'},'TEAM_NATIVE_ROLE_TOKEN_PURPOSES')
  gu=FixedRest(gitea_origin,tokens['gitea'],'token').get('/api/v1/user');mu=FixedRest(mm_origin,tokens['mattermost'],'Bearer').get('/api/v4/users/me')
  g_id(gu.get('id'));mm_id(mu.get('id'));need(gu.get('login')==agent and gu.get('is_admin')is False and mu.get('username')==agent and not mu.get('delete_at',0)and 'system_admin'not in mu.get('roles','').split(),'TEAM_NATIVE_ACTOR_IDENTITY')
  member=m.get('/api/v4/teams/'+team['id']+'/members/'+mu['id']);need(member.get('team_id')==team['id']and member.get('user_id')==mu['id']and not member.get('delete_at',0),'TEAM_NATIVE_TEAM_MEMBER_IDENTITY')
  member=m.get('/api/v4/channels/'+channel['id']+'/members/'+mu['id']);need(member.get('channel_id')==channel['id']and member.get('user_id')==mu['id'],'TEAM_NATIVE_CHANNEL_MEMBER_IDENTITY')
  # Verify role-scoped visibility too, not only admin-side membership records.
  visible=FixedRest(mm_origin,tokens['mattermost'],'Bearer').get('/api/v4/channels/'+channel['id']);need(visible.get('id')==channel['id']and visible.get('team_id')==team['id']and visible.get('type')=='P','TEAM_NATIVE_ACTOR_CHANNEL_VISIBILITY')
  mm_users[role]={'id':mu['id'],'username':agent,'agent':agent};g_users[role]={'id':gu['id'],'username':agent,'agent':agent}
  p=Path(workspaces[role]);need(p.is_absolute()and p.resolve()==p and p.is_dir()and not p.is_symlink(),'TEAM_NATIVE_WORKSPACE');s=p.stat();workspace_roots[role]={'path':str(p),'uid':s.st_uid,'device':s.st_dev,'inode':s.st_ino}
 teams=g.get('/api/v1/orgs/'+org+'/teams');need(type(teams)is list and len(teams)<=64,'TEAM_NATIVE_GITEA_TEAMS')
 gt=[]
 for t in teams:
  # Native Gitea1.22 list projection may have organization:null; never infer
  # its parent from the /orgs/<name>/teams pathname or drop the parent guard.
  need(type(t)is dict,'TEAM_NATIVE_GITEA_TEAM_ROW');g_id(t.get('id'));ident(t.get('name'))
  listed_org=t.get('organization')
  need(listed_org is None or(type(listed_org)is dict and listed_org.get('id')==organization_value['id']),'TEAM_NATIVE_GITEA_TEAM_PARENT')
  detail=g.get('/api/v1/teams/'+str(t['id']))
  need(type(detail)is dict and detail.get('id')==t['id']and detail.get('name')==t['name'],'TEAM_NATIVE_GITEA_TEAM_DETAIL_IDENTITY')
  direct_org=detail.get('organization');need(type(direct_org)is dict and direct_org.get('id')==organization_value['id'],'TEAM_NATIVE_GITEA_TEAM_PARENT')
  gt.append({'id':t['id'],'name':t['name']})
 need(len({t['id']for t in gt})==len(gt)and len({t['name']for t in gt})==len(gt),'TEAM_NATIVE_GITEA_TEAMS_DUPLICATE')
 need(len({u['id']for u in mm_users.values()})==len(roles)and len({u['id']for u in g_users.values()})==len(roles),'TEAM_NATIVE_PRINCIPAL_DUPLICATE')
 base={'trajectory':trajectory,'service_instance_sha256':service_instance_sha256,'bootstrap_receipt_sha256':bootstrap_receipt_sha256}
 gb={**base,'schema':G_SCHEMA,'service_origin':gitea_origin,'organization':{'id':organization_value['id'],'name':organization},'repository':{'id':repository_value['id'],'name':repository},'role_users':g_users,'service_users':[{'id':g_admin['id'],'username':g_admin['login']}],'teams':gt,'workspace_roots':workspace_roots}
 mb={**base,'schema':MM_SCHEMA,'service_origin':mm_origin,'team_id':team['id'],'role_users':mm_users,'service_users':{m_admin['id']:m_admin['username']},'channels':[{'id':channel['id'],'team_id':team['id'],'type':'P'}]}
 receipt={'trajectory':trajectory,'service_instance_sha256':service_instance_sha256,'bootstrap_receipt_sha256':bootstrap_receipt_sha256,'roles':roles,'actors':actors,'gitea_binding_sha256':digest(gb),'mattermost_binding_sha256':digest(mb),'channel_name':'pbench-task','channel_id':channel['id'],'channel_type':'P','role_memberships_verified':len(roles),'read_only':True,'worker_released':False}
 return gb,mb,receipt

def trusted_peer(pid,start_ticks,uid,pidns,netns):
 integer(pid,'TEAM_PEER_PID',1);integer(start_ticks,'TEAM_PEER_START',1);integer(uid,'TEAM_PEER_UID');integer(pidns,'TEAM_PEER_PIDNS',1);integer(netns,'TEAM_PEER_NETNS',1)
 identity=process_identity(pid);need(identity['start_ticks']==start_ticks,'TEAM_PEER_PID_REUSED')
 p=Path('/proc')/str(pid);need((p/'ns/pid').stat().st_ino==pidns and(p/'ns/net').stat().st_ino==netns,'TEAM_PEER_NAMESPACE_CHANGED')
 fields={line.split(':',1)[0]:line.split(':',1)[1].split()for line in(p/'status').read_text().splitlines()if':'in line};need(fields.get('Uid')==[str(uid)]*4,'TEAM_PEER_UID_CHANGED')
 return {**identity,'uid':uid,'pid_namespace_inode':pidns,'net_namespace_inode':netns}

def trusted_front(pid,start_ticks,uid,pidns,netns,port,expected_argv):
 """Trusted PID supplied by OPS, not a worker-written ready flag/JSON.
 Bind listener inode to exact process FD and namespace before narrow firewall.
 """
 integer(port,'TEAM_FRONT_PORT',1);need(port<=65535,'TEAM_FRONT_PORT');proof=trusted_peer(pid,start_ticks,uid,pidns,netns);p=Path('/proc')/str(pid)
 need(type(expected_argv)is list and expected_argv and all(type(x)is str for x in expected_argv),'TEAM_FRONT_ARGV')
 need((p/'cmdline').read_bytes()==b'\0'.join(x.encode()for x in expected_argv)+b'\0','TEAM_FRONT_COMMAND_CHANGED')
 sockets=set()
 for fd in(p/'fd').iterdir():
  try:target=os.readlink(fd)
  except FileNotFoundError:continue
  if target.startswith('socket:['):sockets.add(target[8:-1])
 rows=[line.split()for line in(p/'net/tcp').read_text().splitlines()[1:]]
 owned=[row for row in rows if row[1]==f'0100007F:{port:04X}'and row[3]=='0A'and row[9]in sockets];need(len(owned)==1,'TEAM_FRONT_EXACT_OWNED_LOOPBACK_LISTENER')
 need(trusted_peer(pid,start_ticks,uid,pidns,netns)==proof,'TEAM_FRONT_IDENTITY_RACE')
 return {**proof,'port':port,'listen_address':'127.0.0.1','socket_inode':int(owned[0][9]),'argv_sha256':digest(expected_argv),'readiness':'PROCESS_IDENTITY_AND_OWNED_LISTENER_NOT_EGRESS_QUALIFICATION'}

class NativeTeamOwner:
 """In-process host integration for existing OPS startup, no alternate CLI.

 Caller must retain this instance and shared ledger; on failure the instance
 retains native custodial processes. No cleanup/restart of unknown work. UDS
 are private host paths; OPS either mounts existing endpoints individually or
 uses the dedicated late-published per-role transport export (never owner root).
 """
 def __init__(self,ledger,root,gitea_binding,mm_binding,*,role_tokens,peers,board_origin,board_ids,parent_tool_provider,delivery_roots=None,sandbox=None,sdk_identity=None,sdk_launches=None):
  self.ledger=ledger;self.root=private_dir(root,create=True);need(not any(self.root.iterdir()),'TEAM_OWNER_NEW_ROOT');self.gb=gitea_binding;self.mb=mm_binding;self.tokens=role_tokens;self.peers=peers;self.board_origin=board_origin;self.board_ids=board_ids;self.parent=parent_tool_provider
  need(callable(self.parent),'TEAM_OWNER_PARENT_TOOL_PROVIDER');self.t=self.gb['trajectory'];self.roles=json.loads(ledger.account(self.t)['roles']);self.actors=actor_map(self.roles,self.gb['organization']['name'])
  need(self.mb['trajectory']==self.t and self.mb['service_instance_sha256']==self.gb['service_instance_sha256']and self.mb['bootstrap_receipt_sha256']==self.gb['bootstrap_receipt_sha256'],'TEAM_OWNER_SERVICE_BINDING')
  need(set(peers)==set(self.roles)and set(role_tokens)==set(self.roles),'TEAM_OWNER_EXACT_PEERS');self.sessions={};self.listeners=[];self.configs={};self.git={};self.started=False;self.closed=False;self._stage_registry=None;self._stage_owner_identity=None;self.writer_fence=None
  from native_sandbox import admitted_sandbox
  self.sandbox=admitted_sandbox(sandbox);self.sdk_identity=sdk_identity
  if sdk_identity is not None:
   from native_sandbox import NativeSdkIdentity
   need(type(sdk_identity)is NativeSdkIdentity,'SDK_UID_HOST_ADMISSION_OBJECT');sdk_identity.verify()
   need(all(sdk_identity.uid==v['uid']for v in self.gb['workspace_roots'].values()),'SDK_UID_PEER_WORKSPACE_BINDING')
  self.delivery_roots=delivery_roots
  if delivery_roots is not None:
   from native_delivery import delivery_dir
   need(type(delivery_roots)is dict and set(delivery_roots)==set(self.roles),'TEAM_OWNER_DELIVERY_ROLES')
   for value in delivery_roots.values():need(not any(delivery_dir(value).iterdir()),'TEAM_OWNER_DELIVERY_NEW_EMPTY')
   values=[Path(v)for v in delivery_roots.values()];need(len(set(values))==len(values)and all(a not in b.parents for a in values for b in values if a!=b),'TEAM_OWNER_DELIVERY_DISTINCT')
  self.sdk_launches=sdk_launches
  if sdk_launches is not None:
   from native_cgroup_launch import NativeCgroupLaunch
   need(type(sdk_launches)is dict and set(sdk_launches)==set(self.roles)
        and all(type(v)is NativeCgroupLaunch for v in sdk_launches.values()),'TEAM_OWNER_EXACT_SDK_LAUNCH_ROSTER')
   need(len({v.binding_sha for v in sdk_launches.values()})==len(self.roles),'TEAM_OWNER_DISTINCT_ROLE_SDK_DOMAINS')
   self.sdk_launches=dict(sdk_launches)
   for launch in self.sdk_launches.values():launch.current()
 def start(self):
  need(not self.started,'TEAM_OWNER_START_ONCE_NO_RETRY');self.started=True
  try:
   build_overlay(self.root/'overlay');gg=GiteaScope(self.ledger,self.gb,digest(self.gb),sandbox=self.sandbox,sdk_identity=self.sdk_identity);mg=MattermostScope(self.ledger,self.mb,digest(self.mb),sandbox=self.sandbox,sdk_identity=self.sdk_identity);node=str(Path(shutil.which('node')or'').resolve());need(Path(node).is_file(),'TEAM_OWNER_NODE')
   env={'PATH':'/usr/bin:/bin','BOARD_IDS':','.join(self.board_ids),'AGENT_NAME':self.actors[self.roles[0]],'BOARD_SERVICE_URL':self.board_origin}
   # Original board tools/list is pure declaration handling, not service HTTP.
   r=subprocess.run([node,str(self.root/'overlay/mcp-board.cjs')],input=wire({'jsonrpc':'2.0','id':'owner-declarations','method':'tools/list','params':{}})+b'\n',stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env,timeout=10,check=True);tools=strict(r.stdout)['result']['tools']
   for role in self.roles:
    peer=self.peers[role];trusted_peer(**peer);need(peer['uid']==self.gb['workspace_roots'][role]['uid'],'TEAM_OWNER_WORKSPACE_UID');agent=self.actors[role];home=private_dir(self.root/role,create=True);delivery=Path(self.delivery_roots[role])if self.delivery_roots is not None else home;policies={};sockets={};ss={}
    for purpose in PURPOSES:
     identity=McpIdentity(self.t,role,self.ledger.account(self.t)['generation'],purpose,agent,peer['uid'],peer['pidns'],secrets.token_hex(32))
     if purpose=='gitea':
      policy=compile_gitea_policy(identity,gg);command,environment,_=build_gitea_backend(self.root/'overlay',Path(self.gb['workspace_roots'][role]['path']),origin=self.gb['service_origin'],token=self.tokens[role]['gitea'],agent=agent,board_origin=self.board_origin,sandbox=self.sandbox,sdk_identity=self.sdk_identity)
     elif purpose=='mattermost':
      policy=compile_mattermost_policy(identity,mg);command,environment,_=ImageRuntime.supplied().command(self.root/'overlay',home,origin=self.mb['service_origin'],token=self.tokens[role]['mattermost'],agent=agent,board_origin=self.board_origin,sandbox=self.sandbox,sdk_identity=self.sdk_identity)
     else:
      policy=McpPolicy(identity,native_tools=tools,deny_names=original_denials(),rules=board_rules(self.board_ids));environment={**env,'AGENT_NAME':agent};command=[node,str(self.root/'overlay/mcp-notice-shim.cjs'),'--',node,str(self.root/'overlay/mcp-board.cjs')]
     session=NativeMcpSession(policy,self.ledger,command=command,environment=environment,cwd=home,parent_tool_provider=self.parent,preexec_domain=None if self.sdk_launches is None else self.sdk_launches[role]);self.sessions[(role,purpose)]=session;policies[purpose]=policy
     if purpose in ('gitea','mattermost'):
      from native_model_tool_parent import NativeModelToolParents
      with self.parent.identity_prime(session)if type(self.parent)is NativeModelToolParents else nullcontext():
       if purpose=='gitea':prime_gitea(session)
       else:prime_mattermost(session)
     else:
      session.call({'jsonrpc':'2.0','id':'owner-board-tools','method':'tools/list','params':{}})
     ss[purpose]=session;sockets[purpose]=delivery/(purpose+'.sock')
    config,denials,receipt=build_worker_config(policies,{p:(Path('/run/count14/transport')if self.delivery_roots is not None else Path('/run/count14'))/(p+'.sock')for p in PURPOSES},timeout_ms=180000)
    publish(delivery/'mcp.json.tmpl',wire(config),mode=0o400);publish(delivery/'copilot-deny-tools.json',wire(denials),mode=0o400);publish(delivery/'placeholder.token',b'count14-no-backend-authority\n',mode=0o400)
    capability=secrets.token_hex(32);publish(delivery/'git.capability',capability.encode()+b'\n',mode=0o400)
    for name in('mcp.json.tmpl','copilot-deny-tools.json','placeholder.token','git.capability'):
     if peer['uid']!=os.geteuid():os.chown(delivery/name,peer['uid'],-1)
    gb=NativeGitHttpBinding(self.t,role,self.ledger.account(self.t)['generation'],peer['uid'],peer['pidns'],capability,self.gb['service_instance_sha256'],self.gb['bootstrap_receipt_sha256'],self.gb['service_origin'],self.gb['organization']['name'],self.gb['repository']['name'],self.gb['role_users'][role]['username'])
    broker=NativeGitHttp(gb,self.ledger,home/'git-private',token=self.tokens[role]['gitea'],parent_tool_provider=self.parent);self.git[role]=broker
    self.configs[role]={'config':receipt,'sockets':sockets,'sessions':ss,'home':home,'delivery':delivery,'git_path':delivery/'git.sock'}
   # NO listener is exposed before all roles have passed native prime/readback.
   for role in self.roles:
    c=self.configs[role]
    for purpose in PURPOSES:
     server=McpServer(c['sockets'][purpose],c['sessions'][purpose],**({'late_delivery':True}if self.delivery_roots is not None else{}));self.listeners.append(server);server.start()
    server=NativeGitHttpServer(c['git_path'],self.git[role],**({'late_delivery':True}if self.delivery_roots is not None else{}));self.listeners.append(server);server.start()
   from native_stage_binding import register_native_team_ports
   register_native_team_ports(self)
   if self.delivery_roots is not None:
    from native_delivery import complete_delivery
    for path in self.delivery_roots.values():complete_delivery(path)
   receipt={'trajectory':self.t,'service_instance_sha256':self.gb['service_instance_sha256'],'bootstrap_receipt_sha256':self.gb['bootstrap_receipt_sha256'],'actors':self.actors,'native_sessions':len(self.sessions),'sandbox_executable':self.sandbox.verify(),'native_gitea_scope':gg.pin,'native_mm_scope':mg.pin,'worker_configs':{r:self.configs[r]['config']for r in self.roles},'worker_released':False,'transport_exports':{r:{'path':str(self.configs[r]['delivery']),'device':self.configs[r]['delivery'].stat().st_dev,'inode':self.configs[r]['delivery'].stat().st_ino}for r in self.roles}if self.delivery_roots is not None else{},'requires_ops':'exact per-role binds, placeholder-only credentials, original ACP/router/CLI, front PID/start/netns/port proof + namespace fence before release'}
   publish(self.root/'OWNER_COMPONENT_READY.json',wire(receipt),mode=0o400);return receipt
  except Exception:
   self.ledger.latch_fault(self.t,'TEAM_OWNER_STARTUP_FAILED_RETAIN_CUSTODY_NO_RETRY');raise
 def register_writer_domains(self,domains,*,expected_domains_sha256,whole_team=None):
  # Startup only: actual pre-exec domain provenance comes from original OPS
  # launcher. Register ALL workers and SDKs; no late PID migration is permitted.
  from native_writer_fence import NativeWriterFence
  need(self.writer_fence is None,'TEAM_OWNER_WRITER_DOMAINS_ONCE')
  with self.ledger.mutex:
   need(self.ledger.frontier(self.t)['state']=='RUNNING' and self.ledger.db.execute('SELECT COUNT(*)FROM requests WHERE trajectory=?',(self.t,)).fetchone()[0]==0,'TEAM_OWNER_WRITER_DOMAINS_BEFORE_FIRST_MODEL')
   fence=NativeWriterFence(self,domains,expected_domains_sha256=expected_domains_sha256,whole_team=whole_team)
   with self.ledger.tx():self.ledger.event(self.t,'NATIVE_WRITER_SCOPES_STARTUP_REGISTERED',{'domains_sha256':fence.domains_sha,'participants_sha256':digest(fence.participants),'domains':len(fence.domains)})
   self.writer_fence=fence
   if whole_team is not None:
    for broker in self.git.values():broker.whole_team=whole_team
   return fence
 def close_drained(self):
  # Use the same port->ledger lock order as accepted work and stage prepare.
  # Seal every local admission while still holding those locks, THEN stop
  # listeners outside them so pending handler threads cannot deadlock close.
  with ExitStack()as locks:
   for key in sorted(self.sessions):locks.enter_context(self.sessions[key].lock)
   for role in sorted(self.git):locks.enter_context(self.git[role].lock)
   locks.enter_context(self.ledger.mutex)
   if self.closed:return
   if self.writer_fence is not None:
    need(self.writer_fence.state in('REGISTERED','RELEASED','RETIREMENT_RELEASED')and all(not d.frozen()and d.read('cgroup.freeze').strip()=='0'for d in self.writer_fence.domains),'TEAM_OWNER_WRITER_PARK_RETAIN_CONTROL_NO_EOF_DEADLOCK')
   f=self.ledger.frontier(self.t)
   need(f['unresolved']==f['reserved']==f['active_operations']==0,'TEAM_OWNER_NOT_DRAINED_NO_CANCEL')
   need(all(not s.broken and not s.pending for s in self.sessions.values())and all(not g.children for g in self.git.values()),'TEAM_OWNER_NOT_DRAINED_NO_CANCEL')
   for session in self.sessions.values():session.closing=True
   for broker in self.git.values():broker.closing=True
  for server in self.listeners:server.close_listener()
  for session in self.sessions.values():session.close_when_drained()
  self.closed=True
