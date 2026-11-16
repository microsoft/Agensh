"""One host-driven synthesis agent; sandbox has NO network or credentials.

All model sends and full-context records use original ScientificRelay. Tools are
plain execution, not callback custody/receipt/state-machine guards. Original
team continues independently after its 16M snapshot. No hidden evaluator or FINAL credentials are used.
"""
from pathlib import Path
import copy,json,os,subprocess,time
from common import need,digest,wire,publish
from protocol import prepare,Rejected
TOOLS=[
 {'type':'function','name':'execute_bash','description':'Execute a bash command in the local workspace.','parameters':{'type':'object','properties':{'command':{'type':'string'},'timeout':{'type':'integer','minimum':1,'maximum':600}},'required':['command'],'additionalProperties':False}},
 {'type':'function','name':'think','description':'Record a thought.','parameters':{'type':'object','properties':{'thought':{'type':'string'}},'required':['thought'],'additionalProperties':False}},
 {'type':'function','name':'finish','description':'Finish the current task.','parameters':{'type':'object','properties':{'message':{'type':'string'}},'additionalProperties':False}}]
# Verbatim pilot Role.advance() response, not new synthesis guidance.
CONTINUE='The continuous search allocation remains available. Your current results are retained. Continue autonomous work toward the 14-candidate goal and keep progress.md and candidate files durable; the host will perform checkpoint finalization separately.'
AUTONOMOUS='Continue autonomously with your best judgment and keep durable results. No human answer or hidden evaluation feedback is available.'

def compact(items,limit=180_000):
 """Keep first prompt and complete newer assistant/tool groups. No new prompt.
 Full preceding requests remain in original durable relay records. This is a
 deterministic token-free context bound, never a free summarizing model.
 """
 out=copy.deepcopy(items)
 results=[i for i,x in enumerate(out)if x.get('type')=='function_call_output']
 for i in results[:-6]:
  if len(out[i]['output'])>2000:out[i]['output']=out[i]['output'][:2000]+'\n[Earlier result truncated; saved records remain available through data tools.]'
 while len(wire(out))>limit and len(out)>2:
  # A whole model response group starts at its first message/function call and
  # includes all call outputs. Do not retain orphaned call results.
  end=next((i for i in range(2,len(out))if out[i].get('_turn_start')),len(out))
  del out[1:end]
 for x in out:x.pop('_turn_start',None)
 need(len(wire(out))<=limit,'AGGREGATE_CONTEXT_SINGLE_TURN_CAP')
 return out

