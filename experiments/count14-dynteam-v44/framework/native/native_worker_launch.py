"""Narrow native worker startup replacement spec, not Compose deployment.

Owner/OPS must REPLACE original worker entrypoint/user/environment/volume fields;
Compose list-merging would leave native backend token mounts, and is forbidden.
Original CLI/ACP/router/services/prompts remain. Gate4 stop is not retried here.
"""
from pathlib import Path
import os,shlex
from common import need,ident,integer,digest,publish,private_dir,hash_file,regular_fd,sync_dir
from native_team_owner import actor_map
from native_mcp_overlay import PUBLIC,BASE

HOLD_SCRIPT='''#!/bin/bash
set -euo pipefail
: "${AGENT_NAME:?native actor required}"
: "${COUNT14_GIT_FRONT_PORT:?exact owner port required}"
[ "$(id -u)" = "10000" ] || { echo COUNT14_WORKER_UID_REFUSED >&2; exit 1; }
[ "${MATTERMOST_HOST:-}" = "" ] || { echo COUNT14_BACKEND_ENDPOINT_REFUSED >&2; exit 1; }
case "${COUNT14_LATE_DELIVERY:-0}" in
 0) transport=/run/count14 ;;
 1) transport=/run/count14/transport
    # The pre-existing dedicated directory is already mounted read-only. Only
    # host publishes PORTS_READY, after reading this held worker's real identity
    # and priming every role/backend. No absent socket path is bind-mounted.
    while [ ! -f /run/count14/release/PORTS_READY ]; do sleep .1; done
    [ "$(cat /run/count14/release/PORTS_READY)" = "$AGENT_NAME" ] || exit 1
    for endpoint in gitea mattermost board git; do [ -S "$transport/$endpoint.sock" ] || exit 1; done
    for item in mcp.json.tmpl copilot-deny-tools.json placeholder.token git.capability; do [ -r "$transport/$item" ] || exit 1; done
    ;;
 *) echo COUNT14_TRANSPORT_MODE_REFUSED >&2; exit 1 ;;
esac
[ "${GITEA_TOKEN_FILE:-}" = "$transport/placeholder.token" ] || exit 1
[ "${GITEA_HOST:-}" = "http://127.0.0.1:${COUNT14_GIT_FRONT_PORT}" ] || exit 1
[ "${BOARD_SERVICE_URL:-}" = count14-fixed-uds ] || exit 1
umask 077
mkdir -p /opt/data/git-front-private
/usr/bin/python3 -B /opt/count14/git_http_uds_front.py \\
 --socket "$transport/git.sock" --capability-file "$transport/git.capability" \\
 --private-home /opt/data/git-front-private --organization "$ORG_NAME" \\
 --repository "$COUNT14_REPOSITORY" --port "$COUNT14_GIT_FRONT_PORT" &
front_pid=$!
# Only OPS owns/writes this directory; worker sees a read-only mount. A file
# alone is NOT readiness: OPS verifies exact host PID/start/netns/owned listener,
# installs narrow fence and probes it before publishing this release.
while [ ! -f /run/count14/release/ALLOW_CLI ]; do
 kill -0 "$front_pid" 2>/dev/null || { echo COUNT14_GIT_FRONT_EXITED_NO_RESTART >&2; exit 1; }
 sleep .1
done
[ "$(cat /run/count14/release/ALLOW_CLI)" = "$AGENT_NAME" ] || { echo COUNT14_WRONG_RELEASE_ACTOR >&2; exit 1; }
kill -0 "$front_pid" 2>/dev/null || exit 1
exec /opt/omcgitea/entrypoint.sh
'''

# Fixed module-load closure for BOTH worker entrypoints. Control custody is
# imported by native_git_http and native_mcp_bridge even though ownership stays
# host-side; omitting its public declarations prevents either worker front from
# importing. No host state, authority or additional executable is exposed.
WORKER_CODE=('common.py','bridge.py','native_control_custody.py','native_git_http.py','git_http_uds_front.py','native_mcp_policy.py','native_mcp_bridge.py','mcp_uds_client.py')
def _publish_public_code(path,raw):
 # This exact public closure is finalized while its directory is still 0700.
 # publish's mode is filtered by the caller's umask; do NOT change that global
 # private-file contract or the process-wide umask in this threaded owner.
 publish(path,raw,mode=0o444)
 with regular_fd(path) as fd:
  st=os.fstat(fd);need(st.st_uid==os.geteuid()and st.st_nlink==1,'WORKER_CODE_OWNED_SINGLE_FILE')
  os.fchmod(fd,0o444);os.fsync(fd)
 need((Path(path).stat().st_mode&0o7777)==0o444,'WORKER_CODE_EXACT_PUBLIC_MODE')

