"""Fixed-scope native MCP policy; no worker-selected executable/URL/service.

Tool declarations are the exact native tools/list metadata from a qualified
backend. Original Copilot deny rules remain enforced at this independent
transport boundary. Every admitted tool requires an explicit trusted scope rule;
unknown native tools never gain permissions from their name or description.
"""
from dataclasses import dataclass
import copy,hashlib,math,re
from common import need,integer,ident,digest,wire,trajectory_id,Refused,sha
FRAME_CAP=8*2**20
def normalize_protocol_progress(message):
 """Consume ONLY original native CLI integer progressToken control metadata.

 Actual original Rust MCP tools/list sends _meta.progressToken even without a
 model business call. It is not an argument/parent/capability or native business
 effect. Unknown metadata stays in the frame for the ORIGINAL guards to refuse.
 The caller's object is never mutated. No cursor/string/general meta support.
 """
 if type(message)is not dict or message.get('method')not in('tools/list','tools/call'):return message
 params=message.get('params')
 if type(params)is not dict:return message
 meta=params.get('_meta')
 if type(meta)is not dict or 'progressToken'not in meta:return message
 token=meta['progressToken']
 need(type(token)is int and -(2**53-1)<=token<=2**53-1,'MCP_PROGRESS_TOKEN_SAFE_INTEGER_ONLY')
 other={k:v for k,v in meta.items()if k!='progressToken'}
 clean={k:v for k,v in params.items()if k!='_meta'}
 if other:clean['_meta']=other
 return {**message,'params':clean}

# Exact reviewed patterns from the pinned native MM0.5.1 declarations, not a
# general user-provided regex engine. No backrefs/lookaround/unbounded nested
# repetition; re.fullmatch also rejects the trailing-newline '$' ambiguity.
QUALIFIED_PATTERNS=frozenset(('^[a-z0-9][a-z0-9_-]*$','^[a-zA-Z0-9_+-]+$','^[a-zA-Z][a-zA-Z0-9._-]*$'))
class ArgumentRejected(Refused):
 """Known runtime-value refusal, after valid RPC/tool and trusted schema.

 Not for malformed RPC, unknown tools, schema/config corruption, capability
 failure or any native-side result. It is raised only by explicit checks below.
 """
def argument_need(condition,code):
 if not condition:raise ArgumentRejected(code)

class ScopeRejected(Refused):
 """Known pure authorization refusal before any native byte is dispatched."""
class FixedScopeGuard:
 """Host-selected authorization, never selected/deserialized by the worker."""
 def bind(self,identity,tools,rules):raise NotImplementedError
 def backend(self,identity,command,environment,cwd):raise NotImplementedError
 def ready(self,identity):raise NotImplementedError
 def before(self,identity,name,args):raise NotImplementedError
 def complete(self,identity,request,response):raise NotImplementedError

@dataclass(frozen=True)
class McpIdentity:
 trajectory:str
 role:str
 generation:int
 purpose:str
 agent:str
 uid:int
 pid_namespace_inode:int
 capability:str

def check_schema(schema,depth=0):
 need(depth<=24 and type(schema)is dict,'MCP_ARGUMENT_SCHEMA_DEPTH')
 if 'anyOf'in schema:
  need(set(schema)<={'anyOf','description','title','default','enum'}and type(schema['anyOf'])is list and 1<=len(schema['anyOf'])<=8,'MCP_ANYOF_SCHEMA')
  if 'enum'in schema:need(type(schema['enum'])is list and bool(schema['enum']),'MCP_ENUM_SCHEMA')
  for branch in schema['anyOf']:check_schema(branch,depth+1)
  return
 kind=schema.get('type');need(kind in ('object','string','integer','number','boolean','array','null'),'MCP_QUALIFIED_SCHEMA_TYPE')
 annotations={'type','description','title','default','enum'}
 by_type={'object':{'properties','required','additionalProperties'},'array':{'items','minItems','maxItems'},'string':{'minLength','maxLength','pattern'},'integer':{'minimum','maximum'},'number':{'minimum','maximum'},'boolean':set(),'null':set()}
 need(set(schema)<=annotations|by_type[kind],'MCP_UNSUPPORTED_SCHEMA_KEYWORD')
 if 'enum'in schema:need(type(schema['enum'])is list and bool(schema['enum']),'MCP_ENUM_SCHEMA')
 if 'pattern'in schema:need(type(schema['pattern'])is str and schema['pattern']in QUALIFIED_PATTERNS,'MCP_UNQUALIFIED_PATTERN')
 if kind=='object':
  props=schema.get('properties',{});required=schema.get('required',[])
  need(type(props)is dict and type(required)is list and all(type(k)is str for k in props)and all(type(k)is str for k in required)and len(set(required))==len(required)and set(required)<=set(props),'MCP_OBJECT_SCHEMA')
  need(schema.get('additionalProperties',False)is False,'MCP_UNBOUNDED_ADDITIONAL_PROPERTIES')
  need(not set(props)&{'url','base_url','host','command','shell','headers','access_token','api_key','token','repository_path'},'MCP_NETWORK_OR_EXEC_ARGUMENT_FORBIDDEN')
  for value in props.values():check_schema(value,depth+1)
 elif kind=='array':
  need('items'in schema,'MCP_ARRAY_ITEM_SCHEMA');check_schema(schema['items'],depth+1)
 for low,high in [('minItems','maxItems'),('minLength','maxLength'),('minimum','maximum')]:
  for key in (low,high):
   if key in schema:need(type(schema[key])in(int,float)and math.isfinite(schema[key])and(key in('minimum','maximum')or type(schema[key])is int and schema[key]>=0),'MCP_SCHEMA_RANGE')
  if low in schema and high in schema:need(schema[low]<=schema[high],'MCP_SCHEMA_RANGE')

