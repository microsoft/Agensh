"""Approved additive two-table carrier, exact EMPTY cold new-root boundary.

No old SQL/schema/record or Ledger formula is changed. Shared DDL executor is
also tested behind an explicitly OWN boundary; it never certifies Dev4/owner.
"""
from pathlib import Path
from dataclasses import dataclass
import ast,copy,fcntl,hashlib,inspect,os,re,sqlite3
from common import need,digest,wire,publish,hash_file,private_dir
from budget import Ledger
from final_queue import FinalQueue,process_identity
import final_attempts
from queue_control import CarrierQueueDomain,DDL,AUTH,JOBS,source_pins as proposal_pins,SCHEMA,POLICY
from formal_scope import validate_contract,PUBLIC_CONTRACT_CANONICAL_SHA256

APPROVAL='CARETAKER_APPROVE_DYNTEAM_FORMAL_QUEUE_CONTROL_CARRIER'
PROPOSAL='ccf9588789d3f14ea99e82a25a6608c8d45c4c5e4c3d3dacefc68c1d52c42258'
SQL_DIFF='1bf3bbe52f4c486cd0bb977d419c7ea905207a7f4c8fd3296901821be7df3a90'
DDL_RAW='3b61554abf52f906ccf9ae1a191d4617afd80ab35b673607097d8ec3fbec95ed'
OLD_TABLES=('config','points','jobs','events','replacement_jobs','replicate_partials')


def approved_source_pins():
    root=Path(__file__).resolve().parent
    names=('approved_queue_install.py','approved_queue_reader.py','approved_queue_binding.py',
           'approved_queue_cold.py','approved_queue_child.py','approved_queue_child_ports.py')
    return {n:hash_file(root/n)['sha256']for n in names}


def verify_approval_sources():
    p=Path(__file__).resolve().parents[1]/'formal100m-allowance-queue-proposal-v1'
    need(hash_file(p/'FILES_AND_DELTA_PUBLIC.json')['sha256']==PROPOSAL and
         hash_file(p/'SQL_DIFF_PUBLIC.json')['sha256']==SQL_DIFF and
         hashlib.sha256(DDL.encode()).hexdigest()==DDL_RAW,'APPROVED_CARRIER_EXACT_CARETAKER_PROPOSAL_AND_DDL')


def schemas(db):
    return [tuple(r)for r in db.execute("SELECT type,name,tbl_name,rootpage,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name")]


