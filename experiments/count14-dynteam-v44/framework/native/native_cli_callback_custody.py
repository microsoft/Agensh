"""Original CLI callback terminal AND retained full kernel writer custody.

An asynchronous native shell callback can genuinely return while its command or
persistent descendants are still running. This port NEVER labels those writers
physically terminal. It proves the exact original native callback returned and
keeps the original pre-exec all-writer cgroup domain mandatory for every later
checkpoint. Existing MCP and accepted Git physical terminals remain independent.
No wrapper changes native tool result/command/prompt/capability or background flow.
"""
from pathlib import Path
import copy,os,threading
from common import need,digest,sha,hash_file,strict,Refused
from bridge import process_identity
from native_bridge_backup import NativeBridgeBackup
from native_cli_tool_receipt import NativeCliToolReceipts,cli_peer
from native_mcp_tool_terminal import NativeMcpToolTerminal
from native_model_tool_parent import NativeModelToolParents
from native_team_owner import NativeTeamOwner
from native_writer_fence import NativeWriterFence

SCOPE='ORIGINAL_CLI_CALLBACK_TERMINAL_WITH_RETAINED_WRITER_DOMAIN'
FIELDS=frozenset(('trajectory','role','generation','call_id','operation_id','terminal_scope',
                  'writer_custody_sha256','receipt_sha256'))

def registered_custody(ledger,trajectory):
    """Durable obligation + exact live host object; missing registry is NOT opt-out."""
    with ledger.mutex:
        rows=ledger.db.execute("SELECT metadata FROM events WHERE trajectory=?AND kind='NATIVE_CLI_CALLBACK_WRITER_CUSTODY_BOUND'",(trajectory,)).fetchall()
        registry=getattr(ledger,'native_cli_callback_custody',{})
        need(type(registry)is dict,'CLI_CALLBACK_CUSTODY_ORIGINAL_REGISTRY')
        port=registry.get(trajectory)
        if not rows:
            need(port is None,'CLI_CALLBACK_CUSTODY_UNRECORDED_BINDING');return None
        need(len(rows)==1 and type(port)is NativeCliCallbackCustody
             and port.ledger is ledger and port.t==trajectory
             and strict(rows[0][0])=={'binding_sha256':port.binding_sha,'terminal_scope':SCOPE}
             and digest(port.binding)==port.binding_sha,
             'CLI_CALLBACK_CUSTODY_REGISTERED_ORIGINAL_BINDING_REQUIRED')
        return port

