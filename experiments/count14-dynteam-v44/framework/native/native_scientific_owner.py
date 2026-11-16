"""Single same-live scientific owner for the existing native components.

This composes the ORIGINAL ledger, relay/gate, team ports, whole-writer fence,
service-cut CAS, collector, v2.1 input builder and global K3 queue. It neither
starts Docker nor guesses native tool ancestry, consistent backend backups or
CLI park compatibility. OPS still supplies these original trusted bindings.
No synthetic physical terminal/ACK/recovery/retry is generated here.
"""
from pathlib import Path
import copy, json, threading
from admission_gate import AdmissionGate
from budget import Ledger, SERVICES
from collector import collect
from common import need, sha, digest, private_dir, wire, publish, integer
from final_queue import FinalQueue
from native_budget_park import NativeBudgetParkProjection
from native_service_cut import NativeServiceCut, validate_graph
from native_stage_binding import NativeStageBinding
from native_team_owner import NativeTeamOwner
from native_scientific_http import NativeScientificHttpServer
from native_writer_fence import NativeWriterFence
from native_control_custody import NativeAcceptedControls
from scientific_relay import ScientificRelay
from snapshot import CAS
from v21_inputs import build

class NativeScientificOwner:
    """Trusted host composition; one instance, one trajectory, two native cuts.

    ``backup_ports`` is the trusted host backend implementation, NOT worker JSON.
    Called once with the original cut and fresh private destination after whole
    writer park. It must finish native application async work, use real SQLite/
    MySQL backup ports and bind ALL five service receipts to the same cut. Return
    exactly {'git_exports': [...]} from same-cut preregistered native Git exports.
    ServiceCut verifies actual sealed backup bytes; an empty listener/pending map
    alone is NOT evidence for the backend's asynchronous write boundary.

    Explicit step() polling does not retry a started backup/capture/collection/
    release. A failed step retains original custody and permanently faults this
    instance. Normal waiting returns without blocking the single host controller.
    """
    def __init__(self, team, relay, gate, cas, final_queue, directory, *, setting,
                 graph, expected_graph_sha256, roles, pins, registered_refs,
                 member_cap, backup_ports, http_server):
        need(type(team) is NativeTeamOwner and team.started and not team.closed,
             'SCIENCE_OWNER_ORIGINAL_STARTED_TEAM')
        self.team=team; self.ledger=team.ledger; self.t=team.t
        need(type(self.ledger) is Ledger and type(relay) is ScientificRelay
             and relay.budget is self.ledger, 'SCIENCE_OWNER_ORIGINAL_RELAY_LEDGER')
        need(type(gate) is AdmissionGate and gate.ledger is self.ledger
             and relay.ledger.admission_gate is gate,
             'SCIENCE_OWNER_ORIGINAL_RELAY_GATE')
        need(relay.ledger.global_cap==gate.global_cap,'SCIENCE_OWNER_SAME_ALLOCATED_MODEL_CAP')
        need(type(http_server) is NativeScientificHttpServer
             and http_server.engine is relay and http_server.gate is gate
             and http_server.ledger is self.ledger,
             'SCIENCE_OWNER_ORIGINAL_HTTP_RELAY_GATE')
        http_server.current()
        need({r for t,r in http_server.registered if t==self.t}==set(team.roles),
             'SCIENCE_OWNER_HTTP_ALL_AND_ONLY_SEARCH_ROLES')

        need(type(cas) is CAS and type(final_queue) is FinalQueue,
             'SCIENCE_OWNER_ORIGINAL_CAS_QUEUE')
        need(getattr(self.ledger,'native_unmanaged_cli',False) or callable(relay.tool_terminal_port), 'SCIENCE_OWNER_NATIVE_TOOL_TERMINAL_PORT')
        need(type(team.writer_fence) is NativeWriterFence
             and team.writer_fence.owner is team
             and team.writer_fence.state=='REGISTERED',
             'SCIENCE_OWNER_ORIGINAL_COMPLETE_WRITER_FENCE')
        need(setting in ('Agensh-1','Agensh-16')
             and len(team.roles)==(1 if setting=='Agensh-1' else 16),
             'SCIENCE_OWNER_SCIENTIFIC_TEAM_ROSTER')
        need(type(roles) is dict and set(roles)==set(team.roles)
             and all(type(r) is dict and set(r)=={'workspace','session'} for r in roles.values()),
             'SCIENCE_OWNER_ALL_ROLE_MOUNTS')
        canonical={}
        for role, row in roles.items():
            canonical[role]={}
            for kind,path in row.items():
                p=Path(path)
                need(p.is_absolute() and p.resolve()==p and p.is_dir(),
                     'SCIENCE_OWNER_CANONICAL_ROLE_MOUNT')
                canonical[role][kind]=p
            need(canonical[role]['workspace']==Path(team.gb['workspace_roots'][role]['path']),
                 'SCIENCE_OWNER_ORIGINAL_WORKSPACE')
        # HOME/session is a trusted OWN launch mount, not inferred from stdout.
        paths=[p for row in canonical.values() for p in row.values()]
        need(all(a!=b and not a.is_relative_to(b) and not b.is_relative_to(a)
                 for i,a in enumerate(paths) for b in paths[i+1:]),
             'SCIENCE_OWNER_DISTINCT_NONNESTED_ROLE_MOUNTS')
        validate_graph(graph,expected_graph_sha256)
        need(type(pins) is dict and {'manifest','source','protocol','task_description'}<=set(pins)
             and 'native_writer_fence' not in pins and 'gitea_exports' not in pins,
             'SCIENCE_OWNER_FROZEN_INPUT_PINS')
        for value in pins.values():sha(value)
        need(type(registered_refs) is tuple and registered_refs
             and len(set(registered_refs))==len(registered_refs)
             and all(type(r) is str and r.startswith('refs/') and not any(x in r for x in ('..','\x00','\n','\r')) for r in registered_refs),
             'SCIENCE_OWNER_PREREGISTERED_GIT_REFS')
        integer(member_cap,'SCIENCE_OWNER_NATIVE_MEMBER_CAP',1)
        need(member_cap<=10_000_000 and callable(backup_ports),
             'SCIENCE_OWNER_TRUSTED_BACKUP_PORTS')
        with self.ledger.mutex:
            f=self.ledger.frontier(self.t); a=self.ledger.account(self.t)
            need(f['state']=='RUNNING' and f['generation']==1 and a['stage']==0
                 and self.ledger.db.execute('SELECT COUNT(*) FROM requests WHERE trajectory=?',(self.t,)).fetchone()[0]==0,
                 'SCIENCE_OWNER_FIRST_START_BEFORE_MODEL')
            need(json.loads(a['targets'])==[10_000_000,20_000_000]
                 and pins['manifest']==a['manifest_sha']==final_queue.manifest,
                 'SCIENCE_OWNER_MANIFEST_TARGET_QUEUE_BINDING')
            need(not self.ledger.admission_fault(self.t), 'SCIENCE_OWNER_SHARED_FAULT')
        self.root=private_dir(directory,create=True)
        need(not any(self.root.iterdir()),'SCIENCE_OWNER_NEW_PRIVATE_ROOT')
        # No CLI release is published: caller must wire these exact clock
        # bindings into ORIGINAL router before ALLOW_CLI, plus native tool proof.
        self.relay,self.gate,self.cas,self.queue=relay,gate,cas,final_queue
        self.http=http_server;self.http_binding_sha=http_server.listener_identity_sha256
        self.setting=setting;self.graph=copy.deepcopy(graph);self.graph_sha=expected_graph_sha256
        self.roles=canonical;self.pins=copy.deepcopy(pins);self.refs=registered_refs
        self.pins_sha=digest(self.pins);self.roles_sha=digest({r:{k:str(v) for k,v in row.items()} for r,row in canonical.items()})
        self.mounts={str(p):(p.stat().st_dev,p.stat().st_ino,p.stat().st_uid,p.stat().st_gid) for p in paths}
        self.native_terminal=relay.tool_terminal_port;self.backup_callable=backup_ports
        self.member_cap=member_cap;self.backup_ports=backup_ports;self.fence=team.writer_fence
        self.lock=threading.RLock();self.state='PREPARED';self.cut=None;self.ref=None
        self.parent=None;self.stage=None;self.points=[];self.step_in_progress=False
        self.projection=NativeBudgetParkProjection(gate,self.t,self.root/'budget-clock')
        self._event('NATIVE_SCIENTIFIC_OWNER_PREPARED',{'roles':len(team.roles),
                    'service_graph_sha256':self.graph_sha,'registered_refs_sha256':digest(list(self.refs)),
                    'cli_released':False,'native_tool_terminal_binding_qualified_here':False})
    def _event(self,kind,value):
        with self.ledger.tx():self.ledger.event(self.t,kind,value)
    def start(self):
        with self.lock:
            need(self.state=='PREPARED','SCIENCE_OWNER_START_ONCE')
            self._shared()
            need(self.http.started and self.http.serving.is_set()
                 and not self.http.listener_stopped and not self.http.loop_finished.is_set()
                 and not self.http.lifecycle_storage_unknown,
                 'SCIENCE_OWNER_ORIGINAL_HTTP_MUST_BE_READY_BEFORE_CLOCK')
            self.projection.start();self.state='RUNNING'
            self._event('NATIVE_SCIENTIFIC_OWNER_CLOCK_LIVE',{'cli_released':False})
            return {r:self.projection.metadata(r) for r in self.team.roles}
    def status(self):
        with self.lock:
            f=self.ledger.frontier(self.t)
            return {'trajectory':self.t,'owner_state':self.state,'generation':f['generation'],
                    'ledger_state':f['state'],'search_tokens':f['actual'],
                    'reserved':f['reserved'],'unresolved':f['unresolved'],
                    'active_operations':f['active_operations'],'points':copy.deepcopy(self.points),
                    'new_model_dispatches_by_supervisor':0,'cold_continuation_supported':False}
    def _shared(self):
        need(not self.ledger.admission_fault(self.t),'SCIENCE_OWNER_SHARED_FAULT')
        need(self.team.writer_fence is self.fence and self.fence.owner is self.team
             and not self.team.closed and self.relay.ledger.admission_gate is self.gate,
             'SCIENCE_OWNER_ORIGINAL_RUNTIME_BINDINGS_CHANGED')
        self.http.current()
        need(self.http.engine is self.relay and self.http.gate is self.gate
             and self.http.listener_identity_sha256==self.http_binding_sha
             and {r for t,r in self.http.registered if t==self.t}==set(self.team.roles)
             and not self.http.lifecycle_storage_unknown,
             'SCIENCE_OWNER_ORIGINAL_HTTP_BINDING_CHANGED')
        validate_graph(self.graph,self.graph_sha)
        need(digest(self.pins)==self.pins_sha and digest({r:{k:str(v) for k,v in row.items()} for r,row in self.roles.items()})==self.roles_sha,
             'SCIENCE_OWNER_FROZEN_INPUT_BINDINGS_CHANGED')
        for name,identity in self.mounts.items():
            p=Path(name);st=p.lstat()
            need(p.resolve()==p and p.is_dir() and (st.st_dev,st.st_ino,st.st_uid,st.st_gid)==identity,
                 'SCIENCE_OWNER_ORIGINAL_MOUNT_REPLACED')
        need(self.relay.tool_terminal_port is self.native_terminal and self.backup_ports is self.backup_callable
             and self.relay.ledger.global_cap==self.gate.global_cap,
             'SCIENCE_OWNER_TRUSTED_PORT_REBOUND')
    def _point(self):
        # Only immutable committed snapshots feed original candidate collection.
        # Never read a live candidate, task, evaluator output or model text for
        # management; those bytes stay private to the qualified original ports.
        expected=self.ledger.frontier(self.t)
        nm=getattr(self,'_r16_natural_stop',None)
        active_natural=nm is not None and nm['generation']==expected['generation']
        home=self.root/(('point-natural-' if active_natural else 'point-')+str(self.cut.cut['target_tokens']))
        home.mkdir(mode=0o700)
        exports=self.exports
        collection=collect(self.cas,self.ref,home/'collection',expected=expected,
                           member_cap=self.member_cap,git_exports=exports,registered_refs=self.refs)
        inputs=build(self.cas,self.ref,collection,home/'v21',expected=expected,setting=self.setting)
        ids=self.queue.enqueue(home/'v21',policy_sha256=inputs['input_policy_sha256'],
                               trajectory=self.t,setting=self.setting)
        need(len(ids)==3 and len(set(ids))==3,'SCIENCE_OWNER_EXACT_K3_QUEUE')
        point={'generation':expected['generation'],'target_tokens':expected['target'],
               'snapshot':copy.deepcopy(self.ref),'input_policy_sha256':inputs['input_policy_sha256'],
               'jobs':ids,'final_completed':False}
        if active_natural:point.update(point_kind='NATURAL_STOP',natural_stop=copy.deepcopy(nm),report_label='自然停止点 @ 实际 token',budget_accounting={'actual_budget_tokens':expected['actual'],'measured_search_tokens':expected['measured_actual'],'unknown_reservation_charge':expected['unknown_reservation_charge']})
        publish(home/'POINT_QUEUED.json',wire(point),mode=0o400)
        self.points.append(point)
        self._event('NATIVE_SCIENTIFIC_POINT_K3_QUEUED',point)
    def step(self):
        with self.lock:
            need(not self.step_in_progress,'SCIENCE_OWNER_REENTRANT_STEP')
            need(self.state in ('RUNNING','PARKING','PARKED','COMMITTED','POINT_QUEUED','RELEASING','FINAL_PARKED'), 'SCIENCE_OWNER_NOT_ACTIVE')
            self.step_in_progress=True
            try:
                self._shared()
                if self.state=='FINAL_PARKED':return self.status()
                if self.state=='RUNNING':
                    f=self.ledger.frontier(self.t)
                    if f['state']=='RUNNING':return self.status()
                    need(f['state']=='DRAINING','SCIENCE_OWNER_UNEXPECTED_LEDGER_STATE')
                    # User-authorized logical custody downgrade. Whole-team
                    # freeze still proves snapshot consistency. Actual model
                    # reservations/UNKNOWN and real bridge operations must drain.
                    if self.fence.whole_team is not None and not getattr(self.ledger,'native_unmanaged_cli',False):
                        for role in f['roles']:
                            self.ledger.audit_role_tools((self.t,role),f['generation'],
                                'TOOL_CUSTODY_PENDING_AT_WHOLE_TEAM_CUT')
                        f=self.ledger.frontier(self.t)
                    # Never freeze accepted model/business work or turn UNKNOWN
                    # into a synthetic terminal just to reach zero.
                    # turn UNKNOWN into a synthetic terminal just to reach zero.
                    if f['unresolved'] or f['reserved'] or f['active_operations']:return self.status()
                    if not self.http.trajectory_park_ready(self.t)['safe_to_park_writers']:return self.status()
                    # Ledger terminal can precede the accepted handler's final
                    # write/close. Observe ordinary control drain as WAITING,
                    # not a started freeze attempt/fault, replay or socket kill.
                    if self.fence.whole_team is None:
                        for row in self.team._stage_registry:
                            need(isinstance(row.listener.server,NativeAcceptedControls),
                                 'SCIENCE_OWNER_ORIGINAL_CONTROL_KEEPER_REQUIRED')
                            if row.listener.server.control_snapshot()['active']:return self.status()
                        bridge=getattr(self.team,'bridge_backup',None)
                        if bridge is not None and not bridge.controls_ready():return self.status()
                    # Whole-team mode freezes workers, SDKs AND all backends;
                    # idle accepted connections do not need to be closed/proven.
                    # Ledger ACTIVE/UNKNOWN are still never invented terminal.
                    self.cut=NativeServiceCut(self.ledger,self.cas,self.t,self.graph,self.graph_sha,
                                              writer_owner=self.team)
                    self.fence.request_park(self.cut);self.state='PARKING'
                    return self.status()
                if self.state=='PARKING':
                    if not self.fence.poll_park():return self.status()
                    self.state='PARKED';return self.status()
                if self.state=='PARKED':
                    self.state='BACKUP_STARTED'
                    dest=self.root/('backup-'+str(self.cut.cut['generation']));dest.mkdir(mode=0o700)
                    receipt=self.backup_ports(self.cut,dest)
                    self._shared();self.cut.current({'DRAINING'})
                    need(type(receipt) is dict and set(receipt)=={'git_exports'},
                         'SCIENCE_OWNER_NATIVE_BACKUP_RETURN_FIELDS')
                    need(type(receipt['git_exports']) is list and len(receipt['git_exports'])==len(self.refs)
                         and {r.get('ref') for r in receipt['git_exports']}==set(self.refs),
                         'SCIENCE_OWNER_NATIVE_GIT_EXPORTS_COMPLETE')
                    # No callbacks can substitute another owner/cut or weaken
                    # the exact full-native-service receipt checks.
                    need(set(self.cut.receipts)==SERVICES,'SCIENCE_OWNER_ALL_NATIVE_BACKUPS_REQUIRED')
                    self.exports=copy.deepcopy(receipt['git_exports'])
                    pins={**self.pins,'native_writer_fence':self.fence.receipt['sha256'],
                          'gitea_exports':digest({'registered_refs':list(self.refs),'exports':self.exports})}
                    nm=getattr(self,'_r16_natural_stop',None)
                    if nm is not None and nm['generation']==self.cut.cut['generation']:
                        pins.update(natural_stop_policy=nm['policy_sha256'],natural_stop_point=digest(nm))
                    self.ref=self.cut.capture(roles=self.roles,pins=pins,parent=self.parent)
                    self.state='COMMITTED';return self.status()
                if self.state=='COMMITTED':
                    self.state='POINT_STARTED';self._point();self.state='POINT_QUEUED'
                    return self.status()
                if self.state=='POINT_QUEUED':
                    a=self.ledger.account(self.t)
                    if a['stage']+1==len(json.loads(a['targets'])):
                        # Search remains parked. FINAL children are independent;
                        # stop/retirement is EXPLICIT, not a hidden third stage.
                        self.state='FINAL_PARKED';self.gate.notify();return self.status()
                    self.stage=NativeStageBinding(self.cas,self.ref,self.ledger,self.t)
                    self.fence.request_release(self.stage,self.gate)
                    self.state='RELEASING';return self.status()
                if self.state=='RELEASING':
                    if not self.fence.poll_release():return self.status()
                    self.parent=copy.deepcopy(self.ref);self.fence=self.fence.next_cut()
                    self.cut=None;self.ref=None;self.stage=None;self.state='RUNNING'
                    return self.status()
                need(False,'SCIENCE_OWNER_STARTED_OPERATION_CANNOT_RETRY')
            except BaseException:
                self.state='FAULT'
                self.ledger.latch_fault(self.t,'NATIVE_SCIENTIFIC_OWNER_FAILED_RETAIN_NO_RETRY')
                self.gate.notify()
                raise
            finally:self.step_in_progress=False
    def request_final_retirement_thaw(self):
        with self.lock:
            need(self.state=='FINAL_PARKED','SCIENCE_OWNER_RETIREMENT_ONLY_AFTER_FINAL_POINT')
            try:
                self._shared();self.fence.request_final_retirement_thaw()
                self.state='RETIRING';self.gate.notify()
            except BaseException:
                self.state='FAULT';self.ledger.latch_fault(self.t,'NATIVE_SCIENCE_RETIREMENT_FAILED_NO_RETRY');raise
    def poll_final_retirement_thaw(self):
        with self.lock:
            need(self.state=='RETIRING','SCIENCE_OWNER_ORIGINAL_RETIREMENT_HANDLE')
            try:
                self._shared()
                if not self.fence.poll_final_retirement_thaw():return False
                self.state='RETIRED_WRITERS'
                # Actual CLI/archive shutdown stays OPS-owned. No destroy,
                # signal, automatic SDK-close or queue cancellation here.
                self.projection.close();return True
            except BaseException:
                self.state='FAULT';self.ledger.latch_fault(self.t,'NATIVE_SCIENCE_RETIREMENT_PROOF_FAILED_NO_RETRY');raise
    def close(self):
        with self.lock:
            need(self.state=='RETIRED_WRITERS' and self.team.closed,
                 'SCIENCE_OWNER_NATIVE_TEAM_MUST_RETIRE_FIRST')
            # Other trajectories may still use this shared original listener.
            # Never close/recreate it or declare CLI OBSERVED from an HTTP write.
            h=self.http.status()
            need(not any(r['trajectory']==self.t for r in
                         h['active_http_handlers']+h['retained_http_metadata']),
                 'SCIENCE_OWNER_HTTP_REQUEST_CUSTODY_MUST_DRAIN')
            self.projection.close();self.state='CLOSED'
