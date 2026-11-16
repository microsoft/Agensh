"""Pinned original actual-n policy and V4 PUBLIC-only proof/statistics kernels."""
import ast,copy,json,statistics
from pathlib import Path
from types import SimpleNamespace
from common import need,digest,sha,hash_file

SIDECAR_SHA='91b7a93714695572aae5ef5dd1419b3bca84fcd730ec4a9d145defbda581c000'
NATIVE_PARTIAL_POLICY='USER_20261027_K3_SINGLE_REPLICATE_MAX_TWO_REPLACEMENTS'
METRICS=('unique_candidates','correct_candidates','successful_tasks','maximum_one_to_one_matches')


class WaitForEvidence(Exception):pass


def load_public_rules(path,original_kernels):
    p=Path(path);need(p.is_absolute()and p.resolve()==p and hash_file(p)['sha256']==SIDECAR_SHA,
        'FORMAL_NLT3_ORIGINAL_V4_KERNEL_PIN')
    tree=ast.parse(p.read_text());names={'pin','integer','waited','failed','financial_disposition'}
    nodes=[copy.deepcopy(n)for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in names]
    need({n.name for n in nodes}==names,'FORMAL_NLT3_EXACT_ORIGINAL_PUBLIC_KERNELS')
    space=dict(json=json,digest=digest,POLICY=NATIVE_PARTIAL_POLICY,
        need=lambda ok:need(ok,'FORMAL_NLT3_ORIGINAL_PUBLIC_PROOF_REFUSED'))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),space)
    return SimpleNamespace(**space,policy=original_kernels.policy,
        original_sidecar_sha256=SIDECAR_SHA,original_policy_sha256=original_kernels.source_sha256['policy'])


def select_terminal(snapshot,rules):
    """All actual slots/attempts, not raw-count maximum or selected best score.

    snapshot is captured by the SAME host from real queue/financial control
    metadata. This pure function cannot authorize/construct/replay a job.
    """
    rows=snapshot['rows'];partials=snapshot['partials'];selected=[];excluded=[];decisions={}
    need(len({r['id']for r in rows})==len(rows)and {r['replicate']for r in rows}=={1,2,3},
         'FORMAL_NLT3_ALL_THREE_ORIGINAL_SLOTS')
    for k in(1,2,3):
        group=sorted((r for r in rows if r['replicate']==k),key=lambda r:r.get('attempt',1));chain=[];valid=[]
        for r in group:
            if r['state']not in('CHILD_EXITED_HOLD','COMPLETE')or not snapshot['wait_events'].get(r['id']):
                raise WaitForEvidence('NATURAL_ORIGINAL_WAIT_NOT_YET_PROVEN')
            terminal=rules.waited(r);a=r.get('attempt',1)
            row=dict(point_id=r['point'],replicate_id=k,attempt=a,job_id=r['id'],state=r['state'])
            grant=snapshot['last_extra_grants'].get(r['id'])
            if grant is not None:row.update(last_extra=True,last_extra_grant_sha256=grant)
            if r['id']in partials:
                p=partials[r['id']];excluded.append(rules.failed(r,terminal,p))
                proof=dict(job_id=r['id'],point_id=r['point'],scope=p['scope'],original_claim=r['claim'],
                    custody_proof_sha256=digest(terminal),terminal_sha256=digest(terminal),
                    proof_kind='GENUINE_FAILED_WAIT',wait_observed=True,native_request_count=p['native_request_count'],
                    native_aux_tokens=p['native_aux_tokens'],unknown_aux_reservation_charge=p.get('unknown_aux_reservation_charge',0))
                row.update(state='PARTIAL',failure_proof=proof)
                if r['id']in snapshot['tool_exemptions']:row['tool_exemption']=snapshot['tool_exemptions'][r['id']]
            else:
                if terminal['exit_code']!=0 or terminal['signal']is not None:
                    raise WaitForEvidence('FAILED_ORIGINAL_ATTEMPT_NOT_YET_DISPOSED')
                valid.append(r)
            chain.append(row)
        decision=rules.policy.decide_attempts(chain,original_limit=3);decisions[str(k)]=decision
        need(len(valid)<=1,'FORMAL_NLT3_NO_SCORE_OR_ATTEMPT_SELECTION')
        if valid:
            need(valid[0]['id']==group[-1]['id'],'FORMAL_NLT3_NO_LATER_ATTEMPT_AFTER_SUCCESS')
            selected.extend(valid)
        elif decision['terminal']is not True:
            raise WaitForEvidence('APPROVED_CONSUMED_ALLOWANCE_OR_EXTRA_NOT_EXHAUSTED')
    return dict(selected=selected,excluded=excluded,decisions=decisions,n=len(selected))


def bind_committed_metadata(*,trajectory,target,point,row,checkpoint_entry,committed_rows,initial_jobs,
                            policy,policy_pin,saved,saved_pin):
    """No POINT_QUEUED file. Bind ORIGINAL checkpoint memory + Ledger.snapshots.

    Caller first authenticates exact original CP/core/queue and reads only fixed
    PUBLIC input-policy/saved metadata. No capture/build/seal is made here.
    """
    e=checkpoint_entry;ref=e['snapshot']
    need(point==digest(dict(trajectory=trajectory,target=target))and row['trajectory']==trajectory and
        row['target']==target and e['target_tokens']==target and e['input_policy_sha256']==row['input_policy']and
        policy_pin['sha256']==row['input_policy']and e['jobs']==initial_jobs,
        'FORMAL_NLT3_REAL_CHECKPOINT_QUEUE_INPUT_BINDING')
    need(committed_rows==[(trajectory,e['generation'],target,ref['sha256'])],
        'FORMAL_NLT3_ORIGINAL_LEDGER_COMMITTED_SNAPSHOT_REQUIRED')
    need(policy['trajectory']==trajectory and policy['setting']==row['setting']and policy['target_tokens']==target and
        policy['generation']==e['generation']and policy['snapshot_sha256']==ref['sha256']and
        saved['original_snapshot_sha256']==ref['sha256']and saved['nominal_budget']==target and
        policy['saved']==saved_pin,'FORMAL_NLT3_POLICY_SAVED_ORIGINAL_COMMITTED_SNAPSHOT')
    return dict(trajectory=trajectory,target_tokens=target,point_id=point,generation=e['generation'],
        original_snapshot=ref,original_checkpoint_jobs=initial_jobs,input_policy_sha256=row['input_policy'],
        input_policy=policy_pin,saved=saved_pin,original_committed_row_sha256=digest(committed_rows),
        POINT_QUEUED_not_required_or_created=True,recapture_or_rebuild=False)


def original_statistics(records):
    # Exact same original V4 fmean/min/max expressions; no union/matrix work.
    n=len(records)
    return dict(means={m:statistics.fmean(r[m]for r in records)for m in METRICS}if n else None,
        ranges={m:[min(r[m]for r in records),max(r[m]for r in records)]for m in METRICS}if n else None)
