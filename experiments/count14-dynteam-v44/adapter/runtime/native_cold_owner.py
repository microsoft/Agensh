"""One actual source-owning cold prefix entry over ORIGINAL held core objects.

No activation substitute: task/public tools, modern health/UNKNOWN, complete
writers and real K3 must still qualify before science PREPARED/ACTIVATE. This
entry owns every partial object/child and never discards/replays a failed step.
"""
from dataclasses import dataclass
from pathlib import Path
import os

from common import need,digest
from original_relay_core import OriginalRelayCore
from native_layout import NativeLayout
from native_cold_exports import build as export_native
from native_host_environment import (prepare as prepare_environment, NativeHostFacts,
                                     _executable as preflight_control_executable)
from native_cold_bootstrap import NativeColdBootstrap


@dataclass(frozen=True)
class NativeSourcePins:
    guarded_agent_directory:Path
    compiled_router_directory:Path
    public_router_source:Path
    native_generator:Path
    native_generator_sha256:str
    native_project_directory:Path
    spawn_source:Path
    spawn_source_sha256:str
    spawn_client:Path
    spawn_client_sha256:str
    python_binary:Path
    python_sha256:str


def _native_control_public(core):
    # Existing metadata queues ONLY. No new endpoint, request, physical census,
    # science lock, native UUID/account/peer, or raw exception representation.
    if core is None:
        return None
    result = {}
    for name in ('inbox', 'phase_proof_inbox', 'bridge_inbox', 'spawn_inbox', 'reconnect_inbox'):
        try:
            value = getattr(core, name, None)
            result[name] = None if value is None else value.public()
        except Exception as error:
            result[name] = dict(observer_exception_type=type(error).__name__)
    # Existing frozen latch wrapper metadata only; no live patch or RAM API.
    try:
        clock = getattr(core, 'active_clock', None)
        result['original_latch_observer'] = None if clock is None else clock.public_latch_observer()
    except Exception as error:
        result['original_latch_observer'] = dict(observer_exception_type=type(error).__name__)
    publisher = getattr(core, 'publisher', None)
    result['metadata_publisher_failures'] = [] if publisher is None else [
        dict(row) for row in publisher.last_failures[-128:]]
    control = getattr(core, 'control', None)
    result['control_refusals'] = [] if control is None else [
        dict(row) for row in getattr(control.server, 'last_refusals', ())[-128:]]
    try:
        result['session_ready_resubmission_public'] = (None if control is None else
            control.public_session_ready_resubmissions())
    except Exception as error:
        result['session_ready_resubmission_public'] = dict(observer_exception_type=type(error).__name__)
    return result


