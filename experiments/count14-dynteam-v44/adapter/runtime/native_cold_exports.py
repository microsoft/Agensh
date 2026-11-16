"""Actual held-core -> private native Compose/role-route exports, no launch.

No model/backend/Docker/process/config action. Source files are copied from
reviewed cold exports; only PUBLIC route controls and fresh private role keys
are materialized. The owner's directory, financial DB and provider key are
NEVER mounted. A hardlink exports only its existing metadata socket inode.
"""
from pathlib import Path
import hashlib
import json
import os
import secrets
import stat
import re
from native_network_binding import NativeNetworkBinding

from common import need, digest
from native_beta_layout import native_aliases, render_native_base, guarded_native_overlay
from native_racing_phase_client import NativeRacingPhaseClient

BASE='70e2ca54c078597e3314755064d2ef1a83344c8e'


def _file(path,raw,mode,uid):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    try:
        with os.fdopen(fd,'wb',closefd=False) as out:out.write(raw);out.flush()
        os.fchmod(fd,mode)
        if os.geteuid()==0:os.fchown(fd,uid,uid)
        os.fsync(fd)
    finally:os.close(fd)


def _json(path,value,mode,uid):
    _file(path,(json.dumps(value,sort_keys=True,indent=2)+'\n').encode(),mode,uid)


def render_exact_native_gateway_override(aliases,binding,existing_hosts,*,contract,row,qualification_only):
    need(type(binding) is NativeNetworkBinding,'DYNTEAM_GATEWAY_OVERRIDE_TYPED_NETWORK')
    binding.checked(contract=contract,row=row,qualification_only=qualification_only)
    names=[a[k] for a in aliases.values() for k in ('agent_service','router_service')]
    need(len(names)==len(set(names)) and set(existing_hosts)==set(names),
         'DYNTEAM_GATEWAY_OVERRIDE_EXACT_ALL_NATIVE_SERVICES')
    lines=['services:']
    for name in sorted(names):
        need(type(name) is str and re.fullmatch(r'[A-Za-z0-9_.-]+',name),
             'DYNTEAM_GATEWAY_OVERRIDE_SAFE_SERVICE_NAME')
        hosts=existing_hosts[name]
        need(type(hosts) is dict and all(type(k) is str and re.fullmatch(r'[A-Za-z0-9_.-]+',k) and
             type(v) is str and v and '\n' not in v and '\r' not in v for k,v in hosts.items()),
             'DYNTEAM_GATEWAY_OVERRIDE_FULL_HOST_MAP_FIELDS')
        need(hosts.get('host.docker.internal') in ('host-gateway',binding.gateway),
             'DYNTEAM_GATEWAY_OVERRIDE_EXACT_ORIGINAL_ALIAS_NOT_FOREIGN')
        hosts=dict(hosts,**{'host.docker.internal':binding.gateway})
        lines.extend(['  '+name+':','    extra_hosts: !override'])
        lines.extend('      '+hostname+': '+json.dumps(address) for hostname,address in sorted(hosts.items()))
    return ('\n'.join(lines)+'\n').encode()



