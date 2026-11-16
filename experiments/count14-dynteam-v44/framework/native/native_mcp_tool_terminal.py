"""Original settled model TOOL -> exact original MCP physical-terminal proof.

No ACP/provider call-id equality, worker claim, stdout-only receipt, new tool,
process signal, rerun or guessed Git/shell parent. This port covers native MCP
business calls only. Shell/Git and nested original CLI physical custody remain
separate required ports before whole-scientific launch.
"""
from dataclasses import asdict
from pathlib import Path
import threading
from common import need, sha, digest, strict, hash_file, Refused
from bridge import process_identity
from native_mcp_bridge import NativeMcpSession
from native_model_tool_parent import NativeModelToolParents

class NativeMcpToolTerminal:
    def __init__(self, parents, sessions):
        need(type(parents)is NativeModelToolParents,'MCP_TOOL_TERMINAL_ORIGINAL_MODEL_INDEX')
        need(type(sessions)is tuple and sessions and all(type(s)is NativeMcpSession for s in sessions),
             'MCP_TOOL_TERMINAL_ORIGINAL_SESSIONS')
        self.parents=parents;self.ledger=parents.ledger;self.sessions={};self.bindings={}
        self.lock=threading.RLock();self.implementation_sha=hash_file(Path(__file__))['sha256']
        for session in sessions:
            i=session.identity;key=(i.trajectory,i.role,i.purpose)
            need(key not in self.sessions and i.purpose in ('gitea','mattermost','board'),
                 'MCP_TOOL_TERMINAL_EXACT_UNIQUE_SESSION')
            need(session.ledger is self.ledger and session.parent_tool_provider is parents,
                 'MCP_TOOL_TERMINAL_SHARED_ORIGINAL_PARENT_PROVIDER')
            self.sessions[key]=session
            self.bindings[key]=(session.scope,session.config_sha,dict(session.process_identity),
                                digest({k:v for k,v in asdict(i).items()if k!='generation'}))
        self.team=None;self.registry=None
    @classmethod
    def from_team(cls, parents, team):
        from native_team_owner import NativeTeamOwner
        need(type(parents)is NativeModelToolParents,'MCP_TOOL_TERMINAL_ORIGINAL_MODEL_INDEX')
        need(type(team)is NativeTeamOwner and team.started and not team.closed
             and team.ledger is parents.ledger and team.parent is parents,
             'MCP_TOOL_TERMINAL_ORIGINAL_STARTED_TEAM')
        need(set(team.sessions)=={(r,p)for r in team.roles for p in ('gitea','mattermost','board')},
             'MCP_TOOL_TERMINAL_COMPLETE_TEAM_ROSTER')
        port=cls(parents,tuple(team.sessions.values()));port.team=team
        need(team._stage_registry is not None,'MCP_TOOL_TERMINAL_ORIGINAL_TEAM_REGISTRY')
        port.registry=tuple((r.role,r.purpose,r.port)for r in team._stage_registry if r.kind=='MCP')
        need({(r,p)for r,p,_ in port.registry}==set(team.sessions)
             and all(team.sessions[(r,p)]is s for r,p,s in port.registry),
             'MCP_TOOL_TERMINAL_COMPLETE_REGISTERED_PORTS')
        return port
    def _current(self, key):
        session=self.sessions[key];scope,config,identity,static=self.bindings[key]
        i=session.identity
        need(self.parents.ledger is self.ledger and session.ledger is self.ledger and session.parent_tool_provider is self.parents
             and (i.trajectory,i.role,i.purpose)==key and session.scope==scope
             and session.config_sha==config and session.process_identity==identity
             and digest({k:v for k,v in asdict(i).items()if k!='generation'})==static,
             'MCP_TOOL_TERMINAL_ORIGINAL_BINDING_REPLACED')
        need(not session.broken and not session.closing and not session.closed
             and session.child.poll()is None and process_identity(session.child.pid)==identity,
             'MCP_TOOL_TERMINAL_ORIGINAL_LIVE_SDK_REQUIRED')
        if self.team is not None:
            need(not self.team.closed and self.team.ledger is self.ledger and self.team.parent is self.parents
                 and self.team.sessions.get((i.role,i.purpose))is session
                 and tuple((r.role,r.purpose,r.port)for r in self.team._stage_registry if r.kind=='MCP')==self.registry,
                 'MCP_TOOL_TERMINAL_TEAM_REGISTRY_CHANGED')
        return session
    def rejected_before_dispatch(self, identity, generation, call_id, operation_id):
        """Exact host rejection; NEVER an MCP physical-terminal receipt.

        Only an original live CLI ticket may mint the durable decision. Ordinary
        missing dispatches, stdout/errors and unrelated scope events remain
        insufficient. Accepted calls still require the original native notice.
        """
        t,role=identity
        with self.lock,self.ledger.mutex:
            self.ledger._identity(t,role,generation)
            need(not self.ledger.admission_fault(t),'MCP_REJECTION_SHARED_FAULT')
            records=[]
            for event in self.ledger.db.execute(
                    "SELECT seq,metadata FROM events WHERE trajectory=?AND kind='NATIVE_MCP_ORIGINAL_TOOL_PREDISPATCH_REJECTED' ORDER BY seq",(t,)):
                value=strict(event['metadata'])
                if value.get('operation_id')==operation_id:records.append((event['seq'],value))
            if not records:return None
            need(len(records)==1,'MCP_REJECTION_ONE_EXACT_HOST_DECISION')
            sequence,meta=records[0]
            row=self.ledger.db.execute("""SELECT p.*,s.ticket,o.state,o.kind,o.parent FROM native_model_tool_parents p
                JOIN native_cli_tool_starts s ON s.operation_id=p.operation_id
                JOIN operations o ON o.id=p.operation_id JOIN requests r ON r.id=p.request_id
                WHERE p.trajectory=?AND p.role=?AND p.call_id=?AND p.operation_id=?
                AND s.trajectory=p.trajectory AND s.role=p.role AND s.generation=p.generation
                AND s.request_id=p.request_id AND s.call_id=p.call_id
                AND o.trajectory=p.trajectory AND o.role=p.role AND o.generation=p.generation
                AND r.trajectory=p.trajectory AND r.role=p.role AND r.generation=p.generation
                AND r.state='SETTLED'AND o.parent=p.request_id""",(*identity,call_id,operation_id)).fetchone()
            need(row is not None and row['kind']=='TOOL'and row['state']in('ACTIVE','COMPLETE')
                 and row['generation']<=generation,'MCP_REJECTION_EXACT_ORIGINAL_MODEL_TOOL')
            purpose,sep,_=row['function_name'].partition('-');key=(t,role,purpose)
            need(sep and key in self.sessions,'MCP_REJECTION_REGISTERED_NATIVE_SESSION')
            session=self._current(key)
            need(session.identity.generation==generation,'MCP_REJECTION_CURRENT_NATIVE_GENERATION')
            need(not session.pending,'MCP_REJECTION_NO_PENDING_NATIVE_ACTIVITY')
            from native_cli_tool_receipt import NativeCliToolReceipts
            cli=self.parents.cli_receipts
            need(type(cli)is NativeCliToolReceipts and cli.parents is self.parents and cli.ledger is self.ledger,
                 'MCP_REJECTION_ORIGINAL_CLI_SERVICE')
            callback=cli.callback_receipt(identity,call_id,operation_id)
            need(callback['generation']==row['generation'],'MCP_REJECTION_ORIGINAL_RETURN_GENERATION')
            need(callback['mode']=='CALLBACK'and callback['outcome']=='RETURN','MCP_REJECTION_ORIGINAL_RETURN_REQUIRED')
            fields={'schema','scope','role','generation','operation_id','cli_ticket_sha256',
                    'configuration_sha256','native_process_identity_sha256','rejection_kind',
                    'code','request_sha256','response_sha256','native_bytes_sent'}
            need(set(meta)==fields and meta['schema']=='agensh-original-mcp-predispatch-rejection-v1'
                 and meta['scope']==session.scope and meta['role']==role and meta['generation']==row['generation']
                 and meta['operation_id']==operation_id and meta['cli_ticket_sha256']==digest(row['ticket'])
                 and meta['configuration_sha256']==session.config_sha
                 and meta['native_process_identity_sha256']==digest(session.process_identity)
                 and meta['rejection_kind']in('MCP_SCOPE_REJECTED_BEFORE_DISPATCH','MCP_ARGUMENT_REJECTED_BEFORE_DISPATCH')
                 and type(meta['code'])is str and 0<len(meta['code'])<=160 and meta['native_bytes_sent']is False,
                 'MCP_REJECTION_EXACT_HOST_SCOPE_AND_TICKET')
            sha(meta['request_sha256']);sha(meta['response_sha256'])
            need(self.ledger.db.execute('SELECT COUNT(*)FROM operations WHERE parent=?',(operation_id,)).fetchone()[0]==0,
                 'MCP_REJECTION_NO_ACCEPTED_BUSINESS_CHILDREN')
            return {'decision_sequence':sequence,'decision_sha256':digest(meta),
                    'native_session_scope':session.scope,'code':meta['code'],
                    'response_sha256':meta['response_sha256'],'native_execution_not_claimed':True}

    def __call__(self, identity, generation, call_id, operation_id):
        need(type(identity)is tuple and len(identity)==2,'MCP_TOOL_TERMINAL_HOST_IDENTITY')
        t,role=identity
        with self.lock,self.ledger.mutex:
            self.ledger._identity(t,role,generation)
            need(not self.ledger.admission_fault(t),'MCP_TOOL_TERMINAL_SHARED_FAULT')
            row=self.ledger.db.execute('''SELECT p.*,o.state,o.kind,o.parent FROM native_model_tool_parents p
                JOIN operations o ON o.id=p.operation_id JOIN requests r ON r.id=p.request_id
                WHERE p.trajectory=? AND p.role=? AND p.call_id=? AND p.operation_id=?
                AND o.trajectory=p.trajectory AND o.role=p.role AND o.generation=p.generation
                AND r.trajectory=p.trajectory AND r.role=p.role AND r.generation=p.generation
                AND r.state='SETTLED' AND o.parent=p.request_id''',(*identity,call_id,operation_id)).fetchone()
            need(row is not None and row['kind']=='TOOL'and row['state']in ('ACTIVE','COMPLETE')
                 and type(row['generation'])is int and row['generation']<=generation,
                 'MCP_TOOL_TERMINAL_EXACT_SETTLED_ORIGINAL_TOOL')
            cli_callback=None
            if self.parents.cli_receipts is not None:
                from native_cli_tool_receipt import NativeCliToolReceipts
                cli=self.parents.cli_receipts
                need(type(cli)is NativeCliToolReceipts and cli.parents is self.parents and cli.ledger is self.ledger,
                     'MCP_TOOL_TERMINAL_ORIGINAL_CLI_SERVICE')
                cli_callback=cli.callback_receipt(identity,call_id,operation_id)
                need(cli_callback['generation']==row['generation'],
                     'MCP_TOOL_TERMINAL_ORIGINAL_CLI_CALLBACK_GENERATION')
                need(cli_callback['mode']=='CALLBACK'and cli_callback['outcome']=='RETURN',
                     'MCP_TOOL_TERMINAL_ORIGINAL_CLI_CALLBACK_NOT_RETURNED')
            purpose,separator,_=row['function_name'].partition('-');key=(t,role,purpose)
            need(separator and key in self.sessions,
                 'MCP_TOOL_TERMINAL_NOT_A_REGISTERED_NATIVE_MCP_NO_SHELL_GUESS')
            session=self._current(key)
            need(session.identity.generation==generation,'MCP_TOOL_TERMINAL_CURRENT_NATIVE_GENERATION')
            children=self.ledger.db.execute('SELECT * FROM operations WHERE parent=?ORDER BY id',(operation_id,)).fetchall()
            need(len(children)==1,'MCP_TOOL_TERMINAL_ONE_EXACT_BUSINESS_DISPATCH_REQUIRED')
            child=children[0]
            need((child['trajectory'],child['role'],child['generation'])==(t,role,row['generation'])
                 and child['kind']in ('GIT_READ','GIT_WRITE','CHAT_READ','CHAT_WRITE'),
                 'MCP_TOOL_TERMINAL_ORIGINAL_BRIDGE_SCOPE')
            need(child['state']=='COMPLETE','MCP_TOOL_TERMINAL_ORIGINAL_BRIDGE_NOT_PHYSICALLY_COMPLETE')
            records=[]
            for event in self.ledger.db.execute("SELECT seq,metadata FROM events WHERE trajectory=? AND kind='MCP_OPERATION_PHYSICAL_TERMINAL' ORDER BY seq",(t,)):
                meta=strict(event['metadata'])
                if meta.get('operation_id')==child['id']:records.append((event['seq'],meta))
            need(len(records)==1,'MCP_TOOL_TERMINAL_EXACT_NATIVE_PHYSICAL_RECEIPT_REQUIRED')
            sequence,meta=records[0]
            need(set(meta)=={'scope','operation_id','method','response_sha256'}
                 and meta['scope']==session.scope and meta['method']=='tools/call',
                 'MCP_TOOL_TERMINAL_ORIGINAL_SDK_RECEIPT_SCOPE')
            sha(meta['response_sha256'])
            proof={'trajectory':t,'role':role,'source_generation':row['generation'],
                   'request_id':row['request_id'],'call_id':call_id,'operation_id':operation_id,
                   'bridge_operation_id':child['id'],'native_session_scope':session.scope,
                   'native_terminal_sequence':sequence,'response_sha256':meta['response_sha256'],
                   'implementation_sha256':self.implementation_sha}
            if cli_callback is not None:proof['cli_callback_receipt_sha256']=cli_callback['receipt_sha256']
            receipt_sha=digest(proof)
            old=[]
            for event in self.ledger.db.execute("SELECT metadata FROM events WHERE trajectory=? AND kind='NATIVE_MCP_MODEL_TOOL_TERMINAL_VERIFIED'",(t,)):
                value=strict(event[0])
                if value.get('operation_id')==operation_id:old.append(value)
            need(len(old)<=1 and (not old or old[0]=={**proof,'receipt_sha256':receipt_sha}),
                 'MCP_TOOL_TERMINAL_CONFLICTING_REPLAY_RECEIPT')
            if not old:
                need(row['state']=='ACTIVE','MCP_TOOL_TERMINAL_NO_RETROACTIVE_TERMINAL_CLAIM')
                try:
                    with self.ledger.tx():self.ledger.event(t,'NATIVE_MCP_MODEL_TOOL_TERMINAL_VERIFIED',{**proof,'receipt_sha256':receipt_sha})
                except Exception:
                    self.ledger.latch_fault(t,'MCP_TOOL_TERMINAL_PROOF_STORAGE_UNKNOWN')
                    raise Refused('MCP_TOOL_TERMINAL_PROOF_STORAGE_UNKNOWN')from None
            # The original ScientificRelay, not this proof port, ends the TOOL.
            # Original operation_end still forbids newly ACTIVE bridge children.
            return {'trajectory':t,'role':role,'generation':generation,'call_id':call_id,
                    'operation_id':operation_id,'physical_terminal':True,'receipt_sha256':receipt_sha}