def install_worker_code(destination):
 """Copy fixed public transport closure only; never owner state/token roots.
 Caller bind-mounts this directory read-only at /opt/count14.
 """
 d=private_dir(destination,create=True);need(not any(d.iterdir()),'WORKER_CODE_NEW_ROOT');pins={}
 for name in WORKER_CODE:
  source=BASE/name;pin=hash_file(source);_publish_public_code(d/name,source.read_bytes());need(hash_file(source)==pin==hash_file(d/name),'WORKER_CODE_CHANGED_DURING_COPY');pins[name]=pin
 # Directory is public code, NOT capabilities/credentials. Host parent stays
 # private and the exact directory is a read-only individual worker bind.
 _publish_public_code(d/'worker_hold.sh',HOLD_SCRIPT.encode());pins['worker_hold.sh']=hash_file(d/'worker_hold.sh')
 d.chmod(0o555);sync_dir(d)
 return {'files':pins,'target':'/opt/count14','read_only':True,'service_credentials_or_owner_state':False}

def worker_replacement(owner,role,*,organization,repository,port,workspace,home,acp,release_dir,original_entrypoint,worker_code):
 """Return replacement fields only. Caller keeps actual native image/network,
 original cooperation/count14 prompts, original ACP/CLI and native deny rules.
 Worker code closure is an exact reviewed directory, never the development root.
 No original backend token/password/docker/control sockets may remain mounted.
 """
 need(role in owner.roles and owner.actors==actor_map(owner.roles,organization),'WORKER_NATIVE_ROLE');ident(repository);integer(port,'WORKER_FRONT_PORT',1);need(port<=65535,'WORKER_FRONT_PORT')
 c=owner.configs[role];need(c['home'].is_dir()and len(owner.listeners)==4*len(owner.roles),'WORKER_OWNER_NOT_READY')
 paths={}
 for name,value in(('workspace',workspace),('home',home),('acp',acp),('release',release_dir)):
  p=Path(value);need(p.is_absolute()and p.resolve()==p and p.is_dir()and not p.is_symlink(),'WORKER_EXACT_MOUNT_PATH');paths[name]=p
 need(len(set(paths.values()))==4 and all(a not in b.parents for a in paths.values()for b in paths.values()if a!=b),'WORKER_PRIVATE_MOUNTS_DISTINCT')
 need(paths['workspace']==Path(owner.gb['workspace_roots'][role]['path']),'WORKER_WORKSPACE_BINDING')
 release=paths['release'].stat();need(release.st_uid==os.geteuid()and release.st_uid!=10000 and (release.st_mode&0o777)==0o711 and not(paths['release']/'ALLOW_CLI').exists(),'WORKER_RELEASE_OWNER_OR_STALE')
 for n in('workspace','home','acp'):need(paths[n].stat().st_uid==10000,'WORKER_WRITABLE_MOUNT_UID')
 # Native entrypoint is original byte-pinned public input. No alternate shell or
 # rendered task description can be smuggled through this startup spec.
 from common import hash_file,strict
 pins={r['path']:r['sha256']for r in strict((BASE/'NATIVE_PUBLIC105_CONSUMED.json').read_bytes())['sources']};entry=Path(original_entrypoint);need(hash_file(entry)['sha256']==pins['agent/entrypoint.sh'],'WORKER_NATIVE_ENTRYPOINT_PIN')
 code=Path(worker_code);need(code.is_absolute()and code.resolve()==code and code.is_dir()and set(p.name for p in code.iterdir())==set(WORKER_CODE)|{'worker_hold.sh'},'WORKER_CODE_EXACT_PUBLIC_CLOSURE')
 for name in WORKER_CODE:need(hash_file(code/name)==hash_file(BASE/name),'WORKER_CODE_TRANSPORT_PIN')
 need((code/'worker_hold.sh').read_bytes()==HOLD_SCRIPT.encode(),'WORKER_CODE_HOLD_PIN')
 mounts=[{'source':str(paths['workspace']),'target':'/work','read_only':False},{'source':str(paths['home']),'target':'/opt/data','read_only':False},{'source':str(paths['acp']),'target':'/var/run/acp','read_only':False},{'source':str(paths['release']),'target':'/run/count14/release','read_only':True},{'source':str(entry),'target':'/opt/omcgitea/entrypoint.sh','read_only':True},{'source':str(code),'target':'/opt/count14','read_only':True}]
 for purpose in('gitea','mattermost','board'):mounts.append({'source':str(c['sockets'][purpose]),'target':'/run/count14/'+purpose+'.sock','read_only':True})
 for source,target in(('mcp.json.tmpl','/opt/omcgitea/config/mcp.json.tmpl'),('copilot-deny-tools.json','/opt/omcgitea/config/copilot-deny-tools.json'),('placeholder.token','/run/count14/placeholder.token'),('git.capability','/run/count14/git.capability')):mounts.append({'source':str(c['home']/source),'target':target,'read_only':True})
 mounts.append({'source':str(c['git_path']),'target':'/run/count14/git.sock','read_only':True})
 spec={'user':'10000:10000','entrypoint':['/bin/bash','/opt/count14/worker_hold.sh'],'environment':{'AGENT_NAME':owner.actors[role],'ORG_NAME':organization,'COUNT14_REPOSITORY':repository,'COUNT14_GIT_FRONT_PORT':str(port),'GITEA_HOST':f'http://127.0.0.1:{port}','GITEA_TOKEN_FILE':'/run/count14/placeholder.token','MATTERMOST_HOST':'','BOARD_SERVICE_URL':'count14-fixed-uds'},'mounts':mounts}
 receipt={'role':role,'native_actor':owner.actors[role],'replacement_sha256':digest(spec),'hold_script_sha256':digest(HOLD_SCRIPT),'backend_credentials':False,'worker_released':False,'remaining_required_mounts':'original cooperation/task prompts and ACP/CLI components from native image/source; no backend credentials','merge_semantics':'REPLACE original worker volume list and credential environment, never append/Compose merge'}
 return spec,receipt