def validate_schema(value,schema,depth=0):
 check_schema(schema,depth)
 if 'enum'in schema:argument_need(any(wire(value)==wire(x)for x in schema['enum']),'MCP_ARGUMENT_ENUM')
 if 'anyOf'in schema:
  # check_schema above checked EVERY branch first. Unsupported constraints or
  # network/proxy fields cannot hide behind a different successful alternative.
  for branch in schema['anyOf']:
   try:validate_schema(value,branch,depth+1);return
   except ArgumentRejected:pass
  argument_need(False,'MCP_ARGUMENT_ANYOF')
 kind=schema['type']
 if kind=='object':
  argument_need(type(value)is dict,'MCP_ARGUMENT_OBJECT');props=schema.get('properties',{});argument_need(set(value)<=set(props)and set(schema.get('required',[]))<=set(value),'MCP_ARGUMENT_FIELDS')
  for key,item in value.items():validate_schema(item,props[key],depth+1)
 elif kind=='array':
  argument_need(type(value)is list and len(value)>=schema.get('minItems',0)and len(value)<=schema.get('maxItems',10000),'MCP_ARGUMENT_ARRAY')
  for item in value:validate_schema(item,schema['items'],depth+1)
 elif kind=='string':argument_need(type(value)is str and len(value)>=schema.get('minLength',0)and len(value)<=schema.get('maxLength',FRAME_CAP),'MCP_ARGUMENT_STRING')
 if kind=='string'and'pattern'in schema:argument_need(re.fullmatch(schema['pattern'],value)is not None,'MCP_ARGUMENT_PATTERN')
 if kind=='integer':argument_need(type(value)is int and schema.get('minimum',-2**63)<=value<=schema.get('maximum',2**63-1),'MCP_ARGUMENT_INTEGER')
 elif kind=='number':argument_need(type(value)in(int,float)and math.isfinite(value)and schema.get('minimum',-1e300)<=value<=schema.get('maximum',1e300),'MCP_ARGUMENT_NUMBER')
 elif kind=='boolean':argument_need(type(value)is bool,'MCP_ARGUMENT_BOOL')
 elif kind=='null':argument_need(value is None,'MCP_ARGUMENT_NULL')

def native_denials(purpose,deny_names):
 need(type(deny_names)is list and all(type(n)is str for n in deny_names),'MCP_NATIVE_DENY_METADATA')
 denied=set()
 for entry in deny_names:
  match=re.fullmatch(r'(board|gitea|mattermost)\(([A-Za-z0-9_.+-]+)\)',entry)
  if match:
   if match[1]==purpose:denied.add(match[2])
  else:ident(entry);denied.add(entry)
 return denied

