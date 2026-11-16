"""Fresh root lifecycle composer; scientific/CLI/checkpoint loops stay native.

Not a replacement SEARCH loop. The original driver creates each team; native
owner handles every drain, whole-team freeze/snapshot/thaw, candidate and K3.
Uses separate branch ledger plus same-root conserved36 physical slots; no old
root restoration or credential/worker control is implemented here.
"""
from pathlib import Path
from types import MethodType
import ast,copy,inspect,os,resource,subprocess,sys,threading,time
from common import need,digest,wire,publish,hash_file
from expansion100_contract import check,group


def node_source(link,target,pin,*,owner_uid=0,target_uid=None):
 """One reported public symlink/target pair, never a shared-host mutation."""
 import stat
 target_uid=owner_uid if target_uid is None else target_uid
 link=Path(link);target=Path(target);before=link.lstat()
 need(link.resolve(strict=True)==target and target.resolve(strict=True)==target,
  'FRESH48_ORIGINAL_HOST_NODE_EXACT_RESOLVED_TARGET')
 need(before.st_uid==owner_uid and (stat.S_ISLNK(before.st_mode)or link==target and stat.S_ISREG(before.st_mode)),
  'FRESH48_ORIGINAL_HOST_NODE_OWNER_KIND')
 st=target.lstat();need(stat.S_ISREG(st.st_mode)and st.st_uid==target_uid and not st.st_mode&0o022
  and st.st_mode&0o111,'FRESH48_ORIGINAL_HOST_NODE_REGULAR_TARGET_MODE')
 need(hash_file(target)==pin,'FRESH48_ORIGINAL_HOST_NODE_PIN')
 after=link.lstat();end=target.lstat()
 need((before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns)==
  (after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns)and
  (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)==
  (end.st_dev,end.st_ino,end.st_size,end.st_mtime_ns,end.st_ctime_ns),'FRESH48_ORIGINAL_HOST_NODE_STABLE')
 return target


def qualify_local_environment():
 """Owner-local PATH/rlimit only, never shared configuration or installs."""
 p=node_source('/usr/local/bin/node','/opt/node-v20.19.5-linux-x64/bin/node',
  {'size':97607264,'sha256':'8d01d4c50e7a9047d70196f8fc6f1b165069065b44bd9402491544bd70586c7d'},target_uid=1000)
 path=os.environ.get('PATH','/usr/bin:/bin').split(os.pathsep)
 os.environ['PATH']=os.pathsep.join([str(p.parent)]+[x for x in path if x!=str(p.parent)])
 soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
 need(hard>=65536,'FRESH48_EXISTING_HOST_FD_HARD_CAP');resource.setrlimit(resource.RLIMIT_NOFILE,(max(soft,65536),hard))
 return {'shared_environment_written':False,'node':str(p),'fd_limit':max(soft,65536)}


def local_pause48(dispatcher):
 """Keep every original public AUX metadata guard; add only designated4/8."""
 import disk_capacity
 tree=ast.parse(inspect.getsource(disk_capacity.local_pause));s=ast.unparse(tree)
 old="('Agensh-16', 'Agensh-1')"
 need(s.count(old)==1,'FRESH48_ONE_EXACT_AUX_SETTING_GUARD')
 s=s.replace(old,"('Agensh-1', 'Agensh-4', 'Agensh-8', 'Agensh-16')")
 ns=dict(disk_capacity.local_pause.__globals__);exec(compile(s,'<fresh48-original-AUX-scope-setting-only>','exec'),ns)
 return ns['local_pause'](dispatcher)


def verify_backend_inputs(destination,host_directory):
 from fresh48_backend_inputs import verify_one
 return verify_one(destination,host_directory)


def bind_backend_prestage(host,root):
 """Only new manifest-selected backend, once; native launcher does the rest."""
 original=host.backend;attempted=set();root=Path(root)
 def backend(row,layout):
  p=host.setting(row);r=Path(p['root'])
  proofs=[r/'BACKEND_PREPARATION_PASS_NOT_SCIENTIFIC_ACTIVATION.json',
          r/'BACKEND_PREPARATION_PASS_NOT_SCIENTIFIC_ACTIVATION_V2.json']
  if not any(x.is_file()for x in proofs):
   t=row['trajectory_id'];need(t not in attempted and not(r/'run').exists(),'FRESH48_BACKEND_NO_DUPLICATE_OR_PARTIAL_PRESTAGE')
   verify_backend_inputs(r,Path(host.__file__).parent)
   attempted.add(t);directory=root/'config'/('backend-'+digest(t));directory.mkdir(mode=0o700)
   script=Path(host.__file__).with_name('prepare_scientific_backend_infra.py')
   with (directory/'stdout.private').open('xb')as out,(directory/'stderr.private').open('xb')as err:
    os.fchmod(out.fileno(),0o600);os.fchmod(err.fileno(),0o600)
    result=subprocess.run([sys.executable,'-B',str(script),'--workers',str(p['workers']),'--block',str(p['block'])],
     stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=1200,umask=0o022)
   need(result.returncode==0,'FRESH48_BACKEND_PRESTAGE_FAILED_RETAIN_NO_AUTO_RETRY')
  return original(row,layout)
 host.backend=backend


