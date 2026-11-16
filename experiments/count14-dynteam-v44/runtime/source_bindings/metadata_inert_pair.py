"""Exact-class, existing-inode metadata-only custody. NEVER a paid hydrator.

No original constructor, broad SQLite pin, event/body/result read, migration,
transaction, runtime close, SDK load, request, signal or dispatcher. A ticket
reference supplies material, NOT authority. Authority remains the independent
fixed verifier and is INERT-only. Original runtime methods are quarantined.
"""
from dataclasses import dataclass
from pathlib import Path
from types import MethodType, SimpleNamespace
import copy
import fcntl
import hashlib
import importlib
import json
import os
import sqlite3
import stat
import threading

import paid_cold_material as M
from bounded_metadata_ro import ReadBudget
from native_peer_registry import ProcessBirth, process_birth

PINS = dict(native_cold_owner='22af3bfe52f711ee27bb4e523ed8ab13d375528b05f927afcb64c921095b5ddf',
    original_relay_core='89ac900e66caa67887504522c574c1870f7a8faf51542fe248ca7f35b1541556',
    budget='a05ca90afffb7c149766cf4b74126eb94ba79910afd72049a1ff54d2bc50df8f',
    final_queue='7a7aeadc26ca35bdd64c6569634dab4ff6e9617ec9dee18a71ccd6797742773c',
    bounded_metadata_ro='621cd0db6da2d1e6422537f6ae2188ac8466627efe803d8b4d39f260bfb7c249',
    normal_cold_sealer='dd33e7a7a336c872086b3769f70e112942a466a18f52d099ce188ebe1e129e68')
_SEAL=object()
_REGISTERED={}
_ALLOWED=frozenset(('paid_FINAL_controls','native_SDK_epoch_controls','normal_clock_controls'))
_LEDGER_COLUMNS={
    'accounts':frozenset(('trajectory','manifest_sha','roles','targets','stage','generation','state','actual','request_cap')),
    'requests':frozenset(('id','trajectory','role','generation','state','upper_bound','proof_sha','input','output','receipt_sha')),
    'operations':frozenset(('id','trajectory','role','generation','kind','state','parent')),
    'aux_scopes':frozenset(('scope','trajectory','binding','epoch')),
    'aux_permits':frozenset(('id','scope','epoch','state','request_id','terminal_sha')),
    'unknown_charges':frozenset(('request_id','upper_bound','settlement_seq')),
    'events':frozenset(('seq',)),
}
_QUEUE_COLUMNS={
    'config':frozenset(('singleton','manifest','cap')),
    'points':frozenset(('point','trajectory','setting','target','input_root','input_policy')),
    'jobs':frozenset(('id','point','replicate','state','claim','child','terminal')),
    'replacement_jobs':frozenset(('id','point','replicate','state','claim','child','terminal','attempt','original_job')),
    'formal_final_control_jobs_v1':frozenset(('id','point','replicate','state','claim','child','terminal','attempt','original_job')),
    'formal_final_control_authorizations_v1':frozenset(('id','metadata','sha256')),
    'replicate_partials':frozenset(('job_id','metadata','sha256')),
    'events':frozenset(('seq',)),
}
_SCHEMA_COLUMNS=frozenset(('type','name','tbl_name','rootpage','sql'))


def verify_sources():
    for name,pin in PINS.items():
        p=Path(importlib.import_module(name).__file__)
        M.need(p.is_absolute() and p.resolve()==p and not p.is_symlink() and
            hashlib.sha256(p.read_bytes()).hexdigest()==pin,'INERT_PAIR_FIXED_ORIGINAL_SOURCE_PINS')
    return dict(PINS)


def _budget(value):
    M.need(type(value) is ReadBudget,'INERT_PAIR_EXACT_FINITE_READ_BUDGET')
    value.check()


def _refuse(*args,**kwargs):
    raise M.PaidColdWait('INERT_PAIR_RUNTIME_UNHYDRATED_NO_TRANSACTION_OR_ACTIVATION')


def _quarantine(value,cls,read_only=()):
    for name in vars(cls):
        if not name.startswith('__') and name not in read_only and callable(getattr(cls,name,None)):
            setattr(value,name,MethodType(_refuse,value))


