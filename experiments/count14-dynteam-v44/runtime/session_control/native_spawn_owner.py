"""Same original owner admits native membership effects, never models.

The original shell still consumes original accepted-CLAIM counts and performs
its original launches. Effects are fenced/durable before launch; actual bridge
birth proves completion. Unknown/failed launches remain held, never replayed.
"""
from common import need,digest
from native_spawn_protocol import checked_spawn


class NativeSpawnOwner:
    def __init__(self,core):
        self.core=core;self.next={t:1 for t in core.rows};self.used={t:{1} for t in core.rows}
        self.history={};self.operations={};self.retirement_jobs={}

    def read(self,t):
        value=self.core.active_clock.read(t)
        return dict(status=value['mode'],active_seconds=value['active_ns']//10**9,operation_id='0'*32)

    def _control_seconds(self,t):
        # Completion/drain of an ALREADY admitted effect must not depend on a
        # fresh timer/health gate. This is only the last observed counter, not
        # RUNNING permission; new BEGIN still requires read()'s valid clock.
        return self.core.active_clock.states[t]['active_ns']//10**9

    def begin(self,t,slot,ordinal,reuse):
        need(t in self.core.rows and type(slot) is int and 1<=slot<=32 and type(ordinal) is int and ordinal>=1 and
             type(reuse) is bool,'DYNTEAM_NATIVE_SPAWN_EXACT_ROLE_ORDINAL')
        old=self.operations.get((t,ordinal))
        if old is not None:
            need(old['slot']==slot and old['reuse']==reuse,'DYNTEAM_NATIVE_SPAWN_IDENTITY_CONFLICT')
            return dict(status='DONE' if old['committed'] else 'RETAINED',active_seconds=self._control_seconds(t),
                        operation_id=old['lease'].operation_id)
        value=self.read(t)
        if value['status']!='RUNNING':return {**value,'status':'HOLD' if value['status']!='FINAL' else 'FINAL'}
        need(ordinal==self.next[t],'DYNTEAM_ORIGINAL_SPAWN_ORDINAL_NO_SKIP_OR_REPLAY')
        role='worker-'+str(slot-1).zfill(2);key=t,role
        need((reuse and len(self.used[t])==32 and slot in self.used[t]) or
             (not reuse and slot==len(self.used[t])+1 and slot not in self.used[t]),
             'DYNTEAM_ORIGINAL_UNUSED_THEN_ROUND_ROBIN_NATIVE_SLOTS')
        if reuse:
            cli=getattr(self.core,'bridge_owner',None)
            cli=None if cli is None else cli.clis.get(key)
            if (cli is None or not cli['archived'] or key in self.core.bridge_owner.logical or
                    not self.core.native_physical_projection(t,role)['models_clear'] or
                    not self.core.native_physical_projection(t,role)['tools_clear']):
                return {**value,'status':'HOLD'}
        resources=getattr(self.core,'cohort_resources',None)
        if resources is not None and not resources.reserve_native_launch(key):return {**value,'status':'HOLD'}
        lease=self.core.membership_fences[t].acquire(role,'BIRTH')
        if lease is None:
            if resources is not None:resources.defer_unadmitted_launch(key)
            return {**value,'status':'HOLD'}
        operation=dict(lease=lease,slot=slot,reuse=reuse,committed=False,birth_observed=False)
        # If this durable intent fails, the acquired fence stays held. Do not
        # silently retry/launch after a partially observed control write.
        with self.core.ledger.tx():
            self.core.ledger.event(t,'DYNTEAM_NATIVE_SPAWN_INTENT',dict(worker_slot=slot,spawn_ordinal=ordinal,
                operation_id=lease.operation_id,reuse=reuse,models=0))
        self.operations[t,ordinal]=operation
        self.core.pending_native_launches[key]=operation
        return dict(status='ALLOW',active_seconds=value['active_seconds'],operation_id=lease.operation_id)

    def finish(self,t,slot,ordinal,operation_id,succeeded):
        operation=self.operations.get((t,ordinal));role='worker-'+str(slot-1).zfill(2);key=t,role
        need(operation is not None and operation['slot']==slot and operation['lease'].operation_id==operation_id and
             type(succeeded) is bool,'DYNTEAM_NATIVE_FINISH_EXACT_ADMITTED_EFFECT')
        if operation['committed']:return dict(status='DONE',active_seconds=self._control_seconds(t),operation_id=operation_id)
        if not succeeded or not operation['birth_observed']:
            return dict(status='RETAINED',active_seconds=self._control_seconds(t),operation_id=operation_id)
        need(self.core.pending_native_launches.get(key) is operation,'DYNTEAM_NATIVE_FINISH_ORIGINAL_LEASE')
        proof=digest(['NATIVE_SPAWN_FINISHED',t,slot,ordinal,operation['native_cli_token_sha256']])
        with self.core.ledger.tx():
            self.core.ledger.event(t,'DYNTEAM_NATIVE_SPAWN_COMMITTED',dict(worker_slot=slot,spawn_ordinal=ordinal,
                operation_id=operation_id,native_birth_receipt_sha256=proof,models_replayed=0))
        self.core.membership_fences[t].finish(operation['lease'],original_control_receipt_sha256=proof)
        operation['committed']=True;self.used[t].add(slot);self.next[t]=ordinal+1
        del self.core.pending_native_launches[key]
        resources=getattr(self.core,'cohort_resources',None)
        if resources is not None:resources.finish_native_launch(key)
        return dict(status='DONE',active_seconds=self._control_seconds(t),operation_id=operation_id)

    def handle(self,row,peer):
        checked_spawn(row)
        need(self.core.peers.validate(row,peer),'DYNTEAM_NATIVE_SPAWN_REGISTERED_LAUNCHER_CHILD_REQUIRED')
        t=row['trajectory_id']
        if row['event']=='READ':return self.read(t)
        if row['event']=='BEGIN':return self.begin(t,row['worker_slot'],row['spawn_ordinal'],row['reuse'])
        if row['event'] in ('RETIRE_BEGIN','RETIRE_POLL'):
            return self.retire(t,row['worker_slot'],row['spawn_ordinal'],row['operation_id'],row['container_ids'])
        return self.finish(t,row['worker_slot'],row['spawn_ordinal'],row['operation_id'],row['succeeded'])

    def retire(self,t,slot,ordinal,operation_id,cids):
        operation=self.operations.get((t,ordinal))
        need(operation is not None and operation['slot']==slot and operation['reuse'] and not operation['committed'] and
             operation['lease'].operation_id==operation_id and hasattr(self.core,'native_containers'),
             'DYNTEAM_RETIRE_SAME_ORIGINAL_NATIVE_REUSE_OPERATION')
        job=self.retirement_jobs.get(operation_id)
        if job is None:
            if not cids:return dict(status='RETAINED',active_seconds=self._control_seconds(t),operation_id=operation_id)
            home=self.core.home/'native-retirement-public';home.mkdir(mode=0o700,exist_ok=True)
            job=self.core.native_containers.new_job(t,'worker-'+str(slot-1).zfill(2),operation_id,cids,home/operation_id)
            self.retirement_jobs[operation_id]=job
        elif cids:
            need(set(cids)=={b.cid for b in job.bindings},'DYNTEAM_REPEATED_RETIRE_BEGIN_EXACT_CIDS_ONLY')
        return dict(status=job.step(),active_seconds=self._control_seconds(t),operation_id=operation_id)

    def checkpoint_control_state(self):
        return dict(next_ordinals=dict(self.next),used_slots={t:sorted(s) for t,s in self.used.items()},
            effects=[dict(trajectory_id=t,spawn_ordinal=n,worker_slot=v['slot'],reuse=v['reuse'],
                operation_id=v['lease'].operation_id,committed=v['committed'],birth_observed=v['birth_observed'])
                for (t,n),v in sorted(self.operations.items())])