class DockerSandbox:
 def __init__(self,docker,image,view,output,name):
  need(type(image)is str and image.startswith('sha256:')and len(image)==71,'AGGREGATE_PINNED_IMAGE')
  self.docker=list(docker);self.image=image;self.view=Path(view);self.output=Path(output);self.name=name;self.started=False;self.frozen=False;self.identity=None
  self.output.mkdir(mode=0o755);(self.output/'pocs').mkdir(mode=0o755);(self.output/'progress.md').touch(mode=0o666);os.chmod(self.output/'progress.md',0o666);os.chmod(self.output/'pocs',0o777)
 def command(self):
  # Only these two objects writable. No Docker socket, host IPC, HOME, token,
  # provider environment, mutable source tree or live Gitea/MM endpoint mounted.
  return self.docker+['run','-d','--name',self.name,'--hostname','repo-workspace','--network','none','--read-only',
   '--user','1000:1000','--cpus','4','--memory','16g','--memory-swap','16g','--pids-limit','512','--ulimit','nofile=65536:65536',
   '--cap-drop','ALL','--security-opt','no-new-privileges','--env','HOME=/nonexistent','--env','TMPDIR=/work/output/pocs',
   '--mount','type=bind,src='+str(self.view)+',dst=/work,readonly',
   '--mount','type=bind,src='+str(self.output/'pocs')+',dst=/work/output/pocs',
   '--mount','type=bind,src='+str(self.output/'progress.md')+',dst=/work/output/progress.md',
   '--workdir','/work','--entrypoint','/bin/bash',self.image,'--noprofile','--norc','-c','exec sleep infinity']
 def inspect(self):
  r=subprocess.run(self.docker+['inspect','--format','{{json .}}',self.name],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
  need(r.returncode==0,'AGGREGATE_EXACT_CONTAINER_INSPECT');return json.loads(r.stdout)
 def start(self):
  need(not self.started,'AGGREGATE_SANDBOX_START_ONCE')
  r=subprocess.run(self.command(),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL);need(r.returncode==0,'AGGREGATE_SANDBOX_START')
  self.started=True;data=self.inspect();state=data['State'];pid=state['Pid'];fields=Path('/proc',str(pid),'stat').read_text();start=fields[fields.rfind(')')+2:].split()[19]
  self.identity={'container_id':data['Id'],'pid':pid,'start_ticks':start,'image':data['Image']}
  need(data['HostConfig']['NetworkMode']=='none'and data['HostConfig']['ReadonlyRootfs']is True and not state['Paused']and state['Running'],'AGGREGATE_SANDBOX_ISOLATION')
  mounts={r['Destination']:r for r in data['Mounts']};need(set(mounts)=={'/work','/work/output/pocs','/work/output/progress.md'}and not mounts['/work']['RW']and mounts['/work/output/pocs']['RW']and mounts['/work/output/progress.md']['RW'],'AGGREGATE_EXACT_WRITE_MOUNTS')
  self.execute('test -r /work/proposals/round-0001/team-discussion.jsonl && test -d /work/repo && test -w /work/output/pocs && test -w /work/output/progress.md',timeout=10,require_zero=True)
  return dict(self.identity)
 def execute(self,command,timeout=120,require_zero=False):
  need(self.started and not self.frozen and type(command)is str and 0<=len(command)<=1024*1024,'AGGREGATE_TOOL_EXECUTION')
  try:
   r=subprocess.run(self.docker+['exec','-i','--user','1000:1000','--workdir','/work',self.name,'/bin/bash','--noprofile','--norc','-c',command],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=max(1,min(600,timeout)))
   code=r.returncode;raw=r.stdout
  except subprocess.TimeoutExpired as e:
   # Never replay a command or claim background descendants dead. At final the
   # entire registered container cgroup is frozen before workspace capture.
   code=124;raw=e.stdout or b''
  if require_zero:need(code==0,'AGGREGATE_PUBLIC_UID_MOUNT_PREFLIGHT')
  text=raw.decode('utf-8','replace')
  if len(text)>30000:text=text[:12000]+'\n[Output truncated.]\n'+text[-18000:]
  return {'output':text,'exit_code':code}
 def freeze(self):
  need(self.started and not self.frozen,'AGGREGATE_FREEZE_ONCE')
  before=self.inspect();need(before['Id']==self.identity['container_id']and before['State']['Pid']==self.identity['pid'],'AGGREGATE_EXACT_FRESH_PROCESS')
  r=subprocess.run(self.docker+['pause',self.name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);need(r.returncode==0,'AGGREGATE_WHOLE_CONTAINER_PAUSE')
  after=self.inspect();need(after['Id']==self.identity['container_id']and after['State']['Paused']is True,'AGGREGATE_WHOLE_CGROUP_FROZEN')
  self.frozen=True;return {'schema':'agensh-late-single-agent-whole-cgroup-freeze-v1',**self.identity,'cgroup_frozen':True,'whole_container':True,'network':'none','mainline_controlled_by_branch':False,'at_ns':time.time_ns()}

class Agent:
 def __init__(self,phase,sandbox,prompt):self.phase=phase;self.sandbox=sandbox;self.prompt=prompt;self.items=[{'role':'user','content':prompt}];self.turns=0
 def request(self):
  request={'model':self.phase.relay.model,'input':compact(self.items),'tools':TOOLS,'store':False,'stream':False,'temperature':1,'top_p':1,'reasoning':{'effort':'max'}}
  maximum=self.phase.driver.config['maximum_output']
  if maximum is not None:request['max_output_tokens']=maximum
  return request
 def step(self):
  request=self.phase.profile.normalize(self.request());chat,_=prepare(request,[],model=self.phase.relay.model,max_output=self.phase.driver.config['maximum_output'])
  if not self.phase.before_call(self.phase.driver.bounds.upper(chat)):return False
  try:response=self.phase.relay.run(request,(self.phase.id,'worker-00'))
  except Rejected:
   # Single UNKNOWN is charged by original ledger policy; never replay it.
   f=self.phase.l.frontier(self.phase.id)
   if self.phase.l.admission_fault(self.phase.id):raise
   rows=self.phase.l.db.execute('SELECT id,state FROM requests WHERE trajectory=? ORDER BY rowid DESC LIMIT 1',(self.phase.id,)).fetchall()
   if rows and rows[0]['state']=='UNKNOWN'and self.phase.l.unknown_charged(rows[0]['id']):
    self.items.append({'role':'user','content':'The previous model transmission did not complete. Its possible full usage has been reserved in the budget. No action from that incomplete transmission was executed. Continue from the last delivered state; do not assume the lost response was delivered.','_turn_start':True});return True
   raise
  self.turns+=1;first=True;has_call=False
  for item in response['output']:
   if item['type']=='message':entry={'role':'assistant','content':''.join(p.get('text','')for p in item['content'])}
   elif item['type']=='function_call':entry={k:item[k]for k in('type','call_id','name','arguments')};has_call=True
   else:continue
   entry['_turn_start']=first;first=False;self.items.append(entry)
   if item['type']=='function_call':
    try:args=json.loads(item['arguments'])
    except(ValueError,TypeError):args=None
    if item['name']=='execute_bash'and type(args)is dict and type(args.get('command'))is str:
     result=self.sandbox.execute(args['command'],timeout=args.get('timeout',120));out=wire(result).decode()
    elif item['name']=='think':out='Your thought has been logged.'
    elif item['name']=='finish':out=CONTINUE
    else:out='Unsupported tool or invalid arguments.'
    self.items.append({'type':'function_call_output','call_id':item['call_id'],'output':out})
  if not has_call:self.items.append({'role':'user','content':AUTONOMOUS,'_turn_start':True})
  return True
 def run(self):
  self.sandbox.start()
  while self.step():pass
  receipt=self.sandbox.freeze();return self.phase.seal(self.sandbox.output.parent,receipt)
