"""Strict PUBLIC bindings -> actual SAME-owner baseline smoke constructor.

Import is stdlib-only and side-effect-free. Generated entry installs only pinned
framework roots, never ambient env/cwd; actual create is explicit. No direct key,
question/archive/description/candidate/private-context read or model operation.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import os
import stat
import sys
import time
import urllib.parse

SOURCE_BINDING_SHA='a063532a03a06939242c19c8e9aa72e7acaef37feb4c5d0247db085a6a4c6724'
RETAINED_FACTORY_LEDGER=None
RETAINED_FACTORY_OWNER=None
FIELDS={'schema','template_only','code_root','framework_import_pins','host_guard','contract','model_policy','bounds',
    'provider','docker_route','network_proof','sources','host_facts','resource_plan','system_probe',
    'resource_sampler','baseline_smoke_sources','source_binding','projected_additional_bytes'}


def require(value,code):
    if not value:raise ValueError(code)


def _sha(value):
    require(type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value),
            'DYNTEAM_FACTORY_SHA256_REQUIRED')
    return value


def public(path,pin,maximum=1048576):
    path=Path(path);_sha(pin)
    require(path.is_absolute() and path.resolve()==path and not path.is_symlink() and
            path.name.endswith('PUBLIC.json'),'DYNTEAM_FACTORY_FIXED_PUBLIC_METADATA_ONLY')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);raw=os.read(fd,maximum+1);b=os.fstat(fd);c=path.lstat()
        identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        require(stat.S_ISREG(a.st_mode) and not a.st_mode&0o022 and a.st_uid in (0,os.geteuid()) and
                a.st_nlink==1 and 0<len(raw)==a.st_size<=maximum and identity(a)==identity(b)==identity(c) and
                hashlib.sha256(raw).hexdigest()==pin,'DYNTEAM_FACTORY_PUBLIC_METADATA_PIN_MODE_AND_IDENTITY')
    finally:os.close(fd)
    def pairs(items):
        value={}
        for k,v in items:
            require(k not in value,'DYNTEAM_FACTORY_DUPLICATE_PUBLIC_FIELD');value[k]=v
        return value
    value=json.loads(raw,object_pairs_hook=pairs)
    require(type(value) is dict,'DYNTEAM_FACTORY_PUBLIC_OBJECT_ONLY')
    return value


def descriptor(value,*,extra=()):
    require(type(value) is dict and set(value)=={'path','sha256',*extra},'DYNTEAM_FACTORY_EXACT_PUBLIC_DESCRIPTOR')
    _sha(value['sha256']);return value


def verify_framework_imports(path,pin,*,code_root):
    value=public(path,pin,8*1024*1024)
    require(set(value)=={'schema','code_root','roots'} and value['schema']=='count14-dynteam-framework-import-pins-v1' and
            value['code_root']==str(code_root) and type(value['roots']) is list and value['roots'],
            'DYNTEAM_FACTORY_COMPLETE_FROZEN_IMPORT_REGISTRY')
    roots=[]
    for row in value['roots']:
        require(type(row) is dict and set(row)=={'path','files'},'DYNTEAM_FACTORY_FRAMEWORK_ROOT_FIELDS')
        root=Path(row['path']);require(root.is_absolute() and root.resolve()==root and root.is_dir() and
            root not in roots and type(row['files']) is dict and row['files'], 'DYNTEAM_FACTORY_CANONICAL_PINNED_IMPORT_ROOT')
        roots.append(root)
        for name,expected in row['files'].items():
            relative=Path(name)
            require(not relative.is_absolute() and '..' not in relative.parts and relative.suffix in ('.py','.mjs','.js'),
                    'DYNTEAM_FACTORY_FRAMEWORK_CODE_ONLY_NOT_SCIENTIFIC_INPUT')
            _sha(expected);p=root/relative;s=p.lstat()
            require(p.resolve()==p and stat.S_ISREG(s.st_mode) and s.st_uid in (0,os.geteuid()) and
                    hashlib.sha256(p.read_bytes()).hexdigest()==expected,'DYNTEAM_FACTORY_FRAMEWORK_SOURCE_PIN')
    # No constructor, socket, task, provider credential or model is touched.
    sys.path[:0]=[str(p) for p in roots]
    return tuple(roots)


def verify_actual_import_graph():
    """Import actual cold/FINAL/kernel graph, NEVER construct or activate it.

    Called after complete frozen import roots are installed, including by the
    real -I factory verification entry. A stdlib-only wrapper import cannot
    stand in for qualification of the child/host dependency paths.
    """
    from native_cold_owner import NativeColdOwner,NativeSourcePins
    from native_host_environment import NativeHostFacts
    from native_baseline_smoke import NativeBaselineSmoke,BaselineSmokeSources
    from native_dynamic_checkpoint import DynamicCheckpointPorts
    from smoke_checkpoint_final_controller import SmokeFinalController
    from smoke_checkpoint_final_retirement import SmokeFinalRetirement
    from smoke_racing_tools_kernel_custody import NativeKernelToolCustody
    from native_system_health import SystemProbeSources
    from native_resource_producer import ResourceSamplerSources
    from native_cohort_resources import CohortAllocation
    from scientific_relay import Bounds
    from feasibility_relay import ChatTransport
    import glm_session_header
    return {'actual_framework_import_graph':True,'owner_created':False,'models':0}


def validate_bindings(value,*,code_root):
    require(type(value) is dict and set(value)==FIELDS and value['schema']=='count14-dynteam-baseline-smoke-bindings-v1' and
            value['template_only'] is False and value['code_root']==str(code_root),
            'DYNTEAM_FACTORY_REAL_BINDINGS_NOT_TEMPLATE_OR_SHADOW')
    root=Path(code_root);require(root.is_absolute() and root.resolve()==root and root.is_dir(),
                               'DYNTEAM_FACTORY_CODE_ROOT_CANONICAL')
    for k in ('framework_import_pins','network_proof','resource_plan','source_binding'):
        descriptor(value[k])
    require(value['source_binding']['sha256']==SOURCE_BINDING_SHA,
            'DYNTEAM_FACTORY_EXACT_APPROVED_ORIGINAL_SOURCE_BINDING')
    for k in ('model_policy','bounds'):descriptor(value[k],extra=('canonical_sha256',));_sha(value[k]['canonical_sha256'])
    c=value['contract']
    require(type(c) is dict and set(c)=={'directory','filename','sha256','index_sha256','canonical_sha256'} and
            c['filename']=='SMOKE_PUBLIC_CONTRACT.json','DYNTEAM_FACTORY_EXACT_SMALL_SMOKE_CONTRACT')
    for key in ('sha256','index_sha256','canonical_sha256'):_sha(c[key])
    p=value['provider']
    require(type(p) is dict and set(p)=={'base_url','timeout_seconds','maximum_output','key_path'} and
            type(p['timeout_seconds']) in (int,float) and math.isfinite(p['timeout_seconds']) and
            0<p['timeout_seconds']<=86400 and
            (p['maximum_output']is None or type(p['maximum_output'])is int and p['maximum_output']>0),
            'DYNTEAM_FACTORY_EXPLICIT_ORIGINAL_PROVIDER_PARAMETERS')
    parsed=urllib.parse.urlsplit(p['base_url'])
    require(parsed.scheme in ('http','https') and parsed.hostname and not parsed.username and not parsed.password and
            not parsed.query and not parsed.fragment and parsed.path.rstrip('/').endswith('/v1'),
            'DYNTEAM_FACTORY_ORIGINAL_GLM_ENDPOINT_NO_CREDENTIAL_IN_URL')
    require(type(value['projected_additional_bytes']) is int and value['projected_additional_bytes']>=0,
            'DYNTEAM_FACTORY_EXPLICIT_BOOTSTRAP_FORECAST')
    return value


def _file_json(value):
    """Pinned PUBLIC policy/proof may use its historical .json filename."""
    from common import strict,hash_file,digest
    p=Path(value['path']);s=p.lstat()
    require(p.is_absolute() and p.resolve()==p and stat.S_ISREG(s.st_mode) and s.st_size<=1048576 and
            s.st_uid in (0,os.geteuid()) and not s.st_mode&0o022 and hash_file(p)['sha256']==value['sha256'],
            'DYNTEAM_FACTORY_FROZEN_PUBLIC_POLICY_OR_BOUNDS')
    result=strict(p.read_bytes());require(digest(result)==value['canonical_sha256'],
                                        'DYNTEAM_FACTORY_POLICY_OR_BOUNDS_CANONICAL_PIN')
    return result


def _typed(cls,value,path_fields):
    import dataclasses
    require(type(value) is dict and set(value)=={f.name for f in dataclasses.fields(cls)},
            'DYNTEAM_FACTORY_EXACT_TYPED_PARAMETER_FIELDS')
    return cls(**{k:(None if v is None and k=='opaque_task_executable' else Path(v))
                  if k in path_fields else v for k,v in value.items()})


def _partial(owner,error,phase):
    frames=[];tb=error.__traceback__
    while tb:
        frames.append({'file':tb.tb_frame.f_code.co_filename,'line':tb.tb_lineno,
                       'function':tb.tb_frame.f_code.co_name});tb=tb.tb_next
    owner.errors.append({'PUBLIC_code':'DYNTEAM_FACTORY_POST_OWNER_PARTIAL_RETAINED_NO_RETRY',
        'exception_type':type(error).__name__,'locations':frames,'failed_phase':phase})
    owner.state='PARTIAL_RETAINED_MODELS_NOT_ACTIVATED'
    return owner


def create_prefix_owner(bindings_path,bindings_sha256,*,code_root,factory_path,factory_manifest):
    global RETAINED_FACTORY_LEDGER,RETAINED_FACTORY_OWNER
    require(RETAINED_FACTORY_LEDGER is None and RETAINED_FACTORY_OWNER is None,
            'DYNTEAM_FACTORY_UNIQUE_OWNER_CONSTRUCTOR_NO_REPLAY')
    b=validate_bindings(public(bindings_path,bindings_sha256),code_root=code_root)
    descriptor(b['framework_import_pins'])
    verify_framework_imports(b['framework_import_pins']['path'],b['framework_import_pins']['sha256'],code_root=code_root)
    from common import strict,digest,hash_file
    from native_catalogue_directory import open_from_frozen_directory,read_frozen_catalogues
    from native_docker_scope import DockerRoute,ScopedDocker
    from native_network_binding import NativeNetworkBinding
    from native_cold_owner import NativeColdOwner,NativeSourcePins
    from native_host_environment import NativeHostFacts
    from native_system_health import SystemProbeSources
    from native_resource_producer import ResourceSamplerSources
    from native_cohort_resources import CohortAllocation
    from scientific_relay import Bounds
    from feasibility_relay import ChatTransport
    from native_baseline_smoke import BaselineSmokeSources
    from smoke_racing_tools_kernel_custody import NativeKernelToolCustody
    guard=b['host_guard']
    require(type(guard) is dict and set(guard)=={'hostname','boot_id','uid'} and guard['uid']==0==os.geteuid() and
            os.uname().nodename==guard['hostname'] and
            Path('/proc/sys/kernel/random/boot_id').read_text().strip()==guard['boot_id'],
            'DYNTEAM_FACTORY_EXACT_CURRENT_DEV4_HOST_BOOT_UID')
    c=b['contract'];directory=Path(c['directory'])
    catalogue=read_frozen_catalogues(directory,contract_filename=c['filename'],contract_sha256=c['sha256'],index_sha256=c['index_sha256'])
    contract=strict((directory/c['filename']).read_bytes())
    require(catalogue.mode=='smoke' and digest(contract)==c['canonical_sha256'],
            'DYNTEAM_FACTORY_EXACT_REGISTERED_PAIRED_SMALL_CONTRACT')
    home=Path(contract['arms'][0]['root'])/'owner'
    for row in contract['trajectories']:
        p=Path(row['root']);require(p.is_absolute() and p.resolve()==p and p.is_dir() and
            (p.is_relative_to('/mnt/ptb-scratch2') or p.is_relative_to('/mnt/ptb-scratch')),
            'DYNTEAM_FACTORY_ONLY_REGISTERED_NEW_SCRATCH_TRAJECTORY_ROOTS')
    route=_typed(DockerRoute,b['docker_route'],{'cli','socket_path','data_root'})
    require(route.qualification_only is False,'DYNTEAM_FACTORY_REAL_PRIVATE_DOCKER_NOT_SHADOW')
    docker=ScopedDocker(route)
    network=public(b['network_proof']['path'],b['network_proof']['sha256'])
    require(set(network)=={'schema','observed_ns','boot_id','daemon_id','data_root','networks'} and
            network['schema']=='count14-dynteam-current-network-inspect-public-v1' and
            type(network['observed_ns']) is int and 0<=time.time_ns()-network['observed_ns']<=60*10**9 and
            network['boot_id']==guard['boot_id'] and network['daemon_id']==route.daemon_id and
            network['data_root']==str(route.data_root) and set(network['networks'])=={r['trajectory_id'] for r in contract['trajectories']},
            'DYNTEAM_FACTORY_FRESH_SAME_BOOT_PRIVATE_DAEMON_NETWORK_PROOF')
    networks={r['trajectory_id']:NativeNetworkBinding.from_public_inspect(network['networks'][r['trajectory_id']],
        daemon_data_root=route.data_root,contract=contract,row=r,qualification_only=False) for r in contract['trajectories']}
    policy=_file_json(b['model_policy']);proof=_file_json(b['bounds']);bounds=Bounds(proof,b['bounds']['canonical_sha256'])
    require((bounds.context_limit is not None and b['provider']['maximum_output']is None)or
            (bounds.context_limit is None and type(b['provider']['maximum_output'])is int and
             0<b['provider']['maximum_output']<=proof['maximum_output_tokens']),
            'DYNTEAM_FACTORY_PINNED_BOUNDS_AND_OUTPUT_MODE_MATCH')
    sources=_typed(NativeSourcePins,b['sources'],{'guarded_agent_directory','compiled_router_directory','public_router_source',
        'native_generator','native_project_directory','spawn_source','spawn_client','python_binary'})
    facts=_typed(NativeHostFacts,b['host_facts'],{'make_binary','opaque_task_executable'})
    system=_typed(SystemProbeSources,b['system_probe'],{'python','child'})
    baseline=_typed(BaselineSmokeSources,b['baseline_smoke_sources'],{'original_task_host_source','native_pbench_source',
        'native_tester_source','final_configuration'})
    plan=public(b['resource_plan']['path'],b['resource_plan']['sha256'])
    require(plan['contract_sha256']==digest(contract),'DYNTEAM_FACTORY_RESOURCE_PLAN_SAME_CANONICAL_CONTRACT')
    allocation=CohortAllocation(b['resource_plan']['sha256'],plan['other_maximum_FP8_inflight']).checked()
    # Self manifest validation breaks the hash cycle: bindings pin exact PATH,
    # while the original entry caller independently pins this manifest's SHA.
    sampler=dict(b['resource_sampler'])
    require(set(sampler)=={'python','python_sha256','child','child_sha256','factory_manifest','bootstrap_sha256'} and
            Path(sampler['factory_manifest'])==Path(factory_manifest),
            'DYNTEAM_FACTORY_SAMPLER_EXACT_SELF_ENTRY_MANIFEST_PATH')
    fp=Path(factory_path);fm=Path(factory_manifest);fmsha=hash_file(fm)['sha256'];manifest=public(fm,fmsha)
    require(manifest=={'schema':'count14-native-cold-owner-public-factory-v1','package_code_root':str(code_root),
        'factory_path':str(fp),'factory_sha256':hash_file(fp)['sha256'],'entry':'create_prefix_owner'},
        'DYNTEAM_FACTORY_SAMPLER_IMPORTS_SAME_PINNED_ACTUAL_OWNER_ENTRY')
    sampler['factory_manifest_sha256']=fmsha
    sampler=_typed(ResourceSamplerSources,sampler,{'python','child','factory_manifest'})
    key=Path(b['provider']['key_path']);s=key.lstat()
    require(key.is_absolute() and key.resolve()==key and stat.S_ISREG(s.st_mode) and s.st_uid==0 and
            s.st_nlink==1 and not s.st_mode&0o077,'DYNTEAM_FACTORY_NEW_KEY_PATH_STAT_ONLY')
    # No key read here. Original per-request HeaderOpener replaces this explicit
    # inert authorization field with the new key and exact original SID.
    def transport(_):return ChatTransport(b['provider']['base_url'],'ORIGINAL_HEADER_OPENER_SUPPLIES_NEW_KEY',
        auth_style='bearer',timeout=b['provider']['timeout_seconds'])
    custody=NativeKernelToolCustody()
    ledger=open_from_frozen_directory(home/'ledger',directory,contract_filename=c['filename'],
        contract_sha256=c['sha256'],index_sha256=c['index_sha256'],qualification_only=False)
    RETAINED_FACTORY_LEDGER=ledger
    owner=NativeColdOwner.prepare(core_arguments={'ledger':ledger,'contract':contract,'home':home,
        'original_model_policy':policy,'original_model_policy_sha256':b['model_policy']['canonical_sha256'],
        'bounds':bounds,'maximum_output':b['provider']['maximum_output'],'key_path':key,'transport_factory':transport,
        'qualification_only':False,'native_networks':networks},docker=docker,host_facts=facts,sources=sources,
        native_uid=10000,original_tool_physical_clear=custody,projected_additional_bytes=b['projected_additional_bytes'],
        resource_allocation=allocation,system_probe_sources=system,
        resource_producer={'plan_path':Path(b['resource_plan']['path']),'plan_sha256':b['resource_plan']['sha256'],'sources':sampler})
    RETAINED_FACTORY_OWNER=owner
    if owner.errors:return owner
    phase='BINDING_SAME_ORIGINAL_KERNEL_CUSTODY'
    try:
        custody.bind(owner.core)
        phase='BINDING_SAME_ORIGINAL_BASELINE_SMOKE_GRAPH'
        owner.bind_scientific_smoke(sources=baseline)
        # PREPARE_SOURCE is the NORMAL original control entry after the first
        # real finite resource sample. No fake freshness and no blind retry.
        owner.factory_source_binding=dict(b['source_binding'])
        owner.factory_bindings_sha256=bindings_sha256
        return owner
    except BaseException as error:return _partial(owner,error,phase)