def _generated_native_existing_hosts(base,overlay,aliases):
    """Read only the original public generator's YAML; no dotenv/private files.

    Resolve original YAML anchors. Explicit duplicate keys/hostnames refuse.
    No private overlay is read from disk; the original compiler supplies its
    already-created in-memory object. An unexpected host override refuses
    instead of guessing Compose list/map merge rules or dropping other hosts.
    """
    import yaml
    class CheckedLoader(yaml.SafeLoader):
        def construct_mapping(self,node,deep=False):
            seen=set()
            for key,value in node.value:
                if key.tag=='tag:yaml.org,2002:merge':continue
                item=self.construct_object(key,deep=deep)
                need(type(item) in (str,int,float,bool,type(None)),
                     'DYNTEAM_GATEWAY_PUBLIC_YAML_SCALAR_KEYS')
                need(item not in seen,'DYNTEAM_GATEWAY_PUBLIC_YAML_NO_DUPLICATE_KEYS')
                seen.add(item)
            return super().construct_mapping(node,deep=deep)
    need(type(base) is str and type(overlay) is dict and type(overlay.get('services')) is dict,
         'DYNTEAM_GATEWAY_ORIGINAL_PUBLIC_BASE_AND_IN_MEMORY_OVERLAY')
    data=yaml.load(base,Loader=CheckedLoader)
    need(type(data) is dict and type(data.get('services')) is dict,
         'DYNTEAM_GATEWAY_ORIGINAL_PUBLIC_BASE_SERVICES')
    names=[a[k] for a in aliases.values() for k in ('agent_service','router_service')]
    need(len(names)==len(set(names)),'DYNTEAM_GATEWAY_UNIQUE_ALL_NATIVE_ALIASES')
    result={}
    for name in names:
        need(name in data['services'] and type(data['services'][name]) is dict and
             name in overlay['services'] and type(overlay['services'][name]) is dict and
             'extra_hosts' not in overlay['services'][name],
             'DYNTEAM_GATEWAY_ORIGINAL_BASE_HOSTS_NO_UNKNOWN_OVERLAY_MERGE')
        values=data['services'][name].get('extra_hosts')
        if type(values) is list:
            hosts={}
            for item in values:
                need(type(item) is str,'DYNTEAM_GATEWAY_HOST_LIST_STRING_ONLY')
                hostname,separator,address=item.partition('=' if '=' in item else ':')
                need(separator and hostname and address and hostname not in hosts,
                     'DYNTEAM_GATEWAY_HOST_LIST_NO_MISSING_OR_DUPLICATE_HOST')
                hosts[hostname]=address
        else:
            need(type(values) is dict,'DYNTEAM_GATEWAY_EXPLICIT_COMPLETE_HOST_MAP')
            hosts=dict(values)
        need('host.docker.internal' in hosts,'DYNTEAM_GATEWAY_ORIGINAL_ALIAS_REQUIRED')
        result[name]=hosts
    return result


def _checked_native_gateway_companion(core,t,export):
    """Pinned, public-only original producer -> same consumer, no fallback."""
    need(t in core.rows and t in core.native_networks and
         type(export) is dict and type(export.get('native_gateway_override')) is dict,
         'DYNTEAM_GATEWAY_EXACT_SAME_CORE_PRODUCER_REQUIRED')
    row=core.rows[t];binding=core.native_networks[t];desc=export['native_gateway_override']
    need(type(binding) is NativeNetworkBinding and
         set(desc)=={'path','sha256','existing_hosts','network_name','gateway'},
         'DYNTEAM_GATEWAY_EXACT_TYPED_DESCRIPTOR_FIELDS')
    binding.checked(contract=core.contract,row=row,qualification_only=core.qualification_only)
    destination=Path(export['directory']);path=Path(desc['path'])
    need(path==destination/'compose.native-gateway-override.yml' and
         path.is_absolute() and path.resolve()==path and not path.is_symlink() and
         destination==Path(row['root'])/'native-cold-exports' and
         desc['network_name']==binding.network_name and desc['gateway']==binding.gateway,
         'DYNTEAM_GATEWAY_CANONICAL_SAME_TRAJECTORY_NETWORK_COMPANION')
    s=path.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid() and s.st_nlink==1 and
         stat.S_IMODE(s.st_mode)==0o400 and type(desc['sha256']) is str and
         re.fullmatch('[0-9a-f]{64}',desc['sha256']),
         'DYNTEAM_GATEWAY_IMMUTABLE_OWN_PUBLIC_COMPANION')
    expected=render_exact_native_gateway_override(native_aliases(row['arm']),binding,
        desc['existing_hosts'],contract=core.contract,row=row,qualification_only=core.qualification_only)
    raw=path.read_bytes()
    need(raw==expected and hashlib.sha256(raw).hexdigest()==desc['sha256'],
         'DYNTEAM_GATEWAY_EXACT_FULL_HOSTS_BYTES_PIN')
    after=path.lstat()
    need((s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)==
         (after.st_dev,after.st_ino,after.st_mode,after.st_size,after.st_mtime_ns,after.st_ctime_ns,after.st_nlink),
         'DYNTEAM_GATEWAY_COMPANION_CHANGED_DURING_READ')
    return path