class _Cursor:
    def __init__(self,source,connection):self._source,self._connection=source,connection
    def fetchone(self):
        self._connection._check()
        try:row=self._source.fetchone()
        except sqlite3.Error:raise M.PaidColdWait('INERT_PAIR_FIXED_RO_SQL_WAIT') from None
        self._connection._check();return row
    def __iter__(self):
        while True:
            row=self.fetchone()
            if row is None:return
            yield row
    def fetchall(self):return list(self)


class _ReadOnly:
    """New connection only; authorizer forbids all writes and private columns."""
    def __init__(self,path,kind,budget):
        self.path,self.kind,self.budget,self.thread=path,kind,budget,threading.get_ident()
        self._closed=False
        self._raw=sqlite3.connect(path.as_uri()+'?mode=ro&cache=private',uri=True,
            timeout=0,isolation_level=None,check_same_thread=True)
        self._raw.row_factory=sqlite3.Row
        self._raw.execute('PRAGMA query_only=ON') # this NEW local handle only
        self._raw.set_progress_handler(lambda:int(__import__('time').monotonic()>=self.budget.deadline),1000)
        self._raw.set_authorizer(self._authorize)
    def _authorize(self,action,table,column,database,origin):
        if action==sqlite3.SQLITE_SELECT:return sqlite3.SQLITE_OK
        if action==sqlite3.SQLITE_FUNCTION:
            return sqlite3.SQLITE_OK if column.lower() in ('count','sum','max','coalesce') else sqlite3.SQLITE_DENY
        if action==sqlite3.SQLITE_PRAGMA:
            return sqlite3.SQLITE_OK if table=='table_info' else sqlite3.SQLITE_DENY
        if action==sqlite3.SQLITE_READ:
            columns=_LEDGER_COLUMNS if self.kind=='ledger' else _QUEUE_COLUMNS
            if table in ('sqlite_master','sqlite_schema'):
                return sqlite3.SQLITE_OK if column in _SCHEMA_COLUMNS or column=='' else sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if table in columns and (column in columns[table] or column=='') else sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_DENY
    def _check(self):
        _budget(self.budget)
        M.need(not self._closed and threading.get_ident()==self.thread,'INERT_PAIR_OWN_LIVE_RO_HANDLE_AND_METADATA_THREAD')
    def use_budget(self,budget):
        _budget(budget);self.budget=budget;self._check()
    def execute(self,sql,parameters=()):
        self._check()
        M.need(type(sql) is str and (sql.startswith('SELECT ') or sql.startswith('PRAGMA table_info(')),
            'INERT_PAIR_FIXED_SELECT_OR_TABLE_SCHEMA_ONLY')
        if sql=='SELECT * FROM accounts WHERE trajectory=?':
            sql='SELECT '+','.join(sorted(_LEDGER_COLUMNS['accounts']))+' FROM accounts WHERE trajectory=?'
        M.need('*' not in sql.replace('COUNT(*)',''),'INERT_PAIR_NO_WILDCARD_PRIVATE_BODY_READ')
        try:cursor=self._raw.execute(sql,parameters)
        except sqlite3.Error:raise M.PaidColdWait('INERT_PAIR_FIXED_RO_SQL_WAIT') from None
        self._check();return _Cursor(cursor,self)
    def _close_local(self):
        if not self._closed:self._raw.close();self._closed=True


@dataclass(frozen=True)
class VerifiedMetadataPair:
    owner: object
    source_birth: ProcessBirth
    new_owner_birth: ProcessBirth
    material: dict
    allowed_components: frozenset
    qualification_only: bool
    full_used_fd: int
    lock_fds: tuple
    source_financial_equality_proven: bool
    safe_to_TERM: bool=False
    paid_activation_authorized: bool=False
    whole_runnable_ready: bool=False


class MetadataInertPair:
    def __init__(self,*args,**kwargs):raise M.PaidColdWait('INERT_PAIR_ONLY_FIXED_ATTACHMENT_ENTRY')
    def _close_local(self):
        for db in self.connections:db._close_local()
        self.connections.clear()
        for fd in self.lock_fds:os.close(fd)
        self.lock_fds.clear()
        if self.owner is not None:_REGISTERED.pop(id(self.owner),None)
        self.closed=True
    def close_OWN_after_test(self):
        M.need(self.qualification_only is True and self.new_owner_birth==process_birth(os.getpid()),
            'INERT_PAIR_ONLY_OWN_TEST_NORMAL_LOCAL_CONNECTION_CLOSE')
        self._close_local()


