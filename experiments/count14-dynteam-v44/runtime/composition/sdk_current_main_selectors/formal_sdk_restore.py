"""Prospective strict same-owner SDK restoration, not whole cold-owner recovery.

Original snapshots remain L1. A separate new sidecar identifies a possible
opaque restore input; only actual fixed native loadSession ACK can qualify its
consumption. No paid baseline reset, new SID, model request, signal or cleanup.
"""
from dataclasses import dataclass,asdict,replace
from pathlib import Path
from types import MethodType
import copy,hashlib,json,os,stat,threading,struct,time,shlex

from common import need,digest,wire,publish,strict
from native_peer_registry import process_birth

SIDECAR='count14-formal-native-sdk-restore-candidate-control-v1'


class WaitForSdkRestore(Exception):pass


def sid_pin(value):return hashlib.sha256(value.encode('utf8')).hexdigest()


def directory_identity(path):
    p=Path(path);s=p.lstat()
    need(p.is_absolute()and p.resolve()==p and not p.is_symlink()and stat.S_ISDIR(s.st_mode),
         'SDK_RESTORE_EXACT_PRESERVED_DIRECTORY_METADATA')
    return dict(path=str(p),device=s.st_dev,inode=s.st_ino,uid=s.st_uid,gid=s.st_gid,mode=stat.S_IMODE(s.st_mode))


def role_plan(control,roles,layout):
    """Pure control-only planner. No native state/archives/PKL/logs are read."""
    affinity=control['session_affinity'];clis=control['native_clis'];births=control['role_births']
    need(set(affinity)<=set(roles)and set(clis)<=set(roles)and set(births)<=set(roles)and
         set(layout['roles'])==set(roles),'SDK_RESTORE_COMPLETE_DYNAMIC_CATALOGUE')
    result=[]
    for role,kind in sorted(roles.items()):
        cli=clis.get(role);session=affinity.get(role)
        if cli is not None and not cli['archived']:
            if session is None:raise WaitForSdkRestore('SDK_RESTORE_LIVE_ROLE_HAS_NO_ORIGINAL_SID')
            need(session[0]==births[role]and type(session[1])is str and len(session[1])==36,
                 'SDK_RESTORE_SAME_ORIGINAL_LOGICAL_BIRTH_SID')
            result.append(dict(role=role,kind=kind,state='LIVE_ORIGINAL_SID',birth=session[0],
                session_sha256=sid_pin(session[1]),native_session_uuid=session[1],
                native_turn_sha256=cli['token'][3],logical_birth_sha256=cli['raw_birth'],
                old_cli=copy.deepcopy(cli)))
        else:
            need(session is None and role not in births,'SDK_RESTORE_NO_DORMANT_SID_OR_REVIVED_ENDED_BIRTH')
            result.append(dict(role=role,kind=kind,state='DORMANT_NO_SDK_RESTORE'))
    return result


@dataclass(frozen=True)
class SdkRestorePlan:
    trajectory:str
    snapshot_sha256:str
    candidate_sha256:str
    plan_sha256:str
    roles:tuple
    def public(self):
        return dict(schema='count14-formal-sdk-restore-plan-public-v1',trajectory=self.trajectory,
            snapshot_sha256=self.snapshot_sha256,candidate_sha256=self.candidate_sha256,
            plan_sha256=self.plan_sha256,roles=[dict(role=r['role'],kind=r['kind'],state=r['state'],
                **({'session_sha256':r['session_sha256']}if 'session_sha256'in r else{}))for r in self.roles],
            same_owner_CLI_only=True,whole_cold_owner_restore_qualified=False,
            old_L1_capability_unchanged=True,strict_load_ACK_still_required=True)


