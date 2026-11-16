"""Same-owner NEW native filesystem layout before control/export/environment.

No scientific files are opened/hashed/copied. Only freshly created exact own
directories receive modes/owners; no recursive operation or existing-dir repair.
Public inode proof prevents broadening environment setup to arbitrary old data.
"""
from pathlib import Path
import json
import os
import stat

from common import need,digest
from native_peer_registry import process_birth
from native_beta_layout import native_aliases


def native_names(trajectory):
    return ('pbench-single-node-count14-'+digest(trajectory)[:12],'count14-'+digest(trajectory)[:12])


class NativeLayout:
    def __init__(self,core,*,native_uid):
        need(not hasattr(core,'native_layout') and core.control is None and
             set(core.gate.startup_held)==set(core.rows) and
             type(native_uid) is int and (native_uid==os.geteuid() if core.qualification_only else
                                          native_uid==10000 and os.geteuid()==0),
             'DYNTEAM_NEW_NATIVE_LAYOUT_BEFORE_CONTROL_SAME_HELD_OWNER')
        with core.ledger.mutex:
            need(core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0,
                 'DYNTEAM_NATIVE_LAYOUT_BEFORE_ANY_MODEL_REQUEST')
        self.core,self.uid,self.owner=core,native_uid,process_birth(os.getpid())
        self.contract_sha256=digest(core.contract);self.state='PARTIAL_RETAINED'
        self.rows={};self.archive_bindings={};self.identities={}
        core.native_layout=self
        for t,row in core.rows.items():
            root=Path(row['root']);need(root.is_dir() and root.resolve()==root,'DYNTEAM_EXACT_LAYOUT_TRAJECTORY_ROOT')
            data=root/'native-data';self._mkdir(data,0o700,os.geteuid())
            profile,org=native_names(t);profile_root=data/profile;self._mkdir(profile_root,0o755,os.geteuid())
            for name in ('agents','acp','trajectories','workspaces'):
                self._mkdir(profile_root/name,0o755,os.geteuid())
            roles={}
            for role,alias in native_aliases(row['arm']).items():
                account=org+'-'+alias['native_short']
                archive=profile_root/'trajectories'/account
                control=profile_root/'acp'/account
                state=profile_root/'agents'/account
                workspace=profile_root/'workspaces'/account
                self._mkdir(archive,0o700,os.geteuid()) # original root bridge TurnState producer
                self._mkdir(control,0o755,native_uid) # original entrypoint socket-directory owner
                self._mkdir(state,0o755,native_uid)
                self._mkdir(workspace,0o755,native_uid)
                roles[role]=dict(agent_state=str(state),archive_root=str(archive),acp_root=str(control),workspace=str(workspace))
                self.archive_bindings[t,role]=dict(archive_root=str(archive),
                    native_turn_metadata=str(control/'current-turn.json'),owner_uid=os.geteuid())
            self.rows[t]=dict(data_root=str(data),profile=profile,org=org,profile_root=str(profile_root),roles=roles)
        self.state='NEW_LAYOUT_DURABLE_MODEL_GATES_HELD'
        proof=core.home/'NATIVE_LAYOUT_PUBLIC_INODES.json'
        raw=json.dumps(dict(schema='count14-native-layout-public-v1',owner_pid=self.owner.pid,
            owner_start_ticks=self.owner.start_ticks,owner_boot_id=self.owner.boot_id,contract_sha256=self.contract_sha256,
            directories=[dict(path=name,dev=v[0],inode=v[1],uid=v[2],mode=v[3]) for name,v in sorted(self.identities.items())]),
            sort_keys=True).encode()+b'\n'
        fd=os.open(proof,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
        try:
            with os.fdopen(fd,'wb',closefd=False) as out:out.write(raw);out.flush();os.fsync(fd)
        finally:os.close(fd)

    def _mkdir(self,path,mode,uid):
        path.mkdir(mode=mode) # existing/symlink node never accepted or chmodded
        if os.geteuid()==0:os.chown(path,uid,uid)
        os.chmod(path,mode);s=path.lstat()
        need(stat.S_ISDIR(s.st_mode) and not path.is_symlink() and path.resolve()==path and s.st_uid==uid,
             'DYNTEAM_EXACT_FRESH_NATIVE_LAYOUT_DIRECTORY')
        self.identities[str(path)]=(s.st_dev,s.st_ino,s.st_uid,stat.S_IMODE(s.st_mode))
        for directory in (path,path.parent):
            fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:os.fsync(fd)
            finally:os.close(fd)

    def current(self,t):
        need(self.state=='NEW_LAYOUT_DURABLE_MODEL_GATES_HELD' and t in self.rows and
             process_birth(os.getpid())==self.owner and digest(self.core.contract)==self.contract_sha256 and
             getattr(self.core,'native_layout',None) is self,
             'DYNTEAM_LAYOUT_ONLY_ORIGINAL_CURRENT_OWNER_CONTRACT')
        for name,value in self.identities.items():
            path=Path(name);s=path.lstat()
            need(stat.S_ISDIR(s.st_mode) and not path.is_symlink() and path.resolve()==path and
                 (s.st_dev,s.st_ino,s.st_uid,stat.S_IMODE(s.st_mode))==value,
                 'DYNTEAM_NATIVE_LAYOUT_EXACT_DIRECTORY_IDENTITY_CHANGED')
        return self.rows[t]
