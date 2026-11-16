"""Persistent repo-only comparison driver. Tool/model payloads stay private."""
import pathlib,sys,os,json,subprocess,importlib.util,uuid,time,fcntl,hashlib,shutil,traceback,contextlib,shlex
SHELL_LOST=('The terminal session exited unexpectedly while this command was running; its output and any process it started were lost. '
 'A new terminal session has been started in the same container and working directory. Shell variables were not preserved; files under /workspace are retained.')
from comparison_core import *
from pilot_runtime_binding import configure_environment, bind_request
_services=configure_environment()
E=ROOT;C=pathlib.Path(__file__).resolve().parent;sys.path[:0]=[str(C),_services['framework_root']]
for key in ['DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH']:os.environ.pop(key,None)

def docker(*args,**kw):return subprocess.run(['docker',*args],check=True,capture_output=True,**kw)
def copy_tree(source,dest):
 assert not pathlib.Path(dest).exists();pathlib.Path(dest).parent.mkdir(parents=True,exist_ok=True)
 subprocess.run(['cp','-a','--reflink=auto',str(source),str(dest)],check=True,capture_output=True)

class Transport:
 def __init__(self,role):self.role=role;self.last_request=None
 def completion(self,kind,**kwargs):
  from pilot_initialization_smoke import assert_model_allowed
  assert_model_allowed()
  from request_policy import execute
  from context_policy import compact_messages
  from litellm import ModelResponse
  role=self.role
  body=dict(model=MODEL,messages=compact_messages(kwargs['messages'],kwargs.get('tools',[])),temperature=1.,top_p=1.,reasoning_effort='max',stream=True,stream_options={'include_usage':True})
  if kwargs.get('tools'):body['tools']=kwargs['tools']
  body=bind_request(body,role=role.name,action_index=role.state.iteration)
  def status(phase,**kw):
   if phase=='REQUEST_CHARGED_WITHOUT_RESPONSE':
    from request_policy import interruption_notice
    from openhands.events.action import MessageAction
    from openhands.events.event import EventSource
    role.add(MessageAction(content=interruption_notice([])[0]['content']),EventSource.USER)
   role.owner.status(phase,**kw)
  data,self.last_request=execute(body,role.owner.ledger,role.name,role.root/'requests',role.owner.setting,kind,status)
  role.owner.status('SEARCHING',role=role.name)
  return ModelResponse(**data)

