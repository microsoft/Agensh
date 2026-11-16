#!/usr/bin/env python3
"""Frozen public code/contracts -> actual smoke bindings; no guessed ABI.

Reads only a fixed PUBLIC code layout, public control receipts, reviewed public
framework code/policy/contracts. Never opens/hashes the opaque task executable,
key, question/archive/index, candidate, prompt asset, pickle or private config.
Missing original invocation/tool proof yields a draft + exact fact request, NOT
an executable bindings file and not a green proof. No Docker/model/owner action.
"""
import os as _count14_os  # endpoints/keys come from environment; see CONFIGURATION.md
from pathlib import Path
import argparse
import ast
import hashlib
import importlib.util
import json
import os
import stat

N26_API_CONTEXT_PROOF={'maximum_context_tokens': 524288, 'metadata_get_evidence_sha256': '2c2234bcd1501460d3e80892cbfbbdf98cec28f395b7d51a4136e371b2d1747d', 'model': 'GLM-5.3-FP8', 'model_metadata_sha256': 'c31e06b0f75e128a7fc511dcf45b2cc15c7c9293c56534609e9784e968e53fe6', 'schema': 'agensh-api-context-reservation-proof-v1', 'scope': 'ENTIRE_EXPANDED_CHAT_PROMPT_TOOLS_AND_OUTPUT', 'server_enforces_context_ceiling': True, 'source_url': (_count14_os.environ.get('COUNT14_GLM_BASE_URL', 'https://glm-gateway.example.invalid/v1').rstrip('/') + '/models'), 'wire_policy': 'PASSTHROUGH_CLIENT_MAX_ELSE_OMIT'}
N26_API_CONTEXT_PROOF_PIN='38449d748927483305970b104f2915bd4c2a00c767fdb4d0aa400a72a9ef1fd4'
HOST_SOURCE_SHA='2cb144cdb2b7aeedff8c804d90222e2ccabb6820ee4f462436911197e38776f4'
ORIGINAL_CONFIG_PIN='c9b359f812c4b2b2601312ec566dfb091fc070354c39d9c0e223d7e57688882e'
INFRA=('mysql','gitea','gitea-admin-init','mattermost','bootstrap','secret-service','board-service','nginx-edge')
LAYOUT_FIELDS={'schema','code_root','framework_import_pins','contract_directory','native_source_tree',
    'guarded_agent_directory','compiled_router_directory','public_router_source','spawn_source',
    'original_task_host_source','source_binding','final_configuration'}
FACT_FIELDS={'schema','template_only','host_guard','python','make','docker_route','image_ids','public_runtime_ports',
    'network_proof','resource_plan','key_path','projected_additional_bytes','original_invocation_public',
    'original_tester_executable_public'}


def helper():
    p=Path(__file__).with_name('smoke_bootstrap_task_factory.py')
    s=importlib.util.spec_from_file_location('count14_actual_smoke_input_schema',p)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_file(path,root):
    p=Path(path);s=p.lstat()
    H.require(p.is_absolute() and p.resolve()==p and p.is_relative_to(root) and stat.S_ISREG(s.st_mode),
              'DYNTEAM_INPUTS_FROZEN_PACKAGE_FRAMEWORK_ONLY')
    return p


def original_cli_environment(path):
    p=Path(path);raw=p.read_bytes()
    H.require(hashlib.sha256(raw).hexdigest()==HOST_SOURCE_SHA,'DYNTEAM_INPUTS_ORIGINAL_SUCCESSFUL_HOST_SOURCE_PIN')
    wanted={'COPILOT_PROVIDER_TYPE','COPILOT_PROVIDER_WIRE_API','COPILOT_AGENT_REASONING_EFFORT',
            'COPILOT_PROVIDER_MAX_PROMPT_TOKENS','JOBS'}
    found=[]
    for node in ast.walk(ast.parse(raw)):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='update':
            values={k.arg:k.value.value for k in node.keywords if k.arg in wanted and isinstance(k.value,ast.Constant)}
            if set(values)==wanted:found.append(values)
    H.require(len(found)==1 and found[0]=={'COPILOT_PROVIDER_TYPE':'openai','COPILOT_PROVIDER_WIRE_API':'responses',
        'COPILOT_AGENT_REASONING_EFFORT':'max','COPILOT_PROVIDER_MAX_PROMPT_TOKENS':'110592','JOBS':'8'},
        'DYNTEAM_INPUTS_EXACT_ORIGINAL_CLI_ENV_NOT_DEFAULT_OR_BOUND_GUESS')
    return found[0]


