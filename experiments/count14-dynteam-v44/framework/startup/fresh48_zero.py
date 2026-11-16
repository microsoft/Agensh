"""Dry-only loopback synthetic Chat service and native launcher rehearsal.

No network client/provider route. Request messages are never accessed or saved;
only public function schemas, tool-result counts and derived session IDs are
used to run three fixed harmless shell calls. Synthetic usage is three tokens.
"""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import hashlib,json,stat,threading,time
from common import need,wire,publish
from fresh48_scope import selected
MODEL='GLM-5.3-FP8'
WORKER_UID=10000


def answer(n,tools):
 """Fixed dry command; never derive instructions from model/user messages."""
 if n<=3:
  names={x.get('function',{}).get('name')for x in tools if type(x)is dict and x.get('type')=='function'}
  need('bash'in names,'FRESH48_DRY_PUBLIC_BASH_TOOL_REQUIRED')
  return {'role':'assistant','content':None,'tool_calls':[{'id':f'OWN-zero-tool-{n}',
   'type':'function','function':{'name':'bash','arguments':json.dumps({
    'command':"mkdir -p /work/output/pocs; printf 'ZERO_MODEL_REHEARSAL\\n' >> /work/output/progress.md",
    'description':'Zero-model deployment rehearsal','mode':'sync','initial_wait':1},separators=(',',':'))}}]},'tool_calls'
 return {'role':'assistant','content':'ACK'},'stop'


class Server(ThreadingHTTPServer):
 daemon_threads=True
 def __init__(self,address=('127.0.0.1',12578)):
  self.lock=threading.Lock();self.sessions={};self.errors=[]
  need(address[0]=='127.0.0.1','FRESH48_DRY_LOOPBACK_ONLY')
  super().__init__(address,Handler)
 def observed(self,session,tools,tool_results):
  # The only retained identity is the already metadata-derived X-Session-ID.
  need(len(session)==32 and all(x in'0123456789abcdef'for x in session),'FRESH48_DRY_STABLE_SESSION_HEADER')
  with self.lock:
   v=self.sessions.setdefault(session,{'requests':0,'tool_results':0});v['requests']+=1
   v['tool_results']+=int(tool_results>0);n=v['requests']
  return answer(n,tools)
 def snapshot(self):
  with self.lock:return {'sessions':{k:dict(v)for k,v in self.sessions.items()},'errors':list(self.errors),
   'real_upstream_connections':0,'usage_kind':'SYNTHETIC_OWN_NOT_SCIENTIFIC','provider_key_loaded':False}


class Handler(BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def log_message(self,*a):pass
 def reply(self,status,raw,kind='application/json'):
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)))
  self.send_header('Connection','close');self.end_headers();self.wfile.write(raw);self.close_connection=True
 def do_GET(self):
  if self.path=='/metrics':return self.reply(200,b'smg_gateway_model_request_inflight{model_id="GLM-5.3-FP8"} 0\n','text/plain')
  return self.reply(404,wire({'code':'DRY_FIXED_ROUTE_ONLY'}))
 def do_POST(self):
  try:
   need(self.path=='/v1/chat/completions','DRY_FIXED_CHAT_ROUTE')
   n=int(self.headers.get('Content-Length','-1'));need(0<=n<=128*1024*1024,'DRY_BODY_BOUND')
   body=json.loads(self.rfile.read(n))
   # Do not inspect content, prompts, tool arguments/results, or request token.
   tools=body.get('tools',[]);tool_results=sum(x.get('role')=='tool'for x in body.get('messages',[])if type(x)is dict)
   message,finish=self.server.observed(self.headers.get('X-Session-ID',''),tools,tool_results)
   stream=body.get('stream')is True;del body
   usage={'prompt_tokens':2,'completion_tokens':1,'total_tokens':3}
   if not stream:return self.reply(200,wire({'id':'OWN-zero','object':'chat.completion','model':MODEL,
    'choices':[{'index':0,'message':message,'finish_reason':finish}],'usage':usage}))
   delta=dict(message)
   if 'tool_calls'in delta:
    delta['tool_calls']=[dict(x,index=i)for i,x in enumerate(delta['tool_calls'])]
   pieces=[{'id':'OWN-zero','object':'chat.completion.chunk','model':MODEL,
    'choices':[{'index':0,'delta':delta,'finish_reason':None}]},
    {'id':'OWN-zero','object':'chat.completion.chunk','model':MODEL,'choices':[{'index':0,'delta':{},'finish_reason':finish}]},
    {'id':'OWN-zero','object':'chat.completion.chunk','model':MODEL,'choices':[],'usage':usage}]
   return self.reply(200,b''.join(b'data: '+wire(p)+b'\n\n'for p in pieces)+b'data: [DONE]\n\n','text/event-stream')
  except BaseException as e:
   with self.server.lock:self.server.errors.append(type(e).__name__)
   return self.reply(400,wire({'code':'DRY_METADATA_OR_PUBLIC_TOOL_SCHEMA_REFUSED','exception_type':type(e).__name__}))