class Role:
 def __init__(self,owner,name,stage):
  from openhands.controller.state.state import State
  from openhands.events.action import MessageAction
  from openhands.events.event import EventSource
  self.owner=owner;self.name=name;self.stage=stage;self.root=owner.root/'roles'/name;self.root.mkdir(parents=True)
  for sub in ['events','requests','tools']:(self.root/sub).mkdir()
  self.workspace=self.root/'workspace';self.workspace.mkdir();copy_tree(E/'pristine/repo',self.workspace/'repo')
  for sub in ['output/pocs','output/evidence','.runtime-tmp','.runtime-home','proposals']:(self.workspace/sub).mkdir(parents=True)
  self.container='count14-'+owner.setting+'-'+name+'-01a12f95'
  from pilot_images import toolchain_image
  image=toolchain_image(json.loads((C/'toolchain-image.json').read_text())['id'])
  docker('run','-d','--name',self.container,'--hostname','repo-workspace','--network','none','--cpus','4','--memory','16g','--memory-swap','16g','--pids-limit','512','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
    '--mount','type=bind,src='+str(self.workspace)+',dst=/workspace','--mount','type=bind,src='+str(self.workspace/'.runtime-tmp')+',dst=/tmp','--mount','type=bind,src='+str(self.workspace/'.runtime-home')+',dst=/home/agent','--workdir','/workspace',image)
  spec=importlib.util.spec_from_file_location('count14_runtime_'+owner.setting+'_'+name,C/'runtime_base.py');module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
  module.RUN=self.root;module.NAME=self.container;self.base=module
  self.transport=Transport(self);self.agent=module.create_agent(self.transport);self.state=State(session_id='count14-'+owner.setting+'-'+name,max_iterations=2147483647)
  self.shell=module.Shell();self.paused=False;self.activate(False)
  self.add(MessageAction(content=self.prompt()),EventSource.USER)
 def prompt(self):
  if self.owner.setting.startswith('moe'):import group_policy;return group_policy.role_prompt(self)
  common='''You are participating in a repo-only benchmark experiment. The repository at /workspace/repo is the fixed project version. You are told from the beginning that there are 14 hidden benchmark issues in this version. No individual task description is available. Work autonomously from this repository and your own observations to find the issues, and continuously prepare distinct candidate input files. At each cumulative-budget checkpoint (10M,20M,50M,100M tokens across this entire setting), the setting aims to submit 14 content-distinct candidates. Each candidate should reflect a plausible issue, not arbitrary padding or many trivial variants of the same observation. You do not know hidden tests and will never receive hidden evaluation feedback.
Keep durable candidate files in /workspace/output/pocs and concise ongoing findings, reproduction records, file identities, uncertainties and directions in /workspace/output/progress.md. Update these records regularly, before long commands and whenever a finding is obtained; do not defer all file generation to the end. Save all useful data under /workspace (including temporary candidates); /tmp and HOME are persisted by this runtime. Preserve already useful candidate files. Build and investigate only this local repository; network access and external services are unavailable. Do not attempt to access controller data, other experiment settings, task IDs, reference inputs or hidden evaluator resources. Do not request human input. Continue until the host suspends you at the budget boundary. The host handles checkpoint summaries from isolated copies; those summaries do not become part of your search. The budget includes all search input/output tokens and model condensation calls.
'''
  if self.stage=='single':return common+'You are the single search agent and own the entire setting budget. Aim for 14 useful candidates covering different issues. Your current initial budget segment is 10M tokens; the same state continues later up to 100M. Do not call finish merely because a checkpoint is approaching; keep durable progress files current.'
  if self.stage=='proposal':
   count=len(roster(self.owner.setting))-1
   return common+f'You are independent proposal agent {self.name} of {count}. All proposal agents together share 80% of the setting budget, distributed approximately evenly; the final role has 20%. You have no access to peer work. Independently look for a broad set of useful candidates toward the setting target of 14, and write clear progress records and raw candidate files for the final role. The final role is responsible for choosing the setting submission; you are not assigned a hidden task.'
  behavior='Select existing candidates from the proposal agents; do not generate or modify input bytes. Compare the available records and choose a diverse set of up to 14; maintain the selected list in /workspace/output/selection.json as a JSON array of paths under /workspace/proposals. Copy selected files unchanged into output/pocs if useful.' if __import__('setting_registry').final_mode(self.owner.setting)=='select' else 'Synthesize the proposal agents\' observations and candidates. You may combine their insights and develop candidates in your own workspace during this counted search stage. Aim to improve breadth and produce up to 14 useful final candidates.'
  return common+'You are the final role. Proposal handoffs appear under /workspace/proposals/round-XXXX. Read each proposal\'s progress.md and candidate files. Proposal agents do not receive your work or each other\'s work. You have 20% of the entire setting search budget. '+behavior
 def add(self,event,source,cause=None):return self.base.add_event(self.state,event,source,cause)
 def activate(self,active):
  self.shell.tool_watch.set_active(active)
  if active and self.paused:docker('unpause',self.container);self.paused=False
  elif not active and not self.paused:docker('pause',self.container);self.paused=True
 def advance(self):
  from openhands.events.event import EventSource
  from openhands.events.action import MessageAction,CmdRunAction,AgentFinishAction,AgentThinkAction
  from openhands.events.action.agent import CondensationAction
  from openhands.events.observation.agent import AgentThinkObservation
  self.activate(True)
  try:
   action=self.agent.step(self.state);self.add(action,EventSource.AGENT);self.state.iteration+=1
   if isinstance(action,CmdRunAction):
    self.owner.status('TOOL_RUNNING',role=self.name)
    try:obs=self.shell.execute(action.command,action.is_input,timeout=getattr(action,'timeout',None),blocking=getattr(action,'blocking',False),runtime_rules=getattr(self.owner,'runtime_rules',False))
    except RuntimeError as error:
     if str(error)!='Sandbox persistent shell exited':raise
     obs=self.replace_lost_shell(action.command)
    self.add(obs,EventSource.ENVIRONMENT,action)
   elif isinstance(action,AgentThinkAction):self.add(AgentThinkObservation('Your thought has been logged.'),EventSource.ENVIRONMENT,action)
   elif isinstance(action,CondensationAction):pass
   elif isinstance(action,AgentFinishAction):
    self.agent._complete=False;self.add(MessageAction(content='The continuous search allocation remains available. Your current results are retained. Continue autonomous work toward the 14-candidate goal and keep progress.md and candidate files durable; the host will perform checkpoint finalization separately.'),EventSource.USER)
   elif isinstance(action,MessageAction):
    if action.wait_for_response:self.add(MessageAction(content='Continue autonomously with your best judgment and keep durable results. No human answer or hidden evaluation feedback is available.'),EventSource.USER)
   else:raise RuntimeError('Unsupported generic action type '+type(action).__name__)
  finally:
   if not getattr(self.owner,'runtime_rules',False):self.activate(False)
 def replace_lost_shell(self,command):
  from openhands.events.observation import CmdOutputObservation
  cwd,seq=self.shell.cwd,self.shell.seq
  self.shell.tool_watch.close()
  self.shell=self.base.Shell();self.shell.seq=seq
  if cwd!='/workspace':self.shell.execute('cd -- '+shlex.quote(cwd),wait=3)
  self.owner.shell_restarts=getattr(self.owner,'shell_restarts',0)+1
  return CmdOutputObservation(SHELL_LOST,command,metadata={'exit_code':-1,'working_dir':self.shell.cwd})
 def checkpoint(self,directory):
  assert self.paused;directory.mkdir(parents=True)
  raw=pack_agent(self.agent,self.state);(directory/'agent-state.pkl').write_bytes(raw)
  save(directory/'runtime-state.json',dict(container=self.container,paused=True,shell_cwd=self.shell.cwd,shell_sequence=self.shell.seq,shell_pending=bool(self.shell.pending),search_tokens=self.owner.ledger.roles[self.name],last_request=str(self.transport.last_request) if self.transport.last_request else None,iteration=self.state.iteration))
  from checkpoint_archive_v59999995 import archive
  archive(self,directory)
  # Only compact saved records go to the isolated finalizer.
  from context_policy import checkpoint_context
  save(directory/'private-context.json',checkpoint_context(self))
  save(directory/'snapshot-receipt.json',dict(state_sha256=sha(directory/'agent-state.pkl'),workspace_archive_sha256=sha(directory/'workspace.tar.gz'),paused_container=self.container,at=now()))
  return raw
 def restore(self,raw):
  assert self.paused
  # Continue the same paused container/PTY; no background tool or /tmp state
  # is discarded, and explicitly reload all saved agent/controller data.
  self.state=unpack_agent(self.agent,raw)
  assert snapshot_fingerprint(pack_agent(self.agent,self.state))==snapshot_fingerprint(raw),'Saved controller data did not round-trip exactly'

