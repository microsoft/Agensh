"""Actual same-owner dynamic snapshot -> ORIGINAL collection/FINAL queue.

Original Git exports, physical frozen roots, continuation/usage SQLite backups,
CAS capture, collector, v2.1 input selection and K=3 enqueue are used directly.
Only the native CLI control topology has a new producer; no legacy SDK state is
invented. Each action has one retained handle, no automatic prefix replay.
"""
from pathlib import Path
import copy
import dataclasses
import json

from common import need,digest,wire,publish,private_dir,hash_file
from budget import SERVICES
from collector import collect
from native_dynamic_writer import DynamicCutWriter
from native_git_repository_backup import NativeGitRepositoryBackup, repository_binding
from native_relay_backup import NativeRelayContinuationBackup
from native_whole_team import NativeWholeTeamPhysicalBackup


class DynamicCheckpointPorts:
    def __init__(self,core,trajectory,*,scope,source_ports,pins,registered_refs=('refs/heads/main',),member_cap=1000000):
        from smoke_checkpoint_final_scope import SmokeCheckpointFinalScope
        from smoke_bootstrap_task_ports import NewRootSourceTaskPorts
        need(isinstance(scope,SmokeCheckpointFinalScope) and type(source_ports) is NewRootSourceTaskPorts and
             source_ports.core is core and scope.sha==digest(core.contract),
             'DYNTEAM_CHECKPOINT_EXACT_SAME_CORE_SCOPE_AND_SOURCE_PORTS')
        need(trajectory in core.rows and core.rows[trajectory]['arm']=='DYNTEAM' and
             trajectory in core.gate.startup_held and not core.qualification_only,
             'DYNTEAM_CHECKPOINT_BASELINE_SMOKE_FIRST_BEFORE_MODEL_RELEASE')
        self.core,self.ledger,self.t,self.scope=core,core.ledger,trajectory,scope
        self.pins=copy.deepcopy(pins);self.refs=registered_refs;self.member_cap=member_cap
        need(self.pins.get('manifest')==scope.sha,'DYNTEAM_CHECKPOINT_CANONICAL_CONTRACT_PIN')
        if not hasattr(core.cas,'_smoke_scope_sha256'):self.scope.bind_cas(core.cas)
        if not hasattr(core.queue,'_smoke_scope_sha256'):scope.bind_queue(core.queue)
        record=source_ports.rows[trajectory]
        need(record['state']=='SOURCE_TASK_CHANNEL_READY','DYNTEAM_CHECKPOINT_REAL_SOURCE_PUBLICATION_REQUIRED')
        publisher=record['publisher']
        layout=core.native_layout.current(trajectory)
        # Native Gitea's complete physical data mount, never an old experiment.
        repository=Path(layout['profile_root'])/'gitea'/'git'/'repositories'/layout['org']/'main.git'
        binding=repository_binding(repository,publisher.binding.service_instance_sha256)
        self.git=NativeGitRepositoryBackup(publisher,repository,registered_refs=self.refs,
            expected_repository_binding_sha256=digest(binding),
            expected_publication_pin=hash_file(publisher.home/'gitea-publication.json'))
        self.relay=NativeRelayContinuationBackup(core.engines[trajectory],core.servers[trajectory],trajectory)
        self.state='BOUND_MODELS_HELD';self.writer=None;self.points=[];self.parent=None
        self.executions={};self.sequence=0
        if not hasattr(core,'smoke_checkpoint_ports'):core.smoke_checkpoint_ports={}
        need(trajectory not in core.smoke_checkpoint_ports,'DYNTEAM_ONE_ORIGINAL_CHECKPOINT_PORT_PER_TRAJECTORY')
        core.smoke_checkpoint_ports[trajectory]=self

    def preflight(self):
        """Real current kernel/domain/mount readiness, NOT a mock freeze proof."""
        from bridge import process_identity
        from native_writer_fence import process_cgroup_v2
        import os
        view=DynamicCutWriter.__new__(DynamicCutWriter)
        view.core=self.core;view.ledger=self.ledger;view.t=self.t
        view.row=copy.deepcopy(self.core.rows[self.t]);view.roles=sorted(view.row['roles'])
        rows=view._inventory()
        need({'gitea','mattermost'} < set(rows),'DYNTEAM_PREFLIGHT_ALL_REAL_NATIVE_BACKENDS')
        owner_domain=process_cgroup_v2(process_identity(os.getpid()))
        domains=[]
        for row in rows.values():
            domain=Path('/sys/fs/cgroup')/row['domain'].lstrip('/')
            need(not owner_domain.is_relative_to(Path(row['domain'])) and
                 (domain/'cgroup.type').read_text().strip()=='domain' and
                 (domain/'cgroup.freeze').read_text().strip()=='0',
                 'DYNTEAM_PREFLIGHT_PRIVATE_RUNNING_WRITABLE_WRITER_DOMAIN')
            need(os.access(domain/'cgroup.freeze',os.W_OK),
                 'DYNTEAM_PREFLIGHT_ORIGINAL_FREEZER_WRITE_ACCESS_REQUIRED')
            domains.append(row['domain'])
        need(len(domains)==len(set(domains)), 'DYNTEAM_PREFLIGHT_DISTINCT_CONTAINER_DOMAINS')
        self.preflight_inventory=digest(rows)
        return {'state':'REAL_NATIVE_WRITER_LAYOUT_CHECKED_NOT_FROZEN',
                'containers':len(rows),'registered_roles':len(view.roles),
                'inventory_sha256':self.preflight_inventory,'models_released':False}

    def _begin_cut(self):
        f=self.ledger.frontier(self.t);self.sequence=f['generation']
        need(f['state']=='DRAINING' and f['reserved']==f['unresolved']==f['active_operations']==0,
             'DYNTEAM_CHECKPOINT_NATURAL_MODEL_DRAIN_REQUIRED')
        self.writer=DynamicCutWriter(self.core,self.t)
        whole=self.writer.whole_team
        self.gitea_physical=NativeWholeTeamPhysicalBackup(whole,component='gitea_database',service_names=('gitea',))
        self.collaboration=NativeWholeTeamPhysicalBackup(whole,component='collaboration',
            service_names=('mattermost',*whole.backends))
        from native_dynamic_writer import _function
        for port in (self.gitea_physical,self.collaboration):
            from types import MethodType
            port.run=MethodType(_function(NativeWholeTeamPhysicalBackup.run,
                registered_runtime_sockets=self._native_runtime_sockets),port)
        self.bridge_protocol={'schema':'count14-dynteam-native-control-backup-v1',
                              'implementation':hash_file(Path(__file__))['sha256']}
        self.bridge_domain={'instance_sha256':digest({'contract':self.scope.sha,'trajectory':self.t,
            'owner':self.writer.owner_identity}), 'backup_protocol_sha256':digest(self.bridge_protocol),
            'objects':['bridge_journal','candidate_manifest']}
        graph={'gitea':self.git.graph_domain,'gitea_database':self.gitea_physical.graph_domain,
            'collaboration':self.collaboration.graph_domain,'relay_continuation':self.relay.graph_domain,
            'bridge':self.bridge_domain}
        self.writer.request_park(graph)
        self.state='PARKING'

    def _bridge_control(self):
        core=self.core
        with self.ledger.mutex:
            roles={r:v for (t,r),v in core.roles.births.items() if t==self.t}
            held=sorted(r for t,r in core.roles.held if t==self.t)
            epoch=core.roles.epoch
        sessions=core.sessions.tracks[self.t]
        with sessions._lock:
            affinity={r:list(value) for (t,r),value in sessions._current.items() if t==self.t}
        clis={r:{k:(dataclasses.asdict(v) if dataclasses.is_dataclass(v) else v)
                  for k,v in row.items()} for (t,r),row in core.bridge_owner.clis.items() if t==self.t}
        spawn=core.spawn_owner.checkpoint_control_state()
        spawn={'next_ordinals':{self.t:spawn['next_ordinals'][self.t]},
               'used_slots':{self.t:spawn['used_slots'][self.t]},
               'effects':[r for r in spawn['effects'] if r['trajectory_id']==self.t]}
        return {'schema':'count14-native-same-live-control-v1','role_gate_epoch':epoch,
            'role_births':roles,'held_roles':held,'session_affinity':affinity,'native_clis':clis,
            'spawn':spawn,
            'membership':self.writer.membership_token,
            'same_live_continuation_only':True,'cold_SDK_restore_claimed':False}

    def _native_runtime_sockets(self,registration):
        import stat
        need(registration is self.writer.whole_team,
             'DYNTEAM_REGISTERED_ACP_SOCKETS_SAME_REAL_INVENTORY')
        registration.frozen(self.writer.writer_fence)
        layout=self.core.native_layout.current(self.t);result={}
        # Fixed original beta ACP listener path only; no directory traversal,
        # arbitrary socket exclusion or suppressing unknown special files.
        for row in layout['roles'].values():
            path=Path(row['acp_root'])/'agent.sock'
            try:s=path.lstat()
            except FileNotFoundError:continue # a dormant original slot
            need(path.resolve()==path and stat.S_ISSOCK(s.st_mode),
                 'DYNTEAM_EXACT_ORIGINAL_NATIVE_ACP_SOCKET')
            result[str(path)]=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_mtime_ns)
        original=self.core.control.path.lstat()
        need(stat.S_ISSOCK(original.st_mode),'DYNTEAM_ORIGINAL_CONTROL_LISTENER_IS_SOCKET')
        exports=self.core.cold_native_exports['trajectories'][self.t]['role_exports']
        for role in self.core.rows[self.t]['roles']:
            for name in ('agent_control_directory','router_control_directory'):
                path=Path(exports[role][name])/'native-control.sock';s=path.lstat()
                need(path.resolve()==path and stat.S_ISSOCK(s.st_mode) and
                     (s.st_dev,s.st_ino,s.st_uid,s.st_mode)==
                     (original.st_dev,original.st_ino,original.st_uid,original.st_mode),
                     'DYNTEAM_REGISTERED_CONTROL_EXPORT_SAME_ORIGINAL_SOCKET_INODE')
                result[str(path)]=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_mtime_ns)
        return result

    def _bridge(self,destination,exports):
        cut=self.writer.cut;self.writer.writer_fence.verify_capture(cut,self.writer.role_sources)
        need(set(cut.receipts)==SERVICES-{'bridge'},'DYNTEAM_BRIDGE_BACKUP_ORDER')
        before=self._bridge_control();dest=private_dir(destination,create=True)
        sources={n:private_dir(dest/n,create=True) for n in self.bridge_domain['objects']}
        # Opaque actual original ledger backup, not rewritten financial rows.
        self.ledger.backup(sources['bridge_journal']/'bridge.sqlite')
        publish(sources['bridge_journal']/'NATIVE_CONTROL.json',wire(before))
        role_objects={r:{k:cut.cas.capture_tree(p) for k,p in row.items()}
                      for r,row in sorted(self.writer.role_sources.items())}
        from native_bridge_backup import backup_protocol
        protocol=backup_protocol()
        exports_sha=digest({'registered_refs':list(self.refs),'exports':exports})
        inputs={'schema':'agensh-frozen-candidate-INPUT-source-manifest-v1',
            'cut_sha256':cut.cut_sha,'writer_fence_receipt':self.writer.writer_fence.receipt,
            'roles':role_objects,'registered_refs':list(self.refs),'git_exports':copy.deepcopy(exports),
            'gitea_exports_sha256':exports_sha,'gitea_service_receipt':copy.deepcopy(cut.receipts['gitea']),
            'gitea_repo_object':copy.deepcopy(cut.packed['gitea_repo']),
            'collector_sha256':protocol['implementations']['collector.py'],
            'candidate_policy_sha256':protocol['implementations']['native_candidate_policy.py'],
            'member_cap':self.member_cap,'candidate_selection_applied':False,
            'collection_only_after_original_snapshot_COMMITTED':True}
        publish(sources['candidate_manifest']/'INPUTS.json',wire(inputs))
        need(before==self._bridge_control(),'DYNTEAM_NATIVE_CONTROL_CHANGED_DURING_FROZEN_BACKUP')
        receipt={'schema':'count14-native-control-consistent-backup-v1','cut_sha256':cut.cut_sha,
                 'native_control_sha256':digest(before),'candidate_INPUT_sha256':digest(inputs),
                 'bridge_database':hash_file(sources['bridge_journal']/'bridge.sqlite'),
                 'original_model_requests_replayed':False,'legacy_SDK_state_fabricated':False}
        reference=cut.cas.store_bytes(wire(receipt))
        return cut.record_native_backup('bridge',sources,{'cut_sha256':cut.cut_sha,
            'instance_sha256':self.bridge_domain['instance_sha256'],
            'backup_protocol_sha256':self.bridge_domain['backup_protocol_sha256'],
            'receipt_sha256':reference['sha256']})

    def _note_prepark(self, code, frontier, *, membership=None, http=None):
        old=getattr(self,'prepark_wait',{})
        counts=dict(old.get('reason_counts',{}))
        counts[code]=counts.get(code,0)+1
        self.prepark_wait=dict(reason_code=code,reason_counts=counts,
            generation=frontier['generation'],unresolved=frontier['unresolved'],
            reserved=frontier['reserved'],active_operations=frontier['active_operations'],
            membership=copy.deepcopy(membership),http=copy.deepcopy(http),
            native_END=self.core.bridge_owner.prepark_public(self.t),
            lifecycle_storage_unknown=self.core.servers[self.t].lifecycle_storage_unknown)

    def step(self):
        """Poll-only original handles. Failure retains exact prefix and domains."""
        try:
            if self.state=='BOUND_MODELS_HELD':
                need(self.t not in self.core.gate.startup_held,'DYNTEAM_CHECKPOINT_START_AFTER_ACTUAL_RELEASE')
                self.state='RUNNING'
            if self.state=='RUNNING':
                f=self.ledger.frontier(self.t)
                if f['state']=='RUNNING':return self.public()
                need(f['state']=='DRAINING','DYNTEAM_CHECKPOINT_EXPECTS_ORIGINAL_DRAINING_FRONTIER')
                epochs=getattr(self.core,'native_sdk_startup_epochs',None)
                if epochs is not None and epochs.reconnect.pending_trajectory(self.t):
                    # Do not request the cut fence mid reconnect: original END
                    # and genuinely new BIRTH must still acquire their normal
                    # leases. No freeze/capture until the new session is bound.
                    self._note_prepark('WAIT_SESSION_RECONNECT',f)
                    return self.public()
                if self.core.bridge_owner.prepark_pending(self.t):
                    self._note_prepark('WAIT_NATIVE_END_TRANSITION',f)
                    return self.public()
                membership=self.core.membership_fences[self.t]
                counts=membership.public_counts()
                if counts['pending_native_effects']:
                    self._note_prepark('WAIT_NATIVE_MEMBERSHIP_EFFECTS',f,membership=counts)
                    return self.public()
                membership.request_cut(f['generation'])
                if f['unresolved'] or f['reserved'] or f['active_operations']:
                    self._note_prepark('WAIT_ORIGINAL_MODEL_OR_TOOL_ROWS',f,membership=counts)
                    return self.public()
                http=self.core.servers[self.t]
                ready=http.trajectory_park_ready(self.t)
                if not ready['safe_to_park_writers'] or http.lifecycle_storage_unknown:
                    self._note_prepark('WAIT_ORIGINAL_HTTP_PHYSICAL_DRAIN',f,membership=counts,http=ready)
                    return self.public() # SETTLED is not the final physical HTTP write/close
                self._note_prepark('BEGIN_ORIGINAL_CUT',f,membership=counts,http=ready)
                self._begin_cut();return self.public()
            if self.state=='PARKING':
                if not self.writer.poll_park():return self.public()
                self.state='PARKED';return self.public()
            if self.state=='PARKED':
                home=Path(self.core.rows[self.t]['root'])/'checkpoints'/('generation-'+str(self.sequence))
                home=private_dir(home,create=True);cut=self.writer.cut
                # Each receipt is retained immediately; step is never silently
                # called on this phase again after any exception/partial.
                exports=self.git.run(cut,home/'git')['git_exports']
                self.gitea_physical.run(cut,home/'gitea-physical')
                self.collaboration.run(cut,home/'collaboration-physical')
                self.relay.run(cut,home/'relay',roles=self.writer.role_sources)
                self._bridge(home/'bridge',exports)
                pins={**self.pins,'gitea_exports':digest({'registered_refs':list(self.refs),'exports':exports})}
                self.reference=self.writer.capture(scope=self.scope,pins=pins,parent=self.parent)
                self.exports=exports;self.home=home;self.state='COMMITTED';return self.public()
            if self.state=='COMMITTED':
                self.state='COLLECTION_STARTED'
                expected=self.ledger.frontier(self.t)
                collection=collect(self.core.cas,self.reference,self.home/'collection',expected=expected,
                    member_cap=self.member_cap,git_exports=self.exports,registered_refs=self.refs)
                inputs=self.scope.build(self.core.cas,self.reference,collection,self.home/'v21',
                    expected=expected,setting=self.core.rows[self.t]['arm'])
                jobs=self.core.queue.enqueue(self.home/'v21',policy_sha256=inputs['input_policy_sha256'],
                    trajectory=self.t,setting=self.core.rows[self.t]['arm'])
                need(len(jobs)==len(set(jobs))==3,'DYNTEAM_CHECKPOINT_ORIGINAL_EXACT_K3')
                self.points.append({'generation':self.sequence,'target_tokens':expected['target'],
                    'snapshot':copy.deepcopy(self.reference),'jobs':jobs,'input_policy_sha256':inputs['input_policy_sha256']})
                self.state='POINT_QUEUED';return self.public()
            if self.state=='POINT_QUEUED':
                account=self.ledger.account(self.t)
                if account['stage']+1==len(json.loads(account['targets'])):
                    self.state='FINAL_PARKED';return self.public()
                self.writer.request_same_live_resume();self.state='RELEASING';return self.public()
            if self.state=='RELEASING' and self.writer.poll_same_live_resume():
                self.parent=self.reference;self.writer=None;self.state='RUNNING'
            return self.public()
        except Exception as error:
            phase=self.state;self.state='PARTIAL_RETAINED_NO_RETRY'
            self.failure={'exception_type':type(error).__name__,'phase':phase,'locations':[]}
            tb=error.__traceback__
            while tb:
                self.failure['locations'].append({'file':tb.tb_frame.f_code.co_filename,
                    'line':tb.tb_lineno,'function':tb.tb_frame.f_code.co_name});tb=tb.tb_next
            raise

    def public(self):
        return {'state':self.state,'trajectory':self.t,'points':copy.deepcopy(self.points),
                'failure':getattr(self,'failure',None),'legacy_SDK_restore_claimed':False,
                'native_END':self.core.bridge_owner.prepark_public(self.t),
                'prepark_wait':copy.deepcopy(getattr(self,'prepark_wait',None))}