def rows(db,table):
    need(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',table)is not None,'APPROVED_CARRIER_FIXED_TABLE_IDENTIFIER')
    return [tuple(r)for r in db.execute('SELECT * FROM "'+table+'" ORDER BY rowid')]


def snapshot(l,q):
    return dict(queue_schema=schemas(q.db),queue_rows={n:rows(q.db,n)for n in OLD_TABLES},
        ledger_schema=schemas(l.db),ledger_rows={r[0]:rows(l.db,r[0])for r in
            l.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")})


def pristine_queue_schema():
    """Only original literal schema scripts, ordinary in-memory SQLite, no q."""
    scripts=[]
    for fn in(FinalQueue.__init__,final_attempts.initialize):
        tree=ast.parse(__import__('textwrap').dedent(inspect.getsource(fn)))
        found=[n.args[0].value for n in ast.walk(tree)if isinstance(n,ast.Call)and
            isinstance(n.func,ast.Attribute)and n.func.attr=='executescript'and len(n.args)==1 and
            isinstance(n.args[0],ast.Constant)and type(n.args[0].value)is str]
        need(len(found)==1,'APPROVED_CARRIER_ORIGINAL_QUEUE_SCHEMA_LITERAL')
        scripts.extend(found)
    db=sqlite3.connect(':memory:')
    try:
        for script in scripts:db.executescript(script)
        return [(r[0],r[1],r[2],r[4])for r in schemas(db)]
    finally:db.close()


def ddl_statements():
    buffer='';result=[]
    for line in DDL.splitlines(keepends=True):
        buffer+=line
        if sqlite3.complete_statement(buffer):result.append(buffer);buffer=''
    need(not buffer.strip() and len(result)==7 and ''.join(result)+buffer==DDL,
         'APPROVED_CARRIER_EXACT_TWO_TABLE_FIVE_TRIGGER_DDL_SPLIT')
    return result


def assert_empty_locked(l,q):
    need(type(l)is Ledger and type(q)is FinalQueue and not l.db.in_transaction and not q.db.in_transaction,
         'APPROVED_CARRIER_EXACT_ORIGINAL_IDLE_CONNECTIONS')
    need([(r[0],r[1],r[2],r[4])for r in schemas(q.db)]==pristine_queue_schema(),
         'APPROVED_CARRIER_OLD_QUEUE_SCHEMA_PRISTINE_AND_NO_CONTROL_TABLES')
    need(q.db.execute('SELECT COUNT(*)FROM points').fetchone()[0]==0 and
         all(q.db.execute('SELECT COUNT(*)FROM '+n).fetchone()[0]==0 for n in('jobs','replacement_jobs','replicate_partials')),
         'APPROVED_CARRIER_NO_QUEUED_OR_LIVE_OR_FAILED_OLD_JOBS_POINTS')
    need(l.db.execute('SELECT COUNT(*)FROM requests').fetchone()[0]==0 and
         l.db.execute('SELECT COUNT(*)FROM aux_permits').fetchone()[0]==0,
         'APPROVED_CARRIER_ZERO_EXPERIMENT_REQUESTS_AND_AUX_PERMITS')


class ApprovedOwnDDLBoundary:
    def __init__(self,l,q,root):
        root=Path(root)
        need(root.resolve()==root and root.name.startswith('OWN-')and type(l)is Ledger and type(q)is FinalQueue and
             l.home==root/'ledger'and q.home==root/'queue','APPROVED_CARRIER_EXPLICIT_OWN_ONLY_DDL_BOUNDARY')
        self.l,self.q,self.root=l,q,root


def execute_exact_ddl(l,q,*,production_guard=None,OWN_boundary=None):
    """Caller holds original ledger->queue mutexes at an already typed boundary."""
    if production_guard is not None:
        need(OWN_boundary is None and type(production_guard)is tuple and len(production_guard)==3,
             'APPROVED_CARRIER_ONLY_ONE_EXACT_PRODUCTION_DDL_BOUNDARY')
        core,_=guard(*production_guard)
        need(core.ledger is l and core.queue is q,'APPROVED_CARRIER_PRODUCTION_BOUNDARY_SAME_DB_OBJECTS')
    else:
        need(type(OWN_boundary)is ApprovedOwnDDLBoundary and OWN_boundary.l is l and OWN_boundary.q is q,
             'APPROVED_CARRIER_NO_UNGUARDED_OR_IMPLICIT_OWN_DDL')
    verify_approval_sources();assert_empty_locked(l,q);before=snapshot(l,q)
    with q.tx():
        for statement in ddl_statements():q.db.execute(statement)
    after=snapshot(l,q)
    old_names={r[1]for r in before['queue_schema']}
    old_after=[r for r in after['queue_schema']if r[1]in old_names]
    need(old_after==before['queue_schema'] and before['queue_rows']==after['queue_rows'] and
         before['ledger_schema']==after['ledger_schema'] and before['ledger_rows']==after['ledger_rows'],
         'APPROVED_CARRIER_OLD_SCHEMA_ROWS_EVENT_PREFIX_AND_LEDGER_EXACT_EQUAL')
    new=[r for r in after['queue_schema']if r[1]not in old_names]
    need({r[1]for r in new if r[0]=='table'}=={AUTH,JOBS}and len(new)==7,
         'APPROVED_CARRIER_ONLY_EXACT_TWO_TABLES_AND_FIVE_APPEND_TRIGGERS')
    return dict(schema='count14-approved-cold-carrier-DDL-equality-public-v1',approval=APPROVAL,
        proposal_manifest_sha256=PROPOSAL,sql_diff_sha256=SQL_DIFF,DDL_raw_sha256=DDL_RAW,
        old_queue_schema_equal=True,old_queue_rows_equal=True,old_event_prefix_equal=True,
        ledger_all_old_schema_rows_and_events_equal=True,new_tables=[AUTH,JOBS],new_trigger_count=5,
        old_queue_schema_sha256=digest(before['queue_schema']),old_queue_rows_sha256=digest(before['queue_rows']),
        ledger_schema_sha256=digest(before['ledger_schema']),ledger_rows_sha256=digest(before['ledger_rows']),
        old_table_row_counts={k:len(v)for k,v in before['queue_rows'].items()},
        offline_OWN=production_guard is None,production_install_authorized=production_guard is not None,models=0)


def lock_identity(p,fd):
    p=Path(p);a=p.lstat();b=os.fstat(fd)
    need(p.resolve()==p and not p.is_symlink() and(a.st_dev,a.st_ino)==(b.st_dev,b.st_ino),
         'APPROVED_CARRIER_EXACT_ORIGINAL_OWNER_LOCK_INODE')
    probe=os.open(p,os.O_RDWR|os.O_NOFOLLOW)
    try:
        try:fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:pass
        else:
            fcntl.flock(probe,fcntl.LOCK_UN)
            need(False,'APPROVED_CARRIER_ORIGINAL_OWNER_LOCK_MUST_BE_HELD')
    finally:os.close(probe)
    return dict(path=str(p),dev=a.st_dev,inode=a.st_ino)


def guard(owner,cohort,control):
    from native_cold_owner import NativeColdOwner
    from native_formal_cohort import NativeFormalCohort
    from original_relay_core import OriginalRelayCore
    from allowance_control import FormalAllowanceControl
    from native_peer_registry import process_birth
    need(type(owner)is NativeColdOwner and type(cohort)is NativeFormalCohort and
         type(control)is FormalAllowanceControl and type(owner.core)is OriginalRelayCore and
         cohort.owner is owner and cohort.core is owner.core is control.core and control.owner is owner and
         owner.scientific_smoke is cohort and owner.ledger is owner.core.ledger,
         'APPROVED_CARRIER_EXACT_SAME_NATIVE_OWNER_CORE_COHORT_CONTROL')
    core=owner.core;control.fresh();validate_contract(core.contract,digest(core.contract))
    need(not owner.errors and not core.qualification_only and not core.closed and not cohort.activation_attempted and
         cohort.final is None and cohort.source_ports is None and
         set(core.gate.startup_held)==set(core.rows)and cohort.birth==process_birth(os.getpid()) and
         control.birth==process_identity(os.getpid()) and type(core.queue)is FinalQueue and type(core.ledger)is Ledger,
         'APPROVED_CARRIER_ALL_HELD_FRESH_PID_START_BOOT_ZERO_MODEL_BOUNDARY')
    home=Path(core.contract['arms'][0]['root'])/'owner'
    need(core.home==home and core.ledger.home==home/'ledger'and core.queue.home==home/'final-queue'and
         core.queue.manifest==digest(core.contract)and core.queue.cap==12,
         'APPROVED_CARRIER_ORIGINAL_REGISTERED_NEW_FORMAL_ROOTS_ONLY')
    for row in core.rows.values():
        p=Path(row['root']);need(p.resolve()==p and p.is_dir()and not p.is_symlink() and
            (p.is_relative_to('/mnt/ptb-scratch2')or p.is_relative_to('/mnt/ptb-scratch')),
            'APPROVED_CARRIER_CANONICAL_REGISTERED_NEW_SCRATCH_TRAJECTORIES')
    locks=[lock_identity(core.ledger.home/'owner.lock',core.ledger.fd),
           lock_identity(core.queue.home/'owner.lock',core.queue.fd)]
    return core,locks


def install(owner,cohort,control,*,input_verifier):
    core,locks=guard(owner,cohort,control);q,l=core.queue,core.ledger
    need(not hasattr(core,'formal_approved_carrier_domain')and callable(input_verifier),
         'APPROVED_CARRIER_ONE_NEW_DOMAIN_NO_REAPPLY')
    domain=CarrierQueueDomain(control);core.formal_approved_carrier_domain=domain # retain before fallible work
    domain.home=private_dir(core.home/'final-control-carrier-approved-v1',create=True)
    need(not any(domain.home.iterdir()),'APPROVED_CARRIER_NEW_EMPTY_HOST_METADATA_HOME')
    with l.mutex,q.mutex:receipt=execute_exact_ddl(l,q,production_guard=(owner,cohort,control))
    again,after_locks=guard(owner,cohort,control)
    need(again is core and after_locks==locks,'APPROVED_CARRIER_POST_DDL_FRESH_SAME_OWNER_LOCK_BIRTH_GUARDS')
    receipt.update(offline_OWN=False,production_install_authorized=True,owner=control.birth,locks=locks,
        fresh_PID_start_boot_and_lock_guards_before_and_after=True)
    rp=domain.home/'APPROVED_INSTALL_PUBLIC.json';publish(rp,wire(receipt),mode=0o400)
    domain._bind_private_original_ports(input_verifier)
    value=dict(schema=SCHEMA,offline_OWN=False,production_install_authorized=True,owner=domain.owner,
        home=str(domain.home),core_home=str(core.home),queue_home=str(q.home),ledger_home=str(l.home),
        contract_sha256=digest(core.contract),policy=POLICY,original_kernel_paths=domain.kernels.source_paths,
        original_kernel_sha256=domain.kernels.source_sha256,control_source_sha256=proposal_pins(),
        approved_source_sha256=approved_source_pins(),approval=APPROVAL,proposal_manifest_sha256=PROPOSAL,
        sql_diff_sha256=SQL_DIFF,installed_receipt_sha256=hash_file(rp)['sha256'],
        carrier_table=JOBS,authorization_table=AUTH,DDL_sha256=digest(DDL),
        native_raw_domain='ONLY_ACTUAL_HOST_POLICY_AUTHORIZED_RAW_GE4',original_financial_schema_changed=False)
    domain.descriptor=domain.home/'QUEUE_CONTROL_DOMAIN_PUBLIC.json'
    publish(domain.descriptor,wire(value),mode=0o400);domain.pin=hash_file(domain.descriptor)['sha256']
    domain.installed=True
    return domain