class Setting:
 def __init__(self,setting):
  self.setting=setting;self.root=E/'settings'/setting;self.root.mkdir(parents=True,exist_ok=True)
  assert not (self.root/'started.json').exists(),'No automatic replay of started setting'
  save(self.root/'started.json',dict(at=now(),setting=setting),True)
  self.ledger=Ledger(self.root/'ledger.json',setting);self.roles={name:Role(self,name,stage) for name,stage in roster(setting).items()};self.round=0
 def status(self,phase,**extras):
  save(self.root/'status.json',dict(setting=self.setting,phase=phase,updated_at=now(),actual_search_tokens=self.ledger.actual,target_budget=self.ledger.ceiling,model_calls=self.ledger.calls,unknown_requests=self.ledger.unknown,per_role=dict(self.ledger.roles),per_stage=dict(self.ledger.stages),**extras))
 def run_group(self,names):
  if getattr(self.ledger,"parallel_reservations",False):
   from parallel_roles_v54 import run_group
   return run_group(self,names)
  blocked=set()
  while len(blocked)<len(names):
   if shutil.disk_usage(E).free<40*2**30:raise RuntimeError('Insufficient free scratch space; preserving experiment')
   name=min((n for n in names if n not in blocked),key=lambda n:(self.ledger.roles[n],n))
   try:self.roles[name].advance()
   except BudgetBoundary:blocked.add(name)
   if not self.ledger.drained():raise UnknownRequest()
  self.status('STAGE_BOUNDARY',stage=self.roles[names[0]].stage)
 def handoff(self):
  from legacy_handoff_v59 import publish
  return publish(self)
 def run_until(self,ceiling):
  if self.setting.startswith('moe'):import group_policy;return group_policy.routed(self).run_until(ceiling)
  from trajectory_v51 import run_legacy
  return run_legacy(self,ceiling)
  for amount in range((self.round+1)*10_000_000,ceiling+1,10_000_000):
   self.round+=1;self.ledger.ceiling=amount;self.ledger.persist()
   if self.setting=='single':self.run_group(['single'])
   else:
    self.run_group([n for n,r in self.roles.items() if r.stage=='proposal']);self.handoff();self.run_group(['final'])
  assert self.ledger.drained();self.status('CHECKPOINT_SEARCH_PAUSED')
 def checkpoint(self,budget):
  from checkpoint_jobs import checkpoint_and_enqueue
  return checkpoint_and_enqueue(self,budget)


