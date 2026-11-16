"""Private host environment for SAME held core + pinned native Make/Compose.

No task/prompt/candidate/model/context file is read. Model CLI fields must be
explicitly admitted; no branch/model/root/daemon fallback. Service credentials
are new OWN-root infrastructure only, NEVER the GLM provider key. This compiler
does not launch containers or release scientific/model admission.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import re
import secrets
import shlex
import stat

from common import need,digest
from native_docker_scope import ScopedDocker,sha64
from native_cold_exports import _file,_json,_checked_native_gateway_companion
from native_layout import NativeLayout,native_names

MAKEFILE_SHA='0b5e984280bbb3d0a66db36ae8a666d25611c7850612afec3b66cf2f0272f9f6'
INFRA=('mysql','gitea','gitea-admin-init','mattermost','bootstrap','secret-service','board-service','nginx-edge')
MODEL_FIELDS={'COPILOT_PROVIDER_TYPE','COPILOT_PROVIDER_WIRE_API','COPILOT_AGENT_REASONING_EFFORT',
              'COPILOT_PROVIDER_MAX_PROMPT_TOKENS'}


def infra_labels(core,t,name):
    need(name in INFRA,'DYNTEAM_SAFE_INFRASTRUCTURE_ONLY_NO_RUNNER')
    return {'count14.root':core.rows[t]['root'],'count14.trajectory-sha256':digest(t),
        'count14.contract-sha256':digest(core.contract),'count14.role':'infra-'+name,'count14.component':'infra'}


@dataclass(frozen=True)
class NativeHostFacts:
    make_binary:Path
    make_sha256:str
    image_ids:dict
    native_model_env:dict
    public_runtime_env:dict
    opaque_task_executable:Path
    opaque_task_binding_sha256:str


def _executable(path,pin):
    path=Path(path);s=path.lstat()
    need(path.is_absolute() and path.resolve()==path and stat.S_ISREG(s.st_mode) and
         s.st_mode&0o111 and not s.st_mode&0o022 and s.st_uid in (0,os.geteuid()) and
         sha64(pin) and hashlib.sha256(path.read_bytes()).hexdigest()==pin,
         'DYNTEAM_FROZEN_HOST_CONTROL_EXECUTABLE')
    return str(path)


def new_formal_nginx_worker_config(core, t):
    """One fixed worker only for NEW formal infra, never a shared-host change.

    Original public nginx config remains immutable. Derive one private file,
    changing only worker_processes auto -> 1, same for both arms. Every proxy,
    SSE/WebSocket/header/timeout/security setting and all scientific caps stay.
    No existing file/container is rewritten, no AIO/sysctl/daemon operation.
    """
    need(core.contract.get('mode')=='production' and t in core.rows and
         set(core.gate.startup_held)==set(core.rows) and
         not core.scientific_activation_qualified,
         'DYNTEAM_NGINX_ONE_WORKER_ONLY_NEW_UNRELEASED_FORMAL_CONSTRUCTOR')
    export=core.cold_native_exports['trajectories'][t]
    source=Path(export['project_directory'])/'nginx-edge/nginx.conf'
    st=source.lstat()
    need(source.is_absolute() and source.resolve()==source and not source.is_symlink() and
         stat.S_ISREG(st.st_mode) and not st.st_mode&0o022 and st.st_nlink==1,
         'DYNTEAM_NGINX_ORIGINAL_PUBLIC_CONFIG_SOURCE_IDENTITY')
    raw=source.read_bytes()
    need(hashlib.sha256(raw).hexdigest()=='d2223fa649bb5da4aee652f7eb4559a88b227292cf65b5097521e02f443bc774' and
         raw.count(b'worker_processes auto;')==1 and b'worker_processes 1;'not in raw,
         'DYNTEAM_NGINX_EXACT_FROZEN_PUBLIC_CONFIG_ONE_WORKER_SITE')
    fixed=raw.replace(b'worker_processes auto;',b'worker_processes 1;',1)
    need(fixed.replace(b'worker_processes 1;',b'worker_processes auto;',1)==raw,
         'DYNTEAM_NGINX_ALL_OTHER_CONFIG_BYTES_FULL_INVERSE')
    home=Path(export['directory']);path=home/'nginx.formal-one-worker.private.conf'
    need(home.resolve()==home and home==Path(core.rows[t]['root'])/'native-cold-exports',
         'DYNTEAM_NGINX_ONLY_NEW_SAME_TRAJECTORY_PRIVATE_EXPORT')
    _file(path,fixed,0o400,os.geteuid())
    return {'type':'bind','source':str(path),'target':'/etc/nginx/nginx.conf','read_only':True}


def infrastructure_image_overlay(core,t,image_ids):
    """Fixed infra-only image/scope and approved graceful-stop wiring.

    This is generated before first create, never an update to a live container.
    No credentials, task/model parameters, new service or broad infra exception.
    """
    services={name:{'image':image_ids[name],'labels':infra_labels(core,t,name)} for name in INFRA}
    services['secret-service'].update(init=True,stop_signal='SIGINT')
    if core.contract.get('mode')=='production':
        services['nginx-edge']['volumes']=[new_formal_nginx_worker_config(core,t)]
    return {'services':services}


def prepare(core,*,facts,spawn_source,spawn_source_sha256,spawn_client,spawn_client_sha256,python_binary,
            python_sha256):
    need(type(facts) is NativeHostFacts and hasattr(core,'cold_native_exports') and
         core.cold_native_exports['state']=='EXPORTED_HELD_NOT_DOCKER_OR_SCIENTIFIC_PREPARED' and
         set(core.gate.startup_held)==set(core.rows) and hasattr(core,'native_containers') and
         not hasattr(core,'native_host_environment'),'DYNTEAM_NATIVE_HOST_ENV_ONLY_SAME_HELD_CORE')
    need(type(core.native_containers.docker) is ScopedDocker,'DYNTEAM_ORIGINAL_SCOPED_DOCKER_REQUIRED')
    docker=core.native_containers.docker;docker.verify_daemon()
    expected={'agent','router',*INFRA}
    need(type(facts.image_ids) is dict and set(facts.image_ids)==expected and
         all(type(x) is str and x.startswith('sha256:') and sha64(x[7:]) for x in facts.image_ids.values()) and
         core.native_containers.image_ids=={k:facts.image_ids[k] for k in ('agent','router')},
         'DYNTEAM_ALL_NATIVE_IMAGES_IMMUTABLE_AND_SAME_AS_PEER_REGISTRY')
    need(type(facts.native_model_env) is dict and set(facts.native_model_env)==MODEL_FIELDS and
         facts.native_model_env['COPILOT_PROVIDER_TYPE']=='openai' and
         facts.native_model_env['COPILOT_PROVIDER_WIRE_API']=='responses' and
         facts.native_model_env['COPILOT_AGENT_REASONING_EFFORT']==core.profile.policy['reasoning_effort'] and
         str(facts.native_model_env['COPILOT_PROVIDER_MAX_PROMPT_TOKENS']).isdigit() and
         int(facts.native_model_env['COPILOT_PROVIDER_MAX_PROMPT_TOKENS'])>0,
         'DYNTEAM_EXPLICIT_ORIGINAL_NATIVE_MODEL_CLI_ABI_NO_DEFAULTS')
    # Do NOT synthesize the native client context limit from the gateway's
    # reservation proof. Caller supplies its original frozen public CLI value.
    model_env={k:str(v) for k,v in facts.native_model_env.items()}
    need(type(facts.public_runtime_env) is dict and set(facts.public_runtime_env)==set(core.rows) and
         all(type(env) is dict and set(env)=={'EDGE_HTTP_PORT','EDGE_MM_PORT','JOBS'} and
             all(type(v) is str and v.isdigit() for v in env.values()) and
             all(0<int(env[k])<65536 for k in ('EDGE_HTTP_PORT','EDGE_MM_PORT')) for env in facts.public_runtime_env.values()) and
         len({env[k] for env in facts.public_runtime_env.values() for k in ('EDGE_HTTP_PORT','EDGE_MM_PORT')})==2*len(core.rows),
         'DYNTEAM_EXPLICIT_NATIVE_PUBLIC_PORT_RESOURCE_FIELDS')
    initial_only=(core.contract.get('mode')=='smoke' and facts.opaque_task_executable is None and
                  facts.opaque_task_binding_sha256 is None)
    task=None if initial_only else Path(facts.opaque_task_executable)
    if not initial_only:
        need(task.is_absolute() and task.parent.resolve()==task.parent and task.is_file() and not task.is_symlink() and
             sha64(facts.opaque_task_binding_sha256),'DYNTEAM_ORIGINAL_OPAQUE_PUBLIC_TASK_WRAPPER_BINDING')
    # stat only: task wrapper/input admission is supplied by the ORIGINAL
    # scientific factory. Never open/hash a target executable or question here.
    make=_executable(facts.make_binary,facts.make_sha256)
    python=_executable(python_binary,python_sha256)
    source=_executable(spawn_source,spawn_source_sha256)
    client=Path(spawn_client)
    need(client.is_absolute() and client.resolve()==client and client.is_file() and
         hashlib.sha256(client.read_bytes()).hexdigest()==spawn_client_sha256,'DYNTEAM_FROZEN_NATIVE_CONTROL_CLIENT')
    core.native_host_environment=dict(state='PARTIAL_RETAINED',trajectories={},task_binding_sha256=facts.opaque_task_binding_sha256,
        smoke_initial_tester_only_no_reference_ABI_claim=initial_only)
    for t,row in core.rows.items():
        export=core.cold_native_exports['trajectories'][t]
        destination=Path(export['directory']);project=Path(export['project_directory'])
        makefile=project.parent/'Makefile'
        need(makefile.is_file() and not makefile.is_symlink() and hashlib.sha256(makefile.read_bytes()).hexdigest()==MAKEFILE_SHA,
             'DYNTEAM_PINNED_ORIGINAL_NATIVE_MAKEFILE_AT_ACTUAL_PROJECT_ROOT')
        gateway_path=_checked_native_gateway_companion(core,t,export)
        profile,org=native_names(t)
        data=Path(row['root'])/'native-data'
        if hasattr(core,'native_layout'):
            need(type(core.native_layout) is NativeLayout,'DYNTEAM_EXACT_ORIGINAL_OWNER_LAYOUT_OBJECT')
            layout=core.native_layout.current(t)
            need(layout['data_root']==str(data) and layout['profile']==profile and layout['org']==org,
                 'DYNTEAM_NATIVE_ENV_SAME_PREPARED_LAYOUT')
        else:
            need(core.qualification_only,'DYNTEAM_PRODUCTION_ENV_MUST_USE_PLANNED_NATIVE_LAYOUT')
            data.mkdir(mode=0o700) # legacy OWN unit fixture, never arbitrary existing data
        # Original prep-mm-dirs on an entirely NEW scope, not recursive chmod
        # of an old workspace. No shared host path or existing node is changed.
        mm=data/profile/'mattermost';mm.mkdir(parents=True,mode=0o755)
        for directory in (mm,*(mm/name for name in ('data','logs','config','plugins'))):
            if directory!=mm:directory.mkdir(mode=0o755)
            if not core.qualification_only:os.chown(directory,2000,2000)
        env=dict(facts.public_runtime_env[t],**model_env,PROFILE=profile,DATA_ROOT=str(data),
            ORG_NAME=org,REPOS='main',GITEA_ADMIN_USER='chairman',MATTERMOST_ADMIN_USER='mmadmin',
            PBENCH_WORKERS_PER_TEAM='32',PBENCH_TESTERS='1' if row['arm']=='DYNTEAM' else '9',
            AGENT_IMAGE=facts.image_ids['agent'],MINI_ROUTER_IMAGE=facts.image_ids['router'],
            BOOTSTRAP_IMAGE=facts.image_ids['bootstrap'],BOARD_IMAGE=facts.image_ids['board-service'],
            SECRET_SERVICE_IMAGE=facts.image_ids['secret-service'],AGENT_KIND='copilot',
            ANTHROPIC_MODEL=core.profile.policy['model'],ANTHROPIC_API_KEY='LOCAL_ROLE_RELAY_ONLY_NO_PROVIDER_KEY')
        # Exact native generator already defines PBENCH_BIN's absent default.
        # For this initial-release-only smoke do NOT invent a reference binary,
        # mount an official evaluator or claim an untested wrapper ABI. No
        # periodic TesterRun.run/capture_reference/evaluate is started.
        if task is not None:env['PBENCH_BIN']=str(task)
        host,port=core.servers[t].server_address;env['ANTHROPIC_BASE_URL']=f'http://{host}:{port}/v1'
        for key in ('GITEA_ADMIN_PASSWORD','MATTERMOST_ADMIN_PASSWORD','MYSQL_PASSWORD','MYSQL_ROOT_PASSWORD','SECRET_SERVICE_INTERNAL_AUTH'):
            env[key]=secrets.token_urlsafe(36)
        need(all(re.fullmatch(r'[A-Z0-9_]+',k) and type(v) is str and v and '\n' not in v and '\r' not in v and
                 '\x00' not in v for k,v in env.items()),'DYNTEAM_NATIVE_ENV_SINGLE_LINE_ONLY')
        envfile=destination/'native.private.env'
        # The original shell's grep MYSQL_ROOT_PASSWORD expects bare values;
        # compile bare safe dotenv once, never publish then rewrite it.
        need(all(re.fullmatch(r'[A-Za-z0-9_./:@,+-]+',v) for v in env.values()),
             'DYNTEAM_NATIVE_ORIGINAL_SHELL_ENV_SAFE_SCALAR_ABI')
        _file(envfile,(''.join(k+'='+v+'\n' for k,v in sorted(env.items()))).encode(),0o400,os.geteuid())
        overlay_path=destination/'compose.private-overlay.json'
        # No decoding private overlay contents is needed: original compiler
        # emitted it; add an exact image/scope + secret-service normal-stop overlay, never PBENCH.
        image_overlay=destination/'compose.immutable-images.json'
        _json(image_overlay,infrastructure_image_overlay(core,t,facts.image_ids),0o400,os.geteuid())
        from smoke_bootstrap_task_ports import bootstrap_overlay
        source_overlay=destination/'compose.trusted-source-bootstrap.json'
        _json(source_overlay,bootstrap_overlay((project/'bootstrap/bootstrap.sh').read_bytes(),
            destination=destination/'trusted-source-bootstrap.sh'),0o400,os.geteuid())
        base=destination/'compose.native-base.yml'
        compose=docker.argv('compose','--project-directory',str(project),'-f',str(base),'-f',str(overlay_path),
            '-f',str(image_overlay),'-f',str(source_overlay),'-f',str(gateway_path),'--project-name','omcgitea-'+profile,'--env-file',str(envfile),'--profile',profile)
        launch=dict(COUNT14_NATIVE_MAKE=make,COUNT14_NATIVE_PROFILE=profile,COUNT14_NATIVE_ENV_FILE=str(envfile),
            COUNT14_NATIVE_COMPOSE_BASE=str(base),COUNT14_NATIVE_COMPOSE_COMMAND=shlex.join(compose),
            COUNT14_NATIVE_PYTHON=python,COUNT14_NATIVE_SPAWN_CLIENT=str(client),
            COUNT14_NATIVE_SPAWN_ROUTE=export['launcher_route'],COUNT14_NATIVE_SPAWN_ROUTE_SHA256=export['launcher_route_sha256'],
            COUNT14_NATIVE_DOCKER=str(docker.route.cli),COUNT14_NATIVE_DOCKER_SOCKET='unix://'+str(docker.route.socket_path))
        core.native_host_environment['trajectories'][t]=dict(profile=profile,data_root=str(data),envfile=str(envfile),
            compose=tuple(compose),launcher_env=launch,spawn_source=source,project_root=str(project.parent),
            initial_roles=tuple(row['initial_active_roles']),infra_services=INFRA)
        core.native_host_environment['trajectories'][t]['image_ids']=dict(facts.image_ids)
    core.native_host_environment['state']='HOST_ENV_EXPORTED_MODEL_GATES_HELD'
    return core.native_host_environment
