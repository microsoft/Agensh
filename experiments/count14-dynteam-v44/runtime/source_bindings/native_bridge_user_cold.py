"""Approved all-native-role bridge USER wiring on a NEW held control graph.

msg205+206: both registered smoke roots and formal six tracks only. Does not
start roles, restrict growth, replace containers or grant runtime authority.
Scientific CLI/router UID10000, caps/isolation/image defaults remain unchanged.
The original gateway-only diff keeps the SAME USER layer on both baselines.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_HOSTNAME = _count14_os.environ.get('COUNT14_HOSTNAME', 'count14-host')
from pathlib import Path
from types import FunctionType, MethodType
import hashlib
import json
import os
import shlex
import stat
import subprocess
import time

from agent_bridge_user_layer import proposed_layer

SMOKE = 'a009fcb9880fe694db540c6c9d8742d5e77ba1ce2314ee3b9018517f42f58e1e'
FORMAL = '9d279c1a1fb45737b675dc58800c6da154a93e793556f0f090ada7458700a391'
FORMAL_VALIDATOR_SHA = '8aed2cbcf62da6961b8d609a2c89ab961d9f72f7bca0a6b70da32e2d848b62e4'
LAYER_NAME = 'compose.native-management-bridge-user.private.json'
RETAINED = {}


def need(ok, code):
    if not ok: raise ValueError(code)


def scope(core):
    from common import digest
    c = core.contract
    need(c.get('mode') in ('smoke', 'production'), 'BRIDGE_USER_ONLY_ORIGINAL_TWO_ARM_SMOKE_OR_FORMAL')
    if not core.qualification_only:
        need(os.geteuid() == 0 and digest(c) == (SMOKE if c['mode']=='smoke' else FORMAL),
             'BRIDGE_USER_EXACT_USER_APPROVED_CONTRACT_NOT_ANOTHER_ROOT')
    else:
        need(os.uname().nodename != (_C14_HOSTNAME), 'BRIDGE_USER_NO_OWN_CONTRACT_ON_PRODUCTION')
    if c['mode'] == 'production':
        import formal_scope as F
        need(hashlib.sha256(Path(F.__file__).read_bytes()).hexdigest() == FORMAL_VALIDATOR_SHA,
             'BRIDGE_USER_ORIGINAL_FORMAL_FULL_SCOPE_VALIDATOR')
        fn = F.validate_contract
        if core.qualification_only:
            fn = FunctionType(fn.__code__, dict(fn.__globals__, PUBLIC_CONTRACT_CANONICAL_SHA256=digest(c)), fn.__name__)
        fn(c, digest(c))
    else:
        from smoke_checkpoint_final_scope import SmokeCheckpointFinalScope
        SmokeCheckpointFinalScope(c, contract_sha256=digest(c))
        need(len(c['trajectories']) == 2 and {r['arm'] for r in c['trajectories']} == {'DYNTEAM','DYNTEAM_RACING'} and
             all(r['block'] == 1 for r in c['trajectories']), 'BRIDGE_USER_ONLY_EXISTING_TWO_SMOKE_B1_ROOTS')


def held(core):
    from original_relay_core import OriginalRelayCore
    need(type(core) is OriginalRelayCore and not core.closed and not core.scientific_activation_qualified and
         set(core.gate.startup_held) == set(core.rows) and not core.ledger.mutex._is_owned(),
         'BRIDGE_USER_ONLY_NEW_SAME_TYPED_FULLY_HELD_GRAPH_NO_LOCKED_IO')
    scope(core)
    with core.ledger.mutex:
        for table in ('requests','unknown_charges','aux_scopes','aux_permits','snapshots','acks','unknown_stops'):
            need(core.ledger.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] == 0,
                 'BRIDGE_USER_NO_SCIENTIFIC_PREFIX_OR_FINANCIAL_REWRITE')
        need(core.ledger.db.execute('SELECT paused FROM model_control WHERE singleton=1').fetchone()[0] == 1 and not core.ledger.memory_faults, 'BRIDGE_USER_MODELS_HELD_NO_FAULT_CLEAR')
    return True


def identity(path):
    p = Path(path); s = p.lstat()
    need(p.resolve() == p and not p.is_symlink() and stat.S_ISREG(s.st_mode) and
         s.st_uid == os.geteuid() and stat.S_IMODE(s.st_mode) == 0o400 and s.st_nlink == 1,
         'BRIDGE_USER_LAYER_IMMUTABLE_PRIVATE_EXACT_REGULAR_FILE')
    return (s.st_dev,s.st_ino,s.st_uid,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def install(core, *, control_home):
    """New metadata leaf; apply all34/42 roles, no role is eagerly launched."""
    held(core)
    need(id(core) not in RETAINED and not core.native_containers.records and
         not core.native_containers.boot_plans and not core.peers._peers,
         'BRIDGE_USER_ONE_NEW_GRAPH_INSTALL_BEFORE_INITIAL_NATIVE_PEER_ADOPTION')
    home=Path(control_home)
    need(home.resolve()==home and home.is_dir() and home.is_relative_to(core.home) and
         home in (core.home,getattr(core,'pre_request_control_home',None)),
         'BRIDGE_USER_ONLY_NEW_GRAPH_REGISTERED_CONTROL_METADATA_HOME')
    leaf=home/'native-management-user-layers'
    need(not leaf.exists() and not leaf.is_symlink(), 'BRIDGE_USER_NEW_OUTPUT_ONLY_NO_REWRITE_OR_DELETE')
    record=dict(core=core,phase='PARTIAL_RETAINED_NO_RETRY',bindings={},failures=[])
    RETAINED[id(core)]=record
    try:
        leaf.mkdir(mode=0o700)
        from common import digest
        for t,row in core.rows.items():
            host=core.native_host_environment['trajectories'][t]
            need(type(host['compose']) is tuple and host['compose'].count('compose')==1 and
                 host['launcher_env']['COUNT14_NATIVE_COMPOSE_COMMAND']==shlex.join(host['compose']),
                 'BRIDGE_USER_BOTH_ORIGINAL_COMPOSE_CONSUMERS_EQUAL')
            before=host['compose']; path=leaf/(digest(t)+'.json')
            value=proposed_layer(contract=core.contract,row=row,roles=tuple(row['roles']))
            raw=(json.dumps(value,sort_keys=True)+'\n').encode()
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
            with os.fdopen(fd,'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
            after=(*before,'-f',str(path)); gateway=host.get('current240_gateway_overlay')
            if gateway is not None:
                need(gateway['selected_compose']==before and path.as_posix() not in gateway['original_compose'],
                     'BRIDGE_USER_GATEWAY_ORIGINAL_COMMAND_BASELINES_UNMODIFIED')
                gateway['original_compose']=(*gateway['original_compose'],'-f',str(path))
                gateway['selected_compose']=after
            host['compose']=after
            host['launcher_env']=dict(host['launcher_env'],COUNT14_NATIVE_COMPOSE_COMMAND=shlex.join(after))
            binding=dict(path=path,identity=identity(path),before=before,after=after,roles=tuple(row['roles']))
            host['native_bridge_user_layer']=binding;record['bindings'][t]=binding
        record['phase']='BOUND_FULL_ROSTER_NO_CONTAINER_ACTION'
        return record
    except BaseException as error:
        record['failures'].append(type(error).__name__);raise



def append_existing_cold_overlay(core, trajectory, path):
    """Compose one original approved cold layer into BOTH differential baselines.

    This is constructor/source wiring only, never a live owner repair. Original
    USER and gateway comparison functions/guards are unchanged and still run.
    """
    held(core)
    record=RETAINED.get(id(core));host=core.native_host_environment['trajectories'][trajectory]
    need(record is not None and record['core'] is core and record['phase']=='BOUND_FULL_ROSTER_NO_CONTAINER_ACTION',
         'BRIDGE_USER_COLD_LAYER_SAME_ORIGINAL_REGISTERED_GRAPH')
    b=record['bindings'][trajectory]
    need(host['native_bridge_user_layer'] is b and host['compose']==b['after'] and
         host['launcher_env']['COUNT14_NATIVE_COMPOSE_COMMAND']==shlex.join(b['after']) and
         identity(b['path'])==b['identity'], 'BRIDGE_USER_COLD_LAYER_FRESH_EXISTING_BOTH_CONSUMERS')
    path=Path(path)
    need(path.is_absolute()and path.resolve()==path and
         (path.is_relative_to(core.home)or path.is_relative_to(Path(core.rows[trajectory]['root'])))and
         path.name in {'compose.sdk-restore-cold.json','compose.tester-native-public-runner-ro.json',
                       'compose.racing-game-cold.json','compose.worker-racing-public-ro.json',
                       'compose.approved-helper-input-ro.json'},
         'BRIDGE_USER_ONLY_ORIGINAL_APPROVED_COLD_LAYER_PRODUCERS')
    layer_identity=identity(path)
    previous=b.get('cold_appended_layers',())
    need(all(identity(p)==i and p!=path for p,i in previous),
         'BRIDGE_USER_COLD_LAYERS_UNCHANGED_ONCE_ONLY')
    before,after=b['before'],b['after']
    def remove(command, layer):
        name=str(layer)
        need(type(command)is tuple and command.count(name)==1,'BRIDGE_USER_EXACT_ONE_DIFFERENTIAL_LAYER')
        at=command.index(name);need(at>0 and command[at-1]=='-f','BRIDGE_USER_EXACT_FILE_OPERAND_PAIR')
        return command[:at-1]+command[at+1:]
    def insert(command):
        need(type(command)is tuple and command.count('compose')==command.count('--project-name')==1 and
             str(path)not in command,'BRIDGE_USER_ORIGINAL_COLD_LAYER_INSERT_ONCE')
        at=command.index('--project-name');need(at>command.index('compose')and at+1<len(command),
             'BRIDGE_USER_ORIGINAL_COLD_LAYER_PROJECT_POSITION')
        return command[:at]+('-f',str(path))+command[at:]
    need(remove(after,b['path'])==before,'BRIDGE_USER_EXISTING_EXACT_USER_DIFFERENTIAL')
    new_before,new_after=insert(before),insert(after)
    need(remove(new_after,b['path'])==new_before and remove(new_before,path)==before and
         remove(new_after,path)==after,'BRIDGE_USER_COLD_LAYER_TWO_BASELINES_FULL_INVERSE')
    gateway=host.get('current240_gateway_overlay')
    if gateway is not None:
        need(gateway['selected_compose']==after and
             remove(after,gateway['path'])==gateway['original_compose'],
             'BRIDGE_USER_EXISTING_EXACT_GATEWAY_DIFFERENTIAL')
        new_original=insert(gateway['original_compose'])
        need(remove(new_after,gateway['path'])==new_original and
             remove(new_original,path)==gateway['original_compose'],
             'BRIDGE_USER_COLD_LAYER_GATEWAY_BASELINES_FULL_INVERSE')
        gateway['original_compose']=new_original;gateway['selected_compose']=new_after
    # Same original binding objects/file identities. No source/ledger/fee rewrite.
    b['before']=new_before;b['after']=new_after
    b['cold_appended_layers']=(*previous,(path,layer_identity))
    host['compose']=new_after
    host['launcher_env']['COUNT14_NATIVE_COMPOSE_COMMAND']=shlex.join(new_after)
    need(identity(path)==layer_identity and identity(b['path'])==b['identity'],
         'BRIDGE_USER_COLD_APPEND_FILE_IDENTITIES_UNCHANGED')
    return new_after


def verify_actual_compose(core, trajectory, *, fresh_guard):
    """Real normal Compose config, only agent.user differs; outputs RAM only."""
    held(core)
    need(callable(fresh_guard) and fresh_guard() is True, 'BRIDGE_USER_FULL_SERIAL_OR_NEWROOT_FRESH_GUARD')
    record=RETAINED.get(id(core));host=core.native_host_environment['trajectories'][trajectory]
    need(record is not None and record['core'] is core and record['phase']=='BOUND_FULL_ROSTER_NO_CONTAINER_ACTION',
         'BRIDGE_USER_SAME_REGISTERED_NEW_GRAPH_BINDING')
    b=record['bindings'][trajectory]
    need(host['native_bridge_user_layer'] is b and host['compose']==b['after'] and
         host['launcher_env']['COUNT14_NATIVE_COMPOSE_COMMAND']==shlex.join(b['after']) and
         identity(b['path'])==b['identity'], 'BRIDGE_USER_FRESH_BOTH_CONSUMERS_AND_LAYER_IDENTITY')
    outputs=[];docker=core.native_containers.docker
    for cmd in (b['before'],b['after']):
        need(tuple(cmd[:3])==tuple(docker.argv()), 'BRIDGE_USER_ORIGINAL_SCOPED_DOCKER_ROUTE_ONLY')
        r=subprocess.run([*cmd,'config','--format','json'],cwd=host['project_root'],
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(getattr(core,'pre_request_control_home',core.home))},
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=20)
        need(r.returncode==0 and 0<len(r.stdout)<=8*1024**2, 'BRIDGE_USER_REAL_CONFIG_MUST_SUCCEED_BEFORE_NATIVE_UP')
        v=json.loads(r.stdout)
        need(type(v)is dict and type(v.get('services'))is dict, 'BRIDGE_USER_REAL_CONFIG_FIXED_SHAPE')
        outputs.append(v)
    before,after=outputs
    from native_beta_layout import native_aliases
    aliases=native_aliases(core.rows[trajectory]['arm'])
    need(set(before)==set(after) and set(before['services'])==set(after['services']),
         'BRIDGE_USER_NO_SERVICE_OR_TOPLEVEL_CONFIGURATION_CHANGE')
    for role,alias in aliases.items():
        a=before['services'][alias['agent_service']];c=after['services'][alias['agent_service']]
        need(a.get('user') in (None,'agent') and c.pop('user',None)=='0:0',
             'BRIDGE_USER_ONLY_MANAGEMENT_BRIDGE_EXPLICIT_USER0')
        a.pop('user',None)
        for service in (a, before['services'][alias['router_service']],after['services'][alias['router_service']]):
            env=service.get('environment',{})
            if service is a:
                need(str(env.get('ACP_CHILD_UID'))==str(env.get('ACP_CHILD_GID'))=='10000',
                     'BRIDGE_USER_ORIGINAL_SCIENTIFIC_CLI_UID_GID10000_UNCHANGED')
        need(before['services'][alias['router_service']].get('user')==
             after['services'][alias['router_service']].get('user')=='10000:10000',
             'BRIDGE_USER_ORIGINAL_ROUTER_UID10000_UNCHANGED')
        need(a==c,'BRIDGE_USER_ANY_NON_USER_AGENT_FIELD_CHANGED')
    need(before==after and identity(b['path'])==b['identity'] and fresh_guard() is True,
         'BRIDGE_USER_ALL_OTHER_RUNTIME_NETWORK_SECURITY_CAPS_BYTES_UNCHANGED')
    del outputs,before,after,r,v
    return dict(schema='count14-native-management-user-config-differential-v1',trajectory=trajectory,
                native_roles=len(aliases),only_management_bridge_user_changed=True,
                CLI_and_router_UID10000_unchanged=True,expanded_config_exported_or_hashed=False,
                container_or_model_actions=0)


def bind_new_bootstrap(owner):
    """Wrap only this new object's original spawn; no shared method patch."""
    from native_cold_owner import NativeColdOwner
    need(type(owner)is NativeColdOwner and owner.bootstrap.core is owner.core and not owner.bootstrap.records,
         'BRIDGE_USER_ONLY_GENUINE_NEW_ORIGINAL_UNSTARTED_OWNER')
    core=owner.core;held(core);original=owner.bootstrap._spawn
    need(id(core)in RETAINED and not hasattr(owner.bootstrap,'_bridge_user_once'),
         'BRIDGE_USER_ONE_NEW_BOOTSTRAP_BINDING_AFTER_LAYER_INSTALL')
    actions={};owner.bootstrap._bridge_user_once=actions
    def spawn(bootstrap,raw,argv,env,*,cwd):
        need(bootstrap is owner.bootstrap and bootstrap.records.get(raw['trajectory'])is raw and
             raw['child'] is None and raw['failure_type'] is None,'BRIDGE_USER_SAME_ONCE_ORIGINAL_BOOTSTRAP_RECORD')
        key=(raw['trajectory'],raw['phase'])
        need(key not in actions,'BRIDGE_USER_NO_PARTIAL_CONFIG_OR_SPAWN_RETRY')
        actions[key]='CONFIG_ENTERED'
        try:
            verify_actual_compose(core,raw['trajectory'],fresh_guard=lambda:held(core))
            actions[key]='ORIGINAL_SPAWN_ENTERED'
            return original(raw,argv,env,cwd=cwd)
        except BaseException:
            actions[key]='PARTIAL_RETAINED_NO_RETRY';raise
    owner.bootstrap._spawn=MethodType(spawn,owner.bootstrap)
    return owner
