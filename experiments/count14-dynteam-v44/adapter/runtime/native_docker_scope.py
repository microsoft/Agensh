"""Fixed PUBLIC Docker control projections and exact private-daemon route.

No Env, Args, log/error body, candidate, HOME or session is requested/decoded.
Only info identity and selected container control fields are projected by the
original Docker CLI. Mutation subprocesses are retained; NEVER timeout-killed.
"""
import os as _count14_os  # endpoints/keys/host paths come from environment; see CONFIGURATION.md
_C14_SCRATCH1 = _count14_os.environ.get('COUNT14_SCRATCH1_ROOT', '/srv/count14/scratch1')
_C14_SCRATCH = _count14_os.environ.get('COUNT14_SCRATCH_ROOT', '/srv/count14/scratch2')
from dataclasses import dataclass
from pathlib import Path
import hashlib
import http.client
import json
import os
import socket
import stat
import subprocess

from common import need,digest

INFO='{"daemon_id":{{json .ID}},"data_root":{{json .DockerRootDir}}}'
INSPECT='''{"id":{{json .Id}},"image":{{json .Image}},"pid":{{json .State.Pid}},"running":{{json .State.Running}},"paused":{{json .State.Paused}},"restarting":{{json .State.Restarting}},"dead":{{json .State.Dead}},"exit_code":{{json .State.ExitCode}},"stop_signal":{{if eq (printf "%T" (index .Config "StopSignal")) "<nil>"}}""{{else}}{{json (index .Config "StopSignal")}}{{end}},"restart_policy":{{json .HostConfig.RestartPolicy.Name}},"labels":{"root":{{json (index .Config.Labels "count14.root")}},"trajectory":{{json (index .Config.Labels "count14.trajectory-sha256")}},"contract":{{json (index .Config.Labels "count14.contract-sha256")}},"role":{{json (index .Config.Labels "count14.role")}},"component":{{json (index .Config.Labels "count14.component")}}},"mounts":{{json .Mounts}}}'''


def sha64(value):return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def scope_labels(contract,row,role,component):
    need(role in row['roles'] and component in ('agent','router'),'DYNTEAM_NATIVE_CONTAINER_REGISTERED_COMPONENT')
    return {'count14.root':row['root'],'count14.trajectory-sha256':digest(row['trajectory_id']),
        'count14.contract-sha256':digest(contract),'count14.role':role,'count14.component':component}


@dataclass(frozen=True)
class DockerRoute:
    cli:Path
    cli_sha256:str
    socket_path:Path
    daemon_id:str
    data_root:Path
    qualification_only:bool=False


class _Unix(http.client.HTTPConnection):
    def __init__(self,path):super().__init__('localhost',timeout=2.5);self.path=Path(path)
    def connect(self):
        fd=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(2.5)
            self.sock.connect('/proc/self/fd/'+str(fd)+'/'+self.path.name)
        finally:os.close(fd)