def compile_inputs(layout_path,layout_sha256,*,destination,host_facts_path=None,host_facts_sha256=None):
    global H
    H=helper();layout=H.public(layout_path,layout_sha256)
    H.require(set(layout)==LAYOUT_FIELDS and layout['schema']=='count14-dynteam-smoke-code-layout-v1',
              'DYNTEAM_INPUTS_EXACT_FROZEN_CODE_LAYOUT')
    root=Path(layout['code_root'])
    H.require(root.is_absolute() and root.resolve()==root and root.is_dir(),'DYNTEAM_INPUTS_REAL_FROZEN_CODE_ROOT')
    for k in ('framework_import_pins','source_binding','final_configuration'):H.descriptor(layout[k])
    H.require(layout['source_binding']['sha256']==H.SOURCE_BINDING_SHA,'DYNTEAM_INPUTS_SAME_APPROVED_SOURCE_METADATA')
    source=H.public(layout['source_binding']['path'],layout['source_binding']['sha256'])
    contracts=Path(layout['contract_directory']);contract_path=code_file(contracts/'SMOKE_PUBLIC_CONTRACT.json',root)
    contract_sha=sha(contract_path);contract=json.loads(contract_path.read_bytes())
    index=code_file(contracts/'CONTRACT_AND_NATIVE_ROLE_DIRECTORY_PINS_PUBLIC.json',root)
    H.require(contract['schema']=='count14-dynteam-two-arm-public-contract-v1' and contract['mode']=='smoke' and
        len(contract['trajectories'])==2 and {r['arm'] for r in contract['trajectories']}=={'DYNTEAM','DYNTEAM_RACING'} and
        all(r['checkpoints_tokens']==[500000,1000000] and r['search_tokens']==1000000 and r['request_cap']==13 for r in contract['trajectories']) and
        source['protocol']=={k:contract['v2_baseline_reference_protocol'][k] for k in ('source_bundle','task_description')},
        'DYNTEAM_INPUTS_EXACT_PAIRED_SMALL_BUDGET_AND_ORIGINAL_COUNT14_INPUT_PINS')
    policy=code_file(root/'original-v2-model-policy-v1/model_policy.json',root)
    # This file is pinned public model control metadata, not science content.
    policy_value=json.loads(policy.read_bytes());policy_pin=digest(policy_value)
    H.require(policy_pin==contract['v2_baseline_reference_protocol']['model_configuration'],
              'DYNTEAM_INPUTS_CANONICAL_ORIGINAL_MODEL_POLICY')
    native=Path(layout['native_source_tree'])
    H.require(native.is_absolute() and native.resolve()==native and native.is_relative_to(root),
              'DYNTEAM_INPUTS_FROZEN_BETA_FRAMEWORK_NOT_QUESTION_SOURCE')
    generator=code_file(native/'tools/gen-compose-prod.py',root)
    runtime=Path(__file__).resolve().parent
    H.require(runtime==root/'runtime-v1-msg237-held20-v1-msg237-prefix21-v1','DYNTEAM_INPUTS_COMPILER_FROM_SAME_INSTALLED_FROZEN_CODE_ROOT')
    cli=original_cli_environment(code_file(layout['original_task_host_source'],root));jobs=cli.pop('JOBS')
    H.require(cli['COPILOT_AGENT_REASONING_EFFORT']==policy_value['reasoning_effort'],
              'DYNTEAM_INPUTS_ORIGINAL_NATIVE_AND_RELAY_REASONING_EQUAL')
    spawn=code_file(layout['spawn_source'],root);client=code_file(runtime/'native_spawn_client.py',root)
    # Pin all candidate-independent filenames from the final package, not an
    # old intermediate source-vNN directory selected by a default.
    for name in ('guarded_agent_directory','compiled_router_directory','public_router_source'):
        p=Path(layout[name]);H.require(p.is_absolute() and p.resolve()==p and p.is_dir() and p.is_relative_to(root),
                                    'DYNTEAM_INPUTS_EXACT_FINAL_FROZEN_COLD_EXPORT_DIRECTORY')
    sources={'guarded_agent_directory':layout['guarded_agent_directory'],'compiled_router_directory':layout['compiled_router_directory'],
        'public_router_source':layout['public_router_source'],'native_generator':str(generator),'native_generator_sha256':sha(generator),
        'native_project_directory':str(native/'docker'),'spawn_source':str(spawn),'spawn_source_sha256':sha(spawn),
        'spawn_client':str(client),'spawn_client_sha256':sha(client),'python_binary':None,'python_sha256':None}
    bindings={'schema':'count14-dynteam-baseline-smoke-bindings-v1','template_only':True,'code_root':str(root),
        'framework_import_pins':dict(layout['framework_import_pins']),
        'host_guard':None,'contract':{'directory':str(contracts),'filename':contract_path.name,'sha256':contract_sha,
            'index_sha256':sha(index),'canonical_sha256':digest(contract)},
        'model_policy':{'path':str(policy),'sha256':sha(policy),'canonical_sha256':policy_pin},'bounds':None,'provider':None,
        'docker_route':None,'network_proof':None,'sources':sources,
        'host_facts':{'make_binary':None,'make_sha256':None,'image_ids':None,'native_model_env':cli,'public_runtime_env':None,
            'opaque_task_executable':None,'opaque_task_binding_sha256':None},
        'resource_plan':None,'system_probe':{'python':None,'python_sha256':None,
            'child':str(runtime/'native_system_probe_child.py'),'child_sha256':sha(code_file(runtime/'native_system_probe_child.py',root))},
        'resource_sampler':{'python':None,'python_sha256':None,'child':str(runtime/'native_resource_sample_child.py'),
            'child_sha256':sha(code_file(runtime/'native_resource_sample_child.py',root)),
            'factory_manifest':str(root/'factory/FACTORY_PUBLIC.json'),
            'bootstrap_sha256':sha(code_file(runtime/'native_cold_owner_entry.py',root))},
        'baseline_smoke_sources':{'original_task_host_source':layout['original_task_host_source'],
            'native_pbench_source':str(code_file(native/'scripts/pbench_run.sh',root)),
            'native_tester_source':str(code_file(native/'scripts/pbench_tester.py',root)),
            'final_configuration':layout['final_configuration']['path'],
            'final_configuration_sha256':layout['final_configuration']['sha256']},
        'source_binding':dict(layout['source_binding']),'projected_additional_bytes':None}
    missing=[];required=[]
    facts=None
    if host_facts_path is not None:
        H.require(host_facts_sha256 is not None,'DYNTEAM_INPUTS_HOST_FACTS_RAW_PIN_REQUIRED')
        facts=H.public(host_facts_path,host_facts_sha256)
        H.require(set(facts) in (FACT_FIELDS,FACT_FIELDS-{'original_tester_executable_public'}) and facts['schema']=='count14-dynteam-smoke-fresh-host-facts-v1' and
                  facts['template_only'] is False,'DYNTEAM_INPUTS_REAL_FRESH_HOST_FACTS_NOT_TEMPLATE')
        for k in ('host_guard','docker_route','network_proof','resource_plan','projected_additional_bytes'):bindings[k]=facts[k]
        for k in ('python','make'):H.descriptor(facts[k])
        for target in (bindings['sources'],):target.update(python_binary=facts['python']['path'],python_sha256=facts['python']['sha256'])
        for target in (bindings['system_probe'],bindings['resource_sampler']):target.update(python=facts['python']['path'],python_sha256=facts['python']['sha256'])
        hf=bindings['host_facts'];hf.update(make_binary=facts['make']['path'],make_sha256=facts['make']['sha256'],image_ids=facts['image_ids'])
        H.require(set(facts['image_ids'])=={'agent','router',*INFRA} and
                  all(type(v) is str and v.startswith('sha256:') and len(v)==71 for v in facts['image_ids'].values()),
                  'DYNTEAM_INPUTS_EXACT_FROZEN_NEW_NATIVE_IMAGE_MAP')
        ports=facts['public_runtime_ports'];H.require(set(ports)=={r['trajectory_id'] for r in contract['trajectories']} and
            all(type(v) is dict and set(v)=={'EDGE_HTTP_PORT','EDGE_MM_PORT'} for v in ports.values()),
            'DYNTEAM_INPUTS_ONLY_FRESH_PUBLIC_PORTS_NOT_USER_GUESSED_JOBS_OR_MODEL_ENV')
        hf['public_runtime_env']={t:{**v,'JOBS':jobs} for t,v in ports.items()}
    else:missing.append('FRESH_HOST_DOCKER_NETWORK_RESOURCE_KEY_PATH_METADATA')
    invocation=None if facts is None else facts['original_invocation_public']
    if invocation is None:
        missing.append('ORIGINAL_PUBLIC_BOUNDS_MAX_OUTPUT_ENDPOINT_DESCRIPTOR')
    else:
        H.descriptor(invocation);old=H.public(invocation['path'],invocation['sha256'])
        H.require(set(old)=={'schema','original_configuration_public_pin','model_policy_canonical_sha256','base_url',
            'timeout_seconds','maximum_output','bounds'} and old['schema']=='count14-original-glm-invocation-public-v1' and
            old['original_configuration_public_pin']==ORIGINAL_CONFIG_PIN and old['model_policy_canonical_sha256']==policy_pin,
            'DYNTEAM_INPUTS_TRUE_ORIGINAL_PUBLIC_INVOCATION_NOT_OWN_OR_CLI_INFERENCE')
        H.descriptor(old['bounds'],extra=('canonical_sha256',))
        bindings['bounds']=old['bounds'];bindings['provider']={k:old[k] for k in ('base_url','timeout_seconds','maximum_output')}
        bindings['provider']['key_path']=facts['key_path']
    # EXACT paired 500k/1M smoke only: original release0 never invokes the
    # reference executable. Do NOT manufacture a stat-only wrapper or claim a
    # reference ABI. The original generator/default mount remains byte-equal;
    # host leaves PBENCH_BIN absent, and continuous TesterRun is not admitted.
    H.require(facts is None or facts.get('original_tester_executable_public') is None,
              'DYNTEAM_SMOKE_CYCLE0_ONLY_REFERENCE_WRAPPER_MUST_REMAIN_DISABLED')
    reference_mode={'schema':'count14-native-cycle0-only-smoke-reference-scope-v1',
        'opaque_task_executable':None,'opaque_task_binding_sha256':None,
        'PBENCH_BIN_environment_set':False,'original_native_generator_unchanged':True,
        'original_native_default_reference_mount_unchanged':True,
        'tester_reference_probe_enabled':False,'continuous_tester_run_enabled':False,
        'reference_argv_ABI_proven':False,'formal_100M_reference_adaptation_still_required':True}
    required=[{'code':x,'do_not_guess_or_replace_with_OWN':True} for x in missing]
    output=Path(destination);H.require(output.is_absolute() and output.parent.resolve()==output.parent and not output.exists(),
                                      'DYNTEAM_INPUTS_NEW_OUTPUT_ONLY_NO_BINDINGS_REWRITE')
    output.mkdir(mode=0o700)
    def save(name,value):
        p=output/name;raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
        try:
            with os.fdopen(fd,'wb',closefd=False) as out:out.write(raw);out.flush();os.fsync(fd)
            os.fchmod(fd,0o444)
        finally:os.close(fd)
        return {'path':str(p),'sha256':hashlib.sha256(raw).hexdigest()}
    if contract['mode']=='production'and bindings['provider']is not None:
        H.require(digest(N26_API_CONTEXT_PROOF)==N26_API_CONTEXT_PROOF_PIN and
                  (N26_API_CONTEXT_PROOF['model'],policy_value['model'])==('GLM-5.3-FP8','VLLM-GATEWAY-GLM-5.3-FP8'),
                  'DYNTEAM_N26_REAL_API_CONTEXT_PROOF_AND_MODEL')
        api=save('N26_API_CONTEXT_RESERVATION_PROOF_PUBLIC.json',N26_API_CONTEXT_PROOF)
        api['canonical_sha256']=N26_API_CONTEXT_PROOF_PIN
        bindings['bounds']=api
        bindings['provider']['maximum_output']=None
    draft=save('DERIVED_STATIC_FACTORY_DRAFT_PUBLIC.json',{'schema':'count14-dynteam-smoke-derived-static-draft-v1',
        'source_layout_sha256':layout_sha256,'factory_bindings':bindings,
        'original_native_environment_source_sha256':HOST_SOURCE_SHA,'derived_original_JOBS':jobs,
        'unproven_facts':required,'smoke_only_reference_scope':reference_mode,
        'private_or_scientific_inputs_opened':False,'models':0})
    request=save('REQUIRED_OPS_FACTS_PUBLIC.json',{'schema':'count14-dynteam-smoke-exact-facts-request-v1','items':required,
        'bounds_not_derived_from_110592_CLI_limit':True,'smoke_only_reference_scope':reference_mode,
        'unused_wrapper_descriptor_not_required_for_this_cycle0_only_smoke':True,'waiting_is_not_blocked':True})
    final=None
    if not missing:
        bindings['template_only']=False;H.validate_bindings(bindings,code_root=root)
        final=save('FACTORY_BINDINGS_PUBLIC.json',bindings)
    return {'schema':'count14-dynteam-smoke-inputs-compile-result-v1','ready_to_instantiate_factory':not missing,
        'bindings':final,'static_draft':draft,'required_facts':request,'missing_fact_codes':missing,
        'owner_created':False,'models':0,'scientific_smoke_pass':False}


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--code-layout',required=True);p.add_argument('--code-layout-sha256',required=True)
    p.add_argument('--destination',required=True);p.add_argument('--host-facts');p.add_argument('--host-facts-sha256');a=p.parse_args(argv)
    try:
        result=compile_inputs(a.code_layout,a.code_layout_sha256,destination=a.destination,
            host_facts_path=a.host_facts,host_facts_sha256=a.host_facts_sha256)
        print(json.dumps(result,sort_keys=True));return 0
    except BaseException as e:
        rows=[];tb=e.__traceback__
        while tb:rows.append({'file':tb.tb_frame.f_code.co_filename,'line':tb.tb_lineno,'function':tb.tb_frame.f_code.co_name});tb=tb.tb_next
        print(json.dumps({'PUBLIC_code':'DYNTEAM_INPUTS_COMPILATION_REFUSED','exception_type':type(e).__name__,'locations':rows},sort_keys=True));return 2

if __name__=='__main__':raise SystemExit(main())
