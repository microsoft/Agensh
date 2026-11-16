"""Trusted metadata-only failed-K disposition and fresh independent attempt roots."""
from pathlib import Path
import json,os,sqlite3
from common import need,digest,wire,strict,hash_file,private_dir,publish,regular_fd
import final_attempts


def prepare(configuration,job):
    attempt=job.get('attempt',1);base=Path(configuration['aux_root'])
    if attempt==1:return configuration,base
    root=base/'replacement-attempts'/f"k{job['replicate']}-a{attempt}"
    private_dir(base/'replacement-attempts',create=True)
    need(not root.exists() and not root.is_symlink(),'FINAL_REPLACEMENT_NEW_AUX_ROOT')
    private_dir(root,create=True)
    from run_native_scientific6 import _copy_opaque
    ev=private_dir(root/'evaluator-private',create=True);cr=private_dir(root/'credentials',create=True)
    for name,pin in configuration['profile']['evaluator_assets'].items():
        _copy_opaque(base/'evaluator-private'/name,ev/name,pin['sha256'])
    _copy_opaque(base/'credentials'/'glm_api_key',cr/'glm_api_key')
    configuration.update(aux_root=str(root),replicate_attempt=attempt,point_id=job['point'])
    return configuration,base


def custody(path):
    need(path.is_file()and path.resolve()==path,'FINAL_FAILED_EVALUATOR_CUSTODY_REQUIRED')
    # Existing immutable child DB, opened read-only. No task/command/output.
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
    try:
        counts={r[0]:r[1] for r in db.execute('SELECT state,COUNT(*) FROM scopes GROUP BY state')}
    finally:db.close()
    return sum(v for k,v in counts.items() if k!='REMOVED'),digest(counts)


def proof(dispatcher,record):
    job=record['job'];scope=record['scope'];terminal=record['terminal']
    need(terminal is not None and record['child'] is not None
         and record['child'].returncode is not None,'FINAL_FAILED_ORIGINAL_POPEN_WAIT')
    with dispatcher.ledger.mutex:
        permits=[dict(r) for r in dispatcher.ledger.db.execute('SELECT request_id,state FROM aux_permits WHERE scope=?',(scope,))]
    unresolved=sum(p['state'] in ('RESERVED','SENT','UNKNOWN') for p in permits)
    need(unresolved==0,'FINAL_PARTIAL_UNRESOLVED_CUSTODY')
    root=Path(record['config']['aux_root']);branch=root/f"k{job['replicate']}";ledger=branch/'ledger.json'
    expected={p['request_id'] for p in permits if p['request_id'] is not None}
    if ledger.exists():
        data=strict(ledger.read_bytes());requests=data.get('requests')
        need(data.get('setting')=='single' and type(requests)is dict,'FINAL_FAILED_NATIVE_LEDGER')
        need(set(requests)==expected,'FINAL_FAILED_LEDGER_HOST_REQUEST_SET')
        total=0
        for rid,row in requests.items():
            need(row.get('role')=='single'and row.get('state') in ('COMPLETED','UNKNOWN_CHARGED','REJECTED_PREGEN','RETRYABLE_REJECTED') and type(row.get('tokens'))is int and row['tokens']>=0,'FINAL_FAILED_NATIVE_SETTLEMENT')
            total+=row['tokens']
        need(data.get('actual_tokens')==total and data.get('model_calls')==len(requests),'FINAL_FAILED_NATIVE_COST')
        book=branch/'ledger.json.reservations-v52.json'
        if book.exists():
            b=strict(book.read_bytes());need(b.get('active')=={} and b.get('halted') is False,'FINAL_FAILED_NATIVE_RESERVATIONS')
        else:need(not requests,'FINAL_FAILED_RESERVATIONS_MISSING')
        pin=hash_file(ledger)['sha256']
    else:
        need(not permits,'FINAL_FAILED_MISSING_LEDGER_HAS_PERMITS');total=0;pin=digest({'native_ledger_absent':True})
    cp=root/f"evaluator-custody-k{job['replicate']}"/'custody.sqlite'
    if cp.exists():eu,ep=custody(cp)
    else:
        need(not permits,'FINAL_FAILED_MISSING_EVALUATOR_CUSTODY_AFTER_MODEL');eu=0;ep=digest({'evaluator_not_started':True})
    need(eu==0,'FINAL_PARTIAL_UNRESOLVED_EVALUATOR_CUSTODY')
    return {'scope':scope,'model_unresolved':unresolved,'evaluator_unresolved':eu,
            'native_aux_tokens':total,'native_request_count':len(expected),'request_ids_sha256':digest(sorted(expected)),
            'native_ledger_sha256':pin,'terminal_sha256':digest(terminal),'evaluator_proof_sha256':ep}


