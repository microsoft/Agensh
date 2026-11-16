"""Independent branch owner in the SAME trusted host interpreter.

Does not patch/mainline step/start/targets/resume/fence/task/ledger. OPS handles
16M diagnostic cut + immediate native release and writes FORK_SOURCE_16M.json.
Manager can start late from that immutable source, with separate SEARCH/AUX DB,
manifest/trajectory namespace, queue, native final children and fee roots.
"""
from pathlib import Path
import copy,json,os,threading,time
from common import need,digest,wire,publish,hash_file,private_dir,strict
from manifest import compile_manifest
from budget import Ledger
from model_capacity import ModelCapacity
from final_host_rpc import HostServer
from final_queue import FinalQueue
from native_final_dispatch import NativeFinalDispatcher
from native_images import ORIGINAL_INVENTORY
from run_native_scientific6 import _copy_opaque
from feasibility_relay import ChatTransport
from collector import collect
from aggregate_prompt import render,PILOT_SHA
from aggregate_projection import project,load_recollector,MysqlDiscussionExport
from aggregate_phase import Phase
from aggregate_agent import DockerSandbox,Agent
from aggregate_source import read,NAME
from aggregate_capacity import CapacityPeer,share_final_slots
from aggregate_final_binding import install as install_rng
import aggregate_final

FIELDS={'schema','pilot_campaign','pilot_campaign_sha256','recollector','recollector_sha256','docker_command','toolchain_image','mysql_image','host_socket'}

def memory_available():
 return int(next(x.split()[1]for x in Path('/proc/meminfo').read_text().splitlines()if x.startswith('MemAvailable:')))*1024

