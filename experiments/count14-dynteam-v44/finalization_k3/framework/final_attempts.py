"""Append-only replicate dispositions, separate replacement jobs (attempt2/3).

Original jobs/claims/request records are never rewritten to PARTIAL. The
PARTIAL overlay is append-only; effective K3 selects one attempt per replicate,
never individual scores. Only an observed failed child with zero physical AUX
and evaluator custody may be released for a replacement. No search-budget debit.
"""
import json,time
from common import need,digest,wire,integer
POLICY='USER_20261027_K3_SINGLE_REPLICATE_MAX_TWO_REPLACEMENTS'
RNG_POLICY={'schema':'agensh-replicate-attempt-rng-v1','tuple':['point_id','replicate_id','attempt'],
            'algorithm':'SHA256 canonical wire + seed + action_index; first32bits',
            'attempt1':'unchanged-original-RNG'}


def initialize(q):
    with q.mutex:
        q.db.executescript('''
        CREATE TABLE IF NOT EXISTS replacement_jobs(id TEXT PRIMARY KEY,point TEXT NOT NULL REFERENCES points,
          replicate INTEGER NOT NULL,state TEXT NOT NULL,claim TEXT,child TEXT,terminal TEXT,result TEXT,
          attempt INTEGER NOT NULL CHECK(attempt IN (2,3)),original_job TEXT NOT NULL REFERENCES jobs,
          UNIQUE(point,replicate,attempt));
        CREATE TABLE IF NOT EXISTS replicate_partials(job_id TEXT PRIMARY KEY,metadata TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS no_update_replicate_partial BEFORE UPDATE ON replicate_partials
          BEGIN SELECT RAISE(ABORT,'append only'); END;
        CREATE TRIGGER IF NOT EXISTS no_delete_replicate_partial BEFORE DELETE ON replicate_partials
          BEGIN SELECT RAISE(ABORT,'append only'); END;''')


def table(q,job):
    return 'jobs' if q.db.execute('SELECT 1 FROM jobs WHERE id=?',(job,)).fetchone() else 'replacement_jobs'


def replacement_job(q,job):
    r=q.db.execute('SELECT r.*,p.trajectory,p.setting,p.target,p.input_root,p.input_policy FROM replacement_jobs r JOIN points p ON r.point=p.point WHERE r.id=?',(job,)).fetchone()
    need(r is not None,'FINAL_JOB_UNKNOWN');return dict(r)


def all_rows(q):
    ids=[r[0] for r in q.db.execute('SELECT id FROM jobs ORDER BY rowid')]
    ids += [r[0] for r in q.db.execute('SELECT id FROM replacement_jobs ORDER BY rowid')]
    return [q._job(i) for i in ids]


def live_rows(q):
    partials={r[0] for r in q.db.execute('SELECT job_id FROM replicate_partials')}
    return [r for r in all_rows(q) if r['id'] not in partials]


def effective_rows(q):
    selected={};partials={r[0] for r in q.db.execute('SELECT job_id FROM replicate_partials')}
    for r in all_rows(q):
        k=(r['point'],r['replicate'])
        if k not in selected or r.get('attempt',1)>selected[k].get('attempt',1):selected[k]=r
    return [{**r,'state':'PARTIAL' if r['id'] in partials else r['state']} for r in selected.values()]


def frontier(q):
    result={}
    for r in effective_rows(q):result[r['state']]=result.get(r['state'],0)+1
    return result


def request_rng(seed,point_id,replicate_id,attempt,action_index):
    need(type(attempt)is int and attempt in (2,3),'FINAL_REPLACEMENT_ATTEMPT')
    key={'schema':'agensh-replicate-attempt-rng-v1','point_id':point_id,'replicate_id':replicate_id,
         'attempt':attempt,'seed':seed,'action_index':action_index}
    h=digest(key);return {'seed':int(h[:8],16),'key_sha256':h}


def partial_and_replace(q,job_id,claim,*,proof):
    """One host-only transaction. Repeating same disposition returns existing ID,
    never enqueues twice. Proof is made from original Popen + pinned metadata by
    dispatcher, not accepted from child RPC/worker input.
    """
    with q.tx():
        job=q._job(job_id);attempt=job.get('attempt',1)
        need(job['state']=='CHILD_EXITED_HOLD' and job['claim']==claim,'FINAL_PARTIAL_ORIGINAL_FAILED_CLAIM')
        t=json.loads(job['terminal']);need(t['wait_observed'] is True and (t['exit_code']!=0 or t['signal'] is not None),'FINAL_PARTIAL_REAL_FAILED_TERMINAL')
        need(type(proof)is dict and set(proof)=={'scope','model_unresolved','evaluator_unresolved','native_aux_tokens','native_request_count','request_ids_sha256','native_ledger_sha256','terminal_sha256','evaluator_proof_sha256'},'FINAL_PARTIAL_PROOF_FIELDS')
        need(proof['model_unresolved']==proof['evaluator_unresolved']==0,'FINAL_PARTIAL_UNRESOLVED_CUSTODY')
        need(proof['terminal_sha256']==digest(t),'FINAL_PARTIAL_TERMINAL_CHANGED')
        for k in ('native_aux_tokens','native_request_count'):integer(proof[k],'FINAL_PARTIAL_COST_INTEGER')
        metadata={'policy':POLICY,'point_id':job['point'],'replicate_id':job['replicate'],'attempt':attempt,
                  'original_claim':claim,'disposition':'PARTIAL','allocation':'SYSTEM_CONSUMPTION',
                  'billing_domain':'AUX_FINALIZATION','search_budget_delta':0,**proof}
        old=q.db.execute('SELECT metadata FROM replicate_partials WHERE job_id=?',(job_id,)).fetchone()
        if old is not None:need(json.loads(old[0])==metadata,'FINAL_PARTIAL_PROOF_CHANGED')
        else:
            q.db.execute('INSERT INTO replicate_partials VALUES(?,?)',(job_id,wire(metadata).decode()))
            q.event('REPLICATE_PARTIAL_SYSTEM_CONSUMPTION',{'job_id':job_id,**metadata})
        if attempt>=3:return None
        nxt=attempt+1;new=digest({'point':job['point'],'replicate':job['replicate'],'attempt':nxt})
        old=q.db.execute('SELECT * FROM replacement_jobs WHERE id=?',(new,)).fetchone()
        if old is None:
            q.db.execute("INSERT INTO replacement_jobs VALUES(?,?,?,'QUEUED',NULL,NULL,NULL,NULL,?,?)",
                (new,job['point'],job['replicate'],nxt,job.get('original_job',job_id)))
            q.event('ONE_REPLICATE_REPLACEMENT_ENQUEUED',{'job_id':new,'failed_job_id':job_id,
                'point_id':job['point'],'replicate_id':job['replicate'],'attempt':nxt,
                'rng_policy_sha256':digest(RNG_POLICY),'new_requests_required':True,'billing_domain':'AUX_FINALIZATION',
                'search_budget_delta':0,'policy':POLICY})
        return new