def dispatcher(original,record,*,child_environment):
 from durable_final import FinalOnlyDispatcher
 from durable_cost import dispose,AccountingConflict
 entry=Path(__file__).with_name('run_fresh48_final_child.py')
 need(not original.children and not original.points and not any(original.root.iterdir()),'FRESH48_REPLACE_EMPTY_UNSTARTED_FINAL_OBJECT')
 result=FinalOnlyDispatcher(original.ledger,original.queue,original.capacity,original.server,
  directory=original.root,configuration=original.configuration,python_command=original.command,
  environment={**original.environment,'PYTHONPATH':child_environment['PYTHONPATH']},entry=entry,entry_sha256=hash_file(entry)['sha256'],point_base=original.root.parent/'final-points')
 def failed(self,r):
  # User standing policy: original attempt + at most2 replacement attempts.
  job=dispose(self,r,maximum=3)
  self.held_points.pop(r['job']['point'],None)
  record('FRESH48_FINAL_REPLICATE_PARTIAL_REPLACED',{'point_id':r['job']['point'],
   'replicate_id':r['job']['replicate'],'attempt':r['job'].get('attempt',1),
   'replacement_job_id':job,'requests_replayed':0,'search_budget_delta':0})
  return job
 result.dispose_failed=MethodType(failed,result);local_pause48(result)
 return result


