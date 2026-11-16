"""Durable single-owner model/tool/bridge admission and all-role barriers.

The trusted relay supplies identity and a verified upper-bound proof, never a
worker assertion. No request is resent here. UNKNOWN retains physical custody.
"""
from contextlib import contextmanager
from pathlib import Path
import fcntl,json,os,sqlite3,threading,time
from common import need,Refused,private_dir,digest,wire,integer,ident,sha,publish,sync_dir
SCHEMA='count14-agensh-durable-budget-v1'
# Logical budget custody only. Charged UNKNOWN retains one physical gateway
# slot in global_unresolved(); it is NEVER a measured/physical terminal.
LOGICAL_PENDING="state IN ('RESERVED','SENT','UNKNOWN') AND NOT EXISTS (SELECT 1 FROM unknown_charges uc WHERE uc.request_id=requests.id)"
SERVICES=frozenset(('gitea','gitea_database','collaboration','relay_continuation','bridge'))
# Explicit user-authorized logical tool-custody inconsistencies only.  Never
# classify by prefix/substring: peer, credential, scope, budget, UNKNOWN and
# request-replay refusals must remain refusals.
TOOL_CUSTODY_AUDIT_CODES=frozenset((
    'MCP_TOOL_TERMINAL_ONE_EXACT_BUSINESS_DISPATCH_REQUIRED',
    'MCP_REJECTION_ONE_EXACT_HOST_DECISION',
    'MCP_REJECTION_NO_ACCEPTED_BUSINESS_CHILDREN',
    'MCP_REJECTION_ORIGINAL_RETURN_REQUIRED',
    'MCP_TOOL_TERMINAL_ORIGINAL_BRIDGE_NOT_PHYSICALLY_COMPLETE',
    'MCP_TOOL_TERMINAL_EXACT_NATIVE_PHYSICAL_RECEIPT_REQUIRED',
    'MCP_TOOL_TERMINAL_ORIGINAL_CLI_CALLBACK_NOT_RETURNED',
    'CLI_RECEIPT_ORIGINAL_CALLBACK_RETURN_REQUIRED',
    'CLI_CALLBACK_CUSTODY_EXACT_NATIVE_CALLBACK_RETURN',
    'CLI_CALLBACK_CUSTODY_ACCEPTED_BUSINESS_CHILD_NOT_TERMINAL',
    'CLI_CALLBACK_CUSTODY_EXACT_NATIVE_GIT_TERMINAL_REQUIRED',
    'CLI_CALLBACK_CUSTODY_NOEXEC_WITH_BUSINESS_CHILD',
    'NATIVE_TOOL_NOT_TERMINAL',
    'TOOL_DEPENDENT_BRIDGE_NOT_TERMINAL',
    'ROLE_TOOLS_PENDING',
    'TOOL_CUSTODY_PENDING_AT_WHOLE_TEAM_CUT',
))
class Ledger:
    def __init__(self,home):
        self.home=private_dir(home,create=True);self.mutex=threading.RLock();self.capacity_changed=threading.Condition(self.mutex);self.memory_faults={};self.native_services={}
        self.fd=os.open(self.home/'owner.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:os.close(self.fd);raise Refused('LEDGER_ALREADY_OWNED')from None
        self.owner_marker=self.home/'owner.open'
        try:
            need(not self.owner_marker.is_symlink(),'LEDGER_OWNER_MARKER_SYMLINK')
            unclean_owner=self.owner_marker.exists()
            if not unclean_owner:publish(self.owner_marker,wire({'schema':'count14-agensh-owner-open-v1'}))
        except BaseException:os.close(self.fd);raise
        p=self.home/'ledger.sqlite';need(not p.is_symlink(),'LEDGER_SYMLINK')
        self.db=sqlite3.connect(p,check_same_thread=False,isolation_level=None)
        os.chmod(p,0o600);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL');self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS accounts(trajectory TEXT PRIMARY KEY,manifest_sha TEXT NOT NULL,roles TEXT NOT NULL,targets TEXT NOT NULL,stage INTEGER NOT NULL,generation INTEGER NOT NULL,state TEXT NOT NULL,actual INTEGER NOT NULL,request_cap INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,trajectory TEXT NOT NULL REFERENCES accounts,role TEXT NOT NULL,generation INTEGER NOT NULL,state TEXT NOT NULL,upper_bound INTEGER NOT NULL,proof_sha TEXT NOT NULL,input INTEGER,output INTEGER,receipt_sha TEXT);
        CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY,trajectory TEXT NOT NULL REFERENCES accounts,role TEXT NOT NULL,generation INTEGER NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL,parent TEXT);
        CREATE TABLE IF NOT EXISTS model_control(singleton INTEGER PRIMARY KEY CHECK(singleton=1),paused INTEGER NOT NULL,epoch INTEGER NOT NULL,reason TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS aux_scopes(scope TEXT PRIMARY KEY,trajectory TEXT NOT NULL REFERENCES accounts,binding TEXT NOT NULL,epoch TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS aux_permits(id TEXT PRIMARY KEY,scope TEXT NOT NULL REFERENCES aux_scopes,epoch TEXT NOT NULL,state TEXT NOT NULL,request_id TEXT UNIQUE,terminal_sha TEXT);
        CREATE TABLE IF NOT EXISTS acks(trajectory TEXT NOT NULL,generation INTEGER NOT NULL,component TEXT NOT NULL,receipt_sha TEXT NOT NULL,PRIMARY KEY(trajectory,generation,component));
        CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,at_ns INTEGER NOT NULL,trajectory TEXT NOT NULL,kind TEXT NOT NULL,metadata TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS snapshots(trajectory TEXT NOT NULL,generation INTEGER NOT NULL,target INTEGER NOT NULL,ref_sha TEXT NOT NULL,PRIMARY KEY(trajectory,generation));
        CREATE TRIGGER IF NOT EXISTS immutable_events_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_events_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;''')
        self._unknown_schema()
        with self.tx():
            self.db.execute("INSERT OR IGNORE INTO model_control VALUES(1,1,1,'NEW_OWNER_REQUIRES_FRESH_RELEASE')")
            for r in self.db.execute("SELECT * FROM requests WHERE state='SENT'").fetchall():
                self.db.execute("UPDATE requests SET state='UNKNOWN' WHERE id=?",(r['id'],));self.event(r['trajectory'],'UNKNOWN_EXECUTION',{'request_id':r['id'],'cause':'OWNER_REOPEN_NO_REPLAY'})
                self.db.execute("UPDATE accounts SET state='DRAINING' WHERE trajectory=?",(r['trajectory'],))
            for r in self.db.execute("SELECT id,scope FROM aux_permits WHERE state IN ('RESERVED','SENT')").fetchall():
                self.db.execute("UPDATE aux_permits SET state='UNKNOWN' WHERE id=?",(r['id'],))
                t=self.db.execute('SELECT trajectory FROM aux_scopes WHERE scope=?',(r['scope'],)).fetchone()[0]
                self.event(t,'AUX_CUSTODY_UNKNOWN',{'permit_id':r['id'],'scope':r['scope'],'cause':'OWNER_REOPEN_NO_REPLAY'})
        if unclean_owner:
            # A crash or failed fault commit cannot silently reopen SEARCH on
            # another role. This is metadata reconciliation only, not L2 resume.
            for row in self.db.execute('SELECT trajectory FROM accounts').fetchall():self.latch_fault(row[0],'UNCLEAN_OWNER_REOPEN_NO_AUTOMATIC_SEARCH')
    def latch_fault(self,t,code):
        ident(code)
        with self.capacity_changed:
            self.memory_faults.setdefault(t,code);self.capacity_changed.notify_all()
    def retain_native_service(self,scope,custodian=None):
        # A process may be live before STARTED metadata commits. Even an idle
        # native service is custody, not a financially empty clean owner close.
        ident(scope)
        with self.mutex:
            need(scope not in self.native_services,'NATIVE_SERVICE_CUSTODY_DUPLICATE')
            self.native_services[scope]=custodian
    def release_native_service(self,scope):
        # Trusted owner only, after native wait AND both protocol/control EOF.
        with self.mutex:
            need(scope in self.native_services,'NATIVE_SERVICE_CUSTODY_UNKNOWN')
            del self.native_services[scope]
    def _unknown_schema(self):
        """Additive migration, usable on the already-owned live connection.

        No owner reopen, request rewrite, transaction truncation or script commit.
        """
        with self.tx():
            for sql in (
                'CREATE TABLE IF NOT EXISTS unknown_policy(singleton INTEGER PRIMARY KEY CHECK(singleton=1),version TEXT NOT NULL)',
                'CREATE TABLE IF NOT EXISTS unknown_charges(request_id TEXT PRIMARY KEY REFERENCES requests(id),upper_bound INTEGER NOT NULL,settlement_seq INTEGER NOT NULL UNIQUE REFERENCES events(seq))',
                'CREATE TABLE IF NOT EXISTS unknown_stops(scope TEXT PRIMARY KEY,code TEXT NOT NULL,event_seq INTEGER NOT NULL UNIQUE REFERENCES events(seq))',
                "CREATE TRIGGER IF NOT EXISTS immutable_unknown_charges_update BEFORE UPDATE ON unknown_charges BEGIN SELECT RAISE(ABORT,'append only'); END",
                "CREATE TRIGGER IF NOT EXISTS immutable_unknown_charges_delete BEFORE DELETE ON unknown_charges BEGIN SELECT RAISE(ABORT,'append only'); END",
                "CREATE TRIGGER IF NOT EXISTS immutable_unknown_policy_update BEFORE UPDATE ON unknown_policy BEGIN SELECT RAISE(ABORT,'append only'); END",
                "CREATE TRIGGER IF NOT EXISTS immutable_unknown_policy_delete BEFORE DELETE ON unknown_policy BEGIN SELECT RAISE(ABORT,'append only'); END",
                "CREATE TRIGGER IF NOT EXISTS immutable_unknown_stops_update BEFORE UPDATE ON unknown_stops BEGIN SELECT RAISE(ABORT,'append only'); END",
                "CREATE TRIGGER IF NOT EXISTS immutable_unknown_stops_delete BEFORE DELETE ON unknown_stops BEGIN SELECT RAISE(ABORT,'append only'); END",
            ):self.db.execute(sql)
    def enable_unknown_reservation_policy(self):
        need(getattr(self,'native_unmanaged_cli',False) is True,'UNKNOWN_POLICY_NATIVE_UNMANAGED_ONLY')
        self._unknown_schema()
        with self.tx():
            old=self.db.execute('SELECT version FROM unknown_policy WHERE singleton=1').fetchone()
            if old:need(old[0]=='USER_20261027_RESERVATION_V1','UNKNOWN_POLICY_VERSION');return
            self.db.execute("INSERT INTO unknown_policy VALUES(1,'USER_20261027_RESERVATION_V1')")
            self.event('GLOBAL','UNKNOWN_RESERVATION_POLICY_ENABLED',{'consecutive_limit':3,'ratio_numerator_percent':1,'minimum_sent_requests':200,'physical_slot_retained':True})
    def unknown_policy_enabled(self):
        with self.mutex:return self.db.execute('SELECT 1 FROM unknown_policy WHERE singleton=1').fetchone() is not None
    def unknown_charged(self,rid):
        with self.mutex:return self.db.execute('SELECT 1 FROM unknown_charges WHERE request_id=?',(rid,)).fetchone() is not None
    def unknown_statistics(self,t):
        # Denominator = distinct SEARCH requests actually marked SENT, including
        # in-flight and UNKNOWN. AUX/reserved/unsent are not SEARCH requests.
        # Concurrent roles are ordered by durable terminal event seq per track;
        # another track's successes never reset this track's consecutive count.
        with self.mutex:
            total=self.db.execute("SELECT COUNT(*) FROM requests WHERE state IN ('SENT','SETTLED','UNKNOWN')").fetchone()[0]
            unknown=self.db.execute("SELECT COUNT(*) FROM requests WHERE state='UNKNOWN'").fetchone()[0]
            rows=self.db.execute("SELECT kind FROM events WHERE trajectory=? AND kind IN ('SETTLED','UNKNOWN_EXECUTION') ORDER BY seq DESC LIMIT 3",(t,)).fetchall()
            streak=0
            for row in rows:
                if row[0]!='UNKNOWN_EXECUTION':break
                streak+=1
            return {'sent_requests':total,'unknown_requests':unknown,'trajectory_consecutive_unknown':streak}
    def _unknown_thresholds(self,t):
        # Called INSIDE the writer transaction. Stop latches are durable; a later
        # good request cannot erase an already crossed stop/report threshold.
        if not self.unknown_policy_enabled():return
        stats=self.unknown_statistics(t);stops=[]
        if stats['trajectory_consecutive_unknown']>=3:stops.append((t,'UNKNOWN_CONSECUTIVE_3_STOP'))
        if stats['sent_requests']>=200 and stats['unknown_requests']*100>stats['sent_requests']:
            stops.append(('GLOBAL','UNKNOWN_GLOBAL_RATIO_GT_1_PERCENT_STOP'))
        for scope,code in stops:
            if self.db.execute('SELECT 1 FROM unknown_stops WHERE scope=?',(scope,)).fetchone():continue
            seq=self.event(scope,'UNKNOWN_POLICY_STOP',{'code':code,**stats})
            self.db.execute('INSERT INTO unknown_stops VALUES(?,?,?)',(scope,code,seq))
    def admission_fault(self,t):
        with self.mutex:
            existing=self.memory_faults.get(t)
            if existing:return existing
            stop=self.db.execute("SELECT code FROM unknown_stops WHERE scope IN (?, 'GLOBAL') ORDER BY event_seq LIMIT 1",(t,)).fetchone()
            return None if stop is None else stop[0]
    def charge_unknown_at_reservation(self,rid):
        """Explicit settlement of an existing UNKNOWN; safe to call repeatedly.

        Original request row/usage/history remain intact, including NULL usage.
        Account.actual is budget consumption, not a measured-usage assertion.
        """
        with self.tx():
            need(self.unknown_policy_enabled(),'UNKNOWN_RESERVATION_POLICY_NOT_ENABLED')
            amount=self._charge_unknown_at_reservation(rid)
            r=self.db.execute('SELECT trajectory FROM requests WHERE id=?',(rid,)).fetchone()
            self._unknown_thresholds(r[0]);return amount
    def _charge_unknown_at_reservation(self,rid):
        r=self.db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
        need(r is not None and r['state']=='UNKNOWN','UNKNOWN_CHARGE_REQUIRES_ORIGINAL_UNKNOWN')
        need(r['input'] is None and r['output'] is None and r['receipt_sha'] is None,'UNKNOWN_CHARGE_NO_USAGE_REWRITE')
        old=self.db.execute('SELECT upper_bound FROM unknown_charges WHERE request_id=?',(rid,)).fetchone()
        if old:need(old[0]==r['upper_bound'],'UNKNOWN_CHARGE_CONFLICT');return 0
        seq=self.event(r['trajectory'],'UNKNOWN_CHARGED_AT_RESERVATION',{'request_id':rid,'search_budget_charge':r['upper_bound'],'usage_available':False,'original_state':'UNKNOWN','physical_terminal_claimed':False,'no_replay':True})
        self.db.execute('INSERT INTO unknown_charges VALUES(?,?,?)',(rid,r['upper_bound'],seq))
        self.db.execute('UPDATE accounts SET actual=actual+? WHERE trajectory=?',(r['upper_bound'],r['trajectory']))
        f=self.frontier(r['trajectory'])
        need(f['actual']+f['reserved']<=f['target'],'UNKNOWN_RESERVATION_BUDGET_BREACH')
        return r['upper_bound']
    def model_paused(self):
        with self.mutex:
            return hasattr(self,'model_capacity_global_cap')and bool(self.db.execute('SELECT paused FROM model_control WHERE singleton=1').fetchone()[0])
    def global_unresolved(self):
        # Search and independent native FINAL share one serial capacity writer.
        # Financial settlement is separate; UNKNOWN physical execution still
        # counts even when the native AUX ledger conservatively charged it.
        with self.mutex:
            a=self.db.execute("SELECT COUNT(*) FROM requests WHERE state IN ('RESERVED','SENT','UNKNOWN')").fetchone()[0]
            b=self.db.execute("SELECT COUNT(*) FROM aux_permits WHERE state IN ('RESERVED','SENT','UNKNOWN')").fetchone()[0]
            return a+b
    def global_logical_unresolved(self):
        """Scientific closure only; global_unresolved retains physical slots."""
        with self.mutex:
            charged=self.db.execute('SELECT COUNT(*) FROM unknown_charges').fetchone()[0]
            return self.global_unresolved()-charged
    @contextmanager
    def tx(self):
        with self.mutex:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                yield;self.db.execute('COMMIT')
                # SEARCH admission and native AUX capacity use this same writer
                # and condition. Wake only after durable commit, never by a
                # caller remembering an independent gate.notify().
                self.capacity_changed.notify_all()
            except BaseException:
                if self.db.in_transaction:self.db.execute('ROLLBACK')
                raise
    def event(self,t,kind,meta):
        cur=self.db.execute('INSERT INTO events(at_ns,trajectory,kind,metadata)VALUES(?,?,?,?)',(time.time_ns(),t,kind,wire(meta).decode()));return cur.lastrowid
    def account(self,t):
        # Public identity reads also occur before relay admission. Protect the
        # complete execute/fetchone pair, not only transactional callers; the
        # same SQLite connection/statement cache is shared by all relay threads.
        with self.mutex:
            r=self.db.execute('SELECT * FROM accounts WHERE trajectory=?',(t,)).fetchone();need(r is not None,'UNKNOWN_TRAJECTORY');return r
    def _identity(self,t,role,generation):
        a=self.account(t);need(type(generation)is int and a['generation']==generation,'STALE_GENERATION');need(role in json.loads(a['roles']),'UNREGISTERED_ROLE');return a
    def register(self,t,roles,manifest_sha,*,targets=(10000000,20000000),request_cap=16):
        need(type(t)is str and 0<len(t)<=512,'TRAJECTORY');sha(manifest_sha)
        need(type(roles)is list and 1<=len(roles)<=16 and len(set(roles))==len(roles),'ROLE_ROSTER')
        for r in roles:ident(r)
        need(list(targets)==sorted(set(targets)) and 1<=len(targets)<=3,'TARGETS')
        for b in targets:integer(b,'TARGET',1)
        integer(request_cap,'REQUEST_CAP',1);need(request_cap<=len(roles),'REQUEST_CAP')
        with self.tx():
            need(self.db.execute('SELECT 1 FROM accounts WHERE trajectory=?',(t,)).fetchone()is None,'DUPLICATE_TRAJECTORY')
            self.db.execute('INSERT INTO accounts VALUES(?,?,?,?,0,1,\'RUNNING\',0,?)',(t,manifest_sha,wire(roles).decode(),wire(list(targets)).decode(),request_cap))
            self.event(t,'FIRSTSTART',{'roles':roles,'manifest_sha256':manifest_sha,'targets':list(targets)})
    def frontier(self,t):
        with self.mutex:
            a=self.account(t);rs=self.db.execute("SELECT COUNT(*) AS n,COALESCE(SUM(upper_bound),0) AS r FROM requests WHERE trajectory=? AND "+LOGICAL_PENDING,(t,)).fetchone()
            ops=self.db.execute("SELECT COUNT(*) FROM operations WHERE trajectory=? AND state='ACTIVE'",(t,)).fetchone()[0]
            target=json.loads(a['targets'])[a['stage']]
            charged=self.db.execute('SELECT COALESCE(SUM(uc.upper_bound),0) FROM unknown_charges uc JOIN requests r ON r.id=uc.request_id WHERE r.trajectory=?',(t,)).fetchone()[0]
            return dict(measured_actual=a['actual']-charged,unknown_reservation_charge=charged,trajectory=t,manifest_sha256=a['manifest_sha'],roles=json.loads(a['roles']),generation=a['generation'],state=a['state'],stage=a['stage'],target=target,actual=a['actual'],reserved=rs['r'],unresolved=rs['n'],active_operations=ops,shortfall=target-a['actual'],sequence=self.db.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0])
    def reserve(self,t,role,generation,rid,upper,proof_sha):
        ident(rid);integer(upper,'RESERVATION_UPPER',1);sha(proof_sha)
        with self.tx():
            need(not self.admission_fault(t),'ADMISSION_CLOSED_IN_MEMORY_FAULT')
            a=self._identity(t,role,generation);need(a['state']=='RUNNING','ADMISSION_CLOSED')
            need(self.db.execute('SELECT 1 FROM requests WHERE id=?',(rid,)).fetchone()is None,'REQUEST_ID_ALREADY_CLAIMED_NO_REPLAY')
            active=self.db.execute("SELECT role,upper_bound FROM requests WHERE trajectory=? AND "+LOGICAL_PENDING,(t,)).fetchall()
            need(not any(r['role']==role for r in active),'ROLE_ALREADY_INFLIGHT')
            need(self.db.execute("SELECT COUNT(*) FROM operations WHERE trajectory=? AND role=? AND kind='TOOL' AND state='ACTIVE'",(t,role)).fetchone()[0]==0,'ROLE_TOOLS_PENDING')
            need(len(active)<a['request_cap'],'TRAJECTORY_CAPACITY')
            target=json.loads(a['targets'])[a['stage']];need(a['actual']+sum(r['upper_bound'] for r in active)+upper<=target,'BUDGET_BOUNDARY')
            self.db.execute("INSERT INTO requests VALUES(?,?,?,?,'RESERVED',?,?,NULL,NULL,NULL)",(rid,t,role,generation,upper,proof_sha));self.event(t,'REQUEST_RESERVED',{'request_id':rid,'role':role,'upper':upper,'proof_sha256':proof_sha})
    def sent(self,rid):
        with self.tx():
            r=self.db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone();need(r is not None and r['state']=='RESERVED','REQUEST_NOT_RESERVED');need(not self.admission_fault(r['trajectory']),'ADMISSION_CLOSED_IN_MEMORY_FAULT')
            self.db.execute("UPDATE requests SET state='SENT' WHERE id=?",(rid,));self.event(r['trajectory'],'SENT',{'request_id':rid})
    def cancel_unsent(self,rid):
        with self.tx():
            r=self.db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone();need(r is not None and r['state']=='RESERVED','POSSIBLE_EXECUTION_NO_RELEASE')
            self.db.execute("UPDATE requests SET state='CANCELLED_UNSENT' WHERE id=?",(rid,));self.event(r['trajectory'],'CANCELLED_UNSENT',{'request_id':rid})
    def unknown(self,rid,code='TRANSPORT_UNKNOWN'):
        ident(code)
        with self.tx():
            r=self.db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
            if r is not None and r['state']=='UNKNOWN' and self.unknown_policy_enabled() and self.unknown_charged(rid):return
            need(r is not None and r['state']=='SENT','REQUEST_NOT_SENT')
            self.db.execute("UPDATE requests SET state='UNKNOWN' WHERE id=?",(rid,));self.event(r['trajectory'],'UNKNOWN_EXECUTION',{'request_id':rid,'code':code})
            if self.unknown_policy_enabled():
                self._charge_unknown_at_reservation(rid);self._unknown_thresholds(r['trajectory'])
            else:self.db.execute("UPDATE accounts SET state='DRAINING' WHERE trajectory=?",(r['trajectory'],))
    def settle(self,rid,input_tokens,output_tokens,receipt_sha,*,pending_tools=()):
        integer(input_tokens,'INPUT_TOKENS');integer(output_tokens,'OUTPUT_TOKENS');sha(receipt_sha)
        need(type(pending_tools)in (list,tuple) and len(set(pending_tools))==len(pending_tools),'PENDING_TOOLS')
        for x in pending_tools:ident(x)
        breach=False
        with self.tx():
            r=self.db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone();need(r is not None,'REQUEST_UNKNOWN')
            if r['state']=='SETTLED':
                need((r['input'],r['output'],r['receipt_sha'])==(input_tokens,output_tokens,receipt_sha),'RECEIPT_CONFLICT');return
            need(not self.unknown_charged(rid),'UNKNOWN_ALREADY_CHARGED_NO_USAGE_REWRITE')
            need(r['state']in ('SENT','UNKNOWN'),'REQUEST_NOT_SENT')
            self.db.execute("UPDATE requests SET state='SETTLED',input=?,output=?,receipt_sha=? WHERE id=?",(input_tokens,output_tokens,receipt_sha,rid))
            self.db.execute('UPDATE accounts SET actual=actual+? WHERE trajectory=?',(input_tokens+output_tokens,r['trajectory']))
            for op in pending_tools:self.db.execute("INSERT INTO operations VALUES(?,?,?,?,'TOOL','ACTIVE',?)",(op,r['trajectory'],r['role'],r['generation'],rid))
            self.event(r['trajectory'],'SETTLED',{'request_id':rid,'input_tokens':input_tokens,'output_tokens':output_tokens,'receipt_sha256':receipt_sha,'pending_tools':list(pending_tools)})
            self._unknown_thresholds(r['trajectory'])
            s=self.frontier(r['trajectory']);breach=input_tokens+output_tokens>r['upper_bound'] or s['actual']+s['reserved']>s['target']
            if breach:self.db.execute("UPDATE accounts SET state='FAULT' WHERE trajectory=?",(r['trajectory'],));self.event(r['trajectory'],'UPPER_BOUND_BREACH',{'request_id':rid,'actual':input_tokens+output_tokens,'reserved_upper':r['upper_bound']})
        if breach:raise Refused('UPPER_BOUND_BREACH_USAGE_RETAINED')
    def operation_start(self,t,role,generation,op,kind,*,parent_tool_operation=None,whole_team_scope=None):
        ident(op);need(kind in ('GIT_READ','GIT_WRITE','CHAT_READ','CHAT_WRITE'),'BRIDGE_METHOD')
        with self.tx():
            need(not self.admission_fault(t),'BRIDGE_ADMISSION_CLOSED_IN_MEMORY_FAULT')
            a=self._identity(t,role,generation)
            parent=None
            if parent_tool_operation is not None:
                parent=self.db.execute('SELECT * FROM operations WHERE id=?',(parent_tool_operation,)).fetchone()
                need(parent is not None and parent['kind']=='TOOL' and parent['state']=='ACTIVE' and (parent['trajectory'],parent['role'],parent['generation'])==(t,role,generation),'BRIDGE_PARENT_TOOL_NOT_ACTIVE_OR_SCOPE'if a['state']=='RUNNING'else'BRIDGE_ADMISSION_CLOSED')
            coarse=False
            if whole_team_scope is not None:
                from native_whole_team import NativeWholeTeamRegistration
                from native_writer_fence import NativeWriterFence
                r=whole_team_scope
                need(type(r)is NativeWholeTeamRegistration and r.ledger is self and r.t==t
                     and getattr(self,'native_whole_team_registrations',{}).get(t)is r
                     and type(r.owner.writer_fence)is NativeWriterFence
                     and r.owner.writer_fence.whole_team is r
                     and r.owner.writer_fence.state=='REGISTERED'
                     and kind in ('GIT_READ','GIT_WRITE') and parent_tool_operation is None,
                     'BRIDGE_ORIGINAL_WHOLE_TEAM_GIT_SCOPE')
                # Coarse ROLE admission, explicitly NOT fabricated ancestry.
                # A shell callback already admitted before the cut may finish
                # its native Git work. New idle/background exchanges park.
                coarse=self.db.execute("SELECT COUNT(*) FROM operations WHERE trajectory=? AND role=? AND generation=? AND kind='TOOL' AND state='ACTIVE'",(t,role,generation)).fetchone()[0]>0
            if a['state']!='RUNNING':
                need(a['state']=='DRAINING' and (parent is not None or coarse),'BRIDGE_ADMISSION_CLOSED')
            self.db.execute("INSERT INTO operations VALUES(?,?,?,?,?,'ACTIVE',?)",(op,t,role,generation,kind,parent_tool_operation));self.event(t,'OPERATION_STARTED',{'operation_id':op,'role':role,'kind':kind,'parent_tool_operation':parent_tool_operation})
    def operation_end(self,op):
        with self.tx():
            r=self.db.execute('SELECT * FROM operations WHERE id=?',(op,)).fetchone();need(r is not None,'UNKNOWN_OPERATION')
            if r['state']in ('COMPLETE','AUDIT_RELEASED'):return
            if r['kind']=='TOOL':
                need(self.db.execute("SELECT COUNT(*) FROM operations WHERE parent=? AND state='ACTIVE'",(op,)).fetchone()[0]==0,'TOOL_DEPENDENT_BRIDGE_NOT_TERMINAL')
            self.db.execute("UPDATE operations SET state='COMPLETE' WHERE id=?",(op,));self.event(r['trajectory'],'OPERATION_COMPLETE',{'operation_id':op})
    def tool_audit_released(self,op,identity,generation):
        """Only a same-role, original settled model TOOL may be audit-released.

        AUDIT_RELEASED is NOT COMPLETE/physical terminal; original business
        children, model requests/reservations, and writer freeze stay unchanged.
        Full-context history may mention the same tool on many later requests;
        that is not a new mismatch and must not mint another terminal claim.
        """
        with self.mutex:
            t,role=identity;self._identity(t,role,generation)
            row=self.db.execute('SELECT * FROM operations WHERE id=?',(op,)).fetchone()
            need(row is not None and row['kind']=='TOOL'
                 and (row['trajectory'],row['role'])==identity
                 and type(row['generation'])is int and row['generation']<=generation,
                 'TOOL_AUDIT_ORIGINAL_OWNED_TOOL_REQUIRED')
            parent=self.db.execute('SELECT * FROM requests WHERE id=?',(row['parent'],)).fetchone()
            need(parent is not None and parent['state']=='SETTLED'
                 and (parent['trajectory'],parent['role'],parent['generation'])==
                     (t,role,row['generation']), 'TOOL_AUDIT_ORIGINAL_SETTLED_PARENT_REQUIRED')
            children=self.db.execute('SELECT * FROM operations WHERE parent=?',(op,)).fetchall()
            need(all((c['trajectory'],c['role'],c['generation'])==(t,role,row['generation'])
                 and c['kind']in ('GIT_READ','GIT_WRITE','CHAT_READ','CHAT_WRITE')for c in children),
                 'TOOL_AUDIT_BUSINESS_CHILD_SCOPE')
            return row['state']=='AUDIT_RELEASED'
    def audit_tool_release(self,op,identity,generation,guard_code):
        need(guard_code in TOOL_CUSTODY_AUDIT_CODES,'TOOL_AUDIT_PROTECTED_GUARD')
        try:
            with self.tx():
                if self.tool_audit_released(op,identity,generation):return
                need(not self.admission_fault(identity[0]),'TOOL_AUDIT_SHARED_FAULT')
                row=self.db.execute('SELECT * FROM operations WHERE id=?',(op,)).fetchone()
                need(row['state']in ('ACTIVE','COMPLETE'),'TOOL_AUDIT_OPERATION_STATE')
                children=self.db.execute('SELECT state FROM operations WHERE parent=?',(op,)).fetchall()
                self.event(identity[0],'NATIVE_TOOL_CUSTODY_AUDIT_ONLY',{
                    'schema':'agensh-tool-custody-audit-only-v1','role':identity[1],
                    'generation':generation,'source_generation':row['generation'],
                    'operation_id':op,'guard_code':guard_code,'count':1,
                    'business_children':len(children),
                    'active_business_children':sum(c['state']=='ACTIVE'for c in children),
                    'logical_state':'AUDIT_RELEASED','physical_terminal_claimed':False,
                    'whole_team_freeze_still_required':True})
                # This distinct state records a policy decision, not a forged
                # OPERATION_COMPLETE nor a fabricated native physical receipt.
                self.db.execute("UPDATE operations SET state='AUDIT_RELEASED' WHERE id=?",(op,))
        except Refused:raise
        except Exception:
            self.latch_fault(identity[0],'TOOL_AUDIT_STORAGE_UNKNOWN')
            raise Refused('TOOL_AUDIT_STORAGE_UNKNOWN')from None
    def audit_role_tools(self,identity,generation,guard_code):
        with self.mutex:
            self._identity(*identity,generation)
            rows=self.db.execute("SELECT id FROM operations WHERE trajectory=?AND role=?AND kind='TOOL'AND state='ACTIVE' ORDER BY id",identity).fetchall()
            for row in rows:self.audit_tool_release(row['id'],identity,generation,guard_code)
    def close_admission(self,t,reason):
        ident(reason)
        with self.tx():
            a=self.account(t);need(a['state']=='RUNNING','NOT_RUNNING')
            self.db.execute("UPDATE accounts SET state='DRAINING' WHERE trajectory=?",(t,));self.event(t,'ADMISSION_CLOSED',{'reason':reason,'generation':a['generation']})
    def ack(self,t,component,generation,receipt_sha):
        """Trusted native action-boundary/service-backup ACK, not worker JSON."""
        sha(receipt_sha)
        with self.tx():
            need(not self.admission_fault(t),'ACK_FAULT_NOT_QUIESCENT')
            a=self.account(t);need(type(generation)is int and a['generation']==generation and a['state']=='DRAINING','ACK_BOUNDARY')
            need(component in set(json.loads(a['roles']))|SERVICES,'ACK_COMPONENT')
            if component in json.loads(a['roles']):
                pending=self.db.execute("SELECT COUNT(*) FROM requests WHERE trajectory=? AND role=? AND "+LOGICAL_PENDING,(t,component)).fetchone()[0]
                ops=self.db.execute("SELECT COUNT(*) FROM operations WHERE trajectory=? AND role=? AND state='ACTIVE'",(t,component)).fetchone()[0]
                need(pending==ops==0,'ROLE_NOT_QUIESCENT')
            else:
                # All accepted work must finish BEFORE a native consistent backup.
                # With DRAINING and no active TOOL, operation_start cannot admit
                # another write; no SENT can later produce a new accepted TOOL.
                f=self.frontier(t)
                need(f['reserved']==f['unresolved']==f['active_operations']==0,'SERVICE_BACKUP_BEFORE_FULL_DRAIN')
            old=self.db.execute('SELECT receipt_sha FROM acks WHERE trajectory=? AND generation=? AND component=?',(t,generation,component)).fetchone()
            if old:need(old[0]==receipt_sha,'ACK_CONFLICT');return
            self.db.execute('INSERT INTO acks VALUES(?,?,?,?)',(t,generation,component,receipt_sha));self.event(t,'QUIESCENCE_ACK',{'component':component,'receipt_sha256':receipt_sha})
    def begin_capture(self,t):
        with self.tx():
            need(not self.admission_fault(t),'FAULT_NOT_QUIESCENT')
            a=self.account(t);need(a['state']=='DRAINING','NOT_DRAINING');s=self.frontier(t)
            need(s['reserved']==s['unresolved']==s['active_operations']==0,'NOT_QUIESCENT')
            have={r[0] for r in self.db.execute('SELECT component FROM acks WHERE trajectory=? AND generation=?',(t,a['generation']))}
            need(have==set(s['roles'])|SERVICES,'ALL_ROLE_SERVICE_ACKS_REQUIRED')
            self.db.execute("UPDATE accounts SET state='CAPTURING' WHERE trajectory=?",(t,));self.event(t,'CAPTURING',{'generation':a['generation']});return self.frontier(t)
    def commit(self,t,generation,ref_sha):
        sha(ref_sha)
        with self.tx():
            a=self.account(t);need(type(generation)is int and a['generation']==generation and a['state']=='CAPTURING','NOT_CAPTURING')
            target=json.loads(a['targets'])[a['stage']];self.db.execute('INSERT INTO snapshots VALUES(?,?,?,?)',(t,generation,target,ref_sha))
            self.db.execute("UPDATE accounts SET state='COMMITTED_PARKED' WHERE trajectory=?",(t,));self.event(t,'COMMITTED_PARKED',{'snapshot_ref_sha256':ref_sha,'target':target})
    def resume_next(self,t):
        with self.tx():
            need(not self.admission_fault(t),'TRAJECTORY_FAULT_NO_SEND')
            a=self.account(t);need(a['state']=='COMMITTED_PARKED' and a['stage']+1<len(json.loads(a['targets'])),'NO_NEXT_PARKED_STAGE')
            self.db.execute("UPDATE accounts SET stage=stage+1,generation=generation+1,state='RUNNING' WHERE trajectory=?",(t,));self.event(t,'EXPLICIT_NEXT_STAGE',{'generation':a['generation']+1})
            return self.frontier(t)
    def backup(self,destination):
        p=Path(destination);need(not p.exists() and not p.is_symlink(),'BACKUP_NO_CLOBBER')
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd)
        with self.mutex:
            target=sqlite3.connect(p)
            try:self.db.backup(target)
            finally:target.close()
            os.chmod(p,0o600)
            fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
            try:os.fsync(fd)
            finally:os.close(fd)
    def close(self):
        with self.mutex:
            clean=False
            try:
                clean=not self.memory_faults and not self.native_services and self.global_unresolved()==0 and self.db.execute("SELECT COUNT(*) FROM operations WHERE state='ACTIVE'").fetchone()[0]==0
            finally:
                try:self.db.close()
                finally:os.close(self.fd)
            if clean:
                self.owner_marker.unlink();sync_dir(self.home)