class NativeCliCallbackCustody:
    def __init__(self,team,parents,receipts,mcp_terminal):
        need(type(team)is NativeTeamOwner and team.started and not team.closed,
             'CLI_CALLBACK_CUSTODY_ORIGINAL_STARTED_TEAM')
        need(type(parents)is NativeModelToolParents and team.parent is parents
             and type(receipts)is NativeCliToolReceipts and receipts.parents is parents
             and parents.cli_receipts is receipts and receipts.ledger is team.ledger,
             'CLI_CALLBACK_CUSTODY_ORIGINAL_PARENT_RECEIPT_SERVICE')
        need(type(mcp_terminal)is NativeMcpToolTerminal and mcp_terminal.team is team
             and mcp_terminal.parents is parents,'CLI_CALLBACK_CUSTODY_ORIGINAL_MCP_TERMINAL')
        need(getattr(team,'cli_callback_custody',None)is None,'CLI_CALLBACK_CUSTODY_BIND_ONCE')
        bridge=getattr(team,'bridge_backup',None);fence=team.writer_fence
        need(type(bridge)is NativeBridgeBackup and bridge.owner is team and bridge.receipts is receipts
             and type(fence)is NativeWriterFence and fence.owner is team,
             'CLI_CALLBACK_CUSTODY_ORIGINAL_BRIDGE_AND_WRITER_DOMAINS')
        self.team=team;self.parents=parents;self.receipts=receipts;self.mcp=mcp_terminal
        self.bridge=bridge;self.ledger=team.ledger;self.t=team.t;self.lock=threading.RLock()
        with self.ledger.mutex:
            f=self.ledger.frontier(self.t)
            need(f['state']=='RUNNING'and f['generation']==1
                 and self.ledger.db.execute('SELECT COUNT(*)FROM requests WHERE trajectory=?',(self.t,)).fetchone()[0]==0,
                 'CLI_CALLBACK_CUSTODY_BEFORE_FIRST_MODEL')
        self.registry=team._stage_registry;self.roles=tuple(team.roles)
        self.domains=fence.domains;self.domains_sha=fence.domains_sha
        self.participants=copy.deepcopy(fence.participants);self.peers=copy.deepcopy(bridge.cli_peers)
        self.process=process_identity(os.getpid())
        root=Path(__file__).resolve().parent
        self.implementations={n:hash_file(root/n)['sha256']for n in
            ('native_cli_callback_custody.py','native_cli_tool_receipt.py','native_cli_tool_overlay.py',
             'native_mcp_tool_terminal.py','native_writer_fence.py','native_model_tool_parent.py')}
        self.binding={'schema':'agensh-original-cli-callback-retained-writer-binding-v1',
                      'trajectory':self.t,'roles':list(self.roles),'domains_sha256':self.domains_sha,
                      'participants_sha256':digest(self.participants),
                      'cli_peer_sha256':{r:digest(p)for r,p in self.peers.items()},
                      'implementations':self.implementations,'terminal_scope':SCOPE,
                      'descendant_terminal_not_claimed':True}
        self.binding_sha=digest(self.binding)
        with self.ledger.mutex:
            need(registered_custody(self.ledger,self.t)is None,'CLI_CALLBACK_CUSTODY_LEDGER_BIND_ONCE')
            registry=getattr(self.ledger,'native_cli_callback_custody',None)
            if registry is None:
                registry={};self.ledger.native_cli_callback_custody=registry
            registry[self.t]=self;team.cli_callback_custody=self
        try:
            with self.ledger.tx():self.ledger.event(self.t,'NATIVE_CLI_CALLBACK_WRITER_CUSTODY_BOUND',
                {'binding_sha256':self.binding_sha,'terminal_scope':SCOPE})
            self._current(self.roles[0],1)
        except BaseException:
            self.ledger.latch_fault(self.t,'CLI_CALLBACK_CUSTODY_STARTUP_UNKNOWN_RETAIN');raise
    def _current(self,role,generation):
        need(registered_custody(self.ledger,self.t)is self and self.team.cli_callback_custody is self and self.team.started and not self.team.closed
             and self.team.parent is self.parents and self.parents.cli_receipts is self.receipts
             and self.team.bridge_backup is self.bridge and self.bridge.receipts is self.receipts
             and self.team._stage_registry is self.registry and tuple(self.team.roles)==self.roles
             and process_identity(self.process['pid'])==self.process,
             'CLI_CALLBACK_CUSTODY_ORIGINAL_RUNTIME_CHANGED')
        self.ledger._identity(self.t,role,generation)
        need(not self.ledger.admission_fault(self.t),'CLI_CALLBACK_CUSTODY_SHARED_FAULT')
        f=self.team.writer_fence
        need(type(f)is NativeWriterFence and f.owner is self.team and f.domains==self.domains
             and f.domains_sha==self.domains_sha and f.participants==self.participants,
             'CLI_CALLBACK_CUSTODY_ORIGINAL_WRITER_BINDING_CHANGED')
        # Full trusted pre-exec domain coverage, NOT PPid/PGID or claimed child
        # emptiness. Persistent/future descendants stay in these same domains.
        f._coverage()
        p=self.peers[role]
        need(self.receipts.peers.get((self.t,role))==p and self.bridge.cli_peers.get(role)==p
             and cli_peer(p['pid'])==p,'CLI_CALLBACK_CUSTODY_ORIGINAL_CLI_PEER_CHANGED')
        kernel={k:p[k]for k in('pid','start_ticks','boot_id')}
        matches=[d.binding_sha for d in self.domains if d.contains(kernel)]
        need(len(matches)==1,'CLI_CALLBACK_CUSTODY_CLI_IN_EXACT_ORIGINAL_DOMAIN')
        source=self.bridge.cli_servers[role]
        need(source.receipts is self.receipts and source.identity==(self.t,role)
             and source.thread is self.bridge.cli_threads[role]
             and self.bridge._cli_listener(role)==self.bridge.cli_bindings[role],
             'CLI_CALLBACK_CUSTODY_ORIGINAL_CLI_LISTENER_CHANGED')
        # Other trajectories/roles may be active; no global empty-callback or
        # all-listener drain barrier is introduced in ordinary model progress.
        return {'schema':'agensh-original-cli-callback-retained-writer-proof-v1',
                'binding_sha256':self.binding_sha,'role':role,'peer_sha256':digest(p),
                'domain_binding_sha256':matches[0],'all_writer_domains_sha256':self.domains_sha,
                'all_writer_participants_sha256':digest(self.participants),
                'descendants_physically_terminal':False,'original_cut_full_freezer_required':True}
    def verify_capture(self,cut,roles,pins):
        """Callback closure never substitutes for the full original kernel park."""
        from native_service_cut import NativeServiceCut
        with self.lock,self.ledger.mutex:
            need(type(cut)is NativeServiceCut and cut.ledger is self.ledger and cut.t==self.t
                 and cut.callback_custody is self and cut.writer_owner is self.team
                 and cut.writer_fence is self.team.writer_fence
                 and cut.bridge_backup is self.bridge,
                 'CLI_CALLBACK_CUSTODY_CAPTURE_ORIGINAL_CUT_REQUIRED')
            generation=cut.cut['generation']
            for role in self.roles:self._current(role,generation)
            need(type(roles)is dict and set(roles)==set(self.roles)
                 and all(type(roles[r])is dict and set(roles[r])=={'workspace','session'}
                    and all(Path(roles[r][k])==self.bridge.roles[r][k]for k in roles[r])for r in roles),
                 'CLI_CALLBACK_CUSTODY_CAPTURE_ORIGINAL_ALL_ROOTS')
            cut.current({'DRAINING','CAPTURING'})
            receipt=cut.writer_fence.verify_capture(cut,roles)
            need(pins.get('native_writer_fence')==receipt['sha256'],
                 'CLI_CALLBACK_CUSTODY_CAPTURE_FULL_WRITER_PIN_REQUIRED')
            return receipt
    def _git_children(self,row,callback):
        children=self.ledger.db.execute('SELECT * FROM operations WHERE parent=?ORDER BY id',(row['operation_id'],)).fetchall()
        if callback['mode']=='NATIVE_PLAN_NO_EXECUTION':
            need(not children,'CLI_CALLBACK_CUSTODY_NOEXEC_WITH_BUSINESS_CHILD');return []
        proof=[];broker=self.team.git[row['role']]
        for child in children:
            need((child['trajectory'],child['role'],child['generation'])==(self.t,row['role'],row['generation'])
                 and child['kind']in('GIT_READ','GIT_WRITE'),
                 'CLI_CALLBACK_CUSTODY_ACCEPTED_BUSINESS_CHILD_SCOPE')
            need(child['state']=='COMPLETE','CLI_CALLBACK_CUSTODY_ACCEPTED_BUSINESS_CHILD_NOT_TERMINAL')
            values=[]
            for event in self.ledger.db.execute("SELECT seq,metadata FROM events WHERE trajectory=?AND kind='NATIVE_GIT_HTTP_PHYSICAL_TERMINAL'ORDER BY seq",(self.t,)):
                value=strict(event['metadata'])
                if value.get('operation_id')==child['id']:values.append((event['seq'],value))
            need(len(values)==1,'CLI_CALLBACK_CUSTODY_EXACT_NATIVE_GIT_TERMINAL_REQUIRED')
            seq,value=values[0]
            need(set(value)=={'scope','operation_id','status','response_sha256','bytes'}
                 and value['scope']==broker.scope and type(value['status'])is int and 100<=value['status']<=599
                 and type(value['bytes'])is int and value['bytes']>=0,
                 'CLI_CALLBACK_CUSTODY_NATIVE_GIT_TERMINAL_SCOPE')
            sha(value['response_sha256']);proof.append({'operation_id':child['id'],'sequence':seq,
                'native_scope':broker.scope,'response_sha256':value['response_sha256']})
        return proof
    def __call__(self,identity,generation,call_id,operation_id):
        need(type(identity)is tuple and len(identity)==2 and identity[0]==self.t,
             'CLI_CALLBACK_CUSTODY_EXACT_HOST_ROLE')
        _,role=identity
        with self.lock,self.ledger.mutex:
            writer=self._current(role,generation)
            row=self.ledger.db.execute('''SELECT p.*,o.state,o.kind,o.parent FROM native_model_tool_parents p
                JOIN operations o ON o.id=p.operation_id JOIN requests r ON r.id=p.request_id
                WHERE p.trajectory=?AND p.role=?AND p.call_id=?AND p.operation_id=?
                AND o.trajectory=p.trajectory AND o.role=p.role AND o.generation=p.generation
                AND r.trajectory=p.trajectory AND r.role=p.role AND r.generation=p.generation
                AND r.state='SETTLED'AND o.parent=p.request_id''',(*identity,call_id,operation_id)).fetchone()
            need(row is not None and row['kind']=='TOOL'and row['state']in('ACTIVE','COMPLETE')
                 and type(row['generation'])is int and row['generation']<=generation,
                 'CLI_CALLBACK_CUSTODY_EXACT_SETTLED_ORIGINAL_TOOL')
            callback=self.receipts.callback_receipt(identity,call_id,operation_id)
            need(callback['generation']==row['generation']and callback['peer_sha256']==writer['peer_sha256'],
                 'CLI_CALLBACK_CUSTODY_EXACT_NATIVE_CALLBACK_IDENTITY')
            need((callback['mode']=='CALLBACK'and callback['outcome']in('RETURN','THROW'))or
                 (callback['mode']=='NATIVE_PLAN_NO_EXECUTION'and callback['outcome']=='NATIVE_PLAN_NO_EXECUTION'),
                 'CLI_CALLBACK_CUSTODY_EXACT_NATIVE_CALLBACK_RETURN')
            purpose,sep,_=row['function_name'].partition('-')
            rejection=None
            if callback['mode']=='CALLBACK'and sep and (self.t,role,purpose)in self.mcp.sessions:
                rejection=self.mcp.rejected_before_dispatch(identity,generation,call_id,operation_id)
                if rejection is None:
                    # Accepted native calls still require original notice/protocol
                    # physical terminal. Missing dispatch alone proves nothing.
                    return self.mcp(identity,generation,call_id,operation_id)
            need(callback['mode']=='NATIVE_PLAN_NO_EXECUTION'or row['function_name']not in('task','list_agents'),
                 'CLI_CALLBACK_CUSTODY_ORIGINAL_EXCLUDED_TOOL_NOT_ENABLED')
            children=self._git_children(row,callback)
            # Callbacks and full writer-domain custody are distinct claims. No
            # assertion that an async command, daemon or detached writer exited.
            proof={'schema':'agensh-original-cli-callback-custody-terminal-v1','terminal_scope':SCOPE,
                   'trajectory':self.t,'role':role,'source_generation':row['generation'],
                   'request_id':row['request_id'],'call_id':call_id,'operation_id':operation_id,
                   'callback_receipt_sha256':callback['receipt_sha256'],
                   'callback_mode':callback['mode'],'callback_outcome':callback['outcome'],
                   'writer_custody':writer,'accepted_git_physical_terminals':children}
            if rejection is not None:proof['mcp_predispatch_rejection']=rejection
            receipt_sha=digest(proof);old=[]
            for event in self.ledger.db.execute("SELECT metadata FROM events WHERE trajectory=?AND kind='NATIVE_CLI_CALLBACK_WRITER_CUSTODY_VERIFIED'",(self.t,)):
                value=strict(event[0])
                if value.get('operation_id')==operation_id:old.append(value)
            need(len(old)<=1 and (not old or old[0]=={**proof,'receipt_sha256':receipt_sha}),
                 'CLI_CALLBACK_CUSTODY_CONFLICTING_REPLAY')
            if not old:
                need(row['state']=='ACTIVE','CLI_CALLBACK_CUSTODY_NO_RETROACTIVE_PROOF')
                try:
                    with self.ledger.tx():self.ledger.event(self.t,'NATIVE_CLI_CALLBACK_WRITER_CUSTODY_VERIFIED',
                                                          {**proof,'receipt_sha256':receipt_sha})
                except BaseException:
                    self.ledger.latch_fault(self.t,'CLI_CALLBACK_CUSTODY_PROOF_STORAGE_UNKNOWN');raise
            return {'trajectory':self.t,'role':role,'generation':generation,'call_id':call_id,
                    'operation_id':operation_id,'terminal_scope':SCOPE,
                    'writer_custody_sha256':digest(writer),'receipt_sha256':receipt_sha}
    def validate_relay_receipt(self,receipt,identity,generation,call_id,operation_id):
        need(type(receipt)is dict and set(receipt)==FIELDS and receipt['terminal_scope']==SCOPE,
             'CLI_CALLBACK_CUSTODY_DISTINCT_RECEIPT_SCOPE')
        need((receipt['trajectory'],receipt['role'])==identity and type(receipt['generation'])is int
             and receipt['generation']==generation and receipt['call_id']==call_id
             and receipt['operation_id']==operation_id,'CLI_CALLBACK_CUSTODY_RELAY_EXACT_IDENTITY')
        with self.lock,self.ledger.mutex:
            writer=self._current(identity[1],generation)
            need(receipt['writer_custody_sha256']==digest(writer),'CLI_CALLBACK_CUSTODY_FRESH_WRITER_PROOF')
            sha(receipt['receipt_sha256'])
            rows=[strict(r[0])for r in self.ledger.db.execute("SELECT metadata FROM events WHERE trajectory=?AND kind='NATIVE_CLI_CALLBACK_WRITER_CUSTODY_VERIFIED'",(self.t,))]
            found=[v for v in rows if v.get('operation_id')==operation_id]
            need(len(found)==1 and found[0]['receipt_sha256']==receipt['receipt_sha256'],
                 'CLI_CALLBACK_CUSTODY_RECORDED_ORIGINAL_RECEIPT')
            body={k:v for k,v in found[0].items()if k!='receipt_sha256'}
            need(digest(body)==receipt['receipt_sha256']and body['writer_custody']==writer,
                 'CLI_CALLBACK_CUSTODY_RECORDED_BODY_SHA')
            if 'mcp_predispatch_rejection'in body:
                need(self.mcp.rejected_before_dispatch(identity,generation,call_id,operation_id)==body['mcp_predispatch_rejection'],
                     'CLI_CALLBACK_CUSTODY_FRESH_MCP_REJECTION')