def _ended(material,current):
    old=material['source_birth']
    M.need(type(old) is ProcessBirth and old!=current and old.uid==current.uid and M.nonexecuting(old,current),
        'INERT_PAIR_WAIT_OLD_OWNER_ENDED_SAME_UID_BOOT_PIDNS')
    return old


def _paths(material,*,own):
    home=M.existing(material['owner_home'],directory=True,private=True)
    lh=M.existing(material['ledger_home'],directory=True,private=True)
    qh=M.existing(material['queue_home'],directory=True,private=True)
    full=M.existing(material['full_used_directory'],directory=True,private=True)
    M.need(lh==home/'ledger' and qh==home/('queue' if own and material.get('OWN_scope')=='OWN_REAL_QUEUE_INERT_LINEAGE_MATERIAL_V1' else 'final-queue') and
        full==home/'full-affinity-domain-control-v1','INERT_PAIR_EXACT_EXISTING_METADATA_HOMES')
    for key,path in (('ledger_database',lh/'ledger.sqlite'),('queue_database',qh/'queue.sqlite')):
        M.need(M.existing(material[key],private=True)==path,'INERT_PAIR_ORIGINAL_DATABASE_CANONICAL_NAME')
    locks=material['locks']
    M.need(type(locks) is tuple and len(locks)==3 and [kind for kind,row in locks]==['ledger','queue','fullused'] and
        locks[0][1]['path']==str(lh/'owner.lock') and locks[1][1]['path']==str(qh/'owner.lock') and
        locks[2][1]==material['full_used_directory'],'INERT_PAIR_EXACT_LEDGER_QUEUE_FULLUSED_LOCK_INVENTORY')
    for kind,row in locks:M.existing(row,directory=kind=='fullused',private=True)
    if own:
        M.need(home.name.startswith('OWN-') and all(p.is_relative_to(home) for p in (lh,qh,full)),
            'INERT_PAIR_OWN_PHYSICAL_SANDBOX_ONLY_NOT_PRODUCTION_ROOT_IO')
    else:
        M.registered_scope(material['contract'],material['contract_sha256'])
        M.need(home==Path(material['contract']['arms'][0]['root'])/'owner' and
            home.is_relative_to('/mnt/ptb-scratch2'),'INERT_PAIR_REGISTERED_PRODUCTION_NEW_ARM_HOME')
    return home,lh,qh,full


def _financial(pair,budget):
    """Use EXACT original frontier/account/formulas against the RO-only pair."""
    import normal_cold_sealer as S
    from queue_control import CarrierQueueDomain
    for db in pair.connections:db.use_budget(budget)
    source=pair.material['financial_metadata']
    # OWN components may have a subset of accounts. This is a COUNT/SUM
    # observation only, explicitly NOT source financial equality or paid proof.
    if pair.qualification_only:
        l=pair.ledger.db
        return dict(schema='OWN-fixed-six-table-count-sum-INERT-observation-v1',
            accounts=list(l.execute('SELECT COUNT(*),COALESCE(SUM(actual),0) FROM accounts').fetchone()),
            requests=list(l.execute('SELECT COUNT(*),COALESCE(SUM(upper_bound),0),COALESCE(SUM(input),0),COALESCE(SUM(output),0) FROM requests').fetchone()),
            operations=l.execute('SELECT COUNT(*) FROM operations').fetchone()[0],
            unknown=list(l.execute('SELECT COUNT(*),COALESCE(SUM(upper_bound),0) FROM unknown_charges').fetchone()),
            scopes=l.execute('SELECT COUNT(*) FROM aux_scopes').fetchone()[0],
            permits=l.execute('SELECT COUNT(*) FROM aux_permits').fetchone()[0],
            source_financial_equality_proven=False)
    roles=source['registered_role_controls']
    detached=SimpleNamespace(epoch=roles['epoch'],births={(r['trajectory'],r['role']):r['birth_sha256'] for r in roles['births']},
        held={tuple(r) for r in roles['held']})
    view=SimpleNamespace(ledger=pair.ledger,queue=pair.queue,rows=pair.owner.core.rows,roles=detached)
    approved=CarrierQueueDomain.__new__(CarrierQueueDomain);approved.q=pair.queue
    return S.financial_controls(view,approved)


