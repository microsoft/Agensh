"""Single-owner real v2.1 K3 subprocess dispatcher; no synthetic provider.

Uses original shared queue, fresh lock/child authority, shared FP8 capacity,
HostServer, original NativeFinalRuntime and original K3 audit. Failed launches
retain original claim/Popen; no automatic retry/replacement/cancellation.
"""
from pathlib import Path
import copy,json,os,secrets,subprocess,threading
from common import need,digest,wire,publish,private_dir,hash_file,strict
from budget import Ledger
from final_queue import FinalQueue,process_identity
from final_binding import FinalBinding
from final_authority import FinalAuthority
from model_capacity import ModelCapacity
from final_host_rpc import HostServer,HostBinding
from native_k3 import audit_three
import native_replicate_attempts as replicate_attempts


class NativeFinalDispatcher:
    def __init__(self,ledger,queue,capacity,server,*,directory,configuration,python_command,environment):
        need(type(ledger)is Ledger and type(queue)is FinalQueue and type(capacity)is ModelCapacity
             and capacity.ledger is ledger and type(server)is HostServer and server.capacity is capacity,
             'FINAL_DISPATCH_ORIGINAL_SHARED_OWNER_PORTS')
        need(callable(configuration) and type(python_command)is tuple and python_command
             and Path(python_command[0]).is_absolute() and Path(python_command[0]).is_file()
             and type(environment)is dict,'FINAL_DISPATCH_TRUSTED_CONFIGURATION')
        self.ledger,self.queue,self.capacity,self.server=ledger,queue,capacity,server
        self.root=private_dir(directory,create=True);need(not any(self.root.iterdir()),'FINAL_DISPATCH_NEW_ROOT')
        self.configuration=configuration;self.command=python_command;self.environment=dict(environment)
        self.children={};self.points={};self.faulted=False;self.lock=threading.RLock()
        self.global_faulted=False;self.local_faults={};self.first_failure=None
        self.failure_public=None;self.failure_publication_attempted=False
        need(not hasattr(queue,'_native_final_faulted_trajectories'),'FINAL_ONE_DISPATCHER_FAULT_DOMAIN')
        queue._native_final_faulted_trajectories=set()
        self.entry=Path(__file__).with_name('run_native_final_child.py');self.entry_pin=hash_file(self.entry)
    def _fault(self,trajectory,kind):
        self.faulted=True;self.local_faults.setdefault(trajectory,kind)
        with self.queue.mutex:self.queue._native_final_faulted_trajectories.add(trajectory)
        self.ledger.latch_fault(trajectory,kind)
        with self.ledger.tx():self.ledger.event(trajectory,kind,{'retry':False,'original_handles_retained':True})
    def _retain_first_failure(self,error,phase,trajectory):
        if self.first_failure is not None:return
        frames=[];tb=error.__traceback__
        while tb:
            frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,
                               function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
        self.first_failure=dict(schema='count14-native-first-final-failure-public-v1',
            trajectory=trajectory,phase=phase,exception_type=type(error).__name__,locations=frames,
            messages_args_locals_or_scientific_body_exported=False,requests_replayed=0)
    def publish_first_failure_public(self):
        if self.first_failure is None or self.failure_publication_attempted:return
        self.failure_publication_attempted=True
        try:
            need(not self.ledger.mutex._is_owned()and not self.queue.mutex._is_owned()and
                 not self.lock._is_owned(),'FINAL_FIRST_FAILURE_PUBLIC_OUTSIDE_LOCKS')
            path=self.root.parent/'FINAL_FIRST_FAILURE_PUBLIC.json'
            publish(path,wire(self.first_failure),mode=0o400)
            self.failure_public=dict(path=str(path),sha256=hash_file(path)['sha256'])
        except Exception as error:
            self.failure_public=dict(PUBLIC_code='FINAL_FIRST_FAILURE_PUBLICATION_FAILED_RETAIN',
                                     exception_type=type(error).__name__)
    def dispatch_one(self):
        with self.lock:
            need(not self.global_faulted,'FINAL_DISPATCH_FAULT_NO_RETRY')
            job=self.queue.claim()
            if job is None:return None
            record={'job':copy.deepcopy(job),'child':None,'config':None,'terminal':None}
            self.children[job['id']]=record
            try:
                c=copy.deepcopy(self.configuration(copy.deepcopy(job)))
                need(type(c)is dict and c.get('trajectory')==job['trajectory']
                     and c.get('k')==job['replicate'] and c.get('input_root')==job['input_root']
                     and c.get('input_policy_sha256')==job['input_policy'],
                     'FINAL_DISPATCH_SAME_CLAIM_INPUTS')
                need(digest(c['manifest'])==self.queue.manifest,'FINAL_DISPATCH_SAME_MANIFEST')
                # Build identity only; an attempted authority check before the
                # original child exists is refused, never cached as approval.
                def not_yet_live(*_):need(False,'FINAL_DISPATCH_CHILD_NOT_YET_ATTACHED')
                binding=FinalBinding(c['manifest'],c['model_policy'],digest(c['model_policy']),
                    trajectory=job['trajectory'],input_root=job['input_root'],input_policy_sha256=job['input_policy'],
                    replicate_index=job['replicate'],authorize=not_yet_live,replicate_attempt=job.get('attempt',1),point_id=job['point'])
                scope=digest(binding.identity);cap=secrets.token_hex(32)
                c,point_aux=replicate_attempts.prepare(c,job)
                c.update(schema='agensh-native-final-child-v1',host_socket=str(self.server.path),
                         scope=scope,capability=cap)
                from run_native_final_child import FIELDS
                need(set(c)==FIELDS or (job.get('attempt',1)>1 and set(c)==FIELDS|{'replicate_attempt','point_id'}),'FINAL_DISPATCH_EXACT_CHILD_FIELDS')
                aux=Path(c['aux_root']);private_dir(aux)
                point=self.points.setdefault(job['point'],{'aux':point_aux,'jobs':[],'audited':False,'trajectory':job['trajectory']})
                need(point['aux']==point_aux,'FINAL_DISPATCH_K3_SAME_POINT_AUX')
                config=self.root/(job['id']+'.json');publish(config,wire(c));record['config']=c;record['path']=config
                need(hash_file(self.entry)==self.entry_pin,'FINAL_DISPATCH_ENTRY_CHANGED')
                with config.with_suffix('.stdout').open('xb') as out,config.with_suffix('.stderr').open('xb') as err:
                    child=subprocess.Popen([*self.command,str(self.entry),str(config),hash_file(config)['sha256']],
                        cwd=self.entry.parent,env=self.environment,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                        close_fds=True)
                record['child']=child # retain BEFORE fallible attachment/metadata
                self.queue.attach(job['id'],job['claim'],child)
                authority=FinalAuthority(self.ledger,self.queue,job['id'],job['claim'],child)
                need(self.capacity.register_scope(binding.identity,authorize=authority)==scope,'FINAL_DISPATCH_HOST_SCOPE')
                identity=process_identity(child.pid)
                self.server.register(HostBinding(scope,cap,child.pid,identity['start'],identity['boot_id'],
                    os.geteuid(),os.stat('/proc/'+str(child.pid)+'/ns/pid').st_ino))
                record['scope']=scope;point['jobs'].append(job['id'])
                publish(config.with_suffix('.ready'),wire({'config_sha256':hash_file(config)['sha256'],'scope':scope}))
                return job['id']
            except BaseException as error:
                self._retain_first_failure(error,'DISPATCH_CONFIGURATION_OR_LAUNCH',job['trajectory'])
                record['framework_failed']=True
                self._fault(job['trajectory'],'NATIVE_FINAL_DISPATCH_INCOMPLETE_NO_RETRY')
                if not isinstance(error,Exception):raise
                return None  # exact claim/handles retained; other trajectories still poll
    def poll(self):
        with self.lock:
            need(not self.global_faulted,'FINAL_DISPATCH_FAULT_RETAIN_HANDLES')
            try:return self._poll()
            except BaseException as error:
                # Record/point-specific faults were isolated inside _poll. An
                # unassignable outer invariant failure must retain the whole graph.
                self._retain_first_failure(error,'UNASSIGNED_FINAL_POLL',None)
                self.faulted=True;self.global_faulted=True
                raise
    def _poll(self):
        with self.lock:
            need(not self.global_faulted,'FINAL_DISPATCH_FAULT_RETAIN_HANDLES')
            for key,record in self.children.items():
                if record.get('framework_failed'):continue
                try:
                    child=record['child'];job=record['job']
                    if child is None:continue
                    if record['terminal'] is None:
                        terminal=self.queue.reap(key,job['claim'],child)
                        if terminal is None:continue
                        record['terminal']=terminal
                    terminal=record['terminal']
                    if job['trajectory']in self.local_faults:continue
                    if terminal['exit_code']!=0 or terminal['signal']is not None:
                        if not record.get('partial'):replicate_attempts.dispose(self,record)
                        continue
                    # Child cannot be authorized for new work after physical exit;
                    # audit recorded permit states directly, never fabricate a live
                    # HostClient authority to obtain a historical frontier.
                    with self.ledger.mutex:
                        n=self.ledger.db.execute("SELECT COUNT(*) FROM aux_permits WHERE scope=? AND state IN ('RESERVED','SENT','UNKNOWN')",(record['scope'],)).fetchone()[0]
                    need(n==0,'FINAL_DISPATCH_AUX_PHYSICAL_UNRESOLVED')
                except Exception as error:
                    self._retain_first_failure(error,'CHILD_REAP_OR_DISPOSITION',record['job']['trajectory'])
                    record['framework_failed']=True
                    self._fault(record['job']['trajectory'],'NATIVE_FINAL_AUDIT_FAILED_NO_RETRY')
            for point in self.points.values():
                if point['audited']:continue
                if point['trajectory']in self.local_faults:continue
                try:
                    rows=replicate_attempts.selected(self,point)
                    if rows is None:continue
                    rows.sort(key=lambda r:r['job']['replicate']);c=rows[0]['config'];j=rows[0]['job'];aux=point['aux']
                    from v21_inputs import verify_input
                    from r16_natural_contract import natural,label as point_label
                    ip=verify_input(j['input_root'],expected_policy_sha=j['input_policy'],trajectory=j['trajectory'],setting=j['setting'])
                    nm=natural(ip);label=point_label(j['target'],nm);setting=j['setting']
                    runs=replicate_attempts.paths(rows,label,setting)
                    audit=audit_three(aux,runs,trajectory=j['trajectory'],setting=setting,target_tokens=j['target'],
                        source_sha256=c['manifest']['protocol']['source_bundle'],
                        protocol_sha256=c['manifest']['protocol']['final_v21'],input_policy_sha256=j['input_policy'],natural_stop=nm)
                    publish(aux/'K3_AUDIT.json',wire(audit))
                    for r,run in zip(rows,runs):
                        result=hash_file(run['aggregate'])['sha256']
                        self.queue.complete(r['job']['id'],r['job']['claim'],result_sha256=result,
                            verified_native_audit={'job_id':r['job']['id'],'result_sha256':result,'complete':True,
                                'unresolved_physical_custody':0,'original_k3_audit_sha256':digest(audit)})
                    point['audited']=True
                except Exception as error:
                    self._retain_first_failure(error,'POINT_K3_AUDIT',point['trajectory'])
                    self._fault(point['trajectory'],'NATIVE_FINAL_AUDIT_FAILED_NO_RETRY')
            return self.status()
    def status(self):
        return {'faulted':self.faulted,'global_faulted':self.global_faulted,
                'local_faults':dict(self.local_faults),'first_failure_public':self.failure_public,
                'queue':self.queue.frontier(),
                'children_retained':len(self.children),'audited_points':sum(p['audited'] for p in self.points.values())}
