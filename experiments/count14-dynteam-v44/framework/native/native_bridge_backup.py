"""Original live bridge metadata backup + frozen candidate INPUT provenance.

This produces actual bridge_journal/candidate_manifest objects, not caller ACKs.
It does NOT collect/select candidates, assert Gitea/MM scientific async drain,
prove a detached shell terminal, or invent Git/shell parent attribution. The
unchanged collector runs only AFTER original snapshot COMMITTED. No payloads,
credentials, native exception messages or worker-selected paths are published.
"""
from contextlib import ExitStack
from dataclasses import asdict,replace
from pathlib import Path
import copy,json,os,re,stat,threading
from common import need,sha,digest,wire,strict,private_dir,publish,sync_dir,hash_file,Refused,integer
from bridge import process_identity
from budget import SERVICES
from native_cli_tool_receipt import NativeCliToolReceipts,NativeCliToolServer,cli_peer
from native_control_custody import NativeAcceptedControls,require_control_drained
from native_model_tool_parent import NativeModelToolParents
from native_stage_binding import _listener_identity,_policy_spec
from native_team_owner import NativeTeamOwner
from native_writer_fence import NativeWriterFence
from native_service_cut import NativeServiceCut

COMPONENT='bridge'
OBJECTS=frozenset(('bridge_journal','candidate_manifest'))
FILES=('native_bridge_backup.py','native_cli_tool_receipt.py','native_control_custody.py',
       'native_model_tool_parent.py','native_stage_binding.py','native_team_owner.py',
       'native_mcp_bridge.py','native_git_http.py','native_writer_fence.py',
       'native_service_cut.py','snapshot.py','collector.py','native_candidate_policy.py',
       'native_inert_archive.py','common.py','budget.py')


def backup_protocol():
    root=Path(__file__).resolve().parent
    return {'schema':'agensh-original-bridge-backup-protocol-v1',
            'implementations':{n:hash_file(root/n)['sha256']for n in FILES},
            'ledger_backup':'original-SQLite-backup-api-not-hot-db-wal-copy',
            'candidate_manifest':'frozen-source-input-only-no-selection',
            'selection_stage':'unchanged-original-collector-after-COMMITTED',
            'all_role_workspace_and_session_objects_bound_to_draft':True,
            'backend_async_or_shell_terminal_not_claimed':True}