def _attach(material,*,read_budget,own,source_controls,ticket=None):
    from budget import Ledger
    from final_queue import FinalQueue
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    _budget(read_budget);verify_sources()
    M.need(type(material) is dict and material['qualification_only'] is own and
        M.digest(material['contract'])==M.sha(material['contract_sha256']), 'INERT_PAIR_TYPED_SCOPE_MATERIAL_NOT_FLAGS')
    current=process_birth(os.getpid());old=_ended(material,current)
    home,lh,qh,full=_paths(material,own=own)
    pair=object.__new__(MetadataInertPair)
    pair.connections=[];pair.lock_fds=[];pair.owner=None;pair.closed=False;pair._seal=_SEAL
    pair.material=copy.deepcopy(material);pair.source_birth=old;pair.new_owner_birth=current
    pair.qualification_only=own;pair.source_controls=copy.deepcopy(source_controls)
    pair.allowed_components=frozenset(source_controls)&_ALLOWED
    pair.control_lock_records=copy.deepcopy(material['locks'])
    pair.source_financial_equality_proven=False
    try:
        for kind,row in pair.control_lock_records:
            _budget(read_budget)
            fd=os.open(row['path'],os.O_RDONLY|os.O_NOFOLLOW|(os.O_DIRECTORY if kind=='fullused' else 0))
            pair.lock_fds.append(fd)
            M.need(M.stamp(os.fstat(fd))=={k:row[k] for k in M.stamp(os.fstat(fd))},'INERT_PAIR_OPENED_ORIGINAL_LOCK_INODE_OWNER_MODE')
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise M.PaidColdWait('INERT_PAIR_WAIT_EXISTING_CUSTODIAN_NO_FORCE_UNLOCK') from None
            _ended(material,current)
        for key,kind in (('ledger_database','ledger'),('queue_database','queue')):
            db=_ReadOnly(Path(material[key]['path']),kind,read_budget);pair.connections.append(db)
            M.existing(material[key],private=True)
        l=Ledger.__new__(Ledger);q=FinalQueue.__new__(FinalQueue)
        l.home,l.fd,l.db,l.mutex=lh,pair.lock_fds[0],pair.connections[0],threading.RLock()
        l.capacity_changed=threading.Condition(l.mutex)
        # Unhydrated is NOT an assertion that the old owner had no faults,
        # native services, sessions, connections, peers, or in-flight custody.
        l.memory_faults=l.native_services=l.native_unmanaged_cli=None
        l.owner_marker=lh/'owner.open'
        l._dynteam_catalogues={r['trajectory_id']:tuple(r['roles']) for r in material['contract']['trajectories']}
        l._dynteam_qualification_only=own
        config=qcfg=pair.connections[1].execute('SELECT manifest,cap FROM config WHERE singleton=1').fetchone()
        M.need(config is not None and config['manifest']==material['contract_sha256'] and
            type(config['cap']) is int and 1<=config['cap']<=12,'INERT_PAIR_ORIGINAL_QUEUE_SCOPE_CONFIG')
        q.home,q.fd,q.db,q.mutex,q.manifest,q.cap=qh,pair.lock_fds[1],pair.connections[1],threading.RLock(),qcfg['manifest'],qcfg['cap']
        _quarantine(l,Ledger,('account','frontier'));_quarantine(q,FinalQueue)
        pair.ledger,pair.queue=l,q
        core=OriginalRelayCore.__new__(OriginalRelayCore);owner=NativeColdOwner.__new__(NativeColdOwner)
        core.home,core.contract,core.rows=home,copy.deepcopy(material['contract']),{r['trajectory_id']:copy.deepcopy(r) for r in material['contract']['trajectories']}
        core.ledger,core.queue,core.qualification_only=l,q,own
        core.state='INERT_OWN_QUEUE_LINEAGE_ONLY' if own and material.get('OWN_scope')=='OWN_REAL_QUEUE_INERT_LINEAGE_MATERIAL_V1' else 'INERT_EXISTING_METADATA_ONLY_RUNTIME_UNHYDRATED'
        core.closed=False;core.errors=[];core.scientific_activation_qualified=False;core.native_worker_bindings_complete=False
        for name in ('sessions','control','peers','servers','engines','gate','roles','clocks','cas','native_sdk_startup_epochs',
                     'native_containers','publisher','journals','cohort_resources','system_health','formal_full_used_domain'):
            setattr(core,name,None)
        core.paid_old_owner_birth=__import__('dataclasses').asdict(old);core.paid_new_owner_birth=current
        owner.core,owner.ledger,owner.state,owner.errors=core,l,core.state,[]
        owner.layout=owner.bootstrap=owner.scientific_smoke=None
        core.metadata_inert_pair=owner.metadata_inert_pair=pair;pair.owner=owner
        _quarantine(core,OriginalRelayCore);_quarantine(owner,NativeColdOwner)
        if not own:
            accounts={r['trajectory']:dict(r) for r in l.db.execute('SELECT '+','.join(sorted(_LEDGER_COLUMNS['accounts']))+' FROM accounts')}
            M.need(set(accounts)==set(core.rows) and all(accounts[t]['manifest_sha']==material['contract_sha256'] and
                json.loads(accounts[t]['roles'])==core.rows[t]['roles'] for t in accounts),
                'INERT_PAIR_ORIGINAL_ALL_REGISTERED_LEDGER_ACCOUNTS')
        financial=_financial(pair,read_budget)
        if own:
            pair.material['financial_metadata']=financial
        else:
            M.need(financial==material['financial_metadata'],'INERT_PAIR_WAIT_SOURCE_CURRENT_FINANCIAL_EQUALITY')
            pair.source_financial_equality_proven=True
        _ended(material,current);_paths(pair.material,own=own)
        pair.ticket_identity=None if ticket is None else (ticket.path,ticket.sha256)
        _REGISTERED[id(owner)]=pair
        return owner
    except BaseException:
        pair._close_local();raise