def build(core, *, guarded_agent_directory, compiled_router_directory, public_router_source,
          native_generator, native_generator_sha256, native_project_directory, native_uid):
    """Use existing SAME core/control/clock objects, startup gates stay held.

    This is the real config compiler, not a complete owner/activation entry.
    Real Docker peer/SDK/cgroup/checkpoint/K3 qualification is still required.
    Any failure leaves the partial new exports intact; never delete/retry them.
    """
    need(core.state=='ORIGINAL_TRANSPORT_HELD_NATIVE_BINDINGS_PENDING' and not core.errors and
         core.control is not None and set(core.gate.startup_held)==set(core.rows) and
         not hasattr(core,'cold_native_exports') and
         type(native_uid) is int and (native_uid==os.geteuid() if core.qualification_only else
                                     native_uid==10000 and os.geteuid()==0),
         'DYNTEAM_COLD_NATIVE_EXPORTS_EXACT_HELD_ORIGINAL_CORE')
    with core.ledger.mutex:
        need(core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0,
             'DYNTEAM_COLD_EXPORTS_BEFORE_ANY_REAL_MODEL_REQUEST')
    project=Path(native_project_directory)
    need(project.is_absolute() and project.resolve()==project and project.is_dir() and project.name=='docker',
         'DYNTEAM_ORIGINAL_COMPOSE_PROJECT_DIRECTORY_PRESERVES_RELATIVE_SOURCE_BINDS')
    socket_path=core.control.path;sock=socket_path.lstat()
    need(stat.S_ISSOCK(sock.st_mode) and sock.st_uid==native_uid and stat.S_IMODE(sock.st_mode)==0o600,
         'DYNTEAM_NATIVE_CONTROL_SOCKET_MUST_BE_ACCESSIBLE_TO_ORIGINAL_UID')
    root=core.home/'cold-native-exports';root.mkdir(mode=0o700)
    core.cold_native_exports=dict(state='PARTIAL_RETAINED',root=str(root),trajectories={})
    code=root/'router-public-source';code.mkdir(mode=0o755)
    for name in ('router-entry.mjs','router-session-hook.mjs','native-racing-phase-port.mjs','native-racing-phase-entry.mjs'):
        source=Path(public_router_source)/name
        need(source.is_file() and not source.is_symlink(),'DYNTEAM_FROZEN_COLD_ROUTER_SOURCE_ONLY')
        _file(code/name,source.read_bytes(),0o444,os.geteuid())
    dist=Path(compiled_router_directory)
    pins={n:hashlib.sha256((dist/n).read_bytes()).hexdigest() for n in ('main.js','acp_socket_channel.js')}
    for t,row in core.rows.items():
        destination=Path(row['root'])/'native-cold-exports'
        need(destination.is_absolute() and destination.parent.resolve()==destination.parent,
             'DYNTEAM_NEW_TRAJECTORY_EXPORT_EXACT_CANONICAL_PARENT')
        destination.mkdir(mode=0o700)
        launcher=destination/'native-launcher-control';launcher.mkdir(mode=0o700)
        os.link(socket_path,launcher/'native-control.sock',follow_symlinks=False)
        launcher_route=launcher/'route.json'
        _json(launcher_route,dict(schema='count14-native-spawn-client-route-v1',source_commit=BASE,
            trajectory_id=t,control_socket=str(launcher/'native-control.sock')),0o400,os.geteuid())
        aliases=native_aliases(row['arm'])
        base,actual=render_native_base(native_generator,source_sha256=native_generator_sha256,arm=row['arm'])
        need(actual==aliases and set(aliases)==set(row['roles']),'DYNTEAM_FROZEN_ALL_CHARGED_ROLE_EXPORTS')
        role_exports,relays,phase_routes={},{},{}
        for role,alias in aliases.items():
            ad=destination/'native-agent-control-exports'/role
            rd=destination/'native-private-exports'/role
            ad.mkdir(parents=True,mode=0o755);rd.mkdir(parents=True,mode=0o700)
            if os.geteuid()==0:os.chown(rd,native_uid,native_uid)
            for directory in (ad,rd):
                os.link(socket_path,directory/'native-control.sock',follow_symlinks=False)
                linked=(directory/'native-control.sock').lstat()
                need((linked.st_dev,linked.st_ino)==(sock.st_dev,sock.st_ino),
                     'DYNTEAM_ONLY_EXISTING_METADATA_SOCKET_INODE_EXPORTED')
            route=dict(schema='count14-dynteam-router-cold-route-v1',source_commit=BASE,
                mode='own-zero' if core.qualification_only else core.contract['mode'],
                trajectory_id=t,block=row['block'],role_slot=role,metadata_timeout_ms=2000,
                control_socket='/run/count14-dynteam/native-control.sock',
                native_router_dist='/app/dist',native_module_pins=pins,
                native_acp_socket='/var/run/acp/agent.sock')
            _json(ad/'route.json',route,0o444,os.geteuid())
            if alias['kind'] in ('racing_background','racing_player'):
                route.update(native_agent_socket='/run/acp/agent.sock',
                    native_acp_socket='/run/count14-dynteam/proxy.sock',
                    native_turn_metadata='/run/acp/current-turn.json',
                    private_phase_schema='count14-private-native-racing-phase-v1',
                    private_phase_socket='/run/count14-dynteam/scientific.sock',
                    private_phase_secret='/run/count14-dynteam/phase.secret')
                # This alias is resolved INSIDE the router's original readonly
                # ACP mount. Do not follow/read any host scientific metadata.
                (rd/'current-turn.json').symlink_to('/var/run/acp/current-turn.json')
                _file(rd/'phase.secret',secrets.token_urlsafe(48).encode(),0o600,native_uid)
                phase_routes[role]=dict(socket=str(rd/'scientific.sock'),secret=str(rd/'phase.secret'))
            _json(rd/'route.json',route,0o444,native_uid)
            metadata=core.clocks[t].metadata(role)
            role_exports[role]=dict(agent_control_directory=str(ad),router_control_directory=str(rd),
                clock_directory=str(core.clocks[t].directory),clock_binding_sha256=metadata['binding_sha256'],
                clock_owner_uid=core.clocks[t].directory.stat().st_uid)
            bearer=[token for token,identity in core.tokens[t].items() if identity==(t,role)]
            need(len(bearer)==1,'DYNTEAM_EXACT_EXISTING_ORIGINAL_ROLE_RELAY_BEARER')
            host,port=core.servers[t].server_address
            relays[role]=dict(COPILOT_PROVIDER_BASE_URL=f'http://{host}:{port}/v1',
                COPILOT_PROVIDER_API_KEY=bearer[0],COPILOT_MODEL=core.profile.policy['model'])
        # Serialize only with the ephemeral public publisher, never with the
        # science/ledger mutex. Its atomic .partial may disappear mid-render.
        with core.clocks[t].lock:
            overlay=guarded_native_overlay(aliases,guarded_agent_directory=guarded_agent_directory,
                compiled_router_directory=dist,role_exports=role_exports,
                frozen_public_code_directory=code,role_relay_configuration=relays)
        if t in core.native_networks:
            overlay['networks']={'default':{'external':True,'name':core.native_networks[t].network_name}}
        from native_docker_scope import scope_labels
        for role,alias in aliases.items():
            for component,key in (('agent','agent_service'),('router','router_service')):
                overlay['services'][alias[key]].setdefault('labels',{}).update(
                    scope_labels(core.contract,row,role,component))
            if hasattr(core,'native_layout'):
                layout=core.native_layout.current(t)
                service=overlay['services'][alias['agent_service']]
                service.setdefault('volumes',[]).append({'type':'bind',
                    'source':layout['roles'][role]['workspace'],'target':'/work','read_only':False})
            else:
                need(core.qualification_only,'DYNTEAM_PRODUCTION_WORKSPACE_MUST_BE_A_REAL_NEW_ROOT_BIND')
        need(t in core.native_networks and type(core.native_networks[t]) is NativeNetworkBinding,
             'DYNTEAM_GATEWAY_ALL_NATIVE_ROLES_REQUIRE_EXACT_REGISTERED_NETWORK')
        binding=core.native_networks[t]
        existing_hosts=_generated_native_existing_hosts(base,overlay,aliases)
        gateway_raw=render_exact_native_gateway_override(aliases,binding,existing_hosts,
            contract=core.contract,row=row,qualification_only=core.qualification_only)
        gateway_path=destination/'compose.native-gateway-override.yml'
        _file(gateway_path,gateway_raw,0o400,os.geteuid())
        gateway_descriptor=dict(path=str(gateway_path),sha256=hashlib.sha256(gateway_raw).hexdigest(),
            existing_hosts=existing_hosts,network_name=binding.network_name,gateway=binding.gateway)
        _file(destination/'compose.native-base.yml',base.encode(),0o400,os.geteuid())
        _json(destination/'compose.private-overlay.json',overlay,0o400,os.geteuid())
        core.cold_native_exports['trajectories'][t]=dict(directory=str(destination),native_roles=len(aliases),
            launcher_route=str(launcher_route),launcher_route_sha256=hashlib.sha256(launcher_route.read_bytes()).hexdigest(),
            project_directory=str(project),native_gateway_override=gateway_descriptor,phase_routes=phase_routes,role_exports=role_exports,
            phase_client=NativeRacingPhaseClient(routes=phase_routes,native_secret_owner_uid=native_uid) if phase_routes else None)
    core.cold_native_exports['state']='EXPORTED_HELD_NOT_DOCKER_OR_SCIENTIFIC_PREPARED'
    return core.cold_native_exports
