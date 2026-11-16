"""One actual baseline SYSTEM smoke graph on the already-held original owner.

This is deliberately NOT a formal six-trajectory launcher. The paired RACING
account stays startup-held until its own full scientific graph is qualified.
No alternate model dispatcher, synthetic accounting, request/checkpoint retry
or old-root reuse is introduced. Prepare advances one retained normal action
per owner tick; activation is an explicit separate same-object operation.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import copy

from common import need,digest
from native_peer_registry import process_birth
from smoke_bootstrap_task_ports import NewRootSourceTaskPorts
from smoke_bootstrap_task_launch import NativeSameCoreSmokeLaunch
from smoke_bootstrap_task_tester import NativeTesterInitialRelease
from smoke_checkpoint_final_controller import create_smoke_final_controller
from native_dynamic_checkpoint import DynamicCheckpointPorts
from smoke_checkpoint_final_retirement import create_smoke_retirement


@dataclass(frozen=True)
class BaselineSmokeSources:
    original_task_host_source:Path
    native_pbench_source:Path
    native_tester_source:Path
    final_configuration:Path
    final_configuration_sha256:str


class NativeBaselineSmoke:
    def __init__(self,owner,*,sources):
        from native_cold_owner import NativeColdOwner
        need(type(owner) is NativeColdOwner and type(sources) is BaselineSmokeSources and
             not hasattr(owner,'scientific_smoke') and owner.core is not None and not owner.errors,
             'DYNTEAM_BASELINE_SMOKE_ONLY_SAME_ORIGINAL_VALID_COLD_OWNER')
        core=owner.core
        need(core.contract['mode']=='smoke' and not core.qualification_only and
             hasattr(core,'system_health') and hasattr(core,'resource_producer') and
             hasattr(core,'native_kernel_tool_custody'),
             'DYNTEAM_BASELINE_SMOKE_REAL_SYSTEM_RESOURCE_AND_KERNEL_PORTS_REQUIRED')
        baseline=[t for t,row in core.rows.items() if row['arm']=='DYNTEAM']
        need(len(baseline)==1 and set(core.gate.startup_held)==set(core.rows),
             'DYNTEAM_BASELINE_SMALL_PAIRED_CONTRACT_ALL_HELD')
        self.owner,self.core,self.sources=owner,core,sources
        self.t=baseline[0];self.state='BOUND_AWAIT_ORIGINAL_SOURCE';self.failure=None
        self.birth=process_birth(__import__('os').getpid())
        self.final=self.checkpoint=self.launch=self.tester=self.source_ports=None
        self.retirement=None
        owner.scientific_smoke=self

    def _partial(self,error,phase):
        locations=[];tb=error.__traceback__
        while tb:
            locations.append({'file':tb.tb_frame.f_code.co_filename,'line':tb.tb_lineno,
                              'function':tb.tb_frame.f_code.co_name});tb=tb.tb_next
        self.failure={'PUBLIC_code':'DYNTEAM_REAL_SMOKE_PARTIAL_RETAINED_NO_RETRY',
                      'phase':phase,'exception_type':type(error).__name__,'locations':locations}
        self.state='PARTIAL_RETAINED_NO_RETRY'
        # Stop NEW admissions via the original append-only fault mechanism;
        # do not cancel/replay/reclassify accepted models or erase any prefix.
        self.core.ledger.latch_fault(self.t,'DYNTEAM_SMOKE_FRAMEWORK_PARTIAL_RETAINED')

    def prepare_tick(self):
        try:
            core=self.core;t=self.t
            if self.state=='BOUND_AWAIT_ORIGINAL_SOURCE':
                source=getattr(core,'source_bootstraps',{}).get(t)
                if source is None or source['state']!='SOURCE_ONLY_READY':return self.public()
                self.owner.bootstrap.start(t);self.state='WAITING_ORIGINAL_INFRA';return self.public()
            if self.state in ('WAITING_ORIGINAL_INFRA','WAITING_EXACT_HOST_PUBLISH_READY'):
                b=self.owner.bootstrap.step(t)
                need(b['failure_type'] is None,'DYNTEAM_SMOKE_ORIGINAL_INFRA_PARTIAL')
                if b['phase']!='INFRA_READY_AWAIT_SOURCE_PUBLICATION':return self.public()
                if self.source_ports is None:
                    self.source_ports=NewRootSourceTaskPorts(core,
                        original_task_host_source=self.sources.original_task_host_source)
                result=self.source_ports.prepare(t)
                if result['state']=='WAITING_EXACT_HOST_PUBLISH_READY':
                    self.state=result['state'];return self.public()
                need(result['state']=='SOURCE_TASK_CHANNEL_READY','DYNTEAM_SOURCE_PORTS_TRUE_READY')
                self.state='SOURCE_TASK_CHANNEL_READY';return self.public()
            if self.state=='SOURCE_TASK_CHANNEL_READY':
                self.final=create_smoke_final_controller(core,self.sources.final_configuration,
                                                        self.sources.final_configuration_sha256)
                self.final.preflight()
                core.cohort_resources.bind_aux_capacity(self.final.capacity)
                self.state='ORIGINAL_FINAL_BOUND_BEFORE_SCIENTIFIC_WAITERS';return self.public()
            if self.state=='ORIGINAL_FINAL_BOUND_BEFORE_SCIENTIFIC_WAITERS':
                reference=core.contract['v2_baseline_reference_protocol']
                pins={'manifest':digest(core.contract),'protocol':self.final.scope.protocol_sha256(t),
                      'source':reference['source_bundle'],'task_description':reference['task_description']}
                self.checkpoint=DynamicCheckpointPorts(core,t,scope=self.final.scope,
                    source_ports=self.source_ports,pins=pins)
                self.state='ORIGINAL_RELAY_CHECKPOINT_BOUND';return self.public()
            if self.state=='ORIGINAL_RELAY_CHECKPOINT_BOUND':
                if self.tester is None:
                    self.tester=NativeTesterInitialRelease(core,t,self.source_ports,
                        pbench_tester_source=self.sources.native_tester_source)
                if self.tester.prepare() is None:return self.public()
                self.state='ORIGINAL_TESTER_INPUT_PUBLISHED';return self.public()
            if self.state=='ORIGINAL_TESTER_INPUT_PUBLISHED':
                self.owner.bootstrap.start_initial(t);self.state='WAITING_ORIGINAL_INITIAL_ROLES';return self.public()
            if self.state=='WAITING_ORIGINAL_INITIAL_ROLES':
                b=self.owner.bootstrap.step(t)
                need(b['failure_type'] is None,'DYNTEAM_SMOKE_ORIGINAL_INITIAL_PARTIAL')
                discovery=b.get('discovery')
                if b['phase']!='INITIAL_UP_COMMANDS_RETURNED_MODEL_HELD' or discovery is None or discovery['pending_components']:
                    return self.public()
                self.launch=NativeSameCoreSmokeLaunch(core,t,self.source_ports,
                    pbench_source=self.sources.native_pbench_source)
                self.launch.start();self.checkpoint.preflight()
                self.state='PREPARED_BASELINE_SMOKE_RACING_HELD';return self.public()
            return self.public()
        except Exception as error:
            phase=self.state;self._partial(error,phase);raise

    def activate(self):
        need(self.state=='PREPARED_BASELINE_SMOKE_RACING_HELD' and
             process_birth(__import__('os').getpid())==self.birth,
             'DYNTEAM_ACTIVATE_ONLY_TRUE_PREPARED_SAME_BASELINE_SMOKE_OWNER')
        try:
            self.launch.validate_release_prefix();self.checkpoint.preflight()
            resources=self.core.cohort_resources;resources.maybe_refresh()
            need(resources.experiment_open(),'DYNTEAM_SMOKE_ACTIVATION_FRESH_HEALTH_AND_ALL_OWN_CAPACITY')
            evidence={'current_owner_authorized':True,
                'gateway_health_sha256':resources.state['raw_public_receipt_sha256'],
                'allocation_sha256':digest(asdict(resources.allocation))}
            self.final.release(owner_evidence=evidence)
            self.core.gate.release_startup(self.t)
            self.core.scientific_activation_qualified=True
            self.core.state='SAME_ORIGINAL_BASELINE_SYSTEM_SMOKE_RUNNING_RACING_HELD'
            self.state='ACTIVATED_ORIGINAL_TASK_PENDING'
            self.source_ports.task(self.t,self.launch)
            self.state='RUNNING_BASELINE_SMOKE_RACING_HELD'
            return self.public()
        except Exception as error:
            phase=self.state;self._partial(error,phase);raise

    def poll(self):
        try:return self._poll()
        except Exception as error:
            phase=self.state;self._partial(error,phase);raise

    def _poll(self):
        if self.core.closed:return self.public()
        if self.retirement is not None:
            value=self.retirement.step()
            self.state=value['state']
            return self.public()
        if self.state not in ('RUNNING_BASELINE_SMOKE_RACING_HELD','FINAL_PARKED_K3_PENDING',
                              'SMOKE_SEARCH_AND_K3_COMPLETE','PARTIAL_RETAINED_NO_RETRY'):
            return self.prepare_tick()
        if self.final is not None and self.final.state in ('PREPARED_ORIGINAL_FINAL_MODELS_PAUSED','RELEASED'):
            if self.state=='PARTIAL_RETAINED_NO_RETRY':
                self.final.dispatcher.poll() # retain/reap paid jobs, no new claim
            else:self.final.poll() # original FINAL progresses independently of SEARCH
        if self.state in ('RUNNING_BASELINE_SMOKE_RACING_HELD','FINAL_PARKED_K3_PENDING'):
            self.checkpoint.step()
            if self.checkpoint.state=='FINAL_PARKED':self.state='FINAL_PARKED_K3_PENDING'
            # Full K3 acceptance uses original audit/queue terminal records,
            # never merely a child exit, OS activity or zero inflight count.
            if self.state=='FINAL_PARKED_K3_PENDING':
                frontier=self.core.queue.frontier()
                if frontier and set(frontier)=={'COMPLETE'} and frontier['COMPLETE']==6:
                    self.state='SMOKE_SEARCH_AND_K3_COMPLETE'
                    self.retirement=create_smoke_retirement(self.core,checkpoint=self.checkpoint,
                        final=self.final,launch=self.launch)
        return self.public()

    def public(self):
        if self.core.closed:
            return copy.deepcopy(self.core.smoke_terminal_public)
        with self.core.ledger.mutex:
            f=self.core.ledger.frontier(self.t)
            counters={k:f[k] for k in ('generation','actual','reserved','unresolved','target','state')}
        return {'schema':'count14-actual-baseline-system-smoke-owner-v1','state':self.state,
            'trajectory':self.t,'counter':counters,'RACING_startup_held':all(
                t in self.core.gate.startup_held for t,row in self.core.rows.items() if row['arm']=='DYNTEAM_RACING'),
            'final':None if self.final is None else self.final.public(),
            'checkpoint':None if self.checkpoint is None else self.checkpoint.public(),
            'retirement':None if self.retirement is None else self.retirement.public(),
            'failure':copy.deepcopy(self.failure),'formal_six_trajectory_activation':False}
