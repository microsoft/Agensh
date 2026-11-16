"""Fresh-process independent domain for the complete original native FINAL.

No scientific engine/ledger/transport/evaluator function is rewritten. Modules
whose historical import names begin pilot_ are explicit infrastructure shims,
marked AUX_FINALIZATION and carrying actual Agensh identity, never a forged pilot
manifest. Source/prompt/96-turn/262144/timeout/fallback/metric semantics remain.
Production launcher and dependency admission still must supply actual pins/ports.
"""
from pathlib import Path
import ast,contextlib,copy,importlib,json,os,sys,types
from common import need,digest,hash_file,private_dir,publish,wire,Refused,strict
from final_binding import FinalBinding
from final_host_rpc import HostClient,ControlFailure
from native_materialization import NativeMaterializer
from native_space import NativeSpace
from native_model_port import NativeModelPort
from native_images import NativeImages
from native_evaluator_custody import EvaluatorCustody
from native_final_profile import verify_profile

class NativeFinalRuntime:
    def __init__(self,*,manifest,model_policy,input_root,input_policy_sha256,trajectory,replicate_index,aux_root,native_directory,profile,services,client,images,space_home,space_free=None,replicate_attempt=1,point_id=None):
        self.manifest=copy.deepcopy(manifest);self.profile=copy.deepcopy(profile);self.code=Path(native_directory);self.root=private_dir(aux_root,create=True);self.client=client;self.services=copy.deepcopy(services);self.images=images
        need(isinstance(client,HostClient)and isinstance(images,NativeImages),'NATIVE_CONCRETE_HOST_AND_IMAGE_PORTS_REQUIRED')
        experiment=Path(manifest['root']);need(self.root.is_relative_to(experiment)and self.code.is_relative_to(experiment)and Path(input_root).is_relative_to(experiment),'NATIVE_NEW_EXPERIMENT_ROOTS')
        need(not(self.root.is_relative_to(Path(input_root))or Path(input_root).is_relative_to(self.root)),'NATIVE_AUX_INDEPENDENT_FROM_FROZEN_INPUT')
        self.binding=FinalBinding(manifest,model_policy,digest(model_policy),trajectory=trajectory,input_root=input_root,input_policy_sha256=input_policy_sha256,replicate_index=replicate_index,authorize=client.authorize,replicate_attempt=replicate_attempt,point_id=point_id)
        need(client.scope==digest(self.binding.identity),'NATIVE_HOST_SCOPE_BINDING')
        self.materializer=NativeMaterializer(input_root,self.root,policy_sha=input_policy_sha256,trajectory=trajectory,setting=self.binding.row['setting'])
        self.space=NativeSpace(self.materializer,space_home,manifest_sha256=digest(manifest),authorize=self.authorize,free=space_free)
        self.port=NativeModelPort(client,binding=self.binding,native_directory=self.code);self.evaluator_custody=None;self.installed=False
    def authorize(self):
        try:self.binding.authorize()
        except Refused as e:raise ControlFailure(e.code)from None
    def preflight(self):
        self.authorize();s=self.services
        need(set(s)=={'schema','purpose','framework_root','docker_host','docker_config','dependency_freeze_sha256'}and s['schema']=='count14-agensh-final-services-v1'and s['purpose']=='AUX_FINALIZATION'and s['docker_host']=='unix:///var/run/docker.sock','NATIVE_INDEPENDENT_SERVICE_BINDING')
        experiment=Path(self.manifest['root'])
        for key in ('framework_root','docker_config'):
            p=Path(s[key]);need(p.is_absolute()and p.resolve()==p and p.is_relative_to(experiment)and p.is_dir(),'NATIVE_SERVICE_NEW_ROOT')
        verify_profile(self.profile,self.manifest['protocol']['final_v21'],self.code,source_bundle_sha256=self.manifest['protocol']['source_bundle'],model_policy_sha256=self.binding.profile.sha,evaluator_root=self.root/'evaluator-private',image_mapping_sha256=self.images.content_sha256,dependency_freeze_sha256=s['dependency_freeze_sha256'])
        need(self.images.freeze['manifest_sha256']==digest(self.manifest),'NATIVE_IMAGE_MANIFEST_BINDING')
        source_index=strict((self.code/'source-manifest.json').read_bytes());need(type(source_index)in (dict,list)and len(source_index)>0,'NATIVE_REAL_SOURCE_INDEX_REQUIRED_NOT_EMPTY_STUB')
        need(not(self.root/f'k{self.binding.repeat}').exists(),'NATIVE_BRANCH_FRESH_NO_RETRY')
    def install(self):
        self.preflight();need(not any(n in sys.modules for n in ('comparison_core','request_policy_v54','finalization_engine_v1094','pilot_runtime_binding','limited_runner','level0_evaluator','cc_streaming')),'NATIVE_FRESH_PROCESS_REQUIRED')
        sys.path[:0]=[str(self.code),self.services['framework_root']]
        def module(name,**attrs):
            m=types.ModuleType(name);m.PURPOSE='AUX_FINALIZATION';m.__dict__.update(attrs);sys.modules[name]=m;return m
        def configure():
            os.environ.update(PYTHONPATH=self.services['framework_root'],DOCKER_HOST=self.services['docker_host'],DOCKER_CONFIG=self.services['docker_config'],LITELLM_LOCAL_MODEL_COST_MAP='True',PYTHONDONTWRITEBYTECODE='1')
            for key in ('DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):os.environ.pop(key,None)
            return copy.deepcopy(self.services)
        def final_binding_call(name,*a,**k):
            try:return getattr(self.binding,name)(*a,**k)
            except Refused as e:raise ControlFailure(e.code)from None
        module('pilot_runtime_binding',MANIFEST_SHA256=digest(self.manifest),trajectory_root=lambda:self.root,load_binding=lambda:({'purpose':'AUX_FINALIZATION','experiment_root':str(self.root)},{'purpose':'AUX_FINALIZATION','setting':self.binding.row['setting'],'trajectory_id':self.binding.trajectory,'checkpoints':sorted(set([10000000,20000000]+([self.binding.target]if self.binding.natural_stop is not None else [])))}),services=lambda:copy.deepcopy(self.services),configure_environment=configure,bind_request=lambda *a,**k:final_binding_call('bind_request',*a,**k),verify_request=lambda *a,**k:final_binding_call('verify_request',*a,**k),seed_provider_options=lambda *a,**k:final_binding_call('seed_provider_options',*a,**k))
        def spec(setting):
            need(setting in ('Agensh-16','Agensh-1'),'NATIVE_SCIENTIFIC_SETTING');return types.SimpleNamespace(final_mode='synthesize',proposals=16 if setting=='Agensh-16'else 1)
        module('setting_registry',names=lambda:('Agensh-16','Agensh-1'),get=spec,final_mode=lambda setting:spec(setting).final_mode)
        def reader(snapshot,branch,setting):return self.space.scope(snapshot,branch,setting)['member_cap']
        module('pilot_checkpoint',reader_scope=reader)
        module('pilot_materialization',admitted=self.space.admitted,materialize_terminal=self.materializer.materialize_terminal)
        module('pilot_admission',api_slot=self.port.api_slot)
        module('maintenance_guard_v54',MaintenancePause=self.port.MaintenancePause,before_request=self.port.before_request,begin_request=self.port.begin_request,failure=self.port.failure,wait_finalizer=self.port.wait_finalizer,paused=self.port.paused,state=self.port.state,locked=lambda:self.port.lock)
        module('pilot_images',verify_evaluator_image=self.images.verify_evaluator_image)
        worker=module('parallel_worker');text=(self.code/'parallel_worker.py').read_text();node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)and n.name=='locked_evaluate_pair');exec(compile(ast.Module(body=[node],type_ignores=[]),str(self.code/'parallel_worker.py'),'exec'),worker.__dict__)
        configure();core=importlib.import_module('comparison_core');need(core.ROOT==self.root and core.MODEL==self.binding.profile.policy['model'],'NATIVE_ROOT_OR_MODEL_CHANGED')
        config=importlib.import_module('v4_config');config.load(self.code/'config.json');policy=importlib.import_module('finalization_policy_v514');config.CURRENT=policy.configuration(config.values());need((config.current().finalization_turns,config.current().context_window,config.current().evaluation_slots)==(96,262144,4),'NATIVE_ORIGINAL_POLICY')
        stream=importlib.import_module('cc_streaming');stream.stream_call=self.port.wrap_stream(stream.stream_call)
        self.evaluator_custody=EvaluatorCustody(self.root/f'evaluator-custody-k{self.binding.repeat}')
        runner=importlib.import_module('limited_runner');self.evaluator_custody.wrap(runner.run_container)
        self.engine=importlib.import_module('finalization_engine_v1094');need(self.engine.ROOT==self.root and self.engine.C==self.code,'NATIVE_ENGINE_ROOT_CODE_BINDING')
        if self.binding.natural_stop is not None:
            from r16_natural_contract import install_exact_label_abi
            install_exact_label_abi(self.engine,self.code,self.binding.natural_stop)
        # All missing ports/profiles refuse before the engine's broad normal
        # fallback handler. Native protocol fingerprints are retained as well.
        signature=policy.signature(self.code,self.binding.row['setting'],config.values(),self.root/'evaluator-private')
        publish(self.root/f'native-signature-k{self.binding.repeat}.json',wire(signature),mode=0o400);self.installed=True
    def run(self):
        need(self.installed,'NATIVE_RUNTIME_NOT_INSTALLED');self.authorize();b=self.binding;branch=self.root/f'k{b.repeat}'
        from r16_natural_contract import label as point_label
        label=point_label(b.target,b.natural_stop);setting=b.row['setting']
        # An absent in-new-domain sentinel selects original archive-only path;
        # no live source workspace is ever handed to the native copy branch.
        sentinel=self.root/'NO_LIVE_SOURCE_WORKSPACE';need(not sentinel.exists(),'NATIVE_NO_LIVE_SOURCE_SENTINEL')
        metadata={'trajectory':b.trajectory,'replicate_index':b.repeat,'attempt_ordinal':1,'purpose':'AUX_FINALIZATION','source_sha256':b.policy['pins']['source'],'protocol_sha256':self.manifest['protocol']['final_v21'],'input_policy_sha256':b.input_sha,'native_domain_binding_sha256':digest(b.identity)}
        if b.replicate_attempt>1:metadata.update(replicate_attempt=b.replicate_attempt,point_id=b.point_id)
        if b.natural_stop is not None:metadata.update(point_kind='NATURAL_STOP',natural_stop=b.natural_stop)
        report=self.engine.finalize_checkpoint(setting,label,Path(b.input_root)/'snapshot',sentinel,branch=branch,result_label=f'{label}-k{b.repeat}',supplemental=False,protocol_metadata=metadata)
        frontier=self.client.call('frontier');need(frontier['unresolved']==0,'NATIVE_AUX_PHYSICAL_CUSTODY_UNRESOLVED')
        need(self.evaluator_custody is not None,'NATIVE_EVALUATOR_CUSTODY_REQUIRED')
        evaluator_frontier=self.evaluator_custody.frontier();need(evaluator_frontier['physical_terminal']and evaluator_frontier['unresolved']==0,'NATIVE_EVALUATOR_PHYSICAL_CUSTODY_UNRESOLVED')
        aggregate=self.root/'results'/setting/f'{label}-k{b.repeat}'/'aggregate.json'
        publish(branch/'physical-custody.json',wire({'schema':'count14-agensh-final-physical-custody-v1','trajectory':b.trajectory,'replicate_index':b.repeat,'target_tokens':b.target,'input_policy_sha256':b.input_sha,'native_model_and_evaluator_scopes_terminal':True,'unresolved':0,'evaluator_custody':evaluator_frontier,'aggregate_sha256':hash_file(aggregate)['sha256'],**({'replicate_attempt':b.replicate_attempt,'point_id':b.point_id} if b.replicate_attempt>1 else {})}),mode=0o400)
        return report
