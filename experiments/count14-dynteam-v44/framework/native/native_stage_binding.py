"""Advance live collaboration ports only after a verified committed snapshot.

This does not prove CLI/tool/process quiescence. Preparing ports never releases
model admission; resume_team invokes the existing AdmissionGate only after ALL
registered ports pass same-live preparation. Original native processes, UDS endpoints, capabilities
and session connections remain alive and unchanged; no cold reconstruction.
"""
from contextlib import ExitStack
from dataclasses import dataclass,replace
import json,os,stat
from common import need,sha,digest
from bridge import process_identity
from native_mcp_policy import McpPolicy
from native_control_custody import require_control_drained

@dataclass(frozen=True)
class RegisteredNativePort:
    """Owner-private strong custody references; never worker-authored metadata."""
    kind: str
    role: str
    purpose: str
    port: object
    listener: object
    binding: object
    scope: str
    process: tuple
    policy_spec: str | None
    scope_guard: object
    listener_identity: tuple


def _policy_spec(policy):
    return digest({'tools':policy.tools,'deny':sorted(policy.deny),'rules':policy.rules,
                   'guard':None if policy.scope_guard is None else policy.scope_guard.pin})


def _listener_identity(listener):
    s=listener.path.lstat()
    need(stat.S_ISSOCK(s.st_mode) and not listener.path.is_symlink()
         and listener.path.resolve()==listener.path and s.st_ino==listener.inode,
         'NATIVE_STAGE_LISTENER_PATH_CHANGED')
    need(listener.thread is not None and listener.thread.is_alive()
         and listener.server.socket.fileno()>=0,'NATIVE_STAGE_LISTENER_NOT_SAME_LIVE')
    return (s.st_dev,s.st_ino,os.fstat(listener.server.socket.fileno()).st_ino,listener.thread)


def register_native_team_ports(owner):
    """Called once by original team startup after all real listeners started.

    The registry pins original object/process/listener identity, not a current
    roster reconstructed at checkpoint. It contains no backup/freeze claim.
    """
    from native_mcp_config import PURPOSES
    need(owner._stage_registry is None,'NATIVE_STAGE_REGISTER_ONCE')
    rows=[]
    for role in owner.roles:
        for purpose in PURPOSES:
            port=owner.sessions[(role,purpose)]
            listener=next(s for s in owner.listeners if getattr(s,'session',None)is port)
            rows.append(RegisteredNativePort('MCP',role,purpose,port,listener,port.identity,
                port.scope,tuple(sorted(port.process_identity.items())),_policy_spec(port.policy),
                port.policy.scope_guard,_listener_identity(listener)))
        port=owner.git[role]
        listener=next(s for s in owner.listeners if getattr(s,'broker',None)is port)
        rows.append(RegisteredNativePort('GIT',role,'git',port,listener,port.binding,
            port.scope,(),None,None,_listener_identity(listener)))
    owner._stage_registry=tuple(rows)
    owner._stage_owner_identity=process_identity(os.getpid())