class Manager:
 def __init__(self,driver,config):
  self.driver=driver;self.config=copy.deepcopy(config);self.lock=threading.RLock();self.records={};self.last_error=None;self.needs_caretaker=False;self.finished=False
  need(set(config)==FIELDS and config['schema']=='agensh-fork-aggregate-runtime-v1','AGGREGATE_CONFIG_EXACT_FIELDS')
  need(config['pilot_campaign_sha256']==PILOT_SHA,'AGGREGATE_CONFIG_PILOT_PIN')
  self.prompt,self.prompt_pin=render(config['pilot_campaign']);self.recollector=load_recollector(config['recollector'],config['recollector_sha256'])
  need(config['toolchain_image'].startswith('sha256:')and len(config['toolchain_image'])==71 and config['mysql_image']=='sha256:c831a0f11348d402b43d77453e17d770be2eef356615a2823fe0f5a0d6c8b9af','AGGREGATE_PINNED_ORIGINAL_IMAGES')
  need(type(config['docker_command'])is list and config['docker_command']and all(type(x)is str for x in config['docker_command']),'AGGREGATE_EXPLICIT_DOCKER_ENDPOINT')
  self.home=driver.root/'late-aggregate-fork';self.home.mkdir(mode=0o700)
  self.manifest=copy.deepcopy(driver.manifest);self.manifest['experiment_id']+='-fork16plus4';self.manifest['revision']+=1
  # Keep the approved experiment root: trusted FINAL's existing SDK/framework
  # paths are frozen there. All financial/output state is in this new subroot.
  self.manifest['protocol']['collaboration_prompt']=self.prompt_pin['rendered_utf8_sha256']
  rows=compile_manifest(self.manifest)['trajectories'];by_key={(r['setting'],r['block']):r for r in rows}
  self.branch_rows={t:by_key[(r['setting'],r['block'])]for t,r in driver.rows.items()}
  need(len(self.branch_rows)==6,'AGGREGATE_ALL_SIX_NO_SELECTION')
  self.l=Ledger(self.home/'ledger');self.l.native_unmanaged_cli=True;self.l.enable_unknown_reservation_policy()
  sch=self.manifest['scheduling'];self.peer=CapacityPeer(driver.ledger,self.l,search_cap=sch['search_cap'],global_cap=sch['global_gateway_cap'],hold=lambda:driver.failed)
  f=driver.final
  self.capacity=ModelCapacity(self.l,native_transport_sha256=hash_file(Path(f['native_directory'])/'cc_streaming.py')['sha256'],native_classifier_sha256=hash_file(Path(f['native_directory'])/'request_policy.py')['sha256'],global_allocated_cap=sch['global_gateway_cap'],auxiliary_cap=sch['auxiliary_cap']);self.released=False
  self.queue=FinalQueue(self.home/'final-queue',manifest_sha256=digest(self.manifest),global_cap=sch['final_global_cap'])
  self.final_slots=share_final_slots(driver.queue,self.queue,cap=min(12,sch['final_global_cap']))
  socket=Path(config['host_socket']);need(socket.is_absolute()and socket.resolve()==socket and socket.is_relative_to(Path(driver.manifest['root']))and len(os.fsencode(socket))<100,'AGGREGATE_SHORT_PRIVATE_HOST_SOCKET')
  self.server=HostServer(socket,self.capacity);self.server.start();self.final_points={};install_rng()
  env=dict(f['environment']);env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join([str(Path(__file__).parent),str(Path(__import__('native_final_dispatch').__file__).parent)]))
  self.dispatcher=NativeFinalDispatcher(self.l,self.queue,self.capacity,self.server,directory=self.home/'final-children',configuration=self.final_configuration,python_command=tuple(f['python_command']),environment=env)
  self.dispatcher.entry=Path(__file__).with_name('run_aggregate_final_child.py');self.dispatcher.entry_pin=hash_file(self.dispatcher.entry)
  self.policy={'schema':'agensh-v2-all-six-independent-aggregate-fork-v1','all_six':sorted(driver.rows),'nominal_source':16_000_000,'branch_cap':4_000_000,'nominal_final':20_000_000,'K_at16':0,'K_branch20':3,
   'prompt':self.prompt_pin,'config_sha256':digest(config),'candidate_rule':'original-count14-no-change','mainline_after_snapshot':'immediate-native-release-and-continue-to50M',
   'accounting':'independent-ledger-SEARCH4M-plus-independent-AUX-K3','fee_category':'综合分支','mainline_search_budget_delta':0,'extra_search_total_nominal':24_000_000,
   'snapshot_input':'immutable16M-CAS-copy-no-live-workspace','engine':'single-host-driven-Responses-agent-execute_bash-think-finish','no_agent_custody_state_machine':True,
   'conservative_tail':'no-transfer-from-mainline','results_based_selection':False,'global_final_subtask_cap':self.final_slots['global_final_subtask_cap']}
  publish(self.home/'PREREGISTERED.json',wire(self.policy),mode=0o400);publish(self.home/'MANIFEST.json',wire(self.manifest),mode=0o400);publish(self.home/'aggregate-prompt.txt',self.prompt.encode(),mode=0o400)
  with self.l.tx():self.l.event('GLOBAL','ALL_SIX_FORK_AGGREGATE_REGISTERED',{'sha256':digest(self.policy),'all_six':sorted(driver.rows)})
  self.thread=None
 def bind_main_gates(self):
  for r in list(self.driver.records.values()):
   launch=r.get('launch')
   if launch is not None:self.peer.bind_gate(launch.gate)
 def admit(self,parent):
  # Reserve18GiB for each concurrent projection/container startup not yet
  # reflected in MemAvailable; do not admit six against the same free sample.
  pending=sum(18*2**30 for r in list(self.records.values())if r['state']=='STARTING' or (r['state']=='AGGREGATE_SEARCH'and not getattr(r.get('sandbox'),'started',False)))
  if memory_available()-pending<84*2**30:return None
  return self.driver.admit(self.driver.rows[parent],'late-aggregate-fork-start')
 def final_configuration(self,job):
  point=job['point'];f=self.driver.final
  if point not in self.final_points:
   home=private_dir(self.home/'final-points'/digest(point),create=True);need(not any(home.iterdir()),'AGGREGATE_FRESH_FINAL_POINT')
   self.final_points[point]={'home':home,'ready':False};ev=private_dir(home/'evaluator-private',create=True);cr=private_dir(home/'credentials',create=True)
   for name,pin in self.driver.profile['evaluator_assets'].items():_copy_opaque(Path(f['evaluator_root'])/name,ev/name,pin['sha256'])
   _copy_opaque(f['credential_source'],cr/'glm_api_key');self.final_points[point]['ready']=True
  p=self.final_points[point];need(p['ready'],'AGGREGATE_FINAL_PREP_NO_RETRY')
  return {'manifest':self.manifest,'model_policy':self.driver.config['model_policy'],'input_root':job['input_root'],'input_policy_sha256':job['input_policy'],'trajectory':job['trajectory'],'k':job['replicate'],
   'aux_root':str(p['home']),'native_directory':f['native_directory'],'profile':self.driver.profile,
   'services':{'schema':'count14-agensh-final-services-v1','purpose':'AUX_FINALIZATION','framework_root':f['framework_root'],'docker_host':'unix:///var/run/docker.sock','docker_config':f['docker_config'],'dependency_freeze_sha256':f['dependency_freeze_sha256']},
   'image_freeze':{'schema':'count14-agensh-images-v1','manifest_sha256':digest(self.manifest),'docker_host':'unix:///var/run/docker.sock','original_inventory_sha256':ORIGINAL_INVENTORY,'images':strict(Path(f['image_mapping']).read_bytes())},'space_home':str(self.home/'final-space')}
 def fail(self,parent,record,error):
  record.update(state='FAULT_RETAINED',error_type=type(error).__name__);self.last_error=type(error).__name__
  phase=record.get('phase')
  if phase is not None:
   if phase.l.frontier(phase.id)['state']=='RUNNING':phase.l.close_admission(phase.id,'LATE_AGGREGATE_BRANCH_FAILURE_RETAINED')
   phase.gate.notify()
  # No exception message/body, no retry and NO driver fault for a branch-only
  # infrastructure failure. Model/accounting incidents still stop/report.
  code=getattr(error,'code',None)
  stop=self.l.admission_fault(record['branch_id'])if phase else None
  unsafe=bool(stop)or code in ('UPSTREAM_TOKEN_BOUND_VIOLATION','LOCAL_PROMPT_RESERVATION_EXCEEDED_USAGE_RETAINED','ACCOUNTED_PROTOCOL_ERROR')
  if unsafe:
   self.needs_caretaker=True
   with self.driver.ledger.tx():
    self.driver.ledger.db.execute("UPDATE model_control SET paused=1,epoch=epoch+1,reason='AGGREGATE_BRANCH_MODEL_OR_BILLING_INCIDENT' WHERE singleton=1")
    self.driver.ledger.event('GLOBAL','AGGREGATE_BRANCH_MODEL_OR_BILLING_INCIDENT',{'error_type':type(error).__name__,'branch_trajectory':record['branch_id']})
  with self.l.tx():self.l.event(record['branch_id'],'AGGREGATE_BRANCH_FAILURE_RETAINED',{'error_type':type(error).__name__,'mainline_state_modified':False,'retry':False,'needs_caretaker':unsafe})
  publish(record['home']/'FAULT_RETAINED.json',wire({'error_type':type(error).__name__,'retry':False,'needs_caretaker':unsafe}),mode=0o400)
 def start_one(self,parent,source,evidence):
  need(parent not in self.records,'AGGREGATE_BRANCH_ONCE_NO_REPLAY')
  home=self.home/digest(parent);home.mkdir(mode=0o700)
  record={'state':'STARTING','thread':None,'parent':parent,'branch_id':self.branch_rows[parent]['trajectory_id'],'home':home,'source':copy.deepcopy(source),'error_type':None};self.records[parent]=record
  publish(home/'SOURCE.json',wire(source),mode=0o400)
  if not self.released:self.capacity.release(owner_evidence=evidence);self.released=True
  def run():
   try:self.run_one(parent,record)
   except BaseException as e:self.fail(parent,record,e)
  thread=threading.Thread(target=run,name='fork-aggregate-'+digest(parent)[:12],daemon=False);record['thread']=thread;thread.start()
 def run_one(self,parent,record):
  original=self.driver.records[parent];owner=original['launch'].controller;source=record['source'];home=record['home']
  phase=Phase(self.driver,original,home/'search',self.prompt_pin,ledger=self.l,manifest=self.manifest,source=source,branch_id=record['branch_id'],peer=self.peer);record['phase']=phase
  view,projection=project(owner.cas,source['snapshot'],source['expected'],home/'readonly-source',recollector=self.recollector,mysql_export=MysqlDiscussionExport(self.config['docker_command'],self.config['mysql_image']))
  for p in [view,*view.rglob('*')]:
   if not p.is_symlink():p.chmod(0o555 if p.is_dir()or p.stat().st_mode&0o111 else 0o444)
  work=home/'aggregate-workspace';work.mkdir(mode=0o755)
  sandbox=DockerSandbox(self.config['docker_command'],self.config['toolchain_image'],view,work/'output','ag-fork-'+digest(record['branch_id'])[:20]);record['sandbox']=sandbox
  upstream=self.driver.upstream;token=Path(upstream['token_file']).read_text().strip()
  phase.bind(ChatTransport(upstream['base'],token,auth_style=upstream['auth_style'],timeout=upstream['timeout_seconds']))
  record['state']='AGGREGATE_SEARCH';agent=Agent(phase,sandbox,self.prompt);record['agent']=agent
  phase_ref=agent.run();record.update(phase_ref=phase_ref,state='FINAL_INPUT')
  point=home/'point-20000000';point.mkdir(mode=0o700)
  collection=collect(owner.cas,source['snapshot'],point/'collection',expected=source['expected'],member_cap=source['member_cap'],git_exports=source['git_exports'],registered_refs=tuple(source['registered_refs']))
  inputs=aggregate_final.build(owner.cas,source['snapshot'],phase_ref,collection,point/'v21',expected=source['expected'],setting=source['setting'],member_cap=source['member_cap'],branch_manifest=self.manifest)
  jobs=self.queue.enqueue(point/'v21',policy_sha256=inputs['input_policy_sha256'],trajectory=phase.id,setting=source['setting']);need(len(set(jobs))==3,'AGGREGATE_BRANCH_EXACT_K3')
  metadata={'point_kind':'AGGREGATE_BRANCH','target_tokens':20_000_000,'parent_trajectory':parent,'trajectory':phase.id,'original16_snapshot':source['snapshot'],'aggregate_phase_snapshot':phase_ref,'input_policy_sha256':inputs['input_policy_sha256'],
   'jobs':jobs,'final_completed':False,'budget_accounting':phase.accounting(),'prompt':self.prompt_pin,'candidate_counts':inputs['candidate_counts'],'fee_category':'综合分支','mainline_search_budget_delta':0}
  publish(point/'POINT_QUEUED.json',wire(metadata),mode=0o400)
  with self.l.tx():self.l.event(phase.id,'AGGREGATE_BRANCH_K3_QUEUED',metadata)
  record.update(state='K3_QUEUED',point=metadata)
 def settle(self):
  for parent,r in list(self.records.items()):
   if r['state']!='K3_QUEUED':continue
   ids=r['point']['jobs']
   with self.queue.mutex:jobs=[self.queue._job(j)for j in ids]
   point=self.dispatcher.points.get(jobs[0]['point'])
   if point is None or not point['audited']:continue
   # Native dispatcher has audited exact K3 incl approved replacements. Report
   # actual point fees from that audited auxiliary root, never search budget.
   key=jobs[0]['point'];point=self.dispatcher.points[key];need(point['audited'],'AGGREGATE_K3_AUDIT_REQUIRED')
   audit=strict((point['aux']/'K3_AUDIT.json').read_bytes())
   fee={'schema':'agensh-aggregate-branch-fees-v1','parent_trajectory':parent,'branch_trajectory':r['branch_id'],'fee_category':'综合分支','billing_domain':'SEARCH_AGGREGATE_BRANCH_PLUS_AUX','search':r['phase'].accounting(),'successful_aux_tokens':audit['finalization_tokens'],'mainline_search_budget_delta':0,'K3_audit':hash_file(point['aux']/'K3_AUDIT.json')}
   # Failed replicate costs remain in this independent ledger/native AUX paths.
   failed=[]
   if self.l.db.execute("SELECT 1 FROM sqlite_master WHERE name='aux_attempt_allocations'").fetchone():
    failed=[strict(x[0])for x in self.l.db.execute('SELECT metadata FROM aux_attempt_allocations')if strict(x[0])['point_id']==key]
   fee['failed_replicate_system_allocations']=failed
   publish(r['home']/'FEES.json',wire(fee),mode=0o400)
   with self.l.tx():self.l.event(r['branch_id'],'AGGREGATE_BRANCH_FEES_CLOSED',fee)
   r['state']='COMPLETE'
 def step(self):
  with self.lock:
   self.bind_main_gates()
   paused=self.l.db.execute('SELECT paused,reason FROM model_control WHERE singleton=1').fetchone()
   if paused and paused[0] and paused[1]!='NEW_CURRENT_OWNER_REQUIRES_RELEASE':self.needs_caretaker=True
   for parent,original in list(self.driver.records.items()):
    if self.needs_caretaker or self.driver.failed:break
    if parent in self.records or not hasattr(original.get('launch'),'controller'):continue
    owner=original['launch'].controller;path=owner.root/NAME
    if not path.exists():continue
    source=read(owner.cas,path,parent=parent,manifest_sha=digest(self.driver.manifest))
    evidence=self.admit(parent)
    if evidence is not None:self.start_one(parent,source,evidence)
   self.dispatcher.poll()
   if memory_available()>=64*2**30 and self.released and not self.needs_caretaker and not self.driver.failed:
    while self.dispatcher.dispatch_one()is not None:pass
   self.settle();self.finished=len(self.records)==6 and all(r['state']=='COMPLETE'for r in self.records.values())
   return self.status()
 def status(self):
  return {'schema':'agensh-aggregate-fork-status-v1','finished':self.finished,'needs_caretaker':self.needs_caretaker,'last_error_type':self.last_error,'fee_category':'综合分支','mainline_search_budget_delta':0,'parent_driver_failed':self.driver.failed,'branch_ledger':str(self.l.home),
   'records':{t:{'state':r['state'],'branch_trajectory':r['branch_id'],'error_type':r['error_type'],'source_snapshot':r['source']['snapshot'],'search':r['phase'].accounting()if r.get('phase')else None}for t,r in list(self.records.items())},'dispatcher':self.dispatcher.status()}
 def run(self):
  while not self.finished:
   try:self.step()
   except BaseException as e:
    self.last_error=type(e).__name__
    # Preserve interpreter, child handles, owner locks. No automatic replay.
    p=self.home/'MANAGER_FAULT_RETAINED.json'
    if not p.exists():publish(p,wire({'exception_type':type(e).__name__,'retry':False,'mainline_state_modified':False}),mode=0o400)
    return
   time.sleep(.5)
  publish(self.home/'COMPLETE.json',wire(self.status()),mode=0o400)
 def start(self):
  need(self.thread is None,'AGGREGATE_MANAGER_START_ONCE');self.bind_main_gates()
  self.thread=threading.Thread(target=self.run,name='aggregate-fork-owner',daemon=False);self.thread.start()

def install(driver,config):
 need(not hasattr(driver,'late_aggregate_fork_manager'),'AGGREGATE_INSTALL_ONCE')
 need({(r['setting'],r['block'])for r in driver.rows.values()}=={(f'Agensh-{n}',b)for n in(1,16)for b in(1,2,3)},'AGGREGATE_EXACT_ALL_SIX')
 manager=Manager(driver,config);driver.late_aggregate_fork_manager=manager;manager.start()
 return {'installed':True,'all_six':sorted(driver.rows),'prompt':manager.prompt_pin,'mainline_methods_patched':False,'16M_hard_park_added':False,'financial_ledger_separate':True,'source_file':NAME}

def apply(driver):
 return install(driver,strict((driver.root/'FORK_AGGREGATE_RUNTIME.json').read_bytes()))