def dispose(dispatcher,record):
    q=dispatcher.queue;job=record['job'];p=proof(dispatcher,record)
    # Allocation is separate from unchanged search accounts and native charges.
    # Same key + exact receipt makes crash/reentry idempotent, never double bills.
    row={'job_id':job['id'],'claim':job['claim'],'point_id':job['point'],
         'replicate_id':job['replicate'],'attempt':job.get('attempt',1),'policy':final_attempts.POLICY,
         'allocation':'SYSTEM_CONSUMPTION','billing_domain':'AUX_FINALIZATION','search_budget_delta':0,**p}
    l=dispatcher.ledger
    with l.tx():
        l.db.execute('CREATE TABLE IF NOT EXISTS aux_attempt_allocations(job_id TEXT PRIMARY KEY,metadata TEXT NOT NULL)')
        for action in ('UPDATE','DELETE'):
            l.db.execute(f"CREATE TRIGGER IF NOT EXISTS no_{action.lower()}_aux_attempt_allocation BEFORE {action} ON aux_attempt_allocations BEGIN SELECT RAISE(ABORT,'append only'); END")
        old=l.db.execute('SELECT metadata FROM aux_attempt_allocations WHERE job_id=?',(job['id'],)).fetchone()
        if old is not None:need(json.loads(old[0])==row,'FINAL_FAILED_SYSTEM_ALLOCATION_CHANGED')
        else:
            l.db.execute('INSERT INTO aux_attempt_allocations VALUES(?,?)',(job['id'],wire(row).decode()))
            l.event(job['trajectory'],'AUX_FAILED_REPLICATE_SYSTEM_CONSUMPTION',row)
    new=final_attempts.partial_and_replace(q,job['id'],job['claim'],proof=p)
    record['partial']=True;record['replacement_job_id']=new
    need(new is not None,'FINAL_REPLICATE_TWO_REPLACEMENTS_EXHAUSTED')
    return new


def selected(dispatcher,point):
    q=dispatcher.queue
    with q.mutex:effective={r['id'] for r in final_attempts.effective_rows(q)}
    rows=[dispatcher.children[k] for k in point['jobs'] if k in effective]
    if len(rows)!=3:return None
    rows.sort(key=lambda r:r['job']['replicate'])
    need([r['job']['replicate'] for r in rows]==[1,2,3],'FINAL_EFFECTIVE_REPLICATE_IDENTITIES')
    if any(r['terminal']is None for r in rows):return None
    need(all(r['terminal']['exit_code']==0 and r['terminal']['signal']is None for r in rows),'FINAL_EFFECTIVE_FAILED_NOT_AUDITABLE')
    return rows


def paths(rows,label,setting):
    return [{'branch':Path(r['config']['aux_root'])/f'k{k}',
             'aggregate':Path(r['config']['aux_root'])/'results'/setting/(label+f'-k{k}')/'aggregate.json',
             'matrix':Path(r['config']['aux_root'])/'evaluator-private'/setting/(label+f'-k{k}'),
             'custody':Path(r['config']['aux_root'])/f'k{k}'/'physical-custody.json',
             **({'attempt':r['job']['attempt']} if r['job'].get('attempt',1)>1 else {})}
             for k,r in enumerate(rows,1)]
