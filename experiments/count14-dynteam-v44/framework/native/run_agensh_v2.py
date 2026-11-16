#!/usr/bin/env python3
"""NEW experiment only. Prompt-v2 + qualified R16 policies, no old recovery.

Original science/relay/ledger/FINAL/collector modules remain byte-identical.
The host clock-readiness port binds the existing clock algorithms before the
original CLOCK_READY files, gate release and exact-once original task post.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from pathlib import Path
from types import MethodType
import hashlib,inspect,os,resource,shutil,stat,sys,time
from common import need,digest,wire,publish,hash_file,strict,regular_fd
from run_native_scientific6 import ScientificSixDriver,read_configuration,load_host,compile_configuration
from native_budget_park import NativeBudgetParkProjection
from native_writer_fence import NativeWriterFence
from r16_cohort_clock_publisher_v4 import sample_cohort_atomic
from r16_checkpoint_clock_rearm import request_release_with_checkpoint_rearm,ORIGINAL_RELEASE_SHA256
from r16_owner_control import install_owner_control
from r16_natural_contract import TEMPLATE,TEMPLATE_SHA,POLICY_SHA
from agensh_v2_natural import NaturalStopManager
from agensh_v2_neutral_ports import NativeNeutralPorts

HERE=Path(__file__).resolve().parent
READER_SHA='ee22d21d1285b251aa872e0b3f2a25d5d959b3a910ff9e28db4b4a65b99e2b6f'
PAIRED={1:4287909351,2:1636023914,3:2619738241}

def set_nofile():
 soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
 need(hard==resource.RLIM_INFINITY or hard>=65536,'V2_NOFILE_HARD_LIMIT_65536')
 resource.setrlimit(resource.RLIMIT_NOFILE,(max(soft,65536),hard))
 return resource.getrlimit(resource.RLIMIT_NOFILE)

def install_reader(host):
 """New router code leaf only; original compiled-source checks run unchanged."""
 original=host._router_source
 reader=HERE/'lease120-reader/budget_pause_clock.js'
 need(hash_file(reader)['sha256']==READER_SHA,'V2_QUALIFIED_READER120_PIN')
 def build(record):
  source=Path(original(record));dest=source.with_name(source.name+'-v2-lease120')
  need(not dest.exists()and not dest.is_symlink(),'V2_ROUTER_CODE_NEW_LEAF')
  files={str(p.relative_to(source)):hash_file(p)['sha256']for p in source.rglob('*')if p.is_file()}
  need('budget_pause_clock.js'in files and all(not p.is_symlink()for p in source.rglob('*')),'V2_ROUTER_CODE_REGULAR_CLOSURE')
  shutil.copytree(source,dest)
  for p in [dest,*[p for p in dest.rglob('*')if p.is_dir()]]:p.chmod(0o755)
  target=dest/'budget_pause_clock.js';target.unlink()
  fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
  try:
   data=reader.read_bytes();need(hashlib.sha256(data).hexdigest()==READER_SHA,'V2_READER_CHANGED')
   with os.fdopen(fd,'wb',closefd=False)as f:f.write(data);f.flush();os.fchmod(fd,0o444);os.fsync(fd)
  finally:os.close(fd)
  after={str(p.relative_to(dest)):hash_file(p)['sha256']for p in dest.rglob('*')if p.is_file()}
  expected=dict(files);expected['budget_pause_clock.js']=READER_SHA
  need(after==expected,'V2_ROUTER_ONLY_READER_DELTA')
  for p in dest.rglob('*'):
   if p.is_file():p.chmod(0o444)
  for p in sorted([dest,*[p for p in dest.rglob('*')if p.is_dir()]],reverse=True):p.chmod(0o555)
  return dest
 host._router_source=build
 return original

def install_rearm():
 current=NativeWriterFence.request_release
 need(current is request_release_with_checkpoint_rearm or
      hashlib.sha256(inspect.getsource(current).encode()).hexdigest()==ORIGINAL_RELEASE_SHA256,
      'V2_ORIGINAL_RELEASE_METHOD_PIN')
 NativeWriterFence.request_release=request_release_with_checkpoint_rearm

def bind_clock(launch):
 c=launch.controller;p=c.projection
 need(type(p)is NativeBudgetParkProjection and p.ledger is c.ledger and p.t==c.t
      and p.gate is launch.gate and set(p.roles)==set(c.team.roles),'V2_EXACT_NEW_TEAM_CLOCK')
 with p.lock:
  need(not hasattr(c.team,'_r16_budget_pause_projection'),'V2_BIND_CLOCK_ONCE')
  p.sample=MethodType(sample_cohort_atomic,p)
  c.team._r16_budget_pause_projection=p
  p.sample()
 return p

def natural_policy(rows):
 return {'schema':'ops-r16-natural-stop-neutral-policy-v1','idle_seconds':600,'budget_tokens':20000000,
         'message':{'template_utf8':TEMPLATE,'template_sha256':TEMPLATE_SHA},
         'tracks':[{'trajectory':t,'immediate_first_natural_stop':False}for t in sorted(rows)]}

def canary_released(path,first):
 path=Path(path)
 need(path.is_absolute()and path.resolve()==path and not path.is_symlink(),'V2_CANARY_CANONICAL_APPROVAL')
 if not path.exists():return False
 with regular_fd(path)as fd:
  s=os.fstat(fd);need(s.st_uid in(0,os.geteuid())and stat.S_IMODE(s.st_mode)==0o600
      and s.st_nlink==1 and s.st_size<=4096,'V2_CANARY_PRIVATE_APPROVAL')
  raw=os.read(fd,4097);end=os.fstat(fd)
  need((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==
       (end.st_dev,end.st_ino,end.st_size,end.st_mtime_ns,end.st_ctime_ns),'V2_CANARY_APPROVAL_CHANGED')
 v=strict(raw)
 need(set(v)=={'schema','trajectory','upstream_200','usage_nonempty','continuous_settlement','candidate_files','search_tokens','evidence_sha256'}
      and v['schema']=='agensh-v2-canary-release-v1'and v['trajectory']==first
      and all(v[k]is True for k in('upstream_200','usage_nonempty','continuous_settlement'))
      and type(v['candidate_files'])is int and v['candidate_files']>0
      and type(v['search_tokens'])is int and 0<v['search_tokens']<=3000000,'V2_CANARY_EXACT_RELEASE_EVIDENCE')
 from common import sha
 sha(v['evidence_sha256']);return True

class V2Driver(ScientificSixDriver):
 def __init__(self,configuration,host):
  set_nofile();super().__init__(configuration,host)
  need(not Path(self.manifest['root']).is_relative_to(Path((_C14_SCRATCH + '/ag27s16'))),'V2_NO_R16_ROOT')
  for row in self.rows.values():
   need(row['seed']==PAIRED[row['block']],'V2_PAIRED_R16_SEEDS')
  first=self.rows[self.pending[0]]
  need(first['setting']=='Agensh-16'and first['block']==1,'V2_TEAM16_B1_FIRST')
  self.first=first['trajectory_id'];self.canary_file=self.root/'CANARY_RELEASE.json'
  install_reader(host);install_rearm();original_ready=host.ready
  def ready(launch,workers,bindings):
   p=bind_clock(launch);result=original_ready(launch,workers,bindings)
   need(result is True,'V2_ORIGINAL_READY_REQUIRED')
   with self.ledger.tx():self.ledger.event(launch.t,'AGENSH_V2_COLD_CLOCK_BOUND',{
      'roles':len(p.roles),'reader_sha256':READER_SHA,'local_reader_lease_ns':120000000000,
      'wire_lease_ns':10000000000,'cohort_publisher':True,'checkpoint_rearm':True,
      'new_session_firststart':True,'session_recovery_called':False})
   return result
  host.ready=ready
  original_admit=self.admit
  def admit(row,phase):
   if phase=='new-trajectory'and row['trajectory_id']!=self.first and not canary_released(self.canary_file,self.first):return None
   return original_admit(row,phase)
  self.admit=admit
 def initialize_shared(self,evidence):
  super().initialize_shared(evidence)
  self._v2_natural_policy=natural_policy(self.rows)
  publish(self.root/'NATURAL_POLICY_BINDING.json',wire({'policy_contract_sha256':POLICY_SHA,
      'execution_binding':self._v2_natural_policy,'execution_binding_sha256':digest(self._v2_natural_policy)}))
  self._v2_natural=NaturalStopManager(self,self._v2_natural_policy,NativeNeutralPorts(self))
  self._v2_natural.start();install_owner_control(self)
 def status(self):
  result=super().status()
  if hasattr(self,'_v2_natural'):result['natural_stop']=self._v2_natural.status()
  result['agensh_version']='v2';return result
 def run(self):
  result=super().run()
  self._v2_natural.stop.set();self._v2_natural.thread.join(20)
  self._r16_local_control.close()
  return result

def main():
 if len(sys.argv)==5 and sys.argv[1]=='--compile-config':
  c=compile_configuration(read_configuration(sys.argv[2],sys.argv[3]))
  from manifest import compile_manifest
  rows=compile_manifest(c['manifest'])['trajectories']
  c['launch_order']=[r['trajectory_id']for r in sorted(rows,key=lambda r:(r['block'],0 if r['setting']=='Agensh-16'else 1))]
  out=Path(sys.argv[4]);need(not out.exists()and not out.is_symlink(),'V2_COMPILED_NEW_FILE')
  publish(out,wire(c));print(wire({'configuration':str(out),'sha256':hash_file(out)['sha256'],'model_requests':0}).decode());return 0
 need(len(sys.argv)==3,'V2_CONFIG_AND_SHA_REQUIRED')
 c=read_configuration(sys.argv[1],sys.argv[2]);host=load_host(c['host_module'],c['host_module_sha256']);driver=V2Driver(c,host)
 try:driver.run()
 except BaseException:
  publish(driver.root/'DRIVER_RETAINED_FAILURE.json',wire({'schema':'agensh-v2-retained-failure-v1','state':driver.state,'retry':False}))
  while True:time.sleep(60)
 return 0
if __name__=='__main__':sys.exit(main())
