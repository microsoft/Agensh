"""Normal fresh native SDK epochs only; no cold SDK adoption or paid rebaseline.

One original owner loop prepares pending born proof, original handler clears its
OLD CLI, replaces its own mapping, then commits this new SDK epoch before ACK /
any ACP forwarding. Cumulative original request COUNT is an immutable anchor,
not reset or reclassified. Only new direct CLI descendants can be startup SDKs.
All storage is append-only PUBLIC control metadata. Never read a payload/pickle,
process arguments/locals/stack or scientific log; never send, replay or signal.
"""
from dataclasses import dataclass,replace
from pathlib import Path
import json,os,stat,time

from common import need,digest
from native_peer_registry import ProcessBirth,process_birth
from native_bridge_owner import direct_native_child,same_child_alive
from smoke_racing_tools_kernel_custody import NativeKernelToolCustody,kernel_census,_control_chain
from smoke_racing_tools_fresh_baseline import _binding
from smoke_racing_tools_cold_control_builder import control_snapshot_clear,consume_control_snapshot
from smoke_racing_tools_native_control import checked_control


@dataclass(frozen=True)
class Component:
    component:str
    cid:str
    image_id:str
    init_birth:ProcessBirth
    domain:str
    device:int
    inode:int
    controls:tuple
    sdk:tuple


@dataclass(frozen=True)
class Epoch:
    trajectory:str
    role:str
    ordinal:int
    owner_birth:ProcessBirth
    contract_sha256:str
    child:ProcessBirth
    token:tuple
    request_anchor:int
    session_before:object
    components:tuple
    stage:str
    archived:bool=False
    first_session:bool=False


@dataclass(frozen=True)
class Pending:
    epoch:Epoch
    previous:object
    control:dict


def _token(row):
    return ((row['trajectory_id'],row['role_slot']),row['child_namespace_pid'],row['child_start_ticks'],row['native_turn_sha256'])


def _parent(birth):
    need(process_birth(birth.pid)==birth,'DYNTEAM_EPOCH_PROC_BIRTH_STILL_EXACT')
    path=Path('/proc',str(birth.pid),'status');fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        raw=os.read(fd,65537);need(len(raw)<=65536,'DYNTEAM_EPOCH_PUBLIC_STATUS_FINITE')
        rows=[line.split(b':',1)[1] for line in raw.splitlines() if line.startswith(b'PPid:')]
        need(len(rows)==1 and rows[0].strip().isdigit(),'DYNTEAM_EPOCH_PUBLIC_PARENT_ONLY')
        return int(rows[0])
    finally:os.close(fd)