class Owner:
 def __init__(self,configuration,host,branch_config,*,health_path,reader_path):
  from run_native_scientific6 import ScientificSixDriver
  from aggregate_install import Manager
  from fresh48_branch import install as branch_builder
  from fork_final_claim_nonblocking import install_pair
  from aggregate_manager_isolation import install as manager_isolation
  from fresh48_hooks import install as launch_hooks
  from fresh48_reader import install_host
  from disk_capacity import Slots
  from expansion100_quota import install as quota
  from disk_search_policy import install as policy
  from disk_control import Control
  self.policy=check(configuration['manifest']);need(group(configuration['manifest'])=='new-4-8','FRESH48_NEW_EXACT_AUTHORIZED_OWNER')
  qualify_local_environment()
  self.started_ns=time.time_ns();self.health_path=Path(health_path);self.hold=False
  self.operator_hold=False;self.financial_stop=False;self.upstream_stop=False;self.warnings=set()
  driver=ScientificSixDriver(configuration,host);self.driver=driver;self.home=driver.root
  self.identity={'pid':os.getpid(),'start':Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(') ',1)[1].split()[19],
   'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
  install_host(host,reader_path,self.record)
  bind_backend_prestage(host,driver.manifest['root'])
  evidence=driver.admit(None,'initialize-shared');need(evidence is not None,'FRESH48_INITIAL_FRESH_HOST_ADMISSION')
  driver.initialize_shared(evidence)
  from fresh48_projection import install as projection
  projection();branch_builder();manager=Manager(driver,branch_config);self.manager=manager
  # Original wrapper would hold queue mutex while slow verify_input. Restore the
  # exact original claim and enforce shared metadata cap at the candidate seam.
  install_pair(driver.queue,manager.queue,cap=manager.final_slots['global_final_subtask_cap'])
  driver.dispatcher=dispatcher(driver.dispatcher,self.record,child_environment=driver.final['environment']);manager.dispatcher=dispatcher(manager.dispatcher,self.record,child_environment=driver.final['environment'])
  self.ds={'main':driver.dispatcher,'branch':manager.dispatcher};self.peer=manager.peer;self.peer.hold=lambda:self.hold or self.operator_hold or self.financial_stop or self.upstream_stop
  self.slots=Slots(self.ds.values(),cap=3).install()
  quota(self.peer,[d.capacity for d in self.ds.values()],final_slots=self.slots,group='new-4-8')
  policy(self)
  launch_hooks(driver,manager,self._user100_retry_monitor,self.record)
  manager_isolation(manager);driver.late_aggregate_fork_manager=manager
  self.original_admit=driver.admit
  def admit(row,phase):
   if self.hold or self.operator_hold or self.financial_stop or self.upstream_stop:return None
   return self.original_admit(row,phase)
  driver.admit=admit
  self.natural=self.install_natural()
  self.control=Control(self);self.control.start()
  manager.start()
  self.record('FRESH48_OWNER_NATIVE_COMPONENTS_READY_BEFORE_FIRST_LAUNCH',{
   'trajectories':sorted(driver.rows),'same_v2_task':True,'regular_targets':[10_000_000,20_000_000,50_000_000,100_000_000],
   'diagnostic_source':16_000_000,'independent_branch_budget':4_000_000,'physical_root_cap':36,'final_cap':3,
   'worker_cli_loop':'original unmanaged Agensh','models':0})

 def record(self,kind,value):
  l=self.driver.ledger
  with l.tx():l.event('GLOBAL',kind,value)

 def resource_health(self):
  from health_window20 import external_status
  h=external_status(self.health_path)
  available=int(next(x.split()[1]for x in Path('/proc/meminfo').read_text().splitlines()if x.startswith('MemAvailable:')))*1024
  return h,available

 def local_error(self,domain,where,e):
  from durable_cost import AccountingConflict
  if isinstance(e,AccountingConflict)or where=='POLICY_TICK':
   self.financial_stop=True;self.hold=True
  self.record('FRESH48_LOCAL_COMPONENT_ERROR',{'domain':domain,'stage':where,'exception_type':type(e).__name__,
   'messages_locals_omitted':True,'global_fault':isinstance(e,AccountingConflict),'requests_replayed':0})

 def status(self):
  return {'schema':'agensh-v2-fresh48-owner-status-v1','owner':self.identity,'state':self.driver.state,
   'global_hold':self.hold,'operator_hold':self.operator_hold,'financial_stop':self.financial_stop,
   'upstream_threshold_stop':self.upstream_stop,'actual_FINAL_active':self.slots.active(),'final_cap':self.slots.cap,
   'physical_fp8_including_unknown':self.peer.physical(),'pending':list(self.driver.pending),
   'tracks':{t:{'phase':r['phase'],'frontier':self.driver.ledger.frontier(t),
    'controller':getattr(r.get('launch'),'controller',None).state if getattr(r.get('launch'),'controller',None)else None}
      for t,r in list(self.driver.records.items())},
   'domains':{k:{'frontier':d.queue.frontier(),'point_local_holds':dict(d.held_points),
    'audited_points':sum(p['audited']for p in d.points.values())}for k,d in self.ds.items()}}

 def install_natural(self):
  from agensh_v2_natural import NaturalStopManager
  from agensh_v2_neutral_ports import NativeNeutralPorts
  from r16_natural_contract import TEMPLATE,TEMPLATE_SHA
  p={'schema':'ops-r16-natural-stop-neutral-policy-v1','idle_seconds':600,'budget_tokens':100_000_000,
   'message':{'template_utf8':TEMPLATE,'template_sha256':TEMPLATE_SHA},
   'tracks':[{'trajectory':t,'immediate_first_natural_stop':False}for t in self.driver.rows]}
  self.driver._v2_natural_policy=p
  manager=NaturalStopManager(self.driver,p,NativeNeutralPorts(self.driver));manager.start();return manager

 def tick(self):raise AssertionError('policy-installed instance method required')

 def search_lifecycle(self):
  """Lifecycle only; no manual stage/cut/model/tool operation or held-lock RPC."""
  driver=self.driver
  driver.failed=self.hold # Only real global relay/billing/health/operator policy.
  if not self.hold and driver.pending:
   t=driver.pending[0];row=driver.rows[t]
   if driver.admit(row,'new-trajectory')is not None:
    try:driver.launch_one(t)
    except BaseException as e:self.local_error('main','FIRSTSTART_LOCAL',e)
  finished=not driver.pending and len(driver.records)==6 and all(
   r.get('terminal',{}).get('owner_state')=='FINAL_PARKED'for r in driver.records.values())
  if finished:
   expected=72+3*getattr(driver,'_r16_natural_point_count',0)
   if driver.queue.frontier()=={'COMPLETE':expected}and driver.ledger.global_logical_unresolved()==0:
    driver.finished=True;driver.state='SCIENCE_COMPLETE_NATIVE_RETIREMENT_OPS_OWNED'
  driver._publish_status(self.status())
  return driver.finished and self.manager.finished

 def run(self):
  while True:
   try:self.tick()
   except BaseException as e:self.local_error('owner','POLICY_TICK',e)
   if self.search_lifecycle():return self.status()
   time.sleep(.5)