class ScopedDocker:
    def __init__(self,route):
        need(type(route) is DockerRoute and type(route.qualification_only) is bool,'DYNTEAM_TYPED_NATIVE_DOCKER_ROUTE')
        self.route=route;self._socket_identity=None
        self.verify_files()
        self.verify_daemon()

    def verify_files(self):
        r=self.route
        need(all(type(p) is Path or isinstance(p,Path) for p in (r.cli,r.socket_path,r.data_root)) and
             all(p.is_absolute() and p.resolve()==p and not p.is_symlink() for p in (r.cli,r.socket_path,r.data_root)),
             'DYNTEAM_NATIVE_DOCKER_CANONICAL_ADMITTED_PATHS')
        need(r.data_root.is_dir() and sha64(r.cli_sha256) and type(r.daemon_id) is str and 0<len(r.daemon_id)<=128,
             'DYNTEAM_NATIVE_DOCKER_PUBLIC_ID_PINS')
        if r.qualification_only:
            need(all(any(x.startswith('OWN-') for x in p.parts) for p in (r.cli,r.socket_path,r.data_root)),
                 'DYNTEAM_OWN_DOCKER_FIXTURES_ONLY')
        else:
            need(os.geteuid()==0 and all(p.is_relative_to((_C14_SCRATCH)) or p.is_relative_to((_C14_SCRATCH1))
                 for p in (r.socket_path,r.data_root)), 'DYNTEAM_NATIVE_PRIVATE_DOCKER_NEVER_SYSTEM_ROOT')
        cli,sock=r.cli.stat(),r.socket_path.stat()
        need(stat.S_ISREG(cli.st_mode) and cli.st_mode&0o111 and not cli.st_mode&0o022 and
             cli.st_uid in (0,os.geteuid()) and stat.S_ISSOCK(sock.st_mode) and sock.st_uid in (0,os.geteuid()),
             'DYNTEAM_NATIVE_DOCKER_BINARY_SOCKET_OWNER_MODE')
        need(hashlib.sha256(r.cli.read_bytes()).hexdigest()==r.cli_sha256,'DYNTEAM_NATIVE_DOCKER_CLI_SHA')
        identity=sock.st_dev,sock.st_ino
        need(self._socket_identity in (None,identity),'DYNTEAM_NATIVE_DAEMON_SOCKET_INODE_CHANGED')
        self._socket_identity=identity

    def argv(self,*args):
        return [str(self.route.cli),'--host','unix://'+str(self.route.socket_path),*args]

    def _project(self,*args):
        self.verify_files()
        result=subprocess.run(self.argv(*args),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},cwd='/',timeout=2.5)
        need(result.returncode==0 and 0<len(result.stdout)<=2**20,'DYNTEAM_NATIVE_DOCKER_PUBLIC_PROJECTION_FAILED')
        return json.loads(result.stdout)

    def verify_daemon(self):
        row=self._project('info','--format',INFO)
        need(type(row) is dict and set(row)=={'daemon_id','data_root'} and
             row['daemon_id']==self.route.daemon_id and row['data_root']==str(self.route.data_root),
             'DYNTEAM_NATIVE_DOCKER_DAEMON_ID_DATA_ROOT_CHANGED')

    def inspect(self,cid):
        need(sha64(cid),'DYNTEAM_FULL_NATIVE_CONTAINER_ID_REQUIRED')
        self.verify_daemon()
        row=self._project('inspect','--type','container','--format',INSPECT,cid)
        need(type(row) is dict and set(row)=={'id','image','pid','running','paused','restarting','dead','exit_code',
             'stop_signal','restart_policy','labels','mounts'} and row['id']==cid and
             all(type(row[k]) is bool for k in ('running','paused','restarting','dead')) and
             type(row['pid']) is int and row['pid']>=0 and type(row['exit_code']) is int and
             type(row['labels']) is dict and type(row['mounts']) is list,
             'DYNTEAM_FIXED_NATIVE_CONTAINER_CONTROL_PROJECTION')
        return row

    def list_scope_ids(self,labels):
        need(type(labels) is dict and set(labels)=={'count14.root','count14.trajectory-sha256',
             'count14.contract-sha256','count14.role','count14.component'} and
             all(type(v) is str and v and '\n' not in v and '\r' not in v for v in labels.values()),
             'DYNTEAM_FIXED_NATIVE_CONTAINER_SCOPE_FILTERS_ONLY')
        self.verify_daemon()
        args=['ps','-aq','--no-trunc']
        for key,value in sorted(labels.items()):args+=['--filter','label='+key+'='+value]
        result=subprocess.run(self.argv(*args),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},cwd='/',timeout=2.5)
        need(result.returncode==0 and len(result.stdout)<=4096,'DYNTEAM_NATIVE_SCOPE_ID_PROJECTION_FAILED')
        ids=result.stdout.decode('ascii').splitlines()
        need(all(sha64(cid) for cid in ids) and len(ids)==len(set(ids)),
             'DYNTEAM_NATIVE_FULL_UNIQUE_SCOPE_CIDS_REQUIRED')
        return ids

    def exists(self,cid):
        # Inspect existence by HTTP STATUS ONLY. Do NOT read/decode response
        # body (it could contain Env), including when a daemon reports errors.
        need(sha64(cid),'DYNTEAM_FULL_NATIVE_CONTAINER_ID_REQUIRED');self.verify_daemon()
        connection=_Unix(self.route.socket_path)
        try:
            connection.request('GET','/containers/'+cid+'/json')
            response=connection.getresponse();code=response.status
            need(code in (200,404),'DYNTEAM_NATIVE_CONTAINER_EXISTENCE_STATUS_UNKNOWN')
            return code==200
        finally:connection.close()

    def mutate_once(self,kind,cid):
        need(sha64(cid) and kind in ('DISABLE_RESTART','NORMAL_STOP','REMOVE_STOPPED'),
             'DYNTEAM_NATIVE_CONTAINER_FIXED_ACTION_ONLY')
        self.verify_daemon()
        args={'DISABLE_RESTART':('update','--restart=no',cid),
              'NORMAL_STOP':('stop','-t','-1',cid),'REMOVE_STOPPED':('rm',cid)}[kind]
        # Owner keeps this exact Popen. No communicate/run timeout, cancel,
        # signal, rm-f, prune, image/volume deletion or shared config mutation.
        return subprocess.Popen(self.argv(*args),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},cwd='/')