class McpPolicy:
 def __init__(self,identity,*,native_tools,deny_names,rules,scope_guard=None):
  need(isinstance(identity,McpIdentity)and identity.purpose in ('board','gitea','mattermost'),'MCP_FIXED_PURPOSE');integer(identity.generation,'MCP_GENERATION',1);integer(identity.uid,'MCP_UID');integer(identity.pid_namespace_inode,'MCP_PIDNS',1)
  need(type(native_tools)is list and 0<len(native_tools)<=512 and type(rules)is dict,'MCP_NATIVE_TOOLS_METADATA')
  trajectory_id(identity.trajectory)
  for value in(identity.role,identity.agent):ident(value)
  need(type(identity.capability)is str and len(identity.capability)>=48,'MCP_CAPABILITY_LENGTH')
  need(len(wire(native_tools))<=FRAME_CAP,'MCP_DECLARATIONS_BYTE_BOUND')
  self.identity=identity;self.tools=copy.deepcopy(native_tools);self.declarations={};self.rules=copy.deepcopy(rules);self.deny=native_denials(identity.purpose,deny_names)
  for tool in self.tools:
   need(type(tool)is dict and set(tool)<={'name','description','inputSchema','annotations','outputSchema','title','_meta'}and set(tool)>={'name','inputSchema'},'MCP_NATIVE_TOOL_DECLARATION');ident(tool['name']);need(tool['name']not in self.declarations,'MCP_NATIVE_TOOL_DUPLICATE');self.declarations[tool['name']]=tool
  for tool in self.tools:
   for field in ('_meta','annotations','outputSchema'):
    if field in tool:need(type(tool[field])is dict,'MCP_NATIVE_PASSIVE_METADATA')
   for field in ('description','title'):
    if field in tool:need(type(tool[field])is str,'MCP_NATIVE_PASSIVE_METADATA')
  allowed=set(self.declarations)-self.deny;need(set(rules)==allowed and bool(allowed),'MCP_EVERY_EXPOSED_TOOL_REQUIRES_SCOPE_RULE')
  self.exposed=[t for t in self.tools if t['name']in allowed]
  for name,rule in self.rules.items():
   check_schema(self.declarations[name]['inputSchema'])
   need(type(rule)is dict and set(rule)=={'kind','scope_fields','native_self_scope_qualified'}and rule['kind']in('GIT_READ','GIT_WRITE','CHAT_READ','CHAT_WRITE'),'MCP_TOOL_RULE')
   need(type(rule['scope_fields'])is dict and type(rule['native_self_scope_qualified'])is bool and(rule['scope_fields']or rule['native_self_scope_qualified']),'MCP_TOOL_SCOPE_NOT_PROVEN')
   props=self.declarations[name]['inputSchema'].get('properties',{});need(not set(props)&{'url','base_url','host','command','shell','headers','access_token','api_key','token','repository_path'},'MCP_NETWORK_OR_EXEC_ARGUMENT_FORBIDDEN')
   for key,values in rule['scope_fields'].items():need(key in props and type(values)is list and len(values)>0 and all(type(v)is str and v for v in values),'MCP_EXPLICIT_SCOPE_FIELD')
  need(scope_guard is None or isinstance(scope_guard,FixedScopeGuard),'MCP_TRUSTED_SCOPE_GUARD')
  self.scope_guard=scope_guard
  identity_body={'identity':{k:v for k,v in vars(identity).items()if k!='capability'},'native_tools':self.tools,'deny':sorted(self.deny),'rules':self.rules}
  if scope_guard is not None:
   sha(scope_guard.pin);scope_guard.bind(identity,self.tools,self.rules);identity_body['scope_guard_sha256']=scope_guard.pin
  self.sha=digest(identity_body)
 def request(self,message):
  message=normalize_protocol_progress(message)
  need(type(message)is dict and set(message)<={'jsonrpc','id','method','params'}and message.get('jsonrpc')=='2.0','MCP_JSONRPC_REQUEST')
  method=message.get('method');params=message.get('params',{});need(type(params)is dict,'MCP_PARAMS_OBJECT')
  if method=='notifications/initialized':need('id'not in message and params=={},'MCP_INITIALIZED_NOTIFICATION');return None
  need(type(message.get('id'))in(str,int)and type(message.get('id'))is not bool,'MCP_REQUEST_ID');need(len(wire(message['id']))<=1024,'MCP_REQUEST_ID_BOUND')
  if method=='initialize':
   need(set(params)<={'protocolVersion','capabilities','clientInfo'}and type(params.get('protocolVersion'))is str and type(params.get('capabilities',{}))is dict,'MCP_INITIALIZE_FIELDS');return 'CHAT_READ'
  if method=='tools/list':need(params=={},'MCP_TOOLS_LIST_FIELDS');return 'CHAT_READ'
  need(method=='tools/call'and set(params)=={'name','arguments'},'MCP_FIXED_METHOD_ONLY');name=params['name'];need(type(name)is str and name in self.rules and name not in self.deny,'MCP_TOOL_NOT_QUALIFIED_OR_DENIED')
  arguments=params['arguments']
  # Fixed routing/auth fields stay fail-stop even when the native schema also
  # encodes their allowed values as enum. Never downgrade identity/scope failure
  # merely because schema validation happened to encounter the same field first.
  for field,values in self.rules[name]['scope_fields'].items():need(type(arguments)is dict and field in arguments and type(arguments[field])is str and arguments[field]in values,'MCP_TOOL_CROSS_SCOPE')
  validate_schema(arguments,self.declarations[name]['inputSchema']);argument_need(len(wire(arguments))<=FRAME_CAP,'MCP_ARGUMENT_BYTE_BOUND')
  if self.scope_guard is not None:self.scope_guard.before(self.identity,name,arguments)
  return self.rules[name]['kind']
 def response(self,request,response):
  need(type(response)is dict and set(response)<={'jsonrpc','id','result','error'}and response.get('jsonrpc')=='2.0'and type(response.get('id'))is type(request['id'])and response.get('id')==request['id'],'MCP_NATIVE_RESPONSE_IDENTITY')
  need(('result'in response)^('error'in response),'MCP_NATIVE_RESPONSE_ENVELOPE')
  if request['method']=='tools/list':
   result=response.get('result');need(type(result)is dict,'MCP_NATIVE_TOOL_DECLARATIONS_CHANGED')
   keys=set(result)
   # Original pinned Gitea1.11.0's tools/list has these passive cache fields.
   # Preserve their native bytes/values, not arbitrary future metadata or policy.
   if keys=={'tools','ttlMs','cacheScope'}:need(self.identity.purpose=='gitea'and type(result['ttlMs'])is int and result['ttlMs']==0 and result['cacheScope']=='public','MCP_NATIVE_CACHE_METADATA_CHANGED')
   else:need(keys=={'tools'},'MCP_NATIVE_TOOL_DECLARATIONS_CHANGED')
   need(result['tools']==self.tools,'MCP_NATIVE_TOOL_DECLARATIONS_CHANGED')
   value=copy.deepcopy(response);value['result']['tools']=copy.deepcopy(self.exposed);return value
  return response
 def authorization_response(self,response,terminal):
  """Verify original native text using metadata-only pre-notice prefix proofs.

  Returned copy is for fixed-scope identity authorization only. Worker receives
  the original notice-augmented response unchanged; no suffix delimiter guesses,
  payload duplication in control/event logs or notice bypass are introduced.
  """
  proof=terminal.get('native_text')
  if proof is None:
   need(not getattr(self.scope_guard,'requires_native_text_integrity',False),'MCP_NATIVE_TEXT_PROOF_REQUIRED')
   return response
  need(type(proof)is dict and set(proof)=={'content_count','prefixes'}and type(proof['prefixes'])is list,'MCP_NATIVE_TEXT_PROOF_SHAPE')
  content=response.get('result',{}).get('content');count=proof['content_count'];prefixes=proof['prefixes']
  if count is None:
   need(not isinstance(content,list)and prefixes==[],'MCP_NATIVE_TEXT_PROOF_CONTENT');return response
  need(type(count)is int and 0<=count<=10000 and type(content)is list and len(prefixes)<=count,'MCP_NATIVE_TEXT_PROOF_BOUND')
  need(len(content)==count or len(content)==count+1 and not prefixes and type(content[-1])is dict and content[-1].get('type')=='text','MCP_NATIVE_TEXT_CONTENT_COUNT')
  value=copy.deepcopy(response);original=value['result']['content'][:count];observed=set()
  for item in prefixes:
   need(type(item)is dict and set(item)=={'index','bytes','sha256'},'MCP_NATIVE_TEXT_PREFIX_FIELDS');index=item['index'];length=item['bytes']
   need(type(index)is int and 0<=index<count and index not in observed and type(length)is int and 0<=length<=FRAME_CAP,'MCP_NATIVE_TEXT_PREFIX_BOUND');observed.add(index);sha(item['sha256'])
   entry=original[index];need(type(entry)is dict and entry.get('type')=='text'and type(entry.get('text'))is str,'MCP_NATIVE_TEXT_PREFIX_KIND');raw=entry['text'].encode();need(len(raw)>=length,'MCP_NATIVE_TEXT_PREFIX_LENGTH');raw=raw[:length]
   need(hashlib.sha256(raw).hexdigest()==item['sha256'],'MCP_NATIVE_TEXT_PREFIX_HASH')
   try:entry['text']=raw.decode('utf-8')
   except UnicodeError:raise Refused('MCP_NATIVE_TEXT_PREFIX_UTF8')from None
  need(observed=={index for index,entry in enumerate(original)if type(entry)is dict and entry.get('type')=='text'},'MCP_NATIVE_TEXT_PREFIX_COVERAGE')
  value['result']['content']=original;return value
 def verify_backend(self,command,environment,cwd):
  if self.scope_guard is not None:self.scope_guard.backend(self.identity,command,environment,cwd)
 def worker_ready(self):
  return self.scope_guard is None or self.scope_guard.ready(self.identity)
 def physical_complete(self,request,response):
  if self.scope_guard is not None:self.scope_guard.complete(self.identity,request,response)

def board_rules(board_ids):
 need(type(board_ids)is list and board_ids and len(set(board_ids))==len(board_ids)and all(type(v)is str and v for v in board_ids),'MCP_BOARD_SCOPE')
 return {name:{'kind':'CHAT_WRITE'if name=='board_write'else'CHAT_READ','scope_fields':{'board_id':board_ids},'native_self_scope_qualified':False}for name in ('board_read','board_write','board_grep','board_unfold')}