class NativeColdOwner:
    @classmethod
    def prepare(cls,*,core_arguments,docker,host_facts,sources,native_uid,original_tool_physical_clear,
                projected_additional_bytes,memory_reader=None,resource_allocation=None,
                system_probe_sources=None,system_probe_OWN_endpoint=None,resource_producer=None):
        need(type(core_arguments) is dict and type(sources) is NativeSourcePins and
             callable(original_tool_physical_clear),'DYNTEAM_COLD_OWNER_EXPLICIT_ORIGINAL_BINDINGS')
        self=cls();self.core=None;self.layout=None;self.bootstrap=None;self.errors=[]
        self.ledger=core_arguments.get('ledger')
        self.state='CREATING_ORIGINAL_HELD_CORE'
        try:
            self.state='PREFLIGHT_FROZEN_HOST_CONTROLS_BEFORE_ORIGINAL_CORE'
            need(type(host_facts) is NativeHostFacts,
                 'DYNTEAM_COLD_OWNER_EXACT_HOST_FACTS_BEFORE_CORE')
            for path,pin in ((host_facts.make_binary,host_facts.make_sha256),
                             (sources.python_binary,sources.python_sha256),
                             (sources.spawn_source,sources.spawn_source_sha256)):
                preflight_control_executable(path,pin)
            self.state='CREATING_ORIGINAL_HELD_CORE'
            self.core=OriginalRelayCore.prepare(**core_arguments)
            need(not self.core.errors and self.core.state=='ORIGINAL_TRANSPORT_HELD_NATIVE_BINDINGS_PENDING',
                 'DYNTEAM_COLD_OWNER_ORIGINAL_CORE_MUST_BE_HELD_AND_VALID')
            self.state='PREPARING_EXACT_NATIVE_LAYOUT'
            self.layout=NativeLayout(self.core,native_uid=native_uid)
            self.state='BINDING_ORIGINAL_CONTROL'
            self.core.bind_native_control(self.core.home/'native-control.sock',child_uid=native_uid,
                native_tool_physical_clear=original_tool_physical_clear,archive_bindings=self.layout.archive_bindings,
                native_socket_uid=native_uid,native_socket_gid=native_uid)
            self.state='BINDING_PRIVATE_NATIVE_DOCKER'
            self.core.bind_scoped_native_docker(docker,image_ids={k:host_facts.image_ids[k] for k in ('agent','router')})
            self.state='EXPORTING_SAME_ORIGINAL_NATIVE_ROUTES'
            export_native(self.core,guarded_agent_directory=sources.guarded_agent_directory,
                compiled_router_directory=sources.compiled_router_directory,public_router_source=sources.public_router_source,
                native_generator=sources.native_generator,native_generator_sha256=sources.native_generator_sha256,
                native_project_directory=sources.native_project_directory,native_uid=native_uid)
            self.state='COMPILING_PRIVATE_HOST_ENVIRONMENT'
            prepare_environment(self.core,facts=host_facts,spawn_source=sources.spawn_source,
                spawn_source_sha256=sources.spawn_source_sha256,spawn_client=sources.spawn_client,
                spawn_client_sha256=sources.spawn_client_sha256,python_binary=sources.python_binary,
                python_sha256=sources.python_sha256)
            self.bootstrap=NativeColdBootstrap(self.core,projected_additional_bytes=projected_additional_bytes,
                                              memory_reader=memory_reader)
            if resource_allocation is not None:
                from native_cohort_resources import NativeCohortResources
                self.state='BINDING_ORIGINAL_COHORT_RESOURCES'
                NativeCohortResources(self.core,resource_allocation,memory_reader=memory_reader).refresh()
            if system_probe_sources is not None:
                from native_system_health import NativeSystemHealth
                self.state='BINDING_INDEPENDENT_ORIGINAL_SYSTEM_HEALTH'
                NativeSystemHealth(self.core,system_probe_sources,key_path=core_arguments['key_path'],
                                   OWN_endpoint=system_probe_OWN_endpoint)
            else:
                need(system_probe_OWN_endpoint is None,'DYNTEAM_NO_UNBOUND_PROBE_ENDPOINT')
            self.state='COLD_PREFIX_PREPARED_MODELS_HELD_NOT_SCIENTIFIC_PREPARED'
            if resource_producer is not None:self.bind_resource_producer(**resource_producer)
            self.zero_model_prefix()
        except Exception as error:
            if self.core is not None and self.layout is None:
                self.layout=getattr(self.core,'native_layout',None) # retain constructor's partial same object
            frames=[];tb=error.__traceback__
            while tb:
                frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name))
                tb=tb.tb_next
            self.errors.append(dict(PUBLIC_code='DYNTEAM_COLD_OWNER_PARTIAL_RETAINED_NO_RETRY',
                exception_type=type(error).__name__,locations=frames,failed_phase=self.state))
            self.state='PARTIAL_RETAINED_MODELS_NOT_ACTIVATED'
        return self

    def bind_resource_producer(self,*,plan_path,plan_sha256,sources):
        self._validate_scientific_prefix()
        from native_resource_producer import NativeResourceProducer
        producer=NativeResourceProducer(self.core,plan_path,plan_sha256,sources,
            memory_reader=self.bootstrap.memory if self.core.qualification_only else None)
        return producer.public()

    def prepare_source(self,t,*,binding_path,binding_sha256):
        """Original same-input bootstrap port; never release science/models.

        Source/task bodies are consumed only by the original trusted runtime,
        never decoded/logged here. Already-ready metadata is returned without
        executing bootstrap again; a failed/partial prefix is retained.
        """
        self._validate_scientific_prefix()
        from native_resource_sampler import read_public
        from native_count14_source import prepare
        from native_system_probe_child import append
        import hashlib
        need(t in self.core.rows and hasattr(self.core,'cohort_resources'),
             'DYNTEAM_SOURCE_PREPARE_REQUIRES_EXACT_ROW_AND_RESOURCE_GUARD')
        previous=getattr(self.core,'source_bootstraps',{}).get(t)
        if previous is not None:
            need(previous['binding_sha256']==binding_sha256 and previous['state']=='SOURCE_ONLY_READY',
                 'DYNTEAM_SOURCE_PARTIAL_RETAINED_NO_AUTOMATIC_REPLAY')
            return dict(previous)
        producer=getattr(self.core,'resource_producer',None)
        if producer is not None:producer.poll()
        self.core.cohort_resources.refresh()
        if not self.core.cohort_resources.system_open():
            if not hasattr(self,'_pending_source_preparations'):self._pending_source_preparations={}
            self._pending_source_preparations[t]=dict(binding_path=binding_path,binding_sha256=binding_sha256)
            return dict(state='WAITING_UNCONSUMED_FRESH_RESOURCES',trajectory=t,models=0)
        need(Path(binding_path).name.endswith('PUBLIC.json'),
             'DYNTEAM_SOURCE_ONLY_FIXED_PUBLIC_METADATA_BINDING_NOT_PRIVATE_CONTEXT')
        binding,raw=read_public(Path(binding_path))
        need(hashlib.sha256(raw).hexdigest()==binding_sha256,'DYNTEAM_SOURCE_PUBLIC_BINDING_SHA')
        if not hasattr(self.core,'source_bootstraps'):self.core.source_bootstraps={}
        record=dict(state='SOURCE_PREPARING',binding_sha256=binding_sha256)
        self.core.source_bootstraps[t]=record
        root=Path(self.core.rows[t]['root']);append(root/'SOURCE_ONLY_BOOTSTRAP_INTENT_PUBLIC.json',
            dict(schema='count14-dynteam-source-bootstrap-intent-v1',trajectory=t,contract_sha256=digest(self.core.contract),
                 binding_sha256=binding_sha256,models=0))
        try:
            receipt=prepare(binding,contract=self.core.contract,row=self.core.rows[t],destination=root/'source-bootstrap',
                            qualification_only=self.core.qualification_only)
            append(root/'SOURCE_ONLY_BOOTSTRAP_READY_PUBLIC.json',receipt)
            record.update(state='SOURCE_ONLY_READY',receipt=receipt)
        except Exception as error:
            frames=[];tb=error.__traceback__
            while tb:
                frames.append(dict(file=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno,function=tb.tb_frame.f_code.co_name));tb=tb.tb_next
            record.update(state='SOURCE_PARTIAL_RETAINED',exception_type=type(error).__name__,locations=frames)
            append(root/'SOURCE_ONLY_BOOTSTRAP_FAILED_PUBLIC.json',dict(schema='count14-dynteam-source-bootstrap-failed-v1',
                exception_type=type(error).__name__,locations=frames,models=0,automatic_retries=0))
            raise
        getattr(self,'_pending_source_preparations',{}).pop(t,None)
        return dict(record)

    def _validate_scientific_prefix(self):
        need(self.state=='COLD_PREFIX_PREPARED_MODELS_HELD_NOT_SCIENTIFIC_PREPARED' and not self.errors,
             'DYNTEAM_SAME_COLD_ENTRY_PREFIX_VALIDATION_ONLY')
        self.bootstrap._held()
        need(self.core.control is not None and self.core.control.started and
             self.layout.core is self.core and self.bootstrap.core is self.core,
             'DYNTEAM_COLD_ENTRY_ALL_COMPONENTS_OWN_SAME_ORIGINAL_CORE')
        for t in self.core.rows:
            layout=self.layout.current(t)
            need(self.core.native_host_environment['trajectories'][t]['data_root']==layout['data_root'],
                 'DYNTEAM_COLD_ENTRY_LAYOUT_ENV_PATHS_MUST_MATCH')
        return self.public()

    def zero_model_prefix(self):
        result=self._validate_scientific_prefix()
        health=getattr(self.core,'system_health',None)
        need(health is None or not health.started,
             'DYNTEAM_ZERO_MODEL_ENTRY_NEVER_INCLUDES_STARTED_SYSTEM_PROBE')
        return result

    def start_bootstrap(self,t):
        self._validate_scientific_prefix()
        return self.bootstrap.start(t)

    def bind_scientific_smoke(self,*,sources):
        self._validate_scientific_prefix()
        from native_baseline_smoke import NativeBaselineSmoke
        return NativeBaselineSmoke(self,sources=sources).public()

    def start_system_health(self):
        self._validate_scientific_prefix()
        need(hasattr(self.core,'system_health'),'DYNTEAM_EXPLICIT_SYSTEM_PROBE_SOURCE_REQUIRED')
        return self.core.system_health.start()

    def poll(self,t=None):
        need(self.bootstrap is not None,'DYNTEAM_PARTIAL_OWNER_HAS_NO_BOOTSTRAP_RETRY')
        if self.core.closed:
            from copy import deepcopy
            return deepcopy(self.core.smoke_terminal_public)
        if t is None:
            pending=getattr(self,'_pending_source_preparations',{})
            if pending:
                waiting_t=next(iter(pending))
                self.prepare_source(waiting_t,**pending[waiting_t])
            count=self.core.poll_native_control_once()
            smoke=getattr(self,'scientific_smoke',None)
            if smoke is not None:return smoke.poll()
            return count
        return self.bootstrap.step(t)

    def activate(self):
        from native_baseline_smoke import NativeBaselineSmoke
        smoke=getattr(self,'scientific_smoke',None)
        need(type(smoke) is NativeBaselineSmoke and smoke.owner is self and smoke.core is self.core,
             'DYNTEAM_ACTUAL_TASK_PUBLIC_TOOLS_MODERN_GATES_WRITERS_K3_REQUIRED_BEFORE_ACTIVATION')
        return smoke.activate()

    def public(self):
        if self.core is not None and self.core.closed:
            from copy import deepcopy
            return deepcopy(self.core.smoke_terminal_public)
        smoke=getattr(self,'scientific_smoke',None)
        smoke_state=None if smoke is None else smoke.state
        return dict(state=self.state,owner_pid=os.getpid(),original_core_exists=self.core is not None,
            original_ledger_retained=self.ledger is not None,
            native_layout_roles=0 if self.layout is None else len(self.layout.archive_bindings),
            control_bound=self.core is not None and self.core.control is not None,
            actual_environment_bound=self.core is not None and hasattr(self.core,'native_host_environment') and
                self.core.native_host_environment['state']=='HOST_ENV_EXPORTED_MODEL_GATES_HELD',
            bootstrap_bound=self.bootstrap is not None,
            scientific_PREPARED=smoke_state=='PREPARED_BASELINE_SMOKE_RACING_HELD',
            scientific_ACTIVATED=smoke_state in ('RUNNING_BASELINE_SMOKE_RACING_HELD','FINAL_PARKED_K3_PENDING',
                                               'SMOKE_SEARCH_AND_K3_COMPLETE'),
            scientific_scope=None if smoke is None else 'BASELINE_SYSTEM_SMOKE_ONLY_RACING_HELD',
            scientific_smoke_public=None if smoke is None else smoke.public(),
            cohort_resources_bound=self.core is not None and hasattr(self.core,'cohort_resources'),
            independent_SYSTEM_health_bound=self.core is not None and hasattr(self.core,'system_health'),
            independent_SYSTEM_health_started=self.core is not None and hasattr(self.core,'system_health') and
                self.core.system_health.started,
            resource_producer_bound=self.core is not None and hasattr(self.core,'resource_producer'),
            resource_producer_public=(self.core.resource_producer.public() if self.core is not None and
                hasattr(self.core,'resource_producer') else None),
            source_only_ready=sum(v['state']=='SOURCE_ONLY_READY' for v in
                getattr(self.core,'source_bootstraps',{}).values()) if self.core is not None else 0,
            native_control_metadata_public=_native_control_public(self.core),
            errors=list(self.errors)+([dict(e) for e in self.core.errors if type(e) is dict and
                e.get('PUBLIC_code')=='DYNTEAM_CORE_PARTIAL_RETAINED_NO_AUTOMATIC_RETRY']
                if self.core is not None else []),provider_key_or_task_or_model_body_exported=False)