def _root_identity(path):
    p=Path(path);s=p.lstat()
    need(p.is_absolute()and p.resolve()==p and stat.S_ISDIR(s.st_mode),
         'BRIDGE_BACKUP_ORIGINAL_CANONICAL_ROLE_ROOT')
    return {'device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid,'gid':s.st_gid}


class NativeBridgeBackup:
    def __init__(self,owner,receipts,cli_servers,*,roles,registered_refs,member_cap):
        need(type(owner)is NativeTeamOwner and owner.started and not owner.closed,
             'BRIDGE_BACKUP_ORIGINAL_STARTED_TEAM')
        self.owner=owner;self.ledger=owner.ledger;self.t=owner.t
        need(getattr(owner,'bridge_backup',None)is None,'BRIDGE_BACKUP_FIRST_START_BIND_ONCE')
        self.unmanaged=getattr(self.ledger,'native_unmanaged_cli',False)
        if not self.unmanaged:
            need(type(receipts)is NativeCliToolReceipts and type(owner.parent)is NativeModelToolParents
                 and owner.parent is receipts.parents and receipts.ledger is self.ledger
                 and owner.parent.cli_receipts is receipts,'BRIDGE_BACKUP_ORIGINAL_CLI_PARENT_SERVICE')
            need(type(cli_servers)is dict and set(cli_servers)==set(owner.roles)
                 and all(type(s)is NativeCliToolServer for s in cli_servers.values()),
                 'BRIDGE_BACKUP_ALL_ORIGINAL_CLI_LISTENERS')
        need(type(roles)is dict and set(roles)==set(owner.roles)
             and all(type(r)is dict and set(r)=={'workspace','session'}for r in roles.values()),
             'BRIDGE_BACKUP_ALL_ROLE_SOURCES')
        need(type(registered_refs)is tuple and registered_refs and len(set(registered_refs))==len(registered_refs)
             and all(type(r)is str and r.startswith('refs/')and not any(x in r for x in('..','\x00','\n','\r'))for r in registered_refs),
             'BRIDGE_BACKUP_PREREGISTERED_REFS')
        integer(member_cap,'BRIDGE_BACKUP_MEMBER_CAP',1);need(member_cap<=10_000_000,'BRIDGE_BACKUP_MEMBER_CAP')
        self.receipts=receipts;self.cli_servers=dict(cli_servers);self.roles={r:{k:Path(v)for k,v in row.items()}for r,row in roles.items()}
        self.refs=registered_refs;self.member_cap=member_cap;self.registry=owner._stage_registry
        self.process=process_identity(os.getpid());self.lock=threading.RLock();self.captures={}
        self.root_ids={r:{k:_root_identity(v)for k,v in row.items()}for r,row in self.roles.items()}
        all_roots=[p for row in self.roles.values()for p in row.values()]
        need(all(a!=b and not a.is_relative_to(b)and not b.is_relative_to(a)
                 for i,a in enumerate(all_roots)for b in all_roots[i+1:]),'BRIDGE_BACKUP_DISTINCT_ROLE_ROOTS')
        self.cli_peers={};self.cli_threads={};self.cli_bindings={}
        if not self.unmanaged:
            self.cli_peers={r:copy.deepcopy(receipts.peers.get((self.t,r)))for r in owner.roles}
            need(all(type(p)is dict for p in self.cli_peers.values()),'BRIDGE_BACKUP_CLI_PEERS_BEFORE_FIRST_MODEL')
            self.cli_threads={r:s.thread for r,s in cli_servers.items()}
            self.cli_bindings={r:self._cli_listener(r)for r in owner.roles}
        self.ledger_source=self._ledger_identity()
        with self.ledger.mutex:
            f=self.ledger.frontier(self.t)
            need(f['state']=='RUNNING'and f['generation']==1 and not self.ledger.admission_fault(self.t)
                 and self.ledger.db.execute('SELECT COUNT(*)FROM requests WHERE trajectory=?',(self.t,)).fetchone()[0]==0,
                 'BRIDGE_BACKUP_BIND_BEFORE_FIRST_MODEL')
            ports=self._ports(1)
        self.protocol=backup_protocol();self.protocol_sha=digest(self.protocol)
        self.binding={'schema':'agensh-original-live-bridge-backup-binding-v1','trajectory':self.t,
            'roles':owner.roles,'owner':self.process,'roots':self.root_ids,'ledger':self.ledger_source,
            'native_ports':ports,'cli_listeners':self.cli_bindings,
            'cli_peer_sha256':{r:digest(p)for r,p in self.cli_peers.items()},
            'registered_refs':list(self.refs),'member_cap':self.member_cap}
        self.instance_sha=digest(self.binding);self.graph_domain={'instance_sha256':self.instance_sha,
            'backup_protocol_sha256':self.protocol_sha,'objects':sorted(OBJECTS)}
        owner.bridge_backup=self
        try:self._runtime(1)
        except BaseException:
            # Registration is not rolled back/retried after a partial startup.
            self.ledger.latch_fault(self.t,'NATIVE_BRIDGE_BACKUP_STARTUP_BINDING_UNKNOWN_NO_RETRY');raise

    def _ledger_identity(self):
        p=self.ledger.home/'ledger.sqlite';s=p.lstat();need(stat.S_ISREG(s.st_mode)and not p.is_symlink(),
            'BRIDGE_BACKUP_ORIGINAL_LEDGER_FILE')
        with self.ledger.mutex:files=self.ledger.db.execute('PRAGMA database_list').fetchall()
        need([(r[1],r[2])for r in files]==[('main',str(p))],'BRIDGE_BACKUP_ORIGINAL_OPEN_LEDGER')
        return {'device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid,'mode':stat.S_IMODE(s.st_mode)}

    def _cli_listener(self,role):
        s=self.cli_servers[role]
        need(type(s)is NativeCliToolServer and isinstance(s,NativeAcceptedControls)
             and s.receipts is self.receipts and s.identity==(self.t,role)
             and not s.stopped and not s.closed and s.thread is not None and s.thread.is_alive()
             and s.socket.fileno()>=0 and self.ledger.native_services.get(s.scope)is s,
             'BRIDGE_BACKUP_ORIGINAL_LIVE_CLI_LISTENER')
        st=s.path.lstat();need(stat.S_ISSOCK(st.st_mode)and not s.path.is_symlink()
            and s.path.resolve()==s.path and st.st_ino==s.inode,'BRIDGE_BACKUP_CLI_SOCKET_REPLACED')
        return {'device':st.st_dev,'inode':st.st_ino,'fd_inode':os.fstat(s.socket.fileno()).st_ino,'scope':s.scope}

    def _ports(self,generation):
        from native_mcp_bridge import NativeMcpSession,McpServer
        from native_git_http import NativeGitHttp,NativeGitHttpServer
        need(self.owner._stage_registry is self.registry and type(self.registry)is tuple
             and self.owner._stage_owner_identity==self.process,'BRIDGE_BACKUP_ORIGINAL_REGISTERED_OWNER')
        expected={(r,p)for r in self.owner.roles for p in('gitea','mattermost','board','git')}
        need(len(self.registry)==len(expected)and {(r.role,r.purpose)for r in self.registry}==expected
             and set(self.owner.sessions)=={(r,p)for r,p in expected if p!='git'}
             and set(self.owner.git)==set(self.owner.roles)and len(self.owner.listeners)==len(expected)
             and {id(s)for s in self.owner.listeners}=={id(r.listener)for r in self.registry},
             'BRIDGE_BACKUP_EXACT_ALL_ORIGINAL_PORTS')
        records=[]
        for row in self.registry:
            p,s=row.port,row.listener
            need(_listener_identity(s)==row.listener_identity and p.ledger is self.ledger and p.scope==row.scope,
                 'BRIDGE_BACKUP_NATIVE_LISTENER_OR_SCOPE_CHANGED')
            from native_whole_team import frozen_whole_team
            if not self.unmanaged and not frozen_whole_team(self.owner):
                require_control_drained(s,'BRIDGE_BACKUP_NATIVE_ACCEPTED_CONTROLS_NOT_DRAINED')
            if row.kind=='MCP':
                need(type(p)is NativeMcpSession and type(s)is McpServer and s.session is p
                     and self.owner.sessions[(row.role,row.purpose)]is p and p.parent_tool_provider is (self.owner.parent if self.unmanaged else self.receipts.parents)
                     and p.identity==replace(row.binding,generation=generation)and p.policy.identity==p.identity
                     and _policy_spec(p.policy)==row.policy_spec and p.policy.scope_guard is row.scope_guard
                     and (self.unmanaged or not p.pending and not p.broken) and not p.closing and not p.closed
                     and p.child.poll()is None and process_identity(p.child.pid)==dict(row.process)
                     and p.process_identity==dict(row.process),'BRIDGE_BACKUP_ORIGINAL_DRAINED_MCP')
                public={'kind':'MCP','role':row.role,'purpose':row.purpose,'scope':row.scope,
                        'process_sha256':digest(dict(row.process)),'config_sha256':p.config_sha,
                        'policy_spec_sha256':row.policy_spec}
            else:
                need(row.kind=='GIT'and row.purpose=='git'and type(p)is NativeGitHttp
                     and type(s)is NativeGitHttpServer and s.broker is p and self.owner.git[row.role]is p
                     and p.parent_tool_provider is (self.owner.parent if self.unmanaged else self.receipts.parents)
                     and p.binding==replace(row.binding,generation=generation)and (self.unmanaged or not p.children) and not p.closing,
                     'BRIDGE_BACKUP_ORIGINAL_DRAINED_GIT')
                public={'kind':'GIT','role':row.role,'purpose':'git','scope':row.scope,
                        'binding_sha256':digest({k:v for k,v in asdict(row.binding).items()if k!='capability'})}
            public['listener']={'device':row.listener_identity[0],'inode':row.listener_identity[1],
                               'fd_inode':row.listener_identity[2]};records.append(public)
        return records

    def controls_ready(self):
        if self.unmanaged:return True
        need(not self.receipts.closed,'BRIDGE_BACKUP_CLI_RECEIPTS_CLOSED')
        values=[]
        for role,s in self.cli_servers.items():
            need(s.thread is self.cli_threads[role]and self._cli_listener(role)==self.cli_bindings[role],
                 'BRIDGE_BACKUP_CLI_LISTENER_REBOUND')
            values.append(s.control_snapshot()['active'])
        return not any(values)

    def _runtime(self,generation):
        if self.unmanaged:
            need(self.owner.bridge_backup is self and self.owner.ledger is self.ledger
                 and self._ledger_identity()==self.ledger_source,'BRIDGE_BACKUP_ORIGINAL_RUNTIME_CHANGED')
            need(self.owner.roles==list(self.roles) and backup_protocol()==self.protocol
                 and digest(self.binding)==self.instance_sha,'BRIDGE_BACKUP_FROZEN_INPUT_CHANGED')
            need({r:{k:_root_identity(p)for k,p in row.items()}for r,row in self.roles.items()}==self.root_ids,
                 'BRIDGE_BACKUP_ORIGINAL_ROLE_MOUNT_CHANGED')
            ports=self._ports(generation)
            need(ports==self.binding['native_ports'],'BRIDGE_BACKUP_ORIGINAL_NATIVE_CONFIG_CHANGED')
            return ports
        need(self.owner.bridge_backup is self and self.owner.started and not self.owner.closed
             and self.owner.ledger is self.ledger and process_identity(os.getpid())==self.process
             and self.owner.parent is self.receipts.parents and self.receipts.parents.cli_receipts is self.receipts
             and self._ledger_identity()==self.ledger_source,'BRIDGE_BACKUP_ORIGINAL_RUNTIME_CHANGED')
        need(self.owner.roles==list(self.roles)and backup_protocol()==self.protocol
             and digest(self.binding)==self.instance_sha
             and self.graph_domain=={'instance_sha256':self.instance_sha,'backup_protocol_sha256':self.protocol_sha,'objects':sorted(OBJECTS)},'BRIDGE_BACKUP_FROZEN_INPUT_CHANGED')
        need({r:{k:_root_identity(p)for k,p in row.items()}for r,row in self.roles.items()}==self.root_ids
             and all(self.roles[r]['workspace']==Path(self.owner.gb['workspace_roots'][r]['path'])for r in self.roles),
             'BRIDGE_BACKUP_ORIGINAL_ROLE_MOUNT_CHANGED')
        need({r for t,r in self.receipts.peers if t==self.t}==set(self.roles),'BRIDGE_BACKUP_CLI_EXACT_ROLE_ROSTER')
        for role,p in self.cli_peers.items():
            need(self.receipts.peers[(self.t,role)]==p and cli_peer(p['pid'])==p,
                 'BRIDGE_BACKUP_ORIGINAL_CLI_PEER_CHANGED')
            peer=self.owner.peers[role]
            need((p['uid'],p['pid_namespace_inode'],p['net_namespace_inode'])==(peer['uid'],peer['pidns'],peer['netns']),
                 'BRIDGE_BACKUP_CLI_ORIGINAL_ROLE_NAMESPACE')
        from native_whole_team import frozen_whole_team
        if not self.unmanaged and not frozen_whole_team(self.owner):
            need(self.controls_ready(),'BRIDGE_BACKUP_CLI_ACCEPTED_CONTROLS_NOT_DRAINED')
        fence=self.owner.writer_fence
        need(type(fence)is NativeWriterFence and fence.owner is self.owner,
             'BRIDGE_BACKUP_ORIGINAL_REGISTERED_WRITER_DOMAINS')
        for p in self.cli_peers.values():
            identity={k:p[k]for k in('pid','start_ticks','boot_id')}
            need(sum(d.contains(identity)for d in fence.domains)==1,
                 'BRIDGE_BACKUP_EVERY_CLI_PEER_IN_ORIGINAL_ROLE_DOMAIN')
        ports=self._ports(generation)
        need(ports==self.binding['native_ports'],'BRIDGE_BACKUP_ORIGINAL_NATIVE_CONFIG_CHANGED')
        return ports

    def _scoped_rows(self,generation):
        if self.unmanaged:return {'mode':'UNMANAGED_NATIVE_NO_TOOL_CUSTODY'}
        # Original private tables contain metadata/hashes only. Never select any
        # continuation/model result/argument body. Other trajectories may remain
        # active: global receipts.unresolved() would be an erroneous barrier.
        with self.ledger.mutex:
            p=[dict(r)for r in self.ledger.db.execute('SELECT * FROM native_model_tool_parents WHERE trajectory=?ORDER BY operation_id',(self.t,))]
            s=[dict(r)for r in self.ledger.db.execute('SELECT * FROM native_cli_tool_starts WHERE trajectory=?ORDER BY ticket',(self.t,))]
            for row in p+s:
                need(row['role']in self.roles and type(row['generation'])is int and 1<=row['generation']<=generation,
                     'BRIDGE_BACKUP_FOREIGN_OR_FUTURE_ROLE_METADATA')
            parents={r['operation_id']:r for r in p}
            for row in s:
                original=parents.get(row['operation_id'])
                need(original is not None and all(row[k]==original[k]for k in('role','generation','request_id','call_id','function_name'))
                     and row['peer_sha256']==digest(self.cli_peers[row['role']]),
                     'BRIDGE_BACKUP_ORIGINAL_PARENT_CALLBACK_METADATA')
            e=[dict(r)for r in self.ledger.db.execute('SELECT e.* FROM native_cli_tool_returns e JOIN native_cli_tool_starts s ON s.ticket=e.ticket WHERE s.trajectory=?ORDER BY e.ticket',(self.t,))]
            missing={r['ticket']for r in s}-{r['ticket']for r in e}
            if missing:
                from native_whole_team import frozen_whole_team
                need(frozen_whole_team(self.owner),'BRIDGE_BACKUP_UNRETURNED_ORIGINAL_CLI_CALLBACK')
                kind='NATIVE_TOOL_CUSTODY_AUDIT_ONLY';code='BRIDGE_BACKUP_UNRETURNED_ORIGINAL_CLI_CALLBACK'
                # _scoped_rows is verified repeatedly for a cut; report once,
                # preserving missing rows, not manufacturing native RETURNs.
                old=[strict(r[0])for r in self.ledger.db.execute(
                    'SELECT metadata FROM events WHERE trajectory=?AND kind=?',(self.t,kind))]
                if not any(v.get('guard_code')==code and v.get('generation')==generation for v in old):
                    with self.ledger.tx():self.ledger.event(self.t,kind,{
                        'schema':'agensh-tool-custody-audit-only-v1','guard_code':code,
                        'generation':generation,'role':None,'operation_id':None,
                        'count':len(missing),'physical_terminal_claimed':False,
                        'whole_team_freeze_still_required':True,
                        'whole_team_frozen':True,'unreturned_original_rows_preserved':True})
            w=[dict(r)for r in self.ledger.db.execute('SELECT w.* FROM native_model_tool_wire w JOIN native_model_tool_parents p ON p.operation_id=w.operation_id WHERE p.trajectory=?ORDER BY w.operation_id',(self.t,))]
            need({r['operation_id']for r in w}=={r['operation_id']for r in p},'BRIDGE_BACKUP_ALL_ORIGINAL_MODEL_WIRE_HASHES')
        return {'row_counts':{'parents':len(p),'starts':len(s),'returns':len(e),'wire':len(w)},
                'metadata_sha256':digest({'parents':p,'starts':s,'returns':e,'wire':w})}

    def _current(self,cut,states):
        need(type(cut)is NativeServiceCut and cut.ledger is self.ledger and cut.t==self.t
             and cut.graph[COMPONENT]==self.graph_domain,'BRIDGE_BACKUP_ORIGINAL_SAMECUT_GRAPH')
        cut.current(states);ports=self._runtime(cut.cut['generation'])
        fence=cut.writer_fence;need(type(fence)is NativeWriterFence and fence is self.owner.writer_fence,
                                  'BRIDGE_BACKUP_ORIGINAL_COMPLETE_WRITER_FENCE')
        frozen=fence.verify_capture(cut,self.roles);cli_domains={}
        for role,p in self.cli_peers.items():
            identity={k:p[k]for k in('pid','start_ticks','boot_id')}
            covered=[d.binding_sha for d in fence.domains if d.contains(identity)]
            need(len(covered)==1,'BRIDGE_BACKUP_EVERY_CLI_PEER_IN_ORIGINAL_FROZEN_ROLE_DOMAIN')
            cli_domains[role]=covered[0]
        state={'native_ports':ports,'native_controls':[] if self.unmanaged else [row.listener.server.control_snapshot(require_drained=True)for row in self.registry],
               'cli_controls':{r:s.control_snapshot(require_drained=True)for r,s in self.cli_servers.items()},
               'cli_domains':cli_domains,'scoped_rows':self._scoped_rows(cut.cut['generation'])}
        return frozen,state

    def _exports(self,cut,exports):
        need(type(exports)is list and len(exports)==len(self.refs)
             and {e.get('ref')for e in exports if type(e)is dict}==set(self.refs),
             'BRIDGE_BACKUP_EXACT_PREREGISTERED_GIT_EXPORTS')
        for e in exports:
            need(type(e)is dict and set(e)=={'ref','commit','archive'}and type(e['commit'])is str
                 and re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}',e['commit']),'BRIDGE_BACKUP_NATIVE_GIT_EXPORT_FIELDS')
            cut.cas.resolve(e['archive'])
        return digest({'registered_refs':list(self.refs),'exports':exports})

    def run(self,cut,destination,*,git_exports):
        with self.lock:
            frozen,before=self._current(cut,{'DRAINING'});exports_sha=self._exports(cut,git_exports)
            need(set(cut.receipts)==SERVICES-{COMPONENT},'BRIDGE_BACKUP_OTHER_NATIVE_RECEIPTS_REQUIRED_FIRST')
            need(cut.bridge_backup is self,'BRIDGE_BACKUP_STARTUP_CUT_BINDING_REQUIRED')
            with self.ledger.tx():
                prior=self.ledger.db.execute("SELECT metadata FROM events WHERE trajectory=?AND kind='NATIVE_BRIDGE_BACKUP_STARTED'",(self.t,)).fetchall()
                need(not any(json.loads(r[0]).get('cut_sha256')==cut.cut_sha for r in prior),
                     'BRIDGE_BACKUP_ONE_DURABLE_ATTEMPT_NO_RETRY')
                self.ledger.event(self.t,'NATIVE_BRIDGE_BACKUP_STARTED',{'cut_sha256':cut.cut_sha,
                    'instance_sha256':self.instance_sha,'backup_protocol_sha256':self.protocol_sha})
            try:
                dest=Path(destination);need(not dest.exists()and not dest.is_symlink(),'BRIDGE_BACKUP_NEW_DESTINATION')
                dest=private_dir(dest,create=True);sources={n:private_dir(dest/n,create=True)for n in sorted(OBJECTS)}
                role_objects={r:{k:cut.cas.capture_tree(p)for k,p in row.items()}for r,row in sorted(self.roles.items())}
                self.ledger.backup(sources['bridge_journal']/'bridge.sqlite')
                journal_pin=hash_file(sources['bridge_journal']/'bridge.sqlite')
                inventory={'schema':'agensh-original-live-bridge-inventory-v1','cut_sha256':cut.cut_sha,
                           'instance_sha256':self.instance_sha,'writer_fence_receipt':frozen,'state':before}
                publish(sources['bridge_journal']/'INVENTORY.json',wire(inventory))
                inputs={'schema':'agensh-frozen-candidate-INPUT-source-manifest-v1','cut_sha256':cut.cut_sha,
                        'writer_fence_receipt':frozen,'roles':role_objects,'registered_refs':list(self.refs),
                        'git_exports':copy.deepcopy(git_exports),'gitea_exports_sha256':exports_sha,
                        'gitea_service_receipt':copy.deepcopy(cut.receipts['gitea']),
                        'gitea_repo_object':copy.deepcopy(cut.packed['gitea_repo']),
                        'collector_sha256':self.protocol['implementations']['collector.py'],
                        'candidate_policy_sha256':self.protocol['implementations']['native_candidate_policy.py'],
                        'member_cap':self.member_cap,'candidate_selection_applied':False,
                        'collection_only_after_original_snapshot_COMMITTED':True}
                publish(sources['candidate_manifest']/'INPUTS.json',wire(inputs))
                for path in sources.values():sync_dir(path)
                _,after=self._current(cut,{'DRAINING'});need(after==before,'BRIDGE_BACKUP_NATIVE_CONTROL_OR_METADATA_CHANGED')
                receipt={'schema':'agensh-original-bridge-consistent-backup-receipt-v1','cut_sha256':cut.cut_sha,
                    'instance_sha256':self.instance_sha,'backup_protocol_sha256':self.protocol_sha,
                    'writer_fence_receipt':frozen,'bridge_database':journal_pin,'inventory_sha256':digest(inventory),
                    'candidate_INPUT_sha256':digest(inputs),'gitea_exports_sha256':exports_sha,
                    'other_backend_async_or_shell_terminal_not_claimed':True}
                publish(dest/'RECEIPT.json',wire(receipt));sync_dir(dest)
                native_ref=cut.cas.store_bytes(wire(receipt))
                _,after=self._current(cut,{'DRAINING'});need(after==before,'BRIDGE_BACKUP_NATIVE_CONTROL_OR_METADATA_CHANGED')
                ref=cut.record_native_backup(COMPONENT,sources,{'cut_sha256':cut.cut_sha,
                    'instance_sha256':self.instance_sha,'backup_protocol_sha256':self.protocol_sha,'receipt_sha256':native_ref['sha256']})
                self.captures[cut.cut_sha]={'inputs':copy.deepcopy(inputs),'state':before,'native_receipt':native_ref,'service_receipt':ref}
                return {'native_receipt':native_ref,'service_receipt':ref,'sources':sources,'destination':dest}
            except BaseException as exc:
                self.ledger.latch_fault(self.t,'NATIVE_BRIDGE_BACKUP_INCOMPLETE_NO_RETRY')
                try:
                    with self.ledger.tx():self.ledger.event(self.t,'NATIVE_BRIDGE_BACKUP_FAILED',
                        {'cut_sha256':cut.cut_sha,'exception_type':type(exc).__name__,'code':'NATIVE_BRIDGE_BACKUP_INCOMPLETE_NO_RETRY'})
                except BaseException:pass
                raise Refused('NATIVE_BRIDGE_BACKUP_INCOMPLETE_NO_RETRY')from None

    def verify_capture(self,cut,draft):
        _,state=self._current(cut,{'CAPTURING'})
        need(cut.cut_sha in self.captures,'BRIDGE_BACKUP_REAL_ORIGINAL_PRODUCER_REQUIRED')
        original=self.captures[cut.cut_sha];inputs=original['inputs']
        need(state==original['state'],'BRIDGE_BACKUP_NATIVE_STATE_CHANGED_BEFORE_PUBLICATION')
        need(digest(draft['roles'])==digest(inputs['roles']),'BRIDGE_BACKUP_ROLE_SOURCE_PACK_CHANGED')
        need(draft['pins'].get('gitea_exports')==inputs['gitea_exports_sha256']
             and cut.receipts['gitea']==inputs['gitea_service_receipt']
             and digest(draft['shared']['gitea_repo'])==digest(inputs['gitea_repo_object']),
             'BRIDGE_BACKUP_GIT_SOURCE_CHANGED_BEFORE_PUBLICATION')
        need(cut.receipts[COMPONENT]==original['service_receipt'],'BRIDGE_BACKUP_ORIGINAL_SERVICE_RECEIPT_CHANGED')
        cut.cas.resolve(original['native_receipt'])