class NativeSdkStartupEpochs:
    def __init__(self,custody):
        need(type(custody) is NativeKernelToolCustody and custody.core is not None,
             'DYNTEAM_EPOCH_SAME_ORIGINAL_NATIVE_CUSTODY')
        self.custody,self.core=custody,custody.core;self.owner=process_birth(os.getpid());self.sha=digest(self.core.contract)
        if not self.core.qualification_only:
            from original_relay_core import OriginalRelayCore
            need(type(self.core) is OriginalRelayCore and self.core.native_kernel_tool_custody is custody,
                 'DYNTEAM_EPOCH_REAL_COLD_ORIGINAL_CORE_AND_CUSTODY')
        need(not hasattr(custody,'sdk_startup_epochs') and not self.core.bridge_owner.clis and
             self._requests_all()==0,'DYNTEAM_EPOCH_COLD_INSTALL_BEFORE_ANY_NATIVE_CLI_OR_REQUEST')
        self.current={};self.pending={};self.partial=set();self.history=[];self.session_prepared={};self.session_bound={}
        custody.sdk_startup_epochs=self;self.core.native_sdk_startup_epochs=self
        from native_session_reconnect import NativeSessionReconnectOwner
        self.reconnect=NativeSessionReconnectOwner(self)

    def _owner(self):
        need(process_birth(os.getpid())==self.owner and digest(self.core.contract)==self.sha and
             not self.core.ledger.mutex._is_owned(),'DYNTEAM_EPOCH_SAME_OWNER_CONTRACT_OUTSIDE_SCIENCE_LOCK')

    def _requests_all(self):
        with self.core.ledger.mutex:return self.core.ledger.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]

    def _count(self,key):
        with self.core.ledger.mutex:
            return self.core.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=? AND role=?',key).fetchone()[0]

    def _session(self,key):
        track=self.core.sessions.tracks[key[0]]
        with track._lock:return track._current.get(key)

    def _physical(self,key):
        """Original models + exact role HTTP/retained/unattributed socket COUNT.

        Registry and ledger locks are NEVER nested. No HTTP body/status/message
        is read and no connection is interrupted, closed or otherwise changed.
        """
        _,clear=self.core.original_projection(*key)
        need(clear is True,'DYNTEAM_EPOCH_ORIGINAL_MODEL_PHYSICAL_ZERO')
        server=self.core.servers[key[0]]
        need(server.ledger is self.core.ledger and key in server.registered,
             'DYNTEAM_EPOCH_EXACT_ORIGINAL_ROLE_HTTP_SERVER')
        with server.registry_lock:
            active=tuple(server.requests.values());retained=tuple(server.retained.values())
            known={id(r.connection) for r in active};unattributed=len(set(server.accepted_sockets)-known)
            count=sum(r.identity==key for r in active)+sum(r.identity==key for r in retained)
            bad=server.lifecycle_storage_unknown
        need(type(bad) is bool and not bad and count==unattributed==0,
             'DYNTEAM_EPOCH_ORIGINAL_ROLE_HTTP_RETAINED_AND_UNATTRIBUTED_ZERO')

    def _game(self,t,role):
        if self.core.rows[t]['arm']!='DYNTEAM_RACING' or role!='racing-background-00':return set()
        from smoke_racing_tools_game_manager import registered_game_controls
        return registered_game_controls(self.core,t,role)

    def _capture(self,key,child,*,previous=()):
        """Only exact new SDK descendant subtree; reject every external birth."""
        self._owner();result=[]
        for name in ('agent','router'):
            record=_binding(self.core,*key,name);census=kernel_census(record.init_birth)
            controls=set(_control_chain(record.peer_birth,record.init_birth));game=self._game(*key) if name=='agent' else set()
            if previous:
                before=next(c for c in previous if c.component==name)
                need((record.cid,record.image_id,record.init_birth,census.domain,census.domain_device,census.domain_inode)==
                     (before.cid,before.image_id,before.init_birth,before.domain,before.device,before.inode),
                     'DYNTEAM_EPOCH_RETAINED_EXACT_CONTAINER_NOT_COLD_RESTORE_OR_NEW_CID')
            members=set(census.members);sdk=set();births={v.pid:v for v in members};end=time.monotonic()+.5
            for birth in members-controls-game:
                need(name=='agent' and child is not None and birth.uid==child.uid and birth.gid==child.gid,
                     'DYNTEAM_EPOCH_EXTERNAL_UNKNOWN_BIRTH_NOT_STARTUP')
                current=birth;visited=set()
                while current!=child:
                    need(time.monotonic()<end and len(visited)<128 and current.pid not in visited,
                         'DYNTEAM_EPOCH_FINITE_NEW_SDK_ANCESTRY')
                    visited.add(current.pid);parent=_parent(current)
                    need(parent in births,'DYNTEAM_EPOCH_NEW_SDK_MUST_DESCEND_EXACT_NEW_CLI')
                    current=births[parent]
                sdk.add(birth)
            if name=='agent' and child is not None:
                need(child in sdk and process_birth(child.pid)==child,'DYNTEAM_EPOCH_EXACT_NEW_NATIVE_CHILD_STILL_LIVE')
            result.append(Component(name,record.cid,record.image_id,record.init_birth,census.domain,
                census.domain_device,census.domain_inode,tuple(sorted(controls,key=lambda x:x.pid)),tuple(sorted(sdk,key=lambda x:x.pid))))
        return tuple(result)

    def _receipt(self,epoch,stage,**extra):
        root=Path(self.core.rows[epoch.trajectory]['root'])/'native-sdk-epoch-control'/epoch.role
        root.mkdir(parents=True,mode=0o700,exist_ok=True)
        need(root.resolve()==root and root.stat().st_uid==os.geteuid(),'DYNTEAM_EPOCH_NEW_EXACT_CONTROL_ROOT')
        directory=root/('epoch-'+f'{epoch.ordinal:08d}');directory.mkdir(mode=0o700,exist_ok=True)
        need(directory.resolve()==directory and directory.stat().st_uid==os.geteuid(),'DYNTEAM_EPOCH_CONTROL_DIRECTORY_NO_ALIAS')
        value=dict(schema='count14-native-normal-fresh-sdk-epoch-public-v1',trajectory=epoch.trajectory,role=epoch.role,
            epoch=epoch.ordinal,stage=stage,owner_pid=self.owner.pid,owner_start_ticks=self.owner.start_ticks,
            owner_boot_id=self.owner.boot_id,contract_sha256=self.sha,new_cli_pid=epoch.child.pid,
            new_cli_start_ticks=epoch.child.start_ticks,cumulative_request_count_anchor=epoch.request_anchor,
            cumulative_fees_reset=False,requests_replayed=False,cold_SDK_restore_qualified=False,
            startup_sdk_births=sum(len(c.sdk) for c in epoch.components),**extra)
        raw=(json.dumps(value,sort_keys=True)+'\n').encode();path=directory/(stage+'_PUBLIC.json')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
        try:
            os.fchmod(fd,0o444);need(os.write(fd,raw)==len(raw),'DYNTEAM_EPOCH_PUBLIC_RECEIPT_DURABLE_WRITE');os.fsync(fd)
        finally:os.close(fd)

    def prepare_birth(self,t,role,child,row):
        self._owner();key=t,role
        need(key not in self.partial and t in self.core.rows and role in self.core.rows[t]['roles'] and
             key in self.core.roles.held and type(child) is ProcessBirth,
             'DYNTEAM_EPOCH_BORN_ONLY_EXACT_HELD_REGISTERED_ROLE')
        token=_token(row);need(token[0]==key and row['event']=='CLI_BIRTH' and child.start_ticks==row['child_start_ticks'],
             'DYNTEAM_EPOCH_EXACT_BORN_ENVELOPE')
        control=row.get('tool_control');checked_control(control)
        need(control['pending_prompts']==control['pending_tools']==0 and control['control_complete'] is True and
             control['observer_fault'] is False,'DYNTEAM_EPOCH_PRE_FORWARD_NEW_CLI_CONTROL_ZERO')
        old_pending=self.pending.get(key)
        if old_pending is not None:
            need(old_pending.epoch.child==child and old_pending.epoch.token==token,
                 'DYNTEAM_EPOCH_NO_SECOND_PENDING_BIRTH_OR_REBASELINE')
            return old_pending
        old=self.current.get(key);cli=self.core.bridge_owner.clis.get(key);count=self._count(key)
        if old is None:
            need(cli is None and key not in self.core.roles.births and count==0,
                 'DYNTEAM_EPOCH_FIRST_BIRTH_ONLY_TRULY_FRESH_NO_PAID_ADOPTION')
        else:
            need(old.owner_birth==self.owner and old.archived and cli is not None and cli['archived'] is True and
                 cli['token']==old.token and cli['birth']==old.child and old.token in self.core.bridge_owner.finished and
                 not same_child_alive(old.child),'DYNTEAM_EPOCH_PREVIOUS_ORIGINAL_ARCHIVED_END_AND_REAL_EXIT')
        record=_binding(self.core,t,role,'agent')
        need(direct_native_child(record.peer_birth.pid,row['child_namespace_pid'],child.start_ticks,
             expected_uid=self.core.bridge_owner.uid)==child,'DYNTEAM_EPOCH_EXACT_NEW_DIRECT_NATIVE_CHILD')
        self._physical(key)
        components=self._capture(key,child,previous=() if old is None else old.components)
        need(self._count(key)==count and key in self.core.roles.held,'DYNTEAM_EPOCH_NO_NEW_REQUEST_DURING_BORN_PREPARE')
        epoch=Epoch(t,role,1 if old is None else old.ordinal+1,self.owner,self.sha,child,token,count,
            self._session(key),components,'PENDING_PRE_FORWARD')
        pending=Pending(epoch,old,dict(control));self.pending[key]=pending;self.partial.add(key)
        self._receipt(epoch,'PENDING_PRE_FORWARD',previous_original_ARCHIVED_END=old is not None,
            original_models_and_HTTP_zero=True,external_unknown_births=0)
        self.partial.remove(key);return pending

    def commit_birth(self,t,role,child,token):
        self._owner();key=t,role;p=self.pending.get(key);cli=self.core.bridge_owner.clis.get(key)
        need(key not in self.partial and type(p) is Pending and p.epoch.child==child and p.epoch.token==token and
             cli is not None and cli['birth']==child and cli['token']==token and not cli['archived'],
             'DYNTEAM_EPOCH_COMMIT_ONLY_AFTER_ORIGINAL_CLI_MAPPING_REPLACED')
        self._physical(key);need(self._count(key)==p.epoch.request_anchor,'DYNTEAM_EPOCH_ZERO_NEW_EPOCH_REQUESTS_BEFORE_BORN_ACK')
        components=self._capture(key,child,previous=p.epoch.components)
        epoch=replace(p.epoch,components=components,stage='CLI_COMMITTED_BEFORE_FORWARD')
        self.partial.add(key);self._receipt(epoch,'CLI_COMMITTED_BEFORE_FORWARD',original_old_clear_already_passed=True)
        consume_control_snapshot(self.custody,t,role,child,p.control)
        self.current[key]=epoch;self.history.append(epoch);self.custody.candidates[key]=child
        del self.pending[key];self.partial.remove(key);return epoch

    def birth_committed(self,t,role,child,token):
        key=t,role;epoch=self.current.get(key)
        return bool(key not in self.partial and key not in self.pending and type(epoch) is Epoch and
                    epoch.child==child and epoch.token==token and not epoch.archived)

    def _project_epoch(self,epoch):
        key=epoch.trajectory,epoch.role
        need(epoch.owner_birth==self.owner and epoch.contract_sha256==self.sha,'DYNTEAM_EPOCH_SAME_OWNER_ONLY_NO_COLD_ADOPTION')
        self._physical(key);live=same_child_alive(epoch.child)
        if self._count(key)>epoch.request_anchor and live:
            need(control_snapshot_clear(self.custody,*key,epoch.child),'DYNTEAM_EPOCH_ORIGINAL_ORDERED_PAID_CONTROL_ZERO')
        for c in epoch.components:
            record=_binding(self.core,*key,c.component);now=kernel_census(record.init_birth)
            need((record.cid,record.image_id,record.init_birth,now.domain,now.domain_device,now.domain_inode)==
                 (c.cid,c.image_id,c.init_birth,c.domain,c.device,c.inode),'DYNTEAM_EPOCH_ORIGINAL_CURRENT_CONTAINER_GENERATION')
            allowed=set(c.controls)|(set(c.sdk) if live else set())
            if c.component=='agent':allowed|=self._game(*key)
            need(set(now.members)<=allowed,'DYNTEAM_EPOCH_NO_NEW_OR_OLD_SURVIVING_TOOL_BIRTH')
        return True

    def project(self,t,role):
        try:
            self._owner();key=t,role
            if key in self.partial:return False
            pending=self.pending.get(key)
            if pending is not None:
                need(key in self.core.roles.held and self._count(key)==pending.epoch.request_anchor,
                     'DYNTEAM_EPOCH_PENDING_GATE_AND_ZERO_REQUESTS_STILL_HELD')
                cli=self.core.bridge_owner.clis.get(key);old=pending.previous
                need((cli is None if old is None else cli is not None and cli['token']==old.token and
                     cli['archived'] and not same_child_alive(old.child)),
                     'DYNTEAM_EPOCH_PENDING_OLD_MAPPING_NEVER_OVERWRITTEN_BEFORE_CLEAR')
                self._physical(key);self._capture(key,pending.epoch.child,previous=pending.epoch.components)
                return True
            epoch=self.current.get(key)
            if epoch is None:
                need(self._count(key)==0,'DYNTEAM_EPOCH_NO_UNKNOWN_PAID_ROLE_ADOPTION')
                return None # original truly fresh pre-CLI fallback
            cli=self.core.bridge_owner.clis.get(key)
            need(cli is not None and cli['birth']==epoch.child and cli['token']==epoch.token,
                 'DYNTEAM_EPOCH_BASELINE_MATCHES_ORIGINAL_CURRENT_CLI')
            return self._project_epoch(epoch)
        except Exception:return False

    def prepare_session(self,t,role,row):
        self._owner();key=t,role;epoch=self.current.get(key);cli=self.core.bridge_owner.clis.get(key)
        need(key not in self.partial and key not in self.pending and type(epoch) is Epoch and
             cli is not None and cli['birth']==epoch.child and cli['token']==epoch.token and
             row['trajectory_id']==t and row['role_slot']==role and row['native_turn_sha256']==epoch.token[3] and
             row['logical_birth_sha256']==cli['raw_birth'] and same_child_alive(epoch.child),
             'DYNTEAM_EPOCH_FIRST_SESSION_EXACT_NEW_COMMITTED_NATIVE_CLI')
        sid=row['native_session_uuid'];sk=key,sid
        if sk in self.session_prepared:
            prepared=self.session_prepared[sk]
            need(prepared.child==epoch.child and prepared.token==epoch.token,
                 'DYNTEAM_SESSION_READY_RETRY_SAME_ACTUAL_EPOCH_NOT_OLD_SID_REUSE')
            if sk in self.session_bound:
                # Preserve the original *identity confirmation* behavior for
                # the SAME already-bound SID/CLI/turn. It is not a fresh
                # newSession/END/capture permission or a paid census extension.
                birth=self.core.journals[t].projection._identity(role,row['logical_birth_sha256'])
                need(self._session(key)==(birth,sid),
                     'DYNTEAM_SESSION_IDENTITY_CONFIRM_ONLY_CURRENT_BOUND_SID')
            else:
                # Prepared but not bound is a real unfinished control boundary:
                # require the original physical/kernel projection, not an old
                # prepared receipt. Never initialize or census again here.
                self._project_epoch(epoch)
            return prepared
        self._physical(key)
        if not epoch.first_session:
            need(self._count(key)==epoch.request_anchor and self._session(key)==epoch.session_before,
                 'DYNTEAM_EPOCH_FIRST_SESSION_NO_NEW_REQUEST_AND_PREVIOUS_SID_UNCHANGED')
            components=self._capture(key,epoch.child,previous=epoch.components)
            epoch=replace(epoch,components=components,first_session=True,stage='FIRST_SESSION_BEFORE_BIND')
            need(self._count(key)==epoch.request_anchor,'DYNTEAM_EPOCH_STILL_ZERO_REQUESTS_BEFORE_FIRST_NEW_SID')
        else:
            # Same live CLI may use native newSession many times. NEVER census
            # a growing paid SDK tree again just because it has a new SID.
            self._project_epoch(epoch)
        ordinal=1+sum(k[0]==key for k in self.session_prepared)
        self.partial.add(key);self._receipt(epoch,'SESSION_PREPARED_'+f'{ordinal:08d}',
            first_session_startup_extended=not self.current[key].first_session,previous_session_present=epoch.session_before is not None)
        self.current[key]=epoch;self.history.append(epoch);self.session_prepared[sk]=epoch
        self.partial.remove(key);return epoch

    def commit_session(self,t,role,row):
        self._owner();key=t,role;sid=row['native_session_uuid'];sk=key,sid
        if sk in self.session_bound:return self.session_bound[sk]
        epoch=self.session_prepared.get(sk);birth=self.core.journals[t].projection._identity(role,row['logical_birth_sha256'])
        need(type(epoch) is Epoch and self.current[key].child==epoch.child and self._session(key)==(birth,sid),
             'DYNTEAM_EPOCH_SESSION_COMMIT_ONLY_AFTER_ORIGINAL_AFFINITY_BIND')
        ordinal=1+sum(k[0]==key for k in self.session_bound)
        self.partial.add(key);self._receipt(epoch,'SESSION_BOUND_'+f'{ordinal:08d}',original_affinity_bind=True)
        self.session_bound[sk]=epoch;self.partial.remove(key)
        self.reconnect.bound_new_epoch(key,epoch)
        return epoch

    def note_archived(self,t,role,row):
        self._owner();key=t,role;epoch=self.current.get(key);cli=self.core.bridge_owner.clis.get(key)
        need(type(epoch) is Epoch and cli is not None and cli['token']==epoch.token==_token(row) and
             cli['archived'] is True and epoch.token in self.core.bridge_owner.finished and not same_child_alive(epoch.child),
             'DYNTEAM_EPOCH_END_ONLY_ORIGINAL_ARCHIVED_END_AND_REAL_DEAD_BIRTH')
        if epoch.archived:return epoch
        need(key not in self.partial and self._project_epoch(epoch),'DYNTEAM_EPOCH_END_OLD_MODELS_HTTP_TOOLS_ZERO')
        ended=replace(epoch,stage='ORIGINAL_ARCHIVED_END',archived=True)
        self.partial.add(key);self._receipt(ended,'ORIGINAL_ARCHIVED_END',old_native_birth_physically_absent=True,
            original_models_HTTP_and_old_tools_zero=True)
        self.current[key]=ended;self.history.append(ended);self.partial.remove(key);return ended