def attach_inert_pair(ticket,*,read_budget):
    import normal_inert_cut as T
    _budget(read_budget)
    M.need(type(ticket) is T.NormalInertTicket,'INERT_PAIR_PRODUCTION_REFERENCE_NOT_OWN_OR_DICT')
    inspection=T.inspect_inert_reference(ticket,read_budget=read_budget)
    M.need(type(inspection) is T.InertTicketInspection and inspection.material['qualification_only'] is False,
        'INERT_PAIR_PRODUCTION_INSPECTED_NORMAL_SOURCE_MATERIAL')
    return _attach(inspection.material,read_budget=read_budget,own=False,source_controls=inspection.source_controls,ticket=ticket)


def _OWN_material(raw):
    M.need(type(raw) is dict and raw.get('OWN') is True and raw.get('schema') in
        ('OWN_REAL_QUEUE_INERT_LINEAGE_MATERIAL_V1','OWN_NATIVE_METADATA_ONLY'), 'INERT_PAIR_EXPLICIT_OWN_COMPONENT_SCOPE')
    home=M.existing(raw['owner_home'],directory=True,private=True)
    M.need(home.name.startswith('OWN-'),'INERT_PAIR_OWN_ROOT_NOT_PRODUCTION')
    M.need(M.digest(raw['contract'])==raw['contract_sha256'],'INERT_PAIR_OWN_UNCHANGED_CONTRACT_PIN')
    scope=raw['schema'];controls=raw['source_controls']
    if scope=='OWN_REAL_QUEUE_INERT_LINEAGE_MATERIAL_V1':
        ref=raw['carrier_descriptor'];p=Path(ref['path']);s=p.lstat()
        M.need(p==home/'host-control-carrier/QUEUE_CONTROL_DOMAIN_PUBLIC.json' and p.resolve()==p and
            not p.is_symlink() and stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid() and
            stat.S_IMODE(s.st_mode)==0o400 and s.st_nlink==1 and s.st_size<1024*1024,
            'INERT_PAIR_OWN_ORIGINAL_OFFLINE_CARRIER_DESCRIPTOR')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as f:
            M.need(M.stamp(os.fstat(f.fileno()))==M.stamp(s),'INERT_PAIR_OWN_DESCRIPTOR_OPENED_IDENTITY')
            data=f.read(1024*1024+1)
        M.need(hashlib.sha256(data).hexdigest()==M.sha(ref['sha256']) and M.stamp(p.lstat())==M.stamp(s),
            'INERT_PAIR_OWN_DESCRIPTOR_IMMUTABLE_PIN')
        row=M.strict(data)
        M.need(row['offline_OWN'] is True and row['production_install_authorized'] is False and
            row['queue_home']==raw['queue']['home']['path'] and row['ledger_home']==raw['ledger']['home']['path'] and
            row['contract_sha256']==raw['contract_sha256'] and set(controls)=={'paid_FINAL_controls'},
            'INERT_PAIR_OWN_ORIGINAL_CONTROL_DOMAIN_ONLY_NOT_PRODUCTION_ESCAPE')
    else:
        M.need(set(controls) and set(controls)<= {'native_SDK_epoch_controls','normal_clock_controls'} and
            all(r['trajectory_id'].startswith('OWN-') and Path(r['root']).is_relative_to(home)
                for r in raw['contract']['trajectories']), 'INERT_PAIR_OWN_NATIVE_ONLY_ACTUAL_SANDBOX_ROWS')
    old=raw['old_owner_birth'];old=M.birth(old) if type(old) is dict else old
    return dict(source_birth=old,contract=copy.deepcopy(raw['contract']),contract_sha256=raw['contract_sha256'],
        owner_home=copy.deepcopy(raw['owner_home']),ledger_home=copy.deepcopy(raw['ledger']['home']),
        ledger_database=copy.deepcopy(raw['ledger']['database']),queue_home=copy.deepcopy(raw['queue']['home']),
        queue_database=copy.deepcopy(raw['queue']['database']),full_used_directory=copy.deepcopy(raw['full_used_directory']),
        locks=tuple((kind,copy.deepcopy(row)) for kind,row in (('ledger',raw['ledger']['lock']),
            ('queue',raw['queue']['lock']),('fullused',raw['full_used_directory']))),
        financial_metadata=None,qualification_only=True,OWN_scope=scope)


