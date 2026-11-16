"""Unique OPS native Docker/process lifecycle for the fixed scientific six.
No alternate science loop, scores, provider dispatch, candidate inspection or
ledger construction. The developer driver owns all scientific state machines.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_BOOT = _count14_os.environ.get('COUNT14_HOST_BOOT_ID', '00000000-0000-0000-0000-000000000000')
_C14_FS_UUID = _count14_os.environ.get('COUNT14_SCRATCH_FS_UUID', '00000000-0000-0000-0000-000000000000')
_C14_HOSTNAME = _count14_os.environ.get('COUNT14_HOSTNAME', 'count14-host')
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
import datetime,hashlib,http.client,ipaddress,json,os,re,secrets,socket,stat,subprocess,sys,time,urllib.request,urllib.parse,uuid
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
from whole_team_backend_inventory import collect,root_identity,process
from prepare_scientific_backend_infra import parameters,BOOTSTRAP
from prepare_first_scientific_backend_infra_once import network_plan
D=['docker','--host','unix:///var/run/docker.sock']
PREFIX=Path((_C14_SCRATCH + '/agensh-comparison-20261026/v2-20261028-a3'))
BOOT=(_C14_BOOT)
SYSTEM='0ca0fc69-5a6f-4b60-abd7-9282fd010ff2'
WORKER_IMAGE='sha256:72c6cce8ffe798d89ea17930426455f948185c9db0085eb3c1ee145bc36844b2'
ROUTER_IMAGE='sha256:c3f2fb108890a38b22b320a5cdcf3427752a8d59002c1260fddd72885e191a66'
SDK_IMAGE='sha256:4cea12ab7d78a3312c85f8cab19b6971d4fe9704da25443986c0bc20a6678850'
CLI_EXE='70ae61d651bbb35126900627ade8dff29fcb8638459a101062b010281afbbc4e'
BWRAP_SHA='e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71'
SHIM_SHA='0fbd3a9c652a4c416791adc797f551f93dc266851c857a65b3b7004d9b0c4fa7'
STATE={};CONF=None;SEQ=0

def need(ok,code):
 if not ok:raise ValueError(code)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def wire(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(v):return hashlib.sha256(wire(v)).hexdigest()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb')as f:os.fchmod(f.fileno(),0o600);f.write(wire(v)+b'\n');f.flush();os.fsync(f.fileno())
def call(argv,*,data=None,timeout=60):
 p=subprocess.run(argv,input=data,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=timeout)
 need(p.returncode==0,'OPS_PUBLIC_COMMAND_EXIT');return p.stdout

def inspect(cid):
 # Raw env/config are never written or printed. Only fixed fields are retained.
 z=json.loads(call(D+['inspect',cid]))[0]
 need(z['Id']==cid,'EXACT_CONTAINER_ID');return z

def config():
 global CONF
 if CONF is not None:return CONF
 p=BASE/'OPS_HOST_CONFIGURATION.json';s=p.lstat()
 need(p.resolve()==p and stat.S_ISREG(s.st_mode)and s.st_uid==0 and stat.S_IMODE(s.st_mode)==0o600 and s.st_nlink==1,'OPS_TRUSTED_CONFIG')
 c=json.loads(p.read_bytes());need(c['schema']=='agensh-ops-fixed-native-host-v1','OPS_CONFIG_SCHEMA')
 need(c.get('manifest_root')==(_C14_SCRATCH + '/ag28v2a3')and c.get('repository')=='main-v2-a3','EXACT_NEW_SCIENTIFIC_ROOT_REPOSITORY')
 need(os.geteuid()==0 and os.uname().nodename==(_C14_HOSTNAME)and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'EXACT_HOST_BOOT')
 need(call(['findmnt','-n','-o','UUID','--target',(_C14_SCRATCH)]).decode().strip()==(_C14_FS_UUID),'MOUNT_UUID')
 need(call(D+['info','--format','{{.ID}} {{.DockerRootDir}}']).decode().strip()==SYSTEM+' /var/lib/docker','SYSTEM_DOCKER_ONLY')
 # Public host closure, not any opaque scientific or credential material.
 for name,pin in c['host_files'].items():
  q=BASE/name;need(q.resolve()==q and q.is_file()and sha(q)==pin,'OPS_HOST_FILE_PIN')
 CONF=c;return c

def setting(row):
 n=int(row['setting'].split('-')[-1]);b=row['block']
 need(n in(1,16)and b in(1,2,3)and row['roles']==[f'worker-{i:02d}'for i in range(n)],'FIXED_PAIRED_TEAM_ROSTER')
 return parameters(n,b)

def fp8_inflight(raw):
 rows=[]
 for l in raw.decode('utf-8','strict').splitlines():
  if not l.startswith('smg_gateway_model_request_inflight{'):continue
  labels,value=l.rsplit('}',1)
  matches=re.findall(r'(?:^|[,\{])(?:model|model_name|model_id)="([^"]+)"',labels)
  if matches and matches[0]in('GLM-5.3-FP8','zai-org/GLM-5.3-FP8','VLLM-GATEWAY-GLM-5.3-FP8'):
   v=float(value.strip());need(v>=0 and v.is_integer(),'FP8_GAUGE_NONNEGATIVE_INT');rows.append(int(v))
 need(len(rows)==1,'EXACT_FP8_GAUGE_REQUIRED_NO_ZERO_INFERENCE');return rows[0]

def admit(row,phase):
 global SEQ
 c=config();available=int(next(l.split()[1]for l in Path('/proc/meminfo').read_text().splitlines()if l.startswith('MemAvailable:')))*1024
 # Real observation only. Do not retry inference/metadata or infer absent gauge0.
 req=urllib.request.Request(c['gateway_base'].rstrip('/')+'/metrics',headers={'User-Agent':'count14-ops-readonly-admission'})
 try:
  with urllib.request.urlopen(req,timeout=10)as response:raw=response.read(2**20+1);need(response.status==200 and len(raw)<=2**20,'METRICS_HTTP_BOUND')
  inflight=fp8_inflight(raw)
 except Exception:return None
 reserve=64*2**30
 # Actual-first planning, not the sum of hypothetical worker+6K upper bounds.
 next_planning=0 if row is None or phase not in('new-trajectory',)else len(row['roles'])*512*2**20+4*2**30
 headroom=c.get('initial_admission_headroom',c['planned_search_and_aux_cap'])if phase=='initialize-shared'else (len(row['roles'])if row is not None and phase in('new-trajectory','release-search')else 1)
 allowed=available>=reserve+next_planning and inflight+headroom<=96
 if not allowed:return None
 SEQ+=1
 g={'at':now(),'HTTP':200,'body_sha256':hashlib.sha256(raw).hexdigest(),'FP8_only_inflight':inflight,'model_calls':0}
 a={'at':g['at'],'phase':phase,'trajectory':None if row is None else row['trajectory_id'],'memory_available_bytes':available,'reserve_bytes':reserve,'new_team_planning_bytes':next_planning,'shared_FP8_max':96,'own_planned_search_and_aux_cap':c['planned_search_and_aux_cap'],'new_admission_headroom':headroom,'observed_global_FP8_inflight':inflight,'authorized_user_instruction_sha256':c['authorization_sha256']}
 save(BASE/'admissions'/f'{os.getpid()}-{SEQ:08d}.json',{'gateway':g,'allocation':a})
 return {'current_owner_authorized':True,'gateway_health_sha256':digest(g),'allocation_sha256':digest(a)}

def api(origin,method,path,*,token=None,body=None,scheme='Bearer'):
 u=urllib.parse.urlsplit(origin);need(u.scheme=='http'and u.hostname and path.startswith('/api/'),'FIXED_LOCAL_API')
 conn=http.client.HTTPConnection(u.hostname,u.port,timeout=30)
 try:
  headers={'Accept':'application/json','Connection':'close'}
  if token:headers['Authorization']=scheme+' '+token
  payload=None if body is None else wire(body)
  if payload is not None:headers['Content-Type']='application/json'
  conn.request(method,path,body=payload,headers=headers);r=conn.getresponse();data=r.read(2**20+1);need(len(data)<=2**20,'LOCAL_METADATA_BOUND')
  return r.status,{}if not data else json.loads(data),r.getheader('Token')
 finally:conn.close()

def channel_setup(record,roles,tokens,env):
 """Original pbench private task channel and memberships, no task/model."""
 root=record['layout'];origin=record['origins']['mattermost'];org=record['p']['organization'];journal=root/'TASK_CHANNEL_OWNER_EVENTS.jsonl'
 def request(method,path,**kw):
  if method=='POST':
   with journal.open('ab')as f:f.write(wire({'at':now(),'phase':'DISPATCHED','method':method,'path':path})+b'\n');f.flush();os.fsync(f.fileno())
  v=api(origin,method,path,**kw)
  if method=='POST':
   with journal.open('ab')as f:f.write(wire({'at':now(),'phase':'HTTP_TERMINAL','method':method,'path':path,'HTTP':v[0]})+b'\n');f.flush();os.fsync(f.fileno())
  return v
 st,_,admin=request('POST','/api/v4/users/login',body={'login_id':env['MATTERMOST_ADMIN_USER'],'password':env['MATTERMOST_ADMIN_PASSWORD']});need(st==200 and admin,'MM_LOGIN_NO_RETRY')
 st,team,_=request('GET','/api/v4/teams/name/'+org,token=admin);need(st==200 and team.get('name')==org and re.fullmatch('[a-z0-9]{26}',team.get('id','')),'EXACT_MM_TEAM')
 tid=team['id'];st,ch,_=request('GET',f'/api/v4/teams/{tid}/channels/name/pbench-task',token=admin)
 if st==404:
  need(ch.get('status_code')==404 and ch.get('id')in('app.channel.get_by_name.missing.app_error','store.sql_channel.get_by_name.missing.app_error'),'EXACT_MISSING_PRIVATE_CHANNEL')
  st,ch,_=request('POST','/api/v4/channels',token=admin,body={'team_id':tid,'name':'pbench-task','display_name':'pbench task','type':'P'});need(st in(200,201),'PRIVATE_CHANNEL_POST_NO_RETRY')
 need(st in(200,201)and ch.get('team_id')==tid and ch.get('name')=='pbench-task'and ch.get('type')=='P','EXACT_PRIVATE_TASK_CHANNEL');chid=ch['id']
 members=[]
 for role in roles:
  token=tokens[role]['mattermost'];st,u,_=request('GET','/api/v4/users/me',token=token);need(st==200 and u['username']==record['actors'][role],'EXACT_MM_ROLE')
  uid=u['id'];st,member,_=request('GET',f'/api/v4/channels/{chid}/members/{uid}',token=admin)
  if st==404:st,member,_=request('POST',f'/api/v4/channels/{chid}/members',token=admin,body={'user_id':uid});need(st in(200,201),'MEMBERSHIP_POST_NO_RETRY')
  need(st in(200,201)and member.get('channel_id')==chid and member.get('user_id')==uid,'EXACT_CHANNEL_MEMBER')
  st,visible,_=request('GET','/api/v4/channels/'+chid,token=token);need(st==200 and visible['id']==chid and visible['type']=='P','ROLE_PRIVATE_CHANNEL_VISIBLE')
  members.append({'role':role,'user_id':uid})
 save(root/'ORIGINAL_PRIVATE_TASK_CHANNEL_READY.json',{'at':now(),'team_id':tid,'channel_id':chid,'type':'P','roles':members,'model_calls':0})
 record.update(mm_admin_token=admin,task_channel=chid);return admin

def _worker_bridge(p):
 # Generated runtime names use the SAME frozen current scope as the root guard.
 # Never inherit an old literal bridge from a retained prior owner.
 name=Path(config()['manifest_root']).name+f"s{p['workers']}b{p['block']}w"
 need(re.fullmatch('[a-zA-Z0-9_]{1,15}',name)is not None,'EXACT_CURRENT_SCOPE_BRIDGE_LIMIT')
 return name

def backend(row,layout):
 c=config();p=setting(row);R=p['root'];layout=Path(layout);need(layout.resolve()==layout and layout.is_relative_to(Path(c['manifest_root']))and layout==Path(row['root']),'OWN_DRIVER_ROW_ROOT')
 files=[R/'BACKEND_PREPARATION_PASS_NOT_SCIENTIFIC_ACTIVATION.json',R/'BACKEND_PREPARATION_PASS_NOT_SCIENTIFIC_ACTIVATION_V2.json']
 chosen=next((x for x in reversed(files)if x.is_file()),None);need(chosen is not None,'BACKEND_NOT_READY_NO_DUPLICATE_START')
 proof=json.loads(chosen.read_bytes());need(proof['root']==str(R)and proof['organization']==p['organization']and proof['workers']==p['workers']and proof['models']==0,'EXACT_REGISTERED_BACKEND')
 rows=proof['backend_services'];need(len(rows)==8,'EXACT_BACKEND8')
 services={x['service']:x for x in rows};origins={}
 for service,port in(('gitea',3000),('mattermost',8065),('board-service',8660)):
  z=inspect(services[service]['id']);need(z['State']['Running']and z['Image']==services[service]['image']and z['Config']['Labels']['org.cybergym.agensh.comparison.root']==str(R),'BACKEND_CURRENT_OWN_LIVE')
  need(set(z['NetworkSettings']['Networks'])=={proof['network']['name']},'BACKEND_EXACT_INTERNAL_NET')
  origins[{'board-service':'board'}.get(service,service)]='http://'+z['NetworkSettings']['Networks'][proof['network']['name']]['IPAddress']+':'+str(port)
 env=dict(l.split('=',1)for l in(R/'run/private.env').read_text().splitlines()if l and not l.startswith('#'))
 from native_team_owner import actor_map
 actors=actor_map(row['roles'],p['organization']);tokens={role:{'gitea':(R/'run/data/tokens'/('agent-'+actor+'.token')).read_text().strip(),'mattermost':(R/'run/data/tokens'/('agent-'+actor+'-mm.token')).read_text().strip()}for role,actor in actors.items()}
 subnet,checked=network_plan();netname=p['project']+'-workers-'+secrets.token_hex(4);bridge=_worker_bridge(p)
 nid=call(D+['network','create','--driver','bridge','--internal','--subnet',subnet,'--opt','com.docker.network.bridge.name='+bridge,'--label','org.cybergym.agensh.comparison.root='+str(layout),netname]).decode().strip()
 n=json.loads(call(D+['network','inspect',nid]))[0];need(n['Internal']and n['Name']==netname and not n['Containers'],'WORKER_NET_ONLY_INTERNAL_NEW');gateway=n['IPAM']['Config'][0]['Gateway']
 with socket.socket()as s:s.bind((gateway,4180))
 network={'id':nid,'name':netname,'subnet':subnet,'gateway':gateway,'internal':True,'occupied_routes_checked':checked}
 save(layout/'WORKER_NETWORK_ORIGINAL_CREATE.json',{'at':now(),**network,'models':0})
 record={'repository':c['repository'],'row':row,'layout':layout,'p':p,'backend_proof':proof,'backend_proof_path':chosen,'origins':origins,'env':env,'actors':actors,'tokens':tokens,'network':network,'worker_rows':[],'sdk_capsules':[],'router_rows':[]};STATE[row['trajectory_id']]=record
 admin=channel_setup(record,row['roles'],tokens,env)
 bproof=R/'BOOTSTRAP_REUSED_ORIGINAL_IMAGE.json'
 return {'organization':p['organization'],'repository':record['repository'],'admin_username':env['GITEA_ADMIN_USER'],'writers_team':'coders','service_instance_sha256':digest(proof),'bootstrap_receipt_sha256':sha(bproof),'gitea_origin':origins['gitea'],'mm_origin':origins['mattermost'],'gitea_admin_token':(R/'run/data/tokens/admin.token').read_text().strip(),'mm_admin_token':admin,'role_tokens':tokens,'board_origin':origins['board'],'board_ids':['pbench-top'],'repository_root':str(R/'run/data/gitea/git/repositories'/p['organization']/(record['repository']+'.git')),'relay_listen':(gateway,4180)}

def capsule(cid,root,kind):
 z=inspect(cid);need(z['State']['Running'],'CAPSULE_LIVE_CONTAINER');original=process(z['State']['Pid']);lines=[l[3:]for l in Path('/proc',str(original['pid']),'cgroup').read_text().splitlines()if l.startswith('0::')];need(len(lines)==1,'CGROUP2_SINGLE')
 rel=lines[0];p=Path('/sys/fs/cgroup')/rel.lstrip('/');s=p.lstat();need(p.resolve()==p and p!=Path('/sys/fs/cgroup')and s.st_uid==0 and not s.st_mode&0o022,'OWN_CANONICAL_CGROUP')
 result={'at':now(),'id':cid,'kind':kind,'anchor':original,'directory':str(p),'relative':rel,'device':s.st_dev,'inode':s.st_ino,'owner_uid':s.st_uid,'image':z['Image']};dest=root/(kind+'-CAPSULE.json');save(dest,result);result['provenance_sha256']=sha(dest);return result

def domain(c):
 from common import digest as original_digest
 from native_writer_fence import CgroupV2Domain
 b={'schema':'agensh-native-owned-writer-cgroup-v1',**{k:c[k]for k in('relative','device','inode','owner_uid')},'launch_receipt_sha256':c['provenance_sha256']}
 return CgroupV2Domain(c['directory'],launch_receipt_sha256=c['provenance_sha256'],expected_binding_sha256=original_digest(b))

def inventory(team,workers,backend):
 record=STATE[team.t];rows=record['backend_proof']['backend_services'];rename={'gitea':'gitea','mattermost':'mattermost','mysql':'backend-mysql','secret-service':'backend-secret','nginx-edge':'backend-edge','board-service':'backend-board'}
 services={rename[v['service']]:{'container_id':v['id'],'image_id':v['image']}for v in rows if v['service']in rename}
 for r in record['router_rows']:services['backend-router-'+r['role']]={'container_id':r['id'],'image_id':ROUTER_IMAGE}
 inv=collect({'schema':'ops-exact-team-backend-inventory-config-v1','boot_id':BOOT,'trajectory_root':str(PREFIX.parent),'extra_mount_root':config()['manifest_root'],'services':services})
 save(record['layout']/'ACTUAL_COMPLETE_WHOLE_TEAM_INVENTORY.json',inv)
 domains=[]
 for name,b in services.items():domains.append(domain(capsule(b['container_id'],record['layout'],'backend-'+name)))
 for r in record['worker_rows']:domains.append(domain(r['capsule']))
 for r in record['sdk_capsules']:domains.append(domain(r))
 return {'services':inv['services'],'backend_names':inv['backend_names'],'writer_domains':domains}

# Remaining original lifecycle methods are defined below. No dispatch occurs on
# import; incomplete host closure is never a scientific activation receipt.

def _mkdir(p,mode,uid=0,gid=0):
 p=Path(p);p.mkdir(parents=True,exist_ok=False,mode=mode);p.chmod(mode);os.chown(p,uid,gid);return p

def _copy_public(src,dst,pin=None,mode=0o444):
 import shutil
 src=Path(src);dst=Path(dst);need(src.is_file()and not src.is_symlink(),'PUBLIC_REGULAR_SOURCE')
 if pin:need(sha(src)==pin,'PUBLIC_SOURCE_PIN')
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);dst.chmod(mode);need(sha(src)==sha(dst),'PUBLIC_COPY_CHANGED');return dst

def _own_generated_git_config(workspace):
 # Root-run git remote setup atomically rewrites this one private file AFTER
 # the original workspace chown. Restore only its intended role ownership;
 # never broaden permissions or recursively alter source/mtime.
 fd=os.open(Path(workspace)/'.git/config',os.O_RDONLY|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd);need(stat.S_ISREG(st.st_mode)and stat.S_IMODE(st.st_mode)==0o600,'EXACT_PRIVATE_GENERATED_GIT_CONFIG')
  os.fchown(fd,10000,10000)
 finally:os.close(fd)

def workers(row,layout,bootstrap_root,delivery_roots,launch):
 c=config();record=STATE[row['trajectory_id']];layout=Path(layout);boot=Path(bootstrap_root);root=_mkdir(layout/'host-workers',0o700)
 need(set(launch.startup_bindings)==set(row['roles']),'DRIVER_EXACT_ROLE_STARTUP_HOLD')
 from native_worker_launch import install_worker_code,worker_waiting_replacement
 from native_sandbox import SandboxBinary,NativeSdkIdentity
 from native_sdk_public_runtime import admitted_public_root
 from native_cgroup_launch import NativeCgroupLaunch
 from native_team_owner import trusted_peer
 from common import digest as original_digest
 code=root/'transport-code';install_worker_code(code)
 # Original validated code remains immutable. Individual binds avoid trying to
 # create a new receipt-module leaf under the existing readonly directory bind.
 source=record['p']['root']/'source';owned=_mkdir(root/'original-public',0o755)
 entry=_copy_public(source/'agent/entrypoint.sh',owned/'entrypoint.sh',mode=0o555)
 acpbase=Path(c['qualified_acp_shutdown_root'])
 for name,pin in [('acp-bridge.py','0e28e24650036617c07c9a5ad16c64725f51789d0775036ccd5f920632f484e9'),('acp_child_custody.py','1bfa7bf4cb982bab79a504b2381af60135edf327f0c3a176332b2ae131542368')]:_copy_public(acpbase/name,owned/name,pin,mode=0o555 if name=='acp-bridge.py'else 0o444)
 _copy_public(acpbase/'archive.py',owned/'archive.py')
 for rel,name in(('prompts/agents.txt','agents.md'),('prompts/pbench-brief.txt','pbench-brief.md')):_copy_public(source/rel,owned/name)
 overlay=Path(c['qualified_current_cli_overlay']);need(sha(overlay/'app.js')==c['cli_overlay_app_sha256']and sha(overlay/'native_cli_tool_receipt.mjs')==c['cli_overlay_client_sha256'],'CURRENT_CALLBACK_OVERLAY_PIN')
 wrapper=overlay/'copilot-wrapped';ws=wrapper.lstat()
 need(not wrapper.is_symlink()and stat.S_ISREG(ws.st_mode)and ws.st_uid==0 and stat.S_IMODE(ws.st_mode)==0o555 and ws.st_nlink==1 and sha(wrapper)==c['cli_overlay_wrapper_sha256'],'CURRENT_NATIVE_EXEC_WRAPPER_PIN_MODE_OWNER')
 for im in(WORKER_IMAGE,SDK_IMAGE,ROUTER_IMAGE):need(call(D+['image','inspect','--format','{{.Id}}',im]).decode().strip()==im,'IMMUTABLE_ORIGINAL_IMAGE')
 peers={};roles={};contexts={};launches={};fronts={};record['root']=root
 for i,role in enumerate(row['roles']):
  parent=_mkdir(root/role,0o700);paths={}
  # The bootstrap already made exact independent source-only working copies.
  workspace=boot/'workers'/role;need(workspace.is_dir()and not workspace.is_symlink(),'EXACT_BOOTSTRAP_WORKSPACE')
  call(['chown','-R','10000:10000',str(workspace)],timeout=120)
  paths['workspace']=workspace
  for key in('home','acp'):paths[key]=_mkdir(parent/key,0o700,10000,10000)
  paths['release']=_mkdir(parent/'release',0o711)
  spec,replacement=worker_waiting_replacement(row['roles'],role,organization=record['p']['organization'],repository=record['repository'],port=4181,delivery_root=delivery_roots[role],workspace=workspace,home=paths['home'],acp=paths['acp'],release_dir=paths['release'],original_entrypoint=entry,worker_code=code)
  own=[token for token,identity in launch.http.identities.items()if identity==(row['trajectory_id'],role)];need(len(own)==1,'ONE_OWN_ROLE_RELAY_CAPABILITY')
  gateway,port=launch.http.server_address;need(gateway==record['network']['gateway']and port==4180,'EXACT_NATIVE_RELAY_LISTENER')
  spec['environment'].update(AGENT_KIND='copilot',ACP_CHILD_UID='10000',ACP_CHILD_GID='10000',ANTHROPIC_BASE_URL=f'http://{gateway}:{port}/v1',ANTHROPIC_API_KEY=own[0],ANTHROPIC_MODEL=c['model'],COPILOT_PROVIDER_TYPE='openai',COPILOT_PROVIDER_WIRE_API='responses',COPILOT_AGENT_REASONING_EFFORT='max',COPILOT_PROVIDER_MAX_PROMPT_TOKENS='110592',COPILOT_BIN='/usr/local/bin/copilot-wrapped',COPILOT_CLI_DIST_DIR='/opt/copilot-cli/node_modules/@github/copilot-linux-x64',COPILOT_AUTO_UPDATE='false',GITEA_ORG=record['p']['organization'],BOARD_IDS='pbench-top',PBENCH_WORKERS=str(len(row['roles'])),JOBS='8')
  mounts=[]
  for m in spec['mounts']:
   if m['target']=='/opt/count14':
    mounts.extend({'source':str(f),'target':'/opt/count14/'+f.name,'read_only':True}for f in sorted(code.iterdir()))
   else:mounts.append(m)
  for name,target in [('agents.md','/opt/omcgitea/prompts/agents.md'),('pbench-brief.md','/opt/omcgitea/prompts/pbench-brief.md'),('acp-bridge.py','/opt/omcgitea/acp-bridge.py'),('acp_child_custody.py','/opt/omcgitea/acp_child_custody.py'),('archive.py','/opt/omcgitea/archive.py')]:mounts.append({'source':str(owned/name),'target':target,'read_only':True})
  mounts += [{'source':str(wrapper),'target':'/usr/local/bin/copilot-wrapped','read_only':True},{'source':str(overlay/'app.js'),'target':'/opt/copilot-cli/node_modules/@github/copilot-linux-x64/app.js','read_only':True},{'source':str(overlay/'native_cli_tool_receipt.mjs'),'target':'/opt/count14/native_cli_tool_receipt.mjs','read_only':True}]
  spec['mounts']=mounts;actor=spec['environment']['AGENT_NAME'];name=record['p']['project']+'-r16-'+role
  need(not call(D+['ps','-aq','--filter','name=^/'+name+'$']).strip(),'NEW_WORKER_NO_REPLAY')
  args=D+['create','--ulimit','nofile=65536:65536','--pull=never','--name',name,'--label','org.cybergym.agensh.comparison.root='+str(layout),'--label','org.cybergym.agensh.native.role='+role,'--network',record['network']['name'],'--memory','8g','--memory-swap','8g','--cpus','4','--pids-limit','1024','--cap-drop','NET_RAW','--security-opt','no-new-privileges:true','--user','10000:10000','--workdir','/work','--entrypoint','/bin/bash']
  for k,v in sorted(spec['environment'].items()):args+=['--env',k+'='+v]
  for m in mounts:args+=['--mount','type=bind,src='+m['source']+',dst='+m['target']+(',readonly'if m['read_only']else'')]
  args += [WORKER_IMAGE,'/opt/count14/worker_hold.sh'];cid=call(args).decode().strip()
  # Only metadata; never persist opaque capability-bearing command/env/spec.
  save(parent/'WORKER_CREATED.json',{'at':now(),'id':cid,'image':WORKER_IMAGE,'role':role,'replacement_metadata':replacement,'model_calls':0,'late_delivery':True})
  call(D+['start',cid]);z=inspect(cid);pid=z['State']['Pid'];need(z['State']['Running']and z['Config']['User']=='10000:10000'and set(z['NetworkSettings']['Networks'])=={record['network']['name']},'HELD_OWN_WORKER')
  proc=Path('/proc',str(pid));peer={'pid':pid,'start_ticks':process(pid)['start_ticks'],'uid':10000,'pidns':(proc/'ns/pid').stat().st_ino,'netns':(proc/'ns/net').stat().st_ino};trusted_peer(**peer)
  cap=capsule(cid,parent,'worker');item={'role':role,'actor':actor,'id':cid,'peer':peer,'paths':paths,'capsule':cap};record['worker_rows'].append(item);peers[role]=peer;roles[role]={'workspace':workspace,'session':paths['home']};fronts[role]=f"http://127.0.0.1:4181/{record['p']['organization']}/{record['repository']}.git/"
  # The original pre-exec SDK custody shim joins this exact own Docker domain.
  sdkname=record['p']['project']+'-r16-sdk-'+role
  sid=call(D+['create','--ulimit','nofile=65536:65536','--pull=never','--name',sdkname,'--label','org.cybergym.agensh.comparison.root='+str(layout),'--network','none','--read-only','--user','10000:10000','--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory','1g','--memory-swap','1g','--pids-limit','256','--cpus','2','--entrypoint','python3',SDK_IMAGE,'-B','-c','import signal; signal.signal(signal.SIGTERM,lambda *_:exit(0)); signal.pause()']).decode().strip();call(D+['start',sid]);sc=capsule(sid,parent,'sdk');record['sdk_capsules'].append(sc)
  b={'schema':'agensh-native-sdk-domain-launch-v1',**{k:sc[k]for k in('directory','relative','device','inode','owner_uid','provenance_sha256')}};fd=os.open(sc['directory'],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  try:launches[role]=NativeCgroupLaunch(directory_fd=fd,binding=b,expected_binding_sha256=original_digest(b),shim=Path(c['qualified_cgroup_preexec']),expected_shim_sha256=SHIM_SHA)
  finally:os.close(fd)
  # Preserve public command semantics: only the owned per-process safe.directory
  # and fixed local front change, never shared git config or repository content.
  env=['git','-c','safe.directory='+str(workspace),'-C',str(workspace)]
  call(env+['remote','add','origin',fronts[role]])
  _own_generated_git_config(workspace)
 save(layout/'HELD_ORIGINAL_WORKERS_METADATA.json',{'at':now(),'rows':[{'role':r['role'],'id':r['id'],'peer':r['peer'],'capsule_sha256':r['capsule']['provenance_sha256']}for r in record['worker_rows']],'model_calls':0,'ALLOW_CLI':False})
 public=admitted_public_root(Path(c['qualified_sdk_public_root']))
 return {'peers':peers,'roles':roles,'delivery_roots':delivery_roots,'sandbox':SandboxBinary(Path(c['qualified_bwrap']),BWRAP_SHA),'sdk_identity':NativeSdkIdentity(10000,10000,public),'sdk_launches':launches,'registered_refs':['refs/heads/main','refs/tags/count14-bootstrap'],'member_cap':1000000}

def phaseflag(path,actor):
 p=Path(path);need(not p.exists()and p.parent.stat().st_uid==os.geteuid()and os.geteuid()!=10000,'NEW_HOST_PHASE_FLAG')
 tmp=p.parent/('.host-'+uuid.uuid4().hex)
 with tmp.open('xb')as f:os.fchmod(f.fileno(),0o444);f.write((actor+'\n').encode());f.flush();os.fsync(f.fileno())
 os.rename(tmp,p);fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)

def _members(capsule):
 rows=[]
 for value in(Path(capsule['directory'])/'cgroup.procs').read_text().split():
  pid=int(value)
  try:
   p=Path('/proc',value);f=(p/'stat').read_text().rsplit(') ',1)[1].split()
   if f[0]in('Z','X'):continue
   rows.append({'pid':pid,'parent_pid':int(f[1]),'start_ticks':int(f[19]),'uid':p.stat().st_uid})
  except(FileNotFoundError,ProcessLookupError):continue
 return rows

def _front(record,w):
 from native_team_owner import trusted_peer,trusted_front
 from common import Refused
 peer=w['peer'];expected=['/usr/bin/python3','-B','/opt/count14/git_http_uds_front.py','--socket','/run/count14/transport/git.sock','--capability-file','/run/count14/transport/git.capability','--private-home','/opt/data/git-front-private','--organization',record['p']['organization'],'--repository',record['repository'],'--port','4181']
 deadline=time.monotonic()+30
 while time.monotonic()<deadline:
  trusted_peer(**peer)
  for r in _members(w['capsule']):
   try:
    if Path('/proc',str(r['pid']),'cmdline').read_bytes()!=b'\0'.join(x.encode()for x in expected)+b'\0':continue
    return trusted_front(r['pid'],r['start_ticks'],peer['uid'],peer['pidns'],peer['netns'],4181,expected)
   except(FileNotFoundError,ProcessLookupError):continue
   except Refused as e:
    # The exact process can be observed before its original bind/listen.
    # Retry only this readiness-not-yet predicate, retaining the same strict
    # PID/start/argv/namespace checks and the existing bounded30s deadline.
    if e.code!='TEAM_FRONT_EXACT_OWNED_LOOPBACK_LISTENER':raise
  time.sleep(.1)
 need(False,'ORIGINAL_GIT_FRONT_NOT_READY')

def _router_source(record):
 import shutil
 c=config();source=Path(c['qualified_router_public_js'])
 index=json.loads((source/'PUBLIC_COMPILE_INDEX.json').read_bytes())
 need(index['schema']=='ops-original-router-typescript-to-node20-js-v1'and len(index['rows'])==19,'PUBLIC_ROUTER_COMPILED_CLOSURE')
 frozen=Path(c['adapter_directory'])/'native-budget-park-v1'
 changed={'main.ts','acp_socket_channel.ts','budget_pause_clock.ts','native_startup_hold.ts'}
 for row in index['rows']:
  original=(frozen/row['source'])if row['source']in changed else record['p']['root']/'source/mini-router/src'/row['source']
  need(sha(original)==row['source_sha256']and sha(source/row['output'])==row['output_sha256'],'PUBLIC_ROUTER_ORIGINAL_SOURCES_AND_TRANSFORM_PIN')
 dst=record['root']/'router-public-source';dst.mkdir(mode=0o755)
 for row in index['rows']:
  target=dst/row['output'];target.parent.mkdir(parents=True,exist_ok=True,mode=0o755);shutil.copyfile(source/row['output'],target);target.chmod(0o444)
 # Private owner umask must not make nested public JS import directories0700.
 for directory in sorted((p for p in dst.rglob('*')if p.is_dir()),reverse=True):directory.chmod(0o555)
 dst.chmod(0o555);return dst

def _start_router(record,w,launch,source):
 role=w['role'];actor=w['actor'];base=record['root']/'router-private';base.mkdir(exist_ok=True,mode=0o700)
 pw=base/(actor+'.password');pw.write_bytes((record['p']['root']/'run/data/tokens'/('agent-'+actor+'.password')).read_bytes());pw.chmod(0o400);os.chown(pw,10000,10000)
 home=w['paths']['home'];(home/'home').mkdir(exist_ok=True,mode=0o700);os.chown(home/'home',10000,10000);group=_mkdir(home/'home/group-messages',0o700,10000,10000)
 empty=_mkdir(record['root']/role/'empty-clock',0o755);s=launch.startup_bindings[role]
 need(s['container_directory']=='/run/count14/startup'and s['clock_container_file']==f'/run/count14/budget-clock/{role}.json','ORIGINAL_STARTUP_TARGETS')
 e=record['env'];env={'AGENT_NAME':actor,'ACP_SOCKET_PATH':'/var/run/acp/agent.sock','GITEA_HOST':'http://gitea:3000','GITEA_PASSWORD_FILE':'/run/omcgitea/role.password','MYSQL_DSN':'mysql://omcgitea:'+e['MYSQL_PASSWORD']+'@mysql:3306/omcgitea','SECRET_SERVICE_INTERNAL_AUTH':e['SECRET_SERVICE_INTERNAL_AUTH'],'SECRET_SERVICE_URL':'http://secret-service:8650','MATTERMOST_HOST':'http://mattermost:8065','BOARD_SERVICE_URL':'http://board-service:8660','BOARD_IDS':'pbench-top','MINI_ROUTER_PORT':'8645','MINI_ROUTER_STUCK_MS':'1200000','COUNT14_STARTUP_HOLD_DIR':s['container_directory'],'COUNT14_STARTUP_BINDING_SHA256':s['binding_sha256'],'COUNT14_STARTUP_OWNER_UID':str(s['owner_uid'])}
 mounts=[(pw,'/run/omcgitea/role.password',True),(w['paths']['acp'],'/var/run/acp',True),(group,'/opt/data/home/group-messages',False),(source,'/app/count14-source',True),(Path(s['directory']),s['container_directory'],True),(empty,'/run/count14/budget-clock',True)]
 name=record['p']['project']+'-r16-router-'+role;need(not call(D+['ps','-aq','--filter','name=^/'+name+'$']).strip(),'NEW_ROUTER_NO_REPLAY')
 args=D+['create','--ulimit','nofile=65536:65536','--pull=never','--name',name,'--label','org.cybergym.agensh.comparison.root='+str(record['layout']),'--label','org.cybergym.agensh.native.role='+role,'--network',record['backend_proof']['network']['name'],'--user','10000:10000','--memory','1g','--memory-swap','1g','--cpus','1','--pids-limit','256','--cap-drop','ALL','--security-opt','no-new-privileges:true']
 for k,v in sorted(env.items()):args+=['--env',k+'='+v]
 for src,target,ro in mounts:args+=['--mount','type=bind,src='+str(src)+',dst='+target+(',readonly'if ro else'')]
 args += ['--entrypoint','node',ROUTER_IMAGE,'/app/count14-source/main.js']
 cid=call(args).decode().strip();r={'role':role,'id':cid,'image':ROUTER_IMAGE};record['router_rows'].append(r);save(record['root']/role/'ORIGINAL_ROUTER_CREATED.json',{'at':now(),**r,'startup_hold':True,'model_calls':0})
 call(D+['start',cid]);return r

# No model, task, capability, or scientific body is sent by this connectivity probe.
NETWORK_PROBE=r'''import http.client,socket,json
p={"relay":False,"foreign":False,"front":False}
h=http.client.HTTPConnection(RELAY,4180,timeout=3)
try:h.request('GET','/healthz');r=h.getresponse();r.read(1048576);p['relay']=r.status==200
finally:h.close()
h=http.client.HTTPConnection('127.0.0.1',4181,timeout=3)
try:h.request('GET','/');r=h.getresponse();r.read(1024);p['front']=r.status in(400,403,404)
finally:h.close()
s=socket.socket();s.settimeout(.5)
try:s.connect(('1.1.1.1',443));p['foreign']=True
except OSError:pass
finally:s.close()
assert p['relay']and p['front']and not p['foreign'];print(json.dumps(p,sort_keys=True))'''

def cli(team,workers,launch):
 record=STATE[team.t];from native_team_owner import trusted_peer
 from native_delivery import complete_delivery
 from worker_netns_rules import rules
 for w in record['worker_rows']:
  trusted_peer(**w['peer']);complete_delivery(workers['delivery_roots'][w['role']]);need(not(w['paths']['release']/'ALLOW_CLI').exists(),'NO_PREVIOUS_RELEASE')
 for w in record['worker_rows']:phaseflag(w['paths']['release']/'PORTS_READY',w['actor'])
 fronts=[]
 for w in record['worker_rows']:
  front=_front(record,w);peer=w['peer'];gateway=record['network']['gateway']
  for tool,v6 in(('/usr/sbin/iptables-restore',False),('/usr/sbin/ip6tables-restore',True)):call(['nsenter','-t',str(peer['pid']),'-n','--',tool,'--wait','5'],data=rules(gateway,git_front_port=4181,ipv6=v6))
  # Exact owned transport health only; /v1/models is not a scientific route.
  probe=NETWORK_PROBE
  own=[token for token,identity in launch.http.identities.items()if identity==(team.t,w['role'])];need(len(own)==1,'ONE_ROLE_CAP')
  # Input through stdin, not an argv containing opaque capability material.
  payload=('RELAY='+repr(gateway)+'\n'+probe).encode()
  out=call(D+['exec','-i','--user','10000:10000',w['id'],'python3','-B','-'],data=payload,timeout=15);result=json.loads(out)
  fronts.append({'role':w['role'],'actual_front':front,'only_relay_probe':result})
 save(record['layout']/'ORIGINAL_PORTS_FRONTS_ONLY_RELAY_READY.json',{'at':now(),'fronts':fronts,'models':0})
 for w in record['worker_rows']:phaseflag(w['paths']['release']/'ALLOW_CLI',w['actor'])
 deadline=time.monotonic()+120
 while True:
  if all((w['paths']['acp']/'agent.sock').exists()and stat.S_ISSOCK((w['paths']['acp']/'agent.sock').lstat().st_mode)for w in record['worker_rows']):break
  need(time.monotonic()<deadline,'ORIGINAL_ACP_LISTEN_WAIT');time.sleep(.1)
 source=_router_source(record)
 for w in record['worker_rows']:_start_router(record,w,launch,source)
 return {}

def _late_bind(source,capsule,target,receipt):
 c=config();helper=BASE/'late_bind_readonly.py';need(sha(helper)==c['host_files']['late_bind_readonly.py'],'PINNED_LATE_BIND_HELPER')
 z=process(capsule['anchor']['pid']);need(z==capsule['anchor'],'SAME_TARGET_FOR_LATE_BIND')
 raw=call([sys.executable,'-B',str(helper),'--source',str(source),'--pid',str(z['pid']),'--start-ticks',str(z['start_ticks']),'--target',target],timeout=30)
 result=json.loads(raw);need(result['status']=='EXACT_CONTAINER_READONLY_LATE_BIND_PASS','LATE_BIND_ACTUAL_PASS');save(receipt,result)

def ready(launch,workers,clock_bindings):
 record=STATE[launch.t]
 need(set(clock_bindings)==set(workers['roles']),'EXACT_ROLE_CLOCK')
 hostns=Path('/proc/self/ns/mnt').stat().st_ino
 for r in record['router_rows']:
  cap=capsule(r['id'],record['root']/r['role'],'router-ready')
  _late_bind(launch.controller.projection.directory,cap,'/run/count14/budget-clock',record['root']/r['role']/'BUDGET_CLOCK_READONLY_LATE_BIND.json')
 need(Path('/proc/self/ns/mnt').stat().st_ino==hostns,'HOST_MOUNTNS_UNCHANGED')
 save(record['layout']/'HOST_CLOCK_READY_NO_TASK.json',{'at':now(),'roles':list(workers['roles']),'host_mount_namespace_unchanged':True,'model_calls':0})
 return True

def task(row,launch,bootstrap_root):
 record=STATE[row['trajectory_id']];need(launch.released,'ORIGINAL_GATE_RELEASED_BEFORE_TASK')
 receipt=record['layout']/'ORIGINAL_TASK_POST_INTENT.json';need(not receipt.exists(),'ORIGINAL_TASK_EXACTLY_ONCE_NO_RETRY')
 path=Path(bootstrap_root)/'task-description.bin'
 # The trusted runtime passes the exact approved description to original MM.
 # No human-readable body or response is written, printed or selected by OPS.
 body=path.read_bytes();need(hashlib.sha256(body).hexdigest()==json.loads((Path(bootstrap_root)/'bootstrap-receipt.json').read_bytes())['task_description_sha256'],'EXACT_SAME_TASK_DESCRIPTION')
 save(receipt,{'at':now(),'channel_id':record['task_channel'],'task_sha256':hashlib.sha256(body).hexdigest(),'task_bytes':len(body),'models_not_dispatched_by_host':True,'no_auto_retry':True})
 status,value,_=api(record['origins']['mattermost'],'POST','/api/v4/posts',token=record['mm_admin_token'],body={'channel_id':record['task_channel'],'message':body.decode('utf-8','strict')})
 need(status==201 and value.get('channel_id')==record['task_channel']and type(value.get('id'))is str,'ORIGINAL_TASK_POST_TERMINAL_NO_RETRY')
 save(record['layout']/'ORIGINAL_TASK_POST_HTTP_TERMINAL.json',{'at':now(),'HTTP':status,'post_id':value['id'],'channel_id':record['task_channel'],'task_sha256':hashlib.sha256(body).hexdigest(),'exact_original_description':True})
