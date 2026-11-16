"""Read-only metadata comparison. Never outputs hashes, paths, IDs or content.
Result bodies are not opened; only candidate-index and result.json metadata.
No evaluator, model, network or subprocess is invoked.
"""
import collections,datetime,hashlib,json,pathlib,re,sys

class MetadataError(RuntimeError):pass
def read(path,root):
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):raise MetadataError('Linked/outside metadata')
    return json.loads(path.read_text()) if path.is_file() else None

def index(directory):
    rows=read(directory/'candidate-index.json',directory)
    if not isinstance(rows,list):raise MetadataError('Missing candidate index')
    out={}
    for r in rows:
        sha=r.get('sha256');cid=r.get('candidate_id')
        if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha) or not isinstance(cid,str) or not re.fullmatch(r'C\d{2,9}',cid):raise MetadataError('Malformed candidate identity')
        if sha in out or cid in out.values():raise MetadataError('Duplicate index identity')
        out[sha]=cid
    return out

def retries(row):
    modes=row.get('modes')
    if not isinstance(modes,dict):return None
    return any((v.get('startup_failures',0)>0 or len(v.get('attempts',[]))>1) for v in modes.values() if isinstance(v,dict))

def cell(directory,cid,task,expected):
    root=directory/cid/f'T{task:02d}'
    initial=read(root/'initial/result.json',directory);recheck=read(root/'infrastructure-recheck/result.json',directory)
    if initial is None:return dict(state='missing',retried=recheck is not None)
    for r in (initial,recheck):
        if r is None:continue
        if r.get('poc_sha256')!=expected or type(r.get('success')) is not bool or type(r.get('infrastructure_error')) is not bool or not r.get('completed_at') or not isinstance(r.get('task_id'),str):raise MetadataError('Incomplete or inconsistent pair metadata')
        if r['success'] and r['infrastructure_error']:raise MetadataError('Infrastructure outcome cannot be success')
    if recheck is not None and not initial['infrastructure_error']:raise MetadataError('Unexpected infrastructure recheck')
    if recheck is not None and recheck['task_id']!=initial['task_id']:raise MetadataError('Recheck task identity differs')
    final=recheck if recheck is not None else initial
    retry=recheck is not None or retries(initial) is True or retries(final) is True
    if not retry and (retries(initial) is None or retries(final) is None):retry=None
    return dict(state='infra' if final['infrastructure_error'] else 'valid',success=final['success'],task=final['task_id'],retried=retry,
                initial_state='infra' if initial['infrastructure_error'] else 'pass' if initial['success'] else 'fail')

def compare(left,right,task_count=14):
    left,right=pathlib.Path(left),pathlib.Path(right)
    if left.resolve()==right.resolve():raise MetadataError('Distinct independent evaluations required')
    a,b=index(left),index(right);shared=sorted(set(a)&set(b));counts=collections.Counter()
    for digest in shared:
        for i in range(1,task_count+1):
            x,y=cell(left,a[digest],i,digest),cell(right,b[digest],i,digest)
            if 'missing' in (x['state'],y['state']):counts['missing_pairs']+=1;continue
            if x['task']!=y['task']:counts['task_identity_mismatch']+=1;continue
            counts['initial_state_agree' if x['initial_state']==y['initial_state'] else 'initial_state_differ']+=1
            if 'infra' in (x['state'],y['state']):counts['unresolved_infrastructure_pairs']+=1;continue
            counts['comparable_pairs']+=1
            equal=x['success']==y['success'];counts['consistent' if equal else 'inconsistent']+=1
            if not equal:
                key='inconsistent_with_infrastructure_retry' if x['retried'] or y['retried'] else 'inconsistent_retry_unknown' if x['retried'] is None or y['retried'] is None else 'inconsistent_without_infrastructure_retry'
                counts[key]+=1
            if x['retried'] or y['retried']:counts['comparable_with_infrastructure_retry']+=1
    keys=('comparable_pairs','consistent','inconsistent','inconsistent_with_infrastructure_retry','inconsistent_without_infrastructure_retry','inconsistent_retry_unknown','missing_pairs','task_identity_mismatch','unresolved_infrastructure_pairs','initial_state_agree','initial_state_differ','comparable_with_infrastructure_retry')
    return dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),left_candidates=len(a),right_candidates=len(b),common_sha_count=len(shared),expected_pair_comparisons=len(shared)*task_count,**{k:counts[k] for k in keys},
                inference='Agreement on this shared-hash sample does not prove universal evaluator determinism; retry association is not causation.',read_only=True,model_requests=0,evaluator_invocations=0,content_read=False)

if __name__=='__main__':
    try:print(json.dumps(compare(pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2])),indent=2))
    except Exception as e:print(json.dumps(dict(error_type=type(e).__name__,read_only=True)));raise SystemExit(2)