def attach_OWN_metadata_pair(material,*,read_budget):
    _budget(read_budget)
    return _attach(_OWN_material(material),read_budget=read_budget,own=True,source_controls=material['source_controls'])


def _verify(owner,budget,own):
    from native_cold_owner import NativeColdOwner
    from original_relay_core import OriginalRelayCore
    _budget(budget);verify_sources()
    M.need(type(owner) is NativeColdOwner and type(owner.core) is OriginalRelayCore,
        'INERT_PAIR_EXACT_REGISTERED_ORIGINAL_OWNER_CORE_TYPES')
    pair=_REGISTERED.get(id(owner))
    M.need(type(pair) is MetadataInertPair and pair._seal is _SEAL and pair.owner is owner and
        owner.metadata_inert_pair is owner.core.metadata_inert_pair is pair and not pair.closed and
        pair.qualification_only is own and pair.new_owner_birth==process_birth(os.getpid()) and
        not owner.core.scientific_activation_qualified and owner.core.state.startswith('INERT_'),
        'INERT_PAIR_SAME_REGISTERED_NEW_BIRTH_HELD_NONRUNNABLE_GRAPH')
    _ended(pair.material,pair.new_owner_birth);_paths(pair.material,own=own)
    M.need(len(pair.control_lock_records)==len(pair.lock_fds)==3,'INERT_PAIR_COMPLETE_REAL_LOCK_FD_CUSTODY')
    for (kind,row),fd in zip(pair.control_lock_records,pair.lock_fds):
        st=os.fstat(fd)
        flags=Path('/proc/self/fdinfo',str(fd)).read_text().splitlines()
        M.need(M.stamp(st)=={k:row[k] for k in M.stamp(st)} and
            any(v.startswith('lock:') and ' FLOCK ' in v and ' WRITE ' in v for v in flags),
            'INERT_PAIR_REGISTERED_SAME_INODE_OWN_EXCLUSIVE_FLOCK_STILL_HELD')
    financial=_financial(pair,budget)
    M.need(financial==pair.material['financial_metadata'],'INERT_PAIR_CURRENT_FIXED_FINANCIAL_EQUATIONS_UNCHANGED')
    return VerifiedMetadataPair(owner,pair.source_birth,pair.new_owner_birth,copy.deepcopy(pair.material),
        pair.allowed_components,own,pair.lock_fds[2],tuple(pair.lock_fds),pair.source_financial_equality_proven)


def verify_registered_pair(owner,*,ticket,read_budget):
    import normal_inert_cut as T
    M.need(type(ticket) is T.NormalInertTicket,'INERT_PAIR_PRODUCTION_VERIFIER_REJECTS_OWN_TICKET')
    inspection=T.inspect_inert_reference(ticket,read_budget=read_budget)
    proof=_verify(owner,read_budget,False)
    pair=owner.core.metadata_inert_pair
    M.need(inspection.material==pair.material and inspection.source_controls==pair.source_controls and
        pair.ticket_identity==(ticket.path,ticket.sha256),'INERT_PAIR_SAME_EXACT_FIXED_SOURCE_REFERENCE')
    return proof


def verify_OWN_registered_pair(owner,*,read_budget):
    return _verify(owner,read_budget,True)