class NativeStageBinding:
    def __init__(self,cas,reference,ledger,trajectory):
        self.ledger=ledger;self.trajectory=trajectory
        with ledger.mutex:
            need(not ledger.admission_fault(trajectory),'NATIVE_STAGE_FAULT_NO_ADVANCE')
            f=ledger.frontier(trajectory);need(f['state']=='COMMITTED_PARKED','NATIVE_STAGE_COMMITTED_PARK_REQUIRED')
            self.ref=sha(reference['sha256']);row=ledger.db.execute('SELECT ref_sha FROM snapshots WHERE trajectory=? AND generation=?',(trajectory,f['generation'])).fetchone()
            need(row is not None and row[0]==self.ref,'NATIVE_STAGE_COMMIT_REFERENCE')
            a=ledger.account(trajectory);need(a['stage']+1<len(json.loads(a['targets'])),'NATIVE_STAGE_NO_NEXT_AFTER_FINAL')
            # Hash/verify actual sealed objects ONCE, not once per worker/server.
            cas.verify_snapshot(reference,expected=f)
            self.old=f['generation'];self.new=self.old+1;self.manifest=f['manifest_sha256']
        self.changed=set();self.team=None;self.team_attempted=False;self.team_released=False
    def current(self):
        need(not self.ledger.admission_fault(self.trajectory),'NATIVE_STAGE_FAULT_NO_ADVANCE')
        f=self.ledger.frontier(self.trajectory)
        need(f['state']=='COMMITTED_PARKED'and f['generation']==self.old and f['manifest_sha256']==self.manifest,'NATIVE_STAGE_TRANSITION_NO_LONGER_PARKED')
        row=self.ledger.db.execute('SELECT ref_sha FROM snapshots WHERE trajectory=? AND generation=?',(self.trajectory,self.old)).fetchone()
        need(row is not None and row[0]==self.ref,'NATIVE_STAGE_COMMIT_CHANGED')
    def record(self,kind,metadata):
        with self.ledger.tx():self.ledger.event(self.trajectory,kind,{'old_generation':self.old,'new_generation':self.new,'committed_snapshot_sha256':self.ref,**metadata})
    def advance_mcp(self,session):
        with session.lock,self.ledger.mutex:
            self.current();need(session.ledger is self.ledger and session.identity.trajectory==self.trajectory and session.identity.generation==self.old,'NATIVE_STAGE_MCP_SCOPE')
            need((getattr(self.ledger,'native_unmanaged_cli',False) or not session.pending and not session.broken) and not session.closing and not session.closed,'NATIVE_STAGE_MCP_NOT_DRAINED')
            need(session.child.poll()is None and process_identity(session.child.pid)==session.process_identity,'NATIVE_STAGE_MCP_PROCESS_NOT_SAME_LIVE')
            identity=replace(session.identity,generation=self.new)
            policy=McpPolicy(identity,native_tools=session.policy.tools,deny_names=sorted(session.policy.deny),rules=session.policy.rules,scope_guard=session.policy.scope_guard)
            self.record('NATIVE_MCP_GENERATION_ADVANCED',{'process_scope':session.scope,'role':identity.role,'purpose':identity.purpose,'old_policy_sha256':session.policy.sha,'new_policy_sha256':policy.sha})
            session.identity=identity;session.policy=policy;self.changed.add(('MCP',identity.role,identity.purpose))
            return digest({'scope':session.scope,'generation':self.new,'snapshot':self.ref})
    def advance_git(self,broker):
        from native_git_http import NativeGitHttp
        from bridge import Broker
        need(type(broker)in(NativeGitHttp,Broker),'NATIVE_STAGE_GIT_IMPLEMENTATION')
        with broker.lock,self.ledger.mutex:
            self.current();b=broker.binding;need(broker.ledger is self.ledger and b.trajectory==self.trajectory and b.generation==self.old,'NATIVE_STAGE_GIT_SCOPE')
            # Actual team startup uses NativeGitHttp, not legacy local Git's
            # ChildCustodian. Dispatch explicitly; an arbitrary duck-typed
            # object must not supply an empty fake custody map.
            if type(broker)is NativeGitHttp:
                need((getattr(self.ledger,'native_unmanaged_cli',False) or not broker.children) and not broker.closing,'NATIVE_STAGE_GIT_HTTP_STILL_OWNED_OR_CLOSING')
            else:
                need(type(broker)is Broker,'NATIVE_STAGE_GIT_IMPLEMENTATION')
                with broker.custodian.lock:need(not broker.custodian.children,'NATIVE_STAGE_GIT_CHILD_STILL_OWNED')
            need(self.ledger.frontier(self.trajectory)['active_operations']==0,'NATIVE_STAGE_OPERATIONS_STILL_ACTIVE')
            self.record('NATIVE_GIT_GENERATION_ADVANCED',{'role':b.role})
            broker.binding=replace(b,generation=self.new);self.changed.add(('GIT',b.role))

    def _team_locks(self,owner):
        # Same order as original dispatch and graceful owner close. Never wait
        # on a native child/HTTP operation while holding the ledger mutex.
        locks=ExitStack()
        try:
            for row in sorted(owner._stage_registry,key=lambda x:(0 if x.kind=='MCP'else 1,x.role,x.purpose)):
                locks.enter_context(row.port.lock)
            locks.enter_context(self.ledger.mutex)
            return locks
        except BaseException:
            locks.close();raise
    def _team_current(self,owner,generation):
        from native_team_owner import NativeTeamOwner
        from native_mcp_bridge import NativeMcpSession,McpServer
        from native_mcp_config import PURPOSES
        from native_git_http import NativeGitHttp,NativeGitHttpServer
        need(type(owner)is NativeTeamOwner and owner.ledger is self.ledger
             and owner.t==self.trajectory and owner.started and not owner.closed,
             'NATIVE_STAGE_TEAM_OWNER_SCOPE')
        self.current();f=self.ledger.frontier(self.trajectory)
        need(f['reserved']==f['unresolved']==f['active_operations']==0,'NATIVE_STAGE_TEAM_NOT_DRAINED')
        roles=f['roles']
        need(owner.roles==roles and roles==[f'worker-{i:02}'for i in range(len(roles))]
             and len(roles)in(1,2,16),'NATIVE_STAGE_TEAM_CANONICAL_ROSTER')
        need(owner._stage_owner_identity==process_identity(os.getpid()),'NATIVE_STAGE_TEAM_OWNER_NOT_SAME_LIVE')
        expected={(r,p)for r in roles for p in PURPOSES}
        rows=owner._stage_registry
        need(type(rows)is tuple and len(rows)==4*len(roles)
             and {(x.role,x.purpose)for x in rows if x.kind=='MCP'}==expected
             and {x.role for x in rows if x.kind=='GIT'}==set(roles)
             and set(owner.sessions)==expected and set(owner.git)==set(roles)
             and set(owner.configs)==set(roles)
             and len(owner.listeners)==len(rows)
             and {id(x)for x in owner.listeners}=={id(x.listener)for x in rows},
             'NATIVE_STAGE_TEAM_EXACT_REGISTERED_PORTS')
        bridge=getattr(owner,'bridge_backup',None)
        from native_whole_team import frozen_whole_team
        if bridge is not None and not getattr(self.ledger,'native_unmanaged_cli',False) and not frozen_whole_team(owner):
            need(bridge.controls_ready(),'NATIVE_STAGE_CLI_ACCEPTED_CONTROL_NOT_DRAINED')
        for row in rows:
            p,s=row.port,row.listener
            from native_whole_team import frozen_whole_team
            if not getattr(self.ledger,'native_unmanaged_cli',False) and not frozen_whole_team(owner):
                require_control_drained(s,'NATIVE_STAGE_ACCEPTED_CONTROL_NOT_DRAINED')
            need(_listener_identity(s)==row.listener_identity,'NATIVE_STAGE_LISTENER_NOT_SAME_LIVE')
            need(p.ledger is self.ledger and p.scope==row.scope,'NATIVE_STAGE_TEAM_PORT_SCOPE_CHANGED')
            if row.kind=='MCP':
                need(type(p)is NativeMcpSession and type(s)is McpServer and s.session is p
                     and owner.sessions[(row.role,row.purpose)]is p
                     and owner.configs[row.role]['sessions'][row.purpose]is p
                     and owner.configs[row.role]['sockets'][row.purpose]==s.path,
                     'NATIVE_STAGE_TEAM_MCP_REGISTRY_CHANGED')
                need(p.identity==replace(row.binding,generation=generation)
                     and p.policy.identity==p.identity and _policy_spec(p.policy)==row.policy_spec
                     and p.policy.scope_guard is row.scope_guard,'NATIVE_STAGE_TEAM_POLICY_CHANGED')
                need((getattr(self.ledger,'native_unmanaged_cli',False) or not p.pending and not p.broken) and not p.closing and not p.closed,
                     'NATIVE_STAGE_MCP_NOT_DRAINED')
                need(p.child.poll()is None and process_identity(p.child.pid)==dict(row.process)
                     and p.process_identity==dict(row.process),'NATIVE_STAGE_MCP_PROCESS_NOT_SAME_LIVE')
            else:
                need(type(p)is NativeGitHttp and type(s)is NativeGitHttpServer and s.broker is p
                     and owner.git[row.role]is p and owner.configs[row.role]['git_path']==s.path,
                     'NATIVE_STAGE_TEAM_GIT_REGISTRY_CHANGED')
                need(p.binding==replace(row.binding,generation=generation),
                     'NATIVE_STAGE_TEAM_GIT_BINDING_CHANGED')
                need((getattr(self.ledger,'native_unmanaged_cli',False) or not p.children) and not p.closing,'NATIVE_STAGE_GIT_HTTP_STILL_OWNED_OR_CLOSING')
        return rows
    def prepare_team(self,owner):
        """Preflight ALL actual ports, then prepare them without model release.

        A partial commit is retained/faulted, never rolled back or retried.
        Requires a separately valid whole-writer/service snapshot; this method
        does not manufacture either proof from empty native port maps.
        """
        from native_team_owner import NativeTeamOwner
        need(type(owner)is NativeTeamOwner and type(owner._stage_registry)is tuple,
             'NATIVE_STAGE_TEAM_REGISTERED_OWNER_REQUIRED')
        need(not self.team_attempted,'NATIVE_STAGE_TEAM_NO_RETRY')
        self.team_attempted=True
        try:
            with self._team_locks(owner):
                rows=self._team_current(owner,self.old)
                need(not self.changed,'NATIVE_STAGE_TEAM_NO_PRIOR_PARTIAL_ADVANCE')
                # Construct/validate ALL new policies before mutating ANY port.
                prepared={}
                for row in rows:
                    if row.kind=='MCP':
                        p=row.port;identity=replace(p.identity,generation=self.new)
                        policy=McpPolicy(identity,native_tools=p.policy.tools,deny_names=sorted(p.policy.deny),
                            rules=p.policy.rules,scope_guard=p.policy.scope_guard)
                        prepared[(row.role,row.purpose)]=(identity,policy)
                for row in rows:
                    if row.kind=='MCP':
                        p=row.port;identity,policy=prepared[(row.role,row.purpose)]
                        self.record('NATIVE_MCP_GENERATION_ADVANCED',{'process_scope':p.scope,'role':row.role,
                            'purpose':row.purpose,'old_policy_sha256':p.policy.sha,'new_policy_sha256':policy.sha})
                        p.identity=identity;p.policy=policy;self.changed.add(('MCP',row.role,row.purpose))
                    else:self.advance_git(row.port)
                self._team_current(owner,self.new)
                receipt={'schema':'agensh-native-team-stage-prepared-v1','trajectory':self.trajectory,
                         'old_generation':self.old,'new_generation':self.new,'snapshot_sha256':self.ref,
                         'roles':len(owner.roles),'mcp_ports':3*len(owner.roles),'git_ports':len(owner.roles),
                         'model_admission_released':False}
                self.record('NATIVE_TEAM_GENERATION_PREPARED',receipt)
                self.team=owner
                return receipt
        except BaseException:
            self.ledger.latch_fault(self.trajectory,'NATIVE_STAGE_TEAM_PREPARE_FAILED_NO_RETRY');raise
    def resume_team(self,gate,owner):
        """Original AdmissionGate release only after full same-live prepare."""
        from admission_gate import AdmissionGate
        need(self.team is owner and not self.team_released,'NATIVE_STAGE_TEAM_NOT_PREPARED_OR_ALREADY_RELEASED')
        need(type(gate)is AdmissionGate and gate.ledger is self.ledger,'NATIVE_STAGE_TEAM_ORIGINAL_GATE_REQUIRED')
        try:
            with self._team_locks(owner):
                need(not gate.closed,'NATIVE_STAGE_TEAM_ORIGINAL_GATE_CLOSED')
                rows=self._team_current(owner,self.new)
                expected={(x.kind,x.role,x.purpose)if x.kind=='MCP'else('GIT',x.role)for x in rows}
                need(self.changed==expected,'NATIVE_STAGE_TEAM_INCOMPLETE_PREPARE')
                self.record('NATIVE_TEAM_MODEL_RELEASE_REQUESTED',{'registered_ports':len(rows)})
                result=gate.resume_next(self.trajectory,verified_snapshot_sha256=self.ref)
                self.team_released=True
                return result
        except BaseException:
            self.ledger.latch_fault(self.trajectory,'NATIVE_STAGE_TEAM_RELEASE_FAILED_NO_RETRY');raise