def install():
 """Before Owner creation, in isolated dry interpreter ONLY."""
 from expansion100_contract import NEW_ROOT
 need(NEW_ROOT==selected('zero-model')[0],'FRESH48_DRY_CANNOT_INSTALL_IN_PRODUCTION')
 from durable_final import FinalOnlyDispatcher
 FinalOnlyDispatcher.dispatch_one=lambda self:None # no real AUX, ever
 server=Server();threading.Thread(target=server.serve_forever,daemon=True,name='fresh48-own-zero-chat').start()
 return server


def workspace_assertions(roles):
 """Only lstat metadata of files made by this fixed dry bash command."""
 expected=3*len(b'ZERO_MODEL_REHEARSAL\n');rows=[]
 for role,paths in roles.items():
  work=Path(paths['workspace']);p=work/'output/progress.md';d=work/'output/pocs'
  a=p.lstat();b=d.lstat()
  need(p.resolve()==p and d.resolve()==d and stat.S_ISREG(a.st_mode)and stat.S_ISDIR(b.st_mode),
   'FRESH48_DRY_ACTUAL_WORKSPACE_REGULAR_NO_SYMLINK')
  need(a.st_uid==WORKER_UID and b.st_uid==WORKER_UID and a.st_size==expected,
   'FRESH48_DRY_THREE_REAL_SHELL_WRITES_BY_WORKER_UID')
  rows.append({'role':role,'progress_bytes':a.st_size,'owner_uid':a.st_uid,
   'pocs_directory':True,'private_content_read':False})
 return rows


def rehearsal(owner,server,timeout=2400):
 """Original real worker/CLI/native inventory/collect/freeze/snapshot/thaw.

Runs one team4 and one team8 in the isolated dry ledger. Uses native extra
natural cut only for deployment qualification; no experiment result or model.
"""
 need(owner.driver.manifest['root']==selected('zero-model')[0]and
  owner.driver.upstream['base']=='http://127.0.0.1:12578/v1','FRESH48_DRY_EXACT_LOOPBACK_OWNER')
 owner.natural.stop.set() # explicit synthetic cut, not production idle policy
 targets=[next(t for t,r in owner.driver.rows.items()if r['setting']==f'Agensh-{w}'and r['block']==1)for w in(4,8)]
 receipts=[];end=time.monotonic()+timeout
 for t in targets:
  need(owner.driver.admit(owner.driver.rows[t],'new-trajectory')is not None,'FRESH48_DRY_FRESH_TEAM_ADMISSION')
  owner.driver.launch_one(t)
  request=False
  while time.monotonic()<end:
   owner.tick();s=server.snapshot();need(not s['errors'],'FRESH48_DRY_SYNTHETIC_ERROR_NO_RETRY')
   enough=sum(v['requests']>=4 and v['tool_results']>=3 for v in s['sessions'].values())
   need(not owner.hold,'FRESH48_DRY_REAL_GATE_FAULT_RETAIN')
   if not request and enough>=sum(owner.driver.rows[x]['workers']if 'workers'in owner.driver.rows[x]else len(owner.driver.rows[x]['roles'])for x in targets[:len(receipts)+1]):
    # The original whole team, including MM/DB, may now be frozen.
    # After requesting a cut, no idle RPC is legal until the native
    # completed-snapshot port proves original RUNNING/thaw.
    sample=owner.natural.ports.poll_native_idle(t)
    if all(sample[k]==0 for k in('pending','sending','retrying','team_model_inflight')):
     request=owner.natural.request_first(t,sample,immediate=True)
   ctrl=owner.driver.records[t]['launch'].controller
   if request and owner.natural._completed_snapshot(t)is not None:
    writes=workspace_assertions(owner.driver.records[t]['workers']['roles'])
    point=next(p for p in ctrl.points if p.get('point_kind')=='NATURAL_STOP')
    receipts.append({'trajectory':t,'workers':len(owner.driver.rows[t]['roles']),'snapshot':point['snapshot'],
     'K3_queued_not_dispatched':len(point['jobs']),'native_controller_resumed':ctrl.state=='RUNNING',
     'real_UID10000_three_shell_writes_metadata':writes,
     'inventory_collect_whole_freeze_snapshot_thaw':True})
    break
   time.sleep(.5)
  else:raise RuntimeError('FRESH48_DRY_DEADLINE_RETAIN_NO_AUTO_RETRY')
 owner.operator_hold=True
 from run_fresh48 import bundle_fingerprint
 receipt={'schema':'agensh-v2-fresh48-same-launcher-real-cli-zero-model-v1','PASS':True,'bundle_fingerprint':bundle_fingerprint(),
  'teams':receipts,'synthetic':server.snapshot(),'models':0,'FINAL_calls':0,
  'production_scope_started':False,'scientific_usage':0,'minimum_tool_rounds_per_worker':3}
 publish(owner.home/'ZERO_MODEL_FULL_LAUNCHER_PASS.json',wire(receipt))
 owner.record('FRESH48_DRY_FULL_LAUNCHER_PASS',{'receipt':str(owner.home/'ZERO_MODEL_FULL_LAUNCHER_PASS.json'),'models':0})
 # Keep control reachable for OPS retirement; don't abandon live native teams.
 while True:time.sleep(5)