def worker_waiting_replacement(roles,role,*,organization,repository,port,delivery_root,workspace,home,acp,release_dir,original_entrypoint,worker_code):
 """Render initial hold before worker PID/ns is available, NOT native readiness.

 Only a pre-existing empty dedicated delivery directory is mounted. Owner later
 publishes its exact role-only artifacts into that same inode. Both phase flags
 stay host-owned; no namespace restart/remount or nonexistent file mounts.
 """
 from native_delivery import delivery_dir
 actors=actor_map(roles,organization);need(role in actors,'WORKER_NATIVE_ROLE');ident(repository);integer(port,'WORKER_FRONT_PORT',1);need(port<=65535,'WORKER_FRONT_PORT')
 delivery=delivery_dir(delivery_root);need(not any(delivery.iterdir()),'WORKER_DELIVERY_MUST_START_EMPTY')
 paths={}
 for name,value in(('workspace',workspace),('home',home),('acp',acp),('release',release_dir)):
  p=Path(value);need(p.is_absolute()and p.resolve()==p and p.is_dir()and not p.is_symlink(),'WORKER_EXACT_MOUNT_PATH');paths[name]=p
 values=list(paths.values())+[delivery];need(len(set(values))==len(values)and all(a not in b.parents for a in values for b in values if a!=b),'WORKER_PRIVATE_MOUNTS_DISTINCT')
 release=paths['release'].stat();need(release.st_uid==os.geteuid()and release.st_uid!=10000 and (release.st_mode&0o777)==0o711 and not any(paths['release'].iterdir()),'WORKER_RELEASE_OWNER_OR_STALE')
 for name in('workspace','home','acp'):need(paths[name].stat().st_uid==10000,'WORKER_WRITABLE_MOUNT_UID')
 from common import strict
 pins={r['path']:r['sha256']for r in strict((BASE/'NATIVE_PUBLIC105_CONSUMED.json').read_bytes())['sources']};entry=Path(original_entrypoint);need(hash_file(entry)['sha256']==pins['agent/entrypoint.sh'],'WORKER_NATIVE_ENTRYPOINT_PIN')
 code=Path(worker_code);need(code.is_absolute()and code.resolve()==code and code.is_dir()and set(p.name for p in code.iterdir())==set(WORKER_CODE)|{'worker_hold.sh'},'WORKER_CODE_EXACT_PUBLIC_CLOSURE')
 for name in WORKER_CODE:need(hash_file(code/name)==hash_file(BASE/name),'WORKER_CODE_TRANSPORT_PIN')
 need((code/'worker_hold.sh').read_bytes()==HOLD_SCRIPT.encode(),'WORKER_CODE_HOLD_PIN')
 mounts=[{'source':str(paths['workspace']),'target':'/work','read_only':False},{'source':str(paths['home']),'target':'/opt/data','read_only':False},{'source':str(paths['acp']),'target':'/var/run/acp','read_only':False},{'source':str(paths['release']),'target':'/run/count14/release','read_only':True},{'source':str(entry),'target':'/opt/omcgitea/entrypoint.sh','read_only':True},{'source':str(code),'target':'/opt/count14','read_only':True},{'source':str(delivery),'target':'/run/count14/transport','read_only':True},{'source':str(delivery),'target':'/opt/omcgitea/config','read_only':True}]
 spec={'user':'10000:10000','entrypoint':['/bin/bash','/opt/count14/worker_hold.sh'],'environment':{'AGENT_NAME':actors[role],'ORG_NAME':organization,'COUNT14_REPOSITORY':repository,'COUNT14_GIT_FRONT_PORT':str(port),'COUNT14_LATE_DELIVERY':'1','GITEA_HOST':f'http://127.0.0.1:{port}','GITEA_TOKEN_FILE':'/run/count14/transport/placeholder.token','MATTERMOST_HOST':'','BOARD_SERVICE_URL':'count14-fixed-uds'},'mounts':mounts}
 receipt={'role':role,'native_actor':actors[role],'replacement_sha256':digest(spec),'stage':'WAITING_REAL_PEER_IDENTITY_NO_NATIVE_PORTS','native_ready':False,'worker_released':False,'backend_credentials':False,'same_delivery_device':delivery.stat().st_dev,'same_delivery_inode':delivery.stat().st_ino,'merge_semantics':'REPLACE original volume list and credential environment; retain only separately reviewed native relay/ACP/router/prompts','after_worker_start':'postflight -> read actual held PID/start/uid/pidns/netns -> NativeTeamOwner(...,delivery_roots=...) -> all prime+listen -> host PORTS_READY -> exact front/fence proof -> host ALLOW_CLI'}
 return spec,receipt