class FormalSdkRestoreControl:
    def __init__(self,cohort):
        from native_formal_cohort import NativeFormalCohort
        from native_cold_owner import NativeColdOwner
        from original_relay_core import OriginalRelayCore
        from native_sdk_startup_epochs import NativeSdkStartupEpochs
        need(type(cohort)is NativeFormalCohort and type(cohort.owner)is NativeColdOwner and
             type(cohort.core)is OriginalRelayCore and cohort.owner.core is cohort.core and
             cohort.owner.scientific_smoke is cohort and not cohort.activation_attempted and
             not cohort.core.qualification_only and not cohort.core.closed and
             set(cohort.core.gate.startup_held)==set(cohort.tracks)and
             type(cohort.core.native_sdk_startup_epochs)is NativeSdkStartupEpochs and
             not hasattr(cohort.core,'formal_sdk_restore'), 'SDK_RESTORE_INSTALL_ONLY_EXACT_NEW_COLD_GRAPH')
        self.cohort,self.core=cohort,cohort.core;self.owner=process_birth(os.getpid())
        with self.core.ledger.mutex:
            need(self.core.ledger.db.execute('SELECT COUNT(*)FROM requests').fetchone()[0]==0,
                 'SDK_RESTORE_INSTALL_BEFORE_ANY_PAID_REQUEST')
        self.sha=digest(self.core.contract);self.epochs=self.core.native_sdk_startup_epochs
        self.checkpoints={};self.candidates={};self.plans={};self.pending={};self.retained=[];self.sequence=0
        self.queue_lock=threading.Lock();self.acks=[];self.failure=None;self.resume_authorized=set()
        self.original_handle=self.core.bridge_owner.handle
        self.core.bridge_owner.handle=MethodType(lambda own,row,peer:self.handle_birth(row,peer),self.core.bridge_owner)
        self.original_prepare_session,self.original_commit_session=self.epochs.prepare_session,self.epochs.commit_session
        self.epochs.prepare_session=MethodType(lambda own,t,role,row:self.prepare_session(t,role,row),self.epochs)
        self.epochs.commit_session=MethodType(lambda own,t,role,row:self.commit_session(t,role,row),self.epochs)
        self._install_ack_endpoint()
        self.core.formal_sdk_restore=self;cohort.formal_sdk_restore=self
        original_poll=cohort.poll
        def poll(own):
            self.poll_acks();return original_poll()
        cohort.poll=MethodType(poll,cohort)

    def _current(self):
        need(self.core.formal_sdk_restore is self and self.cohort.core is self.core and
             self.cohort.owner.core is self.core and process_birth(os.getpid())==self.owner and
             digest(self.core.contract)==self.sha and not self.core.closed and
             not self.core.ledger.mutex._is_owned(),'SDK_RESTORE_SAME_LIVE_OWNER_OUTSIDE_SCIENCE_LOCK')

    def _receipt(self,kind,**data):
        # Host-only control, not a new scientific root or financial event.
        root=self.core.home/'sdk-restore-control';root.mkdir(mode=0o700,exist_ok=True)
        self.sequence+=1
        publish(root/(str(self.sequence).zfill(6)+'-'+kind+'_PUBLIC.json'),wire(dict(
            schema='count14-formal-sdk-restore-control-receipt-v1',kind=kind,at_ns=time.time_ns(),
            owner_sha256=digest(asdict(self.owner)),contract_sha256=self.sha,
            requests_replayed=False,fees_reset=False,whole_cold_owner_restore_qualified=False,**data)),mode=0o400)

    def _ledger_anchor(self,t):
        with self.core.ledger.mutex:
            l=self.core.ledger
            requests=[tuple(r)for r in l.db.execute('SELECT id,trajectory,role,generation,state,upper_bound,input,output,receipt_sha FROM requests WHERE trajectory=?ORDER BY id',(t,))]
            unknown=[tuple(r)for r in l.db.execute('SELECT request_id,upper_bound,settlement_seq FROM unknown_charges WHERE request_id IN(SELECT id FROM requests WHERE trajectory=?)ORDER BY request_id',(t,))]
            f=l.frontier(t)
            return dict(requests_sha256=digest(requests),request_count=len(requests),unknown_sha256=digest(unknown),
                financial_frontier={k:f[k]for k in('generation','target','actual','shortfall','reserved','unresolved','active_operations')},
                admission_fault=l.admission_fault(t))

    def bind_checkpoint(self,checkpoint):
        from native_dynamic_checkpoint import DynamicCheckpointPorts
        self._current();t=checkpoint.t
        need(type(checkpoint)is DynamicCheckpointPorts and checkpoint.core is self.core and
             self.core.formal_checkpoint_ports[t]is checkpoint and t in self.core.gate.startup_held and
             checkpoint.state=='BOUND_MODELS_HELD'and t not in self.checkpoints and
             hasattr(checkpoint,'formal_host_writers'),'SDK_RESTORE_AFTER_ORIGINAL_HOST_COLD_CHECKPOINT_ONLY')
        old_control,old_step=checkpoint._bridge_control,checkpoint.step
        def control(own):
            base=old_control();candidate=self.capture_candidate(checkpoint,base)
            need('sdk_restore_candidate'not in base,'SDK_RESTORE_NO_SIDECAR_COLLISION')
            return {**base,'sdk_restore_candidate':candidate}
        def step(own):
            if checkpoint.state=='POINT_QUEUED'and any(p.trajectory==t for p in self.plans.values())and t not in self.resume_authorized:
                return checkpoint.public() # explicit owner resume only; never auto-thaw after ACK
            return old_step()
        checkpoint._bridge_control=MethodType(control,checkpoint);checkpoint.step=MethodType(step,checkpoint)
        checkpoint.formal_sdk_restore=self;self.checkpoints[t]=checkpoint

    def capture_candidate(self,checkpoint,control):
        self._current();writer=checkpoint.writer
        need(writer is not None and writer.cut is not None and checkpoint.state in('PARKED','COMMITTED','COLLECTION_STARTED','POINT_QUEUED','FINAL_PARKED'),
             'SDK_RESTORE_ONLY_ORIGINAL_WHOLE_FROZEN_CUT_CONTROL')
        layout=self.core.native_layout.current(checkpoint.t)
        catalogue=self.core.sessions.tracks[checkpoint.t].roles
        need(set(catalogue)==set(self.core.rows[checkpoint.t]['roles']),'SDK_RESTORE_ORIGINAL_ROLE_KINDS_CATALOGUE')
        rows=role_plan(control,catalogue,layout)
        roots={r:{name:directory_identity(layout['roles'][r][name])for name in
            ('agent_state','workspace','archive_root','acp_root')}for r in self.core.rows[checkpoint.t]['roles']}
        from anonymous_roster_journal import snapshot
        roster=snapshot(self.core.journals[checkpoint.t].projection)
        need(set(roster['roles'])==set(roots),'SDK_RESTORE_ANONYMOUS_DYNAMIC_ROSTER_COMPLETE')
        value=dict(schema=SIDECAR,trajectory=checkpoint.t,cut_sha256=writer.cut.cut_sha,
            contract_sha256=self.sha,owner=asdict(self.owner),roles=rows,roots=roots,
            anonymous_roster=roster,spawn=copy.deepcopy(control['spawn']),
            original_ledger=self._ledger_anchor(checkpoint.t),
            native_epoch_sha256={r:digest(asdict(e))for(t,r),e in self.epochs.current.items()if t==checkpoint.t},
            original_mount_inventory_sha256=writer.inventory_sha,
            host_writers=copy.deepcopy(control.get('scientific_host_writers')),
            original_L1_cold_supported=False,prospective_L2_candidate_only=True,
            actual_strict_load_ACK_qualified=False,opaque_state_consumed_by_original_SDK_only=True)
        # Captured by original bridge JSON -> original CAS/COMMITTED snapshot.
        self.candidates[checkpoint.t]=copy.deepcopy(value);return value

    def prepare_from_committed(self,checkpoint):
        self._current();t=checkpoint.t
        need(self.checkpoints.get(t)is checkpoint and checkpoint.state in('COMMITTED','POINT_QUEUED','FINAL_PARKED')and
             t in self.candidates,'SDK_RESTORE_EXACT_BOUND_COMMITTED_CHECKPOINT')
        candidate=self.candidates[t];ref=checkpoint.reference
        with self.core.ledger.mutex:
            row=self.core.ledger.db.execute('SELECT ref_sha FROM snapshots WHERE trajectory=?AND generation=?',(t,checkpoint.sequence)).fetchone()
        if row is None or row[0]!=ref['sha256']:raise WaitForSdkRestore('SDK_RESTORE_ORIGINAL_COMMITTED_REQUIRED')
        # Only original fixed control JSON, never SDK files or archive members.
        saved=strict((checkpoint.home/'bridge/bridge_journal/NATIVE_CONTROL.json').read_bytes())
        need(saved['sdk_restore_candidate']==candidate and candidate['owner']==asdict(self.owner)and
             candidate['original_ledger']==self._ledger_anchor(t),
             'SDK_RESTORE_COMMITTED_SIDECAR_SAME_OWNER_LEDGER_UNKNOWN')
        body=dict(trajectory=t,snapshot_sha256=ref['sha256'],candidate_sha256=digest(candidate),roles=candidate['roles'])
        key=digest(body);need(key not in self.plans,'SDK_RESTORE_NO_AUTOMATIC_PLAN_RETRY')
        plan=SdkRestorePlan(t,ref['sha256'],digest(candidate),key,tuple(copy.deepcopy(candidate['roles'])))
        self.plans[key]=plan
        for r in plan.roles:
            if r['state']=='LIVE_ORIGINAL_SID':
                role=r['role'];need((t,role)not in self.pending,'SDK_RESTORE_ONE_ROLE_PLAN')
                epoch=self.epochs.current.get((t,role))
                need(epoch is not None and digest(asdict(epoch))==candidate['native_epoch_sha256'][role],
                     'SDK_RESTORE_ORIGINAL_PAID_EPOCH_NOT_REBASELINED')
                self.pending[t,role]=dict(plan=plan,row=r,old_epoch=epoch,old_cli=self.core.bridge_owner.clis[t,role],state='WAIT_ORIGINAL_PHYSICAL_EXIT',strict_ack=False)
        self._receipt('PREPARED_WAIT_PHYSICAL_EXIT',plan=plan.public())
        return plan

    def _unchanged(self,p):
        t=p['plan'].trajectory;candidate=self.candidates[t]
        need(self._ledger_anchor(t)==candidate['original_ledger'], 'SDK_RESTORE_PAID_COUNT_UNKNOWN_OR_FRONTIER_CHANGED_RETAIN')
        for role,roots in candidate['roots'].items():
            for record in roots.values():need(directory_identity(record['path'])==record,'SDK_RESTORE_PRESERVED_WORKSPACE_STATE_ROOT_IDENTITY')
        need(self.core.ledger.frontier(t)['state']=='COMMITTED_PARKED','SDK_RESTORE_NO_SEARCH_ADMISSION_BEFORE_EXPLICIT_ORIGINAL_RESUME')

    def handle_birth(self,row,peer):
        key=row['trajectory_id'],row['role_slot'];p=self.pending.get(key)
        if p is None:return self.original_handle(row,peer)
        if row['event']!='CLI_BIRTH':
            # Normal END/cleanup is not authorized by loading or a failed ACK.
            if not p['strict_ack']:return False
            return self.original_handle(row,peer)
        from native_bridge_protocol import checked_lifecycle
        from native_bridge_owner import direct_native_child,same_child_alive
        from native_sdk_startup_epochs import Epoch
        self._current();checked_lifecycle(row);self._unchanged(p)
        need(self.core.peers.validate(row,peer),'SDK_RESTORE_ORIGINAL_REGISTERED_NATIVE_PEER')
        t,role=key;r=p['row'];old=p['old_epoch']
        need(row['logical_birth_sha256']==r['logical_birth_sha256']and row['native_turn_sha256']==r['native_turn_sha256'],
             'SDK_RESTORE_SAME_LOGICAL_BIRTH_AND_NATIVE_TURN_NO_REVIVAL')
        child=direct_native_child(peer[0],row['child_namespace_pid'],row['child_start_ticks'],expected_uid=self.core.bridge_owner.uid)
        token=(key,row['child_namespace_pid'],row['child_start_ticks'],row['native_turn_sha256'])
        if p['state']!='WAIT_ORIGINAL_PHYSICAL_EXIT':return self.core.bridge_owner.clis[key]['birth']==child and p['token']==token
        if same_child_alive(old.child):return False
        if any(same_child_alive(b)for c in old.components for b in c.sdk):return False
        self.epochs._physical(key)
        components=self.epochs._capture(key,child,previous=old.components)
        from smoke_racing_tools_native_control import checked_control
        native_control=checked_control(row.get('tool_control'))
        need(native_control['control_complete']is True and native_control['observer_fault']is False and
             native_control['pending_prompts']==native_control['pending_tools']==0,
             'SDK_RESTORE_NEW_PRE_FORWARD_COMPLETE_CONTROL_ZERO')
        self._unchanged(p)
        need(self.epochs._session(key)==(r['birth'],r['native_session_uuid'])and
             self.core.roles.births.get(key)==r['birth']and self.core.bridge_owner.clis[key]is p['old_cli'],
             'SDK_RESTORE_ORIGINAL_AFFINITY_LOGICAL_BIRTH_AND_RETAINED_OLD_CLI')
        # Explicit new identity, not ARCHIVED_END, new logical birth or a zero-
        # cost paid baseline. Old exact objects remain retained in the plan.
        epoch=replace(old,ordinal=old.ordinal+1,child=child,token=token,components=components,
            request_anchor=self.epochs._count(key),session_before=self.epochs._session(key),
            stage='COLD_RESTORED_CLI_WAIT_STRICT_SESSION',archived=False,first_session=False)
        p.update(state='ADOPTION_INTENT_RETAIN_ON_FAILURE',token=token,new_epoch=epoch)
        self._receipt('CLI_ADOPTION_INTENT',plan_sha256=p['plan'].plan_sha256,role=role,old_epoch_sha256=digest(asdict(old)),new_child_sha256=digest(asdict(child)))
        self.retained.append((p['old_cli'],old))
        self.core.bridge_owner.clis[key]=dict(token=token,birth=child,raw_birth=r['logical_birth_sha256'],archived=False,end_lease=None)
        self.epochs.current[key]=epoch;self.epochs.history.append(epoch);self.epochs.custody.candidates[key]=child
        from smoke_racing_tools_cold_control_builder import consume_control_snapshot
        consume_control_snapshot(self.epochs.custody,t,role,child,native_control)
        p['state']='WAIT_STRICT_LOAD_ACK';return True

    def adopt_replacement_peers(self,plan,role,*,bridge_birth,router_birth):
        """Explicit host-only normal kernel identities; not first-start bypass.

        This narrow implementation retains current container init/CID/root.
        Replacing containers or the owner needs a DIFFERENT qualified normal
        restore registration; it is not declared invalid in all cold scenarios.
        """
        from native_peer_registry import ProcessBirth
        from native_container_retirement import ContainerBinding,descendant_in_container,alive
        self._current();need(self.plans.get(plan.plan_sha256)is plan,'SDK_RESTORE_ONLY_ISSUED_PLAN_PEER_ADOPTION')
        p=self.pending[plan.trajectory,role];self._unchanged(p)
        need(p['state']=='WAIT_ORIGINAL_PHYSICAL_EXIT'and not alive(p['old_epoch'].child),
             'SDK_RESTORE_OLD_SDK_MUST_EXIT_NATURALLY_BEFORE_PEER_ADOPTION')
        need(all(not alive(b)for c in p['old_epoch'].components for b in c.sdk),
             'SDK_RESTORE_EVERY_OLD_SDK_BIRTH_PHYSICALLY_ABSENT')
        self.epochs._physical((plan.trajectory,role))
        registry=self.core.native_containers;updates=[]
        for component,purpose,birth,uid in(('agent','bridge',bridge_birth,0),('router','router',router_birth,10000)):
            key=plan.trajectory,role,component;old=registry.records[key]
            need(type(birth)is ProcessBirth and process_birth(birth.pid)==birth and birth.uid==uid and
                 descendant_in_container(old.init_birth,birth),'SDK_RESTORE_ACTUAL_REPLACEMENT_PEER_EXACT_KERNEL_DESCENDANT_UID')
            if old.peer_birth==birth:continue
            if alive(old.peer_birth):raise WaitForSdkRestore('SDK_RESTORE_OLD_REGISTERED_PEER_STILL_LIVE')
            new=replace(old,peer_birth=birth);registry.validate(new,registry.docker.inspect(old.cid),running=True)
            from smoke_racing_tools_kernel_custody import kernel_census,_control_chain
            census=kernel_census(old.init_birth);controls=set(_control_chain(birth,old.init_birth))
            need(all(b in controls or component=='agent'and descendant_in_container(birth,b)
                for b in census.members),'SDK_RESTORE_NO_OLD_OR_EXTERNAL_SURVIVING_TOOL_BIRTH')
            updates.append((key,purpose,old,new))
        # Retain exact old bindings, and use ORIGINAL retire/register APIs.
        # No initial-role admission, CLI launch or financial registration runs.
        for key,purpose,old,new in updates:
            self._receipt('PEER_ADOPTION_INTENT',plan_sha256=plan.plan_sha256,role=role,component=old.component,
                old_peer_sha256=digest(asdict(old.peer_birth)),new_peer_sha256=digest(asdict(new.peer_birth)))
            self.core.peers.retire_after_exit(plan.trajectory,role,old.peer_birth,original_physical_clear=True,purpose=purpose)
            self.core.peers.register_from_launcher(plan.trajectory,role,new.peer_birth,expected_birth=new.peer_birth,purpose=purpose)
            need(registry.records[key]is old,'SDK_RESTORE_NO_CONCURRENT_NATIVE_BINDING_REPLACEMENT')
            self.retained.append(old);registry.records[key]=new
        return dict(peers_rebound=len(updates),paid_or_session_rows_changed=False)

    def prepare_session(self,t,role,row):
        p=self.pending.get((t,role))
        if p is None or p['strict_ack']:return self.original_prepare_session(t,role,row)
        self._current();self._unchanged(p);key=t,role;r=p['row'];epoch=self.epochs.current[key]
        need(p['state']=='WAIT_STRICT_LOAD_ACK'and row['native_session_uuid']==r['native_session_uuid']and
             row['logical_birth_sha256']==r['logical_birth_sha256']and row['native_turn_sha256']==r['native_turn_sha256']and
             self.epochs._session(key)==(r['birth'],r['native_session_uuid'])and
             self.epochs._count(key)==epoch.request_anchor,'SDK_RESTORE_ONLY_SAME_SID_ZERO_NEW_REQUEST_SESSION_PREPARE')
        if p.get('session_prepared')is not None:return p['session_prepared']
        self.epochs._physical(key);components=self.epochs._capture(key,epoch.child,previous=epoch.components)
        prepared=replace(epoch,components=components,first_session=True,stage='COLD_ORIGINAL_SESSION_PREPARED')
        self._receipt('SESSION_PREPARED_SAME_SID',plan_sha256=p['plan'].plan_sha256,role=role,session_sha256=r['session_sha256'])
        p['session_prepared']=prepared;self.epochs.current[key]=prepared;self.epochs.history.append(prepared)
        return prepared

    def commit_session(self,t,role,row):
        p=self.pending.get((t,role))
        if p is None or p['strict_ack']:return self.original_commit_session(t,role,row)
        r=p['row'];key=t,role;prepared=p.get('session_prepared')
        need(prepared is not None and self.epochs.current[key]is prepared and
             row['native_session_uuid']==r['native_session_uuid']and self.epochs._session(key)==(r['birth'],r['native_session_uuid']),
             'SDK_RESTORE_COMMIT_AFTER_ORIGINAL_IDEMPOTENT_AFFINITY_BIND')
        if p.get('session_bound')is prepared:return prepared
        self._receipt('SESSION_BOUND_SAME_SID',plan_sha256=p['plan'].plan_sha256,role=role,session_sha256=r['session_sha256'])
        # Preserve the old epoch's session_prepared/session_bound history. The
        # restored same-SID epoch has a distinct explicit control slot here.
        p['session_bound']=prepared;return prepared

    def control_descriptor(self,plan,role,*,native_turn):
        self._current();need(self.plans.get(plan.plan_sha256)is plan,'SDK_RESTORE_ONLY_ISSUED_PLAN')
        p=self.pending[plan.trajectory,role];self._unchanged(p);r=p['row']
        from native_bridge_protocol import BASE
        native_digest=lambda v:hashlib.sha256(json.dumps(v,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        need(native_digest([BASE,plan.trajectory,role,native_turn])==r['native_turn_sha256'], 'SDK_RESTORE_ORIGINAL_TURN_METADATA_ONLY')
        return dict(schema='count14-formal-cold-sdk-load-control-v1',plan_sha256=plan.plan_sha256,
            snapshot_sha256=plan.snapshot_sha256,trajectory=plan.trajectory,role=role,
            native_session_uuid=r['native_session_uuid'],session_sha256=r['session_sha256'],native_turn=native_turn,
            logical_birth_sha256=r['logical_birth_sha256'],native_turn_sha256=r['native_turn_sha256'],
            control_socket='/run/count14-dynteam/native-control.sock',no_prompt=True,no_fallback=True)

    def stage_control_descriptor(self,plan,role,*,native_turn):
        value=self.control_descriptor(plan,role,native_turn=native_turn)
        need(os.geteuid()==0,'SDK_RESTORE_EXISTING_TRUSTED_HOST_UID_NO_ELEVATION')
        raw=wire(value);pin=hashlib.sha256(raw).hexdigest()
        exports=self.core.cold_native_exports['trajectories'][plan.trajectory]['role_exports'][role]
        for key in('agent_control_directory','router_control_directory'):
            path=Path(exports[key])/'cold-sdk-restore.json'
            publish(path,raw,mode=0o444) # no overwrite; both already-scoped control mounts
        self._receipt('COLD_ROLE_DESCRIPTOR_STAGED',plan_sha256=plan.plan_sha256,role=role,descriptor_sha256=pin)
        return dict(COUNT14_COLD_SDK_RESTORE_FILE='/run/count14-dynteam/cold-sdk-restore.json',
            COUNT14_COLD_SDK_RESTORE_SHA256=pin)

    def _install_ack_endpoint(self):
        core=self.core;original=core.control.server.RequestHandlerClass;control=self
        class ColdHandler(original):
            def do_POST(own):
                if own.path not in('/native-sdk-restore-ack','/native-sdk-collaboration-recovery'):return super().do_POST()
                try:
                    lengths=own.headers.get_all('Content-Length',[])
                    need(not own.headers.get('Transfer-Encoding')and len(lengths)==1 and lengths[0].isdigit()and 0<int(lengths[0])<=4096,'SDK_RESTORE_ACK_BOUNDED_FIXED_CONTROL')
                    value=strict(own.rfile.read(int(lengths[0])));peer=struct.unpack('3i',own.request.getsockopt(__import__('socket').SOL_SOCKET,__import__('socket').SO_PEERCRED,12))
                    ticket=dict(value=value,peer=peer,event=threading.Event(),accepted=False,expires=time.monotonic()+2,result={})
                    with control.queue_lock:
                        need(len(control.acks)<128,'SDK_RESTORE_ACK_METADATA_QUEUE_BOUND');control.acks.append(ticket)
                    okay=ticket['event'].wait(2)and ticket['accepted']
                    own.answer(200 if okay else 503,dict(accepted=bool(okay),plan_sha256=value.get('plan_sha256'),**ticket['result']))
                except Exception:own.answer(503,dict(accepted=False,PUBLIC_code='SDK_RESTORE_ACK_RETAIN_NO_PROMPT'))
        core.control.server.RequestHandlerClass=ColdHandler # exact new server instance only

    def poll_acks(self):
        self._current()
        with self.queue_lock:tickets,self.acks=self.acks,[]
        for ticket in tickets:
            try:
                need(time.monotonic()<ticket['expires'],'SDK_RESTORE_EXPIRED_ACK_NOT_ACCEPTED')
                if ticket['value'].get('schema')=='count14-formal-cold-collaboration-recovery-v1':
                    ticket['result']=self._collaboration_recovery(ticket['value'],ticket['peer'])
                    ticket['accepted']=True
                    continue
                v=ticket['value'];need(set(v)=={'schema','plan_sha256','snapshot_sha256','session_sha256','session','loaded_original','prompt_sent'}and v['schema']=='count14-formal-cold-sdk-loaded-ack-v1'and v['loaded_original']is True and v['prompt_sent']is False,'SDK_RESTORE_FIXED_NATIVE_LOAD_ACK')
                from native_session_control import checked
                row=checked(v['session']);key=row['trajectory_id'],row['role_slot'];p=self.pending[key];r=p['row']
                need(p['state']=='WAIT_STRICT_LOAD_ACK'and v['plan_sha256']==p['plan'].plan_sha256 and v['snapshot_sha256']==p['plan'].snapshot_sha256 and v['session_sha256']==r['session_sha256']and
                     row['native_session_uuid']==r['native_session_uuid']and row['logical_birth_sha256']==r['logical_birth_sha256']and row['native_turn_sha256']==r['native_turn_sha256']and self.core.peers.validate(row,ticket['peer']), 'SDK_RESTORE_ACK_SAME_TYPED_PLAN_PEER_SID')
                self._unchanged(p);self.epochs._physical(key)
                from native_bridge_owner import same_child_alive
                need(self.epochs._session(key)==(r['birth'],r['native_session_uuid'])and
                     p.get('session_bound')is self.epochs.current[key]and
                     self.epochs.current[key].child==p['new_epoch'].child and same_child_alive(p['new_epoch'].child),
                     'SDK_RESTORE_ORIGINAL_PUBLISHER_BOUND_SAME_SID_AFTER_NORMAL_LOAD')
                self._receipt('STRICT_NORMAL_SDK_LOAD_ACK',plan_sha256=p['plan'].plan_sha256,role=key[1],session_sha256=r['session_sha256'],snapshot_sha256=p['plan'].snapshot_sha256)
                p.update(state='STRICT_LOAD_ACK_RETAINED_MODELS_STILL_HELD',strict_ack=True);ticket['accepted']=True
            except Exception as error:
                self.failure=dict(PUBLIC_code='SDK_RESTORE_PARTIAL_RETAINED_NO_AUTOMATIC_RETRY',exception_type=type(error).__name__)
            finally:ticket['event'].set()

    def _collaboration_recovery(self,v,peer):
        from native_session_control import checked
        from native_bridge_owner import same_child_alive
        row=checked(v['session']);key=row['trajectory_id'],row['role_slot'];p=self.pending[key];r=p['row']
        base={'schema','plan_sha256','snapshot_sha256','session','stage','before'}
        need(v['stage']in('INTENT','COMMITTED')and set(v)==(base if v['stage']=='INTENT'else base|{'after','recovered','recovery_token'}),
             'COLD_COLLABORATION_EXACT_STAGE_FIELDS')
        need(p['strict_ack']and v['plan_sha256']==p['plan'].plan_sha256 and v['snapshot_sha256']==p['plan'].snapshot_sha256 and
             row['native_session_uuid']==r['native_session_uuid']and row['logical_birth_sha256']==r['logical_birth_sha256']and
             row['native_turn_sha256']==r['native_turn_sha256']and self.core.peers.validate(row,peer)and same_child_alive(p['new_epoch'].child),
             'COLD_COLLABORATION_AFTER_STRICT_ORIGINAL_SDK_ACK_ONLY')
        self._unchanged(p);self.epochs._physical(key)
        before=v['before'];need(type(before)is dict and set(before)=={'sending','retrying'}and
            all(type(n)is int and 0<=n<=1000000 for n in before.values()),'COLD_COLLABORATION_FINITE_QUEUE_METADATA_ONLY')
        if v['stage']=='INTENT':
            if p.get('collaboration_intent')is not None:raise WaitForSdkRestore('COLD_COLLABORATION_RETAINED_INTENT_UNKNOWN_NO_AUTOMATIC_SECOND_CALL')
            token=digest(dict(plan=v['plan_sha256'],role=key[1],before=before,request_anchor=p['new_epoch'].request_anchor))
            self._receipt('COLLABORATION_ORIGINAL_RECOVERY_ONCE_INTENT',plan_sha256=v['plan_sha256'],role=key[1],
                before=before,recovery_token=token,model_request_replay=False)
            p['collaboration_intent']=dict(before=copy.deepcopy(before),token=token)
            return dict(recovery_token=token)
        intent=p.get('collaboration_intent');after=v['after']
        need(intent is not None and not p.get('collaboration_complete',False)and before==intent['before']and
             v['recovery_token']==intent['token']and type(v['recovered'])is int and v['recovered']==before['sending']and
             after==dict(sending=0,retrying=before['retrying']), 'COLD_COLLABORATION_ORIGINAL_ONCE_RECOVERY_RESULT')
        self._receipt('COLLABORATION_ORIGINAL_RECOVERY_ONCE_COMMITTED',plan_sha256=v['plan_sha256'],role=key[1],
            recovery_token=intent['token'],before=before,after=after,recovered=v['recovered'],
            original_request_COUNT_and_UNKNOWN_unchanged=True,original_dispatcher_handles_recovered_collaboration=True)
        p['collaboration_complete']=True
        return dict(recovery_token=intent['token'])

    def authorize_original_resume(self,plan):
        self._current();need(self.plans.get(plan.plan_sha256)is plan,'SDK_RESTORE_ONLY_ISSUED_PLAN_RESUME')
        rows=[p for p in self.pending.values()if p['plan']is plan]
        if not rows or not all(p['strict_ack']and p.get('collaboration_complete',False)for p in rows):raise WaitForSdkRestore('SDK_RESTORE_ALL_ORIGINAL_LIVE_ROLES_STRICT_ACK_AND_ONCE_COLLABORATION_REQUIRED')
        from native_bridge_owner import same_child_alive
        for p in rows:
            self._unchanged(p)
            need(same_child_alive(p['new_epoch'].child),'SDK_RESTORE_NEW_ORIGINAL_SDK_STILL_LIVE_BEFORE_RESUME')
        self._receipt('ALL_STRICT_LOAD_ACKS_ORIGINAL_RESUME_ALLOWED',plan_sha256=plan.plan_sha256,
            old_L1_snapshot_not_rewritten=True,actual_original_SDK_consumption=True,
            whole_new_owner_restore_qualified=False)
        self.resume_authorized.add(plan.trajectory)
        # This does not thaw/resume/send. Next normal checkpoint step still
        # executes original writer/membership/gate/cgroup and shell guards.
        return plan.public()


def install_native_overlay(cohort):
    from native_beta_layout import native_aliases
    from sdk_restore_overlay import CHANNEL_SHA,MAIN_SHA
    own=Path(__file__).resolve().parent;source=own/'native-cold-overlay-v3'
    manifest=strict((source/'CODE_MAP_PUBLIC.json').read_bytes())
    need(manifest['schema']=='count14-formal-cold-sdk-prospective-code-overlay-v1'and
         manifest['proof']['original_channel_sha256']==CHANNEL_SHA and manifest['proof']['original_main_sha256']==MAIN_SHA and
         manifest['proof']['reverse_bytes_equal']is True,'SDK_RESTORE_EXACT_PROSPECTIVE_OVERLAY_SOURCE')
    for name,pin in manifest['files'].items():
        path=source/name
        need(path.name==name and path.resolve()==path and not path.is_symlink()and
             hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256'],'SDK_RESTORE_COMPLETE_NEW_OVERLAY_BYTE_PINS')
    core=cohort.core;home=core.home/'sdk-restore-cold-source';home.mkdir(mode=0o700)
    for t,row in core.rows.items():
        aliases=native_aliases(row['arm']);services={};exports=core.cold_native_exports['trajectories'][t]
        routes=home/digest(t);routes.mkdir(mode=0o700)
        for role,alias in aliases.items():
            export=exports['role_exports'][role]
            for component,key in(('agent','agent_control_directory'),('router','router_control_directory')):
                original=strict((Path(export[key])/'route.json').read_bytes())
                need(original['native_module_pins']=={'main.js':MAIN_SHA,'acp_socket_channel.js':CHANNEL_SHA},
                     'SDK_RESTORE_OLD_FROZEN_NATIVE_PINS_NOT_PREMODIFIED')
                route={**original,'native_module_pins':{n:manifest['files'][n]['sha256']for n in('main.js','acp_socket_channel.js')}}
                path=routes/(role+'-'+component+'-route.json');publish(path,wire(route),mode=0o444)
                volumes=[dict(type='bind',source=str(path),target='/run/count14-dynteam/route.json',read_only=True)]
                if component=='router':
                    volumes += [dict(type='bind',source=str(source/n),target='/app/dist/'+n,read_only=True)
                        for n in('main.js','acp_socket_channel.js','sdk_restore_guest.mjs')]
                else:
                    volumes += [dict(type='bind',source=str(source/n),target='/opt/omcgitea/'+n,read_only=True)
                        for n in('acp-bridge.py','sdk_restore_bridge_guest.py')]
                services[alias[component+'_service']]=dict(volumes=volumes)
        path=routes/'compose.sdk-restore-cold.json';publish(path,wire(dict(services=services)),mode=0o400)
        host=core.native_host_environment['trajectories'][t]
        if 'native_bridge_user_layer' in host:
            from native_bridge_user_cold import append_existing_cold_overlay
            append_existing_cold_overlay(core,t,path)
        else:
            command=list(host['compose']);at=command.index('--project-name')
            command[at:at]=['-f',str(path)];host['compose']=tuple(command)
            host['launcher_env']['COUNT14_NATIVE_COMPOSE_COMMAND']=shlex.join(command)
    return manifest


def install_sdk_restore(cohort):
    need(not cohort.owner.bootstrap.records,'SDK_RESTORE_SOURCE_AND_CONTROL_BEFORE_ANY_NATIVE_UP')
    overlay=install_native_overlay(cohort)
    control=FormalSdkRestoreControl(cohort)
    control.overlay_manifest=overlay
    original=cohort._prepare_one
    from native_dynamic_writer import _function
    namespace=original.__func__.__globals__;old_host=namespace['FormalHostWriters']
    def host(*args,**kwargs):
        result=old_host(*args,**kwargs);control.bind_checkpoint(result.checkpoint);return result
    qualified=_function(original.__func__,FormalHostWriters=host)
    cohort._prepare_one=MethodType(qualified,cohort)
    return control
