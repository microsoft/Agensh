"""Metadata-only GLM affinity and credential rotation. No payload construction."""
import os as _count14_os  # endpoints/keys come from environment; see CONFIGURATION.md
from pathlib import Path
import hashlib,json,threading,time
from common import need

REVISION='a4-glm-session-header-v1'
ROOT=Path('/mnt/ptb-scratch2/ag28v2a4')
KEY=ROOT/_count14_os.environ.get('COUNT14_GLM_KEY_RELPATH', 'config/glm-provider-key')

def session_id(domain,*identity):
 need(domain in ('SEARCH','AUX_FINAL','PROBE'),'GLM_SESSION_DOMAIN')
 need(all(type(v)is str and 0<len(v)<=4096 for v in identity),'GLM_SESSION_METADATA')
 return hashlib.sha256(json.dumps(['agensh-glm-session-affinity-v1',domain,*identity],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()[:32]

def search_session(trajectory,role,original_cli_session):return session_id('SEARCH',trajectory,role,original_cli_session)
def aux_session(point,replicate,attempt):
 need(type(point)is str and len(point)==64 and all(c in '0123456789abcdef'for c in point),'GLM_SESSION_POINT')
 need(type(replicate)is int and replicate in (1,2,3)and type(attempt)is int and 1<=attempt<=4,'GLM_SESSION_REPLICATE_ATTEMPT')
 return session_id('AUX_FINAL',point,str(replicate),str(attempt))
def probe_session(name):return session_id('PROBE',str(ROOT),name)

def read_key(path):
 # Same qualified owner/private/regular/no-symlink/single-link credential gate.
 from feasibility_relay import private_file
 value=private_file(path).decode('utf-8').strip()
 need(bool(value)and not any(c in value for c in '\r\n\x00'),'GLM_PROVIDER_PRIVATE_KEY_FORMAT')
 return value

class Timings:
 """Only duration/identity hashes; no response bytes or raw errors."""
 def __init__(self):self.lock=threading.Lock();self.rows=[]
 def add(self,row):
  with self.lock:
   self.rows.append(row)
   if len(self.rows)>20000:del self.rows[:10000]
 def snapshot(self):
  with self.lock:return [dict(r)for r in self.rows]

class ResponseTiming:
 def __init__(self,response,start,metadata,timings):
  self.response=response;self.start=start;self.metadata=metadata;self.timings=timings;self.first=False
 def __getattr__(self,name):return getattr(self.response,name)
 def __enter__(self):self.response.__enter__();return self
 def __exit__(self,*args):return self.response.__exit__(*args)
 def readline(self,*args,**kwargs):
  row=self.response.readline(*args,**kwargs)
  if row.startswith(b'data:')and row[5:].strip()and not self.first:
   self.first=True;self.timings.add({**self.metadata,'kind':'FIRST_NONEMPTY_SSE_LINE','seconds':time.monotonic()-self.start})
  return row

class HeaderOpener:
 def __init__(self,original,*,url,identity,key_path=KEY,timings=None,metadata=None):
  self.original=original;self.url=url;self.identity=identity;self.key_path=Path(key_path);self.timings=timings or Timings();self.metadata=metadata
 def open(self,request,*args,**kwargs):
  need(request.full_url==self.url and request.get_method()=='POST','GLM_SESSION_EXACT_ORIGINAL_ENDPOINT')
  sid=self.identity();need(type(sid)is str and len(sid)==32 and all(c in '0123456789abcdef'for c in sid),'GLM_SESSION_HEADER_VALUE')
  request.remove_header('Authorization');request.add_header('Authorization','Bearer '+read_key(self.key_path))
  request.remove_header('X-session-id');request.add_header('X-Session-ID',sid)
  start=time.monotonic();meta={'session_id':sid,'sent_at_ns':time.time_ns(),'revision':REVISION}
  if self.metadata is not None:
   fields=self.metadata();need(set(fields)=={'request_id','trajectory','role'},'GLM_SESSION_TIMING_METADATA_ONLY');meta.update(fields)
  self.timings.add({**meta,'kind':'REQUEST_START'})
  try:response=self.original.open(request,*args,**kwargs)
  except BaseException as e:
   self.timings.add({**meta,'kind':'REQUEST_EXCEPTION','seconds':time.monotonic()-start,'exception_type':type(e).__name__});raise
  self.timings.add({**meta,'kind':'RESPONSE_HEADERS','seconds':time.monotonic()-start,'http_status':response.status})
  return ResponseTiming(response,start,meta,self.timings)

def install_search(engine,sessions,*,key_path=KEY):
 """Replace only original raw opener, retaining exact trusted transport closure."""
 from feasibility_relay import ChatTransport
 from scientific_relay import ScientificRelay
 need(type(engine)is ScientificRelay,'GLM_SEARCH_ORIGINAL_ENGINE')
 fn=engine.transport
 cells=dict(zip(fn.__code__.co_freevars,(c.cell_contents for c in fn.__closure__ or ())))
 raw=cells.get('transport');usage=cells.get('usage')
 need(type(raw)is ChatTransport and usage is engine.ledger and raw.auth_style=='bearer','GLM_SEARCH_ORIGINAL_RAW_TRANSPORT')
 need(not isinstance(raw.opener,HeaderOpener),'GLM_SEARCH_INSTALL_ONCE')
 def identity():
  pair=usage.scope.value['identity'];need(pair in sessions,'GLM_SEARCH_ORIGINAL_SESSION_REGISTERED')
  return search_session(*pair,sessions[pair])
 def metadata():
  value=usage.scope.value;return {'request_id':value['rid'],'trajectory':value['identity'][0],'role':value['identity'][1]}
 overlay=HeaderOpener(raw.opener,url=raw.url,identity=identity,key_path=key_path,metadata=metadata)
 raw.opener=overlay
 return overlay

def binding_point(binding):
 from common import digest
 key={'trajectory':binding.trajectory,'target':binding.target}
 if binding.natural_stop is not None:key.update(point_kind='NATURAL_STOP',policy_sha256=binding.natural_stop['policy_sha256'])
 point=digest(key)
 need(binding.point_id in (None,point),'GLM_AUX_ORIGINAL_POINT_ID')
 return point

def aux_transport(original,port,*,key_path=KEY,receipt=None):
 from common import publish,wire
 need(port.binding.identity['purpose']=='AUX_FINALIZATION','GLM_AUX_ORIGINAL_PURPOSE')
 b=port.binding;sid=aux_session(binding_point(b),b.repeat,b.replicate_attempt)
 def stream(completion,options,**kwargs):
  opts=dict(options);opts['extra_headers']=dict(options.get('extra_headers',{}))
  opts['extra_headers']['X-Session-ID']=sid;opts['api_key']=read_key(key_path)
  # Body/model/max_tokens/seed and the original X-Request-ID are untouched.
  return original(completion,opts,**kwargs)
 if receipt is not None:
  publish(receipt,wire({'schema':'agensh-glm-aux-session-header-v1','revision':REVISION,'session_id':sid,
   'point_id':binding_point(b),'replicate_id':b.repeat,'attempt':b.replicate_attempt,'key_path':str(key_path),
   'body_changed':False,'original_request_id_retained':True,'timeout_overlay_retained':True}),mode=0o400)
 return stream
