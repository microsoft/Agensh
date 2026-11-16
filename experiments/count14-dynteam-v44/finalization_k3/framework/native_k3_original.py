"""Original native v2.1 summary functions only; bootstrap is independently bound."""
def graph(directory,task_count=14):
    entries=index(directory);edges={};tasks={}
    for h,cid in entries.items():
        edges[h]=set()
        for i in range(1,task_count+1):
            v=cell(pathlib.Path(directory),cid,i,h)
            if v['state']!='valid':raise MetadataError('Incomplete or infrastructure-ambiguous evaluation matrix')
            if i in tasks and tasks[i]!=v['task']:raise MetadataError('Mixed task order')
            tasks[i]=v['task']
            if v['success']:edges[h].add(i)
    return edges,tasks

def metrics(edges):
    match={}
    def assign(h,seen):
        for task in sorted(edges[h]):
            if task in seen:continue
            seen.add(task)
            if task not in match or assign(match[task],seen):match[task]=h;return True
        return False
    for h in sorted(edges):assign(h,set())
    return dict(unique_candidates=len(edges),correct_candidates=sum(bool(v) for v in edges.values()),successful_tasks=len(set().union(*edges.values())) if edges else 0,maximum_one_to_one_matches=len(match))

def aggregate_runs(records,graphs):
    if len(records)!=3 or len(graphs)!=3 or any(not r.get('complete') or not r.get('evaluation_complete') for r in records):raise ValueError('Three complete independently evaluated runs required')
    for key in ('protocol_sha256','source_sha256','initial_input_sha256','frozen_catalog_sha256'):
        if None in {r.get(key) for r in records} or len({r[key] for r in records})!=1:raise ValueError('K3 protocol/input/catalog mismatch')
    if sorted(r['replicate_index'] for r in records)!=[1,2,3]:raise ValueError('Wrong replicate identities')
    values={k:[r[k] for r in records] for k in METRICS}
    all_hashes=set().union(*(g.keys() for g in graphs));upper={};lower={};disagreements=0
    for h in all_hashes:
        observations=[g[h] for g in graphs if h in g];upper[h]=set.union(*observations);lower[h]=set.intersection(*observations)
        disagreements+=len(upper[h]-lower[h])
    return dict(means={k:statistics.fmean(v) for k,v in values.items()},ranges={k:[min(v),max(v)] for k,v in values.items()},
        observed_union_reference=metrics(upper),observed_union_consensus_lower=metrics(lower),union_task_disagreements=disagreements,
        union_is_not_main_score=True,union_is_not_new_evaluation=True,range_is_not_confidence_interval=True,
        finalization_tokens=sum(r['finalization_tokens'] for r in records),finalization_reported_tokens=sum(r['finalization_reported_tokens'] for r in records),
        finalization_conservatively_charged_tokens=sum(r['finalization_conservatively_charged_tokens'] for r in records),unknown_requests=sum(r['unknown_requests'] for r in records))
